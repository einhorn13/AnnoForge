# plugins/greyscale_converter/plugin.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os

from plugins.api import ImageProcessorPlugin

class GreyscaleConverterPlugin(ImageProcessorPlugin):
    """
    A fully functional plugin to convert images to greyscale and save them.
    """
    def __init__(self):
        super().__init__()
        self.preview_label = None
        self.photo_image = None # To prevent garbage collection
        self.output_path_var = tk.StringVar(value="greyscale_output")

    @property
    def name(self) -> str: return "greyscale_converter"
    
    @property
    def display_name(self) -> str: return "Greyscale"

    @property
    def workspace_title(self) -> str:
        return "Greyscale Preview"

    def create_ui(self, parent_frame: tk.Frame) -> tk.Frame:
        """Creates the settings panel UI for the plugin."""
        ui_frame = ttk.Frame(parent_frame, padding="10")
        
        self.settings = {
            "algorithm": tk.StringVar(value="Luminosity (Rec. 709)")
        }
        
        self.original_size_var = tk.StringVar(value="Original: -")
        ttk.Label(ui_frame, textvariable=self.original_size_var, font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(0, 10))
        
        ttk.Label(ui_frame, text="Conversion Algorithm:").pack(anchor="w", pady=(0, 5))
        
        algos = ["Luminosity (Rec. 709)", "Average ((R+G+B)/3)", "Lightness ((max+min)/2)"]
        ttk.Combobox(
            ui_frame, 
            textvariable=self.settings["algorithm"], 
            values=algos, 
            state="readonly"
        ).pack(fill="x")

        ttk.Label(ui_frame, 
            text="\nLuminosity: Standard, perceptually weighted.\nAverage: Simple channel averaging.\nLightness: Average of bright/dark colors.", 
            justify="left",
            font=("Segoe UI", 8)
        ).pack(anchor="w", pady=(10, 0))

        # --- Action Buttons ---
        action_frame = ttk.LabelFrame(ui_frame, text="Actions", padding=10)
        action_frame.pack(fill="x", pady=(20, 0))
        action_frame.columnconfigure(1, weight=1)
        
        ttk.Button(action_frame, text="Save to", command=self._save_to_output).grid(row=0, column=0, sticky="w")
        ttk.Entry(action_frame, textvariable=self.output_path_var).grid(row=0, column=1, sticky="we", padx=5)
        ttk.Button(action_frame, text="Overwrite Original(s)", command=self._overwrite_originals).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        
        return ui_frame

    def create_workspace(self, parent_frame: tk.Frame) -> tk.Widget:
        """Creates the preview widget for the workspace."""
        if not self.preview_label:
            self.preview_label = ttk.Label(parent_frame, background="#505050", anchor="center")
        return self.preview_label

    def on_image_selected(self, pil_image: Image.Image | None):
        """Updates the info label and the preview when a new image is selected."""
        # FIXED: Add a guard clause to prevent errors during initialization.
        if not self.app_context:
            return
            
        if pil_image:
            self.original_size_var.set(f"Original: {pil_image.width} x {pil_image.height} px")
            # Create a thumbnail for the preview to keep it fast
            preview_image = pil_image.copy()
            preview_image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            
            # Process the thumbnail to show the greyscale effect
            processed_preview = self.process_image(preview_image)
            self.photo_image = ImageTk.PhotoImage(processed_preview)
            self.preview_label.config(image=self.photo_image)
        else:
            self.original_size_var.set("Original: -")
            self.preview_label.config(image=None)
            self.photo_image = None
            
    def _save_to_output(self):
        output_dir = self.output_path_var.get()
        if not output_dir:
            self.app_context.show_error("Path Error", "Output path cannot be empty.")
            return
        self._execute_processing(overwrite=False, out_dir=output_dir)

    def _overwrite_originals(self):
        if messagebox.askyesno("Confirm Overwrite", "This will permanently overwrite the original file(s).\nThis action cannot be undone. Are you sure?", parent=self.app_context.root):
            self._execute_processing(overwrite=True)
            
    def _execute_processing(self, overwrite: bool, out_dir: str = None):
        """Handles the logic for running the batch processing job."""
        checked_ids = self.app_context.get_checked_item_ids()
        if not checked_ids:
            self.app_context.show_info("No Selection", "Please check one or more items to process.")
            return
        
        items_to_process = self.app_context.get_items_data(checked_ids)
        if not overwrite and out_dir:
            os.makedirs(out_dir, exist_ok=True)
        
        def processing_task(item, context):
            """The actual work done for each item in a background thread."""
            context.update_status(f"Converting {item['filename']} to greyscale...")
            with Image.open(item["filepath"]) as img:
                processed_image = self.process_image(img)

            target_path = item["filepath"] if overwrite else os.path.join(out_dir, item["filename"])
            processed_image.save(target_path)
            
            if overwrite:
                context.clear_image_cache([item["item_id"]])
                context.refresh_ui_items([item["item_id"]], update_thumbnail=True)
            return True

        self.app_context.run_job(processing_task, items_to_process, "Greyscale Conversion")

    def process_image(self, image: Image.Image) -> Image.Image:
        """Applies the selected greyscale conversion algorithm."""
        algorithm = self.settings["algorithm"].get()
        image = image.convert("RGB") # Ensure it's in a format we can process

        if algorithm == "Luminosity (Rec. 709)":
            return image.convert("L").convert("RGB")
        
        width, height = image.size
        new_image = Image.new("RGB", (width, height))
        pixels = new_image.load()
        
        for i in range(width):
            for j in range(height):
                r, g, b = image.getpixel((i, j))
                
                if algorithm == "Average ((R+G+B)/3)":
                    gray = (r + g + b) // 3
                elif algorithm == "Lightness ((max+min)/2)":
                    gray = (max(r, g, b) + min(r, g, b)) // 2
                else: # Fallback
                    gray = int(r * 0.299 + g * 0.587 + b * 0.114)
                
                pixels[i, j] = (gray, gray, gray)
                
        return new_image

def register():
    return GreyscaleConverterPlugin()