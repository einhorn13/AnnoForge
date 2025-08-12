# AnnoForge.py
# NEW: Import TkinterDnD for drag-and-drop functionality
from tkinterdnd2 import DND_FILES, TkinterDnD

from app import AutoCaptionerApp
from utils import setup_logging

if __name__ == "__main__":
    setup_logging()
    
    # CORRECTED: Use TkinterDnD.Tk as the root window instead of tk.Tk
    root = TkinterDnD.Tk()
    
    app = AutoCaptionerApp(root)
    root.mainloop()