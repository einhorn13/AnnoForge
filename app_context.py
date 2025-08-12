# app_context.py
import tkinter as tk
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Dict, Any, Callable
from task_queue import Task # Import Task for the convenience method
import utils # NEW: Import utils to access the ImageLoader instance

if TYPE_CHECKING:
    from ui.main_window import AppUI
    from app_state import AppState
    from events import EventBus
    from plugin_manager import PluginManager
    from providers import ImageFileProvider
    from annotation_manager import AnnotationManager
    from project_manager import ProjectManager
    from task_queue import TaskQueue

@dataclass
class AppContext:
    """
    Provides a unified, stable interface for plugins and services to interact
    with the main application, decoupling them from its internal implementation.
    """
    # --- Core Application Components ---
    root: tk.Tk
    event_bus: 'EventBus'
    app_state: 'AppState'
    task_queue: 'TaskQueue'
    plugin_manager: 'PluginManager'
    
    # --- Data and Project Management ---
    data_provider: 'ImageFileProvider'
    annotation_manager: 'AnnotationManager'
    project_manager: 'ProjectManager'
    
    # --- UI Access ---
    ui: 'AppUI'
    
    def run_in_ui_thread(self, func: Callable):
        """Schedules a function to run in the main UI thread."""
        self.root.after(0, func)

    def show_info(self, title: str, message: str):
        from tkinter import messagebox
        self.run_in_ui_thread(lambda: messagebox.showinfo(title, message, parent=self.root))

    def show_error(self, title: str, message: str):
        from tkinter import messagebox
        self.run_in_ui_thread(lambda: messagebox.showerror(title, message, parent=self.root))

    # --- Abstracted Accessors for Plugins ---

    def get_checked_item_ids(self) -> List[str]:
        """Gets the IDs of all currently checked items from the app state."""
        return self.app_state.checked_ids

    def get_active_item_id(self) -> str | None:
        """Gets the ID of the currently active (focused) item from the app state."""
        return self.app_state.active_id

    def get_all_item_ids(self) -> List[str]:
        """Gets the IDs of all items managed by the data provider."""
        if not self.data_provider: return []
        return [item['item_id'] for item in self.data_provider.get_all_files()]

    def get_items_data(self, item_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieves the full data dictionaries for the given item IDs."""
        if not self.data_provider: return []
        return self.data_provider.get_files_by_ids(item_ids)

    def refresh_ui_items(self, item_ids: List[str], update_caption: bool = True, update_thumbnail: bool = False):
        """
        Requests the UI to refresh the display of specific items by publishing an event.
        The UI (e.g., ThumbnailListView) should subscribe to this event.
        """
        if update_caption:
            for item_id in item_ids:
                self.event_bus.publish("data:caption_saved", item_id)
        if update_thumbnail:
            for item_id in item_ids:
                self.event_bus.publish("ui:refresh_thumbnail", item_id)

    def clear_image_cache(self, item_ids: List[str]):
        """
        NEW: Clears the cache in ImageLoader for specific items.
        This is crucial for plugins that overwrite image files, ensuring
        that the UI reloads the new version instead of showing a stale cache.
        """
        items_data = self.get_items_data(item_ids)
        loader = utils.ImageLoader()
        for item in items_data:
            loader.clear_cache_for_item(item['filepath'])

    def update_status(self, message: str):
        """Sets the text of the main status bar."""
        self.event_bus.publish("state:status_changed", message)

    def update_progress(self, value: float):
        """Sets the value of the main progress bar (0.0 to 100.0)."""
        self.event_bus.publish("state:progress_changed", value)

    def run_job(self, task_function: Callable, items_to_process: List[Any], job_name: str, is_iterating: bool = True):
        """
        A convenience method for plugins to run a background job using the TaskQueue.
        
        Args:
            task_function: The function to execute.
            items_to_process: A list of items to iterate over.
            job_name: The display name for the task.
            is_iterating: If True, task_function is called for each item. 
                          If False, it's called once with the context.
        """
        if is_iterating:
            task = Task(name=job_name, target=task_function, items=items_to_process)
        else:
            # For non-iterating tasks, the items list is passed as a single argument.
            task = Task(name=job_name, target=task_function, args=(items_to_process,))

        self.task_queue.add_task(task)
        item_count = len(items_to_process) if items_to_process else 1
        self.show_info("Task Queued", f"Added '{job_name}' to the queue for {item_count} operation(s).")