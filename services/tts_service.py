import os
import logging
import aiohttp
from config import YANDEX_API_KEY, YANDEX_FOLDER_ID, TEMP_DIR

logger = logging.getLogger(__name__)

YANDEX_TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"


async def synthesize_speech(text: str, voice: str, user_id: int) -> str:
    """Synthesize speech via Yandex SpeechKit and return path to MP3 file."""
    output_path = os.path.join(TEMP_DIR, f"audio_{user_id}.mp3")

    # Yandex SpeechKit settings
    data = {
        "text": text,
        "lang": "ru-RU",
        "voice": voice,
        "emotion": "good",
        "speed": "1.05",        # slightly faster for dynamic feel
        "format": "mp3",
        "sampleRateHertz": "48000",
        "folderId": YANDEX_FOLDER_ID,
    }

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(YANDEX_TTS_URL, data=data, headers=headers) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"Yandex TTS error {resp.status}: {error_text}")

            audio_data = await resp.read()

    with open(output_path, "wb") as f:
        f.write(audio_data)

    logger.info(f"Audio saved: {output_path} ({len(audio_data)} bytes)")
    return output_path
