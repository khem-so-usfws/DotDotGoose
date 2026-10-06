"""Release-metadata regression tests for the DDG fork."""

from __future__ import annotations

from typing import Any

from PyQt6 import QtWidgets

from ddg import __version__
from ddg.about_dialog import AboutDialog


def test_release_version_is_1_8_0() -> None:
    """The application should advertise the fork release as version 1.8.0."""
    assert __version__ == "1.8.0"


def test_about_dialog_lists_khem_so_as_contributor(qtbot: Any) -> None:
    """The About dialog should credit Khem So with the requested GitHub URL."""
    dialog: AboutDialog = AboutDialog()
    qtbot.addWidget(dialog)
    contributor_texts: list[str] = [
        label.text()
        for label in dialog.groupBoxContributors.findChildren(QtWidgets.QLabel)
    ]
    assert "Khem So, https://github.com/khem-so-usfws" in contributor_texts
