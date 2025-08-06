# utils.py
import os
import json
import csv

SUPPORTED_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")
CONFIG_FILE = "config.json"

def load_config():
    """Load config from JSON file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config):
    """Save config to JSON file"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass

def scan_images(directory="captions"):
    """List all supported image files in directory"""
    if not os.path.exists(directory):
        return []
    return [f for f in os.listdir(directory) if f.lower().endswith(SUPPORTED_EXT)]

def scan_checkpoints(directory="ckpt"):
    """Scan for valid Florence-2 models"""
    if not os.path.exists(directory):
        return []
    models = []
    for d in os.listdir(directory):
        path = os.path.join(directory, d)
        if os.path.isdir(path):
            if os.path.exists(os.path.join(path, "config.json")):
                models.append(path)
    return models

def export_to_csv(file_data, output_path):
    """Export filename-caption pairs to CSV"""
    try:
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["filename", "caption"])
            for item in file_data:
                writer.writerow([item["filename"], item["caption"]])
        return True
    except Exception:
        return False