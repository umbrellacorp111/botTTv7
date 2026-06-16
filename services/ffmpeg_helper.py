import os
import shutil
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


def get_ffprobe_path():
    global _ffprobe_path
    if _ffprobe_path:
        return _ffprobe_path

    # 1. Check PATH
    which = shutil.which("ffprobe")
    if which:
        _ffprobe_path = which
        logger.info(f"ffprobe found in PATH: {_ffprobe_path}")
        return _ffprobe_path

    # 2. Derive from imageio-ffmpeg's ffmpeg location
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg = get_ffmpeg_exe()
        if ffmpeg and ffmpeg != "ffmpeg":
            dirname = os.path.dirname(ffmpeg)
            basename = os.path.basename(ffmpeg)
            probe_name = basename.replace("ffmpeg", "ffprobe", 1)
            probe_path = os.path.join(dirname, probe_name)
            if os.path.exists(probe_path):
                _ffprobe_path = probe_path
                logger.info(f"ffprobe resolved from ffmpeg dir: {_ffprobe_path}")
                return _ffprobe_path
    except Exception:
        pass

    # 3. Use ffprobe from imageio's bundled tools if available
    try:
        from imageio_ffmpeg import get_ffprobe_exe
        _ffprobe_path = get_ffprobe_exe()
        logger.info(f"ffprobe resolved via get_ffprobe_exe: {_ffprobe_path}")
        return _ffprobe_path
    except Exception:
        pass

    logger.warning("ffprobe not found, will use duration fallback")
    return None
