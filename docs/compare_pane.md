# Lightweight Compare Pane

The Compare pane adds one temporary reference image to normal DotDotGoose.
It is intended primarily for defining and refining native landmarks, cutlines,
and count-region polygons across overlapping source photographs.

## Open and close

Use the **Compare** split button beside Left panel/Right panel to show or hide
the reference pane. Its arrow offers Side by Side and Stacked layouts. These
controls share the same actions as **View > Compare Image** and **Compare Layout**. Hiding Compare
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

The pane marked **CURRENT** has an image picker, Prev/Next, Fit, and 1:1
controls in both single-image and comparison modes. Its picker uses the same
Current image-loading workflow as the sidebar. Selecting the Reference image
as Current retains the existing swap behavior.

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

Count-point placement and Shift+drag selection work in Reference using the
shared class selection. Native annotation editing retains its existing behavior.

## Shared display settings

The left sidebar controls grid spacing, grid color, dot size, and dot color.
The Display toolbar controls dot, grid, and navigator visibility in both panes. Each pane retains its independent
image, zoom, and pan. Display changes preserve the point selection and its
fixed-size yellow/black highlight. Hiding dots temporarily hides their highlights.
Showing dots restores those highlights.

Image pickers list existing project images. Reference excludes Current. Missing
files are omitted when lists refresh. Adding images through the existing project
workflow refreshes both lists.

## Native annotations

Landmark, cutline, and count-region drawing can operate on either displayed
image without pre-activating a pane. Choose the drawing command, then click
directly in Current or Reference. That first image click both chooses the target
pane and places the landmark or first line/polygon vertex.

Select/Edit is a shared tool: click an existing annotation in either pane to
select it directly. Locking and properties act on the selected annotation.
Selecting an annotation in one pane clears the annotation selection in the other.

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


### Image rotation

Use the ↶ and ↷ buttons in either pane header to rotate that view by 90 degrees.
Dots, grids, native annotations, and the navigator follow the image. Fit and 1:1
retain the angle. Images not yet viewed in a pane start upright; revisited images restore their session view. Rotation is a viewing
preference for the current session; saved dots and annotations use original
source-image coordinates. Rotation does not modify the source image file.

## Compact pane controls (1.8.8)

Image names appear once, in each pane’s picker. Hover over the picker or a
dropdown item to read the full filename. Fit, 1:1, and rotation remain local to
each pane. Use the mouse wheel or Z/X+drag to zoom; the old bottom-right
Current-only zoom buttons have been removed. The main toolbar provides
consistent Left panel and Right panel toggles; checked means visible.

## Workspace feedback and recovery (1.8.9)

Each pane has an **Enhance** button for brightness and contrast. Set values and
choose **Apply**, **Reset**, or **Show original** to compare against the applied
adjustments. Close restores the enhanced display. Finish or cancel an unfinished
shape before enhancing. Adjustments affect display pixels only. Source images
and annotation coordinates are unchanged. Native annotation selection may clear
on a scene redraw; count-dot selections are preserved.

The main toolbar groups Panels, Tools, and Display. Tools are mutually exclusive:
Count dots, Landmark, Line, Polygon, and Select/Edit. The chosen tool applies to
both panes and remains selected after completing an annotation. Select/Edit
recognizes any annotation geometry on the first click. Click empty space or press
Esc to clear selection while retaining Select/Edit. Count dots returns to counting.
Esc cancels a draft while retaining its drawing tool; in Count dots it clears the
dot selection. Navigation and Shift-selection do not start annotation geometry.

The blue border identifies the last-clicked pane. Each pane header has two rows:
label/image picker/Previous/Next/More, then Fit/1:1/rotation/Enhance/selection menu.
More contains Reset view and, for Reference, Make Current and Hide Reference.
The fixed-width selection menu reports dots or annotations with suitable actions.
Instructions and unfinished vertex totals appear in the bottom status bar.
An unfinished shape stays in its original pane: finish there with Enter, or cancel
there with Esc before changing tools, images, or hiding that pane. Reselecting the
same tool preserves the draft.

Zoom, pan, and rotation are remembered per image per pane for the current session.
**Reset view** returns upright and fits the image. Enhancement settings are also
remembered per image within each pane. These display settings are not stored in
the point file and start fresh after restarting the application.

The workspace reports unsaved point/field changes and the last confirmed Save.
Native annotations continue to save immediately to their sidecars. Regular point
saves commit atomically. Every two minutes while points/fields are unsaved,
DotDotGoose writes a separate recovery point file in the image folder:
`.survey.ddg-recovery.pnt` for `survey.pnt`, or `.ddg-recovery.pnt` before the first
save. The preceding snapshot is retained with `-previous` in its name. Recovery
never marks changes saved or overwrites the chosen project file. A write failure
is reported in the workspace. The working directory must be writable.

Use **Recover… > Open recovery snapshot…** beside Load/Import/Save/Reset to
open a recovery point file. The menu shows the latest snapshot time and provides
Open recovery folder. Save state appears in the bottom status bar; hover over it
for last-save and recovery details. Failures remain visible until resolved.

