# app.py
import os
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
import threading
from ui import AppUI
from model_manager import load_model, generate_caption
import utils

PROMPT_TYPES = [
    "Caption", "Detailed Caption", "More Detailed",
    "Tags (General)", "Tags (Objects)", "Tags (Style)", "Tags (Composition)",
    "Prompt (SD)", "Prompt (V2)"
]

PROMPT_DESCRIPTIONS = {
    "Caption": "Short, simple description of the image content",
    "Detailed Caption": "More detailed description with main elements",
    "More Detailed": "Comprehensive description including small details",
    "Tags (General)": "General tags describing content, objects, style",
    "Tags (Objects)": "Tags focused on objects present in the image",
    "Tags (Style)": "Tags describing artistic style, mood, composition",
    "Tags (Composition)": "Tags focused on composition, perspective, lighting",
    "Prompt (SD)": "Prompt format optimized for Stable Diffusion",
    "Prompt (V2)": "Enhanced prompt format with detailed elements"
}

PROMPT_MAP = {
    "Caption": "<CAPTION>",
    "Detailed Caption": "<DETAILED_CAPTION>",
    "More Detailed": "<MORE_DETAILED_CAPTION>",
    "Tags (General)": "<GENERATE_TAGS>",
    "Tags (Objects)": "<GENERATE_TAGS_OBJECT>",
    "Tags (Style)": "<GENERATE_TAGS_STYLE>",
    "Tags (Composition)": "<GENERATE_TAGS_COMPOSITION>",
    "Prompt (SD)": "<GENERATE_PROMPT>",
    "Prompt (V2)": "<GENERATE_PROMPT_V2>",
}

class ToolTip:
    def __init__(self, widget):
        self.widget = widget
        self.tip_window = None

    def showtip(self, text):
        if self.tip_window or not text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 20
        y = y + cy + self.widget.winfo_rooty() + 20
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"), wraplength=300)
        label.pack(ipadx=1)

    def hidetip(self):
        if self.tip_window:
            self.tip_window.destroy()
        self.tip_window = None

