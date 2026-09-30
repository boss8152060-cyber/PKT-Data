# Changelog

## Unreleased
- Fixed `build_yolo_dataset` overwriting images that share a file name in different sub-folders.
- Fixed `copy_background=False` copying unlabeled images anyway.
- `data.yaml` no longer points `val` at an empty split.
- `DatasetScanner.scan` no longer crashes on unreadable labels; validates class ids and 0..1 coordinates.
- Label, class-list, project and data.yaml writes are now atomic; the Curate tab writes `data.yaml` via PyYAML.
- A failing UI callback is no longer reported as a job error.
- Curate tab: exported images/labels no longer overwrite files that share a name across sub-folders (shared `flat_name`).
- Fixed background-job callbacks: `ui_call=self.after` raised TclError, so on_done/on_error never reached the UI. Callbacks now go through a thread-safe `UiQueue` drained on the Tk main thread.
- `greedy_select` updates diversity incrementally instead of recomputing all similarities; stops when no candidate is relevant.
- `setup.ps1` verifies the Python installer's Authenticode signature before running it.
- Added requirements files and tests for the builder, scanner, atomic writes and jobs.

## 1.19.0
- Standardized the entire application source, documentation, and user-facing messages to English only.
- Removed remaining Thai text from dialogs, logs, labels, comments, and documentation.
- Kept the monochrome UI direction: white, black, and grayscale surfaces with black typography.
- Preserved colorful Class / Bounding Box colors.

## 1.18.9
- Removed video playback / preview UI from the DATA workflow.
- DATA is now focused strictly on video-to-frame extraction.
- Removed per-video preview-frame decoding from the queue and estimate workflow.
- Removed clip-trimming controls from DATA; trimming remains available under Other.
- Standardized visible application UI text to English.


## 1.18.7
- Simplified the DATA workflow so it contains only video-to-frame extraction.
- Moved video trimming, video merging, and images-to-video into a dedicated **Other** tab.
- Added the Other tab to the main navigation without changing the underlying media-processing logic.
- DATA no longer presents unrelated video utilities inside its primary workspace.

## 1.18.4
- Refined visual system to strict monochrome grayscale for the application UI.
- Kept Class / Bounding Box visuals intentionally colorful with a high-saturation palette.
- Class label tags now use the class color for stronger visual identification.


- Added creator credit in the application footer: “by Pongsakorn Klaywun”.
- Preserved the monochrome-inspired black / white / gray visual direction with a restrained accent color.

---

# PK Studio v1.18.0 — UX/UI Refresh

- Redesigned the application shell with a modern dark navigation rail and light workspace.
- Added clear page title/subtitle hierarchy and dataset-workspace status indicator.
- Added a visual workflow guide in the sidebar: Collect → Label → Curate → Analyze → Export.
- Added keyboard navigation with Ctrl+1 through Ctrl+4.
- Added shared design tokens for surfaces, borders, typography, accent, and semantic states.
- Improved button, entry, combobox, treeview, notebook, and progress-bar styling.
- Kept the existing Data / Label / Curate / Analytics functionality intact.

---

# PK Studio v1.17.0 — Remove Dataset QA & Duplicate Scan

- Removed Dataset QA from Analytics UI and core dataset checks.
- Removed Duplicate Scan and the duplicate-detection core module.
- Removed QA-to-Labeler callback bridge and related test coverage.
- Analytics now focuses on dataset distribution, object counts, box positions, and image dimensions.

---

# PK Studio v1.15.0 — Project Structure Cleanup

- Reorganized application code under `src/pk_studio/`.
- Separated UI (`ui/tabs`), reusable core logic (`core`), and tools (`tools`).
- Moved app assets to `assets/` and consolidated version history into `docs/CHANGELOG.md`.
- Added a root launcher `main.py` so the app is still started the same way.
- Removed Python/test cache files from the release package.
- Updated imports and resource paths without changing application behavior.

---

