# Changelog

This changelog describes changes in this fork relative to upstream DotDotGoose
1.7.1.

## 1.8.9

### Toolbar order, folder path, and quiet status (same version)

- Order the toolbar as Panels, Display, and Tools, with literal pipe dividers
  between these groups. Keep spacing-only subgroups within Tools.
- Order tools as Landmark, Line, Polygon, Select/Edit, Count dots, and Class.
  Preserve one exclusive tool group and the same order in compact menus.
- Allocate visible row space to the working-directory path; abbreviate long
  paths in the middle, with a full-path tooltip and Copy full path context action.
- Restore the right sidebar's legacy one-quarter share of space remaining after
  the left sidebar, while preserving manual splitter adjustments.
- Leave save status blank when idle; show Saved for five seconds after a confirmed
  save and retain unsaved-change and failure messages until resolved.

### Layout polish (same version)

- Restore the left sidebar's 425-pixel starting width while retaining resizing.
- Restore the original folder button, Working Directory caption, and path row.
- Move the selected-class indicator beside Count dots, or beside the active-tool
  selector in compact toolbar layouts.
- Give Recover a recovery icon and match Recover/Export menu-button styling,
  with project-button icons and text aligned left.

### Responsive layout and active-image data revision (same version)

- Bind image coordinates and custom-field values to the active Current or
  Reference pane. Keep Survey ID project-wide and label the image-data target.
- Flush delayed field edits before pane/image changes, save, recovery, or reset;
  mark pending text as unsaved immediately and clear absent image values.
- Add sidebar splitter handles and smaller usable minimum widths, keeping both
  panels open on startup.
- Move pane controls into More as space narrows and restore them when widened.
- Compact toolbar groups into menus as needed, retaining the active tool and
  preserving menu commands, shortcuts, and checked states.
- Replace Export radio choices with an Export menu and compact project buttons.
- Replace the working-directory row with a status-bar folder indicator/menu and
  keep selected-class and save-state indicators visible beside contextual guidance.

### Compare and unified editing revision (same version)

- Add a Compare split button beside the panel toggles. Its main button toggles
  Reference and its arrow offers synchronized side-by-side/stacked layouts.
- Extend Select/Edit to dots, annotations, and mixed selections in either pane.
- Support click selection, Shift+click toggling, additive Shift+drag box selection,
  selected-item dragging, Delete/Backspace, and Escape to clear selection.
- Retain single-annotation vertex editing and right-click vertex operations.
- Treat group moves/deletions as one undoable edit; persist annotation changes
  before mutating dots so failed writes cannot partially edit a selection.
- Block group edits containing locked annotations and resolve ambiguous overlaps
  with a chooser. Preserve selections after moving them.
- Rename precise numeric movement to Move by pixel offset and offer it in the
  selection menu alongside direct dragging.

### UI revision (same version)

- Group the main toolbar into Panels, mutually exclusive Tools, and Display.
- Share Count dots, Landmark, Line, Polygon, and Select/Edit across both panes.
- Keep drawing/editing tools active after completion or Escape; Escape clears
  a selection or cancels a draft. Count dots explicitly returns to counting.
- Preserve unfinished geometry when a tool is reselected or a different tool,
  pane, image, or Reference-hide command is requested.
- Compress each pane header to two rows. Move secondary pane actions to a
  More menu and show dot/annotation selections with contextual actions.
- Remove duplicate sidebar visibility checkboxes for dots and grid.
- Move Recover into the existing project controls and save/recovery feedback
  into the bottom status bar; show snapshot details in menus/tooltips.


- Add independent Enhance dialogs in both pane headers, with Apply, Reset,
  and original-image preview. Remember adjustments per image during the session.
- Preserve zoom, rotation, and dot selections during enhancement redraws.
- Show the active pane, current tool/class, and selected-dot totals/class counts.
- Add pane-local selected-dot Move, Delete, and Clear selection menus.
- Transfer completed drawing tools on the first click in the other pane; retain
  unfinished shapes and explain how to finish or cancel them.
- Remember each pane's zoom, pan, and rotation per image during the session,
  with Reset view to return upright and fit.
- Report confirmed saves, unsaved point/field changes, and save failures.
- Save point files atomically and create separate two-minute recovery snapshots
  for unsaved points/fields, retaining the preceding snapshot.
- Add Recover snapshot to open a snapshot and prompt for a new save destination.

## 1.8.8

- Remove the duplicate filename from the Current pane heading.
- Show full image names in picker and dropdown tooltips.
- Align pane header controls and clarify their tooltips.
- Remove the bottom-right zoom buttons that only affected Current.
- Use consistent Left panel / Right panel toolbar labels.

