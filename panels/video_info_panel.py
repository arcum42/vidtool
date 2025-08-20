#!/usr/bin/env python

import wx
import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app_state import AppState


class VideoInfoPanel(wx.Panel):
    """Panel for displaying detailed video information."""
    
    LABELS = [
        ("Filename:", "filename"),
        ("Resolution:", "resolution"),
        ("Size:", "size"),
        ("Runtime:", "runtime"),
        ("Codec:", "codec"),
        ("Video Streams:", "video_streams"),
        ("Audio Streams:", "audio_streams"),
        ("Subtitle Streams:", "subtitle_streams"),
        ("Data Streams:", "data_streams"),
    ]

    def __init__(self, parent, app_state: "AppState"):
        super().__init__(parent)
        self.app_state = app_state
        self.fields = {}
        self.InitUI()

    def InitUI(self):
        """Initialize the UI elements for video information display."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        for label_text, field_key in self.LABELS:
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)
            label = wx.StaticText(self, label=label_text)
            label.SetMinSize((120, -1))
            
            if field_key in ["video_streams", "audio_streams", "subtitle_streams", "data_streams"]:
                # Use multiline text for stream info
                field = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
                field.SetMinSize((-1, 60))
            else:
                # Use single line text for basic info
                field = wx.TextCtrl(self, style=wx.TE_READONLY)
            
            self.fields[field_key] = field
            
            row_sizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
            row_sizer.Add(field, 1, wx.ALL | wx.EXPAND, 5)
            sizer.Add(row_sizer, 0, wx.EXPAND)
        
        self.SetSizer(sizer)

    def update_info(self, info):
        """Update the display with video information."""
        self.fields["filename"].SetValue(pathlib.Path(info.filename).name)
        self.fields["resolution"].SetValue(f"{info.max_width}x{info.max_height}")
        size = (f"{info.size_kb:.2f} KB" if info.size_kb < 1024 else
                f"{info.size_mb:.2f} MB" if info.size_mb < 1024 else
                f"{info.size_gb:.2f} GB")
        self.fields["size"].SetValue(size)
        self.fields["runtime"].SetValue(str(info.runtime))
        codec_list = []

        for key in ("video_streams", "audio_streams", "subtitle_streams", "data_streams"):
            streams = getattr(info, key)
            if streams:
                codec_list.append(", ".join(s["codec_long_name"] for s in streams))

        self.fields["codec"].SetValue(" / ".join(codec_list))
        self.fields["audio_streams"].SetValue(
            "\n".join(info.get_audio_stream_description(s) for s in info.audio_streams).strip())
        self.fields["video_streams"].SetValue(
            "\n".join(info.get_video_stream_description(s) for s in info.video_streams).strip())
        self.fields["subtitle_streams"].SetValue(
            "\n".join(info.get_subtitle_stream_description(s) for s in info.subtitle_streams).strip())
        self.fields["data_streams"].SetValue(
            "\n".join(info.get_data_stream_description(s) for s in info.data_streams).strip())
