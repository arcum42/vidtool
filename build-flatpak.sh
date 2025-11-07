#!/bin/bash
# Build script for VidTool Flatpak

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}VidTool Flatpak Build Script${NC}"
echo "=============================="

# Check prerequisites
echo -n "Checking for flatpak-builder... "
if ! command -v flatpak-builder &> /dev/null; then
    echo -e "${RED}FAILED${NC}"
    echo "Please install flatpak-builder:"
    echo "  sudo apt install flatpak-builder  # Debian/Ubuntu"
    echo "  sudo dnf install flatpak-builder  # Fedora"
    exit 1
fi
echo -e "${GREEN}OK${NC}"

echo -n "Checking for Freedesktop SDK... "
if ! flatpak list | grep -q "org.freedesktop.Sdk.*24.08"; then
    echo -e "${YELLOW}NOT FOUND${NC}"
    echo "Installing Freedesktop SDK 24.08..."
    flatpak install -y flathub org.freedesktop.Platform//24.08 org.freedesktop.Sdk//24.08
else
    echo -e "${GREEN}OK${NC}"
fi

# Check for icon
if [ ! -f "io.github.arcum42.vidtool.png" ]; then
    echo -e "${YELLOW}Warning: Icon file not found${NC}"
    echo "Creating placeholder icon..."
    if command -v magick &> /dev/null; then
        magick -size 256x256 xc:'#3498db' -pointsize 72 -fill white -gravity center \
               -font DejaVu-Sans-Bold -annotate +0+0 'VT' io.github.arcum42.vidtool.png
    elif command -v convert &> /dev/null; then
        convert -size 256x256 xc:'#3498db' -pointsize 72 -fill white -gravity center \
                -font DejaVu-Sans-Bold -annotate +0+0 'VT' io.github.arcum42.vidtool.png
    else
        echo -e "${RED}ImageMagick not found. Please create io.github.arcum42.vidtool.png manually.${NC}"
        exit 1
    fi
fi

# Parse command line arguments
ACTION=${1:-build}

case "$ACTION" in
    build)
        echo ""
        echo -e "${GREEN}Building Flatpak...${NC}"
        echo -e "${YELLOW}Note: First build may take 50-80 minutes due to codec compilation${NC}"
        echo "Building: NASM, x264, x265, libvpx, wxWidgets, FFmpeg, and VidTool"
        echo ""
        flatpak-builder --force-clean build-dir io.github.arcum42.vidtool.yml
        echo ""
        echo -e "${GREEN}Build complete!${NC}"
        echo "To test: ./build-flatpak.sh test"
        echo "To install: ./build-flatpak.sh install"
        echo "To verify codecs: flatpak run --command=ffmpeg io.github.arcum42.vidtool -codecs | grep -E '264|265|vp8|vp9'"
        ;;
    
    test)
        echo ""
        echo -e "${GREEN}Running VidTool in Flatpak sandbox...${NC}"
        flatpak-builder --run build-dir io.github.arcum42.vidtool.yml vidtool
        ;;
    
    install)
        echo ""
        echo -e "${GREEN}Installing Flatpak locally...${NC}"
        flatpak-builder --user --install --force-clean build-dir io.github.arcum42.vidtool.yml
        echo ""
        echo -e "${GREEN}Installation complete!${NC}"
        echo "Run with: flatpak run io.github.arcum42.vidtool"
        ;;
    
    bundle)
        echo ""
        echo -e "${GREEN}Creating Flatpak bundle...${NC}"
        # Build and export to repo
        flatpak-builder --repo=repo --force-clean build-dir io.github.arcum42.vidtool.yml
        # Create bundle
        flatpak build-bundle repo vidtool.flatpak io.github.arcum42.vidtool
        echo ""
        echo -e "${GREEN}Bundle created: vidtool.flatpak${NC}"
        echo "Users can install with: flatpak install vidtool.flatpak"
        ;;
    
    clean)
        echo ""
        echo -e "${YELLOW}Cleaning build artifacts...${NC}"
        rm -rf build-dir repo .flatpak-builder
        echo -e "${GREEN}Clean complete!${NC}"
        ;;
    
    uninstall)
        echo ""
        echo -e "${YELLOW}Uninstalling VidTool Flatpak...${NC}"
        flatpak uninstall --user -y io.github.arcum42.vidtool || true
        echo -e "${GREEN}Uninstall complete!${NC}"
        ;;
    
    *)
        echo "Usage: $0 {build|test|install|bundle|clean|uninstall}"
        echo ""
        echo "Commands:"
        echo "  build     - Build the Flatpak (default)"
        echo "  test      - Run the app in sandbox without installing"
        echo "  install   - Install the Flatpak locally for current user"
        echo "  bundle    - Create a distributable .flatpak file"
        echo "  clean     - Remove all build artifacts"
        echo "  uninstall - Remove installed Flatpak"
        exit 1
        ;;
esac
