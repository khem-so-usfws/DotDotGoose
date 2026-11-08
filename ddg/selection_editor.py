"""Unified dot and annotation selection with transactional group edits."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PyQt6 import QtCore, QtGui, QtWidgets, sip

from .annotations import Annotation, AnnotationShape
from .canvas import Canvas, HistoryEvent
from .central_graphics_view import CentralGraphicsView, InteractionMode

if TYPE_CHECKING:
    from .workspace_controls import WorkspaceControls

PointSnapshot = dict[str, list[tuple[QtCore.QPointF, QtCore.QPointF]]]


@dataclass
class EditState:
    """Point object identities/coordinates and an optional sidecar snapshot."""

    points: PointSnapshot
    annotations: dict[str, Any] | None


def apply_selection_state(canvas: Canvas, event: HistoryEvent, index: int) -> bool:
    """Restore one side of a mixed edit, writing annotations before point changes.

    Args:
        canvas: Owning scene/project.
        event: Complete mixed-edit history event.
        index: Before-state index (2) or after-state index (3).

    Returns:
        Whether the complete edit was restored successfully.
    """
    image_path: str = str(event[1])
    state: EditState = cast(EditState, event[index])
    if bool(event[4]) and not canvas._apply_annotation_history_snapshot(
        image_path, state.annotations, None
    ):
        return False
    name: str = Path(image_path).name
    if bool(event[5]):
        old_classes: set[str] = set(canvas.points.get(name, {}))
        restored: dict[str, list[QtCore.QPointF]] = {}
        for class_name, points in state.points.items():
            restored[class_name] = []
            for point, position in points:
                point.setX(position.x())
                point.setY(position.y())
                restored[class_name].append(point)
        canvas.points[name] = restored
        for class_name in old_classes | set(restored):
            canvas.update_point_count.emit(
                name, class_name, len(restored.get(class_name, []))
            )
        canvas.dirty = True
    if canvas.current_image_name == name:
        canvas.selection = []
        canvas.clear_external_annotation_selection()
        canvas.display_points()
    return True


@dataclass
class Target:
    """A screen-distance hit on a dot, annotation, or selected vertex."""

    kind: str
    distance: float
    annotation: int = -1
    class_name: str = ""
    point: QtCore.QPointF | None = None
    vertex: int = -1


class SelectionEditor(QtCore.QObject):
    """Provide the same selection and edit gestures for both kinds of geometry."""

    def __init__(
        self, controls: WorkspaceControls, view: CentralGraphicsView, canvas: Canvas
    ) -> None:
        """Install selection gestures on one pane, retaining C/Z/X navigation.

        Args:
            controls: Shared workspace tools.
            view: Target graphics view.
            canvas: Owning scene.
        """
        super().__init__(view)
        self.controls: WorkspaceControls = controls
        self.view: CentralGraphicsView = view
        self.canvas: Canvas = canvas
        self.gesture: str = ""
        self.start: QtCore.QPoint = QtCore.QPoint()
        self.source_start: QtCore.QPointF = QtCore.QPointF()
        self.drag_rect: QtCore.QRect = QtCore.QRect()
        self.target: Target | None = None
        self.rubber: QtWidgets.QRubberBand = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Shape.Rectangle, view.viewport()
        )
        self.menu: QtWidgets.QMenu = QtWidgets.QMenu(view)
        self.menu.addAction("Move by pixel offset…", self.move_by_offset)
        self.menu.addAction("Delete selection", self.delete_selection)
        self.menu.addAction("Clear selection", self.clear)
        self.properties_action: QtGui.QAction = self.menu.addAction(
            "Annotation properties…", self.properties
        )
        self.menu.aboutToShow.connect(self.update_menu)
        view.viewport().installEventFilter(self)
        view.installEventFilter(self)
        canvas.image_about_to_change.connect(self.cancel_gesture)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Handle selection events before the legacy annotation-only handlers.

        Args:
            watched: View or viewport receiving the event.
            event: Input event.

        Returns:
            Whether the event was handled here.
        """
        kind: QtCore.QEvent.Type = event.type()
        if kind not in {
            QtCore.QEvent.Type.KeyPress,
            QtCore.QEvent.Type.MouseButtonPress,
            QtCore.QEvent.Type.MouseButtonRelease,
            QtCore.QEvent.Type.MouseMove,
            QtCore.QEvent.Type.ContextMenu,
        } or sip.isdeleted(self.view):
            return False
        if self.controls.mode is not InteractionMode.SELECT:
            return False
        if (
            self.view._active_navigation_override() is not None
            or self.view.navigation_gesture is not None
        ) and kind != QtCore.QEvent.Type.KeyPress:
            return False
        if kind == QtCore.QEvent.Type.KeyPress:
            key: QtGui.QKeyEvent = cast(QtGui.QKeyEvent, event)
            if key.key() == QtCore.Qt.Key.Key_Escape:
                if self.view.navigation_gesture is not None:
                    return False
                self.clear()
                event.accept()
                return True
            if key.key() in {QtCore.Qt.Key.Key_Delete, QtCore.Qt.Key.Key_Backspace}:
                self.delete_selection()
                event.accept()
                return True
        if watched is self.view.viewport():
            if kind == QtCore.QEvent.Type.MouseButtonPress:
                mouse: QtGui.QMouseEvent = cast(QtGui.QMouseEvent, event)
                if mouse.button() == QtCore.Qt.MouseButton.LeftButton:
                    self.press(mouse)
                    return True
            elif kind == QtCore.QEvent.Type.MouseMove and self.gesture:
                self.move(cast(QtGui.QMouseEvent, event))
                return True
            elif kind == QtCore.QEvent.Type.MouseButtonRelease:
                mouse = cast(QtGui.QMouseEvent, event)
                if mouse.button() == QtCore.Qt.MouseButton.LeftButton:
                    self.release(mouse)
                    return True
            elif kind == QtCore.QEvent.Type.ContextMenu:
                self.context_menu(cast(QtGui.QContextMenuEvent, event))
                return True
        return False

    def point_snapshot(self) -> PointSnapshot:
        """Capture source coordinates while retaining count-dot object identities."""
        return {
            name: [(point, QtCore.QPointF(point)) for point in points]
            for name, points in self.canvas.points.get(
                self.canvas.current_image_name, {}
            ).items()
        }

    def selection_description(self) -> str:
        """Describe selected dots, annotations, and locks for the selection tooltip."""
        counts: Counter[str] = Counter(name for name, _point in self.canvas.selection)
        lines: list[str] = [
            f"{sum(counts.values())} dots; {len(self.canvas.selected_annotation_indices)} annotations"
        ]
        lines.extend(f"{name}: {count}" for name, count in sorted(counts.items()))
        for index in sorted(self.canvas.selected_annotation_indices):
            annotation: Annotation = self.canvas.external_annotations[index]
            lines.append(
                f"{annotation.label} ({annotation.shape_type.value})"
                + (" · locked" if annotation.locked else "")
            )
        return "\n".join(lines)

    def update_menu(self) -> None:
        """Enable properties only for a single selected annotation without dots."""
        self.properties_action.setEnabled(
            len(self.canvas.selected_annotation_indices) == 1
            and not self.canvas.selection
        )

    def properties(self) -> None:
        """Use the existing properties editor for one selected annotation."""
        self.controls.widget.edit_selected_annotation_properties_for_canvas(self.canvas)

    def refresh_selection(self) -> None:
        """Render selection highlights and handles without changing geometry."""
        indices: set[int] = self.canvas.selected_annotation_indices
        self.canvas.selected_external_annotation_index = (
            next(iter(indices))
            if len(indices) == 1 and not self.canvas.selection
            else None
        )
        self.canvas._rerender_external_annotations(
            refresh_mask=False, refresh_points=False
        )
        self.canvas.display_points()
        self.controls.refresh()

    def clear(self) -> None:
        """Clear dots and annotations while retaining Select/Edit."""
        self.cancel_gesture()
        self.canvas.selection = []
        self.canvas.clear_external_annotation_selection()
        self.canvas.display_points()
        self.controls.feedback.notice = ""
        self.controls.refresh()

    def cancel_gesture(self) -> None:
        """Discard the visual drag preview; committed geometry is unchanged."""
        self.gesture = ""
        self.target = None
        self.rubber.hide()

    @staticmethod
    def segment_distance(
        point: QtCore.QPointF, first: QtCore.QPointF, last: QtCore.QPointF
    ) -> float:
        """Measure a screen-space distance to a segment.

        Args:
            point: Cursor position.
            first: Segment start.
            last: Segment end.

        Returns:
            Distance in viewport pixels.
        """
        delta: QtCore.QPointF = last - first
        length: float = delta.x() ** 2 + delta.y() ** 2
        fraction: float = (
            max(
                0.0,
                min(
                    1.0,
                    (
                        (point.x() - first.x()) * delta.x()
                        + (point.y() - first.y()) * delta.y()
                    )
                    / length,
                ),
            )
            if length
            else 0.0
        )
        return QtCore.QLineF(point, first + fraction * delta).length()

    def hits(self, position: QtCore.QPoint) -> list[Target]:
        """Find visible geometry using a fixed eight-pixel screen tolerance.

        Args:
            position: Viewport cursor position.

        Returns:
            Candidates ordered by distance and dot/vertex preference.
        """
        cursor: QtCore.QPointF = QtCore.QPointF(position)
        result: list[Target] = []
        if self.canvas.show_points:
            for name, points in self.canvas.points.get(
                self.canvas.current_image_name, {}
            ).items():
                for point in points:
                    distance: float = QtCore.QLineF(
                        cursor, QtCore.QPointF(self.view.mapFromScene(point))
                    ).length()
                    if distance <= 8:
                        result.append(
                            Target("dot", distance, class_name=name, point=point)
                        )
        for index, annotation in enumerate(self.canvas.external_annotations):
            if not self.canvas.annotation_type_visible(annotation.shape_type):
                continue
            points: list[QtCore.QPointF] = [
                QtCore.QPointF(self.view.mapFromScene(QtCore.QPointF(x, y)))
                for x, y in annotation.points
            ]
            inside: bool = False
            if len(points) == 1:
                distance = QtCore.QLineF(cursor, points[0]).length()
            else:
                pairs: list[tuple[QtCore.QPointF, QtCore.QPointF]] = list(
                    zip(points, points[1:])
                )
                if annotation.shape_type is AnnotationShape.POLYGON:
                    pairs.append((points[-1], points[0]))
                distance = min(
                    self.segment_distance(cursor, first, last) for first, last in pairs
                )
                if annotation.shape_type is AnnotationShape.POLYGON and QtGui.QPolygonF(
                    points
                ).containsPoint(cursor, QtCore.Qt.FillRule.OddEvenFill):
                    inside = True
                    distance = min(distance, 20.0)
            if distance <= 8 or inside:
                result.append(Target("annotation", distance, annotation=index))
            if (
                self.canvas.selected_annotation_indices == {index}
                and not self.canvas.selection
                and not annotation.locked
            ):
                for vertex, point in enumerate(points):
                    distance = QtCore.QLineF(cursor, point).length()
                    if distance <= 8:
                        result.append(
                            Target("vertex", distance, annotation=index, vertex=vertex)
                        )
        result.sort(
            key=lambda hit: (hit.distance, 0 if hit.kind in {"dot", "vertex"} else 1)
        )
        return result

    def choose(self, position: QtCore.QPoint) -> Target | None:
        """Resolve close overlaps with a menu rather than choosing arbitrarily.

        Args:
            position: Viewport cursor position.

        Returns:
            Chosen hit or no selection.
        """
        hits: list[Target] = self.hits(position)
        if not hits:
            return None
        first: Target = hits[0]
        nearby: list[Target] = [first]
        identities: set[tuple[str, int]] = {
            (
                ("dot", id(first.point))
                if first.kind == "dot"
                else ("annotation", first.annotation)
            )
        }
        for hit in hits[1:]:
            identity: tuple[str, int] = (
                ("dot", id(hit.point))
                if hit.kind == "dot"
                else ("annotation", hit.annotation)
            )
            if hit.distance <= first.distance + 1.5 and identity not in identities:
                nearby.append(hit)
                identities.add(identity)
        if len(nearby) == 1:
            return first
        selected: list[Target] = [hit for hit in nearby if self.is_selected(hit)]
        if len(selected) == 1:
            return selected[0]
        menu: QtWidgets.QMenu = QtWidgets.QMenu(self.view)
        actions: dict[QtGui.QAction, Target] = {}
        for number, hit in enumerate(nearby, 1):
            text: str = (
                f"Dot · {hit.class_name}"
                if hit.kind == "dot"
                else f"{self.canvas.external_annotations[hit.annotation].label} · annotation {hit.annotation + 1}"
            )
            actions[menu.addAction(f"{number}. {text}")] = hit
        action: QtGui.QAction | None = menu.exec(
            self.view.viewport().mapToGlobal(position)
        )
        return actions.get(action) if action is not None else None

    def is_selected(self, target: Target) -> bool:
        """Check a candidate against identity-based count and annotation selection.

        Args:
            target: Candidate item.

        Returns:
            Whether the item is already selected.
        """
        return (
            any(point is target.point for _name, point in self.canvas.selection)
            if target.kind == "dot"
            else target.annotation in self.canvas.selected_annotation_indices
        )

    def toggle(self, target: Target) -> None:
        """Add or remove a candidate without changing other selected items.

        Args:
            target: Candidate item.
        """
        if target.kind == "dot":
            if self.is_selected(target):
                self.canvas.selection = [
                    (name, point)
                    for name, point in self.canvas.selection
                    if point is not target.point
                ]
            elif target.point is not None:
                self.canvas.selection.append((target.class_name, target.point))
        elif target.annotation in self.canvas.selected_annotation_indices:
            self.canvas.selected_annotation_indices.remove(target.annotation)
        else:
            self.canvas.selected_annotation_indices.add(target.annotation)
        self.refresh_selection()

    def press(self, event: QtGui.QMouseEvent) -> None:
        """Select on the first click and arm movement only for selected items.

        Args:
            event: Left-button press.
        """
        self.view.view_activated.emit()
        self.cancel_gesture()
        self.start = event.position().toPoint()
        self.source_start = self.view.mapToScene(self.start)
        shift: bool = bool(event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier)
        candidates: list[Target] = self.hits(self.start)
        target: Target | None = self.choose(self.start) if candidates else None
        if candidates and target is None:
            return
        if target is None:
            if shift:
                self.gesture = "box"
                self.rubber.setGeometry(QtCore.QRect(self.start, QtCore.QSize()))
            else:
                self.clear()
            return
        if shift:
            self.toggle(target)
        elif not self.is_selected(target):
            self.clear()
            self.toggle(target)
        elif self.editable():
            self.target = target
            self.gesture = "vertex" if target.kind == "vertex" else "move"
            bounds: QtCore.QRectF = QtCore.QRectF()
            for point in self.selected_positions():
                pixel: QtCore.QPoint = self.view.mapFromScene(point)
                rect: QtCore.QRectF = QtCore.QRectF(
                    pixel.x() - 6, pixel.y() - 6, 12, 12
                )
                bounds = bounds.united(rect)
            self.drag_rect = (
                bounds.toAlignedRect()
                if self.gesture == "move"
                else QtCore.QRect(
                    self.start - QtCore.QPoint(6, 6), QtCore.QSize(12, 12)
                )
            )
        event.accept()

    def selected_positions(self) -> list[QtCore.QPointF]:
        """Return vertices and dot centers used for the group drag preview."""
        return [QtCore.QPointF(point) for _name, point in self.canvas.selection] + [
            QtCore.QPointF(x, y)
            for index in self.canvas.selected_annotation_indices
            for x, y in self.canvas.external_annotations[index].points
        ]

    def move(self, event: QtGui.QMouseEvent) -> None:
        """Show a bounding-box preview without changing saved geometry mid-drag.

        Args:
            event: Drag position.
        """
        position: QtCore.QPoint = event.position().toPoint()
        if (
            position - self.start
        ).manhattanLength() < QtWidgets.QApplication.startDragDistance():
            return
        self.rubber.setGeometry(
            QtCore.QRect(self.start, position).normalized()
            if self.gesture == "box"
            else self.drag_rect.translated(position - self.start)
        )
        self.rubber.show()

    def release(self, event: QtGui.QMouseEvent) -> None:
        """Commit one group edit, or finish an additive box selection.

        Args:
            event: Left-button release.
        """
        position: QtCore.QPoint = event.position().toPoint()
        if (
            self.gesture
            and (position - self.start).manhattanLength()
            >= QtWidgets.QApplication.startDragDistance()
        ):
            if self.gesture == "box":
                self.select_box(QtCore.QRect(self.start, position).normalized())
            else:
                self.edit(
                    offset=self.view.mapToScene(position) - self.source_start,
                    vertex=self.target if self.gesture == "vertex" else None,
                )
        self.cancel_gesture()
        event.accept()

    def select_box(self, rect: QtCore.QRect) -> None:
        """Add visible items fully enclosed by a screen-space rectangle.

        Args:
            rect: Selection rectangle in viewport coordinates.
        """
        if self.canvas.show_points:
            for name, points in self.canvas.points.get(
                self.canvas.current_image_name, {}
            ).items():
                for point in points:
                    if rect.contains(self.view.mapFromScene(point)) and not any(
                        existing is point for _name, existing in self.canvas.selection
                    ):
                        self.canvas.selection.append((name, point))
        for index, annotation in enumerate(self.canvas.external_annotations):
            if self.canvas.annotation_type_visible(annotation.shape_type) and all(
                rect.contains(self.view.mapFromScene(QtCore.QPointF(x, y)))
                for x, y in annotation.points
            ):
                self.canvas.selected_annotation_indices.add(index)
        self.refresh_selection()

    def editable(self) -> bool:
        """Block a whole operation if its selection contains a locked annotation."""
        if any(
            self.canvas.external_annotations[index].locked
            for index in self.canvas.selected_annotation_indices
        ):
            self.controls.feedback.notice = "Selection includes a locked annotation. Unlock it or remove it from the selection before moving/deleting."
            self.controls.refresh()
            return False
        return True

    def edit(
        self,
        offset: QtCore.QPointF | None = None,
        delete: bool = False,
        vertex: Target | None = None,
    ) -> bool:
        """Commit a single atomic, undoable dot/annotation group change.

        Args:
            offset: Source-pixel translation, or no translation for deletion.
            delete: Whether to remove selected items.
            vertex: Optional single vertex to move instead of the whole group.

        Returns:
            Whether the operation committed successfully.
        """
        if (
            not (self.canvas.selection or self.canvas.selected_annotation_indices)
            or not self.editable()
        ):
            return False
        if offset is not None and offset.isNull() and not delete:
            return False
        image_path: str = str(
            Path(self.canvas.directory) / (self.canvas.current_image_name or "")
        )
        annotation_edit: bool = bool(self.canvas.selected_annotation_indices)
        point_edit: bool = bool(self.canvas.selection) and vertex is None
        snapshot: dict[str, Any] | None = (
            self.canvas._annotation_history_snapshot(image_path)
            if annotation_edit
            else None
        )
        if annotation_edit and (
            snapshot is None or self.canvas._annotation_snapshot_unavailable(snapshot)
        ):
            self.controls.feedback.notice = "Cannot edit: the annotation sidecar could not be read. No items changed."
            self.controls.refresh()
            return False
        before: EditState = EditState(
            self.point_snapshot() if point_edit else {}, snapshot
        )
        after: EditState = EditState(
            {
                name: [(point, QtCore.QPointF(position)) for point, position in points]
                for name, points in before.points.items()
            },
            deepcopy(snapshot),
        )
        selected_ids: set[int] = {id(point) for _name, point in self.canvas.selection}
        if point_edit:
            for name, points in after.points.items():
                after.points[name] = [
                    (
                        point,
                        (
                            position + (offset or QtCore.QPointF())
                            if id(point) in selected_ids
                            else position
                        ),
                    )
                    for point, position in points
                    if not (delete and id(point) in selected_ids)
                ]
        source_indices: set[int] = set()
        if after.annotations is not None:
            shapes: list[dict[str, Any]] = after.annotations["shapes"]
            for index in self.canvas.selected_annotation_indices:
                source: int | None = self.canvas.external_annotations[
                    index
                ].source_shape_index
                if source is None or not 0 <= source < len(shapes):
                    self.controls.feedback.notice = "Cannot edit an annotation with no valid sidecar index. No items changed."
                    self.controls.refresh()
                    return False
                source_indices.add(source)
                if not delete:
                    shapes[source]["points"] = [
                        [
                            x
                            + (
                                offset.x()
                                if offset is not None
                                and (vertex is None or number == vertex.vertex)
                                else 0
                            ),
                            y
                            + (
                                offset.y()
                                if offset is not None
                                and (vertex is None or number == vertex.vertex)
                                else 0
                            ),
                        ]
                        for number, (x, y) in enumerate(shapes[source]["points"])
                    ]
            if delete:
                after.annotations["shapes"] = [
                    shape
                    for index, shape in enumerate(shapes)
                    if index not in source_indices
                ]
        event: HistoryEvent = (
            "selection_edit",
            image_path,
            before,
            after,
            annotation_edit,
            point_edit,
        )
        if not apply_selection_state(self.canvas, event, 3):
            self.controls.feedback.notice = (
                "The selection edit could not be saved. No items changed."
            )
            self.controls.refresh()
            return False
        self.canvas._append_history_event(event)
        if not delete:
            self.canvas.selection = [
                (name, point)
                for name, points in before.points.items()
                for point, _position in points
                if id(point) in selected_ids
            ]
            self.canvas.selected_annotation_indices = (
                set(
                    source_index
                    for source_index, annotation in enumerate(
                        self.canvas.external_annotations
                    )
                    if annotation.source_shape_index in source_indices
                )
                if annotation_edit
                else set()
            )
            self.refresh_selection()
        self.controls.feedback.notice = ""
        self.controls.refresh()
        return True

    def delete_selection(self) -> None:
        """Delete the selection using the same undoable action for either type."""
        self.cancel_gesture()
        self.edit(delete=True)

    def move_by_offset(self) -> None:
        """Offer precise source-pixel offsets as an optional group operation."""
        if not self.editable():
            return
        x: float
        y: float
        accepted: bool
        x, accepted = QtWidgets.QInputDialog.getDouble(
            self.view,
            "Move by pixel offset",
            "Horizontal source pixels",
            0,
            -1000000,
            1000000,
            1,
        )
        if not accepted:
            return
        y, accepted = QtWidgets.QInputDialog.getDouble(
            self.view,
            "Move by pixel offset",
            "Vertical source pixels",
            0,
            -1000000,
            1000000,
            1,
        )
        if accepted:
            self.edit(offset=QtCore.QPointF(x, y))

    def context_menu(self, event: QtGui.QContextMenuEvent) -> None:
        """Expose selection actions and retain vertex editing for a single shape.

        Args:
            event: Requested context-menu position.
        """
        self.view.view_activated.emit()
        hit: Target | None = self.choose(event.pos())
        if hit is not None and not self.is_selected(hit):
            self.clear()
            self.toggle(hit)
        if not (self.canvas.selection or self.canvas.selected_annotation_indices):
            return
        self.update_menu()
        vertex_action: QtGui.QAction | None = None
        insert_action: QtGui.QAction | None = None
        if (
            hit is not None
            and hit.kind != "dot"
            and len(self.canvas.selected_annotation_indices) == 1
        ):
            annotation: Annotation = self.canvas.external_annotations[hit.annotation]
            if (
                not annotation.locked
                and annotation.shape_type is not AnnotationShape.POINT
            ):
                if hit.kind == "vertex":
                    vertex_action = self.menu.addAction("Delete vertex")
                else:
                    insert_action = self.menu.addAction("Insert vertex here")
        action: QtGui.QAction | None = self.menu.exec(event.globalPos())
        if action is not None and hit is not None:
            if action is vertex_action:
                self.view.external_annotation_delete_vertex_requested.emit(
                    hit.annotation, hit.vertex
                )
            elif action is insert_action:
                self.view.external_annotation_insert_vertex_requested.emit(
                    hit.annotation, self.view.mapToScene(event.pos())
                )
        for temporary in (vertex_action, insert_action):
            if temporary is not None:
                self.menu.removeAction(temporary)
                temporary.deleteLater()
