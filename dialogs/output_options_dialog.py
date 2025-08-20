#!/usr/bin/env python

import wx
import pathlib
from typing import TYPE_CHECKING

import modules.video as video
from modules.video import VIDEO_EXTENSIONS
from modules.output import OutputPathGenerator, OutputPreset, OUTPUT_PRESETS

if TYPE_CHECKING:
    pass


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
