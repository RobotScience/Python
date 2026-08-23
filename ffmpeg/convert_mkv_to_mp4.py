#!/usr/bin/env python3
"""Convert MKV files in a source directory to MP4 while preserving resolution.

- Preserves the original video resolution
- Re-encodes audio to AAC at 320 kbps
- Uses libx264 with a configurable preset for modest file-size reduction
- Adds an external .srt file when a matching subtitle is found next to the MKV
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import ffmpeg
from loguru import logger


def find_english_audio_stream(mkv_path: Path) -> int:
    """Return the first English, non-commentary audio stream's ffprobe index."""

    # ensures that we are only probing for audio streams and not video or subtitle streams
    probe = ffmpeg.probe(str(mkv_path), select_streams="a")
    for stream in probe.get("streams", []):
        if stream.get("codec_type") != "audio":
            continue

        tags = stream.get("tags", {})
        language = tags.get("language", "").lower()
        title = tags.get("title", "").lower()
        handler_name = tags.get("handler_name", "").lower()
        disposition = stream.get("disposition", {})
        is_commentary = disposition.get("commentary", 0) == 1
        is_commentary = (
            is_commentary
            or "commentary" in title
            or "commentary" in handler_name
        )

        if language in {"en", "eng"} and not is_commentary:
            return int(stream["index"])

    raise ValueError(
        f"No English, non-commentary audio stream found in {mkv_path}"
    )


def iter_mkv_files(source_dir: Path) -> Path:
    """Yield all .mkv files in the source directory."""
    for path in source_dir.iterdir():
        if path.is_file() and path.suffix.lower() == ".mkv":
            yield path


def format_duration(seconds: float) -> str:
    """Format a duration as hours, minutes, and seconds."""
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def convert_mkv_to_mp4(
        mkv_path: Path,
        output_dir: Path,
        preset: str = "medium",
        crf: int = 23):
    """Convert a single MKV file to MP4 using ffmpeg-python."""
    output_path = output_dir / (mkv_path.stem + ".mp4")
    audio_stream_index = find_english_audio_stream(mkv_path)
    duration_probe = ffmpeg.probe(
        str(mkv_path),
        select_streams="a",
        show_entries="format=duration",
    )
    duration = float(duration_probe["format"]["duration"])

    # Check for a matching .srt subtitle file
    srt_path = mkv_path.with_suffix(".srt")
    if srt_path.exists():
        logger.info(f"Found subtitle: {srt_path}")
        input_kwargs = {
            "filename": str(mkv_path),
            "s": str(srt_path),
            "analyzeduration": "100M",
            "probesize": "100M",
            "fflags": "+genpts"
        }
    else:
        input_kwargs = {
            "filename": str(mkv_path),
            "analyzeduration": "100M",
            "probesize": "100M",
            "fflags": "+genpts"
        }

    try:
        input_stream = ffmpeg.input(**input_kwargs)
        process = (
            ffmpeg.output(
                input_stream.video,
                input_stream[str(audio_stream_index)],
                str(output_path),
                vcodec="libx264",
                acodec="aac",
                af="aresample=async=1:first_pts=0",
                ac=2,
                audio_bitrate="320k",
                preset=preset,
                crf=crf,
                movflags="+faststart",
            )
            .global_args("-progress", "pipe:1", "-nostats")
            .run_async(pipe_stdout=True, overwrite_output=True)
        )

        start_time = time.monotonic()
        for line in process.stdout:
            progress = line.decode().strip().split("=", 1)
            if len(progress) != 2 or progress[0] not in {
                "out_time_ms",
                "progress",
            }:
                continue

            if progress[0] == "progress":
                if progress[1] == "end":
                    completed = 100.0
                else:
                    continue
            else:
                elapsed_seconds = int(progress[1]) / 1_000_000
                completed = min(100.0, elapsed_seconds / duration * 100)

            elapsed_wall_time = time.monotonic() - start_time
            if completed > 0:
                remaining = elapsed_wall_time * (100 - completed) / completed
                remaining_text = format_duration(remaining)
            else:
                remaining_text = "--:--"
            logger.info(
                "Conversion progress: {:.1f}% | elapsed {} | remaining {}",
                completed,
                format_duration(elapsed_wall_time),
                remaining_text,
            )

        return_code = process.wait()
        logger.info("Conversion progress complete")
        if return_code:
            raise RuntimeError(
                f"ffmpeg failed to convert {mkv_path} (exit code {return_code})"
            )
    except ffmpeg.Error as e:
        logger.error(f"Error converting {mkv_path}: {e.stderr.decode()}")
        raise

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert MKV files to MP4 using ffmpeg-python while preserving resolution."
    )
    parser.add_argument("source_dir", type=Path, help="Directory containing MKV files to convert")
    parser.add_argument("output_dir", type=Path, help="Directory where converted MP4 files will be written")
    parser.add_argument(
        "--preset",
        default="medium",
        help="FFmpeg x264 preset to use for the video encoder (default: medium)",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=23,
        help="FFmpeg x264 CRF value (lower = higher quality / larger files; default: 23)",
    )
    args = parser.parse_args()

    source_dir = args.source_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    preset = args.preset
    crf = args.crf

    if not source_dir.exists() or not source_dir.is_dir():
        logger.error(f"Source directory does not exist or is not a directory: {source_dir}")
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    else:
        pass

    mkv_files = list(iter_mkv_files(source_dir))
    if not mkv_files:
        logger.warning(f"No .mkv files found in {source_dir}")
        return

    for mkv_path in mkv_files:
        logger.info(f"Converting: {mkv_path} -> {output_dir}")
        target = convert_mkv_to_mp4(mkv_path, output_dir, preset, crf)
        logger.info(f"Created: {target}")


if __name__ == "__main__":
    main()
