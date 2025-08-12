# app.py
import os
import shlex
from tkinter import messagebox, filedialog
import logging
import customtkinter as ctk

from events import EventBus
from app_state import AppState
from app_context import AppContext
from plugin_manager import PluginManager
from providers import ImageFileProvider
from task_queue import TaskQueue, Task
from annotation_manager import AnnotationManager
from project_manager import ProjectManager
from ui.main_window import AppUI
import utils

class AutoCaptionerApp:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.search_debounce_job = None
        
        # --- Core Architecture ---
        self.event_bus = EventBus()
        self.app_state = AppState(self.event_bus)
        
        # --- Managers and Services ---
        self.plugin_manager = PluginManager()
        self.task_queue = TaskQueue(self.event_bus)
        self.annotation_manager = AnnotationManager()
        self.project_manager = ProjectManager(self.event_bus)
        
        self.data_provider = None
        self.active_model_plugin = None
        self.default_prompt_type = "Detailed Caption"
        
        # --- REFACTORED: Initialization order is critical. ---
        
        # 1. Create UI shell
        self.ui = AppUI(root, self.event_bus)
        
        # 2. Discover plugins to have them ready for context
        self.plugin_manager.discover_plugins()
        self.app_state.all_plugins = self.plugin_manager.get_all_plugin_instances()
        
        # 3. Create the AppContext
        self.app_context = self._create_app_context()
        
        # 4. Inject context into ALL components BEFORE initializing their UI
        self._inject_context_into_services()
        
        # 5. Now that all components are context-aware, initialize plugin UI
        self.ui.initialize_plugins(self.plugin_manager.image_processors, self.plugin_manager.batch_operations)

        # 6. Final setup
        self._register_event_listeners()
        self.active_model_plugin = self._get_active_model_plugin()

        if self.active_model_plugin:
            self.ui.set_prompt_types(list(self.active_model_plugin.get_supported_prompts().keys()))
            self.ui.populate_model_dropdown(
                [os.path.basename(p) for p in self.active_model_plugin.get_model_paths()]
            )
        
        self._load_last_project()

    def _create_app_context(self) -> AppContext:
        return AppContext(root=self.root, event_bus=self.event_bus, app_state=self.app_state,
                          data_provider=self.data_provider, task_queue=self.task_queue,
                          plugin_manager=self.plugin_manager, annotation_manager=self.annotation_manager, 
                          project_manager=self.project_manager, ui=self.ui)
        
    def _inject_context_into_services(self):
        """Injects the app context into all services that need it."""
        self.task_queue.app_context = self.app_context
        self.ui.app_context = self.app_context
        self.ui.thumbnail_list.app_context = self.app_context
        for plugin in self.plugin_manager.get_all_plugin_instances():
            plugin.app_context = self.app_context

    def _get_active_model_plugin(self):
        if not self.plugin_manager.model_assistants:
            messagebox.showerror("Fatal Error", "No Model Assistant plugin found."); self.root.destroy(); return None
        return self.plugin_manager.model_assistants[0]

    def _register_event_listeners(self):
        bus = self.event_bus
        bus.subscribe("ui:new_project_clicked", self.on_new_project)
        bus.subscribe("ui:open_project_clicked", self.on_open_project)
        bus.subscribe("project:loaded", self.on_project_loaded)
        bus.subscribe("state:active_item_changed", self.on_active_item_changed)
        bus.subscribe("appstate:set_checked_ids", lambda ids: setattr(self.app_state, 'checked_ids', ids))
        bus.subscribe("appstate:set_active_id", lambda id: setattr(self.app_state, 'active_id', id))
        bus.subscribe("ui:plugin_state_changed", self.on_plugin_state_changed)
        bus.subscribe("ui:batch_apply_plugin_state", self.on_batch_apply_plugin_state)
        bus.subscribe("ui:generate_clicked", self.start_captioning)
        bus.subscribe("ui:queue_run", self.task_queue.start); bus.subscribe("ui:queue_pause", self.task_queue.pause)
        bus.subscribe("ui:queue_resume", self.task_queue.resume); bus.subscribe("ui:queue_stop", self.task_queue.stop)
        bus.subscribe("ui:search_options_changed", self._on_search_options_changed)
        bus.subscribe("ui:batch_prompt_apply", self._apply_prompt_type_to_checked)
        bus.subscribe("ui:model_selected", self.load_model)
        bus.subscribe("ui:caption_edited", self.save_caption)
        bus.subscribe("ui:prompt_type_changed", lambda item_id, pt: self.data_provider.update_prompt_type(item_id, pt))
        bus.subscribe("data:caption_saved", lambda item_id: self.ui.thumbnail_list.update_item_caption(item_id))
        
        self.root.drop_target_register('DND_FILES')
        self.root.dnd_bind('<<Drop>>', self.on_drop)

    def on_new_project(self, image_dir=None):
        if not image_dir:
            image_dir = filedialog.askdirectory(title="Select folder with source images")
        if not image_dir: return
        
        project_dir = filedialog.askdirectory(title="Select folder to save the new project")
        if not project_dir: return
        
        dialog = ctk.CTkInputDialog(text="Enter project name:", title="New Project")
        name = dialog.get_input()
        if name:
            if not self.project_manager.create_project(name, project_dir, image_dir):
                self.app_context.show_error("Creation Failed", "Project directory might already exist or another error occurred.")

    def on_open_project(self):
        project_path = filedialog.askdirectory(title="Select Project Folder")
        if project_path: self.project_manager.load_project(project_path)
            
    def on_project_loaded(self, config: dict):
        self.root.title(f"AnnoForge - [{config['name']}]")
        self.annotation_manager.connect(config['db_path'])
        
        config_from_file = utils.load_config()
        self.default_prompt_type = config_from_file.get("default_prompt_type", "Detailed Caption")
        self.data_provider = ImageFileProvider(self.default_prompt_type)
        self.app_context.data_provider = self.data_provider
        
        files = self.data_provider.scan(config['data_source'])
        self.app_state.all_files = files

        if files:
            first_item_id = files[0]['item_id']
            self.app_state.active_id = first_item_id
            self.app_state.checked_ids = [first_item_id]
        else:
            self.app_state.active_id = None
            self.app_state.checked_ids = []
            
        last_model_path = config_from_file.get("last_model")
        if last_model_path and os.path.exists(last_model_path):
            if not (self.active_model_plugin and self.active_model_plugin.is_model_loaded(last_model_path)):
                self.load_model(last_model_path)
        else:
            logging.warning("Last used model not found or specified.")
            
        if self.project_manager.current_project_path:
            utils.save_config({"last_project_path": self.project_manager.current_project_path})

    def _load_last_project(self):
        config = utils.load_config()
        last_project = config.get("last_project_path")
        if last_project and os.path.exists(last_project):
            logging.info(f"Attempting to load last opened project: {last_project}")
            self.project_manager.load_project(last_project)

    def on_active_item_changed(self, active_id: str | None):
        if not active_id: return
        for plugin in self.plugin_manager.image_processors:
            if hasattr(plugin, 'on_state_load'):
                data = self.annotation_manager.get_data(active_id, plugin.name)
                plugin.on_state_load(data)
    
    def on_plugin_state_changed(self, plugin_name: str):
        active_id = self.app_state.active_id
        if not active_id: return
        plugin_instance = next((p for p in self.plugin_manager.image_processors if p.name == plugin_name), None)
        if plugin_instance and hasattr(plugin_instance, 'get_state_to_save') and (state_to_save := plugin_instance.get_state_to_save()) is not None:
            self.annotation_manager.save_data(active_id, plugin_name, state_to_save)

    def on_batch_apply_plugin_state(self, plugin_name: str, item_ids: list[str], data: dict):
        def task(item_id, context):
            context.annotation_manager.save_data(item_id, plugin_name, data)
            return True
        task_obj = Task(name=f"Apply {plugin_name} state", target=task, items=item_ids)
        self.task_queue.add_task(task_obj)
        self.app_context.show_info("Task Added", f"Added task to apply '{plugin_name}' settings to {len(item_ids)} items.")

    def load_model(self, model_path: str):
        if not model_path or "No models" in model_path: return
        task = Task(name=f"Load Model: {os.path.basename(model_path)}", target=self._load_model_task, args=(model_path,))
        self.task_queue.add_task(task)

    def _load_model_task(self, context, model_path):
        model_name = os.path.basename(model_path)
        context.event_bus.publish("ui:set_enabled", False); context.event_bus.publish("state:status_changed", f"Loading {model_name}...")
        success, msg = self.active_model_plugin.load_model(model_path)
        if success:
            utils.save_config({"last_model": model_path})
            logging.info(f"Successfully loaded model: {model_name}"); context.ui.set_selected_model(model_path)
        else:
            logging.error(f"Failed to load model '{model_name}': {msg}"); context.show_error("Model Load Failed", f"Could not load '{model_name}'.\n\nReason: {msg}")
        context.event_bus.publish("ui:set_enabled", True)
        return success

    def start_captioning(self):
        checked_ids = self.app_state.checked_ids
        if not checked_ids: messagebox.showwarning("Selection", "No images checked."); return
        items = self.data_provider.get_files_by_ids(checked_ids)
        task = Task(name="Generate Captions", target=self._captioning_task, items=items); self.task_queue.add_task(task)
    
    def _captioning_task(self, item_data, context):
        prompt_type = item_data.get("prompt_type", self.default_prompt_type)
        success, caption_or_error = self.active_model_plugin.run_inference(item_data["filepath"], prompt_type)
        if success: self.save_caption(item_data["item_id"], caption_or_error)
        else: logging.error(f"Inference failed for {item_data['filename']}: {caption_or_error}")
        return success
    
    def save_caption(self, item_id: str, content: str):
        if self.data_provider and self.data_provider.save_item_data(item_id, {"caption": content}):
            self.event_bus.publish("data:caption_saved", item_id)

    def _on_search_options_changed(self, options: dict):
        if self.search_debounce_job: self.root.after_cancel(self.search_debounce_job)
        self.search_debounce_job = self.root.after(300, lambda: setattr(self.app_state, 'search_options', options))

    def _apply_prompt_type_to_checked(self, new_prompt_type: str):
        checked_ids = self.app_state.checked_ids
        if not checked_ids: messagebox.showwarning("Selection", "No items checked."); return
        for item_id in checked_ids: self.data_provider.update_prompt_type(item_id, new_prompt_type)
        self.event_bus.publish("ui:update_prompt_display", checked_ids, new_prompt_type)
        logging.info(f"Set prompt type to '{new_prompt_type}' for {len(checked_ids)} items.")

    def on_drop(self, event):
        try:
            paths = shlex.split(event.data)
        except ValueError:
            paths = [event.data.strip()]

        if not paths:
            return
            
        dropped_path = paths[0]

        if os.path.isdir(dropped_path):
            if not self.project_manager.current_project_path:
                if messagebox.askyesno("Create Project?", f"Do you want to create a new project using the folder:\n\n{dropped_path}?"):
                    self.on_new_project(image_dir=dropped_path)
            else:
                self.app_context.show_info("Project Loaded", "A project is already open. Please create a new project via the File menu.")
        else:
            self.app_context.show_info("Drag & Drop", "Please drop a folder to create a new project.")