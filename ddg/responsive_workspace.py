"""Active-image metadata bindings and responsive desktop workspace layout."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from PyQt6 import QtCore, QtGui, QtWidgets, sip

from .canvas import Canvas
from .compare_pane import ComparePane
from .fields import BoxText, LineText
from .central_graphics_view import InteractionMode

if TYPE_CHECKING:
    from .central_widget import CentralWidget
    from .main_window import MainWindow
    from .workspace_controls import WorkspaceControls
    from .point_widget import PointWidget


class FolderPathLabel(QtWidgets.QLabel):
    """Display a real folder path with bounded width and full-path copying."""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        """Create a selectable path label.

        Args:
            parent: Folder-row owner.
        """
        super().__init__(parent)
        self.full_path: str = ""
        self.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

    def setText(self, text: str) -> None:
        """Retain the full path separately from its elided presentation.

        Args:
            text: Complete working-directory path.
        """
        if self.full_path != text:
            self.full_path = text
            self.setToolTip(text)
            self.render_path()

    def render_path(self) -> None:
        """Render the actual path in the width allocated by the folder row."""
        super().setText(
            self.fontMetrics().elidedText(
                self.full_path,
                QtCore.Qt.TextElideMode.ElideMiddle,
                max(0, self.contentsRect().width()),
            )
        )

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Update middle elision when available path width changes.

        Args:
            event: Qt resize event.
        """
        super().resizeEvent(event)
        self.render_path()

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        """Offer full-path copying even when only an abbreviated path fits.

        Args:
            event: Requested context-menu location.
        """
        menu: QtWidgets.QMenu = QtWidgets.QMenu(self)
        menu.addAction(
            "Copy full path",
            lambda: QtWidgets.QApplication.clipboard().setText(self.full_path),
        )
        menu.exec(event.globalPos())


class ToolbarGroup(QtWidgets.QWidget):
    """Present shared actions as buttons or an accessible compact menu."""

    def __init__(
        self,
        title: str,
        bar: QtWidgets.QToolBar,
        actions: list[QtGui.QAction],
        special: QtWidgets.QToolButton | None = None,
        subgroup_breaks: dict[QtGui.QAction, int] | None = None,
    ) -> None:
        """Build presentations without hiding shared menu/shortcut actions.

        Args:
            title: Group label and compact-menu text.
            bar: Target toolbar.
            actions: Existing application actions.
            special: Optional Compare split button to preserve.
            subgroup_breaks: Extra space before selected tool actions.
        """
        super().__init__(bar)
        self.buttons: list[QtWidgets.QToolButton] = []
        self.compact: bool = False
        self.class_label: QtWidgets.QLabel | None = None
        self.class_slot: int = 1
        self.gaps: list[tuple[QtWidgets.QSpacerItem, int]] = []
        row: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        for action in actions:
            if subgroup_breaks and action in subgroup_breaks:
                width: int = subgroup_breaks[action]
                gap: QtWidgets.QSpacerItem = QtWidgets.QSpacerItem(
                    width,
                    0,
                    QtWidgets.QSizePolicy.Policy.Fixed,
                    QtWidgets.QSizePolicy.Policy.Minimum,
                )
                row.addItem(gap)
                self.gaps.append((gap, width))
            button: QtWidgets.QToolButton = QtWidgets.QToolButton(self)
            button.setToolButtonStyle(
                QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            )
            button.setDefaultAction(action)
            row.addWidget(button)
            self.buttons.append(button)
        if special is not None:
            row.addWidget(special)
            special.show()
            self.buttons.append(special)
        self.selector: QtWidgets.QToolButton = QtWidgets.QToolButton(self)
        self.selector.setText(title)
        self.selector.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.selector.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.selector.setToolTip(f"{title}: open all controls in this group")
        menu: QtWidgets.QMenu = QtWidgets.QMenu(self.selector)
        menu.addActions(actions)
        if special is not None:
            menu.addAction(special.defaultAction())
            menu.addMenu(special.menu())
        self.selector.setMenu(menu)
        row.addWidget(self.selector)
        self.selector.hide()
        bar.addWidget(self)

    def natural_width(self) -> int:
        """Return the width of all expanded controls, even when hidden."""
        return (
            sum(button.sizeHint().width() for button in self.buttons)
            + 2 * max(0, len(self.buttons) - 1)
            + 12
            + sum(width for _gap, width in self.gaps)
            + (self.class_label.width() + 2 if self.class_label is not None else 0)
        )

    def compact_width(self) -> int:
        """Return the compact selector width including toolbar margins."""
        return (
            self.selector.sizeHint().width()
            + 12
            + (self.class_label.width() + 2 if self.class_label is not None else 0)
        )

    def set_compact(self, compact: bool) -> None:
        """Switch presentation while preserving every action and checked state.

        Args:
            compact: Whether to show the menu instead of separate buttons.
        """
        if self.compact == compact:
            return
        self.compact = compact
        for button in self.buttons:
            button.setVisible(not compact)
        self.selector.setVisible(compact)
        if self.class_label is not None:
            row: QtWidgets.QHBoxLayout = cast(QtWidgets.QHBoxLayout, self.layout())
            row.removeWidget(self.class_label)
            if compact:
                row.addWidget(self.class_label)
            else:
                row.insertWidget(self.class_slot, self.class_label)
        for gap, width in self.gaps:
            gap.changeSize(
                0 if compact else width,
                0,
                QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Minimum,
            )
        self.layout().invalidate()
        self.updateGeometry()


