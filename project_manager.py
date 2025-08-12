# project_manager.py
import os
import json
import logging
from events import EventBus

class ProjectManager:
    """
    Handles the creation, loading, and configuration of AnnoForge projects.
    A project is defined by a directory containing a 'project.annoforge' file.
    """
    CONFIG_FILENAME = "project.annoforge"

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.current_project_path = None
        self.current_project_config = {}

    def create_project(self, name: str, project_dir: str, image_source_dir: str) -> bool:
        """
        Creates a new project directory and its configuration file.
        
        Returns:
            bool: True if creation was successful, False otherwise.
        """
        project_path = os.path.join(project_dir, name)
        if os.path.exists(project_path):
            logging.error(f"Project directory '{project_path}' already exists.")
            return False
        
        try:
            os.makedirs(project_path)
            
            db_path = os.path.join(project_path, f"{name}.db")
            
            config = {
                "name": name,
                "version": 1,
                "data_source": os.path.abspath(image_source_dir),
                "db_path": os.path.abspath(db_path)
            }
            
            config_path = os.path.join(project_path, self.CONFIG_FILENAME)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            
            logging.info(f"Successfully created project '{name}' at '{project_path}'")
            self.load_project(project_path)
            return True
        except Exception as e:
            logging.error(f"Failed to create project '{name}': {e}")
            return False

    def load_project(self, project_path: str):
        """
        Loads a project from a given directory path.
        It looks for 'project.annoforge', reads it, and publishes the config.
        """
        config_path = os.path.join(project_path, self.CONFIG_FILENAME)
        if not os.path.isfile(config_path):
            logging.error(f"Not a valid project directory. Missing '{self.CONFIG_FILENAME}'.")
            # Optionally, publish an error event
            # self.event_bus.publish("project:load_failed", "Config file not found.")
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            self.current_project_path = os.path.abspath(project_path)
            self.current_project_config = config
            
            logging.info(f"Loading project '{config['name']}' from '{self.current_project_path}'")
            self.event_bus.publish("project:loaded", config)
        except (json.JSONDecodeError, KeyError) as e:
            logging.error(f"Failed to load project config from '{config_path}': {e}")
            # self.event_bus.publish("project:load_failed", "Invalid config file.")