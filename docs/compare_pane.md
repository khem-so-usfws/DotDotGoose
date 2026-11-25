# Image panes and multi-monitor review

DotDotGoose supports up to four editable panes in one project. Pane 1
through Pane 4 have the same counting and annotation tools. Each independently
displays a photo from the working folder.

## Manage the panes

Click **Panes** in the main toolbar to restore the last multi-pane setup.
Click it again to work in only the active pane. The arrow opens the pane count,
docked layout choices, and **Reopen pane** for individual closed panes.

| Docked panes | Layout |
| --- | --- |
| 1 | Full image workspace |
| 2 | Side by Side or Stacked |
| 3 | Large view on the left and two stacked on the right |
| 4 | 2 × 2 grid |

Use **Arrange docked panes** to reapply the preset after manually rearranging
the panes. Drag the dividers to resize neighboring docked views. The preset uses
the number of docked panes, leaving floating panes on their monitors.

### Dock or float a pane

- Drag the pane's title bar clear of the image workspace to float it. Move it to
  the monitor you want. Try two docked panes and two floats on a second monitor
  for a four-photo review.
- Drag a floating pane's title bar back over the image workspace. The preview
  shows the available docking position. Release when it shows the desired split.
- Use **More > Float pane** or **More > Dock pane** when you prefer a command.
- Close a floating pane with its window close button. **Panes > Reopen pane**
  restores that photo and view **docked** in the main window.
- Open floating windows are recorded when you quit. The app restores them when
  you return to the working folder and docks windows whose saved locations are
  outside the available displays.

## Review a sequence of colony photos

1. Open the image folder or load its point project.
2. Choose three or four panes and pick the photos you want to compare. Keep a
   useful overlap or overview photo in one pane while navigating the others.
3. Use **Line** to draw cutlines and **Polygon** to mark count areas across the
   colony before counting. Click directly in the pane you want to edit.
4. Press **Enter** or double-click to finish a shape. Press **Esc** to cancel a
   draft. Finish or cancel before changing the editing target, selecting a
   different photo, or closing the pane.
5. Choose **Count dots** and select a class in the left sidebar. Click birds in
   whichever panes you are counting. Save to write the project point file.

Each pane's picker and Prev/Next controls follow filename order. Navigating one
pane leaves the other photos in place. Use the same photo in two panes if you
want separate views of it. Completed dot and annotation edits appear in both.

## Active pane and shared editing

Click an image or a pane's header control to activate it. The blue border marks
the active image. The right sidebar names the pane and shows that photo's
coordinates and custom-field values. Survey ID and custom-field definitions
apply to the project. Pending field edits are committed to their original image
before activation changes.

Both sidebars stay in the main window. The left sidebar holds the shared
counting class and counts. The main toolbar controls the selected tool and the
visibility of dots, grid, navigator, and annotations across panes. The toolbar
and pane headers move secondary actions into menus when space is limited.

Choose **Select** to move or delete whole dots and annotations in any open pane.
Use the main toolbar’s **Edit Shape** tools to reshape or edit vertices on one
line or polygon in the active pane, including a floating pane.

| Gesture or action | Result |
| --- | --- |
| Click an item | Select it |
| Shift+click | Add or remove one item |
| Shift+drag | Add fully enclosed visible items |
| Drag an already-selected item | Move the group |
| Drag a selected annotation vertex | Move that vertex |
| Delete or Backspace | Delete the selected items |
| Esc | Clear the selection or cancel an unfinished shape |
| **Change class…** | Reclassify selected dots as one undoable edit |

Selections are edited in one pane at a time. The selection menu also offers
**Move by pixel offset**, **Delete selection**, and **Clear selection**. Right
click a selected annotation to access its properties or vertex actions.
Locked annotations must be unlocked or removed from a selection before moving
or deleting the group.

**Ctrl+Z** and **Ctrl+Y** follow project edit order across panes. **Ctrl+S** saves
the shared project from a docked or floating pane. **Count Region QA** opens for
the active image. See [Native annotations](native_annotations.md) for the
count-region and sidecar workflows.

## Independent views

- Zoom with the mouse wheel or **Z+drag / X+drag**. Use **C+drag** to pan.
- **Fit** fits the image while retaining its rotation. **1:1** displays source
  pixels at actual size. **More > Reset view** returns the photo upright and fits it.
- The toolbar **Navigator** shows an overview and visible extent per pane.
- Use the rotation buttons for quarter turns. Dots, annotations, grid, and the
  navigator follow that pane's view.
- Use **Enhance** to adjust brightness and contrast. Click **Apply** or press
  **Enter** to apply both values. **Show original** previews unadjusted pixels.

View settings are remembered for each photo in each pane, including zoom, pan,
rotation, brightness, and contrast. The layout, divider sizes, active pane,
open photos, and floating positions are workstation settings for the working
folder. View adjustments preserve the source pixels and annotation coordinates.

## Saving and recovery

Count dots, image fields, and project metadata save in the shared `.pnt` file.
Landmarks, cutlines, and count regions save immediately to the image's
LabelMe-compatible JSON sidecar. Keep the images and their sidecars together when
moving a project.

The status bar reports unsaved point or field changes, confirmed saves, and
failures. While changes are unsaved, the app writes a recovery snapshot every
two minutes, retaining the preceding snapshot. A project named `survey.pnt`
uses `.survey.ddg-recovery.pnt`. Before the first save the name is
`.ddg-recovery.pnt`. The preceding snapshot has `-previous` in its name.

Use **Recover > Open recovery snapshot** to open one, then save the recovered
points and fields to a chosen project file. Annotation geometry stays in the
image sidecars.
