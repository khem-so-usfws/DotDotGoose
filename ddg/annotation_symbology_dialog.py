"""Dialog for configuring native annotation display symbology."""

from __future__ import annotations

from PyQt6 import QtGui, QtWidgets

from .annotations import (
    AnnotationShape,
    AnnotationStyle,
    load_annotation_style,
    save_annotation_style,
)


class AnnotationSymbologyDialog(QtWidgets.QDialog):
    """Edit color and stroke weight for native annotation geometry types."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the annotation symbology dialog.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Annotation Symbology"))
        self.color_buttons: dict[AnnotationShape, QtWidgets.QPushButton] = {}
        self.width_spins: dict[AnnotationShape, QtWidgets.QDoubleSpinBox] = {}
        self.colors: dict[AnnotationShape, str] = {}

        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        form: QtWidgets.QGridLayout = QtWidgets.QGridLayout()
        form.addWidget(QtWidgets.QLabel(self.tr("Annotation")), 0, 0)
        form.addWidget(QtWidgets.QLabel(self.tr("Color")), 0, 1)
        form.addWidget(QtWidgets.QLabel(self.tr("Weight (px)")), 0, 2)

        rows: list[tuple[AnnotationShape, str]] = [
            (AnnotationShape.POINT, self.tr("Landmark point")),
            (AnnotationShape.LINE, self.tr("Cutline")),
            (AnnotationShape.POLYGON, self.tr("Count region")),
        ]
        for row_index, (shape_type, label) in enumerate(rows, start=1):
            style: AnnotationStyle = load_annotation_style(shape_type)
            self.colors[shape_type] = style.color

            color_button: QtWidgets.QPushButton = QtWidgets.QPushButton()
            color_button.setMinimumWidth(110)
            color_button.clicked.connect(
                lambda checked=False, shape=shape_type: self._choose_color(shape)
            )
            self.color_buttons[shape_type] = color_button
            self._update_color_button(shape_type)

            width_spin: QtWidgets.QDoubleSpinBox = QtWidgets.QDoubleSpinBox()
            width_spin.setRange(0.5, 20.0)
            width_spin.setSingleStep(0.5)
            width_spin.setDecimals(1)
            width_spin.setValue(style.width)
            self.width_spins[shape_type] = width_spin

            form.addWidget(QtWidgets.QLabel(label), row_index, 0)
            form.addWidget(color_button, row_index, 1)
            form.addWidget(width_spin, row_index, 2)

        layout.addLayout(form)

        buttons: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        """Persist the chosen styles and close the dialog."""
        shape_type: AnnotationShape
        for shape_type in AnnotationShape:
            style: AnnotationStyle = AnnotationStyle(
                color=self.colors[shape_type],
                width=self.width_spins[shape_type].value(),
            )
            save_annotation_style(shape_type, style)
        super().accept()

    def _choose_color(self, shape_type: AnnotationShape) -> None:
        """Open a color chooser for one annotation geometry type.

        Args:
            shape_type: Annotation geometry whose color should be changed.
        """
        current_color: QtGui.QColor = QtGui.QColor(self.colors[shape_type])
        selected_color: QtGui.QColor = QtWidgets.QColorDialog.getColor(
            current_color,
            self,
            self.tr("Choose Annotation Color"),
        )
        if not selected_color.isValid():
            return
        self.colors[shape_type] = selected_color.name()
        self._update_color_button(shape_type)

    def _update_color_button(self, shape_type: AnnotationShape) -> None:
        """Update a color button to show its current color.

        Args:
            shape_type: Annotation geometry associated with the button.
        """
        color: QtGui.QColor = QtGui.QColor(self.colors[shape_type])
        text_color: str = "#000000" if color.lightness() > 140 else "#ffffff"
        button: QtWidgets.QPushButton = self.color_buttons[shape_type]
        button.setText(color.name())
        button.setStyleSheet(
            "QPushButton {"
            f"background-color: {color.name()};"
            f"color: {text_color};"
            "}"
        )
