#!/usr/bin/env python

import wx
import pathlib
from typing import TYPE_CHECKING

from modules.video import VIDEO_EXTENSIONS

if TYPE_CHECKING:
    from app_state import AppState


class SelectionOptionsDialog(wx.Dialog):
    """Dialog for advanced video selection options."""
    
    def __init__(self, parent, listbox, app_state: "AppState"):
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
            if self.app_state.working_dir:
                full_path = self.app_state.working_dir / filename
            else:
                continue
            
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
