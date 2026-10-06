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

The `Annotations` menu provides three drawing tools:

- **Landmark point** (`landmark`) — a non-count point for visual reference.
- **Cutline** (`cutline`) — a line/polyline used to mark a visual division.
- **Count region** (`count_region`) — a polygon defining the valid counting area for an image.

All annotation coordinates are stored in original source-image pixel coordinates.

## Creating annotations

### Landmark

Choose **Annotations > Draw Landmark Point** and click once. Press **Esc** to cancel before placement.

### Cutline

Choose **Annotations > Draw Cutline**, click two or more vertices, then press **Enter** or double-click to finish. Press **Esc** to cancel an unfinished line.

### Count-region polygon

Choose **Annotations > Draw Count Region Polygon**, click three or more vertices, then press **Enter** or double-click to finish. Press **Esc** to cancel an unfinished polygon.

For images where the complete image is valid for counting, use **Annotations > Use Whole Image as Count Region**.

## Editing annotations

Choose **Annotations > Select/Edit Annotation**.

- Click an annotation to select it.
- Drag a vertex handle to reshape a line or polygon.
- Drag the annotation body to move the entire annotation.
- Right-click a line or polygon to insert a vertex on the nearest segment.
- Right-click a vertex to delete it when the remaining geometry stays valid.
- Press **Delete** to remove an unlocked selected annotation.
- Use **Ctrl+Z** and **Ctrl+Y** for undo and redo. When Compare is open, history is chronological across Current and Reference rather than tied to the active pane.

Locked annotations remain selectable for inspection but cannot be moved, reshaped, or deleted until unlocked.

## Properties, visibility, and symbology

The `Annotations` menu provides:

- **Annotation Properties...** to change the semantic label and lock state.
- **Lock Selected Annotation** / **Unlock Selected Annotation**.
- independent show/hide toggles for point, line, and polygon annotations.
- **Symbology...** to set color and stroke weight independently for landmarks, cutlines, and count regions.

Symbology and visibility are DDG display preferences. They do not modify annotation geometry or semantic labels.

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
| Line | `cutline` | Visual division between portions of a colony |
| Polygon | `count_region` | Valid point-counting area for that source image |

The shape type and label are separate. Labels can be changed through Annotation Properties when another semantic use is needed.

## Compatibility

The source image is never resampled or modified by native annotations. Coordinates remain in original-image pixel space, preserving compatibility with future training-data and multi-image colony workflows.

## Native annotations v1 regression checklist

Before tagging a release, verify the following with representative operational imagery:

1. Open an image with no sidecar and count points normally.
2. Create a landmark, cutline, and count-region polygon; close and reopen the image.
3. Move whole annotations and individual vertices; insert and delete vertices.
4. Undo and redo annotation creation, deletion, movement, and property changes.
5. Lock an annotation and confirm geometry/deletion is blocked until it is unlocked.
6. Change annotation labels, colors, and stroke weights; restart DDG and confirm display preferences persist.
7. Toggle point, line, and polygon visibility independently.
8. Use a whole-image count region and confirm unrelated annotations survive.
9. Put points inside, outside, and exactly on a count-region boundary; run Count Region QA.
10. Navigate every outside point with Previous/Next and confirm the image recenters correctly.
11. Confirm outside-point warning/highlighting preferences work as expected.
12. Switch rapidly among 10–20 images, including during unfinished annotation drawing and while annotations are selected.
13. Confirm navigation/count controls: click adds a point, Shift+drag selects points, C+drag pans, Z+drag zooms in, and X+drag zooms out. Confirm plain drag does not add a point.
14. Inspect `.json` and `.json.bak` after annotation edits and verify the backup contains the prior live state.
15. Test a malformed annotation JSON and confirm DDG warns rather than overwriting it.
16. Save/reopen the `.pnt` project and confirm existing classes, counts, and exports remain intact.

After this checklist passes, native annotations v1 should be treated as a stable baseline before adding multi-image colony/reference-window functionality.
