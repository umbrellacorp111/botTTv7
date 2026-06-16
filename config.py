import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Stock video APIs
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# Yandex TTS
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")

# Video settings
VIDEO_DURATION = 30          # seconds total
CLIP_DURATION = 5            # seconds per clip
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920          # Vertical (Reels/Shorts format)
FPS = 30

# Temp directory
TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")

# Available voices (Yandex TTS)
VOICES = {
    "Алина (женский)": "alena",
    "Филипп (мужской)": "filipp",
    "Захар (мужской, низкий)": "zahar",
    "Ермил (мужской)": "ermil",
    "Оксана (женский)": "oksana",
    "Джейн (женский, нейтральный)": "jane",
}
