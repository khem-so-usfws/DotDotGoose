"""Interactive shape editing for a single DotDotGoose image pane."""

from __future__ import annotations

from enum import Enum
from math import dist, hypot
from typing import TYPE_CHECKING, cast

from PyQt6 import QtCore, QtGui, QtWidgets, sip

from .annotations import Annotation, AnnotationShape, point_in_polygon
from .annotations.reshape_geometry import (
    Location,
    ReshapeResult,
    distinct,
    polygon_area,
    project,
    reshape,
    section,
    valid_shape,
)
from .annotations.model import Point
from .canvas import Canvas
from .central_graphics_view import CentralGraphicsView, InteractionMode

if TYPE_CHECKING:
    from .workspace_controls import WorkspaceControls


class ShapeTool(str, Enum):
    """Tools that change the geometry of an existing annotation."""

    RESHAPE = "Reshape"
    LINE_END = "Trim/Extend"
    VERTICES = "Edit Vertices"


class ShapeEditor(QtCore.QObject):
    """Keep image-local previews separate from committed annotation geometry."""

    def __init__(
        self, controls: WorkspaceControls, view: CentralGraphicsView, canvas: Canvas
    ) -> None:
        """Attach editing and sketch options to an image view.

        Args:
            controls: Shared toolbar and workspace coordinator.
            view: Image view receiving pointer and keyboard input.
            canvas: Scene and annotation storage for this view.
        """
        super().__init__(view)
        self.controls: WorkspaceControls = controls
        self.view: CentralGraphicsView = view
        self.canvas: Canvas = canvas
        self.tool: ShapeTool | None = None
        self.sketch: list[Point] = []
        self.results: list[ReshapeResult] = []
        self.choice: int | None = None
        self.end: int | None = None
        self.trim: Location | None = None
        self.vertices: set[int] = set()
        self.drag_vertex: int | None = None
        self.drag_start: QtCore.QPoint | None = None
        self.tracing: bool = False
        self.trace_shape: Annotation | None = None
        self.trace_start: Location | None = None
        self.graphics: list[QtWidgets.QGraphicsItem] = []
        self.view.annotation_snap = self.snap
        self.view.shape_draft = self.has_draft
        view.viewport().installEventFilter(self)
        view.installEventFilter(self)
        canvas.image_about_to_change.connect(self.stop)

    def target(self) -> tuple[int, Annotation] | None:
        """Return the single unlocked, visible line or polygon selection."""
        indices: set[int] = self.canvas.selected_annotation_indices
        if len(indices) != 1 or self.canvas.selection:
            return None
        index: int = next(iter(indices))
        if not 0 <= index < len(self.canvas.external_annotations):
            return None
        annotation: Annotation = self.canvas.external_annotations[index]
        if (
            annotation.locked
            or annotation.shape_type is AnnotationShape.POINT
            or not self.canvas.annotation_type_visible(annotation.shape_type)
        ):
            return None
        return index, annotation

    def can_trace(self) -> bool:
        """Report whether the current drawing accepts a traced cutline."""
        target: tuple[int, Annotation] | None = self.target()
        return self.controls.mode is InteractionMode.POLYGON or (
            self.tool is ShapeTool.RESHAPE
            and target is not None
            and target[1].shape_type is AnnotationShape.POLYGON
            and self.choice is None
        )

    def has_draft(self) -> bool:
        """Report work that needs to be applied or canceled before leaving."""
        return bool(
            self.sketch
            or self.end is not None
            or self.drag_vertex is not None
            or self.tracing
        )

    def start(self, tool: ShapeTool) -> None:
        """Enter a shape tool and show its starting instructions."""
        self.stop()
        self.tool = tool
        self.redraw()

    def clear_preview(self) -> None:
        """Remove graphics owned by this editor, including after a scene reset."""
        for item in self.graphics:
            if not sip.isdeleted(item) and item.scene() is self.canvas:
                self.canvas.removeItem(item)
        self.graphics.clear()

    def reset_draft(self) -> None:
        """Discard the sketch while retaining the selected editing tool."""
        self.sketch.clear()
        self.results.clear()
        self.choice = None
        self.end = None
        self.trim = None
        self.drag_vertex = None
        self.drag_start = None
        self.tracing = False
        self.trace_shape = None
        self.trace_start = None
        self.clear_preview()

    def stop(self) -> None:
        """Exit shape editing and clear per-annotation selection handles."""
        self.reset_draft()
        self.vertices.clear()
        self.tool = None

    def notice(self, message: str = "") -> None:
        """Show tool-specific feedback in the main window status bar."""
        self.controls.feedback.notice = message
        self.controls.refresh()

    def instructions(self) -> str:
        """Describe the next gesture for the current stage of editing."""
        if self.tracing:
            return (
                "Trace · click where to leave the cutline. Esc cancels tracing."
                if self.trace_start is not None
                else "Trace · click where to join a visible cutline. Esc cancels tracing."
            )
        if self.tool is ShapeTool.VERTICES:
            return "Edit Vertices · drag a vertex, click an edge to insert, Shift+click to select several, Delete to remove."
        if self.tool is ShapeTool.LINE_END:
            if self.end is None:
                return "Trim/Extend · click the endpoint you want to change."
            if not self.results:
                return "Click along the line to trim, or sketch outward to extend. Esc cancels."
            return "Trim/Extend · Enter applies the preview. Esc cancels."
        if self.tool is ShapeTool.RESHAPE:
            if len(self.results) > 1 and self.choice is None:
                return "Reshape · click the polygon area to keep. Esc cancels."
            if self.results:
                return "Reshape · Enter applies the preview. Esc cancels."
            return "Reshape · sketch across the boundary twice, or use Snap to place two joins. Esc cancels."
        return ""

    def tolerance(self) -> float:
        """Convert the standard eight-screen-pixel hit radius to source pixels."""
        transform: QtGui.QTransform = self.view.transform()
        scale: float = hypot(transform.m11(), transform.m12())
        return 8.0 / max(scale, 1e-6)

    def nearest_edge(
        self, annotation: Annotation, point: Point, excluded_vertex: int | None = None
    ) -> Location | None:
        """Find a visible edge within the pointer hit radius.

        Args:
            annotation: Geometry to search, including a polygon's closing edge.
            point: Source-pixel pointer position.
            excluded_vertex: Moving vertex whose incident edges are ignored.

        Returns:
            The projected location if it is close enough to the pointer.
        """
        points: list[Point] = annotation.points
        count: int = len(points)
        closed: bool = annotation.shape_type is AnnotationShape.POLYGON
        nearest: Location | None = None
        distance: float = self.tolerance()
        for index in range(count if closed else count - 1):
            following: int = (index + 1) % count
            if excluded_vertex in (index, following):
                continue
            position, fraction = project(point, points[index], points[following])
            gap: float = dist(point, position)
            if gap <= distance:
                nearest = Location(position, index + fraction)
                distance = gap
        return nearest

    def snap(self, point: QtCore.QPointF) -> QtCore.QPointF:
        """Apply opt-in vertex or edge snapping to the current sketch point."""
        if not self.controls.snap_action.isChecked():
            return point
        xy: Point = (point.x(), point.y())
        target: tuple[int, Annotation] | None = self.target()
        shapes: list[Annotation] = (
            [target[1]]
            if self.tool is not None and target is not None
            else self.canvas.external_annotations
        )
        vertex: Point | None = None
        edge: Location | None = None
        vertex_distance: float = self.tolerance() / 2
        edge_distance: float = self.tolerance()
        for annotation in shapes:
            if not self.canvas.annotation_type_visible(annotation.visibility_type):
                continue
            for index, candidate in enumerate(annotation.points):
                gap: float = dist(xy, candidate)
                if index != self.drag_vertex and gap <= vertex_distance:
                    vertex, vertex_distance = candidate, gap
            candidate_edge: Location | None = self.nearest_edge(
                annotation, xy, self.drag_vertex
            )
            if candidate_edge is not None:
                gap = dist(xy, candidate_edge.point)
                if gap <= edge_distance:
                    edge, edge_distance = candidate_edge, gap
        if vertex is not None:
            return QtCore.QPointF(*vertex)
        return QtCore.QPointF(*edge.point) if edge is not None else point

    def start_trace(self) -> None:
        """Arm the join point for a traced portion of the current sketch."""
        if self.tracing:
            self.cancel_trace()
        elif self.can_trace():
            self.tracing = True
            self.notice()

    def cancel_trace(self) -> None:
        """Return to the current sketch without adding traced vertices."""
        self.tracing = False
        self.trace_shape = None
        self.trace_start = None
        self.redraw()
        self.notice()

    def trace_click(self, point: Point) -> None:
        """Choose the cutline join or append its path to the sketch."""
        if self.trace_start is None:
            candidates: list[tuple[float, Annotation, Location]] = []
            if self.canvas.annotation_type_visible(AnnotationShape.LINE):
                for annotation in self.canvas.external_annotations:
                    if annotation.shape_type is not AnnotationShape.LINE:
                        continue
                    location: Location | None = self.nearest_edge(annotation, point)
                    if location is not None:
                        candidates.append(
                            (dist(point, location.point), annotation, location)
                        )
            if not candidates:
                self.notice("Trace · click closer to an existing visible cutline.")
                return
            _, self.trace_shape, self.trace_start = min(
                candidates, key=lambda hit: hit[0]
            )
            self.redraw()
            self.notice()
            return

        annotation = self.trace_shape
        if annotation is None:
            self.cancel_trace()
            return
        location = self.nearest_edge(annotation, point)
        if location is None or abs(location.order - self.trace_start.order) < 1e-7:
            self.notice("Trace · choose a different position on the same cutline.")
            return
        traced: list[Point] = section(annotation.points, self.trace_start, location)
        self.cancel_trace()
        if self.tool is ShapeTool.RESHAPE:
            self.sketch = distinct(self.sketch + traced)
            self.update_reshape()
        else:
            vertices: list[QtCore.QPointF] = [QtCore.QPointF(x, y) for x, y in traced]
            polygon: list[QtCore.QPointF] = self.view.polygon_points
            if polygon and polygon[-1] == vertices[0]:
                vertices = vertices[1:]
            polygon.extend(vertices)
            self.view._update_polygon_preview(polygon[-1])
        self.notice()

    def update_reshape(self) -> None:
        """Build a live preview from the vertices already placed."""
        target: tuple[int, Annotation] | None = self.target()
        self.results = []
        self.choice = None
        if target is not None:
            try:
                self.results = reshape(
                    target[1].points,
                    self.sketch,
                    target[1].shape_type is AnnotationShape.POLYGON,
                )
            except ValueError:
                # An incomplete sketch is normal until both joins are placed.
                pass
        if len(self.results) == 1:
            self.choice = 0
        self.redraw()

    def pick_polygon(self, point: Point) -> None:
        """Choose the preview under the click, preferring the smaller overlap."""
        matches: list[int] = [
            index
            for index, result in enumerate(self.results)
            if point_in_polygon(point, result.points)
        ]
        if not matches:
            self.notice("Click inside the polygon area you want to keep.")
            return
        self.choice = min(
            matches, key=lambda index: abs(polygon_area(self.results[index].points))
        )
        self.redraw()
        self.notice()

    def line_end_click(self, annotation: Annotation, point: Point) -> None:
        """Select the end, then prepare a trim position or extension sketch."""
        path: list[Point] = distinct(annotation.points)
        if len(path) < 2:
            self.notice("Choose a line with two distinct vertices.")
            return
        if self.end is None:
            nearest: int = min((0, -1), key=lambda index: dist(path[index], point))
            if dist(path[nearest], point) > self.tolerance():
                self.notice("Click closer to the endpoint you want to edit.")
                return
            self.end = nearest
        else:
            if not self.sketch:
                self.trim = self.nearest_edge(annotation, point)
            if self.trim is not None:
                path = annotation.points
                anchor: Location = Location(path[-1], len(path) - 1)
                first: Location = Location(path[0], 0)
                retained: list[Point] = (
                    section(path, self.trim, anchor)
                    if self.end == 0
                    else section(path, first, self.trim)
                )
                removed: list[Point] = (
                    section(path, first, self.trim)
                    if self.end == 0
                    else section(path, self.trim, anchor)
                )
            else:
                self.sketch = distinct([*self.sketch, point])
                retained = distinct(
                    list(reversed(self.sketch)) + path
                    if self.end == 0
                    else path + self.sketch
                )
                removed = []
            self.results = (
                [ReshapeResult(retained, removed)]
                if valid_shape(retained, False) and retained != path
                else []
            )
            self.choice = 0 if self.results else None
        self.redraw()
        self.notice()

    def vertex_click(
        self, annotation: Annotation, point: Point, position: QtCore.QPoint, shift: bool
    ) -> None:
        """Select a vertex to drag, or insert a vertex into a clicked edge."""
        vertices: list[Point] = annotation.points
        index: int = min(
            range(len(vertices)), key=lambda item: dist(vertices[item], point)
        )
        if dist(vertices[index], point) <= self.tolerance():
            if shift:
                self.vertices.symmetric_difference_update({index})
            else:
                self.vertices = {index}
                self.drag_vertex = index
                self.drag_start = position
            self.redraw()
        elif not shift:
            edge: Location | None = self.nearest_edge(annotation, point)
            if edge is not None:
                new_index: int = int(edge.order) + 1
                updated: list[Point] = (
                    vertices[:new_index] + [edge.point] + vertices[new_index:]
                )
                self.commit(updated, {new_index})
            else:
                self.vertices.clear()
                self.redraw()

    def commit(self, points: list[Point], selected: set[int] | None = None) -> None:
        """Validate and save a preview as one project-wide undo operation."""
        target: tuple[int, Annotation] | None = self.target()
        if target is None:
            self.stop()
            self.notice("Select one editable line or polygon.")
            return
        index, annotation = target
        if not valid_shape(points, annotation.shape_type is AnnotationShape.POLYGON):
            self.redraw()
            self.notice(
                "The edit would collapse the shape or cross its polygon boundary. "
                "Adjust the edit and try again."
            )
            return
        if (
            annotation.points != points
            and not self.canvas.replace_external_annotation_points(index, points)
        ):
            self.notice("The annotation edit could not be saved.")
            return
        self.reset_draft()
        self.vertices = selected or set()
        self.redraw()
        self.notice()

    def apply(self) -> None:
        """Apply the chosen preview or explain which sketch step is missing."""
        if self.tracing:
            self.notice("Finish the traced segment or press Esc to leave Trace.")
        elif self.choice is not None:
            self.commit(self.results[self.choice].points)
        elif len(self.results) > 1:
            self.notice("Click the polygon area to keep before applying.")
        elif self.tool is ShapeTool.RESHAPE:
            target: tuple[int, Annotation] | None = self.target()
            if target is not None:
                try:
                    reshape(
                        target[1].points,
                        self.sketch,
                        target[1].shape_type is AnnotationShape.POLYGON,
                    )
                except ValueError as error:
                    self.notice(str(error))
        else:
            self.notice("Choose a new endpoint or sketch an extension before applying.")

    def pointer(self, position: QtCore.QPoint, snap: bool = False) -> Point:
        """Map a viewport position to source-image coordinates."""
        point: QtCore.QPointF = self.view.mapToScene(position)
        if snap:
            point = self.snap(point)
        return point.x(), point.y()

    def editing_press(self, mouse: QtGui.QMouseEvent) -> None:
        """Route a left click to the geometry editor or Trace."""
        position: QtCore.QPoint = mouse.position().toPoint()
        point: Point = self.pointer(position)
        if self.tracing:
            self.trace_click(point)
            return
        target: tuple[int, Annotation] | None = self.target()
        if target is None:
            return
        annotation: Annotation = target[1]
        if self.tool is ShapeTool.VERTICES:
            shift: bool = bool(
                mouse.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
            )
            self.vertex_click(annotation, point, position, shift)
        elif self.tool is ShapeTool.LINE_END:
            self.line_end_click(
                annotation, point if self.end is None else self.pointer(position, True)
            )
        elif len(self.results) > 1:
            self.pick_polygon(point)
        else:
            self.sketch = distinct([*self.sketch, self.pointer(position, True)])
            self.update_reshape()
            self.notice()

    def editing_key(self, key: QtGui.QKeyEvent) -> bool:
        """Handle editor keys while allowing temporary navigation controls."""
        code: int = key.key()
        if code == QtCore.Qt.Key.Key_Escape:
            if self.view.navigation_gesture is not None:
                return False
            if self.tracing:
                self.cancel_trace()
            elif self.has_draft() or self.vertices:
                self.reset_draft()
                self.vertices.clear()
                self.redraw()
                self.notice()
            else:
                self.controls.select_tool(InteractionMode.SELECT)
            return True
        if code in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            if self.tool is not ShapeTool.VERTICES:
                self.apply()
            return True
        if code in (QtCore.Qt.Key.Key_Delete, QtCore.Qt.Key.Key_Backspace):
            target: tuple[int, Annotation] | None = self.target()
            if self.tool is ShapeTool.VERTICES and self.vertices and target is not None:
                self.commit(
                    [
                        point
                        for i, point in enumerate(target[1].points)
                        if i not in self.vertices
                    ]
                )
            elif self.sketch and not self.tracing and self.tool is ShapeTool.RESHAPE:
                self.sketch.pop()
                self.update_reshape()
                self.notice()
            return True
        return False

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Intercept editing gestures while allowing normal Qt navigation."""
        if (self.tool is None and not self.tracing) or sip.isdeleted(self.view):
            return False
        kind: QtCore.QEvent.Type = event.type()
        if kind == QtCore.QEvent.Type.KeyPress:
            return self.editing_key(cast(QtGui.QKeyEvent, event))
        if (
            watched is not self.view.viewport()
            or self.view._active_navigation_override() is not None
            or self.view.navigation_gesture is not None
        ):
            return False
        if kind == QtCore.QEvent.Type.ContextMenu:
            return self.tool is not None or self.tracing
        if kind == QtCore.QEvent.Type.MouseButtonDblClick:
            return self.tool is not None or self.tracing
        if kind == QtCore.QEvent.Type.MouseButtonPress:
            mouse: QtGui.QMouseEvent = cast(QtGui.QMouseEvent, event)
            if mouse.button() == QtCore.Qt.MouseButton.LeftButton:
                self.view.view_activated.emit()
                if not self.view.annotation_target_blocked:
                    self.editing_press(mouse)
                return True
        if kind in (
            QtCore.QEvent.Type.MouseMove,
            QtCore.QEvent.Type.MouseButtonRelease,
        ):
            mouse = cast(QtGui.QMouseEvent, event)
            position: QtCore.QPoint = mouse.position().toPoint()
            if self.drag_vertex is not None and self.drag_start is not None:
                target: tuple[int, Annotation] | None = self.target()
                if target is None:
                    return False
                index: int = self.drag_vertex
                dragged: bool = (
                    position - self.drag_start
                ).manhattanLength() >= QtWidgets.QApplication.startDragDistance()
                points: list[Point] = list(target[1].points)
                if dragged:
                    delta: QtCore.QPointF = self.view.mapToScene(
                        position
                    ) - self.view.mapToScene(self.drag_start)
                    original: QtCore.QPointF = QtCore.QPointF(*points[index])
                    moved: QtCore.QPointF = self.snap(original + delta)
                    points[index] = (moved.x(), moved.y())
                if kind == QtCore.QEvent.Type.MouseMove:
                    self.redraw(points)
                elif mouse.button() == QtCore.Qt.MouseButton.LeftButton:
                    self.drag_vertex = None
                    self.drag_start = None
                    if dragged:
                        self.commit(points, {index})
                    else:
                        self.redraw()
                return True
        return False

    def draw_path(
        self,
        points: list[Point],
        color: str,
        closed: bool = False,
        filled: bool = False,
    ) -> None:
        """Draw a cosmetic preview path and optional translucent polygon fill."""
        if len(points) < 2:
            return
        path: QtGui.QPainterPath = QtGui.QPainterPath(QtCore.QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(QtCore.QPointF(*point))
        if closed:
            path.closeSubpath()
        pen: QtGui.QPen = QtGui.QPen(QtGui.QColor(color), 2.5)
        pen.setCosmetic(True)
        if color == "#ffab47":
            pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        fill: QtGui.QColor = QtGui.QColor(color)
        fill.setAlpha(48)
        item: QtWidgets.QGraphicsPathItem = self.canvas.addPath(
            path, pen, QtGui.QBrush(fill) if filled else QtGui.QBrush()
        )
        item.setZValue(30)
        self.graphics.append(item)

    def marker(self, point: Point, selected: bool = False) -> None:
        """Draw a screen-sized vertex, endpoint, or sketch anchor."""
        marker: QtWidgets.QGraphicsEllipseItem = self.canvas.addEllipse(
            -4,
            -4,
            8,
            8,
            QtGui.QPen(QtGui.QColor("#164353"), 1.5),
            QtGui.QBrush(QtGui.QColor("#47e4ff" if selected else "#f4ffff")),
        )
        marker.setFlag(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
        )
        marker.setPos(*point)
        marker.setZValue(31)
        self.graphics.append(marker)

    def redraw(self, vertices: list[Point] | None = None) -> None:
        """Show only the shape editor graphics needed for the current phase."""
        self.clear_preview()
        target: tuple[int, Annotation] | None = self.target()
        if target is not None:
            annotation: Annotation = target[1]
            closed: bool = annotation.shape_type is AnnotationShape.POLYGON
            if self.tool is ShapeTool.VERTICES:
                points: list[Point] = (
                    vertices if vertices is not None else annotation.points
                )
                if vertices is not None:
                    self.draw_path(points, "#47e4ff", closed)
                for index, point in enumerate(points):
                    self.marker(point, index in self.vertices)
            elif self.choice is not None:
                result: ReshapeResult = self.results[self.choice]
                self.draw_path(result.removed, "#ffab47")
                self.draw_path(result.points, "#47e4ff", closed, closed)
            elif self.results:
                for result, color in zip(self.results, ("#47e4ff", "#e8abff")):
                    self.draw_path(result.points, color, closed, closed)
            elif self.tool is ShapeTool.LINE_END:
                endpoints: tuple[Point, Point] = (
                    annotation.points[0],
                    annotation.points[-1],
                )
                for index, point in zip((0, -1), endpoints):
                    self.marker(point, self.end == index)
            else:
                self.draw_path(self.sketch, "#47e4ff")
                for point in self.sketch:
                    self.marker(point, True)
        if self.trace_start is not None and self.trace_shape is not None:
            self.draw_path(self.trace_shape.points, "#47e4ff")
            self.marker(self.trace_start.point, True)
