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
from ddg.annotations import Annotation

# from .ui_central_widget import Ui_central as CLASS_DIALOG
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
else:
    bundle_dir = os.path.dirname(__file__)
CLASS_DIALOG, _ = uic.loadUiType(os.path.join(bundle_dir, 'central_widget.ui'))


class CentralWidget(QtWidgets.QDialog, CLASS_DIALOG):

    load_custom_data = QtCore.pyqtSignal(dict)

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
        self.save_shortcut.activated.connect(self.canvas.undo)

        self.save_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.Key.Key_Y), self)
        self.save_shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.save_shortcut.activated.connect(self.canvas.redo)

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

    def cancel_annotation(self) -> None:
        """Cancel the in-progress native annotation, if any."""
        self.graphicsView.cancel_annotation()

    def start_annotation_selection(self) -> bool:
        """Start native annotation selection/edit mode.

        Returns:
            ``True`` when selection mode was started, otherwise ``False``.
        """
        if not self.canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before editing annotations."),
            )
            return False
        self.graphicsView.start_annotation_selection()
        return True

    def delete_selected_annotation(self) -> None:
        """Confirm and delete the currently selected native annotation."""
        annotation: Annotation | None = self.canvas.selected_external_annotation()
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
            self.canvas.delete_selected_external_annotation()

    def edit_selected_annotation_properties(self) -> None:
        """Edit the selected annotation's label and persistent lock state."""
        annotation: Annotation | None = self.canvas.selected_external_annotation()
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
        self.canvas.update_selected_external_annotation_properties(
            dialog.annotation_label(),
            dialog.annotation_locked(),
        )

    def set_selected_annotation_locked(self, locked: bool) -> None:
        """Set the persistent edit-lock state for the selected annotation.

        Args:
            locked: Whether editing should be locked.
        """
        if self.canvas.selected_external_annotation() is None:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("No Annotation Selected"),
                self.tr("Select an annotation before changing its lock state."),
            )
            return
        self.canvas.set_selected_external_annotation_locked(locked)

    def delete_annotation_vertex(
        self,
        annotation_index: int,
        vertex_index: int,
    ) -> None:
        """Delete one selected annotation vertex when geometry remains valid.

        Args:
            annotation_index: Index in the active image annotation list.
            vertex_index: Vertex to remove from the selected annotation.
        """
        annotation: Annotation | None = None
        if 0 <= annotation_index < len(self.canvas.external_annotations):
            annotation = self.canvas.external_annotations[annotation_index]
        if annotation is not None and annotation.locked:
            QtWidgets.QMessageBox.information(
                self,
                self.tr("Annotation Locked"),
                self.tr("Unlock the annotation before editing its vertices."),
            )
            return

        deleted: bool = self.canvas.delete_external_annotation_vertex(
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
        """Start drawing a native landmark point on the active image.

        Returns:
            ``True`` when landmark mode was started, otherwise ``False``.
        """
        if not self.canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before drawing a landmark."),
            )
            return False
        self.graphicsView.start_landmark_annotation()
        return True

    def start_cutline(self) -> bool:
        """Start drawing a native cutline on the active image.

        Returns:
            ``True`` when cutline mode was started, otherwise ``False``.
        """
        if not self.canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before drawing a cutline."),
            )
            return False
        self.graphicsView.start_line_annotation()
        return True

    def start_count_region_polygon(self) -> bool:
        """Start drawing a count-region polygon on the active image.

        Returns:
            ``True`` when polygon mode was started, otherwise ``False``.
        """
        if not self.canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before drawing a count region."),
            )
            return False
        self.graphicsView.start_polygon_annotation()
        return True

    def use_whole_image_count_region(self) -> None:
        """Replace active-image count regions with the full image extent."""
        if not self.canvas.current_image_name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("No Image Loaded"),
                self.tr("Load an image before defining a count region."),
            )
            return

        if self.canvas.has_count_regions():
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

        self.canvas.set_whole_image_count_region()

    def show_count_region_qa(self) -> None:
        """Show active-image bird-point QA for explicit count regions."""
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

        QtWidgets.QMessageBox.information(
            self,
            self.tr("Count Region QA"),
            "\n".join(lines),
        )

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
