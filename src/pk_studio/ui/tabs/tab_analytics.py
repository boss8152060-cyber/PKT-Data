"""
=========================================================================
PK Studio - Tab: Analytics & Insights

+label  Dataset Curator/Splitter 
 ( images/+labels/  +.txt 
)

 3  (Histogram, Heat Map, Dimension Insights)  matplotlib
 ultralytics  ( dependency
 ultralytics )  setup.ps1
=========================================================================
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image

from pk_studio.theme import COLORS
from pk_studio.core.dataset import DatasetScanner

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# : --  ()
# font.family: matplotlib  font engine  tkinter  ( font
#  UI )  default  matplotlib (DejaVu Sans)
#   label  (
# )  Tahoma  ( Windows )
#  label  100% 
#  matplotlib 
plt.rcParams.update({
    "font.family": ["Tahoma", "Leelawadee UI", "Angsana New", "DejaVu Sans"],
    "figure.facecolor": COLORS["card_bg"],
    "axes.facecolor": COLORS["card_bg"],
    "axes.edgecolor": COLORS["text_muted"],
    "axes.labelcolor": COLORS["text_dark"],
    "text.color": COLORS["text_dark"],
    "xtick.color": COLORS["text_muted"],
    "ytick.color": COLORS["text_muted"],
    "font.size": 9,
    "grid.color": COLORS["border"],
})


class AnalyticsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=16)
        self._scan_data = None  # 
        self._build_ui()

    def _build_ui(self) -> None:
        top_bar = ttk.Frame(self)
        top_bar.pack(fill="x", pady=(0, 14))

        ttk.Label(
            top_bar, text="📊 Analytics & Dataset Insights", font=("Segoe UI", 14, "bold"),
            foreground=COLORS["text_dark"],
        ).pack(side="left")
        ttk.Button(top_bar, text="📁 Scan Dataset", command=self._scan_dataset).pack(side="right")

        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill="x", pady=(0, 14))

        self.lbl_card_imgs = self._create_card(cards_frame, "Total Images", "0", COLORS["accent"])
        self.lbl_card_boxes = self._create_card(cards_frame, "Total Objects", "0", COLORS["success"])
        self.lbl_card_avg = self._create_card(cards_frame, "Avg Objects/Image", "0.0", COLORS["warning"])
        self.lbl_card_bg = self._create_card(cards_frame, "Background Images", "0", COLORS["text_muted"])

        # ----- Sub-notebook:  /  3  -----
        self.sub_notebook = ttk.Notebook(self)
        self.sub_notebook.pack(fill="both", expand=True)

        self.tab_overview = ttk.Frame(self.sub_notebook, padding=8)
        self.tab_histogram = ttk.Frame(self.sub_notebook, padding=8)
        self.tab_heatmap = ttk.Frame(self.sub_notebook, padding=8)
        self.tab_dimensions = ttk.Frame(self.sub_notebook, padding=8)

        self.sub_notebook.add(self.tab_overview, text="Overview")
        self.sub_notebook.add(self.tab_histogram, text="Objects per Image")
        self.sub_notebook.add(self.tab_heatmap, text="BBox Heat Map")
        self.sub_notebook.add(self.tab_dimensions, text="Image Dimensions")

        self._build_overview_tab()
        self._build_placeholder(self.tab_histogram, "histogram")
        self._build_placeholder(self.tab_heatmap, "heatmap")
        self._build_placeholder(self.tab_dimensions, "dimensions")

    def _build_overview_tab(self) -> None:
        box_class = ttk.LabelFrame(self.tab_overview, text="📈 Class Distribution", padding=12)
        box_class.pack(fill="both", expand=True)

        columns = ("class_name", "images", "instances", "percentage")
        self.tree = ttk.Treeview(box_class, columns=columns, show="headings", height=12)
        self.tree.heading("class_name", text="Class")
        self.tree.heading("images", text="Images")
        self.tree.heading("instances", text="Instances")
        self.tree.heading("percentage", text="Share (%)")
        self.tree.column("class_name", width=160, anchor="w")
        self.tree.column("images", width=100, anchor="center")
        self.tree.column("instances", width=120, anchor="center")
        self.tree.column("percentage", width=100, anchor="center")
        self.tree.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(box_class, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=scroll.set)

    def _build_placeholder(self, parent, tag) -> None:
        lbl = ttk.Label(
            parent, text="Scan a dataset to view this chart.", foreground=COLORS["text_muted"],
            font=("Segoe UI", 10),
        )
        lbl.pack(expand=True)
        setattr(self, f"_placeholder_{tag}", lbl)

    def _create_card(self, parent, title, initial_value, color):
        card = tk.Frame(
            parent, bg=COLORS["card_bg"], highlightbackground=COLORS["border"],
            highlightthickness=1, bd=0,
        )
        card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        inner = tk.Frame(card, bg=COLORS["card_bg"], padx=14, pady=12)
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=title, font=("Segoe UI", 9), bg=COLORS["card_bg"], fg=COLORS["text_muted"]).pack(
            anchor="w"
        )
        lbl_val = tk.Label(
            inner, text=initial_value, font=("Segoe UI", 20, "bold"), bg=COLORS["card_bg"], fg=color,
        )
        lbl_val.pack(anchor="w", pady=(4, 0))
        return lbl_val

    # -----------------------------------------------------------------
    #  —  Curator/Splitter 
    # -----------------------------------------------------------------
    @staticmethod
    def _find_images_and_labels(source: Path):
        return DatasetScanner.find_images_and_labels(source)

    @staticmethod
    def _load_class_names(source: Path, max_class_idx: int):
        return DatasetScanner.load_class_names(source, max_class_idx)

    def _scan_dataset(self) -> None:
        folder = filedialog.askdirectory(title="Select dataset folder")
        if not folder:
            return

        source = Path(folder)
        try:
            image_files = self._find_images_and_labels(source)
            if not image_files:
                messagebox.showerror(
                    "",
                    "No image files found in the selected folder. Check the dataset layout.",
                )
                return

            image_class_ids = {}
            bbox_centers = []  # [(cx, cy), ...]  normalized 0-1  ( heat map)
            object_counts_per_image = []  #  ( histogram)
            image_dimensions = []  # [(w, h), ...]  ( dimension insights)
            max_class_idx = -1
            n_background = 0

            for stem, (img_path, label_path) in image_files.items():
                ids_here = []
                if label_path is not None:
                    with open(label_path, encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                cls_idx = int(parts[0])
                                cx, cy = float(parts[1]), float(parts[2])
                                ids_here.append(cls_idx)
                                bbox_centers.append((cx, cy))
                                max_class_idx = max(max_class_idx, cls_idx)
                if not ids_here:
                    n_background += 1
                image_class_ids[stem] = ids_here
                object_counts_per_image.append(len(ids_here))

                try:
                    with Image.open(img_path) as im:
                        image_dimensions.append(im.size)  # (width, height)
                except Exception:
                    pass  #  (/format ) 

            class_names = self._load_class_names(source, max_class_idx)

            n_images = len(image_files)
            total_instances = sum(len(ids) for ids in image_class_ids.values())
            avg_per_image = (total_instances / n_images) if n_images else 0.0

            per_class_images = {i: 0 for i in range(len(class_names))}
            per_class_instances = {i: 0 for i in range(len(class_names))}
            for ids_here in image_class_ids.values():
                for i in set(ids_here):
                    per_class_images[i] += 1
                for i in ids_here:
                    per_class_instances[i] += 1

            self._scan_data = {
                "object_counts_per_image": object_counts_per_image,
                "bbox_centers": bbox_centers,
                "image_dimensions": image_dimensions,
            }

            self.lbl_card_imgs.config(text=f"{n_images:,}")
            self.lbl_card_boxes.config(text=f"{total_instances:,}")
            self.lbl_card_avg.config(text=f"{avg_per_image:.2f}")
            self.lbl_card_bg.config(text=f"{n_background:,}")

            for item in self.tree.get_children():
                self.tree.delete(item)

            for i, name in enumerate(class_names):
                cnt_img = per_class_images.get(i, 0)
                cnt_inst = per_class_instances.get(i, 0)
                pct = (cnt_inst / total_instances * 100) if total_instances > 0 else 0.0
                warn = " ⚠" if 0 < cnt_img < 3 else ""
                self.tree.insert("", tk.END, values=(name + warn, f"{cnt_img:,}", f"{cnt_inst:,}", f"{pct:.1f}%"))

            self._draw_histogram(object_counts_per_image)
            self._draw_heatmap(bbox_centers)
            self._draw_dimensions(image_dimensions)

        except Exception as exc:
            messagebox.showerror("Error", f"Scan failed: {exc}")

    # -----------------------------------------------------------------
    #  1: Histogram  object 
    # -----------------------------------------------------------------
    def _draw_histogram(self, object_counts_per_image) -> None:
        self._placeholder_histogram.destroy()
        for widget in self.tab_histogram.winfo_children():
            widget.destroy()

        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)
        max_count = max(object_counts_per_image) if object_counts_per_image else 0
        bins = list(range(0, max_count + 2))
        ax.hist(object_counts_per_image, bins=bins, color=COLORS["text_dark"], edgecolor=COLORS["card_bg"])
        ax.set_xlabel("Object Count per Image")
        ax.set_ylabel("Frequency (number of images)")
        ax.set_title("Histogram of Object Count by Image")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.tab_histogram)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)

    # -----------------------------------------------------------------
    #  2: Heat Map  ( center  normalized 0-1
    #  label  )
    # -----------------------------------------------------------------
    def _draw_heatmap(self, bbox_centers) -> None:
        self._placeholder_heatmap.destroy()
        for widget in self.tab_heatmap.winfo_children():
            widget.destroy()

        fig, ax = plt.subplots(figsize=(6, 5.5), dpi=100)
        if bbox_centers:
            xs = [c[0] for c in bbox_centers]
            ys = [1 - c[1] for c in bbox_centers]  #  y 
            ax.hist2d(xs, ys, bins=50, range=[[0, 1], [0, 1]], cmap="Greys")
        ax.set_xlabel("Horizontal position (0 = left, 1 = right)")
        ax.set_ylabel("Vertical position (0 = bottom, 1 = top)")
        ax.set_title("Annotation Heat Map")
        ax.set_aspect("equal")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.tab_heatmap)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)

    # -----------------------------------------------------------------
    #  3: Dimension Insights (  x  )
    # -----------------------------------------------------------------
    def _draw_dimensions(self, image_dimensions) -> None:
        self._placeholder_dimensions.destroy()
        for widget in self.tab_dimensions.winfo_children():
            widget.destroy()

        fig, ax = plt.subplots(figsize=(6, 5.5), dpi=100)
        if image_dimensions:
            widths = [d[0] for d in image_dimensions]
            heights = [d[1] for d in image_dimensions]
            ax.scatter(widths, heights, s=14, alpha=0.5, color=COLORS["text_dark"])
            median_w = sorted(widths)[len(widths) // 2]
            median_h = sorted(heights)[len(heights) // 2]
            ax.axvline(median_w, color=COLORS["text_muted"], linestyle="--", linewidth=1)
            ax.axhline(median_h, color=COLORS["text_muted"], linestyle="--", linewidth=1)
            ax.set_title(f"Dimension Insights (median: {median_w}x{median_h})")
        else:
            ax.set_title("Dimension Insights")
        ax.set_xlabel("Width (pixels)")
        ax.set_ylabel("Height (pixels)")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.tab_dimensions)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)
