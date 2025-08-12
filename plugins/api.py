# plugins/api.py
from abc import ABC, abstractmethod
import tkinter as tk
from tkinter import ttk
from PIL import Image

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app_context import AppContext

class AnnoForgePlugin(ABC):
    """Base class for all plugins."""
    def __init__(self):
        self.app_context: 'AppContext' = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier (e.g., 'florence2_generator')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """User-facing name (e.g., 'Florence-2 Captioner')."""
        pass

class ModelAssistantPlugin(AnnoForgePlugin):
    """Plugin for generating captions, tags, etc."""
    @abstractmethod
    def load_model(self, model_path: str) -> tuple[bool, str]:
        pass
        
    @abstractmethod
    def get_model_paths(self) -> list[str]:
        pass

    @abstractmethod
    def run_inference(self, image_path: str, prompt_type: str) -> tuple[bool, str]:
        pass
        
    @abstractmethod
    def get_supported_prompts(self) -> dict:
        pass

    # NEW: Add a method to check if a specific model is already loaded.
    @abstractmethod
    def is_model_loaded(self, model_path: str) -> bool:
        """Checks if the model at the given path is the currently active one."""
        pass


class BatchOperationPlugin(AnnoForgePlugin):
    """Plugin for operations on multiple files (e.g., export, find/replace)."""
    @abstractmethod
    def execute(self):
        """
        The main method to run the operation.
        This method should use the 'self.app_context' attribute, which is
        injected by the main application, to interact with the system.
        """
        pass

class ImageProcessorPlugin(AnnoForgePlugin):
    """Plugin for image processing, providing its own UI for settings."""
    @property
    def workspace_title(self) -> str:
        return "Image Processor Workspace"

    @abstractmethod
    def create_ui(self, parent_frame: tk.Frame) -> tk.Frame:
        pass

    @abstractmethod
    def process_image(self, image: Image.Image) -> Image.Image:
        pass

    def create_workspace(self, parent_frame: tk.Frame) -> tk.Widget:
        return ttk.Frame(parent_frame)

    def on_image_selected(self, pil_image: Image.Image | None):
        pass