# ui/selection_model.py
from typing import List
from events import EventBus

class SelectionModel:
    """
    Manages item selection logic (active item, checked items) for a list view.
    Decouples selection handling from the view itself.
    """
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.item_order: List[str] = []
        self._checked_ids: set[str] = set()
        self._active_id: str | None = None
        self._last_clicked_id: str | None = None

    def update_item_order(self, ordered_ids: List[str]):
        """Updates the internal list of all items in their display order."""
        self.item_order = ordered_ids
        
        if self._active_id and self._active_id not in self.item_order:
            self.set_active(None)

        current_checked = self._checked_ids.copy()
        visible_set = set(self.item_order)
        for item_id in current_checked:
            if item_id not in visible_set:
                self._checked_ids.remove(item_id)
        self._publish_changes()


    def handle_click(self, item_id: str, modifiers: int):
        """
        The main entry point for handling a click on an item.
        Determines the selection behavior based on Shift or Ctrl keys.

        Args:
            item_id (str): The ID of the clicked item.
            modifiers (int): The modifier state from the tkinter event.
        """
        is_shift_pressed = (modifiers & 0x0001) != 0
        is_ctrl_pressed = (modifiers & 0x0004) != 0

        if is_shift_pressed:
            self._handle_shift_click(item_id)
        elif is_ctrl_pressed:
            self._handle_ctrl_click(item_id)
        else:
            self._handle_simple_click(item_id)
        
        self.set_active(item_id)
        self._last_clicked_id = item_id

    def _handle_simple_click(self, item_id: str):
        """Selects only the clicked item."""
        self._checked_ids = {item_id}
        self._publish_changes()

    def _handle_ctrl_click(self, item_id: str):
        """Toggles the selection state of the clicked item."""
        if item_id in self._checked_ids:
            self._checked_ids.remove(item_id)
        else:
            self._checked_ids.add(item_id)
        self._publish_changes()

    def _handle_shift_click(self, item_id: str):
        """Selects a range of items from the last clicked item to the current one."""
        if not self._last_clicked_id or self._last_clicked_id not in self.item_order:
            self._handle_simple_click(item_id)
            return

        try:
            start_index = self.item_order.index(self._last_clicked_id)
            end_index = self.item_order.index(item_id)
            
            if start_index > end_index:
                start_index, end_index = end_index, start_index
                
            self._checked_ids = set(self.item_order[start_index : end_index + 1])
            self._publish_changes()
        except ValueError:
            self._handle_simple_click(item_id)

    def set_active(self, item_id: str | None):
        """Sets the single active (focused) item."""
        if self._active_id != item_id:
            self._active_id = item_id
            self.event_bus.publish("appstate:set_active_id", self._active_id)

    def is_checked(self, item_id: str) -> bool:
        """Checks if a specific item is in the current selection."""
        return item_id in self._checked_ids

    def select_all(self):
        """Selects all items."""
        self._checked_ids = set(self.item_order)
        # NEW: Set the last visible item as active for better UX
        if self.item_order:
            self.set_active(self.item_order[-1])
        self._publish_changes()

    def clear(self):
        """Clears all selections."""
        self._checked_ids.clear()
        self.set_active(None)
        self._last_clicked_id = None
        self._publish_changes()
        
    def add_to_selection(self, item_ids: List[str]):
        """Programmatically adds items to the selection."""
        self._checked_ids.update(item_ids)
        self._publish_changes()

    def remove_from_selection(self, item_ids: List[str]):
        """Programmatically removes items from the selection."""
        self._checked_ids.difference_update(item_ids)
        self._publish_changes()

    def _publish_changes(self):
        """Publishes the updated list of checked IDs to the app state."""
        self.event_bus.publish("appstate:set_checked_ids", list(self._checked_ids))