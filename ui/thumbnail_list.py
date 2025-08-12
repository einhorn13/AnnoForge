# ui/thumbnail_list.py
import customtkinter as ctk
import tkinter as tk
import sys
from .thumbnail_widget import ThumbnailItemWidget
from .selection_model import SelectionModel
from events import EventBus
import utils
import threading
import os
import pyperclip

class ThumbnailListView(ctk.CTkScrollableFrame):
    def __init__(self, parent: ctk.CTkFrame, event_bus: EventBus):
        super().__init__(parent)
        self.event_bus = event_bus
        self.app_context = None
        self.widgets = {}
        self.widget_ids_in_order = []
        self.reflow_job_id = None
        self.last_known_cols = -1
        self.selection_model = SelectionModel(self.event_bus)
        self.context_menu_item_id = None
        
        self.no_items_label = ctk.CTkLabel(self, text="No images loaded or no items match the current filter.")
        
        self._set_appearance()
        self._setup_hotkeys()
        self.context_menu = self._create_context_menu()
        
        self.bind("<Configure>", self._debounce_reflow)
        self.bind("<Button-1>", lambda e: self.selection_model.clear() if e.widget == self else None)
        
        self.event_bus.subscribe("state:files_changed", self._create_all_widgets)
        self.event_bus.subscribe("state:filter_changed", self._apply_filter)
        self.event_bus.subscribe("ui:select_all_clicked", self.selection_model.select_all)
        self.event_bus.subscribe("ui:deselect_all_clicked", self.selection_model.clear)
        self.event_bus.subscribe("state:selection_changed", self._update_widget_selections)
        self.event_bus.subscribe("state:active_item_changed", self._on_active_item_changed)
        self.event_bus.subscribe("ui:update_prompt_display", self.update_items_prompt_type)
        self.event_bus.subscribe("ui:refresh_thumbnail", self.refresh_thumbnail)
        self.event_bus.subscribe("<<ThemeChanged>>", self._set_appearance)

    def _set_appearance(self, event=None):
        fg_color = ("#f0f0f0" if ctk.get_appearance_mode() == "Light" else "#242424")
        self.configure(fg_color=fg_color)

    def _setup_hotkeys(self):
        self.bind_all("<Control-a>", self._select_all_hotkey, "+")
        self.bind_all("<Control-A>", self._select_all_hotkey, "+")
        self.bind_all("<Delete>", self._exclude_hotkey, "+")
        self.bind_all("<F2>", self._edit_caption_hotkey, "+")

    def _create_context_menu(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Copy Caption", command=self._copy_caption)
        menu.add_command(label="Paste Caption", command=self._paste_caption)
        menu.add_separator()
        menu.add_command(label="Show in Explorer/Finder", command=self._show_in_explorer)
        menu.add_command(label="Exclude from Project (Not Implemented)", command=self._exclude_hotkey, state="disabled")
        return menu

    def _show_context_menu(self, event):
        widget = event.widget
        while widget and not hasattr(widget, 'item_data'):
            widget = widget.master
        
        if hasattr(widget, 'item_data'):
            self.context_menu_item_id = widget.item_data['item_id']
            if not self.selection_model.is_checked(self.context_menu_item_id):
                 self.selection_model.set_active(self.context_menu_item_id)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _create_all_widgets(self, all_items_data: list[dict]):
        for widget in self.widgets.values():
            widget.destroy()
        self.widgets.clear()
        
        self.selection_model.clear()
        self.last_known_cols = -1 

        if not all_items_data:
            self._apply_filter([])
            return

        prompt_types = []
        if self.app_context and self.app_context.plugin_manager.model_assistants:
            active_model_plugin = self.app_context.plugin_manager.model_assistants[0]
            prompt_types = list(active_model_plugin.get_supported_prompts().keys())

        widget_map = {}
        for item in all_items_data:
            item_id = item['item_id']
            widget = ThumbnailItemWidget(self, item, self.app_context, self.selection_model, prompt_types, width=210, height=270)
            
            widget.bind("<Button-3>", self._show_context_menu)
            for child in widget.winfo_children():
                child.bind("<Button-3>", self._show_context_menu)

            self.widgets[item_id] = widget
            widget_map[item_id] = (widget, item['filepath'])
            widget.grid_remove() 
        
        self._batch_load_thumbnails(widget_map)
        self._apply_filter(all_items_data)

    def _apply_filter(self, filtered_items_data: list[dict]):
        self.widget_ids_in_order = [item['item_id'] for item in filtered_items_data]
        visible_ids = set(self.widget_ids_in_order)
        
        self.selection_model.update_item_order(self.widget_ids_in_order)
        
        if not visible_ids:
            self.no_items_label.grid(row=0, column=0, pady=20, padx=20)
        else:
            self.no_items_label.grid_remove()

        for item_id, widget in self.widgets.items():
            if item_id not in visible_ids:
                widget.grid_remove()
        
        self._debounce_reflow()

    def _batch_load_thumbnails(self, widget_map):
        def task():
            image_loader = utils.ImageLoader()
            for item_id, (widget, path) in widget_map.items():
                if not widget.winfo_exists(): continue
                thumb = image_loader.get_thumbnail(path, (200, 150))
                if thumb and self.app_context:
                    self.app_context.run_in_ui_thread(lambda w=widget, t=thumb: w.set_thumbnail(t))
        threading.Thread(target=task, daemon=True).start()

    def _debounce_reflow(self, event=None):
        if self.reflow_job_id: self.after_cancel(self.reflow_job_id)
        self.reflow_job_id = self.after(100, self._reflow_widgets)

    def _reflow_widgets(self):
        canvas_width = self.winfo_width()
        if canvas_width < 2 or not self.widget_ids_in_order:
            # If no items are visible, ensure the scrollbar is reset
            self.update_idletasks()
            return
        
        padding = 10
        item_width = 210
        cols = max(1, (canvas_width - padding) // (item_width + padding))
        
        if cols == self.last_known_cols and self.winfo_children():
             return 
        self.last_known_cols = cols

        for i in range(len(self.grid_slaves())):
            self.grid_columnconfigure(i, weight=0)
            self.grid_rowconfigure(i, weight=0)

        for i in range(cols):
            self.grid_columnconfigure(i, weight=1)

        for i, item_id in enumerate(self.widget_ids_in_order):
            if item_id in self.widgets:
                widget = self.widgets[item_id]
                row, col = divmod(i, cols)
                widget.grid(row=row, column=col, padx=padding/2, pady=padding/2, sticky="nsew")

        # FIXED: Use the correct, public method to force geometry updates.
        self.update_idletasks()

    def _update_widget_selections(self, checked_ids: list[str]):
        checked_set = set(checked_ids)
        for item_id, widget in self.widgets.items():
            if widget.winfo_ismapped():
                widget.set_checked(item_id in checked_set)
        
    def _on_active_item_changed(self, active_id: str | None):
        for item_id, widget in self.widgets.items():
            widget.set_active(item_id == active_id)
        if active_id and active_id in self.widgets:
            self.widgets[active_id].focus_set()

    def update_items_prompt_type(self, item_ids: list[str], new_prompt_type: str):
        for item_id in item_ids:
            if item_id in self.widgets:
                self.widgets[item_id].prompt_type_var.set(new_prompt_type)
            
    def update_item_caption(self, item_id: str):
        if item_id in self.widgets:
            self.widgets[item_id].update_caption_display()
        
    def refresh_thumbnail(self, item_id: str):
        if item_id in self.widgets:
            self.widgets[item_id].load_thumbnail()

    def _select_all_hotkey(self, event):
        self.selection_model.select_all()
        return "break"
    
    def _exclude_hotkey(self, event=None):
        pass
    
    def _edit_caption_hotkey(self, event=None):
        if self.app_context and self.app_context.app_state:
            active_id = self.app_context.app_state.active_id
            if active_id and active_id in self.widgets:
                self.widgets[active_id]._start_editing()
    
    def _copy_caption(self):
        if self.context_menu_item_id and (item := self.app_context.data_provider.get_file_by_id(self.context_menu_item_id)):
            pyperclip.copy(item.get('caption', ''))
    
    def _paste_caption(self):
        if self.context_menu_item_id:
            self.event_bus.publish("ui:caption_edited", self.context_menu_item_id, pyperclip.paste())

    def _show_in_explorer(self):
        if self.context_menu_item_id and (item := self.app_context.data_provider.get_file_by_id(self.context_menu_item_id)):
            filepath = item['filepath']
            if os.name == 'nt':
                os.startfile(os.path.dirname(filepath))
            elif sys.platform == "darwin":
                os.system(f'open "{os.path.dirname(filepath)}"')
            else:
                os.system(f'xdg-open "{os.path.dirname(filepath)}"')