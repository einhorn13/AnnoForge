# plugins/csv_exporter/plugin.py
from tkinter import filedialog
from plugins.api import BatchOperationPlugin
from task_queue import Task # FIXED: Correct import path for Task
import utils
import logging

class CsvExportPlugin(BatchOperationPlugin):
    @property
    def name(self) -> str:
        return "csv_exporter"

    @property
    def display_name(self) -> str:
        return "📤 Export CSV"

    def execute(self):
        """
        Sets up and runs the background job for exporting data to a CSV file.
        The UI part (file dialog) is handled here, while the actual I/O
        is performed in the background task via the TaskQueue.
        """
        output_path = filedialog.asksaveasfilename(
            parent=self.app_context.root,
            title="Export Captions to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not output_path:
            return

        all_item_ids = self.app_context.get_all_item_ids()
        items_to_process = self.app_context.get_items_data(all_item_ids)

        if not items_to_process:
            self.app_context.show_info("Export", "There is no data to export.")
            return

        # Define the task for the background job.
        # This function will be executed ONCE by the TaskQueue.
        def export_task(context, all_items_data, path):
            context.update_status("Exporting all captions to CSV...")
            success = utils.export_to_csv(all_items_data, path)
            if success:
                logging.info(f"Successfully exported {len(all_items_data)} items to {path}")
            else:
                logging.error(f"Failed to export data to {path}")
            return success

        # Create a non-iterating task.
        task = Task(
            name="CSV Export",
            target=export_task,
            args=(items_to_process, output_path) # Pass data and path as args
        )
        
        self.app_context.task_queue.add_task(task)
        self.app_context.show_info("Task Queued", f"CSV export for {len(items_to_process)} items has been added to the queue.")

def register():
    """The entry point for the plugin manager."""
    return CsvExportPlugin()