"""PK Studio launcher.

Keeps the project root clean while the application code lives under src/.
"""
from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pk_studio.main import PKStudioApp  # noqa: E402
import tkinter as tk  # noqa: E402

if __name__ == "__main__":
    root = tk.Tk()
    PKStudioApp(root)
    root.mainloop()
