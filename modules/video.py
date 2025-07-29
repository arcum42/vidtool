import subprocess
import json
import datetime
import pathlib
import os
import shutil


class VideoProcessingError(Exception):
    """Custom exception for video processing errors."""
    pass


class FFmpegNotFoundError(VideoProcessingError):
    """Raised when ffmpeg/ffprobe binaries are not found."""
    pass


class VideoFileError(VideoProcessingError):
    """Raised when there are issues with video files."""
    pass

ffprobe_bin = "ffprobe"
ffmpeg_bin = "ffmpeg"
ffplay_bin = "ffplay"


def check_ffmpeg_availability():
    """Check if ffmpeg, ffprobe, and ffplay are available."""
    missing_tools = []
    
    for tool_name, tool_bin in [("ffmpeg", ffmpeg_bin), ("ffprobe", ffprobe_bin), ("ffplay", ffplay_bin)]:
        if not shutil.which(tool_bin):
            missing_tools.append(f"{tool_name} ('{tool_bin}')")
    
    if missing_tools:
        raise FFmpegNotFoundError(f"Missing required tools: {', '.join(missing_tools)}. "
                                 f"Please install FFmpeg or configure the correct paths in Settings.")
    return True

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
    """Run a command and print its output line by line with error handling."""
    try:
        print(subprocess.list2cmdline(cmd))
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                             bufsize=1, universal_newlines=True) as p:
            
            # Stream output in real-time
            stdout_lines = []
            if p.stdout:
                for line in iter(p.stdout.readline, ''):
                    if line:
                        print(line, end='')
                        stdout_lines.append(line)
            
            # Wait for process to complete and check return code
            return_code = p.wait()
            if return_code != 0:
                # Combine stdout lines for error message (ffmpeg outputs to stderr but we redirected)
                output = ''.join(stdout_lines[-10:])  # Last 10 lines for context
                raise VideoProcessingError(f"Command failed with return code {return_code}. Last output:\n{output}")
                
    except FileNotFoundError as e:
        raise FFmpegNotFoundError(f"Could not find executable: {cmd[0]}. Please check your FFmpeg installation.")
    except Exception as e:
        raise VideoProcessingError(f"Error executing command: {e}")

def play(video):
    """Play a video file using ffplay with error handling."""
    try:
        check_ffmpeg_availability()
        execute([ffplay_bin, str(video)])
    except Exception as e:
        raise VideoProcessingError(f"Error playing video '{video}': {e}")

