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
import sys
from typing import cast
from PyQt6 import QtCore, QtWidgets, QtGui, uic

from ddg import Canvas
from ddg import PointWidget
from ddg.fields import BoxText, LineText
from ddg.annotation_properties_dialog import AnnotationPropertiesDialog
from ddg.count_region_qa_dialog import CountRegionQADialog
from ddg.annotations import Annotation, AnnotationShape
from ddg.central_graphics_view import CentralGraphicsView
from ddg.compare_pane import ComparePane

# from .ui_central_widget import Ui_central as CLASS_DIALOG
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
else:
    bundle_dir = os.path.dirname(__file__)
CLASS_DIALOG, _ = uic.loadUiType(os.path.join(bundle_dir, 'central_widget.ui'))


class CentralWidget(QtWidgets.QDialog, CLASS_DIALOG):

    load_custom_data = QtCore.pyqtSignal(dict)
    compare_enabled_changed = QtCore.pyqtSignal(bool)
    compare_layout_changed = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self)
        self.setupUi(self)
        self.canvas = Canvas(self)

        self.point_widget = PointWidget(self.canvas, self)
        self.findChild(QtWidgets.QFrame, 'framePointWidget').layout().addWidget(self.point_widget)
        self.point_widget.hide_custom_fields.connect(self.hide_custom_fields)
        self.canvas.saving.connect(self.display_quick_save)

        # Keyboard shortcuts
        # Quick save using Ctrl+S
        self.save_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.Key.Key_S), self)
        self.save_shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.save_shortcut.activated.connect(self.canvas.quick_save)

        # Undo Redo shortcuts
        self.save_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.Key.Key_Z), self)
        self.save_shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.save_shortcut.activated.connect(self.undo_active_viewer)

        self.save_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.Key.Key_Y), self)
        self.save_shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.save_shortcut.activated.connect(self.redo_active_viewer)

        # Arrow short cuts to move among images
        self.up_arrow = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Up), self)
        self.up_arrow.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.up_arrow.activated.connect(self.point_widget.previous)

        self.down_arrow = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Down), self)
        self.down_arrow.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.down_arrow.activated.connect(self.point_widget.next)

        # Same as arrow keys but conventient for right handed people
        self.up_arrow = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_W), self)
        self.up_arrow.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.up_arrow.activated.connect(self.point_widget.previous)

        self.down_arrow = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_S), self)
        self.down_arrow.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.down_arrow.activated.connect(self.point_widget.next)

        # Make signal slot connections
        self.graphicsView.setScene(self.canvas)
        self.graphicsView.drop_complete.connect(self.canvas.load)
        self.graphicsView.region_selected.connect(self.canvas.select_points)
        self.graphicsView.delete_selection.connect(self.canvas.delete_selected_points)
        self.graphicsView.relabel_selection.connect(self.canvas.relabel_selected_points)
        self.graphicsView.toggle_points.connect(self.point_widget.checkBoxDisplayPoints.toggle)
        self.graphicsView.toggle_grid.connect(self.point_widget.checkBoxDisplayGrid.toggle)
        self.graphicsView.switch_class.connect(self.point_widget.set_active_class)
        self.graphicsView.add_point.connect(self.canvas.add_point)
        self.graphicsView.annotation_point_completed.connect(
            self.canvas.add_landmark_annotation
        )
        self.graphicsView.line_completed.connect(self.canvas.add_line_annotation)
        self.graphicsView.polygon_completed.connect(self.canvas.add_polygon_annotation)
        self.graphicsView.external_annotation_selected.connect(
            self.canvas.select_external_annotation
        )
        self.graphicsView.external_annotation_vertex_moved.connect(
            self.canvas.move_external_annotation_vertex
        )
        self.graphicsView.external_annotation_vertex_move_finished.connect(
            self.canvas.finish_external_annotation_vertex_move
        )
        self.graphicsView.external_annotation_moved.connect(
            self.canvas.move_external_annotation
        )
        self.graphicsView.external_annotation_move_finished.connect(
            self.canvas.finish_external_annotation_move
        )
        self.graphicsView.external_annotation_insert_vertex_requested.connect(
            self.canvas.insert_external_annotation_vertex
        )
        self.graphicsView.external_annotation_delete_vertex_requested.connect(
            self.delete_annotation_vertex
        )
        self.graphicsView.external_annotation_delete_requested.connect(
            self.delete_selected_annotation
        )
        self.graphicsView.external_annotation_properties_requested.connect(
            self.edit_selected_annotation_properties
        )
        self.graphicsView.external_annotation_lock_requested.connect(
            self.set_selected_annotation_locked
        )
        self.graphicsView.external_annotation_selection_cleared.connect(
            self.canvas.clear_external_annotation_selection
        )
        self.canvas.image_about_to_change.connect(
            self.graphicsView.prepare_for_image_change
        )
        self.canvas.image_loaded.connect(self.graphicsView.image_loaded)
        self.canvas.image_loaded.connect(self.graphicsView.reset_annotation_state)
        self.canvas.directory_set.connect(self.display_working_directory)

        # Lightweight two-image comparison. The normal DDG canvas remains the
        # authoritative Current image; this second canvas is annotation-only.
        self._main_image_before_change: str | None = None
        self._last_reference_image_name: str | None = None
        self._compare_enabled: bool = False
        self.reference_canvas: Canvas = Canvas(self)
        self.reference_canvas.show_grid = False
        self.reference_canvas.show_points = False
        self.compare_pane: ComparePane = ComparePane(self.frameCenter)
        self.reference_graphics_view: CentralGraphicsView = (
            self.compare_pane.graphics_view
        )
        self.reference_graphics_view.set_count_point_placement_enabled(False)
        self.reference_graphics_view.setScene(self.reference_canvas)
        self._last_active_view_name: str = "current"
        self.graphicsView.view_activated.connect(
            lambda: self._set_last_active_view("current")
        )
        self.reference_graphics_view.view_activated.connect(
            lambda: self._set_last_active_view("reference")
        )
        self._connect_reference_annotation_signals()
        self.reference_canvas.image_about_to_change.connect(
            self.reference_graphics_view.prepare_for_image_change
        )
        self.reference_canvas.image_loaded.connect(
            self.reference_graphics_view.image_loaded
        )
        self.reference_canvas.image_loaded.connect(
            self.reference_graphics_view.reset_annotation_state
        )
        self.compare_pane.image_requested.connect(self.load_reference_image)
        self.compare_pane.make_current_requested.connect(
            self.make_reference_current
        )
        self.compare_pane.hide_requested.connect(
            lambda: self.set_compare_enabled(False)
        )
        self.canvas.image_about_to_change.connect(
            self._remember_main_image_before_change
        )
        self.canvas.image_loaded.connect(self._main_image_changed)
        self.canvas.directory_set.connect(lambda _directory: self.refresh_compare_images())

        center_layout: QtWidgets.QVBoxLayout = cast(
            QtWidgets.QVBoxLayout, self.frameCenter.layout()
        )
        center_layout.removeWidget(self.graphicsView)
        self.current_pane: QtWidgets.QFrame = QtWidgets.QFrame(self.frameCenter)
        self.current_pane.setMinimumSize(0, 0)
        self.current_pane.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Ignored,
        )
        current_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(
            self.current_pane
        )
        current_layout.setSizeConstraint(
            QtWidgets.QLayout.SizeConstraint.SetNoConstraint
        )
        current_layout.setContentsMargins(2, 2, 2, 2)
        current_layout.setSpacing(2)
        self.current_compare_label: QtWidgets.QLabel = QtWidgets.QLabel(
            self.tr("★ CURRENT"), self.current_pane
        )
        self.current_compare_label.setStyleSheet("font-weight: bold;")
        self.current_compare_label.hide()
        current_layout.addWidget(self.current_compare_label)
        current_layout.addWidget(self.graphicsView, 1)

        self.compare_splitter: QtWidgets.QSplitter = QtWidgets.QSplitter(
            QtCore.Qt.Orientation.Horizontal, self.frameCenter
        )
        self.compare_splitter.setChildrenCollapsible(False)
        self.compare_splitter.addWidget(self.current_pane)
        self.compare_splitter.addWidget(self.compare_pane)
        self.compare_splitter.setStretchFactor(0, 1)
        self.compare_splitter.setStretchFactor(1, 1)
        center_layout.insertWidget(0, self.compare_splitter, 1)
        self.compare_pane.hide()
        settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
        saved_layout: str = str(settings.value("compare/layout", "1x2"))
        self.set_compare_layout(saved_layout if saved_layout in {"1x2", "2x1"} else "1x2")

        # Image data fields
        self.canvas.image_loaded.connect(self.display_coordinates)
        self.canvas.image_loaded.connect(self.get_custom_field_data)
        self.canvas.fields_updated.connect(self.display_custom_fields)
        self.lineEditX.textEdited.connect(self.update_coordinates)
        self.lineEditY.textEdited.connect(self.update_coordinates)

        # Buttons
        self.pushButtonAddField.clicked.connect(self.add_field_dialog)
        self.pushButtonDeleteField.clicked.connect(self.delete_field_dialog)
        self.pushButtonFolder.clicked.connect(self.select_folder)
        self.pushButtonZoomOut.clicked.connect(self.graphicsView.zoom_out)
        self.pushButtonZoomIn.clicked.connect(self.graphicsView.zoom_in)

        # Fix icons since no QRC file integration
        self.pushButtonFolder.setIcon(QtGui.QIcon('icons:folder.svg'))
        self.pushButtonZoomIn.setIcon(QtGui.QIcon('icons:zoom_in.svg'))
        self.pushButtonZoomOut.setIcon(QtGui.QIcon('icons:zoom_out.svg'))
        self.pushButtonDeleteField.setIcon(QtGui.QIcon('icons:delete.svg'))
        self.pushButtonAddField.setIcon(QtGui.QIcon('icons:add.svg'))

        self.quick_save_frame = QtWidgets.QFrame(self.graphicsView)
        self.quick_save_frame.setStyleSheet("QFrame { background: #4caf50;color: #FFF;font-weight: bold}")
        self.quick_save_frame.setLayout(QtWidgets.QHBoxLayout())
        self.quick_save_frame.layout().addWidget(QtWidgets.QLabel(self.tr('Saving...')))
        self.quick_save_frame.setGeometry(3, 3, 100, 35)
        self.quick_save_frame.hide()

        self.lineEditSurveyId.textChanged.connect(self.canvas.update_survey_id)
        self.canvas.points_loaded.connect(self.lineEditSurveyId.setText)

    def _connect_reference_annotation_signals(self) -> None:
        """Connect annotation editing for the reference viewer."""
        view: CentralGraphicsView = self.reference_graphics_view
        canvas: Canvas = self.reference_canvas
        view.annotation_point_completed.connect(canvas.add_landmark_annotation)
        view.line_completed.connect(canvas.add_line_annotation)
        view.polygon_completed.connect(canvas.add_polygon_annotation)
        view.external_annotation_selected.connect(canvas.select_external_annotation)
        view.external_annotation_vertex_moved.connect(
            canvas.move_external_annotation_vertex
        )
        view.external_annotation_vertex_move_finished.connect(
            canvas.finish_external_annotation_vertex_move
        )
        view.external_annotation_moved.connect(canvas.move_external_annotation)
        view.external_annotation_move_finished.connect(
            canvas.finish_external_annotation_move
        )
        view.external_annotation_insert_vertex_requested.connect(
            canvas.insert_external_annotation_vertex
        )
        view.external_annotation_delete_vertex_requested.connect(
            lambda annotation_index, vertex_index: self.delete_annotation_vertex_for_canvas(
                canvas, annotation_index, vertex_index
            )
        )
        view.external_annotation_delete_requested.connect(
            lambda: self.delete_selected_annotation_for_canvas(canvas)
        )
        view.external_annotation_properties_requested.connect(
            lambda: self.edit_selected_annotation_properties_for_canvas(canvas)
        )
        view.external_annotation_lock_requested.connect(
            lambda locked: self.set_selected_annotation_locked_for_canvas(
                canvas, locked
            )
        )
        view.external_annotation_selection_cleared.connect(
            canvas.clear_external_annotation_selection
        )

    def _set_last_active_view(self, view_name: str) -> None:
        """Remember the image pane most recently clicked by the user.

        Hover/focus is intentionally not used here. In a stacked comparison,
        moving the pointer from Reference to the menu can pass over Current;
        that must not silently retarget annotation commands.

        Args:
            view_name: ``"current"`` or ``"reference"``.
        """
        if view_name in {"current", "reference"}:
            self._last_active_view_name = view_name

    def _active_annotation_context(self) -> tuple[Canvas, CentralGraphicsView]:
        """Return the last-clicked canvas/view for annotation commands."""
        if self._compare_enabled and self._last_active_view_name == "reference":
            return self.reference_canvas, self.reference_graphics_view
        return self.canvas, self.graphicsView

    def undo_active_viewer(self) -> None:
        """Undo in the viewer that currently owns focus."""
        canvas, _view = self._active_annotation_context()
        canvas.undo()

    def redo_active_viewer(self) -> None:
        """Redo in the viewer that currently owns focus."""
        canvas, _view = self._active_annotation_context()
        canvas.redo()

    def compare_enabled(self) -> bool:
        """Return whether the reference comparison pane is visible."""
        return self._compare_enabled

    def compare_layout(self) -> str:
        """Return ``1x2`` for side-by-side or ``2x1`` for stacked layout."""
        return (
            "1x2"
            if self.compare_splitter.orientation() == QtCore.Qt.Orientation.Horizontal
            else "2x1"
        )

    def set_compare_enabled(self, enabled: bool) -> None:
        """Show or hide the lightweight second-image comparison pane.

        Args:
            enabled: Whether comparison should be visible.
        """
        enabled = bool(enabled)
        if enabled == self._compare_enabled:
            return
        if enabled and not self.canvas.current_image_name:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("Compare Images"),
                self.tr("Load images before opening the comparison pane."),
            )
            self.compare_enabled_changed.emit(False)
            return
        self._compare_enabled = enabled
        self.compare_pane.setVisible(enabled)
        self.current_compare_label.setVisible(enabled)
        if enabled:
            self.refresh_compare_images(
                preferred=self._last_reference_image_name, load_if_needed=True
            )
            self.compare_splitter.setSizes([1, 1])
        else:
            self.reference_graphics_view.cancel_annotation()
            self._last_reference_image_name = (
                self.reference_canvas.current_image_name
                or self.compare_pane.selected_image()
            )
            self.reference_canvas.release_image()
            self._last_active_view_name = "current"
        self.compare_enabled_changed.emit(enabled)

    def set_compare_layout(self, layout_name: str) -> None:
        """Set side-by-side or stacked comparison layout.

        Args:
            layout_name: ``1x2`` for horizontal or ``2x1`` for vertical.
        """
        normalized: str = "2x1" if layout_name == "2x1" else "1x2"
        orientation: QtCore.Qt.Orientation = (
            QtCore.Qt.Orientation.Vertical
            if normalized == "2x1"
            else QtCore.Qt.Orientation.Horizontal
        )
        if hasattr(self, "compare_splitter"):
            self.compare_splitter.setOrientation(orientation)
            if self._compare_enabled:
                self.compare_splitter.setSizes([1, 1])
        settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue("compare/layout", normalized)
        self.compare_layout_changed.emit(normalized)

    def _remember_main_image_before_change(self) -> None:
        """Remember the Current image so a reference promotion can swap panes."""
        self._main_image_before_change = self.canvas.current_image_name

    def _main_image_changed(self, directory: str, image_name: str) -> None:
        """Synchronize reference selection after Current image navigation.

        Args:
            directory: Current DDG working directory.
            image_name: Newly loaded Current image basename.
        """
        del directory
        self.current_compare_label.setText(
            self.tr("★ CURRENT — {}").format(image_name)
        )
        if not self._compare_enabled:
            return
        reference_name: str | None = self.reference_canvas.current_image_name
        previous_name: str | None = self._main_image_before_change
        if (
            reference_name == image_name
            and previous_name
            and previous_name != image_name
            and previous_name in self.canvas.points
        ):
            self.refresh_compare_images(preferred=previous_name)
            self.load_reference_image(previous_name)
        else:
            self.refresh_compare_images(preferred=reference_name, load_if_needed=True)

    def _available_reference_images(self) -> list[str]:
        """Return existing project images except the Current image."""
        current: str | None = self.canvas.current_image_name
        names: list[str] = []
        for image_name in sorted(self.canvas.points):
            if image_name == current:
                continue
            path: str = os.path.join(self.canvas.directory, image_name)
            if os.path.isfile(path):
                names.append(image_name)
        return names

    def refresh_compare_images(
        self,
        preferred: str | None = None,
        load_if_needed: bool = False,
    ) -> None:
        """Refresh the reference selector from DDG's existing image set.

        Args:
            preferred: Reference basename to preserve when possible.
            load_if_needed: Load a sensible reference if none is loaded.
        """
        names: list[str] = self._available_reference_images()
        selected: str | None = (
            preferred
            or self.reference_canvas.current_image_name
            or self._last_reference_image_name
        )
        if selected not in names:
            selected = self._default_reference_image(names)
        self.compare_pane.set_images(names, selected)
        if load_if_needed and selected:
            if self.reference_canvas.current_image_name != selected:
                self.load_reference_image(selected)

    def _default_reference_image(self, names: list[str]) -> str | None:
        """Choose the next image after Current when possible.

        Args:
            names: Eligible reference image basenames.
        """
        if not names:
            return None
        all_names: list[str] = sorted(self.canvas.points)
        current: str | None = self.canvas.current_image_name
        if current in all_names:
            current_index: int = all_names.index(current)
            for candidate in all_names[current_index + 1 :] + all_names[:current_index]:
                if candidate in names:
                    return candidate
        return names[0]

    def load_reference_image(self, image_name: str) -> None:
        """Load one image into the annotation-only reference canvas.

        Args:
            image_name: Image basename from the current DDG working directory.
        """
        if not image_name or image_name == self.canvas.current_image_name:
            return
        image_path: str = os.path.join(self.canvas.directory, image_name)
        if not os.path.isfile(image_path):
            return
        self.reference_canvas.directory = self.canvas.directory
        self.reference_canvas.load_image(image_path)
        self._last_reference_image_name = image_name
        self.compare_pane.select_image(image_name)

    def make_reference_current(self) -> None:
        """Promote the reference image to Current and swap the former Current."""
        reference_name: str | None = self.reference_canvas.current_image_name
        if not reference_name:
            return
        image_path: str = os.path.join(self.canvas.directory, reference_name)
        if os.path.isfile(image_path):
            self.canvas.load_image(image_path)

    def set_annotation_type_visible(
        self, shape_type: AnnotationShape, visible: bool
    ) -> None:
        """Apply native-annotation visibility to both displayed images."""
        self.canvas.set_annotation_type_visible(shape_type, visible)
        self.reference_canvas.set_annotation_type_visible(shape_type, visible)

    def set_dim_outside_count_region(self, enabled: bool) -> None:
        """Apply count-region dimming preference to both displayed images."""
        self.canvas.set_dim_outside_count_region(enabled)
        self.reference_canvas.set_dim_outside_count_region(enabled)

    def refresh_annotation_styles(self) -> None:
        """Refresh annotation symbology in Current and Reference panes."""
        self.canvas.refresh_external_annotation_styles()
        self.reference_canvas.refresh_external_annotation_styles()

    def cancel_annotation(self) -> None:
        """Cancel the in-progress native annotation in the focused pane."""
        _canvas, view = self._active_annotation_context()
        view.cancel_annotation()

    def start_annotation_selection(self) -> bool:
        """Start native annotation selection/edit mode in the focused pane."""
        canvas, view = self._active_annotation_context()
        if not canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before editing annotations."),
            )
            return False
        view.start_annotation_selection()
        return True

    def delete_selected_annotation(self) -> None:
        """Delete the selected annotation in the focused pane."""
        canvas, _view = self._active_annotation_context()
        self.delete_selected_annotation_for_canvas(canvas)

    def delete_selected_annotation_for_canvas(self, canvas: Canvas) -> None:
        """Confirm and delete the selected annotation on one canvas."""
        annotation: Annotation | None = canvas.selected_external_annotation()
        if annotation is None:
            return
        if annotation.locked:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("Annotation Locked"),
                self.tr("Unlock the annotation before deleting it."),
            )
            return
        response = QtWidgets.QMessageBox.question(
            self,
            self.tr("Delete Annotation"),
            self.tr("Delete the selected annotation? You can undo this with Ctrl+Z."),
        )
        if response == QtWidgets.QMessageBox.StandardButton.Yes:
            canvas.delete_selected_external_annotation()

    def edit_selected_annotation_properties(self) -> None:
        """Edit properties for the selected annotation in the focused pane."""
        canvas, _view = self._active_annotation_context()
        self.edit_selected_annotation_properties_for_canvas(canvas)

    def edit_selected_annotation_properties_for_canvas(self, canvas: Canvas) -> None:
        """Edit label and lock state for a selected annotation on one canvas."""
        annotation: Annotation | None = canvas.selected_external_annotation()
        if annotation is None:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("No Annotation Selected"),
                self.tr("Select an annotation before editing its properties."),
            )
            return
        dialog: AnnotationPropertiesDialog = AnnotationPropertiesDialog(
            annotation, self
        )
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        canvas.update_selected_external_annotation_properties(
            dialog.annotation_label(), dialog.annotation_locked()
        )

    def set_selected_annotation_locked(self, locked: bool) -> None:
        """Set lock state for the selected annotation in the focused pane."""
        canvas, _view = self._active_annotation_context()
        self.set_selected_annotation_locked_for_canvas(canvas, locked)

    def set_selected_annotation_locked_for_canvas(
        self, canvas: Canvas, locked: bool
    ) -> None:
        """Set persistent edit-lock state on one canvas."""
        if canvas.selected_external_annotation() is None:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("No Annotation Selected"),
                self.tr("Select an annotation before changing its lock state."),
            )
            return
        canvas.set_selected_external_annotation_locked(locked)

    def delete_annotation_vertex(
        self, annotation_index: int, vertex_index: int
    ) -> None:
        """Delete a selected vertex in the focused pane."""
        canvas, _view = self._active_annotation_context()
        self.delete_annotation_vertex_for_canvas(
            canvas, annotation_index, vertex_index
        )

    def delete_annotation_vertex_for_canvas(
        self,
        canvas: Canvas,
        annotation_index: int,
        vertex_index: int,
    ) -> None:
        """Delete a vertex on one canvas while preserving valid geometry."""
        annotation: Annotation | None = None
        if 0 <= annotation_index < len(canvas.external_annotations):
            annotation = canvas.external_annotations[annotation_index]
        if annotation is not None and annotation.locked:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("Annotation Locked"),
                self.tr("Unlock the annotation before editing its vertices."),
            )
            return
        deleted: bool = canvas.delete_external_annotation_vertex(
            annotation_index, vertex_index
        )
        if not deleted:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("Vertex Not Deleted"),
                self.tr(
                    "The vertex cannot be removed because the annotation must "
                    "retain the minimum number of vertices."
                ),
            )

    def start_landmark_point(self) -> bool:
        """Start drawing a landmark point in the focused image pane."""
        canvas, view = self._active_annotation_context()
        if not canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before drawing a landmark."),
            )
            return False
        view.start_landmark_annotation()
        return True

    def start_cutline(self) -> bool:
        """Start drawing a native cutline in the focused image pane."""
        canvas, view = self._active_annotation_context()
        if not canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before drawing a cutline."),
            )
            return False
        view.start_line_annotation()
        return True

    def start_count_region_polygon(self) -> bool:
        """Start drawing a count-region polygon in the focused image pane."""
        canvas, view = self._active_annotation_context()
        if not canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before drawing a count region."),
            )
            return False
        view.start_polygon_annotation()
        return True

    def use_whole_image_count_region(self) -> None:
        """Replace active-image count regions with the full image extent."""
        canvas, _view = self._active_annotation_context()
        if not canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before defining a count region."),
            )
            return

        if canvas.has_count_regions():
            response: QtWidgets.QMessageBox.StandardButton = (
                QtWidgets.QMessageBox.question(
                    self,
                    self.tr("Replace Count Regions"),
                    self.tr(
                        "Replace the existing count-region polygon(s) with "
                        "one whole-image count region?"
                    ),
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No,
                )
            )
            if response != QtWidgets.QMessageBox.StandardButton.Yes:
                return

        canvas.set_whole_image_count_region()

    def show_count_region_qa(self) -> None:
        """Show active-image count-region QA with outside-point navigation."""
        if not self.canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before running count-region QA."),
            )
            return

        qa: dict[str, object] = self.canvas.count_region_qa()
        if not bool(qa["has_regions"]):
            QtWidgets.QMessageBox.information(
                self,
                self.tr("Count Region QA"),
                self.tr("No count-region polygon is defined for this image."),
            )
            return

        inside: int = int(qa["inside"])
        outside: int = int(qa["outside"])
        lines: list[str] = [
            self.tr("Inside count region: {}").format(inside),
            self.tr("Outside count region: {}").format(outside),
        ]
        by_class: dict[str, dict[str, int]] = cast(
            dict[str, dict[str, int]], qa["by_class"]
        )
        if by_class:
            lines.append("")
            lines.append(self.tr("By class:"))
            for class_name in sorted(by_class):
                class_counts: dict[str, int] = by_class[class_name]
                lines.append(
                    self.tr("{}: {} inside, {} outside").format(
                        class_name,
                        class_counts["inside"],
                        class_counts["outside"],
                    )
                )

        dialog: CountRegionQADialog = CountRegionQADialog(
            summary_lines=lines,
            outside_points=self.canvas.outside_count_region_points(),
            parent=self,
        )
        dialog.point_requested.connect(self._center_on_count_region_qa_point)
        dialog.focus_current_point()
        dialog.exec()

    def _center_on_count_region_qa_point(self, point: QtCore.QPointF) -> None:
        """Center the image viewer on one outside-region point.

        Args:
            point: Point in source-image pixel coordinates.
        """
        self.graphicsView.centerOn(point)

    def resizeEvent(self, theEvent):
        self.graphicsView.resize_image()

    # Image data field functions
    def add_field(self):
        field_def = (self.field_name.text(), self.field_type.currentText())
        field_names = [x[0] for x in self.canvas.custom_fields['fields']]
        if field_def[0] in field_names:
            QtWidgets.QMessageBox.warning(self, self.tr('Warning'), self.tr('Field name already exists'))
        else:
            self.canvas.add_custom_field(field_def)
            self.add_dialog.close()

    def add_field_dialog(self):
        self.field_name = QtWidgets.QLineEdit()
        self.field_type = QtWidgets.QComboBox()
        self.field_type.addItems(['line', 'box'])
        self.add_button = QtWidgets.QPushButton(self.tr('Save'))
        self.add_button.clicked.connect(self.add_field)
        self.add_dialog = QtWidgets.QDialog(self)
        self.add_dialog.setWindowTitle(self.tr('Add Custom Field'))
        self.add_dialog.setLayout(QtWidgets.QVBoxLayout())
        self.add_dialog.layout().addWidget(self.field_name)
        self.add_dialog.layout().addWidget(self.field_type)
        self.add_dialog.layout().addWidget(self.add_button)
        self.add_dialog.resize(250, self.add_dialog.height())
        self.add_dialog.show()

    def delete_field(self):
        self.canvas.delete_custom_field(self.field_list.currentText())
        self.delete_dialog.close()

    def delete_field_dialog(self):
        self.field_list = QtWidgets.QComboBox()
        self.field_list.addItems([x[0] for x in self.canvas.custom_fields['fields']])
        self.delete_button = QtWidgets.QPushButton(self.tr('Delete'))
        self.delete_button.clicked.connect(self.delete_field)
        self.delete_dialog = QtWidgets.QDialog(self)
        self.delete_dialog.setWindowTitle(self.tr('Delete Custom Field'))
        self.delete_dialog.setLayout(QtWidgets.QVBoxLayout())
        self.delete_dialog.layout().addWidget(self.field_list)
        self.delete_dialog.layout().addWidget(self.delete_button)
        self.delete_dialog.resize(250, self.delete_dialog.height())
        self.delete_dialog.show()

    def display_coordinates(self, directory, image):
        if image in self.canvas.coordinates:
            self.lineEditX.setText(self.canvas.coordinates[image]['x'])
            self.lineEditY.setText(self.canvas.coordinates[image]['y'])
        else:
            self.lineEditX.setText('')
            self.lineEditY.setText('')

    def display_custom_fields(self, fields):

        def build(item):
            container = QtWidgets.QGroupBox(item[0], self)
            container.setObjectName(item[0])
            container.setLayout(QtWidgets.QVBoxLayout())
            if item[1].lower() == 'line':
                edit = LineText(container)
            else:
                edit = BoxText(container)
            edit.update.connect(self.canvas.save_custom_field_data)
            self.load_custom_data.connect(edit.load_data)
            container.layout().addWidget(edit)
            return container

        custom_fields = self.findChild(QtWidgets.QFrame, 'frameCustomFields')
        if custom_fields.layout() is None:
            custom_fields.setLayout(QtWidgets.QVBoxLayout())
        else:
            layout = custom_fields.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        for item in fields:
            widget = build(item)
            custom_fields.layout().addWidget(widget)
        v = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        custom_fields.layout().addItem(v)
        self.get_custom_field_data()

    def display_working_directory(self, directory):
        self.labelWorkingDirectory.setText(directory)

    def display_quick_save(self):
        self.quick_save_frame.show()
        QtCore.QTimer.singleShot(500, self.quick_save_frame.hide)

    def get_custom_field_data(self):
        self.load_custom_data.emit(self.canvas.get_custom_field_data())

    def hide_custom_fields(self, hide):
        if hide is True:
            self.frameCustomField.hide()
        else:
            self.frameCustomField.show()

    def select_folder(self):
        name = QtWidgets.QFileDialog.getExistingDirectory(self, self.tr('Select image folder'), self.canvas.directory)
        if name != '':
            self.canvas.load([QtCore.QUrl('file:{}'.format(name))])

    def update_coordinates(self, text):
        x = self.lineEditX.text()
        y = self.lineEditY.text()
        self.canvas.save_coordinates(x, y)
