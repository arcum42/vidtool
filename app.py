#!/usr/bin/python

import wx
import os
import pathlib
import modules.video as video


class VideoInfoPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.video_info = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.video_info.SetValue("Select a video file from the list.")
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.video_info, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(sizer)

    def update_info(self, info):
        self.video_info.SetValue(info)


class MyFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="Vid Tool")

        # Create a panel and sizers
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        top = wx.BoxSizer(wx.HORIZONTAL)
        middle = wx.BoxSizer(wx.HORIZONTAL)
        bottom = wx.BoxSizer(wx.HORIZONTAL)
        top.SetMinSize((800, 50))
        bottom.SetMinSize((800, 100))

        # On the top, create a button to open a file dialog
        self.label = wx.StaticText(panel, label="Directory", style=wx.ALIGN_CENTER)
        top.Add(self.label, 0, wx.SHAPED | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 5)

        self.working_dir_box = wx.TextCtrl(panel)
        self.working_dir = os.getcwd()
        self.working_dir_box.SetValue(self.working_dir)
        top.Add(self.working_dir_box, 1, wx.EXPAND | wx.TOP)

        self.button = wx.Button(panel, label="Browse")
        self.button.SetDefault()
        self.button.SetFocus()
        top.Add(self.button, 0, wx.EXPAND | wx.RIGHT | wx.TOP, 5)
        self.button.Bind(wx.EVT_BUTTON, self.OnChangeDir)

        # In the middle, create a listbox
        self.listbox = wx.ListBox(panel)
        self.populateListBox()
        self.listbox.Bind(wx.EVT_LISTBOX, self.OnListBox)

        # To the right of the listbox, add the VideoInfoPanel
        self.video_info_panel = VideoInfoPanel(panel)

        middle.Add(self.listbox, 1, wx.LEFT | wx.EXPAND, 5)
        middle.Add(self.video_info_panel, 1, wx.RIGHT | wx.EXPAND, 5)

        # On the bottom, create a text control
        self.text = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.text.SetValue("This is a text control.")
        bottom.Add(self.text, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(top, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(middle, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(bottom, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        self.CreateStatusBar()
        self.SetStatusText("Welcome to Vid Tool!")

        self.SetSize((800, 600))
        self.Center()

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Show()

    def OnChangeDir(self, event):
        dlg = wx.DirDialog(
            self,
            "Choose a directory:",
            self.working_dir,
            wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.working_dir = pathlib.Path(dlg.GetPath()).resolve()
            self.working_dir_box.SetValue(str(self.working_dir))
            self.SetStatusText(f"Working directory: {str(self.working_dir)}")
            self.populateListBox()
        dlg.Destroy()

    def populateListBox(self):
        self.listbox.Clear()
        files = (
            p.resolve()
            for p in pathlib.Path(self.working_dir).glob("**/*")
            if p.suffix
            in {
                ".avi",
                ".mpg",
                ".mkv",
                ".mp4",
                ".mov",
                ".webm",
                ".wmv",
                ".mov",
                ".m4v",
                ".ogv",
                ".divx",
            }
        )
        for video in files:
            self.listbox.Append(str(video.relative_to(self.working_dir)))

    def OnClose(self, event):
        self.Destroy()

    def OnListBox(self, event):
        selection = event.GetSelection()
        item = self.listbox.GetString(selection)
        self.SetStatusText(f"Selected: {item}")
        info = video.info(self.working_dir / item)
        self.video_info_panel.update_info(info.get_info_block())


if __name__ == "__main__":
    app = wx.App()
    frame = MyFrame()
    app.MainLoop()