## 1.8.7

- Add independent 90-degree left/right view rotation in both pane headers.
- Rotate images, dots, grids, and native annotations together.
- Retain rotation through Fit, 1:1, pan, and zoom.
- Rotate navigator thumbnails and their viewport outlines.
- Open each image upright and preserve source-image coordinates when editing.

## 1.8.6

- Add matching Current and Reference image pickers, Prev/Next, Fit, and 1:1 controls.
- Keep Current controls available in single-image mode.
- Share sidebar grid and dot display settings across both canvases.
- Preserve point selections and their visible highlights during display changes.
- Guard annotation-preview cleanup against graphics already deleted by the scene.
- Retain independent image views and the existing image-swap and annotation workflows.

## 1.8.0

Version 1.8.0 adds native annotation tools, an ArcGIS-inspired navigation model,
and a lightweight two-image Compare workflow while retaining DDG's original
source-image point-counting approach.

### Native annotations

- Added native non-count annotation support for:
  - landmark points (`landmark`);
  - cutlines (`cutline`);
  - count-region polygons (`count_region`).
- Added direct creation of annotations from the **Annotations** menu.
- Added line and polygon previews while digitizing.
- Added Enter/double-click completion for cutlines and polygons and Esc
  cancellation for unfinished geometry.
- Added selection and editing of native annotations.
- Added whole-shape movement and vertex dragging.
- Added nearest-segment vertex insertion for lines and polygons.
- Added vertex deletion with minimum-geometry safeguards.
- Added annotation deletion with confirmation.
- Added annotation properties for semantic label and lock state.
- Added lock/unlock commands; locked annotations remain selectable but cannot be
  reshaped, moved, or deleted.
- Added independent point, line, and polygon visibility controls.
- Added configurable annotation color and stroke weight.
- Added fixed-screen/cosmetic rendering behavior so annotation symbols remain
  usable across zoom levels.

### LabelMe-compatible persistence and data safety

- Native annotations are stored in LabelMe-compatible JSON sidecars beside the
  source image.
- Annotation coordinates remain in original-image pixel coordinates.
- Existing unsupported LabelMe shapes and unrelated metadata are preserved where
  practical.
- Added compatibility handling for legacy polygon records with missing
  `shape_type`.
- Multi-vertex cutlines are written as LabelMe `linestrip` shapes; two-vertex
  cutlines remain `line` shapes.
- Added validation against non-finite annotation coordinates.
- Added atomic JSON writes using a temporary file and replacement step.
- Added rolling `.json.bak` backup containing the immediately previous sidecar
  version.
- Malformed or unreadable annotation sidecars now produce a warning rather than
  being silently overwritten.
- Annotation undo snapshots no longer retain repeated copies of embedded
  LabelMe `imageData`, reducing history memory growth.
- Failed history reads/writes no longer masquerade as a missing sidecar or lose
  the corresponding undo event.

### Count-region workflow and QA

- Added **Use Whole Image as Count Region**.
- Added optional dimming of image areas outside explicit count regions.
- Added optional highlighting of DDG count points outside count regions.
- Added optional confirmation before placing a count point outside a count
  region.
- Added **Count Region QA** summaries of inside/outside points by class.
- Added Previous/Next Outside Point navigation that recenters the image on each
  outside point.
- Points exactly on a count-region boundary are treated as inside.
- Multiple count-region polygons on one image are treated as a union.
- Images without an explicit count region remain unrestricted.
- Count-region behavior is advisory in 1.8.0: standard DDG raw totals and
  exports remain unchanged.

### ArcGIS-inspired navigation and counting

- Changed normal Count-mode point placement to plain left-click.
- Retained Ctrl+click as a compatibility alias for point placement.
- Retained Shift+drag rubber-band point selection.
- Added **C+drag** temporary pan.
- Added **Z+drag** rectangle zoom in.
- Added **X+drag** rectangle zoom out.
- Retained mouse-wheel incremental zoom.
- Added a small click/drag threshold to prevent accidental point placement after
  mouse movement.
- C/Z/X navigation temporarily overrides annotation drawing/editing without
  cancelling the active annotation tool.
- Esc cancels an active navigation gesture before cancelling unfinished
  annotation geometry.
- Focus loss and image changes clear transient navigation and pending-click
  state to prevent stale input behavior.
- Point undo/redo records retain their source image rather than relying only on
  the currently displayed image.

### Lightweight Compare pane

