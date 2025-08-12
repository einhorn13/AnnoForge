# ui/task_queue_viewer.py
import customtkinter as ctk

class TaskQueueViewer(ctk.CTkToplevel):
    _instance = None
    @classmethod
    def show(cls, parent, event_bus):
        if cls._instance is None or not cls._instance.winfo_exists(): cls._instance = cls(parent, event_bus)
        else: cls._instance.lift()
        cls._instance.focus_set()

    def __init__(self, parent, event_bus):
        super().__init__(parent)
        self.event_bus = event_bus; self.title("Task Queue"); self.geometry("500x300")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Queued Tasks")
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.event_bus.subscribe("queue:updated", self.update_view)
        # Request initial state
        self.event_bus.publish("ui:request_queue_state")

    def update_view(self, count, task_names):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        if not task_names: ctk.CTkLabel(self.scrollable_frame, text="Queue is empty.").pack(pady=10); return
        for name in task_names:
            task_frame = ctk.CTkFrame(self.scrollable_frame, fg_color=("gray85", "gray28"))
            task_frame.pack(fill="x", pady=2, padx=2)
            ctk.CTkLabel(task_frame, text=name).pack(side="left", padx=10, pady=5)
    
    def _on_close(self):
        TaskQueueViewer._instance = None; self.destroy()