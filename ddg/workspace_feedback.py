"""Pane-local display adjustments and counting-workspace feedback."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from time import monotonic
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

from .canvas import Canvas
from .central_graphics_view import CentralGraphicsView, InteractionMode
from .compare_pane import ComparePane

if TYPE_CHECKING:
    from .central_widget import CentralWidget
    from .workspace_controls import WorkspaceControls


class EnhancementDialog(QtWidgets.QDialog):
    """Apply display adjustments to one explicitly named pane."""

    def __init__(
        self, owner: WorkspaceFeedback, pane: ComparePane, canvas: Canvas
    ) -> None:
        """Build controls for the pane's currently loaded image.

        Args:
            owner: Workspace coordinator.
            pane: Target image pane.
            canvas: Target scene.
        """
        super().__init__(pane)
        self.owner: WorkspaceFeedback = owner
        self.pane: ComparePane = pane
        self.canvas: Canvas = canvas
        self.image_path: str = str(canvas.image_cache["file_name"])
        self.setWindowTitle(f"Enhance {pane.label.text().title()}")
        layout: QtWidgets.QFormLayout = QtWidgets.QFormLayout(self)
        self.brightness: QtWidgets.QSpinBox = QtWidgets.QSpinBox(self)
        self.brightness.setRange(0, 128)
        self.contrast: QtWidgets.QSpinBox = QtWidgets.QSpinBox(self)
        self.contrast.setRange(-100, 100)
        values: tuple[int, int] = canvas.enhancements.get(self.image_path, (0, 0))
        self.brightness.setValue(values[0])
        self.contrast.setValue(values[1])
        layout.addRow("Brightness", self.brightness)
        layout.addRow("Contrast", self.contrast)
        self.original: QtWidgets.QCheckBox = QtWidgets.QCheckBox("Show original", self)
        layout.addRow(self.original)
        buttons: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(self)
        apply_button: QtWidgets.QPushButton = buttons.addButton(
            "Apply", QtWidgets.QDialogButtonBox.ButtonRole.ApplyRole
        )
        reset_button: QtWidgets.QPushButton = buttons.addButton(
            "Reset", QtWidgets.QDialogButtonBox.ButtonRole.ResetRole
        )
        buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        apply_button.clicked.connect(self.apply)
        reset_button.clicked.connect(self.reset)
        self.original.toggled.connect(self.preview)
        layout.addRow(buttons)
        canvas.image_loaded.connect(self.image_changed)

    def image_changed(self, directory: str, name: str) -> None:
        """Close adjustments when their target image changes.

        Args:
            directory: Image directory.
            name: Image basename.
        """
        if os.path.join(directory, name) != self.image_path:
            self.close()

    def apply(self) -> None:
        """Apply both values together to avoid repeated large-image redraws."""
        if (
            self.pane.graphics_view.line_points
            or self.pane.graphics_view.polygon_points
        ):
            self.owner.notice = (
                "Finish (Enter) or cancel (Esc) the shape before enhancing."
            )
            self.owner.refresh()
            return
        self.canvas.enhancements[self.image_path] = (
            self.brightness.value(),
            self.contrast.value(),
        )
        blocker: QtCore.QSignalBlocker = QtCore.QSignalBlocker(self.original)
        self.original.setChecked(False)
        del blocker
        self.preview()

    def reset(self) -> None:
        """Restore neutral display settings for this image."""
        self.brightness.setValue(0)
        self.contrast.setValue(0)
        self.apply()

    def preview(self) -> None:
        """Temporarily compare original pixels with the applied adjustments."""
        values: tuple[int, int] = (
            (0, 0)
            if self.original.isChecked()
            else self.canvas.enhancements.get(self.image_path, (0, 0))
        )
        self.owner.adjust_image(self.pane, self.canvas, values)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Restore the enhanced display when an original preview is closed.

        Args:
            event: Dialog close event.
        """
        if (
            self.original.isChecked()
            and self.canvas.image_cache["file_name"] == self.image_path
        ):
            self.original.setChecked(False)
        super().closeEvent(event)


