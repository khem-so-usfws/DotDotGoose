"""Tests for persistent native annotation symbology settings."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import QtCore

from ddg.annotations import (
    AnnotationShape,
    AnnotationStyle,
    annotation_visibility_enabled,
    load_annotation_style,
    save_annotation_style,
    save_annotation_visibility,
)


def test_annotation_style_round_trip(tmp_path: Path) -> None:
    """Saved color and weight should load from an isolated QSettings file."""
    settings_path: Path = tmp_path / "ddg-test.ini"
    settings: QtCore.QSettings = QtCore.QSettings(
        str(settings_path), QtCore.QSettings.Format.IniFormat
    )
    expected: AnnotationStyle = AnnotationStyle(color="#123456", width=2.5)

    save_annotation_style(AnnotationShape.LINE, expected, settings)
    settings.sync()
    actual: AnnotationStyle = load_annotation_style(AnnotationShape.LINE, settings)

    assert actual == expected


def test_invalid_stored_style_falls_back_to_defaults(tmp_path: Path) -> None:
    """Malformed persisted values should not break annotation rendering."""
    settings_path: Path = tmp_path / "ddg-test.ini"
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


def test_annotation_visibility_round_trip(tmp_path: Path) -> None:
    """Per-type visibility should persist independently of annotation JSON."""
    settings_path: Path = tmp_path / "ddg-visibility-test.ini"
    settings: QtCore.QSettings = QtCore.QSettings(
        str(settings_path), QtCore.QSettings.Format.IniFormat
    )

    save_annotation_visibility(AnnotationShape.LINE, False, settings)
    settings.sync()

    assert annotation_visibility_enabled(AnnotationShape.LINE, settings) is False
    assert annotation_visibility_enabled(AnnotationShape.POINT, settings) is True


def test_nonfinite_stored_width_falls_back_to_default(tmp_path: Path) -> None:
    """NaN/Infinity in settings must not reach QPen construction."""
    settings_path: Path = tmp_path / "ddg-nonfinite-style-test.ini"
    settings: QtCore.QSettings = QtCore.QSettings(
        str(settings_path), QtCore.QSettings.Format.IniFormat
    )
    settings.setValue("annotations/symbology/line/width", "nan")

    style: AnnotationStyle = load_annotation_style(AnnotationShape.LINE, settings)

    assert style.width == 4.0