class info:
    """Extracts and holds metadata for a video file with comprehensive error handling."""
    def __init__(self, file):
        self.file = file
        
        # Validate file exists and is readable
        if not pathlib.Path(file).exists():
            raise VideoFileError(f"Video file not found: {file}")
        
        if not pathlib.Path(file).is_file():
            raise VideoFileError(f"Path is not a file: {file}")
            
        try:
            self.metadata = self.get_metadata(file)
        except Exception as e:
            raise VideoFileError(f"Failed to extract metadata from '{file}': {e}")
            
        self.format_info = self.metadata.get("format", {})
        streams = self.metadata.get("streams", [])
        
        # Safely extract stream information
        self.video_streams = [s for s in streams if s.get("codec_type") == "video"]
        self.audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        self.subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
        self.data_streams = [s for s in streams if s.get("codec_type") == "data"]
        
        try:
            self.max_width, self.max_height = self.get_video_dimensions()
            self.duration = float(self.format_info.get("duration", 0))
            self.size = int(self.format_info.get("size", 0))
            self.size_kb = self.size / 1024
            self.size_mb = self.size_kb / 1024
            self.size_gb = self.size_mb / 1024
            self.bitrate = int(self.format_info.get("bit_rate", 0))
            self.runtime = str(datetime.timedelta(seconds=self.duration))
            self.filename = self.format_info.get("filename", str(file))
        except (ValueError, TypeError) as e:
            raise VideoFileError(f"Invalid video metadata in '{file}': {e}")

    @staticmethod
    def get_metadata(file):
        """Extract metadata using ffprobe with error handling."""
        try:
            check_ffmpeg_availability()
        except FFmpegNotFoundError:
            raise
            
        try:
            result = subprocess.run([
                ffprobe_bin, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(file)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            
            if result.returncode != 0:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                raise VideoProcessingError(f"ffprobe failed: {error_msg}")
                
            return json.loads(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise VideoProcessingError(f"ffprobe timed out processing '{file}'")
        except json.JSONDecodeError as e:
            raise VideoProcessingError(f"Invalid JSON output from ffprobe: {e}")
        except FileNotFoundError:
            raise FFmpegNotFoundError(f"ffprobe not found: {ffprobe_bin}")
        except Exception as e:
            raise VideoProcessingError(f"Unexpected error running ffprobe: {e}")

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
    """Builds and runs ffmpeg encode commands with comprehensive error handling."""
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
        """Add input file with validation."""
        input_path = pathlib.Path(input_file)
        
        if not input_path.exists():
            raise VideoFileError(f"Input file not found: {input_file}")
            
        if not input_path.is_file():
            raise VideoFileError(f"Input path is not a file: {input_file}")
        
        self.input.append(str(input_path.resolve()))
        
        # Only get info for video files, not subtitle files
        if input_path.suffix.lower() not in [".srt", ".vtt", ".ass", ".ssa"]:
            print(f"Adding input file: {input_file}")
            try:
                self.file_info.append(info(input_file))
            except Exception as e:
                print(f"Warning: Could not get info for {input_file}: {e}")

    def add_output(self, output_file):
        """Set output file with validation."""
        output_path = pathlib.Path(output_file)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if we can write to the output location
        try:
            output_path.touch(exist_ok=True)
            if output_path.exists() and output_path.stat().st_size == 0:
                output_path.unlink()  # Remove the test file
        except PermissionError:
            raise VideoFileError(f"Cannot write to output location: {output_file}")
            
        self.output = str(output_path.resolve())

    def add_output_from_input(self, file_append, file_extension, idx=0):
        """Generate output filename from input with validation."""
        if not self.input:
            raise VideoProcessingError("No input files specified")
            
        if idx >= len(self.input):
            raise VideoProcessingError(f"Input index {idx} out of range (have {len(self.input)} inputs)")
            
        if not file_extension.startswith('.'):
            file_extension = '.' + file_extension
            
        input_file = pathlib.Path(self.input[idx])
        output_file = input_file.with_stem(input_file.stem + file_append).with_suffix(file_extension)
        self.add_output(str(output_file))

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
        """Build the ffmpeg command with validation."""
        if not self.input:
            raise VideoProcessingError("No input files specified for encoding")
            
        if not self.output:
            raise VideoProcessingError("No output file specified for encoding")
            
        try:
            check_ffmpeg_availability()
        except FFmpegNotFoundError:
            raise
            
        cmd = [ffmpeg_bin]
        self.less_noise()
        
        for input_file in self.input:
            cmd += ['-i', str(input_file)]
            
        cmd += self.arguments
        cmd.append(str(self.output))
        return cmd

    def reencode(self):
        """Execute the encoding with comprehensive error handling."""
        try:
            command = self.reencode_str()
            print(f"Starting encode: {' '.join(command)}")
            execute(command)
            
            # Verify output file was created
            output_path = pathlib.Path(self.output)
            if not output_path.exists():
                raise VideoProcessingError(f"Output file was not created: {self.output}")
                
            if output_path.stat().st_size == 0:
                raise VideoProcessingError(f"Output file is empty: {self.output}")
                
            print(f"Encoding completed successfully: {self.output}")
            
        except Exception as e:
            # Clean up failed output file
            output_path = pathlib.Path(self.output)
            if output_path.exists() and output_path.stat().st_size == 0:
                try:
                    output_path.unlink()
                    print(f"Cleaned up empty output file: {self.output}")
                except:
                    pass
            raise

def batch_rename(the_path):
    """Batch rename files with error handling."""
    try:
        path = pathlib.Path(the_path)
        if not path.exists():
            raise VideoFileError(f"Path does not exist: {the_path}")
            
        if not path.is_dir():
            raise VideoFileError(f"Path is not a directory: {the_path}")
            
        files = (p.resolve() for p in path.glob("**/*") if p.suffix in VIDEO_EXTENSIONS)
        renamed_count = 0
        
        for video in files:
            try:
                v = info(video)
                print(f"{video} = {v.max_width}x{v.max_height}")
                v.rename_resolution()
                renamed_count += 1
            except Exception as e:
                print(f"Error processing {video}: {e}")
                continue
                
        print(f"Successfully renamed {renamed_count} files")
        
    except Exception as e:
        raise VideoProcessingError(f"Batch rename failed: {e}")