class AutoCaptionerApp:
    def __init__(self, root):
        self.root = root
        self.selected_files = {}
        self.generating = False
        self.abort_flag = False

        config = utils.load_config()
        self.last_model = config.get("last_model")
        self.default_prompt_type = config.get("default_prompt_type", "Detailed Caption")
        if self.default_prompt_type not in PROMPT_TYPES:
            self.default_prompt_type = "Detailed Caption"

        # --- Callbacks ---
        callbacks = {
            "on_refresh": self.load_files,
            "on_generate": self.start_captioning,
            "on_abort": self.abort,
            "on_export": self.export_csv,
            "on_replace": self.open_replace_dialog,
            "on_bulk_change_prompt": self.bulk_change_prompt,
            "on_click": self.on_click,
            "on_edit": self.on_edit,
            "on_selection": self.on_selection,
            "on_context_menu": self.show_context_menu,
            "on_edit_prompt_type": self.on_edit_prompt_type,
            "on_model_selected": lambda e: self.load_model(),
        }

        # --- UI ---
        self.ui = AppUI(root, callbacks)

        # --- Assign UI elements ---
        self.tree = self.ui.tree
        self.status_var = self.ui.status_var
        self.progress_var = self.ui.progress_var
        self.model_dropdown = self.ui.model_dropdown
        self.preview_label = self.ui.preview_label
        self.context_menu = self.ui.context_menu

        # --- Tooltip ---
        self.tooltip = ToolTip(self.tree)

        # --- Load data ---
        self.load_files()
        self.model_paths = utils.scan_checkpoints()
        self.ui.populate_model_dropdown(self.model_paths)

        # --- Restore last model ---
        if self.last_model and self.last_model in self.model_paths:
            try:
                idx = self.model_paths.index(self.last_model)
                if idx < len(self.model_dropdown["values"]):
                    self.model_dropdown.current(idx)
                    self.load_model()
            except ValueError:
                pass

    def load_model(self):
        idx = self.model_dropdown.current()
        if idx < 0 or idx >= len(self.model_paths):
            return
        model_path = self.model_paths[idx]
        self.status_var.set(f"Loading {os.path.basename(model_path)}...")
        threading.Thread(target=self._load_in_bg, args=(model_path,), daemon=True).start()

    def _load_in_bg(self, model_path):
        success, msg = load_model(model_path)
        self.root.after(0, lambda: self.status_var.set(msg))
        if success:
            self.last_model = model_path
            utils.save_config({
                "last_model": model_path,
                "default_prompt_type": self.default_prompt_type
            })

    def load_files(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.selected_files.clear()

        files = utils.scan_images()
        for f in files:
            path = os.path.join("captions", f)
            txt_path = f"{os.path.splitext(path)[0]}.txt"
            status = "✅" if os.path.exists(txt_path) else "❌"
            item_id = self.tree.insert("", "end", values=(f, self.default_prompt_type, status))
            self.selected_files[item_id] = {
                "item_id": item_id,
                "filename": f,
                "filepath": path,
                "txt_path": txt_path,
                "prompt_type": self.default_prompt_type
            }
        self.on_selection()

    def on_click(self, event):
        """Handle click - no checkbox logic anymore"""
        pass  # Selection handled by Treeview's built-in selection

    def on_selection(self, event=None):
        """Update preview and status when file is selected"""
        selected = self.tree.selection()
        if not selected:
            self.clear_preview()
            self.status_var.set("Ready")
            return

        item_id = selected[0]
        data = self.selected_files.get(item_id)
        if not data or not os.path.exists(data["filepath"]):
            self.clear_preview()
            return

        try:
            img = Image.open(data["filepath"])
            img.thumbnail((240, 240))
            photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=photo)
            self.preview_label.image = photo
            self.status_var.set(f"Selected: {data['filename']} | Type: {data['prompt_type']}")
        except Exception as e:
            print(f"Preview error: {e}")
            self.clear_preview()

    def clear_preview(self):
        self.preview_label.configure(image=None)
        self.preview_label.image = None

    def show_context_menu(self, event):
        if len(self.tree.selection()) > 1:
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def bulk_change_prompt(self):
        new_type = simpledialog.askstring("Prompt Type", f"Available: {', '.join(PROMPT_TYPES)}")
        if new_type and new_type in PROMPT_TYPES:
            for item_id in self.tree.selection():
                data = self.selected_files.get(item_id)
                if data is not None:
                    data["prompt_type"] = new_type
                    self.tree.set(item_id, "prompt_type", new_type)
            self.default_prompt_type = new_type
            utils.save_config({
                "last_model": self.last_model,
                "default_prompt_type": new_type
            })
            self.on_selection()  # Update status bar

    def on_edit(self, event):
        """Open editor only when clicking on filename (not on 'Type' column)"""
        column = self.tree.identify_column(event.x)
        if column == "#2":  # This is the 'Type' column now (after removing checkbox)
            return
        item_id = self.tree.identify_row(event.y)
        data = self.selected_files.get(item_id)
        if data is not None:
            self.edit_caption(data["txt_path"], data["filepath"])

    def on_edit_prompt_type(self, event):
        """Inline edit prompt_type with tooltip description"""
        column = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)
        if not item_id or column != "#2":  # Now column #2 is 'Type'
            return

        data = self.selected_files.get(item_id)
        if data is None:
            return

        current = data["prompt_type"]
        x, y, width, height = self.tree.bbox(item_id, column)

        var = tk.StringVar(value=current)
        combo = ttk.Combobox(self.tree, textvariable=var, values=PROMPT_TYPES, state="readonly", width=18)
        combo.place(x=x, y=y, width=width, height=height)

        # Tooltip
        tooltip = ToolTip(combo)

        def update_tooltip(_=None):
            desc = PROMPT_DESCRIPTIONS.get(var.get(), "")
            tooltip.showtip(desc)

        combo.bind("<Enter>", update_tooltip)
        combo.bind("<Motion>", update_tooltip)
        combo.bind("<Leave>", lambda e: tooltip.hidetip())
        combo.bind("<<ComboboxSelected>>", update_tooltip)

        def save_edit(_=None):
            if var.get() in PROMPT_TYPES:
                data["prompt_type"] = var.get()
                self.tree.set(item_id, "prompt_type", var.get())
                self.default_prompt_type = var.get()
                utils.save_config({
                    "last_model": self.last_model,
                    "default_prompt_type": var.get()
                })
                self.on_selection()  # Update status
            combo.destroy()
            tooltip.hidetip()

        def cancel_edit(_=None):
            combo.destroy()
            tooltip.hidetip()

        combo.bind("<Return>", save_edit)
        combo.bind("<Escape>", cancel_edit)
        combo.bind("<FocusOut>", cancel_edit)
        combo.focus_set()
        combo.selection_clear()

    def edit_caption(self, txt_path, img_path):
        win = tk.Toplevel(self.root)
        win.title(f"Edit: {os.path.basename(txt_path)}")
        win.geometry("600x400")
        win.transient(self.root)
        win.grab_set()

        try:
            img = Image.open(img_path)
            img.thumbnail((100, 100))
            photo = ImageTk.PhotoImage(img)
            tk.Label(win, image=photo).pack(side=tk.LEFT, padx=10, pady=10)
            win.image = photo
        except Exception:
            tk.Label(win, text="Image error").pack(side=tk.LEFT, padx=10)

        text = tk.Text(win, wrap=tk.WORD, font=("Courier", 10))
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                text.insert("1.0", f.read())
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def save():
            try:
                content = text.get("1.0", tk.END).strip()
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.root.after(0, lambda: self.tree.set(data["item_id"], "status", "✅"))
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Save failed: {e}")

        btn = tk.Frame(win)
        btn.pack(fill=tk.X, pady=5)
        tk.Button(btn, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        tk.Button(btn, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=5)

    def start_captioning(self):
        if self.generating:
            return
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Selection", "No files selected.")
            return
        self.generating = True
        self.abort_flag = False
        self.progress_var.set(0)
        threading.Thread(target=self.process, args=(selected_items,), daemon=True).start()

    def abort(self):
        if self.generating:
            self.abort_flag = True
            self.generating = False
            self.status_var.set("Aborted")

    def process(self, item_ids):
        total = len(item_ids)
        for i, item_id in enumerate(item_ids):
            if self.abort_flag:
                break
            data = self.selected_files.get(item_id)
            if not data:  # ✅ Исправленная строка
                continue
            success, caption = generate_caption(data["filepath"], data["prompt_type"], PROMPT_MAP)
            if success:
                try:
                    with open(data["txt_path"], "w", encoding="utf-8") as f:
                        f.write(caption)
                    self.root.after(0, lambda item_id=item_id: self.tree.set(item_id, "status", "✅"))
                except Exception as e:
                    print(f"Write error {data['txt_path']}: {e}")
                    self.root.after(0, lambda item_id=item_id: self.tree.set(item_id, "status", "❌"))
            else:
                print(f"Generation failed: {caption}")
                self.root.after(0, lambda item_id=item_id: self.tree.set(item_id, "status", "❌"))
            self.root.after(0, lambda i=i: self.progress_var.set((i + 1) / total * 100))
        self.root.after(0, self.finalize_generation)

    def finalize_generation(self):
        self.generating = False
        status = "Done!" if not self.abort_flag else "Aborted"
        self.status_var.set(status)

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        data = []
        for d in self.selected_files.values():
            caption = ""
            if os.path.exists(d["txt_path"]):
                with open(d["txt_path"], "r", encoding="utf-8") as f:
                    caption = f.read().strip()
            data.append({"filename": d["filename"], "caption": caption})
        if utils.export_to_csv(data, path):
            messagebox.showinfo("Export", "Saved to CSV")
        else:
            messagebox.showerror("Export", "Failed to save CSV")

    def open_replace_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("Find and Replace")
        win.geometry("400x150")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Find:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        find_var = tk.StringVar()
        tk.Entry(win, textvariable=find_var, width=40).grid(row=0, column=1, padx=10, pady=5)

        tk.Label(win, text="Replace:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        replace_var = tk.StringVar()
        tk.Entry(win, textvariable=replace_var, width=40).grid(row=1, column=1, padx=10, pady=5)

        def do_replace():
            find = find_var.get()
            replace = replace_var.get()
            if not find:
                return
            items = self.tree.selection() or self.tree.get_children()
            changed = 0
            for item_id in items:
                data = self.selected_files.get(item_id)
                if data is None:
                    continue
                txt_path = data["txt_path"]
                if os.path.exists(txt_path):
                    with open(txt_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if find in content:
                        new_content = content.replace(find, replace)
                        with open(txt_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        changed += 1
                        self.root.after(0, lambda item_id=item_id: self.tree.set(item_id, "status", "✅"))
            messagebox.showinfo("Replace", f"Updated {changed} files")
            win.destroy()

        tk.Button(win, text="Replace", command=do_replace).grid(row=2, column=1, padx=10, pady=10, sticky="e")