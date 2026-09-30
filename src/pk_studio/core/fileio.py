"""Small file helpers shared by core and UI code."""
import os
from pathlib import Path


def atomic_write_text(path, text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` so a crash never leaves a truncated file behind."""
    path = Path(path)
    tmp = path.with_name(path.name + ".pk_tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)
