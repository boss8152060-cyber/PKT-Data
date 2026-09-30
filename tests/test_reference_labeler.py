import cv2
import numpy as np

from pk_studio.core.reference_labeler import (
    Proposal, build_references, nms, propose, read_gray, to_yolo_line,
)


def _scene(seed_patch, at, size=(240, 320), noise_seed=0):
    rng = np.random.default_rng(noise_seed)
    img = rng.integers(90, 110, size=size, dtype=np.uint8)
    x, y = at
    h, w = seed_patch.shape
    img[y:y + h, x:x + w] = seed_patch
    return img


def _save(path, img):
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(path))


def test_finds_object_drawn_in_another_image(tmp_path):
    patch = np.random.default_rng(5).integers(0, 255, size=(40, 60), dtype=np.uint8)
    labeled = tmp_path / "a.png"
    _save(labeled, _scene(patch, (50, 60)))
    label = tmp_path / "a.txt"
    # box around the patch at x=50..110, y=60..100 in a 320x240 image
    label.write_text(f"0 {80 / 320:.6f} {80 / 240:.6f} {60 / 320:.6f} {40 / 240:.6f}\n", encoding="utf-8")

    refs = build_references([(labeled, label)])
    assert len(refs) == 1 and refs[0].cls_id == 0

    target = _scene(patch, (200, 150), noise_seed=1)
    result = propose(target, refs, threshold=0.8)
    assert len(result) == 1
    p = result[0]
    assert abs(p.x1 - 200) <= 3 and abs(p.y1 - 150) <= 3 and p.cls_id == 0


def test_excluded_image_is_not_used_as_reference(tmp_path):
    patch = np.random.default_rng(1).integers(0, 255, size=(40, 60), dtype=np.uint8)
    img = tmp_path / "a.png"
    _save(img, _scene(patch, (50, 60)))
    lbl = tmp_path / "a.txt"
    lbl.write_text("0 0.25 0.33 0.19 0.17\n", encoding="utf-8")
    assert build_references([(img, lbl)], exclude=img) == []


def test_no_references_or_flat_patch_gives_no_proposals():
    assert propose(np.zeros((50, 50), np.uint8), []) == []


def test_nms_keeps_best_overlapping_box():
    a = Proposal(0, 0, 0, 10, 10, 0.9)
    b = Proposal(1, 1, 1, 11, 11, 0.8)
    c = Proposal(0, 50, 50, 60, 60, 0.7)
    assert nms([b, a, c]) == [a, c]


def test_yolo_line_is_normalized():
    line = to_yolo_line(Proposal(2, 10, 20, 30, 60, 0.9), 100, 200)
    assert line == "2 0.200000 0.200000 0.200000 0.200000"


def test_read_gray_handles_missing_file(tmp_path):
    assert read_gray(tmp_path / "nope.png") is None
