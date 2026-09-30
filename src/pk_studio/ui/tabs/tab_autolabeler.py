"""
=========================================================================
PK Studio - Tab: Auto-Labeler (Annotation + Auto-Label )

 annotation_tool_py.py (AnnotationStudio) — logic ,
undo/redo, class manager, filter, keyboard shortcuts Original
  Auto-Label  YOLO ( Load Model,
Auto-Label Current, Batch Auto-Label) 
 

Features Original annotation_tool_py.py:
  1. Updated App Title:  "PK Studio"
  2. Color Format Correction:  RGB -> BGR  OpenCV 
      Canvas  Manage Classes 100%
  3. Jump to Specific Image:  + Enter 
  4. BBox Status Filter:  Labeled / Unlabeled
  5. Auto-Review Navigation:  Next ►  Review + 

Batch Auto-Label:  label  ( label )
=========================================================================
"""

import json
import os
import shutil
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser, simpledialog
import cv2
import numpy as np
from PIL import Image, ImageTk

from pk_studio.theme import COLORS
from pk_studio.core.class_registry import ClassRegistry
from pk_studio.core.fileio import atomic_write_text
from pk_studio.core.job_manager import JobManager, ui_queue_for

DEFAULT_COLORS = [
    # High-saturation, easy-to-distinguish colors for Classes / Bounding Boxes.
    (255, 0, 0),       # Red
    (0, 180, 255),     # Sky blue
    (0, 220, 120),     # Green
    (255, 170, 0),     # Orange
    (190, 0, 255),     # Purple
    (255, 0, 170),     # Magenta
    (0, 210, 210),     # Cyan
    (255, 220, 0),     # Yellow
    (80, 120, 255),    # Periwinkle
    (120, 255, 0),     # Lime
    (255, 90, 40),     # Coral
    (0, 120, 255),     # Blue
    (220, 0, 100),     # Raspberry
    (0, 255, 180),     # Aqua
    (160, 80, 255),    # Violet
    (255, 120, 0),     # Tangerine
    (40, 220, 70),     # Emerald
    (255, 60, 190),    # Pink
    (0, 200, 255),     # Bright cyan
    (255, 210, 70),    # Gold
]

CONFIG_FILE = ".pk_ui_config.json"

class AutoLabelerTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=0)

        # Data State
        self.src_dir = ""
        self.img_dir = ""
        self.lbl_dir = ""
        self.meta_file = ""
        self.cls_file = ""

        # Auto-Label (YOLO) State
        self.model_path = ""
        self.auto_model = None
        self.conf_threshold = 0.35
        self.imgsz = 640
        self._batch_running = False
        self.job_manager = JobManager()
        self._auto_job = None
        self._batch_errors = []

        self.classes = []
        self.class_registry = ClassRegistry()
        self.class_colors = {}     # {cls_id: (r, g, b)}
        self.image_files = []
        self.filtered_images = []
        self.current_idx = 0
        self.meta_data = {}

        # Bbox State
        self.cv_img = None
        self.orig_w, self.orig_h = 1, 1
        self.bboxes = []
        self.history = []
        self.history_idx = -1
        
        # Interactive Canvas States
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.selected_box_idx = None
        self.drag_mode = None
        self.drag_start = (0, 0)
        self.initial_bbox = None

        # Filter & Visibility State
        self.visible_classes = {}
        self.search_classes = {}
        self.search_mode = "OR"

        # Mouse Gesture Trackers
        self.pending_right_click = False
        self.last_right_click_time = 0
        self.last_left_click_time = 0

        # Typing Buffer for Class Change
        self.class_input_buffer = ""

        # Load Saved UI Config
        self.ui_config = self._load_ui_config()

        self._build_ui()
        self._bind_shortcuts()

    # =========================================================================
    # UI Setup
    # =========================================================================
    def _build_ui(self):
        # Top Control Bar
        top_bar = ttk.Frame(self, padding=(8, 6))
        top_bar.pack(fill="x", side="top")

        ttk.Button(top_bar, text="📁 Open", command=self.load_dataset).pack(side="left", padx=2)
        ttk.Button(top_bar, text="💾 Save", command=self.save_current).pack(side="left", padx=2)
        ttk.Button(top_bar, text="💾 Save All", command=self.save_all).pack(side="left", padx=2)
        ttk.Button(top_bar, text="💾 Save As...", command=self.save_as_dataset).pack(side="left", padx=2)

        ttk.Separator(top_bar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(top_bar, text="↶ Undo", command=self.undo).pack(side="left", padx=2)
        ttk.Button(top_bar, text="↷ Redo", command=self.redo).pack(side="left", padx=2)

        ttk.Separator(top_bar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(top_bar, text="🤖 Model", command=self.load_yolo_model).pack(side="left", padx=2)
        ttk.Button(top_bar, text="⚡ Auto-Label", command=self.auto_label_current_image).pack(side="left", padx=2)
        ttk.Button(top_bar, text="🚀 Batch", command=self.run_batch_autolabel).pack(side="left", padx=2)

        ttk.Separator(top_bar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(top_bar, text="🏷️ Classes", command=self.open_class_manager_window).pack(side="left", padx=2)
        ttk.Button(top_bar, text="🔍 Search", command=self.open_search_filter_window).pack(side="left", padx=2)
        ttk.Button(top_bar, text="⌨️ Shortcuts", command=self.open_shortcut_cheatsheet_window).pack(side="left", padx=2)

        self.lbl_progress = ttk.Label(top_bar, text="Reviewed: 0/0 | Total: 0", font=("Segoe UI", 9, "bold"))
        self.lbl_progress.pack(side="right", padx=15)

        # Main Paned Window
        self.main_paned = ttk.PanedWindow(self, orient="horizontal")
        self.main_paned.pack(fill="both", expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(self.main_paned)
        right_frame = ttk.Frame(self.main_paned)

        self.main_paned.add(left_frame, weight=3)
        self.main_paned.add(right_frame, weight=1)

        # Canvas Toolbar
        filter_bar = ttk.Frame(left_frame, padding=2)
        filter_bar.pack(fill="x", side="top")

        ttk.Label(filter_bar, text="Status Filter:").pack(side="left", padx=2)
        self.filter_var = tk.StringVar(value="All")
        
        cb_filter = ttk.Combobox(
            filter_bar, textvariable=self.filter_var, 
            values=["All", "Reviewed", "Unreviewed", "Labeled", "Unlabeled"], 
            state="readonly", width=12
        )
        cb_filter.pack(side="left", padx=2)
        cb_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_image_filters())

        ttk.Label(filter_bar, text="Zoom:").pack(side="right", padx=2)
        self.lbl_zoom = ttk.Label(filter_bar, text="100%", width=6)
        self.lbl_zoom.pack(side="right", padx=2)
        ttk.Button(filter_bar, text="-", width=2, command=lambda: self.change_zoom(-0.15)).pack(side="right")
        ttk.Button(filter_bar, text="+", width=2, command=lambda: self.change_zoom(0.15)).pack(side="right")
        ttk.Button(filter_bar, text="Reset", command=self.reset_zoom).pack(side="right", padx=2)

        # Canvas
        self.canvas = tk.Canvas(left_frame, bg=COLORS["sidebar_bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.bind("<Button-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_right_click_start)
        self.canvas.bind("<B3-Motion>", self.on_right_click_drag)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

        # Bottom Bar
        bot_bar = ttk.Frame(left_frame, padding=5)
        bot_bar.pack(fill="x", side="bottom")

        ttk.Button(bot_bar, text="◄ Prev", command=self.prev_image).pack(side="left", padx=4)
        ttk.Button(bot_bar, text="Next ►", command=self.next_image).pack(side="left", padx=4)

        ttk.Separator(bot_bar, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Label(bot_bar, text="Jump to Image:").pack(side="left", padx=(2, 2))
        self.entry_jump = ttk.Entry(bot_bar, width=6)
        self.entry_jump.pack(side="left", padx=2)
        self.entry_jump.bind("<Return>", lambda e: self.jump_to_image())
        
        ttk.Button(bot_bar, text="Go", width=4, command=self.jump_to_image).pack(side="left", padx=2)

        self.lbl_file_info = ttk.Label(bot_bar, text="No dataset loaded")
        self.lbl_file_info.pack(side="right", padx=5)

        # Right Panel Structure
        self.right_paned = ttk.PanedWindow(right_frame, orient="vertical")
        self.right_paned.pack(fill="both", expand=True)

        top_right_box = ttk.Frame(self.right_paned)
        bot_right_box = ttk.Frame(self.right_paned)

        self.right_paned.add(top_right_box, weight=1)
        self.right_paned.add(bot_right_box, weight=4)

        # Active Class Setup Frame
        cls_frame = ttk.LabelFrame(top_right_box, text="Active Class Setup", padding=5)
        cls_frame.pack(fill="both", expand=True)
        
        ttk.Label(cls_frame, text="Active Class for new box:").pack(anchor="w")
        self.cb_classes = ttk.Combobox(cls_frame, state="readonly")
        self.cb_classes.pack(fill="x", pady=(2, 2))
        self.cb_classes.bind("<<ComboboxSelected>>", lambda e: self.apply_class_change())

        self.lbl_typing_feedback = ttk.Label(cls_frame, text="Type Class ID + Enter to apply", font=("Segoe UI", 8, "italic"), foreground=COLORS["accent"])
        self.lbl_typing_feedback.pack(anchor="w")

        # UNIFIED PANEL: Current Image Boxes
        unified_frame = ttk.LabelFrame(bot_right_box, text="📦 Current Image Boxes & Visibility", padding=5)
        unified_frame.pack(fill="both", expand=True)

        self.unified_container = ttk.Frame(unified_frame)
        self.unified_container.pack(fill="both", expand=True)

        # All Dataset Summary Section
        summary_group = ttk.LabelFrame(bot_right_box, text="📊 All Dataset Summary", padding=5)
        summary_group.pack(fill="both", expand=True, pady=(5, 0))

        self.global_stats_text = tk.Text(
            summary_group, font=("Consolas", 9),
            bg=COLORS["card_bg"], fg=COLORS["text_dark"], insertbackground=COLORS["text_dark"],
            state="disabled", height=8, relief="flat", highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.global_stats_text.pack(fill="both", expand=True, side="left")
        global_scroll = ttk.Scrollbar(summary_group, orient="vertical", command=self.global_stats_text.yview)
        global_scroll.pack(side="right", fill="y")
        self.global_stats_text.config(yscrollcommand=global_scroll.set)

        self.after(100, self._restore_ui_config)

    # =========================================================================
    # Persistence & Configs
    # =========================================================================
    def _load_ui_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_ui_config(self):
        try:
            config = {
                "main_sash": self.main_paned.sashpos(0),
                "right_sash_0": self.right_paned.sashpos(0),
                "class_colors": {str(k): list(v) for k, v in self.class_colors.items()}
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

    def _restore_ui_config(self):
        try:
            if "main_sash" in self.ui_config:
                self.main_paned.sashpos(0, self.ui_config["main_sash"])
            if "right_sash_0" in self.ui_config:
                self.right_paned.sashpos(0, self.ui_config["right_sash_0"])
            if "class_colors" in self.ui_config:
                self.class_colors = {int(k): tuple(v) for k, v in self.ui_config["class_colors"].items()}
        except Exception:
            pass

    def _on_close(self):
        self._save_ui_config()
        self.destroy()

    # =========================================================================
    # Jump to Specific Image Engine
    # =========================================================================
    def jump_to_image(self):
        if not self.filtered_images:
            return
        
        val = self.entry_jump.get().strip()
        if not val.isdigit():
            messagebox.showwarning("Warning", "Enter an image number.")
            return

        target_num = int(val)
        if 1 <= target_num <= len(self.filtered_images):
            # Auto-save the image we're leaving before jumping away from it.
            self._write_current_labels()
            self.current_idx = target_num - 1
            self.load_current_image()
            self.entry_jump.delete(0, tk.END)
            self.focus_set()
        else:
            messagebox.showerror("Error", f"Image index is out of range. Valid range: 1 to {len(self.filtered_images)}.")

    # =========================================================================
    # Cheat Sheet Window
    # =========================================================================
    def open_shortcut_cheatsheet_window(self):
        win = tk.Toplevel(self)
        win.title("Keyboard Shortcuts Cheat Sheet")
        win.geometry("550x500")
        win.grab_set()

        ttk.Label(win, text="⌨️ Keyboard Shortcuts", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=15, pady=10)

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)

        columns = ("key", "action")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        
        tree.heading("key", text="Shortcut / Action")
        tree.heading("action", text="Description")
        
        tree.column("key", width=180, anchor="w")
        tree.column("action", width=320, anchor="w")

        shortcuts_data = [
            ("A", "Previous image"),
            ("D / Space", "Review and go to next image"),
            ("0-9", "Enter Class ID and press Enter"),
            ("Backspace", "Delete typed digits / selected BBox"),
            ("Delete", "Delete selected BBox"),
            ("Right click → left click", "Right-click a BBox, then left-click again to delete"),
            ("Ctrl + S", "Save current image"),
            ("Ctrl + Z", "Undo"),
            ("Ctrl + Y", "Redo"),
            ("Escape", "Cancel Class ID entry"),
            ("Scroll Wheel", "Zoom in / out"),
            ("Right click + drag", "Pan image"),
            ("Double left click (empty area)", "Previous image"),
            ("Double right click (empty area)", "Review and go to next image")
        ]

        for item in shortcuts_data:
            tree.insert("", tk.END, values=item)

        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    # =========================================================================
    # Class Manager & Color Palette Window
    # =========================================================================
    def open_class_manager_window(self):
        win = tk.Toplevel(self)
        win.title("Manage Classes & Colors")
        win.geometry("420x520")
        win.grab_set()

        ttk.Label(win, text="🏷️ Dataset Class & Color Palette", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=5)

        list_frame = ttk.Frame(win, padding=5)
        list_frame.pack(fill="both", expand=True, padx=5)

        canvas = tk.Canvas(list_frame, highlightthickness=0)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        selected_cls_idx = [None]

        def refresh_manager_list():
            for w in inner.winfo_children():
                w.destroy()

            for i, c in enumerate(self.classes):
                row = ttk.Frame(inner)
                row.pack(fill="x", anchor="w", pady=2, padx=2)

                rgb = self.get_class_color(i)
                hex_col = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

                btn_color = tk.Button(
                    row, width=2, height=1, bg=hex_col, relief="flat",
                    command=lambda idx=i: self.choose_class_color(idx, win, refresh_manager_list)
                )
                btn_color.pack(side="left", padx=(0, 6))

                lbl = ttk.Label(row, text=f"[{i + 1}] {c}", font=("Consolas", 10))
                lbl.pack(side="left")

                def select_row(idx=i):
                    selected_cls_idx[0] = idx

                row.bind("<Button-1>", lambda e, idx=i: select_row(idx))
                lbl.bind("<Button-1>", lambda e, idx=i: select_row(idx))

            inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        refresh_manager_list()

        move_frame = ttk.Frame(win, padding=(10, 2))
        move_frame.pack(fill="x", padx=0, pady=2)

        def move_selected(delta):
            idx = selected_cls_idx[0]
            if idx is None:
                return
            old_classes = list(self.classes)
            new_idx = idx + delta
            if not (0 <= new_idx < len(self.classes)):
                return
            if not messagebox.askyesno(
                "Change Class Order",
                "Changing class order changes YOLO class IDs and will update every label file in this dataset.\n\nContinue?",
            ):
                return
            self.classes[idx], self.classes[new_idx] = self.classes[new_idx], self.classes[idx]
            self._update_classes_after_change(old_classes)
            selected_cls_idx[0] = new_idx
            refresh_manager_list()

        ttk.Button(move_frame, text="↑ Move Up", command=lambda: move_selected(-1)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(move_frame, text="↓ Move Down", command=lambda: move_selected(1)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Label(move_frame, text="Default = alphabetical; moving changes YOLO IDs", foreground=COLORS["text_muted"]).pack(side="left", padx=8)

        add_frame = ttk.LabelFrame(win, text="Add New Class", padding=5)
        add_frame.pack(fill="x", padx=10, pady=5)

        entry_name = ttk.Entry(add_frame)
        entry_name.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def add_cls():
            name = entry_name.get().strip()
            if name and name not in self.classes:
                old_classes = list(self.classes)
                self.class_registry.load(self.classes, sort=False)
                self.class_registry.add(name, sort=True)
                self.classes = self.class_registry.names
                self._update_classes_after_change(old_classes)
                refresh_manager_list()
                entry_name.delete(0, tk.END)

        ttk.Button(add_frame, text="Add", command=add_cls).pack(side="right")

        def del_cls():
            if selected_cls_idx[0] is not None:
                del_idx = selected_cls_idx[0]
                del_name = self.classes[del_idx]
                if messagebox.askyesno("Confirm", f"Delete class [{del_idx + 1}] {del_name}?"):
                    old_classes = list(self.classes)
                    self.classes.remove(del_name)
                    self.class_registry.load(self.classes, sort=False)
                    self.bboxes = [b for b in self.bboxes if b[0] != del_idx]
                    self._update_classes_after_change(old_classes)
                    selected_cls_idx[0] = None
                    refresh_manager_list()

        ttk.Button(win, text="🗑️ Delete Selected Class", command=del_cls).pack(fill="x", padx=10, pady=5)

    def choose_class_color(self, cls_idx, parent_win=None, callback=None):
        curr_rgb = self.get_class_color(cls_idx)
        curr_hex = f"#{curr_rgb[0]:02x}{curr_rgb[1]:02x}{curr_rgb[2]:02x}"
        
        color_code = colorchooser.askcolor(
            title=f"Choose Color for [{cls_idx + 1}] {self.classes[cls_idx]}", 
            initialcolor=curr_hex,
            parent=parent_win or self
        )
        if color_code and color_code[0]:
            rgb = tuple(map(int, color_code[0]))
            self.class_colors[cls_idx] = rgb
            self._save_ui_config()
            self.update_box_list()
            self.render()
            if callback:
                callback()

    def get_class_color(self, cls_idx):
        if cls_idx in self.class_colors:
            return self.class_colors[cls_idx]
        return DEFAULT_COLORS[cls_idx % len(DEFAULT_COLORS)]

    def open_search_filter_window(self):
        if not self.classes:
            messagebox.showinfo("Info", "No classes available to filter.")
            return

        win = tk.Toplevel(self)
        win.title("Advanced Image Search Filter")
        win.geometry("450x550")

        ttk.Label(win, text="🔍 Filter Images by Class Occurrence", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=5)

        mode_frame = ttk.LabelFrame(win, text="Matching Rule", padding=5)
        mode_frame.pack(fill="x", padx=10, pady=5)

        mode_var = tk.StringVar(value=self.search_mode)
        ttk.Radiobutton(mode_frame, text="OR (Has AT LEAST ONE selected class)", variable=mode_var, value="OR").pack(anchor="w")
        ttk.Radiobutton(mode_frame, text="AND (Must contain ALL selected classes together)", variable=mode_var, value="AND").pack(anchor="w")

        cls_frame = ttk.LabelFrame(win, text="Select Classes to Search", padding=5)
        cls_frame.pack(fill="both", expand=True, padx=10, pady=5)

        canvas = tk.Canvas(cls_frame, highlightthickness=0)
        scroll = ttk.Scrollbar(cls_frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        chk_vars = {}
        for i, c in enumerate(self.classes):
            var = tk.BooleanVar(value=self.search_classes.get(i, False))
            chk_vars[i] = var
            ttk.Checkbutton(inner, text=f"[{i + 1}] {c}", variable=var).pack(anchor="w", pady=2)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def apply_search():
            self.search_mode = mode_var.get()
            self.search_classes = {i: v.get() for i, v in chk_vars.items()}
            self.apply_image_filters()
            win.destroy()

        def reset_search():
            self.search_classes = {}
            self.apply_image_filters()
            win.destroy()

        btn_frame = ttk.Frame(win, padding=5)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="Apply Filter", command=apply_search).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Reset Search", command=reset_search).pack(side="right", padx=4)

    # =========================================================================
    # Unified Checklist Panel
    # =========================================================================
    def _update_classes_after_change(self, old_classes):
        """Persist class order and remap YOLO ids across the whole dataset."""
        old_to_new = {old_idx: self.classes.index(name) for old_idx, name in enumerate(old_classes) if name in self.classes}
        removed_old_ids = {old_idx for old_idx, name in enumerate(old_classes) if name not in self.classes}

        # Colors belong to the class name, not its numeric position. Preserve
        # them when the user reorders classes.
        old_colors = dict(self.class_colors)
        self.class_colors = {
            old_to_new[old_idx]: color
            for old_idx, color in old_colors.items()
            if old_idx in old_to_new
        }

        if self.lbl_dir and os.path.isdir(self.lbl_dir):
            for filename in os.listdir(self.lbl_dir):
                if not filename.lower().endswith('.txt') or filename.lower() == 'classes.txt':
                    continue
                path = os.path.join(self.lbl_dir, filename)
                try:
                    lines_out, changed = [], False
                    with open(path, 'r', encoding='utf-8') as f:
                        for line in f:
                            parts = line.strip().split()
                            if not parts:
                                continue
                            try:
                                old_id = int(parts[0])
                            except ValueError:
                                lines_out.append(line.rstrip())
                                continue
                            if old_id not in old_to_new:
                                # Only IDs belonging to an intentionally deleted class are removed.
                                # Preserve unrelated invalid IDs so Dataset QA can report them.
                                if old_id in removed_old_ids:
                                    changed = True
                                    continue
                                lines_out.append(' '.join(parts))
                                continue
                            new_id = old_to_new[old_id]
                            changed = changed or (new_id != old_id)
                            parts[0] = str(new_id)
                            lines_out.append(' '.join(parts))
                    if changed:
                        tmp = path + '.pk_tmp'
                        with open(tmp, 'w', encoding='utf-8') as f:
                            if lines_out:
                                f.write('\n'.join(lines_out) + '\n')
                        os.replace(tmp, path)
                except (OSError, UnicodeError) as exc:
                    messagebox.showwarning('Class update warning', f'Could not update {filename}: {exc}')

        if self.cls_file:
            with open(self.cls_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.classes))

        new_bboxes = []
        for bbox in self.bboxes:
            if bbox[0] in old_to_new:
                bbox[0] = old_to_new[bbox[0]]
                new_bboxes.append(bbox)
        self.bboxes = new_bboxes

        old_color_by_name = {name: self.class_colors.get(i, DEFAULT_COLORS[i % len(DEFAULT_COLORS)]) for i, name in enumerate(old_classes)}
        self.class_colors = {i: old_color_by_name[name] for i, name in enumerate(self.classes) if name in old_color_by_name}
        self.class_registry.load(self.classes, sort=False)

        display_classes = [f"[{i + 1}] {c}" for i, c in enumerate(self.classes)]
        self.cb_classes['values'] = display_classes
        if self.classes:
            self.cb_classes.current(0)
        self.update_box_list()
        self.render()

    def update_box_list(self):
        for widget in self.unified_container.winfo_children():
            widget.destroy()

        canvas = tk.Canvas(self.unified_container, highlightthickness=0)
        scroll = ttk.Scrollbar(self.unified_container, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        local_cls_counts = {}
        for cls_id, _, _, _, _ in self.bboxes:
            local_cls_counts[cls_id] = local_cls_counts.get(cls_id, 0) + 1

        for i, c in enumerate(self.classes):
            if i not in self.visible_classes:
                self.visible_classes[i] = True

            count = local_cls_counts.get(i, 0)
            var = tk.BooleanVar(value=self.visible_classes[i])

            def make_cmd(cls_idx=i, v=var):
                return lambda: self._toggle_visibility(cls_idx, v.get())

            row = ttk.Frame(inner)
            row.pack(fill="x", anchor="w", pady=2, padx=2)

            chk = ttk.Checkbutton(row, variable=var, command=make_cmd())
            chk.pack(side="left")

            rgb = self.get_class_color(i)
            hex_col = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            
            color_swatch = tk.Frame(row, width=12, height=12, bg=hex_col)
            color_swatch.pack(side="left", padx=(0, 6))

            lbl_text = f"[{i + 1}] {c} ({count})"
            lbl = ttk.Label(row, text=lbl_text, font=("Consolas", 9, "bold" if count > 0 else "normal"))
            lbl.pack(side="left")

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.update_stats()

    def _toggle_visibility(self, cls_idx, is_visible):
        self.visible_classes[cls_idx] = is_visible
        self.render()

    # =========================================================================
    # Image Filters
    # =========================================================================
    def apply_image_filters(self):
        if not self.image_files:
            return

        status_filter = self.filter_var.get()
        active_search_classes = [i for i, v in self.search_classes.items() if v]

        self.filtered_images = []
        for img_name in self.image_files:
            is_rev = self.meta_data.get(img_name, {}).get("reviewed", False)
            if status_filter == "Reviewed" and not is_rev:
                continue
            if status_filter == "Unreviewed" and is_rev:
                continue

            txt_name = os.path.splitext(img_name)[0] + ".txt"
            txt_path = os.path.join(self.lbl_dir, txt_name)
            has_bbox = False
            img_classes = set()

            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts:
                            has_bbox = True
                            img_classes.add(int(parts[0]))

            if status_filter == "Labeled" and not has_bbox:
                continue
            if status_filter == "Unlabeled" and has_bbox:
                continue

            if active_search_classes:
                if self.search_mode == "OR":
                    if not any(c in img_classes for c in active_search_classes):
                        continue
                elif self.search_mode == "AND":
                    if not all(c in img_classes for c in active_search_classes):
                        continue

            self.filtered_images.append(img_name)

        self.current_idx = 0
        self.load_current_image()

    # =========================================================================
    # Shortcuts Engine
    # =========================================================================
    def _bind_shortcuts(self):
        #  winfo_toplevel() ()  self ( Frame )
        #  Frame  keyboard focus   self
        #    ()
        # add="+" so this coexists with other tabs' own root-level keypress
        # bindings instead of silently replacing them.
        self.winfo_toplevel().bind("<KeyPress>", self._on_global_keypress, add="+")

    def _on_global_keypress(self, event):
        if not self.winfo_ismapped():
            return  # the Label tab isn't the one currently showing
        if isinstance(self.focus_get(), (ttk.Entry, tk.Entry, tk.Text)):
            return

        code = event.keycode
        state = event.state
        char = event.char
        ctrl_pressed = (state & 0x0004) != 0 or (state & 0x0001) != 0

        if ctrl_pressed and (code == 83 or char in ['s', 'S']):
            self.save_current()
            return "break"
        if ctrl_pressed and (code == 90 or char in ['z', 'Z']):
            self.undo()
            return "break"
        if ctrl_pressed and (code == 89 or char in ['y', 'Y']):
            self.redo()
            return "break"

        if not ctrl_pressed:
            if code == 65 or char in ['a', 'A']:
                self.prev_image()
                return "break"
            if code == 68 or char in ['d', 'D'] or code == 32 or char == ' ':
                self.next_image()
                return "break"

            if code == 13 or event.keysym in ['Return', 'KP_Enter']:
                self.on_key_enter()
                return "break"
            if code == 27 or event.keysym == 'Escape':
                self.clear_typing_buffer()
                return "break"

            if event.keysym in ['Delete', 'BackSpace'] or code in [46, 8]:
                self.on_key_backspace()
                return "break"

            digit_map = {
                '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
                '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
                '_': '0',                 '!:': '1',                 '@': '2', '/': '2',
                '#': '3', '-': '3',
                '$': '4',
                '%': '5',
                '^': '6',
                '&': '7',
                '*': '8',
                '(': '9'
            }

            if char in digit_map:
                self.on_number_key(digit_map[char])
                return "break"

            if 96 <= code <= 105:
                self.on_number_key(str(code - 96))
                return "break"
            if 48 <= code <= 57:
                self.on_number_key(str(code - 48))
                return "break"

    # =========================================================================
    # Mouse Gestures
    # =========================================================================
    def on_canvas_press(self, event):
        x, y = self.canvas_to_orig(event.x, event.y)
        self.drag_start = (x, y)
        self.clear_typing_buffer()
        curr_time = time.time()

        if self.pending_right_click:
            clicked_idx = self._find_clicked_box(x, y)
            if clicked_idx is not None:
                self.selected_box_idx = clicked_idx
                self.delete_selected_box()
            self.pending_right_click = False
            return

        self.pending_right_click = False

        if curr_time - self.last_left_click_time < 0.35:
            clicked_idx = self._find_clicked_box(x, y)
            if clicked_idx is None:
                self.prev_image()
                self.last_left_click_time = 0
                return

        self.last_left_click_time = curr_time

        if self.selected_box_idx is not None:
            sb = self.bboxes[self.selected_box_idx]
            x1, y1, x2, y2 = sb[1], sb[2], sb[3], sb[4]
            tol = int(12 / self.render_scale)
            
            if abs(x - x1) < tol and abs(y - y1) < tol: self.drag_mode = 'resize_tl'
            elif abs(x - x2) < tol and abs(y - y1) < tol: self.drag_mode = 'resize_tr'
            elif abs(x - x1) < tol and abs(y - y2) < tol: self.drag_mode = 'resize_bl'
            elif abs(x - x2) < tol and abs(y - y2) < tol: self.drag_mode = 'resize_br'

            if self.drag_mode:
                self.initial_bbox = list(sb)
                return

        clicked_idx = self._find_clicked_box(x, y)
        if clicked_idx is not None:
            self.selected_box_idx = clicked_idx
            self.drag_mode = 'move'
            self.initial_bbox = list(self.bboxes[clicked_idx])
            self.cb_classes.current(self.bboxes[clicked_idx][0])
        else:
            self.selected_box_idx = None
            self.drag_mode = 'create'

        self.render()

    def on_right_click_start(self, event):
        self.drag_start = (event.x, event.y)
        curr_time = time.time()
        x, y = self.canvas_to_orig(event.x, event.y)

        if curr_time - self.last_right_click_time < 0.35:
            self.next_image()
            self.last_right_click_time = 0
            self.pending_right_click = False
            return

        self.last_right_click_time = curr_time
        
        clicked_idx = self._find_clicked_box(x, y)
        if clicked_idx is not None:
            self.pending_right_click = True
        else:
            self.pending_right_click = False

    def _find_clicked_box(self, x, y):
        for idx, (cls_id, x1, y1, x2, y2) in enumerate(self.bboxes):
            if self.visible_classes.get(cls_id, True):
                if x1 <= x <= x2 and y1 <= y <= y2:
                    return idx
        return None

    def on_canvas_drag(self, event):
        x, y = self.canvas_to_orig(event.x, event.y)
        dx = x - self.drag_start[0]
        dy = y - self.drag_start[1]

        if self.drag_mode == 'move' and self.selected_box_idx is not None:
            init = self.initial_bbox
            w, h = init[3] - init[1], init[4] - init[2]
            nx1 = max(0, min(self.orig_w - w, init[1] + dx))
            ny1 = max(0, min(self.orig_h - h, init[2] + dy))
            self.bboxes[self.selected_box_idx][1:5] = [nx1, ny1, nx1 + w, ny1 + h]

        elif self.drag_mode and self.drag_mode.startswith('resize'):
            init = self.initial_bbox
            b = list(init)
            if 'tl' in self.drag_mode: b[1], b[2] = min(x, b[3]-5), min(y, b[4]-5)
            elif 'tr' in self.drag_mode: b[3], b[2] = max(x, b[1]+5), min(y, b[4]-5)
            elif 'bl' in self.drag_mode: b[1], b[4] = min(x, b[3]-5), max(y, b[2]+5)
            elif 'br' in self.drag_mode: b[3], b[4] = max(x, b[1]+5), max(y, b[2]+5)
            self.bboxes[self.selected_box_idx][1:5] = b[1:5]

        elif self.drag_mode == 'create':
            x1, y1 = self.drag_start
            cls_id = self.cb_classes.current() if self.cb_classes.current() >= 0 else 0
            temp_bboxes = list(self.bboxes) + [[cls_id, min(x1, x), min(y1, y), max(x1, x), max(y1, y)]]
            self.render_temp(temp_bboxes)
            return

        self.render()

    def on_canvas_release(self, event):
        if self.drag_mode == 'create':
            x, y = self.canvas_to_orig(event.x, event.y)
            x1, y1 = self.drag_start
            if abs(x - x1) > 8 and abs(y - y1) > 8:
                cls_id = self.cb_classes.current() if self.cb_classes.current() >= 0 else 0
                new_box = [cls_id, min(x1, x), min(y1, y), max(x1, x), max(y1, y)]
                self.bboxes.append(new_box)
                self.selected_box_idx = len(self.bboxes) - 1
                self.push_history()

        elif self.drag_mode in ['move', 'resize_tl', 'resize_tr', 'resize_bl', 'resize_br']:
            self.push_history()

        self.drag_mode = None
        self.render()
        self.update_box_list()

    def on_right_click_drag(self, event):
        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]
        self.pan_x += dx
        self.pan_y += dy
        self.drag_start = (event.x, event.y)
        self.render()

    # =========================================================================
    # Render Engine
    # =========================================================================
    def render(self):
        if self.cv_img is None:
            return

        disp_img = self.cv_img.copy()

        for idx, (cls_id, x1, y1, x2, y2) in enumerate(self.bboxes):
            if not self.visible_classes.get(cls_id, True):
                continue

            rgb_color = self.get_class_color(cls_id)
            bgr_color = rgb_color[::-1]
            
            is_sel = (idx == self.selected_box_idx)
            thickness = 3 if is_sel else 2

            cv2.rectangle(disp_img, (x1, y1), (x2, y2), bgr_color, thickness)
            
            if is_sel:
                handle_radius = max(4, int(6 / self.render_scale))
                for hx, hy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
                    cv2.circle(disp_img, (hx, hy), handle_radius, (255, 255, 255), -1)

            c_name = self.classes[cls_id] if cls_id < len(self.classes) else f"Class {cls_id + 1}"
            lbl_str = f" [{cls_id + 1}] {c_name} "

            font_scale = 0.55
            font_thickness = 1
            (text_w, text_h), baseline = cv2.getTextSize(lbl_str, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
            
            label_y1 = max(y1 - text_h - 8, 0)
            label_y2 = label_y1 + text_h + 8
            label_x2 = x1 + text_w + 4

            # Keep the UI monochrome, but make Class labels / boxes intentionally colorful.
            cv2.rectangle(disp_img, (x1, label_y1), (label_x2, label_y2), bgr_color, -1)
            text_color = (0, 0, 0) if sum(rgb_color) > 430 else (255, 255, 255)
            cv2.putText(disp_img, lbl_str, (x1 + 2, label_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, font_thickness, cv2.LINE_AA)

        cw = self.canvas.winfo_width() or 800
        ch = self.canvas.winfo_height() or 600

        scale_base = min(cw / self.orig_w, ch / self.orig_h)
        self.render_scale = scale_base * self.zoom_level

        new_w = max(1, int(self.orig_w * self.render_scale))
        new_h = max(1, int(self.orig_h * self.render_scale))

        resized = cv2.resize(disp_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        rgb_img = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        self.tk_image = ImageTk.PhotoImage(Image.fromarray(rgb_img))
        self.canvas.delete("all")
        
        self.offset_x = (cw - new_w) // 2 + self.pan_x
        self.offset_y = (ch - new_h) // 2 + self.pan_y

        self.canvas.create_image(self.offset_x + new_w // 2, self.offset_y + new_h // 2, image=self.tk_image, anchor="center")

    # =========================================================================
    # Dataset Engine
    # =========================================================================
    def load_dataset(self):
        dir_path = filedialog.askdirectory(title="Select Auto-labeled Output Directory")
        if not dir_path:
            return

        self.src_dir = os.path.abspath(dir_path)
        
        self.img_dir = os.path.join(self.src_dir, "images") if os.path.exists(os.path.join(self.src_dir, "images")) else self.src_dir
        self.lbl_dir = os.path.join(self.src_dir, "labels") if os.path.exists(os.path.join(self.src_dir, "labels")) else self.src_dir
        self.meta_file = os.path.join(self.src_dir, ".pk_annotation_meta.json")

        if os.path.exists(self.meta_file):
            with open(self.meta_file, "r", encoding="utf-8") as f:
                self.meta_data = json.load(f)
        else:
            self.meta_data = {}

        self.cls_file = os.path.join(self.src_dir, "classes.txt")
        if not os.path.exists(self.cls_file):
            self.cls_file = os.path.join(self.lbl_dir, "classes.txt")

        if os.path.exists(self.cls_file):
            with open(self.cls_file, "r", encoding="utf-8") as f:
                self.classes = [line.strip() for line in f if line.strip()]
        elif self.auto_model is not None:
            #  classes.txt  ->  class 
            #  "Class 1".."Class 10" ( Auto-Label  map 
            #  )
            model_names = self.auto_model.names
            self.classes = sorted([model_names[i] for i in range(len(model_names))], key=lambda x: x.casefold())
            self._write_classes_file()
        else:
            self.classes = [f"Class {i + 1}" for i in range(10)]

        # Roboflow-compatible default is alphabetical. Once a classes.txt exists,
        # preserve its explicit order so user reordering survives reload.
        self.class_registry.load(self.classes, sort=False)
        self.classes = self.class_registry.names
        
        display_classes = [f"[{i + 1}] {c}" for i, c in enumerate(self.classes)]
        self.cb_classes["values"] = display_classes
        if self.classes:
            self.cb_classes.current(0)

        exts = (".jpg", ".jpeg", ".png", ".bmp")
        self.image_files = sorted([f for f in os.listdir(self.img_dir) if f.lower().endswith(exts)])
        
        if not self.image_files:
            messagebox.showerror("Error", "No valid image files found!")
            return

        self.apply_image_filters()
        self.calculate_global_statistics()

    # =========================================================================
    # Auto-Label Engine (YOLO) — : 
    # =========================================================================
    def load_yolo_model(self) -> None:
        path = filedialog.askopenfilename(title="Select YOLO model (best.pt)", filetypes=[("PyTorch Model", "*.pt")])
        if path:
            self.load_yolo_model_path(path, show_message=True)

    def load_yolo_model_path(self, path: str, show_message: bool = True) -> bool:
        """Load a model supplied by another PK Studio workflow, e.g. Training Studio."""
        if not path:
            return False
        try:
            from ultralytics import YOLO
            self.model_path = path
            self.auto_model = YOLO(path)

            #  dataset  classes.txt  (
            # "Class 1".."Class 10" )  sync  
            # Auto-Label  map 
            if self.src_dir and (not self.cls_file or not os.path.exists(self.cls_file)):
                model_names = self.auto_model.names
                self.classes = [model_names[i] for i in range(len(model_names))]
                self._write_classes_file()
                display_classes = [f"[{i + 1}] {c}" for i, c in enumerate(self.classes)]
                self.cb_classes["values"] = display_classes
                if self.classes:
                    self.cb_classes.current(0)

            if show_message:
                messagebox.showinfo("Model Loaded", f"Model loaded:\n{os.path.basename(path)}")
            return True
        except Exception as e:
            if show_message:
                messagebox.showerror("Model Load Failed", f"Unexpected error: {e}")
            return False

    def _write_classes_file(self) -> None:
        """ classes.txt  dataset  class 
        self.classes (filesOriginal) 
        Original """
        if not self.src_dir:
            return
        try:
            target = os.path.join(self.src_dir, "classes.txt")
            with open(target, "w", encoding="utf-8") as f:
                f.write("\n".join(self.classes))
            self.cls_file = target
        except Exception:
            pass

    def _map_model_result_to_bboxes(self, result):
        """ model.predict()  self.bboxes (pixel x1,y1,x2,y2) 
        map  class  -> index  self.classes 
         Roboflow  classes.txt
         class  self.classes  ()"""
        model_names = self.auto_model.names
        new_bboxes = []
        skipped_classes = set()
        for box in result.boxes:
            cls_name = model_names[int(box.cls.item())]
            if cls_name not in self.classes:
                skipped_classes.add(cls_name)
                continue
            cls_id = self.classes.index(cls_name)
            cx, cy, w, h = box.xywhn[0].tolist()
            x1 = int((cx - w / 2) * self.orig_w)
            y1 = int((cy - h / 2) * self.orig_h)
            x2 = int((cx + w / 2) * self.orig_w)
            y2 = int((cy + h / 2) * self.orig_h)
            new_bboxes.append([cls_id, x1, y1, x2, y2])
        return new_bboxes, skipped_classes

    def auto_label_current_image(self) -> None:
        if self.auto_model is None:
            self.load_yolo_model()
            if self.auto_model is None:
                return
        if not self.filtered_images:
            messagebox.showwarning("Dataset Not Open", "Open a dataset folder first.")
            return
        if self._auto_job and self._auto_job.status in {"pending", "running", "cancelling"}:
            return

        img_name = self.filtered_images[self.current_idx]
        img_path = os.path.join(self.img_dir, img_name)
        self.lbl_file_info.config(text=f"Auto-Label processing: {img_name}")

        def job(cancel_event):
            if cancel_event.is_set():
                return None
            results = self.auto_model.predict(
                source=img_path, conf=self.conf_threshold, imgsz=self.imgsz, verbose=False
            )
            if cancel_event.is_set():
                return None
            return self._map_model_result_to_bboxes(results[0])

        def done(job_obj):
            if job_obj.status == "cancelled" or job_obj.result is None:
                self.lbl_file_info.config(text=f"Auto-Label cancelled: {img_name}")
                return
            new_bboxes, skipped = job_obj.result
            self.bboxes = new_bboxes
            self.selected_box_idx = None
            self.push_history()
            self.render()
            self.update_box_list()
            msg = f"Auto-label complete: {len(new_bboxes)} objects found"
            if skipped:
                msg += f"\n\n(Skipped classes not present in classes.txt: {', '.join(sorted(skipped))})"
            messagebox.showinfo("Auto-Label Complete", msg)

        def error(job_obj):
            self.lbl_file_info.config(text=f"Auto-Label error: {img_name}")
            messagebox.showerror("Auto-Label", f"Processing failed for {img_name}\n\n{job_obj.error}")

        self._auto_job = self.job_manager.start(job, on_done=done, on_error=error, ui_call=ui_queue_for(self).call)

    def cancel_auto_label(self) -> None:
        if self._auto_job and self._auto_job.status in {"pending", "running"}:
            self._auto_job.cancel()

    def run_batch_autolabel(self) -> None:
        if self.auto_model is None:
            self.load_yolo_model()
            if self.auto_model is None:
                return
        if not self.image_files:
            messagebox.showwarning("Dataset Not Open", "Open a dataset folder before starting Batch Auto-Label.")
            return
        if self._batch_running:
            messagebox.showinfo("Batch Auto-Label", "A batch job is already running.")
            return

        to_process = []
        for img_name in self.image_files:
            txt_path = os.path.join(self.lbl_dir, os.path.splitext(img_name)[0] + ".txt")
            if not os.path.exists(txt_path) or os.path.getsize(txt_path) == 0:
                to_process.append(img_name)

        if not to_process:
            messagebox.showinfo("Nothing to Process", "All images already have labels. Batch Auto-Label skips labeled images.")
            return
        if not messagebox.askyesno(
            "Confirm Batch Auto-Label",
            f"Found {len(to_process)} unlabeled images out of {len(self.image_files)} total.\n"
            f"Run Auto-Label on these images?\n"
            f"(Existing labels will not be modified.)",
        ):
            return

        self._batch_running = True
        self._batch_errors = []

        def job(cancel_event):
            done_count = 0
            skipped_classes_all = set()
            total = len(to_process)
            for idx, img_name in enumerate(to_process, start=1):
                if cancel_event.is_set():
                    break
                try:
                    img_path = os.path.join(self.img_dir, img_name)
                    results = self.auto_model.predict(
                        source=img_path, conf=self.conf_threshold, imgsz=self.imgsz, verbose=False
                    )
                    model_names = self.auto_model.names
                    lines = []
                    for box in results[0].boxes:
                        cls_name = model_names[int(box.cls.item())]
                        if cls_name not in self.classes:
                            skipped_classes_all.add(cls_name)
                            continue
                        cls_id = self.classes.index(cls_name)
                        cx, cy, w, h = box.xywhn[0].tolist()
                        lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                    txt_path = os.path.join(self.lbl_dir, os.path.splitext(img_name)[0] + ".txt")
                    atomic_write_text(txt_path, "\n".join(lines))
                    done_count += 1
                except Exception as exc:
                    self._batch_errors.append({"file": img_name, "error": str(exc)})
                self.after(0, lambda i=idx, t=total: self.lbl_file_info.config(
                    text=f"Batch Auto-Label: {i}/{t} images..."
                ))
            return done_count, skipped_classes_all, len(to_process)

        def finish(job_obj):
            self._batch_running = False
            done_count, skipped_classes_all, total = job_obj.result or (0, set(), len(to_process))
            error_count = len(self._batch_errors)
            state = "cancelled" if job_obj.status == "cancelled" else "completed"
            msg = f"Batch Auto-Label {state}!\nSuccess: {done_count} | Errors: {error_count} | Total: {total}"
            if skipped_classes_all:
                msg += f"\n\n(Skipped classes not present in classes.txt: {', '.join(sorted(skipped_classes_all))})"
            if self._batch_errors:
                msg += "\n\nFailed files:\n" + "\n".join(
                    f"- {e['file']}: {e['error']}" for e in self._batch_errors[:10]
                )
                if len(self._batch_errors) > 10:
                    msg += f"\n... and {len(self._batch_errors) - 10} more"
            messagebox.showinfo("Batch Auto-Label", msg)
            self.apply_image_filters()
            self.calculate_global_statistics()

        def error(job_obj):
            self._batch_running = False
            messagebox.showerror("Batch Auto-Label", f"Batch failed: {job_obj.error}")

        self._auto_job = self.job_manager.start(job, on_done=finish, on_error=error, ui_call=ui_queue_for(self).call)

    def load_current_image(self):
        if not self.filtered_images:
            self.canvas.delete("all")
            self.lbl_file_info.config(text="No images match current filter criteria!")
            return

        img_name = self.filtered_images[self.current_idx]
        img_path = os.path.join(self.img_dir, img_name)
        
        img_data = np.fromfile(img_path, dtype=np.uint8)
        self.cv_img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
        self.orig_h, self.orig_w, _ = self.cv_img.shape

        txt_name = os.path.splitext(img_name)[0] + ".txt"
        txt_path = os.path.join(self.lbl_dir, txt_name)

        self.bboxes = []
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id = int(parts[0])
                        cx, cy, w, h = map(float, parts[1:5])
                        
                        x1 = int((cx - w / 2) * self.orig_w)
                        y1 = int((cy - h / 2) * self.orig_h)
                        x2 = int((cx + w / 2) * self.orig_w)
                        y2 = int((cy + h / 2) * self.orig_h)
                        self.bboxes.append([cls_id, x1, y1, x2, y2])

        self.selected_box_idx = None
        self.reset_zoom()
        self.clear_typing_buffer()
        self.init_history()
        self.render()
        self.update_box_list()
        
        is_rev = self.meta_data.get(img_name, {}).get("reviewed", False)
        rev_str = "✓ Reviewed" if is_rev else "⚠ Unreviewed"
        
        self.lbl_file_info.config(text=f"[{self.current_idx + 1}/{len(self.filtered_images)}] {img_name} ({rev_str})")

    def calculate_global_statistics(self):
        if not self.image_files:
            return

        global_cls_counts = {i: 0 for i in range(len(self.classes))}
        total_boxes = 0

        for img_name in self.image_files:
            txt_name = os.path.splitext(img_name)[0] + ".txt"
            txt_path = os.path.join(self.lbl_dir, txt_name)
            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts:
                            cls_id = int(parts[0])
                            global_cls_counts[cls_id] = global_cls_counts.get(cls_id, 0) + 1
                            total_boxes += 1

        stats_lines = [
            f"Total Dataset Images: {len(self.image_files)}",
            f"Total Dataset Boxes:  {total_boxes}",
            "=" * 30,
            "Class Breakdown (Whole Folder):"
        ]
        for i, c_name in enumerate(self.classes):
            count = global_cls_counts.get(i, 0)
            stats_lines.append(f"  [{i + 1}] {c_name}: {count}")

        self.global_stats_text.config(state="normal")
        self.global_stats_text.delete("1.0", tk.END)
        self.global_stats_text.insert(tk.END, "\n".join(stats_lines))
        self.global_stats_text.config(state="disabled")

    def apply_class_change(self):
        if self.selected_box_idx is not None and self.selected_box_idx < len(self.bboxes):
            cls_id = self.cb_classes.current()
            if cls_id >= 0:
                self.bboxes[self.selected_box_idx][0] = cls_id
                self.push_history()
                self.render()
                self.update_box_list()

    def canvas_to_orig(self, cx, cy):
        ox = int((cx - self.offset_x) / self.render_scale)
        oy = int((cy - self.offset_y) / self.render_scale)
        return max(0, min(ox, self.orig_w)), max(0, min(oy, self.orig_h))

    def render_temp(self, temp_bboxes):
        curr_bboxes = self.bboxes
        self.bboxes = temp_bboxes
        self.render()
        self.bboxes = curr_bboxes

    def reset_zoom(self):
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.lbl_zoom.config(text="100%")

    def change_zoom(self, delta):
        self.zoom_level = max(0.25, min(8.0, self.zoom_level + delta))
        self.lbl_zoom.config(text=f"{int(self.zoom_level * 100)}%")
        self.render()

    def on_mouse_wheel(self, event):
        delta = 0.15 if event.delta > 0 else -0.15
        self.change_zoom(delta)

    def init_history(self):
        self.history = [[list(b) for b in self.bboxes]]
        self.history_idx = 0

    def push_history(self):
        self.history = self.history[:self.history_idx + 1]
        self.history.append([list(b) for b in self.bboxes])
        self.history_idx += 1

    def undo(self):
        if self.history_idx > 0:
            self.history_idx -= 1
            self.bboxes = [list(b) for b in self.history[self.history_idx]]
            self.render()
            self.update_box_list()

    def redo(self):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self.bboxes = [list(b) for b in self.history[self.history_idx]]
            self.render()
            self.update_box_list()

    def _ensure_dataset_structure(self, root_dir):
        """Create the standard PK/YOLO dataset layout.

        A saved annotation dataset always has:
          dataset/images/   -> source images
          dataset/labels/   -> YOLO .txt annotations
          dataset/classes.txt -> one class name per line
        """
        root_dir = os.path.abspath(root_dir)
        self.src_dir = root_dir
        self.img_dir = os.path.join(root_dir, "images")
        self.lbl_dir = os.path.join(root_dir, "labels")
        self.meta_file = os.path.join(root_dir, ".pk_annotation_meta.json")
        self.cls_file = os.path.join(root_dir, "classes.txt")
        os.makedirs(self.img_dir, exist_ok=True)
        os.makedirs(self.lbl_dir, exist_ok=True)
        if self.classes:
            self._write_classes_file()
        return root_dir

    def save_as_dataset(self):
        """Save the current annotation project as a self-contained dataset.

        The user chooses a destination folder. PK Studio creates images/ and
        labels/, copies the source images, and writes classes.txt. Existing
        annotation files in the destination are never overwritten unless they
        are generated by the current Save operation.
        """
        if not self.image_files:
            messagebox.showwarning("Save As", "Open a dataset first.")
            return

        parent = filedialog.askdirectory(title="Select output folder for Save As")
        if not parent:
            return

        dataset_name = simpledialog.askstring(
            "Save Dataset As",
            "Dataset folder name:",
            initialvalue=os.path.basename(self.src_dir) or "dataset",
            parent=self.winfo_toplevel(),
        )
        if not dataset_name:
            return
        dataset_name = dataset_name.strip()
        if not dataset_name:
            return

        destination = os.path.join(parent, dataset_name)
        if os.path.exists(destination) and os.listdir(destination):
            if not messagebox.askyesno(
                "Save As",
                f"This folder already contains files:\n{destination}\n\nUse this folder anyway?",
            ):
                return

        source_img_dir = self.img_dir if os.path.isdir(self.img_dir) else self.src_dir
        source_root = self.src_dir
        source_lbl_dir = os.path.join(source_root, "labels") if os.path.isdir(os.path.join(source_root, "labels")) else source_root
        self._ensure_dataset_structure(destination)

        copied = 0
        errors = []
        exts = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
        for img_name in self.image_files:
            src = os.path.join(source_img_dir, img_name)
            dst = os.path.join(self.img_dir, img_name)
            if not os.path.isfile(src):
                errors.append(f"File not found: {img_name}")
                continue
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
            except OSError as exc:
                errors.append(f"{img_name}: {exc}")

        # Copy existing annotations from the source dataset.
        for img_name in self.image_files:
            txt_name = os.path.splitext(img_name)[0] + ".txt"
            candidate = os.path.join(source_lbl_dir, txt_name)
            if not os.path.exists(candidate):
                candidate = os.path.join(source_img_dir, txt_name)
            if os.path.isfile(candidate):
                try:
                    shutil.copy2(candidate, os.path.join(self.lbl_dir, txt_name))
                except OSError as exc:
                    errors.append(f"{txt_name}: {exc}")

        # Save the current in-memory annotations to the new labels folder.
        self.filtered_images = list(self.image_files)
        if self.current_idx >= len(self.filtered_images):
            self.current_idx = max(0, len(self.filtered_images) - 1)
        self.save_current()

        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(self.meta_data, f, indent=2, ensure_ascii=False)
        self._write_classes_file()

        msg = (
            f"Dataset saved successfully\n\n"
            f"{destination}\n\n"
            f"images/: {copied} files\n"
            f"labels/: YOLO .txt files\n"
            f"classes.txt : {len(self.classes)} classes"
        )
        if errors:
            msg += f"\n\nFound {len(errors)} errors"
        messagebox.showinfo("Save As Complete", msg)
        self.image_files = sorted(
            [f for f in os.listdir(self.img_dir) if f.lower().endswith(exts)],
            key=str.casefold,
        )
        self.apply_image_filters()
        self.calculate_global_statistics()

    def _write_current_labels(self):
        """Write the current image's label/meta files to disk without
        recomputing the whole-dataset statistics. Used both by the explicit
        Save button and by the lightweight auto-save on navigation."""
        if not self.filtered_images:
            return

        # Save always guarantees the standard folder layout. This is especially
        # useful when a user opened a flat image folder and then starts labeling.
        os.makedirs(self.lbl_dir, exist_ok=True)
        os.makedirs(self.img_dir, exist_ok=True)
        self._write_classes_file()

        img_name = self.filtered_images[self.current_idx]
        txt_name = os.path.splitext(img_name)[0] + ".txt"
        txt_path = os.path.join(self.lbl_dir, txt_name)

        lines = []
        for cls_id, x1, y1, x2, y2 in self.bboxes:
            bw = (x2 - x1) / self.orig_w
            bh = (y2 - y1) / self.orig_h
            cx = (x1 + (x2 - x1) / 2) / self.orig_w
            cy = (y1 + (y2 - y1) / 2) / self.orig_h
            lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        atomic_write_text(txt_path, "\n".join(lines))

        if img_name not in self.meta_data:
            self.meta_data[img_name] = {}

        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(self.meta_data, f, indent=2)

    def save_current(self):
        if not self.filtered_images:
            return
        self._write_current_labels()
        self.calculate_global_statistics()

    def save_all(self):
        self.save_current()
        messagebox.showinfo("Save All", "Saved labels directly to dataset folder!")

    def prev_image(self):
        if self.current_idx > 0:
            # Auto-save the image we're leaving before moving away from it.
            self._write_current_labels()
            self.current_idx -= 1
            self.load_current_image()

    def next_image(self):
        if not self.filtered_images:
            return

        img_name = self.filtered_images[self.current_idx]
        if img_name not in self.meta_data:
            self.meta_data[img_name] = {}
        
        self.meta_data[img_name]["reviewed"] = True

        # Auto-save the image we're leaving before moving away from it.
        self._write_current_labels()

        if self.current_idx < len(self.filtered_images) - 1:
            self.current_idx += 1
            self.load_current_image()
        else:
            self.load_current_image()

    def delete_selected_box(self):
        if self.selected_box_idx is not None and self.selected_box_idx < len(self.bboxes):
            del self.bboxes[self.selected_box_idx]
            self.selected_box_idx = None
            self.push_history()
            self.render()
            self.update_box_list()

    def update_stats(self):
        total_images = len(self.filtered_images)
        reviewed_images = sum(1 for v in self.meta_data.values() if v.get("reviewed", False))
        self.lbl_progress.config(text=f"Filtered Images: {total_images} | Reviewed: {reviewed_images}")

    def on_number_key(self, digit):
        self.class_input_buffer += digit
        self.update_typing_feedback()

    def on_key_backspace(self):
        if self.class_input_buffer:
            self.class_input_buffer = self.class_input_buffer[:-1]
            self.update_typing_feedback()
        else:
            self.delete_selected_box()

    def clear_typing_buffer(self):
        self.class_input_buffer = ""
        self.update_typing_feedback()

    def update_typing_feedback(self):
        if self.class_input_buffer:
            try:
                user_num = int(self.class_input_buffer)
                target_idx = user_num - 1
                
                if 0 <= target_idx < len(self.classes):
                    c_name = self.classes[target_idx]
                    self.lbl_typing_feedback.config(text=f"Typing: [{user_num}] ➔ {c_name} (Press ENTER)", foreground=COLORS["warning"])
                else:
                    self.lbl_typing_feedback.config(text=f"Typing: [{user_num}] (Out of range!)", foreground=COLORS["danger"])
            except ValueError:
                pass
        else:
            self.lbl_typing_feedback.config(text="Type Class ID + Enter to apply", foreground=COLORS["accent"])

    def on_key_enter(self):
        if self.class_input_buffer:
            try:
                user_num = int(self.class_input_buffer)
                target_idx = user_num - 1
                
                if 0 <= target_idx < len(self.classes):
                    self.cb_classes.current(target_idx)
                    if self.selected_box_idx is not None and self.selected_box_idx < len(self.bboxes):
                        self.bboxes[self.selected_box_idx][0] = target_idx
                        self.push_history()
                        self.render()
                        self.update_box_list()
            except ValueError:
                pass
            
            self.clear_typing_buffer()
