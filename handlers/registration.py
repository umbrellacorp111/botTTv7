import logging
import os
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from states import VideoCreation
from config import VOICES
from services.script_generator import generate_script
from services.tts_service import synthesize_speech
from services.video_builder import build_video
from services.stock_service import search_stock_videos
from services.ai_video_service import generate_ai_clips

logger = logging.getLogger(__name__)
router = Router()


def source_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Стоковые видео", callback_data="source_stock"),
            InlineKeyboardButton(text="🤖 ИИ-генерация", callback_data="source_ai"),
        ]
    ])


def voice_keyboard():
    buttons = []
    row = []
    for name, code in VOICES.items():
        row.append(InlineKeyboardButton(text=name, callback_data=f"voice_{code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я создаю короткие видео (30 сек) для Reels/Shorts.\n\n"
        "📹 Выбери источник видеоряда:",
        reply_markup=source_keyboard()
    )
    await state.set_state(VideoCreation.choosing_source)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Как пользоваться ботом:</b>\n\n"
        "1. /start — начать создание видео\n"
        "2. Выбери источник: стоки или ИИ-генерация\n"
        "3. Введи тему видео\n"
        "4. Выбери голос для озвучки\n"
        "5. Жди готовое видео 🎬\n\n"
        "<b>Форматы видео:</b>\n"
        "• 1080×1920 (вертикальное, для Reels/Shorts)\n"
        "• 30 секунд\n"
        "• Субтитры + монтаж с переходами",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено. Напиши /start чтобы начать заново.")


@router.callback_query(VideoCreation.choosing_source, F.data.in_(["source_stock", "source_ai"]))
async def choose_source(callback: CallbackQuery, state: FSMContext):
    source = "stock" if callback.data == "source_stock" else "ai"
    await state.update_data(source=source)

    source_label = "🎬 Стоковые видео" if source == "stock" else "🤖 ИИ-генерация"
    await callback.message.edit_text(
        f"✅ Выбрано: {source_label}\n\n"
        "📝 Введи тему видео:\n"
        "<i>Например: польза утренней пробежки, 5 лайфхаков для сна, история Рима</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(VideoCreation.entering_topic)


@router.message(VideoCreation.entering_topic)
async def enter_topic(message: Message, state: FSMContext):
    topic = message.text.strip()
    if len(topic) < 3:
        await message.answer("⚠️ Тема слишком короткая. Введи подробнее:")
        return
    if len(topic) > 200:
        await message.answer("⚠️ Тема слишком длинная (макс. 200 символов). Сократи:")
        return

    await state.update_data(topic=topic)
    await message.answer(
        f"✅ Тема: <b>{topic}</b>\n\n"
        "🎙 Выбери голос для озвучки:",
        parse_mode="HTML",
        reply_markup=voice_keyboard()
    )
    await state.set_state(VideoCreation.choosing_voice)


@router.callback_query(VideoCreation.choosing_voice, F.data.startswith("voice_"))
async def choose_voice(callback: CallbackQuery, state: FSMContext):
    voice_code = callback.data.replace("voice_", "")
    voice_name = next((k for k, v in VOICES.items() if v == voice_code), voice_code)

    await state.update_data(voice=voice_code, voice_name=voice_name)
    data = await state.get_data()

    await callback.message.edit_text(
        f"🎬 <b>Параметры видео:</b>\n\n"
        f"📹 Источник: {'Стоки' if data['source'] == 'stock' else 'ИИ-генерация'}\n"
        f"📝 Тема: {data['topic']}\n"
        f"🎙 Голос: {voice_name}\n\n"
        f"⏳ Создаю видео... Это займёт 1-3 минуты.",
        parse_mode="HTML"
    )
    await state.set_state(VideoCreation.generating)

    asyncio.create_task(process_video(callback.message, state, data, callback.bot))


async def process_video(message: Message, state: FSMContext, data: dict, bot):
    user_id = message.chat.id
    topic = data["topic"]
    source = data["source"]
    voice = data["voice"]

    status_msg = await bot.send_message(user_id, "⏳ Генерирую сценарий...")

    try:
        # Step 1: Generate script
        script = await generate_script(topic)
        logger.info(f"Script generated: {len(script)} chars")

        await bot.edit_message_text("🎙 Синтезирую речь...", chat_id=user_id, message_id=status_msg.message_id)

        # Step 2: TTS
        audio_path = await synthesize_speech(script, voice, user_id)
        logger.info(f"Audio: {audio_path}")

        await bot.edit_message_text("🔍 Ищу видеоматериалы...", chat_id=user_id, message_id=status_msg.message_id)

        # Step 3: Get video clips
        if source == "stock":
            clips_paths = await search_stock_videos(topic, script)
        else:
            clips_paths = await generate_ai_clips(topic, script)

        logger.info(f"Got {len(clips_paths)} clips")

        await bot.edit_message_text("🎬 Монтирую видео...", chat_id=user_id, message_id=status_msg.message_id)

        # Step 4: Build final video
        output_path = await build_video(
            clips=clips_paths,
            audio_path=audio_path,
            script=script,
            user_id=user_id
        )

        await bot.edit_message_text("📤 Отправляю видео...", chat_id=user_id, message_id=status_msg.message_id)

        # Step 5: Send video
        with open(output_path, "rb") as video_file:
            await bot.send_video(
                chat_id=user_id,
                video=video_file,
                caption=f"🎬 <b>{topic}</b>\n\n✅ Видео готово! Напиши /start для нового.",
                parse_mode="HTML",
                supports_streaming=True
            )

        await bot.delete_message(chat_id=user_id, message_id=status_msg.message_id)

        # Cleanup
        _cleanup_files([audio_path, output_path] + clips_paths)

    except Exception as e:
        logger.error(f"Video creation error: {e}", exc_info=True)
        await bot.edit_message_text(
            f"❌ Ошибка при создании видео:\n<code>{str(e)[:200]}</code>\n\nПопробуй /start снова.",
            chat_id=user_id,
            message_id=status_msg.message_id,
            parse_mode="HTML"
        )

    finally:
        await state.clear()


def _cleanup_files(paths: list):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
