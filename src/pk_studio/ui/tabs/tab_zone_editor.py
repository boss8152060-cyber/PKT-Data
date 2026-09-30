"""
=========================================================================
PK Studio - Tab: Zone Editor

Draw polygon zones on a chosen video frame (entry / exit / conflict /
detection zones) and export them as JSON so a downstream tracking script
can test whether a detected object's position falls inside a given zone
on each frame (e.g. for PET / Gap Acceptance analysis at access points).

Workflow:
  1. Open a video.
  2. Scrub to a clear reference frame (scrubber + frame step buttons).
  3. Set a zone name first (optional but handy), then left-click on
     the canvas to place polygon vertices (>= 3 points).
  4. Right-click removes the last placed vertex while drawing.
  5. Click back near the first point (it grows a white ring) to snap-close
     the polygon, or press Enter / "Finish Zone" / double-click.
  6. Select a zone in the list to drag its points and reshape it; right-click
     a point (while a zone is selected) to delete that point.
  7. Save all zones to a .json file (pixel + normalized coordinates), or
     export ready-to-use Python code.
=========================================================================
"""

import json
import uuid
import copy
import tkinter as tk
from datetime import datetime
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

from pk_studio.theme import COLORS

VIDEO_FILETYPES = [
    ("Video files", "*.mp4 *.avi *.mov *.mkv *.MP4 *.AVI *.MOV *.MKV"),
    ("All files", "*.*"),
]

SNAP_RADIUS_PX = 12    # canvas-space distance (screen px) that snaps/closes the polygon
VERTEX_HIT_PX = 10     # canvas-space distance (screen px) that counts as "clicked this vertex"
MAX_UNDO = 50

