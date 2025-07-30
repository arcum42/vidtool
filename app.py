#!/usr/bin/env python

import wx
import pathlib
import threading
import subprocess
import json
import time
from typing import Optional, List, Dict, Any

import modules.video as video
from modules.video import VIDEO_EXTENSIONS, VIDEO_CODECS, AUDIO_CODECS
from modules.video import VideoProcessingError, FFmpegNotFoundError, VideoFileError


class AppState:
    """Central application state manager to replace global variables."""
    
    def __init__(self):
        self.video_list: List[str] = []
        self.selected_video: Optional[pathlib.Path] = None
        self.config: Dict[str, Any] = {}
        self.working_dir: Optional[pathlib.Path] = None
        self.main_frame: Any = None  # Will be set to MyFrame instance (avoid typing conflicts)
        
    def load_config(self):
        """Load configuration from config.json file."""
        config_file = pathlib.Path(__file__).parent / "config.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    self.config = json.load(f)
                    print("Config loaded:", self.config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}. Using default settings.")
                self.config = {}
        else:
            print("Config file not found. Using default settings.")
            
    def save_config(self):
        """Save configuration to config.json file."""
        config_file = pathlib.Path(__file__).parent / "config.json"
        try:
            with open(config_file, "w") as f:
                json.dump(self.config, f, indent=2)
                print("Config saved:", self.config)
        except IOError as e:
            print(f"Error saving config: {e}")


