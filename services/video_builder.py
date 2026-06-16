"""
Video builder — собирает финальное видео из клипов + аудио + субтитры.
Использует ffmpeg напрямую для скорости и контроля.
"""

import os
import asyncio
import logging
import json
import math
import re
from config import (
    TEMP_DIR, VIDEO_WIDTH, VIDEO_HEIGHT, FPS,
    VIDEO_DURATION, CLIP_DURATION, OPENAI_API_KEY
)
from openai import AsyncOpenAI
from services.ffmpeg_helper import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

FFMPEG = get_ffmpeg_path()
FFPROBE = get_ffprobe_path()

TRANSITIONS = ["fade", "zoom_in", "zoom_out", "slide_left", "slide_right"]
TRANSITION_DURATION = 0.4  # seconds


async def build_video(clips: list[str], audio_path: str, script: str, user_id: int) -> str:
    """
    Build final 30-second video with:
    - Multiple clips
    - Transitions between clips
    - Zoom effects
    - Subtitles (ASS format)
    """
    output_path = os.path.join(TEMP_DIR, f"final_{user_id}.mp4")

    # Step 1: Prepare clips (resize + duration)
    prepared_clips = await _prepare_clips(clips, user_id)

    # Step 2: Get audio duration
    audio_duration = await _get_duration(audio_path)
    target_duration = min(audio_duration + 0.5, VIDEO_DURATION)

    # Step 3: Generate subtitles
    subs_path = await _generate_subtitles(script, audio_path, user_id)

    # Step 4: Concatenate clips with transitions
    concat_path = await _concat_with_transitions(prepared_clips, user_id, target_duration)

    # Step 5: Merge video + audio + subtitles
    await _merge_final(concat_path, audio_path, subs_path, output_path, target_duration)

    logger.info(f"Final video: {output_path}")
    return output_path


