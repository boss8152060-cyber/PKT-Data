"""PK Studio visual theme.

Centralized design tokens so the shell and all tabs can share the same visual
language without scattering colors throughout the application.
"""

from tkinter import ttk

COLORS = {
    # App shell
    "sidebar_bg": "#111111",
    "sidebar_hover_bg": "#262626",
    "sidebar_active_bg": "#333333",
    "sidebar_border": "#3A3A3A",
    "sidebar_text": "#FFFFFF",
    "sidebar_muted": "#A3A3A3",
    "sidebar_icon": "#D4D4D4",

    # Workspace
    "main_bg": "#F5F5F5",
    "card_bg": "#FFFFFF",
    "surface_alt": "#EBEBEB",
    "border": "#D8D8D8",
    "border_strong": "#BDBDBD",

    # Typography
    "text_dark": "#111111",
    "text_muted": "#666666",
    "text_subtle": "#909090",

    # Brand / semantic
    "accent": "#202020",
    "accent_hover": "#000000",
    "accent_soft": "#E5E5E5",
    "success": "#404040",
    "success_soft": "#EAEAEA",
    "warning": "#555555",
    "warning_soft": "#EDEDED",
    "danger": "#222222",
    "danger_soft": "#E7E7E7",
}


def apply_global_theme(root) -> ttk.Style:
    """Apply the shared PK Studio light workspace theme."""
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(bg=COLORS["main_bg"])

    style.configure(
        ".",
        background=COLORS["main_bg"],
        foreground=COLORS["text_dark"],
        font=("Segoe UI", 9),
    )
    style.configure("TFrame", background=COLORS["main_bg"])
    style.configure("TLabel", background=COLORS["main_bg"], foreground=COLORS["text_dark"])

    style.configure(
        "TLabelframe",
        background=COLORS["card_bg"],
        foreground=COLORS["text_dark"],
        bordercolor=COLORS["border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=COLORS["card_bg"],
        foreground=COLORS["text_dark"],
        font=("Segoe UI", 10, "bold"),
    )

    style.configure(
        "TButton",
        background=COLORS["accent"],
        foreground="#FFFFFF",
        borderwidth=0,
        relief="flat",
        padding=(13, 7),
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "TButton",
        background=[
            ("active", COLORS["accent_hover"]),
            ("pressed", COLORS["accent_hover"]),
            ("disabled", "#C9CDDA"),
        ],
        foreground=[("disabled", "#FFFFFF")],
    )

    style.configure(
        "Secondary.TButton",
        background=COLORS["card_bg"],
        foreground=COLORS["text_dark"],
        bordercolor=COLORS["border_strong"],
        borderwidth=1,
        padding=(12, 6),
    )
    style.map("Secondary.TButton", background=[("active", COLORS["surface_alt"])])

    style.configure(
        "TEntry",
        fieldbackground=COLORS["card_bg"],
        foreground=COLORS["text_dark"],
        bordercolor=COLORS["border_strong"],
        padding=6,
    )
    style.configure("TCombobox", fieldbackground=COLORS["card_bg"], padding=5)

    style.configure("TNotebook", background=COLORS["main_bg"], borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=COLORS["main_bg"],
        foreground=COLORS["text_muted"],
        padding=(14, 8),
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["card_bg"])],
        foreground=[("selected", COLORS["accent"])],
    )

    style.configure(
        "Treeview",
        background=COLORS["card_bg"],
        fieldbackground=COLORS["card_bg"],
        foreground=COLORS["text_dark"],
        bordercolor=COLORS["border"],
        rowheight=28,
        font=("Segoe UI", 9),
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["surface_alt"],
        foreground=COLORS["text_muted"],
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        padding=(8, 6),
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["accent"])],
        foreground=[("selected", "#FFFFFF")],
    )

    style.configure("TPanedwindow", background=COLORS["main_bg"])
    style.configure(
        "TProgressbar",
        background=COLORS["accent"],
        troughcolor=COLORS["border"],
        borderwidth=0,
        thickness=8,
    )
    style.configure("TCheckbutton", background=COLORS["main_bg"], foreground=COLORS["text_dark"])
    style.configure("TRadiobutton", background=COLORS["main_bg"], foreground=COLORS["text_dark"])
    style.configure("TSeparator", background=COLORS["border"])

    return style
