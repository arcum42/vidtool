"""
Advanced output management for video encoding operations.
"""

import pathlib
import datetime
import re
from typing import Optional, Dict, Any, List
from .video import VideoProcessingError, info
from .logging_config import get_logger

# Module logger  
logger = get_logger('output')


class OutputPathGenerator:
    """Generates output paths with various naming and organization options."""
    
    def __init__(self):
        self.output_directory: Optional[pathlib.Path] = None
        self.subdirectory_pattern: str = ""
        self.filename_pattern: str = "{stem}{suffix}{extension}"
        self.suffix: str = "_encoded"
        self.extension: str = ".mkv"
        self.include_resolution: bool = False
        self.include_codec: bool = False
        self.include_date: bool = False
        self.include_quality: bool = False
        self.preserve_directory_structure: bool = True
        self.overwrite_policy: str = "skip"  # skip, overwrite, increment
        
    def set_output_directory(self, directory: Optional[pathlib.Path]):
        """Set the base output directory. None means same as input."""
        self.output_directory = directory
        
    def set_subdirectory_pattern(self, pattern: str):
        """Set pattern for creating subdirectories. Examples:
        - "encoded" -> creates 'encoded' folder
        - "{codec}" -> creates folder named after video codec
        - "{date}" -> creates folder with current date
        - "{resolution}" -> creates folder like "1920x1080"
        """
        self.subdirectory_pattern = pattern
        
    def set_filename_pattern(self, pattern: str):
        """Set pattern for output filenames. Placeholders:
        - {stem} = original filename without extension
        - {suffix} = custom suffix
        - {extension} = output extension
        - {resolution} = width x height
        - {codec} = video codec
        - {date} = current date (YYYY-MM-DD)
        - {time} = current time (HHMMSS)
        - {quality} = quality setting (CRF value)
        """
        self.filename_pattern = pattern
        
    def set_naming_options(self, suffix: str = "_encoded", extension: str = ".mkv",
                          include_resolution: bool = False, include_codec: bool = False,
                          include_date: bool = False, include_quality: bool = False):
        """Set various naming options."""
        self.suffix = suffix
        self.extension = extension
        self.include_resolution = include_resolution
        self.include_codec = include_codec
        self.include_date = include_date
        self.include_quality = include_quality
        
    def set_overwrite_policy(self, policy: str):
        """Set how to handle existing files: 'skip', 'overwrite', 'increment'."""
        if policy not in ["skip", "overwrite", "increment"]:
            raise ValueError("Policy must be 'skip', 'overwrite', or 'increment'")
        self.overwrite_policy = policy
        
    def generate_output_path(self, input_path: pathlib.Path, 
                           video_info: Optional[info] = None,
                           encoding_settings: Optional[Dict[str, Any]] = None) -> pathlib.Path:
        """Generate the complete output path for a given input file."""
        input_path = pathlib.Path(input_path)
        
        # Determine base output directory
        if self.output_directory:
            base_dir = self.output_directory
            if self.preserve_directory_structure:
                # Try to preserve the relative directory structure
                try:
                    # This is a simplified approach - in practice you'd want to handle this more robustly
                    base_dir = self.output_directory / input_path.name
                except:
                    base_dir = self.output_directory
        else:
            base_dir = input_path.parent
            
        # Create subdirectory if specified
        if self.subdirectory_pattern:
            subdir_name = self._resolve_pattern(self.subdirectory_pattern, input_path, 
                                              video_info, encoding_settings)
            base_dir = base_dir / subdir_name
            
        # Generate filename
        filename = self._generate_filename(input_path, video_info, encoding_settings)
        
        # Combine path
        output_path = base_dir / filename
        
        # Handle existing files based on policy
        output_path = self._handle_existing_file(output_path)
        
        return output_path
        
    def _generate_filename(self, input_path: pathlib.Path,
                          video_info: Optional[info] = None,
                          encoding_settings: Optional[Dict[str, Any]] = None) -> str:
        """Generate the output filename based on the pattern and options."""
        
        # Build dynamic suffix based on options
        suffix_parts = [self.suffix] if self.suffix else []
        
        if self.include_resolution and video_info:
            suffix_parts.append(f"{video_info.max_width}x{video_info.max_height}")
            
        if self.include_codec and encoding_settings:
            video_codec = encoding_settings.get("video_codec", "")
            if video_codec and video_codec != "copy":
                # Clean up codec name (remove lib prefix, etc.)
                codec_clean = video_codec.replace("lib", "").replace("_", "")
                suffix_parts.append(codec_clean)
                
        if self.include_quality and encoding_settings:
            if encoding_settings.get("use_crf") and "crf_value" in encoding_settings:
                suffix_parts.append(f"crf{encoding_settings['crf_value']}")
                
        if self.include_date:
            suffix_parts.append(datetime.datetime.now().strftime("%Y%m%d"))
            
        # Combine suffix parts
        combined_suffix = "_".join(suffix_parts) if suffix_parts else ""
        if combined_suffix and not combined_suffix.startswith("_"):
            combined_suffix = "_" + combined_suffix
            
        # Resolve the filename pattern
        filename = self._resolve_pattern(self.filename_pattern, input_path, 
                                       video_info, encoding_settings, combined_suffix)
        
        return filename
        
    def _resolve_pattern(self, pattern: str, input_path: pathlib.Path,
                        video_info: Optional[info] = None,
                        encoding_settings: Optional[Dict[str, Any]] = None,
                        resolved_suffix: Optional[str] = None) -> str:
        """Resolve placeholders in a pattern string."""
        
        replacements = {
            "{stem}": input_path.stem,
            "{suffix}": resolved_suffix or self.suffix,
            "{extension}": self.extension,
            "{date}": datetime.datetime.now().strftime("%Y-%m-%d"),
            "{time}": datetime.datetime.now().strftime("%H%M%S"),
        }
        
        if video_info:
            replacements.update({
                "{resolution}": f"{video_info.max_width}x{video_info.max_height}",
                "{width}": str(video_info.max_width),
                "{height}": str(video_info.max_height),
                "{duration}": str(int(video_info.duration)),
                "{size_mb}": str(int(video_info.size_mb)),
            })
            
        if encoding_settings:
            replacements.update({
                "{codec}": encoding_settings.get("video_codec", "unknown"),
                "{quality}": str(encoding_settings.get("crf_value", "")),
            })
            
        # Replace placeholders
        result = pattern
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, str(value))
            
        # Clean up the result (remove invalid filename characters)
        result = re.sub(r'[<>:"/\\|?*]', '_', result)
        
        return result
        
    def _handle_existing_file(self, output_path: pathlib.Path) -> pathlib.Path:
        """Handle existing files based on the overwrite policy."""
        if not output_path.exists():
            return output_path
            
        if self.overwrite_policy == "overwrite":
            return output_path
        elif self.overwrite_policy == "skip":
            return output_path  # Caller should check if file exists
        elif self.overwrite_policy == "increment":
            # Find an available filename with incremental suffix
            counter = 1
            base_path = output_path.parent
            stem = output_path.stem
            extension = output_path.suffix
            
            while output_path.exists():
                new_name = f"{stem}_{counter:03d}{extension}"
                output_path = base_path / new_name
                counter += 1
                
                # Prevent infinite loops
                if counter > 999:
                    raise VideoProcessingError("Too many existing files with similar names")
                    
        return output_path
        
    def preview_output_paths(self, input_files: List[pathlib.Path],
                           encoding_settings: Optional[Dict[str, Any]] = None) -> List[tuple]:
        """Preview output paths for a list of input files.
        Returns list of (input_path, output_path, exists) tuples."""
        results = []
        
        for input_file in input_files:
            try:
                # Get video info if we need it for the pattern
                video_info = None
                if (self.include_resolution or "{resolution}" in self.filename_pattern or 
                    "{resolution}" in self.subdirectory_pattern or
                    "{width}" in self.filename_pattern or "{height}" in self.filename_pattern):
                    try:
                        video_info = info(str(input_file))
                    except:
                        pass  # Continue without video info
                        
                output_path = self.generate_output_path(input_file, video_info, encoding_settings)
                exists = output_path.exists()
                results.append((input_file, output_path, exists))
                
            except Exception as e:
                # Include error info
                results.append((input_file, None, f"Error: {e}"))
                
        return results


