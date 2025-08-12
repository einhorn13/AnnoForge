# providers.py
import os
import logging
import utils

class ImageFileProvider:
    """
    Manages the project's source image files and their associated simple data,
    like captions stored in .txt files. It acts as the primary source of truth
    for the list of items in a project.
    """
    def __init__(self, default_prompt_type: str):
        self.directory = ""
        self.files_data = {}  # In-memory cache: {item_id: data_dict}
        self.default_prompt_type = default_prompt_type

    def scan(self, directory: str) -> list[dict]:
        """
        Scans a directory for images, loads associated captions, and populates
        the internal data store.
        """
        self.directory = directory
        self.files_data.clear()
        
        if not os.path.exists(self.directory):
            logging.error(f"Data source directory not found: {self.directory}")
            return []
        
        image_filenames = utils.scan_images(self.directory)
        
        for filename in image_filenames:
            item_id = filename
            filepath = os.path.join(self.directory, filename)
            txt_path = f"{os.path.splitext(filepath)[0]}.txt"
            
            caption_content = ""
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, "r", encoding="utf-8") as f:
                        caption_content = f.read().strip()
                except Exception as e:
                    logging.error(f"Could not read caption for {filename}: {e}")

            self.files_data[item_id] = {
                "item_id": item_id,
                "filename": filename,
                "filepath": filepath,
                "txt_path": txt_path,
                "caption": caption_content,
                "prompt_type": self.default_prompt_type,
            }
            
        logging.info(f"Scanned {len(self.files_data)} images from '{self.directory}'.")
        return list(self.files_data.values())

    def get_all_files(self) -> list[dict]:
        """Returns all file data dictionaries as a list."""
        return list(self.files_data.values())

    def get_files_by_ids(self, item_ids: list[str]) -> list[dict]:
        """Returns data for a specific list of item IDs."""
        return [self.files_data[id] for id in item_ids if id in self.files_data]

    def get_file_by_id(self, item_id: str) -> dict | None:
        """Returns data for a single item ID."""
        return self.files_data.get(item_id)

    def save_item_data(self, item_id: str, data: dict) -> bool:
        """
        Saves data for an item. Currently only handles saving 'caption' to a .txt file.
        """
        file_data = self.get_file_by_id(item_id)
        if not file_data:
            logging.warning(f"Attempted to save data for non-existent item_id: {item_id}")
            return False
            
        if "caption" in data:
            content = data["caption"].strip()
            try:
                with open(file_data["txt_path"], "w", encoding="utf-8") as f:
                    f.write(content)
                # Update in-memory cache
                file_data["caption"] = content
                logging.debug(f"Saved caption for {item_id}")
                return True
            except Exception as e:
                logging.error(f"Error saving caption for {item_id}: {e}")
                return False
        
        return False

    def update_prompt_type(self, item_id: str, new_type: str):
        """Updates the prompt type for a single item in the in-memory cache."""
        if item_id in self.files_data:
            self.files_data[item_id]["prompt_type"] = new_type
        else:
            logging.warning(f"Attempted to update prompt for non-existent item_id: {item_id}")