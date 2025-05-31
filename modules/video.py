import subprocess
import json
import datetime
import pathlib
import os

ffprobe_bin = "ffprobe"
ffmpeg_bin = "ffmpeg"
ffplay_bin = "ffplay"

VIDEO_EXTENSIONS = (
    ".mkv", ".mp4", ".webm", ".ogv", ".avi", ".mpg", ".mov", ".wmv", ".m4v", ".ogm", ".flv", ".divx", ".mpeg", ".ts"
)

VIDEO_CODECS = (
    "copy", "libx264", "libx265", "libxvid", "libvpx-vp9", "nvenc_h264", "nvenc_hevc"
)
AUDIO_CODECS = (
    "copy", "aac", "mp3", "flac", "ogg", "ac3", "opus"
)

def execute(cmd):
    """Run a command and print its output line by line."""
    print(subprocess.list2cmdline(cmd))
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as p:
        if p.stdout:
            for line in p.stdout:
                print(line, end='')

def play(video):
    """Play a video file using ffplay."""
    execute([ffplay_bin, str(video)])

class info:
    """Extracts and holds metadata for a video file."""
    def __init__(self, file):
        self.file = file
        self.metadata = self.get_metadata(file)
        self.format_info = self.metadata.get("format", {})
        streams = self.metadata.get("streams", [])
        self.video_streams = [s for s in streams if s.get("codec_type") == "video"]
        self.audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        self.subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
        self.data_streams = [s for s in streams if s.get("codec_type") == "data"]
        self.max_width, self.max_height = self.get_video_dimensions()
        self.duration = float(self.format_info.get("duration", 0))
        self.size = int(self.format_info.get("size", 0))
        self.size_kb = self.size / 1024
        self.size_mb = self.size_kb / 1024
        self.size_gb = self.size_mb / 1024
        self.bitrate = int(self.format_info.get("bit_rate", 0))
        self.runtime = str(datetime.timedelta(seconds=self.duration))
        self.filename = self.format_info.get("filename", str(file))

    @staticmethod
    def get_metadata(file):
        result = subprocess.run([
            ffprobe_bin, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", file
        ], stdout=subprocess.PIPE)
        return json.loads(result.stdout)

    def get_video_dimensions(self):
        max_width = max_height = 0
        for stream in self.video_streams:
            temp_width = int(stream.get('width', stream.get('coded_width', 0)))
            temp_height = int(stream.get('height', stream.get('coded_height', 0)))
            max_width = max(max_width, temp_width)
            max_height = max(max_height, temp_height)
        return max_width, max_height

    def print_json(self):
        print(json.dumps(self.metadata, indent=4))

    def get_video_stream_description(self, stream):
        s = stream
        desc = f'#{s.get("index", "?")} {s.get("codec_type", "?")}: {s.get("codec_long_name", "?")}'
        if s.get("height", 0) > 0:
            desc += f' - {s.get("width", "N/A")} x {s.get("height", "N/A")}'
        if s.get("coded_height", 0) > 0:
            desc += f' - {s.get("coded_width", "N/A")} x {s.get("coded_height", "N/A")}'
        if s.get("display_aspect_ratio", "N/A") != "N/A":
            desc += f' - DAR: {s.get("display_aspect_ratio", "N/A")}'
        desc += f' - bitrate: {s.get("bit_rate", "N/A")}'
        return desc

    def get_audio_stream_description(self, stream):
        s = stream
        desc = f'#{s.get("index", "?")} {s.get("codec_type", "?")}: {s.get("codec_long_name", "?")}'
        if s.get("channels", 0) > 0:
            desc += f' - channels: {s.get("channels")}'
        desc += f' - bitrate: {s.get("bit_rate", "N/A")}'
        return desc

    def get_subtitle_stream_description(self, stream):
        return f'#{stream.get("index", "?")} {stream.get("codec_type", "?")}: {stream.get("codec_long_name", "?")}'

    def get_data_stream_description(self, stream):
        return f'#{stream.get("index", "?")} {stream.get("codec_type", "?")}: {stream.get("codec_long_name", "?")}'

    def get_info_block(self):
        info_block = f'{self.format_info.get("filename", "?")} - {self.format_info.get("format_name", "?")} - {self.format_info.get("format_long_name", "?")}, Runtime = {self.runtime}\n'
        if self.max_width % 2 or self.max_height % 2:
            info_block += f'Warning: Resolution ({self.max_width}x{self.max_height}) is not divisible by 2.\n'
        if self.video_streams:
            info_block += f'{len(self.video_streams)} Video stream{"s" if len(self.video_streams) > 1 else ""}: {self.max_width}x{self.max_height}\n'
            for s in self.video_streams:
                info_block += self.get_video_stream_description(s) + "\n"
        if self.audio_streams:
            info_block += f'{len(self.audio_streams)} Audio stream{"s" if len(self.audio_streams) > 1 else ""}:\n'
            for s in self.audio_streams:
                info_block += self.get_audio_stream_description(s) + "\n"
        if self.subtitle_streams:
            info_block += f'{len(self.subtitle_streams)} Subtitle stream{"s" if len(self.subtitle_streams) > 1 else ""}:\n'
            for s in self.subtitle_streams:
                info_block += self.get_subtitle_stream_description(s) + "\n"
        if self.data_streams:
            info_block += f'{len(self.data_streams)} Data stream{"s" if len(self.data_streams) > 1 else ""}:\n'
            for s in self.data_streams:
                info_block += self.get_data_stream_description(s) + "\n"
        return info_block

    def print_info(self):
        print(self.get_info_block())

    def rename_resolution(self):
        p = pathlib.Path(self.file)
        new_file_name = f"{p.stem}-{self.max_width}x{self.max_height}{p.suffix}"
        new_path = p.parent / new_file_name
        if not new_path.exists():
            print(f"{p} -> {new_path}")
            p.rename(new_path)

