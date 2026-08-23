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

import ffmpeg
from loguru import logger

def iter_mkv_files(source_dir: Path) -> Path:
    """Yield all .mkv files in the source directory."""
    for path in source_dir.iterdir():
        if path.is_file() and path.suffix.lower() == ".mkv":
            yield path

def convert_mkv_to_mp4(
    mkv_path: Path,
    output_dir: Path,
    preset: str = "medium",
    crf: int = 23,


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