Opening a snapshot checks for unsaved
changes first. Save the recovered project using Save As; Ctrl+S opens the save
dialog after recovery. Recovery snapshots contain points, fields, and project
metadata; native annotation geometry remains in its separately saved sidecars.
These snapshots are local recovery aids, not backups against disk loss.

## Unified selection and editing (1.8.9 follow-up)

Choose **Select/Edit** in the toolbar to work with dots and annotations together
in either pane. A click selects one item; the first click never moves it. Drag an
already selected item to move the selected group. A bounding-box preview shows
where the group will move; geometry commits when the mouse is released.

- Shift+click adds/removes items from the selection.
- Shift+drag from empty space adds visible items fully enclosed by the rectangle.
- Delete/Backspace removes the selected group; Esc or an empty click clears it.
- C/Z/X navigation continues to work without changing the selected tool.
- Dot selections made in Count dots carry into Select/Edit in the active pane.
- Clicking another pane clears the previous pane's selection.
- Mixed selections report their total; hover for class, annotation, and lock details.

A single selected annotation exposes its vertex handles. Drag a handle to move
that vertex; drag the shape body to move the shape/group. Right-click a vertex or
segment to delete/insert vertices, subject to geometry validity and lock rules.
Right-click also offers Delete selection, Clear selection, Properties for a single
annotation, and optional **Move by pixel offset…** for precise source-pixel shifts.

When a click is ambiguous, an overlap menu identifies nearby dots/annotations.
Distances use viewport pixels so selection tolerance remains stable under zoom
and rotation. An already-selected nearby item is preferred for dragging.

Moves and deletions are single undoable actions, including mixed groups. If the
selection includes a locked annotation, the entire move/delete is blocked; unlock
or deselect it first. Annotation sidecars are written before count points change,
so a failed sidecar write leaves the entire group unchanged. Dots still require
Save; annotations continue to save immediately. No source image pixels change.

## Responsive layout and active-image data (1.8.9 follow-up)

The right sidebar follows the pane most recently clicked, including explicit
clicks on its header controls. The heading names Current or Reference; hover to
see the image filename. Clicking a sidebar field retains that image target.
Coordinates and custom-field values are image-specific; Survey ID and custom-field
definitions remain project-wide. Values from Reference are saved in the same
project point file and recovery snapshots as Current values.

Pending field text is marked unsaved immediately. Its one-second delayed update
is flushed to the original image before activation/image changes, Save, recovery,
or project reset. Missing image values display as blank, preventing stale text
from being carried into another image. Reset discards the old project's values.

Drag the handles between sidebars and the image workspace to change their widths.
Both sidebars start open. The left sidebar starts at its former 425-pixel width
when space permits, while remaining resizable. Sidebars retain usable minimum
sizes, and many custom
fields scroll vertically instead of shrinking their editors.

Each image pane retains two header rows. Narrow panes move 1:1, rotation, Enhance,
and navigation controls into **More (⋯)** as necessary. A selection submenu is
also available there if its button cannot fit. Controls return when widened.
Toolbar groups similarly switch from buttons to compact menus when necessary;
the compact Tools selector always names the current tool. The same actions and
shortcuts remain available through the menu bar. Panels are never automatically
hidden, and Compare never automatically changes layout. A practical minimum
window width prevents the remaining essential controls from being clipped.

**Export…** now offers Counts, Points, Chips, and Overlay without permanent radio
buttons. Export behavior is unchanged; Overlay exports the Current image.
The original folder button, **Working Directory:** caption, and path row appear
below the image workspace. The path is selectable, and its full value is available
on hover. Recover now has a recovery icon; Recover and Export use matching menu
buttons with icons/text aligned left and dropdown indicators on the right.

The selected-class indicator sits beside **Count dots** in the Tools toolbar.
When the toolbar compacts, it stays beside the active-tool selector, including
when the left sidebar is hidden. Long class names have full details on hover.
Save/recovery state remains in the bottom status bar.

## Toolbar order and quiet status (1.8.9 follow-up)

The toolbar is arranged as Panels (Left panel, Right panel, Compare), then Display
(Dots, Grid, Navigator), then Tools (Landmark, Line, Polygon, Select/Edit, Count
dots, Class). Literal pipe dividers separate the three groups. Small gaps separate
drawing tools, Select/Edit, and counting within Tools; all five tools still belong
to one mutually exclusive group. Compact menus preserve this order and keep the
active tool/class visible.

The Working Directory row gives the path remaining horizontal space. Long paths
abbreviate in the middle instead of forcing the window wider. Hover to see the
full path or right-click and choose Copy full path.

The left sidebar starts at 425 px when space permits. Before manual adjustment,
the right sidebar uses the old layout's one-quarter share of space remaining
after the left sidebar, with the image workspace receiving three quarters.
Dragging a splitter handle preserves the user's chosen sizes during subsequent
window resizing. Both sidebars remain resizable and start open.

The save indicator is blank when idle. Unsaved changes remain visible, a confirmed
save shows Saved for five seconds, and save/recovery failures remain visible until
resolved. Detailed last-save and recovery information remains available on hover.
