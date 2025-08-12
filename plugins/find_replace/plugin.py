# plugins/find_replace/plugin.py
import tkinter as tk
from tkinter import ttk
from plugins.api import BatchOperationPlugin
import logging

class FindReplacePlugin(BatchOperationPlugin):
    @property
    def name(self) -> str: return "find_replace"
    @property
    def display_name(self) -> str: return "🔍 Replace"

    def execute(self):
        self._show_dialog()

    def _show_dialog(self):
        win = tk.Toplevel(self.app_context.root)
        win.title("Find and Replace in Captions")
        win.geometry("400x150")
        win.transient(self.app_context.root); win.grab_set()

        ttk.Label(win, text="Find:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        find_var = tk.StringVar()
        ttk.Entry(win, textvariable=find_var, width=40).grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(win, text="Replace:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        replace_var = tk.StringVar()
        ttk.Entry(win, textvariable=replace_var, width=40).grid(row=1, column=1, padx=10, pady=5)

        def start_replace_job():
            find_text = find_var.get()
            replace_text = replace_var.get()
            if not find_text: return
            
            checked_ids = self.app_context.get_checked_item_ids()
            if not checked_ids:
                self.app_context.show_info("Selection", "No items are checked. The operation will apply to ALL items.")
                items_to_process = self.app_context.get_items_data(self.app_context.get_all_item_ids())
            else:
                items_to_process = self.app_context.get_items_data(checked_ids)

            # This task will be executed for each item by the TaskQueue
            def replace_task(item_data, context):
                original_caption = item_data.get("caption", "")
                if find_text not in original_caption:
                    return None # Returning None skips logging/counting this as a failure
                
                new_caption = original_caption.replace(find_text, replace_text)
                # Use data_provider from context to save, ensuring it's the right one
                if context.data_provider.save_item_data(item_data["item_id"], {"caption": new_caption}):
                    # Request UI update for the changed item via an event
                    context.event_bus.publish("data:caption_saved", item_data["item_id"])
                    return True
                else:
                    logging.error(f"Failed to save caption for {item_data['filename']}")
                    return False

            # CORRECTED: Use the unified run_job method
            self.app_context.run_job(replace_task, items_to_process, "Find & Replace")
            win.destroy()

        ttk.Button(win, text="Replace in Checked (or All)", command=start_replace_job).grid(row=2, column=1, padx=10, pady=10, sticky="e")

def register():
    return FindReplacePlugin()