async def _prepare_clips(clips: list[str], user_id: int) -> list[str]:
    """Resize clips to target resolution and add dynamic zoom."""
    prepared = []
    num_clips = max(len(clips), 1)

    for i, clip_path in enumerate(clips):
        out_path = os.path.join(TEMP_DIR, f"prep_{user_id}_{i}.mp4")
        duration = CLIP_DURATION

        # Dynamic zoom effect: alternate zoom in / zoom out
        if i % 3 == 0:
            # Zoom in
            vf = (
                f"scale={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2},"
                f"zoompan=z='min(zoom+0.0008,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={duration*FPS}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
            )
        elif i % 3 == 1:
            # Zoom out
            vf = (
                f"scale={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2},"
                f"zoompan=z='if(lte(zoom\\,1.0)\\,1.2\\,max(1.0\\,zoom-0.0008))'"
                f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={duration*FPS}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
            )
        else:
            # Pan left to right
            vf = (
                f"scale={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2},"
                f"zoompan=z='1.1':x='if(lte(on\\,1)\\,0\\,min(iw/2-(iw/zoom/2)+on*1\\,iw/2))'"
                f":y='ih/2-(ih/zoom/2)'"
                f":d={duration*FPS}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
            )

        cmd = [
            FFMPEG, "-y",
            "-i", clip_path,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-r", str(FPS),
            "-an",
            out_path
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode == 0 and os.path.exists(out_path):
            prepared.append(out_path)
        else:
            logger.warning(f"Clip prep failed {i}: {stderr.decode()[-300:]}")
            # Try simple resize fallback
            fallback = await _simple_resize(clip_path, out_path, duration, user_id, i)
            if fallback:
                prepared.append(fallback)

    return prepared if prepared else clips


async def _simple_resize(clip_path: str, out_path: str, duration: float, user_id: int, idx: int) -> str:
    """Simple resize without zoom for fallback."""
    cmd = [
        FFMPEG, "-y",
        "-i", clip_path,
        "-t", str(duration),
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-r", str(FPS),
        "-an",
        out_path
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()
    return out_path if proc.returncode == 0 else None


async def _concat_with_transitions(clips: list[str], user_id: int, target_duration: float) -> str:
    """Concatenate clips with fade transitions using xfade filter."""
    out_path = os.path.join(TEMP_DIR, f"concat_{user_id}.mp4")

    if len(clips) == 1:
        # Loop single clip if needed
        cmd = [
            FFMPEG, "-y",
            "-stream_loop", "-1",
            "-i", clips[0],
            "-t", str(target_duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            out_path
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        return out_path

    # Build xfade filter chain
    inputs = []
    for clip in clips:
        inputs.extend(["-i", clip])

    # Build filter graph with xfade transitions
    filter_parts = []
    current = "[0:v]"
    transitions_list = ["fade", "wipeleft", "wiperight", "slideleft", "slideright", "fadeblack"]

    for i in range(1, len(clips)):
        offset = i * CLIP_DURATION - TRANSITION_DURATION
        trans = transitions_list[i % len(transitions_list)]
        next_label = f"[v{i}]" if i < len(clips) - 1 else "[outv]"
        filter_parts.append(
            f"{current}[{i}:v]xfade=transition={trans}:duration={TRANSITION_DURATION}:offset={offset}{next_label}"
        )
        current = f"[v{i}]"

    filter_graph = ";".join(filter_parts)

    cmd = [
        FFMPEG, "-y",
        *inputs,
        "-filter_complex", filter_graph,
        "-map", "[outv]",
        "-t", str(target_duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-r", str(FPS),
        out_path
    ]

    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.warning(f"xfade failed, using simple concat: {stderr.decode()[-300:]}")
        return await _simple_concat(clips, out_path, target_duration, user_id)

    return out_path


async def _simple_concat(clips: list[str], out_path: str, target_duration: float, user_id: int) -> str:
    """Fallback: simple concat using ffmpeg concat demuxer."""
    list_path = os.path.join(TEMP_DIR, f"list_{user_id}.txt")
    with open(list_path, "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-t", str(target_duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        out_path
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Concat failed: {stderr.decode()[-300:]}")

    return out_path


async def _generate_subtitles(script: str, audio_path: str, user_id: int) -> str:
    """
    Generate ASS subtitle file.
    Uses Whisper API to get word-level timing, then creates styled subtitles.
    """
    subs_path = os.path.join(TEMP_DIR, f"subs_{user_id}.ass")

    try:
        # Use OpenAI Whisper for timing
        with open(audio_path, "rb") as af:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=af,
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )

        words = transcript.words or []
        segments = _group_words_into_segments(words, max_words=5)

    except Exception as e:
        logger.warning(f"Whisper failed, using equal timing: {e}")
        segments = _fallback_segments(script)

    _write_ass_file(segments, subs_path)
    return subs_path


def _group_words_into_segments(words: list, max_words: int = 5) -> list[dict]:
    """Group word timestamps into subtitle segments."""
    segments = []
    current = []

    for word in words:
        current.append(word)
        if len(current) >= max_words:
            segments.append({
                "start": current[0].start,
                "end": current[-1].end,
                "text": " ".join(w.word for w in current).strip()
            })
            current = []

    if current:
        segments.append({
            "start": current[0].start,
            "end": current[-1].end,
            "text": " ".join(w.word for w in current).strip()
        })

    return segments


def _fallback_segments(script: str) -> list[dict]:
    """Create equal-time segments from script text."""
    words = script.split()
    total_words = len(words)
    total_time = VIDEO_DURATION
    words_per_second = total_words / total_time

    segments = []
    chunk_size = 5
    for i in range(0, total_words, chunk_size):
        chunk = words[i:i + chunk_size]
        start = i / words_per_second
        end = (i + len(chunk)) / words_per_second
        segments.append({
            "start": start,
            "end": end,
            "text": " ".join(chunk)
        })

    return segments


def _ts(seconds: float) -> str:
    """Convert seconds to ASS timestamp H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _write_ass_file(segments: list[dict], path: str):
    """Write styled ASS subtitle file."""
    # ASS style: bold white text, black outline, bottom center
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,80,80,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]

    for seg in segments:
        start = _ts(seg["start"])
        end = _ts(seg["end"])
        text = seg["text"].replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


async def _get_duration(path: str) -> float:
    """Get media file duration using ffprobe."""
    cmd = [
        FFPROBE, "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        path
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()

    try:
        info = json.loads(stdout)
        return float(info["format"]["duration"])
    except Exception:
        return VIDEO_DURATION


async def _merge_final(
    video_path: str,
    audio_path: str,
    subs_path: str,
    output_path: str,
    duration: float
):
    """Merge video + audio + burn subtitles into final file."""
    # Escape path for ffmpeg ASS filter
    subs_escaped = subs_path.replace("\\", "/").replace(":", "\\:")

    cmd = [
        FFMPEG, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-vf", f"ass={subs_escaped}",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-t", str(duration),
        "-movflags", "+faststart",
        output_path
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error(f"Merge error: {stderr.decode()[-500:]}")
        # Try without subtitles as fallback
        await _merge_without_subs(video_path, audio_path, output_path, duration)


async def _merge_without_subs(video_path: str, audio_path: str, output_path: str, duration: float):
    """Merge video + audio without subtitles as fallback."""
    cmd = [
        FFMPEG, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-t", str(duration),
        "-movflags", "+faststart",
        output_path
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Final merge failed: {stderr.decode()[-300:]}")
