"""Exercise companion selections through the pickers, exports, and project save."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import cast

import pytest
from PIL import Image
from PyQt6 import QtCore, QtWidgets
from pytestqt.qtbot import QtBot

from ddg.canvas import Canvas
from ddg.central_widget import CentralWidget
from ddg.exporter import Exporter
from ddg.image_workspace import ImageWorkspace
from ddg.main_window import MainWindow
from ddg.photo_selection import PhotoSelection, read_photo_selection
from test_workspace_controls import window  # noqa: F401


def write_selection(
    path: Path, photos: list[str], indices: list[int], *, checked: bool = False
) -> Path:
    """Write the companion fields that DotDotGoose reads."""
    index_field: str = "photo_indices" if checked else "counting_set"
    records: list[dict[str, str]] = [{"name": name} for name in photos]
    path.write_text(
        json.dumps({"schema_version": 1, "photos": records, index_field: indices}),
        encoding="utf-8",
    )
    return path


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read the emitted CSV with normal CSV quoting rules."""
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_companion_selection_formats(tmp_path: Path) -> None:
    """Tier 1 indexes candidates, and Tier 2 stores checked photos directly."""
    plan: Path = write_selection(
        tmp_path / "selection-plan.json", ["d.png", "b.png", "a.png"], [0, 2]
    )
    checked: Path = write_selection(
        tmp_path / "tier2-selection.json", ["c.png", "b.png"], [75, 12], checked=True
    )
    assert read_photo_selection(plan).names == ("a.png", "d.png")
    assert read_photo_selection(checked).names == ("b.png", "c.png")
    assert read_photo_selection(checked).description == "Tier 2 checked photos"


@pytest.mark.parametrize("index", [-1, True, 1])
def test_reject_invalid_plan_index(tmp_path: Path, index: int) -> None:
    """An invalid or Boolean index must never become a different photo."""
    plan: Path = write_selection(tmp_path / "selection-plan.json", ["a.png"], [index])
    with pytest.raises(ValueError, match="invalid photo index"):
        read_photo_selection(plan)


