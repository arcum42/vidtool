#!/usr/bin/env python

import wx
import pathlib
from typing import TYPE_CHECKING
from .video_info_panel import VideoInfoPanel

if TYPE_CHECKING:
    from app_state import AppState


class VideoInfoCollapsiblePanel(wx.CollapsiblePane):
    """Collapsible panel for displaying detailed video information."""
    
    def __init__(self, parent, app_state: "AppState"):
        super().__init__(parent, label="Video Information", style=wx.CP_DEFAULT_STYLE)
        
        self.app_state = app_state
        self.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.OnExpand)
        
        # Get the pane and set up the video info panel
        pane = self.GetPane()
        
        # Create the video info panel inside this collapsible pane
        self.vid_info_panel = VideoInfoPanel(pane, app_state)
        
        # Set up the sizer
        pane_sizer = wx.BoxSizer(wx.VERTICAL)
        pane_sizer.Add(self.vid_info_panel, 1, wx.EXPAND | wx.ALL, 5)
        pane.SetSizer(pane_sizer)
        
        # Start collapsed
        self.Collapse(True)
    
    def OnExpand(self, event):
        """Handle expansion/collapse events."""
        # Force layout update
        self.GetParent().Layout()
    
    def update_info(self, info):
        """Update the video information display."""
        if self.vid_info_panel:
            self.vid_info_panel.update_info(info)
            # Auto-expand when showing new info only if setting is enabled
            auto_expand = self.app_state.config.get("auto_expand_video_info", False)
            if auto_expand and self.IsCollapsed():
                self.Expand()
                # Force layout refresh after expansion
                wx.CallAfter(self._refresh_layout)
    
    def _refresh_layout(self):
        """Force a complete layout refresh."""
        # Refresh multiple levels to ensure proper display
        self.GetPane().Layout()
        self.Layout()
        parent = self.GetParent()
        if parent:
            parent.Layout()
            # Also refresh the main frame if needed
            grandparent = parent.GetParent()
            if grandparent:
                grandparent.Layout()
    
    def show_video_info(self, info_obj):
        """Show video information and auto-expand."""
        self.update_info(info_obj)
