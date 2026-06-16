import os
import logging
import asyncio
import aiohttp
import aiofiles
from config import PEXELS_API_KEY, PIXABAY_API_KEY, TEMP_DIR, CLIP_DURATION, VIDEO_DURATION
from services.script_generator import generate_search_keywords

logger = logging.getLogger(__name__)

CLIPS_NEEDED = VIDEO_DURATION // CLIP_DURATION  # 6 clips for 30s


async def search_stock_videos(topic: str, script: str) -> list[str]:
    """Search and download stock video clips from Pexels and Pixabay."""
    keywords = await generate_search_keywords(topic, script)

    video_urls = []

    async with aiohttp.ClientSession() as session:
        # Try Pexels first
        pexels_urls = await _search_pexels(session, keywords)
        video_urls.extend(pexels_urls)

        # Fill gaps with Pixabay
        if len(video_urls) < CLIPS_NEEDED:
            pixabay_urls = await _search_pixabay(session, keywords)
            video_urls.extend(pixabay_urls)

    if not video_urls:
        raise RuntimeError("Не удалось найти видео по теме. Попробуй другую тему.")

    # Download clips
    downloaded = []
    tasks = []
    for i, url in enumerate(video_urls[:CLIPS_NEEDED]):
        path = os.path.join(TEMP_DIR, f"clip_{i}.mp4")
        tasks.append(_download_video(url, path))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, str) and os.path.exists(r):
            downloaded.append(r)
        else:
            logger.warning(f"Failed to download clip: {r}")

    if not downloaded:
        raise RuntimeError("Не удалось скачать видеоматериалы.")

    logger.info(f"Downloaded {len(downloaded)} clips")
    return downloaded


async def _search_pexels(session: aiohttp.ClientSession, keywords: list[str]) -> list[str]:
    """Search Pexels for vertical videos."""
    urls = []
    headers = {"Authorization": PEXELS_API_KEY}

    for keyword in keywords:
        if len(urls) >= CLIPS_NEEDED:
            break
        try:
            params = {
                "query": keyword,
                "per_page": 3,
                "orientation": "portrait",
                "size": "medium",
            }
            async with session.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params=params
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for video in data.get("videos", []):
                        # Get HD file
                        for vf in sorted(video.get("video_files", []), key=lambda x: x.get("height", 0), reverse=True):
                            if vf.get("height", 0) >= 720:
                                urls.append(vf["link"])
                                break
        except Exception as e:
            logger.warning(f"Pexels search error for '{keyword}': {e}")

    logger.info(f"Pexels found {len(urls)} videos")
    return urls


async def _search_pixabay(session: aiohttp.ClientSession, keywords: list[str]) -> list[str]:
    """Search Pixabay for videos."""
    urls = []

    for keyword in keywords:
        if len(urls) >= CLIPS_NEEDED:
            break
        try:
            params = {
                "key": PIXABAY_API_KEY,
                "q": keyword,
                "video_type": "film",
                "per_page": 3,
                "safesearch": "true",
            }
            async with session.get(
                "https://pixabay.com/api/videos/",
                params=params
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for hit in data.get("hits", []):
                        videos = hit.get("videos", {})
                        # Prefer large or medium
                        for quality in ["large", "medium", "small"]:
                            v = videos.get(quality, {})
                            if v.get("url"):
                                urls.append(v["url"])
                                break
        except Exception as e:
            logger.warning(f"Pixabay search error for '{keyword}': {e}")

    logger.info(f"Pixabay found {len(urls)} videos")
    return urls


async def _download_video(url: str, path: str) -> str:
    """Download a video file."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            resp.raise_for_status()
            async with aiofiles.open(path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 64):
                    await f.write(chunk)
    return path
