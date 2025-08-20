#!/usr/bin/env python

import wx
from typing import TYPE_CHECKING

from modules.presets import PresetError

if TYPE_CHECKING:
    from modules.presets import PresetManager


class PresetManagerDialog(wx.Dialog):
    """Dialog for managing presets."""
    
    def __init__(self, parent, preset_manager: "PresetManager"):
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
