# VidTool - Video Processing Application

VidTool is a comprehensive video processing application that provides both a modern wxPython-based GUI and a command-line interface for batch video processing, reencoding, and management tasks.

## Project Overview

This project enables users to efficiently process video files using FFmpeg as the backend. The GUI application (`app.py`) offers an intuitive interface for directory browsing, video selection, detailed video information display, and batch processing operations. The CLI tool (`vidtool.py`) provides scriptable access to core functionality.

## Architecture & Structure

- **GUI Application (`app.py`)**: Main wxPython application with multiple panels and dialogs
- **CLI Tool (`vidtool.py`)**: Command-line interface for batch operations
- **Modules Directory**: Core functionality split into focused modules
  - `video.py`: FFmpeg/FFprobe integration, video processing, codec detection
  - `presets.py`: Encoding preset management and storage
  - `output.py`: Output path generation and naming patterns

## Key Technologies & Dependencies

- **Python 3.x** - Primary language
- **wxPython** - GUI framework for cross-platform desktop interface
- **FFmpeg/FFprobe** - External video processing tools (required system dependency)
- **Threading** - Background video scanning and processing
- **JSON** - Configuration and preset storage

## GUI Components & Classes

- `MyFrame`: Main application window with directory navigation and video list
- `VideoList`: Custom wx.ListCtrl with checkboxes for video selection and caching
- `VideoInfoPanel`: Displays detailed video metadata (resolution, codecs, streams)
- `ReencodePane`: Collapsible panel with encoding options and progress tracking
- `SelectionOptionsDialog`: Advanced filtering dialog with codec, resolution, and size criteria
- `OutputOptionsDialog`: Complex multi-tab dialog for output path configuration
- `SettingsPanel`: FFmpeg binary path configuration

## Key Features & Functionality

- **Dynamic Codec Detection**: Extracts actual codec names from video files for accurate filtering
- **Advanced Selection Options**: Multi-criteria filtering by video/audio codecs, resolution, file size, extensions
- **Flexible Output Patterns**: Customizable naming with placeholders ({stem}, {codec}, {resolution}, etc.)
- **Preset Management**: Save/load encoding configurations with import/export
- **Progress Tracking**: Real-time encoding progress with cancellation support
- **Recursive Directory Scanning**: Configurable depth for subdirectory traversal

## Coding Standards & Conventions

- Use **PEP 8** naming conventions (snake_case for functions/variables, PascalCase for classes)
- **Type hints** where appropriate, especially for function parameters and returns
- **Error handling** with specific exception types (VideoProcessingError, FFmpegNotFoundError)
- **Threading best practices** - use wx.CallAfter() for UI updates from worker threads
- **Resource cleanup** - properly close dialogs and handle process termination
- **Configuration persistence** - save user preferences to config.json

## UI/UX Guidelines

- **Dialog auto-sizing** - use self.Fit() and SetMinSize() for proper layout
- **Progress feedback** - show progress bars and status messages for long operations
- **Validation** - check prerequisites (FFmpeg availability, file existence) before operations  
- **User confirmations** - confirm destructive operations with message dialogs
- **Consistent spacing** - use consistent padding (5-10px) in sizers and layouts

## FFmpeg Integration Patterns

- **Path detection** - check system PATH and configurable binary paths
- **Process management** - use subprocess with proper error handling and output parsing
- **Stream analysis** - parse FFprobe JSON output for video/audio stream information
- **Codec mapping** - distinguish between encoder names (libx265) and actual codecs (hevc)

## Common Development Tasks

When adding new features:
- Extend `AppState` for new configuration options
- Add validation in dialog `OnApply()` methods  
- Use `wx.CallAfter()` for thread-safe UI updates
- Cache expensive operations (video info, codec detection)
- Provide user feedback for all long-running operations
- Follow existing error handling patterns with specific exception types

When modifying video processing:
- Update codec detection logic in `get_available_codecs()`
- Maintain compatibility between GUI and CLI interfaces
- Test with various video formats and edge cases
- Ensure proper cleanup of temporary files and processes
