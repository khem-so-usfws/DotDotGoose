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
    annotation_visibility_enabled,
    append_labelme_annotation,
    delete_labelme_annotation,
    load_annotation_style,
    load_labelme_document,
    load_labelme_raw_document,
    count_region_polygons,
    point_in_count_regions,
    point_in_polygon,
    replace_labelme_annotations_by_label,
    save_annotation_visibility,
    update_labelme_annotation,
    write_labelme_raw_document,
)

_ANNOTATION_HISTORY_IMAGE_DATA_KEY: str = "__ddg_history_preserve_image_data__"
_ANNOTATION_HISTORY_UNAVAILABLE_KEY: str = "__ddg_history_snapshot_unavailable__"


class Canvas(QtWidgets.QGraphicsScene):
    image_loading = QtCore.pyqtSignal(bool, bool)  # Params (Large image, redraw)
    image_loaded = QtCore.pyqtSignal(str, str)  # Params (directory, image_name)
    image_about_to_change = QtCore.pyqtSignal()
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
        self.show_points = True

        self.selected_pen = QtGui.QPen(QtGui.QBrush(QtCore.Qt.GlobalColor.red, QtCore.Qt.BrushStyle.SolidPattern), 1)
        self.external_annotations: list[Annotation] = []
        self.external_annotation_document: LabelMeDocument | None = None
        self.external_annotation_items: list[QtWidgets.QGraphicsItem] = []
        self.external_annotation_handle_items: list[QtWidgets.QGraphicsItem] = []
        self.selected_external_annotation_index: int | None = None
        self.count_region_mask_item: QtWidgets.QGraphicsPathItem | None = None

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
            if (
                self.point_is_outside_count_region(point)
                and self.warn_outside_count_region_point_enabled()
            ):
                response = QtWidgets.QMessageBox.question(
                    self.parent(),
                    self.tr("Point Outside Count Region"),
                    self.tr(
                        "This point is outside the defined count region. "
                        "Add it anyway?"
                    ),
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No,
                )
                if response != QtWidgets.QMessageBox.StandardButton.Yes:
                    return

            if self.current_class_name not in self.points[self.current_image_name]:
                self.points[self.current_image_name][self.current_class_name] = []
            self.points[self.current_image_name][self.current_class_name].append(point)
            self.display_points()
            self.update_point_count.emit(self.current_image_name, self.current_class_name, len(self.points[self.current_image_name][self.current_class_name]))
            self.dirty = True
            self.undo_queue.append(
                ('add', self.current_image_name, self.current_class_name, point)
            )
            self.redo_queue = []

    def clear_grid(self):
        for graphic in self.items():
            if isinstance(graphic, QtWidgets.QGraphicsLineItem):
                self.removeItem(graphic)

    def clear_points(self):
        for graphic in list(self.items()):
            item_kind: object = graphic.data(0)
            if item_kind in {
                "ddg_bird_point",
                "ddg_count_region_warning",
                "ddg_selected_bird_point",
            }:
                self.removeItem(graphic)

    def clear_queues(self):
        self.redo_queue = []
        self.undo_queue = []

    def delete_selected_points(self):
        if self.current_image_name is not None:
            points = self.points[self.current_image_name]
            self.undo_queue.append(
                ('delete', self.current_image_name, list(self.selection))
            )
            self.redo_queue = []
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
        if (
            annotation.shape_type is AnnotationShape.POLYGON
            and annotation.label == "count_region"
        ):
            self.refresh_count_region_mask()
            self.display_points()

    def has_count_regions(self) -> bool:
        """Return whether the active image has explicit count-region polygons.

        Returns:
            ``True`` when at least one polygon labeled ``count_region`` exists.
        """
        return bool(count_region_polygons(self.external_annotations))

    def set_whole_image_count_region(self) -> bool:
        """Replace active-image count regions with one whole-image polygon.

        Returns:
            ``True`` when the count region was written successfully.
        """
        if self.current_image_name is None:
            return False

        image_data: np.ndarray | None = self.image_cache.get("data")
        if image_data is None or image_data.ndim < 2:
            return False

        image_height: int = int(image_data.shape[0])
        image_width: int = int(image_data.shape[1])
        annotation: Annotation = Annotation(
            label="count_region",
            shape_type=AnnotationShape.POLYGON,
            points=[
                (0.0, 0.0),
                (float(image_width), 0.0),
                (float(image_width), float(image_height)),
                (0.0, float(image_height)),
            ],
        )
        image_path: str = os.path.join(self.directory, self.current_image_name)
        before_snapshot: dict[str, Any] | None = self._annotation_history_snapshot(
            image_path
        )
        try:
            replace_labelme_annotations_by_label(
                image_path=image_path,
                label="count_region",
                annotations=[annotation],
                image_width=image_width,
                image_height=image_height,
                shape_type=AnnotationShape.POLYGON,
            )
        except (OSError, json.JSONDecodeError, ValueError) as error:
            QtWidgets.QMessageBox.critical(
                self.parent(),
                self.tr("Annotation Save Failed"),
                self.tr("The count region could not be saved.\n\n{}").format(error),
            )
            return False

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
        self.display_external_annotations(image_path)
        return True

    def count_region_qa(self) -> dict[str, Any]:
        """Summarize active-image points inside and outside count regions.

        Returns:
            Dictionary containing ``has_regions``, total ``inside`` and
            ``outside`` counts, and per-class counts.
        """
        regions = count_region_polygons(self.external_annotations)
        result: dict[str, Any] = {
            "has_regions": bool(regions),
            "inside": 0,
            "outside": 0,
            "by_class": {},
        }
        if self.current_image_name is None or not regions:
            return result

        image_points: dict[str, list[QtCore.QPointF]] = self.points.get(
            self.current_image_name, {}
        )
        for class_name, points in image_points.items():
            inside_count: int = 0
            outside_count: int = 0
            for point in points:
                point_xy: tuple[float, float] = (
                    float(point.x()),
                    float(point.y()),
                )
                if any(
                    point_in_polygon(point_xy, region.points) for region in regions
                ):
                    inside_count += 1
                else:
                    outside_count += 1
            result["by_class"][class_name] = {
                "inside": inside_count,
                "outside": outside_count,
            }
            result["inside"] += inside_count
            result["outside"] += outside_count
        return result

    def outside_count_region_points(self) -> list[tuple[str, QtCore.QPointF]]:
        """Return active-image points outside explicit count regions.

        Images without an explicit ``count_region`` polygon are unrestricted and
        therefore return an empty list. The returned points are copies so QA
        navigation cannot mutate stored DDG point data.

        Returns:
            ``(class_name, point)`` pairs for outside-region points.
        """
        if self.current_image_name is None:
            return []
        regions: list[Annotation] = count_region_polygons(
            self.external_annotations
        )
        if not regions:
            return []

        outside_points: list[tuple[str, QtCore.QPointF]] = []
        image_points: dict[str, list[QtCore.QPointF]] = self.points.get(
            self.current_image_name, {}
        )
        for class_name in sorted(image_points):
            for point in image_points[class_name]:
                point_xy: tuple[float, float] = (
                    float(point.x()),
                    float(point.y()),
                )
                if not any(
                    point_in_polygon(point_xy, region.points) for region in regions
                ):
                    outside_points.append((class_name, QtCore.QPointF(point)))
        return outside_points

    def point_is_outside_count_region(self, point: QtCore.QPointF) -> bool:
        """Return whether a point is outside an explicit count region.

        Images without any explicit ``count_region`` polygon are treated as
        unrestricted, so their points are never flagged as outside.

        Args:
            point: Point in source-image pixel coordinates.

        Returns:
            ``True`` only when count regions exist and ``point`` is outside
            every count-region polygon.
        """
        if not self.has_count_regions():
            return False
        return not point_in_count_regions(
            (float(point.x()), float(point.y())), self.external_annotations
        )

    def highlight_outside_count_region_points_enabled(self) -> bool:
        """Return whether outside-region points should be highlighted."""
        settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
        value: object = settings.value(
            "annotations/count_region/highlight_outside_points", True
        )
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off"}

    def set_highlight_outside_count_region_points(self, enabled: bool) -> None:
        """Persist and apply outside-region point highlighting.

        Args:
            enabled: Whether outside-region points should receive a warning ring.
        """
        settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue(
            "annotations/count_region/highlight_outside_points", enabled
        )
        self.display_points()

    def warn_outside_count_region_point_enabled(self) -> bool:
        """Return whether DDG should warn before adding an outside point."""
        settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
        value: object = settings.value(
            "annotations/count_region/warn_outside_point", True
        )
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off"}

    def set_warn_outside_count_region_point(self, enabled: bool) -> None:
        """Persist the warning preference for new outside-region points.

        Args:
            enabled: Whether point placement should ask for confirmation.
        """
        settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue("annotations/count_region/warn_outside_point", enabled)

    def dim_outside_count_region_enabled(self) -> bool:
        """Return the persisted outside-region dimming preference.

        Returns:
            Whether the mask should be displayed.
        """
        settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
        value: object = settings.value(
            "annotations/count_region/dim_outside", True
        )
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off"}

    def set_dim_outside_count_region(self, enabled: bool) -> None:
        """Persist and apply the outside-count-region dimming preference.

        Args:
            enabled: Whether dimming should be displayed.
        """
        settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue("annotations/count_region/dim_outside", enabled)
        self.refresh_count_region_mask()

    def annotation_type_visible(self, shape_type: AnnotationShape) -> bool:
        """Return whether one native annotation geometry type is visible.

        Args:
            shape_type: Geometry type to query.

        Returns:
            Persisted visibility state.
        """
        return annotation_visibility_enabled(shape_type)

    def set_annotation_type_visible(
        self,
        shape_type: AnnotationShape,
        visible: bool,
    ) -> None:
        """Persist and apply visibility for one annotation geometry type.

        Args:
            shape_type: Geometry type to show or hide.
            visible: Whether it should be rendered.
        """
        save_annotation_visibility(shape_type, visible)
        selected_index: int | None = self.selected_external_annotation_index
        if (
            not visible
            and selected_index is not None
            and 0 <= selected_index < len(self.external_annotations)
            and self.external_annotations[selected_index].shape_type is shape_type
        ):
            self.selected_external_annotation_index = None
        self._rerender_external_annotations(
            refresh_mask=False, refresh_points=False
        )

    def _clear_count_region_mask(self) -> None:
        """Remove the current outside-region mask from the scene."""
        if self.count_region_mask_item is None:
            return
        try:
            if self.count_region_mask_item.scene() is self:
                self.removeItem(self.count_region_mask_item)
        except RuntimeError:
            pass
        self.count_region_mask_item = None

    def refresh_count_region_mask(self) -> None:
        """Render a translucent mask outside the union of count regions."""
        self._clear_count_region_mask()
        if not self.dim_outside_count_region_enabled():
            return

        regions = count_region_polygons(self.external_annotations)
        image_data: np.ndarray | None = self.image_cache.get("data")
        if not regions or image_data is None or image_data.ndim < 2:
            return

        image_height: float = float(image_data.shape[0])
        image_width: float = float(image_data.shape[1])
        valid_path: QtGui.QPainterPath = QtGui.QPainterPath()
        for region in regions:
            polygon = QtGui.QPolygonF(
                [QtCore.QPointF(x, y) for x, y in region.points]
            )
            region_path: QtGui.QPainterPath = QtGui.QPainterPath()
            region_path.addPolygon(polygon)
            region_path.closeSubpath()
            valid_path = valid_path.united(region_path)

        image_path: QtGui.QPainterPath = QtGui.QPainterPath()
        image_path.addRect(QtCore.QRectF(0.0, 0.0, image_width, image_height))
        outside_path: QtGui.QPainterPath = image_path.subtracted(valid_path)
        if outside_path.isEmpty():
            return

        mask_color: QtGui.QColor = QtGui.QColor(0, 0, 0, 90)
        mask_pen: QtGui.QPen = QtGui.QPen(QtCore.Qt.PenStyle.NoPen)
        mask_brush: QtGui.QBrush = QtGui.QBrush(mask_color)
        item: QtWidgets.QGraphicsPathItem = self.addPath(
            outside_path, mask_pen, mask_brush
        )
        item.setZValue(-5.0)
        item.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self.count_region_mask_item = item

    def display_external_annotations(
        self,
        file_name: str,
        refresh_points: bool = True,
    ) -> None:
        """Render supported LabelMe annotations for an image.

        Native annotations are deliberately kept separate from DDG bird-count
        points. Point and line annotations are rendered as painter paths so
        existing ``clear_points`` and ``clear_grid`` behavior does not remove
        them when the active class or grid display changes.

        Args:
            file_name: Full path to the source image.
            refresh_points: Whether point graphics should be redrawn after the
                annotations are loaded. Image loading already redraws points, so
                callers may disable this to avoid duplicate work.
        """
        self._clear_external_annotation_graphics()
        self._clear_count_region_mask()
        self.external_annotations = []
        self.external_annotation_document = None
        self.selected_external_annotation_index = None
        try:
            document: LabelMeDocument | None = load_labelme_document(file_name)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            QtWidgets.QMessageBox.warning(
                self.parent(),
                self.tr("Annotation Load Warning"),
                self.tr(
                    "Annotations for {} could not be loaded. The image will "
                    "remain available, but its annotation sidecar should be "
                    "checked before counting.\n\n{}"
                ).format(os.path.basename(file_name), error),
            )
            return

        if document is None:
            return

        important_warnings: list[str] = [
            warning
            for warning in document.warnings
            if "was not loaded" in warning
            or "'shapes' value is not a list" in warning
        ]
        if important_warnings:
            QtWidgets.QMessageBox.warning(
                self.parent(),
                self.tr("Annotation Load Warning"),
                self.tr(
                    "Some annotations for {} could not be loaded and will not "
                    "be displayed. Check the sidecar before counting.\n\n{}"
                ).format(
                    os.path.basename(file_name),
                    "\n".join(important_warnings[:5]),
                ),
            )

        self.external_annotation_document = document
        self.external_annotations = document.annotations
        annotation_index: int
        annotation: Annotation
        for annotation_index, annotation in enumerate(self.external_annotations):
            self._render_external_annotation(annotation, annotation_index)
        self.refresh_count_region_mask()
        if refresh_points:
            self.display_points()

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
        if not self.annotation_type_visible(annotation.shape_type):
            return

        style = load_annotation_style(annotation.shape_type)
        annotation_color: QtGui.QColor = QtGui.QColor(style.color)
        annotation_pen: QtGui.QPen = QtGui.QPen(annotation_color, style.width)
        annotation_pen.setCosmetic(True)
        if annotation_index == self.selected_external_annotation_index:
            annotation_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
            annotation_pen.setWidthF(max(style.width + 1.5, 2.0))

        item: QtWidgets.QGraphicsItem | None = None
        if annotation.shape_type is AnnotationShape.POINT:
            x: float
            y: float
            x, y = annotation.points[0]
            path: QtGui.QPainterPath = QtGui.QPainterPath()
            path.addEllipse(QtCore.QPointF(0.0, 0.0), 6.0, 6.0)
            item = self.addPath(path, annotation_pen)
            item.setPos(x, y)
            item.setFlag(
                QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
                True,
            )

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
            item.setData(4, annotation.locked)
            if annotation.label:
                tooltip: str = annotation.label
                if annotation.locked:
                    tooltip += self.tr(" (locked)")
                item.setToolTip(tooltip)
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
        if annotation.locked or not self.annotation_type_visible(annotation.shape_type):
            return
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
            self._rerender_external_annotations(
                refresh_mask=False, refresh_points=False
            )

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
        self._rerender_external_annotations(
            refresh_mask=False, refresh_points=False
        )

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
        if annotation.locked:
            return
        if vertex_index < 0 or vertex_index >= len(annotation.points):
            return
        annotation.points[vertex_index] = (point.x(), point.y())
        self.selected_external_annotation_index = annotation_index
        refresh_mask: bool = (
            annotation.shape_type is AnnotationShape.POLYGON
            and annotation.label == "count_region"
        )
        self._rerender_external_annotations(
            refresh_mask=refresh_mask, refresh_points=False
        )

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
        if annotation.locked:
            return
        annotation.points = [
            (x + delta.x(), y + delta.y()) for x, y in annotation.points
        ]
        self.selected_external_annotation_index = annotation_index
        refresh_mask: bool = (
            annotation.shape_type is AnnotationShape.POLYGON
            and annotation.label == "count_region"
        )
        self._rerender_external_annotations(
            refresh_mask=refresh_mask, refresh_points=False
        )

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
        if annotation.locked:
            return False
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
        if annotation.locked:
            return False
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
        if annotation.locked:
            return False
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

    def selected_external_annotation(self) -> Annotation | None:
        """Return the selected native annotation, if any.

        Returns:
            Selected annotation or ``None``.
        """
        annotation_index: int | None = self.selected_external_annotation_index
        if annotation_index is None:
            return None
        if annotation_index < 0 or annotation_index >= len(self.external_annotations):
            return None
        return self.external_annotations[annotation_index]

    def update_selected_external_annotation_properties(
        self,
        label: str,
        locked: bool,
    ) -> bool:
        """Persist label and lock-state changes for the selected annotation.

        Args:
            label: New non-empty semantic label.
            locked: Whether editing should be locked.

        Returns:
            ``True`` when the properties were saved successfully.
        """
        annotation: Annotation | None = self.selected_external_annotation()
        if annotation is None or self.current_image_name is None:
            return False
        normalized_label: str = label.strip()
        if not normalized_label:
            return False
        source_shape_index: int | None = annotation.source_shape_index
        if source_shape_index is None:
            return False
        if annotation.label == normalized_label and annotation.locked == locked:
            return True

        image_path: str = os.path.join(self.directory, self.current_image_name)
        before_snapshot: dict[str, Any] | None = self._annotation_history_snapshot(
            image_path
        )
        annotation.label = normalized_label
        annotation.set_locked(locked)
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
                self.tr("The annotation properties could not be saved.\n\n{}").format(
                    error
                ),
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

    def set_selected_external_annotation_locked(self, locked: bool) -> bool:
        """Persist the edit-lock state for the selected annotation.

        Args:
            locked: Whether editing should be locked.

        Returns:
            ``True`` when a selected annotation was saved successfully.
        """
        annotation: Annotation | None = self.selected_external_annotation()
        if annotation is None:
            return False
        return self.update_selected_external_annotation_properties(
            annotation.label, locked
        )

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
        if annotation.locked:
            return False
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
        """Return a lightweight LabelMe document for annotation undo/redo.

        Embedded LabelMe ``imageData`` can be very large. DDG never edits that
        field, so history snapshots omit its value and restore the current live
        value when undo/redo is applied. This avoids retaining one base64 image
        copy for every annotation edit.

        Args:
            image_path: Source image whose annotation sidecar should be read.

        Returns:
            Detached LabelMe root object, or ``None`` when no sidecar exists.
        """
        try:
            raw_data: dict[str, Any] | None = load_labelme_raw_document(image_path)
        except (OSError, json.JSONDecodeError, ValueError):
            # ``None`` has a real meaning in history: no sidecar existed. Keep
            # read failures distinguishable so a later undo/redo cannot
            # accidentally delete a valid annotation file.
            return {_ANNOTATION_HISTORY_UNAVAILABLE_KEY: True}
        if raw_data is None:
            return None

        snapshot: dict[str, Any] = deepcopy(raw_data)
        if snapshot.get("imageData") is not None:
            snapshot["imageData"] = None
            snapshot[_ANNOTATION_HISTORY_IMAGE_DATA_KEY] = True
        return snapshot

    @staticmethod
    def _annotation_snapshot_unavailable(
        snapshot: dict[str, Any] | None,
    ) -> bool:
        """Return whether a history snapshot represents a read failure.

        ``None`` intentionally means that no sidecar existed. A separate
        sentinel prevents transient read failures from being interpreted as
        "delete the sidecar" during undo/redo.

        Args:
            snapshot: Candidate history snapshot.

        Returns:
            ``True`` for the private unavailable-snapshot sentinel.
        """
        return bool(
            snapshot is not None
            and snapshot.get(_ANNOTATION_HISTORY_UNAVAILABLE_KEY, False)
        )

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
        if self._annotation_snapshot_unavailable(before_snapshot) or (
            self._annotation_snapshot_unavailable(after_snapshot)
        ):
            return
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
    ) -> bool:
        """Restore a LabelMe sidecar snapshot and refresh the active image.

        Args:
            image_path: Source image associated with the sidecar.
            snapshot: Raw LabelMe document to restore, or ``None`` to remove it.
            selection_source_index: Shape source index to reselect after restore.

        Returns:
            ``True`` when the history snapshot was restored successfully.
        """
        restored_snapshot: dict[str, Any] | None = deepcopy(snapshot)
        if restored_snapshot is not None and bool(
            restored_snapshot.pop(_ANNOTATION_HISTORY_IMAGE_DATA_KEY, False)
        ):
            try:
                current_document: dict[str, Any] | None = load_labelme_raw_document(
                    image_path
                )
            except (OSError, json.JSONDecodeError, ValueError):
                current_document = None
            if current_document is not None:
                restored_snapshot["imageData"] = current_document.get("imageData")

        try:
            write_labelme_raw_document(image_path, restored_snapshot)
        except (OSError, TypeError, ValueError) as error:
            QtWidgets.QMessageBox.critical(
                self.parent(),
                self.tr("Annotation History Restore Failed"),
                self.tr(
                    "The annotation undo/redo operation could not be written. "
                    "The current sidecar was left unchanged.\n\n{}"
                ).format(error),
            )
            return False

        current_path: str | None = None
        if self.current_image_name is not None:
            current_path = os.path.normcase(
                os.path.abspath(os.path.join(self.directory, self.current_image_name))
            )
        restored_path: str = os.path.normcase(os.path.abspath(image_path))
        if current_path != restored_path:
            return True

        self.display_external_annotations(image_path)
        if selection_source_index is None:
            return True
        for annotation_index, annotation in enumerate(self.external_annotations):
            if annotation.source_shape_index == selection_source_index:
                self.selected_external_annotation_index = annotation_index
                self._rerender_external_annotations(
                    refresh_mask=False, refresh_points=False
                )
                return True
        return True

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
                self._rerender_external_annotations(
                    refresh_mask=False, refresh_points=False
                )
                return

    def _rerender_external_annotations(
        self,
        refresh_mask: bool = True,
        refresh_points: bool = True,
    ) -> None:
        """Re-render native annotations while preserving selection state.

        Args:
            refresh_mask: Whether the outside-count-region mask should be rebuilt.
            refresh_points: Whether point graphics and outside-region warning
                rings should be redrawn.
        """
        self._clear_external_annotation_graphics()

        annotation_index: int
        annotation: Annotation
        for annotation_index, annotation in enumerate(self.external_annotations):
            self._render_external_annotation(annotation, annotation_index)
        self._render_external_annotation_handles()
        if refresh_mask:
            self.refresh_count_region_mask()
        if refresh_points:
            self.display_points()

    def refresh_external_annotation_styles(self) -> None:
        """Re-render current native annotations using configured symbology."""
        self._rerender_external_annotations(
            refresh_mask=False, refresh_points=False
        )

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

    def _render_bird_point(
        self,
        point: QtCore.QPointF,
        pen: QtGui.QPen,
        brush: QtGui.QBrush,
        *,
        highlight_outside: bool = False,
        count_regions: list[Annotation] | None = None,
    ) -> None:
        """Render one count point and an optional outside-region warning ring.

        Args:
            point: Point in source-image pixel coordinates.
            pen: Normal point outline.
            brush: Normal point fill.
            highlight_outside: Whether outside-region warning rings are enabled.
            count_regions: Precomputed count-region polygons for this redraw.
        """
        display_radius: float = float(self.ui['point']['radius'])
        point_rect: QtCore.QRectF = QtCore.QRectF(
            point.x() - ((display_radius - 1.0) / 2.0),
            point.y() - ((display_radius - 1.0) / 2.0),
            display_radius,
            display_radius,
        )
        item: QtWidgets.QGraphicsEllipseItem = self.addEllipse(
            point_rect, pen, brush
        )
        item.setData(0, "ddg_bird_point")
        item.setZValue(0.0)

        regions: list[Annotation] = count_regions or []
        if not highlight_outside or not regions:
            return
        point_xy: tuple[float, float] = (float(point.x()), float(point.y()))
        if any(point_in_polygon(point_xy, region.points) for region in regions):
            return

        warning_radius: float = display_radius + 10.0
        warning_rect: QtCore.QRectF = QtCore.QRectF(
            point.x() - ((warning_radius - 1.0) / 2.0),
            point.y() - ((warning_radius - 1.0) / 2.0),
            warning_radius,
            warning_radius,
        )
        warning_pen: QtGui.QPen = QtGui.QPen(QtGui.QColor(255, 64, 64), 3.0)
        warning_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        warning_item: QtWidgets.QGraphicsEllipseItem = self.addEllipse(
            warning_rect, warning_pen
        )
        warning_item.setData(0, "ddg_count_region_warning")
        warning_item.setToolTip(self.tr("Point is outside the count region"))
        warning_item.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        warning_item.setZValue(1.0)

    def display_points(self):
        self.clear_points()
        if not self.show_points:
            return
        if self.current_image_name in self.points:
            highlight_outside: bool = (
                self.highlight_outside_count_region_points_enabled()
            )
            regions: list[Annotation] = (
                count_region_polygons(self.external_annotations)
                if highlight_outside
                else []
            )
            active_color = QtGui.QColor(self.ui['point']['color'][0], self.ui['point']['color'][1], self.ui['point']['color'][2])
            active_brush = QtGui.QBrush(active_color, QtCore.Qt.BrushStyle.SolidPattern)
            active_pen = QtGui.QPen(active_brush, 2)
            for class_name in self.points[self.current_image_name]:
                points = self.points[self.current_image_name][class_name]
                brush = QtGui.QBrush(self.colors[class_name], QtCore.Qt.BrushStyle.SolidPattern)
                pen = QtGui.QPen(brush, 2)
                for point in points:
                    if class_name == self.current_class_name:
                        self._render_bird_point(
                            point,
                            active_pen,
                            active_brush,
                            highlight_outside=highlight_outside,
                            count_regions=regions,
                        )
                    else:
                        self._render_bird_point(
                            point,
                            pen,
                            brush,
                            highlight_outside=highlight_outside,
                            count_regions=regions,
                        )

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

    def _prepare_annotation_graphics_for_scene_clear(self) -> None:
        """Release annotation graphics before ``QGraphicsScene.clear``.

        Qt deletes the underlying C++ graphics items when a scene is cleared.
        Explicitly removing DDG-owned annotation items first prevents stale
        Python wrappers from surviving an image switch.
        """
        self._clear_count_region_mask()
        self._clear_external_annotation_graphics()
        self.external_annotations = []
        self.external_annotation_document = None
        self.selected_external_annotation_index = None

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
            # Tear down transient/view-owned graphics while their C++ objects
            # are still valid.  QGraphicsScene.clear() deletes all scene items.
            self.image_about_to_change.emit()
            self._prepare_annotation_graphics_for_scene_clear()
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
                        item.setZValue(-10.0)
                        item.moveBy(s, 0)
                    # Fix for windows, thin slivers at the end cause the app to hang. QImage bug?
                    if tail > 0:
                        tile = np.ones((array.shape[0], stride, array.shape[2]), dtype=np.uint8) * 255
                        tile[:, 0:tail] = array[:, max_stride:array.shape[1]]
                        qt_image = QtGui.QImage(tile.data, tile.shape[1], tile.shape[0], QtGui.QImage.Format.Format_RGB888)
                        pixmap = QtGui.QPixmap.fromImage(qt_image)
                        item = self.addPixmap(pixmap)
                        item.setZValue(-10.0)
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
                    image_item: QtWidgets.QGraphicsPixmapItem = self.addPixmap(self.pixmap)
                    image_item.setZValue(-10.0)
                self.display_external_annotations(file_name, refresh_points=False)
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
                image_name: str = event[1]
                class_name: str = event[2]
                point: QtCore.QPointF = event[3]
                self.points[image_name][class_name].append(point)
                self.update_point_count.emit(
                    image_name, class_name, len(self.points[image_name][class_name])
                )
                if self.current_image_name == image_name:
                    self.display_points()
                self.undo_queue.append(event)
            elif event[0] == 'delete':
                image_name = event[1]
                selection = event[2]
                for class_name, point in selection:
                    self.points[image_name][class_name].remove(point)
                    self.update_point_count.emit(
                        image_name,
                        class_name,
                        len(self.points[image_name][class_name]),
                    )
                if self.current_image_name == image_name:
                    self.display_points()
                self.undo_queue.append(event)
            elif event[0] == 'relabel':
                image_name = event[1]
                target_class_name: str = event[2]
                selection = event[3]
                for class_name, point in selection:
                    self.points[image_name][class_name].remove(point)
                    self.update_point_count.emit(
                        image_name,
                        class_name,
                        len(self.points[image_name][class_name]),
                    )
                    if target_class_name not in self.points[image_name]:
                        self.points[image_name][target_class_name] = []
                    self.points[image_name][target_class_name].append(point)
                self.update_point_count.emit(
                    image_name,
                    target_class_name,
                    len(self.points[image_name][target_class_name]),
                )
                if self.current_image_name == image_name:
                    self.display_points()
                self.undo_queue.append(event)
            elif event[0] == 'annotation_json':
                if self._apply_annotation_history_snapshot(
                    event[1], event[3], event[5]
                ):
                    self.undo_queue.append(event)
                else:
                    self.redo_queue.append(event)

    def redraw_image(self):
        if self.directory != '':
            self.load_image(self.directory + "/" + self.current_image_name, redraw=True)

    def relabel_selected_points(self):
        if self.current_class_name is not None:
            self.undo_queue.append(
                (
                    'relabel',
                    self.current_image_name,
                    self.current_class_name,
                    list(self.selection),
                )
            )
            self.redo_queue = []
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
        self.external_annotation_handle_items = []
        self.selected_external_annotation_index = None
        self.count_region_mask_item = None

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
                    selected_item: QtWidgets.QGraphicsEllipseItem = self.addEllipse(
                        QtCore.QRectF(
                            point.x() - offset,
                            point.y() - offset,
                            display_radius + 6,
                            display_radius + 6,
                        ),
                        self.selected_pen,
                    )
                    selected_item.setData(0, "ddg_selected_bird_point")
                    selected_item.setZValue(1.5)
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
        self.show_points = bool(display)
        if display:
            self.display_points()
            self.selection = []
        else:
            self.clear_points()

    def undo(self):
        if len(self.undo_queue) > 0:
            event = self.undo_queue.pop()
            if event[0] == 'add':
                image_name: str = event[1]
                class_name: str = event[2]
                point: QtCore.QPointF = event[3]
                self.points[image_name][class_name].remove(point)
                self.update_point_count.emit(
                    image_name, class_name, len(self.points[image_name][class_name])
                )
                if self.current_image_name == image_name:
                    self.display_points()
                self.redo_queue.append(event)
            elif event[0] == 'delete':
                image_name = event[1]
                selection = event[2]
                for class_name, point in selection:
                    if class_name not in self.points[image_name]:
                        self.points[image_name][class_name] = []
                    self.points[image_name][class_name].append(point)
                    self.update_point_count.emit(
                        image_name,
                        class_name,
                        len(self.points[image_name][class_name]),
                    )
                if self.current_image_name == image_name:
                    self.display_points()
                self.redo_queue.append(event)
            elif event[0] == 'relabel':
                image_name = event[1]
                target_class_name: str = event[2]
                selection = event[3]
                for class_name, point in selection:
                    self.points[image_name][target_class_name].remove(point)
                    self.update_point_count.emit(
                        image_name,
                        target_class_name,
                        len(self.points[image_name][target_class_name]),
                    )
                    if class_name not in self.points[image_name]:
                        self.points[image_name][class_name] = []
                    self.points[image_name][class_name].append(point)
                    self.update_point_count.emit(
                        image_name,
                        class_name,
                        len(self.points[image_name][class_name]),
                    )
                if self.current_image_name == image_name:
                    self.display_points()
                self.redo_queue.append(event)
            elif event[0] == 'annotation_json':
                if self._apply_annotation_history_snapshot(
                    event[1], event[2], event[4]
                ):
                    self.redo_queue.append(event)
                else:
                    self.undo_queue.append(event)

    def update_survey_id(self, text):
        self.survey_id = text
