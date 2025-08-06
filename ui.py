# ui.py
import os
import tkinter as tk
from tkinter import ttk

class AppUI:
    def __init__(self, root, callbacks):
        self.root = root
        self.callbacks = callbacks
        self.tree = None
        self.progress_var = None
        self.status_var = None
        self.model_dropdown = None
        self.preview_label = None
        self.context_menu = None
        self.setup_ui()

    def setup_ui(self):
        """Build the entire UI"""
        self.root.title("AnnoForge — Florence-2")
        self.root.geometry("1200x700")

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left: File list and controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Right: Preview
        self.preview_label = self._create_preview_frame(main_frame)

        # Toolbar
        toolbar = ttk.Frame(left_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        self._create_toolbar_buttons(toolbar)

        # Model selector
        model_frame = ttk.Frame(toolbar)
        model_frame.pack(side=tk.LEFT, padx=(20, 0))
        ttk.Label(model_frame, text="Model:").pack(side=tk.LEFT)
        self.model_var = tk.StringVar()
        self.model_dropdown = ttk.Combobox(
            model_frame, textvariable=self.model_var, state="readonly", width=25
        )
        self.model_dropdown.pack(side=tk.LEFT, padx=2)

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(left_frame, variable=self.progress_var, maximum=100).pack(fill=tk.X, pady=(0, 5))

        # File tree (without checkbox column)
        self.tree = self._create_file_tree(left_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, font=("Consolas", 9)).pack(fill=tk.X, padx=10, pady=2)

        # Context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Change Prompt Type", command=self.callbacks["on_bulk_change_prompt"])

        # Bind events
        self.tree.bind("<Double-1>", self.callbacks["on_edit"])
        self.tree.bind("<<TreeviewSelect>>", self.callbacks["on_selection"])
        self.tree.bind("<Button-3>", self.callbacks["on_context_menu"])
        self.tree.bind("<Double-1>", self.callbacks["on_edit_prompt_type"], add="+")
        self.model_dropdown.bind("<<ComboboxSelected>>", self.callbacks["on_model_selected"])

    def _create_preview_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Preview", width=250)
        frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        frame.pack_propagate(False)
        label = ttk.Label(frame)
        label.pack(expand=True)
        return label

    def _create_toolbar_buttons(self, parent):
        buttons = [
            ("🔄 Refresh", self.callbacks["on_refresh"]),
            ("⚡ Generate", self.callbacks["on_generate"]),
            ("⏹ Abort", self.callbacks["on_abort"]),
            ("📤 Export CSV", self.callbacks["on_export"]),
            ("🔍 Replace", self.callbacks["on_replace"]),
        ]
        for text, cmd in buttons:
            ttk.Button(parent, text=text, command=cmd).pack(side=tk.LEFT, padx=2)

    def _create_file_tree(self, parent):
        mid_frame = ttk.Frame(parent)
        mid_frame.pack(fill=tk.BOTH, expand=True)

        # Removed 'selected' column
        columns = ("filename", "prompt_type", "status")
        tree = ttk.Treeview(mid_frame, columns=columns, show="headings", height=20)

        headings = {"filename": "File", "prompt_type": "Type", "status": "Status"}
        widths = {"filename": 340, "prompt_type": 150, "status": 80}

        for col, text in headings.items():
            tree.heading(col, text=text)
            tree.column(col, width=widths[col], anchor="w")

        vsb = ttk.Scrollbar(mid_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        return tree

    def populate_model_dropdown(self, model_paths):
        """Populate model dropdown with model names"""
        names = [os.path.basename(p) for p in model_paths] if model_paths else ["No models"]
        self.model_dropdown["values"] = names
        if names:
            self.model_var.set(names[0])