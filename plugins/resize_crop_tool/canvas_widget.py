# plugins/resize_crop_tool/canvas_widget.py
import tkinter as tk
from PIL import Image, ImageTk

class InteractiveCanvas(tk.Canvas):
    """
    An interactive canvas for image cropping.

    This widget displays an image and provides a draggable and resizable
    cropping rectangle. It handles user input via mouse and keyboard,
    displays real-time crop dimensions, and communicates the final
    crop geometry back to the parent plugin via a callback.
    """
    def __init__(self, parent, update_callback, save_callback):
        super().__init__(parent, background="#505050", highlightthickness=0)
        self.update_callback = update_callback
        # NEW: Callback to notify the plugin that the state should be saved.
        self.save_callback = save_callback

        # Image and scaling state
        self.original_image = None
        self.display_image = None
        self.photo_image = None
        self.scale_factor = 1.0
        self.img_offset_x = 0
        self.img_offset_y = 0

        # Crop box state
        self.crop_box_coords = [0, 0, 0, 0]

        # Dragging state
        self.drag_info = {}

        self.bind_events()

    def bind_events(self):
        """Binds all necessary mouse and keyboard events."""
        self.bind("<Configure>", self._on_resize)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_mouse_move)
        self.bind("<KeyPress>", self._on_key_press)

    def load_image(self, pil_image: Image.Image | None):
        """Loads a new PIL image, fits it to the canvas, and resets the crop box."""
        self.original_image = pil_image
        self._fit_image_to_canvas()
        # Important: Don't reset the crop box here. The plugin will decide whether
        # to reset it or load a saved state.
        # self.set_crop_box_to_full_image()

    def set_crop_box_to_full_image(self):
        """Resets the crop box to cover the entire visible image."""
        if self.display_image:
            w, h = self.display_image.size
            self.crop_box_coords = [0, 0, w, h]
        else:
            self.crop_box_coords = [0, 0, 0, 0]
        self._redraw()
        self._notify_ui_update()

    # NEW: Method to set the crop box from saved, real-pixel coordinates.
    def set_crop_geometry(self, real_coords: list[int]):
        """Sets the crop box based on coordinates scaled to the original image."""
        if not self.display_image or self.scale_factor == 0:
            return
        
        # Scale the real coordinates to the currently displayed image size
        canvas_coords = [int(c * self.scale_factor) for c in real_coords]
        self.crop_box_coords = canvas_coords
        self._redraw()
        self._notify_ui_update()


    def update_crop_box_from_real_size(self, real_width, real_height):
        """Updates the crop box based on REAL pixel dimensions from the plugin."""
        if not self.display_image or self.scale_factor == 0: return
        
        canvas_width = real_width * self.scale_factor
        canvas_height = real_height * self.scale_factor
        
        center_x = (self.crop_box_coords[0] + self.crop_box_coords[2]) / 2
        center_y = (self.crop_box_coords[1] + self.crop_box_coords[3]) / 2
        
        self._place_box(center_x, center_y, canvas_width, canvas_height)
        self._redraw()

    def _place_box(self, center_x, center_y, width, height):
        """Positions a box of a given size, centered and clamped to boundaries."""
        if not self.display_image: return
        img_w, img_h = self.display_image.size
        
        x1, y1 = center_x - width / 2, center_y - height / 2
        if x1 < 0: x1 = 0
        if y1 < 0: y1 = 0
        
        x2, y2 = x1 + width, y1 + height
        if x2 > img_w: x1 = img_w - width
        if y2 > img_h: y1 = img_h - height
            
        self.crop_box_coords = [max(0, x1), max(0, y1), min(img_w, x1+width), min(img_h, y1+height)]

    def get_crop_geometry(self):
        """Returns crop coordinates scaled to the original image's dimensions."""
        if self.scale_factor == 0: return [0, 0, 0, 0]
        return [int(c / self.scale_factor) for c in self.crop_box_coords]

    def _fit_image_to_canvas(self):
        """Resizes the source image to fit within the canvas widget."""
        self.delete("all")
        if not self.original_image:
            self.display_image = self.photo_image = None
            return

        canvas_w, canvas_h = self.winfo_width(), self.winfo_height()
        if canvas_w < 2 or canvas_h < 2: return

        img_w, img_h = self.original_image.size
        if img_w == 0 or img_h == 0: return

        self.scale_factor = min((canvas_w-10) / img_w, (canvas_h-10) / img_h)
        new_w, new_h = int(img_w * self.scale_factor), int(img_h * self.scale_factor)
        self.display_image = self.original_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.photo_image = ImageTk.PhotoImage(self.display_image)

    def _redraw(self):
        """Clears and redraws all elements on the canvas."""
        self.delete("all")
        if not self.photo_image or not self.display_image: return

        img_w, img_h = self.display_image.size
        canvas_w, canvas_h = self.winfo_width(), self.winfo_height()
        
        self.img_offset_x = (canvas_w - img_w) / 2
        self.img_offset_y = (canvas_h - img_h) / 2
        self.create_image(self.img_offset_x, self.img_offset_y, image=self.photo_image, anchor="nw", tags="image")

        x1, y1, x2, y2 = self.crop_box_coords
        self.create_rectangle(self.img_offset_x, self.img_offset_y, self.img_offset_x + img_w, self.img_offset_y + y1, fill="black", stipple="gray50", outline="")
        self.create_rectangle(self.img_offset_x, self.img_offset_y + y2, self.img_offset_x + img_w, self.img_offset_y + img_h, fill="black", stipple="gray50", outline="")
        self.create_rectangle(self.img_offset_x, self.img_offset_y + y1, self.img_offset_x + x1, self.img_offset_y + y2, fill="black", stipple="gray50", outline="")
        self.create_rectangle(self.img_offset_x + x2, self.img_offset_y + y1, self.img_offset_x + img_w, self.img_offset_y + y2, fill="black", stipple="gray50", outline="")
        
        self.create_rectangle(self.img_offset_x + x1, self.img_offset_y + y1, self.img_offset_x + x2, self.img_offset_y + y2, outline="white", width=2, tags="crop_box")
        
        handle_size = 4
        positions = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
        coords = [(x1, y1), ((x1+x2)/2, y1), (x2, y1), (x2, (y1+y2)/2), (x2, y2), ((x1+x2)/2, y2), (x1, y2), (x1, (y1+y2)/2)]
        for pos, (px, py) in zip(positions, coords):
            self.create_rectangle(self.img_offset_x + px-handle_size, self.img_offset_y + py-handle_size, self.img_offset_x + px+handle_size, self.img_offset_y + py+handle_size, fill="white", outline="black", tags=(f"handle_{pos}", "handle"))

    def _on_resize(self, event):
        """Called when the canvas widget changes size."""
        self._fit_image_to_canvas()
        self.set_crop_box_to_full_image()

    def _on_press(self, event):
        """Initiates a drag operation (move, resize, or new box)."""
        self.focus_set()
        item = self.find_closest(event.x, event.y)
        if not item: return
        tags = self.gettags(item[0])
        
        mode = next((t.split('_')[1] for t in tags if t.startswith("handle_")), None)
        
        if not mode:
            try:
                x1,y1,x2,y2 = self.bbox("crop_box")
                if x1 <= event.x <= x2 and y1 <= event.y <= y2: mode = "move"
                elif "image" in tags: mode = "new_box"
            except (TypeError, tk.TclError): pass

        if mode:
            start_x_img, start_y_img = event.x - self.img_offset_x, event.y - self.img_offset_y
            self.drag_info = { "start_x": start_x_img, "start_y": start_y_img,
                "mode": mode, "initial_box": list(self.crop_box_coords) }
            if mode == "new_box":
                self.crop_box_coords = [start_x_img, start_y_img, start_x_img, start_y_img]

    def _on_drag(self, event):
        """Handles moving/resizing the crop box and displaying dimensions."""
        if not self.drag_info or not self.display_image: return
        
        curr_x_img, curr_y_img = event.x - self.img_offset_x, event.y - self.img_offset_y
        dx, dy = curr_x_img - self.drag_info["start_x"], curr_y_img - self.drag_info["start_y"]
        x1, y1, x2, y2 = self.drag_info["initial_box"]
        mode = self.drag_info["mode"]

        if mode == 'move':
            box_w, box_h = x2 - x1, y2 - y1
            new_x1, new_y1 = x1 + dx, y1 + dy
            img_w, img_h = self.display_image.size
            new_x1 = max(0, min(new_x1, img_w - box_w))
            new_y1 = max(0, min(new_y1, img_h - box_h))
            self.crop_box_coords = [new_x1, new_y1, new_x1 + box_w, new_y1 + box_h]
        elif mode == 'new_box':
            start_x, start_y = self.drag_info["start_x"], self.drag_info["start_y"]
            self.crop_box_coords = [min(start_x, curr_x_img), min(start_y, curr_y_img), max(start_x, curr_x_img), max(start_y, curr_y_img)]
        else: # Resize mode
            if 'n' in mode: y1 += dy
            if 's' in mode: y2 += dy
            if 'w' in mode: x1 += dx
            if 'e' in mode: x2 += dx
            self.crop_box_coords = [x1, y1, x2, y2]
        
        self._clamp_and_redraw()
        self._draw_info_text(event.x, event.y)

    def _on_release(self, event):
        self.drag_info = {}
        self.delete("info_text")
        self._notify_ui_update()
        # NEW: Trigger state save after user finishes interaction.
        if self.save_callback:
            self.save_callback()


    def _on_mouse_move(self, event):
        cursor_map = {'nw': 'size_nw_se', 'ne': 'size_ne_sw', 'sw': 'size_ne_sw', 'se': 'size_nw_se', 'n': 'sb_v_double_arrow', 's': 'sb_v_double_arrow', 'w': 'sb_h_double_arrow', 'e': 'sb_h_double_arrow', 'move': 'fleur'}
        item = self.find_closest(event.x, event.y)
        new_cursor = ""
        if item:
            tags = self.gettags(item[0])
            mode = next((t.split('_')[1] for t in tags if t.startswith("handle_")), None)
            if not mode:
                try:
                    x1,y1,x2,y2 = self.bbox("crop_box")
                    if x1 <= event.x <= x2 and y1 <= event.y <= y2: mode = "move"
                except (TypeError, tk.TclError): pass
            new_cursor = cursor_map.get(mode, "")
        if self.cget("cursor") != new_cursor: self.config(cursor=new_cursor)
    
    def _on_key_press(self, event):
        if not self.display_image: return
        nudge = 10 if "Shift" in event.state.__str__() else 1
        x1, y1, x2, y2 = self.crop_box_coords
        box_w, box_h = x2 - x1, y2 - y1
        img_w, img_h = self.display_image.size
        
        key_map = {'Up': (0, -nudge), 'Down': (0, nudge), 'Left': (-nudge, 0), 'Right': (nudge, 0)}
        if event.keysym in key_map:
            dx, dy = key_map[event.keysym]
            new_x1 = max(0, min(x1 + dx, img_w - box_w))
            new_y1 = max(0, min(y1 + dy, img_h - box_h))
            self.crop_box_coords = [new_x1, new_y1, new_x1 + box_w, new_y1 + box_h]
            self._redraw()
            self._notify_ui_update()
            # NEW: Trigger state save after user finishes interaction.
            if self.save_callback:
                self.save_callback()

    def _clamp_and_redraw(self):
        x1, y1, x2, y2 = self.crop_box_coords
        if not self.display_image: return
        img_w, img_h = self.display_image.size
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img_w, x2), min(img_h, y2)
        if y1 >= y2: y1 = y2 - 1
        if x1 >= x2: x1 = x2 - 1
        self.crop_box_coords = [x1, y1, x2, y2]
        self._redraw()
        
    def _draw_info_text(self, x, y):
        self.delete("info_text")
        if self.scale_factor == 0: return
        canvas_w = self.crop_box_coords[2] - self.crop_box_coords[0]
        canvas_h = self.crop_box_coords[3] - self.crop_box_coords[1]
        real_w, real_h = int(canvas_w / self.scale_factor), int(canvas_h / self.scale_factor)
        text = f"{real_w} x {real_h}"
        self.create_text(x + 15, y, text=text, anchor="w", fill="white", font=("Segoe UI", 9), tags="info_text")

    def _notify_ui_update(self):
        if self.update_callback and self.scale_factor > 0:
            canvas_w = self.crop_box_coords[2] - self.crop_box_coords[0]
            canvas_h = self.crop_box_coords[3] - self.crop_box_coords[1]
            real_width, real_height = canvas_w / self.scale_factor, canvas_h / self.scale_factor
            self.update_callback(real_width, real_height)