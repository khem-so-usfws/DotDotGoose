"""Count-region QA dialog with navigation through outside bird points."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets


class CountRegionQADialog(QtWidgets.QDialog):
    """Display count-region QA results and navigate outside bird points."""

    point_requested = QtCore.pyqtSignal(QtCore.QPointF)

    def __init__(
        self,
        summary_lines: list[str],
        outside_points: list[tuple[str, QtCore.QPointF]],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initialize the QA dialog.

        Args:
            summary_lines: Human-readable QA summary lines.
            outside_points: ``(class_name, point)`` pairs outside valid regions.
            parent: Optional Qt parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Count Region QA"))
        self.setModal(True)
        self.resize(460, 360)

        self._outside_points: list[tuple[str, QtCore.QPointF]] = [
            (class_name, QtCore.QPointF(point))
            for class_name, point in outside_points
        ]
        self._current_index: int = 0

        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)

        summary: QtWidgets.QPlainTextEdit = QtWidgets.QPlainTextEdit(self)
        summary.setReadOnly(True)
        summary.setPlainText("\n".join(summary_lines))
        layout.addWidget(summary)

        self.point_label: QtWidgets.QLabel = QtWidgets.QLabel(self)
        self.point_label.setWordWrap(True)
        layout.addWidget(self.point_label)

        navigation_layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        self.previous_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            self.tr("Previous Outside Point"), self
        )
        self.next_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            self.tr("Next Outside Point"), self
        )
        self.previous_button.clicked.connect(self.previous_point)
        self.next_button.clicked.connect(self.next_point)
        navigation_layout.addWidget(self.previous_button)
        navigation_layout.addWidget(self.next_button)
        layout.addLayout(navigation_layout)

        buttons: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close, parent=self
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_navigation_state()

    def focus_current_point(self) -> None:
        """Center the image viewer on the currently selected outside point."""
        if not self._outside_points:
            return
        _, point = self._outside_points[self._current_index]
        self.point_requested.emit(QtCore.QPointF(point))

    def previous_point(self) -> None:
        """Move to the previous outside point and request viewer navigation."""
        if self._current_index <= 0:
            return
        self._current_index -= 1
        self._refresh_navigation_state()
        self.focus_current_point()

    def next_point(self) -> None:
        """Move to the next outside point and request viewer navigation."""
        if self._current_index >= len(self._outside_points) - 1:
            return
        self._current_index += 1
        self._refresh_navigation_state()
        self.focus_current_point()

    def _refresh_navigation_state(self) -> None:
        """Refresh point text and enablement of navigation controls."""
        count: int = len(self._outside_points)
        if count == 0:
            self.point_label.setText(
                self.tr("No bird points are outside the count region.")
            )
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        class_name, point = self._outside_points[self._current_index]
        self.point_label.setText(
            self.tr("Outside point {} of {}: {} at x={:.1f}, y={:.1f}").format(
                self._current_index + 1,
                count,
                class_name,
                point.x(),
                point.y(),
            )
        )
        self.previous_button.setEnabled(self._current_index > 0)
        self.next_button.setEnabled(self._current_index < count - 1)
