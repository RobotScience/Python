#!/usr/bin/env python3
"""Convert MKV files in a source directory to MP4 while preserving resolution.

- Preserves the original video resolution
- Re-encodes audio to AAC at 320 kbps
- Uses libx264 with a configurable preset for modest file-size reduction
- Adds an external .srt file when a matching subtitle is found next to the MKV
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

script_dir = str(Path(__file__).resolve().parent)
if script_dir in sys.path:
    sys.path.remove(script_dir)

import ffmpeg


def parse_time_to_seconds(value: str) -> float:
    """Convert an ffmpeg time string like 00:01:02.34 into seconds."""
    try:
        parts = value.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        return float(value)
    except ValueError:
        return 0.0


def format_duration(seconds: float) -> str:
    """Return a compact duration string in HH:MM:SS format."""
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def get_media_duration(source_path: Path) -> float:
    """Read the input media duration in seconds using ffprobe."""
    try:
        metadata = ffmpeg.probe(str(source_path))
        format_info = metadata.get("format", {})
        duration = format_info.get("duration")
        if duration is not None:
            return float(duration)
        for stream in metadata.get("streams", []):
            if stream.get("codec_type") == "video":
                stream_duration = stream.get("duration")
                if stream_duration is not None:
                    return float(stream_duration)
    except ffmpeg.Error:
        return 0.0
    return 0.0


def find_matching_srt(video_path: Path, source_dir: Path) -> Path | None:
    """Return an SRT file for the MKV, preferring the same directory or matching stem."""
    candidate_names = [
        video_path.with_suffix(".srt"),
        video_path.with_name(f"{video_path.stem}.srt"),
    ]

    for candidate in candidate_names:
        if candidate.exists() and candidate.is_file():
            return candidate

    stem_matches = sorted(source_dir.rglob(f"{video_path.stem}.srt"), key=lambda p: str(p).lower())
    if stem_matches:
        return stem_matches[0]

    prefix_matches = sorted(source_dir.rglob(f"{video_path.stem}*.srt"), key=lambda p: str(p).lower())
    if prefix_matches:
        return prefix_matches[0]

    return None


def detect_best_vcodec(source_path: Path) -> str:
    """Detect the best video codec for the output based on the source file's codec.
    
    Maps source codecs to optimized output codecs, with fallback to libx264.
    """
    try:
        metadata = ffmpeg.probe(str(source_path))
        video_streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
        if not video_streams:
            return "libx264"
        
        source_codec = video_streams[0].get("codec_name", "").lower()
        
        # Map source codecs to best output codecs
        codec_mapping = {
            "hevc": "libx265",      # H.265/HEVC -> libx265
            "h265": "libx265",
            "h264": "libx264",      # H.264 -> libx264
            "mpeg4": "libx264",     # MPEG4 -> libx264
            "mpeg2video": "libx264", # MPEG2 -> libx264
            "vp8": "libx264",       # VP8 -> libx264
            "vp9": "libx265",       # VP9 -> libx265 (better compression)
            "av1": "libx265",       # AV1 -> libx265 (reasonable approximation)
        }
        
        return codec_mapping.get(source_codec, "libx264")
    except (ffmpeg.Error, KeyError, IndexError):
        return "libx264"


def convert_mkv_to_mp4(source_root: Path, source_path: Path, output_dir: Path, preset: str, crf: int) -> Path:
    """Convert a single MKV file into an MP4 in the given output directory."""
    source_root = source_root.resolve()
    source_path = source_path.resolve()
    relative_path = source_path.relative_to(source_root)
    target_path = output_dir / relative_path.with_suffix(".mp4")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    subtitle_path = find_matching_srt(source_path, source_root)
    input_stream = ffmpeg.input(str(source_path))
    
    # Get video stream
    video = input_stream.video
    
    # Get all audio streams and combine them
    try:
        metadata = ffmpeg.probe(str(source_path))
        audio_streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"]
    except ffmpeg.Error:
        audio_streams = []
    
    # If there are audio streams, use amix filter to combine them
    if audio_streams:
        audio_inputs = [input_stream.audio[i] for i in range(len(audio_streams))]
        # Create filter string for combining audio streams
        filter_str = f"[0:a]amix=inputs={len(audio_streams)}:duration=longest[aout]"
        combined_audio = ffmpeg.filter(audio_inputs[0], "amix", inputs=len(audio_streams), duration="longest")
        streams = [video, combined_audio]
    else:
        streams = [video]
    
    if subtitle_path is not None:
        streams.append(ffmpeg.input(str(subtitle_path)))

    # Determine best video codec based on source
    best_vcodec = detect_best_vcodec(source_path)

    output_kwargs = {
        "vcodec": best_vcodec,
        "preset": preset,
        "crf": crf,
        "pix_fmt": "yuv420p",
        "acodec": "aac",
        "audio_bitrate": "320k",
        "movflags": "+faststart",
    }

    if subtitle_path is not None:
        output_kwargs["scodec"] = "mov_text"

    output = ffmpeg.output(*streams, str(target_path), **output_kwargs)
    duration_seconds = get_media_duration(source_path)
    last_status = "Starting conversion..."

    process = output.run_async(pipe_stderr=True, overwrite_output=True)
    if process.stderr is not None:
        for raw_line in iter(process.stderr.readline, b""):
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d+)", line)
            if match:
                elapsed_seconds = parse_time_to_seconds(match.group(1))
                if duration_seconds > 0:
                    percent = min((elapsed_seconds / duration_seconds) * 100, 100.0)
                    remaining = max(duration_seconds - elapsed_seconds, 0.0)
                    last_status = (
                        f"Progress: {percent:5.1f}% | "
                        f"{format_duration(elapsed_seconds)} / {format_duration(duration_seconds)} | "
                        f"ETA {format_duration(remaining)}"
                    )
                else:
                    last_status = f"Progress: {match.group(1)} elapsed"
                print(f"\r{last_status}", end="", flush=True)

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg failed with exit code {return_code} for: {source_path}")

    print(f"\r{last_status} - complete        ")
    return target_path


def iter_mkv_files(source_dir: Path):
    """Yield MKV files found under the source directory."""
    for path in sorted(source_dir.rglob("*.mkv"), key=lambda p: str(p).lower()):
        yield path


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

    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    mkv_files = list(iter_mkv_files(source_dir))
    if not mkv_files:
        print(f"No .mkv files found in {source_dir}")
        return

    for mkv_path in mkv_files:
        print(f"Converting: {mkv_path} -> {output_dir}")
        target = convert_mkv_to_mp4(source_dir, mkv_path, output_dir, args.preset, args.crf)
        print(f"Created: {target}")


if __name__ == "__main__":
    main()
