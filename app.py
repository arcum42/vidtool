#!/usr/bin/env python

import wx
from app_state import AppState
from main_frame import MyFrame
from modules.logging_config import setup_logging

# Initialize logging system
setup_logging()

# Global app state instance
app_state = AppState()


class MyApp(wx.App):
    """Main application class for VidTool."""
    
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
