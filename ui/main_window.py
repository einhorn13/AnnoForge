# ui/main_window.py
import customtkinter as ctk
import tkinter as tk
from tkinter import Event
from .thumbnail_list import ThumbnailListView
from .log_viewer import LogViewer
from .task_queue_viewer import TaskQueueViewer
from events import EventBus
from plugins.api import ImageProcessorPlugin, BatchOperationPlugin
from PIL import Image
import os
import logging
import utils

class AppUI:
    def __init__(self, root: ctk.CTk, event_bus: EventBus):
        self.root = root; self.event_bus = event_bus; self.interactive_widgets = []
        self.app_context = None; self.image_processors = []; self.active_plugin = None
        self.image_loader = utils.ImageLoader()
        self.model_path_map = {}
        
        self._setup_ui()
        self._subscribe_to_events()
        self.root.after(100, self._set_theme_colors)
        
    def _setup_ui(self):
        self.root.title("AnnoForge - No Project Loaded"); self.root.geometry("1500x950")
        self.main_menu = tk.Menu(self.root); self.root.config(menu=self.main_menu)
        file_menu = tk.Menu(self.main_menu, tearoff=0)
        self.main_menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Project...", command=lambda: self.event_bus.publish("ui:new_project_clicked"))
        file_menu.add_command(label="Open Project...", command=lambda: self.event_bus.publish("ui:open_project_clicked"))
        file_menu.add_separator(); file_menu.add_command(label="Exit", command=self.root.quit)

        self.root.grid_columnconfigure(0, weight=1); self.root.grid_rowconfigure(1, weight=1)
        top_toolbar = ctk.CTkFrame(self.root); top_toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,0))
        self._create_top_toolbar(top_toolbar)
        
        self.main_paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=8)
        self.main_paned_window.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        left_pane = ctk.CTkFrame(self.main_paned_window, fg_color="transparent")
        self.main_paned_window.add(left_pane, width=900, stretch="always")
        self._create_left_pane(left_pane)

        right_main_frame = ctk.CTkFrame(self.main_paned_window, fg_color="transparent")
        right_main_frame.grid_columnconfigure(1, weight=1); right_main_frame.grid_rowconfigure(0, weight=1)
        self.main_paned_window.add(right_main_frame, width=600, stretch="always")

        self.plugin_toolbar = ctk.CTkFrame(right_main_frame, width=50)
        self.plugin_toolbar.grid(row=0, column=0, sticky="ns", pady=10, padx=(0,5))
        
        workspace_pane = ctk.CTkFrame(right_main_frame, fg_color="transparent")
        workspace_pane.grid(row=0, column=1, sticky="nsew", pady=10)
        self._create_workspace(workspace_pane)
        
        status_frame = ctk.CTkFrame(self.root); status_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        self._create_status_and_queue_controls(status_frame)

    def _subscribe_to_events(self):
        bus = self.event_bus
        bus.subscribe("ui:set_enabled", self.set_ui_enabled)
        bus.subscribe("state:status_changed", lambda msg: self.status_var.set(msg))
        bus.subscribe("state:progress_changed", lambda val: self.progress_var.set(val))
        bus.subscribe("queue:updated", self._update_queue_controls)
        bus.subscribe("queue:started", lambda: self._set_queue_state("running"))
        bus.subscribe("queue:paused", lambda: self._set_queue_state("paused"))
        bus.subscribe("queue:resumed", lambda: self._set_queue_state("running"))
        bus.subscribe("queue:finished", lambda: self._set_queue_state("idle"))
        bus.subscribe("state:selection_changed", self._update_selection_count)
        bus.subscribe("state:active_item_changed", self.on_active_item_changed_event)
        
        self.root.bind("<<ThemeChanged>>", self._set_theme_colors, add="+")

    def _set_theme_colors(self, event: Event | None = None):
        theme_data = ctk.ThemeManager.theme["CTkFrame"]
        bg_color = theme_data["fg_color"][0] if ctk.get_appearance_mode() == "Light" else theme_data["fg_color"][1]

        self.main_paned_window.configure(bg=bg_color)
        if hasattr(self, 'plugin_paned_window'):
            self.plugin_paned_window.configure(bg=bg_color)

    def _create_top_toolbar(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(parent, text="🔍 Filter:").grid(row=0, column=0, padx=(10,5), pady=10)
        self.search_var = ctk.StringVar(); self.search_var.trace_add("write", lambda *_: self._publish_search_options())
        search_entry = ctk.CTkEntry(parent, textvariable=self.search_var, placeholder_text="Filter..."); search_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=10); self.interactive_widgets.append(search_entry)
        self.regex_var = ctk.BooleanVar(); self.regex_checkbox = ctk.CTkCheckBox(parent, text="RegEx", variable=self.regex_var, command=self._publish_search_options); self.regex_checkbox.grid(row=0, column=2, padx=5); self.interactive_widgets.append(self.regex_checkbox)
        self.invert_var = ctk.BooleanVar(); self.invert_checkbox = ctk.CTkCheckBox(parent, text="Invert", variable=self.invert_var, command=self._publish_search_options); self.invert_checkbox.grid(row=0, column=3, padx=5); self.interactive_widgets.append(self.invert_checkbox)
        ctk.CTkLabel(parent, text="Set Prompt for Checked:").grid(row=0, column=4, padx=(20, 5), pady=10)
        self.batch_prompt_var = ctk.StringVar(); self.prompt_combo = ctk.CTkComboBox(parent, variable=self.batch_prompt_var, state="readonly"); self.prompt_combo.grid(row=0, column=5, padx=5, pady=10); self.interactive_widgets.append(self.prompt_combo)
        apply_button = ctk.CTkButton(parent, text="Apply", width=80, command=lambda: self.event_bus.publish("ui:batch_prompt_apply", self.batch_prompt_var.get())); apply_button.grid(row=0, column=6, padx=(5,10), pady=10); self.interactive_widgets.append(apply_button)

    def _publish_search_options(self):
        self.event_bus.publish("ui:search_options_changed", {"term": self.search_var.get(), "regex": self.regex_var.get(), "invert": self.invert_var.get()})

    def _create_left_pane(self, parent):
        parent.grid_rowconfigure(1, weight=1); parent.grid_columnconfigure(0, weight=1)
        
        list_toolbar = ctk.CTkFrame(parent); list_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        list_toolbar.columnconfigure(1, weight=1)

        list_toolbar_actions = ctk.CTkFrame(list_toolbar, fg_color="transparent")
        list_toolbar_actions.grid(row=0, column=0, sticky="w")
        
        b1=ctk.CTkButton(list_toolbar_actions, text="Generate Captions", command=lambda: self.event_bus.publish("ui:generate_clicked"))
        b1.pack(side="left", padx=(0, 5)); self.interactive_widgets.append(b1)

        list_toolbar_selection = ctk.CTkFrame(list_toolbar, fg_color="transparent")
        list_toolbar_selection.grid(row=0, column=1, sticky="ew")
        
        b2 = ctk.CTkButton(list_toolbar_selection, text="Select All", command=lambda: self.event_bus.publish("ui:select_all_clicked"))
        b2.pack(side="left", padx=5); self.interactive_widgets.append(b2)
        
        b3 = ctk.CTkButton(list_toolbar_selection, text="Deselect All", command=lambda: self.event_bus.publish("ui:deselect_all_clicked"))
        b3.pack(side="left", padx=5); self.interactive_widgets.append(b3)

        self.batch_op_container = ctk.CTkFrame(list_toolbar, fg_color="transparent")
        self.batch_op_container.grid(row=0, column=2, sticky="e")
        
        self.thumbnail_list = ThumbnailListView(parent, self.event_bus)
        self.thumbnail_list.grid(row=1, column=0, sticky="nsew")

    def _create_workspace(self, parent):
        parent.grid_rowconfigure(1, weight=1); parent.grid_columnconfigure(0, weight=1)
        
        model_frame = ctk.CTkFrame(parent, fg_color="transparent")
        model_frame.grid(row=0, column=0, sticky="ew")
        model_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(model_frame, text="Model:").grid(row=0, column=0, padx=(0, 5))
        self.model_var = ctk.StringVar()
        self.model_dropdown = ctk.CTkComboBox(model_frame, variable=self.model_var, state="readonly", command=self._on_model_selected)
        self.model_dropdown.grid(row=0, column=1, sticky="ew")
        self.interactive_widgets.append(self.model_dropdown)
        
        self.plugin_paned_window = tk.PanedWindow(parent, orient=tk.VERTICAL, sashwidth=8)
        self.plugin_paned_window.grid(row=1, column=0, sticky="nsew", pady=(10,0))
        
        self.main_workspace_frame = ctk.CTkFrame(self.plugin_paned_window, fg_color="transparent")
        self.plugin_paned_window.add(self.main_workspace_frame, stretch="always")
        self.main_workspace_frame.grid_rowconfigure(0, weight=1)
        self.main_workspace_frame.grid_columnconfigure(0, weight=1)

        self.settings_frame = ctk.CTkFrame(self.plugin_paned_window)
        self.plugin_paned_window.add(self.settings_frame, stretch="always", minsize=100)
        self.settings_frame.grid_rowconfigure(0, weight=1)
        self.settings_frame.grid_columnconfigure(0, weight=1)
        
    def _create_status_and_queue_controls(self, parent):
        parent.grid_columnconfigure(2, weight=1)
        
        left_status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        left_status_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=5, sticky="w")
        
        self.queue_status_var = ctk.StringVar(value="Queue: 0")
        queue_label = ctk.CTkLabel(left_status_frame, textvariable=self.queue_status_var, font=("Segoe UI", 12, "italic"))
        queue_label.pack(side="left", padx=(0, 10))
        queue_label.bind("<Button-1>", lambda e: TaskQueueViewer.show(self.root, self.event_bus))
        
        self.selection_count_var = ctk.StringVar(value="Selected: 0")
        selection_label = ctk.CTkLabel(left_status_frame, textvariable=self.selection_count_var, font=("Segoe UI", 12, "italic"))
        selection_label.pack(side="left")
        
        self.status_var = ctk.StringVar(value="Ready")
        status_label = ctk.CTkLabel(parent, textvariable=self.status_var, font=("Consolas", 12), anchor='w')
        status_label.grid(row=0, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        status_label.bind("<Button-1>", lambda e: LogViewer.show(self.root))
        
        self.progress_var = ctk.DoubleVar(value=0.0)
        ctk.CTkProgressBar(parent, variable=self.progress_var).grid(row=1, column=1, columnspan=2, sticky="ew", padx=10, pady=(0,5))
        
        controls_frame = ctk.CTkFrame(parent, fg_color="transparent")
        controls_frame.grid(row=0, column=3, rowspan=2, padx=10, pady=5, sticky="e")
        self.run_button = ctk.CTkButton(controls_frame, text="▶️ Run", command=lambda: self.event_bus.publish("ui:queue_run"), width=80, state="disabled"); self.run_button.pack(side="left", padx=2)
        self.pause_button = ctk.CTkButton(controls_frame, text="⏸️ Pause", command=lambda: self.event_bus.publish("ui:queue_pause"), width=80, state="disabled"); self.pause_button.pack(side="left", padx=2)
        self.stop_button = ctk.CTkButton(controls_frame, text="⏹️ Stop", command=lambda: self.event_bus.publish("ui:queue_stop"), width=80, state="disabled"); self.stop_button.pack(side="left", padx=2)

    def _update_queue_controls(self, count, task_names):
        self.queue_status_var.set(f"Queue: {count}")
        current_state = self.run_button.cget("state")
        if current_state == "disabled" and self.run_button.cget("text") == "▶️ Run":
            self.run_button.configure(state="normal" if count > 0 else "disabled")

    def _update_selection_count(self, checked_ids: list[str]):
        self.selection_count_var.set(f"Selected: {len(checked_ids)}")

    def _set_queue_state(self, state: str):
        is_idle = state == "idle"
        is_running = state == "running"
        is_paused = state == "paused"
        
        queue_count = int(self.queue_status_var.get().split(": ")[-1]) if ": " in self.queue_status_var.get() else 0

        self.run_button.configure(
            state="normal" if is_idle and queue_count > 0 else "disabled",
            text="▶️ Run"
        )
        self.pause_button.configure(
            state="normal" if is_running or is_paused else "disabled",
            text="▶️ Resume" if is_paused else "⏸️ Pause",
            command=lambda: self.event_bus.publish("ui:queue_resume" if is_paused else "ui:queue_pause")
        )
        self.stop_button.configure(state="normal" if is_running or is_paused else "disabled")

    def initialize_plugins(self, image_processors: list[ImageProcessorPlugin], batch_operations: list[BatchOperationPlugin]):
        self.image_processors = image_processors
        
        for plugin in self.image_processors:
            plugin.settings_ui = plugin.create_ui(self.settings_frame)
            plugin.workspace_ui = plugin.create_workspace(self.main_workspace_frame)
            
            if plugin.settings_ui: plugin.settings_ui.grid_remove()
            if plugin.workspace_ui: plugin.workspace_ui.grid_remove()

            icon = ctk.CTkButton(self.plugin_toolbar, text=plugin.display_name[:5], width=65, height=40,
                                 command=lambda p=plugin: self.activate_plugin(p))
            icon.pack(pady=5, padx=5)

        if self.image_processors: self.activate_plugin(self.image_processors[0])
            
        for op in reversed(batch_operations):
            btn = ctk.CTkButton(self.batch_op_container, text=op.display_name, command=op.execute)
            btn.pack(side="right", padx=(5, 0)); self.interactive_widgets.append(btn)
        
    def activate_plugin(self, plugin_to_activate: ImageProcessorPlugin):
        if self.active_plugin == plugin_to_activate: return

        if self.active_plugin:
            if hasattr(self.active_plugin, 'settings_ui') and self.active_plugin.settings_ui.winfo_exists():
                self.active_plugin.settings_ui.grid_remove()
            if hasattr(self.active_plugin, 'workspace_ui') and self.active_plugin.workspace_ui.winfo_exists():
                self.active_plugin.workspace_ui.grid_remove()

        self.active_plugin = plugin_to_activate

        if self.active_plugin:
            if hasattr(self.active_plugin, 'settings_ui') and self.active_plugin.settings_ui:
                self.active_plugin.settings_ui.grid(row=0, column=0, sticky="nsew")
            if hasattr(self.active_plugin, 'workspace_ui') and self.active_plugin.workspace_ui:
                self.active_plugin.workspace_ui.grid(row=0, column=0, sticky="nsew")
        
        self.on_active_item_changed_event(self.app_context.app_state.active_id)

    def on_active_item_changed_event(self, active_id: str | None = None):
        if not self.app_context or not self.active_plugin:
            return

        image_to_show = None
        if active_id and self.app_context.data_provider and (file_data := self.app_context.data_provider.get_file_by_id(active_id)):
            image_to_show = self.image_loader.get_full_image(file_data["filepath"])
        
        if hasattr(self.active_plugin, 'on_image_selected'):
            self.active_plugin.on_image_selected(image_to_show)

    def set_ui_enabled(self, enabled: bool):
        for widget in self.interactive_widgets:
            if widget.winfo_exists(): widget.configure(state="normal" if enabled else "disabled")
            
    def set_prompt_types(self, prompt_types: list[str]):
        if prompt_types:
            self.prompt_combo.configure(values=prompt_types)
            default_prompt = "Detailed Caption" if "Detailed Caption" in prompt_types else prompt_types[0]
            self.prompt_combo.set(default_prompt)
        
    def populate_model_dropdown(self, model_paths: list[str]):
        self.model_path_map = {os.path.basename(p): p for p in model_paths}
        model_names = list(self.model_path_map.keys())
        self.model_dropdown.configure(values=model_names)
        self.model_dropdown.set(model_names[0] if model_names else "No models found")
        
    def set_selected_model(self, model_path: str):
        self.model_dropdown.set(os.path.basename(model_path))

    def _on_model_selected(self, choice: str):
        full_path = self.model_path_map.get(choice)
        if full_path:
            self.event_bus.publish("ui:model_selected", full_path)