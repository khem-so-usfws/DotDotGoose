# DotDotGoose

DotDotGoose is a free, open source tool for manually counting objects in images.
This fork extends upstream DotDotGoose 1.7.1 with native image annotations,
ArcGIS-inspired navigation, and a lightweight two-image Compare workflow while
preserving the original point-counting model and source-image pixel coordinates.

Current fork version: **1.8.0**.


*Point data collected with DotDotGoose can provide valuable training and
validation data for future computer-assisted counting workflows.*

## What is new in this fork

### Native annotations

DotDotGoose can now create and edit non-count annotations directly on source
images without requiring LabelMe for routine boundary work:

- **Landmark points** for visual reference;
- **Cutlines** for separating portions of an image or colony;
- **Count-region polygons** for marking the valid counting area;
- vertex and whole-shape editing, insertion/deletion of vertices, locking,
  visibility controls, properties, and configurable symbology;
- chronological undo/redo integrated with normal DDG point edits;
- LabelMe-compatible JSON sidecars using original-image pixel coordinates;
- atomic JSON writes plus `.json.bak` backups of the previous sidecar version.

Count regions can optionally dim areas outside the valid region, highlight or
warn about points outside it, and provide QA navigation through outside points.
They are validation aids in 1.8.0: standard DDG raw point totals and exports are
not automatically filtered by count regions.

See [Native Annotations](docs/native_annotations.md) for the complete workflow.

### ArcGIS-inspired counting and navigation

The fork changes the primary image interaction so ordinary clicking stays
focused on counting:

| Input | Action |
| --- | --- |
| **Click** | Add a point in the selected class |
| **Shift+drag** | Rubber-band select count points |
| **C+drag** | Temporarily pan |
| **Z+drag** | Rectangle zoom in |
| **X+drag** | Rectangle zoom out |
| **Mouse wheel** | Incremental zoom |
| **Ctrl+Z / Ctrl+Y** | Undo / redo |

C, Z, and X are temporary navigation overrides, including while an annotation
tool is active. A small click/drag threshold helps prevent accidental point
creation during mouse movement.

### Lightweight Compare pane

Use **View > Compare Image** to display one additional full-resolution reference
image without replacing normal DDG counting.

Key behavior:

- **1×2 Side by Side** is the default layout;
- **2×1 Stacked** is also available;
- both panels have matching image pickers, Previous/Next, Fit, and 1:1 controls;
- Reference has an independent selector plus Previous/Next, Fit, 1:1,
  **Make Current**, and hide controls;
- pan and zoom are independent between panes;
- count points can be added and selected in either pane using the shared class;
- sidebar grid spacing, color, visibility and dot size, color, visibility update both panes;
- landmarks, cutlines, and count regions can be drawn and edited in either pane;
- after choosing a drawing tool, the first ordinary click in either pane both
  selects that pane and starts the annotation—no separate activation click is
  required;
- **Make Current** swaps Current and Reference rather than duplicating an image;
- undo/redo follows edit chronology across both panes rather than the last
  active pane;
- hiding Compare releases the decoded Reference image while remembering its
  filename and layout for the next Compare session.

Only Current and the one visible Reference image are decoded simultaneously, so
projects can contain many large images without loading them all into memory.
Compare does not create mosaics, resample images, or transform annotation
coordinates.

See [Lightweight Compare Pane](docs/compare_pane.md) for details.

## Data compatibility

The fork keeps the original DDG count data separate from native annotations:

- DDG count points remain in the `.pnt` project and retain original-image pixel
  coordinates.
- Native annotations are stored in a LabelMe-compatible `.json` sidecar beside
  each source image.
- Source images are not modified or resampled.
- Unsupported LabelMe shapes and unrelated metadata are preserved where
  practical.

This design keeps original-image point and annotation coordinates suitable for
later QA, analysis, or machine-learning workflows.

## Dependencies

DotDotGoose is developed with the following libraries:

- PyQt6 (6.7.1)
- Pillow (10.3.0)
- NumPy (1.26.4)

## Installation

Clone this fork/repository, then create an environment and install its
requirements. For example on Linux/macOS:

