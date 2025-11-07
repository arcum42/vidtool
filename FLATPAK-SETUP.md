# Flatpak Setup Summary

I've successfully created a complete Flatpak configuration for VidTool. Here's what was added:

## Files Created

### 1. **io.github.arcum42.vidtool.yml** (Main Flatpak Manifest)
   - Defines the application structure and build process
   - Includes all dependencies: wxPython, FFmpeg, and video codecs (x264, x265, libvpx)
   - Configures filesystem permissions for accessing video files
   - Sets up the Python environment with necessary packages

### 2. **vidtool-launcher.sh** (Application Launcher)
   - Simple bash script that launches app.py from the Flatpak environment
   - Sets the working directory and executes the Python application

### 3. **io.github.arcum42.vidtool.desktop** (Desktop Entry)
   - Provides desktop integration (application menu entry)
   - Defines application name, icon, and categories
   - Enables launching from desktop environments

### 4. **io.github.arcum42.vidtool.metainfo.xml** (AppStream Metadata)
   - Contains application description and metadata
   - Required for application stores like Flathub
   - Includes feature list and version information

### 5. **io.github.arcum42.vidtool.png** (Application Icon)
   - 256x256 placeholder icon with "VT" text
   - You can replace this with a custom icon design

### 6. **build-flatpak.sh** (Build Script)
   - Convenient script for building, testing, and installing the Flatpak
   - Includes commands for creating distributable bundles
   - Checks prerequisites and provides helpful error messages

### 7. **README-flatpak.md** (Flatpak Documentation)
   - Comprehensive guide for building and distributing the Flatpak
   - Includes troubleshooting tips and publishing instructions
   - Documents filesystem permissions and security considerations

### 8. **.gitignore** (Git Ignore File)
   - Excludes build artifacts (build-dir/, repo/, .flatpak-builder/)
   - Standard Python and IDE exclusions

## Quick Start

### Build and Test

```bash
# Build the Flatpak
./build-flatpak.sh build

# Test without installing
./build-flatpak.sh test

# Install locally
./build-flatpak.sh install

# Run the installed app
flatpak run io.github.arcum42.vidtool
```

### Verify Codec Support

After installation, verify that FFmpeg has been compiled with all codecs:

```bash
# Check available encoders
flatpak run --command=ffmpeg io.github.arcum42.vidtool -encoders | grep -E "264|265|vp8|vp9"

# Check available decoders  
flatpak run --command=ffmpeg io.github.arcum42.vidtool -decoders | grep -E "264|265|vp8|vp9"

# Full codec list
flatpak run --command=ffmpeg io.github.arcum42.vidtool -codecs | grep -E "264|265|vp8|vp9"
```

Expected output should include:
- `libx264` - H.264/AVC encoder
- `libx265` - H.265/HEVC encoder
- `libvpx` - VP8 encoder
- `libvpx-vp9` - VP9 encoder

### Create Distribution Bundle

```bash
# Create a single .flatpak file for distribution
./build-flatpak.sh bundle

# This creates: vidtool.flatpak
```

Users can install your bundle with:
```bash
flatpak install vidtool.flatpak
```

## Key Features

### Complete Dependency Bundling
- **wxPython 4.2.1**: GUI framework included
- **FFmpeg 7.1**: Video processing tool compiled with codec support
- **Video Codecs**: 
  - **x264** (H.264/AVC): Static library compiled with PIC
  - **x265** (H.265/HEVC): Static library v4.1 with position-independent code
  - **libvpx** (VP8/VP9): Shared library v1.15.2 with 10-bit/12-bit support
- **NASM**: Assembler used during codec compilation (not included in runtime)
- **Python 3.11**: From Freedesktop runtime

All codecs are compiled from source following FFmpeg compilation guide best practices.

### Filesystem Access
The Flatpak is configured with `--filesystem=host` to allow:
- Browsing any directory on the system
- Reading video files from any location
- Writing reencoded videos to any location

This is necessary for VidTool's core functionality.

### Cross-Platform Support
- Works on any Linux distribution with Flatpak support
- Includes all dependencies (no external package installation needed)
- Sandboxed environment for security

## Customization

### Replace the Icon
Create a better 256x256 PNG icon and save it as `io.github.arcum42.vidtool.png`

### Update Dependencies
Edit `io.github.arcum42.vidtool.yml` to:
- Change wxPython version
- Update FFmpeg version
- Add additional codecs or libraries
- Modify filesystem permissions

### Publish to Flathub
Follow the instructions in README-flatpak.md to submit to Flathub for wider distribution.

## Filesystem Permissions Explained

The manifest includes:
```yaml
finish-args:
  - --filesystem=host        # Full filesystem access
  - --filesystem=xdg-run/media  # Access to mounted drives
  - --share=ipc              # X11 shared memory
  - --socket=x11             # X11 display
  - --socket=wayland         # Wayland display
  - --socket=pulseaudio      # Audio for video playback
  - --device=dri             # GPU acceleration
```

These permissions ensure VidTool can:
- Access video files anywhere on the system
- Display the GUI properly
- Play video previews with audio
- Use GPU acceleration if available

## Next Steps

1. **Test the build**: Run `./build-flatpak.sh build` and `./build-flatpak.sh test`
2. **Customize the icon**: Replace the placeholder with a proper application icon
3. **Test on different systems**: Try the Flatpak on various Linux distributions
4. **Create bundles**: Use `./build-flatpak.sh bundle` for easy distribution
5. **Consider Flathub**: Submit to Flathub for official distribution

## Troubleshooting

If you encounter issues:
- Check README-flatpak.md for detailed troubleshooting
- Ensure flatpak-builder is installed
- Verify the Freedesktop SDK is available
- Check build logs for specific errors

## Notes

- The current manifest uses pre-built wxPython wheels for faster builds
- FFmpeg and codecs are built from source for compatibility
- Configuration files are stored in `~/.var/app/io.github.arcum42.vidtool/config/vidtool/`
- The app runs in a sandbox but has broad filesystem access for functionality
