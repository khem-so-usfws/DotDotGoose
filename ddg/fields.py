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
from __future__ import annotations

from PyQt6 import QtCore, QtWidgets


class LineText(QtWidgets.QLineEdit):
    """Single-line editor with explicit, flushable delayed updates."""

    update: QtCore.pyqtSignal = QtCore.pyqtSignal(str, str)
    edited: QtCore.pyqtSignal = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        """Create an editor with a timer owned by the editor.

        Args:
            parent: Labeled field container.
        """
        super().__init__(parent)
        self.timer: QtCore.QTimer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.fire)
        self.textEdited.connect(self.schedule)

    def schedule(self) -> None:
        """Mark text unsaved now and debounce its data update."""
        self.edited.emit()
        self.timer.start()

    def fire(self) -> None:
        """Commit text before its image binding changes."""
        self.timer.stop()
        self.update.emit(self.parentWidget().objectName(), self.text())

    def load_data(self, data: dict[str, str]) -> None:
        """Load an image value without scheduling a write or retaining stale text.

        Args:
            data: Custom-field values for the bound image.
        """
        self.timer.stop()
        blocker: QtCore.QSignalBlocker = QtCore.QSignalBlocker(self)
        self.setText(data.get(self.parentWidget().objectName(), ""))
        del blocker


class BoxText(QtWidgets.QTextEdit):
    """Multi-line editor with the same update semantics as single-line fields."""

    update: QtCore.pyqtSignal = QtCore.pyqtSignal(str, str)
    edited: QtCore.pyqtSignal = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        """Create a plain-text editor with delayed, flushable updates.

        Args:
            parent: Labeled field container.
        """
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.timer: QtCore.QTimer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.fire)
        self.textChanged.connect(self.schedule)

    def schedule(self) -> None:
        """Schedule updates for typing, paste, and other text edits."""
        self.edited.emit()
        self.timer.start()

    def fire(self) -> None:
        """Commit the pending plain text to the currently bound image."""
        self.timer.stop()
        self.update.emit(self.parentWidget().objectName(), self.toPlainText())

    def load_data(self, data: dict[str, str]) -> None:
        """Replace text, including missing/empty values, without writing it back.

        Args:
            data: Custom-field values for the bound image.
        """
        self.timer.stop()
        blocker: QtCore.QSignalBlocker = QtCore.QSignalBlocker(self)
        self.setPlainText(data.get(self.parentWidget().objectName(), ""))
        del blocker
