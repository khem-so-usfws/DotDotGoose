# -*- coding: utf-8 -*-
#
# DotDotGoose
# Author: Peter Ersts (ersts@amnh.org)
#
# --------------------------------------------------------------------------
#
# This file is part of the DotDotGoose application.
# DotDotGoose was forked from the Neural Network Image Classifier (Nenetic).
#
# DotDotGoose is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# DotDotGoose is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with with this software.  If not, see <http://www.gnu.org/licenses/>.
#
# --------------------------------------------------------------------------
from enum import Enum

from PyQt6 import QtCore, QtGui, QtWidgets

from .annotations import AnnotationShape, load_annotation_style


class InteractionMode(str, Enum):
    """Mouse interaction modes supported by the central image view."""

    COUNT = "count"
    SELECT = "select"
    POINT = "point"
    LINE = "line"
    POLYGON = "polygon"


class CentralGraphicsView(QtWidgets.QGraphicsView):
    add_point = QtCore.pyqtSignal(QtCore.QPointF)
    drop_complete = QtCore.pyqtSignal(list)
    region_selected = QtCore.pyqtSignal(QtCore.QRectF)
    delete_selection = QtCore.pyqtSignal()
    relabel_selection = QtCore.pyqtSignal()
    toggle_points = QtCore.pyqtSignal()
    toggle_grid = QtCore.pyqtSignal()
    switch_class = QtCore.pyqtSignal(int)
    annotation_point_completed = QtCore.pyqtSignal(QtCore.QPointF)
    line_completed = QtCore.pyqtSignal(list)
    polygon_completed = QtCore.pyqtSignal(list)
    annotation_mode_changed = QtCore.pyqtSignal(str)
    external_annotation_selected = QtCore.pyqtSignal(int)
    external_annotation_vertex_moved = QtCore.pyqtSignal(int, int, QtCore.QPointF)
    external_annotation_vertex_move_finished = QtCore.pyqtSignal(int, int)
    external_annotation_moved = QtCore.pyqtSignal(int, QtCore.QPointF)
    external_annotation_move_finished = QtCore.pyqtSignal(int)
    external_annotation_insert_vertex_requested = QtCore.pyqtSignal(
        int, QtCore.QPointF
    )
    external_annotation_delete_vertex_requested = QtCore.pyqtSignal(int, int)
    external_annotation_delete_requested = QtCore.pyqtSignal()
    external_annotation_selection_cleared = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        QtWidgets.QGraphicsView.__init__(self, parent)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.shift = False
        self.ctrl = False
        self.alt = False
        self.delay = 0
        self.interaction_mode: InteractionMode = InteractionMode.COUNT
        self.line_points: list[QtCore.QPointF] = []
        self.line_preview_item: QtWidgets.QGraphicsPathItem | None = None
        self.polygon_points: list[QtCore.QPointF] = []
        self.polygon_preview_item: QtWidgets.QGraphicsPathItem | None = None
        self.dragging_annotation_vertex: tuple[int, int] | None = None
        self.dragging_annotation_index: int | None = None
        self.dragging_annotation_last_point: QtCore.QPointF | None = None
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

    def enterEvent(self, event: QtCore.QEvent) -> None:
        self.setFocus()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        event.setAccepted(True)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        pass

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        if len(event.mimeData().urls()) > 0:
            self.drop_complete.emit(event.mimeData().urls())

    def image_loaded(self, directory: str, file_name: str) -> None:
        self.resetTransform()
        self.fitInView(self.scene().itemsBoundingRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        self.setSceneRect(self.scene().itemsBoundingRect())

    def cancel_annotation(self) -> None:
        """Cancel any annotation interaction and return to count mode."""
        was_selection_mode: bool = self.interaction_mode is InteractionMode.SELECT
        self._clear_line_preview()
        self._clear_polygon_preview()
        self.line_points = []
        self.polygon_points = []
        self.dragging_annotation_vertex = None
        self.dragging_annotation_index = None
        self.dragging_annotation_last_point = None
        self.interaction_mode = InteractionMode.COUNT
        if was_selection_mode:
            self.external_annotation_selection_cleared.emit()
        self.annotation_mode_changed.emit(self.interaction_mode.value)

    def reset_annotation_state(self, directory: str, file_name: str) -> None:
        """Discard transient annotation state after an image change.

        Args:
            directory: Active image directory supplied by the canvas signal.
            file_name: Active image filename supplied by the canvas signal.
        """
        del directory, file_name
        self.line_preview_item = None
        self.polygon_preview_item = None
        self.line_points = []
        self.polygon_points = []
        self.dragging_annotation_vertex = None
        self.dragging_annotation_index = None
        self.dragging_annotation_last_point = None
        self.interaction_mode = InteractionMode.COUNT
        self.annotation_mode_changed.emit(self.interaction_mode.value)


    def start_annotation_selection(self) -> None:
        """Enter native annotation selection/edit mode."""
        self.cancel_annotation()
        self.interaction_mode = InteractionMode.SELECT
        self.annotation_mode_changed.emit(self.interaction_mode.value)


    def finish_line_annotation(self) -> None:
        """Finish the current cutline when it contains valid geometry."""
        if self.interaction_mode is not InteractionMode.LINE:
            return
        if len(self.line_points) < 2:
            return

        completed_points: list[QtCore.QPointF] = [
            QtCore.QPointF(point) for point in self.line_points
        ]
        self._clear_line_preview()
        self.line_points = []
        self.interaction_mode = InteractionMode.COUNT
        self.annotation_mode_changed.emit(self.interaction_mode.value)
        self.line_completed.emit(completed_points)

    def start_landmark_annotation(self) -> None:
        """Enter point annotation mode for a new landmark."""
        self.cancel_annotation()
        self.interaction_mode = InteractionMode.POINT
        self.annotation_mode_changed.emit(self.interaction_mode.value)

    def start_line_annotation(self) -> None:
        """Enter line annotation mode for a new cutline."""
        self.cancel_annotation()
        self.line_points = []
        self.interaction_mode = InteractionMode.LINE
        self.annotation_mode_changed.emit(self.interaction_mode.value)

    def finish_polygon_annotation(self) -> None:
        """Finish the current polygon when it contains valid geometry."""
        if self.interaction_mode is not InteractionMode.POLYGON:
            return
        if len(self.polygon_points) < 3:
            return

        completed_points: list[QtCore.QPointF] = [
            QtCore.QPointF(point) for point in self.polygon_points
        ]
        self._clear_polygon_preview()
        self.polygon_points = []
        self.interaction_mode = InteractionMode.COUNT
        self.annotation_mode_changed.emit(self.interaction_mode.value)
        self.polygon_completed.emit(completed_points)

    def start_polygon_annotation(self) -> None:
        """Enter polygon annotation mode for a new count region."""
        self.cancel_annotation()
        self.polygon_points = []
        self.interaction_mode = InteractionMode.POLYGON
        self.annotation_mode_changed.emit(self.interaction_mode.value)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.cancel_annotation()
            return
        if (
            event.key() in {QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter}
            and self.interaction_mode in {InteractionMode.LINE, InteractionMode.POLYGON}
        ):
            if self.interaction_mode is InteractionMode.LINE:
                self.finish_line_annotation()
            else:
                self.finish_polygon_annotation()
            return
        if event.key() == QtCore.Qt.Key.Key_Alt:
            self.alt = True
        elif event.key() == QtCore.Qt.Key.Key_Control:
            self.ctrl = True
        elif event.key() == QtCore.Qt.Key.Key_Shift:
            self.shift = True
        elif event.key() == QtCore.Qt.Key.Key_Delete or event.key() == QtCore.Qt.Key.Key_Backspace:
            if self.interaction_mode is InteractionMode.SELECT:
                self.external_annotation_delete_requested.emit()
            else:
                self.delete_selection.emit()
        elif event.key() == QtCore.Qt.Key.Key_R:
            self.relabel_selection.emit()
        elif event.key() == QtCore.Qt.Key.Key_D:
            self.toggle_points.emit()
        elif event.key() == QtCore.Qt.Key.Key_G:
            self.toggle_grid.emit()
        elif event.key() == QtCore.Qt.Key.Key_1:
            self.switch_class.emit(0)
        elif event.key() == QtCore.Qt.Key.Key_2:
            self.switch_class.emit(1)
        elif event.key() == QtCore.Qt.Key.Key_3:
            self.switch_class.emit(2)
        elif event.key() == QtCore.Qt.Key.Key_4:
            self.switch_class.emit(3)
        elif event.key() == QtCore.Qt.Key.Key_5:
            self.switch_class.emit(4)
        elif event.key() == QtCore.Qt.Key.Key_6:
            self.switch_class.emit(5)
        elif event.key() == QtCore.Qt.Key.Key_7:
            self.switch_class.emit(6)
        elif event.key() == QtCore.Qt.Key.Key_8:
            self.switch_class.emit(7)
        elif event.key() == QtCore.Qt.Key.Key_9:
            self.switch_class.emit(8)
        elif event.key() == QtCore.Qt.Key.Key_0:
            self.switch_class.emit(9)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_Alt:
            self.alt = False
        elif event.key() == QtCore.Qt.Key.Key_Control:
            self.ctrl = False
        elif event.key() == QtCore.Qt.Key.Key_Shift:
            self.shift = False

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        """Finish a line or polygon on a left-button double-click."""
        if (
            self.interaction_mode in {InteractionMode.LINE, InteractionMode.POLYGON}
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            if self.interaction_mode is InteractionMode.LINE:
                self.finish_line_annotation()
            else:
                self.finish_polygon_annotation()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if (
            self.interaction_mode is InteractionMode.SELECT
            and self.dragging_annotation_vertex is not None
        ):
            annotation_index: int
            vertex_index: int
            annotation_index, vertex_index = self.dragging_annotation_vertex
            point: QtCore.QPointF = self.mapToScene(event.position().toPoint())
            self.external_annotation_vertex_moved.emit(
                annotation_index, vertex_index, point
            )
            event.accept()
            return
        if (
            self.interaction_mode is InteractionMode.SELECT
            and self.dragging_annotation_index is not None
            and self.dragging_annotation_last_point is not None
        ):
            point: QtCore.QPointF = self.mapToScene(event.position().toPoint())
            delta: QtCore.QPointF = point - self.dragging_annotation_last_point
            self.dragging_annotation_last_point = QtCore.QPointF(point)
            self.external_annotation_moved.emit(
                self.dragging_annotation_index, delta
            )
            event.accept()
            return
        if self.interaction_mode is InteractionMode.LINE:
            self._update_line_preview(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self.interaction_mode is InteractionMode.POLYGON:
            self._update_polygon_preview(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        QtWidgets.QGraphicsView.mouseMoveEvent(self, event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.interaction_mode is InteractionMode.SELECT:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                item: QtWidgets.QGraphicsItem | None = self.itemAt(
                    event.position().toPoint()
                )
                if item is None:
                    self.external_annotation_selected.emit(-1)
                    event.accept()
                    return

                item_kind: object = item.data(0)
                if item_kind == "ddg_external_annotation_handle":
                    annotation_index: int = int(item.data(1))
                    vertex_index: int = int(item.data(2))
                    self.dragging_annotation_vertex = (
                        annotation_index,
                        vertex_index,
                    )
                    self.external_annotation_selected.emit(annotation_index)
                    event.accept()
                    return
                if item_kind == "ddg_external_annotation":
                    annotation_index: int = int(item.data(1))
                    self.external_annotation_selected.emit(annotation_index)
                    self.dragging_annotation_index = annotation_index
                    self.dragging_annotation_last_point = self.mapToScene(
                        event.position().toPoint()
                    )
                    event.accept()
                    return

                self.external_annotation_selected.emit(-1)
                event.accept()
            return
        if self.interaction_mode is InteractionMode.POINT:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                point: QtCore.QPointF = self.mapToScene(event.position().toPoint())
                self.interaction_mode = InteractionMode.COUNT
                self.annotation_mode_changed.emit(self.interaction_mode.value)
                self.annotation_point_completed.emit(QtCore.QPointF(point))
                event.accept()
            return
        if self.interaction_mode is InteractionMode.LINE:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self._add_line_vertex(self.mapToScene(event.position().toPoint()))
                event.accept()
            return
        if self.interaction_mode is InteractionMode.POLYGON:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self._add_polygon_vertex(self.mapToScene(event.position().toPoint()))
                event.accept()
            return
        if self.ctrl:
            self.add_point.emit(self.mapToScene(event.pos()))
        elif self.shift:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)
            QtWidgets.QGraphicsView.mousePressEvent(self, event)
        else:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
            QtWidgets.QGraphicsView.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if (
            self.interaction_mode is InteractionMode.SELECT
            and self.dragging_annotation_vertex is not None
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            annotation_index: int
            vertex_index: int
            annotation_index, vertex_index = self.dragging_annotation_vertex
            self.dragging_annotation_vertex = None
            self.external_annotation_vertex_move_finished.emit(
                annotation_index, vertex_index
            )
            event.accept()
            return
        if (
            self.interaction_mode is InteractionMode.SELECT
            and self.dragging_annotation_index is not None
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            annotation_index: int = self.dragging_annotation_index
            self.dragging_annotation_index = None
            self.dragging_annotation_last_point = None
            self.external_annotation_move_finished.emit(annotation_index)
            event.accept()
            return
        if self.dragMode() == QtWidgets.QGraphicsView.DragMode.RubberBandDrag:
            rect = self.rubberBandRect()
            self.region_selected.emit(self.mapToScene(rect).boundingRect())
            QtWidgets.QGraphicsView.mouseReleaseEvent(self, event)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        """Offer vertex-edit operations while annotation selection is active.

        Args:
            event: Graphics-view context-menu event.
        """
        if self.interaction_mode is not InteractionMode.SELECT:
            super().contextMenuEvent(event)
            return

        item: QtWidgets.QGraphicsItem | None = self.itemAt(event.pos())
        if item is None:
            return

        item_kind: object = item.data(0)
        menu: QtWidgets.QMenu = QtWidgets.QMenu(self)
        if item_kind == "ddg_external_annotation_handle":
            annotation_index: int = int(item.data(1))
            vertex_index: int = int(item.data(2))
            shape_type: str = str(item.data(3) or "")
            self.external_annotation_selected.emit(annotation_index)
            if shape_type != AnnotationShape.POINT.value:
                delete_vertex_action: QtGui.QAction = menu.addAction(
                    self.tr("Delete Vertex")
                )
                chosen_action: QtGui.QAction | None = menu.exec(event.globalPos())
                if chosen_action is delete_vertex_action:
                    self.external_annotation_delete_vertex_requested.emit(
                        annotation_index, vertex_index
                    )
            return

        if item_kind != "ddg_external_annotation":
            return

        annotation_index = int(item.data(1))
        shape_type = str(item.data(3) or "")
        self.external_annotation_selected.emit(annotation_index)
        insert_vertex_action: QtGui.QAction | None = None
        if shape_type in {
            AnnotationShape.LINE.value,
            AnnotationShape.POLYGON.value,
        }:
            insert_vertex_action = menu.addAction(self.tr("Insert Vertex Here"))
        delete_annotation_action: QtGui.QAction = menu.addAction(
            self.tr("Delete Annotation")
        )
        chosen_action = menu.exec(event.globalPos())
        if insert_vertex_action is not None and chosen_action is insert_vertex_action:
            scene_point: QtCore.QPointF = self.mapToScene(event.pos())
            self.external_annotation_insert_vertex_requested.emit(
                annotation_index, scene_point
            )
        elif chosen_action is delete_annotation_action:
            self.external_annotation_delete_requested.emit()


    def _add_line_vertex(self, point: QtCore.QPointF) -> None:
        """Add one vertex to the in-progress cutline.

        Args:
            point: Scene/source-image coordinate of the new vertex.
        """
        self.line_points.append(QtCore.QPointF(point))
        self._update_line_preview(point)

    def _clear_line_preview(self) -> None:
        """Remove the temporary in-progress cutline graphics item."""
        if self.line_preview_item is not None:
            scene: QtWidgets.QGraphicsScene | None = self.scene()
            if scene is not None:
                scene.removeItem(self.line_preview_item)
            self.line_preview_item = None

    def _update_line_preview(self, cursor_point: QtCore.QPointF) -> None:
        """Redraw the temporary cutline path through current vertices.

        Args:
            cursor_point: Current scene coordinate used for the preview segment.
        """
        self._clear_line_preview()
        if len(self.line_points) == 0:
            return

        path: QtGui.QPainterPath = QtGui.QPainterPath(self.line_points[0])
        point: QtCore.QPointF
        for point in self.line_points[1:]:
            path.lineTo(point)
        path.lineTo(cursor_point)

        style = load_annotation_style(AnnotationShape.LINE)
        pen: QtGui.QPen = QtGui.QPen(
            QtGui.QColor(style.color),
            style.width,
            QtCore.Qt.PenStyle.DashLine,
        )
        scene: QtWidgets.QGraphicsScene | None = self.scene()
        if scene is not None:
            self.line_preview_item = scene.addPath(path, pen)
            self.line_preview_item.setZValue(10.0)

    def _add_polygon_vertex(self, point: QtCore.QPointF) -> None:
        """Add one vertex to the in-progress polygon.

        Args:
            point: Scene/source-image coordinate of the new vertex.
        """
        self.polygon_points.append(QtCore.QPointF(point))
        self._update_polygon_preview(point)

    def _clear_polygon_preview(self) -> None:
        """Remove the temporary in-progress polygon graphics item."""
        if self.polygon_preview_item is not None:
            scene: QtWidgets.QGraphicsScene | None = self.scene()
            if scene is not None:
                scene.removeItem(self.polygon_preview_item)
            self.polygon_preview_item = None

    def _update_polygon_preview(self, cursor_point: QtCore.QPointF) -> None:
        """Redraw the temporary polygon path through current vertices.

        Args:
            cursor_point: Current scene coordinate used for the preview segment.
        """
        self._clear_polygon_preview()
        if len(self.polygon_points) == 0:
            return

        path: QtGui.QPainterPath = QtGui.QPainterPath(self.polygon_points[0])
        point: QtCore.QPointF
        for point in self.polygon_points[1:]:
            path.lineTo(point)
        path.lineTo(cursor_point)
        if len(self.polygon_points) >= 2:
            path.lineTo(self.polygon_points[0])

        style = load_annotation_style(AnnotationShape.POLYGON)
        pen: QtGui.QPen = QtGui.QPen(
            QtGui.QColor(style.color),
            style.width,
            QtCore.Qt.PenStyle.DashLine,
        )
        scene: QtWidgets.QGraphicsScene | None = self.scene()
        if scene is not None:
            self.polygon_preview_item = scene.addPath(path, pen)
            self.polygon_preview_item.setZValue(10.0)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        self.resize_image()

    def resize_image(self) -> None:
        vsb = self.verticalScrollBar().isVisible()
        hsb = self.horizontalScrollBar().isVisible()
        if not (vsb or hsb):
            self.fitInView(self.scene().itemsBoundingRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            self.setSceneRect(self.scene().itemsBoundingRect())

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if len(self.scene().items()) > 0:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()

    def zoom_in(self) -> None:
        self.scale(1.1, 1.1)
        # Fix for MacOS and PyQt5 > v5.10
        self.repaint()

    def zoom_out(self) -> None:
        self.scale(0.9, 0.9)
        # Fix for MacOS and PyQt5 > v5.10
        self.repaint()
