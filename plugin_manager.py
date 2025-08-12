# plugin_manager.py
import importlib.util
import logging
import traceback
from pathlib import Path

from plugins.api import (BatchOperationPlugin, ImageProcessorPlugin,
                         ModelAssistantPlugin)


class PluginManager:
    PLUGIN_ENTRY_MODULE = "plugin"

    def __init__(self, plugin_folder="plugins"):
        self.plugin_folder = Path(plugin_folder).resolve()
        self.model_assistants: list[ModelAssistantPlugin] = []
        self.batch_operations: list[BatchOperationPlugin] = []
        self.image_processors: list[ImageProcessorPlugin] = []
        self._registered_names = set()

    def discover_plugins(self):
        """Finds, loads, and registers all valid plugins."""
        logging.debug("--- Discovering plugins ---")
        if not self.plugin_folder.is_dir():
            logging.error(f"Plugin directory not found: {self.plugin_folder}")
            return

        for item in self.plugin_folder.iterdir():
            # Skip non-directories and private/special folders
            if item.is_dir() and not item.name.startswith(("_", ".")):
                self._load_plugin_from_path(item)

        # Sort plugins by their display name for consistent UI presentation
        self.model_assistants.sort(key=lambda p: p.display_name)
        self.batch_operations.sort(key=lambda p: p.display_name)
        self.image_processors.sort(key=lambda p: p.display_name)
        
        logging.debug("--- Plugin discovery finished ---")

    def _load_plugin_from_path(self, plugin_path: Path):
        plugin_name = plugin_path.name
        logging.debug(f"Attempting to load plugin from: '{plugin_name}'")
        
        entry_point_file = plugin_path / f"{self.PLUGIN_ENTRY_MODULE}.py"
        init_file = plugin_path / "__init__.py"

        if not init_file.is_file():
            logging.warning(f"Skipping '{plugin_name}' because it is not a package (missing __init__.py).")
            return
            
        if not entry_point_file.is_file():
            # This is not a critical error, some plugin folders might be for assets.
            # logging.warning(f"Skipping '{plugin_name}' (missing entry point: {entry_point_file.name}).")
            return

        try:
            # Create a full module name for importlib
            module_name = f"plugins.{plugin_name}.{self.PLUGIN_ENTRY_MODULE}"
            spec = importlib.util.spec_from_file_location(module_name, entry_point_file)
            if spec is None:
                logging.error(f"Could not create spec for module {module_name}")
                return

            plugin_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugin_module)

            if not hasattr(plugin_module, "register"):
                logging.warning(f"No 'register' function found in {plugin_name}")
                return

            plugin_instance = plugin_module.register()
            if not plugin_instance:
                logging.warning(f"'register' function in {plugin_name} returned None.")
                return

            self._register_plugin(plugin_instance)

        except Exception as e:
            logging.error(f"FAILED to load plugin from '{plugin_name}'. Error: {e}")
            traceback.print_exc()

    def _register_plugin(self, plugin):
        if not hasattr(plugin, 'name') or not plugin.name:
             logging.warning(f"Plugin from module has no 'name' attribute, skipping.")
             return

        if plugin.name in self._registered_names:
            logging.warning(f"A plugin with the name '{plugin.name}' is already registered. Skipping.")
            return
            
        registration_message = f"Registered {plugin.display_name} ({plugin.name})"
        registered = False

        if isinstance(plugin, ModelAssistantPlugin):
            self.model_assistants.append(plugin)
            registration_message += " as Model Assistant."
            registered = True
        elif isinstance(plugin, BatchOperationPlugin):
            self.batch_operations.append(plugin)
            registration_message += " as Batch Operation."
            registered = True
        elif isinstance(plugin, ImageProcessorPlugin):
            self.image_processors.append(plugin)
            registration_message += " as Image Processor."
            registered = True
        
        if registered:
            self._registered_names.add(plugin.name)
            logging.info(registration_message)
        else:
            plugin_type = type(plugin).__name__
            logging.warning(f"Plugin '{getattr(plugin, 'name', 'Unknown')}' of type '{plugin_type}' has an unknown base class and was not registered.")

    def get_all_plugin_instances(self) -> list:
        """
        Returns a single list containing all registered plugin instances
        from all categories.
        """
        return self.model_assistants + self.batch_operations + self.image_processors