# Thai-capable fonts to try, in order — Windows fonts first (the app's actual
# target), then common Linux Thai fonts (so this also renders correctly when
# developed/tested on Linux), then a generic Unicode fallback.
FONT_CANDIDATES = [
    "tahoma.ttf", "Tahoma.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/leelawui.ttf",
    "C:/Windows/Fonts/angsau.ttf",
    "C:/Windows/Fonts/cordiau.ttf",
    "/usr/share/fonts/truetype/tlwg/Garuda.ttf",
    "/usr/share/fonts/truetype/tlwg/Loma.ttf",
    "/usr/share/fonts/truetype/tlwg/Sawasdee.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# BGR palette (cv2 drawing order) — cycled per zone so each new zone gets a
# visually distinct, stable color that is also saved into the zone's data.
ZONE_PALETTE_BGR = [
    (0, 200, 0),      # green
    (0, 0, 230),      # red
    (0, 150, 255),    # orange
    (230, 120, 0),    # blue
    (200, 0, 200),    # magenta
    (0, 210, 210),    # yellow-ish cyan
    (255, 0, 120),    # purple-pink
    (0, 255, 255),    # yellow
    (150, 150, 150),  # gray
    (255, 255, 0),    # cyan
]


def _format_area(area_px):
    """Compact display for the zone list column so it never gets clipped."""
    if area_px >= 10000:
        return f"{area_px / 1000:.1f}k"
    return f"{area_px:,.0f}"


class ZoneEditorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=0)

        # Video state
        self.video_path = ""
        self.cap = None
        self.fps = 0.0
        self.total_frames = 0
        self.orig_w, self.orig_h = 1, 1
        self.current_frame_idx = 0
        self.cv_frame = None

        # Zone state
        self.zones = []            # list of dicts (see _finish_zone)
        self.current_points = []   # in-progress polygon, orig pixel coords
        self.selected_zone_idx = None
        self.dragging_vertex_idx = None  # index into the selected zone's points, while dragging
        self.mouse_orig_pos = None       # last known mouse position, orig pixel coords
        self._pan_drag_start = None      # (event.x, event.y) while right-button is held
        self._pan_did_drag = False       # True once a right-drag has moved past the click threshold
        self.zones_file = ""

        # Zone name presets — set up before drawing, then recall with
        # number keys (any length) + Enter instead of retyping every time.
        self.zone_presets = []     # list of {"name": ...}
        self.preset_input_buffer = ""

        # Undo / redo — snapshots of self.zones taken before each mutation.
        self.undo_stack = []
        self.redo_stack = []

        # Canvas render state
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.offset_x = 0
        self.offset_y = 0
        self.render_scale = 1.0
        self.tk_image = None
        self._font_cache = {}

        self.show_all_labels = tk.BooleanVar(value=True)

        self._updating_scrub = False

        self._build_ui()
        self._bind_shortcuts()

    # =====================================================================
    # UI
    # =====================================================================
    def _build_ui(self):
        top_bar = ttk.Frame(self, padding=(12, 10, 12, 4))
        top_bar.pack(fill="x")

        ttk.Button(top_bar, text="📂 Open Video", command=self._pick_video).pack(side="left")
        self.lbl_video_path = ttk.Label(top_bar, text="No video loaded", foreground=COLORS["text_muted"])
        self.lbl_video_path.pack(side="left", padx=(8, 10))

        ttk.Separator(top_bar, orient="vertical").pack(side="left", fill="y", padx=4)
        ttk.Button(top_bar, text="❓ Help", style="Secondary.TButton", command=self._show_help_popup).pack(side="left", padx=2)
        ttk.Button(top_bar, text="↶ Undo", style="Secondary.TButton", command=self._undo).pack(side="left", padx=2)
        ttk.Button(top_bar, text="↷ Redo", style="Secondary.TButton", command=self._redo).pack(side="left", padx=2)

        ttk.Separator(top_bar, orient="vertical").pack(side="left", fill="y", padx=4)
        ttk.Button(top_bar, text="💾 Save", command=self._save_zones).pack(side="left", padx=2)
        ttk.Button(top_bar, text="📂 Load", style="Secondary.TButton", command=self._load_zones).pack(side="left", padx=2)
        ttk.Button(top_bar, text="🐍 Export .py", style="Secondary.TButton", command=self._show_code_preview).pack(side="left", padx=2)
        ttk.Button(top_bar, text="🗑 Clear All", style="Secondary.TButton", command=self._clear_all_zones).pack(side="left", padx=2)

        self.lbl_frame_info = ttk.Label(top_bar, text="", foreground=COLORS["text_muted"])
        self.lbl_frame_info.pack(side="right")

        # -----------------------------------------------------------
        # Frame scrubber
        # -----------------------------------------------------------
        scrub_bar = ttk.Frame(self, padding=(12, 0, 12, 6))
        scrub_bar.pack(fill="x")

        ttk.Button(scrub_bar, text="|◀", width=3, command=lambda: self._step_frame(-1)).pack(side="left")
        self.scrubber = ttk.Scale(
            scrub_bar, from_=0, to=0, orient="horizontal", command=self._on_scrub_drag
        )
        self.scrubber.pack(side="left", fill="x", expand=True, padx=6)
        self.scrubber.bind("<ButtonRelease-1>", self._on_scrub_release)
        ttk.Button(scrub_bar, text="▶|", width=3, command=lambda: self._step_frame(1)).pack(side="left")

        ttk.Button(scrub_bar, text="◀◀ 1s", command=self._step_back_1s).pack(side="left", padx=(10, 2))
        ttk.Button(scrub_bar, text="1s ▶▶", command=self._step_fwd_1s).pack(side="left", padx=(2, 10))

        ttk.Label(scrub_bar, text="Go to frame:").pack(side="left")
        self.entry_jump_frame = ttk.Entry(scrub_bar, width=8)
        self.entry_jump_frame.pack(side="left", padx=4)
        self.entry_jump_frame.bind("<Return>", lambda e: self._on_jump_frame())
        ttk.Button(scrub_bar, text="Go", command=self._on_jump_frame).pack(side="left", padx=(0, 10))

        ttk.Button(scrub_bar, text="⤢ Reset View", style="Secondary.TButton", command=self._reset_view).pack(side="left")

        # -----------------------------------------------------------
        # Body: canvas + side panel, in a draggable split so the panel
        # width can be adjusted if content would otherwise get clipped.
        # -----------------------------------------------------------
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=(12, 12), pady=(0, 10))

        canvas_frame = tk.Frame(body, bg="#1A1A1A")
        self.canvas = tk.Canvas(canvas_frame, bg="#1A1A1A", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.render())
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", lambda e: self._finish_zone())
        self.canvas.bind("<ButtonPress-3>", self._on_canvas_right_press)
        self.canvas.bind("<B3-Motion>", self._on_canvas_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_canvas_right_release)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Return>", lambda e: self._finish_zone())
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, 0.15))   # Linux scroll up
        self.canvas.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, -0.15))  # Linux scroll down

        # The side panel is wrapped in its own scrollable canvas so that on
        # a short window (or with several presets/zones) every section is
        # still reachable by scrolling — nothing gets silently clipped off.
        side_container = ttk.Frame(body)
        side_canvas = tk.Canvas(side_container, highlightthickness=0, bg=COLORS["main_bg"])
        side_scroll = ttk.Scrollbar(side_container, orient="vertical", command=side_canvas.yview)
        side_canvas.configure(yscrollcommand=side_scroll.set)
        side_canvas.pack(side="left", fill="both", expand=True)
        side_scroll.pack(side="right", fill="y")

        side = ttk.Frame(side_canvas, padding=(6, 0, 6, 10))
        side_window = side_canvas.create_window((0, 0), window=side, anchor="nw")

        def _sync_scrollregion(_event=None):
            side_canvas.configure(scrollregion=side_canvas.bbox("all"))

        def _sync_side_width(event):
            side_canvas.itemconfig(side_window, width=event.width)

        side.bind("<Configure>", _sync_scrollregion)
        side_canvas.bind("<Configure>", _sync_side_width)

        def _on_side_wheel(event):
            side_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_wheel(_e):
            side_canvas.bind_all("<MouseWheel>", _on_side_wheel)

        def _unbind_wheel(_e):
            side_canvas.unbind_all("<MouseWheel>")

        side_canvas.bind("<Enter>", _bind_wheel)
        side_canvas.bind("<Leave>", _unbind_wheel)

        body.add(canvas_frame, weight=3)
        body.add(side_container, weight=1)

        # ---- Zone name: one merged box (saved-name list + the active name
        # for the zone about to be finished) instead of two look-alike boxes.
        name_box = ttk.LabelFrame(side, text="Zone name")
        name_box.pack(fill="x", pady=(0, 8))

        ttk.Label(name_box, text="Name for the next zone:").pack(anchor="w", padx=8, pady=(8, 0))
        self.entry_zone_name = ttk.Entry(name_box)
        self.entry_zone_name.pack(fill="x", padx=8, pady=(2, 4))
        self.entry_zone_name.bind("<Return>", lambda e: self._finish_zone())

        ttk.Button(name_box, text="+ Save this name to the list below", style="Secondary.TButton", command=self._add_preset).pack(fill="x", padx=8, pady=(0, 6))

        ttk.Label(name_box, text="Saved names (click, or type a number + Enter):").pack(anchor="w", padx=8)
        self.list_presets = tk.Listbox(name_box, height=4, exportselection=False)
        self.list_presets.pack(fill="x", padx=8, pady=(2, 4))
        self.list_presets.bind("<<ListboxSelect>>", self._on_preset_listbox_select)

        ttk.Button(name_box, text="✕ Remove Selected", style="Secondary.TButton", command=self._remove_selected_preset).pack(fill="x", padx=8, pady=(0, 6))

        self.lbl_preset_typing = ttk.Label(
            name_box, text="Type a number + Enter to load a saved name", foreground=COLORS["text_muted"], wraplength=290, justify="left",
        )
        self.lbl_preset_typing.pack(anchor="w", padx=8, pady=(0, 8))

        btn_row = ttk.Frame(name_box)
        btn_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btn_row, text="✔ Finish Zone", command=self._finish_zone).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(btn_row, text="✕ Cancel Draw", style="Secondary.TButton", command=self._cancel_draw).pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.lbl_point_count = ttk.Label(name_box, text="Points placed: 0", foreground=COLORS["text_muted"])
        self.lbl_point_count.pack(anchor="w", padx=8, pady=(0, 8))

        list_box = ttk.LabelFrame(side, text="Zones")
        list_box.pack(fill="both", expand=True, pady=(0, 8))

        ttk.Checkbutton(
            list_box, text="Show name labels on canvas", variable=self.show_all_labels,
            command=self.render,
        ).pack(anchor="w", padx=8, pady=(8, 2))

        self.tree_zones = ttk.Treeview(
            list_box, columns=("pts", "area", "lbl"), show="tree headings", height=8, selectmode="browse"
        )
        self.tree_zones.heading("#0", text="Name")
        self.tree_zones.heading("pts", text="Pts")
        self.tree_zones.heading("area", text="Area px\u00b2")
        self.tree_zones.heading("lbl", text="Label")
        self.tree_zones.column("#0", width=120, minwidth=60)
        self.tree_zones.column("pts", width=30, minwidth=24, anchor="center")
        self.tree_zones.column("area", width=64, minwidth=44, anchor="e")
        self.tree_zones.column("lbl", width=44, minwidth=36, anchor="center")
        self.tree_zones.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree_zones.bind("<<TreeviewSelect>>", self._on_zone_select)
        self.tree_zones.bind("<Delete>", lambda e: self._delete_selected_zone())
        self.tree_zones.bind("<BackSpace>", lambda e: self._delete_selected_zone())

        zone_btn_row = ttk.Frame(list_box)
        zone_btn_row.pack(fill="x", padx=8, pady=(0, 3))
        ttk.Button(zone_btn_row, text="Rename", style="Secondary.TButton", command=self._rename_selected_zone).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(zone_btn_row, text="🎨 Color", style="Secondary.TButton", command=self._change_selected_zone_color).pack(side="left", expand=True, fill="x", padx=(3, 0))

        zone_btn_row2 = ttk.Frame(list_box)
        zone_btn_row2.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(zone_btn_row2, text="🏷 Toggle Label", style="Secondary.TButton", command=self._toggle_selected_zone_label).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(zone_btn_row2, text="Delete", style="Secondary.TButton", command=self._delete_selected_zone).pack(side="left", expand=True, fill="x", padx=(3, 0))

        self.status_label = ttk.Label(self, text="Open a video to begin.", padding=(12, 4), foreground=COLORS["text_muted"])
        self.status_label.pack(fill="x", side="bottom")

    # =====================================================================
    # Video loading / navigation
    # =====================================================================
    def _pick_video(self):
        path = filedialog.askopenfilename(title="Select a video", filetypes=VIDEO_FILETYPES)
        if not path:
            return
        if self.zones:
            if not messagebox.askyesno(
                "Open new video",
                "Opening a new video will clear the zones you've drawn so far "
                "(save them first if you want to keep them). Continue?",
            ):
                return
        self._load_video(path)

    def _load_video(self, path):
        if self.cap is not None:
            self.cap.release()

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            messagebox.showerror("Error", f"Could not open video:\n{path}")
            return

        self.cap = cap
        self.video_path = path
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        self.total_frames = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        self.orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1
        self.orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1

        self.zones = []
        self.current_points = []
        self.selected_zone_idx = None
        self.dragging_vertex_idx = None
        self.undo_stack = []
        self.redo_stack = []
        self._refresh_zone_list()

        self.scrubber.config(from_=0, to=max(0, self.total_frames - 1))
        self.reset_zoom()

        self.lbl_video_path.config(text=Path(path).name, foreground=COLORS["text_dark"])
        self._seek_and_load_frame(0)
        self.status_label.config(text=f"Loaded video: {path}  ({self.orig_w}x{self.orig_h}, {self.total_frames} frames)")

    def _seek_and_load_frame(self, idx):
        if self.cap is None:
            return
        idx = max(0, min(idx, self.total_frames - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = self.cap.read()
        if not ret:
            messagebox.showwarning("Warning", f"Could not read frame {idx}.")
            return

        self.cv_frame = frame
        self.current_frame_idx = idx

        self._updating_scrub = True
        self.scrubber.set(idx)
        self._updating_scrub = False

        t_str = f"  |  t={idx / self.fps:.2f}s" if self.fps > 0 else ""
        self.lbl_frame_info.config(text=f"Frame {idx + 1}/{self.total_frames}{t_str}")
        self.render()

    def _step_frame(self, delta):
        if self.cap is None:
            return
        self._seek_and_load_frame(self.current_frame_idx + delta)

    def _step_back_1s(self):
        step = int(self.fps) if self.fps > 0 else 30
        self._step_frame(-step)

    def _step_fwd_1s(self):
        step = int(self.fps) if self.fps > 0 else 30
        self._step_frame(step)

    def _on_scrub_drag(self, value):
        # Lightweight preview while dragging — avoid reading a video frame on
        # every pixel of drag movement; the actual seek happens on release.
        if self._updating_scrub or self.cap is None:
            return
        idx = int(float(value))
        t_str = f"  |  t={idx / self.fps:.2f}s" if self.fps > 0 else ""
        self.lbl_frame_info.config(text=f"Frame {idx + 1}/{self.total_frames}{t_str} (dragging...)")

    def _on_scrub_release(self, _event):
        if self.cap is None:
            return
        idx = int(float(self.scrubber.get()))
        self._seek_and_load_frame(idx)

    def _on_jump_frame(self):
        if self.cap is None:
            return
        val = self.entry_jump_frame.get().strip()
        if not val.isdigit():
            messagebox.showwarning("Warning", "Enter a frame number.")
            return
        target = int(val) - 1  # shown as 1-based to match the frame info label
        if 0 <= target < self.total_frames:
            self._seek_and_load_frame(target)
            self.entry_jump_frame.delete(0, tk.END)
        else:
            messagebox.showerror("Error", f"Valid range: 1 to {self.total_frames}.")

    # =====================================================================
    # Zone presets + keyboard shortcuts (1-9 to recall, Enter to finish)
    # =====================================================================
    def _bind_shortcuts(self):
        # add="+" so this never displaces the Label tab's own global keypress
        # binding on the same root window — both handlers run; each one
        # ignores key events while its own tab isn't the visible one.
        self.winfo_toplevel().bind("<KeyPress>", self._on_global_keypress, add="+")

    def _on_global_keypress(self, event):
        if not self.winfo_ismapped():
            return  # the Zone tab isn't the one currently showing
        if isinstance(self.focus_get(), (ttk.Entry, tk.Entry, tk.Text, ttk.Combobox, tk.Listbox)):
            return  # don't hijack typing in a text field

        ctrl_held = bool(event.state & 0x4)
        if ctrl_held and event.keysym.lower() == "z":
            self._undo()
            return "break"
        if ctrl_held and event.keysym.lower() in ("y",):
            self._redo()
            return "break"

        if event.keysym in ("Return", "KP_Enter"):
            if self.preset_input_buffer:
                self._apply_typed_preset()
            else:
                self._finish_zone()
            return "break"

        if event.keysym == "Escape":
            if self.preset_input_buffer:
                self._clear_preset_typing_buffer()
            else:
                self._cancel_draw()
            return "break"

        if event.keysym in ("BackSpace", "Delete") and self.preset_input_buffer:
            self.preset_input_buffer = self.preset_input_buffer[:-1]
            self._update_preset_typing_feedback()
            return "break"

        digit = None
        if event.char.isdigit():
            digit = event.char
        elif event.keysym.startswith("KP_") and event.keysym[3:].isdigit():
            digit = event.keysym[3:]

        if digit is not None:
            self.preset_input_buffer += digit
            self._update_preset_typing_feedback()
            return "break"

    # ---- Zone name presets (any number of them; recalled by typing their
    # number, of any length, then Enter — not limited to single digits) ----
    def _refresh_preset_list(self):
        self.list_presets.delete(0, tk.END)
        for i, p in enumerate(self.zone_presets, start=1):
            self.list_presets.insert(tk.END, f"{i}. {p['name']}")

    def _add_preset(self):
        name = self.entry_zone_name.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Type a name in the field above first.")
            return
        self.zone_presets.append({"name": name})
        self._refresh_preset_list()
        self.status_label.config(text=f"Saved '{name}' as preset #{len(self.zone_presets)}.")

    def _remove_selected_preset(self):
        sel = self.list_presets.curselection()
        if not sel:
            messagebox.showinfo("No selection", "Select a saved name from the list first.")
            return
        del self.zone_presets[sel[0]]
        self._refresh_preset_list()

    def _apply_preset(self, idx):
        if idx < 0 or idx >= len(self.zone_presets):
            self.status_label.config(text=f"No saved name #{idx + 1} — save one first.")
            return
        preset = self.zone_presets[idx]
        self.entry_zone_name.delete(0, tk.END)
        self.entry_zone_name.insert(0, preset["name"])
        self.status_label.config(
            text=f"Loaded #{idx + 1}: '{preset['name']}' \u2014 press Enter (or Finish Zone) to close the polygon."
        )

    def _on_preset_listbox_select(self, _event):
        sel = self.list_presets.curselection()
        if sel:
            self._apply_preset(sel[0])

    def _update_preset_typing_feedback(self):
        if self.preset_input_buffer:
            try:
                num = int(self.preset_input_buffer)
            except ValueError:
                return
            idx = num - 1
            if 0 <= idx < len(self.zone_presets):
                name = self.zone_presets[idx]["name"]
                self.lbl_preset_typing.config(text=f"Typing: [{num}] \u2192 {name} (Enter to load)", foreground=COLORS["warning"])
            else:
                self.lbl_preset_typing.config(text=f"Typing: [{num}] (out of range)", foreground=COLORS["danger"])
        else:
            self.lbl_preset_typing.config(text="Type a number + Enter to load a saved name", foreground=COLORS["text_muted"])

    def _clear_preset_typing_buffer(self):
        self.preset_input_buffer = ""
        self._update_preset_typing_feedback()

    def _apply_typed_preset(self):
        try:
            num = int(self.preset_input_buffer)
            self._apply_preset(num - 1)
        except ValueError:
            pass
        self._clear_preset_typing_buffer()

    def _show_help_popup(self):
        messagebox.showinfo(
            "How to draw / edit a zone",
            "1) Left-click to place polygon points (need 3+)\n"
            "2) Right-click to undo the last point; right-click + drag pans the view\n"
            "3) Set a name below (before or after drawing) \u2014 or type a saved "
            "name's number + Enter to recall it\n"
            "4) Click back near the first point, press Enter, double-click, "
            "or press \"Finish Zone\" to close it\n"
            "5) Select a zone in the list to drag its points; right-click a "
            "point to delete it\n"
            "6) Scroll wheel zooms; Undo/Redo (or Ctrl+Z / Ctrl+Y) step through zone changes",
            parent=self,
        )

    # =====================================================================
    # Undo / redo — snapshots of the zone list, taken before each mutation
    # =====================================================================
    def _snapshot(self):
        return copy.deepcopy(self.zones)

    def _push_undo(self):
        self.undo_stack.append(self._snapshot())
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _undo(self):
        if not self.undo_stack:
            self.status_label.config(text="Nothing to undo.")
            return
        self.redo_stack.append(self._snapshot())
        self.zones = self.undo_stack.pop()
        self.selected_zone_idx = None
        self.dragging_vertex_idx = None
        self._refresh_zone_list()
        self.render()
        self.status_label.config(text="Undid last zone change.")

    def _redo(self):
        if not self.redo_stack:
            self.status_label.config(text="Nothing to redo.")
            return
        self.undo_stack.append(self._snapshot())
        self.zones = self.redo_stack.pop()
        self.selected_zone_idx = None
        self.dragging_vertex_idx = None
        self._refresh_zone_list()
        self.render()
        self.status_label.config(text="Redid zone change.")

    def reset_zoom(self):
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0

    def _reset_view(self):
        self.reset_zoom()
        self.render()

    def _change_zoom(self, delta):
        self.zoom_level = max(0.25, min(8.0, self.zoom_level + delta))
        self.render()

    def _zoom_at(self, screen_x, screen_y, delta):
        """Zoom in/out while keeping the image point under the cursor fixed
        on screen, instead of always zooming toward the canvas center."""
        if self.cv_frame is None:
            self._change_zoom(delta)
            return

        ox, oy = self.canvas_to_orig(screen_x, screen_y)
        new_zoom = max(0.25, min(8.0, self.zoom_level + delta))
        if new_zoom == self.zoom_level:
            return
        self.zoom_level = new_zoom

        cw = self.canvas.winfo_width() or 800
        ch = self.canvas.winfo_height() or 600
        scale_base = min(cw / self.orig_w, ch / self.orig_h)
        new_render_scale = scale_base * new_zoom
        new_w = int(self.orig_w * new_render_scale)
        new_h = int(self.orig_h * new_render_scale)

        # Solve for the pan that keeps (ox, oy) under (screen_x, screen_y).
        self.pan_x = int(screen_x - ox * new_render_scale - (cw - new_w) // 2)
        self.pan_y = int(screen_y - oy * new_render_scale - (ch - new_h) // 2)

        self.render()

    def _on_mouse_wheel(self, event):
        delta = 0.15 if event.delta > 0 else -0.15
        self._zoom_at(event.x, event.y, delta)

    def canvas_to_orig(self, cx, cy):
        ox = int((cx - self.offset_x) / self.render_scale)
        oy = int((cy - self.offset_y) / self.render_scale)
        return max(0, min(ox, self.orig_w)), max(0, min(oy, self.orig_h))

    @staticmethod
    def _polygon_area(points):
        """Shoelace formula — area in px^2 for a simple (non-self-intersecting) polygon."""
        n = len(points)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0

    # =====================================================================
    # Drawing / editing interactions
    # =====================================================================
    def _find_vertex_at(self, zone_idx, x, y):
        """Return the index of the closest vertex of zones[zone_idx] within
        hit-test tolerance of (x, y) in original pixel coords, or None."""
        if zone_idx is None or zone_idx >= len(self.zones):
            return None
        tol = VERTEX_HIT_PX / max(self.render_scale, 1e-6)
        best_idx, best_dist = None, tol
        for i, (px, py) in enumerate(self.zones[zone_idx]["points"]):
            d = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
            if d <= best_dist:
                best_idx, best_dist = i, d
        return best_idx

    def _on_canvas_press(self, event):
        if self.cv_frame is None:
            return
        self.canvas.focus_set()
        x, y = self.canvas_to_orig(event.x, event.y)

        # If a zone is selected and we're not mid-draw, a click on one of its
        # vertices starts dragging that vertex instead of starting a new shape.
        if not self.current_points and self.selected_zone_idx is not None:
            vidx = self._find_vertex_at(self.selected_zone_idx, x, y)
            if vidx is not None:
                self._push_undo()
                self.dragging_vertex_idx = vidx
                return

        # Snap-close: clicking back near the first point of the in-progress
        # polygon closes it immediately (same as double-click / Finish Zone).
        if len(self.current_points) >= 3:
            fx, fy = self.current_points[0]
            tol = SNAP_RADIUS_PX / max(self.render_scale, 1e-6)
            if abs(x - fx) <= tol and abs(y - fy) <= tol:
                self._finish_zone()
                return

        self.current_points.append((x, y))
        self.lbl_point_count.config(text=f"Points placed: {len(self.current_points)}")
        self.render()

    def _on_canvas_drag(self, event):
        if self.dragging_vertex_idx is None or self.selected_zone_idx is None:
            return
        x, y = self.canvas_to_orig(event.x, event.y)
        zone = self.zones[self.selected_zone_idx]
        zone["points"][self.dragging_vertex_idx] = [x, y]
        self.render()

    def _on_canvas_release(self, _event):
        if self.dragging_vertex_idx is None or self.selected_zone_idx is None:
            return
        zone = self.zones[self.selected_zone_idx]
        zone["area_px"] = round(self._polygon_area(zone["points"]), 2)
        self._refresh_zone_list(keep_selection=True)
        self.dragging_vertex_idx = None
        self.render()

    def _on_canvas_right_press(self, event):
        # Right-click alone (no drag) undoes a point / deletes a vertex;
        # right-click + drag pans the view instead — like the Label tab.
        self._pan_drag_start = (event.x, event.y)
        self._pan_did_drag = False

    def _on_canvas_right_drag(self, event):
        if self._pan_drag_start is None:
            return
        dx = event.x - self._pan_drag_start[0]
        dy = event.y - self._pan_drag_start[1]
        if not self._pan_did_drag and (abs(dx) + abs(dy)) < 3:
            return  # still within click tolerance — not a real drag yet
        self._pan_did_drag = True
        self.pan_x += dx
        self.pan_y += dy
        self._pan_drag_start = (event.x, event.y)
        self.render()

    def _on_canvas_right_release(self, event):
        was_drag = self._pan_did_drag
        self._pan_drag_start = None
        self._pan_did_drag = False
        if was_drag:
            return  # panning already applied live during the drag

        x, y = self.canvas_to_orig(event.x, event.y)

        # If a zone is selected and we're not mid-draw, right-click on one of
        # its vertices deletes that point instead of undoing a drawn point.
        if not self.current_points and self.selected_zone_idx is not None:
            zone = self.zones[self.selected_zone_idx]
            vidx = self._find_vertex_at(self.selected_zone_idx, x, y)
            if vidx is not None:
                if len(zone["points"]) <= 3:
                    messagebox.showwarning("Cannot delete", "A zone needs at least 3 points.")
                    return
                self._push_undo()
                del zone["points"][vidx]
                zone["area_px"] = round(self._polygon_area(zone["points"]), 2)
                self._refresh_zone_list(keep_selection=True)
                self.render()
                return

        if self.current_points:
            self.current_points.pop()
            self.lbl_point_count.config(text=f"Points placed: {len(self.current_points)}")
            self.render()

    def _on_canvas_motion(self, event):
        if self.cv_frame is None:
            return
        self.mouse_orig_pos = self.canvas_to_orig(event.x, event.y)
        # Only worth a re-render while actively drawing, to show the
        # rubber-band preview line and the "click here to close" hint.
        if self.current_points:
            self.render()

    def _cancel_draw(self):
        self.current_points = []
        self.lbl_point_count.config(text="Points placed: 0")
        self.render()

    def _finish_zone(self):
        if self.cv_frame is None:
            return
        if len(self.current_points) < 3:
            messagebox.showwarning("Not enough points", "A zone needs at least 3 points.")
            return

        name = self.entry_zone_name.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Please name the zone before finishing it.")
            return

        color = ZONE_PALETTE_BGR[len(self.zones) % len(ZONE_PALETTE_BGR)]
        area_px = self._polygon_area(self.current_points)

        self._push_undo()
        zone = {
            "id": f"zone_{uuid.uuid4().hex[:8]}",
            "name": name,
            "points": [[int(x), int(y)] for x, y in self.current_points],
            "area_px": round(area_px, 2),
            "color_bgr": list(color),
            "show_label": True,
            "reference_frame_index": self.current_frame_idx,
        }
        self.zones.append(zone)
        self.current_points = []

        self.entry_zone_name.delete(0, tk.END)
        self.lbl_point_count.config(text="Points placed: 0")
        self._refresh_zone_list()
        self.render()
        self.status_label.config(
            text=f"Added zone '{name}' — {len(zone['points'])} points, area \u2248 {area_px:,.0f} px\u00b2."
        )

    # =====================================================================
    # Zone list management
    # =====================================================================
    def _refresh_zone_list(self, keep_selection=False):
        selected = self.tree_zones.selection()
        self.tree_zones.delete(*self.tree_zones.get_children())
        for i, z in enumerate(self.zones):
            area = z.get("area_px")
            if area is None:
                area = self._polygon_area(z["points"])
                z["area_px"] = round(area, 2)
            self.tree_zones.insert(
                "", "end", iid=str(i), text=z["name"],
                values=(len(z["points"]), _format_area(z["area_px"]), "on" if z.get("show_label", True) else "off"),
            )
        if keep_selection and selected:
            try:
                self.tree_zones.selection_set(selected)
            except tk.TclError:
                pass

    def _on_zone_select(self, _event):
        sel = self.tree_zones.selection()
        self.selected_zone_idx = int(sel[0]) if sel else None
        self.render()

    def _rename_selected_zone(self):
        if self.selected_zone_idx is None:
            messagebox.showinfo("No selection", "Select a zone from the list first.")
            return
        zone = self.zones[self.selected_zone_idx]
        new_name = simpledialog.askstring("Rename zone", "New name:", initialvalue=zone["name"])
        if new_name and new_name.strip():
            self._push_undo()
            zone["name"] = new_name.strip()
            self._refresh_zone_list()
            self.render()

    def _change_selected_zone_color(self):
        if self.selected_zone_idx is None:
            messagebox.showinfo("No selection", "Select a zone from the list first.")
            return
        zone = self.zones[self.selected_zone_idx]
        b, g, r = zone.get("color_bgr", [0, 200, 0])
        initial_hex = f"#{r:02x}{g:02x}{b:02x}"
        rgb, _hexstr = colorchooser.askcolor(color=initial_hex, title=f"Color for '{zone['name']}'", parent=self)
        if rgb is None:
            return
        r, g, b = (int(round(v)) for v in rgb)
        self._push_undo()
        zone["color_bgr"] = [b, g, r]
        self.render()

    def _toggle_selected_zone_label(self):
        if self.selected_zone_idx is None:
            messagebox.showinfo("No selection", "Select a zone from the list first.")
            return
        zone = self.zones[self.selected_zone_idx]
        self._push_undo()
        zone["show_label"] = not zone.get("show_label", True)
        self._refresh_zone_list(keep_selection=True)
        self.render()

    def _delete_selected_zone(self):
        if self.selected_zone_idx is None:
            messagebox.showinfo("No selection", "Select a zone from the list first.")
            return
        zone = self.zones[self.selected_zone_idx]
        if messagebox.askyesno("Delete zone", f"Delete zone '{zone['name']}'?"):
            self._push_undo()
            del self.zones[self.selected_zone_idx]
            self.selected_zone_idx = None
            self._refresh_zone_list()
            self.render()

    def _clear_all_zones(self):
        if not self.zones:
            return
        if messagebox.askyesno("Clear all zones", "Delete every zone? You can Undo this afterward."):
            self._push_undo()
            self.zones = []
            self.selected_zone_idx = None
            self._refresh_zone_list()
            self.render()

    # =====================================================================
    # Save / Load
    # =====================================================================
    def _save_zones(self):
        if not self.zones:
            messagebox.showwarning("Nothing to save", "No zones have been drawn yet.")
            return

        default_name = f"{Path(self.video_path).stem}_zones.json" if self.video_path else "zones.json"
        path = filedialog.asksaveasfilename(
            title="Save zones",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("Zone JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        zones_out = []
        for z in self.zones:
            pts = z["points"]
            pts_norm = [[round(x / self.orig_w, 6), round(y / self.orig_h, 6)] for x, y in pts]
            zones_out.append({
                "id": z["id"],
                "name": z["name"],
                "points": pts,
                "points_norm": pts_norm,
                "area_px": z.get("area_px", self._polygon_area(pts)),
                "color_bgr": z.get("color_bgr"),
                "show_label": z.get("show_label", True),
                "reference_frame_index": z.get("reference_frame_index"),
            })

        data = {
            "video_path": self.video_path,
            "frame_width": self.orig_w,
            "frame_height": self.orig_h,
            "zones": zones_out,
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            messagebox.showerror("Save failed", f"Could not save zones:\n{exc}")
            return

        self.zones_file = path
        self.status_label.config(text=f"Saved {len(self.zones)} zone(s) to: {path}")
        messagebox.showinfo("Saved", f"Saved {len(self.zones)} zone(s) to:\n{path}")

    def _load_zones(self):
        path = filedialog.askopenfilename(title="Load zones", filetypes=[("Zone JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            messagebox.showerror("Load failed", f"Could not read zones file:\n{exc}")
            return

        if self.cv_frame is not None:
            fw, fh = data.get("frame_width"), data.get("frame_height")
            if fw and fh and (fw != self.orig_w or fh != self.orig_h):
                if not messagebox.askyesno(
                    "Resolution mismatch",
                    f"This zone file was made for a {fw}x{fh} frame, but the current "
                    f"video is {self.orig_w}x{self.orig_h}. Zone positions may not line "
                    f"up. Load anyway?",
                ):
                    return

        loaded_zones = data.get("zones", [])
        for i, z in enumerate(loaded_zones):
            z.setdefault("id", f"zone_{uuid.uuid4().hex[:8]}")
            z.setdefault("color_bgr", list(ZONE_PALETTE_BGR[i % len(ZONE_PALETTE_BGR)]))
            z.setdefault("show_label", True)

        self._push_undo()
        self.zones = loaded_zones
        self.zones_file = path
        self.selected_zone_idx = None
        self._refresh_zone_list()
        self.render()
        self.status_label.config(text=f"Loaded {len(self.zones)} zone(s) from: {path}")

    # =====================================================================
    # Export as Python code
    # =====================================================================
    def _generate_python_code(self):
        video_name = Path(self.video_path).name if self.video_path else "(no video loaded)"
        lines = []
        lines.append('"""')
        lines.append("Zone definitions exported from PK Studio - Zone Editor")
        lines.append(f"Video: {video_name}  ({self.orig_w}x{self.orig_h})")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append('"""')
        lines.append("")
        lines.append(f"FRAME_WIDTH = {self.orig_w}")
        lines.append(f"FRAME_HEIGHT = {self.orig_h}")
        lines.append("")
        lines.append("ZONES = [")
        for z in self.zones:
            area = z.get("area_px", self._polygon_area(z["points"]))
            pts_tuple = ", ".join(f"({x}, {y})" for x, y in z["points"])
            lines.append("    {")
            lines.append(f'        "id": {z["id"]!r},')
            lines.append(f'        "name": {z["name"]!r},')
            lines.append(f'        "points": [{pts_tuple}],')
            lines.append(f'        "area_px": {area:.2f},')
            lines.append("    },")
        lines.append("]")
        lines.append("")
        lines.append("")
        lines.append("def point_in_zone(x, y, zone):")
        lines.append('    """Return True if point (x, y) — e.g. a bbox centroid — falls')
        lines.append("    inside zone['points']. Coordinates must be in the same pixel")
        lines.append("    space as FRAME_WIDTH x FRAME_HEIGHT (same video resolution).")
        lines.append('    """')
        lines.append("    import cv2")
        lines.append("    import numpy as np")
        lines.append('    pts = np.array(zone["points"], dtype=np.int32)')
        lines.append("    return cv2.pointPolygonTest(pts, (float(x), float(y)), False) >= 0")
        lines.append("")
        lines.append("")
        lines.append("def zone_for_point(x, y, zones=ZONES):")
        lines.append('    """Return the name of the first zone containing (x, y), or None.')
        lines.append("    Use this per-frame with each tracked object's bbox centroid to")
        lines.append("    know which zone (if any) it is currently in — the starting point")
        lines.append('    for behavior detection (entry/exit, dwell time, PET, etc.).')
        lines.append('    """')
        lines.append("    for zone in zones:")
        lines.append("        if point_in_zone(x, y, zone):")
        lines.append('            return zone["name"]')
        lines.append("    return None")
        lines.append("")
        return "\n".join(lines)

    def _show_code_preview(self):
        if not self.zones:
            messagebox.showwarning("Nothing to export", "No zones have been drawn yet.")
            return

        code = self._generate_python_code()

        win = tk.Toplevel(self)
        win.title("Zone code (Python)")
        win.geometry("760x600")

        text = ScrolledText(win, wrap="none", font=("Consolas", 10))
        text.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        text.insert("1.0", code)
        text.config(state="normal")  # keep editable/selectable for easy copying

        btn_row = ttk.Frame(win)
        btn_row.pack(fill="x", padx=8, pady=(0, 8))

        def copy_to_clipboard():
            win.clipboard_clear()
            win.clipboard_append(code)
            status.config(text="Copied to clipboard.")

        def save_as_py():
            default_name = f"{Path(self.video_path).stem}_zones.py" if self.video_path else "zones.py"
            path = filedialog.asksaveasfilename(
                title="Save zone code",
                defaultextension=".py",
                initialfile=default_name,
                filetypes=[("Python file", "*.py"), ("All files", "*.*")],
                parent=win,
            )
            if not path:
                return
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            status.config(text=f"Saved to: {path}")

        ttk.Button(btn_row, text="📋 Copy to Clipboard", command=copy_to_clipboard).pack(side="left", padx=(0, 4))
        ttk.Button(btn_row, text="💾 Save as .py", style="Secondary.TButton", command=save_as_py).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Close", style="Secondary.TButton", command=win.destroy).pack(side="right")

        status = ttk.Label(win, text=f"{len(self.zones)} zone(s) — ready to copy or save.", foreground=COLORS["text_muted"])
        status.pack(fill="x", padx=8, pady=(0, 8))

    # =====================================================================
    # Render
    # =====================================================================
    def _get_font(self, size):
        """Cached, Thai-capable TrueType font (cv2.putText can't render Thai
        glyphs — it silently prints '???' — so all zone-label text is drawn
        with PIL/ImageFont instead)."""
        size = max(8, int(size))
        font = self._font_cache.get(size)
        if font is not None:
            return font
        for path in FONT_CANDIDATES:
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        self._font_cache[size] = font
        return font

    def render(self):
        if self.cv_frame is None:
            self.canvas.delete("all")
            return

        disp = self.cv_frame.copy()

        for idx, zone in enumerate(self.zones):
            pts = np.array(zone["points"], dtype=np.int32)
            color = tuple(zone.get("color_bgr") or ZONE_PALETTE_BGR[idx % len(ZONE_PALETTE_BGR)])
            is_sel = (idx == self.selected_zone_idx)

            if is_sel:
                overlay = disp.copy()
                cv2.fillPoly(overlay, [pts], color)
                cv2.addWeighted(overlay, 0.20, disp, 0.80, 0, disp)

            cv2.polylines(disp, [pts], isClosed=True, color=color, thickness=3 if is_sel else 2)
            for (px, py) in zone["points"]:
                if is_sel:
                    # Bigger white-ringed handles on the selected zone —
                    # a visual cue that these points can be dragged.
                    cv2.circle(disp, (px, py), 7, (255, 255, 255), -1)
                    cv2.circle(disp, (px, py), 7, color, 2)
                else:
                    cv2.circle(disp, (px, py), 4, color, -1)

        if self.current_points:
            draw_color = (0, 255, 255)  # bright yellow — the polygon currently being drawn
            for i in range(len(self.current_points) - 1):
                cv2.line(disp, self.current_points[i], self.current_points[i + 1], draw_color, 2)
            if self.mouse_orig_pos is not None:
                cv2.line(disp, self.current_points[-1], self.mouse_orig_pos, draw_color, 1)
            for i, (px, py) in enumerate(self.current_points):
                radius = 6 if i == 0 else 4
                cv2.circle(disp, (px, py), radius, draw_color, -1)

        cw = self.canvas.winfo_width() or 800
        ch = self.canvas.winfo_height() or 600

        scale_base = min(cw / self.orig_w, ch / self.orig_h)
        self.render_scale = scale_base * self.zoom_level

        new_w = max(1, int(self.orig_w * self.render_scale))
        new_h = max(1, int(self.orig_h * self.render_scale))

        resized = cv2.resize(disp, (new_w, new_h), interpolation=cv2.INTER_AREA)
        rgb_img = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)

        # Name/type labels are drawn last, on the already-resized image, via
        # PIL so Thai (and any other Unicode) zone names render correctly —
        # cv2.putText only supports Latin-1 and shows "???" for Thai text.
        show_all = self.show_all_labels.get()
        if show_all and self.zones:
            draw = ImageDraw.Draw(pil_img)
            font_size = max(10, min(26, int(15 * self.render_scale)))
            font = self._get_font(font_size)
            for idx, zone in enumerate(self.zones):
                if not zone.get("show_label", True):
                    continue
                color_bgr = tuple(zone.get("color_bgr") or ZONE_PALETTE_BGR[idx % len(ZONE_PALETTE_BGR)])
                color_rgb = color_bgr[::-1]
                pts = zone["points"]
                cx = int(sum(p[0] for p in pts) / len(pts) * self.render_scale)
                cy = int(sum(p[1] for p in pts) / len(pts) * self.render_scale)

                label = f" {zone['name']} "
                l, t, r, b = draw.textbbox((0, 0), label, font=font)
                tw, th = r - l, b - t
                rect = (cx - tw // 2 - 3, cy - th - 6, cx + tw // 2 + 3, cy + 6)
                draw.rectangle(rect, fill=color_rgb)
                text_color = (0, 0, 0) if sum(color_rgb) > 430 else (255, 255, 255)
                draw.text((cx - tw // 2 - l, cy - th - 3 - t), label, font=font, fill=text_color)

        self.tk_image = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")

        self.offset_x = (cw - new_w) // 2 + self.pan_x
        self.offset_y = (ch - new_h) // 2 + self.pan_y

        self.canvas.create_image(self.offset_x + new_w // 2, self.offset_y + new_h // 2, image=self.tk_image, anchor="center")
