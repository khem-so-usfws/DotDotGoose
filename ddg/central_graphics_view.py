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


class NavigationOverride(str, Enum):
    """Temporary ArcGIS-style navigation overrides."""

    PAN = "pan"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"


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
    external_annotation_properties_requested = QtCore.pyqtSignal()
    external_annotation_lock_requested = QtCore.pyqtSignal(bool)
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
        self.dragging_annotation_vertex_changed: bool = False
        self.dragging_annotation_index: int | None = None
        self.dragging_annotation_changed: bool = False
        self.dragging_annotation_last_point: QtCore.QPointF | None = None
        self.navigation_keys_down: list[NavigationOverride] = []
        self.navigation_gesture: NavigationOverride | None = None
        self.navigation_press_position: QtCore.QPoint | None = None
        self.zoom_rubber_band: QtWidgets.QRubberBand = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Shape.Rectangle, self.viewport()
        )
        self.count_click_press_position: QtCore.QPoint | None = None
        self.count_click_scene_point: QtCore.QPointF | None = None
        self.count_click_moved: bool = False
        self.count_click_threshold_px: int = 4
        self.setViewportUpdateMode(
            QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        )

    def enterEvent(self, event: QtCore.QEvent) -> None:
        self.setFocus()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        """Clear cached modifier state when the view loses focus.

        Modal dialogs can receive focus before key-release events return to the
        graphics view. Clearing cached modifier and C/Z/X navigation state
        prevents a stale key from leaking into later mouse behavior.

        Args:
            event: Qt focus-out event.
        """
        self.ctrl = False
        self.shift = False
        self.alt = False
        self._clear_navigation_state()
        self._cancel_pending_count_click()
        super().focusOutEvent(event)

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
        self._cancel_pending_count_click()
        self._clear_line_preview()
        self._clear_polygon_preview()
        self.line_points = []
        self.polygon_points = []
        self.dragging_annotation_vertex = None
        self.dragging_annotation_vertex_changed = False
        self.dragging_annotation_index = None
        self.dragging_annotation_changed = False
        self.dragging_annotation_last_point = None
        self.interaction_mode = InteractionMode.COUNT
        if was_selection_mode:
            self.external_annotation_selection_cleared.emit()
        self.annotation_mode_changed.emit(self.interaction_mode.value)

    def prepare_for_image_change(self) -> None:
        """Release transient annotation graphics before the scene is cleared.

        ``QGraphicsScene.clear()`` destroys the underlying C++ items.  Preview
        item references therefore need to be released before the canvas clears
        the scene during image navigation.
        """
        self._clear_line_preview()
        self._clear_polygon_preview()
        self.line_points = []
        self.polygon_points = []
        self.dragging_annotation_vertex = None
        self.dragging_annotation_vertex_changed = False
        self.dragging_annotation_index = None
        self.dragging_annotation_changed = False
        self.dragging_annotation_last_point = None
        self._clear_navigation_state()
        self._cancel_pending_count_click()
        self.interaction_mode = InteractionMode.COUNT
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
        self.dragging_annotation_vertex_changed = False
        self.dragging_annotation_index = None
        self.dragging_annotation_changed = False
        self.dragging_annotation_last_point = None
        self._clear_navigation_state()
        self._cancel_pending_count_click()
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

    @staticmethod
    def _navigation_override_for_key(key: int) -> NavigationOverride | None:
        """Map a keyboard key to its temporary navigation override.

        Args:
            key: Qt key code.

        Returns:
            Navigation override for C, Z, or X; otherwise ``None``.
        """
        mapping: dict[int, NavigationOverride] = {
            int(QtCore.Qt.Key.Key_C): NavigationOverride.PAN,
            int(QtCore.Qt.Key.Key_Z): NavigationOverride.ZOOM_IN,
            int(QtCore.Qt.Key.Key_X): NavigationOverride.ZOOM_OUT,
        }
        return mapping.get(int(key))

    def _active_navigation_override(self) -> NavigationOverride | None:
        """Return the most recently pressed temporary navigation key."""
        if not self.navigation_keys_down:
            return None
        return self.navigation_keys_down[-1]

    def _push_navigation_override(self, override: NavigationOverride) -> None:
        """Activate a temporary navigation override until its key is released.

        Args:
            override: Navigation operation associated with the pressed key.
        """
        self.navigation_keys_down = [
            item for item in self.navigation_keys_down if item is not override
        ]
        self.navigation_keys_down.append(override)
        self._cancel_pending_count_click()
        self._update_navigation_cursor()

    def _release_navigation_override(self, override: NavigationOverride) -> None:
        """Release one temporary navigation override.

        Args:
            override: Navigation operation associated with the released key.
        """
        self.navigation_keys_down = [
            item for item in self.navigation_keys_down if item is not override
        ]
        self._update_navigation_cursor()

    def _update_navigation_cursor(self) -> None:
        """Update the viewport cursor for the current navigation override."""
        override: NavigationOverride | None = self._active_navigation_override()
        if self.navigation_gesture is NavigationOverride.PAN:
            self.viewport().setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        elif override is NavigationOverride.PAN:
            self.viewport().setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        elif override in {NavigationOverride.ZOOM_IN, NavigationOverride.ZOOM_OUT}:
            self.viewport().setCursor(QtCore.Qt.CursorShape.CrossCursor)
        else:
            self.viewport().unsetCursor()

    def _cancel_navigation_gesture(self) -> None:
        """Cancel the active mouse gesture but preserve held navigation keys."""
        self.navigation_gesture = None
        self.navigation_press_position = None
        self.zoom_rubber_band.hide()
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self._update_navigation_cursor()

    def _clear_navigation_state(self) -> None:
        """Cancel temporary navigation state without changing annotation mode."""
        self.navigation_keys_down = []
        self._cancel_navigation_gesture()
        self.viewport().unsetCursor()

    def _start_navigation_gesture(
        self, event: QtGui.QMouseEvent, override: NavigationOverride
    ) -> None:
        """Start a C/Z/X mouse gesture.

        Args:
            event: Mouse press event that begins the gesture.
            override: Active temporary navigation operation.
        """
        self.navigation_gesture = override
        self.navigation_press_position = event.position().toPoint()
        self._cancel_pending_count_click()
        if override is NavigationOverride.PAN:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
            QtWidgets.QGraphicsView.mousePressEvent(self, event)
        else:
            origin: QtCore.QPoint = self.navigation_press_position
            self.zoom_rubber_band.setGeometry(QtCore.QRect(origin, origin))
            self.zoom_rubber_band.show()
            event.accept()
        self._update_navigation_cursor()

    def _update_navigation_gesture(self, event: QtGui.QMouseEvent) -> bool:
        """Update an active temporary navigation gesture.

        Args:
            event: Mouse move event.

        Returns:
            ``True`` when the event was consumed by navigation.
        """
        if self.navigation_gesture is None:
            return False
        if self.navigation_gesture is NavigationOverride.PAN:
            QtWidgets.QGraphicsView.mouseMoveEvent(self, event)
        elif self.navigation_press_position is not None:
            rectangle: QtCore.QRect = QtCore.QRect(
                self.navigation_press_position, event.position().toPoint()
            ).normalized()
            self.zoom_rubber_band.setGeometry(rectangle)
            event.accept()
        return True

    def _finish_navigation_gesture(self, event: QtGui.QMouseEvent) -> bool:
        """Finish a temporary C/Z/X navigation gesture.

        Args:
            event: Mouse release event.

        Returns:
            ``True`` when the event was consumed by navigation.
        """
        override: NavigationOverride | None = self.navigation_gesture
        if override is None or event.button() != QtCore.Qt.MouseButton.LeftButton:
            return False

        if override is NavigationOverride.PAN:
            QtWidgets.QGraphicsView.mouseReleaseEvent(self, event)
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        else:
            origin: QtCore.QPoint | None = self.navigation_press_position
            self.zoom_rubber_band.hide()
            if origin is not None:
                rectangle: QtCore.QRect = QtCore.QRect(
                    origin, event.position().toPoint()
                ).normalized()
                self._apply_zoom_rectangle(
                    rectangle, zoom_in=override is NavigationOverride.ZOOM_IN
                )
            event.accept()

        self.navigation_gesture = None
        self.navigation_press_position = None
        self._update_navigation_cursor()
        return True

    def _apply_zoom_rectangle(self, rectangle: QtCore.QRect, zoom_in: bool) -> None:
        """Apply a rectangle zoom without changing the current interaction tool.

        Args:
            rectangle: Drag rectangle in viewport coordinates.
            zoom_in: ``True`` for Z-drag zoom in, ``False`` for X-drag zoom out.
        """
        if rectangle.width() < 4 or rectangle.height() < 4:
            return
        if self.scene() is None or not self.scene().items():
            return

        scene_rectangle: QtCore.QRectF = self.mapToScene(rectangle).boundingRect()
        if zoom_in:
            if scene_rectangle.width() <= 0.0 or scene_rectangle.height() <= 0.0:
                return
            self.fitInView(
                scene_rectangle, QtCore.Qt.AspectRatioMode.KeepAspectRatio
            )
        else:
            viewport_rectangle: QtCore.QRect = self.viewport().rect()
            if viewport_rectangle.width() <= 0 or viewport_rectangle.height() <= 0:
                return
            factor: float = max(
                rectangle.width() / viewport_rectangle.width(),
                rectangle.height() / viewport_rectangle.height(),
            )
            factor = max(0.1, min(1.0, factor))
            if factor >= 1.0:
                return
            center: QtCore.QPointF = self.mapToScene(rectangle.center())
            self.scale(factor, factor)
            self.centerOn(center)
        self.repaint()

    def _cancel_pending_count_click(self) -> None:
        """Clear an unfinished click-to-add count-point gesture."""
        self.count_click_press_position = None
        self.count_click_scene_point = None
        self.count_click_moved = False

    def _start_pending_count_click(self, event: QtGui.QMouseEvent) -> None:
        """Record a possible click-to-add point gesture.

        Args:
            event: Left-button press in normal count mode.
        """
        self.count_click_press_position = event.position().toPoint()
        self.count_click_scene_point = self.mapToScene(event.position().toPoint())
        self.count_click_moved = False
        event.accept()

    def _update_pending_count_click(self, event: QtGui.QMouseEvent) -> bool:
        """Track mouse movement so a drag is never mistaken for a point click.

        Args:
            event: Mouse move event.

        Returns:
            ``True`` when a pending count click consumed the event.
        """
        origin: QtCore.QPoint | None = self.count_click_press_position
        if origin is None:
            return False
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            delta: QtCore.QPoint = event.position().toPoint() - origin
            if delta.manhattanLength() > self.count_click_threshold_px:
                self.count_click_moved = True
        event.accept()
        return True

    def _finish_pending_count_click(self, event: QtGui.QMouseEvent) -> bool:
        """Emit a count point only for a true click rather than a drag.

        Args:
            event: Mouse release event.

        Returns:
            ``True`` when a pending count gesture consumed the event.
        """
        if (
            self.count_click_press_position is None
            or event.button() != QtCore.Qt.MouseButton.LeftButton
        ):
            return False
        point: QtCore.QPointF | None = self.count_click_scene_point
        origin: QtCore.QPoint = self.count_click_press_position
        release_delta: QtCore.QPoint = event.position().toPoint() - origin
        moved: bool = (
            self.count_click_moved
            or release_delta.manhattanLength() > self.count_click_threshold_px
        )
        self._cancel_pending_count_click()
        event.accept()
        if not moved and point is not None:
            self.add_point.emit(QtCore.QPointF(point))
        return True

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_Escape:
            if self.navigation_gesture is not None:
                # Cancel the temporary navigation gesture without discarding an
                # unfinished annotation. The held C/Z/X override remains active
                # until its key is released.
                self._cancel_navigation_gesture()
                event.accept()
                return
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

        navigation_override: NavigationOverride | None = (
            self._navigation_override_for_key(event.key())
        )
        if (
            navigation_override is not None
            and event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier
        ):
            if not event.isAutoRepeat():
                self._push_navigation_override(navigation_override)
            event.accept()
            return

        if event.key() == QtCore.Qt.Key.Key_Alt:
            self.alt = True
        elif event.key() == QtCore.Qt.Key.Key_Control:
            self.ctrl = True
        elif event.key() == QtCore.Qt.Key.Key_Shift:
            self.shift = True
        elif event.key() in {
            QtCore.Qt.Key.Key_Delete,
            QtCore.Qt.Key.Key_Backspace,
        }:
            if self.interaction_mode is InteractionMode.SELECT:
                self.external_annotation_delete_requested.emit()
            elif self.interaction_mode is InteractionMode.COUNT:
                self.delete_selection.emit()
        elif self.interaction_mode is not InteractionMode.COUNT:
            # Count-point shortcuts should not mutate point data while an
            # annotation drawing/edit mode owns the keyboard interaction.
            return
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
        navigation_override: NavigationOverride | None = (
            self._navigation_override_for_key(event.key())
        )
        if navigation_override is not None:
            if not event.isAutoRepeat():
                self._release_navigation_override(navigation_override)
            event.accept()
            return
        if event.key() == QtCore.Qt.Key.Key_Alt:
            self.alt = False
        elif event.key() == QtCore.Qt.Key.Key_Control:
            self.ctrl = False
        elif event.key() == QtCore.Qt.Key.Key_Shift:
            self.shift = False

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        """Finish a line or polygon on a left-button double-click."""
        if self._active_navigation_override() is not None:
            event.accept()
            return
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
        if self._update_navigation_gesture(event):
            return
        if self._update_pending_count_click(event):
            return
        if (
            self.interaction_mode is InteractionMode.SELECT
            and self.dragging_annotation_vertex is not None
        ):
            annotation_index: int
            vertex_index: int
            annotation_index, vertex_index = self.dragging_annotation_vertex
            point: QtCore.QPointF = self.mapToScene(event.position().toPoint())
            self.dragging_annotation_vertex_changed = True
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
            if delta.x() != 0.0 or delta.y() != 0.0:
                self.dragging_annotation_changed = True
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
        navigation_override: NavigationOverride | None = (
            self._active_navigation_override()
        )
        if (
            navigation_override is not None
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            self._start_navigation_gesture(event, navigation_override)
            return

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
                    self.dragging_annotation_vertex_changed = False
                    self.external_annotation_selected.emit(annotation_index)
                    event.accept()
                    return
                if item_kind == "ddg_external_annotation":
                    annotation_index: int = int(item.data(1))
                    locked: bool = bool(item.data(4))
                    self.external_annotation_selected.emit(annotation_index)
                    if not locked:
                        self.dragging_annotation_index = annotation_index
                        self.dragging_annotation_changed = False
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

        shift_pressed: bool = bool(
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
        )
        if (
            shift_pressed
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            self._cancel_pending_count_click()
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)
            QtWidgets.QGraphicsView.mousePressEvent(self, event)
            return
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Plain click is the primary count action. Ctrl+click remains a
            # harmless compatibility alias because Ctrl does not change this
            # branch; C/Z/X are the explicit navigation overrides.
            self._start_pending_count_click(event)
            return
        QtWidgets.QGraphicsView.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._finish_navigation_gesture(event):
            return
        if self._finish_pending_count_click(event):
            return
        if (
            self.interaction_mode is InteractionMode.SELECT
            and self.dragging_annotation_vertex is not None
            and event.button() == QtCore.Qt.MouseButton.LeftButton
        ):
            annotation_index: int
            vertex_index: int
            annotation_index, vertex_index = self.dragging_annotation_vertex
            changed: bool = self.dragging_annotation_vertex_changed
            self.dragging_annotation_vertex = None
            self.dragging_annotation_vertex_changed = False
            if changed:
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
            changed: bool = self.dragging_annotation_changed
            self.dragging_annotation_index = None
            self.dragging_annotation_changed = False
            self.dragging_annotation_last_point = None
            if changed:
                self.external_annotation_move_finished.emit(annotation_index)
            event.accept()
            return
        if self.dragMode() == QtWidgets.QGraphicsView.DragMode.RubberBandDrag:
            rect: QtCore.QRect = self.rubberBandRect()
            self.region_selected.emit(self.mapToScene(rect).boundingRect())
            QtWidgets.QGraphicsView.mouseReleaseEvent(self, event)
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
            return
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        QtWidgets.QGraphicsView.mouseReleaseEvent(self, event)

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
        locked: bool = bool(item.data(4))
        self.external_annotation_selected.emit(annotation_index)

        properties_action: QtGui.QAction = menu.addAction(
            self.tr("Annotation Properties...")
        )
        lock_action: QtGui.QAction = menu.addAction(
            self.tr("Unlock Annotation") if locked else self.tr("Lock Annotation")
        )
        menu.addSeparator()

        insert_vertex_action: QtGui.QAction | None = None
        delete_annotation_action: QtGui.QAction | None = None
        if not locked:
            if shape_type in {
                AnnotationShape.LINE.value,
                AnnotationShape.POLYGON.value,
            }:
                insert_vertex_action = menu.addAction(
                    self.tr("Insert Vertex Here")
                )
            delete_annotation_action = menu.addAction(
                self.tr("Delete Annotation")
            )

        chosen_action = menu.exec(event.globalPos())
        if chosen_action is properties_action:
            self.external_annotation_properties_requested.emit()
        elif chosen_action is lock_action:
            self.external_annotation_lock_requested.emit(not locked)
        elif insert_vertex_action is not None and chosen_action is insert_vertex_action:
            scene_point: QtCore.QPointF = self.mapToScene(event.pos())
            self.external_annotation_insert_vertex_requested.emit(
                annotation_index, scene_point
            )
        elif (
            delete_annotation_action is not None
            and chosen_action is delete_annotation_action
        ):
            self.external_annotation_delete_requested.emit()


    def _add_line_vertex(self, point: QtCore.QPointF) -> None:
        """Add one vertex to the in-progress cutline.

        Args:
            point: Scene/source-image coordinate of the new vertex.
        """
        self.line_points.append(QtCore.QPointF(point))
        self._update_line_preview(point)

    def _clear_line_preview(self) -> None:
        """Remove the temporary in-progress cutline graphics item safely."""
        item: QtWidgets.QGraphicsPathItem | None = self.line_preview_item
        self.line_preview_item = None
        if item is None:
            return
        try:
            scene: QtWidgets.QGraphicsScene | None = item.scene()
            if scene is not None:
                scene.removeItem(item)
        except RuntimeError:
            # The scene may already have deleted the C++ item.
            pass

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
        pen.setCosmetic(True)
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
        """Remove the temporary in-progress polygon graphics item safely."""
        item: QtWidgets.QGraphicsPathItem | None = self.polygon_preview_item
        self.polygon_preview_item = None
        if item is None:
            return
        try:
            scene: QtWidgets.QGraphicsScene | None = item.scene()
            if scene is not None:
                scene.removeItem(item)
        except RuntimeError:
            # The scene may already have deleted the C++ item.
            pass

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
        pen.setCosmetic(True)
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