# Global app state instance
app_state = AppState()

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

    def __init__(self, parent, app_state: AppState):
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
        ('Filename', 500),
        ('Video', 50),
        ('Audio', 50),
        ('Res', 80),
        ('Size', 80),
    ]

    def __init__(self, parent, app_state, main_frame=None, vid_info_panel=None):
        super().__init__(parent, style=wx.LC_REPORT | wx.SUNKEN_BORDER)
        self.app_state = app_state
        self.main_frame = main_frame
        self.vid_info_panel = vid_info_panel
        self.info_cache = {}  # filename (str) -> video.info object

        for idx, (label, width) in enumerate(self.COLS):
            self.InsertColumn(idx, label)
            self.SetColumnWidth(idx, width)

        self.EnableCheckBoxes()
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelected)
        self.Bind(wx.EVT_LIST_ITEM_CHECKED, self.OnChecked)
        self.refresh()

    def OnSelected(self, event):
        selection = self.GetFirstSelected()
        if selection == -1:
            if self.main_frame:
                self.main_frame.SetStatusText("No selection")
            return

        item = self.GetItemText(selection, 0)
        if self.main_frame:
            self.main_frame.SetStatusText(f"Selected: {item}")
        self.app_state.selected_video = self.app_state.working_dir / item

        info_obj = self.info_cache.get(str(self.app_state.selected_video))
        if not info_obj:
            try:
                info_obj = video.info(self.app_state.selected_video)
                self.info_cache[str(self.app_state.selected_video)] = info_obj
            except (VideoProcessingError, FFmpegNotFoundError, VideoFileError) as e:
                if self.main_frame:
                    self.main_frame.SetStatusText(f"Error loading video info: {e}")
                wx.MessageBox(f"Error loading video information:\n\n{e}", 
                             "Video Processing Error", wx.OK | wx.ICON_ERROR)
                return
            except Exception as e:
                if self.main_frame:
                    self.main_frame.SetStatusText(f"Unexpected error: {e}")
                wx.MessageBox(f"Unexpected error loading video:\n\n{e}", 
                             "Unexpected Error", wx.OK | wx.ICON_ERROR)
                return

        if self.vid_info_panel and info_obj:
            self.vid_info_panel.update_info(info_obj)

    def OnChecked(self, event):
        self.app_state.video_list = [
            str(self.app_state.working_dir / self.GetItemText(i, 0))
            for i in range(self.GetItemCount()) if self.IsItemChecked(i)
        ]

    def refresh(self):
        self.app_state.video_list = []

        self.DeleteAllItems()
        self.info_cache = {}

        if not self.app_state.working_dir:
            return

        wd = self.app_state.working_dir  # capture current working_dir for thread safety
        def scan_and_update():
            files = []
            info_cache = {}
            errors = []
            
            try:
                # Check FFmpeg availability once at the start
                video.check_ffmpeg_availability()
            except FFmpegNotFoundError as e:
                wx.CallAfter(lambda: wx.MessageBox(f"FFmpeg Error:\n\n{e}", 
                                                  "FFmpeg Not Found", wx.OK | wx.ICON_ERROR))
                return
            
            for p in sorted(pathlib.Path(wd).glob("**/*")):
                if p.suffix in VIDEO_EXTENSIONS:
                    abs_path = str(p.resolve())
                    files.append(p.resolve())
                    try:
                        info_cache[abs_path] = video.info(abs_path)
                    except (VideoProcessingError, VideoFileError) as e:
                        errors.append(f"{p.name}: {e}")
                        print(f"Failed to get info for {abs_path}: {e}")
                    except Exception as e:
                        errors.append(f"{p.name}: Unexpected error - {e}")
                        print(f"Unexpected error processing {abs_path}: {e}")

            def update_ui():
                if self.app_state.working_dir != wd:
                    return

                self.DeleteAllItems()
                for i, v in enumerate(files):
                    abs_path = str(v)
                    rel_path = str(v.relative_to(wd))
                    info_obj = info_cache.get(abs_path)

                    video_codec = audio_codec = res = size_str = ""

                    if info_obj:
                        if info_obj.video_streams:
                            video_codec = info_obj.video_streams[0].get("codec_name", "")

                        if info_obj.audio_streams:
                            audio_codec = info_obj.audio_streams[0].get("codec_name", "")

                        res = f"{info_obj.max_width}x{info_obj.max_height}" if info_obj.max_width and info_obj.max_height else ""

                        if info_obj.size_kb < 1024:
                            size_str = f"{info_obj.size_kb:.2f} KB"
                        elif info_obj.size_mb < 1024:
                            size_str = f"{info_obj.size_mb:.2f} MB"
                        else:
                            size_str = f"{info_obj.size_gb:.2f} GB"
                    else:
                        # Mark files that failed to process
                        video_codec = "ERROR"

                    self.InsertItem(i, rel_path)
                    self.SetItem(i, 1, video_codec)
                    self.SetItem(i, 2, audio_codec)
                    self.SetItem(i, 3, res)
                    self.SetItem(i, 4, size_str)

                self.info_cache = info_cache
                self.app_state.video_list = []
                
                # Show error summary if there were issues
                if errors and self.main_frame:
                    error_count = len(errors)
                    status_msg = f"Loaded {len(files)} files ({error_count} errors)"
                    self.main_frame.SetStatusText(status_msg)
                    
                    if error_count <= 5:  # Show details for few errors
                        error_msg = f"Errors processing {error_count} files:\n\n" + "\n".join(errors)
                    else:  # Summarize for many errors
                        error_msg = f"Errors processing {error_count} files. First 5:\n\n" + "\n".join(errors[:5]) + f"\n\n... and {error_count - 5} more"
                    
                    wx.CallAfter(lambda: wx.MessageBox(error_msg, "Video Processing Errors", wx.OK | wx.ICON_WARNING))

            wx.CallAfter(update_ui)
        threading.Thread(target=scan_and_update, daemon=True).start()

