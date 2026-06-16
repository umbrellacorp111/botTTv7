import os
import io
import shutil
import logging
import zipfile
import urllib.request

logger = logging.getLogger(__name__)

_ffmpeg_path = None
_ffprobe_path = None
FONT_NAME = "DejaVu Sans"
FONT_FILENAME = "DejaVuSans.ttf"
FONT_ZIP_URL = "https://github.com/dejavu-fonts/dejavu-fonts/archive/refs/tags/version_2_37.zip"


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

    which = shutil.which("ffprobe")
    if which:
        _ffprobe_path = which
        logger.info(f"ffprobe found in PATH: {_ffprobe_path}")
        return _ffprobe_path

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

    try:
        from imageio_ffmpeg import get_ffprobe_exe
        _ffprobe_path = get_ffprobe_exe()
        logger.info(f"ffprobe resolved via get_ffprobe_exe: {_ffprobe_path}")
        return _ffprobe_path
    except Exception:
        pass

    logger.warning("ffprobe not found, will use duration fallback")
    return None


def ensure_font(font_dir: str) -> str:
    font_path = os.path.join(font_dir, FONT_FILENAME)
    if os.path.exists(font_path):
        logger.info(f"Font already exists: {font_path}")
        return font_path

    os.makedirs(font_dir, exist_ok=True)
    try:
        logger.info(f"Downloading font archive from {FONT_ZIP_URL}...")
        req = urllib.request.urlopen(FONT_ZIP_URL)
        data = req.read()

        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.endswith("DejaVuSans.ttf"):
                    with z.open(name) as src, open(font_path, "wb") as dst:
                        dst.write(src.read())
                    logger.info(f"Font saved: {font_path}")
                    return font_path

        logger.warning("DejaVuSans.ttf not found in downloaded archive")
        return None
    except Exception as e:
        logger.warning(f"Font download failed, subtitles may be invisible: {e}")
        return None
