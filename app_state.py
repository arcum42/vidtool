#!/usr/bin/env python

import json
import pathlib
from typing import Optional, List, Dict, Any

from modules.presets import PresetManager
from modules.logging_config import get_logger, set_log_level
import logging

logger = get_logger('app_state')


class AppState:
    """Central application state manager to replace global variables."""
    
    def __init__(self):
        self.video_list: List[str] = []
        self.selected_video: Optional[pathlib.Path] = None
        self.config: Dict[str, Any] = {}
        self.working_dir: Optional[pathlib.Path] = None
        self.main_frame: Any = None  # Will be set to MyFrame instance (avoid typing conflicts)
        self.preset_manager: Optional[PresetManager] = None
        
    def load_config(self):
        """Load configuration from config.json file."""
        config_file = pathlib.Path(__file__).parent / "config.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    self.config = json.load(f)
                    logger.info("Configuration loaded successfully")
                    logger.debug(f"Config contents: {self.config}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading config: {e}. Using default settings.")
                self.config = {}
        else:
            logger.info("Config file not found. Using default settings.")
            
        # Configure logging level based on config
        log_level = self.config.get("log_level", "INFO")
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR
        }
        if log_level in level_map:
            set_log_level(level_map[log_level])
            logger.info(f"Log level set to {log_level}")
        else:
            set_log_level(logging.INFO)
            logger.warning(f"Unknown log level '{log_level}', defaulting to INFO")
            
        # Initialize preset manager
        self.preset_manager = PresetManager()
        self.preset_manager.load_presets()
            
    def save_config(self):
        """Save configuration to config.json file."""
        config_file = pathlib.Path(__file__).parent / "config.json"
        try:
            with open(config_file, "w") as f:
                json.dump(self.config, f, indent=2)
                print("Config saved:", self.config)
        except IOError as e:
            print(f"Error saving config: {e}")