class WorkspaceFeedback(QtCore.QObject):
    """Coordinate view memory, explicit pane feedback, and recovery snapshots."""

    def __init__(self, widget: CentralWidget) -> None:
        """Attach feedback to the existing workspace without owning project data.

        Args:
            widget: Fully initialized counting workspace.
        """
        super().__init__(widget)
        self.widget: CentralWidget = widget
        self.controls: WorkspaceControls | None = None
        self.transfer_mode: InteractionMode | None = None
        self.last_tool_view: CentralGraphicsView | None = None
        self.notice: str = ""
        self.last_save: str = ""
        self.save_notice_until: float = 0.0
        self.save_error: bool = False
        self.recovery_text: str = "Recovery snapshots every 2 minutes"
        self.states: dict[
            tuple[int, str], tuple[QtGui.QTransform, QtCore.QPointF, int]
        ] = {}
        self.paths: dict[int, str] = {}
        self.dialogs: list[EnhancementDialog] = []
        self.panes: tuple[tuple[ComparePane, Canvas], ...] = (
            (widget.current_pane, widget.canvas),
            (widget.compare_pane, widget.reference_canvas),
        )
        self.labels: list[QtWidgets.QLabel] = []
        self.selection_buttons: list[QtWidgets.QToolButton] = []
        # Enhancement now lives with its image, rather than in the shared sidebar.
        widget.point_widget.groupBox.hide()
        for pane, canvas in self.panes:
            view: CentralGraphicsView = pane.graphics_view
            enhance: QtWidgets.QPushButton = QtWidgets.QPushButton("Enhance", pane)
            enhance.setToolTip("Adjust brightness and contrast for this pane")
            pane.layout().itemAt(1).layout().addWidget(enhance)
            enhance.clicked.connect(
                lambda _checked=False, p=pane, c=canvas: self.enhance(p, c)
            )
            label: QtWidgets.QLabel = QtWidgets.QLabel(pane)
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setFixedHeight(label.fontMetrics().height() * 2 + 4)
            label.hide()
            selection: QtWidgets.QToolButton = QtWidgets.QToolButton(pane)
            selection.setPopupMode(
                QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
            )
            menu: QtWidgets.QMenu = QtWidgets.QMenu(selection)
            menu.addAction(
                "Move dots by pixel offset…", lambda p=pane: self.move_selection(p)
            )
            menu.addAction("Delete selected dots", canvas.delete_selected_points)
            menu.addAction(
                "Clear dot selection", lambda c=canvas: self.clear_selection(c)
            )
            selection.setMenu(menu)
            selection.setFixedWidth(
                selection.fontMetrics().horizontalAdvance("9999 dots") + 26
            )
            pane.layout().itemAt(1).layout().addWidget(selection)
            pane.overflow_menu.addAction(
                "Reset view", lambda v=view: self.reset_view(v)
            )
            self.labels.append(label)
            self.selection_buttons.append(selection)
            canvas.image_about_to_change.connect(lambda v=view: self.remember(v))
            canvas.image_loaded.connect(
                lambda directory, name, v=view: self.restore(v, directory, name)
            )
            view.annotation_mode_changed.connect(
                lambda mode, v=view: self.tool_changed(v, mode)
            )
            view.annotation_cancel_requested.connect(self.cancel_transfer)
        self.save_label: QtWidgets.QLabel = QtWidgets.QLabel(widget)
        self.save_label.setWordWrap(False)
        self.save_label.hide()
        self.save_label.setToolTip(
            "Point and field edits require Save. Native annotations save immediately. "
            "Recovery files can be opened like other .pnt files from the same image folder."
        )
        self.recover_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            widget.point_widget
        )
        self.recover_button.setText("Recover…")
        self.recover_button.setToolTip("Open recovery snapshots or their folder")
        self.recover_button.setIcon(QtGui.QIcon("icons:recover.svg"))
        self.recover_button.setIconSize(widget.point_widget.pushButtonSave.iconSize())
        self.recover_button.setStyleSheet("text-align: left;")
        recovery_menu: QtWidgets.QMenu = QtWidgets.QMenu(self.recover_button)
        recovery_menu.addAction("Open recovery snapshot…", self.recover)
        recovery_menu.addAction("Open recovery folder", self.open_recovery_folder)
        recovery_menu.aboutToShow.connect(self.update_recovery_menu)
        self.recover_button.setMenu(recovery_menu)
        widget.point_widget.gridLayout_4.addWidget(self.recover_button, 7, 1)
        widget.canvas.save_finished.connect(self.saved)
        widget.canvas.points_loaded.connect(self.project_loaded)
        self.feedback_timer: QtCore.QTimer = QtCore.QTimer(self)
        self.feedback_timer.timeout.connect(self.refresh)
        self.feedback_timer.start(250)
        self.recovery_timer: QtCore.QTimer = QtCore.QTimer(self)
        self.recovery_timer.timeout.connect(self.write_recovery)
        self.recovery_timer.start(120000)
        self.refresh()

    def enhance(self, pane: ComparePane, canvas: Canvas) -> None:
        """Open one adjustment dialog for a loaded pane.

        Args:
            pane: Target pane.
            canvas: Corresponding image scene.
        """
        if not canvas.current_image_name:
            return
        for dialog in self.dialogs:
            if dialog.canvas is canvas and dialog.isVisible():
                dialog.raise_()
                return
        dialog: EnhancementDialog = EnhancementDialog(self, pane, canvas)
        self.dialogs.append(dialog)
        dialog.finished.connect(lambda _result, d=dialog: self.close_dialog(d))
        dialog.show()

    def close_dialog(self, dialog: EnhancementDialog) -> None:
        """Release a finished adjustment dialog and its scene signal connections.

        Args:
            dialog: Dialog being closed.
        """
        if dialog in self.dialogs:
            self.dialogs.remove(dialog)
        dialog.deleteLater()

    def adjust_image(
        self, pane: ComparePane, canvas: Canvas, values: tuple[int, int]
    ) -> None:
        """Redraw enhanced pixels while preserving the view and dot selection.

        Args:
            pane: Target pane.
            canvas: Target scene.
            values: Brightness and contrast values.
        """
        view: CentralGraphicsView = pane.graphics_view
        if view.line_points or view.polygon_points:
            self.notice = "Finish (Enter) or cancel (Esc) the shape before enhancing."
            self.refresh()
            return
        self.remember(view)
        navigator: QtGui.QImage = QtGui.QImage(view.navigator_image)
        navigator_size: QtCore.QSize = QtCore.QSize(view.navigator_source_size)
        selected: list[tuple[str, QtCore.QPointF]] = list(canvas.selection)
        canvas.generate_lookup_table(*values)
        canvas.redraw_image()
        canvas.selection = selected
        canvas.display_points()
        self.restore(view, canvas.directory, canvas.current_image_name or "")
        view.navigator_path = str(canvas.image_cache["file_name"])
        view.navigator_image = navigator
        view.navigator_source_size = navigator_size
        view.viewport().update()

    def remember(self, view: CentralGraphicsView) -> None:
        """Capture the displayed image's transform and source-space center.

        Args:
            view: View about to change images or redraw.
        """
        key: int = id(view)
        path: str = self.paths.get(key, "")
        if path and view.scene() is not None:
            self.states[(key, path)] = (
                QtGui.QTransform(view.transform()),
                view.mapToScene(view.viewport().rect().center()),
                view.rotation_degrees,
            )

    def restore(self, view: CentralGraphicsView, directory: str, name: str) -> None:
        """Restore a previously visited image in this pane during this session.

        Args:
            view: Target image view.
            directory: Source directory.
            name: Source basename.
        """
        self.cancel_transfer()
        if self.controls is not None:
            self.controls.restore_tool(view)
        key: int = id(view)
        path: str = os.path.join(directory, name) if name else ""
        self.paths[key] = path
        state: tuple[QtGui.QTransform, QtCore.QPointF, int] | None = self.states.get(
            (key, path)
        )
        if state is not None:
            view.rotation_degrees = state[2]
            view.setTransform(state[0])
            view.centerOn(state[1])
            # Scrollbar visibility settles after the image-load signal returns.
            QtCore.QTimer.singleShot(
                0, lambda v=view, p=path, saved=state: self.settle_view(v, p, saved)
            )
        self.refresh()

    def settle_view(
        self,
        view: CentralGraphicsView,
        path: str,
        state: tuple[QtGui.QTransform, QtCore.QPointF, int],
    ) -> None:
        """Center a restored image after pending scrollbar layout changes.

        Args:
            view: Target view.
            path: Image whose restore was queued.
            state: Saved transform, center, and rotation.
        """
        if self.paths.get(id(view)) == path and view.transform() == state[0]:
            view.centerOn(state[1])

    @staticmethod
    def reset_view(view: CentralGraphicsView) -> None:
        """Reset one pane's rotation and fit the full image.

        Args:
            view: Target view.
        """
        view.rotation_degrees = 0
        view.fit_image()

    def tool_changed(self, view: CentralGraphicsView, mode: str) -> None:
        """Remember the last drawing tool for a direct handoff between panes.

        Args:
            view: Tool owner.
            mode: New interaction mode.
        """
        if self.controls is not None:
            self.controls.refresh()
            return
        if mode in {"point", "line", "polygon"}:
            self.transfer_mode = InteractionMode(mode)
            self.last_tool_view = view
        elif mode == "select":
            self.cancel_transfer()
        self.refresh()

    def cancel_transfer(self) -> None:
        """Return subsequent pane clicks to ordinary counting after Escape."""
        self.transfer_mode = None
        self.last_tool_view = None
        self.notice = ""

    def transfer_tool(self, target: CentralGraphicsView) -> None:
        """Start the last drawing tool on a different pane's first click.

        Args:
            target: Pane receiving a drawing click.
        """
        if self.controls is not None:
            self.controls.claim(target)
            return
        source: CentralGraphicsView | None = self.last_tool_view
        if source is None or source is target or self.transfer_mode is None:
            return
        if source.line_points or source.polygon_points:
            target.annotation_target_blocked = True
            self.notice = (
                "Unfinished shape in other pane: Enter to finish there, Esc to cancel."
            )
            self.refresh()
            return
        mode: InteractionMode = self.transfer_mode
        self.notice = ""
        self.widget._handoff_annotation_tool(target)
        self.widget._start_annotation_mode_on_view(target, mode)

    def move_selection(self, pane: ComparePane) -> None:
        """Route the existing move dialog to its explicitly chosen pane.

        Args:
            pane: Owner of the selected dots.
        """
        self.widget._set_last_active_view(
            "current" if pane is self.widget.current_pane else "reference"
        )
        self.widget.move_selected_dots()

    @staticmethod
    def clear_selection(canvas: Canvas) -> None:
        """Clear count-dot selection without altering project data.

        Args:
            canvas: Selected-dot owner.
        """
        canvas.selection = []
        canvas.display_points()

    def saved(self, path: str, success: bool) -> None:
        """Show a confirmed save result rather than only a saving animation.

        Args:
            path: Requested destination.
            success: Whether the atomic save committed.
        """
        self.save_error = not success
        if success:
            self.last_save = f"{Path(path).name} at {datetime.now():%H:%M:%S}"
            self.save_notice_until = monotonic() + 5.0
            self.widget.reference_canvas.dirty = False
        self.refresh()

    def refresh(self) -> None:
        """Update lightweight feedback without redrawing image scenes."""
        if self.controls is not None:
            self.controls.refresh()
            return
        if not self.labels:
            return
        for index, (pane, canvas) in enumerate(self.panes):
            view: CentralGraphicsView = pane.graphics_view
            active: bool = (index == 1) == (
                self.widget._last_active_view_name == "reference"
            )
            style: str = (
                f"QFrame#{pane.objectName()} {{ border: {'2px solid #438ac7' if active else '2px solid palette(mid)'}; }}"
            )
            if pane.styleSheet() != style:
                pane.setStyleSheet(style)
            # Only active-state changes update styles, avoiding layout churn.
            mode: str = view.interaction_mode.value
            names: dict[str, str] = {
                "count": "Count",
                "point": "Draw landmark",
                "line": "Draw cutline",
                "polygon": "Draw count region",
                "select": "Edit annotation",
            }
            tool: str = names.get(mode, mode.title())
            if self.widget._pending_compare_annotation_mode is not None:
                tool = (
                    "Draw "
                    + self.widget._pending_compare_annotation_mode.value
                    + " · click either pane"
                )
            transferring: bool = (
                self.widget._pending_compare_annotation_mode is None
                and self.transfer_mode is not None
                and self.last_tool_view is not None
                and self.last_tool_view is not view
            )
            if transferring:
                if (
                    self.last_tool_view.line_points
                    or self.last_tool_view.polygon_points
                ):
                    tool = "Finish or cancel shape in other pane"
                else:
                    tool = (
                        names.get(self.transfer_mode.value, "Draw")
                        + " · click to start"
                    )
            if (
                mode == "count"
                and not transferring
                and self.widget._pending_compare_annotation_mode is None
            ):
                tool += " · " + (
                    self.widget.canvas.current_class_name or "Choose a class"
                )
            vertices: int = len(view.line_points) + len(view.polygon_points)
            if vertices:
                tool += f" · {vertices} vertices · Enter finish / Esc cancel"
            self.labels[index].setText(tool)
            counts: Counter[str] = Counter(name for name, _point in canvas.selection)
            button: QtWidgets.QToolButton = self.selection_buttons[index]
            button.setText(f"{len(canvas.selection)} selected")
            button.setEnabled(bool(canvas.selection))
            button.setToolTip(
                "\n".join(f"{name}: {count}" for name, count in sorted(counts.items()))
            )
        dirty: bool = self.widget.canvas.dirty
        state: str = "Unsaved changes" if dirty else "No unsaved point/field changes"
        if self.save_error:
            state = "Save failed — changes remain unsaved"
        elif self.last_save:
            state += " · Last saved " + self.last_save
        self.save_label.setText(
            " · ".join(
                part for part in (state, self.recovery_text, self.notice) if part
            )
        )

    def write_recovery(self) -> None:
        """Atomically snapshot unsaved points/fields beside the source images."""
        canvas: Canvas = self.widget.canvas
        if not canvas.dirty or not canvas.directory:
            return
        stem: str = (
            Path(canvas.previous_file_name).stem + "."
            if canvas.previous_file_name
            else ""
        )
        path: Path = Path(canvas.directory) / f".{stem}ddg-recovery.pnt"
        # Keep the preceding snapshot too, so a later mistake does not replace
        # the only recovery copy. Ordinary saves never remove recovery files.
        previous: Path = path.with_name(path.stem + "-previous.pnt")
        try:
            package, _count = canvas.package_points()
            payload: bytes = json.dumps(package, indent=2).encode("utf-8")
            if path.exists():
                old: bytes = path.read_bytes()
                self.atomic_snapshot(previous, old)
            self.atomic_snapshot(path, payload)
            self.recovery_text = (
                f"Recovery snapshot {datetime.now():%H:%M:%S} ({path.name})"
            )
        except (OSError, ValueError, TypeError) as error:
            self.recovery_text = f"Recovery failed: {error}"
        self.refresh()

    def project_loaded(self, survey_id: str) -> None:
        """Clear feedback belonging to the preceding project.

        Args:
            survey_id: Newly loaded survey identifier.
        """
        del survey_id
        self.last_save = ""
        self.save_notice_until = 0.0
        self.save_error = False
        self.cancel_transfer()
        self.states.clear()
        self.paths.clear()
        self.recovery_text = "Recovery snapshots every 2 minutes"
        self.refresh()

    def open_recovery_folder(self) -> None:
        """Open the current image folder, where recovery snapshots are stored."""
        directory: str = self.widget.canvas.directory
        if directory and not QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(directory)
        ):
            self.notice = "Could not open the recovery folder."
            self.refresh()

    def update_recovery_menu(self) -> None:
        """Show existing snapshot details without adding permanent layout space."""
        directory: str = self.widget.canvas.directory
        snapshots: list[Path] = (
            list(Path(directory).glob(".*ddg-recovery*.pnt")) if directory else []
        )
        latest: Path | None = (
            max(snapshots, key=lambda path: path.stat().st_mtime) if snapshots else None
        )
        description: str = (
            "Latest snapshot: "
            + datetime.fromtimestamp(latest.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if latest
            else "No recovery snapshot in the current image folder"
        )
        menu: QtWidgets.QMenu = self.recover_button.menu()
        menu.setToolTipsVisible(True)
        menu.actions()[0].setText(
            "Open recovery snapshot…"
            + (
                " ("
                + datetime.fromtimestamp(latest.stat().st_mtime).strftime("%H:%M")
                + ")"
                if latest
                else ""
            )
        )
        menu.actions()[0].setToolTip(
            description + ("\n" + str(latest) if latest else "")
        )
        menu.actions()[0].setEnabled(bool(directory))
        menu.actions()[1].setEnabled(bool(directory))

    def recover(self) -> None:
        """Open a snapshot through the normal point-file loader after save checks."""
        canvas: Canvas = self.widget.canvas
        if not canvas.directory or not canvas.dirty_data_check():
            return
        path: str
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self.widget,
            "Recover snapshot",
            canvas.directory,
            "Recovery point files (*ddg-recovery*.pnt);;Point files (*.pnt)",
        )
        if not path:
            return
        try:
            # Validate the payload before the legacy loader resets the project.
            payload: object = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not {
                "points",
                "classes",
                "colors",
                "metadata",
            }.issubset(payload):
                raise ValueError("Not a complete point-file snapshot")
            canvas.load_points(path)
            canvas.previous_file_name = None
            canvas.dirty = True
            self.notice = "Recovery loaded. Save As to choose your project file."
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.notice = f"Recovery could not be opened: {error}"
        self.refresh()

    @staticmethod
    def atomic_snapshot(path: Path, payload: bytes) -> None:
        """Commit a complete recovery file without changing save/dirty state.

        Args:
            path: Destination path.
            payload: Serialized project bytes.

        Raises:
            OSError: If the snapshot could not be committed.
        """
        output: QtCore.QSaveFile = QtCore.QSaveFile(str(path))
        if not output.open(QtCore.QIODevice.OpenModeFlag.WriteOnly):
            raise OSError(output.errorString())
        if output.write(payload) != len(payload):
            output.cancelWriting()
            raise OSError("Incomplete recovery write")
        if not output.commit():
            raise OSError(output.errorString())
