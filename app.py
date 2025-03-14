#!/usr/bin/env python

import wx
import pathlib
import modules.video as video
from modules.video import VIDEO_EXTENSIONS

class ReencodePane(wx.CollapsiblePane):
    def __init__(self, parent):
        super().__init__(parent, label="Reencode Options", style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE)
        self.parent = parent
        
        panel = self.GetPane()
        re_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.OnExpand)


        self.extension_label = wx.StaticText(panel, label="Output Extension:")
        self.extension_choice = wx.Choice(panel, choices=list(VIDEO_EXTENSIONS))
        self.extension_choice.SetSelection(0)

        self.video_codec_label = wx.StaticText(panel, label="Video Codec:")
        self.video_codec = wx.TextCtrl(panel)

        self.audio_codec_label = wx.StaticText(panel, label="Audio Codec:")
        self.audio_codec = wx.TextCtrl(panel)

        self.include_subtitles = wx.CheckBox(panel, label="Include Subtitles")
        self.include_data_streams = wx.CheckBox(panel, label="Include Data Streams")

        re_sizer.Add(self.extension_label, 0, wx.ALL, 5)
        re_sizer.Add(self.extension_choice, 0, wx.ALL | wx.EXPAND, 5)
        re_sizer.Add(self.video_codec_label, 0, wx.ALL, 5)
        re_sizer.Add(self.video_codec, 0, wx.ALL | wx.EXPAND, 5)
        re_sizer.Add(self.audio_codec_label, 0, wx.ALL, 5)
        re_sizer.Add(self.audio_codec, 0, wx.ALL | wx.EXPAND, 5)
        re_sizer.Add(self.include_subtitles, 0, wx.ALL, 5)
        re_sizer.Add(self.include_data_streams, 0, wx.ALL, 5)
        
        panel.SetSizer(re_sizer)
    
    def OnExpand(self, event):
        self.Layout()
        self.Fit()
        parent = self.GetParent()
        parent.Layout()
        parent.Fit()

    def OnReencode(self, event):
        print("Reencode button clicked")
        
class VideoInfoPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.filename_label = wx.StaticText(self, label="Filename:")
        self.filename = wx.TextCtrl(self, style=wx.TE_READONLY)
        
        self.resolution_label = wx.StaticText(self, label="Resolution:")
        self.resolution = wx.TextCtrl(self, style=wx.TE_READONLY)
        
        self.runtime_label = wx.StaticText(self, label="Runtime:")
        self.runtime = wx.TextCtrl(self, style=wx.TE_READONLY)
        
        self.codec_label = wx.StaticText(self, label="Codec:")
        self.codec = wx.TextCtrl(self, style=wx.TE_READONLY)
        
        self.audio_streams_label = wx.StaticText(self, label="Audio Streams:")
        self.audio_streams = wx.TextCtrl(self, style=wx.TE_READONLY)
        
        self.video_streams_label = wx.StaticText(self, label="Video Streams:")
        self.video_streams = wx.TextCtrl(self, style=wx.TE_READONLY)
        
        self.subtitle_streams_label = wx.StaticText(self, label="Subtitle Streams:")
        self.subtitle_streams = wx.TextCtrl(self, style=wx.TE_READONLY)
        
        self.data_streams_label = wx.StaticText(self, label="Data Streams:")
        self.data_streams = wx.TextCtrl(self, style=wx.TE_READONLY)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        filename_row = wx.BoxSizer(wx.HORIZONTAL)
        filename_row.Add(self.filename_label, 0, wx.ALL, 5)
        filename_row.Add(self.filename, 1, wx.EXPAND | wx.ALL, 5)
        
        resolution_runtime_row = wx.BoxSizer(wx.HORIZONTAL)
        resolution_runtime_row.Add(self.resolution_label, 0, wx.ALL, 5)
        resolution_runtime_row.Add(self.resolution, 1, wx.EXPAND | wx.ALL, 5)
        resolution_runtime_row.Add(self.runtime_label, 0, wx.ALL, 5)
        resolution_runtime_row.Add(self.runtime, 1, wx.EXPAND | wx.ALL, 5)
        
        codec_row = wx.BoxSizer(wx.HORIZONTAL)
        codec_row.Add(self.codec_label, 0, wx.ALL, 5)
        codec_row.Add(self.codec, 1, wx.EXPAND | wx.ALL, 5)
        
        audio_streams_row = wx.BoxSizer(wx.HORIZONTAL)
        audio_streams_row.Add(self.audio_streams_label, 0, wx.ALL, 5)
        audio_streams_row.Add(self.audio_streams, 1, wx.EXPAND | wx.ALL, 5)
        
        video_streams_row = wx.BoxSizer(wx.HORIZONTAL)
        video_streams_row.Add(self.video_streams_label, 0, wx.ALL, 5)
        video_streams_row.Add(self.video_streams, 1, wx.EXPAND | wx.ALL, 5)
        
        subtitle_streams_row = wx.BoxSizer(wx.HORIZONTAL)
        subtitle_streams_row.Add(self.subtitle_streams_label, 0, wx.ALL, 5)
        subtitle_streams_row.Add(self.subtitle_streams, 1, wx.EXPAND | wx.ALL, 5)
        
        data_streams_row = wx.BoxSizer(wx.HORIZONTAL)
        data_streams_row.Add(self.data_streams_label, 0, wx.ALL, 5)
        data_streams_row.Add(self.data_streams, 1, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(filename_row, 0, wx.EXPAND)
        sizer.Add(resolution_runtime_row, 0, wx.EXPAND)
        sizer.Add(codec_row, 0, wx.EXPAND)
        sizer.Add(audio_streams_row, 0, wx.EXPAND)
        sizer.Add(video_streams_row, 0, wx.EXPAND)
        sizer.Add(subtitle_streams_row, 0, wx.EXPAND)
        sizer.Add(data_streams_row, 0, wx.EXPAND)
        
        self.SetSizer(sizer)

    def update_info(self, info):
        self.filename.SetValue(pathlib.Path(info.filename).name)
        self.resolution.SetValue(f"{info.max_width}x{info.max_height}")
        self.runtime.SetValue(str(info.runtime))
        codec_list = []
        if info.video_streams:
            codec_list.append(", ".join([stream["codec_long_name"] for stream in info.video_streams]))
        if info.audio_streams:
            codec_list.append(", ".join([stream["codec_long_name"] for stream in info.audio_streams]))
        if info.subtitle_streams:
            codec_list.append(", ".join([stream["codec_long_name"] for stream in info.subtitle_streams]))
        if info.data_streams:
            codec_list.append(", ".join([stream["codec_long_name"] for stream in info.data_streams]))
        self.codec.SetValue(" / ".join(codec_list))
        
        audio_stream_text = "\n".join([info.get_audio_stream_description(stream) for stream in info.audio_streams])
        self.audio_streams.SetValue(audio_stream_text.strip())
        
        video_stream_text = "\n".join([info.get_video_stream_description(stream) for stream in info.video_streams])
        self.video_streams.SetValue(video_stream_text.strip())
        
        subtitle_stream_text = "\n".join([info.get_subtitle_stream_description(stream) for stream in info.subtitle_streams])
        self.subtitle_streams.SetValue(subtitle_stream_text.strip())

class MyFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="Vid Tool")

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        notebook = wx.Notebook(panel)
        main_panel = wx.Panel(notebook)
        log_panel = wx.Panel(notebook)

        notebook.AddPage(main_panel, "Main")
        notebook.AddPage(log_panel, "Log")

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        top = wx.BoxSizer(wx.HORIZONTAL)
        middle = wx.BoxSizer(wx.HORIZONTAL)
        bottom = wx.BoxSizer(wx.VERTICAL)
        top.SetMinSize((800, 50))

        self.label = wx.StaticText(main_panel, label="Directory", style=wx.ALIGN_CENTER)
        top.Add(self.label, 0, wx.SHAPED | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 5)

        self.working_dir_box = wx.TextCtrl(main_panel)
        self.working_dir = pathlib.Path.cwd()
        self.working_dir_box.SetValue(str(self.working_dir))
        top.Add(self.working_dir_box, 1, wx.EXPAND | wx.TOP)

        self.button = wx.Button(main_panel, label="Browse")
        self.button.SetDefault()
        self.button.SetFocus()
        top.Add(self.button, 0, wx.EXPAND | wx.RIGHT | wx.TOP, 5)
        self.button.Bind(wx.EVT_BUTTON, self.OnChangeDir)

        self.listbox = wx.CheckListBox(main_panel)
        self.populateListBox()
        self.listbox.Bind(wx.EVT_LISTBOX, self.OnListBox)

        self.video_info_panel = VideoInfoPanel(main_panel)

        middle.Add(self.listbox, 1, wx.LEFT | wx.EXPAND, 5)
        middle.Add(self.video_info_panel, 1, wx.RIGHT | wx.EXPAND, 5)
        
        self.reencode_pane = ReencodePane(main_panel)
        self.reencode_pane.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.reencode_pane.SetSize((200, 100))
        bottom.Add(self.reencode_pane, 0, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(top, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(middle, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(bottom, 0, wx.EXPAND | wx.ALL, 5)

        main_panel.SetSizer(main_sizer)

        log_sizer = wx.BoxSizer(wx.VERTICAL)
        self.text = wx.TextCtrl(log_panel, style=wx.TE_MULTILINE)
        self.text.SetValue("This is a text control.")
        log_sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 5)
        log_panel.SetSizer(log_sizer)

        sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)

        self.file_progress = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        self.total_progress = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        sizer.Add(wx.StaticText(panel, label="File Progress:"), 0, wx.ALL, 5)
        sizer.Add(self.file_progress, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(wx.StaticText(panel, label="Total Progress:"), 0, wx.ALL, 5)
        sizer.Add(self.total_progress, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)

        self.CreateStatusBar()
        self.SetStatusText("Welcome to Vid Tool!")

        self.SetSize((1200, 600))
        self.Center()

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Show()

    def OnChangeDir(self, event):
        dlg = wx.DirDialog(
            self,
            "Choose a directory:",
            str(self.working_dir),
            wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.working_dir = pathlib.Path(dlg.GetPath()).resolve()
            self.working_dir_box.SetValue(str(self.working_dir))
            self.SetStatusText(f"Working directory: {str(self.working_dir)}")
            self.populateListBox()
        dlg.Destroy()

    def populateListBox(self):
        self.listbox.Clear()
        files = (
            p.resolve()
            for p in pathlib.Path(self.working_dir).glob("**/*")
            if p.suffix in VIDEO_EXTENSIONS
        )
        for video in files:
            self.listbox.Append(str(video.relative_to(self.working_dir)))

    def OnClose(self, event):
        self.Destroy()

    def OnListBox(self, event):
        selection = event.GetSelection()
        item = self.listbox.GetString(selection)
        self.SetStatusText(f"Selected: {item}")
        info = video.info(self.working_dir / item)
        self.video_info_panel.update_info(info)

if __name__ == "__main__":
    app = wx.App()
    frame = MyFrame()
    app.MainLoop()
