"""Class registry for PK Studio.

The registry keeps the dataset/model class order deterministic while allowing
an explicit user reorder. Display numbering can be 1-based, but YOLO ids stay
0-based on disk.
"""
from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass
class ClassInfo:
    id: int
    name: str


class ClassRegistry:
    def __init__(self, names: Optional[Iterable[str]] = None):
        self._names: List[str] = []
        if names:
            self.load(names)

    @property
    def names(self) -> List[str]:
        return list(self._names)

    def load(self, names: Iterable[str], sort: bool = True) -> None:
        cleaned = []
        seen = set()
        for raw in names:
            name = str(raw).strip()
            if name and name not in seen:
                cleaned.append(name)
                seen.add(name)
        # Keep the existing Roboflow-style deterministic alphabetical default.
        self._names = sorted(cleaned, key=str.casefold) if sort else cleaned

    def index(self, name: str) -> int:
        return self._names.index(name)

    def add(self, name: str, sort: bool = True) -> bool:
        name = str(name).strip()
        if not name or name in self._names:
            return False
        self._names.append(name)
        if sort:
            self._names.sort(key=str.casefold)
        return True

    def remove(self, name_or_index) -> str:
        idx = self._resolve_index(name_or_index)
        return self._names.pop(idx)

    def move(self, index: int, delta: int) -> bool:
        new_index = index + delta
        if not (0 <= index < len(self._names) and 0 <= new_index < len(self._names)):
            return False
        self._names[index], self._names[new_index] = self._names[new_index], self._names[index]
        return True

    def reorder(self, old_index: int, new_index: int) -> bool:
        if not (0 <= old_index < len(self._names) and 0 <= new_index < len(self._names)):
            return False
        item = self._names.pop(old_index)
        self._names.insert(new_index, item)
        return True

    def mapping_to(self, new_names: Iterable[str]) -> dict:
        new_names = list(new_names)
        return {old_id: new_names.index(name) for old_id, name in enumerate(self._names) if name in new_names}

    def _resolve_index(self, value) -> int:
        if isinstance(value, int):
            return value
        return self._names.index(value)
