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


def test_smart_curator_diversity_prefers_dissimilar_embedding():
    from pk_studio.core.smart_curator import greedy_select
    labels = {"a": ["x"], "b": ["x"], "c": ["x"]}
    emb = {"a": [1.0, 0.0], "b": [0.99, 0.01], "c": [0.0, 1.0]}
    picked = greedy_select(["a", "b", "c"], labels, {"x": 2}, embeddings=emb)
    assert picked[0] == "a" and picked[1] == "c"


def test_ui_queue_runs_callbacks_on_main_thread():
    import threading
    import tkinter as tk
    import pytest
    from pk_studio.core.job_manager import JobManager, ui_queue_for
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    seen = []
    q = ui_queue_for(root)
    JobManager().start(lambda ev: 7, on_done=lambda j: seen.append((j.result, threading.current_thread() is threading.main_thread())), ui_call=q.call)
    for _ in range(40):
        root.update()
        if seen:
            break
        root.after(25)
    root.destroy()
    assert seen == [(7, True)]
