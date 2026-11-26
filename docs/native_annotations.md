# Native Annotations in DotDotGoose

DotDotGoose can create, edit, and store non-count annotations directly alongside the source image. This removes the routine need to open LabelMe for counting boundaries while keeping LabelMe-compatible JSON sidecars.

## Normal point counting

DDG uses ArcGIS-inspired temporary navigation overrides so ordinary clicking can stay focused on counting:

- **Left-click** adds a point for the active class.
- **Shift+drag** rubber-band selects points.
- **C+drag** temporarily pans the image.
- **Z+drag** draws a rectangle and zooms in to it.
- **X+drag** draws a rectangle and proportionally zooms out around it.
- **Mouse wheel** performs incremental zoom.
- DDG count points remain separate from native annotation points.

C, Z, and X are temporary overrides: release the key and the current count or annotation tool resumes. A plain drag without C does not pan and does not add a point.

## Annotation types

The Tools toolbar and **Annotations** menu provide four drawing tools.

- **Landmark point** (`landmark`) — a non-count point for visual reference.
- **Text Label** (`text_label`) — an outlined caption anchored to a point on a photo.
- **Cutline** (`cutline`) — a line/polyline used to mark a visual division.
- **Count region** (`count_region`) — a polygon defining the valid counting area for an image.

All annotation coordinates are stored in original source-image pixel coordinates.

## Creating annotations

### Landmark

Choose **Annotations > Draw Landmark Point** and click once. Press **Esc** to cancel before placement.

### Text label

Choose **Text Label** beside **Landmark** in the main toolbar, or choose
**Annotations > Add Text Label**. Click any open photo, type a short caption,
and press **Enter**. Use **Esc** or **Cancel** in the prompt to skip placement.
The tool stays active for the next label. Choose **Count dots** to resume counting.

The anchor follows the photo. The text stays upright at a fixed display size
while you pan, zoom, or rotate. Hover over a shortened caption to read the full
text. Text labels leave counts and count regions unchanged.

### Cutline

Choose **Annotations > Draw Cutline**, click two or more vertices, then press **Enter** or double-click to finish. Press **Esc** to cancel an unfinished line.

### Count-region polygon

Choose **Annotations > Draw Count Region Polygon**, click three or more vertices, then press **Enter** or double-click to finish. Press **Esc** to cancel an unfinished polygon.

For images where the complete image is valid for counting, use **Annotations > Use Whole Image as Count Region**.

## Editing annotations

Use **Select** to click, move, or delete whole annotations and count dots.
Shift+click adds or removes an item, and Shift+drag selects fully enclosed
items. An overlap menu helps choose among nearby items.

Click a text label's caption or anchor to select it. Drag a selected label to
move its anchor, or press **Delete** to remove it. Choose **Annotation properties…**
from its right-click or selection menu to edit the caption. Unlock a locked
label before changing its text or location. Creation, text changes, moves, and
deletions use the same cross-pane undo/redo as other annotations.

Select one unlocked line or polygon and open **Edit Shape** in the main toolbar.

| Tool | Workflow |
| --- | --- |
| Reshape | Click to sketch a replacement with two clear joins to the selected line or boundary. Click the area to keep if the preview offers two polygons, then press Enter. The dashed orange segment shows what will be replaced. |
| Trim/Extend | Click the end of the line you want to change. Click along that line to choose a new stopping point, or click out from the end to sketch an extension. Press Enter to apply the preview. |
| Edit Vertices | Drag a handle to move it. Click an edge to insert a vertex. Shift+click to toggle individual handles, then press Delete to remove the selected vertices. |

**Snap** is optional and starts off. Turn it on to attach clicks to nearby
image annotation edges or vertices. When reshaping, you can click two snapped
joins on the selected annotation or sketch across it twice.

To copy a section of a cutline into a new or reshaped count area, choose
**Trace** while drawing that area. Click near the start and end of the section
on the same visible cutline. Trace inserts the intervening cutline vertices in
the clicked direction. Resume the polygon sketch, or trace another stretch.
The line and polygon remain independently editable. Esc exits Trace and keeps
the surrounding sketch. Snap and Trace are in **Edit Shape** at narrow widths.

