import logging
from openai import AsyncOpenAI
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate_script(topic: str) -> str:
    """Generate a 30-second video narration script via GPT-4."""
    prompt = (
        f"Напиши текст для закадрового голоса видеоролика длиной ровно 30 секунд на тему: «{topic}».\n\n"
        "Требования:\n"
        "- Текст для голосового прочтения (не субтитры, не заголовки)\n"
        "- Разговорный стиль, энергичный, держит внимание\n"
        "- Примерно 70-90 слов (30 секунд при среднем темпе речи)\n"
        "- Начни с цепляющей фразы\n"
        "- Заверши призывом к действию или сильным выводом\n"
        "- Только чистый текст, без разметки, без нумерации"
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты профессиональный сценарист коротких вирусных видео для соцсетей."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.8
    )

    script = response.choices[0].message.content.strip()
    logger.info(f"Generated script ({len(script.split())} words): {script[:100]}...")
    return script


async def generate_search_keywords(topic: str, script: str) -> list[str]:
    """Generate search keywords for stock footage."""
    prompt = (
        f"Тема видео: «{topic}»\n"
        f"Текст озвучки: {script[:300]}\n\n"
        "Дай 6 коротких поисковых запросов на АНГЛИЙСКОМ для поиска стокового видео.\n"
        "Каждый запрос — 1-3 слова, для визуального контента.\n"
        "Формат: одно слово/фраза в строке, без нумерации."
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.5
    )

    keywords = [
        line.strip()
        for line in response.choices[0].message.content.strip().split("\n")
        if line.strip()
    ]
    logger.info(f"Keywords: {keywords}")
    return keywords[:6]
