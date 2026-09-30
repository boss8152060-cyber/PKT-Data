"""Lightweight PK Studio project persistence."""
import json
from pathlib import Path

from pk_studio.core.fileio import atomic_write_text

PROJECT_DIR = ".pkstudio"
PROJECT_FILE = "project.json"


def project_file(dataset_dir) -> Path:
    return Path(dataset_dir) / PROJECT_DIR / PROJECT_FILE


def load_project(dataset_dir) -> dict:
    path = project_file(dataset_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_project(dataset_dir, data: dict) -> Path:
    path = project_file(dataset_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["schema_version"] = 1
    payload["dataset_dir"] = str(Path(dataset_dir).resolve())
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path
