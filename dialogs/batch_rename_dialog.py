#!/usr/bin/env python

import wx
import re
import pathlib
from typing import List

from modules.logging_config import get_logger

logger = get_logger('batch_operations')


class BatchRenameDialog(wx.Dialog):
    """Dedicated dialog for batch rename operations only."""
    
    def __init__(self, parent, selected_files: List[str], working_dir: pathlib.Path):
        super().__init__(parent, title="Batch Rename", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        self.selected_files = selected_files
        self.working_dir = working_dir
        self.preview_data = []  # Store preview results
        
        self.InitUI()
        self.UpdatePreview()
        
    def InitUI(self):
        """Initialize the user interface."""
        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Instructions
        instructions = wx.StaticText(self, label="""Batch Rename with Regular Expressions

Use regex to find and replace parts of filenames. Common patterns:
• \\d+ = numbers    • \\w+ = word characters    • .* = any characters
• ^text = starts with    • text$ = ends with    • (group) = capture group

Examples:
• Find: "(.*)_old(.*)"  Replace: "\\1_new\\2"  → Changes "_old" to "_new"
• Find: "^(\\d{4})"  Replace: "Year_\\1"  → Adds "Year_" before 4-digit numbers""")
        instructions.Wrap(750)
        font = instructions.GetFont()
        font.PointSize += 1
        instructions.SetFont(font)
        
        main_sizer.Add(instructions, 0, wx.EXPAND | wx.ALL, 10)
        
        # Find pattern
        find_sizer = wx.BoxSizer(wx.HORIZONTAL)
        find_label = wx.StaticText(self, label="Find (regex):")
        self.find_text = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.find_text.SetToolTip("Regular expression pattern to find in filenames")
        
        find_sizer.Add(find_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        find_sizer.Add(self.find_text, 1, wx.EXPAND | wx.ALL, 5)
        
        # Replace pattern
        replace_sizer = wx.BoxSizer(wx.HORIZONTAL)
        replace_label = wx.StaticText(self, label="Replace:")
        self.replace_text = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.replace_text.SetToolTip("Replacement text (use \\1, \\2, etc. for capture groups)")
        
        replace_sizer.Add(replace_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        replace_sizer.Add(self.replace_text, 1, wx.EXPAND | wx.ALL, 5)
        
        # Options
        options_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.case_sensitive_cb = wx.CheckBox(self, label="Case sensitive")
        self.test_mode_cb = wx.CheckBox(self, label="Test mode (preview only)")
        self.test_mode_cb.SetValue(True)
        
        options_sizer.Add(self.case_sensitive_cb, 0, wx.ALL, 5)
        options_sizer.Add(self.test_mode_cb, 0, wx.ALL, 5)
        
        # Preview list
        preview_label = wx.StaticText(self, label="Preview:")
        self.preview_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.preview_list.InsertColumn(0, "Original", width=300)
        self.preview_list.InsertColumn(1, "New Name", width=300)
        self.preview_list.InsertColumn(2, "Status", width=150)
        
        main_sizer.Add(find_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(replace_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(options_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(preview_label, 0, wx.ALL, 5)
        main_sizer.Add(self.preview_list, 1, wx.EXPAND | wx.ALL, 5)
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.preview_btn = wx.Button(self, label="Update Preview")
        self.apply_btn = wx.Button(self, wx.ID_OK, label="Apply Changes")
        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, label="Cancel")
        
        button_sizer.Add(self.preview_btn, 0, wx.ALL, 5)
        button_sizer.AddStretchSpacer()
        button_sizer.Add(self.apply_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        
        # Bind events
        self.preview_btn.Bind(wx.EVT_BUTTON, self.OnUpdatePreview)
        self.apply_btn.Bind(wx.EVT_BUTTON, self.OnApply)
        
        # Bind events for live preview
        self.find_text.Bind(wx.EVT_TEXT, self.OnTextChange)
        self.replace_text.Bind(wx.EVT_TEXT, self.OnTextChange)
        self.case_sensitive_cb.Bind(wx.EVT_CHECKBOX, self.OnTextChange)
        
        # Set initial size
        self.SetSize(wx.Size(800, 600))
        self.CenterOnParent()
    
    def OnTextChange(self, event):
        """Handle text changes in rename fields."""
        # Debounce updates
        if hasattr(self, 'update_timer'):
            self.update_timer.Stop()
        
        self.update_timer = wx.Timer(self)
        self.update_timer.Bind(wx.EVT_TIMER, lambda e: self.UpdatePreview())
        self.update_timer.Start(500, wx.TIMER_ONE_SHOT)
    
    def OnUpdatePreview(self, event):
        """Handle preview button click."""
        self.UpdatePreview()
    
    def UpdatePreview(self):
        """Update the rename preview."""
        self.preview_list.DeleteAllItems()
        self.preview_data = []
        
        find_pattern = self.find_text.GetValue()
        replace_pattern = self.replace_text.GetValue()
        case_sensitive = self.case_sensitive_cb.GetValue()
        
        if not find_pattern:
            return
        
        # Compile regex
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(find_pattern, flags)
        except re.error as e:
            # Show error in first row
            index = self.preview_list.InsertItem(0, "ERROR")
            self.preview_list.SetItem(index, 1, f"Invalid regex: {e}")
            self.preview_list.SetItem(index, 2, "ERROR")
            return
        
        for i, file_path in enumerate(self.selected_files):
            path_obj = pathlib.Path(file_path)
            original_name = path_obj.name
            
            try:
                # Apply regex substitution
                new_name = regex.sub(replace_pattern, original_name)
                
                # Check if name changed
                if new_name == original_name:
                    status = "No change"
                elif not new_name or new_name.isspace():
                    status = "ERROR: Empty name"
                    new_name = original_name
                elif any(char in new_name for char in '<>:"/\\|?*'):
                    status = "ERROR: Invalid characters"
                else:
                    # Check if new file would exist
                    new_path = path_obj.parent / new_name
                    if new_path.exists() and new_path != path_obj:
                        status = "WARNING: File exists"
                    else:
                        status = "OK"
                
                # Add to preview
                index = self.preview_list.InsertItem(i, original_name)
                self.preview_list.SetItem(index, 1, new_name)
                self.preview_list.SetItem(index, 2, status)
                
                # Store data for apply operation
                self.preview_data.append({
                    'original_path': path_obj,
                    'new_name': new_name,
                    'status': status
                })
                
            except Exception as e:
                index = self.preview_list.InsertItem(i, original_name)
                self.preview_list.SetItem(index, 1, f"ERROR: {e}")
                self.preview_list.SetItem(index, 2, "ERROR")
                
                self.preview_data.append({
                    'original_path': path_obj,
                    'new_name': original_name,
                    'status': f"ERROR: {e}"
                })
    
    def OnApply(self, event):
        """Apply the batch rename operations."""
        if self.test_mode_cb.GetValue():
            wx.MessageBox("Test mode is enabled. Disable test mode to apply changes.", 
                         "Test Mode", wx.OK | wx.ICON_INFORMATION)
            return
        
        if not self.preview_data:
            wx.MessageBox("No rename operations to apply.", "Nothing to Do", 
                         wx.OK | wx.ICON_INFORMATION)
            return
        
        # Count operations
        valid_operations = [item for item in self.preview_data if item['status'] == 'OK']
        warning_operations = [item for item in self.preview_data if item['status'].startswith('WARNING')]
        
        if not valid_operations and not warning_operations:
            wx.MessageBox("No valid rename operations to apply.", "Nothing to Do", 
                         wx.OK | wx.ICON_INFORMATION)
            return
        
        # Confirm operation
        msg = f"Apply {len(valid_operations)} rename operations"
        if warning_operations:
            msg += f" and {len(warning_operations)} operations with warnings"
        msg += "?"
        
        if wx.MessageBox(msg, "Confirm Batch Rename", 
                        wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        
        # Apply operations
        success_count = 0
        error_count = 0
        errors = []
        
        for item in self.preview_data:
            if item['status'] in ['OK', 'WARNING: File exists']:
                original_path = item['original_path']
                try:
                    new_path = original_path.parent / item['new_name']
                    
                    if original_path != new_path:
                        original_path.rename(new_path)
                        success_count += 1
                        logger.info(f"Renamed: {original_path.name} → {new_path.name}")
                        
                except Exception as e:
                    error_count += 1
                    error_msg = f"{original_path.name}: {e}"
                    errors.append(error_msg)
                    logger.error(f"Rename failed: {error_msg}")
        
        # Show results
        if error_count == 0:
            wx.MessageBox(f"Successfully renamed {success_count} files.", 
                         "Batch Rename Complete", wx.OK | wx.ICON_INFORMATION)
            self.EndModal(wx.ID_OK)
        else:
            error_summary = f"Renamed {success_count} files successfully.\n{error_count} operations failed:\n\n"
            error_summary += "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                error_summary += f"\n... and {len(errors) - 5} more errors"
            
            wx.MessageBox(error_summary, "Batch Rename Completed with Errors", 
                         wx.OK | wx.ICON_WARNING)
            self.EndModal(wx.ID_OK)
