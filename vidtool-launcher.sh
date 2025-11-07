#!/bin/bash
# Launcher script for VidTool Flatpak

cd /app/share/vidtool
exec python3 app.py "$@"