Project history consolidated from v1.1 through the current release.

# PK Studio v1.14.2

## Training Studio UI cleanup
- Removed the separate Current Run / Current Epoch live panel.
- Removed the Training Dashboard and its plotting controls.
- Removed the outer Training-page vertical scrollbar.
- Epoch History is now the only scrolling area in the Training workspace.
- Kept live `results.csv` polling so the Epoch History table continues to update while training.
- Kept Run History with configured/completed epochs, best epoch, best mAP50-95, and status.

---

# PK Studio v1.14.1

## Training Studio UI refinement

- Combined **Current Run / Current Epoch**, **Epoch History**, and **Training Dashboard** into one continuous Training workspace.
- Removed the need to switch between Epoch History and Dashboard tabs.
- Added a single vertical scrollbar for the Training workspace so the user can scroll down through the complete Run view.
- Kept a dedicated vertical/horizontal scrollbar on the Epoch History table for large numbers of Epochs.
- Current Run remains visible at the top of the same scrollable flow.
- Run History remains visible on the right for quick comparison with previous Runs.
- Preserved live Epoch telemetry and results.csv polling from v1.14.

## Verification

- `python -m py_compile tabs/tab_training.py` passed.
- `python -m pytest -q` passed: 15 tests.

---

# PK Studio v1.14

## Training Studio — Live Run / Epoch Monitor

-  Training Studio  Local YOLO26 training script:
  - `yolo26m.pt`
  - 300 epochs
  - image size 640
  - batch 32
  - workers 12
  - cache disk
  - patience 20
  - project `models`
-  Mode: `auto`, `new`, `continue_from_run`
-  Current Run / Current Epoch  live
-  GPU memory, box loss, cls loss, l1/dfl loss, instances, image size
-  Precision, Recall, mAP50  mAP50-95  Epoch 
-  Epoch History  Epoch  Run
-  Run History  Configured Epochs / Completed Epochs / Best Epoch / Best mAP50-95
-  `results.csv`  Train 
-  STOP  JobManager  Stopping / Stopped
-  auto-resume  `IN_PROGRESS.flag` + `weights/last.pt`
-  best.pt / last.pt  Model Manager artifacts

---

# PK Studio v1.13

## Inference Studio
- Added `core/inference.py` for background-safe YOLO image inference.
- Added Predict tab for single-image or folder inference.
- Export annotated images and YOLO-format prediction labels.
- Added confidence / IoU / image size / device controls.
- Added cancellation support through JobManager.
- Added `inference_summary.json` for each run.
- Added regression tests for source discovery and configuration validation.

---

# PK Studio v1.12

## Evaluation Studio
- Added YOLO validation/evaluation workflow for train/val/test splits.
- Reports metrics from Ultralytics `results_dict`.
- Saves evaluation summary JSON and discovers standard curve/confusion-matrix plots.
- Runs evaluation through JobManager with progress and cancellation checks.
- Added Evaluation tab to the main navigation.
- Added configuration validation tests.

---


# v1.11
## Training Studio — Prepare Dataset
-  `core/dataset_builder.py`  PK Studio dataset  flat  train/valid/test
-  `data.yaml`  `classes.txt` 
-  deterministic multilabel-aware split
-  `🧰 Prepare Dataset`  Training Studio
-  Dataset  Dataset  Train 
-  regression test

---

# PK Studio v1.10

## Label — Save As Dataset

 workflow  Label  Dataset :

```text
MyDataset/
├── images/       # 
├── labels/       # YOLO .txt 
└── classes.txt   #  class  Class Registry 
```

### 
-  `💾 Save As...`  Label tab
-  Dataset 
-  `images/`  `labels/` 
-  Dataset Original `images/`
-  label Original `labels/`
-  annotation  memory 
- / `classes.txt`  root  Dataset
-  `.pk_annotation_meta.json`
-  overwrite 
-  Save  Dataset   `images/`/`labels/` 

