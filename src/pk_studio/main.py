"""PK Studio - Dataset Studio application shell."""

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from pk_studio.theme import COLORS, apply_global_theme
from pk_studio.ui.tabs.tab_data import DataTab
from pk_studio.ui.tabs.tab_autolabeler import AutoLabelerTab
from pk_studio.ui.tabs.tab_curator_splitter import CuratorSplitterTab
from pk_studio.ui.tabs.tab_analytics import AnalyticsTab
from pk_studio.ui.tabs.tab_zone_editor import ZoneEditorTab
from pk_studio.ui.tabs.tab_other import OtherTab


class PKStudioApp:
    """Modern shell for the Dataset → Label → Curate → Analyze workflow."""

    NAV_ITEMS = [
        ("data", "▣", "Data", "Import videos and build image datasets"),
        ("autolabeler", "◇", "Label", "Annotate and review objects"),
        ("curator_splitter", "✂", "Curate", "Select, balance and split data"),
        ("analytics", "◫", "Analytics", "Understand dataset quality and shape"),
        ("zone_editor", "⬡", "Zone", "Draw polygon zones on video frames"),
        ("other", "⋯", "Other", "Extra video utilities"),
    ]

    PAGE_INFO = {
        "data": ("Data", "Bring your raw media into a clean image dataset."),
        "autolabeler": ("Label", "Create, review and refine bounding-box annotations."),
        "curator_splitter": ("Curate", "Select the most useful samples and prepare splits."),
        "analytics": ("Analytics", "See the distribution and structure of your dataset."),
        "zone_editor": ("Zone", "Draw polygon zones on a video frame for zone-based detection."),
        "other": ("Other", "Extra video utilities that sit outside the main dataset workflow."),
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PK Studio — Dataset Studio")
        self.root.geometry("1440x900")
        self.root.minsize(1180, 720)

        try:
            icon_path = Path(__file__).resolve().parents[2] / "assets" / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

        self.style = apply_global_theme(self.root)
        self._build_ui()
        self._bind_shortcuts()

    def _build_ui(self) -> None:
        self.sidebar = tk.Frame(self.root, bg=COLORS["sidebar_bg"], width=224)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Frame(self.root, bg=COLORS["sidebar_border"], width=1).pack(side="left", fill="y")

        self._build_sidebar()

        self.shell = tk.Frame(self.root, bg=COLORS["main_bg"])
        self.shell.pack(side="left", fill="both", expand=True)

        self._build_header()

        self.workspace = tk.Frame(self.shell, bg=COLORS["main_bg"])
        self.workspace.pack(fill="both", expand=True)

        self.tabs = {
            "data": DataTab(self.workspace),
            "autolabeler": AutoLabelerTab(self.workspace),
            "curator_splitter": CuratorSplitterTab(self.workspace),
            "analytics": AnalyticsTab(self.workspace),
            "zone_editor": ZoneEditorTab(self.workspace),
            "other": OtherTab(self.workspace),
        }

        self._build_footer()
        self.switch_tab("data")

    def _build_sidebar(self) -> None:
        brand = tk.Frame(self.sidebar, bg=COLORS["sidebar_bg"], height=92)
        brand.pack(fill="x")
        brand.pack_propagate(False)

        logo = tk.Frame(brand, bg=COLORS["accent"], width=42, height=42)
        logo.place(x=22, y=24)
        logo.pack_propagate(False)
        tk.Label(
            logo, text="PK", bg=COLORS["accent"], fg="#FFFFFF",
            font=("Segoe UI", 12, "bold"),
        ).place(relx=.5, rely=.5, anchor="center")

        tk.Label(
            brand, text="PK Studio", bg=COLORS["sidebar_bg"], fg=COLORS["sidebar_text"],
            font=("Segoe UI", 14, "bold"),
        ).place(x=76, y=24)
        tk.Label(
            brand, text="DATASET STUDIO", bg=COLORS["sidebar_bg"], fg=COLORS["sidebar_muted"],
            font=("Segoe UI", 7, "bold"),
        ).place(x=77, y=49)

        tk.Label(
            self.sidebar, text="WORKSPACE", bg=COLORS["sidebar_bg"], fg=COLORS["sidebar_muted"],
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill="x", padx=20, pady=(9, 8))

        self.nav_buttons = {}
        for tab_id, icon, label, hint in self.NAV_ITEMS:
            self._make_nav_item(tab_id, icon, label, hint)

        tk.Frame(self.sidebar, bg=COLORS["sidebar_border"], height=1).pack(fill="x", padx=18, pady=18)

        tk.Label(
            self.sidebar, text="PIPELINE", bg=COLORS["sidebar_bg"], fg=COLORS["sidebar_muted"],
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill="x", padx=20, pady=(0, 8))

        for step, text in [("01", "Collect"), ("02", "Label"), ("03", "Curate"), ("04", "Analyze"), ("05", "Export")]:
            row = tk.Frame(self.sidebar, bg=COLORS["sidebar_bg"], height=28)
            row.pack(fill="x", padx=20, pady=1)
            tk.Label(row, text=step, width=3, bg=COLORS["sidebar_bg"], fg=COLORS["accent"],
                     font=("Consolas", 8, "bold"), anchor="w").pack(side="left")
            tk.Label(row, text=text, bg=COLORS["sidebar_bg"], fg=COLORS["sidebar_muted"],
                     font=("Segoe UI", 8)).pack(side="left")

        spacer = tk.Frame(self.sidebar, bg=COLORS["sidebar_bg"])
        spacer.pack(fill="both", expand=True)
        tk.Label(
            spacer, text="Dataset Preparation\nfor Computer Vision", bg=COLORS["sidebar_bg"],
            fg="#72798C", justify="left", anchor="w", font=("Segoe UI", 8),
        ).pack(side="bottom", fill="x", padx=20, pady=(0, 18))

    def _make_nav_item(self, tab_id: str, icon: str, label: str, hint: str) -> None:
        frame = tk.Frame(self.sidebar, bg=COLORS["sidebar_bg"], height=62, cursor="hand2")
        frame.pack(fill="x", padx=12, pady=3)
        frame.pack_propagate(False)

        accent = tk.Frame(frame, bg=COLORS["sidebar_bg"], width=3)
        accent.pack(side="left", fill="y")

        icon_box = tk.Frame(frame, bg=COLORS["sidebar_bg"], width=40)
        icon_box.pack(side="left", fill="y")
        icon_box.pack_propagate(False)
        icon_lbl = tk.Label(icon_box, text=icon, bg=COLORS["sidebar_bg"], fg=COLORS["sidebar_icon"],
                            font=("Segoe UI Symbol", 19))
        icon_lbl.place(relx=.5, rely=.5, anchor="center")

        text_box = tk.Frame(frame, bg=COLORS["sidebar_bg"])
        text_box.pack(side="left", fill="both", expand=True, padx=(5, 6))
        text_lbl = tk.Label(text_box, text=label, bg=COLORS["sidebar_bg"], fg=COLORS["sidebar_text"],
                            font=("Segoe UI", 10, "bold"), anchor="w")
        text_lbl.pack(anchor="w", pady=(12, 0))
        hint_lbl = tk.Label(text_box, text=hint, bg=COLORS["sidebar_bg"], fg=COLORS["sidebar_muted"],
                            font=("Segoe UI", 7), anchor="w")
        hint_lbl.pack(anchor="w", pady=(1, 0))

        widgets = (frame, accent, icon_box, icon_lbl, text_box, text_lbl, hint_lbl)
        for widget in widgets:
            widget.bind("<Button-1>", lambda _e, tid=tab_id: self.switch_tab(tid))
            widget.bind("<Enter>", lambda _e, tid=tab_id: self._nav_hover(tid, True))
            widget.bind("<Leave>", lambda _e, tid=tab_id: self._nav_hover(tid, False))

        self.nav_buttons[tab_id] = (frame, accent, icon_box, icon_lbl, text_box, text_lbl, hint_lbl)

    def _nav_hover(self, tab_id: str, hover: bool) -> None:
        if tab_id == getattr(self, "selected_tab_id", None):
            return
        bg = COLORS["sidebar_hover_bg"] if hover else COLORS["sidebar_bg"]
        for widget in self.nav_buttons[tab_id]:
            if isinstance(widget, tk.Frame) or isinstance(widget, tk.Label):
                widget.configure(bg=bg)

    def _build_header(self) -> None:
        self.header = tk.Frame(self.shell, bg=COLORS["card_bg"], height=82,
                               highlightbackground=COLORS["border"], highlightthickness=1)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        left = tk.Frame(self.header, bg=COLORS["card_bg"])
        left.pack(side="left", fill="y", padx=28)

        self.page_title = tk.Label(left, text="", bg=COLORS["card_bg"], fg=COLORS["text_dark"],
                                   font=("Segoe UI", 17, "bold"))
        self.page_title.pack(anchor="w", pady=(15, 0))
        self.page_subtitle = tk.Label(left, text="", bg=COLORS["card_bg"], fg=COLORS["text_muted"],
                                      font=("Segoe UI", 8))
        self.page_subtitle.pack(anchor="w", pady=(1, 0))

        right = tk.Frame(self.header, bg=COLORS["card_bg"])
        right.pack(side="right", fill="y", padx=22)

        chip = tk.Frame(right, bg=COLORS["success_soft"], padx=10, pady=5)
        chip.pack(side="right", pady=23)
        tk.Label(chip, text="●  Dataset workspace", bg=COLORS["success_soft"], fg=COLORS["success"],
                 font=("Segoe UI", 8, "bold")).pack()

    def _build_footer(self) -> None:
        footer = tk.Frame(self.shell, bg=COLORS["card_bg"], height=30,
                          highlightbackground=COLORS["border"], highlightthickness=1)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Label(footer, text="PK Studio", bg=COLORS["card_bg"], fg=COLORS["text_subtle"],
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(18, 6))
        tk.Label(footer, text="by Pongsakorn Klaywun", bg=COLORS["card_bg"], fg=COLORS["text_subtle"],
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(footer, text="DATA → LABEL → CURATE → ANALYTICS → EXPORT", bg=COLORS["card_bg"],
                 fg=COLORS["text_subtle"], font=("Segoe UI", 8)).pack(side="right", padx=18)

    def _bind_shortcuts(self) -> None:
        for index, (tab_id, *_rest) in enumerate(self.NAV_ITEMS, start=1):
            self.root.bind(f"<Control-Key-{index}>", lambda _e, tid=tab_id: self.switch_tab(tid))

    def switch_tab(self, selected_tab_id: str) -> None:
        if selected_tab_id not in self.tabs:
            return
        self.selected_tab_id = selected_tab_id

        for tab_frame in self.tabs.values():
            tab_frame.pack_forget()
        self.tabs[selected_tab_id].pack(fill="both", expand=True)

        title, subtitle = self.PAGE_INFO[selected_tab_id]
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)

        for tab_id, parts in self.nav_buttons.items():
            frame, accent, icon_box, icon_lbl, text_box, text_lbl, hint_lbl = parts
            active = tab_id == selected_tab_id
            bg = COLORS["sidebar_active_bg"] if active else COLORS["sidebar_bg"]
            accent_bg = COLORS["accent"] if active else COLORS["sidebar_bg"]
            frame.configure(bg=bg)
            accent.configure(bg=accent_bg)
            for widget in (icon_box, icon_lbl, text_box, text_lbl, hint_lbl):
                widget.configure(bg=bg)
            icon_lbl.configure(fg=COLORS["accent"] if active else COLORS["sidebar_icon"])
            text_lbl.configure(fg=COLORS["sidebar_text"] if active else COLORS["sidebar_text"])
            hint_lbl.configure(fg="#B7BDCC" if active else COLORS["sidebar_muted"])


if __name__ == "__main__":
    root = tk.Tk()
    app = PKStudioApp(root)
    root.mainloop()
