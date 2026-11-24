"""Edit → duplicates, merge joints, divide and join frames, mesh."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import (
    DeleteElementsCommand,
    DeleteNodesCommand,
    FixDuplicatesCommand,
    JoinFramesCommand,
    MergeJointsCommand,
    MeshCommand,
)
from opensees_studio.commands.tables import ApplyModelTablesCommand
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import DuplicatesDialog, MeshDialog
from opensees_studio.views.dialogs.connect_joints import DivideFramesDialog, MergeJointsDialog
from opensees_studio.views.dialogs.model_tables import ModelTablesDialog


class ModelToolsController(QObject):
    """What repairs and refines the geometry of a model, one undo step each.

    Check Model for Duplicates, Merge Joints, Divide Frames at Joints, Join
    Frames and Mesh; and the two blunt edits, Delete selection and Interactive
    Table Editing. The plans and reports come from ``core``; this shows the
    dialog, applies one command and leaves selected what the command made.
    ``select_rows`` is the window's "show me this row" of a report (it selects
    the joints and elements of the row in the viewport). It keeps no state.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        select_rows: Callable[[Sequence[int], Sequence[int]], None],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._select_rows = select_rows

    def check_duplicates(self) -> None:
        """Edit → Check Model for Duplicates: report, then repair on request.

        The dialog reports; :class:`FixDuplicatesCommand` repairs and recomputes
        the element duplicates *after* merging the nodes, because merging two
        coincident nodes can turn two members into the same member.
        """
        project = self._vm.project
        if project is None:
            QMessageBox.information(self._window, "Duplicates", "Open or create a project first.")
            return
        dlg = DuplicatesDialog(project, on_select=self._select_rows, parent=self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        command = FixDuplicatesCommand(self._vm, tolerance=dlg.tolerance())
        try:
            self._vm.apply_command(command)
        except Exception as exc:
            QMessageBox.critical(self._window, "Could not fix the duplicates", str(exc))
            return
        self._shell.canvas().selection.clear()
        self._shell.canvas().render()
        self._shell.log(f"Duplicates: {command.report.summary()}")

    def merge_joints(self) -> None:
        """Edit → Merge Joints: joints closer than a tolerance become one, one undo step."""
        project = self._vm.project
        if project is None:
            return
        dialog = MergeJointsDialog(
            project, selected_nodes=set(self._shell.canvas().selection.nodes), parent=self._window
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        command = MergeJointsCommand(
            self._vm, tolerance=dialog.tolerance(), node_ids=dialog.scope_ids()
        )
        try:
            self._vm.apply_command(command)
        except Exception as exc:
            QMessageBox.critical(self._window, "Could not merge the joints", str(exc))
            return
        self._shell.canvas().selection.clear()
        report = command.report
        self._shell.log(
            f"Merge Joints: {report.merged_node_groups} group(s), {report.removed_nodes} "
            f"joint(s) removed, {report.removed_elements} repeated member(s) removed."
        )

    def divide_frames(self) -> None:
        """Edit → Divide Frames at Joints: split members at the joints inside them."""
        project = self._vm.project
        if project is None:
            return
        dialog = DivideFramesDialog(
            project,
            selected_elements=set(self._shell.canvas().selection.elements),
            parent=self._window,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        plan = dialog.plan()
        if plan.is_empty:
            return
        try:
            self._vm.apply_command(MeshCommand(self._vm, plan))
        except Exception as exc:
            QMessageBox.critical(self._window, "Could not divide the frames", str(exc))
            return
        self._shell.canvas().selection.set_selection(set(), {e.id for e in plan.new_elements})
        self._shell.log(f"Divide Frames at Joints: {plan.summary()}")

    def join_frames(self) -> None:
        """Edit → Join Frames: merge selected members that continue each other."""
        if self._vm.project is None:
            return
        command = JoinFramesCommand(self._vm, set(self._shell.canvas().selection.elements))
        if not self._dry_join_finds_something():
            return
        try:
            self._vm.apply_command(command)
        except Exception as exc:
            QMessageBox.critical(self._window, "Join Frames failed", str(exc))
            return
        report = command.report
        survivors = {e.id for e in self._vm.project.elements} & set(
            self._shell.canvas().selection.elements
        )
        self._shell.canvas().selection.set_selection(set(), survivors)
        self._shell.log(f"Join Frames: {report.summary()}")
        for node_id, reason in sorted(report.kept.items()):
            self._shell.log(f"  joint {node_id} kept: {reason}.")
        self._window.statusBar().showMessage(f"Join Frames: {report.summary()}", 6000)

    def _dry_join_finds_something(self) -> bool:
        """Try the join on a copy first: nothing to join is a message, not an undo step."""
        from opensees_studio.core.geometry.join import join_frames

        project = self._vm.project
        assert project is not None
        trial = join_frames(
            project.model_copy(deep=True), set(self._shell.canvas().selection.elements)
        )
        if trial.joined:
            return True
        reasons = sorted(set(trial.kept.values()))
        QMessageBox.information(
            self._window,
            "Join Frames",
            "Nothing to join: select two or more members that meet end to end in a "
            "straight line." + (f"\n\nKept because {'; '.join(reasons)}." if reasons else ""),
        )
        return False

    def mesh(self) -> None:
        """Edit → Mesh: subdivide members and shells, and join the mesh up.

        The plan comes from ``core.mesh`` (pure geometry, tested on its own) and
        is applied by one command, so a mesh is a single undo step.
        """
        project = self._vm.project
        if project is None:
            QMessageBox.information(self._window, "Mesh", "Open or create a project first.")
            return
        selected = set(self._shell.canvas().selection.elements)
        dialog = MeshDialog(
            project,
            selected_element_ids=selected,
            has_selection=bool(selected),
            parent=self._window,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        plan = dialog.plan()
        if plan.is_empty:
            return
        try:
            self._vm.apply_command(MeshCommand(self._vm, plan))
        except Exception as exc:
            QMessageBox.critical(self._window, "Could not mesh the model", str(exc))
            return
        self._shell.canvas().selection.clear()
        for node in plan.new_nodes:
            self._shell.canvas().selection.select_node(node.id, additive=True)
        self._shell.canvas().render()
        self._shell.log(f"Mesh: {plan.summary()}")

    def delete_selection(self) -> None:
        """Edit → Delete selection: the selected joints and elements, as one undo step."""
        if self._vm.project is None:
            return
        sel = self._shell.canvas().selection
        if sel.is_empty:
            return
        elements, nodes = set(sel.elements), set(sel.nodes)
        stack = self._vm.undo_stack
        # Frames and joints go in one undo step, so one Undo brings the whole
        # selection back (and the model lock asks once).
        stack.beginMacro(f"Delete {len(elements) + len(nodes)} object(s)")
        try:
            if elements:
                self._vm.apply_command(DeleteElementsCommand(self._vm, elements))
            if nodes:
                self._vm.apply_command(DeleteNodesCommand(self._vm, nodes))
        except Exception as exc:
            QMessageBox.critical(self._window, "Delete failed", str(exc))
        finally:
            stack.endMacro()
        sel.clear()

    def table_editing(self) -> None:
        """Edit → Interactive Table Editing: joints, elements and joint loads as tables."""
        project = self._vm.project
        if project is None:
            return
        dlg = ModelTablesDialog(project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.edited is None:
            return
        try:
            self._vm.apply_command(ApplyModelTablesCommand(self._vm, dlg.edited))
            self._shell.log(
                f"Tables applied: {len(project.nodes)} joint(s), "
                f"{len(project.elements)} element(s)."
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Interactive Table Editing failed", str(exc))
