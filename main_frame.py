#!/usr/bin/env python

import wx
import pathlib
import threading
from typing import TYPE_CHECKING

import modules.video as video
from modules.video import VideoProcessingError, FFmpegNotFoundError, VideoFileError
from modules.logging_config import get_logger
from panels.video_info_panel import VideoInfoPanel
from panels.video_list_panel import VideoList
from panels.reencode_panel import ReencodePane
from panels.settings_panel import SettingsPanel
from dialogs.selection_dialog import SelectionOptionsDialog

if TYPE_CHECKING:
    from app_state import AppState

logger = get_logger('main_frame')


class MyFrame(wx.Frame):
    """Main application frame containing all the GUI components."""
    
    def __init__(self, app_state: "AppState"):
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
        self.refresh_button.Bind(wx.EVT_RIGHT_UP, self.OnRefreshMenu)  # Right-click for menu
        self.refresh_button.SetToolTip("Refresh file list (right-click for options)")

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
        """Handle directory change button."""
        dlg = wx.DirDialog(self, "Choose a directory:", str(self.app_state.working_dir), wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,)
        if dlg.ShowModal() == wx.ID_OK:
            self.app_state.working_dir = pathlib.Path(dlg.GetPath()).resolve()
            self.working_dir_box.SetValue(str(self.app_state.working_dir))
            self.SetStatusText(f"Working directory: {str(self.app_state.working_dir)}")
            self.listbox.refresh(force_full_refresh=True)  # Force full refresh on directory change
            self.app_state.config["working_dir"] = str(self.app_state.working_dir)
        dlg.Destroy()

    def OnRefresh(self, event):
        """Handle refresh button."""
        self.listbox.refresh()
        self.SetStatusText("File list refreshed.")

    def OnRefreshMenu(self, event):
        """Show refresh options menu on right-click."""
        menu = wx.Menu()
        
        normal_refresh = menu.Append(wx.ID_ANY, "Normal Refresh", "Refresh list (preserve cached info)")
        force_refresh = menu.Append(wx.ID_ANY, "Force Complete Refresh", "Re-process all files (clear cache)")
        clear_errors = menu.Append(wx.ID_ANY, "Clear Error Cache", "Clear failed files cache")
        
        # Bind menu events
        self.Bind(wx.EVT_MENU, self.OnRefresh, normal_refresh)
        self.Bind(wx.EVT_MENU, self.OnForceRefresh, force_refresh)
        self.Bind(wx.EVT_MENU, self.OnClearErrorCache, clear_errors)
        
        # Show menu at mouse position
        self.PopupMenu(menu)
        menu.Destroy()

    def OnForceRefresh(self, event):
        """Force a complete refresh that re-processes all files."""
        self.listbox.force_refresh_all()

    def OnClearErrorCache(self, event):
        """Clear the cache of files that previously failed processing."""
        self.listbox.clear_error_cache()

    def OnGoUp(self, event):
        """Handle go up directory button."""
        if self.app_state.working_dir is not None:
            self.app_state.working_dir = self.app_state.working_dir.parent
            self.working_dir_box.SetValue(str(self.app_state.working_dir))
            self.SetStatusText(f"Working directory: {str(self.app_state.working_dir)}")
            self.listbox.refresh(force_full_refresh=True)  # Force full refresh on directory change

    def OnRecursionDepthChanged(self, event):
        """Handle recursion depth control change."""
        depth = self.recursion_spin.GetValue()
        self.app_state.config["recursion_depth"] = depth
        self.listbox.refresh(force_full_refresh=True)  # Force full refresh when depth changes
        if depth == 0:
            self.SetStatusText("Directory scan depth: unlimited (all subdirectories)")
        else:
            self.SetStatusText(f"Directory scan depth: {depth} level{'s' if depth != 1 else ''} deep")

    def OnClose(self, event):
        """Handle application close."""
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
        """Handle play button."""
        logger.debug("Play button clicked")
        
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
                    logger.info(f"Playing: {vid}")
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
        """Select all videos."""
        for i in range(self.listbox.GetItemCount()):
            self.listbox.CheckItem(i)
        self.listbox.OnChecked(event)

    def OnSelectNone(self, event):
        """Deselect all videos."""
        for i in range(self.listbox.GetItemCount()):
            self.listbox.CheckItem(i, False)
        self.listbox.OnChecked(event)

    def OnSelectOptions(self, event):
        """Show advanced selection options dialog."""
        dlg = SelectionOptionsDialog(self, self.listbox, self.app_state)
        dlg.ShowModal()
        dlg.Destroy()
