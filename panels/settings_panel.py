#!/usr/bin/env python

import wx
import pathlib
from typing import TYPE_CHECKING

import modules.video as video
from modules.video import FFmpegNotFoundError
from modules.logging_config import get_logger, set_log_level
import logging

if TYPE_CHECKING:
    from app_state import AppState

logger = get_logger('settings_panel')


class SettingsPanel(wx.Panel):
    """Panel for application settings configuration."""
    
    def __init__(self, parent, app_state: "AppState"):
        self.app_state = app_state
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # ffmpeg
        ffmpeg_box = wx.BoxSizer(wx.HORIZONTAL)
        ffmpeg_label = wx.StaticText(self, label="ffmpeg binary:")
        self.ffmpeg_path = wx.TextCtrl(self)
        self.ffmpeg_path.SetValue(self.app_state.config.get("ffmpeg_bin", ""))
        ffmpeg_browse = wx.Button(self, label="Browse")
        ffmpeg_browse.Bind(wx.EVT_BUTTON, lambda evt: self.on_browse(evt, self.ffmpeg_path))
        ffmpeg_box.Add(ffmpeg_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        ffmpeg_box.Add(self.ffmpeg_path, 1, wx.ALL | wx.EXPAND, 5)
        ffmpeg_box.Add(ffmpeg_browse, 0, wx.ALL, 5)

        # ffprobe
        ffprobe_box = wx.BoxSizer(wx.HORIZONTAL)
        ffprobe_label = wx.StaticText(self, label="ffprobe binary:")
        self.ffprobe_path = wx.TextCtrl(self)
        self.ffprobe_path.SetValue(self.app_state.config.get("ffprobe_bin", ""))
        ffprobe_browse = wx.Button(self, label="Browse")
        ffprobe_browse.Bind(wx.EVT_BUTTON, lambda evt: self.on_browse(evt, self.ffprobe_path))
        ffprobe_box.Add(ffprobe_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        ffprobe_box.Add(self.ffprobe_path, 1, wx.ALL | wx.EXPAND, 5)
        ffprobe_box.Add(ffprobe_browse, 0, wx.ALL, 5)

        # ffplay
        ffplay_box = wx.BoxSizer(wx.HORIZONTAL)
        ffplay_label = wx.StaticText(self, label="ffplay binary:")
        self.ffplay_path = wx.TextCtrl(self)
        self.ffplay_path.SetValue(self.app_state.config.get("ffplay_bin", ""))
        ffplay_browse = wx.Button(self, label="Browse")
        ffplay_browse.Bind(wx.EVT_BUTTON, lambda evt: self.on_browse(evt, self.ffplay_path))
        ffplay_box.Add(ffplay_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        ffplay_box.Add(self.ffplay_path, 1, wx.ALL | wx.EXPAND, 5)
        ffplay_box.Add(ffplay_browse, 0, wx.ALL, 5)

        # Auto-expand video info panel setting
        auto_expand_box = wx.BoxSizer(wx.HORIZONTAL)
        self.auto_expand_checkbox = wx.CheckBox(self, label="Auto-expand video info panel")
        self.auto_expand_checkbox.SetValue(self.app_state.config.get("auto_expand_video_info", False))
        auto_expand_help = wx.StaticText(self, label="Automatically expand the video info panel when selecting a video")
        auto_expand_help.SetFont(auto_expand_help.GetFont().Smaller())
        
        auto_expand_box.Add(self.auto_expand_checkbox, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        auto_expand_box.Add(auto_expand_help, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # Log level setting
        log_level_box = wx.BoxSizer(wx.HORIZONTAL)
        log_level_label = wx.StaticText(self, label="Log level:")
        self.log_level_choice = wx.ComboBox(self, choices=["DEBUG", "INFO", "WARNING", "ERROR"], style=wx.CB_READONLY)
        current_log_level = self.app_state.config.get("log_level", "INFO")
        if current_log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            self.log_level_choice.SetValue(current_log_level)
        else:
            self.log_level_choice.SetValue("INFO")
        
        log_level_help = wx.StaticText(self, label="Controls verbosity of console output and log file detail")
        log_level_help.SetFont(log_level_help.GetFont().Smaller())
        
        log_level_box.Add(log_level_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        log_level_box.Add(self.log_level_choice, 0, wx.ALL, 5)
        log_level_box.Add(log_level_help, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # Save button
        save_btn = wx.Button(self, label="Save Settings")
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)

        sizer.Add(ffmpeg_box, 0, wx.EXPAND)
        sizer.Add(ffprobe_box, 0, wx.EXPAND)
        sizer.Add(ffplay_box, 0, wx.EXPAND)
        sizer.Add(auto_expand_box, 0, wx.EXPAND)
        sizer.Add(log_level_box, 0, wx.EXPAND)
        sizer.Add(save_btn, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizer(sizer)

    def on_browse(self, event, textbox):
        """Browse for binary file."""
        dlg = wx.FileDialog(self, "Choose binary", wildcard="*", style=wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            textbox.SetValue(dlg.GetPath())
        dlg.Destroy()

    def on_save(self, event):
        """Save settings with validation."""
        ffmpeg_path = self.ffmpeg_path.GetValue().strip()
        ffprobe_path = self.ffprobe_path.GetValue().strip()
        ffplay_path = self.ffplay_path.GetValue().strip()
        log_level = self.log_level_choice.GetValue()
        auto_expand_video_info = self.auto_expand_checkbox.GetValue()
        
        # Validate paths if provided
        invalid_paths = []
        for name, path in [("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path), ("ffplay", ffplay_path)]:
            if path and not pathlib.Path(path).exists():
                invalid_paths.append(f"{name}: {path}")
        
        if invalid_paths:
            wx.MessageBox(f"Invalid paths found:\n\n" + "\n".join(invalid_paths) + 
                         "\n\nSettings not saved. Please check the paths.", 
                         "Invalid Paths", wx.OK | wx.ICON_ERROR)
            return
        
        # Save to config
        self.app_state.config["ffmpeg_bin"] = ffmpeg_path
        self.app_state.config["ffprobe_bin"] = ffprobe_path
        self.app_state.config["ffplay_bin"] = ffplay_path
        self.app_state.config["log_level"] = log_level
        self.app_state.config["auto_expand_video_info"] = auto_expand_video_info

        # Update module-level variables
        video.ffmpeg_bin = ffmpeg_path or "ffmpeg"
        video.ffprobe_bin = ffprobe_path or "ffprobe"
        video.ffplay_bin = ffplay_path or "ffplay"
        
        # Update log level immediately
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR
        }
        if log_level in level_map:
            set_log_level(level_map[log_level])
            logger.info(f"Log level changed to {log_level}")
        
        # Save the config to disk
        self.app_state.save_config()
        
        # Test FFmpeg availability with new settings
        try:
            video.check_ffmpeg_availability()
            wx.MessageBox("Settings saved and FFmpeg tools verified successfully!", 
                         "Settings Saved", wx.OK | wx.ICON_INFORMATION)
        except FFmpegNotFoundError as e:
            wx.MessageBox(f"Settings saved, but FFmpeg tools not found:\n\n{e}\n\n" +
                         "Please ensure FFmpeg is installed or provide correct paths.", 
                         "Settings Saved - Warning", wx.OK | wx.ICON_WARNING)
