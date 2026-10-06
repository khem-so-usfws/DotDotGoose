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

import os
import sys
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets, uic

from ddg import __version__

# from .ui_central_widget import Ui_central as CLASS_DIALOG
bundle_dir: str
if getattr(sys, "frozen", False):
    bundle_dir = sys._MEIPASS
else:
    bundle_dir = os.path.dirname(__file__)
CLASS_DIALOG: type[Any]
_UI_BASE: type[Any]
CLASS_DIALOG, _UI_BASE = uic.loadUiType(
    os.path.join(bundle_dir, "about_dialog.ui")
)


class AboutDialog(QtWidgets.QDialog, CLASS_DIALOG):
    """Display DotDotGoose version, developer, and contributor credits."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the About dialog.

        Args:
            parent: Optional Qt parent widget.
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.setupUi(self)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        self.groupBoxDevelopers.setLayout(QtWidgets.QVBoxLayout())
        self.groupBoxContributors.setLayout(QtWidgets.QVBoxLayout())
        self.groupBoxTranslators.setLayout(QtWidgets.QVBoxLayout())

        self.labelVersion.setText(__version__)

        entry: QtWidgets.QLabel = QtWidgets.QLabel(
            "Peter J. Ersts, {}".format(
                self.tr("Center for Biodiversity and Conservation")
            )
        )
        font: QtGui.QFont = entry.font()
        font.setPointSize(10)
        entry.setFont(font)
        self.groupBoxDevelopers.layout().addWidget(entry)

        contributor_labels: tuple[str, ...] = (
            "Ido Senesh, https://github.com/idoadse",
            "Julie Young, https://github.com/julieyoung6",
            "Ștefan Istrate, https://github.com/stefanistrate",
            "Khem So, https://github.com/khem-so-usfws",
        )
        for label_text in contributor_labels:
            contributor_entry: QtWidgets.QLabel = QtWidgets.QLabel(label_text)
            contributor_entry.setFont(font)
            self.groupBoxContributors.layout().addWidget(contributor_entry)

        translator_labels: tuple[str, ...] = (
            "{} : Julie Young, [{}] {}, https://github.com/julieyoung6".format(
                self.tr("Chinese (Mandarin)"),
                self.tr("Intern"),
                self.tr("Center for Biodiversity and Conservation"),
            ),
            "{} : Adrien Charbonneau, "
            "https://github.com/Adri-Charbonneau ".format(self.tr("French")),
            "{} : Charles K Barcza, "
            "https://github.com/blackPantherOS ".format(self.tr("Hungarian")),
            "{} : Mary Blair & Daniel López Lozano, {}".format(
                self.tr("Spanish"),
                self.tr("Center for Biodiversity and Conservation"),
            ),
            "{} : Nguyễn Tuấn Anh, {}".format(
                self.tr("Vietnamese"),
                self.tr(
                    "University of Science, Vietnam National University, Hanoi"
                ),
            ),
        )
        for label_text in translator_labels:
            translator_entry: QtWidgets.QLabel = QtWidgets.QLabel(label_text)
            translator_entry.setFont(font)
            self.groupBoxTranslators.layout().addWidget(translator_entry)