```bash
python3 -m venv ddg-env
source ddg-env/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows, a Conda environment also works well:

```bat
conda create -n ddg-dev python=3.12
conda activate ddg-dev
python -m pip install -r requirements.txt
```

## Launching DotDotGoose

From the repository root:

```bash
python main.py
```

## Documentation

- [Native Annotations](docs/native_annotations.md)
- [Lightweight Compare Pane](docs/compare_pane.md)
- [Changelog](changelog.md)

## Windows executable releases

Windows users do not need Python or Conda when using a packaged release. Download
the versioned Windows ZIP from this repository's GitHub **Releases** page, extract
the complete folder, and run `DotDotGoose.exe`. Do not move the executable out of
its extracted folder because the bundled runtime files beside it are required.

A new unsigned build may trigger Windows SmartScreen or organization-specific
antivirus review. That warning is separate from Python installation and can be
reduced in future releases by code-signing the Windows executable.

### Building the Windows release

Windows release builds are defined by the checked-in `DotDotGoose.spec`
PyInstaller specification and `build_windows.bat` wrapper. Build the Windows
package on a Windows x64 machine; PyInstaller does not cross-compile a Windows
application from Linux or macOS.

From an activated development environment in the repository root:

```bat
python -m pip install -r requirements-build.txt
build_windows.bat
```

By default the script runs the test suite first, builds a windowed PyInstaller
**one-folder** application, copies the license and user documentation into the
release folder, and creates:

```text
dist\DotDotGoose-1.8.0-windows-x64\
dist\DotDotGoose-1.8.0-windows-x64.zip
```

The version in those names is read from `ddg.__version__`, so later releases do
not require editing the batch file. `requirements-build.txt` pins the tested
release-tool versions separately from the application runtime requirements. The
spec explicitly bundles the Qt Designer `.ui` files plus the `icons` and `i18n`
resources that DDG loads at runtime.

Use the optional switch only if the exact same source revision has already been
tested:

```bat
build_windows.bat --skip-tests
```

Before publishing a release, extract the generated ZIP and test it on a Windows
machine that does **not** have Python or Conda installed. At minimum verify image
loading, point counting, save/reopen, native annotations, Count Region QA, both
Compare layouts, Reference annotations, cross-pane undo/redo, export, and normal
application shutdown/restart.

Generated `build/` and `dist/` directories are ignored by Git and should not be
committed.

### Publishing a GitHub Release

Build the executable from the exact commit being released. After the final tests
and merge to `main`, create and push an annotated version tag:

```bat
git checkout main
git pull origin main
pytest -v
git tag -a v1.8.0 -m "DotDotGoose 1.8.0"
git push origin main
git push origin v1.8.0
```

Then open the repository on GitHub and create a new **Release** using the
`v1.8.0` tag. Use a title such as `DotDotGoose 1.8.0`, summarize the major changes
from `changelog.md`, and attach:

```text
DotDotGoose-1.8.0-windows-x64.zip
```

Mark the release as **Latest** when it is the current stable version. GitHub also
creates source-code archives automatically; Windows users who do not install
Python should use the attached `windows-x64.zip` asset instead.

## Upstream project

This fork is based on the upstream
[DotDotGoose project](https://github.com/persts/DotDotGoose). Upstream-provided
executables are available from the
[AMNH DotDotGoose page](https://biodiversityinformatics.amnh.org/open_source/dotdotgoose/),
but those executables may not include the fork-specific 1.8.0 features described
above.

## Contributors

- Peter Erst — https://github.com/persts
- Ido Senesh — https://github.com/idoadse
- Julie Young — https://github.com/julieyoung6
- Ștefan Istrate — https://github.com/stefanistrate
- Khem So — https://github.com/khem-so-usfws


### Image rotation

Use the ↶ and ↷ buttons in either pane header to rotate that view by 90 degrees.
Dots, grids, native annotations, and the navigator follow the image. Fit and 1:1
retain the angle. Each newly opened image starts upright. Rotation is a viewing
preference for the current session; saved dots and annotations use original
source-image coordinates. Rotation does not modify the source image file.

### Workspace improvements (1.8.9)

Both panes have independent Enhance controls, active tool/class and selection
feedback, remembered session views, and Reset view. Confirmed save status and
separate recovery snapshots help protect unsaved point/field edits. See
[the compare-pane guide](docs/compare_pane.md#workspace-feedback-and-recovery-189).

The 1.8.9 UI revision groups shared tools and display toggles in the main toolbar.
Pane headers use two rows; secondary actions are in More (⋯). Recover is beside
the existing project buttons, with save/recovery feedback in the status bar.
Tools stay selected across both panes; Esc cancels a draft or clears selection,
and Count dots explicitly returns to counting.

The next 1.8.9 follow-up adds a Compare visibility/layout split button beside the
panel toggles. Select/Edit now selects, drags, and deletes dots and annotations
using the same gestures, including mixed groups and single-step undo/redo.

The responsive-layout follow-up keeps 1.8.9 and connects the right sidebar to the
active image, safely commits pending field text, adds resizable sidebars and
adaptive overflow, and compacts Export controls. The folder button and Working Directory path row
appear below the images. The left sidebar starts at 425 px and remains resizable.
The selected class appears beside Count dots (or the compact tool selector), while
save state remains in the status bar. Recover and Export share left-aligned
icon/text menu-button styling.

The toolbar-order follow-up keeps version 1.8.9: Panels, Display, and Tools are
separated by pipes; Tools uses Landmark/Line/Polygon, Select/Edit, then Count dots
and Class. The Working Directory path receives visible row space, the right
sidebar starts with its legacy width proportion, and idle save status is blank.
