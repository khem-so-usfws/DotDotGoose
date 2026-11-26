"""Dockable image views and per-folder workspace preferences."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable, TypedDict

from PyQt6 import QtCore, QtGui, QtWidgets, sip

if TYPE_CHECKING:
    from .canvas import Canvas, HistoryEvent
    from .central_graphics_view import CentralGraphicsView
    from .central_widget import CentralWidget
    from .compare_pane import ComparePane


class SavedWorkspace(TypedDict):
    """Workspace preferences stored under one working folder."""

    opened: list[str]
    last_setup: list[str]
    reopen_docked: list[str]
    photos: dict[str, str]
    active: str
    orientation: str
    views: dict[str, dict[str, list[float]]]
    enhancements: dict[str, dict[str, tuple[int, int]]]
    floating: dict[str, list[int]]


class ImageDock(QtWidgets.QDockWidget):
    """Use the same draggable title bar in docked and floating windows."""

    def __init__(self, workspace: ImageWorkspace, name: str, title: str) -> None:
        """Bind this dock's close button to the workspace.

        Args:
            workspace: Owner of the image and its remembered state.
            name: Stable identifier of the pane.
            title: Displayed pane number.
        """
        super().__init__(title, workspace.host)
        self.setObjectName(f"imageDock-{name}")
        self.workspace: ImageWorkspace = workspace
        self.name: str = name
        self.setFeatures(
            self.DockWidgetFeature.DockWidgetClosable
            | self.DockWidgetFeature.DockWidgetMovable
            | self.DockWidgetFeature.DockWidgetFloatable
        )
        # A Qt title bar keeps the redocking gesture available in floating windows.
        header: QtWidgets.QWidget = QtWidgets.QWidget(self)
        row: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(6, 2, 2, 2)
        row.setSpacing(3)
        self.caption: QtWidgets.QLabel = QtWidgets.QLabel(title, header)
        self.caption.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.caption.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        row.addWidget(self.caption, 1)
        self.float_button: QtWidgets.QToolButton = QtWidgets.QToolButton(header)
        self.float_button.setAutoRaise(True)
        self.float_button.clicked.connect(lambda: workspace.toggle_float(name))
        row.addWidget(self.float_button)
        close: QtWidgets.QToolButton = QtWidgets.QToolButton(header)
        close.setAutoRaise(True)
        close.setIcon(
            self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_TitleBarCloseButton
            )
        )
        close.setToolTip("Close pane")
        close.setAccessibleName("Close pane")
        close.clicked.connect(self.close)
        row.addWidget(close)
        self.setTitleBarWidget(header)
        self.windowTitleChanged.connect(self.caption.setText)
        self.windowTitleChanged.connect(header.setToolTip)
        self.topLevelChanged.connect(self.update_float_button)
        self.update_float_button(False)

    def update_float_button(self, floating: bool) -> None:
        """Reflect the available docking action in the title bar.

        Args:
            floating: Whether the pane is in its own window.
        """
        pixmap: QtWidgets.QStyle.StandardPixmap = (
            QtWidgets.QStyle.StandardPixmap.SP_TitleBarNormalButton
            if floating
            else QtWidgets.QStyle.StandardPixmap.SP_TitleBarMaxButton
        )
        self.float_button.setIcon(self.style().standardIcon(pixmap))
        label: str = "Dock pane" if floating else "Float pane"
        self.float_button.setToolTip(label)
        self.float_button.setAccessibleName(label)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Activate the pane when its native header is pressed.

        Args:
            event: Mouse press received by the dock.
        """
        view: CentralGraphicsView = self.workspace.widget.image_panes[self.name][
            0
        ].graphics_view
        view.view_activated.emit()
        if view.annotation_target_blocked:
            event.accept()
            return
        super().mousePressEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Close the pane and retain its image for the next docked opening.

        Args:
            event: Native window or dock close request.
        """
        if self.workspace.close_pane(self.name):
            super().closeEvent(event)
        else:
            event.ignore()


class ImageWorkspace(QtCore.QObject):
    """Manage four peer views within a docking area between the sidebars."""

    def __init__(self, widget: CentralWidget) -> None:
        """Install the dock host and its per-pane controls.

        Args:
            widget: Main counting workspace.
        """
        super().__init__(widget)
        self.widget: CentralWidget = widget
        self.host: QtWidgets.QMainWindow = QtWidgets.QMainWindow(widget.frameCenter)
        self.host.setWindowFlags(QtCore.Qt.WindowType.Widget)
        self.host.setDockNestingEnabled(True)
        self.host.setDockOptions(QtWidgets.QMainWindow.DockOption.AllowNestedDocks)
        self.host.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        layout: QtWidgets.QVBoxLayout = widget.frameCenter.layout()
        layout.replaceWidget(widget.compare_splitter, self.host)
        widget.compare_splitter.hide()
        self.host.show()
        self.docks: dict[str, ImageDock] = {}
        self.float_actions: dict[str, QtGui.QAction] = {}
        self.opened: set[str] = {"current"}
        self.last_setup: set[str] = {"current", "reference"}
        self.reopen_docked: set[str] = set()
        self.photos: dict[str, str] = {}
        self.directory: str = ""
        self.orientation: str = widget.compare_layout()
        self.settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
        self.shutting_down: bool = False
        self.has_arranged: bool = False

        for number, (name, (pane, canvas)) in enumerate(widget.image_panes.items(), 1):
            title: str = f"Pane {number}"
            dock: ImageDock = ImageDock(self, name, title)
            self.docks[name] = dock
            pane.label.setText(title)
            pane.label.hide()
            pane.setMinimumHeight(110)
            pane.graphics_view.preserve_docked_view = True
            pane.graphics_view.setResizeAnchor(
                QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter
            )
            dock.setWidget(pane)
            self.host.addDockWidget(QtCore.Qt.DockWidgetArea.TopDockWidgetArea, dock)
            pane.show()
            dock.setVisible(name in self.opened)
            # The common header already has More. Keep the menu usable off the main monitor.
            pane.overflow_menu.clear()
            action: QtGui.QAction = pane.overflow_menu.addAction("Float pane")
            action.triggered.connect(
                lambda _checked=False, key=name: self.toggle_float(key)
            )
            self.float_actions[name] = action
            pane.overflow_menu.addAction("Close pane", dock.close)
            dock.topLevelChanged.connect(
                lambda floating, key=name: self.floating_changed(key, floating)
            )
            canvas.image_loaded.connect(
                lambda directory, photo, key=name: self.update_photo(
                    key, directory, photo
                )
            )
            self.attach_shortcuts(dock, pane)

    def connect_project(self) -> None:
        """Start observing folder changes after the shared controls exist."""
        self.widget.canvas.directory_set.connect(self.folder_changed)

    def attach_shortcuts(self, dock: ImageDock, pane: ComparePane) -> None:
        """Route shortcuts within the floating window to the shared project.

        Args:
            dock: Floating window that receives the shortcuts.
            pane: Pane whose image should advance or go back.
        """
        callbacks: dict[str, Callable[[], object]] = {
            "Ctrl+S": self.widget.canvas.quick_save,
            "Ctrl+Z": self.widget.undo_global_history,
            "Ctrl+Y": self.widget.redo_global_history,
            "Up": pane.previous_image,
            "Down": pane.next_image,
            "W": pane.previous_image,
            "S": pane.next_image,
        }
        for key, callback in callbacks.items():
            shortcut: QtGui.QShortcut = QtGui.QShortcut(QtGui.QKeySequence(key), dock)
            shortcut.setEnabled(False)
            shortcut.activated.connect(callback)
            dock.topLevelChanged.connect(shortcut.setEnabled)

    def can_switch(self, target: str | None = None) -> bool:
        """Block changes that would leave another pane's unfinished shape.

        Args:
            target: Pane that can retain its own draft, if any.

        Returns:
            Whether the action can continue.
        """
        for name, (pane, _canvas) in self.widget.image_panes.items():
            view: CentralGraphicsView = pane.graphics_view
            if name != target and view.has_annotation_draft():
                feedback = self.widget.workspace_feedback
                feedback.notice = (
                    f"Unfinished shape in {pane.label.text()}. "
                    "Press Enter there to finish or Esc to cancel."
                )
                feedback.refresh()
                return False
        return True

    def activate(self, name: str) -> bool:
        """Accept an explicit activation when the pane is open.

        Args:
            name: Clicked pane.

        Returns:
            Whether this pane can receive edits.
        """
        return name in self.opened and self.can_switch(target=name)

    def toggle_float(self, name: str) -> None:
        """Move a pane between its floating and docked locations.

        Args:
            name: Pane to move.
        """
        if name in self.opened and self.can_switch():
            dock: ImageDock = self.docks[name]
            dock.setFloating(not dock.isFloating())
            dock.show()
            if dock.isFloating():
                dock.raise_()

    def floating_changed(self, name: str, floating: bool) -> None:
        """Update the explicit docking command after a drag or menu action.

        Args:
            name: Pane that moved.
            floating: Whether the pane is now floating.
        """
        self.float_actions[name].setText("Dock pane" if floating else "Float pane")
        self.update_title(name, self.photos.get(name, ""))

    def close_pane(self, name: str) -> bool:
        """Close one pane and arrange for it to reopen docked.

        Args:
            name: Pane being closed.

        Returns:
            Whether the close request succeeded.
        """
        if self.shutting_down or name not in self.opened:
            return True
        if not self.can_switch():
            return False
        self.last_setup = set(self.opened) if len(self.opened) > 1 else self.last_setup
        self.hide_pane(name)
        self.reopen_docked.add(name)
        self.changed()
        return True

    def reopen(self, name: str) -> None:
        """Reopen a pane docked when no unfinished annotation blocks it.

        Args:
            name: Pane chosen in the Reopen pane menu.
        """
        if self.can_switch():
            self.open_pane(name)

    def update_reopen_menu(self, menu: QtWidgets.QMenu) -> None:
        """List the pane number and remembered photo for closed panes.

        Args:
            menu: Menu with a stable action for each pane.
        """
        for action in menu.actions():
            name: str = action.data()
            pane: ComparePane = self.widget.image_panes[name][0]
            photo: str = self.photos.get(name, "")
            action.setText(
                f"{pane.label.text()} · {photo}" if photo else pane.label.text()
            )
            action.setEnabled(name not in self.opened)

    def update_count_menu(self, group: QtGui.QActionGroup) -> None:
        """Check the menu entry that matches the open pane count.

        Args:
            group: Pane-count actions in ascending order.
        """
        for count, action in enumerate(group.actions(), 1):
            action.setChecked(count == len(self.opened))

    def hide_pane(self, name: str) -> None:
        """Release a hidden secondary image after recording its view.

        Args:
            name: Pane to hide.
        """
        pane, canvas = self.widget.image_panes[name]
        self.widget.workspace_layout.flush()
        if canvas.current_image_name:
            self.photos[name] = canvas.current_image_name
            self.widget.workspace_feedback.remember(pane.graphics_view)
        self.opened.remove(name)
        self.docks[name].hide()
        canvas.clear_external_annotation_selection()
        canvas.selection.clear()
        if canvas is not self.widget.canvas:
            canvas.release_image()
        else:
            canvas.display_points()

    def open_pane(self, name: str, *, layout: bool = True) -> None:
        """Open a stored photo or choose the next available photo for a new pane.

        Args:
            name: Pane to show.
            layout: Whether to rebuild the docked arrangement now.
        """
        if name not in self.opened:
            self.opened.add(name)
            dock: ImageDock = self.docks[name]
            redock: bool = name in self.reopen_docked
            if redock:
                dock.setFloating(False)
                self.reopen_docked.remove(name)
            dock.show()
            self.refresh_images()
            pane, canvas = self.widget.image_panes[name]
            selected: str | None = pane.selected_image()
            if selected and selected != canvas.current_image_name:
                self.widget.load_pane_image(name, selected)
            if layout and (not self.has_arranged or not redock):
                self.arrange()
        if layout:
            if len(self.opened) > 1:
                self.last_setup = set(self.opened)
            self.changed()

    def set_count(self, count: int) -> None:
        """Show the requested number of panes and retain the photos in closed panes.

        Args:
            count: Number of open image panes.
        """
        if not self.can_switch():
            return
        ordered: list[str] = [name for name in self.docks if name in self.opened]
        target: set[str] = set(
            (ordered + [name for name in self.docks if name not in self.opened])[:count]
        )
        self.show_setup(target)
        self.arrange()

    def show_setup(self, target: set[str], *, restore_floating: bool = False) -> None:
        """Show the given panes together and refresh shared controls.

        Args:
            target: Set of panes to show.
            restore_floating: Whether to retain positions during the toolbar toggle.
        """
        for name in self.docks:
            if name in self.opened - target:
                self.hide_pane(name)
                if not restore_floating:
                    self.reopen_docked.add(name)
        for name in self.docks:
            if name in target:
                self.open_pane(name, layout=False)
        if len(target) > 1:
            self.last_setup = set(target)
        self.changed()

    def toggle(self, enabled: bool) -> None:
        """Restore the previous multi-pane setup or temporarily show one pane.

        Args:
            enabled: Whether to show the multi-pane setup.
        """
        if not self.can_switch():
            self.changed()
            return
        if enabled and len(self.opened) <= 1:
            self.show_setup(self.last_setup, restore_floating=True)
            if not self.has_arranged:
                self.arrange()
        elif not enabled and len(self.opened) > 1:
            active: str = self.widget._last_active_view_name
            self.last_setup = set(self.opened)
            self.show_setup({active}, restore_floating=True)

    def changed(self) -> None:
        """Keep focus, right sidebar, and Panes checked state consistent."""
        active: str = self.widget._last_active_view_name
        if self.opened:
            if active not in self.opened:
                active = next(name for name in self.docks if name in self.opened)
            self.widget._set_last_active_view(active)
        else:
            self.widget.workspace_layout.bind_active()
        self.widget.compare_enabled_changed.emit(len(self.opened) > 1)

    def set_layout(self, orientation: str) -> None:
        """Apply a layout to the docked panes, leaving floating panes in place.

        Args:
            orientation: Side-by-side or stacked preference.
        """
        self.orientation = orientation
        if self.opened:
            self.arrange()
        self.widget.compare_layout_changed.emit(orientation)

    def arrange(self) -> None:
        """Arrange docked panes as a row, column, one plus two, or two by two."""
        docked: list[ImageDock] = [
            dock
            for name, dock in self.docks.items()
            if name in self.opened and not dock.isFloating()
        ]
        if len(docked) < 2:
            return
        self.has_arranged = True
        horizontal = QtCore.Qt.Orientation.Horizontal
        vertical = QtCore.Qt.Orientation.Vertical
        for dock in docked:
            self.host.removeDockWidget(dock)
        self.host.addDockWidget(QtCore.Qt.DockWidgetArea.TopDockWidgetArea, docked[0])
        direction = (
            vertical if len(docked) == 2 and self.orientation == "2x1" else horizontal
        )
        self.host.splitDockWidget(docked[0], docked[1], direction)
        if len(docked) == 3:
            self.host.splitDockWidget(docked[1], docked[2], vertical)
        elif len(docked) == 4:
            self.host.splitDockWidget(docked[0], docked[2], vertical)
            self.host.splitDockWidget(docked[1], docked[3], vertical)
        for dock in docked:
            dock.show()
        half_height: int = max(110, self.host.height() // 2)
        if len(docked) == 3:
            self.host.resizeDocks(docked[1:], [half_height, half_height], vertical)
        elif len(docked) == 4:
            self.host.resizeDocks(
                [docked[0], docked[2]], [half_height, half_height], vertical
            )
            self.host.resizeDocks(
                [docked[1], docked[3]], [half_height, half_height], vertical
            )
        half: int = (
            half_height if direction == vertical else max(220, self.host.width() // 2)
        )
        self.host.resizeDocks(docked[:2], [half, half], direction)

    def refresh_images(self) -> None:
        """Give every pane the same independent, filename-ordered picker."""
        project = self.widget.canvas
        names: list[str] = [
            name
            for name in sorted(project.project_image_names())
            if (Path(project.directory) / name).is_file()
        ]
        used: set[str] = {
            canvas.current_image_name
            for _pane, canvas in self.widget.image_panes.values()
            if canvas.current_image_name
        }
        for name, (pane, canvas) in self.widget.image_panes.items():
            selected: str | None = canvas.current_image_name or self.photos.get(name)
            if selected not in names:
                # A small selection can be shared by several open panes.
                selected = next(
                    (photo for photo in names if photo not in used),
                    names[0] if names else None,
                )
            if selected:
                used.add(selected)
            pane.set_images(names, selected)

    def refresh_after_photo_selection(self) -> None:
        """Keep allowed images and replace excluded images in open panes."""
        self.refresh_images()
        # Capture replacement choices before image-load signals refresh the pickers.
        replacements: list[tuple[str, str]] = []
        for name, (pane, canvas) in self.widget.image_panes.items():
            photo: str | None = pane.selected_image()
            if name in self.opened and photo and photo != canvas.current_image_name:
                replacements.append((name, photo))
        for name, photo in replacements:
            self.widget.load_pane_image(name, photo)
        self.refresh_images()

    def update_title(self, name: str, photo: str) -> None:
        """Put the photo in the floating window title.

        Args:
            name: Pane that loaded an image.
            photo: Image basename.
        """
        pane: ComparePane = self.widget.image_panes[name][0]
        dock: ImageDock = self.docks[name]
        dock.setWindowTitle(
            f"{pane.label.text()} · {photo}"
            if photo and dock.isFloating()
            else pane.label.text()
        )

    def update_photo(self, name: str, directory: str, photo: str) -> None:
        """Remember the photo and fit a new view after the dock layout settles.

        Args:
            name: Pane that loaded an image.
            directory: Project image folder.
            photo: Image basename.
        """
        self.update_title(name, photo)
        if photo:
            self.photos[name] = photo
            view: CentralGraphicsView = self.widget.image_panes[name][0].graphics_view
            path: str = str(Path(directory) / photo)
            feedback = self.widget.workspace_feedback
            if (id(view), path) not in feedback.states:
                initial: QtGui.QTransform = view.transform()
                QtCore.QTimer.singleShot(
                    0, lambda: self.fit_loaded_photo(view, path, initial)
                )

    def fit_loaded_photo(
        self, view: CentralGraphicsView, path: str, initial: QtGui.QTransform
    ) -> None:
        """Fit a newly loaded photo if the user has not changed its view.

        Args:
            view: View that loaded a photo.
            path: Loaded image path.
            initial: Transform before the layout finished resizing.
        """
        if (
            not sip.isdeleted(view)
            and self.widget.workspace_feedback.paths.get(id(view)) == path
            and view.transform() == initial
        ):
            view.fit_image()

    def refresh_shared_edit(self, source: Canvas, event: HistoryEvent) -> None:
        """Refresh other open copies of an edited photo.

        Args:
            source: Scene issuing the edit.
            event: Recorded history event holding the edited image.
        """
        annotation: bool = event[0] == "annotation_json" or (
            event[0] == "selection_edit" and bool(event[4])
        )
        image: str = Path(str(event[1])).name
        for name in self.opened:
            _pane, canvas = self.widget.image_panes[name]
            if canvas is source or canvas.current_image_name != image:
                continue
            if annotation:
                canvas.display_external_annotations(
                    str(Path(canvas.directory) / image), refresh_points=False
                )
            canvas.display_points()

    def settings_key(self) -> str:
        """Return the local settings key for the current working folder."""
        digest: str = hashlib.sha256(
            str(Path(self.directory).resolve()).encode()
        ).hexdigest()
        return f"imageWorkspace/{digest}"

    def save(self) -> None:
        """Save photos, dock positions, and per-photo view settings locally."""
        if not self.directory:
            return
        feedback = self.widget.workspace_feedback
        views: dict[str, dict[str, list[float]]] = {}
        enhancements: dict[str, dict[str, tuple[int, int]]] = {}
        for name, (pane, canvas) in self.widget.image_panes.items():
            view = pane.graphics_view
            if name in self.opened:
                feedback.remember(view)
            views[name] = {
                Path(path).name: [
                    matrix.m11(),
                    matrix.m12(),
                    matrix.m21(),
                    matrix.m22(),
                    matrix.dx(),
                    matrix.dy(),
                    center.x(),
                    center.y(),
                    angle,
                ]
                for (key, path), (matrix, center, angle) in feedback.states.items()
                if key == id(view) and Path(path).parent == Path(self.directory)
            }
            enhancements[name] = {
                Path(path).name: values
                for path, values in canvas.enhancements.items()
                if Path(path).parent == Path(self.directory)
            }
        key: str = self.settings_key()
        self.settings.setValue(key + "/docks", self.host.saveState(1))
        state: SavedWorkspace = {
            "opened": sorted(self.opened),
            "last_setup": sorted(self.last_setup),
            "reopen_docked": sorted(self.reopen_docked),
            "photos": self.photos,
            "active": self.widget._last_active_view_name,
            "orientation": self.orientation,
            "views": views,
            "enhancements": enhancements,
            "floating": {
                name: list(dock.frameGeometry().getRect())
                for name, dock in self.docks.items()
                if name in self.opened and dock.isFloating()
            },
        }
        self.settings.setValue(key + "/views", json.dumps(state))

    def folder_changed(self, directory: str) -> None:
        """Keep photos and view preferences scoped to their working folder.

        Args:
            directory: Newly selected working folder.
        """
        if directory == self.directory:
            return
        self.save()
        self.directory = directory
        self.photos.clear()
        for name, (_pane, canvas) in self.widget.image_panes.items():
            if name != "current":
                canvas.release_image()
        if not directory:
            self.refresh_images()

    def image_loaded(self, directory: str, photo: str) -> None:
        """Restore a stored layout once the new folder's images are available.

        Args:
            directory: Working folder of the primary project canvas.
            photo: Loaded photo basename.
        """
        if not directory or not photo:
            return
        if directory != self.directory:
            self.folder_changed(directory)
        if self.widget.canvas.directory != directory:
            return
        if self.photos.get("current") is None:
            self.restore(photo)
        self.update_title("current", self.widget.canvas.current_image_name or photo)
        self.refresh_images()
        for name in self.docks:
            if name == "current" or name not in self.opened:
                continue
            pane, canvas = self.widget.image_panes[name]
            if not canvas.current_image_name and pane.selected_image():
                self.widget.load_pane_image(name, pane.selected_image())

    def restore(self, initial_photo: str) -> None:
        """Restore saved positions and views, keeping floating panes on-screen.

        Args:
            initial_photo: First image loaded by the project.
        """
        self.photos["current"] = initial_photo
        key: str = self.settings_key()
        settings: str = self.settings.value(key + "/views", "")
        if not settings:
            return
        try:
            data: SavedWorkspace = json.loads(settings)
        except json.JSONDecodeError:
            return
        self.photos.update(data["photos"])
        self.reopen_docked = set(data["reopen_docked"]) & self.docks.keys()
        self.orientation = data["orientation"]
        feedback = self.widget.workspace_feedback
        directory: Path = Path(self.directory)
        for name, (pane, canvas) in self.widget.image_panes.items():
            view = pane.graphics_view
            for photo, state in data["views"].get(name, {}).items():
                matrix: QtGui.QTransform = QtGui.QTransform(*state[:6])
                center: QtCore.QPointF = QtCore.QPointF(*state[6:8])
                feedback.states[(id(view), str(directory / photo))] = (
                    matrix,
                    center,
                    state[8],
                )
            for photo, values in data["enhancements"].get(name, {}).items():
                canvas.enhancements[str(directory / photo)] = tuple(values)
        primary: str = self.photos["current"]
        if primary in self.widget.canvas.points and (directory / primary).is_file():
            self.widget.load_current_image(primary)
        self.show_setup(set(data["opened"]) & self.docks.keys(), restore_floating=True)
        self.last_setup = set(data["last_setup"]) & self.docks.keys()
        state: QtCore.QByteArray | None = self.settings.value(key + "/docks")
        if state:
            self.has_arranged = self.host.restoreState(state, 1)
        if not self.has_arranged:
            self.arrange()
        for name, dock in self.docks.items():
            dock.setVisible(name in self.opened)
            geometry_values: list[int] | None = data.get("floating", {}).get(name)
            if name in self.opened and geometry_values is not None:
                geometry: QtCore.QRect = QtCore.QRect(*geometry_values)
                on_screen: bool = any(
                    screen.availableGeometry().intersects(geometry)
                    for screen in QtWidgets.QApplication.screens()
                )
                dock.setFloating(on_screen)
        active: str = data["active"]
        if active in self.opened:
            self.widget._set_last_active_view(active)
        self.changed()

    def shutdown(self) -> None:
        """Record and close floating windows when the project window exits."""
        self.save()
        self.shutting_down = True
        for dock in self.docks.values():
            dock.hide()
