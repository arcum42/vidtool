import subprocess
import json
import datetime
import pathlib
import os
import shutil
import re
import threading
import time
from .logging_config import get_logger, log_ffmpeg_command, log_error_with_context

# Module logger
logger = get_logger('video')


class VideoProcessingError(Exception):
    """Custom exception for video processing errors."""
    pass


class FFmpegNotFoundError(VideoProcessingError):
    """Raised when ffmpeg/ffprobe binaries are not found."""
    pass


class VideoFileError(VideoProcessingError):
    """Raised when there are issues with video files."""
    pass


class ProgressInfo:
    """Holds progress information for encoding operations."""
    def __init__(self):
        self.frame = 0
        self.fps = 0.0
        self.bitrate = "0kbits/s"
        self.total_size = 0
        self.out_time_ms = 0
        self.progress = "continue"
        self.speed = "0x"
        self.percent = 0.0
        self.eta_seconds = 0
        
    def update_from_line(self, line):
        """Parse a line of FFmpeg progress output."""
        if "=" in line:
            key, value = line.strip().split("=", 1)
            if key == "frame":
                self.frame = int(value) if value.isdigit() else 0
            elif key == "fps":
                try:
                    self.fps = float(value)
                except ValueError:
                    self.fps = 0.0
            elif key == "bitrate":
                self.bitrate = value
            elif key == "total_size":
                self.total_size = int(value) if value.isdigit() else 0
            elif key == "out_time_us":
                # Convert microseconds to milliseconds
                self.out_time_ms = int(value) // 1000 if value.isdigit() else 0
            elif key == "out_time_ms":
                # FFmpeg reports this in microseconds despite the name
                self.out_time_ms = int(value) // 1000 if value.isdigit() else 0
            elif key == "progress":
                self.progress = value
            elif key == "speed":
                self.speed = value
                
    def calculate_progress(self, total_duration_ms):
        """Calculate percentage and ETA based on current progress."""
        if total_duration_ms > 0 and self.out_time_ms > 0:
            self.percent = min(100.0, (self.out_time_ms / total_duration_ms) * 100)
            
            if self.fps > 0 and self.percent > 0:
                remaining_ms = total_duration_ms - self.out_time_ms
                remaining_frames = remaining_ms / 1000 * (self.frame / (self.out_time_ms / 1000)) if self.out_time_ms > 0 else 0
                self.eta_seconds = remaining_frames / self.fps if self.fps > 0 else 0
        else:
            self.percent = 0.0
            self.eta_seconds = 0

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

def execute(command, callback=None, progress_callback=None, cancel_event=None):
    """
    Execute a command using subprocess with enhanced error handling and progress tracking.
    
    Args:
        command: List of command and arguments to execute
        callback: Optional function to call with each line of output
        progress_callback: Optional function to call with ProgressInfo objects
        cancel_event: Optional threading.Event to check for cancellation
        
    Returns:
        tuple: (success, stdout, stderr, return_code)
    """
    if not command:
        raise ValueError("Command cannot be empty")
    
    stdout_lines = []
    stderr_lines = []
    progress_info = ProgressInfo()
    process = None
    
    try:
        # Combine stderr with stdout to capture FFmpeg progress output
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout
            universal_newlines=True,
            bufsize=1
        )
        
        # Read output line by line
        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                # Check for cancellation
                if cancel_event and cancel_event.is_set():
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    return False, [], ["Process cancelled by user"], -1
                
                line = line.strip()
                if line:
                    stdout_lines.append(line)
                    
                    # Call the general callback if provided
                    if callback:
                        callback(line)
                    
                    # Parse progress information for FFmpeg
                    if progress_callback:
                        # FFmpeg progress lines contain key=value pairs
                        if "=" in line:
                            progress_info.update_from_line(line)
                            
                            # When we get a complete progress update (indicated by progress=continue or progress=end)
                            if line.startswith("progress="):
                                progress_callback(progress_info)
        
        # Wait for process to complete
        return_code = process.wait()
        
        # Determine success based on return code
        success = return_code == 0
        
        return success, stdout_lines, stderr_lines, return_code
        
    except FileNotFoundError as e:
        error_msg = f"Command not found: {command[0] if command else 'unknown'}"
        raise FFmpegNotFoundError(error_msg) from e
    except PermissionError as e:
        error_msg = f"Permission denied executing: {command[0] if command else 'unknown'}"
        raise VideoProcessingError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error executing command: {str(e)}"
        raise VideoProcessingError(error_msg) from e
    finally:
        # Ensure process cleanup
        try:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
        except:
            pass  # Ignore cleanup errors

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
            logger.info(f"Renaming: {p} -> {new_path}")
            p.rename(new_path)