class OutputPreset:
    """Predefined output configurations for common use cases."""
    
    @staticmethod
    def get_preset(name: str) -> OutputPathGenerator:
        """Get a predefined output configuration."""
        generator = OutputPathGenerator()
        
        if name == "Same Directory":
            # Default behavior - same directory with suffix
            generator.set_naming_options(suffix="_encoded")
            
        elif name == "Encoded Subdirectory":
            # Create 'encoded' subdirectory
            generator.set_subdirectory_pattern("encoded")
            generator.set_naming_options(suffix="")
            
        elif name == "Codec Subdirectory":
            # Organize by codec
            generator.set_subdirectory_pattern("{codec}")
            generator.set_naming_options(suffix="", include_quality=True)
            
        elif name == "Date Subdirectory":
            # Organize by date
            generator.set_subdirectory_pattern("{date}")
            generator.set_naming_options(suffix="")
            
        elif name == "Resolution + Codec":
            # Include resolution and codec in filename
            generator.set_naming_options(suffix="", include_resolution=True, include_codec=True)
            
        elif name == "Quality Testing":
            # For testing different quality settings
            generator.set_subdirectory_pattern("quality_test")
            generator.set_naming_options(suffix="", include_quality=True, include_date=True)
            generator.set_overwrite_policy("increment")
            
        elif name == "Archive Organization":
            # Organized archive structure
            generator.set_subdirectory_pattern("archived/{codec}")
            generator.set_naming_options(suffix="_archived", include_resolution=True)
            
        elif name == "Custom Directory":
            # Will be customized by user
            generator.set_naming_options(suffix="_processed")
            
        else:
            raise ValueError(f"Unknown output preset: {name}")
            
        return generator


# Common output presets
OUTPUT_PRESETS = [
    "Same Directory",
    "Encoded Subdirectory", 
    "Codec Subdirectory",
    "Date Subdirectory",
    "Resolution + Codec",
    "Quality Testing",
    "Archive Organization",
    "Custom Directory"
]
