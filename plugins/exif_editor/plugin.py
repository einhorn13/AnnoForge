# plugins/exif_editor/plugin.py
"""
EXIF Editor Plugin for AnnoForge.

Allows viewing and editing of EXIF metadata for JPEG and TIFF images.

Dependencies:
  - piexif: A library for easy EXIF manipulation.
    Install with: pip install piexif
"""
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image
import piexif
import logging
import os

from plugins.api import ImageProcessorPlugin

class ExifEditorPlugin(ImageProcessorPlugin):
    def __init__(self):
        super().__init__()
        # --- UI Widgets ---
        self.tree = None
        self.edit_var = tk.StringVar()

        # --- State ---
        self.current_exif_data = None
        self.selected_image_path = None
        # A mapping to link treeview item IDs to their EXIF tag details
        self.tree_item_map = {}

    @property
    def name(self) -> str: return "exif_editor"
    @property
    def display_name(self) -> str: return "EXIF Editor"
    @property
    def workspace_title(self) -> str: return "EXIF Metadata"

    def create_ui(self, parent_frame: tk.Frame) -> tk.Frame:
        """Creates the settings and action panel for the plugin."""
        ui_frame = ttk.Frame(parent_frame, padding="10")
        ui_frame.columnconfigure(0, weight=1)

        # --- Editing Frame ---
        edit_frame = ttk.LabelFrame(ui_frame, text="Edit Selected Tag", padding=10)
        edit_frame.grid(row=0, column=0, sticky="ew")
        edit_frame.columnconfigure(0, weight=1)

        self.edit_entry = ttk.Entry(edit_frame, textvariable=self.edit_var, state="disabled")
        self.edit_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.apply_button = ttk.Button(edit_frame, text="Apply", command=self._on_apply_edit, state="disabled")
        self.apply_button.grid(row=0, column=1, sticky="e")

        # --- Actions Frame ---
        action_frame = ttk.LabelFrame(ui_frame, text="Actions", padding=10)
        action_frame.grid(row=1, column=0, sticky="ew", pady=(15, 0))
        action_frame.columnconfigure(0, weight=1)

        ttk.Button(action_frame, text="Overwrite Original", command=self._overwrite_original).grid(row=0, column=0, sticky="ew")
        ttk.Button(action_frame, text="Remove All EXIF", command=self._on_remove_all).grid(row=1, column=0, sticky="ew", pady=(5, 0))
        
        return ui_frame

    def create_workspace(self, parent_frame: tk.Frame) -> tk.Widget:
        """Creates the Treeview for displaying EXIF data."""
        ws_frame = ttk.Frame(parent_frame)
        ws_frame.rowconfigure(0, weight=1)
        ws_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(ws_frame, columns=("Tag", "Value"), show="headings")
        self.tree.heading("Tag", text="Tag Name")
        self.tree.heading("Value", text="Value")
        self.tree.column("Tag", width=150, anchor="w")
        self.tree.column("Value", width=250, anchor="w")

        scrollbar = ttk.Scrollbar(ws_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        return ws_frame

    def on_image_selected(self, pil_image: Image.Image | None):
        """Loads EXIF data when a new image is selected."""
        # FIXED: Add a guard clause to prevent errors during initialization.
        if not self.app_context:
            return

        self._clear_view()
        if not pil_image:
            return

        active_id = self.app_context.get_active_item_id()
        if not active_id:
            return

        item_data = self.app_context.get_items_data([active_id])[0]
        self.selected_image_path = item_data['filepath']

        try:
            # piexif is great for loading EXIF data as a dictionary
            self.current_exif_data = piexif.load(self.selected_image_path)
            self._populate_tree(self.current_exif_data)
        except (ValueError, piexif.InvalidImageDataError):
            self.tree.insert("", "end", values=("(No EXIF Data)", ""))
        except Exception as e:
            logging.error(f"Failed to load EXIF for {self.selected_image_path}: {e}")
            self.tree.insert("", "end", values=("(Error Reading EXIF)", str(e)))

    def _populate_tree(self, exif_data):
        """Fills the treeview with EXIF tag names and values."""
        self.tree.delete(*self.tree.get_children())
        self.tree_item_map.clear()
        
        for ifd_name in exif_data:
            if ifd_name == "thumbnail":
                continue
            
            # Create a collapsible section for each IFD (e.g., "0th", "Exif")
            section_id = self.tree.insert("", "end", text=ifd_name, values=(f"--- {ifd_name} ---", ""), open=True)

            for tag, value in exif_data[ifd_name].items():
                tag_name = piexif.TAGS.get(ifd_name, {}).get(tag, {"name": f"UnknownTag {tag}"})["name"]
                
                # Decode bytes to string for display, handle potential errors
                try:
                    display_value = value.decode('utf-8', errors='ignore').strip('\x00')
                except (UnicodeDecodeError, AttributeError):
                    display_value = str(value)

                item_id = self.tree.insert(section_id, "end", values=(tag_name, display_value))
                self.tree_item_map[item_id] = (ifd_name, tag)

    def _on_tree_select(self, event=None):
        """Called when a user selects a row in the treeview."""
        selected_items = self.tree.selection()
        if not selected_items:
            self.edit_entry.config(state="disabled")
            self.apply_button.config(state="disabled")
            return

        item_id = selected_items[0]
        if item_id in self.tree_item_map: # It's an editable tag
            current_value = self.tree.item(item_id, "values")[1]
            self.edit_var.set(current_value)
            self.edit_entry.config(state="normal")
            self.apply_button.config(state="normal")
        else: # It's a section header
             self.edit_entry.config(state="disabled")
             self.apply_button.config(state="disabled")


    def _on_apply_edit(self):
        """Applies the edited value to the in-memory EXIF data and the UI."""
        selected_items = self.tree.selection()
        if not selected_items or not self.current_exif_data:
            return
        
        item_id = selected_items[0]
        ifd_name, tag = self.tree_item_map[item_id]
        
        new_value_str = self.edit_var.get()
        new_value_bytes = new_value_str.encode('utf-8')
        
        # Update in-memory data
        self.current_exif_data[ifd_name][tag] = new_value_bytes
        
        # Update UI for immediate feedback
        current_tag_name = self.tree.item(item_id, "values")[0]
        self.tree.item(item_id, values=(current_tag_name, new_value_str))
        logging.info(f"Updated EXIF tag '{current_tag_name}' in memory.")

    def _on_remove_all(self):
        """Removes all EXIF data from memory and clears the view."""
        if not self.current_exif_data:
            self.app_context.show_info("EXIF Editor", "No EXIF data to remove.")
            return
        
        self.current_exif_data = {}
        self.tree.delete(*self.tree.get_children())
        self.tree.insert("", "end", values=("(All EXIF removed in memory)", "Save to apply."))
        logging.info("Removed all EXIF data in memory. Click 'Overwrite' to save.")

    def _overwrite_original(self):
        """Starts the background job to save the modified EXIF data."""
        if self.current_exif_data is None or self.selected_image_path is None:
            self.app_context.show_error("Save Error", "No image selected or no EXIF data loaded.")
            return
            
        if not messagebox.askyesno("Confirm Overwrite", "This will permanently modify the EXIF data of the original file.\nAre you sure?", parent=self.app_context.root):
            return

        item_data = {'filepath': self.selected_image_path}
        
        def save_task(item, context):
            """The background task to save EXIF data."""
            context.update_status(f"Saving EXIF to {os.path.basename(item['filepath'])}...")
            try:
                if self.current_exif_data:
                    exif_bytes = piexif.dump(self.current_exif_data)
                    piexif.insert(exif_bytes, item['filepath'])
                else: # Handle removal of all EXIF data
                    piexif.remove(item['filepath'])
                return True
            except Exception as e:
                logging.error(f"Failed to save EXIF data to {item['filepath']}: {e}")
                return False

        self.app_context.run_job(save_task, [item_data], "Saving EXIF Data")

    def _clear_view(self):
        """Resets the UI and internal state."""
        self.edit_var.set("")
        self.edit_entry.config(state="disabled")
        self.apply_button.config(state="disabled")
        if self.tree:
            self.tree.delete(*self.tree.get_children())
        self.current_exif_data = None
        self.selected_image_path = None
        self.tree_item_map.clear()
        
    def process_image(self, image: Image.Image) -> Image.Image:
        """This plugin doesn't process image pixels, so it returns the original."""
        return image

def register():
    """The entry point for the plugin manager."""
    return ExifEditorPlugin()