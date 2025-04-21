#!/usr/bin/env python

import wx
import pathlib
import modules.video as video
from modules.video import VIDEO_EXTENSIONS, VIDEO_CODECS, AUDIO_CODECS
import threading
import time
import subprocess
    
global video_list, selected_video
class ReencodePane(wx.CollapsiblePane):
    def __init__(self, parent):
        super().__init__(parent, label="Reencode Options", style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE)

        panel = self.GetPane()
        re_vsizer = wx.BoxSizer(wx.VERTICAL)
        re_hsizer1 = wx.BoxSizer(wx.HORIZONTAL)
        re_hsizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.OnExpand)

        self.vcodec_checkbox = wx.CheckBox(panel, label="Video Codec:")
        self.vcodec_choice = wx.ComboBox(panel, choices=list(VIDEO_CODECS))
        self.vcodec_choice.SetSelection(VIDEO_CODECS.index("libx265"))

        self.acodec_checkbox = wx.CheckBox(panel, label="Audio Codec:")
        self.acodec_choice = wx.ComboBox(panel, choices=list(AUDIO_CODECS))
        self.acodec_choice.SetSelection(0)

        self.suffix_label = wx.StaticText(panel, label="Suffix:")
        self.suffix_textbox = wx.TextCtrl(panel)
        self.suffix_textbox.SetValue("_copy")
        
        self.extension_label = wx.StaticText(panel, label="Extension:")
        self.extension_choice = wx.ComboBox(panel, choices=list(VIDEO_EXTENSIONS))
        self.extension_choice.SetSelection(VIDEO_EXTENSIONS.index(".mkv"))

        self.exclude_subtitles = wx.CheckBox(panel, label="No Subtitles")
        self.exclude_data_streams = wx.CheckBox(panel, label="No Data")
        self.fix_res = wx.CheckBox(panel, label="Fix Resolution")
        self.fix_errors = wx.CheckBox(panel, label="Fix Errors")

        self.crf_checkbox = wx.CheckBox(panel, label="CRF:")
        self.crf_int = wx.SpinCtrl(panel, initial = 28, min = 4, max = 63)

        self.reencode_button = wx.Button(panel, label="Reencode")
        self.reencode_button.Bind(wx.EVT_BUTTON, self.OnReencode)

        self.total_label = wx.StaticText(panel, label="Total Progress:")
        self.total_progress = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)

        re_hsizer1.Add(self.vcodec_checkbox, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.vcodec_choice, 0, wx.ALL | wx.EXPAND, 5)
        re_hsizer1.Add(self.acodec_checkbox, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.acodec_choice, 0, wx.ALL | wx.EXPAND, 10)

        re_hsizer1.Add(self.suffix_label, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.suffix_textbox, 0, wx.ALL | wx.EXPAND, 10)
        re_hsizer1.Add(self.extension_label, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.extension_choice, 0, wx.ALL | wx.EXPAND, 5)

        re_hsizer2.Add(self.exclude_subtitles, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer2.Add(self.exclude_data_streams, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer2.Add(self.fix_res, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer2.Add(self.fix_errors, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer2.Add(self.crf_checkbox, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer2.Add(self.crf_int, 0, wx.ALL, 5)
        re_hsizer2.AddStretchSpacer()
        
        re_hsizer1.Add(self.reencode_button, 0, wx.ALL | wx.EXPAND, 10)
        
        re_vsizer.Add(re_hsizer1, 0, wx.ALL | wx.EXPAND, 0)
        re_vsizer.Add(re_hsizer2, 0, wx.ALL | wx.EXPAND, 0)
        re_vsizer.Add(self.total_label, 0, wx.ALL, 5)
        re_vsizer.Add(self.total_progress, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(re_vsizer)

    def OnExpand(self, event):
        self.Layout()
        self.Fit()
        parent = self.GetParent()
        parent.Layout()
        parent.Fit()

    def OnReencode(self, event):
        print("Reencode button clicked")
        output_extension = self.extension_choice.GetStringSelection()
        output_suffix = self.suffix_textbox.GetValue()

        encode_video = self.vcodec_checkbox.GetValue()
        video_codec = self.vcodec_choice.GetStringSelection()

        encode_audio = self.acodec_checkbox.GetValue()
        audio_codec = self.acodec_choice.GetStringSelection()

        no_subs = self.exclude_subtitles.GetValue()
        no_data = self.exclude_data_streams.GetValue()
        
        fix_resolution = self.fix_res.GetValue()
        fix_err = self.fix_errors.GetValue()

        use_crf = self.crf_checkbox.GetValue()
        crf_value = str(self.crf_int.GetValue())
        
        wx.CallAfter(self.ReEncodeAfter, output_extension, output_suffix, encode_video, video_codec, encode_audio, audio_codec, no_subs, no_data, fix_resolution, fix_err, use_crf, crf_value)

    def ReEncodeAfter( 
                    self,
                    output_extension, output_suffix, 
                    encode_video, video_codec, 
                    encode_audio, audio_codec, 
                    no_subs, no_data, fix_resolution, fix_err,
                    use_crf, crf_value
                    ):
        
        def do_execute(cmd):
            print(subprocess.list2cmdline(cmd))

            with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as p:
                for line in p.stdout:
                    print(line, end='')
                    wx.Yield()

        progress = 0

        vid_jobs = []
        for video_file in video_list:
            if not video_file: continue

            print(f"Encoding video_file: {video_file}")
            progress += 1

            try:
                encode_job = video.encode()
                encode_job.add_input(video_file)
                encode_job.add_output_from_input(file_append = output_suffix, file_extension = output_extension)
                if (encode_video): encode_job.set_video_codec(video_codec)
                if (encode_audio): encode_job.set_audio_codec(audio_codec)
                if (no_subs): encode_job.exclude_subtitles()
                if (no_data): encode_job.exclude_data()
                if (fix_resolution): encode_job.fix_resolution()
                if (fix_err): encode_job.fix_errors()
                if (use_crf): encode_job.set_crf(crf_value)
                if (pathlib.Path(encode_job.output).exists()):
                    print(f"Output file '{encode_job.output}' already exists. Skipping.")
                    continue
                
                vid_jobs.append(threading.Thread(name = f"encode_{progress}", target=do_execute(encode_job.reencode_str()), daemon = True))
            except:
                print("What-Ho? There was some sort of issue, I'm afraid...")
            
        for job in vid_jobs:
            job.start()
class VideoInfoPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent, style = wx.RAISED_BORDER)

        self.filename_label = wx.StaticText(self, label="Filename:")
        self.filename = wx.TextCtrl(self, style=wx.TE_READONLY)

        self.resolution_label = wx.StaticText(self, label="Resolution:")
        self.resolution = wx.TextCtrl(self, style=wx.TE_READONLY)
        
        self.size_label = wx.StaticText(self, label="Size:")
        self.size = wx.TextCtrl(self, style=wx.TE_READONLY)

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
        resolution_runtime_row.Add(self.size_label, 0, wx.ALL, 5)
        resolution_runtime_row.Add(self.size, 1, wx.EXPAND | wx.ALL, 5)

        codec_row = wx.BoxSizer(wx.HORIZONTAL)
        codec_row.Add(self.codec_label, 0, wx.ALL, 5)
        codec_row.Add(self.codec, 1, wx.EXPAND | wx.ALL, 5)

        video_streams_row = wx.BoxSizer(wx.HORIZONTAL)
        video_streams_row.Add(self.video_streams_label, 0, wx.ALL, 5)
        video_streams_row.Add(self.video_streams, 1, wx.EXPAND | wx.ALL, 5)

        audio_streams_row = wx.BoxSizer(wx.HORIZONTAL)
        audio_streams_row.Add(self.audio_streams_label, 0, wx.ALL, 5)
        audio_streams_row.Add(self.audio_streams, 1, wx.EXPAND | wx.ALL, 5)

        subtitle_streams_row = wx.BoxSizer(wx.HORIZONTAL)
        subtitle_streams_row.Add(self.subtitle_streams_label, 0, wx.ALL, 5)
        subtitle_streams_row.Add(self.subtitle_streams, 1, wx.EXPAND | wx.ALL, 5)

        data_streams_row = wx.BoxSizer(wx.HORIZONTAL)
        data_streams_row.Add(self.data_streams_label, 0, wx.ALL, 5)
        data_streams_row.Add(self.data_streams, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(filename_row, 0, wx.EXPAND)
        sizer.Add(resolution_runtime_row, 0, wx.EXPAND)
        sizer.Add(codec_row, 0, wx.EXPAND)
        sizer.Add(video_streams_row, 0, wx.EXPAND)
        sizer.Add(audio_streams_row, 0, wx.EXPAND)
        sizer.Add(subtitle_streams_row, 0, wx.EXPAND)
        sizer.Add(data_streams_row, 0, wx.EXPAND)

        self.SetSizer(sizer)

    def update_info(self, info):
        self.filename.SetValue(pathlib.Path(info.filename).name)
        self.resolution.SetValue(f"{info.max_width}x{info.max_height}")
        if (info.size_kb < 1024):
            self.size.SetValue(f"{info.size_kb:.2f} KB")
        elif (info.size_mb < 1024):
            self.size.SetValue(f"{info.size_mb:.2f} MB")
        else:
            self.size.SetValue(f"{info.size_gb:.2f} GB")

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
        play_size = wx.BoxSizer(wx.HORIZONTAL)
        bottom = wx.BoxSizer(wx.VERTICAL)
        
        self.label = wx.StaticText(main_panel, label="Directory", style=wx.ALIGN_CENTER)

        self.working_dir_box = wx.TextCtrl(main_panel)
        self.working_dir = pathlib.Path.cwd()
        self.working_dir_box.SetValue(str(self.working_dir))

        self.button = wx.BitmapButton(main_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_FOLDER_OPEN, wx.ART_BUTTON))
        self.button.SetDefault()
        self.button.SetFocus()
        self.button.Bind(wx.EVT_BUTTON, self.OnChangeDir)

        self.refresh_button = wx.BitmapButton(main_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_REDO, wx.ART_BUTTON))
        self.refresh_button.Bind(wx.EVT_BUTTON, self.OnRefresh)
        
        self.up_button = wx.BitmapButton(main_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_GO_TO_PARENT, wx.ART_BUTTON))
        self.up_button.Bind(wx.EVT_BUTTON, self.OnGoUp)

        top.Add(self.label, 0, wx.LEFT | wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        top.Add(self.working_dir_box, 1, wx.CENTRE | wx.ALL | wx.EXPAND, 0)
        top.Add(self.button, 0, wx.EXPAND | wx.RIGHT | wx.ALL, 5)
        top.Add(self.refresh_button, 0, wx.EXPAND | wx.RIGHT | wx.ALL, 5)
        top.Add(self.up_button, 0, wx.EXPAND | wx.RIGHT | wx.ALL, 5)

        self.listbox = wx.CheckListBox(main_panel)
        self.populateListBox()
        self.listbox.Bind(wx.EVT_LISTBOX, self.OnListBox)
        self.listbox.Bind(wx.EVT_CHECKLISTBOX, self.OnListBoxCheck)

        self.video_info_panel = VideoInfoPanel(main_panel)

        middle.Add(self.listbox, 1, wx.LEFT | wx.EXPAND, 5)
        middle.Add(self.video_info_panel, 1, wx.RIGHT | wx.EXPAND, 5)

        self.play_label = wx.StaticText(main_panel, label="Play Selection with ffplay:", style=wx.ALIGN_CENTER)
        self.play_button = wx.Button(main_panel, label="Play")
        self.play_button.Bind(wx.EVT_BUTTON, self.OnPlay)
        
        self.reencode_pane = ReencodePane(main_panel)
        self.reencode_pane.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.reencode_pane.SetSize((200, 100))
        
        play_size.Add(self.play_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        play_size.Add(self.play_button, 0, wx.ALL, 5)
        bottom.Add(self.reencode_pane, 0, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(top, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(middle, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(play_size, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(bottom, 0, wx.EXPAND | wx.ALL, 5)

        main_panel.SetSizer(main_sizer)

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

    def OnRefresh(self, event):
        self.populateListBox()
        self.SetStatusText("File list refreshed.")

    def OnGoUp(self, event):
        self.working_dir = self.working_dir.parent
        self.working_dir_box.SetValue(str(self.working_dir))
        self.SetStatusText(f"Working directory: {str(self.working_dir)}")
        self.populateListBox()

    def populateListBox(self):
        global video_list
        video_list = []
        self.listbox.Clear()
        files = sorted(
            p.resolve()
            for p in pathlib.Path(self.working_dir).glob("**/*")
            if p.suffix in VIDEO_EXTENSIONS
        )

        for video in files:
            self.listbox.Append(str(video.relative_to(self.working_dir)))

    def OnClose(self, event):
        self.Destroy()

    def OnListBox(self, event):
        global video_list, selected_video
        selection = event.GetSelection()
        item = self.listbox.GetString(selection)
        self.SetStatusText(f"Selected: {item}")
        selected_video = self.working_dir / item
        info = video.info(selected_video)
        self.video_info_panel.update_info(info)
    
    def OnListBoxCheck(self, event):
        global video_list, selected_video
        video_list = []
        for file in self.listbox.GetCheckedStrings():
            video_list.append(str(self.working_dir / file))
        
    def OnPlay(self, event):
        print("Play button clicked")
        video.play(selected_video)
        event.Skip(True)

class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame()
        frame.Show(True)
        frame.Centre()
        return True

if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
