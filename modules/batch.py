"""
Advanced batch operations for video processing.
"""

import pathlib
import fnmatch
from typing import List, Dict, Any, Callable, Optional, Set
from .video import VIDEO_EXTENSIONS, info, VideoProcessingError, VideoFileError
import re


class BatchFilter:
    """Advanced filtering system for batch operations."""
    
    def __init__(self):
        self.min_size_mb: Optional[float] = None
        self.max_size_mb: Optional[float] = None
        self.min_duration_sec: Optional[float] = None
        self.max_duration_sec: Optional[float] = None
        self.min_width: Optional[int] = None
        self.max_width: Optional[int] = None
        self.min_height: Optional[int] = None
        self.max_height: Optional[int] = None
        self.video_codecs: Set[str] = set()
        self.audio_codecs: Set[str] = set()
        self.filename_patterns: List[str] = []
        self.exclude_patterns: List[str] = []
        self.extensions: Set[str] = set()
    
    def set_size_range(self, min_mb: Optional[float] = None, max_mb: Optional[float] = None):
        """Set file size filtering range in megabytes."""
        self.min_size_mb = min_mb
        self.max_size_mb = max_mb
    
    def set_duration_range(self, min_sec: Optional[float] = None, max_sec: Optional[float] = None):
        """Set duration filtering range in seconds."""
        self.min_duration_sec = min_sec
        self.max_duration_sec = max_sec
    
    def set_resolution_range(self, min_width: Optional[int] = None, max_width: Optional[int] = None,
                           min_height: Optional[int] = None, max_height: Optional[int] = None):
        """Set resolution filtering range."""
        self.min_width = min_width
        self.max_width = max_width
        self.min_height = min_height
        self.max_height = max_height
    
    def add_video_codecs(self, codecs: List[str]):
        """Add video codecs to filter for."""
        self.video_codecs.update(codecs)
    
    def add_audio_codecs(self, codecs: List[str]):
        """Add audio codecs to filter for."""
        self.audio_codecs.update(codecs)
    
    def add_filename_patterns(self, patterns: List[str]):
        """Add filename patterns (supports wildcards like *.mp4, *season*episode*)."""
        self.filename_patterns.extend(patterns)
    
    def add_exclude_patterns(self, patterns: List[str]):
        """Add patterns to exclude from results."""
        self.exclude_patterns.extend(patterns)
    
    def add_extensions(self, extensions: List[str]):
        """Add file extensions to filter for."""
        self.extensions.update(ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions)
    
    def matches(self, file_path: pathlib.Path, file_info: Optional[info] = None) -> bool:
        """Check if a file matches all filter criteria."""
        # Extension filter
        if self.extensions and file_path.suffix.lower() not in self.extensions:
            return False
        
        # Filename include patterns
        if self.filename_patterns:
            filename = file_path.name.lower()
            if not any(fnmatch.fnmatch(filename, pattern.lower()) for pattern in self.filename_patterns):
                return False
        
        # Filename exclude patterns
        if self.exclude_patterns:
            filename = file_path.name.lower()
            if any(fnmatch.fnmatch(filename, pattern.lower()) for pattern in self.exclude_patterns):
                return False
        
        # If we need file info for filtering but don't have it, try to get it
        if (self.min_size_mb or self.max_size_mb or self.min_duration_sec or self.max_duration_sec or
            self.min_width or self.max_width or self.min_height or self.max_height or
            self.video_codecs or self.audio_codecs):
            
            if file_info is None:
                try:
                    file_info = info(str(file_path))
                except (VideoProcessingError, VideoFileError):
                    return False  # Skip files we can't analyze
        
        if file_info:
            # Size filter
            if self.min_size_mb and file_info.size_mb < self.min_size_mb:
                return False
            if self.max_size_mb and file_info.size_mb > self.max_size_mb:
                return False
            
            # Duration filter
            if self.min_duration_sec and file_info.duration < self.min_duration_sec:
                return False
            if self.max_duration_sec and file_info.duration > self.max_duration_sec:
                return False
            
            # Resolution filter
            if self.min_width and file_info.max_width < self.min_width:
                return False
            if self.max_width and file_info.max_width > self.max_width:
                return False
            if self.min_height and file_info.max_height < self.min_height:
                return False
            if self.max_height and file_info.max_height > self.max_height:
                return False
            
            # Video codec filter
            if self.video_codecs:
                video_codec_names = [stream.get('codec_name', '').lower() for stream in file_info.video_streams]
                if not any(codec.lower() in video_codec_names for codec in self.video_codecs):
                    return False
            
            # Audio codec filter
            if self.audio_codecs:
                audio_codec_names = [stream.get('codec_name', '').lower() for stream in file_info.audio_streams]
                if not any(codec.lower() in audio_codec_names for codec in self.audio_codecs):
                    return False
        
        return True


