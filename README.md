# Python

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

- The log level logger (not yet implemented)
    