class MyFrame(wx.Frame):
    def __init__(self, app_state):
        self.app_state = app_state

        super().__init__(parent=None, title="Vid Tool")

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        notebook = wx.Notebook(panel)

        main_panel = wx.Panel(notebook)
        notebook.AddPage(main_panel, "Main")

        settings_panel = SettingsPanel(notebook, self.app_state)
        notebook.AddPage(settings_panel, "Settings")

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        top = wx.BoxSizer(wx.HORIZONTAL)
        play_size = wx.BoxSizer(wx.HORIZONTAL)
        bottom = wx.BoxSizer(wx.VERTICAL)
        self.label = wx.StaticText(main_panel, label="Directory", style=wx.ALIGN_CENTER)
        self.app_state.working_dir = pathlib.Path(self.app_state.config.get("working_dir", str(pathlib.Path.cwd())))

        self.working_dir_box = wx.TextCtrl(main_panel)
        self.working_dir_box.SetValue(str(self.app_state.working_dir))

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

        # --- Splitter Window for Video List and Info ---
        splitter = wx.SplitterWindow(main_panel)
        self.vid_info_panel = VideoInfoPanel(splitter, self.app_state)
        self.listbox = VideoList(splitter, self.app_state, main_frame=self, vid_info_panel=self.vid_info_panel)
        splitter.SplitVertically(self.listbox, self.vid_info_panel, sashPosition=760)
        splitter.SetMinimumPaneSize(200)

        self.select_all_button = wx.Button(main_panel, label="Select All")
        self.select_all_button.Bind(wx.EVT_BUTTON, self.OnSelectAll)

        self.select_none_button = wx.Button(main_panel, label="Select None")
        self.select_none_button.Bind(wx.EVT_BUTTON, self.OnSelectNone)

        self.play_label = wx.StaticText(main_panel, label="Play Selection with ffplay:", style=wx.ALIGN_CENTER)
        self.play_button = wx.Button(main_panel, label="Play")
        self.play_button.Bind(wx.EVT_BUTTON, self.OnPlay)

        self.reencode_pane = ReencodePane(main_panel, self.app_state)
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

        main_sizer.Add(splitter, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(bottom, 0, wx.EXPAND | wx.ALL, 5)
        main_panel.SetSizer(main_sizer)

        sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)
        self.CreateStatusBar()
        self.SetStatusText("Welcome to Vid Tool!")
        self.SetSize((1200, 600))
        self.Center()
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Show()

    def OnChangeDir(self, event):
        dlg = wx.DirDialog(self, "Choose a directory:", str(self.app_state.working_dir), wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,)
        if dlg.ShowModal() == wx.ID_OK:
            self.app_state.working_dir = pathlib.Path(dlg.GetPath()).resolve()
            self.working_dir_box.SetValue(str(self.app_state.working_dir))
            self.SetStatusText(f"Working directory: {str(self.app_state.working_dir)}")
            self.listbox.refresh()
            self.app_state.config["working_dir"] = str(self.app_state.working_dir)
        dlg.Destroy()

    def OnRefresh(self, event):
        self.listbox.refresh()
        self.SetStatusText("File list refreshed.")

    def OnGoUp(self, event):
        if self.app_state.working_dir is not None:
            self.app_state.working_dir = self.app_state.working_dir.parent
            self.working_dir_box.SetValue(str(self.app_state.working_dir))
            self.SetStatusText(f"Working directory: {str(self.app_state.working_dir)}")
            self.listbox.refresh()

    def OnClose(self, event):
        pane = self.reencode_pane
        self.app_state.config["output_extension"] = pane.extension_choice.GetStringSelection()
        self.app_state.config["output_suffix"] = pane.suffix_textbox.GetValue()
        self.app_state.config["append_res"] = pane.append_res_checkbox.GetValue()
        self.app_state.config["encode_video"] = pane.vcodec_checkbox.GetValue()
        self.app_state.config["video_codec"] = pane.vcodec_choice.GetStringSelection()
        self.app_state.config["encode_audio"] = pane.acodec_checkbox.GetValue()
        self.app_state.config["audio_codec"] = pane.acodec_choice.GetStringSelection()
        self.app_state.config["no_data"] = pane.exclude_data_streams.GetValue()
        self.app_state.config["fix_resolution"] = pane.fix_res.GetValue()
        self.app_state.config["fix_err"] = pane.fix_errors.GetValue()
        self.app_state.config["use_crf"] = pane.crf_checkbox.GetValue()
        self.app_state.config["crf_value"] = str(pane.crf_int.GetValue())
        self.app_state.config["working_dir"] = str(self.app_state.working_dir) if self.app_state.working_dir else str(pathlib.Path.cwd())
        self.Destroy()

    def OnPlay(self, event):
        print("Play button clicked")
        
        if not self.app_state.video_list:
            wx.MessageBox("No videos selected for playback.", "No Selection", wx.OK | wx.ICON_INFORMATION)
            return
            
        def play_videos():
            try:
                # Check FFmpeg availability
                video.check_ffmpeg_availability()
            except FFmpegNotFoundError as e:
                wx.CallAfter(lambda: wx.MessageBox(f"Cannot play videos:\n\n{e}", 
                                                  "FFmpeg Not Found", wx.OK | wx.ICON_ERROR))
                return
                
            for vid in self.app_state.video_list:
                try:
                    print(f"Playing: {vid}")
                    video.play(vid)
                except (VideoProcessingError, VideoFileError) as e:
                    wx.CallAfter(lambda v=vid, err=e: wx.MessageBox(f"Error playing {pathlib.Path(v).name}:\n\n{err}", 
                                                                   "Playback Error", wx.OK | wx.ICON_ERROR))
                    continue
                except Exception as e:
                    wx.CallAfter(lambda v=vid, err=e: wx.MessageBox(f"Unexpected error playing {pathlib.Path(v).name}:\n\n{err}", 
                                                                   "Unexpected Error", wx.OK | wx.ICON_ERROR))
                    continue
                    
        threading.Thread(target=play_videos, daemon=True).start()
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
    def __init__(self, parent, app_state):
        self.app_state = app_state
        self.cancel_event = threading.Event()
        self.current_encode_job = None
        self.current_file_name = ""
        self.encoding_start_time = 0
        super().__init__(parent, label="Reencode Options", style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE)

        panel = self.GetPane()
        re_vsizer = wx.BoxSizer(wx.VERTICAL)
        re_hsizer1 = wx.BoxSizer(wx.HORIZONTAL)
        re_hsizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.OnExpand)

        self.vcodec_checkbox = wx.CheckBox(panel, label="Video Codec:")
        self.vcodec_checkbox.SetValue(self.app_state.config.get("encode_video", False))
        self.vcodec_choice = wx.ComboBox(panel, size = [-1, -1], choices=list(VIDEO_CODECS))
        vcodec_default = self.app_state.config.get("video_codec", "libx265")
        if vcodec_default not in VIDEO_CODECS:
            print(f"Warning: {vcodec_default} is not a valid video codec. Using default.")
            vcodec_default = "libx265"
        self.vcodec_choice.SetSelection(VIDEO_CODECS.index(vcodec_default))

        self.acodec_checkbox = wx.CheckBox(panel, label="Audio Codec:")
        self.acodec_checkbox.SetValue(self.app_state.config.get("encode_audio", False))
        self.acodec_choice = wx.ComboBox(panel, size = [-1, -1], choices=list(AUDIO_CODECS))
        acodec_default = self.app_state.config.get("audio_codec", "aac")

        if acodec_default not in AUDIO_CODECS:
            print(f"Warning: {acodec_default} is not a valid audio codec. Using default.")
            acodec_default = "aac"
        self.acodec_choice.SetSelection(AUDIO_CODECS.index(acodec_default))

        self.suffix_label = wx.StaticText(panel, label="Suffix:")
        self.suffix_textbox = wx.TextCtrl(panel)
        self.suffix_textbox.SetValue(self.app_state.config.get("output_suffix", "_copy"))

        self.append_res_checkbox = wx.CheckBox(panel, label="Append Resolution")
        self.append_res_checkbox.SetValue(self.app_state.config.get("append_res", False))

        self.extension_label = wx.StaticText(panel, label="Extension:")
        self.extension_choice = wx.ComboBox(panel, size = [-1, -1], choices=list(VIDEO_EXTENSIONS))
        extension_default = self.app_state.config.get("output_extension", ".mkv")

        if extension_default not in VIDEO_EXTENSIONS:
            print(f"Warning: {extension_default} is not a valid video extension. Using default.")
            extension_default = ".mkv"
        self.extension_choice.SetSelection(list(VIDEO_EXTENSIONS).index(extension_default))

        self.sub_label = wx.StaticText(panel, label="Subtitles:")
        sub_list = ["None", "First", "All", "srt"]
        self.sub_choice = wx.ComboBox(panel, size = [-1, -1], choices=sub_list)
        self.sub_choice.SetSelection(sub_list.index(self.app_state.config.get("subtitles", "First")))
        
        self.exclude_data_streams = wx.CheckBox(panel, label="No Data")
        self.exclude_data_streams.SetValue(self.app_state.config.get("no_data", False))
        self.fix_res = wx.CheckBox(panel, label="Fix Resolution")
        self.fix_res.SetValue(self.app_state.config.get("fix_resolution", False))
        self.fix_errors = wx.CheckBox(panel, label="Fix Errors")
        self.fix_errors.SetValue(self.app_state.config.get("fix_err", False))

        self.crf_checkbox = wx.CheckBox(panel, label="CRF:")
        self.crf_checkbox.SetValue(self.app_state.config.get("use_crf", False))
        self.crf_int = wx.SpinCtrl(panel, size = [-1, -1], initial = 28, min = 4, max = 63)
        self.crf_int.SetValue(self.app_state.config.get("crf_value", 28))

        self.reencode_button = wx.Button(panel, label="Reencode")
        self.reencode_button.Bind(wx.EVT_BUTTON, self.OnReencode)
        
        self.cancel_button = wx.Button(panel, label="Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.cancel_button.Enable(False)

        self.total_label = wx.StaticText(panel, label="Total Progress:")
        self.total_progress = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        
        self.current_file_label = wx.StaticText(panel, label="Current File:")
        self.current_file_progress = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        
        self.progress_details = wx.StaticText(panel, label="")
        self.time_estimate = wx.StaticText(panel, label="")

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
        
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.reencode_button, 0, wx.ALL | wx.EXPAND, 5)
        button_sizer.Add(self.cancel_button, 0, wx.ALL | wx.EXPAND, 5)
        re_hsizer2.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        re_vsizer.Add(re_hsizer1, 0, wx.ALL | wx.EXPAND, 0)
        re_vsizer.Add(re_hsizer2, 0, wx.ALL | wx.EXPAND, 0)
        re_vsizer.Add(self.total_label, 0, wx.ALL, 5)
        re_vsizer.Add(self.total_progress, 0, wx.EXPAND | wx.ALL, 5)
        re_vsizer.Add(self.current_file_label, 0, wx.ALL, 5)
        re_vsizer.Add(self.current_file_progress, 0, wx.EXPAND | wx.ALL, 5)
        re_vsizer.Add(self.progress_details, 0, wx.ALL, 5)
        re_vsizer.Add(self.time_estimate, 0, wx.ALL, 5)

        panel.SetSizer(re_vsizer)

    def OnExpand(self, event):
        self.Layout()
        self.Fit()
        parent = self.GetParent()
        parent.Layout()
        parent.Fit()

    def OnReencode(self, event):
        print("Reencode button clicked")
        self.reencode_button.Disable()
        self.cancel_button.Enable()
        self.cancel_event.clear()
        
        # Reset progress displays
        self.current_file_progress.SetValue(0)
        self.progress_details.SetLabel("")
        self.time_estimate.SetLabel("")
        self.encoding_start_time = time.time()
        
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

    def OnCancel(self, event):
        """Cancel the current encoding operation."""
        if self.cancel_event:
            self.cancel_event.set()
            self.cancel_button.Disable()
            wx.CallAfter(self.progress_details.SetLabel, "Cancelling...")

    def update_progress(self, progress_info):
        """Update the current file progress display."""
        wx.CallAfter(self.current_file_progress.SetValue, int(progress_info.percent))
        
        # Format progress details with ETA on the same line
        details = f"Frame: {progress_info.frame} | FPS: {progress_info.fps:.1f} | Speed: {progress_info.speed}"
        
        # Add ETA to the same line if available
        if progress_info.eta_seconds > 0:
            eta_minutes = int(progress_info.eta_seconds // 60)
            eta_seconds = int(progress_info.eta_seconds % 60)
            details += f" | ETA: {eta_minutes:02d}:{eta_seconds:02d}"
        
        wx.CallAfter(self.progress_details.SetLabel, details)
        
        # Clear the separate time estimate label since we're showing it inline
        wx.CallAfter(self.time_estimate.SetLabel, "")

    def output_callback(self, line):
        """Handle FFmpeg output lines."""
        # This could be used for additional logging if needed
        pass

    def ReEncodeWorker(self, options):
        """Worker thread for reencoding with comprehensive error handling."""
        
        # Check prerequisites first
        try:
            video.check_ffmpeg_availability()
        except FFmpegNotFoundError as e:
            wx.CallAfter(lambda: wx.MessageBox(f"Cannot start encoding:\n\n{e}", 
                                              "FFmpeg Not Found", wx.OK | wx.ICON_ERROR))
            wx.CallAfter(self.reencode_button.Enable)
            return
            
        if not self.app_state.video_list:
            wx.CallAfter(lambda: wx.MessageBox("No videos selected for encoding.", 
                                              "No Selection", wx.OK | wx.ICON_INFORMATION))
            wx.CallAfter(self.reencode_button.Enable)
            return

        wx.CallAfter(self.total_progress.SetValue, 0)
        wx.CallAfter(self.total_progress.SetRange, len(self.app_state.video_list))
        
        progress = 0
        successful = 0
        errors = []
        
        for video_file in self.app_state.video_list:
            if not video_file:
                continue
                
            # Check for cancellation
            if self.cancel_event.is_set():
                wx.CallAfter(self.progress_details.SetLabel, "Cancelled by user")
                break
                
            video_name = pathlib.Path(video_file).name
            print(f"Encoding video_file: {video_file}")
            
            # Update current file label
            wx.CallAfter(self.current_file_label.SetLabel, f"Current File: {video_name}")
            wx.CallAfter(self.current_file_progress.SetValue, 0)
            
            try:
                info = video.info(video_file)
                output_suffix = options["output_suffix"]

                if options["append_res"]:
                    res_width = info.max_width
                    res_height = info.max_height
                    if options["fix_resolution"]:
                        res_width = (res_width // 2) * 2  # Use integer division
                        res_height = (res_height // 2) * 2
                    output_suffix = f"{output_suffix}_{int(res_width)}x{int(res_height)}"

                if output_suffix and not output_suffix.startswith("_"):
                    output_suffix = f"_{output_suffix}"
                    
                encode_job = video.encode()
                encode_job.add_input(video_file)
                encode_job.add_output_from_input(file_append=output_suffix, file_extension=options["output_extension"])

                # Check if output file already exists
                if pathlib.Path(encode_job.output).exists():
                    print(f"Output file '{encode_job.output}' already exists. Skipping.")
                    errors.append(f"{video_name}: Output file already exists")
                    progress += 1
                    wx.CallAfter(self.total_progress.SetValue, progress)
                    continue

                # Configure encoding options
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

                # Set up progress tracking
                encode_job.set_progress_callback(self.update_progress)
                encode_job.set_cancel_event(self.cancel_event)
                self.current_encode_job = encode_job

                # Calculate duration for this specific file
                if hasattr(info, 'runtime') and info.runtime:
                    try:
                        # Parse runtime format like "00:01:23.45" 
                        time_parts = info.runtime.split(':')
                        if len(time_parts) >= 3:
                            hours = int(time_parts[0])
                            minutes = int(time_parts[1])
                            seconds = float(time_parts[2])
                            duration_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
                            encode_job.total_duration_ms = duration_ms
                    except (ValueError, IndexError):
                        pass

                # Define output callback to print to console
                def console_output_callback(line):
                    print(line)

                # Perform the encoding
                encode_result = encode_job.reencode(output_callback=console_output_callback)
                
                if encode_result and not self.cancel_event.is_set():
                    successful += 1
                elif self.cancel_event.is_set():
                    errors.append(f"{video_name}: Cancelled by user")
                    break
                
            except (VideoProcessingError, FFmpegNotFoundError, VideoFileError) as e:
                error_msg = f"{video_name}: {e}"
                errors.append(error_msg)
                print(f"Video processing error: {error_msg}")
                
            except Exception as e:
                error_msg = f"{video_name}: Unexpected error - {e}"
                errors.append(error_msg)
                print(f"Unexpected error: {error_msg}")
            
            finally:
                progress += 1
                wx.CallAfter(self.total_progress.SetValue, progress)
                wx.CallAfter(self.current_file_progress.SetValue, 0)
                self.current_encode_job = None

        # Show completion summary
        total_files = len(self.app_state.video_list)
        failed = len(errors)
        cancelled = self.cancel_event.is_set()
        
        # Reset UI state
        wx.CallAfter(self.reencode_button.Enable)
        wx.CallAfter(self.cancel_button.Disable)
        wx.CallAfter(self.current_file_label.SetLabel, "Current File:")
        wx.CallAfter(self.current_file_progress.SetValue, 0)
        
        if cancelled:
            wx.CallAfter(self.progress_details.SetLabel, "Encoding cancelled")
            wx.CallAfter(self.time_estimate.SetLabel, "")
            wx.CallAfter(lambda: wx.MessageBox("Encoding was cancelled by user.", 
                                              "Encoding Cancelled", wx.OK | wx.ICON_INFORMATION))
        elif errors:
            wx.CallAfter(self.progress_details.SetLabel, "Encoding completed with errors")
            wx.CallAfter(self.time_estimate.SetLabel, "")
            
            if failed <= 5:
                error_details = "\n".join(errors)
            else:
                error_details = "\n".join(errors[:5]) + f"\n... and {failed - 5} more errors"
                
            summary = f"Encoding completed:\n\n✓ {successful} successful\n✗ {failed} failed\n\nErrors:\n{error_details}"
            wx.CallAfter(lambda: wx.MessageBox(summary, "Encoding Complete", wx.OK | wx.ICON_WARNING))
        else:
            wx.CallAfter(self.progress_details.SetLabel, "All files encoded successfully")
            wx.CallAfter(self.time_estimate.SetLabel, "")
            wx.CallAfter(lambda: wx.MessageBox(f"All {successful} files encoded successfully!", 
                                              "Encoding Complete", wx.OK | wx.ICON_INFORMATION))

        top_frame = wx.GetTopLevelParent(self)
        if hasattr(top_frame, "listbox"):
            wx.CallAfter(top_frame.listbox.refresh)

class SettingsPanel(wx.Panel):
    def __init__(self, parent, app_state):
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

        # Save button
        save_btn = wx.Button(self, label="Save Settings")
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)

        sizer.Add(ffmpeg_box, 0, wx.EXPAND)
        sizer.Add(ffprobe_box, 0, wx.EXPAND)
        sizer.Add(ffplay_box, 0, wx.EXPAND)
        sizer.Add(save_btn, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        self.SetSizer(sizer)

    def on_browse(self, event, textbox):
        dlg = wx.FileDialog(self, "Choose binary", wildcard="*", style=wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            textbox.SetValue(dlg.GetPath())
        dlg.Destroy()

    def on_save(self, event):
        """Save settings with validation."""
        ffmpeg_path = self.ffmpeg_path.GetValue().strip()
        ffprobe_path = self.ffprobe_path.GetValue().strip()
        ffplay_path = self.ffplay_path.GetValue().strip()
        
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

        # Update module-level variables
        video.ffmpeg_bin = ffmpeg_path or "ffmpeg"
        video.ffprobe_bin = ffprobe_path or "ffprobe"
        video.ffplay_bin = ffplay_path or "ffplay"
        
        # Test FFmpeg availability with new settings
        try:
            video.check_ffmpeg_availability()
            wx.MessageBox("Settings saved and FFmpeg tools verified successfully!", 
                         "Settings Saved", wx.OK | wx.ICON_INFORMATION)
        except FFmpegNotFoundError as e:
            wx.MessageBox(f"Settings saved, but FFmpeg tools not found:\n\n{e}\n\n" +
                         "Please ensure FFmpeg is installed or provide correct paths.", 
                         "Settings Saved - Warning", wx.OK | wx.ICON_WARNING)

class MyApp(wx.App):
    def OnInit(self):
        # Initialize app state and load config
        app_state.load_config()
        
        self.main_frame = MyFrame(app_state)
        app_state.main_frame = self.main_frame
        self.main_frame.Show(True)
        self.main_frame.Centre()
        return True

    def OnExit(self):
        # Save the config file to json
        app_state.save_config()
        return True

if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
