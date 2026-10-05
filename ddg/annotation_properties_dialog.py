"""Dialog for editing native annotation semantic properties."""

from __future__ import annotations

from PyQt6 import QtWidgets

from .annotations import Annotation


class AnnotationPropertiesDialog(QtWidgets.QDialog):
    """Edit the label and lock state for one native annotation."""

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

        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        shape_value: QtWidgets.QLabel = QtWidgets.QLabel(annotation.shape_type.value)
        self.label_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(annotation.label)
        self.locked_checkbox: QtWidgets.QCheckBox = QtWidgets.QCheckBox(
            self.tr("Lock annotation against editing")
        )
        self.locked_checkbox.setChecked(annotation.locked)

        form.addRow(self.tr("Geometry:"), shape_value)
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
        return self.label_edit.text().strip()

    def annotation_locked(self) -> bool:
        """Return the requested lock state.

        Returns:
            Whether editing should be locked.
        """
        return self.locked_checkbox.isChecked()

    def accept(self) -> None:
        """Validate the semantic label before accepting changes."""
        if not self.annotation_label():
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Annotation Label Required"),
                self.tr("Enter a label before saving annotation properties."),
            )
            return
        super().accept()