Press **Backspace** to remove the last reshape sketch point, or **Esc** to cancel the edit. After applying a reshape,
continue working on the selected annotation or click **Select** to select a
different shape. Edits preserve labels, styling, and other annotation
properties, and invalid polygon geometry is blocked. **Ctrl+Z** and
**Ctrl+Y** undo and redo in edit order across the project.

## Properties, visibility, and symbology

The `Annotations` menu provides:

- **Annotation Properties...** to change the semantic label or caption and lock state.
- **Lock Selected Annotation** / **Unlock Selected Annotation**.
- independent show/hide toggles for text labels, landmarks, lines, and polygons.
- **Symbology...** to set color and stroke weight independently for landmarks, cutlines, and count regions.

Symbology and visibility are DDG display preferences. They do not modify annotation geometry or semantic labels.
**Annotations > Show Text Labels** controls captions separately from landmark
points. The toolbar's **Annotations** button controls all annotation categories.

## Count-region behavior

When one or more `count_region` polygons exist, a point is valid when its point coordinate lies inside any of those polygons. A point exactly on a polygon boundary is treated as inside.

Optional assistance includes:

- dimming image areas outside the valid count region;
- highlighting points outside the valid area;
- warning before adding a new point outside the valid area;
- **Count Region QA...** summaries by class.

The QA dialog provides **Previous Outside Point** and **Next Outside Point** controls to center the image on each outside-region point for review.

An image with no explicit `count_region` is treated as unrestricted; ordinary DDG behavior applies to the whole image.

**Native annotations v1 does not filter DDG's standard point totals or exports.** Count-region inclusion, warnings, highlighting, and QA are advisory/validation features at this stage; raw DDG point data remain unchanged.

## Files and data safety

DDG count points remain in the DDG `.pnt` project. Native annotations are stored in a LabelMe-compatible JSON sidecar next to each image:

```text
IMG_4103.JPG
IMG_4103.json
```

DDG writes annotation JSON atomically. When an existing sidecar is replaced, the immediately previous version is retained as:

```text
IMG_4103.json.bak
```

DDG preserves unrelated LabelMe metadata and unsupported shapes where practical. If an existing JSON sidecar is malformed, DDG reports an error rather than silently replacing it.

## Annotation semantics

The standard counting workflow uses:

| Geometry | Label | Meaning |
|---|---|---|
| Point | `landmark` | Visual reference location; never a count point |
| Point | `text_label` | The caption is stored in the shape's `description` field |
| Line | `cutline` | Visual division between portions of a colony |
| Polygon | `count_region` | Valid point-counting area for that source image |

The shape type and label are separate. The `text_label` point class is reserved
for captions. Use Annotation Properties to change the caption or an ordinary
annotation's semantic label.

## Compatibility

The source image is never resampled or modified by native annotations. Coordinates remain in original-image pixel space, preserving compatibility with future training-data and multi-image colony workflows.

Each text label uses a standard LabelMe point shape. For example, a shape in the
sidecar's `shapes` array can contain the following fields.

```json
{
  "label": "text_label",
  "points": [[640.0, 420.0]],
  "group_id": null,
  "description": "Start count here",
  "shape_type": "point",
  "flags": {}
}
```

LabelMe reads this as a point and retains the caption in the description field
in versions that support shape descriptions. DotDotGoose draws that description
on the image. Other point classes keep their usual appearance even when they
have a description. See the [LabelMe shape parser](https://github.com/wkentaro/labelme/blob/v5.7.0/labelme/label_file.py#L95-L107).

## Shared toolbar tools

The Tools toolbar exposes Count dots, Landmark, Text Label, Line, Polygon, Select, and Edit Shape.
Choose one tool and use any open pane directly. Drawing tools stay active after
completion. Select handles dots and every annotation type without choosing
a geometry type first. Shift+click toggles items, Shift+drag from empty space adds
items fully enclosed by the box, and dragging an already-selected item moves the
selected group. Delete/Backspace removes the group in one undoable action. Clicking empty space or pressing Esc clears selection
while retaining the tool. Esc cancels an unfinished drawing and retains its tool;
click Count dots to return to counting. Unfinished shapes must be finished or
explicitly cancelled before changing tools, images, or hiding their pane.
