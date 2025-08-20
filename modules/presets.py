"""
Preset management system for saving and loading encoding configurations.
"""

import json
import pathlib
from typing import Dict, List, Any, Optional
from .video import VideoProcessingError
from .logging_config import get_logger, log_error_with_context

# Module logger
logger = get_logger('presets')


class PresetError(Exception):
    """Custom exception for preset-related errors."""
    pass


class PresetManager:
    """Manages encoding presets for the video tool."""
    
    def __init__(self, preset_file: Optional[str] = None):
        """Initialize preset manager with optional custom preset file location."""
        if preset_file:
            self.preset_file = pathlib.Path(preset_file)
        else:
            # Default to presets.json in the same directory as the script
            self.preset_file = pathlib.Path(__file__).parent.parent / "presets.json"
        
        self.presets: Dict[str, Dict[str, Any]] = {}
        self.load_presets()
    
    def load_presets(self) -> None:
        """Load presets from the preset file."""
        try:
            if self.preset_file.exists():
                with open(self.preset_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.presets = data.get("presets", {})
                    print(f"Loaded {len(self.presets)} presets from {self.preset_file}")
            else:
                # Create default presets if file doesn't exist
                self._create_default_presets()
                self.save_presets()
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading presets: {e}. Using default presets.")
            self._create_default_presets()
    
    def save_presets(self) -> None:
        """Save presets to the preset file."""
        try:
            # Ensure the directory exists
            self.preset_file.parent.mkdir(parents=True, exist_ok=True)
            
            preset_data = {
                "version": "1.0",
                "presets": self.presets
            }
            
            with open(self.preset_file, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.presets)} presets to {self.preset_file}")
        except IOError as e:
            raise PresetError(f"Failed to save presets: {e}")
    
    def _create_default_presets(self) -> None:
        """Create default encoding presets."""
        self.presets = {
            "H.265 High Quality": {
                "description": "High quality H.265 encoding with CRF 18",
                "encode_video": True,
                "video_codec": "libx265",
                "encode_audio": False,  # Copy audio, don't encode
                "audio_codec": "copy",
                "use_crf": True,
                "crf_value": 18,
                "output_extension": ".mkv",
                "output_suffix": "_h265_hq",
                "fix_resolution": True,
                "no_data": True,
                "subtitles": "All"
            },
            "H.265 Balanced": {
                "description": "Balanced H.265 encoding with CRF 23",
                "encode_video": True,
                "video_codec": "libx265",
                "encode_audio": False,  # Copy audio, don't encode
                "audio_codec": "copy",
                "use_crf": True,
                "crf_value": 23,
                "output_extension": ".mkv",
                "output_suffix": "_h265",
                "fix_resolution": True,
                "no_data": True,
                "subtitles": "All"
            },
            "H.265 Small Size": {
                "description": "Smaller file size H.265 encoding with CRF 28",
                "encode_video": True,
                "video_codec": "libx265",
                "encode_audio": False,  # Copy audio, don't encode
                "audio_codec": "copy",
                "use_crf": True,
                "crf_value": 28,
                "output_extension": ".mkv",
                "output_suffix": "_small",
                "fix_resolution": True,
                "no_data": True,
                "subtitles": "None"
            },
            "H.264 Compatible": {
                "description": "H.264 encoding for maximum compatibility",
                "encode_video": True,
                "video_codec": "libx264",
                "encode_audio": True,  # Encode audio to AAC for compatibility
                "audio_codec": "aac",
                "use_crf": True,
                "crf_value": 23,
                "output_extension": ".mp4",
                "output_suffix": "_h264",
                "fix_resolution": True,
                "no_data": True,
                "subtitles": "All"
            },
            "Copy Video + Convert Audio": {
                "description": "Copy video stream, convert audio to AAC",
                "encode_video": False,  # Copy video, don't encode
                "video_codec": "copy",
                "encode_audio": True,   # Encode audio to AAC
                "audio_codec": "aac",
                "use_crf": False,
                "crf_value": 23,
                "output_extension": ".mkv",
                "output_suffix": "_audio_aac",
                "fix_resolution": False,
                "no_data": True,
                "subtitles": "All"
            },
            "Archive Quality": {
                "description": "Lossless/near-lossless archival quality",
                "encode_video": True,
                "video_codec": "libx265",
                "encode_audio": False,  # Copy audio to preserve original quality
                "audio_codec": "copy",
                "use_crf": True,
                "crf_value": 12,
                "output_extension": ".mkv",
                "output_suffix": "_archive",
                "fix_resolution": False,
                "no_data": False,
                "subtitles": "All"
            }
        }
    
    def get_preset_names(self) -> List[str]:
        """Get a list of all preset names."""
        return sorted(self.presets.keys())
    
    def get_preset(self, name: str) -> Dict[str, Any]:
        """Get a preset by name."""
        if name not in self.presets:
            raise PresetError(f"Preset '{name}' not found")
        return self.presets[name].copy()
    
    def save_preset(self, name: str, settings: Dict[str, Any], description: str = "") -> None:
        """Save a new preset or update an existing one."""
        if not name or not name.strip():
            raise PresetError("Preset name cannot be empty")
        
        # Filter out None values and ensure we have the basic required settings
        filtered_settings = {k: v for k, v in settings.items() if v is not None}
        filtered_settings["description"] = description
        
        self.presets[name] = filtered_settings
        self.save_presets()
        print(f"Saved preset: {name}")
    
    def delete_preset(self, name: str) -> None:
        """Delete a preset."""
        if name not in self.presets:
            raise PresetError(f"Preset '{name}' not found")
        
        del self.presets[name]
        self.save_presets()
        print(f"Deleted preset: {name}")
    
    def rename_preset(self, old_name: str, new_name: str) -> None:
        """Rename a preset."""
        if old_name not in self.presets:
            raise PresetError(f"Preset '{old_name}' not found")
        
        if not new_name or not new_name.strip():
            raise PresetError("New preset name cannot be empty")
        
        if new_name in self.presets and new_name != old_name:
            raise PresetError(f"Preset '{new_name}' already exists")
        
        self.presets[new_name] = self.presets.pop(old_name)
        self.save_presets()
        print(f"Renamed preset: {old_name} -> {new_name}")
    
    def export_preset(self, name: str, file_path: str) -> None:
        """Export a single preset to a file."""
        if name not in self.presets:
            raise PresetError(f"Preset '{name}' not found")
        
        export_data = {
            "vidtool_preset": {
                "version": "1.0",
                "name": name,
                "settings": self.presets[name]
            }
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(f"Exported preset '{name}' to {file_path}")
        except IOError as e:
            raise PresetError(f"Failed to export preset: {e}")
    
    def import_preset(self, file_path: str) -> str:
        """Import a preset from a file. Returns the imported preset name."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "vidtool_preset" not in data:
                raise PresetError("Invalid preset file format")
            
            preset_data = data["vidtool_preset"]
            name = preset_data.get("name", "Imported Preset")
            settings = preset_data.get("settings", {})
            
            # Handle name conflicts
            original_name = name
            counter = 1
            while name in self.presets:
                name = f"{original_name} ({counter})"
                counter += 1
            
            self.presets[name] = settings
            self.save_presets()
            print(f"Imported preset: {name}")
            return name
            
        except (json.JSONDecodeError, IOError, KeyError) as e:
            raise PresetError(f"Failed to import preset: {e}")


# Global preset manager instance
preset_manager = PresetManager()


def get_preset_manager() -> PresetManager:
    """Get the global preset manager instance."""
    return preset_manager
