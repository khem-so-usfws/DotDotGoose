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

Changing layouts does not change either selected image.

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

Landmark, cutline, count-region, selection/editing, locking, properties, and
annotation undo/redo can operate on either displayed image. Click or move the
mouse into the desired image pane before invoking the annotation command. The
most recently focused pane receives the command.

Annotations remain stored against their original source image in its existing
LabelMe-compatible sidecar. Compare creates no mosaic or transformed image.

## Performance

Only Current and the one visible Reference image are decoded simultaneously.
Other project images remain filenames only. When Compare is hidden, DDG releases
the Reference scene and decoded image array while retaining the selected
filename for the next Compare session.

- Native annotations can be displayed and edited in either pane. Click an image pane before choosing an annotation command; the last-clicked pane remains the annotation target even while the pointer moves to the menu.
- The divider between Current and Reference can be dragged close to either edge; comparison controls must not impose a large minimum pane size.
