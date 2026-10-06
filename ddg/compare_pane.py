# -*- coding: utf-8 -*-
"""Lightweight second-image comparison pane for DotDotGoose."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from .central_graphics_view import CentralGraphicsView


class ComparePane(QtWidgets.QFrame):
    """Reference-image viewer controls and graphics view.

    The pane owns no project state itself.  ``CentralWidget`` supplies the
    available image names and responds to the emitted selection/navigation
    signals.
    """

    image_requested: QtCore.pyqtSignal = QtCore.pyqtSignal(str)
    make_current_requested: QtCore.pyqtSignal = QtCore.pyqtSignal()
    hide_requested: QtCore.pyqtSignal = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Create the reference pane.

        Args:
            parent: Optional Qt parent widget.
        """
        super().__init__(parent)
        self.setObjectName("compareReferencePane")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Ignored,
        )

        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        header: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        self.label: QtWidgets.QLabel = QtWidgets.QLabel(self.tr("REFERENCE"), self)
        self.label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.label)

        self.image_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(self)
        self.image_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.image_combo.setMinimumContentsLength(8)
        self.image_combo.setMinimumWidth(0)
        self.image_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        header.addWidget(self.image_combo, 1)

        self.previous_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            self.tr("Prev"), self
        )
        self.next_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            self.tr("Next"), self
        )
        self.make_current_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            self.tr("Make Current"), self
        )
        self.fit_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            self.tr("Fit"), self
        )
        self.actual_size_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            self.tr("1:1"), self
        )
        self.close_button: QtWidgets.QPushButton = QtWidgets.QPushButton("×", self)
        self.close_button.setToolTip(self.tr("Hide comparison pane"))
        self.close_button.setMaximumWidth(30)

        for button in (
            self.previous_button,
            self.next_button,
            self.make_current_button,
            self.fit_button,
            self.actual_size_button,
            self.close_button,
        ):
            header.addWidget(button)
        layout.addLayout(header)

        self.graphics_view: CentralGraphicsView = CentralGraphicsView(self)
        self.graphics_view.setMinimumSize(0, 0)
        layout.addWidget(self.graphics_view, 1)

        self.image_combo.currentTextChanged.connect(self._request_selected_image)
        self.previous_button.clicked.connect(self.previous_image)
        self.next_button.clicked.connect(self.next_image)
        self.make_current_button.clicked.connect(self.make_current_requested.emit)
        self.fit_button.clicked.connect(self.fit_image)
        self.actual_size_button.clicked.connect(self.actual_size)
        self.close_button.clicked.connect(self.hide_requested.emit)

    def set_images(self, image_names: list[str], selected: str | None = None) -> None:
        """Replace selectable image names without emitting a load request.

        Args:
            image_names: Image basenames available for reference viewing.
            selected: Image to preserve/select when present.
        """
        blocker: QtCore.QSignalBlocker = QtCore.QSignalBlocker(self.image_combo)
        self.image_combo.clear()
        self.image_combo.addItems(image_names)
        if selected and selected in image_names:
            self.image_combo.setCurrentText(selected)
        del blocker
        enabled: bool = self.image_combo.count() > 0
        self.image_combo.setEnabled(enabled)
        self.previous_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)
        self.make_current_button.setEnabled(enabled)

    def selected_image(self) -> str | None:
        """Return the currently selected reference image basename."""
        text: str = self.image_combo.currentText().strip()
        return text if text else None

    def select_image(self, image_name: str) -> None:
        """Select an image in the combo without emitting a load request.

        Args:
            image_name: Image basename already present in the selector.
        """
        index: int = self.image_combo.findText(image_name)
        if index < 0:
            return
        blocker: QtCore.QSignalBlocker = QtCore.QSignalBlocker(self.image_combo)
        self.image_combo.setCurrentIndex(index)
        del blocker

    def previous_image(self) -> None:
        """Select the previous available reference image."""
        count: int = self.image_combo.count()
        if count <= 0:
            return
        index: int = max(0, self.image_combo.currentIndex() - 1)
        self.image_combo.setCurrentIndex(index)

    def next_image(self) -> None:
        """Select the next available reference image."""
        count: int = self.image_combo.count()
        if count <= 0:
            return
        index: int = min(count - 1, self.image_combo.currentIndex() + 1)
        self.image_combo.setCurrentIndex(index)

    def fit_image(self) -> None:
        """Fit the reference image to the available viewport."""
        scene: QtWidgets.QGraphicsScene | None = self.graphics_view.scene()
        if scene is None or not scene.items():
            return
        self.graphics_view.resetTransform()
        self.graphics_view.fitInView(
            scene.itemsBoundingRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio
        )

    def actual_size(self) -> None:
        """Display the reference image at a 1:1 scene/view scale."""
        self.graphics_view.resetTransform()

    def _request_selected_image(self, image_name: str) -> None:
        """Emit a non-empty selector change.

        Args:
            image_name: Newly selected image basename.
        """
        if image_name:
            self.image_requested.emit(image_name)
