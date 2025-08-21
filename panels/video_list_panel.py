#!/usr/bin/env python

import wx
import pathlib
import threading
import re
import os
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
        ('Rename Preview', 400),  # Moved to second position, hidden by default
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
        
        # Filtering state
        self.filter_pattern = ""  # Current filter pattern
        self.compiled_filter = None  # Compiled regex pattern
        self.all_items = []  # Store all items (including filtered out ones)
        self.use_regex = True  # Whether to treat filter as regex
        
        # Rename mode state
        self.rename_mode = False  # Whether rename mode is active
        self.rename_pattern = ""  # Current rename pattern
        self.replace_pattern = ""  # Current replace pattern
        self.case_sensitive = False  # Case sensitive rename
        self.rename_preview_cache = {}  # Cache for rename previews

        for idx, (label, width) in enumerate(self.COLS):
            self.InsertColumn(idx, label)
            if idx == 1 and not self.rename_mode:  # Hide rename preview column (index 1) initially
                self.SetColumnWidth(idx, 0)
            else:
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
        elif self.main_frame and hasattr(self.main_frame, 'show_video_info') and info_obj:
            self.main_frame.show_video_info(info_obj)

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
        
        # Update the select all checkbox state
        if self.main_frame and hasattr(self.main_frame, 'UpdateSelectAllCheckbox'):
            self.main_frame.UpdateSelectAllCheckbox()

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
            elif self.sort_column == 1:  # Rename Preview
                return value.lower()
            elif self.sort_column == 2 or self.sort_column == 3:  # Video/Audio codec (now columns 2,3)
                return value.lower()
            elif self.sort_column == 4:  # Resolution (now column 4)
                if not value or value == "":
                    return (0, 0)
                try:
                    width, height = value.split('x')
                    return (int(width), int(height))
                except (ValueError, AttributeError):
                    return (0, 0)
            elif self.sort_column == 5:  # Size (now column 5)
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

    def set_filter(self, pattern: str, use_regex: bool = True):
        """Set the filter pattern and apply it to the list.
        
        Args:
            pattern: Filter pattern (regex or plain text)
            use_regex: Whether to treat pattern as regex (default: True)
        """
        self.filter_pattern = pattern
        self.use_regex = use_regex
        
        # Compile regex pattern if using regex mode
        if self.use_regex and pattern:
            try:
                self.compiled_filter = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                # Invalid regex - fall back to plain text search
                self.compiled_filter = None
                if self.main_frame:
                    self.main_frame.SetStatusText(f"Invalid regex: {e}")
        else:
            self.compiled_filter = None
        
        self.apply_filter()

    def apply_filter(self):
        """Apply the current filter to the video list."""
        if not self.filter_pattern:
            # No filter - show all items
            self._show_all_items()
            return
        
        # Store current check states and selection
        checked_items = set()
        selected_item = None
        
        for i in range(self.GetItemCount()):
            if self.IsItemChecked(i):
                checked_items.add(self.GetItemText(i, 0))
            if self.GetItemState(i, wx.LIST_STATE_SELECTED):
                selected_item = self.GetItemText(i, 0)
        
        # Store all current items if not already stored
        if not self.all_items:
            self._store_all_items()
        
        # Filter items
        filtered_items = []
        for item_data in self.all_items:
            if self._item_matches_filter(item_data):
                filtered_items.append(item_data)
        
        # Update the list with filtered items
        self.DeleteAllItems()
        for i, item_data in enumerate(filtered_items):
            self.InsertItem(i, item_data[0])
            for col in range(1, len(item_data)):
                if col < len(item_data):
                    self.SetItem(i, col, item_data[col])
        
        # Apply current sorting if any
        if self.sort_column != -1:
            self.sort_items()
        
        # Restore check states and selection for visible items
        for i in range(self.GetItemCount()):
            filename = self.GetItemText(i, 0)
            if filename in checked_items:
                self.CheckItem(i, True)
            if filename == selected_item:
                self.SetItemState(i, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
        
        # Update status
        total_items = len(self.all_items)
        visible_items = self.GetItemCount()
        if self.main_frame:
            if visible_items == total_items:
                self.main_frame.SetStatusText(f"Showing all {total_items} videos")
            else:
                self.main_frame.SetStatusText(f"Showing {visible_items} of {total_items} videos (filtered)")
        
        # Update the video list state
        self.OnChecked(None)

    def _item_matches_filter(self, item_data):
        """Check if an item matches the current filter."""
        if not self.filter_pattern:
            return True
        
        # Search across all columns
        search_text = " ".join(str(col) for col in item_data).lower()
        
        if self.use_regex and self.compiled_filter:
            return bool(self.compiled_filter.search(search_text))
        else:
            # Plain text search (case-insensitive)
            return self.filter_pattern.lower() in search_text

    def _store_all_items(self):
        """Store all current items for filtering."""
        self.all_items = []
        for i in range(self.GetItemCount()):
            item_data = []
            for col in range(self.GetColumnCount()):
                item_data.append(self.GetItemText(i, col))
            self.all_items.append(item_data)

    def _show_all_items(self):
        """Show all items (clear filter)."""
        if not self.all_items:
            return  # Nothing to restore
        
        # Store current check states and selection
        checked_items = set()
        selected_item = None
        
        for i in range(self.GetItemCount()):
            if self.IsItemChecked(i):
                checked_items.add(self.GetItemText(i, 0))
            if self.GetItemState(i, wx.LIST_STATE_SELECTED):
                selected_item = self.GetItemText(i, 0)
        
        # Restore all items
        self.DeleteAllItems()
        for i, item_data in enumerate(self.all_items):
            self.InsertItem(i, item_data[0])
            for col in range(1, len(item_data)):
                if col < len(item_data):
                    self.SetItem(i, col, item_data[col])
        
        # Apply current sorting if any
        if self.sort_column != -1:
            self.sort_items()
        
        # Restore check states and selection
        for i in range(self.GetItemCount()):
            filename = self.GetItemText(i, 0)
            if filename in checked_items:
                self.CheckItem(i, True)
            if filename == selected_item:
                self.SetItemState(i, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
        
        # Update status
        if self.main_frame:
            self.main_frame.SetStatusText(f"Showing all {self.GetItemCount()} videos")
        
        # Update the video list state
        self.OnChecked(None)

    def clear_filter(self):
        """Clear the current filter and show all items."""
        self.filter_pattern = ""
        self.compiled_filter = None
        self._show_all_items()

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
        # Column 1 is now Rename Preview (will be empty initially)
        self.SetItem(index, 1, "")  # Rename Preview - empty by default
        self.SetItem(index, 2, video_codec)  # Video codec moved to column 2
        self.SetItem(index, 3, audio_codec)  # Audio codec moved to column 3  
        self.SetItem(index, 4, res)          # Resolution moved to column 4
        self.SetItem(index, 5, size_str)     # Size moved to column 5

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
        
        # Update stored items for filtering
        self._store_all_items()
        
        # Re-apply current filter if any
        if self.filter_pattern:
            self.apply_filter()
        
        # Restore check states for items that still exist (done after filtering)
        if not self.filter_pattern:  # Only if not filtering
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
                    
                    # Store all items for filtering
                    self._store_all_items()
                    
                    # Apply current filter if any
                    if self.filter_pattern:
                        self.apply_filter()
                    elif self.sort_column != -1:
                        # Apply current sorting if any and no filter
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

    def set_rename_mode(self, enabled, rename_pattern="", replace_pattern="", case_sensitive=False):
        """Enable or disable rename mode and update the preview column."""
        print(f"DEBUG: set_rename_mode called - enabled={enabled}, pattern='{rename_pattern}', replace='{replace_pattern}', case={case_sensitive}")
        
        self.rename_mode = enabled
        self.rename_pattern = rename_pattern
        self.replace_pattern = replace_pattern
        self.case_sensitive = case_sensitive
        
        # Show/hide the rename preview column (index 1)
        preview_col_idx = 1
        print(f"DEBUG: Preview column index: {preview_col_idx}")
        if enabled:
            print(f"DEBUG: Showing preview column with width {self.COLS[preview_col_idx][1]}")
            self.SetColumnWidth(preview_col_idx, self.COLS[preview_col_idx][1])  # Show with default width
            # Always update previews when patterns change, even if mode was already enabled
            self.update_rename_previews()
        else:
            self.SetColumnWidth(preview_col_idx, 0)  # Hide column
            self.rename_preview_cache.clear()
    
    def update_rename_patterns(self, rename_pattern, replace_pattern, case_sensitive):
        """Update rename patterns and refresh previews without changing column visibility."""
        print(f"DEBUG: update_rename_patterns called - pattern='{rename_pattern}', replace='{replace_pattern}', case={case_sensitive}")
        self.rename_pattern = rename_pattern
        self.replace_pattern = replace_pattern
        self.case_sensitive = case_sensitive
        if self.rename_mode:
            print("DEBUG: Rename mode is enabled, calling update_rename_previews")
            self.update_rename_previews()
        else:
            print("DEBUG: Rename mode is disabled")
    
    def update_rename_previews(self):
        """Update the rename preview column for all visible items."""
        print(f"DEBUG: update_rename_previews called - mode={self.rename_mode}, pattern='{self.rename_pattern}', replace='{self.replace_pattern}'")
        print(f"DEBUG: Item count: {self.GetItemCount()}")
        
        if not self.rename_mode:
            # Clear all preview values if rename mode is disabled, but only if they're not already empty
            for i in range(self.GetItemCount()):
                current_preview = self.GetItemText(i, 1)  # Column 1 is rename preview
                if current_preview:  # Only update if not already empty
                    self.SetItem(i, 1, "")
            return
            
        # If no pattern is provided, clear previews only if they're not already empty
        if not self.rename_pattern:
            print("DEBUG: No rename pattern, clearing previews")
            for i in range(self.GetItemCount()):
                current_preview = self.GetItemText(i, 1)  # Column 1 is rename preview
                if current_preview:  # Only update if not already empty
                    print(f"DEBUG: Clearing preview for item {i}")
                    self.SetItem(i, 1, "")
            return
        
        # Compile regex
        try:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            regex = re.compile(self.rename_pattern, flags)
        except re.error:
            # Show error in all preview cells, but only if they don't already show the error
            for i in range(self.GetItemCount()):
                current_preview = self.GetItemText(i, 1)  # Column 1 is rename preview
                if current_preview != "ERROR: Invalid regex":
                    self.SetItem(i, 1, "ERROR: Invalid regex")
            return
        
        # Update preview for each visible item
        for i in range(self.GetItemCount()):
            original_name = self.GetItemText(i, 0)
            print(f"DEBUG: Processing item {i}: '{original_name}'")
            
            try:
                # Apply regex substitution
                new_name = regex.sub(self.replace_pattern, original_name)
                
                # Check if name changed and validate
                if new_name == original_name:
                    preview = "No change"
                elif not new_name or new_name.isspace():
                    preview = "ERROR: Empty name"
                else:
                    # Split path to validate only the filename part, not the directory path
                    directory_part = os.path.dirname(new_name)
                    filename_part = os.path.basename(new_name)
                    
                    # Check for invalid characters only in the filename part
                    if any(char in filename_part for char in '<>:"/\\|?*'):
                        preview = "ERROR: Invalid characters"
                    elif not filename_part or filename_part.isspace():
                        preview = "ERROR: Empty filename"
                    else:
                        # Check if file would exist
                        if self.app_state.working_dir:
                            new_path = self.app_state.working_dir / new_name
                            old_path = self.app_state.working_dir / original_name
                            if new_path.exists() and new_path != old_path:
                                preview = f"WARNING: {new_name}"
                            else:
                                preview = new_name
                        else:
                            preview = new_name
                
                print(f"DEBUG: Final preview text: '{preview}'")
                # Only update if the preview text actually changed
                current_preview = self.GetItemText(i, 1)  # Column 1 is rename preview
                if current_preview != preview:
                    print(f"DEBUG: Setting preview for item {i} from '{current_preview}' to '{preview}'")
                    self.SetItem(i, 1, preview)
                else:
                    print(f"DEBUG: Preview unchanged for item {i}: '{current_preview}'")
                
            except Exception as e:
                error_text = f"ERROR: {str(e)[:30]}"
                current_preview = self.GetItemText(i, 1)  # Column 1 is rename preview
                if current_preview != error_text:
                    self.SetItem(i, 1, error_text)

    def apply_renames(self):
        """Apply the rename operations based on current preview."""
        if not self.rename_mode or not self.rename_pattern:
            return 0, []
        
        success_count = 0
        errors = []
        
        for i in range(self.GetItemCount()):
            original_name = self.GetItemText(i, 0)
            preview = self.GetItemText(i, 1)  # Rename Preview is column 1
            
            # Skip if no change or error
            if preview in ["No change", ""] or preview.startswith("ERROR:"):
                continue
                
            # Handle warnings (extract new name)
            if preview.startswith("WARNING: "):
                new_name = preview[9:]  # Remove "WARNING: " prefix
            else:
                new_name = preview
            
            # Perform the rename
            if self.app_state.working_dir:
                try:
                    old_path = self.app_state.working_dir / original_name
                    new_path = self.app_state.working_dir / new_name
                    
                    # Only rename if actually different
                    if old_path != new_path:
                        # Check if target already exists (should have been caught earlier)
                        if new_path.exists():
                            # This is an overwrite - log it but proceed since user confirmed
                            logger.warning(f"Overwriting existing file: {new_name}")
                        
                        old_path.rename(new_path)
                        success_count += 1
                        logger.info(f"Renamed: {original_name} → {new_name}")
                        
                except Exception as e:
                    error_msg = f"{original_name}: {e}"
                    errors.append(error_msg)
                    logger.error(f"Rename failed: {error_msg}")
        
        return success_count, errors


class VideoListPanel(wx.Panel):
    """Panel containing a filter text box and the video list."""
    
    def __init__(self, parent, app_state: "AppState", main_frame=None, vid_info_panel=None, 
                 select_all_checkbox=None, select_options_button=None, menu_button=None):
        super().__init__(parent)
        self.app_state = app_state
        self.main_frame = main_frame
        
        # Reparent the controls to this panel if provided
        if select_all_checkbox:
            select_all_checkbox.Reparent(self)
            self.select_all_checkbox = select_all_checkbox
        else:
            self.select_all_checkbox = None
            
        if select_options_button:
            select_options_button.Reparent(self)
            self.select_options_button = select_options_button
        else:
            self.select_options_button = None
            
        if menu_button:
            menu_button.Reparent(self)
            self.menu_button = menu_button
            self.menu_button.Bind(wx.EVT_BUTTON, self.OnMenuButton)
        else:
            self.menu_button = None
        
        # Create the main sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create filter controls
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Add selection controls to the far left if provided
        if self.select_all_checkbox:
            filter_sizer.Add(self.select_all_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        if self.select_options_button:
            filter_sizer.Add(self.select_options_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL | wx.FIXED_MINSIZE, 5)
        
        # Add a separator if we have selection controls
        if self.select_all_checkbox or self.select_options_button:
            separator = wx.StaticLine(self, style=wx.LI_VERTICAL)
            filter_sizer.Add(separator, 0, wx.EXPAND | wx.ALL, 5)
        
        filter_label = wx.StaticText(self, label="Filter:")
        self.filter_text = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.filter_text.SetToolTip("Filter videos by filename, codec, resolution, or size. Supports regular expressions.")
        
        self.regex_checkbox = wx.CheckBox(self, label="Regex")
        self.regex_checkbox.SetValue(True)
        self.regex_checkbox.SetToolTip("Enable regular expression filtering")
        
        self.clear_filter_btn = wx.Button(self, label="Clear")
        self.clear_filter_btn.SetSize(wx.Size(60, -1))
        
        filter_sizer.Add(filter_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        filter_sizer.Add(self.filter_text, 1, wx.EXPAND | wx.ALL, 5)
        filter_sizer.Add(self.regex_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        filter_sizer.Add(self.clear_filter_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        # Add menu button to the far right if provided
        if self.menu_button:
            filter_sizer.Add(self.menu_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL | wx.FIXED_MINSIZE, 5)
        
        # Create rename bar (initially hidden)
        self.rename_bar = wx.Panel(self)
        rename_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        rename_label = wx.StaticText(self.rename_bar, label="Find:")
        self.rename_find_text = wx.TextCtrl(self.rename_bar, style=wx.TE_PROCESS_ENTER)
        self.rename_find_text.SetToolTip("Regular expression pattern to find in filenames")
        
        replace_label = wx.StaticText(self.rename_bar, label="Replace:")
        self.rename_replace_text = wx.TextCtrl(self.rename_bar, style=wx.TE_PROCESS_ENTER)
        self.rename_replace_text.SetToolTip("Replacement text (use \\1, \\2, etc. for capture groups)")
        
        self.rename_case_cb = wx.CheckBox(self.rename_bar, label="Case sensitive")
        
        self.rename_apply_btn = wx.Button(self.rename_bar, label="Apply Rename")
        self.rename_cancel_btn = wx.Button(self.rename_bar, label="Cancel")
        
        rename_sizer.Add(rename_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        rename_sizer.Add(self.rename_find_text, 1, wx.EXPAND | wx.ALL, 5)
        rename_sizer.Add(replace_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        rename_sizer.Add(self.rename_replace_text, 1, wx.EXPAND | wx.ALL, 5)
        rename_sizer.Add(self.rename_case_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        rename_sizer.Add(self.rename_apply_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        rename_sizer.Add(self.rename_cancel_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        self.rename_bar.SetSizer(rename_sizer)
        self.rename_bar.Hide()  # Initially hidden
        
        # Create the video list
        self.video_list = VideoList(self, app_state, main_frame, vid_info_panel)
        
        # Add to main sizer
        sizer.Add(filter_sizer, 0, wx.EXPAND)
        sizer.Add(self.rename_bar, 0, wx.EXPAND)
        sizer.Add(self.video_list, 1, wx.EXPAND)
        
        self.SetSizer(sizer)
        
        # Bind events for filter controls
        self.filter_text.Bind(wx.EVT_TEXT, self.OnFilterText)
        self.filter_text.Bind(wx.EVT_TEXT_ENTER, self.OnFilterEnter)
        self.regex_checkbox.Bind(wx.EVT_CHECKBOX, self.OnRegexToggle)
        self.clear_filter_btn.Bind(wx.EVT_BUTTON, self.OnClearFilter)
        
                # Bind events for rename controls
        self.rename_find_text.Bind(wx.EVT_TEXT, self.OnRenameTextChange)
        self.rename_find_text.Bind(wx.EVT_TEXT_ENTER, self.OnRenameTextChange)
        self.rename_find_text.Bind(wx.EVT_KILL_FOCUS, self.OnRenameTextChange)  # Try focus events too
        self.rename_replace_text.Bind(wx.EVT_TEXT, self.OnRenameTextChange)
        self.rename_replace_text.Bind(wx.EVT_TEXT_ENTER, self.OnRenameTextChange)
        self.rename_replace_text.Bind(wx.EVT_KILL_FOCUS, self.OnRenameTextChange)  # Try focus events too
        self.rename_case_cb.Bind(wx.EVT_CHECKBOX, self.OnRenameTextChange)
        self.rename_apply_btn.Bind(wx.EVT_BUTTON, self.OnApplyRename)
        self.rename_cancel_btn.Bind(wx.EVT_BUTTON, self.OnCancelRename)
        
        # Timer for live filtering (to avoid filtering on every keystroke)
        self.filter_timer = None
        
        # Timer for rename preview updates
        self.rename_timer = None
        
        # Timer for live filtering (to avoid filtering on every keystroke)
        self.filter_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnFilterTimer)
    
    def OnFilterText(self, event):
        """Handle text changes in the filter box."""
        # Use a timer to debounce rapid typing
        self.filter_timer.Stop()
        self.filter_timer.Start(300, wx.TIMER_ONE_SHOT)  # 300ms delay
    
    def OnFilterEnter(self, event):
        """Handle Enter key in filter text box."""
        self.filter_timer.Stop()
        self.ApplyFilter()
    
    def OnFilterTimer(self, event):
        """Handle the timer event for debounced filtering."""
        self.ApplyFilter()
    
    def OnRegexToggle(self, event):
        """Handle regex checkbox toggle."""
        self.ApplyFilter()
    
    def OnClearFilter(self, event):
        """Handle clear filter button."""
        self.filter_text.SetValue("")
        self.ApplyFilter()
    
    def OnMenuButton(self, event):
        """Handle menu button click - show operations menu."""
        if not self.menu_button:
            return
            
        menu = wx.Menu()
        
        # Add Play menu item
        play_item = menu.Append(wx.ID_ANY, "Play Selection...", "Play selected videos with ffplay")
        
        # Add separator
        menu.AppendSeparator()
        
        # Add inline rename toggle
        if hasattr(self, 'rename_bar') and self.rename_bar.IsShown():
            rename_toggle_item = menu.Append(wx.ID_ANY, "Hide Inline Rename", "Hide the inline rename bar")
        else:
            rename_toggle_item = menu.Append(wx.ID_ANY, "Show Inline Rename", "Show the inline rename bar")
        
        # Add separator
        menu.AppendSeparator()
        
        # Add batch operation menu items
        batch_rename_item = menu.Append(wx.ID_ANY, "Batch Rename Dialog...", "Open batch rename dialog")
        move_subfolder_item = menu.Append(wx.ID_ANY, "Move to Subfolder...", "Move selected videos to a subfolder")
        
        # Add separator for destructive operations
        menu.AppendSeparator()
        
        # Add delete option
        delete_item = menu.Append(wx.ID_ANY, "Delete Selected Files...", "Delete selected video files permanently")
        
        # Bind menu events
        self.Bind(wx.EVT_MENU, self.OnPlay, play_item)
        self.Bind(wx.EVT_MENU, self.OnToggleInlineRename, rename_toggle_item)
        self.Bind(wx.EVT_MENU, self.OnBatchRename, batch_rename_item)
        self.Bind(wx.EVT_MENU, self.OnMoveToSubfolder, move_subfolder_item)
        self.Bind(wx.EVT_MENU, self.OnDeleteSelected, delete_item)
        
        # Show menu at the menu button position
        menu_position = self.menu_button.GetPosition()
        menu_position.y += self.menu_button.GetSize().height
        self.PopupMenu(menu, menu_position)
        menu.Destroy()
    
    def OnToggleInlineRename(self, event):
        """Toggle the inline rename bar visibility."""
        if hasattr(self, 'rename_bar'):
            if self.rename_bar.IsShown():
                self.hide_inline_rename()
            else:
                self.show_inline_rename()
    
    def show_inline_rename(self):
        """Show the inline rename bar and enable rename mode."""
        if hasattr(self, 'rename_bar'):
            self.rename_bar.Show()
            # Enable rename mode with current field values
            find_pattern = self.rename_find_text.GetValue()
            replace_pattern = self.rename_replace_text.GetValue()
            case_sensitive = self.rename_case_cb.GetValue()
            self.video_list.set_rename_mode(True, find_pattern, replace_pattern, case_sensitive)
            
            # Start a periodic timer to monitor text changes
            self.start_rename_monitoring()
            
            self.Layout()
    
    def hide_inline_rename(self):
        """Hide the inline rename bar and disable rename mode."""
        if hasattr(self, 'rename_bar'):
            self.rename_bar.Hide()
            self.video_list.set_rename_mode(False)
            
            # Stop monitoring timer
            self.stop_rename_monitoring()
            
            self.Layout()
    
    def start_rename_monitoring(self):
        """Start monitoring text changes with a periodic timer."""
        print("DEBUG: start_rename_monitoring called")
        # Stop any existing monitoring
        self.stop_rename_monitoring()
        
        # Use CallLater approach instead of wx.Timer for better reliability
        self.rename_monitoring_active = True
        
        # Store current values
        self.last_find_pattern = self.rename_find_text.GetValue()
        self.last_replace_pattern = self.rename_replace_text.GetValue()
        self.last_case_sensitive = self.rename_case_cb.GetValue()
        print(f"DEBUG: Initial values - find='{self.last_find_pattern}', replace='{self.last_replace_pattern}', case={self.last_case_sensitive}")
        
        # Start the monitoring loop
        self.schedule_rename_check()
    
    def schedule_rename_check(self):
        """Schedule the next rename field check."""
        if hasattr(self, 'rename_monitoring_active') and self.rename_monitoring_active:
            wx.CallLater(500, self.check_rename_changes)
    
    def check_rename_changes(self):
        """Check if rename fields have changed and update preview if needed."""
        print("DEBUG: check_rename_changes called")
        
        # Check if monitoring should continue
        if not hasattr(self, 'rename_monitoring_active') or not self.rename_monitoring_active:
            print("DEBUG: Monitoring not active, stopping")
            return
            
        if not hasattr(self, 'rename_bar') or not self.rename_bar.IsShown():
            print("DEBUG: Rename bar not shown, stopping monitoring")
            self.stop_rename_monitoring()
            return
        
        # Get current values
        current_find = self.rename_find_text.GetValue()
        current_replace = self.rename_replace_text.GetValue()
        current_case = self.rename_case_cb.GetValue()
        print(f"DEBUG: Current values - find='{current_find}', replace='{current_replace}', case={current_case}")
        
        # Check if anything changed
        if (current_find != self.last_find_pattern or 
            current_replace != self.last_replace_pattern or 
            current_case != self.last_case_sensitive):
            
            print("DEBUG: Change detected, updating patterns")
            # Update stored values
            self.last_find_pattern = current_find
            self.last_replace_pattern = current_replace
            self.last_case_sensitive = current_case
            
            # Update patterns and preview
            self.video_list.update_rename_patterns(current_find, current_replace, current_case)
        else:
            print("DEBUG: No changes detected")
        
        # Schedule next check
        self.schedule_rename_check()
    
    def stop_rename_monitoring(self):
        """Stop the rename monitoring."""
        print("DEBUG: stop_rename_monitoring called")
        self.rename_monitoring_active = False
        # Clean up old timer if it exists
        if hasattr(self, 'rename_monitor_timer') and self.rename_monitor_timer:
            print("DEBUG: Stopping old timer")
            self.rename_monitor_timer.Stop()
            self.rename_monitor_timer = None
        else:
            print("DEBUG: No old timer to stop")
    
    def OnRenameTextChange(self, event):
        """Handle changes in rename text fields (legacy method for compatibility)."""
        # This method is kept for compatibility but the CallLater monitoring approach is used instead
        pass
    
    def OnRenameTimerExpired(self, event):
        """Handle timer expiration and update rename preview (legacy method)."""
        # This method is kept for compatibility but not used with new CallLater approach
        pass
    
    def update_rename_preview(self):
        """Update the rename preview based on current input."""
        if not hasattr(self, 'rename_bar') or not self.rename_bar.IsShown():
            return
            
        find_pattern = self.rename_find_text.GetValue()
        replace_pattern = self.rename_replace_text.GetValue()
        case_sensitive = self.rename_case_cb.GetValue()
        
        # Debug print to verify this method is being called with correct values
        print(f"DEBUG: update_rename_preview - find='{find_pattern}', replace='{replace_pattern}', case={case_sensitive}")
        
        self.video_list.set_rename_mode(True, find_pattern, replace_pattern, case_sensitive)
    
    def OnApplyRename(self, event):
        """Apply the rename operations."""
        # Count valid operations and check for overwrites
        valid_count = 0
        warning_count = 0
        overwrite_conflicts = []
        
        for i in range(self.video_list.GetItemCount()):
            original_name = self.video_list.GetItemText(i, 0)
            preview = self.video_list.GetItemText(i, 1)  # Rename Preview is now column 1
            
            if preview and not preview.startswith("ERROR:") and preview != "No change":
                # Extract the new name (handle warnings)
                if preview.startswith("WARNING: "):
                    new_name = preview[9:]  # Remove "WARNING: " prefix
                    warning_count += 1
                else:
                    new_name = preview
                    valid_count += 1
                
                # Check for potential overwrites
                if self.app_state.working_dir:
                    old_path = self.app_state.working_dir / original_name
                    new_path = self.app_state.working_dir / new_name
                    
                    # Only check if it's actually a different file
                    if old_path != new_path and new_path.exists():
                        overwrite_conflicts.append(f"{original_name} → {new_name}")
        
        if valid_count == 0 and warning_count == 0:
            wx.MessageBox("No valid rename operations to apply.", "Nothing to Do", 
                         wx.OK | wx.ICON_INFORMATION)
            return
        
        # Check for overwrite conflicts
        if overwrite_conflicts:
            conflict_msg = f"The following {len(overwrite_conflicts)} rename(s) would overwrite existing files:\n\n"
            conflict_msg += "\n".join(overwrite_conflicts[:10])  # Show first 10
            if len(overwrite_conflicts) > 10:
                conflict_msg += f"\n... and {len(overwrite_conflicts) - 10} more"
            conflict_msg += "\n\nDo you want to proceed anyway?"
            
            if wx.MessageBox(conflict_msg, "Overwrite Warning", 
                           wx.YES_NO | wx.ICON_WARNING) != wx.YES:
                return
        
        # Confirm operation
        msg = f"Apply {valid_count} rename operations"
        if warning_count > 0:
            msg += f" and {warning_count} operations with warnings"
        msg += "?"
        
        if wx.MessageBox(msg, "Confirm Inline Rename", 
                        wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        
        # Apply the renames
        success_count, errors = self.video_list.apply_renames()
        
        # Show results
        if not errors:
            wx.MessageBox(f"Successfully renamed {success_count} files.", 
                         "Rename Complete", wx.OK | wx.ICON_INFORMATION)
        else:
            error_summary = f"Renamed {success_count} files successfully.\n{len(errors)} operations failed:\n\n"
            error_summary += "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                error_summary += f"\n... and {len(errors) - 5} more errors"
            
            wx.MessageBox(error_summary, "Rename Completed with Errors", 
                         wx.OK | wx.ICON_WARNING)
        
        # Refresh the list to show new names
        if success_count > 0:
            self.refresh()
        
        # Hide the rename bar after successful operation
        self.hide_inline_rename()
    
    def OnCancelRename(self, event):
        """Cancel rename mode and hide the rename bar."""
        self.hide_inline_rename()

    def OnBatchRename(self, event):
        """Handle batch rename menu item - delegate to main frame."""
        if self.main_frame:
            self.main_frame.OnBatchRename(event)
    
    def OnMoveToSubfolder(self, event):
        """Handle move to subfolder menu item - delegate to main frame."""
        if self.main_frame:
            self.main_frame.OnMoveToSubfolder(event)
    
    def OnPlay(self, event):
        """Handle play menu item - delegate to main frame."""
        if self.main_frame:
            self.main_frame.OnPlay(event)
    
    def OnDeleteSelected(self, event):
        """Handle delete selected files menu item."""
        # Get selected files
        selected_files = []
        for i in range(self.video_list.GetItemCount()):
            if self.video_list.IsItemChecked(i):
                filename = self.video_list.GetItemText(i, 0)
                selected_files.append(filename)
        
        if not selected_files:
            wx.MessageBox("No files selected for deletion.", "Nothing to Delete", 
                         wx.OK | wx.ICON_INFORMATION)
            return
        
        # Show confirmation dialog with file list
        file_list = "\n".join([f"• {f}" for f in selected_files[:20]])  # Show first 20
        if len(selected_files) > 20:
            file_list += f"\n... and {len(selected_files) - 20} more files"
        
        msg = f"Are you sure you want to permanently delete {len(selected_files)} file(s)?\n\n{file_list}\n\nThis action cannot be undone!"
        
        dlg = wx.MessageDialog(self, msg, "Confirm Delete", 
                              wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
        
        if dlg.ShowModal() == wx.ID_YES:
            # Perform deletion
            success_count = 0
            errors = []
            
            for filename in selected_files:
                if self.app_state.working_dir:
                    file_path = self.app_state.working_dir / filename
                    try:
                        if file_path.exists():
                            file_path.unlink()  # Delete the file
                            success_count += 1
                            logger.info(f"Deleted file: {filename}")
                        else:
                            errors.append(f"{filename}: File not found")
                    except Exception as e:
                        errors.append(f"{filename}: {e}")
                        logger.error(f"Failed to delete {filename}: {e}")
            
            # Show results
            if not errors:
                wx.MessageBox(f"Successfully deleted {success_count} file(s).", 
                             "Delete Complete", wx.OK | wx.ICON_INFORMATION)
            else:
                error_summary = f"Deleted {success_count} file(s) successfully.\n{len(errors)} deletion(s) failed:\n\n"
                error_summary += "\n".join(errors[:5])  # Show first 5 errors
                if len(errors) > 5:
                    error_summary += f"\n... and {len(errors) - 5} more errors"
                
                wx.MessageBox(error_summary, "Delete Completed with Errors", 
                             wx.OK | wx.ICON_WARNING)
            
            # Refresh the list to remove deleted files
            if success_count > 0:
                self.refresh()
        
        dlg.Destroy()
    
    def ApplyFilter(self):
        """Apply the current filter to the video list."""
        pattern = self.filter_text.GetValue()
        use_regex = self.regex_checkbox.GetValue()
        self.video_list.set_filter(pattern, use_regex)
    
    # Delegate methods to the video list
    def refresh(self, completion_callback=None, force_full_refresh=False):
        """Delegate refresh to the video list."""
        return self.video_list.refresh(completion_callback, force_full_refresh)
    
    def clear_error_cache(self):
        """Delegate to the video list."""
        return self.video_list.clear_error_cache()
    
    def force_refresh_all(self):
        """Delegate to the video list."""
        return self.video_list.force_refresh_all()
    
    def uncheck_video_by_path(self, video_path):
        """Delegate to the video list."""
        return self.video_list.uncheck_video_by_path(video_path)
    
    def recheck_videos_by_paths(self, video_paths):
        """Delegate to the video list."""
        return self.video_list.recheck_videos_by_paths(video_paths)
    
    # Additional delegation methods for main_frame compatibility
    def GetItemCount(self):
        """Delegate to the video list."""
        return self.video_list.GetItemCount()
    
    def CheckItem(self, index, checked=True):
        """Delegate to the video list."""
        return self.video_list.CheckItem(index, checked)
    
    def OnChecked(self, event):
        """Delegate to the video list."""
        return self.video_list.OnChecked(event)
    
    def get_all_visible_files(self):
        """Get all currently visible (filtered) files as absolute paths."""
        if not self.app_state.working_dir:
            return []
            
        visible_files = []
        for i in range(self.video_list.GetItemCount()):
            rel_path = self.video_list.GetItemText(i, 0)
            abs_path = str(self.app_state.working_dir / rel_path)
            visible_files.append(abs_path)
        return visible_files

    def toggle_inline_rename(self):
        """Toggle the inline rename mode."""
        if hasattr(self, 'rename_bar') and self.rename_bar.IsShown():
            self.hide_inline_rename()
        else:
            self.show_inline_rename()
