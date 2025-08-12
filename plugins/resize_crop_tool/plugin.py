# plugins/resize_crop_tool/plugin.py
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image
import math
import os
from plugins.api import ImageProcessorPlugin
from .canvas_widget import InteractiveCanvas

class ResizeCropPlugin(ImageProcessorPlugin):
    def __init__(self):
        super().__init__()
        self.interactive_canvas = None
        self._is_programmatic_update = False
        
        # REFACTORED: Define aspect ratio presets
        self.aspect_ratios = {
            "Freeform": None,
            "1:1 Square": (1, 1),
            "4:3 Standard": (4, 3),
            "3:2 Classic": (3, 2),
            "16:9 Widescreen": (16, 9),
            "21:9 Cinema": (21, 9),
            "3:4 Portrait": (3, 4),
            "2:3 Portrait": (2, 3),
            "9:16 Vertical": (9, 16)
        }

    @property
    def name(self) -> str: return "resize_crop_tool"
    @property
    def display_name(self) -> str: return "Resize & Crop"
    @property
    def workspace_title(self) -> str: return "Resize & Crop Canvas"

    def create_ui(self, parent_frame: tk.Frame) -> tk.Frame:
        ui_frame = ttk.Frame(parent_frame, padding="10")
        ui_frame.columnconfigure(1, weight=1)
        
        self.settings = {
            "width": tk.IntVar(value=512), "height": tk.IntVar(value=512),
            "ratio_w": tk.IntVar(value=1), "ratio_h": tk.IntVar(value=1),
            "aspect_lock": tk.BooleanVar(value=True),
            "aspect_preset": tk.StringVar(value="1:1 Square"),
            "algorithm": tk.StringVar(value="Lanczos"),
            "output_path": tk.StringVar(value="output")
        }
        
        self.original_size_var = tk.StringVar(value="Original: -")
        ttk.Label(ui_frame, textvariable=self.original_size_var, font=("Segoe UI", 8, "italic")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        ttk.Label(ui_frame, text="Crop Width:").grid(row=1, column=0, sticky="w", pady=2)
        width_entry = ttk.Entry(ui_frame, textvariable=self.settings["width"], width=7)
        width_entry.grid(row=1, column=1, sticky="w")
        
        ttk.Label(ui_frame, text="Crop Height:").grid(row=2, column=0, sticky="w", pady=2)
        height_entry = ttk.Entry(ui_frame, textvariable=self.settings["height"], width=7)
        height_entry.grid(row=2, column=1, sticky="w")
        
        # REFACTORED: Use a Combobox for aspect ratio presets
        ttk.Label(ui_frame, text="Aspect Ratio:").grid(row=1, column=2, sticky="w", padx=(15, 5))
        self.preset_combo = ttk.Combobox(ui_frame, textvariable=self.settings["aspect_preset"], values=list(self.aspect_ratios.keys()), state="readonly")
        self.preset_combo.grid(row=1, column=3, sticky="we")
        self.preset_combo.bind("<<ComboboxSelected>>", lambda e: self._on_preset_selected(self.preset_combo.get()))

        lock_btn = ttk.Checkbutton(ui_frame, text="Lock Aspect", variable=self.settings["aspect_lock"], command=self._on_lock_toggled)
        lock_btn.grid(row=2, column=2, columnspan=2, sticky="w", padx=15)
        
        # Button container for Reset and Apply Size
        btn_frame = ttk.Frame(ui_frame)
        btn_frame.grid(row=3, column=2, columnspan=2, sticky="w", padx=15, pady=5)
        
        # NEW: Button to apply size from entry fields to the crop box
        apply_size_btn = ttk.Button(btn_frame, text="Apply Size", command=self._on_apply_size_clicked)
        apply_size_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        reset_btn = ttk.Button(btn_frame, text="Reset Crop", command=self._on_reset_clicked)
        reset_btn.pack(side=tk.LEFT)

        ttk.Label(ui_frame, text="Algorithm:").grid(row=4, column=0, sticky="w", pady=(10,2))
        algos = ["Nearest", "Bilinear", "Bicubic", "Lanczos"]
        ttk.Combobox(ui_frame, textvariable=self.settings["algorithm"], values=algos, state="readonly").grid(row=4, column=1, columnspan=3, sticky="we")
        
        action_frame = ttk.LabelFrame(ui_frame, text="Actions", padding=10)
        action_frame.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(20, 0))
        action_frame.columnconfigure(1, weight=1)
        ttk.Button(action_frame, text="Save to", command=self._save_to_output).grid(row=0, column=0, sticky="w")
        ttk.Entry(action_frame, textvariable=self.settings["output_path"]).grid(row=0, column=1, sticky="we", padx=5)
        ttk.Button(action_frame, text="Overwrite Original(s)", command=self._overwrite_originals).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        
        self.settings["width"].trace_add("write", lambda *args: self._on_ui_value_changed("width"))
        self.settings["height"].trace_add("write", lambda *args: self._on_ui_value_changed("height"))
        
        return ui_frame

    def get_state_to_save(self) -> dict | None:
        if not self.interactive_canvas:
            return None
        crop_box = self.interactive_canvas.get_crop_geometry()
        return {"crop_box": crop_box}

    def _request_save_state(self):
        if self.app_context:
            self.app_context.event_bus.publish("ui:plugin_state_changed", self.name)

    # ... (execution methods remain the same) ...
    def _save_to_output(self):
        output_dir = self.settings["output_path"].get()
        if not output_dir:
            self.app_context.show_error("Path Error", "Output path cannot be empty.")
            return
        self._execute_processing(overwrite=False, out_dir=output_dir)

    def _overwrite_originals(self):
        if messagebox.askyesno("Confirm Overwrite", "This will permanently overwrite the original file(s).\nThis action cannot be undone. Are you sure?", parent=self.app_context.root):
            self._execute_processing(overwrite=True)

    def _execute_processing(self, overwrite: bool, out_dir: str = None):
        checked_ids = self.app_context.get_checked_item_ids()
        is_batch = len(checked_ids) > 1

        if checked_ids:
            items_to_process = self.app_context.get_items_data(checked_ids)
        else:
            active_id = self.app_context.get_active_item_id()
            if not active_id:
                self.app_context.show_info("No Selection", "Please check items or select a single item to process.")
                return
            items_to_process = self.app_context.get_items_data([active_id])
        
        if not items_to_process: return
        if not overwrite and out_dir: os.makedirs(out_dir, exist_ok=True)
            
        target_w = self.settings["width"].get()
        target_h = self.settings["height"].get()
        
        def processing_task(item, context):
            context.update_status(f"Processing {item['filename']}...")
            with Image.open(item["filepath"]) as img:
                if is_batch:
                    processed_image = self._smart_crop_and_resize(img.copy(), target_w, target_h)
                else:
                    processed_image = self._process_single_from_canvas(img.copy(), target_w, target_h)

            target_path = item["filepath"] if overwrite else os.path.join(out_dir, item["filename"])
            processed_image.save(target_path)
            
            if overwrite:
                context.clear_image_cache([item["item_id"]])
                context.refresh_ui_items([item["item_id"]], update_thumbnail=True)
            return True

        self.app_context.run_job(processing_task, items_to_process, "Image Processing")

    def _get_algorithm(self):
        algo_map = {"Nearest": Image.Resampling.NEAREST, "Bilinear": Image.Resampling.BILINEAR, "Bicubic": Image.Resampling.BICUBIC, "Lanczos": Image.Resampling.LANCZOS}
        return algo_map.get(self.settings["algorithm"].get(), Image.Resampling.LANCZOS)

    def _process_single_from_canvas(self, image: Image.Image, target_w: int, target_h: int) -> Image.Image:
        if not self.interactive_canvas: raise ValueError("Canvas not initialized")
        crop_coords = self.interactive_canvas.get_crop_geometry()
        cropped_image = image.crop(crop_coords)
        if target_w > 0 and target_h > 0:
            return cropped_image.resize((target_w, target_h), resample=self._get_algorithm())
        return cropped_image

    def _smart_crop_and_resize(self, image: Image.Image, target_w: int, target_h: int) -> Image.Image:
        target_ratio = target_w / target_h
        img_w, img_h = image.size
        img_ratio = img_w / img_h

        if target_ratio > img_ratio:
            new_h = img_w / target_ratio
            top = (img_h - new_h) / 2
            box = (0, top, img_w, top + new_h)
        else:
            new_w = img_h * target_ratio
            left = (img_w - new_w) / 2
            box = (left, 0, left + new_w, img_h)
            
        cropped_image = image.crop(box)
        return cropped_image.resize((target_w, target_h), resample=self._get_algorithm())

    def create_workspace(self, parent_frame: tk.Frame) -> tk.Widget:
        if not self.interactive_canvas:
            self.interactive_canvas = InteractiveCanvas(parent_frame, self._update_ui_from_canvas, self._request_save_state)
        return self.interactive_canvas

    def on_image_selected(self, pil_image: Image.Image | None):
        if not self.app_context: return
            
        if pil_image:
            self.original_size_var.set(f"Original: {pil_image.width} x {pil_image.height} px")
        else:
            self.original_size_var.set("Original: -")
        
        if self.interactive_canvas:
            self.interactive_canvas.load_image(pil_image)
            
            active_id = self.app_context.get_active_item_id()
            if active_id:
                saved_data = self.app_context.annotation_manager.get_data(active_id, self.name)
                if saved_data and "crop_box" in saved_data:
                    self.interactive_canvas.set_crop_geometry(saved_data["crop_box"])
                else:
                    self.interactive_canvas.set_crop_box_to_full_image()
            else:
                 self.interactive_canvas.set_crop_box_to_full_image()

    def process_image(self, image: Image.Image) -> Image.Image:
        target_w, target_h = self.settings["width"].get(), self.settings["height"].get()
        return self._process_single_from_canvas(image, target_w, target_h)

    def _update_ui_from_canvas(self, real_width, real_height):
        self._is_programmatic_update = True
        self.settings["width"].set(int(real_width))
        self.settings["height"].set(int(real_height))
        
        # When user drags, unlock aspect ratio and set preset to Freeform
        self.settings["aspect_lock"].set(False)
        self.settings["aspect_preset"].set("Freeform")
        
        self._is_programmatic_update = False

    def _on_ui_value_changed(self, changed_field: str):
        if self._is_programmatic_update: return
        
        if not self.settings["aspect_lock"].get():
            self._request_save_state()
            return
            
        try:
            w, h = self.settings["width"].get(), self.settings["height"].get()
            rw, rh = self.settings["ratio_w"].get(), self.settings["ratio_h"].get()
            
            if rw > 0 and rh > 0:
                ratio = rw / rh
                self._is_programmatic_update = True
                if changed_field == "width":
                    self.settings["height"].set(int(w / ratio))
                elif changed_field == "height":
                    self.settings["width"].set(int(h * ratio))
                self._is_programmatic_update = False
        except (ValueError, tk.TclError):
            pass 
        finally:
            self._is_programmatic_update = False
            self._request_save_state()

    def _on_lock_toggled(self):
        is_locked = self.settings["aspect_lock"].get()
        if not is_locked:
            self.settings["aspect_preset"].set("Freeform")
        else: # If user re-locks, apply the current preset
             self._on_preset_selected(self.settings["aspect_preset"].get())

    def _on_preset_selected(self, choice: str):
        ratio = self.aspect_ratios.get(choice)
        if ratio is None: # Freeform
            self.settings["aspect_lock"].set(False)
        else:
            self.settings["aspect_lock"].set(True)
            self.settings["ratio_w"].set(ratio[0])
            self.settings["ratio_h"].set(ratio[1])
            self._on_ui_value_changed("width") # Recalculate based on width

    def _on_apply_size_clicked(self):
        if self.interactive_canvas:
            try:
                w = self.settings["width"].get()
                h = self.settings["height"].get()
                self.interactive_canvas.update_crop_box_from_real_size(w, h)
                self._request_save_state()
            except (ValueError, tk.TclError):
                self.app_context.show_error("Invalid Size", "Please enter valid numbers for width and height.")


    def _on_reset_clicked(self):
        if self.interactive_canvas:
            self.interactive_canvas.set_crop_box_to_full_image()
            self._request_save_state()

def register():
    return ResizeCropPlugin()