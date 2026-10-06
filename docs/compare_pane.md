# Lightweight Compare Pane

The Compare pane adds one temporary reference image to normal DotDotGoose.
It is intended primarily for defining and refining native landmarks, cutlines,
and count-region polygons across overlapping source photographs.

## Open and close

Use **View > Compare Image** to show or hide the reference pane. Hiding Compare
returns the Current viewer to the full image area. DDG remembers the selected
reference filename and layout, but releases the decoded reference image from
memory while Compare is hidden.

## Layout

Use **View > Compare Layout**:

- **1×2 Side by Side** — Current and Reference are arranged horizontally.
- **2×1 Stacked** — Current is above Reference.

The fresh/default layout is **1×2 Side by Side**. DDG remembers an explicit
layout choice, so a previously saved 2×1 preference remains in effect after an
upgrade. Changing layouts does not change either selected image.

## Current image

The existing DDG image selection remains authoritative. The pane marked
**★ CURRENT** is the normal DDG image and retains standard count-point behavior.

- Click adds a point in the selected class.
- Shift+drag selects count points.
- C+drag pans.
- Z+drag zooms in.
- X+drag zooms out.

## Reference image

The Reference header provides an independent image selector plus:

- **Prev / Next** — change only the reference image;
- **Fit** — fit the reference image in its viewport;
- **1:1** — reset the reference view to one scene pixel per view pixel;
- **Make Current** — promote Reference to Current while moving the former
  Current image into Reference;
- **×** — hide Compare.

Normal DDG count-point placement and Shift count-point selection are disabled in
Reference. Navigation and native annotation editing remain available.

## Native annotations

Landmark, cutline, and count-region drawing can operate on either displayed
image without pre-activating a pane. Choose the drawing command, then click
directly in Current or Reference. That first image click both chooses the target
pane and places the landmark or first line/polygon vertex.

Selection/editing, locking, and properties remain targeted to the most recently
clicked pane because those commands act on an existing annotation rather than
starting new geometry.

Ctrl+Z and Ctrl+Y use one chronological history across Current and Reference.
Undo therefore reverses the most recent edit regardless of which pane is active;
redo follows the same cross-pane chronology.

Annotations remain stored against their original source image in its existing
LabelMe-compatible sidecar. Compare creates no mosaic or transformed image.

## Performance

Only Current and the one visible Reference image are decoded simultaneously.
Other project images remain filenames only. When Compare is hidden, DDG releases
the Reference scene and decoded image array while retaining the selected
filename for the next Compare session.
