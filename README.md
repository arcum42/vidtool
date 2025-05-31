# VidTool

VidTool is a video processing tool with both a modern graphical user interface (GUI) and a command line interface (CLI). It relies on ffmpeg and ffprobe, making it easy to batch process video files, reencode, gather information, and perform common video management tasks.

## Features (GUI)

The GUI version (`app.py`) provides an intuitive interface for managing and processing video files. Key features include:

- Browse and select directories containing video files
- View detailed information about each video (resolution, codecs, streams, etc.)
- Batch select and process multiple videos
- Reencode videos with customizable options (codec, suffix, extension, CRF, etc.)
- Play videos directly from the interface
- Rename files to include resolution

The GUI is built with wxPython. To use it, ensure you have `wxPython` installed:

```
pip install wxPython
```

Then run:

```
python app.py
```

## Command Line Tool

VidTool also includes a command line tool (`vidtool.py`) for advanced users and scripting. The CLI supports batch reencoding, renaming, and information extraction.

```
usage: vidtool [-h] {reencode,rename,info} ...

Tool for batch reencoding, getting video info, and renaming videos with resolution.

options:
  -h, --help            show this help message and exit

subcommands:
  {reencode,rename,info}
    reencode            Reencode a file/files with the extension specified, appending a suffix to the filename.
    rename              Rename a file (or all files in the current directory) to include video resolution.
    info                Get information about a video file.
```

See below for full CLI usage and options.

## Installation

VidTool does not require installation. Just make sure you have `ffmpeg` and `ffprobe` installed and available in your system path. For the GUI, you will also need `wxPython` (see above).

To install all required Python dependencies, run:

```
pip install -r requirements.txt
```

---

<details>
<summary>Command Line Usage Details</summary>

```
usage: vidtool reencode [-h] [--av-copy-only] [--x265] [--vcodec [VCODEC]] [--acodec [ACODEC]] [--strip-video] [--strip-audio] [--strip-subs] [--strip-data]
                        [--custom-flags [CUSTOM_FLAGS ...]] [--batch] [--fix-resolution] [--fix-errors] [--force | --no-clobber]
                        pattern ext suffix

positional arguments:
  pattern               Pattern to match input files. "*.avi" for example.
  ext                   File extension to use for output files. Determines the codec used.
  suffix                Suffix to add after the file name and before the extension.

options:
  -h, --help            show this help message and exit
  --av-copy-only        Copy audio and video streams only, strip everything else, and make an exact copy.
  --x265                Force using x265, and set crf to 28.
  --vcodec [VCODEC]     Specify a video codec (or use copy to copy rather than reencode video).
  --acodec [ACODEC]     Specify a audio codec (or use copy to copy rather than reencode audio).
  --strip-video         Strip video streams.
  --strip-audio         Strip audio streams.
  --strip-subs          Strip subtitle streams.
  --strip-data          Strip data streams.
  --custom-flags [CUSTOM_FLAGS ...]
                        Custom flags to use with ffmpeg, enclosed in quotes.
  --batch               Batch reencode all files in a directory matching a pattern, such as "*.avi".
  --fix-resolution      Odd numbered resolution fix. Scale to nearest even resolution.
  --fix-errors          Attempt to fix errors. Same as --err_detect ignore_err in ffmpeg.
  --force               Force overwriting existing files.
  --no-clobber          Don't overwriting existing files.

usage: vidtool info [-h] [--json] file

positional arguments:
  file        Video file to get information about.

options:
  -h, --help  show this help message and exit
  --json      Output information in JSON format.

usage: vidtool rename [-h] [--batch] [file]

positional arguments:
  file        Filename. Required if not using --batch.

options:
  -h, --help  show this help message and exit
  --batch     Batch rename all files in a directory.
```

</details>
