# DotDotGoose

DotDotGoose is a free, open source tool for manually counting objects in images.
This fork extends upstream DotDotGoose 1.7.1 with native annotations, a two-image
Compare workspace, and shared counting and editing tools.

Current fork version **1.8.9**.

Count points and annotations retain original-image pixel coordinates, making
them suitable for review, analysis, and future computer-assisted counting.

## Download and run on Windows

Download the Windows x64 ZIP from this fork's
[GitHub Releases](https://github.com/khem-so-usfws/DotDotGoose/releases).
Extract the entire archive, then run `DotDotGoose.exe` inside the extracted
folder. Keep the bundled runtime files alongside the executable.

The 1.8.9 package is named `DotDotGoose-1.8.9-windows-x64.zip`. Python and Conda
are required only when running from source or building a release.

## Counting and comparison

Select a class in the left sidebar, choose **Count dots**, and click an image to
add count points. The same selected class applies to Current and Reference, and
counts update for edits made in either pane.

Use the **Compare** toolbar button to show or hide Reference. Its dropdown
selects **1×2 Side by Side** or **2×1 Stacked**. Each pane has an image picker,
Previous/Next, Fit, 1:1, rotation, and Enhance controls. Secondary controls move
into **More (⋯)** when space is limited.

- Pan and zoom independently in each pane.
- Use **Navigator** to show a read-only overview at the bottom right of each pane,
  with a rectangle showing the visible image extent.
- Use **Make Current** in Reference's More menu to swap the two displayed images.
- Undo and redo follow edit order across both panes.
- Hiding Reference releases its decoded image while remembering the image choice.

The workspace loads the displayed Current and Reference images rather than every
image in the project. See the [Compare guide](docs/compare_pane.md) for details.

### Navigation and keyboard controls

| Input | Action |
| --- | --- |
| Click in Count dots | Add a count point in the selected class |
| Shift+drag in Count dots | Select count points within a rectangle |
| C+drag | Temporarily pan |
| Z+drag | Rectangle zoom in |
| X+drag | Rectangle zoom out |
| Mouse wheel | Incremental zoom |
| Ctrl+Z / Ctrl+Y | Undo / redo across both panes |
| Enter or double-click while drawing | Finish a line or polygon |
| Esc | Cancel an unfinished shape or clear selection, retaining the selected tool |

C, Z, and X also work while drawing or editing annotations. Choose **Count dots**
to return to counting after using another tool.

## Native annotations and Select/Edit

Use **Landmark**, **Line**, or **Polygon** to mark reference points, cutlines, and
count regions directly in either pane. The first click activates that pane and
starts the shape. Drawing tools stay selected after a shape is completed.
Finish an unfinished shape with Enter, or cancel it with Esc, before changing
tools or images or starting a shape in the other pane.

Choose **Select/Edit** to work with count dots and annotations together.

| Input | Action |
| --- | --- |
| Click an item | Select it |
| Shift+click | Add or remove an item from the selection |
| Shift+drag | Add visible items fully enclosed by the selection rectangle |
| Drag an already selected item | Move the selected group |
| Drag a selected annotation's vertex handle | Move that vertex |
| Delete / Backspace | Delete selected items |
| Esc or click empty space | Clear the selection |

The first click selects an item. Use a subsequent drag to move it. Moves and
deletions of mixed dot/annotation groups are single undoable actions. A selection
containing a locked annotation must be unlocked or adjusted before moving or
deleting it. An overlap menu helps choose between nearby items.

The pane's selection menu offers **Move by pixel offset**, Delete, and Clear
selection. A single selected annotation also supports properties and right-click
vertex insertion/deletion. Annotation properties include labels, symbology, and
locking.

Count-region polygons can dim the area outside a region, highlight outside
points, and support QA review. Standard point totals and exports include all
count points, including those outside a count region.

See [Native Annotations](docs/native_annotations.md) for geometry, sidecar, and
count-region workflows.

## Image display and workspace

Use the rotation buttons in either pane to rotate its view in 90-degree steps.
Dots, grids, annotations, and the navigator follow the view. **Enhance** provides
independent brightness and contrast controls with Apply, Reset, and an original
image preview.

Zoom, pan, rotation, and enhancement settings are remembered per image within
each pane for the current session. **Reset view** returns the image upright and
fits it to the pane. Display adjustments preserve source-image pixel coordinates.

The main toolbar has three groups separated by pipe dividers.

| Group | Controls |
| --- | --- |
| Panels | Left panel, Right panel, Compare |
| Display | Dots, Grid, Navigator |
| Tools | Landmark, Line, Polygon, Select/Edit, Count dots, Class |

Tools share one active mode across both panes. The selected class appears beside
Count dots, or beside the active-tool selector when the toolbar is compact.
Toolbar groups collapse into menus as the window narrows.

Both sidebars start open and can be toggled or resized. The left sidebar starts
at 425 pixels when space permits. The right sidebar initially receives one quarter
of the space remaining after the left sidebar. Custom fields scroll vertically
when needed to keep their editors usable.

The right sidebar follows the most recently clicked pane. Its heading identifies
Current or Reference. Coordinates and custom-field values belong to that image,
while Survey ID and field definitions apply to the project. Pending field edits
are committed to their original image before changing panes or saving.

The **Working Directory** row below the images displays the image folder. Long
paths shorten in the middle. Hover for the full path, or right-click to copy it.

## Saving and recovery

Count dots, custom-field values, and project metadata are saved in the `.pnt`
project. Native annotations save immediately in LabelMe-compatible `.json`
sidecars beside the source images, with `.json.bak` backups of the previous
sidecar version. Keep the images and their sidecars together when moving a
project. Source images retain their original pixels.

The status bar reports unsaved point/field changes and save failures. A confirmed
save displays **Saved** briefly, then the save indicator becomes blank when idle.
Hover over the indicator for save and recovery details.

Every two minutes while point/field changes are unsaved, DotDotGoose writes a
separate recovery snapshot in the image folder and retains the preceding
snapshot. Use **Recover > Open recovery snapshot** beside Load, Import, Save,
and Reset to open one, then save the recovered project to a chosen destination.
Recovery snapshots contain point/project data. Annotation geometry is stored in
its image sidecars.

See the [recovery documentation](docs/compare_pane.md#workspace-feedback-and-recovery-189)
for snapshot filenames and behavior.

## Run from source

The application requirements are PyQt6 6.7.1, Pillow 10.3.0, and NumPy 1.26.4,
pinned in `requirements.txt`.

Clone the repository and enter its directory.

```bash
git clone https://github.com/khem-so-usfws/DotDotGoose.git
cd DotDotGoose
```

On Windows, use Anaconda Prompt or Miniconda Prompt to create the development
environment.

```bat
conda create -n ddg-dev python=3.12
conda activate ddg-dev
python -m pip install -r requirements.txt
python main.py
```

For later sessions, activate `ddg-dev`, enter the repository directory, and run
`python main.py`.

On Linux or macOS, use a Python 3.12 virtual environment.

```bash
python3.12 -m venv ddg-env
source ddg-env/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Build a Windows executable

Run the build on Windows x64, from the repository root in the activated
development environment.

```bat
python -m pip install -r requirements-build.txt
build_windows.bat
```

The script runs the tests, builds the application using `DotDotGoose.spec`, adds
the license and documentation, and creates the versioned folder and ZIP.

```text
dist\DotDotGoose-1.8.9-windows-x64\DotDotGoose.exe
dist\DotDotGoose-1.8.9-windows-x64.zip
```

The package version comes from `ddg.__version__`. Generated `build/` and `dist/`
directories are ignored by Git. The complete application folder is required
for distribution.

### Recover from a staging error

If PyInstaller reports **Build complete** followed by **Access is denied** and
**Could not stage the versioned release directory**, first confirm that
`dist\DotDotGoose\DotDotGoose.exe` exists. Close any running copy of the built
application. The following commands copy that existing build into a new temp
folder, add the documentation, and create the ZIP.

Run these commands from the repository root in Anaconda Prompt.

```bat
set "DDG_STAGE=%TEMP%\ddg-1.8.9-release-%RANDOM%"
set "DDG_PACKAGE=DotDotGoose-1.8.9-windows-x64"

powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $package=Join-Path $env:DDG_STAGE $env:DDG_PACKAGE; New-Item -ItemType Directory -Path $package -Force | Out-Null; Get-ChildItem -LiteralPath 'dist\DotDotGoose' -Force | Copy-Item -Destination $package -Recurse -Force; Copy-Item -LiteralPath 'LICENSE','README.md','changelog.md','docs' -Destination $package -Recurse; $zip=$package+'.zip'; Compress-Archive -LiteralPath $package -DestinationPath $zip -CompressionLevel Optimal; Get-Item -LiteralPath $zip | Select-Object FullName,Length"

explorer "%DDG_STAGE%"
```

Use the ZIP in that temp folder as the release asset.

### Publish a release

Build from the exact commit being released. Extract the ZIP and test image
loading, counting in both panes, selection/movement/deletion, save and reopen,
annotations, rotation, enhancement, recovery, undo/redo, and export. Include a
Windows machine without Python or Conda when testing the packaged application.

For each new release, commit the final source, push the release branch, and
create an annotated version tag. The example below uses `main` and `v1.8.9`.
Use a new version for a release following an already published tag.

```bat
git push origin main
git tag -a v1.8.9 -m "DotDotGoose 1.8.9"
git push origin refs/tags/v1.8.9
```

Create a release from that tag on the
[GitHub Releases page](https://github.com/khem-so-usfws/DotDotGoose/releases),
add release notes, and attach `DotDotGoose-1.8.9-windows-x64.zip`. The attached
Windows ZIP contains the executable and runtime files. GitHub's automatic
source archives contain the source code.

## Documentation

- [Native Annotations](docs/native_annotations.md)
- [Compare, workspace controls, and recovery](docs/compare_pane.md)
- [Changelog](changelog.md)

## Upstream project

This fork is based on the upstream
[DotDotGoose project](https://github.com/persts/DotDotGoose). Upstream executables
are available from the
[AMNH DotDotGoose page](https://biodiversityinformatics.amnh.org/open_source/dotdotgoose/).
Use this fork's releases for the features described here.

## Contributors

- Peter Erst — https://github.com/persts
- Ido Senesh — https://github.com/idoadse
- Julie Young — https://github.com/julieyoung6
- Ștefan Istrate — https://github.com/stefanistrate
- Khem So — https://github.com/khem-so-usfws
