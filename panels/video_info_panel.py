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
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Row 1: Filename (full width since it can be long)
        filename_sizer = wx.BoxSizer(wx.HORIZONTAL)
        filename_label = wx.StaticText(self, label="Filename:")
        filename_label.SetMinSize(wx.Size(80, -1))
        self.fields["filename"] = wx.TextCtrl(self, style=wx.TE_READONLY)
        filename_sizer.Add(filename_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        filename_sizer.Add(self.fields["filename"], 1, wx.ALL | wx.EXPAND, 3)
        main_sizer.Add(filename_sizer, 0, wx.EXPAND)
        
        # Row 2: Resolution, Size, Runtime (compact info in one row)
        info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Resolution
        res_label = wx.StaticText(self, label="Resolution:")
        res_label.SetMinSize(wx.Size(80, -1))
        self.fields["resolution"] = wx.TextCtrl(self, style=wx.TE_READONLY)
        self.fields["resolution"].SetMinSize(wx.Size(100, -1))
        
        # Size
        size_label = wx.StaticText(self, label="Size:")
        size_label.SetMinSize(wx.Size(40, -1))
        self.fields["size"] = wx.TextCtrl(self, style=wx.TE_READONLY)
        self.fields["size"].SetMinSize(wx.Size(100, -1))
        
        # Runtime
        runtime_label = wx.StaticText(self, label="Runtime:")
        runtime_label.SetMinSize(wx.Size(60, -1))
        self.fields["runtime"] = wx.TextCtrl(self, style=wx.TE_READONLY)
        self.fields["runtime"].SetMinSize(wx.Size(120, -1))
        
        info_sizer.Add(res_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        info_sizer.Add(self.fields["resolution"], 0, wx.ALL, 3)
        info_sizer.Add(size_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        info_sizer.Add(self.fields["size"], 0, wx.ALL, 3)
        info_sizer.Add(runtime_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        info_sizer.Add(self.fields["runtime"], 1, wx.ALL | wx.EXPAND, 3)
        main_sizer.Add(info_sizer, 0, wx.EXPAND)
        
        # Row 3: Codec summary (full width since it can be long)
        codec_sizer = wx.BoxSizer(wx.HORIZONTAL)
        codec_label = wx.StaticText(self, label="Codecs:")
        codec_label.SetMinSize(wx.Size(80, -1))
        self.fields["codec"] = wx.TextCtrl(self, style=wx.TE_READONLY)
        codec_sizer.Add(codec_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        codec_sizer.Add(self.fields["codec"], 1, wx.ALL | wx.EXPAND, 3)
        main_sizer.Add(codec_sizer, 0, wx.EXPAND)
        
        # Stream details - Row 1: Video and Audio
        stream_row1_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Video streams
        video_label = wx.StaticText(self, label="Video:")
        video_label.SetMinSize(wx.Size(50, -1))
        self.fields["video_streams"] = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.fields["video_streams"].SetMinSize(wx.Size(-1, 40))
        
        # Audio streams  
        audio_label = wx.StaticText(self, label="Audio:")
        audio_label.SetMinSize(wx.Size(50, -1))
        self.fields["audio_streams"] = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.fields["audio_streams"].SetMinSize(wx.Size(-1, 40))
        
        stream_row1_sizer.Add(video_label, 0, wx.ALL | wx.ALIGN_TOP, 3)
        stream_row1_sizer.Add(self.fields["video_streams"], 1, wx.ALL | wx.EXPAND, 3)
        stream_row1_sizer.Add(audio_label, 0, wx.ALL | wx.ALIGN_TOP, 3)
        stream_row1_sizer.Add(self.fields["audio_streams"], 1, wx.ALL | wx.EXPAND, 3)
        main_sizer.Add(stream_row1_sizer, 0, wx.EXPAND)
        
        # Stream details - Row 2: Subtitles and Data
        stream_row2_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Subtitle streams
        subtitle_label = wx.StaticText(self, label="Subtitles:")
        subtitle_label.SetMinSize(wx.Size(60, -1))
        self.fields["subtitle_streams"] = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.fields["subtitle_streams"].SetMinSize(wx.Size(-1, 40))
        
        # Data streams
        data_label = wx.StaticText(self, label="Data:")
        data_label.SetMinSize(wx.Size(40, -1))
        self.fields["data_streams"] = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.fields["data_streams"].SetMinSize(wx.Size(-1, 40))
        
        stream_row2_sizer.Add(subtitle_label, 0, wx.ALL | wx.ALIGN_TOP, 3)
        stream_row2_sizer.Add(self.fields["subtitle_streams"], 1, wx.ALL | wx.EXPAND, 3)
        stream_row2_sizer.Add(data_label, 0, wx.ALL | wx.ALIGN_TOP, 3)
        stream_row2_sizer.Add(self.fields["data_streams"], 1, wx.ALL | wx.EXPAND, 3)
        main_sizer.Add(stream_row2_sizer, 0, wx.EXPAND)
        
        self.SetSizer(main_sizer)

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
                codec_names = []
                for s in streams:
                    # Safely get codec name with fallbacks
                    codec_name = s.get("codec_long_name") or s.get("codec_name") or "Unknown"
                    codec_names.append(codec_name)
                if codec_names:
                    codec_list.append(", ".join(codec_names))

        self.fields["codec"].SetValue(" / ".join(codec_list))
        self.fields["audio_streams"].SetValue(
            "\n".join(info.get_audio_stream_description(s) for s in info.audio_streams).strip())
        self.fields["video_streams"].SetValue(
            "\n".join(info.get_video_stream_description(s) for s in info.video_streams).strip())
        self.fields["subtitle_streams"].SetValue(
            "\n".join(info.get_subtitle_stream_description(s) for s in info.subtitle_streams).strip())
        self.fields["data_streams"].SetValue(
            "\n".join(info.get_data_stream_description(s) for s in info.data_streams).strip())
