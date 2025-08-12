# app_state.py
from typing import List, Dict, Any
import re
from events import EventBus

class AppState:
    """
    Manages the dynamic state of the application.

    It acts as an observable state store. When a property is changed,
    it publishes an event on the EventBus, allowing other components
    (like the UI) to react to state changes automatically.
    """
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
        # --- Internal State ---
        self._all_files: List[Dict[str, Any]] = []
        self._search_options: Dict[str, Any] = {"term": "", "regex": False, "invert": False}
        self._checked_ids: List[str] = []
        self._active_id: str | None = None
        self.all_plugins: List[Any] = []

    # --- Properties with Event Publishing ---

    @property
    def all_files(self) -> List[Dict[str, Any]]:
        return self._all_files

    @all_files.setter
    def all_files(self, value: List[Dict[str, Any]]):
        self._all_files = value
        # FIXED: `state:files_changed` MUST publish the complete, unfiltered list.
        # This is the source of truth for UI elements that need to create all their widgets.
        self.event_bus.publish("state:files_changed", self._all_files)
        # After notifying about the new master list, we can publish the initially filtered list.
        self.event_bus.publish("state:filter_changed", self._get_filtered_files())


    @property
    def search_options(self) -> Dict[str, Any]:
        return self._search_options

    @search_options.setter
    def search_options(self, value: Dict[str, Any]):
        if self._search_options != value:
            self._search_options = value
            self.event_bus.publish("state:filter_changed", self._get_filtered_files())

    @property
    def checked_ids(self) -> List[str]:
        return self._checked_ids

    @checked_ids.setter
    def checked_ids(self, value: List[str]):
        if self._checked_ids != value:
            self._checked_ids = sorted(value) # Keep it sorted for consistent comparisons
            self.event_bus.publish("state:selection_changed", self._checked_ids)

    @property
    def active_id(self) -> str | None:
        return self._active_id

    @active_id.setter
    def active_id(self, value: str | None):
        if self._active_id != value:
            self._active_id = value
            self.event_bus.publish("state:active_item_changed", self._active_id)

    # --- Filtering Logic ---

    def _get_filtered_files(self) -> List[Dict[str, Any]]:
        """Applies search/filter criteria to the master list of files."""
        if not self._all_files:
            return []

        term = self._search_options.get("term", "").strip()
        use_regex = self._search_options.get("regex", False)
        invert = self._search_options.get("invert", False)

        if not term:
            return self._all_files

        filtered_list = []
        for item in self._all_files:
            # Search in both filename and caption
            text_to_search = f"{item.get('filename', '')} {item.get('caption', '')}"
            match_found = False
            
            try:
                if use_regex:
                    if re.search(term, text_to_search, re.IGNORECASE):
                        match_found = True
                else:
                    if term.lower() in text_to_search.lower():
                        match_found = True
            except re.error:
                match_found = False

            if match_found ^ invert:
                filtered_list.append(item)
        
        return filtered_list