- Added **View > Compare Image** to show or hide one additional Reference image.
- Added **1×2 Side by Side** and **2×1 Stacked** layouts.
- Fresh/default Compare layout is **1×2 Side by Side**; an explicit saved layout
  preference is retained across sessions.
- Existing DDG image selection remains authoritative for the pane marked
  **★ CURRENT**.
- Reference has an independent image selector.
- Added Reference Previous/Next navigation.
- Added Reference Fit and 1:1 controls.
- Added **Make Current**, which swaps Current and Reference rather than
  duplicating or discarding the comparison pair.
- Added a Reference close/hide control that returns DDG to its normal single-pane
  layout.
- Current and Reference have independent pan/zoom state.
- DDG count-point placement and Shift count-point selection are disabled in
  Reference.
- Native annotations can be displayed and edited in both Current and Reference.
- Drawing tools can be armed before a target pane is chosen; the first ordinary
  drawing click in either pane both selects that pane and places the annotation
  point/first vertex.
- No preliminary pane-activation click is required for Landmark, Cutline, or
  Count Region drawing.
- Only one pane owns unfinished annotation interaction at a time; explicitly
  starting a drawing tool in the other pane safely transfers tool ownership.
- Completed point, cutline, or polygon geometry returns its pane to Count mode,
  allowing immediate annotation work in the other pane.
- Annotation selection/editing and properties target the most recently clicked
  pane.
- Added one chronological Ctrl+Z/Ctrl+Y history across Current and Reference,
  including mixed DDG count-point and annotation edits.
- New edits invalidate redo history globally.
- Failed annotation undo/redo persistence leaves history order intact rather
  than skipping older events.
- Compare splitter panes can be resized substantially without header controls
  imposing the earlier large minimum pane size.
- Hiding Compare retains the selected Reference filename/layout but releases the
  Reference scene, decoded image array, and display pixmap.
- Only Current and one visible Reference image are decoded simultaneously; no
  thumbnail or bulk image cache is required.
- Compare does not mosaic, register, resample, or transform source images.

### Reliability and regression fixes

- Fixed crashes caused by stale Python references to Qt graphics items after
  `QGraphicsScene.clear()` during image changes.
- Added explicit teardown of annotation previews, selected handles, count-region
  masks, and transient edit state before clearing a scene.
- Fixed stale cached Ctrl state after modal dialogs by using event modifiers for
  mouse interaction.
- Prevented point-specific Delete/relabel/class shortcuts from acting while an
  annotation drawing tool owns the interaction.
- Avoided unnecessary annotation JSON rewrites when an annotation is clicked but
  not actually moved.
- Reduced repeated settings reads and count-region filtering during count-point
  redraws.
- Reduced unnecessary point redraws during annotation-only selection/style
  changes.
- Added clear annotation-load warnings for malformed supported geometry or
  malformed JSON structure.
- Improved cleanup and image-memory release when Compare is hidden.

### Documentation and release metadata

- Added `docs/native_annotations.md` with annotation workflow, count-region
  semantics, persistence behavior, and a regression checklist.
- Added `docs/compare_pane.md` describing the lightweight Compare workflow.
- Updated built-in annotation help and Count-mode status guidance.
- Updated application version to **1.8.0**.
- Added Khem So (https://github.com/khem-so-usfws) to contributor credits.
- Added checked-in PyInstaller Windows build configuration, a repeatable release
  batch script, pinned build-tool requirements, and Git ignore rules for generated
  build artifacts.

### Compatibility and intentional scope

- Existing DDG `.pnt` count projects remain the authoritative storage for count
  points.
- Native annotations remain separate from count points and use image-adjacent
  JSON sidecars.
- Original images are never modified or resampled by native annotation or
  Compare features.
- Standard DDG raw count totals/exports are not automatically filtered by count
  regions in 1.8.0.
- Compare intentionally loads one Reference image rather than an unrestricted
  grid of simultaneous full-resolution images.
- Image registration, automatic cross-image correspondence, saved colony/image
  groups, linked landmarks, and colony-level combined totals are not part of
  1.8.0.
- Held C/Z/X navigation-key state is still local to an individual image viewer;
  moving between Compare panes while continuing to hold the same key may require
  releasing and pressing it again.
- Loading a different image into a pane clears that Canvas's legacy undo history;
  undo/redo is chronological across the currently represented pane histories,
  not a permanent project-wide transaction log.

## Upstream 1.7.1

Upstream DotDotGoose 1.7.1 is the base version for this fork. For upstream
history and releases, see https://github.com/persts/DotDotGoose.
