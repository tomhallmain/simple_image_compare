import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from utils.custom_formatter import CustomFormatter

def _cleanup_old_logs(log_dir):
    """
    Clean up log files that are older than 30 days if there are more than 10 log files.
    """
    try:
        log_files = list(log_dir.glob('simple_image_compare_*.log'))
        if len(log_files) <= 10:
            return

        current_time = datetime.now()
        cutoff_date = current_time - timedelta(days=30)
        
        for log_file in log_files:
            try:
                # Extract date from filename (format: simple_image_compare_YYYY-MM-DD.log)
                date_str = log_file.stem.split('_')[-1]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                if file_date < cutoff_date:
                    log_file.unlink()
                    logger.debug(f"Deleted old log file: {log_file}")
            except (ValueError, IndexError):
                # Skip files that don't match the expected format
                continue
    except Exception as e:
        logger.error(f"Error cleaning up old log files: {e}")

def setup_logging():
    """
    Set up the logging configuration for the application.
    Returns the logger instance and the log file path.
    """
    # create logger
    logger = logging.getLogger("simple_image_compare")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)

    # Create log file in ApplicationData
    appdata_dir = os.getenv('APPDATA') if sys.platform == 'win32' else os.path.expanduser('~/.local/share')
    log_dir = Path(appdata_dir) / 'simple_image_compare' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    # Clean up old logs before creating new one
    _cleanup_old_logs(log_dir)

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f'simple_image_compare_{date_str}.log'

    # Add file handler
    fh = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(CustomFormatter())
    logger.addHandler(fh)

    return logger, log_file

# Initialize logging
logger, log_file = setup_logging() 