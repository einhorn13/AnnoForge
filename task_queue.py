# task_queue.py
import threading
import time
import logging
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, List, Any, Tuple

from events import EventBus

@dataclass
class Task:
    """Represents a single unit of work for the TaskQueue."""
    name: str
    target: Callable
    items: List[Any] = field(default_factory=list)  # For iterating tasks
    args: Tuple[Any, ...] = ()                      # For non-iterating tasks
    
    @property
    def is_iterating(self) -> bool:
        """A task is iterating if it has items to process."""
        return bool(self.items)

class TaskQueue:
    """Manages a queue of tasks to be executed in a background thread."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.app_context = None  # Will be injected by the main app
        self._queue = deque()
        self._worker_thread = None
        self._is_running = False
        self._is_paused = False
        self._abort_flag = False

    def add_task(self, task: Task):
        """Adds a task to the queue."""
        self._queue.append(task)
        self.publish_queue_update()

    def start(self):
        """Starts the worker thread if it's not already running."""
        if self._is_running:
            return
        if not self._queue:
            logging.info("Task queue is empty. Nothing to start.")
            return

        self._is_running = True
        self._abort_flag = False
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._worker_thread.start()
        self.event_bus.publish("queue:started")
        logging.info("Task queue started.")

    def pause(self):
        if self._is_running and not self._is_paused:
            self._is_paused = True
            self.event_bus.publish("queue:paused")
            logging.info("Task queue paused.")

    def resume(self):
        if self._is_running and self._is_paused:
            self._is_paused = False
            self.event_bus.publish("queue:resumed")
            logging.info("Task queue resumed.")

    def stop(self):
        if self._is_running:
            self._abort_flag = True
            self._is_paused = False # Ensure the loop can see the abort flag
            logging.info("Task queue stop requested.")

    def _run_worker(self):
        """The main loop for the background worker thread."""
        while self._queue:
            if self._abort_flag:
                logging.warning("Task execution aborted by user.")
                break

            current_task = self._queue.popleft()
            self.publish_queue_update()
            
            if current_task.is_iterating:
                self._execute_iterating_task(current_task)
            else:
                self._execute_non_iterating_task(current_task)

        self._finalize_run()

    def _execute_iterating_task(self, task: Task):
        total = len(task.items)
        success_count, fail_count, skip_count = 0, 0, 0
        
        for i, item in enumerate(task.items):
            while self._is_paused:
                time.sleep(0.1)
            
            if self._abort_flag:
                logging.warning(f"Task '{task.name}' aborted mid-run.")
                break
            
            self.app_context.update_status(f"{task.name}: {i+1}/{total}")
            try:
                result = task.target(item, self.app_context)
                if result is True: success_count += 1
                elif result is False: fail_count += 1
                else: skip_count +=1
            except Exception as e:
                fail_count += 1
                item_name = item.get("filename", "unknown item") if isinstance(item, dict) else str(item)
                logging.error(f"Task '{task.name}' failed on '{item_name}': {e}")
                traceback.print_exc()
            
            progress = (i + 1) / total * 100
            self.app_context.update_progress(progress)
            
        logging.info(f"Task '{task.name}' finished. Succeeded: {success_count}, Failed: {fail_count}, Skipped: {skip_count}")

    def _execute_non_iterating_task(self, task: Task):
        self.app_context.update_status(f"Running: {task.name}...")
        self.app_context.update_progress(-1) # Indeterminate progress
        try:
            task.target(self.app_context, *task.args)
            logging.info(f"Task '{task.name}' completed successfully.")
        except Exception as e:
            logging.error(f"Task '{task.name}' failed: {e}")
            traceback.print_exc()

    def _finalize_run(self):
        """Cleans up and resets state after the queue is empty or stopped."""
        self._is_running = False
        self._is_paused = False
        self._abort_flag = False
        self._queue.clear()
        
        self.app_context.update_status("Ready")
        self.app_context.update_progress(0)
        self.publish_queue_update()
        self.event_bus.publish("queue:finished")
        logging.info("Task queue finished processing.")
    
    def publish_queue_update(self):
        """Notifies the UI about the current state of the queue."""
        task_names = [task.name for task in self._queue]
        self.event_bus.publish("queue:updated", len(task_names), task_names)