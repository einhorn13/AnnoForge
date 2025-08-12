# ui/thumbnail_widget.py
import customtkinter as ctk
from PIL import Image
import threading
import utils

class ThumbnailItemWidget(ctk.CTkFrame):
    """A card-like widget for a single image, handling its own state and display."""
    def __init__(self, parent, item_data, app_context, selection_model, prompt_types: list, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.item_data = item_data
        self.app_context = app_context
        self.selection_model = selection_model
        self.prompt_types = prompt_types
        self.image_loader = utils.ImageLoader()
        
        self.is_hovered = False
        self.is_active = False
        self.is_checked = ctk.BooleanVar(value=False)
        self.prompt_type_var = ctk.StringVar(value=item_data.get("prompt_type", ""))
        self.photo_image = None
        
        self._initialize_colors()
        self._create_widgets()
        self.load_thumbnail()
        self._bind_events()
        self.update_style()
    
    def _initialize_colors(self):
        """Get all required colors from the theme manager at once."""
        theme = ctk.ThemeManager.theme
        self.color_bg = self.cget("fg_color")
        self.color_bg_checked = theme["CTkFrame"]["top_fg_color"]
        self.color_border = theme["CTkFrame"]["border_color"]
        self.color_border_hover = theme["CTkButton"]["border_color"]
        self.color_border_active = theme["CTkButton"]["fg_color"]
    
    def _create_widgets(self):
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.check_button = ctk.CTkCheckBox(self, variable=self.is_checked, text="", width=20, height=20,
                                            command=self._on_check_toggle)
        self.check_button.place(x=8, y=8, anchor="nw")

        self.preview_label = ctk.CTkLabel(self, text="Loading...", anchor="center", fg_color="#333333")
        self.preview_label.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        prompt_frame = ctk.CTkFrame(self, fg_color="transparent")
        prompt_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(5,0))
        
        if self.prompt_types:
            self.prompt_combo = ctk.CTkComboBox(prompt_frame, variable=self.prompt_type_var, values=self.prompt_types, state="readonly", height=10)
            self.prompt_combo.pack(side="left", fill="x", expand=True)
            self.prompt_combo.bind("<<ComboboxSelected>>", self._on_prompt_change)
        
        self.filename_label = ctk.CTkLabel(self, text=self.item_data['filename'], anchor="w", font=("Segoe UI", 8, "bold"))
        self.filename_label.grid(row=2, column=0, sticky="ew", padx=5)

        self.caption_display = ctk.CTkLabel(self, text=self.get_caption_preview(), anchor="nw", justify="left", wraplength=180, font=("Segoe UI", 8))
        self.caption_display.grid(row=3, column=0, sticky="nsew", padx=5, pady=(0, 5))
        
        self.caption_editor = ctk.CTkTextbox(self, height=3, wrap="word", font=("Segoe UI", 8), border_width=1)

    def _bind_events(self):
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._bind_scrolling(self)

        for widget in self.winfo_children():
            widget.bind("<Button-1>", self._on_click)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            self._bind_scrolling(widget)

        self.caption_display.bind("<Double-Button-1>", self._start_editing)
        self.caption_editor.bind("<Escape>", self._cancel_editing)
        self.caption_editor.bind("<FocusOut>", self._save_editing)

    def _bind_scrolling(self, widget):
        widget.bind("<MouseWheel>", self._on_mouse_scroll, add=True)
        widget.bind("<Button-4>", self._on_mouse_scroll, add=True)
        widget.bind("<Button-5>", self._on_mouse_scroll, add=True)

    def _on_mouse_scroll(self, event):
        """Propagates scroll events to the parent canvas with increased speed."""
        if hasattr(self.master, '_parent_canvas'):
            canvas = self.master._parent_canvas
            scroll_multiplier = 12
            if event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-scroll_multiplier, "units")
            elif event.num == 5 or event.delta < 0:
                canvas.yview_scroll(scroll_multiplier, "units")

    def load_thumbnail(self):
        def task():
            thumb = self.image_loader.get_thumbnail(self.item_data['filepath'], (200, 200))
            if thumb and self.winfo_exists() and self.app_context:
                self.app_context.run_in_ui_thread(lambda: self.set_thumbnail(thumb))
        threading.Thread(target=task, daemon=True).start()

    def set_thumbnail(self, image: Image.Image):
        self.photo_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        self.preview_label.configure(image=self.photo_image, text="")

    def get_caption_preview(self):
        content = self.item_data.get("caption", "").strip()
        if not content: return "(no caption)"
        lines = content.split('\n')
        preview = '\n'.join(lines[:6])
        if len(lines) > 6:
            preview += '...'
        return preview

    def update_caption_display(self):
        if not self.app_context or not self.app_context.data_provider: return
        item_data = self.app_context.data_provider.get_file_by_id(self.item_data['item_id'])
        if item_data:
            self.item_data['caption'] = item_data.get('caption', '')
            self.caption_display.configure(text=self.get_caption_preview())

    def set_active(self, is_active: bool):
        if self.is_active != is_active:
            self.is_active = is_active
            self.update_style()

    def set_checked(self, is_checked: bool):
        if self.is_checked.get() != is_checked:
            self.is_checked.set(is_checked)
        self.update_style()

    def update_style(self):
        border_width = 1
        bg_color = self.color_bg
        border_color = self.color_border

        if self.is_checked.get() or self.is_active:
            bg_color = self.color_bg_checked
            border_color = self.color_border_active
            if self.is_active:
                border_width = 2
            else:
                border_width = 1
        elif self.is_hovered:
            border_color = self.color_border_hover

        self.configure(fg_color=bg_color, border_color=border_color, border_width=border_width)

    def _on_enter(self, event=None):
        self.is_hovered = True
        self.update_style()

    def _on_leave(self, event=None):
        self.is_hovered = False
        self.update_style()

    def _on_click(self, event):
        if event.widget != self.check_button:
            self.selection_model.handle_click(self.item_data['item_id'], event.state)

    def _on_check_toggle(self):
        if self.is_checked.get():
            self.selection_model.add_to_selection([self.item_data['item_id']])
        else:
            self.selection_model.remove_from_selection([self.item_data['item_id']])
    
    def _on_prompt_change(self, event=None):
        new_type = self.prompt_type_var.get()
        if self.app_context:
            self.app_context.event_bus.publish("ui:prompt_type_changed", self.item_data['item_id'], new_type)

    def _start_editing(self, event=None):
        self.caption_display.grid_remove()
        self.caption_editor.grid(row=3, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.caption_editor.delete("1.0", "end")
        self.caption_editor.insert("1.0", self.item_data.get("caption", ""))
        self.caption_editor.focus_set()
        return "break"

    def _save_editing(self, event=None):
        if self.caption_editor.winfo_ismapped():
            new_content = self.caption_editor.get("1.0", "end-1c").strip()
            if self.app_context:
                self.app_context.event_bus.publish("ui:caption_edited", self.item_data['item_id'], new_content)
        self._cancel_editing()
        return "break"

    def _cancel_editing(self, event=None):
        self.caption_editor.grid_remove()
        self.caption_display.grid(row=3, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.focus_set()
        return "break"