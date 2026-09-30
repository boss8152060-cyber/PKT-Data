# PK Studio

Desktop dataset-preparation workspace for collecting frames, labeling, curating, analyzing, splitting, and exporting computer-vision datasets. Training, evaluation, and prediction remain in VS Code / the project's existing scripts.

## Project layout

```text
PK Studio/
├── main.py                 # Simple entry point
├── install_and_run.bat     # First-time installer + launcher
├── run_app.bat             # Normal launcher
├── setup.ps1               # Windows dependency setup
├── README.md
├── .gitignore
├── assets/
│   └── icon.ico            # App icon
├── docs/
│   └── CHANGELOG.md        # Single project history
├── src/
│   └── pk_studio/
│       ├── main.py         # Application shell / navigation
│       ├── theme.py        # Shared UI theme
│       ├── core/           # UI-independent business logic
│       ├── ui/
│       │   └── tabs/       # Screen-level Tkinter UI
│       └── tools/          # Standalone / embedded utilities
└── tests/                  # Automated tests
```

## Product workflow

```text
DATA → LABEL → CURATE → ANALYTICS → SPLIT / EXPORT → VS Code → TRAIN / EVAL / PREDICT
```

PK Studio intentionally focuses on dataset preparation.

## UI

- Modern light workspace with dark navigation rail.
- Six screens: Data, Label, Curate, Analytics, Zone, Other.
- Keyboard shortcuts: Ctrl+1 through Ctrl+6.
- Shared visual tokens live in `src/pk_studio/theme.py`.

## Design rules

- `core/` does not depend on Tkinter UI.
- `ui/tabs/` owns screen-level UI and calls reusable core services.
- `tools/` contains standalone utilities such as frame extraction.
- `assets/` contains non-code application assets.
- `docs/` contains project documentation.
- Python caches and test caches are never shipped.

## Run

Double-click `run_app.bat`, or run `python main.py`.

## Development

```text
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

## Auto-Label without a model

Click Auto-Label or Batch with no YOLO model loaded and choose **No**. PK Studio then crops the boxes you already drew and searches new images for similar regions. Best for fixed cameras and similar-looking objects; always review the results.