## Compatibility
- YOLO label IDs  0-based  disk
- UI class numbering  1-based
- Class Registry  reorder class Original

---

# PK Studio v1.9.1

## Bug Fix
- Fixed startup crash in `AnalyticsTab` caused by the Duplicate Scan button referencing a missing `_run_duplicates` method.
- Restored Duplicate Scan UI using the existing `DatasetQA.duplicate_scan()` bridge.
- Duplicate Scan remains report-only and does not modify dataset files.
- Added regression coverage for the Dataset QA duplicate-scan bridge.

## Tests
- 11/11 tests passed.
- Existing Pillow `Image.getdata` deprecation warning remains and does not affect test results.

---

# PK Studio v1.9

## Training Dashboard
- Added interactive Matplotlib dashboard for training runs.
- Four charts: Loss, mAP50-95, Precision, Recall.
- Supports plotting up to four selected runs for visual comparison.
- Added Matplotlib navigation toolbar for pan/zoom/save.
- Added Best Run detection based on peak mAP50-95.
- Added reusable `TrainingRun` and `scan_training_runs()` helpers.
- Training history is read from Ultralytics `results.csv` without requiring a live training session.
- Existing Training Studio, Model Manager, Auto-Labeler handoff, and JobManager workflow are preserved.

## Tests
- 10/10 tests passed.
- Existing Pillow deprecation warning remains in duplicate detection and does not affect test results.

---

# PK Studio v1.8 — Training Metrics & Model Manager

- Added Training Metrics table from `results.csv`.
- Added Model Manager to discover `best.pt` / `last.pt` artifacts from training runs.
- Added one-click `Use Selected in Auto-Labeler` workflow.
- Added Auto-Labeler model loading API for cross-tab integration.
- Training configuration and latest run metadata are persisted into `.pkstudio/project.json` when possible.
- Preserved background JobManager training and existing dataset/class architecture.

---

# PK Studio v1.7 — Training Studio

- Added Training Studio tab to the main application.
- Added YOLO training configuration: model, dataset, epochs, image size, batch, device, workers, patience, output project/name.
- Added automatic data.yaml generation for standard YOLO train/val layouts when a dataset YAML is not present.
- Added background training through the shared JobManager so the Tk UI remains responsive.
- Added epoch progress and cooperative stop support through the Ultralytics epoch callback.
- Added final run directory, best.pt, last.pt and results.csv metric summary.
- Preserved the existing class ordering concept: alphabetical default, explicit reorder retained, YOLO IDs remain 0-based.
- Training is additive: existing Data, Label, Curate and Analytics workflows remain available.

---

PK Studio v1.6 — Dataset Health & QA Dashboard

- Added interactive Dataset QA dashboard with issue list and severity.
- Double-click / Open Selected in Labeler can jump from QA findings to Auto-Labeler.
- Added QA report export to TXT.
- Added callback bridge from Analytics to Auto-Labeler.
- Fixed DatasetQA.duplicate_scan() to use scanned image paths correctly.
- Preserved existing class-order behavior: alphabetical default, explicit reorder retained, YOLO ids remain 0-based.
- Non-destructive QA: no dataset files are modified by scanning.

---

# PK Studio v1.5

## Dataset Intelligence
- Added exact duplicate detection using SHA-256.
- Added near-duplicate detection using perceptual dHash with bucketed comparison.
- Added Duplicate Scan button to Analytics / Dataset QA.
- Added deterministic duplicate reports and hashing error reporting.
- Extended DatasetQA with `duplicate_scan()`.

## Safety / compatibility
- Existing class ordering and Class Registry behavior are unchanged.
- No destructive cleanup is performed by Duplicate Scan; it is report-only.
- Near-duplicate detection is intentionally conservative and should be reviewed before deleting files.

---

# PK Studio v1.4 — Smart Dataset Intelligence

## 

