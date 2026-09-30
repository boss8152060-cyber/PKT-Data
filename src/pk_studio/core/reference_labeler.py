"""Reference-based auto labeling: label new images from boxes you already drew.

No trained model is needed. Boxes from already-labeled images are cropped into
small reference patches, and each new image is searched for regions that look
like those patches (multi-scale normalized template matching, then NMS).

This is a labeling *assistant*, not a detector: it works best on a fixed camera
or objects that look alike from image to image, and every result should still
be reviewed. The module is independent from Tkinter.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

MAX_CANDIDATES_PER_MATCH = 200


@dataclass
class Reference:
    cls_id: int
    patch: np.ndarray  # grayscale uint8 crop at the original image scale
    source: str


@dataclass
class Proposal:
    cls_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    score: float


def read_gray(path) -> Optional[np.ndarray]:
    """Read an image as grayscale; works with non-ASCII Windows paths."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)


def read_yolo_boxes(label_path) -> List[Tuple[int, float, float, float, float]]:
    """Parse ``cls cx cy w h`` lines, silently skipping malformed ones."""
    boxes = []
    try:
        lines = Path(label_path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return boxes
    for line in lines:
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            cid = int(parts[0])
            cx, cy, w, h = (float(x) for x in parts[1:5])
        except ValueError:
            continue
        if cid >= 0 and w > 0 and h > 0:
            boxes.append((cid, cx, cy, w, h))
    return boxes


def _evenly_spaced(items: list, count: int) -> list:
    if len(items) <= count:
        return list(items)
    idx = np.linspace(0, len(items) - 1, count).round().astype(int)
    return [items[i] for i in dict.fromkeys(idx.tolist())]


def build_references(
    pairs: Sequence[Tuple[Path, Path]],
    valid_class_ids: Optional[Sequence[int]] = None,
    exclude: Optional[Path] = None,
    total_limit: int = 40,
    min_side: int = 12,
    cancel=None,
) -> List[Reference]:
    """Crop reference patches from (image, label) pairs.

    Patches are spread evenly across the labeled images and split evenly between
    classes so a common class cannot crowd out a rare one.
    """
    allowed = set(valid_class_ids) if valid_class_ids is not None else None
    per_class: Dict[int, list] = {}
    for img_path, lbl_path in pairs:
        if exclude is not None and Path(img_path) == Path(exclude):
            continue
        for cid, cx, cy, w, h in read_yolo_boxes(lbl_path):
            if allowed is None or cid in allowed:
                per_class.setdefault(cid, []).append((Path(img_path), cx, cy, w, h))
    if not per_class:
        return []

    quota = max(2, total_limit // len(per_class))
    chosen: Dict[Path, list] = {}
    for cid, entries in per_class.items():
        for img_path, cx, cy, w, h in _evenly_spaced(entries, quota):
            chosen.setdefault(img_path, []).append((cid, cx, cy, w, h))

    refs: List[Reference] = []
    for img_path, boxes in chosen.items():
        if cancel is not None and cancel.is_set():
            break
        gray = read_gray(img_path)
        if gray is None:
            continue
        ih, iw = gray.shape
        for cid, cx, cy, w, h in boxes:
            x1 = max(0, int((cx - w / 2) * iw))
            y1 = max(0, int((cy - h / 2) * ih))
            x2 = min(iw, int((cx + w / 2) * iw))
            y2 = min(ih, int((cy + h / 2) * ih))
            if min(x2 - x1, y2 - y1) < min_side:
                continue
            patch = gray[y1:y2, x1:x2].copy()
            if patch.std() < 2.0:  # flat patches match everything
                continue
            refs.append(Reference(cid, patch, img_path.name))
    return refs


def _iou(a: Proposal, b: Proposal) -> float:
    ix = max(0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    union = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter
    return inter / union if union > 0 else 0.0


def nms(proposals: List[Proposal], iou_threshold: float = 0.4) -> List[Proposal]:
    """Keep the best-scoring box among overlapping ones (across classes too)."""
    kept: List[Proposal] = []
    for p in sorted(proposals, key=lambda p: p.score, reverse=True):
        if all(_iou(p, k) < iou_threshold for k in kept):
            kept.append(p)
    return kept


def propose(
    gray: np.ndarray,
    references: Sequence[Reference],
    threshold: float = 0.7,
    scales: Sequence[float] = (0.85, 1.0, 1.15),
    nms_iou: float = 0.4,
    max_side: int = 960,
    cancel=None,
) -> List[Proposal]:
    """Find regions of ``gray`` that resemble the reference patches."""
    if gray is None or not references:
        return []
    height, width = gray.shape
    shrink = min(1.0, max_side / max(height, width))
    small = gray if shrink >= 1.0 else cv2.resize(
        gray, (max(1, int(width * shrink)), max(1, int(height * shrink))), interpolation=cv2.INTER_AREA)
    sh, sw = small.shape

    found: List[Proposal] = []
    for ref in references:
        for scale in scales:
            if cancel is not None and cancel.is_set():
                return nms(found, nms_iou)
            factor = shrink * scale
            th = int(round(ref.patch.shape[0] * factor))
            tw = int(round(ref.patch.shape[1] * factor))
            if th < 8 or tw < 8 or th >= sh or tw >= sw:
                continue
            tpl = cv2.resize(ref.patch, (tw, th), interpolation=cv2.INTER_AREA)
            if tpl.std() < 1.0:
                continue
            res = cv2.matchTemplate(small, tpl, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(res >= threshold)
            if ys.size == 0:
                continue
            if ys.size > MAX_CANDIDATES_PER_MATCH:
                top = np.argpartition(res[ys, xs], -MAX_CANDIDATES_PER_MATCH)[-MAX_CANDIDATES_PER_MATCH:]
                ys, xs = ys[top], xs[top]
            for y, x in zip(ys.tolist(), xs.tolist()):
                found.append(Proposal(
                    ref.cls_id,
                    int(x / shrink), int(y / shrink),
                    min(width, int((x + tw) / shrink)), min(height, int((y + th) / shrink)),
                    float(res[y, x]),
                ))
    return nms(found, nms_iou)


def to_yolo_line(p: Proposal, width: int, height: int) -> str:
    cx = (p.x1 + p.x2) / 2 / width
    cy = (p.y1 + p.y2) / 2 / height
    return f"{p.cls_id} {cx:.6f} {cy:.6f} {(p.x2 - p.x1) / width:.6f} {(p.y2 - p.y1) / height:.6f}"