class encode:
    """Builds and runs ffmpeg encode commands with comprehensive error handling."""
    def __init__(self):
        self.input = []
        self.file_info = []
        self.output = ""
        self.arguments = []
        self.cancel_event = None
        self.progress_callback = None
        self.total_duration_ms = 0

    def set_progress_callback(self, callback):
        """Set a callback function to receive ProgressInfo updates."""
        self.progress_callback = callback
        
    def set_cancel_event(self, cancel_event):
        """Set a threading.Event to check for cancellation requests."""
        self.cancel_event = cancel_event
        
    def calculate_total_duration(self):
        """Calculate total duration of all input files in milliseconds."""
        total_ms = 0
        for file_info in self.file_info:
            if hasattr(file_info, 'runtime') and file_info.runtime:
                # Parse runtime format like "00:01:23.45" 
                try:
                    time_parts = file_info.runtime.split(':')
                    if len(time_parts) >= 3:
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        seconds = float(time_parts[2])
                        total_ms += (hours * 3600 + minutes * 60 + seconds) * 1000
                except (ValueError, IndexError):
                    pass
        self.total_duration_ms = total_ms
        return total_ms

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
            logger.info(f"Adding input file: {input_file}")
            try:
                self.file_info.append(info(input_file))
            except Exception as e:
                logger.warning(f"Could not get info for {input_file}: {e}")

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
        
        # Enable parsable output for progress tracking if callback is set
        if self.progress_callback:
            self.parsable_output()
        
        for input_file in self.input:
            cmd += ['-i', str(input_file)]
            
        cmd += self.arguments
        cmd.append(str(self.output))
        return cmd

    def reencode(self, output_callback=None):
        """Execute the encoding with comprehensive error handling and progress tracking."""
        try:
            command = self.reencode_str()
            log_ffmpeg_command(command, logger)
            
            # Calculate total duration for progress tracking
            self.calculate_total_duration()
            
            # Create progress callback wrapper
            def progress_wrapper(progress_info):
                # Calculate percentage based on total duration
                if self.total_duration_ms > 0:
                    progress_info.calculate_progress(self.total_duration_ms)
                
                # Call the user's callback if provided
                if self.progress_callback:
                    self.progress_callback(progress_info)
            
            success, stdout, stderr, return_code = execute(
                command, 
                callback=output_callback,
                progress_callback=progress_wrapper,
                cancel_event=self.cancel_event
            )
            
            if not success:
                if self.cancel_event and self.cancel_event.is_set():
                    raise VideoProcessingError("Encoding was cancelled by user")
                else:
                    error_msg = f"FFmpeg failed with return code {return_code}"
                    if stdout:
                        error_msg += f"\nOutput: {' '.join(stdout[-5:])}"  # Last 5 lines
                    raise VideoProcessingError(error_msg)
            
            # Verify output file was created
            output_path = pathlib.Path(self.output)
            if not output_path.exists():
                raise VideoProcessingError(f"Output file was not created: {self.output}")
                
            if output_path.stat().st_size == 0:
                raise VideoProcessingError(f"Output file is empty: {self.output}")
                
            logger.info(f"Encoding completed successfully: {self.output}")
            return True
            
        except Exception as e:
            # Clean up failed output file
            output_path = pathlib.Path(self.output)
            if output_path.exists() and output_path.stat().st_size == 0:
                try:
                    output_path.unlink()
                    logger.info(f"Cleaned up empty output file: {self.output}")
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
        
        logger.info(f"Starting batch rename in directory: {the_path}")
        
        for video in files:
            try:
                v = info(video)
                logger.debug(f"{video} = {v.max_width}x{v.max_height}")
                v.rename_resolution()
                renamed_count += 1
            except Exception as e:
                logger.error(f"Error processing {video}: {e}")
                continue
                
        logger.info(f"Successfully renamed {renamed_count} files")
        
    except Exception as e:
        log_error_with_context(e, "Batch rename operation", logger)
        raise VideoProcessingError(f"Batch rename failed: {e}")