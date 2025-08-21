#!/usr/bin/env python

import wx
import pathlib
import shutil
import os
from typing import List

from modules.logging_config import get_logger

logger = get_logger('move_to_subfolder')


class MoveToSubfolderDialog(wx.Dialog):
    """Simple dialog for moving files to a subfolder."""
    
    def __init__(self, parent, selected_files: List[str], working_dir: pathlib.Path):
        super().__init__(parent, title="Move to Subfolder", 
                        style=wx.DEFAULT_DIALOG_STYLE)
        
        self.selected_files = selected_files
        self.working_dir = working_dir
        
        self.InitUI()
        
    def InitUI(self):
        """Initialize the user interface."""
        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Info text
        info_text = f"Moving {len(self.selected_files)} video{'s' if len(self.selected_files) != 1 else ''} to a subfolder."
        info_label = wx.StaticText(self, label=info_text)
        main_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)
        
        # Subfolder name input
        folder_sizer = wx.BoxSizer(wx.HORIZONTAL)
        folder_label = wx.StaticText(self, label="Subfolder name:")
        self.folder_text = wx.TextCtrl(self, size=wx.Size(200, -1))
        
        folder_sizer.Add(folder_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        folder_sizer.Add(self.folder_text, 1, wx.EXPAND)
        
        main_sizer.Add(folder_sizer, 0, wx.ALL | wx.EXPAND, 10)
        
        # Options
        options_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.create_folder_cb = wx.CheckBox(self, label="Create folder if it doesn't exist")
        self.create_folder_cb.SetValue(True)
        options_sizer.Add(self.create_folder_cb, 0, wx.ALL, 5)
        
        self.copy_instead_cb = wx.CheckBox(self, label="Copy instead of move")
        self.copy_instead_cb.SetValue(False)
        options_sizer.Add(self.copy_instead_cb, 0, wx.ALL, 5)
        
        main_sizer.Add(options_sizer, 0, wx.ALL | wx.EXPAND, 10)
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        cancel_btn = wx.Button(self, wx.ID_CANCEL, label="Cancel")
        self.ok_btn = wx.Button(self, wx.ID_OK, label="Move Files")
        
        button_sizer.AddStretchSpacer()
        button_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.ok_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        self.Fit()
        self.Center()
        
        # Bind events
        self.ok_btn.Bind(wx.EVT_BUTTON, self.OnOK)
        self.copy_instead_cb.Bind(wx.EVT_CHECKBOX, self.OnCopyModeChanged)
        
        # Set focus to text field
        self.folder_text.SetFocus()
        
    def OnCopyModeChanged(self, event):
        """Update button label when copy mode changes."""
        if self.copy_instead_cb.GetValue():
            self.ok_btn.SetLabel("Copy Files")
        else:
            self.ok_btn.SetLabel("Move Files")
        
    def OnOK(self, event):
        """Handle OK button - perform the move operation."""
        folder_name = self.folder_text.GetValue().strip()
        if not folder_name:
            wx.MessageBox("Please enter a subfolder name.", "Missing Folder Name", 
                         wx.OK | wx.ICON_WARNING)
            return
        
        target_folder = self.working_dir / folder_name
        copy_mode = self.copy_instead_cb.GetValue()
        operation_name = "copy" if copy_mode else "move"
        
        # Create folder if needed
        if not target_folder.exists():
            if self.create_folder_cb.GetValue():
                try:
                    target_folder.mkdir(parents=True)
                    logger.info(f"Created folder: {target_folder}")
                except Exception as e:
                    wx.MessageBox(f"Failed to create folder '{folder_name}':\n{e}", 
                                 "Folder Creation Error", wx.OK | wx.ICON_ERROR)
                    return
            else:
                wx.MessageBox(f"Folder '{folder_name}' doesn't exist and 'Create folder' is disabled.", 
                             "Folder Doesn't Exist", wx.OK | wx.ICON_WARNING)
                return
        
        # Confirm operation
        if wx.MessageBox(f"{operation_name.title()} {len(self.selected_files)} file{'s' if len(self.selected_files) != 1 else ''} to '{folder_name}'?", 
                        f"Confirm {operation_name.title()}", 
                        wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        
        # Perform the operation
        success_count = 0
        error_count = 0
        errors = []
        
        for file_path in self.selected_files:
            source_path = None
            try:
                source_path = pathlib.Path(file_path)
                target_path = target_folder / source_path.name
                
                # Check if target file already exists
                if target_path.exists():
                    # Generate unique filename
                    base_name = target_path.stem
                    extension = target_path.suffix
                    counter = 1
                    while target_path.exists():
                        target_path = target_folder / f"{base_name}_{counter}{extension}"
                        counter += 1
                
                if copy_mode:
                    shutil.copy2(source_path, target_path)
                else:
                    shutil.move(str(source_path), str(target_path))
                
                success_count += 1
                logger.info(f"{operation_name.title()}d: {source_path.name} -> {target_path}")
                
            except Exception as e:
                error_count += 1
                file_name = source_path.name if source_path else pathlib.Path(file_path).name
                error_msg = f"{file_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to {operation_name} {file_name}: {e}")
        
        # Show results
        if error_count == 0:
            wx.MessageBox(f"Successfully {operation_name}d {success_count} file{'s' if success_count != 1 else ''} to '{folder_name}'.", 
                         f"{operation_name.title()} Complete", wx.OK | wx.ICON_INFORMATION)
            self.EndModal(wx.ID_OK)
        else:
            error_summary = f"{operation_name.title()}d {success_count} file{'s' if success_count != 1 else ''} successfully.\n{error_count} operation{'s' if error_count != 1 else ''} failed:\n\n"
            error_summary += "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                error_summary += f"\n... and {len(errors) - 5} more error{'s' if len(errors) - 5 != 1 else ''}"
            
            wx.MessageBox(error_summary, f"{operation_name.title()} Completed with Errors", 
                         wx.OK | wx.ICON_WARNING)
            self.EndModal(wx.ID_OK)
