#!/usr/bin/env python

import wx
import pathlib
import modules.video as video
from modules.video import VIDEO_EXTENSIONS, VIDEO_CODECS, AUDIO_CODECS
import threading
import subprocess
import json

global video_list, selected_video, config, working_dir

video_list = []
config = {}

selected_video = None
working_dir = None
class VideoInfoPanel(wx.Panel):
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

    def __init__(self, parent):
        super().__init__(parent, style=wx.RAISED_BORDER)
        self.scrollable_panel = wx.ScrolledWindow(self, style=wx.VSCROLL | wx.HSCROLL)
        self.scrollable_panel.SetScrollRate(5, 5)
        self.fields = {}
        sizer = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        for label, attr in self.LABELS:
            lbl = wx.StaticText(self.scrollable_panel, label=label)
            txt = wx.TextCtrl(self.scrollable_panel, style=wx.TE_READONLY)
            self.fields[attr] = txt
            sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            sizer.Add(txt, 1, wx.EXPAND)
        sizer.AddGrowableCol(1, 1)
        self.scrollable_panel.SetSizer(sizer)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.scrollable_panel, 1, wx.EXPAND)
        self.SetSizer(main_sizer)

    def update_info(self, info):
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

class VideoList(wx.ListCtrl):
    COLS = [
        ('Filename', 300),
        ('Video', 100),
        ('Audio', 100),
        ('Res', 80),
        ('Size', 80),
    ]

    def __init__(self, parent, main_frame=None, vid_info_panel=None):
        super().__init__(parent, style=wx.LC_REPORT | wx.SUNKEN_BORDER)
        self.main_frame = main_frame
        self.vid_info_panel = vid_info_panel
        for idx, (label, width) in enumerate(self.COLS):
            self.InsertColumn(idx, label)
            self.SetColumnWidth(idx, width)
        self.EnableCheckBoxes()
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelected)
        self.Bind(wx.EVT_LIST_ITEM_CHECKED, self.OnChecked)
        self.refresh()

    def OnSelected(self, event):
        global selected_video, working_dir
        selection = self.GetFirstSelected()
        if selection == -1:
            if self.main_frame:
                self.main_frame.SetStatusText("No selection")
            return
        item = self.GetItemText(selection, 0)
        if self.main_frame:
            self.main_frame.SetStatusText(f"Selected: {item}")
        selected_video = working_dir / item
        info = video.info(selected_video)
        if self.vid_info_panel:
            self.vid_info_panel.update_info(info)

    def OnChecked(self, event):
        global video_list, working_dir
        video_list = [
            str(working_dir / self.GetItemText(i, 0))
            for i in range(self.GetItemCount()) if self.IsItemChecked(i)
        ]

    def refresh(self):
        global video_list, working_dir
        video_list = []
        self.DeleteAllItems()
        if not working_dir:
            return
        files = sorted(
            p.resolve()
            for p in pathlib.Path(working_dir).glob("**/*")
            if p.suffix in VIDEO_EXTENSIONS
        )
        for i, v in enumerate(files):
            self.InsertItem(i, str(v.relative_to(working_dir)))

