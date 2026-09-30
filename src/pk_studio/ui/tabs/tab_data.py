"""
=========================================================================
PK Studio - Tab: Data (Multi Video Tool — )

Original subprocess  
extract_frames.py  launch_gui()  parent  (
 2  — standalone Original  embedded  — 
 )   2500+
 Multi Video Tool -
launch_gui() 
=========================================================================
"""

import importlib.util
from pathlib import Path
from tkinter import messagebox, ttk

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
EXTRACT_FRAMES_SCRIPT = TOOLS_DIR / "extract_frames.py"


def _load_extract_frames_module():
    """ extract_frames.py  ( import  
     package  tabs/)  module """
    spec = importlib.util.spec_from_file_location("mvt_extract_frames", str(EXTRACT_FRAMES_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DataTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=0)

        if not EXTRACT_FRAMES_SCRIPT.exists():
            ttk.Label(
                self,
                text=f"Missing file: {EXTRACT_FRAMES_SCRIPT}\nPlace extract_frames.py in the tools folder.",
                foreground="red",
                padding=20,
            ).pack()
            return

        try:
            mvt_module = _load_extract_frames_module()
            #  self (ttk.Frame )  parent -> launch_gui() 
            # Multi Video Tool  ttk.Frame 
            # ( standalone Original  extract_frames.py  )
            mvt_frame = mvt_module.launch_gui(parent=self, visible_tools={"extract"})
            mvt_frame.pack(fill="both", expand=True)
        except Exception as exc:
            messagebox.showerror("Could Not Load Video Tool", f"Unexpected error: {exc}")
            ttk.Label(self, text=f"Load failed: {exc}", foreground="red", padding=20).pack()
