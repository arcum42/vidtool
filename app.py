#!/usr/bin/python

import wx
import os
import pathlib
import modules.video as video
from modules.video import VIDEO_EXTENSIONS

class ReencodeOptions(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Reencode Options", size=(400, 300))

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.extension_label = wx.StaticText(panel, label="Output Extension:")
        self.extension_choice = wx.Choice(panel, choices=VIDEO_EXTENSIONS)
        self.extension_choice.SetSelection(0)

        self.video_codec_label = wx.StaticText(panel, label="Video Codec:")
        self.video_codec = wx.TextCtrl(panel)

        self.audio_codec_label = wx.StaticText(panel, label="Audio Codec:")
        self.audio_codec = wx.TextCtrl(panel)

        self.include_subtitles = wx.CheckBox(panel, label="Include Subtitles")
        self.include_data_streams = wx.CheckBox(panel, label="Include Data Streams")

        sizer.Add(self.extension_label, 0, wx.ALL, 5)
        sizer.Add(self.extension_choice, 0, wx.ALL | wx.EXPAND, 5)
        sizer.Add(self.video_codec_label, 0, wx.ALL, 5)
        sizer.Add(self.video_codec, 0, wx.ALL | wx.EXPAND, 5)
        sizer.Add(self.audio_codec_label, 0, wx.ALL, 5)
        sizer.Add(self.audio_codec, 0, wx.ALL | wx.EXPAND, 5)
        sizer.Add(self.include_subtitles, 0, wx.ALL, 5)
        sizer.Add(self.include_data_streams, 0, wx.ALL, 5)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, wx.ID_OK, label="OK")
        cancel_button = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        button_sizer.Add(ok_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)

        sizer.Add(button_sizer, 0, wx.ALIGN_CENTER)

        panel.SetSizer(sizer)
        self.Fit()

class VideoInfoPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        
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
        
        self.video_info = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.video_info.SetValue("Select a video file from the list.")
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(self.resolution_label, 0, wx.ALL, 5)
        row1.Add(self.resolution, 1, wx.EXPAND | wx.ALL, 5)
        row1.Add(self.runtime_label, 0, wx.ALL, 5)
        row1.Add(self.runtime, 1, wx.EXPAND | wx.ALL, 5)
        
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(self.codec_label, 0, wx.ALL, 5)
        row2.Add(self.codec, 1, wx.EXPAND | wx.ALL, 5)
        
        row3 = wx.BoxSizer(wx.HORIZONTAL)
        row3.Add(self.audio_streams_label, 0, wx.ALL, 5)
        row3.Add(self.audio_streams, 1, wx.EXPAND | wx.ALL, 5)
        
        row4 = wx.BoxSizer(wx.HORIZONTAL)
        row4.Add(self.video_streams_label, 0, wx.ALL, 5)
        row4.Add(self.video_streams, 1, wx.EXPAND | wx.ALL, 5)
        
        row5 = wx.BoxSizer(wx.HORIZONTAL)
        row5.Add(self.subtitle_streams_label, 0, wx.ALL, 5)
        row5.Add(self.subtitle_streams, 1, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(row1, 0, wx.EXPAND)
        sizer.Add(row2, 0, wx.EXPAND)
        sizer.Add(row3, 0, wx.EXPAND)
        sizer.Add(row4, 0, wx.EXPAND)
        sizer.Add(row5, 0, wx.EXPAND)
        sizer.Add(self.video_info, 1, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(sizer)

    def update_info(self, info):
        self.resolution.SetValue(f"{info.max_width}x{info.max_height}")
        self.runtime.SetValue(str(info.runtime))
        self.codec.SetValue(", ".join([stream["codec_long_name"] for stream in info.video_streams]))
        
        audio_stream_text = ""
        for stream in info.audio_streams:
            audio_stream_text += f"{info.get_audio_stream_description(stream)} \n"
        self.audio_streams.SetValue(audio_stream_text.strip())
        
        video_stream_text = ""
        for stream in info.video_streams:
            video_stream_text = f"{info.get_video_stream_description(stream)} \n"
        self.video_streams.SetValue(video_stream_text.strip())
        
        subtitle_stream_text = ""
        for stream in info.subtitle_streams:
            subtitle_stream_text = f"{info.get_subtitle_stream_description(stream)} \n"
        self.subtitle_streams.SetValue(subtitle_stream_text.strip())
        self.video_info.SetValue(info.get_info_block())


class MyFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="Vid Tool")

        # Create a panel and sizers
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Create a notebook
        notebook = wx.Notebook(panel)
        main_panel = wx.Panel(notebook)
        log_panel = wx.Panel(notebook)

        notebook.AddPage(main_panel, "Main")
        notebook.AddPage(log_panel, "Log")

        # Main panel content
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        top = wx.BoxSizer(wx.HORIZONTAL)
        middle = wx.BoxSizer(wx.HORIZONTAL)
        top.SetMinSize((800, 50))

        # On the top, create a button to open a file dialog
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
        # In the middle, create a listbox with checkboxes
        self.listbox = wx.CheckListBox(main_panel)
        self.populateListBox()
        self.listbox.Bind(wx.EVT_LISTBOX, self.OnListBox)

        # To the right of the listbox, add the VideoInfoPanel
        self.video_info_panel = VideoInfoPanel(main_panel)

        middle.Add(self.listbox, 1, wx.LEFT | wx.EXPAND, 5)
        middle.Add(self.video_info_panel, 1, wx.RIGHT | wx.EXPAND, 5)

        main_sizer.Add(top, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(middle, 1, wx.EXPAND | wx.ALL, 5)

        main_panel.SetSizer(main_sizer)

        # Log panel content
        log_sizer = wx.BoxSizer(wx.VERTICAL)
        self.text = wx.TextCtrl(log_panel, style=wx.TE_MULTILINE)
        self.text.SetValue("This is a text control.")
        log_sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 5)
        log_panel.SetSizer(log_sizer)

        sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
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
