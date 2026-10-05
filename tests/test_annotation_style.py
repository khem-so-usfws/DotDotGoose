"""Tests for persistent native annotation symbology settings."""

from __future__ import annotations

from PyQt6 import QtCore

from ddg.annotations import (
    AnnotationShape,
    AnnotationStyle,
    load_annotation_style,
    save_annotation_style,
)


def test_annotation_style_round_trip(tmp_path) -> None:
    """Saved color and weight should load from an isolated QSettings file."""
    settings_path = tmp_path / "ddg-test.ini"
    settings: QtCore.QSettings = QtCore.QSettings(
        str(settings_path), QtCore.QSettings.Format.IniFormat
    )
    expected: AnnotationStyle = AnnotationStyle(color="#123456", width=2.5)

    save_annotation_style(AnnotationShape.LINE, expected, settings)
    settings.sync()
    actual: AnnotationStyle = load_annotation_style(AnnotationShape.LINE, settings)

    assert actual == expected


def test_invalid_stored_style_falls_back_to_defaults(tmp_path) -> None:
    """Malformed persisted values should not break annotation rendering."""
    settings_path = tmp_path / "ddg-test.ini"
    settings: QtCore.QSettings = QtCore.QSettings(
        str(settings_path), QtCore.QSettings.Format.IniFormat
    )
    settings.setValue("annotations/symbology/polygon/color", "not-a-color")
    settings.setValue("annotations/symbology/polygon/width", -10)

    style: AnnotationStyle = load_annotation_style(
        AnnotationShape.POLYGON, settings
    )

    assert style.color == "#ff00ff"
    assert style.width == 4.0
