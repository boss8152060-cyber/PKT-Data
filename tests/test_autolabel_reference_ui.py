import cv2
import numpy as np
import pytest


def test_batch_reference_mode_labels_unlabeled_images(tmp_path, monkeypatch):
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    from tkinter import messagebox, simpledialog
    from pk_studio.ui.tabs.tab_autolabeler import AutoLabelerTab

    patch = np.random.default_rng(5).integers(0, 255, size=(40, 60), dtype=np.uint8)
    img_dir, lbl_dir = tmp_path / "images", tmp_path / "labels"
    img_dir.mkdir()
    lbl_dir.mkdir()
    for i, (x, y) in enumerate([(50, 60), (200, 150), (20, 20)]):
        img = np.random.default_rng(i).integers(90, 110, size=(240, 320), dtype=np.uint8)
        img[y:y + 40, x:x + 60] = patch
        cv2.imwrite(str(img_dir / f"f{i}.png"), img)
    (lbl_dir / "f0.txt").write_text("0 0.25 0.333333 0.1875 0.166667\n", encoding="utf-8")

    monkeypatch.setattr(messagebox, "askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: (_ for _ in ()).throw(AssertionError(a)))
    monkeypatch.setattr(simpledialog, "askfloat", lambda *a, **k: 0.8)

    tab = AutoLabelerTab(root)
    tab.img_dir, tab.lbl_dir = str(img_dir), str(lbl_dir)
    tab.image_files = ["f0.png", "f1.png", "f2.png"]
    tab.classes = ["vehicle"]
    tab.apply_image_filters = lambda: None
    tab.calculate_global_statistics = lambda: None
    tab.run_batch_autolabel()
    for _ in range(200):
        root.update()
        if not tab._batch_running:
            break
        root.after(25)
    root.destroy()

    for name, (x, y) in [("f1", (200, 150)), ("f2", (20, 20))]:
        cid, cx, cy, w, h = (lbl_dir / f"{name}.txt").read_text().split()
        assert cid == "0"
        assert abs(float(cx) * 320 - (x + 30)) < 4 and abs(float(cy) * 240 - (y + 20)) < 4
