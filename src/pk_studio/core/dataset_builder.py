"""Build a train/valid/test YOLO dataset from a flat PK Studio dataset."""
from dataclasses import dataclass
from pathlib import Path
import random
import shutil
import yaml

from pk_studio.core.dataset import DatasetScanner, flat_name
from pk_studio.core.fileio import atomic_write_text


@dataclass
class BuildResult:
    output: Path
    counts: dict
    warnings: list[str]
    data_yaml: Path


def _labels_for(item):
    if not item.label_path or not item.label_path.exists():
        return []
    out = []
    try:
        for line in item.label_path.read_text(encoding="utf-8").splitlines():
            p = line.split()
            if p:
                try: out.append(int(p[0]))
                except ValueError: pass
    except OSError:
        pass
    return out


def split_items(items, train=0.7, valid=0.2, test=0.1, seed=0):
    ratios = {"train": float(train), "valid": float(valid), "test": float(test)}
    if any(v < 0 for v in ratios.values()) or sum(ratios.values()) <= 0:
        raise ValueError("split ratios must be non-negative and have a positive total")
    total = sum(ratios.values()); ratios = {k: v / total for k, v in ratios.items()}
    splits = [k for k,v in ratios.items() if v > 0]
    rng = random.Random(seed)
    records = [(k, _labels_for(item)) for k,item in items.items()]
    class_to_keys = {}
    for key, labels in records:
        for cid in set(labels): class_to_keys.setdefault(cid, []).append(key)
    target = {s: len(records) * ratios[s] for s in splits}
    capacity = {s: int(target[s]) for s in splits}
    while sum(capacity.values()) < len(records):
        s = max(splits, key=lambda x: target[x]-capacity[x]); capacity[s]+=1
    while sum(capacity.values()) > len(records):
        s = max(splits, key=lambda x: capacity[x]-target[x]); capacity[s]-=1
    ordered = list(records); rng.shuffle(ordered)
    rarity = {k: sum(1/max(1,len(class_to_keys.get(c,[]))) for c in set(labels)) for k,labels in ordered}
    ordered.sort(key=lambda x: rarity[x[0]], reverse=True)
    assigned = {}
    class_assigned = {c:{s:0 for s in splits} for c in class_to_keys}
    warnings=[]
    for key, labels in ordered:
        available=[s for s in splits if capacity[s]>0]
        labs=set(labels)
        def score(s):
            deficit=sum(max(0, len(class_to_keys[c])*ratios[s]-class_assigned[c][s]) for c in labs if c in class_assigned)
            fit=deficit/max(1,len(labs)) if labs else 0
            return fit + capacity[s]/max(1,len(records)) + rng.random()*1e-6
        chosen=max(available,key=score)
        assigned[key]=chosen; capacity[chosen]-=1
        for c in labs:
            if c in class_assigned: class_assigned[c][chosen]+=1
    for cid, keys in class_to_keys.items():
        if len(keys) < len(splits): warnings.append(f"class {cid}: {len(keys)} image(s), cannot appear in every split")
    return assigned, warnings


def build_yolo_dataset(source, output, train=0.7, valid=0.2, test=0.1, seed=0, copy_background=True):
    source = Path(source).resolve()
    output = Path(output).resolve()
    scan = DatasetScanner.scan(source)
    if not scan.items:
        raise ValueError("No images found in the source dataset.")
    items = scan.items
    if not copy_background:
        items = {k: v for k, v in items.items() if v.label_path and v.label_path.exists()}
        if not items:
            raise ValueError("No labeled images found (copy_background is off).")
    assignment, warnings = split_items(items, train, valid, test, seed)
    counts = {s: 0 for s in ("train", "valid", "test")}
    for key, split in assignment.items():
        item = items[key]
        img_dir = output / split / "images"
        lbl_dir = output / split / "labels"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        stem = flat_name(key)
        shutil.copy2(item.image_path, img_dir / (stem + item.image_path.suffix))
        if item.label_path and item.label_path.exists():
            shutil.copy2(item.label_path, lbl_dir / (stem + ".txt"))
        counts[split] += 1
    for split in ("train", "valid", "test"):
        if counts[split] == 0:
            (output / split / "images").mkdir(parents=True, exist_ok=True)
            (output / split / "labels").mkdir(parents=True, exist_ok=True)
    atomic_write_text(output / "classes.txt", "\n".join(scan.class_names) + "\n")
    payload = {"path": str(output), "train": "train/images", "names": {i: n for i, n in enumerate(scan.class_names)}}
    if counts["valid"] > 0:
        payload["val"] = "valid/images"
    elif counts["train"] > 0:
        payload["val"] = "train/images"
        warnings.append("valid split is empty; data.yaml uses train/images for validation")
    if counts["test"] > 0:
        payload["test"] = "test/images"
    data_yaml = output / "data.yaml"
    atomic_write_text(data_yaml, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    return BuildResult(output, counts, warnings, data_yaml)
