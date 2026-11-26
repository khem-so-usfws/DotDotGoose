"""Dialog for editing native annotation semantic properties."""

from __future__ import annotations

from PyQt6 import QtWidgets

from .annotations import Annotation, AnnotationShape
from .annotations.model import TEXT_LABEL


class AnnotationPropertiesDialog(QtWidgets.QDialog):
    """Edit the semantic label or visible text and the annotation lock state."""

    def __init__(
        self,
        annotation: Annotation,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize the properties dialog.

        Args:
            annotation: Annotation whose current values should be displayed.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Annotation Properties"))

        self.annotation: Annotation = annotation
        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        shape_value: QtWidgets.QLabel = QtWidgets.QLabel(annotation.shape_type.value)
        self.label_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(annotation.label)
        self.locked_checkbox: QtWidgets.QCheckBox = QtWidgets.QCheckBox(
            self.tr("Lock annotation against editing")
        )
        self.locked_checkbox.setChecked(annotation.locked)

        form.addRow(self.tr("Geometry:"), shape_value)
        if annotation.is_text_label:
            self.label_edit.setText(annotation.description or "")
            self.label_edit.setReadOnly(annotation.locked)
            form.addRow(self.tr("Text:"), self.label_edit)
        else:
            form.addRow(self.tr("Label:"), self.label_edit)
        form.addRow("", self.locked_checkbox)

        buttons: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def annotation_label(self) -> str:
        """Return the requested semantic label.

        Returns:
            Trimmed annotation label.
        """
        if self.annotation.is_text_label:
            return TEXT_LABEL
        return self.label_edit.text().strip()

    def annotation_description(self) -> str | None:
        """Return the new caption when text label content was changed."""
        if self.annotation.is_text_label and self.label_edit.isModified():
            return self.label_edit.text().strip()
        return None

    def annotation_locked(self) -> bool:
        """Return the requested lock state.

        Returns:
            Whether editing should be locked.
        """
        return self.locked_checkbox.isChecked()

    def accept(self) -> None:
        """Validate the label or caption before accepting changes."""
        label: str = self.annotation_label()
        if self.annotation.is_text_label:
            if self.annotation_description() == "":
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("Text Required"),
                    self.tr("Enter text for the label."),
                )
                return
        elif not label:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Annotation Label Required"),
                self.tr("Enter a label before saving annotation properties."),
            )
            return
        elif (
            self.annotation.shape_type is AnnotationShape.POINT and label == TEXT_LABEL
        ):
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Reserved Label"),
                self.tr("Use the Text Label tool to add text to an image."),
            )
            return
        super().accept()