class BatchSelector:
    """Advanced selection system for batch operations."""
    
    def __init__(self, base_path: pathlib.Path):
        self.base_path = pathlib.Path(base_path)
        self.files: List[pathlib.Path] = []
        self.file_info_cache: Dict[str, info] = {}
    
    def scan_directory(self, recursive: bool = True, 
                      extensions: Optional[Set[str]] = None,
                      progress_callback: Optional[Callable[[str], None]] = None) -> List[pathlib.Path]:
        """Scan directory for video files."""
        if extensions is None:
            extensions = set(VIDEO_EXTENSIONS)
        
        pattern = "**/*" if recursive else "*"
        found_files = []
        
        try:
            for file_path in self.base_path.glob(pattern):
                if file_path.is_file() and file_path.suffix.lower() in extensions:
                    found_files.append(file_path)
                    if progress_callback:
                        progress_callback(f"Found: {file_path.name}")
        except PermissionError as e:
            raise VideoProcessingError(f"Permission denied accessing directory: {e}")
        
        self.files = sorted(found_files)
        return self.files
    
    def apply_filter(self, batch_filter: BatchFilter, 
                    progress_callback: Optional[Callable[[str], None]] = None) -> List[pathlib.Path]:
        """Apply a batch filter to the current file list."""
        filtered_files = []
        
        for file_path in self.files:
            if progress_callback:
                progress_callback(f"Filtering: {file_path.name}")
            
            # Use cached info if available
            file_info = self.file_info_cache.get(str(file_path))
            
            if batch_filter.matches(file_path, file_info):
                # Cache the info if we had to load it
                if file_info is None and str(file_path) not in self.file_info_cache:
                    try:
                        file_info = info(str(file_path))
                        self.file_info_cache[str(file_path)] = file_info
                    except (VideoProcessingError, VideoFileError):
                        pass  # Skip files we can't analyze
                
                filtered_files.append(file_path)
        
        return filtered_files
    
    def select_by_pattern(self, pattern: str) -> List[pathlib.Path]:
        """Select files matching a specific pattern."""
        return [f for f in self.files if fnmatch.fnmatch(f.name.lower(), pattern.lower())]
    
    def select_by_size_range(self, min_mb: float, max_mb: float) -> List[pathlib.Path]:
        """Select files within a size range."""
        batch_filter = BatchFilter()
        batch_filter.set_size_range(min_mb, max_mb)
        return self.apply_filter(batch_filter)
    
    def select_by_resolution(self, min_width: int = 0, max_width: int = 999999,
                           min_height: int = 0, max_height: int = 999999) -> List[pathlib.Path]:
        """Select files within a resolution range."""
        batch_filter = BatchFilter()
        batch_filter.set_resolution_range(min_width, max_width, min_height, max_height)
        return self.apply_filter(batch_filter)
    
    def select_by_codec(self, video_codecs: Optional[List[str]] = None,
                       audio_codecs: Optional[List[str]] = None) -> List[pathlib.Path]:
        """Select files with specific codecs."""
        batch_filter = BatchFilter()
        if video_codecs:
            batch_filter.add_video_codecs(video_codecs)
        if audio_codecs:
            batch_filter.add_audio_codecs(audio_codecs)
        return self.apply_filter(batch_filter)
    
    def get_file_info(self, file_path: pathlib.Path) -> Optional[info]:
        """Get cached file info or load it."""
        file_str = str(file_path)
        if file_str not in self.file_info_cache:
            try:
                self.file_info_cache[file_str] = info(file_str)
            except (VideoProcessingError, VideoFileError):
                return None
        return self.file_info_cache.get(file_str)


