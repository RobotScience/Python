#!/usr/bin/env python3

"""
Reads mkv movie and tv files and transcodes them into mp4 files using the HandBrakeCLI.
Files are organized them into appropriate directories depending on their parent source directory.
Destination files are named according to Plex naming conventions.

Sources:
https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/
https://support.plex.tv/articles/naming-and-organizing-your-movie-media-files/
https://handbrake.fr/docs/en/latest/cli/command-line-reference.html
"""

import os
import re
import shutil
import argparse
import logging
from videoprops import get_video_properties


def encode_video(data: dict):
    
    # get dict values
    source = data['source']
    destination = data['destination']
    width = data['width']
    height = data['height']


    # $cliExe -ArgumentList "-i `"$source`" -t 1 -o `"$destination`" -f av_mp4 -w $vWidth -l $vHeight -O -e x265 --vfr -E ac3 -6 stereo -R Auto -B 48 -D 1.5 --gain 2 --verbose=0"
    full_command = f"HandBrakeCLI -i '{source}' -o '{destination}' -f av_mp4 -w {width} -l {height} -O -e x265 -vfr -E ac3 -6 stereo -R Auto -B 48 -D 1.5 --gain 2 --subtitle-lang-list eng --all-subtitles --subtitle-default=none --subtitle-burned=none --verbose=0"

    os.system(full_command)

    # move the fild to the converted directory
    shutil.move(source, source.replace('to_convert', 'converted'))


def main(arguments: dict):

    out_path = arguments['out_path']
    source_path = arguments['source_path']
    logging.basicConfig(level=f"{arguments['log_level']}")

    # look for files in source
    sub_folders = os.listdir(source_path)
    for f in sub_folders:
        if f == 'movies':
            
            # handle movie files
            for v in os.listdir(f"{source_path}/{f}"):
                if v.endswith(".mkv"):
                    logging.info(f"Movie file found: {v}. Attempting to transcode...")

                    # parse name from file
                    full_source_path = f"{source_path}/{f}/{v}"
                    split_name = v.split('.')

                    # figure out the movie year
                    for i in split_name:
                        if (i.isnumeric()) and (len(i) == 4):
                            year = i
                            logging.info(f"Date determined to be: {i}")
                    
                    # split name on date to extract title and build full output name
                    mp4_filename = f"{v.split(year)[0].replace('.', '')} ({year}).mp4"
                    output_filepath = f"{out_path}/Movies/{mp4_filename}"

                    # get video propeerties
                    props = get_video_properties(full_source_path)
                    video_width = props['width']
                    video_height = props['height']

                    encode_video({
                        'source': full_source_path,
                        'destination': output_filepath,
                        'width': video_width,
                        'height': video_height
                    })


        elif f == 'tv':
            # handle tv files
            for folder in os.listdir(f"{source_path}/{f}"):

                if 'DS_Store' not in folder:
                    # get all tv files in the directory
                    get_files = os.listdir(f"{source_path}/{f}/{folder}")

                    if len(get_files) > 0:
                        # sort the list
                        get_files.sort()
                        # determine the converted path
                        converted_path = f"{source_path.replace('to_convert', 'converted')}/tv/{folder}"
                        
                        # create the converted path if it does not exist
                        if not os.path.isdir(converted_path):
                            os.mkdir(converted_path)
                        
                        for file in get_files: # handle tv files
                            if file.endswith(".mkv"):
                                logging.info(f"TV file found: {file}. Attempting to transcode...")

                                # parse name from file
                                full_source_path = f"{source_path}/{f}/{folder}/{file}"
                                split_name = file.split('.')

                                # match to series and episode number and resolution
                                season_and_episode = re.search(r"s\d{2}e\d{2}", file, flags=re.IGNORECASE).group()
                                resolution = re.search(r"\d{3,4}p", file, flags=re.IGNORECASE).group()

                                # get the series name
                                series_name = file.split(season_and_episode)[0].replace('.', ' ').strip()
                                
                                # get the episode title
                                episode_title = file.split(resolution)[0].split(season_and_episode)[-1].replace('.', ' ').strip()
                                
                                # build full file name and output path
                                mp4_filename = f"{series_name} - {season_and_episode} - {episode_title}.mp4"
                                output_filepath = f"{out_path}/TV/{series_name}/{mp4_filename}"

                                # create series name dir if not exists
                                if not os.path.isdir(f"{out_path}/TV/{series_name}"):
                                    os.mkdir(f"{out_path}/TV/{series_name}")

                                # get video propeerties
                                props = get_video_properties(full_source_path)
                                video_width = props['width']
                                video_height = props['height']

                                encode_video({
                                    'source': full_source_path,
                                    'destination': output_filepath,
                                    'width': video_width,
                                    'height': video_height
                                })
        else:
            continue


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Auto encoding script for plex video files')
    parser.add_argument('-sp', '--source_path', help="Root source path to look for video files", type=str)
    parser.add_argument('-op', '--out_path', help="Root output path for destination files", type=str)
    parser.add_argument('-ll', '--log_level', help="logging log level", type=str, default='CRITICAL')

    args = parser.parse_args()

    main({
        'out_path': args.out_path,
        'source_path': args.source_path,
        'log_level': args.log_level
    })
