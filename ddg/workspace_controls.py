"""Shared toolbar tools and compact, stable workspace feedback."""

from __future__ import annotations

from collections import Counter
from time import monotonic
from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

from .canvas import Canvas
from .central_graphics_view import CentralGraphicsView, InteractionMode
from .workspace_feedback import WorkspaceFeedback
from .selection_editor import SelectionEditor

if TYPE_CHECKING:
    from .main_window import MainWindow
    from .central_widget import CentralWidget


class WorkspaceControls(QtCore.QObject):
    """Keep toolbar, menu, pane interactions, and status feedback synchronized."""

    def __init__(
        self,
        window: MainWindow,
        panels: QtWidgets.QToolBar,
        annotation_actions: dict[InteractionMode, QtGui.QAction],
        navigator_action: QtGui.QAction,
    ) -> None:
        """Attach shared controls to the existing main window.

        Args:
            window: Owning application window.
            panels: Existing sidebar toolbar.
            annotation_actions: Existing menu actions and shortcuts to reuse.
            navigator_action: Existing shared navigator action.
        """
        super().__init__(window)
        self.window: MainWindow = window
        self.feedback: WorkspaceFeedback = window.centralWidget().workspace_feedback
        self.widget: CentralWidget = self.feedback.widget
        self.mode: InteractionMode = InteractionMode.COUNT
        self.switching: bool = False
        self.feedback.controls = self
        panels.setWindowTitle("Panels")
        self.compare_button: QtWidgets.QToolButton = QtWidgets.QToolButton(panels)
        self.compare_button.setDefaultAction(window.compare_action)
        self.compare_button.setText("Compare")
        window.compare_action.setIconText("Compare")
        window.compare_action.setToolTip(
            "Show or hide Reference; use the arrow to choose its layout"
        )
        self.compare_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        compare_menu: QtWidgets.QMenu = QtWidgets.QMenu(self.compare_button)
        compare_menu.addAction(window.compare_1x2_action)
        compare_menu.addAction(window.compare_2x1_action)
        self.compare_button.setMenu(compare_menu)
        panels.addWidget(self.compare_button)
        panels.addSeparator()
        self.tools_toolbar: QtWidgets.QToolBar = self.toolbar("Tools", "toolsToolbar")
        self.tool_group: QtGui.QActionGroup = QtGui.QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.actions: dict[InteractionMode, QtGui.QAction] = {}
        descriptions: dict[InteractionMode, tuple[str, str]] = {
            InteractionMode.COUNT: (
                "Count dots",
                "Click to count using the selected class; Shift+drag selects dots",
            ),
            InteractionMode.POINT: (
                "Landmark",
                "Place landmark point annotations in either pane",
            ),
            InteractionMode.LINE: (
                "Line",
                "Draw cutlines in either pane; Enter finishes, Esc cancels the draft",
            ),
            InteractionMode.POLYGON: (
                "Polygon",
                "Draw count regions in either pane; Enter finishes, Esc cancels the draft",
            ),
            InteractionMode.SELECT: (
                "Select/Edit",
                "Select and edit dots or annotations in either pane; Esc clears selection",
            ),
        }
        for mode, (label, tooltip) in descriptions.items():
            action: QtGui.QAction = annotation_actions.get(mode) or QtGui.QAction(
                label, window
            )
            if mode is InteractionMode.COUNT:
                action.triggered.connect(
                    lambda _checked=False: self.select_tool(InteractionMode.COUNT)
                )
            action.setCheckable(True)
            action.setIconText(label)
            action.setToolTip(tooltip + ". Applies to both panes.")
            action.setIcon(QtGui.QIcon(f"icons:tool_{mode.value}.svg"))
            self.tool_group.addAction(action)
            self.tools_toolbar.addAction(action)
            self.actions[mode] = action
        self.tools_toolbar.addSeparator()
        self.display_toolbar: QtWidgets.QToolBar = self.toolbar(
            "Display", "displayToolbar"
        )
        self.display_actions: dict[str, QtGui.QAction] = {}
        for name, checkbox in (
            ("Dots", self.widget.point_widget.checkBoxDisplayPoints),
            ("Grid", self.widget.point_widget.checkBoxDisplayGrid),
        ):
            display_action: QtGui.QAction = self.display_toolbar.addAction(name)
            display_action.setCheckable(True)
            display_action.setChecked(checkbox.isChecked())
            display_action.setToolTip(f"Show or hide {name.lower()} in both panes")
            display_action.toggled.connect(checkbox.setChecked)
            checkbox.toggled.connect(display_action.setChecked)
            checkbox.hide()
            self.display_actions[name] = display_action
        navigator_action.setIconText("Navigator")
        navigator_action.setToolTip("Show or hide the overview navigator in both panes")
        self.display_toolbar.addAction(navigator_action)
        self.display_actions["Navigator"] = navigator_action
        self.editors: dict[CentralGraphicsView, SelectionEditor] = {}
        self.dot_menus: list[QtWidgets.QMenu] = []
        self.annotation_menus: list[QtWidgets.QMenu] = []
        for index, (pane, canvas) in enumerate(self.feedback.panes):
            view: CentralGraphicsView = pane.graphics_view
            view.persistent_mode = self.mode
            canvas.image_change_allowed = lambda p=pane, c=canvas: self.can_leave_image(
                p.graphics_view, c
            )
            view.view_activated.connect(lambda v=view: self.activate(v))
            view.annotation_cancel_requested.connect(
                lambda c=canvas: self.feedback.clear_selection(c)
            )
            button: QtWidgets.QToolButton = self.feedback.selection_buttons[index]
            self.dot_menus.append(button.menu())
            menu: QtWidgets.QMenu = QtWidgets.QMenu(button)
            menu.addAction(
                "Annotation properties…",
                lambda c=canvas: self.widget.edit_selected_annotation_properties_for_canvas(
                    c
                ),
            )
            menu.addAction(
                "Delete annotation…",
                lambda c=canvas: self.widget.delete_selected_annotation_for_canvas(c),
            )
            menu.addAction(
                "Clear annotation selection", canvas.clear_external_annotation_selection
            )
            self.annotation_menus.append(menu)
            self.editors[view] = SelectionEditor(self, view, canvas)
        self.save_indicator: QtWidgets.QLabel = self.feedback.save_label
        self.save_indicator.setFixedWidth(
            self.save_indicator.fontMetrics().horizontalAdvance("Unsaved changes") + 24
        )
        self.save_indicator.setMaximumHeight(
            self.window.statusBar().sizeHint().height()
        )
        self.window.statusBar().addPermanentWidget(self.save_indicator)
        self.save_indicator.show()
        self.select_tool(InteractionMode.COUNT)
        self.widget.workspace_layout.attach_window(window, self, panels)

    def toolbar(self, title: str, name: str) -> QtWidgets.QToolBar:
        """Create a named toolbar on the existing row with native overflow.

        Args:
            title: Accessible toolbar/group title.
            name: Stable Qt object name.

        Returns:
            Newly attached toolbar.
        """
        bar: QtWidgets.QToolBar = QtWidgets.QToolBar(title, self.window)
        bar.setObjectName(name)
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        bar.setIconSize(QtCore.QSize(18, 18))
        self.window.addToolBar(bar)
        return bar

    def select_tool(self, mode: InteractionMode) -> bool:
        """Select one workspace tool without discarding unfinished geometry.

        Args:
            mode: Requested tool for both panes.

        Returns:
            Whether the requested tool became active.
        """
        if mode is self.mode:
            self.actions[mode].setChecked(True)
            self.refresh()
            return True
        if mode is not self.mode:
            for pane, _canvas in self.feedback.panes:
                if pane.graphics_view.line_points or pane.graphics_view.polygon_points:
                    self.feedback.notice = f"Unfinished shape in {pane.label.text().title()}: Enter finishes; Esc cancels there before changing tools."
                    self.actions[self.mode].setChecked(True)
                    self.refresh()
                    return False
        self.switching = True
        self.mode = mode
        self.feedback.cancel_transfer()
        self.widget._pending_compare_annotation_mode = None
        try:
            for pane, canvas in self.feedback.panes:
                view: CentralGraphicsView = pane.graphics_view
                view.persistent_mode = mode
                view.cancel_annotation()
                canvas.clear_external_annotation_selection()
                active_view: CentralGraphicsView = (
                    self.widget._active_annotation_context()[1]
                )
                if mode is not InteractionMode.SELECT or view is not active_view:
                    canvas.selection = []
                canvas.display_points()
                self.restore_tool(view)
            self.actions[mode].setChecked(True)
        finally:
            self.switching = False
        self.refresh()
        return True

    def restore_tool(self, view: CentralGraphicsView) -> None:
        """Restore the selected tool after image loads or enhancement redraws.

        Args:
            view: Pane whose transient state was reset.
        """
        view.persistent_mode = self.mode
        view.interaction_mode = self.mode
        view.annotation_mode_changed.emit(self.mode.value)

    def activate(self, view: CentralGraphicsView) -> None:
        """Keep annotation selection in only the pane explicitly clicked.

        Args:
            view: Newly clicked pane.
        """
        if self.mode is InteractionMode.SELECT:
            for pane, canvas in self.feedback.panes:
                if pane.graphics_view is not view:
                    canvas.clear_external_annotation_selection()
                    canvas.selection = []
                    canvas.display_points()
        self.refresh()

    def claim(self, target: CentralGraphicsView) -> None:
        """Protect an unfinished drawing when the user clicks another pane.

        Args:
            target: Pane receiving an ordinary drawing click.
        """
        for pane, _canvas in self.feedback.panes:
            view: CentralGraphicsView = pane.graphics_view
            if view is not target and (view.line_points or view.polygon_points):
                target.annotation_target_blocked = True
                self.feedback.notice = f"Unfinished shape in {pane.label.text().title()}: finish with Enter or cancel with Esc in that pane."
                self.refresh()
                return
        self.feedback.notice = ""

    def can_leave_image(self, view: CentralGraphicsView, canvas: Canvas) -> bool:
        """Prevent image navigation from discarding an unfinished annotation.

        Args:
            view: View whose image would change.
            canvas: Current image owner.

        Returns:
            Whether navigation can proceed safely.
        """
        if not (view.line_points or view.polygon_points):
            return True
        self.feedback.notice = "Finish the shape with Enter, or cancel it with Esc, before changing or hiding its image."
        self.refresh()
        for pane, owner in self.feedback.panes:
            if owner is canvas and canvas.current_image_name:
                # Picker handlers may select a new name after load_image returns.
                QtCore.QTimer.singleShot(
                    0,
                    lambda p=pane, name=canvas.current_image_name: p.select_image(name),
                )
        return False

    def cancel_current(self) -> None:
        """Cancel a draft or clear selections while retaining the selected tool."""
        canvas: Canvas
        view: CentralGraphicsView
        canvas, view = self.widget._active_annotation_context()
        view.cancel_annotation()
        canvas.clear_external_annotation_selection()
        canvas.selection = []
        canvas.display_points()
        self.restore_tool(view)
        self.feedback.notice = ""
        self.refresh()

    def refresh(self) -> None:
        """Update status and selection menus without changing viewport geometry."""
        if self.switching or not hasattr(self, "save_indicator"):
            return
        for index, (pane, canvas) in enumerate(self.feedback.panes):
            active: bool = (index == 1) == (
                self.widget._last_active_view_name == "reference"
            )
            color: str = "#438ac7" if active else "palette(mid)"
            style: str = f"QFrame#{pane.objectName()} {{ border: 2px solid {color}; }}"
            if pane.styleSheet() != style:
                pane.setStyleSheet(style)
            button: QtWidgets.QToolButton = self.feedback.selection_buttons[index]
            if self.mode is InteractionMode.SELECT:
                editor: SelectionEditor = self.editors[pane.graphics_view]
                dots: int = len(canvas.selection)
                annotations: int = len(canvas.selected_annotation_indices)
                button.setText(
                    f"{dots + annotations} items"
                    if dots and annotations
                    else (
                        (
                            "1 annotation"
                            if annotations == 1
                            else f"{annotations} annotations"
                        )
                        if annotations
                        else ("1 dot" if dots == 1 else f"{dots} dots")
                    )
                )
                button.setEnabled(bool(dots + annotations))
                button.setToolTip(editor.selection_description())
                button.setMenu(editor.menu)
            else:
                count: int = len(canvas.selection)
                counts: Counter[str] = Counter(
                    name for name, _point in canvas.selection
                )
                button.setText(f"{count} dots")
                button.setEnabled(bool(count))
                button.setToolTip(
                    "\n".join(
                        f"{name}: {amount}" for name, amount in sorted(counts.items())
                    )
                )
                button.setMenu(self.dot_menus[index])
        failure: str = (
            self.feedback.recovery_text
            if self.feedback.recovery_text.startswith("Recovery failed")
            else ""
        )
        if self.feedback.save_error:
            self.save_indicator.setText("Save failed")
        elif failure:
            self.save_indicator.setText("Recovery failed")
        elif self.widget.canvas.dirty:
            self.save_indicator.setText("Unsaved changes")
        else:
            self.save_indicator.setText(
                "Saved" if monotonic() < self.feedback.save_notice_until else ""
            )
        self.save_indicator.setToolTip(
            "\n".join(
                part
                for part in (
                    "Point/field data: "
                    + ("unsaved" if self.widget.canvas.dirty else "no unsaved changes"),
                    (
                        "Last saved: " + self.feedback.last_save
                        if self.feedback.last_save
                        else ""
                    ),
                    self.feedback.recovery_text,
                    (
                        "Recovery folder: " + self.widget.canvas.directory
                        if self.widget.canvas.directory
                        else ""
                    ),
                    "Native annotations save immediately to sidecars.",
                )
                if part
            )
        )
        instructions: dict[InteractionMode, str] = {
            InteractionMode.COUNT: "Count dots · click adds a point; Shift+drag selects points; Esc clears selection; C+drag pans; Z+drag zooms in; X+drag zooms out.",
            InteractionMode.POINT: "Landmark · click either pane to place a point. Tool stays selected; Count dots returns to counting.",
            InteractionMode.LINE: "Line · click vertices in either pane; Enter/double-click finishes; Esc cancels the draft. Tool stays selected.",
            InteractionMode.POLYGON: "Polygon · click vertices in either pane; Enter/double-click finishes; Esc cancels the draft. Tool stays selected.",
            InteractionMode.SELECT: "Select/Edit · click dots or annotations; Shift+click toggles; Shift+drag selects; drag selected items to move; Delete removes; Esc clears.",
        }
        message: str = self.feedback.notice or instructions[self.mode]
        for pane, _canvas in self.feedback.panes:
            vertices: int = len(pane.graphics_view.line_points) + len(
                pane.graphics_view.polygon_points
            )
            if vertices and not self.feedback.notice:
                message = (
                    f"{pane.label.text().title()}: {vertices} vertices · " + message
                )
                break
        if failure:
            message = failure
        elif self.feedback.save_error:
            message = (
                "Save failed — point/field changes remain unsaved. Try Save again."
            )
        if self.window.statusBar().currentMessage() != message:
            self.window.statusBar().showMessage(message)
        self.widget.workspace_layout.sync_status()
