"""
=========================================================================
PK Studio - Tab: Dataset Curator & Splitter

 2  ( = Curator,
 = Splitter) — logic  (must-keep/candidate-pool, embedding,
difficulty  IoU matching, greedy selection, stratified split) 
 4_dataset_curator_gui.py  5_dataset_splitter_gui.py  
 ( difficulty 
 0.5)
=========================================================================
"""

import random
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yaml

from pk_studio.core.dataset import DatasetScanner, flat_name
from pk_studio.core.fileio import atomic_write_text
from pk_studio.core.job_manager import JobManager, ui_queue_for
from pk_studio.core.smart_curator import CuratorWeights, class_rarity


class CuratorSplitterTab(ttk.Frame):
    """ — / Curator  Splitter 
      Curator  Splitter """

    def __init__(self, parent):
        super().__init__(parent, padding=10)

        ttk.Label(
            self, text="✂️ Dataset Curator & Splitter", font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 10))

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        curator_panel = CuratorPanel(paned)
        splitter_panel = SplitterPanel(paned)

        paned.add(curator_panel, weight=1)
        paned.add(splitter_panel, weight=1)


class CuratorPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)

        self.model_path = tk.StringVar()
        self.source_folder = tk.StringVar()
        self.output_folder = tk.StringVar()

        self._model = None
        self._scan_result = None
        self._target_vars = {}
        self._job_manager = JobManager()
        self._active_job = None

        self._build_ui()

    # =================================================================
    # UI
    # =================================================================
    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frame_model = ttk.LabelFrame(self, text="1. Model File (best.pt) — optional ranking aid")
        frame_model.pack(fill="x", **pad)
        ttk.Entry(frame_model, textvariable=self.model_path).pack(
            side="left", fill="x", expand=True, padx=5, pady=5
        )
        ttk.Button(frame_model, text="Browse...", command=self._pick_model).pack(
            side="right", padx=5, pady=5
        )

        frame_src = ttk.LabelFrame(
            self, text="2. Source Dataset (before train/valid/test split)"
        )
        frame_src.pack(fill="x", **pad)
        ttk.Entry(frame_src, textvariable=self.source_folder).pack(
            side="left", fill="x", expand=True, padx=5, pady=5
        )
        ttk.Button(frame_src, text="Browse...", command=self._pick_source).pack(
            side="right", padx=5, pady=5
        )

        frame_out = ttk.LabelFrame(self, text="3. Output Folder (selected dataset)")
        frame_out.pack(fill="x", **pad)
        ttk.Entry(frame_out, textvariable=self.output_folder).pack(
            side="left", fill="x", expand=True, padx=5, pady=5
        )
        ttk.Button(frame_out, text="Browse...", command=self._pick_output).pack(
            side="right", padx=5, pady=5
        )

        self.scan_button = ttk.Button(
            self, text="Scan Dataset", command=self._start_scan
        )
        self.scan_button.pack(pady=6)

        self.class_frame = ttk.LabelFrame(
            self, text="4. Target Images per Class"
        )
        self.class_frame.pack(fill="both", expand=True, **pad)
        ttk.Label(
            self.class_frame,
            text="Use a large value (e.g. 999999) to keep all images for a class.",
            wraplength=580,
        ).pack(padx=5, pady=5)

        button_row = ttk.Frame(self)
        button_row.pack(fill="x", pady=8)
        self.run_button = ttk.Button(
            button_row, text="Start Curation", command=self._start_run, state="disabled"
        )
        self.run_button.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.cancel_button = ttk.Button(button_row, text="Cancel", command=self._cancel_job, state="disabled")
        self.cancel_button.pack(side="left", padx=(4, 0))

        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", padx=10)

        self.status_label = ttk.Label(self, text="Dataset not scanned", wraplength=580)
        self.status_label.pack(padx=10, pady=8)

    def _pick_model(self) -> None:
        path = filedialog.askopenfilename(
            title="Select model file", filetypes=[("PyTorch model", "*.pt")]
        )
        if path:
            self.model_path.set(path)

    def _pick_source(self) -> None:
        path = filedialog.askdirectory(title="Select source dataset")
        if path:
            self.source_folder.set(path)

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.output_folder.set(path)

    # =================================================================
    # :  + /label  +  class
    # =================================================================
    def _start_scan(self) -> None:
        if not self.model_path.get() or not self.source_folder.get():
            messagebox.showwarning("Missing Information", "Select a model file and source dataset before scanning.")
            return
        self.scan_button.config(state="disabled")
        self.status_label.config(text="Scanning...")
        model_path = self.model_path.get()
        source_folder = self.source_folder.get()
        self._active_job = self._job_manager.start(
            lambda cancel: self._scan_job(cancel, model_path, source_folder),
            ui_call=ui_queue_for(self).call,
        )

    @staticmethod
    def _find_images_and_labels(source: Path):
        """Use the shared DatasetScanner so every tab discovers datasets identically."""
        return DatasetScanner.find_images_and_labels(source)

    def _scan_job(self, cancel_event=None, model_path=None, source_folder=None) -> None:
        try:
            from ultralytics import YOLO
        except ImportError:
            self._show_error("Ultralytics is not installed. Please run: pip install ultralytics")
            return

        try:
            model_path = model_path or self.model_path.get()
            source_folder = source_folder or self.source_folder.get()
            if self._model is None or getattr(self._model, "ckpt_path", None) != model_path:
                self._model = YOLO(model_path)
            model = self._model

            names_dict = model.names
            class_names = [names_dict[i] for i in range(len(names_dict))]

            source = Path(source_folder)
            image_files = self._find_images_and_labels(source)
            if not image_files:
                self._show_error(
                    "No image files found in the selected folder. Check the dataset layout."
                )
                return

            image_labels = {}
            for stem, (img_path, label_path) in image_files.items():
                labels_here = []
                if label_path is not None:
                    with open(label_path, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            cls_idx = int(line.split()[0])
                            if 0 <= cls_idx < len(class_names):
                                labels_here.append(class_names[cls_idx])
                image_labels[stem] = labels_here

            current_image_count = {
                c: sum(1 for labs in image_labels.values() if c in labs) for c in class_names
            }

            self._scan_result = {
                "class_names": class_names,
                "image_files": image_files,
                "image_labels": image_labels,
                "current_image_count": current_image_count,
            }

            self.after(0, self._build_class_rows, class_names, current_image_count, len(image_files))

        except Exception as exc:
            self._show_error(f"Scan failed: {exc}")

    def _build_class_rows(self, class_names, current_image_count, n_images) -> None:
        for widget in self.class_frame.winfo_children():
            widget.destroy()

        ttk.Label(
            self.class_frame,
            text=f"Found {n_images} images — use a large target to keep all images.",
            wraplength=580,
        ).grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w")

        ttk.Label(self.class_frame, text="Class", font=("", 9, "bold")).grid(
            row=1, column=0, padx=5, sticky="w"
        )
        ttk.Label(self.class_frame, text="Current Images", font=("", 9, "bold")).grid(
            row=1, column=1, padx=5, sticky="w"
        )
        ttk.Label(self.class_frame, text="Target Images", font=("", 9, "bold")).grid(
            row=1, column=2, padx=5, sticky="w"
        )

        self._target_vars = {}
        for i, c in enumerate(class_names, start=2):
            current = current_image_count.get(c, 0)
            ttk.Label(self.class_frame, text=c).grid(row=i, column=0, padx=5, pady=2, sticky="w")
            ttk.Label(self.class_frame, text=str(current)).grid(row=i, column=1, padx=5, pady=2)
            target_var = tk.StringVar(value=str(current))
            ttk.Entry(self.class_frame, textvariable=target_var, width=10).grid(
                row=i, column=2, padx=5, pady=2
            )
            self._target_vars[c] = target_var

        self.scan_button.config(state="normal")
        self.run_button.config(state="normal")
        self.status_label.config(
            text=f"Scan complete: {n_images} images. Set targets and start curation."
        )

    # =================================================================
    # 
    # =================================================================
    def _start_run(self) -> None:
        if self._scan_result is None:
            messagebox.showwarning("Not Scanned", "Scan the dataset first.")
            return
        if not self.output_folder.get():
            messagebox.showwarning("Missing Information", "Select an output folder first.")
            return

        try:
            target_counts = {c: int(v.get()) for c, v in self._target_vars.items()}
        except ValueError:
            messagebox.showerror("Invalid Number", "Target values must be whole numbers.")
            return

        self.run_button.config(state="disabled")
        self.scan_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.status_label.config(text="Curating dataset...")
        target_counts_snapshot = dict(target_counts)
        output_folder = self.output_folder.get()
        self._active_job = self._job_manager.start(
            lambda cancel: self._run_job(cancel, target_counts_snapshot, output_folder),
            ui_call=ui_queue_for(self).call,
        )

    def _run_job(self, cancel_event, target_counts: dict, output_folder: str) -> None:
        try:
            import torch

            scan = self._scan_result
            class_names = scan["class_names"]
            image_files = scan["image_files"]
            image_labels = scan["image_labels"]
            current_image_count = scan["current_image_count"]
            model = self._model

            # ----  must_keep ()  candidate_pool () ----
            over_target_classes = {c for c in class_names if target_counts[c] < current_image_count[c]}
            protected_classes = set(class_names) - over_target_classes
            must_keep_stems = {
                stem for stem, labs in image_labels.items()
                if not labs or any(c in protected_classes for c in labs)
            }
            candidate_pool_stems = list(set(image_labels.keys()) - must_keep_stems)

            base_count = {c: sum(1 for s in must_keep_stems if c in image_labels[s]) for c in over_target_classes}
            remaining_quota = {c: max(0, target_counts[c] - base_count[c]) for c in over_target_classes}

            self._log(f"must_keep: {len(must_keep_stems)} images, candidate_pool: {len(candidate_pool_stems)} ")

            selected_stems = []
            if cancel_event.is_set():
                return
            if candidate_pool_stems and any(v > 0 for v in remaining_quota.values()):
                # ----  embedding () — batch  + auto-retry  OOM ----
                self.after(0, lambda: self.status_label.config(
                    text=f"Computing embeddings for {len(candidate_pool_stems)} images..."
                ))
                candidate_paths = [str(image_files[s][0]) for s in candidate_pool_stems]

                def embed_progress(done, total):
                    self.after(0, lambda: self.status_label.config(
                        text=f"Computing embeddings {done}/{total}..."
                    ))

                raw_embeddings = self._run_with_oom_retry(
                    model, candidate_paths, initial_batch_size=8, progress_cb=embed_progress
                )
                embeddings_map = {}
                for stem, emb in zip(candidate_pool_stems, raw_embeddings):
                    emb = emb.float()
                    embeddings_map[stem] = emb / (emb.norm() + 1e-8)

                # ----  difficulty ( predict  label ) ----
                self.after(0, lambda: self.status_label.config(
                    text="Computing difficulty (prediction vs. ground truth)..."
                ))
                difficulty_map = self._compute_difficulty(model, class_names, candidate_pool_stems, image_files)

                # ---- greedy selection ----
                self.after(0, lambda: self.status_label.config(text="Selecting images..."))
                remaining = dict(remaining_quota)
                pool = list(candidate_pool_stems)
                selected_embeds = []

                # Smart Curator: rare classes receive a controlled bonus while
                # preserving the proven diversity/difficulty/relevance heuristic.
                class_to_images = {c: [] for c in over_target_classes}
                for stem in candidate_pool_stems:
                    for c in set(image_labels.get(stem, [])):
                        if c in class_to_images:
                            class_to_images[c].append(stem)
                rarity = class_rarity(class_to_images)
                weights = CuratorWeights()

                while pool and any(v > 0 for v in remaining.values()):
                    if cancel_event.is_set():
                        return
                    best_score, best_i = -1e18, None
                    for i, stem in enumerate(pool):
                        labs = image_labels[stem]
                        relevant_classes = [c for c in labs if remaining.get(c, 0) > 0]
                        relevance = len(relevant_classes)
                        if relevance == 0:
                            continue
                        if selected_embeds:
                            sims = torch.stack([torch.dot(embeddings_map[stem], e) for e in selected_embeds])
                            diversity = 1.0 - float(sims.max())
                        else:
                            diversity = 1.0
                        rarity_score = sum(rarity.get(c, 0.0) for c in relevant_classes) / relevance
                        multi_label_bonus = max(0, relevance - 1)
                        score = (
                            weights.diversity * diversity
                            + weights.difficulty * difficulty_map[stem]
                            + weights.relevance * relevance
                            + weights.rarity * rarity_score
                            + weights.multi_label * multi_label_bonus
                        )
                        if score > best_score:
                            best_score, best_i = score, i

                    if best_i is None:
                        break

                    stem = pool.pop(best_i)
                    selected_stems.append(stem)
                    selected_embeds.append(embeddings_map[stem])
                    for c in image_labels[stem]:
                        if c in remaining:
                            remaining[c] = max(0, remaining[c] - 1)

                self._log(f" candidate_pool  {len(selected_stems)} ")

            final_stems = must_keep_stems | set(selected_stems)

            # ----  ----
            self.after(0, lambda: self.status_label.config(text="Copying files..."))
            output = Path(output_folder)
            images_out = output / "images"
            labels_out = output / "labels"
            images_out.mkdir(parents=True, exist_ok=True)
            labels_out.mkdir(parents=True, exist_ok=True)

            self.after(0, lambda: self.progress.config(maximum=len(final_stems), value=0))
            for idx, stem in enumerate(final_stems, start=1):
                img_path, label_path = image_files[stem]
                shutil.copy2(img_path, images_out / flat_name(stem, img_path.suffix))
                if label_path is not None:
                    shutil.copy2(label_path, labels_out / flat_name(stem, '.txt'))
                if idx % 20 == 0 or idx == len(final_stems):
                    self.after(0, self._update_progress, idx, len(final_stems))

            final_image_count = {c: sum(1 for s in final_stems if c in image_labels[s]) for c in class_names}
            summary_lines = [f"Complete! Original images {len(image_labels)} -> selected images {len(final_stems)}", ""]
            summary_lines.append(f"{'Class':<15}{'Original':>8}{'Target':>10}{'Actual':>10}")
            for c in class_names:
                summary_lines.append(
                    f"{c:<15}{current_image_count[c]:>8}{target_counts[c]:>10}{final_image_count[c]:>10}"
                )
            summary_lines.append("")
            summary_lines.append(f"Output: {output.resolve()}")
            summary = "\n".join(summary_lines)

            self.after(0, lambda: self.status_label.config(text=summary))
            self.after(0, lambda: self.run_button.config(state="normal"))
            self.after(0, lambda: self.scan_button.config(state="normal"))
            self.after(0, lambda: self.cancel_button.config(state="disabled"))

        except Exception as exc:
            self._show_error(f"Unexpected error: {exc}")

    @staticmethod
    def _run_with_oom_retry(model, paths, initial_batch_size, progress_cb=None):
        """ model.embed()   (batch) 
        ( CUDA out of memory  VRAM ) —  OOM 
         batch size   batch=1
         OOM  (   error )"""
        import torch

        results = []
        i = 0
        batch_size = initial_batch_size
        while i < len(paths):
            batch = paths[i:i + batch_size]
            try:
                out = model.embed(batch, verbose=False)
                results.extend(out)
                i += len(batch)
                if progress_cb is not None:
                    progress_cb(i, len(paths))
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if batch_size == 1:
                    raise RuntimeError(
                        " VRAM  1  —  GPU  "
                        " ( yolo26n/yolo26s  yolo26m)"
                    )
                batch_size = max(1, batch_size // 2)
        return results

    @staticmethod
    def _predict_with_oom_retry(model, paths, initial_batch_size, conf):
        """ _run_with_oom_retry  model.predict()"""
        import torch

        results = []
        i = 0
        batch_size = initial_batch_size
        while i < len(paths):
            batch = paths[i:i + batch_size]
            try:
                out = model.predict(batch, verbose=False, conf=conf)
                results.extend(out)
                i += len(batch)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if batch_size == 1:
                    raise RuntimeError(
                        " VRAM  1  —  GPU  "
                        " ( yolo26n/yolo26s  yolo26m)"
                    )
                batch_size = max(1, batch_size // 2)
        return results

    @staticmethod
    def _compute_difficulty(model, class_names, candidate_pool_stems, image_files):
        """ predict  label   difficulty score (0=,
        1=/)  —  IoU >= 0.5 + class """

        def yolo_txt_to_xyxy(label_path, img_w, img_h):
            boxes = []
            if label_path is None:
                return boxes
            with open(label_path, encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) != 5:
                        continue
                    cls_idx, cx, cy, w, h = int(parts[0]), *map(float, parts[1:])
                    if not (0 <= cls_idx < len(class_names)):
                        continue
                    x1 = (cx - w / 2) * img_w
                    y1 = (cy - h / 2) * img_h
                    x2 = (cx + w / 2) * img_w
                    y2 = (cy + h / 2) * img_h
                    boxes.append([x1, y1, x2, y2, class_names[cls_idx]])
            return boxes

        def iou_xyxy(box_a, box_b):
            xa1, ya1, xa2, ya2 = box_a
            xb1, yb1, xb2, yb2 = box_b
            ix1, iy1 = max(xa1, xb1), max(ya1, yb1)
            ix2, iy2 = min(xa2, xb2), min(ya2, yb2)
            iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
            inter = iw * ih
            area_a = max(0.0, xa2 - xa1) * max(0.0, ya2 - ya1)
            area_b = max(0.0, xb2 - xb1) * max(0.0, yb2 - yb1)
            union = area_a + area_b - inter
            return inter / union if union > 0 else 0.0

        IOU_MATCH_THRESHOLD = 0.5
        difficulty_map = {}
        candidate_paths = [str(image_files[s][0]) for s in candidate_pool_stems]
        results = CuratorPanel._predict_with_oom_retry(
            model, candidate_paths, initial_batch_size=8, conf=0.15
        )

        for stem, result in zip(candidate_pool_stems, results):
            img_w, img_h = result.orig_shape[1], result.orig_shape[0]
            _, label_path = image_files[stem]
            gt_boxes = yolo_txt_to_xyxy(label_path, img_w, img_h)

            if not gt_boxes:
                difficulty_map[stem] = 0.0
                continue

            pred_boxes = result.boxes.xyxy.cpu().numpy()
            pred_cls = [class_names[int(c)] for c in result.boxes.cls.cpu().numpy()]
            pred_conf = result.boxes.conf.cpu().numpy()

            per_box_difficulty = []
            for gx1, gy1, gx2, gy2, gt_cls in gt_boxes:
                best_iou, best_conf = 0.0, 0.0
                for (px1, py1, px2, py2), p_cls, p_conf in zip(pred_boxes, pred_cls, pred_conf):
                    if p_cls != gt_cls:
                        continue
                    iou = iou_xyxy((gx1, gy1, gx2, gy2), (px1, py1, px2, py2))
                    if iou > best_iou:
                        best_iou, best_conf = iou, p_conf
                per_box_difficulty.append(1.0 - float(best_conf) if best_iou >= IOU_MATCH_THRESHOLD else 1.0)

            difficulty_map[stem] = sum(per_box_difficulty) / len(per_box_difficulty)

        return difficulty_map

    def _update_progress(self, current: int, total: int) -> None:
        self.progress.config(value=current)
        self.status_label.config(text=f"Copying files {current}/{total}...")

    def _log(self, message: str) -> None:
        self.after(0, lambda: self.status_label.config(text=message))

    def _show_error(self, message: str) -> None:
        self.after(0, lambda: messagebox.showerror("Error", message))
        self.after(0, lambda: self.run_button.config(state="normal"))
        self.after(0, lambda: self.scan_button.config(state="normal"))
        self.after(0, lambda: self.cancel_button.config(state="disabled"))

    def _cancel_job(self) -> None:
        if self._active_job and self._active_job.status in {"pending", "running", "cancelling"}:
            self._active_job.cancel()
            self.status_label.config(text="Cancelling...")


class SplitterPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)

        self.source_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.classes_file = tk.StringVar()  #  classes.txt  data.yaml (  class)
        self.train_pct = tk.StringVar(value="70")
        self.valid_pct = tk.StringVar(value="20")
        self.test_pct = tk.StringVar(value="10")

        self._scan_result = None
        self._job_manager = JobManager()
        self._active_job = None

        self._build_ui()

    # =================================================================
    # UI
    # =================================================================
    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frame_src = ttk.LabelFrame(self, text="1. Source Dataset (before split)")
        frame_src.pack(fill="x", **pad)
        ttk.Entry(frame_src, textvariable=self.source_folder).pack(
            side="left", fill="x", expand=True, padx=5, pady=5
        )
        ttk.Button(frame_src, text="Browse...", command=self._pick_source).pack(
            side="right", padx=5, pady=5
        )

        frame_out = ttk.LabelFrame(self, text="2. Output Dataset")
        frame_out.pack(fill="x", **pad)
        ttk.Entry(frame_out, textvariable=self.output_folder).pack(
            side="left", fill="x", expand=True, padx=5, pady=5
        )
        ttk.Button(frame_out, text="Browse...", command=self._pick_output).pack(
            side="right", padx=5, pady=5
        )

        frame_classes = ttk.LabelFrame(
            self, text="3. classes.txt (optional)"
        )
        frame_classes.pack(fill="x", **pad)
        ttk.Entry(frame_classes, textvariable=self.classes_file).pack(
            side="left", fill="x", expand=True, padx=5, pady=5
        )
        ttk.Button(frame_classes, text="Browse...", command=self._pick_classes_file).pack(
            side="right", padx=5, pady=5
        )

        frame_ratio = ttk.LabelFrame(self, text="4. Train / Valid / Test Split (%)")
        frame_ratio.pack(fill="x", **pad)
        row = ttk.Frame(frame_ratio)
        row.pack(padx=5, pady=8)
        ttk.Label(row, text="train:").pack(side="left")
        ttk.Entry(row, textvariable=self.train_pct, width=6).pack(side="left", padx=(4, 16))
        ttk.Label(row, text="valid:").pack(side="left")
        ttk.Entry(row, textvariable=self.valid_pct, width=6).pack(side="left", padx=(4, 16))
        ttk.Label(row, text="test:").pack(side="left")
        ttk.Entry(row, textvariable=self.test_pct, width=6).pack(side="left", padx=(4, 16))
        ttk.Label(row, text="(must total 100)").pack(side="left")

        self.scan_button = ttk.Button(
            self, text="Scan Dataset", command=self._start_scan
        )
        self.scan_button.pack(pady=6)

        self.summary_text = tk.Text(self, height=10, wrap="word", state="disabled")
        self.summary_text.pack(fill="both", expand=True, padx=10, pady=4)

        button_row = ttk.Frame(self)
        button_row.pack(fill="x", pady=8)
        self.run_button = ttk.Button(
            button_row, text="Start Split", command=self._start_run, state="disabled"
        )
        self.run_button.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.cancel_button = ttk.Button(button_row, text="Cancel", command=self._cancel_job, state="disabled")
        self.cancel_button.pack(side="left", padx=(4, 0))

        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", padx=10)

        self.status_label = ttk.Label(self, text="Dataset not scanned", wraplength=580)
        self.status_label.pack(padx=10, pady=8)

    def _pick_source(self) -> None:
        path = filedialog.askdirectory(title="Select source dataset")
        if path:
            self.source_folder.set(path)

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.output_folder.set(path)

    def _pick_classes_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select classes.txt", filetypes=[("Text/YAML", "*.txt *.yaml *.yml"), ("All files", "*.*")]
        )
        if path:
            self.classes_file.set(path)

    # =================================================================
    # 
    # =================================================================
    @staticmethod
    def _find_images_and_labels(source: Path):
        return DatasetScanner.find_images_and_labels(source)

    @staticmethod
    def _load_class_names(classes_file_str: str, max_class_idx: int):
        """ class  classes.txt ( 1 )  data.yaml (key names)
          class0, class1, ...  (
          classes.txt  data.yaml )"""
        if classes_file_str:
            p = Path(classes_file_str)
            if p.suffix.lower() in (".yaml", ".yml"):
                import yaml

                with open(p, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                names = cfg.get("names")
                if isinstance(names, dict):
                    return [names[i] for i in range(len(names))]
                return list(names)
            else:
                with open(p, encoding="utf-8") as f:
                    return [line.strip() for line in f if line.strip()]
        return [f"class{i}" for i in range(max_class_idx + 1)]

    def _start_scan(self) -> None:
        if not self.source_folder.get():
            messagebox.showwarning("Missing Information", "Select a source dataset first.")
            return
        self.scan_button.config(state="disabled")
        self.status_label.config(text="Scanning...")
        source_folder = self.source_folder.get()
        classes_file = self.classes_file.get()
        self._active_job = self._job_manager.start(
            lambda cancel: self._scan_job(cancel, source_folder, classes_file),
            ui_call=ui_queue_for(self).call,
        )

    def _scan_job(self, cancel_event=None, source_folder=None, classes_file=None) -> None:
        try:
            source_folder = source_folder or self.source_folder.get()
            classes_file = classes_file if classes_file is not None else self.classes_file.get()

            source = Path(source_folder)
            image_files = self._find_images_and_labels(source)
            if not image_files:
                self._show_error(
                    "No image files found in the selected folder. Check the dataset layout."
                )
                return

            image_labels = {}  # stem -> list of class index (int)
            max_class_idx = -1
            for stem, (img_path, label_path) in image_files.items():
                labels_here = []
                if label_path is not None:
                    with open(label_path, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            cls_idx = int(line.split()[0])
                            labels_here.append(cls_idx)
                            max_class_idx = max(max_class_idx, cls_idx)
                image_labels[stem] = labels_here

            class_names = self._load_class_names(classes_file, max_class_idx)

            current_count = {i: sum(1 for labs in image_labels.values() if i in labs) for i in range(len(class_names))}
            n_background = sum(1 for labs in image_labels.values() if not labs)

            self._scan_result = {
                "image_files": image_files,
                "image_labels": image_labels,
                "class_names": class_names,
                "current_count": current_count,
                "n_background": n_background,
            }

            self.after(0, self._show_scan_summary, class_names, current_count, n_background, len(image_files))

        except Exception as exc:
            self._show_error(f"Scan failed: {exc}")

    def _show_scan_summary(self, class_names, current_count, n_background, n_total) -> None:
        lines = [f"Found {n_total} images ({n_background} background images)", ""]
        lines.append(f"{'Class':<15}{'Images':>10}")
        for i, name in enumerate(class_names):
            warn = ""
            c = current_count[i]
            if 0 < c < 3:
                warn = "  ⚠ Too few images to populate all three splits."
            lines.append(f"{name:<15}{c:>10}{warn}")

        self.summary_text.config(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", "\n".join(lines))
        self.summary_text.config(state="disabled")

        self.scan_button.config(state="normal")
        self.run_button.config(state="normal")
        self.status_label.config(text="Scan complete. Review the split and start.")

    # =================================================================
    #  (Iterative Stratified Split)
    # =================================================================
    def _start_run(self) -> None:
        if self._scan_result is None:
            messagebox.showwarning("Not Scanned", "Scan the dataset first.")
            return
        if not self.output_folder.get():
            messagebox.showwarning("Missing Information", "Select an output folder first.")
            return

        try:
            train_p = float(self.train_pct.get())
            valid_p = float(self.valid_pct.get())
            test_p = float(self.test_pct.get())
        except ValueError:
            messagebox.showerror("Invalid Number", "Train/valid/test ratios must be numeric.")
            return

        if abs((train_p + valid_p + test_p) - 100) > 0.01:
            messagebox.showerror("Split Total Error", f"Current total is {train_p + valid_p + test_p}; it must equal 100.")
            return

        self.run_button.config(state="disabled")
        self.scan_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.status_label.config(text="Splitting dataset...")
        output_folder = self.output_folder.get()
        self._active_job = self._job_manager.start(
            lambda cancel: self._run_job(cancel, train_p / 100, valid_p / 100, test_p / 100, output_folder),
            ui_call=ui_queue_for(self).call,
        )

    @staticmethod
    def _stratified_split(image_labels: dict, class_names: list, train_ratio: float, valid_ratio: float, test_ratio: float, seed: int = 0):
        """Deterministic greedy iterative multilabel split.

        Rare classes are assigned first. Each image is placed into the split
        with the largest remaining demand across its labels, while also
        respecting global split capacity. This is closer to multilabel
        stratification than assigning each class independently because an image
        is assigned exactly once and contributes to every class it contains.
        """
        rng = random.Random(seed)
        ratios = {"train": train_ratio, "valid": valid_ratio, "test": test_ratio}
        splits = tuple(k for k, v in ratios.items() if v > 0)
        if not splits:
            raise ValueError("At least one split ratio must be greater than 0.")

        # Normalize tiny floating point drift.
        total_ratio = sum(ratios.values())
        ratios = {k: v / total_ratio for k, v in ratios.items()}
        stems = list(image_labels)
        rng.shuffle(stems)

        class_to_images = {i: [] for i in range(len(class_names))}
        for stem, labs in image_labels.items():
            for c in set(labs):
                if isinstance(c, int) and 0 <= c < len(class_names):
                    class_to_images[c].append(stem)

        target_images = {s: len(stems) * ratios[s] for s in splits}
        capacities = {s: int(round(target_images[s])) for s in splits}
        # Ensure capacities sum exactly to N.
        while sum(capacities.values()) < len(stems):
            s = max(splits, key=lambda x: target_images[x] - capacities[x])
            capacities[s] += 1
        while sum(capacities.values()) > len(stems):
            s = max(splits, key=lambda x: capacities[x] - target_images[x])
            if capacities[s] > 0:
                capacities[s] -= 1

        class_targets = {
            c: {s: len(class_to_images[c]) * ratios[s] for s in splits}
            for c in class_to_images
        }
        class_assigned = {c: {s: 0 for s in splits} for c in class_to_images}
        assignment = {}
        warnings = []

        # Rare / highly constrained images first. Multi-label images get a
        # small priority bonus because assigning them incorrectly affects more classes.
        def image_priority(stem):
            labs = set(image_labels.get(stem, []))
            rarity = sum(1.0 / max(1, len(class_to_images.get(c, []))) for c in labs)
            return rarity + 0.15 * max(0, len(labs) - 1)

        ordered = sorted(stems, key=image_priority, reverse=True)

        for stem in ordered:
            labs = {c for c in image_labels.get(stem, []) if c in class_to_images}
            available = [s for s in splits if capacities[s] > 0]
            if not available:
                break

            def score(split):
                capacity_pressure = capacities[split] / max(1, len(stems))
                if labs:
                    deficit = sum(max(0.0, class_targets[c][split] - class_assigned[c][split]) for c in labs)
                    total_target = sum(max(1e-9, class_targets[c][split]) for c in labs)
                    class_fit = deficit / total_target
                else:
                    class_fit = 0.0
                global_fit = max(0.0, (target_images[split] - (len(stems) - sum(capacities.values()))) / max(1.0, target_images[split]))
                return class_fit * 3.0 + capacity_pressure + global_fit * 0.25 + rng.random() * 1e-6

            chosen = max(available, key=score)
            assignment[stem] = chosen
            capacities[chosen] -= 1
            for c in labs:
                class_assigned[c][chosen] += 1

        # Safety fallback (should only trigger on pathological input).
        for stem in stems:
            if stem not in assignment:
                chosen = max(splits, key=lambda s: capacities[s])
                assignment[stem] = chosen
                capacities[chosen] = max(0, capacities[chosen] - 1)

        for c, name in enumerate(class_names):
            count = len(class_to_images[c])
            if count == 1:
                warnings.append(f"{name}: only 1 image; it cannot be distributed across all splits.")
            elif count == 2 and len(splits) >= 3:
                warnings.append(f"{name}: only 2 images; it cannot represent all three splits.")

        return assignment, warnings

    def _run_job(self, cancel_event, train_ratio: float, valid_ratio: float, test_ratio: float, output_folder: str) -> None:
        try:
            scan = self._scan_result
            image_files = scan["image_files"]
            image_labels = scan["image_labels"]
            class_names = scan["class_names"]

            assignment, warnings = self._stratified_split(
                image_labels, class_names, train_ratio, valid_ratio, test_ratio
            )

            output = Path(output_folder)
            for split in ("train", "valid", "test"):
                (output / split / "images").mkdir(parents=True, exist_ok=True)
                (output / split / "labels").mkdir(parents=True, exist_ok=True)

            self.after(0, lambda: self.progress.config(maximum=len(assignment), value=0))
            for idx, (stem, split) in enumerate(assignment.items(), start=1):
                if cancel_event.is_set():
                    return
                img_path, label_path = image_files[stem]
                shutil.copy2(img_path, output / split / "images" / flat_name(stem, img_path.suffix))
                if label_path is not None:
                    shutil.copy2(label_path, output / split / "labels" / flat_name(stem, ".txt"))
                if idx % 20 == 0 or idx == len(assignment):
                    self.after(0, self._update_progress, idx, len(assignment))

            #  
            split_counts = {"train": 0, "valid": 0, "test": 0}
            for split in assignment.values():
                split_counts[split] += 1

            data_yaml_path = output / "data.yaml"
            atomic_write_text(data_yaml_path, yaml.safe_dump(
    {"train": "train/images", "val": "valid/images", "test": "test/images",
     "nc": len(class_names), "names": list(class_names)},
    sort_keys=False, allow_unicode=True))

            summary_lines = [
                f"Split complete: train={split_counts['train']}, "
                f"valid={split_counts['valid']}, test={split_counts['test']}",
                f"Created data.yaml at: {data_yaml_path}",
            ]
            if warnings:
                summary_lines.append("")
                summary_lines.append("Warnings (classes with too few images for all three splits):")
                summary_lines.extend(f"  - {w}" for w in warnings)
            summary_lines.append("")
            summary_lines.append(f"Output: {output.resolve()}")
            summary = "\n".join(summary_lines)

            self.after(0, lambda: self.status_label.config(text=summary))
            self.after(0, lambda: self.run_button.config(state="normal"))
            self.after(0, lambda: self.scan_button.config(state="normal"))
            self.after(0, lambda: self.cancel_button.config(state="disabled"))

        except Exception as exc:
            self._show_error(f"Unexpected error: {exc}")

    def _update_progress(self, current: int, total: int) -> None:
        self.progress.config(value=current)
        self.status_label.config(text=f"Copying files {current}/{total}...")

    def _show_error(self, message: str) -> None:
        self.after(0, lambda: messagebox.showerror("Error", message))
        self.after(0, lambda: self.run_button.config(state="normal"))
        self.after(0, lambda: self.scan_button.config(state="normal"))

    def _cancel_job(self) -> None:
        if self._active_job and self._active_job.status in {"pending", "running", "cancelling"}:
            self._active_job.cancel()
            self.status_label.config(text="Cancelling...")