class MyFrame(wx.Frame):
    def __init__(self):
        global config, working_dir
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
        working_dir = pathlib.Path(config.get("working_dir", str(pathlib.Path.cwd())))
        self.working_dir_box = wx.TextCtrl(main_panel)
        self.working_dir_box.SetValue(str(working_dir))
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
        self.vid_info_panel = VideoInfoPanel(main_panel)
        self.listbox = VideoList(main_panel, main_frame=self, vid_info_panel=self.vid_info_panel)
        middle.Add(self.listbox, 1, wx.LEFT | wx.EXPAND, 5)
        middle.Add(self.vid_info_panel, 1, wx.RIGHT | wx.EXPAND, 5)
        self.select_all_button = wx.Button(main_panel, label="Select All")
        self.select_all_button.Bind(wx.EVT_BUTTON, self.OnSelectAll)
        self.select_none_button = wx.Button(main_panel, label="Select None")
        self.select_none_button.Bind(wx.EVT_BUTTON, self.OnSelectNone)
        self.play_label = wx.StaticText(main_panel, label="Play Selection with ffplay:", style=wx.ALIGN_CENTER)
        self.play_button = wx.Button(main_panel, label="Play")
        self.play_button.Bind(wx.EVT_BUTTON, self.OnPlay)
        self.reencode_pane = ReencodePane(main_panel)
        self.reencode_pane.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.reencode_pane.Expand()
        self.reencode_pane.Layout()
        self.reencode_pane.Fit()
        play_size.Add(self.select_all_button, 0, wx.ALL, 5)
        play_size.Add(self.select_none_button, 0, wx.ALL, 5)
        play_size.Add(self.play_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        play_size.Add(self.play_button, 0, wx.ALL, 5)
        bottom.Add(self.reencode_pane, 0, wx.GROW | wx.ALL, 5)
        main_sizer.Add(top, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(play_size, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(middle, 1, wx.EXPAND | wx.ALL, 5)
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
        global config, working_dir
        dlg = wx.DirDialog(self, "Choose a directory:", str(working_dir), wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,)
        if dlg.ShowModal() == wx.ID_OK:
            working_dir = pathlib.Path(dlg.GetPath()).resolve()
            self.working_dir_box.SetValue(str(working_dir))
            self.SetStatusText(f"Working directory: {str(working_dir)}")
            self.listbox.refresh()
            config["working_dir"] = str(working_dir)
        dlg.Destroy()

    def OnRefresh(self, event):
        self.listbox.refresh()
        self.SetStatusText("File list refreshed.")

    def OnGoUp(self, event):
        global working_dir
        if working_dir is not None:
            working_dir = working_dir.parent
            self.working_dir_box.SetValue(str(working_dir))
            self.SetStatusText(f"Working directory: {str(working_dir)}")
            self.listbox.refresh()

    def OnClose(self, event):
        global config, working_dir
        # Save config from reencode_pane
        pane = self.reencode_pane
        config["output_extension"] = pane.extension_choice.GetStringSelection()
        config["output_suffix"] = pane.suffix_textbox.GetValue()
        config["append_res"] = pane.append_res_checkbox.GetValue()
        config["encode_video"] = pane.vcodec_checkbox.GetValue()
        config["video_codec"] = pane.vcodec_choice.GetStringSelection()
        config["encode_audio"] = pane.acodec_checkbox.GetValue()
        config["audio_codec"] = pane.acodec_choice.GetStringSelection()
        config["no_data"] = pane.exclude_data_streams.GetValue()
        config["fix_resolution"] = pane.fix_res.GetValue()
        config["fix_err"] = pane.fix_errors.GetValue()
        config["use_crf"] = pane.crf_checkbox.GetValue()
        config["crf_value"] = str(pane.crf_int.GetValue())
        config["working_dir"] = str(working_dir) if working_dir else str(pathlib.Path.cwd())
        self.Destroy()

    def OnPlay(self, event):
        print("Play button clicked")
        video.play(selected_video)
        event.Skip(True)

    def OnSelectAll(self, event):
        for i in range(self.listbox.GetItemCount()):
            self.listbox.CheckItem(i)
        self.listbox.OnChecked(event)

    def OnSelectNone(self, event):
        for i in range(self.listbox.GetItemCount()):
            self.listbox.CheckItem(i, False)
        self.listbox.OnChecked(event)

class ReencodePane(wx.CollapsiblePane):
    def __init__(self, parent):
        global config
        super().__init__(parent, label="Reencode Options", style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE)

        panel = self.GetPane()
        re_vsizer = wx.BoxSizer(wx.VERTICAL)
        re_hsizer1 = wx.BoxSizer(wx.HORIZONTAL)
        re_hsizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.OnExpand)

        self.vcodec_checkbox = wx.CheckBox(panel, label="Video Codec:")
        self.vcodec_checkbox.SetValue(config.get("encode_video", False))
        self.vcodec_choice = wx.ComboBox(panel, size = [-1, -1], choices=list(VIDEO_CODECS))
        vcodec_default = config.get("video_codec", "libx265")
        if vcodec_default not in VIDEO_CODECS:
            print(f"Warning: {vcodec_default} is not a valid video codec. Using default.")
            vcodec_default = "libx265"
        self.vcodec_choice.SetSelection(VIDEO_CODECS.index(vcodec_default))

        self.acodec_checkbox = wx.CheckBox(panel, label="Audio Codec:")
        self.acodec_checkbox.SetValue(config.get("encode_audio", False))
        self.acodec_choice = wx.ComboBox(panel, size = [-1, -1], choices=list(AUDIO_CODECS))
        acodec_default = config.get("audio_codec", "aac")
        if acodec_default not in AUDIO_CODECS:
            print(f"Warning: {acodec_default} is not a valid audio codec. Using default.")
            acodec_default = "aac"
        self.acodec_choice.SetSelection(AUDIO_CODECS.index(acodec_default))

        self.suffix_label = wx.StaticText(panel, label="Suffix:")
        self.suffix_textbox = wx.TextCtrl(panel)
        self.suffix_textbox.SetValue(config.get("output_suffix", "_copy"))

        self.append_res_checkbox = wx.CheckBox(panel, label="Append Resolution")
        self.append_res_checkbox.SetValue(config.get("append_res", False))

        self.extension_label = wx.StaticText(panel, label="Extension:")
        self.extension_choice = wx.ComboBox(panel, size = [-1, -1], choices=list(VIDEO_EXTENSIONS))
        extension_default = config.get("output_extension", ".mkv")
        if extension_default not in VIDEO_EXTENSIONS:
            print(f"Warning: {extension_default} is not a valid video extension. Using default.")
            extension_default = ".mkv"
        self.extension_choice.SetSelection(list(VIDEO_EXTENSIONS).index(extension_default))

        self.sub_label = wx.StaticText(panel, label="Subtitles:")
        sub_list = ["None", "First", "All", "srt"]
        self.sub_choice = wx.ComboBox(panel, size = [-1, -1], choices=sub_list)
        self.sub_choice.SetSelection(sub_list.index(config.get("subtitles", "First")))
        
        self.exclude_data_streams = wx.CheckBox(panel, label="No Data")
        self.exclude_data_streams.SetValue(config.get("no_data", False))
        self.fix_res = wx.CheckBox(panel, label="Fix Resolution")
        self.fix_res.SetValue(config.get("fix_resolution", False))
        self.fix_errors = wx.CheckBox(panel, label="Fix Errors")
        self.fix_errors.SetValue(config.get("fix_err", False))

        self.crf_checkbox = wx.CheckBox(panel, label="CRF:")
        self.crf_checkbox.SetValue(config.get("use_crf", False))
        self.crf_int = wx.SpinCtrl(panel, size = [-1, -1], initial = 28, min = 4, max = 63)
        self.crf_int.SetValue(config.get("crf_value", 28))

        self.reencode_button = wx.Button(panel, label="Reencode")
        self.reencode_button.Bind(wx.EVT_BUTTON, self.OnReencode)

        self.total_label = wx.StaticText(panel, label="Total Progress:")
        self.total_progress = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)

        re_hsizer1.Add(self.vcodec_checkbox, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.vcodec_choice, 0, wx.ALL | wx.EXPAND, 5)
        re_hsizer1.Add(self.acodec_checkbox, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.acodec_choice, 0, wx.ALL | wx.EXPAND, 10)

        re_hsizer1.Add(self.crf_checkbox, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.crf_int, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        re_hsizer1.Add(self.sub_label, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.sub_choice, 0, wx.ALL | wx.EXPAND, 5)
        re_hsizer1.Add(self.exclude_data_streams, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.fix_res, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer1.Add(self.fix_errors, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        
        re_hsizer2.Add(self.suffix_label, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer2.Add(self.suffix_textbox, 0, wx.ALL | wx.EXPAND, 0)
        re_hsizer2.Add(self.append_res_checkbox, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        re_hsizer2.Add(self.extension_label, 0, wx.ALL | wx.ALIGN_CENTER, 0)
        re_hsizer2.Add(self.extension_choice, 0, wx.ALL | wx.EXPAND, 5)
        
        re_hsizer2.Add(self.reencode_button, 0, wx.ALL | wx.EXPAND, 10)
        
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
        options = {}
        options["output_extension"] = self.extension_choice.GetStringSelection()
        options["output_suffix"] = self.suffix_textbox.GetValue()
        options["append_res"] = self.append_res_checkbox.GetValue()
        options["encode_video"] = self.vcodec_checkbox.GetValue()
        options["video_codec"] = self.vcodec_choice.GetStringSelection()
        options["encode_audio"] = self.acodec_checkbox.GetValue()
        options["audio_codec"] = self.acodec_choice.GetStringSelection()
        options["subtitles"] = self.sub_choice.GetStringSelection()
        options["no_data"] = self.exclude_data_streams.GetValue()
        options["fix_resolution"] = self.fix_res.GetValue()
        options["fix_err"] = self.fix_errors.GetValue()
        options["use_crf"] = self.crf_checkbox.GetValue()
        options["crf_value"] = str(self.crf_int.GetValue())
        # Start reencoding in a background thread
        threading.Thread(target=self.ReEncodeWorker, args=(options,), daemon=True).start()

    def ReEncodeWorker(self, options):
        def do_execute(cmd):
            print(subprocess.list2cmdline(cmd))
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as p:
                if p.stdout:
                    for line in p.stdout:
                        print(line, end='')
                # No wx.Yield() in thread

        wx.CallAfter(self.GetParent().Disable)
        wx.CallAfter(self.total_progress.SetValue, 0)
        wx.CallAfter(self.total_progress.SetRange, len(video_list))
        progress = 0
        for video_file in video_list:
            if not video_file:
                continue
            print(f"Encoding video_file: {video_file}")
            try:
                info = video.info(video_file)
                output_suffix = options["output_suffix"]
                if options["append_res"]:
                    res_width = info.max_width
                    res_height = info.max_height
                    if options["fix_resolution"]:
                        res_width = (res_width / 2) * 2
                        res_height = (res_height / 2) * 2
                    output_suffix = f"{output_suffix}_{res_width}x{res_height}"
                if output_suffix and not output_suffix.startswith("_"):
                    output_suffix = f"_{output_suffix}"
                encode_job = video.encode()
                encode_job.add_input(video_file)
                encode_job.add_output_from_input(file_append=output_suffix, file_extension=options["output_extension"])
                if options["encode_video"]:
                    encode_job.set_video_codec(options["video_codec"])
                if options["encode_audio"]:
                    encode_job.set_audio_codec(options["audio_codec"])
                if options["subtitles"] == "None":
                    encode_job.exclude_subtitles()
                elif options["subtitles"] == "All":
                    encode_job.copy_subtitles()
                elif options["subtitles"] == "srt":
                    print("Adding srt file")
                    srt_file = pathlib.Path(video_file).with_suffix(".srt")
                    print(f"Adding srt file: {srt_file}")
                    if srt_file.exists():
                        print(f"Exists. Adding srt file: {srt_file}")
                        encode_job.add_input(str(srt_file))
                    else:
                        print(f"Warning: {srt_file} does not exist. Skipping.")
                if options["no_data"]:
                    encode_job.exclude_data()
                if options["fix_resolution"]:
                    encode_job.fix_resolution()
                if options["fix_err"]:
                    encode_job.fix_errors()
                if options["use_crf"]:
                    encode_job.set_crf(options["crf_value"])
                if pathlib.Path(encode_job.output).exists():
                    print(f"Output file '{encode_job.output}' already exists. Skipping.")
                    continue
                do_execute(encode_job.reencode_str())
                progress += 1
                wx.CallAfter(self.total_progress.SetValue, progress)
            except Exception as e:
                print(f"What-Ho? There was some sort of issue, I'm afraid... {e}")
        wx.CallAfter(self.GetParent().Enable)
        # Use wx.GetTopLevelParent(self) to access the frame and its listbox
        top_frame = wx.GetTopLevelParent(self)
        if hasattr(top_frame, "listbox"):
            wx.CallAfter(top_frame.listbox.refresh)

class MyApp(wx.App):
    def OnInit(self):
        global config, main_frame
        
        # Load the config file from json
        config_file = pathlib.Path(__file__).parent / "config.json"
        if config_file.exists():
            with open(config_file, "r") as f:
                config = json.load(f)
                print("Config loaded:", config)
        else:
            print("Config file not found. Using default settings.")

        main_frame = MyFrame()
        main_frame.Show(True)
        main_frame.Centre()
        return True

    def OnExit(self):
        global config
        
        # Save the config file to json
        config_file = pathlib.Path(__file__).parent / "config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)
            print("Config saved:", config)
        return True

if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
