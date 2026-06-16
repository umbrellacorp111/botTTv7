import os
import logging

logger = logging.getLogger(__name__)

_ffmpeg_path = None
_ffprobe_path = None


def get_ffmpeg_path() -> str:
    global _ffmpeg_path
    if _ffmpeg_path:
        return _ffmpeg_path

    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        _ffmpeg_path = get_ffmpeg_exe()
        logger.info(f"ffmpeg resolved via imageio-ffmpeg: {_ffmpeg_path}")
    except Exception as e:
        logger.warning(f"imageio-ffmpeg failed, falling back to 'ffmpeg' in PATH: {e}")
        _ffmpeg_path = "ffmpeg"

    return _ffmpeg_path


def get_ffprobe_path() -> str:
    global _ffprobe_path
    if _ffprobe_path:
        return _ffprobe_path

    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
        if exe and exe != "ffmpeg":
            _ffprobe_path = exe.replace("ffmpeg", "ffprobe")
            if os.path.exists(_ffprobe_path):
                logger.info(f"ffprobe resolved via imageio-ffmpeg: {_ffprobe_path}")
                return _ffprobe_path
    except Exception:
        pass

    try:
        from imageio_ffmpeg import get_ffprobe_exe
        _ffprobe_path = get_ffprobe_exe()
    except Exception:
        _ffprobe_path = "ffprobe"

    logger.info(f"ffprobe: {_ffprobe_path}")
    return _ffprobe_path
