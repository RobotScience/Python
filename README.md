# Python

## ffmpeg

### convert_mkv_to_mp4.py

This script converts every `.mkv` file in a source directory to an `.mp4` file
in the output directory. It requires both the `ffmpeg` command-line tools
(`ffmpeg` and `ffprobe`) and the Python dependencies in
`ffmpeg/requirements.txt`.

Install the Python dependencies from the repository root with:

```bash
python3 -m pip install -r ffmpeg/requirements.txt
```

Run the converter with:

```bash
python3 ffmpeg/convert_mkv_to_mp4.py SOURCE_DIR OUTPUT_DIR
```

Optional arguments:

- `--preset`: x264 encoding preset. Defaults to `medium`.
- `--crf`: x264 quality value. Defaults to `23`.

The conversion preserves the source video resolution, re-encodes video with
`libx264`, and re-encodes audio to stereo AAC at 320 kbps. The script selects
the first audio stream tagged `en` or `eng` that is not marked or named as
commentary. Audio timestamps are resynchronized to help prevent gaps in the
converted file.

If an `.srt` file with the same name as an input `.mkv` is next to it, the
subtitle file is included in the conversion.

## handbrake

### auto_encode_videos.py

This script uses the HandBrakeCLI to convert TV and Movie files from a source directory. HandBrakeCLI must be installed and in the path of the user executing the script.

**Requirements**

- videoprops

**Arguments**

*source_path*

- This is the root path for all source video files. The script currently looks for files in a *tv* or *movies* folder, inside the source path

*out_path*

- If source path is *movies* then the output of the converted file will be [out_path]/Movies/[FILENAME].mp4
- If the source path is *tv* then the output of the converted file will be [outh_path]/TV/[SERIES NAME]/[FILENAME].mp4

*log_level*

- Instantiates loguru at the minimum level provided
    - Options (from lowest value to highest): ['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL']
