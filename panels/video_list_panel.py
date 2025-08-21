#!/usr/bin/env python

import wx
import pathlib
import threading
from typing import TYPE_CHECKING, Optional

import modules.video as video
from modules.video import VIDEO_EXTENSIONS, VideoProcessingError, FFmpegNotFoundError, VideoFileError
from modules.logging_config import get_logger

if TYPE_CHECKING:
    from app_state import AppState

logger = get_logger('video_list')


class VideoList(wx.ListCtrl):
    """Custom ListCtrl for displaying and managing video files with sorting capabilities.
    
    Features:
    - Click column headers to sort by that column
    - Click the same header again to reverse sort order
    - Sorting is maintained during list refreshes
    - Supports sorting by:
      - Filename (alphabetical)
      - Video/Audio codecs (alphabetical)
      - Resolution (by width then height)
      - File size (by actual size in bytes)
    """
    
    COLS = [
        ('Filename', 500),
        ('Video', 50),
        ('Audio', 50),
        ('Res', 80),
        ('Size', 80),
    ]

    def __init__(self, parent, app_state: "AppState", main_frame=None, vid_info_panel=None):
        super().__init__(parent, style=wx.LC_REPORT | wx.SUNKEN_BORDER)
        self.app_state = app_state
        self.main_frame = main_frame
        self.vid_info_panel = vid_info_panel
        self.info_cache = {}  # filename (str) -> video.info object
        self.error_files = set()  # Track files that previously failed processing
        
        # Sorting state
        self.sort_column = -1  # Currently sorted column (-1 for none)
        self.sort_ascending = True  # Sort direction

        for idx, (label, width) in enumerate(self.COLS):
            self.InsertColumn(idx, label)
            self.SetColumnWidth(idx, width)

        self.EnableCheckBoxes()
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelected)
        self.Bind(wx.EVT_LIST_ITEM_CHECKED, self.OnChecked)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColumnClick)
        self.refresh()

    def get_video_files_with_depth(self, directory):
        """Get video files from directory respecting the recursion depth setting."""
        directory = pathlib.Path(directory)
        depth = self.app_state.config.get("recursion_depth", 0)
        
        if depth == 0:
            # Unlimited recursion (original behavior)
            return directory.glob("**/*")
        elif depth == 1:
            # Only current directory
            return directory.glob("*")
        else:
            # Limited recursion depth
            files = []
            for d in range(1, depth + 1):
                pattern = "/".join(["*"] * d)
                files.extend(directory.glob(pattern))
            return files

    def OnSelected(self, event):
        """Handle video selection in the list."""
        selection = self.GetFirstSelected()
        if selection == -1:
            if self.main_frame:
                self.main_frame.SetStatusText("No selection")
            return

        item = self.GetItemText(selection, 0)
        if self.main_frame:
            self.main_frame.SetStatusText(f"Selected: {item}")
        
        if self.app_state.working_dir:
            self.app_state.selected_video = self.app_state.working_dir / item
        else:
            self.app_state.selected_video = None
            return

        info_obj = self.info_cache.get(str(self.app_state.selected_video))
        if not info_obj:
            try:
                info_obj = video.info(self.app_state.selected_video)
                self.info_cache[str(self.app_state.selected_video)] = info_obj
            except (VideoProcessingError, FFmpegNotFoundError, VideoFileError) as e:
                if self.main_frame:
                    self.main_frame.SetStatusText(f"Error loading video info: {e}")
                wx.MessageBox(f"Error loading video information:\n\n{e}", 
                             "Video Processing Error", wx.OK | wx.ICON_ERROR)
                return
            except Exception as e:
                if self.main_frame:
                    self.main_frame.SetStatusText(f"Unexpected error: {e}")
                wx.MessageBox(f"Unexpected error loading video:\n\n{e}", 
                             "Unexpected Error", wx.OK | wx.ICON_ERROR)
                return

        if self.vid_info_panel and info_obj:
            self.vid_info_panel.update_info(info_obj)

    def OnChecked(self, event):
        """Handle video checkbox changes."""
        if self.app_state.working_dir:
            self.app_state.video_list = [
                str(self.app_state.working_dir / self.GetItemText(i, 0))
                for i in range(self.GetItemCount()) if self.IsItemChecked(i)
            ]
        else:
            self.app_state.video_list = []
        
        # Update the output preview in the reencode pane
        if self.main_frame and hasattr(self.main_frame, 'reencode_pane'):
            self.main_frame.reencode_pane.update_output_preview()

    def OnColumnClick(self, event):
        """Handle column header clicks to sort the list."""
        column = event.GetColumn()
        
        # Toggle sort direction if clicking the same column
        if self.sort_column == column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = column
            self.sort_ascending = True
        
        # Show sorting status
        column_names = ['Filename', 'Video Codec', 'Audio Codec', 'Resolution', 'File Size']
        direction = "ascending" if self.sort_ascending else "descending"
        if self.main_frame:
            self.main_frame.SetStatusText(f"Sorted by {column_names[column]} ({direction})")
        
        self.sort_items()

    def sort_items(self):
        """Sort the list items based on current sort column and direction."""
        if self.sort_column == -1 or self.GetItemCount() == 0:
            return
        
        # Store current check states and selection
        checked_items = set()
        selected_item = None
        
        for i in range(self.GetItemCount()):
            if self.IsItemChecked(i):
                checked_items.add(self.GetItemText(i, 0))
            if self.GetItemState(i, wx.LIST_STATE_SELECTED):
                selected_item = self.GetItemText(i, 0)
        
        # Collect all row data
        items = []
        for i in range(self.GetItemCount()):
            row_data = []
            for col in range(self.GetColumnCount()):
                row_data.append(self.GetItemText(i, col))
            items.append(row_data)
        
        # Sort based on the selected column
        def sort_key(item):
            value = item[self.sort_column]
            
            if self.sort_column == 0:  # Filename
                return value.lower()
            elif self.sort_column == 1 or self.sort_column == 2:  # Video/Audio codec
                return value.lower()
            elif self.sort_column == 3:  # Resolution
                if not value or value == "":
                    return (0, 0)
                try:
                    width, height = value.split('x')
                    return (int(width), int(height))
                except (ValueError, AttributeError):
                    return (0, 0)
            elif self.sort_column == 4:  # Size
                if not value or value == "":
                    return 0
                try:
                    # Extract numeric value and unit
                    parts = value.split()
                    if len(parts) == 2:
                        size_value = float(parts[0])
                        unit = parts[1].upper()
                        # Convert to bytes for comparison
                        if unit == 'KB':
                            return size_value * 1024
                        elif unit == 'MB':
                            return size_value * 1024 * 1024
                        elif unit == 'GB':
                            return size_value * 1024 * 1024 * 1024
                    return float(parts[0]) if parts else 0
                except (ValueError, IndexError):
                    return 0
            
            return value.lower()
        
        # Sort the items
        items.sort(key=sort_key, reverse=not self.sort_ascending)
        
        # Clear and repopulate the list
        self.DeleteAllItems()
        for i, row_data in enumerate(items):
            self.InsertItem(i, row_data[0])
            for col in range(1, len(row_data)):
                self.SetItem(i, col, row_data[col])
        
        # Restore check states and selection
        for i in range(self.GetItemCount()):
            filename = self.GetItemText(i, 0)
            if filename in checked_items:
                self.CheckItem(i, True)
            if filename == selected_item:
                self.SetItemState(i, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
        
        # Update the video list state
        self.OnChecked(None)

    def uncheck_video_by_path(self, video_path):
        """Uncheck a specific video by its absolute path."""
        try:
            print(f"Attempting to uncheck video: {video_path}")
            # Convert absolute path to relative path for comparison
            video_path = pathlib.Path(video_path)
            if self.app_state.working_dir:
                relative_path = str(video_path.relative_to(self.app_state.working_dir))
                print(f"Looking for relative path: {relative_path}")
                
                # Find the item in the list
                for i in range(self.GetItemCount()):
                    item_text = self.GetItemText(i, 0)
                    if item_text == relative_path:
                        print(f"Found matching item at index {i}: {item_text} - unchecking")
                        self.CheckItem(i, False)
                        # Update the video list to remove the unchecked item
                        self.OnChecked(None)
                        print(f"Video list after unchecking: {[pathlib.Path(v).name for v in self.app_state.video_list]}")
                        return
                
                print(f"Could not find item with relative path: {relative_path}")
                print(f"Available items: {[self.GetItemText(i, 0) for i in range(self.GetItemCount())]}")
        except (ValueError, TypeError) as e:
            print(f"Could not uncheck video {video_path}: {e}")

    def recheck_videos_by_paths(self, video_paths):
        """Re-check multiple videos by their absolute paths after a refresh."""
        try:
            print(f"recheck_videos_by_paths called with {len(video_paths) if video_paths else 0} paths")
            if not video_paths or not self.app_state.working_dir:
                print("No video paths or working directory, returning early")
                return
                
            # Convert all video paths to relative paths for comparison
            relative_paths = []
            for video_path in video_paths:
                try:
                    video_path = pathlib.Path(video_path)
                    relative_path = str(video_path.relative_to(self.app_state.working_dir))
                    relative_paths.append(relative_path)
                    print(f"Converted {video_path} to relative path: {relative_path}")
                except (ValueError, TypeError) as e:
                    print(f"Could not convert video path {video_path}: {e}")
                    continue
            
            print(f"Looking for {len(relative_paths)} relative paths in {self.GetItemCount()} list items")
            
            # Check items that match the relative paths
            checked_count = 0
            for i in range(self.GetItemCount()):
                item_text = self.GetItemText(i, 0)
                if item_text in relative_paths:
                    print(f"Re-checking item {i}: {item_text}")
                    self.CheckItem(i, True)
                    checked_count += 1
            
            print(f"Successfully re-checked {checked_count} videos")
            
            # Update the video list with newly checked items
            self.OnChecked(None)
            
        except Exception as e:
            print(f"Could not recheck videos: {e}")
            import traceback
            traceback.print_exc()

    def _insert_video_item(self, index, video_path, working_dir, info_cache):
        """Insert a single video item into the list at the specified index."""
        abs_path = str(video_path)
        rel_path = str(video_path.relative_to(working_dir))
        info_obj = info_cache.get(abs_path)

        video_codec = audio_codec = res = size_str = ""

        if info_obj:
            if info_obj.video_streams:
                video_codec = info_obj.video_streams[0].get("codec_name", "")

            if info_obj.audio_streams:
                audio_codec = info_obj.audio_streams[0].get("codec_name", "")

            res = f"{info_obj.max_width}x{info_obj.max_height}" if info_obj.max_width and info_obj.max_height else ""

            if info_obj.size_kb < 1024:
                size_str = f"{info_obj.size_kb:.2f} KB"
            elif info_obj.size_mb < 1024:
                size_str = f"{info_obj.size_mb:.2f} MB"
            else:
                size_str = f"{info_obj.size_gb:.2f} GB"
        else:
            # Mark files that failed to process
            video_codec = "ERROR"

        self.InsertItem(index, rel_path)
        self.SetItem(index, 1, video_codec)
        self.SetItem(index, 2, audio_codec)
        self.SetItem(index, 3, res)
        self.SetItem(index, 4, size_str)

    def _smart_update_list(self, expected_files, working_dir, info_cache):
        """Smart update that only adds/removes items that have changed."""
        # Store current check states before making changes
        checked_items = {}
        for i in range(self.GetItemCount()):
            rel_path = self.GetItemText(i, 0)
            abs_path = str(working_dir / rel_path)
            if self.IsItemChecked(i):
                checked_items[abs_path] = True

        # Get current items in the list
        current_items = {}
        for i in range(self.GetItemCount()):
            rel_path = self.GetItemText(i, 0)
            abs_path = str(working_dir / rel_path)
            current_items[abs_path] = i

        # Create sets for comparison
        expected_paths = {str(f) for f in expected_files}
        current_paths = set(current_items.keys())

        # Find items to remove (exist in current but not in expected)
        to_remove = current_paths - expected_paths
        # Find items to add (exist in expected but not in current)
        to_add = expected_paths - current_paths

        # Remove items in reverse order to maintain indices
        items_to_remove = [(current_items[path], path) for path in to_remove]
        items_to_remove.sort(reverse=True)
        
        for index, path in items_to_remove:
            self.DeleteItem(index)
            logger.debug(f"Removed item at index {index}: {pathlib.Path(path).name}")

        # Add new items
        for file_path in expected_files:
            abs_path = str(file_path)
            if abs_path in to_add:
                # Find the correct insertion position to maintain sorted order
                insert_index = self._find_insert_position(file_path, expected_files)
                self._insert_video_item(insert_index, file_path, working_dir, info_cache)
                logger.debug(f"Added item at index {insert_index}: {file_path.name}")

        # Apply current sorting if any
        if self.sort_column != -1:
            self.sort_items()
        
        # Restore check states for items that still exist
        for i in range(self.GetItemCount()):
            rel_path = self.GetItemText(i, 0)
            abs_path = str(working_dir / rel_path)
            if abs_path in checked_items:
                self.CheckItem(i, True)

        # Update the video list to reflect current checked state
        self.OnChecked(None)

    def _find_insert_position(self, new_file, expected_files):
        """Find the correct position to insert a new file to maintain sorted order."""
        expected_list = list(expected_files)
        new_file_index = expected_list.index(new_file)
        
        # Count how many files before this one are already in the list
        files_before = 0
        for i in range(new_file_index):
            file_to_check = expected_list[i]
            rel_path = str(file_to_check.relative_to(self.app_state.working_dir))
            # Check if this file is already in the list
            for list_index in range(self.GetItemCount()):
                if self.GetItemText(list_index, 0) == rel_path:
                    files_before += 1
                    break
        
        return files_before

    def _update_video_list_for_existing_files(self, expected_files):
        """Update the app_state.video_list to only include files that still exist."""
        if not self.app_state.video_list:
            return
            
        expected_paths = {str(f) for f in expected_files}
        # Filter video_list to only include files that still exist
        self.app_state.video_list = [
            video_path for video_path in self.app_state.video_list 
            if video_path in expected_paths
        ]

    def clear_error_cache(self):
        """Clear the cache of files that previously failed processing."""
        self.error_files.clear()
        if self.main_frame:
            self.main_frame.SetStatusText("Error file cache cleared - failed files will be retried on next refresh")
    
    def force_refresh_all(self):
        """Force a complete refresh that re-processes all files, including previously failed ones."""
        self.info_cache.clear()
        self.error_files.clear()
        self.refresh(force_full_refresh=True)
        if self.main_frame:
            self.main_frame.SetStatusText("Forcing complete refresh - all files will be re-processed")

    def refresh(self, completion_callback=None, force_full_refresh=False):
        """Refresh the video list by scanning the working directory.
        
        Args:
            completion_callback: Function to call when refresh is complete
            force_full_refresh: If True, delete all items and rebuild from scratch
        """
        if not self.app_state.working_dir:
            if completion_callback:
                wx.CallAfter(completion_callback)
            return

        # Check if working directory has changed - if so, force full refresh
        current_wd = self.app_state.working_dir
        if not hasattr(self, '_last_working_dir') or self._last_working_dir != current_wd:
            force_full_refresh = True
            self._last_working_dir = current_wd

        if force_full_refresh:
            self.app_state.video_list = []
            self.DeleteAllItems()

        wd = self.app_state.working_dir  # capture current working_dir for thread safety
        def scan_and_update():
            files = []
            # Preserve existing cache and only update for new/changed files
            info_cache = self.info_cache.copy()
            errors = []
            new_errors = []  # Track only new errors for this refresh
            
            try:
                # Check FFmpeg availability once at the start
                video.check_ffmpeg_availability()
            except FFmpegNotFoundError as e:
                wx.CallAfter(lambda: wx.MessageBox(f"FFmpeg Error:\n\n{e}", 
                                                  "FFmpeg Not Found", wx.OK | wx.ICON_ERROR))
                return
            
            # Get current list of files that should be displayed
            expected_files = []
            for p in sorted(self.get_video_files_with_depth(wd)):
                if p.suffix in VIDEO_EXTENSIONS:
                    abs_path = str(p.resolve())
                    expected_files.append(p.resolve())
                    
                    # Only process files that aren't already in cache
                    if abs_path not in info_cache:
                        # Skip files that previously failed unless forced to retry
                        if abs_path in self.error_files:
                            # File previously failed, mark as error but don't retry
                            errors.append(f"{p.name}: Previously failed processing")
                            continue
                            
                        try:
                            info_cache[abs_path] = video.info(abs_path)
                        except (VideoProcessingError, VideoFileError) as e:
                            error_msg = f"{p.name}: {e}"
                            errors.append(error_msg)
                            new_errors.append(error_msg)
                            self.error_files.add(abs_path)  # Remember this file failed
                            logger.warning(f"Failed to get info for {abs_path}: {e}")
                        except Exception as e:
                            error_msg = f"{p.name}: Unexpected error - {e}"
                            errors.append(error_msg)
                            new_errors.append(error_msg)
                            self.error_files.add(abs_path)  # Remember this file failed
                            logger.error(f"Unexpected error processing {abs_path}: {e}")

            files = expected_files

            def update_ui():
                if self.app_state.working_dir != wd:
                    return

                if force_full_refresh:
                    # Full refresh - rebuild everything
                    self.DeleteAllItems()
                    for i, v in enumerate(files):
                        self._insert_video_item(i, v, wd, info_cache)
                    
                    # Apply current sorting if any
                    if self.sort_column != -1:
                        self.sort_items()
                else:
                    # Smart refresh - compare current list with expected files
                    self._smart_update_list(files, wd, info_cache)

                self.info_cache = info_cache
                
                # Only clear video_list if we're doing a full refresh
                if force_full_refresh:
                    self.app_state.video_list = []
                else:
                    # Update video_list to remove any files that no longer exist
                    self._update_video_list_for_existing_files(files)
                
                # Show error summary only for NEW errors in this refresh
                if new_errors and self.main_frame:
                    error_count = len(new_errors)
                    total_error_count = len(errors)
                    
                    if total_error_count > len(new_errors):
                        status_msg = f"Loaded {len(files)} files ({error_count} new errors, {total_error_count} total errors)"
                    else:
                        status_msg = f"Loaded {len(files)} files ({error_count} errors)"
                    self.main_frame.SetStatusText(status_msg)
                    
                    if error_count <= 5:  # Show details for few errors
                        error_msg = f"New errors processing {error_count} files:\n\n" + "\n".join(new_errors)
                    else:  # Summarize for many errors
                        error_msg = f"New errors processing {error_count} files. First 5:\n\n" + "\n".join(new_errors[:5]) + f"\n\n... and {error_count - 5} more"
                    
                    wx.CallAfter(lambda: wx.MessageBox(error_msg, "Video Processing Errors", wx.OK | wx.ICON_WARNING))
                elif errors and not new_errors and self.main_frame:
                    # Only old errors, just update status
                    error_count = len(errors)
                    status_msg = f"Loaded {len(files)} files ({error_count} known errors)"
                    self.main_frame.SetStatusText(status_msg)

                # Call the completion callback if provided
                if completion_callback:
                    wx.CallAfter(completion_callback)

            wx.CallAfter(update_ui)
        threading.Thread(target=scan_and_update, daemon=True).start()