### Smart Curator
-  `core/smart_curator.py`  engine  Tkinter/PyTorch
-  **class rarity**  inverse frequency
-  rarity bonus 
-  heuristic Original: diversity + difficulty + relevance
-  multi-label coverage bonus 
-  tie-break  deterministic 

### Curator UI
- Curator Original embedding  difficulty  YOLO Original
-  scoring  rarity-aware selection  logic Original
-  Class Registry /  class  Roboflow

### Core architecture
- Smart selection logic  `core/`  GUI
-  unit test  rare-class prioritization

## Validation
- `py_compile`: PASS
- `pytest`: 5/5 PASS

##  Class ID
- Default order: alphabetical (Roboflow-style)
- UI numbering: 1-based
- YOLO label IDs: 0-based
- User reorder remains supported and must remap dataset labels

---

# PK Studio v1.3 — Dataset Intelligence & Unified Jobs

## 

### Curator / Splitter
-  background execution  JobManager 
- 
-  DatasetScanner   logic 
- Splitter  deterministic greedy iterative multilabel split  class 
-  nested paths  duplicate stem

### Dataset QA
:
- missing labels
- empty labels
- orphan labels
- corrupt images
- invalid dimensions
- invalid bbox
- bbox class id out of range
- tiny boxes
- huge boxes
- duplicate filenames
- parse errors

### Tests
- 4 core tests 
- py_compile  Python module

## Original
- Class default  A-Z  Roboflow
- UI  1-based
- YOLO  disk  0-based
-  Move Up / Move Down  remap labels  dataset
- Class Registry   sort  classes.txt

---

# PK Studio v1.2 — Core Job & Dataset Foundation

## 

### 1. Shared JobManager
-  `core/job_manager.py`  background job 
-  status: pending / running / cancelling / cancelled / done / error
-  cancellation  `threading.Event`
-  dispatch callback  Tkinter main loop  `widget.after`
-  `active()`, `cancel_all()`  cleanup  finished jobs

### 2. Auto-Label  JobManager
- Auto-Label Current  UI  YOLO inference
- Batch Auto-Label  job 
-  cancellation state
-  error   error 
-  10 

### 3. DatasetScanner 
- scanner  relative path  key  image stem 
-  `cam1/frame.jpg`  `cam2/frame.jpg` 
-  nested folders  image/label roots

### 4. Class Registry / Class Order
-  default  alphabetical  workflow  Roboflow
-  `classes.txt`  
- Move Up / Move Down  YOLO ID  remap label files  dataset
-  class  class ID   class

## Tests
- 3 core tests 
- `py_compile`  Python module

## 
 incremental refactor  GUI Original  behavior   JobManager + DatasetScanner  Curator/Splitter  Dataset QA 

---

# PK Studio – V1.1 foundation changes

## Class order policy
- Default class creation remains alphabetical, matching the current Roboflow-style workflow.
- The Class Manager now supports **Move Up / Move Down**.
- The UI displays class numbers starting at 1, while YOLO label files remain correctly 0-based.
- Reordering, adding, or deleting a class remaps YOLO IDs across the entire dataset so labels stay attached to the same class name.
- Explicit order stored in `classes.txt` is preserved when reopening the dataset.

## New core modules
- `core/class_registry.py` – deterministic class registry with explicit reorder support.
- `core/dataset.py` – shared image/label scanner and non-destructive Dataset QA checks.
- `core/job_manager.py` – common background-job foundation for future long-running operations.
- `core/project.py` – lightweight `.pkstudio/project.json` persistence foundation.

## Analytics
- Analytics now uses the shared `DatasetScanner`.
- Added **Dataset QA** with a health score and checks for missing/empty labels, corrupt images, invalid bounding boxes, out-of-range class IDs, parse errors, and duplicate filenames.

## Safety
- Class updates use temporary files + `os.replace()` when rewriting labels.
- Invalid class IDs unrelated to a deleted class are preserved so QA can report them instead of silently deleting them.

## Tests
- Added `tests/test_core.py` covering class ordering/reordering and Dataset QA basics.

---

