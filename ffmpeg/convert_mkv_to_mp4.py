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


def find_video_encoder(mkv_path: Path) -> str:
    """Return the matching encoder for an H.264 or HEVC video stream."""
    probe = ffmpeg.probe(
        str(mkv_path),
        select_streams="v:0",
        show_entries="stream=codec_name",
    )
    streams = probe.get("streams", [])
    codec_name = streams[0].get("codec_name", "").lower() if streams else ""

    if codec_name == "hevc":
        return "libx265"
    if codec_name == "h264":
        return "libx264"

    logger.warning(
        f"Unsupported source video codec '{codec_name}' in {mkv_path}; "
        "using libx264"
    )
    return "libx264"


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


def choose_default_video_settings(video_encoder: str) -> tuple[str, int]:
    """Return sensible default preset/CRF values for each encoder."""
    if video_encoder == "libx265":
        return "slow", 28
    return "medium", 23


def convert_mkv_to_mp4(
        mkv_path: Path,
        output_dir: Path,
        preset: str | None = None,
        crf: int | None = None):
    """Convert a single MKV file to MP4 using ffmpeg-python."""
    output_path = output_dir / (mkv_path.stem + ".mp4")
    audio_stream_index = find_english_audio_stream(mkv_path)
    video_encoder = find_video_encoder(mkv_path)

    if preset is None or crf is None:
        default_preset, default_crf = choose_default_video_settings(video_encoder)
        preset = default_preset if preset is None else preset
        crf = default_crf if crf is None else crf

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
                vcodec=video_encoder,
                acodec="aac",
                af="loudnorm=I=-16:TP=-1.5:LRA=11,aresample=async=1:first_pts=0",
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

            key, value = progress
            if key == "progress":
                if value == "end":
                    completed = 100.0
                else:
                    continue
            else:
                try:
                    elapsed_seconds = int(value) / 1_000_000
                except ValueError:
                    # FFmpeg can emit out_time_ms=N/A while the stream is still being
                    # measured on some inputs; skip those updates instead of crashing.
                    continue
                completed = min(100.0, elapsed_seconds / duration * 100)

            elapsed_wall_time = time.monotonic() - start_time
            if completed > 0:
                remaining = elapsed_wall_time * (100 - completed) / completed
                remaining_text = format_duration(remaining)
            else:
                remaining_text = "--:--"
            print(
                f"\r{completed:5.1f}% | elapsed {format_duration(elapsed_wall_time)} "
                f"| remaining {remaining_text}",
                end="",
                flush=True,
            )

        return_code = process.wait()
        print()
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
        default=None,
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
        help="FFmpeg preset to use for the selected encoder. Defaults to x264=medium or x265=slow.",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=None,
        choices=range(0, 52),
        help="FFmpeg CRF value. Defaults to x264=23 or x265=28 when not specified.",
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
