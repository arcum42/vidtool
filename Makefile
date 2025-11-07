.PHONY: help build test install bundle clean uninstall check-deps

help:
	@echo "VidTool Flatpak Build System"
	@echo "============================="
	@echo ""
	@echo "Available targets:"
	@echo "  make build      - Build the Flatpak"
	@echo "  make test       - Run the app without installing"
	@echo "  make install    - Install the Flatpak locally"
	@echo "  make bundle     - Create a distributable .flatpak file"
	@echo "  make clean      - Remove build artifacts"
	@echo "  make uninstall  - Uninstall the Flatpak"
	@echo "  make check-deps - Check for required dependencies"

check-deps:
	@echo "Checking dependencies..."
	@command -v flatpak-builder >/dev/null 2>&1 || { echo "Error: flatpak-builder not found"; exit 1; }
	@flatpak list | grep -q "org.freedesktop.Sdk.*23.08" || { echo "Error: Freedesktop SDK 23.08 not found"; exit 1; }
	@echo "All dependencies OK"

build: check-deps
	flatpak-builder --force-clean build-dir io.github.arcum42.vidtool.yml

test: build
	flatpak-builder --run build-dir io.github.arcum42.vidtool.yml vidtool

install: check-deps
	flatpak-builder --user --install --force-clean build-dir io.github.arcum42.vidtool.yml

bundle: check-deps
	flatpak-builder --repo=repo --force-clean build-dir io.github.arcum42.vidtool.yml
	flatpak build-bundle repo vidtool.flatpak io.github.arcum42.vidtool

clean:
	rm -rf build-dir repo .flatpak-builder

uninstall:
	flatpak uninstall --user -y io.github.arcum42.vidtool || true
