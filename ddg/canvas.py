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
import os
import json
import glob
from copy import deepcopy
from typing import Any

import numpy as np

from PIL import Image
from PyQt6 import QtCore, QtGui, QtWidgets

from .annotations import (
    Annotation,
    AnnotationShape,
    LabelMeDocument,
    append_labelme_annotation,
    delete_labelme_annotation,
    load_annotation_style,
    load_labelme_document,
    load_labelme_raw_document,
    update_labelme_annotation,
    write_labelme_raw_document,
)


class Canvas(QtWidgets.QGraphicsScene):
    image_loading = QtCore.pyqtSignal(bool, bool)  # Params (Large image, redraw)
    image_loaded = QtCore.pyqtSignal(str, str)  # Params (directory, image_name)
    points_loaded = QtCore.pyqtSignal(str)  # Params(survey_id)
    directory_set = QtCore.pyqtSignal(str)  # Params (directory)
    fields_updated = QtCore.pyqtSignal(list)
    update_point_count = QtCore.pyqtSignal(str, str, int)  # Params (image_name, class, count)
    metadata_imported = QtCore.pyqtSignal()
    saving = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        QtWidgets.QGraphicsScene.__init__(self, parent)
        self.dirty = False
        self.points = {}
        self.colors = {}
        self.coordinates = {}
        self.custom_fields = {'fields': [], 'data': {}}
        self.classes = []
        self.selection = []
        self.redo_queue = []
        self.undo_queue = []
        self.ui = {'grid': {'size': 200, 'color': [255, 255, 255]}, 'point': {'radius': 25, 'color': [255, 255, 0]}}

        self.survey_id = ''

        self.directory = ''
        self.previous_file_name = None  # used for quick save
        self.current_image_name = None
        self.current_class_name = None

        self.image_cache = {'file_name': '', 'channels': 0, 'data': None}
        self.LUT = np.array([x for x in range(0, 256)], dtype=np.uint8)
        self.show_grid = True

        self.selected_pen = QtGui.QPen(QtGui.QBrush(QtCore.Qt.GlobalColor.red, QtCore.Qt.BrushStyle.SolidPattern), 1)
        self.external_annotations: list[Annotation] = []
        self.external_annotation_document: LabelMeDocument | None = None
        self.external_annotation_items: list[QtWidgets.QGraphicsItem] = []
        self.external_annotation_handle_items: list[QtWidgets.QGraphicsItem] = []
        self.selected_external_annotation_index: int | None = None

    def add_class(self, class_name):
        if class_name not in self.classes:
            self.classes.append(class_name)
            self.classes.sort()
            self.colors[class_name] = QtGui.QColor(QtCore.Qt.GlobalColor.black)
            self.dirty = True

    def add_custom_field(self, field_def):
        self.custom_fields['fields'].append(field_def)
        self.custom_fields['data'][field_def[0]] = {}
        self.fields_updated.emit(self.custom_fields['fields'])
        self.dirty = True

    def add_point(self, point):
        if self.current_image_name is not None and self.current_class_name is not None:
            if self.current_class_name not in self.points[self.current_image_name]:
                self.points[self.current_image_name][self.current_class_name] = []
            display_radius = self.ui['point']['radius']
            active_color = QtGui.QColor(self.ui['point']['color'][0], self.ui['point']['color'][1], self.ui['point']['color'][2])
            active_brush = QtGui.QBrush(active_color, QtCore.Qt.BrushStyle.SolidPattern)
            active_pen = QtGui.QPen(active_brush, 2)
            self.points[self.current_image_name][self.current_class_name].append(point)
            self.addEllipse(QtCore.QRectF(point.x() - ((display_radius - 1) / 2), point.y() - ((display_radius - 1) / 2), display_radius, display_radius), active_pen, active_brush)
            self.update_point_count.emit(self.current_image_name, self.current_class_name, len(self.points[self.current_image_name][self.current_class_name]))
            self.dirty = True
            self.undo_queue.append(('add', self.current_class_name, point))

    def clear_grid(self):
        for graphic in self.items():
            if isinstance(graphic, QtWidgets.QGraphicsLineItem):
                self.removeItem(graphic)

    def clear_points(self):
        for graphic in self.items():
            if isinstance(graphic, QtWidgets.QGraphicsEllipseItem):
                self.removeItem(graphic)

    def clear_queues(self):
        self.redo_queue = []
        self.undo_queue = []

    def delete_selected_points(self):
        if self.current_image_name is not None:
            points = self.points[self.current_image_name]
            self.undo_queue.append(('delete', None, self.selection))
            for class_name, point in self.selection:
                points[class_name].remove(point)
                self.update_point_count.emit(self.current_image_name, class_name, len(self.points[self.current_image_name][class_name]))
            self.selection = []
            self.display_points()
            self.dirty = True

    def delete_custom_field(self, field):
        if field in self.custom_fields['data']:
            self.custom_fields['data'].pop(field)
            index = -1
            for i, (field_name, _) in enumerate(self.custom_fields['fields']):
                if field_name == field:
                    index = i
            if index >= 0:
                self.custom_fields['fields'].pop(index)
            self.fields_updated.emit(self.custom_fields['fields'])
            self.dirty = True

    def dirty_data_check(self):
        proceed = True
        if self.dirty:
            msg_box = QtWidgets.QMessageBox(self.parent())
            msg_box.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            msg_box.setWindowTitle(self.tr('Unsaved Changes'))
            msg_box.setText(self.tr('Point or field data have been modified.'))
            msg_box.setInformativeText(self.tr('Do you want to save your changes?'))
            msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Save | QtWidgets.QMessageBox.StandardButton.Cancel | QtWidgets.QMessageBox.StandardButton.Ignore)
            msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Save)
            response = msg_box.exec()
            if response == QtWidgets.QMessageBox.StandardButton.Save:
                proceed = self.save()
            elif response == QtWidgets.QMessageBox.StandardButton.Cancel:
                proceed = False
        return proceed

    def add_landmark_annotation(self, point: QtCore.QPointF) -> None:
        """Create and immediately save a landmark point annotation.

        Args:
            point: Landmark coordinate in source-image pixel coordinates.
        """
        annotation: Annotation = Annotation(
            label="landmark",
            shape_type=AnnotationShape.POINT,
            points=[(point.x(), point.y())],
        )
        self._save_native_annotation(annotation)

    def add_line_annotation(self, points: list[QtCore.QPointF]) -> None:
        """Create and immediately save a cutline annotation.

        Args:
            points: Ordered cutline vertices in source-image pixel coordinates.
        """
        if len(points) < 2:
            return
        annotation: Annotation = Annotation(
            label="cutline",
            shape_type=AnnotationShape.LINE,
            points=[(point.x(), point.y()) for point in points],
        )
        self._save_native_annotation(annotation)

    def add_polygon_annotation(self, points: list[QtCore.QPointF]) -> None:
        """Create and immediately save a count-region polygon.

        Args:
            points: Polygon vertices in source-image pixel coordinates.
        """
        if len(points) < 3:
            return
        annotation: Annotation = Annotation(
            label="count_region",
            shape_type=AnnotationShape.POLYGON,
            points=[(point.x(), point.y()) for point in points],
        )
        self._save_native_annotation(annotation)

    def _save_native_annotation(self, annotation: Annotation) -> None:
        """Append one native annotation to the active image sidecar.

        Args:
            annotation: Valid native annotation to save and render.
        """
        if self.current_image_name is None:
            return

        image_path: str = os.path.join(self.directory, self.current_image_name)
        image_height: int | None = None
        image_width: int | None = None
        image_data: np.ndarray | None = self.image_cache.get("data")
        if image_data is not None and image_data.ndim >= 2:
            image_height = int(image_data.shape[0])
            image_width = int(image_data.shape[1])

        before_snapshot: dict[str, Any] | None = self._annotation_history_snapshot(
            image_path
        )
        try:
            append_labelme_annotation(
                image_path=image_path,
                annotation=annotation,
                image_width=image_width,
                image_height=image_height,
            )
        except (OSError, json.JSONDecodeError, ValueError) as error:
            QtWidgets.QMessageBox.critical(
                self.parent(),
                self.tr("Annotation Save Failed"),
                self.tr("The annotation could not be saved.\n\n{}").format(error),
            )
            return

        after_snapshot: dict[str, Any] | None = self._annotation_history_snapshot(
            image_path
        )
        self._record_annotation_history(
            image_path=image_path,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            before_selection_source_index=None,
            after_selection_source_index=annotation.source_shape_index,
        )

        self.external_annotations.append(annotation)
        self._render_external_annotation(
            annotation, len(self.external_annotations) - 1
        )

    def display_external_annotations(self, file_name: str) -> None:
        """Render supported LabelMe annotations for an image.

        Native annotations are deliberately kept separate from DDG bird-count
        points. Point and line annotations are rendered as painter paths so
        existing ``clear_points`` and ``clear_grid`` behavior does not remove
        them when the active class or grid display changes.

        Args:
            file_name: Full path to the source image.
        """
        self._clear_external_annotation_graphics()
        self.external_annotations = []
        self.external_annotation_document = None
        self.selected_external_annotation_index = None
        try:
            document: LabelMeDocument | None = load_labelme_document(file_name)
        except (OSError, json.JSONDecodeError, ValueError):
            return

        if document is None:
            return

        self.external_annotation_document = document
        self.external_annotations = document.annotations
        annotation_index: int
        annotation: Annotation
        for annotation_index, annotation in enumerate(self.external_annotations):
            self._render_external_annotation(annotation, annotation_index)

    def _render_external_annotation(
        self,
        annotation: Annotation,
        annotation_index: int,
    ) -> None:
        """Render one native annotation on the current graphics scene.

        Args:
            annotation: Annotation to render.
            annotation_index: Index in ``external_annotations``.
        """
        style = load_annotation_style(annotation.shape_type)
        annotation_color: QtGui.QColor = QtGui.QColor(style.color)
        annotation_pen: QtGui.QPen = QtGui.QPen(annotation_color, style.width)
        if annotation_index == self.selected_external_annotation_index:
            annotation_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
            annotation_pen.setWidthF(max(style.width + 1.5, 2.0))

        item: QtWidgets.QGraphicsItem | None = None
        if annotation.shape_type is AnnotationShape.POINT:
            x: float
            y: float
            x, y = annotation.points[0]
            path: QtGui.QPainterPath = QtGui.QPainterPath()
            path.addEllipse(QtCore.QPointF(x, y), 6.0, 6.0)
            item = self.addPath(path, annotation_pen)

        elif annotation.shape_type is AnnotationShape.LINE:
            first_x: float
            first_y: float
            first_x, first_y = annotation.points[0]
            path = QtGui.QPainterPath(QtCore.QPointF(first_x, first_y))
            for x, y in annotation.points[1:]:
                path.lineTo(x, y)
            item = self.addPath(path, annotation_pen)

        elif annotation.shape_type is AnnotationShape.POLYGON:
            polygon_points: list[QtCore.QPointF] = [
                QtCore.QPointF(x, y) for x, y in annotation.points
            ]
            item = self.addPolygon(
                QtGui.QPolygonF(polygon_points),
                annotation_pen,
            )

        if item is not None:
            item.setZValue(2.0)
            item.setData(0, "ddg_external_annotation")
            item.setData(1, annotation_index)
            item.setData(3, annotation.shape_type.value)
            if annotation.label:
                item.setToolTip(annotation.label)
            self.external_annotation_items.append(item)

    def _render_external_annotation_handles(self) -> None:
        """Render fixed-screen-size vertex handles for the selected annotation."""
        self._clear_external_annotation_handles()
        annotation_index: int | None = self.selected_external_annotation_index
        if annotation_index is None:
            return
        if annotation_index < 0 or annotation_index >= len(self.external_annotations):
            return

        annotation: Annotation = self.external_annotations[annotation_index]
        style = load_annotation_style(annotation.shape_type)
        color: QtGui.QColor = QtGui.QColor(style.color)
        pen: QtGui.QPen = QtGui.QPen(color, 2.0)
        brush: QtGui.QBrush = QtGui.QBrush(
            QtGui.QColor(255, 255, 255, 220),
            QtCore.Qt.BrushStyle.SolidPattern,
        )

        vertex_index: int
        x: float
        y: float
        for vertex_index, (x, y) in enumerate(annotation.points):
            handle_path: QtGui.QPainterPath = QtGui.QPainterPath()
            handle_path.addEllipse(QtCore.QPointF(0.0, 0.0), 5.0, 5.0)
            handle: QtWidgets.QGraphicsPathItem = self.addPath(
                handle_path, pen, brush
            )
            handle.setPos(x, y)
            handle.setFlag(
                QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
                True,
            )
            handle.setZValue(20.0)
            handle.setData(0, "ddg_external_annotation_handle")
            handle.setData(1, annotation_index)
            handle.setData(2, vertex_index)
            handle.setData(3, annotation.shape_type.value)
            self.external_annotation_handle_items.append(handle)

    def _clear_external_annotation_handles(self) -> None:
        """Remove all transient vertex handles from the scene."""
        item: QtWidgets.QGraphicsItem
        for item in self.external_annotation_handle_items:
            try:
                if item.scene() is self:
                    self.removeItem(item)
            except RuntimeError:
                # The scene may already have deleted C++ graphics objects after
                # a full image clear. Dropping the stale Python reference is safe.
                pass
        self.external_annotation_handle_items = []

    def _clear_external_annotation_graphics(self) -> None:
        """Remove rendered native annotations and transient edit handles."""
        item: QtWidgets.QGraphicsItem
        for item in self.external_annotation_items:
            try:
                if item.scene() is self:
                    self.removeItem(item)
            except RuntimeError:
                # See ``_clear_external_annotation_handles``.
                pass
        self.external_annotation_items = []
        self._clear_external_annotation_handles()

    def clear_external_annotation_selection(self) -> None:
        """Clear the selected native annotation and its vertex handles."""
        had_selection: bool = self.selected_external_annotation_index is not None
        self.selected_external_annotation_index = None
        self._clear_external_annotation_handles()
        if had_selection:
            self._rerender_external_annotations()

    def select_external_annotation(self, annotation_index: int) -> None:
        """Select one native annotation by internal index.

        Args:
            annotation_index: Index in ``external_annotations`` or ``-1`` to
                clear selection.
        """
        if annotation_index < 0 or annotation_index >= len(self.external_annotations):
            self.clear_external_annotation_selection()
            return
        self.selected_external_annotation_index = annotation_index
        self._rerender_external_annotations()

    def move_external_annotation_vertex(
        self,
        annotation_index: int,
        vertex_index: int,
        point: QtCore.QPointF,
    ) -> None:
        """Move one selected annotation vertex in memory.

        The geometry is persisted when the drag finishes.

        Args:
            annotation_index: Index in ``external_annotations``.
            vertex_index: Vertex index within the selected annotation.
            point: New source-image pixel coordinate.
        """
        if annotation_index < 0 or annotation_index >= len(self.external_annotations):
            return
        annotation: Annotation = self.external_annotations[annotation_index]
        if vertex_index < 0 or vertex_index >= len(annotation.points):
            return
        annotation.points[vertex_index] = (point.x(), point.y())
        self.selected_external_annotation_index = annotation_index
        self._rerender_external_annotations()

    def move_external_annotation(
        self,
        annotation_index: int,
        delta: QtCore.QPointF,
    ) -> None:
        """Translate one selected annotation in memory by a scene delta.

        Geometry is persisted when the drag finishes.

        Args:
            annotation_index: Index in ``external_annotations``.
            delta: Source-image x/y translation since the previous mouse event.
        """
        if annotation_index < 0 or annotation_index >= len(self.external_annotations):
            return
        annotation: Annotation = self.external_annotations[annotation_index]
        annotation.points = [
            (x + delta.x(), y + delta.y()) for x, y in annotation.points
        ]
        self.selected_external_annotation_index = annotation_index
        self._rerender_external_annotations()

    def finish_external_annotation_move(self, annotation_index: int) -> None:
        """Persist a whole-annotation translation after dragging completes.

        Args:
            annotation_index: Index in ``external_annotations``.
        """
        self._persist_external_annotation_edit(annotation_index)

    def finish_external_annotation_vertex_move(
        self,
        annotation_index: int,
        vertex_index: int,
    ) -> None:
        """Persist an edited annotation after a vertex drag completes.

        Args:
            annotation_index: Index in ``external_annotations``.
            vertex_index: Vertex index that was moved. This is retained in the
                API for future undo/redo support.
        """
        del vertex_index
        self._persist_external_annotation_edit(annotation_index)

    def insert_external_annotation_vertex(
        self,
        annotation_index: int,
        point: QtCore.QPointF,
    ) -> bool:
        """Insert a vertex on the nearest segment of a line or polygon.

        The inserted coordinate is projected onto the nearest segment so the
        shape does not jump toward an imprecise context-menu click.

        Args:
            annotation_index: Index in ``external_annotations``.
            point: Source-image coordinate near the desired edge.

        Returns:
            ``True`` when a vertex was inserted and saved.
        """
        if annotation_index < 0 or annotation_index >= len(self.external_annotations):
            return False
        annotation: Annotation = self.external_annotations[annotation_index]
        if annotation.shape_type is AnnotationShape.POINT:
            return False

        nearest: tuple[int, tuple[float, float]] | None = self._nearest_segment_point(
            annotation, point
        )
        if nearest is None:
            return False
        segment_index, projected_point = nearest
        insert_index: int = segment_index + 1
        annotation.points.insert(insert_index, projected_point)
        self.selected_external_annotation_index = annotation_index
        return self._persist_external_annotation_edit(annotation_index)

    def delete_external_annotation_vertex(
        self,
        annotation_index: int,
        vertex_index: int,
    ) -> bool:
        """Delete one line/polygon vertex when valid geometry will remain.

        Args:
            annotation_index: Index in ``external_annotations``.
            vertex_index: Vertex to remove.

        Returns:
            ``True`` when the vertex was removed and saved.
        """
        if annotation_index < 0 or annotation_index >= len(self.external_annotations):
            return False
        annotation: Annotation = self.external_annotations[annotation_index]
        if vertex_index < 0 or vertex_index >= len(annotation.points):
            return False
        minimum_vertices: int
        if annotation.shape_type is AnnotationShape.LINE:
            minimum_vertices = 2
        elif annotation.shape_type is AnnotationShape.POLYGON:
            minimum_vertices = 3
        else:
            return False
        if len(annotation.points) <= minimum_vertices:
            return False

        annotation.points.pop(vertex_index)
        self.selected_external_annotation_index = annotation_index
        return self._persist_external_annotation_edit(annotation_index)

    def _persist_external_annotation_edit(self, annotation_index: int) -> bool:
        """Persist one in-memory annotation geometry edit with undo history.

        Args:
            annotation_index: Index in ``external_annotations``.

        Returns:
            ``True`` when the edit was saved successfully.
        """
        if self.current_image_name is None:
            return False
        if annotation_index < 0 or annotation_index >= len(self.external_annotations):
            return False

        annotation: Annotation = self.external_annotations[annotation_index]
        source_shape_index: int | None = annotation.source_shape_index
        if source_shape_index is None:
            return False

        image_path: str = os.path.join(self.directory, self.current_image_name)
        before_snapshot: dict[str, Any] | None = self._annotation_history_snapshot(
            image_path
        )
        try:
            update_labelme_annotation(image_path, annotation)
        except (
            OSError,
            json.JSONDecodeError,
            IndexError,
            ValueError,
        ) as error:
            QtWidgets.QMessageBox.critical(
                self.parent(),
                self.tr("Annotation Save Failed"),
                self.tr("The annotation edit could not be saved.\n\n{}").format(error),
            )
            self._reload_external_annotations_preserving_selection(
                image_path, source_shape_index
            )
            return False

        after_snapshot: dict[str, Any] | None = self._annotation_history_snapshot(
            image_path
        )
        self._record_annotation_history(
            image_path=image_path,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            before_selection_source_index=source_shape_index,
            after_selection_source_index=source_shape_index,
        )
        self._reload_external_annotations_preserving_selection(
            image_path, source_shape_index
        )
        return True

    def _nearest_segment_point(
        self,
        annotation: Annotation,
        point: QtCore.QPointF,
    ) -> tuple[int, tuple[float, float]] | None:
        """Find the nearest line/polygon segment and projected coordinate.

        Args:
            annotation: Line or polygon annotation.
            point: Source-image coordinate supplied by the user.

        Returns:
            ``(segment_index, projected_point)`` or ``None`` when the shape has
            no editable segments.
        """
        point_count: int = len(annotation.points)
        if point_count < 2:
            return None

        segment_count: int = point_count
        if annotation.shape_type is AnnotationShape.LINE:
            segment_count = point_count - 1

        best_segment: int | None = None
        best_point: tuple[float, float] | None = None
        best_distance_squared: float | None = None
        target_x: float = point.x()
        target_y: float = point.y()

        for segment_index in range(segment_count):
            start_x, start_y = annotation.points[segment_index]
            end_x, end_y = annotation.points[(segment_index + 1) % point_count]
            dx: float = end_x - start_x
            dy: float = end_y - start_y
            length_squared: float = (dx * dx) + (dy * dy)
            if length_squared == 0.0:
                projected_x = start_x
                projected_y = start_y
            else:
                fraction: float = (
                    ((target_x - start_x) * dx) + ((target_y - start_y) * dy)
                ) / length_squared
                fraction = max(0.0, min(1.0, fraction))
                projected_x = start_x + (fraction * dx)
                projected_y = start_y + (fraction * dy)

            distance_squared: float = (
                ((target_x - projected_x) ** 2) + ((target_y - projected_y) ** 2)
            )
            if (
                best_distance_squared is None
                or distance_squared < best_distance_squared
            ):
                best_distance_squared = distance_squared
                best_segment = segment_index
                best_point = (projected_x, projected_y)

        if best_segment is None or best_point is None:
            return None
        return best_segment, best_point

    def delete_selected_external_annotation(self) -> bool:
        """Delete the currently selected native annotation from its sidecar.

        Returns:
            ``True`` when an annotation was deleted, otherwise ``False``.
        """
        if self.current_image_name is None:
            return False
        annotation_index: int | None = self.selected_external_annotation_index
        if annotation_index is None:
            return False
        if annotation_index < 0 or annotation_index >= len(self.external_annotations):
            return False

        annotation: Annotation = self.external_annotations[annotation_index]
        source_shape_index: int | None = annotation.source_shape_index
        if source_shape_index is None:
            return False

        image_path: str = os.path.join(self.directory, self.current_image_name)
        before_snapshot: dict[str, Any] | None = self._annotation_history_snapshot(
            image_path
        )
        try:
            delete_labelme_annotation(image_path, source_shape_index)
        except (
            OSError,
            json.JSONDecodeError,
            IndexError,
            ValueError,
        ) as error:
            QtWidgets.QMessageBox.critical(
                self.parent(),
                self.tr("Annotation Delete Failed"),
                self.tr("The annotation could not be deleted.\n\n{}").format(error),
            )
            return False

        after_snapshot: dict[str, Any] | None = self._annotation_history_snapshot(
            image_path
        )
        self._record_annotation_history(
            image_path=image_path,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            before_selection_source_index=source_shape_index,
            after_selection_source_index=None,
        )
        self.display_external_annotations(image_path)
        return True

    def _annotation_history_snapshot(
        self,
        image_path: str,
    ) -> dict[str, Any] | None:
        """Return a detached LabelMe document for annotation undo/redo.

        Args:
            image_path: Source image whose annotation sidecar should be read.

        Returns:
            Deep-copied LabelMe root object, or ``None`` when no sidecar exists.
        """
        try:
            raw_data: dict[str, Any] | None = load_labelme_raw_document(image_path)
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        return deepcopy(raw_data) if raw_data is not None else None

    def _record_annotation_history(
        self,
        image_path: str,
        before_snapshot: dict[str, Any] | None,
        after_snapshot: dict[str, Any] | None,
        before_selection_source_index: int | None,
        after_selection_source_index: int | None,
    ) -> None:
        """Append one complete annotation-document change to DDG history.

        Args:
            image_path: Source image associated with the sidecar.
            before_snapshot: LabelMe document before the operation.
            after_snapshot: LabelMe document after the operation.
            before_selection_source_index: Shape index to select when undoing.
            after_selection_source_index: Shape index to select when redoing.
        """
        if before_snapshot == after_snapshot:
            return
        event: tuple[object, ...] = (
            "annotation_json",
            image_path,
            deepcopy(before_snapshot),
            deepcopy(after_snapshot),
            before_selection_source_index,
            after_selection_source_index,
        )
        self.undo_queue.append(event)
        self.redo_queue = []

    def _apply_annotation_history_snapshot(
        self,
        image_path: str,
        snapshot: dict[str, Any] | None,
        selection_source_index: int | None,
    ) -> None:
        """Restore a LabelMe sidecar snapshot and refresh the active image.

        Args:
            image_path: Source image associated with the sidecar.
            snapshot: Raw LabelMe document to restore, or ``None`` to remove it.
            selection_source_index: Shape source index to reselect after restore.
        """
        write_labelme_raw_document(image_path, deepcopy(snapshot))
        current_path: str | None = None
        if self.current_image_name is not None:
            current_path = os.path.normcase(
                os.path.abspath(os.path.join(self.directory, self.current_image_name))
            )
        restored_path: str = os.path.normcase(os.path.abspath(image_path))
        if current_path != restored_path:
            return

        self.display_external_annotations(image_path)
        if selection_source_index is None:
            return
        for annotation_index, annotation in enumerate(self.external_annotations):
            if annotation.source_shape_index == selection_source_index:
                self.selected_external_annotation_index = annotation_index
                self._rerender_external_annotations()
                return

    def _reload_external_annotations_preserving_selection(
        self,
        image_path: str,
        source_shape_index: int,
    ) -> None:
        """Reload annotations and restore selection by LabelMe source index.

        Args:
            image_path: Active source image path.
            source_shape_index: LabelMe shape index that should remain selected.
        """
        self.display_external_annotations(image_path)
        annotation_index: int
        annotation: Annotation
        for annotation_index, annotation in enumerate(self.external_annotations):
            if annotation.source_shape_index == source_shape_index:
                self.selected_external_annotation_index = annotation_index
                self._rerender_external_annotations()
                return

    def _rerender_external_annotations(self) -> None:
        """Re-render native annotations while preserving selection state."""
        self._clear_external_annotation_graphics()

        annotation_index: int
        annotation: Annotation
        for annotation_index, annotation in enumerate(self.external_annotations):
            self._render_external_annotation(annotation, annotation_index)
        self._render_external_annotation_handles()

    def refresh_external_annotation_styles(self) -> None:
        """Re-render current native annotations using configured symbology."""
        self._rerender_external_annotations()

    def display_grid(self):
        self.clear_grid()
        if self.current_image_name and self.show_grid:
            grid_color = QtGui.QColor(self.ui['grid']['color'][0], self.ui['grid']['color'][1], self.ui['grid']['color'][2])
            grid_size = self.ui['grid']['size']
            rect = self.itemsBoundingRect()
            brush = QtGui.QBrush(grid_color, QtCore.Qt.BrushStyle.SolidPattern)
            pen = QtGui.QPen(brush, 1)
            for x in range(grid_size, int(rect.width()), grid_size):
                line = QtCore.QLineF(x, 0.0, x, rect.height())
                self.addLine(line, pen)
            for y in range(grid_size, int(rect.height()), grid_size):
                line = QtCore.QLineF(0.0, y, rect.width(), y)
                self.addLine(line, pen)

    def display_points(self):
        self.clear_points()
        if self.current_image_name in self.points:
            display_radius = self.ui['point']['radius']
            active_color = QtGui.QColor(self.ui['point']['color'][0], self.ui['point']['color'][1], self.ui['point']['color'][2])
            active_brush = QtGui.QBrush(active_color, QtCore.Qt.BrushStyle.SolidPattern)
            active_pen = QtGui.QPen(active_brush, 2)
            for class_name in self.points[self.current_image_name]:
                points = self.points[self.current_image_name][class_name]
                brush = QtGui.QBrush(self.colors[class_name], QtCore.Qt.BrushStyle.SolidPattern)
                pen = QtGui.QPen(brush, 2)
                for point in points:
                    if class_name == self.current_class_name:
                        self.addEllipse(QtCore.QRectF(point.x() - ((display_radius - 1) / 2), point.y() - ((display_radius - 1) / 2), display_radius, display_radius), active_pen, active_brush)
                    else:
                        self.addEllipse(QtCore.QRectF(point.x() - ((display_radius - 1) / 2), point.y() - ((display_radius - 1) / 2), display_radius, display_radius), pen, brush)

    def export_counts(self, file_name):
        if self.current_image_name is not None:
            file = open(file_name, 'w')
            output = self.tr('survey id,image')
            for class_name in self.classes:
                output += ',' + class_name
            output += ",x,y"
            for field_name, _ in self.custom_fields['fields']:
                output += ',{}'.format(field_name)
            output += '\n'
            file.write(output)
            for image in self.points:
                output = self.survey_id + ',' + image
                for class_name in self.classes:
                    if class_name in self.points[image]:
                        output += ',' + str(len(self.points[image][class_name]))
                    else:
                        output += ',0'
                if image in self.coordinates:
                    output += ',' + self.coordinates[image]['x']
                    output += ',' + self.coordinates[image]['y']
                else:
                    output += ',,'
                for field_name, _ in self.custom_fields['fields']:
                    if image in self.custom_fields['data'][field_name]:
                        output += ',{}'.format(self.custom_fields['data'][field_name][image])
                    else:
                        output += ','
                output += "\n"
                file.write(output)
            file.close()

    def export_points(self, file_name):
        if self.current_image_name is not None:
            file = open(file_name, 'w')
            output = self.tr('survey id,image,class,x,y')
            file.write(output)
            for image in self.points:
                for class_name in self.classes:
                    if class_name in self.points[image]:
                        for point in self.points[image][class_name]:
                            output = '\n{},{},{},{},{}'.format(self.survey_id, image, class_name, point.x(), point.y())
                            file.write(output)
            file.close()

    def export_overlay(self, file_name):
        if self.current_image_name is not None:
            image = QtGui.QImage(int(self.sceneRect().width()), int(self.sceneRect().height()), QtGui.QImage.Format.Format_RGB32)
            painter = QtGui.QPainter(image)
            self.render(painter)
            image.save(file_name)
            painter.end()

    def generate_lookup_table(self, brightness, contrast):
        LUT = [i for i in range(0, 256)]
        # Brighten image
        base_min = brightness
        base_max = 255
        for i in range(0, 256):
            LUT[i] = min(255, LUT[i] + brightness)

        # Apply contrast
        new_min = base_min - contrast
        new_max = 255 + contrast
        for i in range(0, 256):
            value = ((LUT[i] - base_min) / (base_max - base_min)) * (new_max - new_min) + new_min
            LUT[i] = min(255, max(0, value))
        self.LUT = np.array(LUT, dtype=np.uint8)

    def get_custom_field_data(self):
        data = {}
        if self.current_image_name is not None:
            for field_def in self.custom_fields['fields']:
                if self.current_image_name in self.custom_fields['data'][field_def[0]]:
                    data[field_def[0]] = self.custom_fields['data'][field_def[0]][self.current_image_name]
                else:
                    data[field_def[0]] = ''
        return data

    def import_metadata(self, file_name):
        file = open(file_name, 'r')
        data = json.load(file)
        file.close()

        # Backward compat
        if 'custom_fields' in data:
            self.custom_fields = data['custom_fields']
        else:
            self.custom_fields = {'fields': [], 'data': {}}
        if 'ui' in data:
            self.ui = data['ui']
        else:
            self.ui = {'grid': {'size': 200, 'color': [255, 255, 255]}, 'point': {'radius': 25, 'color': [255, 255, 0]}}
        # End Backward compat

        self.colors = data['colors']
        for class_name in data['colors']:
            self.colors[class_name] = QtGui.QColor(self.colors[class_name][0], self.colors[class_name][1], self.colors[class_name][2])
        self.classes = data['classes']
        self.fields_updated.emit(self.custom_fields['fields'])
        self.points_loaded.emit('')
        self.metadata_imported.emit()

    def load(self, drop_list):
        peek = drop_list[0].toLocalFile()
        if os.path.isdir(peek):
            # strip off trailing sep from path
            osx_hack = os.path.join(peek, 'OSX')
            directory = os.path.split(osx_hack)[0]
            # end
            if self.directory == '' or self.directory == directory:
                self.directory = directory
                self.directory_set.emit(self.directory)
                files = glob.glob(os.path.join(self.directory, '*'))
                image_format = [".jpg", ".jpeg", ".png", ".tif"]
                f = (lambda x: os.path.splitext(x)[1].lower() in image_format)
                image_list = list(filter(f, files))
                image_list = sorted(image_list)
                self.load_images(image_list)
            else:
                QtWidgets.QMessageBox.warning(self.parent(), self.tr('Warning'), self.tr('Working directory already set. Load canceled.'), QtWidgets.QMessageBox.StandardButton.Ok)
        else:
            base_path = os.path.split(peek)[0]
            for entry in drop_list:
                file_name = entry.toLocalFile()
                path = os.path.split(file_name)[0]
                error = False
                message = ''
                if os.path.isdir(file_name):
                    error = True
                    message = self.tr('Mix of files and directories detected. Load canceled.')
                if base_path != path:
                    error = True
                    message = self.tr('Files from multiple directories detected. Load canceled.')
                if self.directory != '' and self.directory != path:
                    error = True
                    message = self.tr('Image originated outside current working directory. Load canceled.')
                if error:
                    QtWidgets.QMessageBox.warning(self.parent(), self.tr('Warning'), message, QtWidgets.QMessageBox.StandardButton.Ok)
                    return None
            self.directory = base_path
            self.directory_set.emit(self.directory)
            self.load_images(drop_list)

    def load_image(self, in_file_name, redraw=False):
        Image.MAX_IMAGE_PIXELS = 1000000000
        file_name = in_file_name
        if isinstance(file_name, QtCore.QUrl):
            file_name = in_file_name.toLocalFile()

        if self.directory == '':
            self.directory = os.path.split(file_name)[0]
            self.directory_set.emit(self.directory)

        if self.directory == os.path.split(file_name)[0]:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            self.selection = []
            self.clear()
            self.current_image_name = os.path.split(file_name)[1]
            if self.current_image_name not in self.points:
                self.points[self.current_image_name] = {}
            try:
                if self.image_cache['file_name'] != file_name:
                    self.image_cache['file_name'] = file_name
                    img = Image.open(file_name)
                    self.image_cache['channels'] = len(img.getbands())
                    self.image_cache['data'] = np.array(img)
                    img.close()
                channels = self.image_cache['channels']
                array = self.image_cache['data']
                if not redraw:
                    self.generate_lookup_table(0, 0)
                if array.shape[0] > 10000 or array.shape[1] > 10000:
                    self.image_loading.emit(True, redraw)
                    # Make smaller tiles to save memory
                    stride = 100
                    max_stride = (array.shape[1] // stride) * stride
                    tail = array.shape[1] - max_stride
                    tile = np.zeros((array.shape[0], stride, array.shape[2]), dtype=np.uint8)
                    for s in range(0, max_stride, stride):
                        tile[:, :] = self.LUT[array[:, s:s + stride]]
                        qt_image = QtGui.QImage(tile.data, tile.shape[1], tile.shape[0], QtGui.QImage.Format.Format_RGB888)
                        pixmap = QtGui.QPixmap.fromImage(qt_image)
                        item = self.addPixmap(pixmap)
                        item.moveBy(s, 0)
                    # Fix for windows, thin slivers at the end cause the app to hang. QImage bug?
                    if tail > 0:
                        tile = np.ones((array.shape[0], stride, array.shape[2]), dtype=np.uint8) * 255
                        tile[:, 0:tail] = array[:, max_stride:array.shape[1]]
                        qt_image = QtGui.QImage(tile.data, tile.shape[1], tile.shape[0], QtGui.QImage.Format.Format_RGB888)
                        pixmap = QtGui.QPixmap.fromImage(qt_image)
                        item = self.addPixmap(pixmap)
                        item.moveBy(max_stride, 0)
                else:
                    self.image_loading.emit(False, redraw)
                    if channels == 1:
                        qt_image = QtGui.QImage(array.data, array.shape[1], array.shape[0], QtGui.QImage.Format.Format_Grayscale8)
                    else:
                        array = self.LUT[array]
                        bpl = int(array.nbytes / array.shape[0])
                        if array.shape[2] == 4:
                            qt_image = QtGui.QImage(array.data, array.shape[1], array.shape[0], QtGui.QImage.Format.Format_RGBA8888)
                        else:
                            qt_image = QtGui.QImage(array.data, array.shape[1], array.shape[0], bpl, QtGui.QImage.Format.Format_RGB888)
                    self.pixmap = QtGui.QPixmap.fromImage(qt_image)
                    self.addPixmap(self.pixmap)
                self.display_external_annotations(file_name)
                self.display_grid()
                self.display_points()
            except FileNotFoundError:
                QtWidgets.QMessageBox.critical(None, self.tr('File Not Found'), '{} {}'.format(self.current_image_name, self.tr('is not in the same folder as the point file.')))
                if not redraw:
                    self.image_loaded.emit(self.directory, self.current_image_name)
            if not redraw:
                self.image_loaded.emit(self.directory, self.current_image_name)
                self.clear_queues()
            QtWidgets.QApplication.restoreOverrideCursor()

    def load_images(self, images):
        for file in images:
            file_name = file
            if isinstance(file, QtCore.QUrl):
                file_name = file.toLocalFile()

            image_name = os.path.split(file_name)[1]
            if image_name not in self.points:
                self.points[image_name] = {}
        if len(images) > 0:
            self.load_image(images[0])

    def load_points(self, file_name):
        self.reset()
        self.directory = os.path.split(file_name)[0]
        file = open(file_name, 'r')
        self.previous_file_name = file_name
        data = json.load(file)
        file.close()
        self.survey_id = data['metadata']['survey_id']

        # Backward compat
        if 'custom_fields' in data:
            self.custom_fields = data['custom_fields']
        else:
            self.custom_fields = {'fields': [], 'data': {}}
        if 'ui' in data:
            self.ui = data['ui']
        else:
            self.ui = {'grid': {'size': 200, 'color': [255, 255, 255]}, 'point': {'radius': 25, 'color': [255, 255, 0]}}
        # End Backward compat

        self.colors = data['colors']
        self.classes = data['classes']
        self.coordinates = data['metadata']['coordinates']
        self.points = {}
        if 'points' in data:
            self.points = data['points']

        for image in self.points:
            for class_name in self.points[image]:
                for p in range(len(self.points[image][class_name])):
                    point = self.points[image][class_name][p]
                    self.points[image][class_name][p] = QtCore.QPointF(point['x'], point['y'])
        for class_name in data['colors']:
            self.colors[class_name] = QtGui.QColor(self.colors[class_name][0], self.colors[class_name][1], self.colors[class_name][2])
        self.points_loaded.emit(self.survey_id)
        self.fields_updated.emit(self.custom_fields['fields'])
        # Force rescan of working folder for new images
        self.load([QtCore.QUrl('file:{}'.format(self.directory))])

    def package_points(self):
        count = 0
        package = {'classes': [], 'points': {}, 'colors': {}, 'metadata': {'survey_id': self.survey_id, 'coordinates': self.coordinates}, 'custom_fields': self.custom_fields, 'ui': self.ui}
        package['classes'] = self.classes
        for class_name in self.colors:
            r = self.colors[class_name].red()
            g = self.colors[class_name].green()
            b = self.colors[class_name].blue()
            package['colors'][class_name] = [r, g, b]
        for image in self.points:
            package['points'][image] = {}
            for class_name in self.points[image]:
                package['points'][image][class_name] = []
                src = self.points[image][class_name]
                dst = package['points'][image][class_name]
                for point in src:
                    p = {'x': point.x(), 'y': point.y()}
                    dst.append(p)
                    count += 1
        return (package, count)

    def quick_save(self):
        if self.previous_file_name is None:
            self.save()
        else:
            self.saving.emit()
            self.save_points(self.previous_file_name)

    def redo(self):
        if len(self.redo_queue) > 0:
            event = self.redo_queue.pop()
            if event[0] == 'add':
                self.points[self.current_image_name][event[1]].append(event[2])
                self.update_point_count.emit(self.current_image_name, event[1], len(self.points[self.current_image_name][event[1]]))
                self.display_points()
                self.undo_queue.append(event)
            elif event[0] == 'delete':
                for class_name, point in event[2]:
                    self.points[self.current_image_name][class_name].remove(point)
                    self.update_point_count.emit(self.current_image_name, class_name, len(self.points[self.current_image_name][class_name]))
                self.display_points()
                self.undo_queue.append(event)
            elif event[0] == 'relabel':
                for class_name, point in event[2]:
                    self.points[self.current_image_name][class_name].remove(point)
                    self.update_point_count.emit(self.current_image_name, class_name, len(self.points[self.current_image_name][class_name]))
                    self.points[self.current_image_name][event[1]].append(point)
                self.update_point_count.emit(self.current_image_name, event[1], len(self.points[self.current_image_name][event[1]]))
                self.display_points()
                self.undo_queue.append(event)
            elif event[0] == 'annotation_json':
                self._apply_annotation_history_snapshot(
                    event[1], event[3], event[5]
                )
                self.undo_queue.append(event)

    def redraw_image(self):
        if self.directory != '':
            self.load_image(self.directory + "/" + self.current_image_name, redraw=True)

    def relabel_selected_points(self):
        if self.current_class_name is not None:
            self.undo_queue.append(('relabel', self.current_class_name, self.selection))
            for class_name, point in self.selection:
                # Remove original point
                self.points[self.current_image_name][class_name].remove(point)
                self.update_point_count.emit(self.current_image_name, class_name, len(self.points[self.current_image_name][class_name]))
                if self.current_class_name not in self.points[self.current_image_name]:
                    self.points[self.current_image_name][self.current_class_name] = []
                self.points[self.current_image_name][self.current_class_name].append(point)
                self.update_point_count.emit(self.current_image_name, self.current_class_name, len(self.points[self.current_image_name][self.current_class_name]))
            self.selection = []
            self.display_points()
            self.dirty = True

    def rename_class(self, old_class, new_class):
        index = self.classes.index(old_class)
        del self.classes[index]
        if new_class not in self.classes:
            self.colors[new_class] = self.colors.pop(old_class)
            self.classes.append(new_class)
            self.classes.sort()
        else:
            del self.colors[old_class]

        for image in self.points:
            if old_class in self.points[image] and new_class in self.points[image]:
                self.points[image][new_class] += self.points[image].pop(old_class)
            elif old_class in self.points[image]:
                self.points[image][new_class] = self.points[image].pop(old_class)
        self.display_points()
        self.dirty = True

    def reset(self):
        self.dirty = False
        self.points = {}
        self.colors = {}
        self.classes = []
        self.classes = []
        self.selection = []
        self.redo_queue = []
        self.undo_queue = []
        self.coordinates = {}
        self.custom_fields = {'fields': [], 'data': {}}
        self.external_annotations = []
        self.external_annotation_document = None
        self.external_annotation_items = []

        self.clear()
        self.directory = ''
        self.previous_file_name = None
        self.current_image_name = ''
        self.current_class_name = None
        self.fields_updated.emit([])
        self.points_loaded.emit('')
        self.image_loaded.emit('', '')
        self.directory_set.emit('')

    def remove_class(self, class_name):
        index = self.classes.index(class_name)
        del self.colors[class_name]
        del self.classes[index]
        for image in self.points:
            if class_name in self.points[image]:
                del self.points[image][class_name]
        self.display_points()
        self.dirty = True

    def save(self, override=False):
        file_name = QtWidgets.QFileDialog.getSaveFileName(self.parent(), self.tr('Save Points'), os.path.join(self.directory, 'untitled.pnt'), 'Point Files (*.pnt)')
        if file_name[0] != '':
            if override is False and self.directory != os.path.split(file_name[0])[0]:
                QtWidgets.QMessageBox.warning(self.parent(), self.tr('ERROR'), self.tr('You are attempting to save the pnt file outside of the working directory. Operation canceled. POINT DATA NOT SAVED.'), QtWidgets.QMessageBox.StandardButton.Ok)
            else:
                if self.save_points(file_name[0]) is False:
                    msg_box = QtWidgets.QMessageBox()
                    msg_box.setWindowTitle(self.tr('ERROR'))
                    msg_box.setText(self.tr('Save Failed!'))
                    msg_box.setInformativeText(self.tr('It appears you cannot save your pnt file in the working directory, possibly due to permissions.\n\nEither change the permissions on the folder or click the SAVE button and select another location outside of the working directory. Remember to copy of the pnt file back into the current working directory.'))
                    msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Save | QtWidgets.QMessageBox.StandardButton.Cancel)
                    msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Save)
                    response = msg_box.exec()
                    if response == QtWidgets.QMessageBox.StandardButton.Save:
                        self.save(True)
                    else:
                        return False
                self.previous_file_name = file_name[0]
                self.clear_queues()
                return True

    def save_coordinates(self, x, y):
        if self.current_image_name is not None:
            if self.current_image_name not in self.coordinates:
                self.coordinates[self.current_image_name] = {'x': '', 'y': ''}
            self.coordinates[self.current_image_name]['x'] = x
            self.coordinates[self.current_image_name]['y'] = y

    def save_custom_field_data(self, field, data):
        if self.current_image_name is not None:
            if self.current_image_name not in self.custom_fields['data'][field]:
                self.custom_fields['data'][field][self.current_image_name] = ''
            self.custom_fields['data'][field][self.current_image_name] = data

    def save_points(self, file_name):
        try:
            output, _ = self.package_points()
            file = open(file_name, 'w')
            json.dump(output, file, indent=2)
            file.close()
            self.dirty = False
        except OSError:
            return False
        return True

    def select_points(self, rect):
        self.selection = []
        self.display_points()
        current = self.points[self.current_image_name]
        display_radius = self.ui['point']['radius']
        for class_name in current:
            for point in current[class_name]:
                if rect.contains(point):
                    offset = ((display_radius + 6) // 2)
                    self.addEllipse(QtCore.QRectF(point.x() - offset, point.y() - offset, display_radius + 6, display_radius + 6), self.selected_pen)
                    self.selection.append((class_name, point))

    def set_current_class(self, class_index):
        if class_index is None or class_index >= len(self.classes):
            self.current_class_name = None
        else:
            self.current_class_name = self.classes[class_index]
        self.display_points()

    def set_grid_color(self, color):
        self.ui['grid']['color'] = [color.red(), color.green(), color.blue()]
        self.display_grid()

    def set_grid_size(self, size):
        self.ui['grid']['size'] = size
        self.display_grid()

    def set_point_color(self, color):
        self.ui['point']['color'] = [color.red(), color.green(), color.blue()]
        self.display_points()

    def set_point_radius(self, radius):
        self.ui['point']['radius'] = radius
        self.display_points()

    def toggle_grid(self, display):
        if display:
            self.show_grid = True
            self.display_grid()
        else:
            self.show_grid = False
            self.clear_grid()

    def toggle_points(self, display):
        if display:
            self.display_points()
            self.selection = []
        else:
            self.clear_points()

    def undo(self):
        if len(self.undo_queue) > 0:
            event = self.undo_queue.pop()
            if event[0] == 'add':
                self.points[self.current_image_name][event[1]].remove(event[2])
                self.update_point_count.emit(self.current_image_name, event[1], len(self.points[self.current_image_name][event[1]]))
                self.display_points()
                self.redo_queue.append(event)
            elif event[0] == 'delete':
                for class_name, point in event[2]:
                    self.points[self.current_image_name][class_name].append(point)
                    self.update_point_count.emit(self.current_image_name, class_name, len(self.points[self.current_image_name][class_name]))
                self.display_points()
                self.redo_queue.append(event)
            elif event[0] == 'relabel':
                for class_name, point in event[2]:
                    self.points[self.current_image_name][event[1]].remove(point)
                    self.update_point_count.emit(self.current_image_name, event[1], len(self.points[self.current_image_name][event[1]]))
                    self.points[self.current_image_name][class_name].append(point)
                    self.update_point_count.emit(self.current_image_name, class_name, len(self.points[self.current_image_name][class_name]))
                self.display_points()
                self.redo_queue.append(event)
            elif event[0] == 'annotation_json':
                self._apply_annotation_history_snapshot(
                    event[1], event[2], event[4]
                )
                self.redo_queue.append(event)

    def update_survey_id(self, text):
        self.survey_id = text
