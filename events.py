# events.py
from typing import Callable, Dict, List
import logging

class EventBus:
    """A simple publisher-subscriber event bus."""

    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, fn: Callable):
        """
        Register a function to be called when an event of event_type is published.
        
        Args:
            event_type (str): The name of the event to subscribe to.
            fn (Callable): The function (callback) to execute.
        """
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(fn)

    def publish(self, event_type: str, *args, **kwargs):
        """
        Publish an event, calling all subscribed functions.
        
        Args:
            event_type (str): The name of the event to publish.
            *args: Positional arguments to pass to the callback functions.
            **kwargs: Keyword arguments to pass to the callback functions.
        """
        if event_type in self.listeners:
            for fn in self.listeners[event_type]:
                try:
                    fn(*args, **kwargs)
                except Exception as e:
                    logging.error(f"Error in event handler for '{event_type}': {e}", exc_info=True)