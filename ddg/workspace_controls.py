"""Shared toolbar tools and compact, stable workspace feedback."""

from __future__ import annotations

from collections import Counter
from time import monotonic
from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

from .annotations import Annotation, AnnotationShape
from .canvas import Canvas
from .central_graphics_view import CentralGraphicsView, InteractionMode
from .workspace_feedback import WorkspaceFeedback
from .selection_editor import SelectionEditor
from .shape_editor import ShapeEditor, ShapeTool

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
        self.compare_button.setText("Panes")
        window.compare_action.setIconText("Panes")
        window.compare_action.setToolTip(
            "Restore the last multi-pane setup or show only the active pane"
        )
        self.compare_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        compare_menu: QtWidgets.QMenu = QtWidgets.QMenu(self.compare_button)
        workspace = self.widget.image_workspace
        if workspace is not None:
            count_group: QtGui.QActionGroup = QtGui.QActionGroup(compare_menu)
            for count in range(1, 5):
                action: QtGui.QAction = compare_menu.addAction(
                    f"{count} pane" if count == 1 else f"{count} panes"
                )
                action.setCheckable(True)
                count_group.addAction(action)
                action.triggered.connect(
                    lambda _checked=False, total=count: workspace.set_count(total)
                )
            compare_menu.aboutToShow.connect(
                lambda: workspace.update_count_menu(count_group)
            )
            compare_menu.addSeparator()
        compare_menu.addAction(window.compare_1x2_action)
        compare_menu.addAction(window.compare_2x1_action)
        if workspace is not None:
            compare_menu.addAction("Arrange docked panes", workspace.arrange)
            reopen: QtWidgets.QMenu = compare_menu.addMenu("Reopen pane")
            for name, dock in workspace.docks.items():
                action = reopen.addAction(dock.windowTitle())
                action.setData(name)
                action.triggered.connect(
                    lambda _checked=False, key=name: workspace.reopen(key)
                )
            reopen.aboutToShow.connect(lambda: workspace.update_reopen_menu(reopen))
        self.compare_button.setMenu(compare_menu)
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
                "Place landmark point annotations in any pane",
            ),
            InteractionMode.LINE: (
                "Line",
                "Draw cutlines in any pane; Enter finishes, Esc cancels the draft",
            ),
            InteractionMode.POLYGON: (
                "Polygon",
                "Draw count regions in any pane; Enter finishes, Esc cancels the draft",
            ),
            InteractionMode.SELECT: (
                "Select",
                "Select, move, or delete whole dots and annotations; Esc clears selection",
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
            action.setToolTip(tooltip + ". Applies to all panes.")
            action.setIcon(QtGui.QIcon(f"icons:tool_{mode.value}.svg"))
            self.tool_group.addAction(action)
            self.tools_toolbar.addAction(action)
            self.actions[mode] = action
        self.last_shape_tool: ShapeTool = ShapeTool.RESHAPE
        self.shape_default: QtGui.QAction = QtGui.QAction("Edit Shape", window)
        self.shape_default.setCheckable(True)
        self.shape_default.triggered.connect(self.resume_shape_tool)
        self.shape_button: QtWidgets.QToolButton = QtWidgets.QToolButton(
            self.tools_toolbar
        )
        self.shape_button.setObjectName("editShapeButton")
        self.shape_button.setDefaultAction(self.shape_default)
        self.shape_button.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.shape_button.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self.shape_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.shape_menu: QtWidgets.QMenu = QtWidgets.QMenu(
            "Edit Shape", self.shape_button
        )
        self.shape_button.setMenu(self.shape_menu)
        self.shape_actions: dict[ShapeTool, QtGui.QAction] = {}
        for tool in ShapeTool:
            shape_action: QtGui.QAction = self.shape_menu.addAction(tool.value)
            shape_action.setCheckable(True)
            shape_action.triggered.connect(
                lambda _checked=False, selected=tool: self.start_shape_tool(selected)
            )
            self.shape_actions[tool] = shape_action
        self.snap_action: QtGui.QAction = QtGui.QAction("Snap", window)
        self.snap_action.setCheckable(True)
        self.snap_action.setToolTip(
            "Snap sketch clicks to nearby annotation vertices or edges"
        )
        self.snap_action.triggered.connect(self.resume_image_focus)
        self.trace_action: QtGui.QAction = QtGui.QAction("Trace", window)
        self.trace_action.setCheckable(True)
        self.trace_action.setToolTip(
            "Follow part of a cutline while drawing or reshaping a count area"
        )
        self.trace_action.triggered.connect(self.trace)
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
            display_action.setToolTip(f"Show or hide {name.lower()} in all panes")
            display_action.toggled.connect(checkbox.setChecked)
            checkbox.toggled.connect(display_action.setChecked)
            checkbox.hide()
            self.display_actions[name] = display_action
        navigator_action.setIconText("Navigator")
        navigator_action.setToolTip("Show or hide the overview navigator in all panes")
        self.display_toolbar.addAction(navigator_action)
        self.display_actions["Navigator"] = navigator_action
        annotations_action: QtGui.QAction = self.display_toolbar.addAction(
            "Annotations"
        )
        annotations_action.setCheckable(True)
        annotations_action.setChecked(True)
        annotations_action.setToolTip("Show or hide annotations in all panes")
        annotations_action.toggled.connect(self.set_annotations_visible)
        self.display_actions["Annotations"] = annotations_action
        self.editors: dict[CentralGraphicsView, SelectionEditor] = {}
        self.shape_editors: dict[CentralGraphicsView, ShapeEditor] = {}
        self.dot_menus: list[QtWidgets.QMenu] = []
        self.annotation_menus: list[QtWidgets.QMenu] = []
        for index, (pane, canvas) in enumerate(self.feedback.panes):
            view: CentralGraphicsView = pane.graphics_view
            view.persistent_mode = self.mode
            canvas.image_change_allowed = lambda p=pane, c=canvas: self.can_leave_image(
                p.graphics_view, c
            )
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
            self.editors[view] = SelectionEditor(self, view, canvas, button.menu())
            canvas.show_external_annotation_handles = False
            self.shape_editors[view] = ShapeEditor(self, view, canvas)
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

    def set_annotations_visible(self, visible: bool) -> None:
        """Update annotation visibility in Current and Reference.

        Args:
            visible: Whether annotation graphics should be shown.
        """
        for pane, canvas in self.feedback.panes:
            self.editors[pane.graphics_view].cancel_gesture()
            canvas.set_annotations_visible(visible)
        self.refresh()

    def active_shape_editor(self) -> ShapeEditor:
        """Resolve the last clicked pane even when a toolbar menu has focus."""
        return self.shape_editors[self.widget._active_annotation_context()[1]]

    def resume_image_focus(self) -> None:
        """Send sketch keystrokes back to the pane owning the edit."""
        view: CentralGraphicsView = self.active_shape_editor().view
        view.window().activateWindow()
        view.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def resume_shape_tool(self) -> None:
        """Start the last eligible tool or show options for a new sketch."""
        editor: ShapeEditor = self.active_shape_editor()
        target: tuple[int, Annotation] | None = editor.target()
        if target is None:
            self.refresh()
            self.shape_button.showMenu()
            return
        tool: ShapeTool = self.last_shape_tool
        if (
            tool is ShapeTool.LINE_END
            and target[1].shape_type is not AnnotationShape.LINE
        ):
            tool = ShapeTool.RESHAPE
        self.start_shape_tool(tool)

    def start_shape_tool(self, tool: ShapeTool) -> None:
        """Start a shape tool on the selected geometry in the active pane."""
        editor: ShapeEditor = self.active_shape_editor()
        target: tuple[int, Annotation] | None = editor.target()
        if target is None or self.mode is not InteractionMode.SELECT:
            self.refresh()
            return
        if (
            tool is ShapeTool.LINE_END
            and target[1].shape_type is not AnnotationShape.LINE
        ):
            self.refresh()
            return
        if editor.has_draft():
            editor.notice(
                "Press Enter to apply or Esc to cancel before changing shape tools."
            )
            self.resume_image_focus()
            return
        self.last_shape_tool = tool
        self.editors[editor.view].cancel_gesture()
        editor.start(tool)
        editor.notice()
        self.resume_image_focus()

    def trace(self) -> None:
        """Arm or cancel tracing in the pane that owns the polygon sketch."""
        self.active_shape_editor().start_trace()
        self.refresh()
        self.resume_image_focus()

    def refresh_shape_controls(self) -> str:
        """Synchronize enabled, pressed, and labeled shape controls."""
        editor: ShapeEditor = self.active_shape_editor()
        target: tuple[int, Annotation] | None = editor.target()
        drawing: bool = self.mode in {InteractionMode.LINE, InteractionMode.POLYGON}
        eligible: bool = self.mode is InteractionMode.SELECT and target is not None
        self.shape_default.setEnabled(eligible or drawing)
        self.shape_menu.menuAction().setEnabled(eligible or drawing)
        tool: ShapeTool | None = editor.tool if eligible else None
        label: str = tool.value if tool is not None else "Edit Shape"
        if self.shape_default.text() != label:
            self.shape_default.setText(label)
            self.widget.workspace_layout.schedule()
        self.shape_default.setChecked(tool is not None)
        self.actions[self.mode].setChecked(tool is None)
        for candidate, action in self.shape_actions.items():
            action.setEnabled(
                eligible
                and (
                    candidate is not ShapeTool.LINE_END
                    or (
                        target is not None
                        and target[1].shape_type is AnnotationShape.LINE
                    )
                )
            )
            action.setChecked(candidate is tool)
        self.snap_action.setEnabled(drawing or tool is not None)
        self.trace_action.setEnabled(editor.can_trace() or editor.tracing)
        self.trace_action.setChecked(editor.tracing)
        return editor.instructions()

    def select_tool(self, mode: InteractionMode) -> bool:
        """Select one workspace tool without discarding unfinished geometry.

        Args:
            mode: Requested tool for all panes.

        Returns:
            Whether the requested tool became active.
        """
        shape_editor: ShapeEditor = self.active_shape_editor()
        if mode is self.mode and shape_editor.tool is None:
            self.actions[mode].setChecked(True)
            self.refresh()
            return True
        for pane, _canvas in self.feedback.panes:
            if pane.graphics_view.has_annotation_draft():
                self.feedback.notice = f"Unfinished shape in {pane.label.text().title()}: Enter finishes; Esc cancels there before changing tools."
                self.refresh()
                return False
        shape_editor.stop()
        self.feedback.notice = ""
        if mode is self.mode:
            self.refresh()
            return True
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
        if (
            self.widget.image_workspace is not None
            and view is not self.widget._active_annotation_context()[1]
        ):
            return
        if self.mode is InteractionMode.SELECT:
            for pane, canvas in self.feedback.panes:
                if pane.graphics_view is not view:
                    self.shape_editors[pane.graphics_view].stop()
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
            if view is not target and view.has_annotation_draft():
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
        workspace = self.widget.image_workspace
        if workspace is not None:
            allowed: bool = workspace.can_switch()
        else:
            allowed = not view.has_annotation_draft()
        if allowed:
            return True
        if workspace is None:
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
        self.shape_editors[view].stop()
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
            active: bool = pane.graphics_view is self.widget._active_annotation_context()[1]
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
        shape_instructions: str = self.refresh_shape_controls()
        instructions: dict[InteractionMode, str] = {
            InteractionMode.COUNT: "Count dots · click adds a point; Shift+drag selects points; Esc clears selection; C+drag pans; Z+drag zooms in; X+drag zooms out.",
            InteractionMode.POINT: "Landmark · click any pane to place a point. Tool stays selected; Count dots returns to counting.",
            InteractionMode.LINE: "Line · click vertices in any pane; Enter/double-click finishes; Esc cancels the draft. Tool stays selected.",
            InteractionMode.POLYGON: "Polygon · click vertices in any pane; Enter/double-click finishes; Esc cancels the draft. Tool stays selected.",
            InteractionMode.SELECT: "Select · click dots or annotations; Shift+click toggles; Shift+drag selects; drag selected items to move; Delete removes; Esc clears.",
        }
        if self.feedback.notice.startswith("Unfinished shape in ") and not any(
            pane.graphics_view.has_annotation_draft()
            for pane, _canvas in self.feedback.panes
        ):
            self.feedback.notice = ""
        message: str = (
            self.feedback.notice or shape_instructions or instructions[self.mode]
        )
        for pane, _canvas in self.feedback.panes:
            vertices: int = len(pane.graphics_view.line_points) + len(
                pane.graphics_view.polygon_points
            )
            if vertices and not (self.feedback.notice or shape_instructions):
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
