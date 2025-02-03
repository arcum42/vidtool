import argparse
import os
import pathlib

import modules.ffmpeg as ffmpeg
import modules.ffprobe as ffprobe
import modules.video as video

global_parser = argparse.ArgumentParser(
    prog='vidtool',
    description='Tool for batch reencoding, getting video info, and renaming videos with resolution.'
    )

subparsers = global_parser.add_subparsers(title='subcommands', dest='which')

# reencode
parser_reencode = subparsers.add_parser('reencode', help='Reencode a file/files with the extension specified, appending a suffix to the filename.')
parser_reencode.add_argument("pattern", help='Pattern to match input files. "*.avi" for example.')
parser_reencode.add_argument("ext", help="File extension to use for output files. Determines the codec used.")
parser_reencode.add_argument("suffix", help="Suffix to add after the file name and before the extension.")
parser_reencode.add_argument("--av-copy-only", action="store_true", help="Copy audio and video streams only, strip everything else, and make an exact copy.")
parser_reencode.add_argument("--x265", action="store_true", help="Force using x265, and set crf to 28.")
parser_reencode.add_argument("--vcodec", nargs="?", help="Specify a video codec (or use copy to copy rather than reencode video).")
parser_reencode.add_argument("--acodec", nargs="?", help="Specify a audio codec (or use copy to copy rather than reencode audio).")
parser_reencode.add_argument("--strip-video", action="store_true", help="Strip video streams.")
parser_reencode.add_argument("--strip-audio", action="store_true", help="Strip audio streams.")
parser_reencode.add_argument("--strip-subs", action="store_true", help="Strip subtitle streams.")
parser_reencode.add_argument("--strip-data", action="store_true", help="Strip data streams.")
parser_reencode.add_argument("--custom-flags", nargs="*", help="Custom flags to use with ffmpeg, enclosed in quotes.")
parser_reencode.add_argument("--batch", action="store_true", help='Batch reencode all files in a directory matching a pattern, such as "*.avi".')
parser_reencode.add_argument("--fix-resolution", action="store_true", help="Odd numbered resolution fix. Scale to nearest even resolution.")
parser_reencode.add_argument("--fix-errors", action="store_true", help="Attempt to fix errors. Same as --err_detect ignore_err in ffmpeg.")
int_group = parser_reencode.add_mutually_exclusive_group()
int_group.add_argument("--force", action="store_true", help="Force overwriting existing files.")
int_group.add_argument("--no-clobber", action="store_true", help="Don't overwriting existing files.")

# rename
parser_rename = subparsers.add_parser('rename', help='Rename a file (or all files in the current directory) to include video resolution.')
parser_rename.add_argument("file", nargs='?', help="Filename. Required if not using --batch.", default = "")
parser_rename.add_argument("--batch", action="store_true", help="Batch rename all files in a directory.")

# info
parser_info = subparsers.add_parser('info', help='Get information about a video file.')
parser_info.add_argument("file", help="Video file to get information about.")
parser_info.add_argument("--json", action="store_true", help="Output information in JSON format.")

args = global_parser.parse_args()

def reencode(video_file):
    v = video.encode()
    v.add_input(video_file)
    v.add_output_from_input(file_append = args.suffix, file_extension = args.ext)
    if pathlib.Path(v.output).exists():
        if args.force:
            print(f"Overwriting existing file '{v.output}'")
        elif args.no_clobber:
            print(f"Not overwriting existing file '{v.output}'")
            return
        else:
            prompt = input(f"Output file '{v.output}' already exists. Overwrite? (y/n) ")
            if prompt.lower() != 'y' and prompt.lower() != 'yes':
                print(f"Output file '{v.output}' already exists. Skipping.")
                return

    if args.strip_subs:
        v.exclude_subtitles()
    else:
        v.copy_subtitles()

    if args.av_copy_only:
        if args.strip_data: print("Warning: --strip-data is ignored when using --av-copy-only.")
        if args.strip_video: print("Warning: --strip-video is ignored when using --av-copy-only.")
        if args.strip_audio: print("Warning: --strip-audio is ignored when using --av-copy-only.")
        if args.x265: print("Warning: --x265 is ignored when using --av-copy-only.")
        if args.vcodec: print("Warning: --vcodec is ignored when using --av-copy-only.")
        if args.acodec: print("Warning: --acodec is ignored when using --av-copy-only.")

        v.set_video_codec('copy')
        v.set_audio_codec('copy')
        v.exclude_data()
        v.exclude_subtitles()
    else:
        if args.strip_data: v.exclude_data()
        if args.strip_video: v.exclude_video()
        if args.strip_audio: v.exclude_audio()

        if args.x265: v.encode_x265()
        if args.vcodec:
            if args.x265: print("Warning: ignoring --vcodec because --x265 is specified.")
        else:
            v.set_video_codec(args.vcodec)
        if args.acodec: v.set_audio_codec(args.acodec)

    if args.fix_resolution: v.fix_resolution()
    if args.fix_errors: v.fix_errors()
    if args.custom_flags: v.custom_flags(args.custom_flags)

    v.reencode()

if args.which == 'reencode':
    if args.batch:
        print(f"Reencode '{args.pattern}' to '*{args.ext}.{args.suffix}'.")
        for video_file in pathlib.Path(os.getcwd()).glob(f'{args.pattern}'):
            reencode(video_file)
    else:
        reencode(args.pattern)

elif args.which == 'rename':
    if args.batch:
        print("Batch rename files to include resolution.")
        video.batch_rename(args.file)
    else:
        if args.file == "":
            print("File required if not using --batch.")
            exit(1)
        print(f"Rename '{args.file}' to include resolution.")
        v = video.info(args.file)
        v.rename_resolution()
elif args.which == 'info':
    v = video.info(args.file)
    if args.json:
        v.print_json()
    else:
        v.print_info()
