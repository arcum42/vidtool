import subprocess
import json
import datetime
import pathlib
import os

ffprobe_bin = "ffprobe"
ffmpeg_bin = "ffmpeg"

def execute(cmd):
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            print(line, end='')  # process line here

    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, p.args)

class info:
    def __init__(self, file):
        #print(f"Getting info for {file}")
        self.file = file
        self.metadata = self.get_metadata(file)
        self.format_info = self.metadata["format"]

        self.video_streams = [stream for stream in self.metadata["streams"] if stream["codec_type"] == "video"]
        self.audio_streams = [stream for stream in self.metadata["streams"] if stream["codec_type"] == "audio"]
        self.subtitle_streams = [stream for stream in self.metadata["streams"] if stream["codec_type"] == "subtitle"]
        self.data_streams = [stream for stream in self.metadata["streams"] if stream["codec_type"] == "data"]

        self.max_width, self.max_height = 0, 0
        self.get_video_dimensions()

        self.duration = float(self.format_info["duration"])
        self.size = int(self.format_info["size"])
        self.bitrate = int(self.format_info["bit_rate"])
        self.runtime = str(datetime.timedelta(seconds=float(self.format_info["duration"])))

    def get_metadata(self, file):
        result = subprocess.run(
            [ffprobe_bin, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", file],
            stdout=subprocess.PIPE
        )
        return json.loads(result.stdout)

    def get_video_dimensions(self):
        for stream in self.video_streams:
            temp_width = int(stream.get('width', stream.get('coded_width', 0)))
            temp_height = int(stream.get('height', stream.get('coded_height', 0)))
            if temp_width > self.max_width:  # prefer the largest video stream
                self.max_width = temp_width
            if temp_height > self.max_height:
                self.max_height = temp_height

    def print_json(self):
        print(json.dumps(self.metadata, indent=4))

    def get_info_block(self):
        info_block = ""
        info_block += f'{self.format_info["filename"]} - {self.format_info["format_name"]} - {self.format_info["format_long_name"]}, Runtime = {self.runtime}\n'
        if self.max_width % 2 == 1 or self.max_height % 2 == 1:
            info_block += f'Warning: Resolution ({self.max_width}x{self.max_height}) is not divisible by 2.\n'

        if len(self.video_streams) > 0:
            if len(self.video_streams) > 1:
                info_block += f'{len(self.video_streams)} Video streams: {self.max_width}x{self.max_height}\n'
            else:
                info_block += f'{len(self.video_streams)} Video stream: {self.max_width}x{self.max_height}\n'

            for stream in self.video_streams:
                stream_text = f'#{stream["index"]} {stream["codec_type"]}: {stream["codec_long_name"]}'
                if stream.get("height", 0) > 0:
                    stream_text += f' - {stream.get("width", "N/A")} x {stream.get("height", "N/A")}'
                if stream.get("coded_height", 0) > 0:
                    stream_text += f' - {stream.get("coded_width", "N/A")} x {stream.get("coded_height", "N/A")}'
                if stream.get("display_aspect_ratio", "N/A") != "N/A":
                    stream_text += f' - DAR: {stream.get("display_aspect_ratio", "N/A")}'
                stream_text += f' - bitrate: {stream.get("bit_rate", "N/A")}\n'
                info_block += stream_text

        if len(self.audio_streams) > 0:
            if len(self.audio_streams) > 1:
                info_block += f'{len(self.audio_streams)} Audio streams:'
            else:
                info_block += f'{len(self.audio_streams)} Audio stream:'

            for stream in self.audio_streams:
                stream_text = f'#{stream["index"]} {stream["codec_type"]}: {stream["codec_long_name"]}'
                if stream.get("channels", 0) > 0:
                    stream_text += f' - channels: {stream["channels"]}'
                stream_text += f' - bitrate: {stream.get("bit_rate", "N/A")}\n'
                info_block += stream_text

        if len(self.subtitle_streams) > 0:
            if len(self.subtitle_streams) > 1:
                info_block += f'{len(self.subtitle_streams)} Subtitle streams:'
            else:
                info_block += f'{len(self.subtitle_streams)} Subtitle stream:'

            for stream in self.subtitle_streams:
                stream_text = f'#{stream["index"]} {stream["codec_type"]}: {stream["codec_long_name"]}\n'
                info_block += stream_text

        if len(self.data_streams) > 0:
            if len(self.data_streams) > 1:
                info_block += f'{len(self.data_streams)} Data streams:'
            else:
                info_block += f'{len(self.data_streams)} Data stream:'

            for stream in self.data_streams:
                stream_text = f'#{stream["index"]} {stream["codec_type"]}: {stream["codec_long_name"]}\n'
                info_block += stream_text
        return info_block
    
    def print_info(self):
        print(self.get_info_block())

    def rename_resolution(self):
        p = pathlib.Path(self.file)
        new_file_name = f"{p.stem}-{self.max_width}x{self.max_height}{p.suffix}"
        new_path = pathlib.Path(p.parent, new_file_name)
        if not new_path.exists():
            print(f"{p} -> {new_path}")
            p.rename(new_path)

class encode:
    def __init__(self):
        self.input = []
        self.file_info = []
        self.output = ""
        self.arguments = []

    def add_input(self, input_file):
        self.input.append(input_file)
        self.file_info.append(info(input_file))

    def add_output(self, output_file):
        self.output = output_file

    def add_output_from_input(self, file_append, file_extension, idx = 0):
        if not file_extension.startswith('.'):
            file_extension = '.' + file_extension

        input_file = pathlib.Path(self.input[idx])
        self.output = input_file.with_stem(input_file.stem + file_append).with_suffix(file_extension)
        #print(f'input = {input_file}, output = {self.output}')

    def map_all_streams(self, input_index):
        self.arguments.extend(['-map', input_index])

    def exclude_video(self):
        self.arguments.append('-vn')

    def exclude_audio(self):
        self.arguments.append('-an')

    def exclude_subtitles(self):
        self.arguments.append('-sn')

    def exclude_data(self):
        self.arguments.append('-dn')

    def set_video_codec(self, codec):
        self.arguments.extend(['-vcodec', codec])

    def set_audio_codec(self, codec):
        self.arguments.extend(['-acodec', codec])

    def set_subtitle_codec(self, codec):
        self.arguments.extend(['-scodec', codec])

    def set_crf(self, crf):
        self.arguments.extend(['-crf', crf])

    def fix_resolution(self):
        self.arguments.extend(['-vf', 'scale=trunc(oh*a/2)*2:trunc(ow/a/2)*2'])

    def fix_errors(self):
        self.arguments.extend(['-err_detect', 'ignore_err'])

    def copy_subtitles(self):
        self.map_all_streams('0')
        self.set_subtitle_codec('copy')

    def encode_x265(self):
        self.set_video_codec('libx265')
        self.set_crf('28')

    def custom_flags(self, flags):
        self.arguments.extend(' '.join(flags).split())

    def reencode(self):
        cmd = [ffmpeg_bin]
        for input_file in self.input:
            cmd.extend(['-i', str(input_file)])
        cmd.extend(self.arguments)
        cmd.append(str(self.output))
        
        #print(f"Command line:{cmd}")
        print(subprocess.list2cmdline(cmd))
        execute(cmd)

def batch_rename(the_path):
    files = (p.resolve() for p in pathlib.Path(the_path).glob("**/*") if p.suffix in {".avi", ".mpg", ".mkv", ".mp4", ".mov", ".webm", ".wmv", ".mov", ".m4v", ".ogv", ".divx"})
    for video in files:
        v = info(video)
        print(f"{video} = {v.max_width}x{v.max_height}")
        v.rename_resolution()