class BatchOperation:
    """Represents a batch operation configuration."""
    
    def __init__(self, name: str):
        self.name = name
        self.files: List[pathlib.Path] = []
        self.preset_name: Optional[str] = None
        self.custom_settings: Dict[str, Any] = {}
        self.output_suffix: str = "_processed"
        self.output_extension: str = ".mkv"
        self.output_directory: Optional[pathlib.Path] = None
        self.overwrite_existing: bool = False
        self.dry_run: bool = False
    
    def set_files(self, files: List[pathlib.Path]):
        """Set the files to process."""
        self.files = files
    
    def set_preset(self, preset_name: str):
        """Set the encoding preset to use."""
        self.preset_name = preset_name
    
    def set_custom_settings(self, settings: Dict[str, Any]):
        """Set custom encoding settings (overrides preset)."""
        self.custom_settings = settings
    
    def set_output_options(self, suffix: str = "_processed", extension: str = ".mkv",
                          output_directory: Optional[pathlib.Path] = None):
        """Set output file options."""
        self.output_suffix = suffix
        self.output_extension = extension
        self.output_directory = output_directory
    
    def set_overwrite_policy(self, overwrite: bool):
        """Set whether to overwrite existing files."""
        self.overwrite_existing = overwrite
    
    def set_dry_run(self, dry_run: bool):
        """Set dry run mode (preview operations without executing)."""
        self.dry_run = dry_run
    
    def get_output_path(self, input_path: pathlib.Path) -> pathlib.Path:
        """Generate output path for an input file."""
        if self.output_directory:
            output_dir = self.output_directory
        else:
            output_dir = input_path.parent
        
        output_name = f"{input_path.stem}{self.output_suffix}{self.output_extension}"
        return output_dir / output_name
    
    def validate(self) -> List[str]:
        """Validate the batch operation and return any errors."""
        errors = []
        
        if not self.files:
            errors.append("No files selected for processing")
        
        if not self.preset_name and not self.custom_settings:
            errors.append("No preset or custom settings specified")
        
        # Check if output directory is writable
        if self.output_directory:
            try:
                self.output_directory.mkdir(parents=True, exist_ok=True)
                test_file = self.output_directory / ".write_test"
                test_file.touch()
                test_file.unlink()
            except (PermissionError, OSError):
                errors.append(f"Cannot write to output directory: {self.output_directory}")
        
        # Check for output conflicts
        if not self.overwrite_existing:
            conflicts = []
            for input_file in self.files:
                output_path = self.get_output_path(input_file)
                if output_path.exists():
                    conflicts.append(str(output_path))
            
            if conflicts:
                if len(conflicts) <= 5:
                    errors.append(f"Output files already exist: {', '.join(conflicts)}")
                else:
                    errors.append(f"Output files already exist for {len(conflicts)} files. First few: {', '.join(conflicts[:3])}...")
        
        return errors
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the batch operation."""
        return {
            "name": self.name,
            "file_count": len(self.files),
            "preset": self.preset_name,
            "custom_settings": bool(self.custom_settings),
            "output_suffix": self.output_suffix,
            "output_extension": self.output_extension,
            "output_directory": str(self.output_directory) if self.output_directory else "Same as input",
            "overwrite_existing": self.overwrite_existing,
            "dry_run": self.dry_run
        }