class encode:
    """Builds and runs ffmpeg encode commands."""
    def __init__(self):
        self.input = []
        self.file_info = []
        self.output = ""
        self.arguments = []

    def less_noise(self):
        self.arguments.append('-hide_banner')

    def parsable_output(self):
        self.arguments += ['-stats', '-loglevel', 'error', '-progress', '-']

    def add_input(self, input_file):
        self.input.append(input_file)
        if pathlib.Path(input_file).suffix != ".srt":
            print(f"Adding input file: {input_file}")
            self.file_info.append(info(input_file))

    def add_output(self, output_file):
        self.output = output_file

    def add_output_from_input(self, file_append, file_extension, idx=0):
        if not file_extension.startswith('.'):
            file_extension = '.' + file_extension
        input_file = pathlib.Path(self.input[idx])
        self.output = input_file.with_stem(input_file.stem + file_append).with_suffix(file_extension)

    def map_all_streams(self, input_index):
        self.arguments += ['-map', input_index]

    def exclude_video(self):
        self.arguments.append('-vn')

    def exclude_audio(self):
        self.arguments.append('-an')

    def exclude_subtitles(self):
        self.arguments.append('-sn')

    def exclude_data(self):
        self.arguments.append('-dn')

    def set_video_codec(self, codec):
        self.arguments += ['-vcodec', codec]

    def set_audio_codec(self, codec):
        self.arguments += ['-acodec', codec]

    def set_subtitle_codec(self, codec):
        self.arguments += ['-scodec', codec]

    def set_crf(self, crf):
        self.arguments += ['-crf', crf]

    def fix_resolution(self):
        self.arguments += ['-vf', 'scale=trunc(oh*a/2)*2:trunc(ow/a/2)*2']

    def fix_errors(self):
        self.arguments += ['-err_detect', 'ignore_err']

    def copy_subtitles(self):
        self.map_all_streams('0')
        self.set_subtitle_codec('copy')

    def encode_x265(self):
        self.set_video_codec('libx265')
        self.set_crf('28')

    def custom_flags(self, flags):
        self.arguments += ' '.join(flags).split()

    def reencode_str(self):
        cmd = [ffmpeg_bin]
        self.less_noise()
        for input_file in self.input:
            cmd += ['-i', str(input_file)]
        cmd += self.arguments
        cmd.append(str(self.output))
        return cmd

    def reencode(self):
        execute(self.reencode_str())

def batch_rename(the_path):
    files = (p.resolve() for p in pathlib.Path(the_path).glob("**/*") if p.suffix in VIDEO_EXTENSIONS)
    for video in files:
        v = info(video)
        print(f"{video} = {v.max_width}x{v.max_height}")
        v.rename_resolution()