class PaneOverflow(QtCore.QObject):
    """Keep two pane-header rows usable and expose hidden controls in More."""

    minimum_changed: QtCore.pyqtSignal = QtCore.pyqtSignal()

    def __init__(self, pane: ComparePane, selection: QtWidgets.QToolButton) -> None:
        """Attach width-based overflow to an existing pane.

        Args:
            pane: Current or Reference pane.
            selection: Its dot/annotation selection menu button.
        """
        super().__init__(pane)
        self.pane: ComparePane = pane
        self.selection: QtWidgets.QToolButton = selection
        self.queued: bool = False
        self.enhance: QtWidgets.QPushButton = next(
            button
            for button in pane.findChildren(QtWidgets.QPushButton)
            if button.text() == "Enhance"
        )
        self.proxies: dict[QtWidgets.QAbstractButton, QtGui.QAction] = {}
        pane.overflow_menu.addSeparator()
        for button, label in (
            (pane.previous_button, "Previous image"),
            (pane.next_button, "Next image"),
            (pane.actual_size_button, "Actual size (1:1)"),
            (pane.rotate_left_button, "Rotate 90° left"),
            (pane.rotate_right_button, "Rotate 90° right"),
            (self.enhance, "Enhance image…"),
        ):
            action: QtGui.QAction = pane.overflow_menu.addAction(label, button.click)
            action.setVisible(False)
            self.proxies[button] = action
        self.selection_menu: QtWidgets.QMenu = pane.overflow_menu.addMenu("Selection")
        self.selection_menu.aboutToShow.connect(self.populate_selection)
        self.selection_menu.menuAction().setVisible(False)
        pane.overflow_menu.aboutToShow.connect(self.sync_actions)
        pane.image_combo.setMinimumWidth(
            pane.fontMetrics().horizontalAdvance("00000000") + 22
        )
        pane.setMinimumWidth(
            pane.label.sizeHint().width()
            + pane.image_combo.minimumWidth()
            + pane.overflow_button.sizeHint().width()
            + 22
        )
        pane.installEventFilter(self)
        self.schedule()

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Schedule relayout after pane size or font changes.

        Args:
            watched: Pane receiving the event.
            event: Qt layout event.

        Returns:
            False so normal rendering continues.
        """
        if event.type() in {
            QtCore.QEvent.Type.Resize,
            QtCore.QEvent.Type.Show,
            QtCore.QEvent.Type.FontChange,
        }:
            self.schedule()
        return False

    def schedule(self) -> None:
        """Coalesce repeated resize events into one layout update."""
        if not self.queued:
            self.queued = True
            QtCore.QTimer.singleShot(0, self.adapt)

    def adapt(self) -> None:
        """Move low-priority controls into More before they can be clipped."""
        self.queued = False
        if sip.isdeleted(self.pane):
            return
        pane: ComparePane = self.pane
        pane.image_combo.setMinimumWidth(
            pane.fontMetrics().horizontalAdvance("00000000") + 22
        )
        old_minimum: int = pane.minimumWidth()
        pane.setMinimumWidth(
            pane.label.sizeHint().width()
            + pane.image_combo.minimumWidth()
            + pane.overflow_button.sizeHint().width()
            + 22
        )
        for button in (
            pane.fit_button,
            pane.actual_size_button,
            pane.rotate_left_button,
            pane.rotate_right_button,
        ):
            button.setFixedWidth(
                button.fontMetrics().horizontalAdvance(button.text()) + 20
            )
            button.setFixedHeight(pane.image_combo.sizeHint().height())
        for button in (pane.previous_button, pane.next_button):
            button.setFixedWidth(
                button.fontMetrics().horizontalAdvance(button.text()) + 18
            )
            button.setFixedHeight(pane.image_combo.sizeHint().height())
        self.selection.setFixedWidth(
            max(
                self.selection.fontMetrics().horizontalAdvance("9999 dots"),
                self.selection.fontMetrics().horizontalAdvance("99 annotations"),
            )
            + 26
        )
        if old_minimum != pane.minimumWidth():
            self.minimum_changed.emit()
        width: int = pane.contentsRect().width() - 8
        row_one: int = (
            pane.label.sizeHint().width()
            + pane.image_combo.minimumWidth()
            + pane.overflow_button.sizeHint().width()
            + 16
        )
        navigation_width: int = (
            pane.previous_button.width() + pane.next_button.width() + 8
        )
        show_navigation: bool = row_one + navigation_width <= width
        pane.previous_button.setVisible(show_navigation)
        pane.next_button.setVisible(show_navigation)
        buttons: list[QtWidgets.QAbstractButton] = [
            pane.fit_button,
            pane.actual_size_button,
            pane.rotate_left_button,
            pane.rotate_right_button,
            self.enhance,
            self.selection,
        ]
        visible: set[QtWidgets.QAbstractButton] = set(buttons)
        for group in (
            (),
            (pane.actual_size_button,),
            (pane.rotate_left_button, pane.rotate_right_button),
            (self.enhance,),
            (self.selection,),
        ):
            visible.difference_update(group)
            needed: int = sum(
                (
                    button.sizeHint().width()
                    if button.maximumWidth() > 1000
                    else button.maximumWidth()
                )
                for button in visible
            ) + 4 * max(0, len(visible) - 1)
            if needed <= width:
                break
        for button in buttons:
            button.setVisible(button in visible)
        self.sync_actions()

    def sync_actions(self) -> None:
        """Mirror button availability and the current selection-menu target."""
        for button, action in self.proxies.items():
            action.setVisible(button.isHidden())
            action.setEnabled(button.isEnabled())
        self.selection_menu.menuAction().setVisible(self.selection.isHidden())
        self.selection_menu.menuAction().setEnabled(self.selection.isEnabled())
        self.selection_menu.setTitle("Selection · " + self.selection.text())

    def populate_selection(self) -> None:
        """Populate overflow from the actual current-mode selection menu."""
        self.selection_menu.clear()
        menu: QtWidgets.QMenu | None = self.selection.menu()
        if menu is not None:
            menu.aboutToShow.emit()
            self.selection_menu.addActions(menu.actions())


class ResponsiveWorkspace(QtCore.QObject):
    """Bind image fields safely and organize responsive workspace controls."""

    def __init__(self, widget: CentralWidget) -> None:
        """Prepare sidebars, metadata binding, and pane overflow.

        Args:
            widget: Initialized central workspace.
        """
        super().__init__(widget)
        self.widget: CentralWidget = widget
        self.header_targets: dict[QtCore.QObject, ComparePane] = {}
        self.bound_canvas: Canvas | None = None
        self.image_name: str = ""
        self.window: MainWindow | None = None
        self.controls: WorkspaceControls | None = None
        self.groups: list[ToolbarGroup] = []
        self.toolbar_pipes: list[QtWidgets.QLabel] = []
        self.sidebars_adjusted: bool = False
        self.queued: bool = False
        self.flushing: bool = False
        root: QtWidgets.QHBoxLayout = cast(QtWidgets.QHBoxLayout, widget.layout())
        self.splitter: QtWidgets.QSplitter = QtWidgets.QSplitter(
            QtCore.Qt.Orientation.Horizontal, widget
        )
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        self.splitter.splitterMoved.connect(self.sidebar_moved)
        for frame in (
            widget.framePointWidget,
            widget.frameCenter,
            widget.frameCustomField,
        ):
            root.removeWidget(frame)
            frame.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Preferred,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
            frame.setMinimumWidth(180 if frame is not widget.frameCenter else 220)
            self.splitter.addWidget(frame)
        root.addWidget(self.splitter)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([425, 800, 230])
        self.compact_project_controls()
        # Existing tables and the custom-field area retain native scrolling.
        for row in (0, 1):
            spacer: QtWidgets.QLayoutItem | None = (
                widget.point_widget.gridLayout_3.itemAtPosition(row, 3)
            )
            if spacer is not None and spacer.spacerItem() is not None:
                spacer.spacerItem().changeSize(
                    0,
                    0,
                    QtWidgets.QSizePolicy.Policy.Expanding,
                    QtWidgets.QSizePolicy.Policy.Minimum,
                )
        self.pane_overflows: list[PaneOverflow] = [
            PaneOverflow(pane, widget.workspace_feedback.selection_buttons[index])
            for index, (pane, _canvas) in enumerate(widget.workspace_feedback.panes)
        ]
        for overflow in self.pane_overflows:
            overflow.minimum_changed.connect(self.schedule)
            pane: ComparePane = overflow.pane
            for child in pane.findChildren(QtWidgets.QWidget):
                if (
                    child is not pane.graphics_view
                    and not pane.graphics_view.isAncestorOf(child)
                ):
                    self.header_targets[child] = pane
                    child.installEventFilter(self)
        # Give the path explicit stretch rather than allowing the trailing
        # expanding spacer to take all its width.
        old_path: QtWidgets.QLabel = widget.labelWorkingDirectory
        path_label: FolderPathLabel = FolderPathLabel(widget.frameCenter)
        path_label.setObjectName("labelWorkingDirectory")
        directory_row: QtWidgets.QHBoxLayout = widget.horizontalLayout
        directory_row.replaceWidget(old_path, path_label)
        old_path.hide()
        old_path.deleteLater()
        widget.labelWorkingDirectory = path_label
        directory_row.setStretch(directory_row.indexOf(path_label), 1)
        self.class_indicator: QtWidgets.QLabel | None = None
        for canvas in (widget.canvas, widget.reference_canvas):
            canvas.image_about_to_change.connect(self.flush)
            canvas.image_loaded.connect(self.image_changed)
            canvas.flush_fields = self.flush
        widget.compare_enabled_changed.connect(self.bind_active)
        widget.compare_enabled_changed.connect(self.schedule)
        widget.compare_layout_changed.connect(self.schedule)
        widget.canvas.fields_updated.connect(self.load_fields)
        widget.lineEditSurveyId.setToolTip(
            "Project-wide survey ID; shared by all images and panes"
        )
        for label in widget.frameCustomField.findChildren(QtWidgets.QLabel):
            if label.text().strip() == "Survey Id":
                label.setText("Project survey ID")
        widget.pushButtonAddField.setToolTip(
            "Add a project-wide custom field; its values are stored per image"
        )
        widget.pushButtonDeleteField.setToolTip(
            "Remove a custom field and its values from the project"
        )
        self.bind_active()

    def compact_project_controls(self) -> None:
        """Replace export radio choices with a menu and a compact project grid."""
        point_widget: PointWidget = self.widget.point_widget
        grid: QtWidgets.QGridLayout = point_widget.gridLayout_4
        export_menu: QtWidgets.QMenu = QtWidgets.QMenu(point_widget.pushButtonExport)
        for label, radio in (
            ("Counts…", point_widget.radioButtonCounts),
            ("Points…", point_widget.radioButtonPoints),
            ("Chips…", point_widget.radioButtonChips),
            ("Overlay…", point_widget.radioButtonOverlay),
        ):
            radio.hide()
            action: QtGui.QAction = export_menu.addAction(
                label, lambda r=radio: self.export(r)
            )
            if label == "Overlay…":
                action.setToolTip("Export the Current image with its dot overlay")
        export_menu.setToolTipsVisible(True)
        point_widget.pushButtonExport.clicked.disconnect(point_widget.export)
        point_widget.pushButtonExport.setText("Export…")
        point_widget.pushButtonExport.setMenu(export_menu)
        project: QtWidgets.QFrame = QtWidgets.QFrame(point_widget)
        buttons: QtWidgets.QGridLayout = QtWidgets.QGridLayout(project)
        buttons.setContentsMargins(0, 0, 0, 0)
        recover: QtWidgets.QPushButton = self.widget.workspace_feedback.recover_button
        for index, button in enumerate(
            (
                point_widget.pushButtonLoadPoints,
                point_widget.pushButtonSave,
                point_widget.pushButtonImport,
                recover,
                point_widget.pushButtonReset,
                point_widget.pushButtonExport,
            )
        ):
            grid.removeWidget(button)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            button.setStyleSheet("text-align: left;")
            button.setIconSize(point_widget.pushButtonSave.iconSize())
            button.setFixedHeight(point_widget.pushButtonSave.sizeHint().height())
            buttons.addWidget(button, index // 2, index % 2)
        spacer: QtWidgets.QLayoutItem | None = grid.itemAtPosition(6, 1)
        if spacer is not None:
            grid.removeItem(spacer)
        grid.addWidget(project, 5, 0, 3, 3)
        point_widget.pushButtonLoadPoints.setToolTip(
            "Open an existing point/project file"
        )
        point_widget.pushButtonImport.setToolTip(
            "Import classes and custom fields from another point file"
        )

    def export(self, radio: QtWidgets.QRadioButton) -> None:
        """Run the existing exporter for an explicitly chosen output type.

        Args:
            radio: Hidden legacy selection backing the exporter.
        """
        self.flush()
        radio.setChecked(True)
        self.widget.point_widget.export()

    def flush(self) -> None:
        """Commit pending text while the old image binding is still intact."""
        if self.flushing:
            return
        self.flushing = True
        try:
            for edit in self.widget.frameCustomField.findChildren((LineText, BoxText)):
                if edit.timer.isActive():
                    edit.fire()
        finally:
            self.flushing = False

    def bind_active(self) -> None:
        """Flush the previous target, then bind fields to the active image."""
        canvas: Canvas = self.widget._active_annotation_context()[0]
        name: str = canvas.current_image_name or ""
        master: Canvas = self.widget.canvas
        if not master.directory or (
            canvas is not master
            and (canvas.directory != master.directory or name not in master.points)
        ):
            canvas = master
            name = master.current_image_name or ""
        if canvas is self.bound_canvas and name == self.image_name:
            return
        self.flush()
        self.bound_canvas = canvas
        self.image_name = name
        self.refresh_metadata()

    def image_changed(self, directory: str, name: str) -> None:
        """Refresh image fields after either canvas changes its displayed image.

        Args:
            directory: Source image directory.
            name: Image basename.
        """
        del directory, name
        self.bind_active()
        self.sync_status()

    def refresh_metadata(self) -> None:
        """Show coordinates, fields, and an explicit Current/Reference heading."""
        reference: bool = self.bound_canvas is self.widget.reference_canvas
        target: str = "Reference" if reference else "Current"
        self.widget.groupBoxImageData.setTitle(
            "Image data — " + (target if self.image_name else "No image")
        )
        self.widget.groupBoxImageData.setToolTip(self.image_name or "No image loaded")
        self.widget.lineEditX.setEnabled(bool(self.image_name))
        self.widget.lineEditY.setEnabled(bool(self.image_name))
        self.widget.frameCustomFields.setEnabled(bool(self.image_name))
        values: dict[str, float | str] = self.widget.canvas.coordinates.get(
            self.image_name, {}
        )
        self.widget.lineEditX.setText(str(values.get("x", "")))
        self.widget.lineEditY.setText(str(values.get("y", "")))
        self.load_fields()

    def load_fields(self) -> None:
        """Load the bound image's values, clearing fields absent from that image."""
        self.flush()
        data: dict[str, str] = {
            field: values.get(self.image_name, "")
            for field, values in self.widget.canvas.custom_fields["data"].items()
        }
        self.widget.load_custom_data.emit(data)

    def save_field(self, field: str, text: str) -> None:
        """Write delayed text to the explicit bound image in shared project data.

        Args:
            field: Custom-field name.
            text: Editor text.
        """
        canvas: Canvas = self.widget.canvas
        definitions: set[str] = {name for name, _kind in canvas.custom_fields["fields"]}
        if self.image_name and field in definitions:
            values: dict[str, str] = canvas.custom_fields["data"].setdefault(field, {})
            if values.get(self.image_name, "") != text:
                values[self.image_name] = text
                canvas.dirty = True

    def save_coordinates(self) -> None:
        """Write coordinates to the bound image without changing pane activation."""
        if self.image_name:
            self.widget.canvas.coordinates[self.image_name] = {
                "x": self.widget.lineEditX.text(),
                "y": self.widget.lineEditY.text(),
            }
            self.widget.canvas.dirty = True

    def attach_window(
        self,
        window: MainWindow,
        controls: WorkspaceControls,
        panels: QtWidgets.QToolBar,
    ) -> None:
        """Attach compact toolbar presentations and stable status indicators.

        Args:
            window: Owning application window.
            controls: Existing shared tool coordinator.
            panels: Existing panels toolbar.
        """
        self.window = window
        self.controls = controls
        for bar in (panels, controls.tools_toolbar, controls.display_toolbar):
            for action in list(bar.actions()):
                bar.removeAction(action)
        panels_group: ToolbarGroup = ToolbarGroup(
            "Panels",
            panels,
            [window.left_sidebar_action, window.right_sidebar_action],
            controls.compare_button,
        )
        controls.compare_button.menu().setTitle("Compare layout")
        tools_group: ToolbarGroup = ToolbarGroup(
            "Tools",
            controls.tools_toolbar,
            [
                controls.actions[mode]
                for mode in (
                    InteractionMode.POINT,
                    InteractionMode.LINE,
                    InteractionMode.POLYGON,
                    InteractionMode.SELECT,
                    InteractionMode.COUNT,
                )
            ],
            subgroup_breaks={
                controls.actions[InteractionMode.SELECT]: 8,
                controls.actions[InteractionMode.COUNT]: 6,
            },
        )
        tools_group.selector.setCheckable(True)
        tools_group.selector.setChecked(True)
        display_group: ToolbarGroup = ToolbarGroup(
            "Display", controls.display_toolbar, list(controls.display_actions.values())
        )
        window.insertToolBar(controls.tools_toolbar, controls.display_toolbar)
        for bar in (panels, controls.display_toolbar):
            pipe: QtWidgets.QLabel = QtWidgets.QLabel("|", bar)
            pipe.setObjectName("toolbarGroupPipe")
            pipe.setMargin(5)
            pipe.setForegroundRole(QtGui.QPalette.ColorRole.Mid)
            pipe.setAccessibleName("Toolbar group separator")
            bar.addWidget(pipe)
            self.toolbar_pipes.append(pipe)
        self.groups = [panels_group, tools_group, display_group]
        self.class_indicator = QtWidgets.QLabel(tools_group)
        self.class_indicator.setObjectName("selectedClassIndicator")
        self.class_indicator.setFixedWidth(170)
        self.class_indicator.setMargin(4)
        tools_group.class_label = self.class_indicator
        tools_row: QtWidgets.QHBoxLayout = cast(
            QtWidgets.QHBoxLayout, tools_group.layout()
        )
        count_button: QtWidgets.QToolButton = next(
            button
            for button in tools_group.buttons
            if button.defaultAction() is controls.actions[InteractionMode.COUNT]
        )
        tools_group.class_slot = tools_row.indexOf(count_button) + 1
        tools_row.insertWidget(tools_group.class_slot, self.class_indicator)
        window.setMinimumSize(900, 540)
        window.installEventFilter(self)
        window.left_sidebar_action.toggled.connect(self.schedule)
        window.right_sidebar_action.toggled.connect(self.schedule)
        self.sync_status()
        self.schedule()

    def sidebar_moved(self, position: int, index: int) -> None:
        """Keep user-chosen sidebar sizes after a splitter handle is dragged.

        Args:
            position: New handle position.
            index: Splitter handle index.
        """
        del position, index
        self.sidebars_adjusted = True

    def copy_path(self) -> None:
        """Copy the full working-folder path to the clipboard."""
        QtWidgets.QApplication.clipboard().setText(self.widget.canvas.directory)

    def sync_status(self) -> None:
        """Keep the class beside its tool and the original folder row current."""
        if self.class_indicator is None:
            return
        if self.window is not None:
            self.widget.workspace_feedback.save_label.setFixedWidth(
                self.widget.workspace_feedback.save_label.fontMetrics().horizontalAdvance(
                    "Unsaved changes"
                )
                + 24
            )
            self.widget.workspace_feedback.save_label.setMaximumHeight(
                self.window.statusBar().sizeHint().height()
            )
        name: str = self.widget.canvas.current_class_name or "Choose a class"
        text: str = "Class: " + name
        width: int = min(
            170,
            max(90, self.class_indicator.fontMetrics().horizontalAdvance(text) + 12),
        )
        if self.class_indicator.width() != width:
            self.class_indicator.setFixedWidth(width)
            self.schedule()
        self.class_indicator.setText(
            self.class_indicator.fontMetrics().elidedText(
                text, QtCore.Qt.TextElideMode.ElideMiddle, width - 8
            )
        )
        self.class_indicator.setToolTip("Selected counting class: " + name)
        directory: str = self.widget.canvas.directory
        if self.widget.labelWorkingDirectory.text() != directory:
            self.widget.labelWorkingDirectory.setText(directory)
        self.widget.labelWorkingDirectory.setToolTip(directory)
        if self.groups and self.controls is not None:
            action: QtGui.QAction = self.controls.actions[self.controls.mode]
            if self.groups[1].selector.text() != action.iconText():
                self.groups[1].selector.setText(action.iconText())
                self.schedule()
            self.groups[1].selector.setIcon(action.icon())
            self.groups[1].selector.setChecked(True)
            self.groups[1].selector.setToolTip(action.toolTip())
        for overflow in self.pane_overflows:
            overflow.sync_actions()

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Schedule adaptive toolbar presentation on window/font changes.

        Args:
            watched: Main window.
            event: Qt layout event.

        Returns:
            False so normal window handling continues.
        """
        if watched in self.header_targets and event.type() in {
            QtCore.QEvent.Type.MouseButtonPress,
            QtCore.QEvent.Type.KeyPress,
        }:
            pane: ComparePane = self.header_targets[watched]
            pane.graphics_view.view_activated.emit()
        if event.type() in {
            QtCore.QEvent.Type.Resize,
            QtCore.QEvent.Type.Show,
            QtCore.QEvent.Type.FontChange,
        }:
            self.schedule()
        return False

    def schedule(self) -> None:
        """Coalesce window resize notifications."""
        if not self.queued:
            self.queued = True
            QtCore.QTimer.singleShot(0, self.adapt)

    def adapt(self) -> None:
        """Compact tool groups before controls can disappear off the window."""
        self.queued = False
        if self.window is None or sip.isdeleted(self.window) or not self.groups:
            return
        current: int = self.widget.current_pane.minimumWidth()
        reference: int = self.widget.compare_pane.minimumWidth()
        center: int = current
        if self.widget.compare_enabled():
            center = (
                current + reference + self.widget.compare_splitter.handleWidth()
                if self.widget.compare_layout() == "1x2"
                else max(current, reference)
            )
        self.widget.frameCenter.setMinimumWidth(center)
        sides: int = 0
        for frame in (self.widget.framePointWidget, self.widget.frameCustomField):
            minimum_width: int = max(180, frame.minimumSizeHint().width())
            if frame is self.widget.frameCustomField:
                minimum_width = max(
                    minimum_width,
                    frame.fontMetrics().horizontalAdvance("Image data — Reference")
                    + 36,
                )
            frame.setMinimumWidth(minimum_width)
            if not frame.isHidden():
                sides += minimum_width
        widths: list[int] = [group.natural_width() for group in self.groups]
        pipes_width: int = sum(pipe.sizeHint().width() for pipe in self.toolbar_pipes)
        available: int = self.window.width() - 40 - pipes_width
        compact: list[bool] = [False, False, False]
        for index in (1, 2, 0):
            if sum(widths) <= available:
                break
            compact[index] = True
            widths[index] = self.groups[index].compact_width()
        for index, group in enumerate(self.groups):
            group.set_compact(compact[index])
        minimum: int = (
            sum(group.compact_width() for group in self.groups) + 48 + pipes_width
        )
        self.window.setMinimumWidth(max(900, minimum, sides + center + 40))
        if self.window.isVisible() and not self.sidebars_adjusted:
            available_space: int = (
                self.splitter.width() - 2 * self.splitter.handleWidth()
            )
            left: int = 425 if not self.widget.framePointWidget.isHidden() else 0
            remainder: int = max(0, available_space - left)
            right: int = (
                round(remainder / 4)
                if not self.widget.frameCustomField.isHidden()
                else 0
            )
            self.splitter.setSizes([left, remainder - right, right])
        for overflow in self.pane_overflows:
            overflow.schedule()
