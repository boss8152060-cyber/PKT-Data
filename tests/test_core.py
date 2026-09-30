import tempfile
from pathlib import Path

from pk_studio.core.class_registry import ClassRegistry
from pk_studio.core.dataset import DatasetScanner


def test_registry_alphabetical_default_and_reorder():
    r = ClassRegistry(["zebra", "car", "Person"])
    assert r.names == ["car", "Person", "zebra"]
    assert r.move(2, -1)
    assert r.names == ["car", "zebra", "Person"]


def test_dataset_scanner_keeps_duplicate_stems_separate():
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "images" / "cam1").mkdir(parents=True)
        (root / "images" / "cam2").mkdir(parents=True)
        (root / "labels" / "cam1").mkdir(parents=True)
        (root / "labels" / "cam2").mkdir(parents=True)
        Image.new("RGB", (10, 10)).save(root / "images" / "cam1" / "frame.jpg")
        Image.new("RGB", (10, 10)).save(root / "images" / "cam2" / "frame.jpg")
        (root / "labels" / "cam1" / "frame.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        scan = DatasetScanner.scan(root, ["person"])
        assert scan.image_count == 2
        assert set(scan.items) == {"cam1/frame", "cam2/frame"}


def test_smart_curator_prioritizes_rare_class():
    from pk_studio.core.smart_curator import greedy_select
    labels = {
        "common_a": ["person"],
        "common_b": ["person"],
        "rare": ["helmet"],
    }
    selected = greedy_select(
        list(labels), labels, {"person": 1, "helmet": 1},
        difficulty={"common_a": 0.0, "common_b": 0.0, "rare": 0.0},
    )
    assert "rare" in selected
    assert len(selected) == 2
