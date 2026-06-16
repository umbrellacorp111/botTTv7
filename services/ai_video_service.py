import os
import asyncio
import logging
import aiohttp
import aiofiles
import base64
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, TEMP_DIR, CLIP_DURATION, VIDEO_DURATION, VIDEO_WIDTH, VIDEO_HEIGHT, FPS
from services.ffmpeg_helper import get_ffmpeg_path
from services.script_generator import generate_search_keywords

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

CLIPS_NEEDED = VIDEO_DURATION // CLIP_DURATION
FFMPEG = get_ffmpeg_path()


async def generate_ai_clips(topic: str, script: str) -> list[str]:
    """
    Generate AI video clips using DALL-E 3 images animated with Ken Burns effect.
    Returns list of .mp4 paths.
    """
    keywords = await generate_search_keywords(topic, script)
    image_prompts = await _build_image_prompts(topic, keywords)

    # Generate images in parallel
    tasks = [_generate_image(prompt, i) for i, prompt in enumerate(image_prompts[:CLIPS_NEEDED])]
    image_paths = await asyncio.gather(*tasks, return_exceptions=True)

    valid_images = [p for p in image_paths if isinstance(p, str) and os.path.exists(p)]
    if not valid_images:
        raise RuntimeError("Не удалось сгенерировать изображения через ИИ.")

    # Animate each image into a video clip
    tasks = [_image_to_video(img_path, i) for i, img_path in enumerate(valid_images)]
    clip_paths = await asyncio.gather(*tasks, return_exceptions=True)

    valid_clips = [p for p in clip_paths if isinstance(p, str) and os.path.exists(p)]
    if not valid_clips:
        raise RuntimeError("Не удалось создать видеоклипы из изображений.")

    logger.info(f"Generated {len(valid_clips)} AI clips")
    return valid_clips


async def _build_image_prompts(topic: str, keywords: list[str]) -> list[str]:
    """Ask GPT to build cinematic image prompts."""
    keyword_str = ", ".join(keywords)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Тема видео: «{topic}». Ключевые слова: {keyword_str}.\n\n"
                f"Создай {CLIPS_NEEDED} коротких промптов для DALL-E 3 на английском.\n"
                "Каждый промпт — одна кинематографичная сцена, фотореализм, 9:16 вертикальный кадр.\n"
                "Формат: одна строка на промпт, без нумерации."
            )
        }],
        max_tokens=400,
        temperature=0.7
    )
    prompts = [
        line.strip()
        for line in response.choices[0].message.content.strip().split("\n")
        if line.strip()
    ]
    return prompts[:CLIPS_NEEDED]


async def _generate_image(prompt: str, index: int) -> str:
    """Generate image via DALL-E 3 and save to disk."""
    path = os.path.join(TEMP_DIR, f"ai_img_{index}.png")
    try:
        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt + ", cinematic lighting, high quality, vertical 9:16",
            size="1024x1792",
            quality="standard",
            n=1,
            response_format="b64_json"
        )
        img_data = base64.b64decode(response.data[0].b64_json)
        async with aiofiles.open(path, "wb") as f:
            await f.write(img_data)
        logger.info(f"Image {index} generated: {len(img_data)} bytes")
        return path
    except Exception as e:
        logger.error(f"Image generation error {index}: {e}")
        return ""


async def _image_to_video(image_path: str, index: int) -> str:
    """Convert image to video with Ken Burns (zoom/pan) effect using ffmpeg."""
    output_path = os.path.join(TEMP_DIR, f"ai_clip_{index}.mp4")

    # Ken Burns: slow zoom in + slight pan, 5 seconds
    # zoompan filter: zoom from 1.0 to 1.3, pan across
    zoom_filter = (
        f"scale={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2},"
        f"zoompan=z='min(zoom+0.001,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={CLIP_DURATION * FPS}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
    )

    cmd = [
        FFMPEG, "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", zoom_filter,
        "-t", str(CLIP_DURATION),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-r", str(FPS),
        output_path
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error(f"ffmpeg error: {stderr.decode()[-500:]}")
        raise RuntimeError(f"ffmpeg failed for clip {index}")

    return output_path
