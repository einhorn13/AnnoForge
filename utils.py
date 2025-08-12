# utils.py
import os
import json
import csv
from PIL import Image
import threading
import logging
from collections import deque
from logging import Handler, LogRecord

# --- Centralized Logging System ---

class AppLogHandler(Handler):
    def __init__(self, maxlen=200):
        super().__init__()
        self.log_records = deque(maxlen=maxlen)

    def emit(self, record: LogRecord):
        self.log_records.append(self.format(record))
    
    def get_logs(self):
        return list(self.log_records)
    
    def clear(self):
        self.log_records.clear()

app_log_handler = AppLogHandler()

def setup_logging():
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    
    app_log_handler.setLevel(logging.INFO)
    app_log_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        logger.addHandler(app_log_handler)
        logger.addHandler(console_handler)

# --- Existing Functions ---

SUPPORTED_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
    return {}

def save_config(config):
    existing_config = load_config()
    existing_config.update(config)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_config, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving config: {e}")

def scan_images(directory="captions"):
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        return []
    try:
        return sorted([
            f for f in os.listdir(directory) 
            if f.lower().endswith(SUPPORTED_EXT)
        ])
    except Exception as e:
        logging.error(f"Error scanning directory {directory}: {e}")
        return []

def export_to_csv(file_data, output_path):
    if not file_data:
        logging.warning("export_to_csv called with no data.")
        return False
    try:
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            headers = ["filename", "caption"]
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for item in file_data:
                writer.writerow({
                    "filename": item.get("filename", "N/A"),
                    "caption": item.get("caption", "")
                })
        logging.info(f"Successfully exported {len(file_data)} items to {output_path}")
        return True
    except (IOError, csv.Error) as e:
        logging.error(f"Error exporting to CSV at {output_path}: {e}")
        return False

class ImageLoader:
    """
    A thread-safe singleton class for loading and caching image thumbnails and full images.
    This prevents re-reading and resizing the same image multiple times.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.thumb_cache = {}
                cls._instance.full_image_cache = {}
        return cls._instance

    def get_thumbnail(self, path: str, size: tuple[int, int]) -> Image.Image | None:
        cache_key = (path, tuple(size))
        if cache_key in self.thumb_cache:
            return self.thumb_cache[cache_key]
        
        full_image = self.get_full_image(path)
        if full_image:
            try:
                thumb = full_image.copy()
                thumb.thumbnail(size, Image.Resampling.LANCZOS)
                self.thumb_cache[cache_key] = thumb
                return thumb
            except Exception as e:
                logging.warning(f"Error creating thumbnail for {path}: {e}")
        return None
        
    def get_full_image(self, path: str) -> Image.Image | None:
        if path in self.full_image_cache:
            return self.full_image_cache[path]
        
        try:
            with Image.open(path) as img:
                img.load()
                self.full_image_cache[path] = img
                return img
        except Exception as e:
            logging.warning(f"Error loading full image for {path}: {e}")
            return None
            
    def clear_cache_for_item(self, path: str):
        """Removes all cached versions (thumbnails and full) for a specific path."""
        with self._lock:
            keys_to_del = [k for k in self.thumb_cache if k[0] == path]
            for key in keys_to_del:
                del self.thumb_cache[key]
            if path in self.full_image_cache:
                del self.full_image_cache[path]
                logging.debug(f"Cleared cache for image: {os.path.basename(path)}")