#!/usr/bin/env python

import wx
import pathlib
import threading
import time
from typing import TYPE_CHECKING, Optional

import modules.video as video
from modules.video import VIDEO_EXTENSIONS, VIDEO_CODECS, AUDIO_CODECS
from modules.video import VideoProcessingError, FFmpegNotFoundError, VideoFileError
from modules.presets import PresetError
from modules.output import OutputPathGenerator
from modules.logging_config import get_logger, log_error_with_context

if TYPE_CHECKING:
    from app_state import AppState

logger = get_logger('reencode_panel')


class ReencodePane(wx.CollapsiblePane):
    """Collapsible panel for video reencoding options and controls."""
    
    def __init__(self, parent, app_state: "AppState"):
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
        """Handle panel expansion/collapse."""
        self.Layout()
        self.Fit()
        parent = self.GetParent()
        parent.Layout()
        parent.Fit()

    def OnReencode(self, event):
        """Start the reencoding process."""
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
            logger.info(f"Starting encoding for: {video_file}")
            
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
                    logger.warning(f"Output generator failed, using fallback: {e}")
                    encode_job.add_output_from_input(file_append=output_suffix, file_extension=options["output_extension"])

                # Get the output filename for display
                output_name = pathlib.Path(encode_job.output).name
                
                # Update current file label with both input and output filenames
                wx.CallAfter(self.current_file_label.SetLabel, f"{video_name} → {output_name}")
                wx.CallAfter(self.current_file_progress.SetValue, 0)

                # Check if output file already exists and handle according to policy
                if pathlib.Path(encode_job.output).exists():
                    if self.output_generator.overwrite_policy == "skip":
                        logger.info(f"Output file '{encode_job.output}' already exists. Skipping.")
                        errors.append(f"{video_name}: Output file already exists")
                        progress += 1
                        wx.CallAfter(self.total_progress.SetValue, progress)
                        continue
                    elif self.output_generator.overwrite_policy == "overwrite":
                        logger.info(f"Output file '{encode_job.output}' already exists. Will overwrite.")
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
                    logger.debug("Adding srt file")
                    srt_file = pathlib.Path(video_file).with_suffix(".srt")
                    logger.debug(f"Looking for srt file: {srt_file}")
                    if srt_file.exists():
                        logger.info(f"Adding srt file: {srt_file}")
                        encode_job.add_input(str(srt_file))
                    else:
                        logger.warning(f"SRT file {srt_file} does not exist. Skipping.")
                        
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
                    logger.debug(f"FFmpeg output: {line}")

                # Perform the encoding
                encode_result = encode_job.reencode(output_callback=console_output_callback)
                
                if encode_result and not self.cancel_event.is_set():
                    successful += 1
                    
                    # Capture the completed video file path before any async operations
                    completed_video_file = video_file
                    
                    # After successful encoding, refresh the video list and recheck remaining videos
                    if self.app_state.main_frame and hasattr(self.app_state.main_frame, "listbox"):
                        def refresh_and_recheck():
                            # First uncheck the completed video to update the video list
                            logger.debug(f"Unchecking completed video: {pathlib.Path(completed_video_file).name}")
                            self.app_state.main_frame.listbox.uncheck_video_by_path(completed_video_file)
                            
                            # Get the updated list of selected videos (should exclude the just-processed one)
                            remaining_videos = list(self.app_state.video_list)  # Make a copy
                            logger.debug(f"Current video_list after unchecking: {[pathlib.Path(v).name for v in remaining_videos]}")
                            logger.debug(f"Preserving selection for {len(remaining_videos)} remaining videos: {[pathlib.Path(v).name for v in remaining_videos]}")
                            
                            # Refresh the list to show the new encoded file
                            def on_refresh_complete():
                                logger.debug(f"Refresh completed, re-checking {len(remaining_videos)} videos")
                                self.app_state.main_frame.listbox.recheck_videos_by_paths(remaining_videos)
                            
                            self.app_state.main_frame.listbox.refresh(completion_callback=on_refresh_complete)
                        
                        wx.CallAfter(refresh_and_recheck)
                        
                elif self.cancel_event.is_set():
                    errors.append(f"{video_name}: Cancelled by user")
                    break
                
            except (VideoProcessingError, FFmpegNotFoundError, VideoFileError) as e:
                error_msg = f"{video_name}: {e}"
                errors.append(error_msg)
                log_error_with_context(e, f"Processing video {video_name}", logger)
                
            except Exception as e:
                error_msg = f"{video_name}: Unexpected error - {e}"
                errors.append(error_msg)
                log_error_with_context(e, f"Unexpected error processing {video_name}", logger)
            
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

        if self.app_state.main_frame and hasattr(self.app_state.main_frame, "listbox"):
            wx.CallAfter(self.app_state.main_frame.listbox.refresh)

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
        from dialogs.preset_manager_dialog import PresetManagerDialog
        dlg = PresetManagerDialog(self, self.app_state.preset_manager)
        if dlg.ShowModal() == wx.ID_OK:
            self.load_preset_choices()  # Refresh the list
        dlg.Destroy()

    def OnOutputOptions(self, event):
        """Open advanced output options dialog."""
        from dialogs.output_options_dialog import OutputOptionsDialog
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
