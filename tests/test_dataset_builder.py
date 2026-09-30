from pathlib import Path

import yaml
from PIL import Image

from pk_studio.core.dataset import DatasetScanner
from pk_studio.core.dataset_builder import build_yolo_dataset, split_items
from pk_studio.core.fileio import atomic_write_text
from pk_studio.core.job_manager import Job


def _make(root: Path, names, labeled=True):
    for n in names:
        p = root / "images" / f"{n}.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 32)).save(p)
        if labeled:
            lp = root / "labels" / f"{n}.txt"
            lp.parent.mkdir(parents=True, exist_ok=True)
            lp.write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")


def test_build_yolo_dataset_creates_training_layout(tmp_path):
    root, out = tmp_path / "src", tmp_path / "out"
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir()
    (root / "classes.txt").write_text("cat\ndog\n", encoding="utf-8")
    for i in range(10):
        Image.new("RGB", (32, 32)).save(root / "images" / f"im{i}.jpg")
        (root / "labels" / f"im{i}.txt").write_text(f"{i % 2} 0.5 0.5 0.5 0.5\n", encoding="utf-8")
    r = build_yolo_dataset(root, out)
    assert sum(r.counts.values()) == 10
    assert (out / "classes.txt").read_text(encoding="utf-8").splitlines() == ["cat", "dog"]
    assert (out / "train" / "images").is_dir()


def test_duplicate_stems_in_subfolders_do_not_overwrite(tmp_path):
    root, out = tmp_path / "src", tmp_path / "out"
    _make(root, ["cam1/frame", "cam2/frame"])
    r = build_yolo_dataset(root, out)
    files = list(out.glob("*/images/*.jpg"))
    assert len(files) == 2 and sum(r.counts.values()) == 2
    for f in files:
        assert (f.parents[1] / "labels" / (f.stem + ".txt")).exists()


def test_copy_background_false_skips_unlabeled(tmp_path):
    root, out = tmp_path / "src", tmp_path / "out"
    _make(root, ["a", "b"])
    _make(root, ["bg"], labeled=False)
    r = build_yolo_dataset(root, out, copy_background=False)
    assert sum(r.counts.values()) == 2
    assert not list(out.glob("*/images/bg.jpg"))


def test_empty_valid_split_falls_back_in_data_yaml(tmp_path):
    root, out = tmp_path / "src", tmp_path / "out"
    _make(root, [f"i{i}" for i in range(6)])
    r = build_yolo_dataset(root, out, train=0.8, valid=0, test=0.2)
    data = yaml.safe_load(r.data_yaml.read_text(encoding="utf-8"))
    assert data["val"] == "train/images"
    assert r.warnings


def test_split_is_deterministic_for_seed(tmp_path):
    _make(tmp_path, [f"i{i}" for i in range(20)])
    items = DatasetScanner.scan(tmp_path).items
    assert split_items(items, seed=3)[0] == split_items(items, seed=3)[0]


def test_scan_reports_bad_labels_without_crashing(tmp_path):
    _make(tmp_path, ["a"], labeled=False)
    (tmp_path / "labels").mkdir()
    (tmp_path / "labels" / "a.txt").write_bytes(bytes([0xFF, 0xFE, 0x00, 0x62]))
    scan = DatasetScanner.scan(tmp_path, ["x"])
    assert scan.image_count == 1 and scan.invalid_labels
    (tmp_path / "labels" / "a.txt").write_text(
        "0 2.0 0.5 0.5 0.5\n-1 0.5 0.5 0.5 0.5\n1 0.5\n", encoding="utf-8")
    scan = DatasetScanner.scan(tmp_path, ["x"])
    assert len(scan.invalid_labels) == 3


def test_atomic_write_leaves_no_temp(tmp_path):
    p = tmp_path / "f.txt"
    atomic_write_text(p, "hi")
    assert p.read_text() == "hi" and not list(tmp_path.glob("*.pk_tmp"))


def test_job_callback_error_not_reported_as_job_error():
    def boom(_job):
        raise RuntimeError("ui")
    job = Job(lambda ev: 1, on_done=boom)
    job._run()
    assert job.status == "done" and job.result == 1


def test_job_target_error_sets_status():
    def bad(ev):
        raise ValueError
    job = Job(bad)
    job._run()
    assert job.status == "error"