def test_filter_pickers_sidebar_and_navigation(
    window: MainWindow, qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apply the filter through View and retain existing selected pane photos."""
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    workspace: ImageWorkspace = cast(ImageWorkspace, widget.image_workspace)
    for name in ("c.png", "d.png"):
        Image.new("RGB", (1200, 800), (90, 100, 110)).save(tmp_path / name)
        widget.canvas.points[name] = {}
    workspace.set_count(4)
    workspace.toggle_float("reference")
    selected: list[str] = ["b.png", "d.png"]
    path: Path = write_selection(
        tmp_path / "tier2-selection.json",
        list(reversed(selected)),
        [93, 4],
        checked=True,
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileName", lambda *_: (str(path), "*.json")
    )
    window.load_photo_selection()
    qtbot.waitUntil(lambda: window.photo_selection_label.isVisible())

    assert window.photo_selection_label.text() == "Selected photos · 2 of 4"
    assert window.show_all_photos_action.isEnabled()
    assert workspace.docks["reference"].isFloating()
    assert widget.reference_canvas.current_image_name == "b.png"
    for pane, canvas in widget.image_panes.values():
        combo: QtWidgets.QComboBox = pane.image_combo
        assert [combo.itemText(i) for i in range(combo.count())] == selected
        assert canvas.current_image_name in selected
        assert canvas.current_image_name == pane.selected_image()

    model = widget.point_widget.model
    assert [model.item(i).text() for i in range(model.rowCount())] == selected
    widget._set_last_active_view("reference")
    widget.step_active_image(1)
    assert widget.reference_canvas.current_image_name == "d.png"
    widget.step_active_image(-1)
    assert widget.reference_canvas.current_image_name == "b.png"
    widget.load_active_image("a.png")
    assert widget.reference_canvas.current_image_name == "b.png"
    original: str | None = widget.canvas.current_image_name
    widget.canvas.load_image(str(tmp_path / "a.png"))
    assert widget.canvas.current_image_name == original

    # Clearing the filter restores all picker choices without switching photos.
    window.show_all_photos_action.trigger()
    assert widget.canvas.photo_selection is None
    assert not window.photo_selection_label.isVisible()
    assert widget.current_pane.image_combo.count() == 4
    assert model.rowCount() == 4
    assert widget.reference_canvas.current_image_name == "b.png"


def test_invalid_selection_and_pending_draft_preserve_scope(
    window: MainWindow, tmp_path: Path
) -> None:
    """Reject incomplete selections atomically and preserve unfinished sketches."""
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    selection: PhotoSelection = read_photo_selection(
        write_selection(tmp_path / "selection-plan.json", ["b.png"], [0])
    )
    assert widget.apply_photo_selection(selection)
    widget.canvas.points["missing.png"] = {}
    bad: PhotoSelection = read_photo_selection(
        write_selection(
            tmp_path / "bad.json", ["a.png", "missing.png", "elsewhere.png"], [0, 1, 2]
        )
    )
    with pytest.raises(ValueError, match=r"(?s)elsewhere\.png.*missing\.png"):
        widget.apply_photo_selection(bad)
    assert widget.canvas.photo_selection is selection
    assert widget.canvas.current_image_name == "b.png"
    assert widget.current_pane.image_combo.count() == 1

    widget.graphicsView.line_points.append(QtCore.QPointF(300, 300))
    try:
        assert not widget.apply_photo_selection(None)
        assert widget.canvas.photo_selection is selection
        assert widget.graphicsView.has_annotation_draft()
    finally:
        widget.graphicsView.line_points.clear()


def test_export_scope_and_full_project_save(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use the Export menu for both scopes and retain excluded data in .pnt."""
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    canvas: Canvas = widget.canvas
    canvas.points["a.png"] = {"Bird": [QtCore.QPointF(300, 400)]}
    canvas.points["b.png"] = {}
    comma_name: str = "c, selected.png"
    Image.new("RGB", (1200, 800)).save(tmp_path / comma_name)
    canvas.points[comma_name] = {"Bird": [QtCore.QPointF(120, 240)]}
    selected: list[str] = ["b.png", comma_name]
    choice: PhotoSelection = read_photo_selection(
        write_selection(tmp_path / "selection-plan.json", selected, [1, 0])
    )
    assert widget.apply_photo_selection(choice)

    output: list[Path] = []

    def choose_csv(
        _parent: QtWidgets.QWidget, _title: str, destination: str, _filters: str
    ) -> tuple[str, str]:
        """Save each CSV to the default name suggested by the export action."""
        output.append(Path(destination))
        return destination, "*.csv"

    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", choose_csv)
    export_menu: QtWidgets.QMenu = widget.point_widget.pushButtonExport.menu()
    counts, points, chips, overlay, all_photos = export_menu.actions()
    assert counts.text() == "Counts (selected photos)…"
    assert all_photos.text() == "All photos"

    counts.trigger()
    assert output[-1].name == "counts-selected.csv"
    count_rows: list[dict[str, str]] = read_rows(output[-1])
    assert [(row["image"], row["Bird"]) for row in count_rows] == [
        ("b.png", "0"),
        (comma_name, "1"),
    ]
    points.trigger()
    assert output[-1].name == "points-selected.csv"
    assert [row["image"] for row in read_rows(output[-1])] == [comma_name]

    choices: list[dict[str, dict[str, list[QtCore.QPointF]]]] = []

    class ChipProbe:
        """Capture the actual chip export input without decoding or cropping."""

        def __init__(
            self,
            _classes: list[str],
            points: dict[str, dict[str, list[QtCore.QPointF]]],
            _directory: str,
            _survey: str,
        ) -> None:
            """Record the photo scope passed from the export menu."""
            choices.append(points)

        def show(self) -> None:
            """Stand in for opening the image chip dialog."""

    monkeypatch.setattr("ddg.point_widget.ChipDialog", ChipProbe)
    chips.trigger()
    assert list(choices[-1]) == selected
    chips_directory: Path = tmp_path / "chips"
    chips_directory.mkdir()
    worker: Exporter = Exporter(
        canvas.survey_id,
        canvas.classes,
        choices[-1],
        str(tmp_path),
        str(chips_directory),
        24,
        24,
        ".png",
    )
    worker.run()
    chip_rows: list[dict[str, str]] = read_rows(chips_directory / "summary.csv")
    assert [row["image"] for row in chip_rows] == [comma_name]
    assert Path(chip_rows[0]["chip name"]).is_file()
    assert overlay.text() == "Overlay…"
    all_counts, all_points, all_chips = all_photos.menu().actions()
    all_counts.trigger()
    assert output[-1].name == "counts.csv"
    assert [row["image"] for row in read_rows(output[-1])] == ["a.png", *selected]
    all_points.trigger()
    assert [row["image"] for row in read_rows(output[-1])] == ["a.png", comma_name]
    all_chips.trigger()
    assert list(choices[-1]) == ["a.png", *selected]
    assert canvas.photo_selection is choice

    project: Path = tmp_path / "survey.pnt"
    assert canvas.save_points(str(project))
    data = json.loads(project.read_text(encoding="utf-8"))
    assert set(data["points"]) == {"a.png", *selected}
    assert data["points"]["a.png"]["Bird"] == [{"x": 300.0, "y": 400.0}]
    canvas.load_points(str(project))
    assert canvas.photo_selection is None
    assert set(canvas.points) == {"a.png", *selected}
    assert not window.photo_selection_label.isVisible()
