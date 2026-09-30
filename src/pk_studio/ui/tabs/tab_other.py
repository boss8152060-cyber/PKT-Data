"""PK Studio - Other video utilities.

Keeps secondary video utilities out of the primary DATA workflow.
"""

import importlib.util
from pathlib import Path
from tkinter import messagebox, ttk

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
EXTRACT_FRAMES_SCRIPT = TOOLS_DIR / "extract_frames.py"


def _load_extract_frames_module():
    spec = importlib.util.spec_from_file_location("mvt_extract_frames_other", str(EXTRACT_FRAMES_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OtherTab(ttk.Frame):
    """Secondary media utilities: trim, merge and images-to-video."""

    def __init__(self, parent):
        super().__init__(parent, padding=0)
        if not EXTRACT_FRAMES_SCRIPT.exists():
            ttk.Label(
                self,
                text=f"Missing file: {EXTRACT_FRAMES_SCRIPT}",
                foreground="red",
                padding=20,
            ).pack()
            return
        try:
            module = _load_extract_frames_module()
            frame = module.launch_gui(
                parent=self,
                visible_tools={"trim", "merge", "images_to_video"},
            )
            frame.pack(fill="both", expand=True)
        except Exception as exc:
            messagebox.showerror("Could Not Load Other", f"Unexpected error: {exc}")
            ttk.Label(self, text=f"Load failed: {exc}", foreground="red", padding=20).pack()
