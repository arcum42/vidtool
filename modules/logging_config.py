"""
Logging configuration module for VidTool.

This module provides centralized logging configuration and utilities for the VidTool application.
It supports structured logging with proper formatting, file output, and context-aware error logging.
"""

import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


# Global logger registry to track loggers
_loggers = {}
_log_level = logging.INFO
_log_file = None


def setup_logging(log_file="vidtool.log", log_level=logging.INFO, max_bytes=10*1024*1024, backup_count=3, 
                  log_to_console=None, log_to_file=None):
    """
    Set up centralized logging configuration for the application.
    
    Args:
        log_file (str): Path to the log file
        log_level (int): Default log level (e.g., logging.INFO, logging.DEBUG)
        max_bytes (int): Maximum size of log file before rotation (default: 10MB)
        backup_count (int): Number of backup files to keep (default: 3)
        log_to_console (bool): Force console logging on/off (None for auto-detect)
        log_to_file (bool): Force file logging on/off (None for auto-detect)
    """
    global _log_level, _log_file
    
    _log_level = log_level
    _log_file = log_file
    
    # Auto-detect logging preferences if not specified
    if log_to_console is None:
        log_to_console = True  # Default to console logging
    if log_to_file is None:
        log_to_file = True  # Default to file logging unless explicitly disabled
    
    # Create logs directory if it doesn't exist and file logging is enabled
    if log_to_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create rotating file handler if file logging is enabled
    if log_to_file:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, 
                maxBytes=max_bytes, 
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            # Fallback to console if file logging fails
            print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)
            log_to_console = True  # Force console logging as fallback
    
    # Create console handler if console logging is enabled
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)


def get_logger(name="vidtool"):
    """
    Get a configured logger instance for the specified module.
    
    Args:
        name (str): Logger name, typically the module name
        
    Returns:
        logging.Logger: Configured logger instance
    """
    global _loggers
    
    if name not in _loggers:
        logger = logging.getLogger(f"vidtool.{name}")
        logger.setLevel(_log_level)
        _loggers[name] = logger
    
    return _loggers[name]


def set_log_level(level):
    """
    Set the log level for all existing loggers and future loggers.
    
    Args:
        level (int): Log level constant from logging module
    """
    global _log_level
    
    _log_level = level
    
    # Update root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Update all handlers
    for handler in root_logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.setLevel(level)
    
    # Update all tracked loggers
    for logger in _loggers.values():
        logger.setLevel(level)


def log_ffmpeg_command(command, logger_instance=None):
    """
    Log an FFmpeg command with proper formatting and security considerations.
    
    Args:
        command (list): FFmpeg command as a list of arguments
        logger_instance (logging.Logger, optional): Logger to use, defaults to main logger
    """
    if logger_instance is None:
        logger_instance = get_logger('video')
    
    if not command:
        logger_instance.warning("Empty FFmpeg command provided")
        return
    
    try:
        # Convert command list to string, handling potential special characters
        if isinstance(command, list):
            # Join with spaces, but be careful about file paths with spaces
            command_str = ' '.join(str(arg) for arg in command)
        else:
            command_str = str(command)
        
        # Log the command
        logger_instance.info(f"Executing FFmpeg command: {command_str}")
        
        # Also log individual arguments for debugging if in debug mode
        if logger_instance.isEnabledFor(logging.DEBUG):
            logger_instance.debug(f"FFmpeg command arguments: {command}")
            
    except Exception as e:
        logger_instance.error(f"Error logging FFmpeg command: {e}")


def log_error_with_context(exception, context_message, logger_instance=None, include_traceback=True):
    """
    Log an exception with contextual information and optional traceback.
    
    Args:
        exception (Exception): The exception that occurred
        context_message (str): Contextual information about when/where the error occurred
        logger_instance (logging.Logger, optional): Logger to use, defaults to main logger
        include_traceback (bool): Whether to include full traceback (default: True)
    """
    if logger_instance is None:
        logger_instance = get_logger('app')
    
    try:
        # Create the main error message
        error_msg = f"{context_message}: {type(exception).__name__}: {str(exception)}"
        
        # Log the error
        logger_instance.error(error_msg)
        
        # Include traceback for debugging if requested and in debug mode
        if include_traceback and logger_instance.isEnabledFor(logging.DEBUG):
            tb_str = traceback.format_exc()
            logger_instance.debug(f"Traceback for {context_message}:\n{tb_str}")
        
        # For certain critical exceptions, always include some traceback info
        if isinstance(exception, (MemoryError, SystemError, KeyboardInterrupt)):
            tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
            # Just log the last few lines of traceback for critical errors
            logger_instance.error(f"Critical error traceback: {''.join(tb_lines[-3:])}")
            
    except Exception as log_error:
        # Fallback error logging - something went wrong with logging itself
        try:
            print(f"LOGGING ERROR: Failed to log exception: {log_error}", file=sys.stderr)
            print(f"Original error: {context_message}: {exception}", file=sys.stderr)
        except:
            pass  # Give up if even basic error reporting fails


def get_log_stats():
    """
    Get statistics about the current logging configuration.
    
    Returns:
        dict: Dictionary containing logging statistics and configuration info
    """
    root_logger = logging.getLogger()
    
    stats = {
        'log_level': logging.getLevelName(_log_level),
        'log_file': _log_file,
        'num_loggers': len(_loggers),
        'logger_names': list(_loggers.keys()),
        'num_handlers': len(root_logger.handlers),
        'handler_types': [type(h).__name__ for h in root_logger.handlers]
    }
    
    # Add file size if log file exists
    if _log_file and os.path.exists(_log_file):
        try:
            stats['log_file_size'] = os.path.getsize(_log_file)
        except OSError:
            stats['log_file_size'] = 'unknown'
    
    return stats


def flush_logs():
    """
    Force flush all log handlers to ensure messages are written to disk.
    """
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass  # Ignore flush errors


# Convenience function for backward compatibility
def configure_logging(*args, **kwargs):
    """Alias for setup_logging for backward compatibility."""
    return setup_logging(*args, **kwargs)


# Initialize default logging if this module is imported
if not logging.getLogger().handlers:
    setup_logging()
