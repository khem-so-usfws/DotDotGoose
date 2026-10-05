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
from ddg import CentralWidget
from PyQt6 import QtWidgets, QtCore, QtGui
from ddg import AboutDialog
from ddg import __version__
from ddg.annotation_symbology_dialog import AnnotationSymbologyDialog
from ddg.annotations import AnnotationShape


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setWindowTitle('DotDotGoose [v {}]'.format(__version__))
        self.setWindowIcon(QtGui.QIcon("icons:ddg.png"))
        self.setCentralWidget(CentralWidget())
        self.about_dialog = AboutDialog(self)

        self.error_widget = QtWidgets.QTextBrowser()
        self.error_widget.setWindowTitle(self.tr('EXCEPTION DETECTED'))
        self.error_widget.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.error_widget.resize(900, 500)

        self.setMenuBar(QtWidgets.QMenuBar())
        self.menuBar().setNativeMenuBar(False)
        menu = self.menuBar().addMenu(self.tr('File'))
        menu.setObjectName('File')
        menu.addAction(self.tr('Quit'), self.quit)

        annotation_menu = self.menuBar().addMenu(self.tr("Annotations"))
        annotation_menu.setObjectName("Annotations")
        select_annotation_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Select/Edit Annotation")
        )
        select_annotation_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+E"))
        select_annotation_action.triggered.connect(self.start_annotation_selection)

        annotation_properties_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Annotation Properties...")
        )
        annotation_properties_action.triggered.connect(
            self.centralWidget().edit_selected_annotation_properties
        )
        lock_annotation_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Lock Selected Annotation")
        )
        lock_annotation_action.triggered.connect(
            lambda: self.centralWidget().set_selected_annotation_locked(True)
        )
        unlock_annotation_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Unlock Selected Annotation")
        )
        unlock_annotation_action.triggered.connect(
            lambda: self.centralWidget().set_selected_annotation_locked(False)
        )

        annotation_menu.addSeparator()
        draw_landmark_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Draw Landmark Point")
        )
        draw_landmark_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+M"))
        draw_landmark_action.triggered.connect(self.start_landmark_point)

        draw_line_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Draw Cutline")
        )
        draw_line_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+L"))
        draw_line_action.triggered.connect(self.start_cutline)

        draw_polygon_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Draw Count Region Polygon")
        )
        draw_polygon_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+P"))
        draw_polygon_action.triggered.connect(self.start_count_region_polygon)

        use_whole_image_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Use Whole Image as Count Region")
        )
        use_whole_image_action.triggered.connect(
            self.centralWidget().use_whole_image_count_region
        )

        annotation_menu.addSeparator()
        dim_outside_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Dim Outside Count Region")
        )
        dim_outside_action.setCheckable(True)
        dim_outside_action.setChecked(
            self.centralWidget().canvas.dim_outside_count_region_enabled()
        )
        dim_outside_action.toggled.connect(
            self.centralWidget().canvas.set_dim_outside_count_region
        )

        highlight_outside_points_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Highlight Points Outside Count Region")
        )
        highlight_outside_points_action.setCheckable(True)
        highlight_outside_points_action.setChecked(
            self.centralWidget().canvas.highlight_outside_count_region_points_enabled()
        )
        highlight_outside_points_action.toggled.connect(
            self.centralWidget().canvas.set_highlight_outside_count_region_points
        )

        warn_outside_point_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Warn When Adding Point Outside Count Region")
        )
        warn_outside_point_action.setCheckable(True)
        warn_outside_point_action.setChecked(
            self.centralWidget().canvas.warn_outside_count_region_point_enabled()
        )
        warn_outside_point_action.toggled.connect(
            self.centralWidget().canvas.set_warn_outside_count_region_point
        )

        count_region_qa_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Count Region QA...")
        )
        count_region_qa_action.triggered.connect(
            self.centralWidget().show_count_region_qa
        )

        annotation_menu.addSeparator()
        show_points_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Show Point Annotations")
        )
        show_points_action.setCheckable(True)
        show_points_action.setChecked(
            self.centralWidget().canvas.annotation_type_visible(
                AnnotationShape.POINT
            )
        )
        show_points_action.toggled.connect(
            lambda visible: self.centralWidget().canvas.set_annotation_type_visible(
                AnnotationShape.POINT, visible
            )
        )

        show_lines_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Show Line Annotations")
        )
        show_lines_action.setCheckable(True)
        show_lines_action.setChecked(
            self.centralWidget().canvas.annotation_type_visible(
                AnnotationShape.LINE
            )
        )
        show_lines_action.toggled.connect(
            lambda visible: self.centralWidget().canvas.set_annotation_type_visible(
                AnnotationShape.LINE, visible
            )
        )

        show_polygons_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Show Polygon Annotations")
        )
        show_polygons_action.setCheckable(True)
        show_polygons_action.setChecked(
            self.centralWidget().canvas.annotation_type_visible(
                AnnotationShape.POLYGON
            )
        )
        show_polygons_action.toggled.connect(
            lambda visible: self.centralWidget().canvas.set_annotation_type_visible(
                AnnotationShape.POLYGON, visible
            )
        )

        annotation_menu.addSeparator()
        symbology_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Symbology...")
        )
        symbology_action.triggered.connect(self.configure_annotation_symbology)

        annotation_menu.addSeparator()
        cancel_annotation_action: QtGui.QAction = annotation_menu.addAction(
            self.tr("Cancel Annotation")
        )
        cancel_annotation_action.triggered.connect(
            self.centralWidget().cancel_annotation
        )
        self.centralWidget().graphicsView.annotation_mode_changed.connect(
            self.annotation_mode_changed
        )

        menu = self.menuBar().addMenu(self.tr('Language'))
        menu.setObjectName('Language')
        menu.addAction(self.tr('Chinese (Mandarin)'), self.zh_Hans_CN)
        menu.addAction(self.tr('English'), self.en_US)
        menu.addAction(self.tr('French'), self.fr_FR)
        menu.addAction(self.tr('Hungarian'), self.hu_HU)
        menu.addAction(self.tr('Spanish'), self.es_CO)
        menu.addAction(self.tr('Vietnamese'), self.vi_VN)

        self.menuBar().addSeparator()

        self.menuBar().addAction(self.tr('About'), self.about_dialog.show)

    def annotation_mode_changed(self, mode: str) -> None:
        """Show concise guidance when annotation mode changes.

        Args:
            mode: Current graphics-view interaction mode.
        """
        if mode == "select":
            self.statusBar().showMessage(
                self.tr(
                    "Annotation edit: drag a shape to move it; drag a vertex "
                    "handle to reshape it; right-click a shape/vertex for insert "
                    "or delete; locked annotations can be selected but not "
                    "moved; Ctrl+Z/Ctrl+Y undo/redo; Esc exits edit mode."
                )
            )
        elif mode == "point":
            self.statusBar().showMessage(
                self.tr("Landmark point: click once to place; Esc to cancel.")
            )
        elif mode == "line":
            self.statusBar().showMessage(
                self.tr(
                    "Cutline: click vertices; Enter or double-click to finish; "
                    "Esc to cancel."
                )
            )
        elif mode == "polygon":
            self.statusBar().showMessage(
                self.tr(
                    "Count-region polygon: click vertices; Enter or double-click "
                    "to finish; Esc to cancel."
                )
            )
        else:
            self.statusBar().clearMessage()


    def configure_annotation_symbology(self) -> None:
        """Open annotation symbology settings and refresh visible annotations."""
        dialog: AnnotationSymbologyDialog = AnnotationSymbologyDialog(self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.centralWidget().canvas.refresh_external_annotation_styles()

    def start_annotation_selection(self) -> None:
        """Start native annotation selection/edit mode."""
        self.centralWidget().start_annotation_selection()

    def start_landmark_point(self) -> None:
        """Start native landmark point drawing."""
        self.centralWidget().start_landmark_point()

    def start_cutline(self) -> None:
        """Start native cutline drawing."""
        self.centralWidget().start_cutline()

    def start_count_region_polygon(self) -> None:
        """Start native count-region polygon drawing."""
        self.centralWidget().start_count_region_polygon()

    def closeEvent(self, event):
        if self.centralWidget().canvas.dirty_data_check():
            event.accept()
        else:
            event.ignore()

    def display_exception(self, error):
        self.error_widget.clear()
        for line in error:
            self.error_widget.append(line)
        self.error_widget.show()

    def en_US(self):
        settings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue('locale', 'en_US')
        self.restart_message()

    def es_CO(self):
        settings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue('locale', 'es_CO')
        self.restart_message()

    def fr_FR(self):
        settings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue('locale', 'fr')
        self.restart_message()

    def hu_HU(self):
        settings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue('locale', 'hu')
        self.restart_message()

    def vi_VN(self):
        settings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue('locale', 'vi_VN')
        self.restart_message()

    def zh_Hans_CN(self):
        settings = QtCore.QSettings("AMNH", "DotDotGoose")
        settings.setValue('locale', 'zh_Hans_CN')
        self.restart_message()

    def restart_message(self):
        QtWidgets.QMessageBox.warning(self, self.tr('Restart Required'), self.tr('You must restart the application for the language setting to be applied.'), QtWidgets.QMessageBox.StandardButton.Ok)

    def quit(self):
        self.close()
