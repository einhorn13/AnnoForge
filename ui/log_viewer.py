# ui/log_viewer.py
import tkinter as tk
from tkinter import ttk
from utils import app_log_handler
import logging

class LogViewer(tk.Toplevel):
    """
    A non-modal window to display application logs.
    Implemented as a singleton to ensure only one instance exists.
    """
    _instance = None

    @classmethod
    def show(cls, parent):
        if cls._instance is None or not cls._instance.winfo_exists():
            cls._instance = cls(parent)
        cls._instance.lift()
        cls._instance.focus_set()
        cls._instance.populate_log()

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Application Log")
        self.geometry("800x250")
        self.transient(parent)

        self._position_window(parent)
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _position_window(self, parent):
        """Positions the log viewer just above the bottom of the parent window."""
        parent.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_height = parent.winfo_height()
        parent_width = parent.winfo_width()
        
        my_height = 250
        x_pos = parent_x + (parent_width // 2) - (800 // 2)
        y_pos = parent_y + parent_height - my_height - 40
        self.geometry(f"+{x_pos}+{y_pos}")

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(main_frame, wrap="word", font=("Consolas", 9), state="disabled", relief="solid", borderwidth=1)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=2, sticky="e", pady=(5,0))

        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self._on_close).pack(side=tk.LEFT)

    def populate_log(self):
        """Fills the text widget with logs from the handler."""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        logs = app_log_handler.get_logs()
        if not logs:
            self.log_text.insert(tk.END, "Log is empty.")
        else:
            for record in logs:
                self.log_text.insert(tk.END, record + "\n")
        
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def clear_log(self):
        """Clears the logs in the handler and refreshes the view."""
        # NEW: Log the clear action itself for traceability.
        logging.info("Log viewer cleared by user.")
        app_log_handler.clear()
        self.populate_log()

    def _on_close(self):
        """Hides the window instead of destroying it."""
        LogViewer._instance = None
        self.destroy()