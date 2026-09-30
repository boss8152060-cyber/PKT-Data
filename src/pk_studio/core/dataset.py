"""Shared YOLO dataset discovery."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class DatasetItem:
    key: str
    image_path: Path
    label_path: Optional[Path]
    class_ids: List[int] = field(default_factory=list)


@dataclass
class DatasetScan:
    root: Path
    items: Dict[str, DatasetItem]
    class_names: List[str]
    invalid_labels: List[str] = field(default_factory=list)

    @property
    def image_count(self) -> int:
        return len(self.items)


class DatasetScanner:
    """Single source of truth for images/labels discovery."""

    @staticmethod
    def find_images_and_labels(source: Path) -> Dict[str, Tuple[Path, Optional[Path]]]:
        """Discover images and matching YOLO labels without stem collisions.

        The key is the image path relative to the image root, so two files such
        as ``cam1/frame001.jpg`` and ``cam2/frame001.jpg`` remain distinct.
        """
        source = Path(source)
        images_dir = source / "images"
        labels_dir = source / "labels"
        image_root = images_dir if images_dir.is_dir() else source
        label_root = labels_dir if labels_dir.is_dir() else source
        result: Dict[str, Tuple[Path, Optional[Path]]] = {}

        for img in sorted(image_root.rglob("*"), key=lambda p: str(p).casefold()):
            if not img.is_file() or img.suffix.casefold() not in IMAGE_EXTENSIONS:
                continue
            rel = img.relative_to(image_root)
            key = rel.with_suffix("").as_posix()
            label = label_root / rel.with_suffix(".txt")
            result[key] = (img, label if label.exists() else None)
        return result

    @staticmethod
    def load_class_names(source: Path, max_class_idx: int = -1) -> List[str]:
        candidates = [Path(source) / "classes.txt", Path(source) / "obj.names"]
        labels_dir = Path(source) / "labels"
        candidates.append(labels_dir / "classes.txt")
        for path in candidates:
            if path.exists():
                names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if names:
                    return names
        return [f"class{i}" for i in range(max_class_idx + 1)]

    @classmethod
    def scan(cls, source: Path, class_names: Optional[List[str]] = None) -> DatasetScan:
        source = Path(source)
        raw = cls.find_images_and_labels(source)
        max_id = -1
        parsed = {}
        invalid = []
        for key, (img, label) in raw.items():
            ids = []
            if label:
                try:
                    lines = label.read_text(encoding="utf-8").splitlines()
                except (OSError, UnicodeError) as exc:
                    invalid.append(f"{label.name} — unreadable: {exc}")
                    lines = []
                for line_no, line in enumerate(lines, 1):
                    parts = line.strip().split()
                    if not parts:
                        continue
                    try:
                        cid = int(parts[0])
                    except ValueError:
                        invalid.append(f"{label.name}:{line_no} — invalid class id")
                        continue
                    if cid < 0:
                        invalid.append(f"{label.name}:{line_no} — negative class id")
                        continue
                    if len(parts) < 5:
                        invalid.append(f"{label.name}:{line_no} — expected YOLO 5+ fields")
                        continue
                    try:
                        coords = [float(x) for x in parts[1:5]]
                    except ValueError:
                        invalid.append(f"{label.name}:{line_no} — non-numeric coordinates")
                        continue
                    if any(not 0.0 <= c <= 1.0 for c in coords):
                        invalid.append(f"{label.name}:{line_no} — coordinates outside 0..1")
                    ids.append(cid)
                    max_id = max(max_id, cid)
            parsed[key] = DatasetItem(key, img, label, ids)
        names = list(class_names) if class_names else cls.load_class_names(source, max_id)
        return DatasetScan(source, parsed, names, invalid)
