# 🎬 VideoBot — Telegram бот для создания коротких видео

Бот создаёт 30-секундные вертикальные видео (1080×1920) для Reels/Shorts  
с монтажом, переходами, зумом и субтитрами.

---

## ⚙️ Установка на bothost.ru

### 1. Загрузи файлы
Загрузи все файлы проекта в корень своего хостинга через файловый менеджер или FTP.

### 2. Установи зависимости
В терминале хостинга:
```bash
pip install -r requirements.txt
```

### 3. Проверь наличие ffmpeg
```bash
ffmpeg -version
```
Если не установлен — напиши в поддержку bothost.ru, они должны предоставить ffmpeg.

### 4. Создай файл `.env`
Скопируй `.env.example` в `.env` и заполни свои ключи:
```bash
cp .env.example .env
nano .env
```

Заполни:
```
BOT_TOKEN=токен_от_BotFather
OPENAI_API_KEY=sk-...
PEXELS_API_KEY=...
PIXABAY_API_KEY=...
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...
```

### 5. Запусти бота
```bash
python bot.py
```

На bothost.ru обычно есть кнопка «Запустить» или поле «Команда запуска» — вставь туда:
```
python bot.py
```

---

## 🔑 Где получить ключи API

| Сервис | Где получить |
|--------|-------------|
| **Telegram Bot Token** | [@BotFather](https://t.me/BotFather) → /newbot |
| **OpenAI** | https://platform.openai.com/api-keys |
| **Pexels** | https://www.pexels.com/api/ (бесплатно) |
| **Pixabay** | https://pixabay.com/api/docs/ (бесплатно) |
| **Yandex SpeechKit** | https://cloud.yandex.ru/services/speechkit |

---

## 🤖 Что умеет бот

### Режим "Стоковые видео"
- Ищет видео на Pexels + Pixabay по теме
- Скачивает 6 клипов по 5 секунд
- Монтирует с переходами (fade, wipe, slide)
- Добавляет динамический зум (zoom in/out/pan)

### Режим "ИИ-генерация"  
- Генерирует 6 изображений через DALL-E 3
- Анимирует их эффектом Ken Burns (плавный зум)
- Собирает в видео с переходами

### Общие функции
- 🎙 Озвучка через Yandex SpeechKit (6 голосов на выбор)
- 📝 Сценарий генерирует GPT-4o-mini
- 💬 Субтитры с тайм-кодами (через Whisper)
- 🎬 Финальный монтаж: видео + аудио + субтитры

---

## 📁 Структура проекта

```
videobot/
├── bot.py                    # Точка входа
├── config.py                 # Настройки
├── states.py                 # FSM состояния
├── requirements.txt          # Зависимости
├── .env                      # Твои ключи (создать вручную)
├── handlers/
│   └── registration.py       # Диалог с пользователем
├── services/
│   ├── script_generator.py   # GPT сценарий
│   ├── tts_service.py        # Yandex TTS
│   ├── stock_service.py      # Pexels + Pixabay
│   ├── ai_video_service.py   # DALL-E + Ken Burns
│   └── video_builder.py      # Монтаж + субтитры
└── temp/                     # Временные файлы (авто-создаётся)
```

---

## ⚠️ Важные моменты

- **ffmpeg обязателен** — без него видео не собрать
- Создание одного видео занимает **1-3 минуты**
- Режим ИИ дороже по API (DALL-E 3 = ~$0.12 за изображение × 6 = ~$0.72 за видео)
- Режим стоков бесплатнее (только GPT + Whisper)
- Временные файлы автоматически удаляются после отправки

---

## 🛠 Устранение проблем

**"ffmpeg not found"** → установи ffmpeg или запроси через поддержку хостинга

**"Yandex TTS error 401"** → проверь YANDEX_API_KEY и YANDEX_FOLDER_ID

**"OpenAI error"** → проверь OPENAI_API_KEY и баланс на аккаунте

**Видео не отправляется** → файл может быть больше 50MB, уменьши VIDEO_DURATION в config.py
