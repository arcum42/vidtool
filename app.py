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
from modules import video
from modules.presets import PresetManager, PresetError
from modules.output import OutputPathGenerator, OutputPreset, OUTPUT_PRESETS


class AppState:
    """Central application state manager to replace global variables."""
    
    def __init__(self):
        self.video_list: List[str] = []
        self.selected_video: Optional[pathlib.Path] = None
        self.config: Dict[str, Any] = {}
        self.working_dir: Optional[pathlib.Path] = None
        self.main_frame: Any = None  # Will be set to MyFrame instance (avoid typing conflicts)
        self.preset_manager: Optional[PresetManager] = None
        
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
            
        # Initialize preset manager
        self.preset_manager = PresetManager()
        self.preset_manager.load_presets()
            
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

    def get_video_files_with_depth(self, directory):
        """Get video files from directory respecting the recursion depth setting."""
        directory = pathlib.Path(directory)
        depth = self.app_state.config.get("recursion_depth", 0)
        
        if depth == 0:
            # Unlimited recursion (original behavior)
            return directory.glob("**/*")
        elif depth == 1:
            # Only current directory
            return directory.glob("*")
        else:
            # Limited recursion depth
            files = []
            for d in range(1, depth + 1):
                pattern = "/".join(["*"] * d)
                files.extend(directory.glob(pattern))
            return files

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
        
        # Update the output preview in the reencode pane
        if self.main_frame and hasattr(self.main_frame, 'reencode_pane'):
            self.main_frame.reencode_pane.update_output_preview()

    def uncheck_video_by_path(self, video_path):
        """Uncheck a specific video by its absolute path."""
        try:
            print(f"Attempting to uncheck video: {video_path}")
            # Convert absolute path to relative path for comparison
            video_path = pathlib.Path(video_path)
            if self.app_state.working_dir:
                relative_path = str(video_path.relative_to(self.app_state.working_dir))
                print(f"Looking for relative path: {relative_path}")
                
                # Find the item in the list
                for i in range(self.GetItemCount()):
                    item_text = self.GetItemText(i, 0)
                    if item_text == relative_path:
                        print(f"Found matching item at index {i}: {item_text} - unchecking")
                        self.CheckItem(i, False)
                        # Update the video list to remove the unchecked item
                        self.OnChecked(None)
                        print(f"Video list after unchecking: {[pathlib.Path(v).name for v in self.app_state.video_list]}")
                        return
                
                print(f"Could not find item with relative path: {relative_path}")
                print(f"Available items: {[self.GetItemText(i, 0) for i in range(self.GetItemCount())]}")
        except (ValueError, TypeError) as e:
            print(f"Could not uncheck video {video_path}: {e}")

    def recheck_videos_by_paths(self, video_paths):
        """Re-check multiple videos by their absolute paths after a refresh."""
        try:
            print(f"recheck_videos_by_paths called with {len(video_paths) if video_paths else 0} paths")
            if not video_paths or not self.app_state.working_dir:
                print("No video paths or working directory, returning early")
                return
                
            # Convert all video paths to relative paths for comparison
            relative_paths = []
            for video_path in video_paths:
                try:
                    video_path = pathlib.Path(video_path)
                    relative_path = str(video_path.relative_to(self.app_state.working_dir))
                    relative_paths.append(relative_path)
                    print(f"Converted {video_path} to relative path: {relative_path}")
                except (ValueError, TypeError) as e:
                    print(f"Could not convert video path {video_path}: {e}")
                    continue
            
            print(f"Looking for {len(relative_paths)} relative paths in {self.GetItemCount()} list items")
            
            # Check items that match the relative paths
            checked_count = 0
            for i in range(self.GetItemCount()):
                item_text = self.GetItemText(i, 0)
                if item_text in relative_paths:
                    print(f"Re-checking item {i}: {item_text}")
                    self.CheckItem(i, True)
                    checked_count += 1
            
            print(f"Successfully re-checked {checked_count} videos")
            
            # Update the video list with newly checked items
            self.OnChecked(None)
            
        except Exception as e:
            print(f"Could not recheck videos: {e}")
            import traceback
            traceback.print_exc()

    def refresh(self, completion_callback=None):
        self.app_state.video_list = []

        self.DeleteAllItems()
        self.info_cache = {}

        if not self.app_state.working_dir:
            if completion_callback:
                wx.CallAfter(completion_callback)
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
            
            for p in sorted(self.get_video_files_with_depth(wd)):
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

                # Call the completion callback if provided
                if completion_callback:
                    wx.CallAfter(completion_callback)

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

        # Recursion depth control
        self.recursion_label = wx.StaticText(main_panel, label="Depth:")
        self.recursion_spin = wx.SpinCtrl(main_panel, size=(60, -1), initial=0, min=0, max=20)
        self.recursion_spin.SetValue(self.app_state.config.get("recursion_depth", 0))  # 0 = unlimited
        self.recursion_spin.SetToolTip("Directory recursion depth (0 = unlimited)")
        self.recursion_spin.Bind(wx.EVT_SPINCTRL, self.OnRecursionDepthChanged)

        top.Add(self.label, 0, wx.LEFT | wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        top.Add(self.working_dir_box, 1, wx.CENTRE | wx.ALL | wx.EXPAND, 0)
        top.Add(self.button, 0, wx.EXPAND | wx.RIGHT | wx.ALL, 5)
        top.Add(self.refresh_button, 0, wx.EXPAND | wx.RIGHT | wx.ALL, 5)
        top.Add(self.up_button, 0, wx.EXPAND | wx.RIGHT | wx.ALL, 5)
        top.Add(self.recursion_label, 0, wx.LEFT | wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        top.Add(self.recursion_spin, 0, wx.EXPAND | wx.RIGHT | wx.ALL, 5)

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

        # Advanced selection options
        self.select_options_button = wx.Button(main_panel, label="Select Options ▼")
        self.select_options_button.Bind(wx.EVT_BUTTON, self.OnSelectOptions)

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
        play_size.Add(self.select_options_button, 0, wx.ALL, 5)
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

    def OnRecursionDepthChanged(self, event):
        """Handle recursion depth control change."""
        depth = self.recursion_spin.GetValue()
        self.app_state.config["recursion_depth"] = depth
        self.listbox.refresh()  # Refresh the file list with new depth
        if depth == 0:
            self.SetStatusText("Directory scan depth: unlimited (all subdirectories)")
        else:
            self.SetStatusText(f"Directory scan depth: {depth} level{'s' if depth != 1 else ''} deep")

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
        self.app_state.config["recursion_depth"] = self.recursion_spin.GetValue()
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

    def OnSelectOptions(self, event):
        """Show advanced selection options dialog."""
        dlg = SelectionOptionsDialog(self, self.listbox, self.app_state)
        dlg.ShowModal()
        dlg.Destroy()

class ReencodePane(wx.CollapsiblePane):
    def __init__(self, parent, app_state):
        self.app_state = app_state
        self.cancel_event = threading.Event()
        self.current_encode_job = None
        self.current_file_name = ""
        self.encoding_start_time = 0
        
        # Initialize output path generator with default settings
        self.output_generator = OutputPathGenerator()
        self.output_generator.set_naming_options(suffix="_encoded")
        
        super().__init__(parent, label="Reencode Options", style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE)

        panel = self.GetPane()
        re_vsizer = wx.BoxSizer(wx.VERTICAL)
        re_hsizer1 = wx.BoxSizer(wx.HORIZONTAL)
        re_hsizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.OnExpand)

        # Preset Management Section
        preset_sizer = wx.BoxSizer(wx.HORIZONTAL)
        preset_label = wx.StaticText(panel, label="Preset:")
        self.preset_choice = wx.ComboBox(panel, style=wx.CB_READONLY)
        self.load_preset_choices()
        
        self.save_preset_button = wx.Button(panel, label="Save Preset...")
        self.save_preset_button.Bind(wx.EVT_BUTTON, self.OnSavePreset)
        
        self.manage_presets_button = wx.Button(panel, label="Manage...")
        self.manage_presets_button.Bind(wx.EVT_BUTTON, self.OnManagePresets)
        
        preset_sizer.Add(preset_label, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        preset_sizer.Add(self.preset_choice, 1, wx.ALL | wx.EXPAND, 5)
        preset_sizer.Add(self.save_preset_button, 0, wx.ALL, 5)
        preset_sizer.Add(self.manage_presets_button, 0, wx.ALL, 5)
        
        self.preset_choice.Bind(wx.EVT_COMBOBOX, self.OnPresetSelected)

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
        
        self.current_file_label = wx.StaticText(panel, label="→")
        self.current_file_progress = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        
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
        
        self.output_options_button = wx.Button(panel, label="Output Options...")
        self.output_options_button.Bind(wx.EVT_BUTTON, self.OnOutputOptions)
        button_sizer.Add(self.output_options_button, 0, wx.ALL | wx.EXPAND, 5)
        button_sizer.Add(self.reencode_button, 0, wx.ALL | wx.EXPAND, 5)
        button_sizer.Add(self.cancel_button, 0, wx.ALL | wx.EXPAND, 5)
        
        # Add preview label for output filename
        self.output_preview_label = wx.StaticText(panel, label="Preview: (no file selected)")
        self.output_preview_label.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
        button_sizer.Add(self.output_preview_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        re_hsizer2.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        re_vsizer.Add(preset_sizer, 0, wx.ALL | wx.EXPAND, 5)
        re_vsizer.Add(re_hsizer1, 0, wx.ALL | wx.EXPAND, 0)
        re_vsizer.Add(re_hsizer2, 0, wx.ALL | wx.EXPAND, 0)
        re_vsizer.Add(self.total_label, 0, wx.ALL, 5)
        re_vsizer.Add(self.total_progress, 0, wx.EXPAND | wx.ALL, 5)
        re_vsizer.Add(self.current_file_label, 0, wx.ALL, 5)
        re_vsizer.Add(self.current_file_progress, 0, wx.EXPAND | wx.ALL, 5)
        re_vsizer.Add(self.time_estimate, 0, wx.ALL, 5)

        panel.SetSizer(re_vsizer)
        
        # Load advanced output settings from config after UI is set up
        self.load_advanced_output_settings()
        
        # Bind events to update preview
        self.suffix_textbox.Bind(wx.EVT_TEXT, self.OnUpdatePreview)
        self.append_res_checkbox.Bind(wx.EVT_CHECKBOX, self.OnUpdatePreview)
        self.extension_choice.Bind(wx.EVT_COMBOBOX, self.OnUpdatePreview)
        self.vcodec_checkbox.Bind(wx.EVT_CHECKBOX, self.OnUpdatePreview)
        self.vcodec_choice.Bind(wx.EVT_COMBOBOX, self.OnUpdatePreview)
        self.crf_checkbox.Bind(wx.EVT_CHECKBOX, self.OnUpdatePreview)
        self.crf_int.Bind(wx.EVT_SPINCTRL, self.OnUpdatePreview)
        
        # Initial preview update
        self.update_output_preview()

    def OnUpdatePreview(self, event=None):
        """Handle control changes that should update the output preview."""
        self.update_output_preview()
        if event:
            event.Skip()

    def update_output_preview(self):
        """Update the output filename preview based on current settings."""
        try:
            # Get the first selected video file
            if not self.app_state.video_list:
                self.output_preview_label.SetLabel("Preview: (no file selected)")
                return
                
            first_video = pathlib.Path(self.app_state.video_list[0])
            
            # Sync main controls to output generator
            self.sync_main_controls_to_generator()
            
            # Create a mock options dict with current settings
            options = {
                "output_suffix": self.suffix_textbox.GetValue(),
                "append_res": self.append_res_checkbox.GetValue(),
                "output_extension": self.extension_choice.GetStringSelection(),
                "encode_video": self.vcodec_checkbox.GetValue(),
                "video_codec": self.vcodec_choice.GetStringSelection(),
                "use_crf": self.crf_checkbox.GetValue(),
                "crf_value": str(self.crf_int.GetValue()),
                "fix_resolution": self.fix_res.GetValue()
            }
            
            # Try to get video info for resolution
            try:
                info = video.info(str(first_video))
                output_path = self.output_generator.generate_output_path(first_video, info, options)
                preview_name = pathlib.Path(output_path).name
            except Exception as e:
                # Fallback to simple preview if video info fails
                print(f"Preview generation failed, using fallback: {e}")
                suffix = options["output_suffix"]
                
                if options["append_res"]:
                    # Use placeholder resolution for preview
                    suffix = f"{suffix}_WxH"
                    
                if suffix and not suffix.startswith("_"):
                    suffix = f"_{suffix}"
                    
                preview_name = f"{first_video.stem}{suffix}{options['output_extension']}"
            
            # Truncate if too long
            if len(preview_name) > 50:
                preview_name = preview_name[:47] + "..."
                
            self.output_preview_label.SetLabel(f"Preview: {preview_name}")
            
        except Exception as e:
            print(f"Error updating preview: {e}")
            self.output_preview_label.SetLabel("Preview: (error)")

    def update_status_bar(self, message):
        """Helper method to update the main frame's status bar."""
        def update_status():
            top_frame = wx.GetTopLevelParent(self)
            if hasattr(top_frame, 'SetStatusText'):
                top_frame.SetStatusText(message)
        wx.CallAfter(update_status)

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
        
        # Sync main screen controls to output generator before encoding
        self.sync_main_controls_to_generator()
        
        # Reset progress displays
        self.current_file_progress.SetValue(0)
        self.update_status_bar("Starting encoding...")
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
            self.update_status_bar("Cancelling...")

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
        
        # Get the main frame to update status bar
        wx.CallAfter(self.update_status_bar, details)
        
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
                self.update_status_bar("Cancelled by user")
                break
                
            video_name = pathlib.Path(video_file).name
            print(f"Encoding video_file: {video_file}")
            
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
                
                # Use advanced output path generator instead of simple suffix
                try:
                    video_info_obj = info
                    output_path = self.output_generator.generate_output_path(
                        pathlib.Path(video_file), video_info_obj, options)
                    encode_job.add_output(str(output_path))
                except Exception as e:
                    # Fallback to original method if output generator fails
                    print(f"Output generator failed, using fallback: {e}")
                    encode_job.add_output_from_input(file_append=output_suffix, file_extension=options["output_extension"])

                # Get the output filename for display
                output_name = pathlib.Path(encode_job.output).name
                
                # Update current file label with both input and output filenames
                wx.CallAfter(self.current_file_label.SetLabel, f"{video_name} → {output_name}")
                wx.CallAfter(self.current_file_progress.SetValue, 0)

                # Check if output file already exists and handle according to policy
                if pathlib.Path(encode_job.output).exists():
                    if self.output_generator.overwrite_policy == "skip":
                        print(f"Output file '{encode_job.output}' already exists. Skipping.")
                        errors.append(f"{video_name}: Output file already exists")
                        progress += 1
                        wx.CallAfter(self.total_progress.SetValue, progress)
                        continue
                    elif self.output_generator.overwrite_policy == "overwrite":
                        print(f"Output file '{encode_job.output}' already exists. Will overwrite.")
                    # increment policy is handled by the output generator itself

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
                    
                    # Capture the completed video file path before any async operations
                    completed_video_file = video_file
                    
                    # After successful encoding, refresh the video list and recheck remaining videos
                    top_frame = wx.GetTopLevelParent(self)
                    if hasattr(top_frame, "listbox"):
                        def refresh_and_recheck():
                            # First uncheck the completed video to update the video list
                            print(f"Unchecking completed video: {pathlib.Path(completed_video_file).name}")
                            top_frame.listbox.uncheck_video_by_path(completed_video_file)
                            
                            # Get the updated list of selected videos (should exclude the just-processed one)
                            remaining_videos = list(self.app_state.video_list)  # Make a copy
                            print(f"Current video_list after unchecking: {[pathlib.Path(v).name for v in remaining_videos]}")
                            print(f"Preserving selection for {len(remaining_videos)} remaining videos: {[pathlib.Path(v).name for v in remaining_videos]}")
                            
                            # Refresh the list to show the new encoded file
                            def on_refresh_complete():
                                print(f"Refresh completed, re-checking {len(remaining_videos)} videos")
                                top_frame.listbox.recheck_videos_by_paths(remaining_videos)
                            
                            top_frame.listbox.refresh(completion_callback=on_refresh_complete)
                        
                        wx.CallAfter(refresh_and_recheck)
                        
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
        wx.CallAfter(self.current_file_label.SetLabel, "→")
        wx.CallAfter(self.current_file_progress.SetValue, 0)
        
        if cancelled:
            self.update_status_bar("Encoding cancelled")
            wx.CallAfter(self.time_estimate.SetLabel, "")
            wx.CallAfter(lambda: wx.MessageBox("Encoding was cancelled by user.", 
                                              "Encoding Cancelled", wx.OK | wx.ICON_INFORMATION))
        elif errors:
            self.update_status_bar("Encoding completed with errors")
            wx.CallAfter(self.time_estimate.SetLabel, "")
            
            if failed <= 5:
                error_details = "\n".join(errors)
            else:
                error_details = "\n".join(errors[:5]) + f"\n... and {failed - 5} more errors"
                
            summary = f"Encoding completed:\n\n✓ {successful} successful\n✗ {failed} failed\n\nErrors:\n{error_details}"
            wx.CallAfter(lambda: wx.MessageBox(summary, "Encoding Complete", wx.OK | wx.ICON_WARNING))
        else:
            self.update_status_bar("All files encoded successfully")
            wx.CallAfter(self.time_estimate.SetLabel, "")
            wx.CallAfter(lambda: wx.MessageBox(f"All {successful} files encoded successfully!", 
                                              "Encoding Complete", wx.OK | wx.ICON_INFORMATION))

        top_frame = wx.GetTopLevelParent(self)
        if hasattr(top_frame, "listbox"):
            wx.CallAfter(top_frame.listbox.refresh)

    def load_preset_choices(self):
        """Load available presets into the choice control."""
        if self.app_state.preset_manager:
            preset_names = ["[Custom Settings]"] + list(self.app_state.preset_manager.get_preset_names())
            self.preset_choice.Clear()
            self.preset_choice.AppendItems(preset_names)
            self.preset_choice.SetSelection(0)  # Default to custom settings

    def OnPresetSelected(self, event):
        """Handle preset selection."""
        selection = self.preset_choice.GetSelection()
        if selection <= 0:  # Custom settings selected
            return
            
        preset_name = self.preset_choice.GetStringSelection()
        if self.app_state.preset_manager:
            try:
                preset = self.app_state.preset_manager.get_preset(preset_name)
                self.apply_preset_settings(preset)
            except PresetError as e:
                wx.MessageBox(f"Error loading preset: {e}", "Preset Error", wx.OK | wx.ICON_ERROR)

    def apply_preset_settings(self, preset):
        """Apply preset settings to the interface."""
        # Video codec settings
        if "encode_video" in preset:
            self.vcodec_checkbox.SetValue(preset["encode_video"])
        if "video_codec" in preset and preset["video_codec"] in VIDEO_CODECS:
            self.vcodec_choice.SetSelection(VIDEO_CODECS.index(preset["video_codec"]))
        
        # Audio codec settings
        if "encode_audio" in preset:
            self.acodec_checkbox.SetValue(preset["encode_audio"])
        if "audio_codec" in preset and preset["audio_codec"] in AUDIO_CODECS:
            self.acodec_choice.SetSelection(AUDIO_CODECS.index(preset["audio_codec"]))
        
        # CRF settings
        if "use_crf" in preset:
            self.crf_checkbox.SetValue(preset["use_crf"])
        if "crf_value" in preset:
            self.crf_int.SetValue(preset["crf_value"])
        
        # Output settings
        if "output_suffix" in preset:
            self.suffix_textbox.SetValue(preset["output_suffix"])
        if "append_res" in preset:
            self.append_res_checkbox.SetValue(preset["append_res"])
        if "output_extension" in preset and preset["output_extension"] in VIDEO_EXTENSIONS:
            self.extension_choice.SetSelection(list(VIDEO_EXTENSIONS).index(preset["output_extension"]))
        
        # Subtitle settings
        sub_list = ["None", "First", "All", "srt"]
        if "subtitles" in preset and preset["subtitles"] in sub_list:
            self.sub_choice.SetSelection(sub_list.index(preset["subtitles"]))
        
        # Other settings
        if "no_data" in preset:
            self.exclude_data_streams.SetValue(preset["no_data"])
        if "fix_resolution" in preset:
            self.fix_res.SetValue(preset["fix_resolution"])
        if "fix_err" in preset:
            self.fix_errors.SetValue(preset["fix_err"])
            
        # Update preview after applying preset
        self.update_output_preview()

    def get_current_settings(self):
        """Get current settings from the interface."""
        sub_list = ["None", "First", "All", "srt"]
        return {
            "encode_video": self.vcodec_checkbox.GetValue(),
            "video_codec": list(VIDEO_CODECS)[self.vcodec_choice.GetSelection()],
            "encode_audio": self.acodec_checkbox.GetValue(),
            "audio_codec": list(AUDIO_CODECS)[self.acodec_choice.GetSelection()],
            "use_crf": self.crf_checkbox.GetValue(),
            "crf_value": self.crf_int.GetValue(),
            "output_suffix": self.suffix_textbox.GetValue(),
            "append_res": self.append_res_checkbox.GetValue(),
            "output_extension": list(VIDEO_EXTENSIONS)[self.extension_choice.GetSelection()],
            "subtitles": sub_list[self.sub_choice.GetSelection()],
            "no_data": self.exclude_data_streams.GetValue(),
            "fix_resolution": self.fix_res.GetValue(),
            "fix_err": self.fix_errors.GetValue()
        }

    def OnSavePreset(self, event):
        """Handle saving current settings as a preset."""
        dlg = wx.TextEntryDialog(self, "Enter preset name:", "Save Preset")
        if dlg.ShowModal() == wx.ID_OK:
            preset_name = dlg.GetValue().strip()
            if preset_name:
                if self.app_state.preset_manager:
                    try:
                        current_settings = self.get_current_settings()
                        self.app_state.preset_manager.save_preset(preset_name, current_settings)
                        self.load_preset_choices()  # Refresh the list
                        # Select the newly created preset
                        for i in range(self.preset_choice.GetCount()):
                            if self.preset_choice.GetString(i) == preset_name:
                                self.preset_choice.SetSelection(i)
                                break
                        wx.MessageBox(f"Preset '{preset_name}' saved successfully!", "Preset Saved", 
                                    wx.OK | wx.ICON_INFORMATION)
                    except PresetError as e:
                        wx.MessageBox(f"Error saving preset: {e}", "Preset Error", wx.OK | wx.ICON_ERROR)
        dlg.Destroy()

    def OnManagePresets(self, event):
        """Open preset management dialog."""
        dlg = PresetManagerDialog(self, self.app_state.preset_manager)
        if dlg.ShowModal() == wx.ID_OK:
            self.load_preset_choices()  # Refresh the list
        dlg.Destroy()

    def OnOutputOptions(self, event):
        """Open advanced output options dialog."""
        # Sync main screen controls to output generator before opening dialog
        self.sync_main_controls_to_generator()
        
        dlg = OutputOptionsDialog(self, self.output_generator)
        if dlg.ShowModal() == wx.ID_OK:
            # Optionally sync back to main screen controls
            self.sync_generator_to_main_controls()
            # Update preview after output options change
            self.update_output_preview()
        dlg.Destroy()
    
    def sync_main_controls_to_generator(self):
        """Sync main screen controls (suffix, extension, append resolution) to output generator."""
        # Get current values from main screen controls
        suffix = self.suffix_textbox.GetValue()
        extension = self.extension_choice.GetStringSelection()
        append_resolution = self.append_res_checkbox.GetValue()
        
        # Update output generator with main screen values (only basic naming)
        # Note: We only sync the basic options that exist on the main screen
        # Advanced options (directory, patterns, etc.) are preserved
        self.output_generator.set_naming_options(
            suffix=suffix,
            extension=extension,
            include_resolution=append_resolution,
            # Preserve other advanced options
            include_codec=self.output_generator.include_codec,
            include_quality=self.output_generator.include_quality,
            include_date=self.output_generator.include_date
        )
        
    def sync_generator_to_main_controls(self):
        """Sync output generator settings back to main screen controls."""
        # Update main screen controls with generator values
        self.suffix_textbox.SetValue(self.output_generator.suffix)
        
        # Find and select the extension in the choice control
        extension = self.output_generator.extension
        extension_index = self.extension_choice.FindString(extension)
        if extension_index != wx.NOT_FOUND:
            self.extension_choice.SetSelection(extension_index)
        else:
            # If exact match not found, try to set the value directly
            self.extension_choice.SetValue(extension)
            
        self.append_res_checkbox.SetValue(self.output_generator.include_resolution)
        
        # Update the config to keep main screen and generator in sync
        self.app_state.config["output_suffix"] = self.output_generator.suffix
        self.app_state.config["output_extension"] = self.output_generator.extension
        self.app_state.config["append_res"] = self.output_generator.include_resolution  # Use correct config key
        
        # Save all advanced output settings to config
        self.save_advanced_output_settings()
        
        # Update preview after syncing
        self.update_output_preview()
    
    def save_advanced_output_settings(self):
        """Save all advanced output settings to app config."""
        config = self.app_state.config
        
        # Directory settings
        config["output_directory"] = str(self.output_generator.output_directory) if self.output_generator.output_directory else ""
        config["subdirectory_pattern"] = self.output_generator.subdirectory_pattern
        
        # Naming settings
        config["filename_pattern"] = self.output_generator.filename_pattern
        config["include_codec"] = self.output_generator.include_codec
        config["include_quality"] = self.output_generator.include_quality
        config["include_date"] = self.output_generator.include_date
        
        # File handling
        config["overwrite_policy"] = self.output_generator.overwrite_policy
        config["preserve_directory_structure"] = self.output_generator.preserve_directory_structure
    
    def load_advanced_output_settings(self):
        """Load all advanced output settings from app config."""
        config = self.app_state.config
        
        # Directory settings
        output_dir = config.get("output_directory", "")
        if output_dir:
            self.output_generator.set_output_directory(pathlib.Path(output_dir))
        else:
            self.output_generator.set_output_directory(None)
            
        self.output_generator.set_subdirectory_pattern(config.get("subdirectory_pattern", ""))
        
        # Naming settings
        self.output_generator.set_filename_pattern(config.get("filename_pattern", "{stem}{suffix}{extension}"))
        
        # Advanced naming options
        self.output_generator.set_naming_options(
            suffix=config.get("output_suffix", "_encoded"),
            extension=config.get("output_extension", ".mkv"),
            include_resolution=config.get("append_res", False),  # Use correct config key
            include_codec=config.get("include_codec", False),
            include_quality=config.get("include_quality", False),
            include_date=config.get("include_date", False)
        )
        
        # File handling
        self.output_generator.set_overwrite_policy(config.get("overwrite_policy", "skip"))
        self.output_generator.preserve_directory_structure = config.get("preserve_directory_structure", True)
        
        # Update preview after loading settings
        self.update_output_preview()


class OutputOptionsDialog(wx.Dialog):
    """Dialog for configuring advanced output options."""
    
    def __init__(self, parent, output_generator: OutputPathGenerator):
        super().__init__(parent, title="Advanced Output Options", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.output_generator = output_generator
        
        # Create a notebook for different option categories
        notebook = wx.Notebook(self)
        
        # Basic Options Tab
        basic_panel = wx.Panel(notebook)
        self.create_basic_options(basic_panel)
        notebook.AddPage(basic_panel, "Basic Options")
        
        # Directory Options Tab
        directory_panel = wx.Panel(notebook)
        self.create_directory_options(directory_panel)
        notebook.AddPage(directory_panel, "Directory Options")
        
        # Naming Options Tab
        naming_panel = wx.Panel(notebook)
        self.create_naming_options(naming_panel)
        notebook.AddPage(naming_panel, "Naming Options")
        
        # Preview Tab
        preview_panel = wx.Panel(notebook)
        self.create_preview_options(preview_panel)
        notebook.AddPage(preview_panel, "Preview")
        
        # Dialog buttons
        button_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        
        # Add info text about main screen sync at the bottom
        info_text = wx.StaticText(self, label="Note: Basic options (Suffix, Extension, Append Resolution) are synced with the main screen controls.")
        info_text.SetFont(info_text.GetFont().Italic())
        
        # Main layout
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(info_text, 0, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        self.SetSize((720, 680))
        self.SetMinSize((680, 650))
        
        # Bind events
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)
        
        # Load current settings
        self.load_current_settings()
    
    def create_basic_options(self, panel):
        """Create basic output options."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add some top padding
        sizer.AddSpacer(10)
        
        # Output preset selection
        preset_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Output Presets")
        self.preset_choice = wx.ComboBox(panel, choices=OUTPUT_PRESETS, style=wx.CB_READONLY)
        self.preset_choice.Bind(wx.EVT_COMBOBOX, self.OnPresetSelected)
        preset_box.Add(self.preset_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        # Basic naming options
        naming_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Basic Naming")
        
        suffix_sizer = wx.BoxSizer(wx.HORIZONTAL)
        suffix_sizer.Add(wx.StaticText(panel, label="Suffix:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.suffix_ctrl = wx.TextCtrl(panel, value="_encoded")
        suffix_sizer.Add(self.suffix_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        
        ext_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ext_sizer.Add(wx.StaticText(panel, label="Extension:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.extension_choice = wx.ComboBox(panel, choices=list(VIDEO_EXTENSIONS), style=wx.CB_READONLY)
        ext_sizer.Add(self.extension_choice, 1, wx.ALL | wx.EXPAND, 5)
        
        naming_box.Add(suffix_sizer, 0, wx.EXPAND | wx.ALL, 3)
        naming_box.Add(ext_sizer, 0, wx.EXPAND | wx.ALL, 3)
        
        # Options checkboxes
        options_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Include in Filename")
        self.include_resolution_check = wx.CheckBox(panel, label="Include resolution (e.g., 1920x1080)")
        self.include_codec_check = wx.CheckBox(panel, label="Include video codec")
        self.include_quality_check = wx.CheckBox(panel, label="Include quality setting (CRF)")
        self.include_date_check = wx.CheckBox(panel, label="Include date")
        
        options_box.Add(self.include_resolution_check, 0, wx.ALL, 5)
        options_box.Add(self.include_codec_check, 0, wx.ALL, 5)
        options_box.Add(self.include_quality_check, 0, wx.ALL, 5)
        options_box.Add(self.include_date_check, 0, wx.ALL, 5)
        
        # File handling
        handling_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "File Handling")
        self.overwrite_choice = wx.RadioButton(panel, label="Overwrite existing files", style=wx.RB_GROUP)
        self.skip_choice = wx.RadioButton(panel, label="Skip existing files")
        self.increment_choice = wx.RadioButton(panel, label="Auto-increment filename for existing files")
        
        handling_box.Add(self.overwrite_choice, 0, wx.ALL, 5)
        handling_box.Add(self.skip_choice, 0, wx.ALL, 5)
        handling_box.Add(self.increment_choice, 0, wx.ALL, 5)
        
        # Layout
        sizer.Add(preset_box, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(naming_box, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(options_box, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(handling_box, 0, wx.EXPAND | wx.ALL, 8)
        
        # Add some bottom padding
        sizer.AddSpacer(10)
        
        panel.SetSizer(sizer)
    
    def create_directory_options(self, panel):
        """Create directory and organization options."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Output directory selection
        dir_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Output Directory")
        
        self.same_dir_radio = wx.RadioButton(panel, label="Same as input files", style=wx.RB_GROUP)
        self.custom_dir_radio = wx.RadioButton(panel, label="Custom directory:")
        
        custom_dir_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.custom_dir_ctrl = wx.TextCtrl(panel, style=wx.TE_READONLY)
        self.browse_dir_button = wx.Button(panel, label="Browse...")
        self.browse_dir_button.Bind(wx.EVT_BUTTON, self.OnBrowseDirectory)
        
        custom_dir_sizer.Add(self.custom_dir_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        custom_dir_sizer.Add(self.browse_dir_button, 0, wx.ALL, 5)
        
        dir_box.Add(self.same_dir_radio, 0, wx.ALL, 5)
        dir_box.Add(self.custom_dir_radio, 0, wx.ALL, 5)
        dir_box.Add(custom_dir_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Subdirectory options
        subdir_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Subdirectory Organization")
        
        self.no_subdir_radio = wx.RadioButton(panel, label="No subdirectory", style=wx.RB_GROUP)
        self.encoded_subdir_radio = wx.RadioButton(panel, label="Create 'encoded' subdirectory")
        self.codec_subdir_radio = wx.RadioButton(panel, label="Organize by codec")
        self.date_subdir_radio = wx.RadioButton(panel, label="Organize by date")
        self.custom_subdir_radio = wx.RadioButton(panel, label="Custom subdirectory pattern:")
        
        self.custom_subdir_ctrl = wx.TextCtrl(panel, value="")
        self.custom_subdir_ctrl.SetToolTip("Use placeholders like {codec}, {date}, {resolution}")
        
        subdir_box.Add(self.no_subdir_radio, 0, wx.ALL, 5)
        subdir_box.Add(self.encoded_subdir_radio, 0, wx.ALL, 5)
        subdir_box.Add(self.codec_subdir_radio, 0, wx.ALL, 5)
        subdir_box.Add(self.date_subdir_radio, 0, wx.ALL, 5)
        subdir_box.Add(self.custom_subdir_radio, 0, wx.ALL, 5)
        subdir_box.Add(self.custom_subdir_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        
        # Layout
        sizer.Add(dir_box, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(subdir_box, 0, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(sizer)
    
    def create_naming_options(self, panel):
        """Create advanced filename pattern options."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Custom filename pattern
        pattern_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Custom Filename Pattern")
        
        self.pattern_ctrl = wx.TextCtrl(panel, value="{stem}{suffix}{extension}")
        pattern_box.Add(wx.StaticText(panel, label="Filename Pattern:"), 0, wx.ALL, 5)
        pattern_box.Add(self.pattern_ctrl, 0, wx.EXPAND | wx.ALL, 5)
        
        # Pattern help
        help_text = """Available placeholders:
{stem} - Original filename without extension
{suffix} - Custom suffix
{extension} - Output file extension
{resolution} - Video resolution (e.g., 1920x1080)
{width} - Video width
{height} - Video height
{codec} - Video codec name
{quality} - Quality setting (CRF value)
{date} - Current date (YYYY-MM-DD)
{time} - Current time (HHMMSS)
{duration} - Video duration in seconds
{size_mb} - Original file size in MB

Example: {stem}_{codec}_crf{quality}{extension}
Result: movie_h265_crf23.mkv"""
        
        help_label = wx.StaticText(panel, label=help_text)
        help_label.SetFont(wx.Font(8, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        pattern_box.Add(help_label, 0, wx.ALL, 5)
        
        sizer.Add(pattern_box, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)
    
    def create_preview_options(self, panel):
        """Create preview tab to show example output paths."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Sample input files for preview
        preview_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Preview Output Paths")
        
        self.preview_button = wx.Button(panel, label="Update Preview")
        self.preview_button.Bind(wx.EVT_BUTTON, self.OnUpdatePreview)
        
        self.preview_list = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.preview_list.SetFont(wx.Font(9, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        preview_box.Add(self.preview_button, 0, wx.ALL, 5)
        preview_box.Add(self.preview_list, 1, wx.EXPAND | wx.ALL, 5)
        
        sizer.Add(preview_box, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)
    
    def load_current_settings(self):
        """Load current settings from the output generator."""
        self.suffix_ctrl.SetValue(self.output_generator.suffix)
        
        # Find matching extension
        try:
            extension_list = list(VIDEO_EXTENSIONS)
            if self.output_generator.extension in extension_list:
                ext_index = extension_list.index(self.output_generator.extension)
                self.extension_choice.SetSelection(ext_index)
        except (ValueError, AttributeError):
            pass
        
        # Set checkboxes
        self.include_resolution_check.SetValue(self.output_generator.include_resolution)
        self.include_codec_check.SetValue(self.output_generator.include_codec)
        self.include_quality_check.SetValue(self.output_generator.include_quality)
        self.include_date_check.SetValue(self.output_generator.include_date)
        
        # Set overwrite policy
        if self.output_generator.overwrite_policy == "overwrite":
            self.overwrite_choice.SetValue(True)
        elif self.output_generator.overwrite_policy == "skip":
            self.skip_choice.SetValue(True)
        else:
            self.increment_choice.SetValue(True)
        
        # Set directory options
        if self.output_generator.output_directory:
            self.custom_dir_radio.SetValue(True)
            self.custom_dir_ctrl.SetValue(str(self.output_generator.output_directory))
        else:
            self.same_dir_radio.SetValue(True)
        
        # Set subdirectory options
        if not self.output_generator.subdirectory_pattern:
            self.no_subdir_radio.SetValue(True)
        elif self.output_generator.subdirectory_pattern == "encoded":
            self.encoded_subdir_radio.SetValue(True)
        elif self.output_generator.subdirectory_pattern == "{codec}":
            self.codec_subdir_radio.SetValue(True)
        elif self.output_generator.subdirectory_pattern == "{date}":
            self.date_subdir_radio.SetValue(True)
        else:
            self.custom_subdir_radio.SetValue(True)
            self.custom_subdir_ctrl.SetValue(self.output_generator.subdirectory_pattern)
        
        # Set filename pattern
        self.pattern_ctrl.SetValue(self.output_generator.filename_pattern)
    
    def OnPresetSelected(self, event):
        """Handle output preset selection."""
        preset_name = self.preset_choice.GetStringSelection()
        if preset_name:
            try:
                self.output_generator = OutputPreset.get_preset(preset_name)
                self.load_current_settings()
            except ValueError as e:
                wx.MessageBox(f"Error loading preset: {e}", "Preset Error", wx.OK | wx.ICON_ERROR)
    
    def OnBrowseDirectory(self, event):
        """Browse for custom output directory."""
        dlg = wx.DirDialog(self, "Choose output directory:")
        if dlg.ShowModal() == wx.ID_OK:
            self.custom_dir_ctrl.SetValue(dlg.GetPath())
            self.custom_dir_radio.SetValue(True)
        dlg.Destroy()
    
    def OnUpdatePreview(self, event):
        """Update the preview with sample output paths."""
        # Apply current settings to generator
        self.apply_settings_to_generator()
        
        # Create sample input files for preview
        sample_files = [
            pathlib.Path("/path/to/movies/Action Movie (2023).mkv"),
            pathlib.Path("/path/to/series/Show S01E01.mp4"),
            pathlib.Path("/path/to/home/vacation_video.avi")
        ]
        
        # Create sample encoding settings
        sample_settings = {
            "video_codec": "libx265",
            "audio_codec": "aac",
            "use_crf": True,
            "crf_value": 23
        }
        
        # Generate preview
        preview_text = "Preview Output Paths:\n\n"
        
        for input_file in sample_files:
            try:
                output_path = self.output_generator.generate_output_path(
                    input_file, None, sample_settings)
                preview_text += f"Input:  {input_file}\n"
                preview_text += f"Output: {output_path}\n\n"
            except Exception as e:
                preview_text += f"Input:  {input_file}\n"
                preview_text += f"Error:  {e}\n\n"
        
        self.preview_list.SetValue(preview_text)
    
    def apply_settings_to_generator(self):
        """Apply dialog settings to the output generator."""
        # Basic naming
        self.output_generator.set_naming_options(
            suffix=self.suffix_ctrl.GetValue(),
            extension=list(VIDEO_EXTENSIONS)[self.extension_choice.GetSelection()],
            include_resolution=self.include_resolution_check.GetValue(),
            include_codec=self.include_codec_check.GetValue(),
            include_quality=self.include_quality_check.GetValue(),
            include_date=self.include_date_check.GetValue()
        )
        
        # Overwrite policy
        if self.overwrite_choice.GetValue():
            policy = "overwrite"
        elif self.skip_choice.GetValue():
            policy = "skip"
        else:
            policy = "increment"
        self.output_generator.set_overwrite_policy(policy)
        
        # Output directory
        if self.custom_dir_radio.GetValue():
            custom_dir = self.custom_dir_ctrl.GetValue().strip()
            if custom_dir:
                self.output_generator.set_output_directory(pathlib.Path(custom_dir))
        else:
            self.output_generator.set_output_directory(None)
        
        # Subdirectory pattern
        if self.no_subdir_radio.GetValue():
            pattern = ""
        elif self.encoded_subdir_radio.GetValue():
            pattern = "encoded"
        elif self.codec_subdir_radio.GetValue():
            pattern = "{codec}"
        elif self.date_subdir_radio.GetValue():
            pattern = "{date}"
        else:
            pattern = self.custom_subdir_ctrl.GetValue()
        
        self.output_generator.set_subdirectory_pattern(pattern)
        
        # Filename pattern
        self.output_generator.set_filename_pattern(self.pattern_ctrl.GetValue())
    
    def OnOK(self, event):
        """Handle OK button - apply all settings."""
        try:
            self.apply_settings_to_generator()
            event.Skip()  # Close dialog
        except Exception as e:
            wx.MessageBox(f"Error applying settings: {e}", "Configuration Error", wx.OK | wx.ICON_ERROR)


class PresetManagerDialog(wx.Dialog):
    """Dialog for managing presets."""
    
    def __init__(self, parent, preset_manager):
        super().__init__(parent, title="Manage Presets", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.preset_manager = preset_manager
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Preset list
        list_label = wx.StaticText(self, label="Available Presets:")
        self.preset_list = wx.ListBox(self, style=wx.LB_SINGLE)
        self.refresh_preset_list()
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.rename_button = wx.Button(self, label="Rename")
        self.rename_button.Bind(wx.EVT_BUTTON, self.OnRename)
        
        self.delete_button = wx.Button(self, label="Delete")
        self.delete_button.Bind(wx.EVT_BUTTON, self.OnDelete)
        
        self.export_button = wx.Button(self, label="Export...")
        self.export_button.Bind(wx.EVT_BUTTON, self.OnExport)
        
        self.import_button = wx.Button(self, label="Import...")
        self.import_button.Bind(wx.EVT_BUTTON, self.OnImport)
        
        button_sizer.Add(self.rename_button, 0, wx.ALL, 5)
        button_sizer.Add(self.delete_button, 0, wx.ALL, 5)
        button_sizer.Add(self.export_button, 0, wx.ALL, 5)
        button_sizer.Add(self.import_button, 0, wx.ALL, 5)
        
        # Dialog buttons
        dialog_buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        
        # Layout
        sizer.Add(list_label, 0, wx.ALL, 5)
        sizer.Add(self.preset_list, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        sizer.Add(dialog_buttons, 0, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(sizer)
        self.SetSize((400, 300))
        
        # Enable/disable buttons based on selection
        self.preset_list.Bind(wx.EVT_LISTBOX, self.OnSelectionChanged)
        self.OnSelectionChanged(None)
    
    def refresh_preset_list(self):
        """Refresh the preset list."""
        self.preset_list.Clear()
        if self.preset_manager:
            preset_names = list(self.preset_manager.get_preset_names())
            self.preset_list.AppendItems(preset_names)
    
    def OnSelectionChanged(self, event):
        """Handle selection changes in the preset list."""
        has_selection = self.preset_list.GetSelection() != wx.NOT_FOUND
        self.rename_button.Enable(has_selection)
        self.delete_button.Enable(has_selection)
        self.export_button.Enable(has_selection)
    
    def OnRename(self, event):
        """Handle renaming a preset."""
        selection = self.preset_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return
        
        old_name = self.preset_list.GetStringSelection()
        dlg = wx.TextEntryDialog(self, f"Enter new name for '{old_name}':", "Rename Preset", old_name)
        
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.GetValue().strip()
            if new_name and new_name != old_name:
                try:
                    self.preset_manager.rename_preset(old_name, new_name)
                    self.refresh_preset_list()
                    # Select the renamed preset
                    for i in range(self.preset_list.GetCount()):
                        if self.preset_list.GetString(i) == new_name:
                            self.preset_list.SetSelection(i)
                            break
                except PresetError as e:
                    wx.MessageBox(f"Error renaming preset: {e}", "Rename Error", wx.OK | wx.ICON_ERROR)
        dlg.Destroy()
    
    def OnDelete(self, event):
        """Handle deleting a preset."""
        selection = self.preset_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return
        
        preset_name = self.preset_list.GetStringSelection()
        if wx.MessageBox(f"Are you sure you want to delete the preset '{preset_name}'?", 
                        "Confirm Delete", wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            try:
                self.preset_manager.delete_preset(preset_name)
                self.refresh_preset_list()
            except PresetError as e:
                wx.MessageBox(f"Error deleting preset: {e}", "Delete Error", wx.OK | wx.ICON_ERROR)
    
    def OnExport(self, event):
        """Handle exporting a preset."""
        selection = self.preset_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return
        
        preset_name = self.preset_list.GetStringSelection()
        wildcard = "JSON files (*.json)|*.json"
        dlg = wx.FileDialog(self, f"Export preset '{preset_name}'", 
                           defaultFile=f"{preset_name}.json",
                           wildcard=wildcard, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        
        if dlg.ShowModal() == wx.ID_OK:
            try:
                self.preset_manager.export_preset(preset_name, dlg.GetPath())
                wx.MessageBox(f"Preset '{preset_name}' exported successfully!", "Export Complete",
                            wx.OK | wx.ICON_INFORMATION)
            except PresetError as e:
                wx.MessageBox(f"Error exporting preset: {e}", "Export Error", wx.OK | wx.ICON_ERROR)
        dlg.Destroy()
    
    def OnImport(self, event):
        """Handle importing a preset."""
        wildcard = "JSON files (*.json)|*.json"
        dlg = wx.FileDialog(self, "Import preset", wildcard=wildcard, style=wx.FD_OPEN)
        
        if dlg.ShowModal() == wx.ID_OK:
            try:
                imported_name = self.preset_manager.import_preset(dlg.GetPath())
                self.refresh_preset_list()
                # Select the imported preset
                for i in range(self.preset_list.GetCount()):
                    if self.preset_list.GetString(i) == imported_name:
                        self.preset_list.SetSelection(i)
                        break
                wx.MessageBox(f"Preset '{imported_name}' imported successfully!", "Import Complete",
                            wx.OK | wx.ICON_INFORMATION)
            except PresetError as e:
                wx.MessageBox(f"Error importing preset: {e}", "Import Error", wx.OK | wx.ICON_ERROR)
        dlg.Destroy()


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


class SelectionOptionsDialog(wx.Dialog):
    """Dialog for advanced video selection options."""
    
    def __init__(self, parent, listbox, app_state):
        super().__init__(parent, title="Selection Options")
        self.listbox = listbox
        self.app_state = app_state
        
        self.InitUI()
        self.Fit()  # Size dialog to fit all content
        self.SetMinSize((500, 650))  # Set a reasonable minimum size with extra width
        self.CenterOnParent()
    
    def get_available_codecs(self):
        """Extract video and audio codecs that are actually present in the current video list."""
        video_codecs = set()
        audio_codecs = set()
        
        # Go through all cached video info to collect actual codec names
        for abs_path, info_obj in self.listbox.info_cache.items():
            if info_obj:
                # Extract video codecs
                if info_obj.video_streams:
                    for stream in info_obj.video_streams:
                        codec_name = stream.get("codec_name", "")
                        if codec_name and codec_name != "ERROR":
                            video_codecs.add(codec_name)
                
                # Extract audio codecs
                if info_obj.audio_streams:
                    for stream in info_obj.audio_streams:
                        codec_name = stream.get("codec_name", "")
                        if codec_name and codec_name != "ERROR":
                            audio_codecs.add(codec_name)
        
        # Convert to sorted lists for consistent display
        video_codec_list = sorted(list(video_codecs))
        audio_codec_list = sorted(list(audio_codecs))
        
        # If no codecs found (empty list), provide some fallback options
        if not video_codec_list:
            video_codec_list = ["(no videos loaded)"]
        if not audio_codec_list:
            audio_codec_list = ["(no videos loaded)"]
            
        return video_codec_list, audio_codec_list
    
    def InitUI(self):
        """Initialize the dialog UI."""
        # First, extract available codecs from the current video list
        available_video_codecs, available_audio_codecs = self.get_available_codecs()
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(panel, label="Advanced Selection Options")
        title_font = title.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        # Video Codec Selection
        codec_box = wx.StaticBox(panel, label="Video Codec")
        codec_sizer = wx.StaticBoxSizer(codec_box, wx.VERTICAL)
        
        self.select_by_vcodec = wx.CheckBox(panel, label="Select by video codec:")
        codec_sizer.Add(self.select_by_vcodec, 0, wx.ALL, 5)
        
        codec_choice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.vcodec_condition = wx.Choice(panel, choices=["that are", "that are NOT"])
        self.vcodec_condition.SetSelection(1)  # Default to "NOT" for conversion workflows
        self.vcodec_choice = wx.Choice(panel, choices=available_video_codecs)
        if available_video_codecs and available_video_codecs[0] != "(no videos loaded)":
            self.vcodec_choice.SetSelection(0)
        
        codec_choice_sizer.Add(wx.StaticText(panel, label="Videos "), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
        codec_choice_sizer.Add(self.vcodec_condition, 0, wx.ALL, 2)
        codec_choice_sizer.Add(self.vcodec_choice, 0, wx.ALL, 2)
        codec_sizer.Add(codec_choice_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Audio Codec Selection
        audio_box = wx.StaticBox(panel, label="Audio Codec")
        audio_sizer = wx.StaticBoxSizer(audio_box, wx.VERTICAL)
        
        self.select_by_acodec = wx.CheckBox(panel, label="Select by audio codec:")
        audio_sizer.Add(self.select_by_acodec, 0, wx.ALL, 5)
        
        audio_choice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.acodec_condition = wx.Choice(panel, choices=["that are", "that are NOT"])
        self.acodec_condition.SetSelection(1)
        self.acodec_choice = wx.Choice(panel, choices=available_audio_codecs)
        if available_audio_codecs and available_audio_codecs[0] != "(no videos loaded)":
            self.acodec_choice.SetSelection(0)
        
        audio_choice_sizer.Add(wx.StaticText(panel, label="Videos "), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
        audio_choice_sizer.Add(self.acodec_condition, 0, wx.ALL, 2)
        audio_choice_sizer.Add(self.acodec_choice, 0, wx.ALL, 2)
        audio_sizer.Add(audio_choice_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Resolution Selection
        res_box = wx.StaticBox(panel, label="Resolution")
        res_sizer = wx.StaticBoxSizer(res_box, wx.VERTICAL)
        
        self.select_by_resolution = wx.CheckBox(panel, label="Select by resolution:")
        res_sizer.Add(self.select_by_resolution, 0, wx.ALL, 5)
        
        res_choice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.res_condition = wx.Choice(panel, choices=["higher than", "lower than", "equal to"])
        self.res_condition.SetSelection(0)
        
        res_presets = ["720p (1280x720)", "1080p (1920x1080)", "1440p (2560x1440)", "4K (3840x2160)", "Custom"]
        self.res_preset = wx.Choice(panel, choices=res_presets)
        self.res_preset.SetSelection(1)  # Default to 1080p
        self.res_preset.Bind(wx.EVT_CHOICE, self.OnResolutionPreset)
        
        res_choice_sizer.Add(wx.StaticText(panel, label="Videos "), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
        res_choice_sizer.Add(self.res_condition, 0, wx.ALL, 2)
        res_choice_sizer.Add(self.res_preset, 1, wx.ALL | wx.EXPAND, 2)
        res_sizer.Add(res_choice_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Custom resolution input
        custom_res_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.res_width = wx.SpinCtrl(panel, min=1, max=7680, initial=1920)
        self.res_height = wx.SpinCtrl(panel, min=1, max=4320, initial=1080)
        
        custom_res_sizer.Add(wx.StaticText(panel, label="Width:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
        custom_res_sizer.Add(self.res_width, 0, wx.ALL, 2)
        custom_res_sizer.Add(wx.StaticText(panel, label="Height:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
        custom_res_sizer.Add(self.res_height, 0, wx.ALL, 2)
        res_sizer.Add(custom_res_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # File Size Selection
        size_box = wx.StaticBox(panel, label="File Size")
        size_sizer = wx.StaticBoxSizer(size_box, wx.VERTICAL)
        
        self.select_by_size = wx.CheckBox(panel, label="Select by file size:")
        size_sizer.Add(self.select_by_size, 0, wx.ALL, 5)
        
        size_choice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.size_condition = wx.Choice(panel, choices=["larger than", "smaller than"])
        self.size_condition.SetSelection(0)
        self.size_value = wx.SpinCtrlDouble(panel, min=0.1, max=100.0, initial=1.0, inc=0.1)
        self.size_unit = wx.Choice(panel, choices=["MB", "GB"])
        self.size_unit.SetSelection(1)  # Default to GB
        
        size_choice_sizer.Add(wx.StaticText(panel, label="Videos "), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
        size_choice_sizer.Add(self.size_condition, 0, wx.ALL, 2)
        size_choice_sizer.Add(self.size_value, 0, wx.ALL, 2)
        size_choice_sizer.Add(self.size_unit, 0, wx.ALL, 2)
        size_sizer.Add(size_choice_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Extension Selection
        ext_box = wx.StaticBox(panel, label="File Extension")
        ext_sizer = wx.StaticBoxSizer(ext_box, wx.VERTICAL)
        
        self.select_by_extension = wx.CheckBox(panel, label="Select by file extension:")
        ext_sizer.Add(self.select_by_extension, 0, wx.ALL, 5)
        
        ext_choice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.ext_condition = wx.Choice(panel, choices=["that are", "that are NOT"])
        self.ext_condition.SetSelection(0)
        self.ext_choice = wx.Choice(panel, choices=list(VIDEO_EXTENSIONS))
        self.ext_choice.SetSelection(0)
        
        ext_choice_sizer.Add(wx.StaticText(panel, label="Videos "), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
        ext_choice_sizer.Add(self.ext_condition, 0, wx.ALL, 2)
        ext_choice_sizer.Add(self.ext_choice, 0, wx.ALL, 2)
        ext_sizer.Add(ext_choice_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Add all sections to main sizer
        main_sizer.Add(codec_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(audio_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(res_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(size_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(ext_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        apply_btn = wx.Button(panel, wx.ID_OK, "Apply Selection")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        
        apply_btn.Bind(wx.EVT_BUTTON, self.OnApply)
        
        button_sizer.Add(apply_btn, 0, wx.ALL, 5)
        button_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.CENTER, 10)
        
        panel.SetSizer(main_sizer)
        
        # Create a top-level sizer for the dialog
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(dialog_sizer)
    
    def OnResolutionPreset(self, event):
        """Handle resolution preset selection."""
        selection = self.res_preset.GetSelection()
        presets = {
            0: (1280, 720),    # 720p
            1: (1920, 1080),   # 1080p
            2: (2560, 1440),   # 1440p
            3: (3840, 2160),   # 4K
            4: None            # Custom - don't change values
        }
        
        if selection in presets and presets[selection]:
            width, height = presets[selection]
            self.res_width.SetValue(width)
            self.res_height.SetValue(height)
    
    def OnApply(self, event):
        """Apply the selection filters."""
        # Check if there are any videos loaded
        if not self.listbox.GetItemCount():
            wx.MessageBox("No videos available to select from.", 
                         "No Videos", wx.OK | wx.ICON_INFORMATION)
            return
        
        # Check if codec filters are enabled but no valid codecs are available
        if (self.select_by_vcodec.GetValue() and 
            self.vcodec_choice.GetStringSelection() == "(no videos loaded)"):
            wx.MessageBox("Cannot filter by video codec: no video codec information available.", 
                         "No Codec Information", wx.OK | wx.ICON_WARNING)
            return
            
        if (self.select_by_acodec.GetValue() and 
            self.acodec_choice.GetStringSelection() == "(no videos loaded)"):
            wx.MessageBox("Cannot filter by audio codec: no audio codec information available.", 
                         "No Codec Information", wx.OK | wx.ICON_WARNING)
            return
        
        # First, unselect all items
        for i in range(self.listbox.GetItemCount()):
            self.listbox.CheckItem(i, False)
        
        selected_count = 0
        
        # Apply filters
        for i in range(self.listbox.GetItemCount()):
            filename = self.listbox.GetItemText(i, 0)  # Get relative path
            full_path = self.app_state.working_dir / filename
            
            should_select = True
            
            # Get video info from cache if available
            info_obj = self.listbox.info_cache.get(str(full_path))
            if not info_obj:
                # Skip files without valid info
                continue
            
            # Video codec filter
            if self.select_by_vcodec.GetValue():
                target_codec = self.vcodec_choice.GetStringSelection()
                has_codec = False
                
                if info_obj.video_streams:
                    video_codec = info_obj.video_streams[0].get("codec_name", "")
                    has_codec = (video_codec == target_codec)
                
                is_not_condition = self.vcodec_condition.GetSelection() == 1
                if is_not_condition:
                    should_select = should_select and not has_codec
                else:
                    should_select = should_select and has_codec
            
            # Audio codec filter
            if self.select_by_acodec.GetValue():
                target_codec = self.acodec_choice.GetStringSelection()
                has_codec = False
                
                if info_obj.audio_streams:
                    audio_codec = info_obj.audio_streams[0].get("codec_name", "")
                    has_codec = (audio_codec == target_codec)
                
                is_not_condition = self.acodec_condition.GetSelection() == 1
                if is_not_condition:
                    should_select = should_select and not has_codec
                else:
                    should_select = should_select and has_codec
            
            # Resolution filter
            if self.select_by_resolution.GetValue():
                target_width = self.res_width.GetValue()
                target_height = self.res_height.GetValue()
                video_width = info_obj.max_width or 0
                video_height = info_obj.max_height or 0
                
                condition = self.res_condition.GetSelection()
                if condition == 0:  # higher than
                    should_select = should_select and (video_width > target_width or video_height > target_height)
                elif condition == 1:  # lower than
                    should_select = should_select and (video_width < target_width and video_height < target_height)
                else:  # equal to
                    should_select = should_select and (video_width == target_width and video_height == target_height)
            
            # File size filter
            if self.select_by_size.GetValue():
                target_size = self.size_value.GetValue()
                if self.size_unit.GetSelection() == 1:  # GB
                    target_size *= 1024  # Convert to MB
                
                video_size_mb = info_obj.size_mb or 0
                
                if self.size_condition.GetSelection() == 0:  # larger than
                    should_select = should_select and (video_size_mb > target_size)
                else:  # smaller than
                    should_select = should_select and (video_size_mb < target_size)
            
            # Extension filter
            if self.select_by_extension.GetValue():
                target_ext = list(VIDEO_EXTENSIONS)[self.ext_choice.GetSelection()]
                file_ext = pathlib.Path(filename).suffix.lower()
                
                has_ext = (file_ext == target_ext)
                is_not_condition = self.ext_condition.GetSelection() == 1
                
                if is_not_condition:
                    should_select = should_select and not has_ext
                else:
                    should_select = should_select and has_ext
            
            # Apply selection
            if should_select:
                self.listbox.CheckItem(i, True)
                selected_count += 1
        
        # Update the video list
        self.listbox.OnChecked(None)
        
        # Show result
        wx.MessageBox(f"Selected {selected_count} videos based on your criteria.", 
                     "Selection Applied", wx.OK | wx.ICON_INFORMATION)
        
        self.EndModal(wx.ID_OK)


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
