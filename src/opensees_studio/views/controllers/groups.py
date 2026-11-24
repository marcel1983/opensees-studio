"""Define → Groups and Section Cuts; Assign → Assign to Group."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands.groups import (
    EditGroupMembersCommand,
    SetGroupsCommand,
    SetSectionCutsCommand,
)
from opensees_studio.core.groups import Group, colour_for
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs.groups import (
    NEW_GROUP,
    AssignGroupDialog,
    GroupsDialog,
    SectionCutsDialog,
)


class GroupsController(QObject):
    """Named sets of joints and elements, and what is read through them.

    Define → Groups edits the list, Assign → Assign to Group puts the selection
    in one (creating it in the same undo step when asked), and Define → Section
    Cuts sets the cuts whose resultants a static case reports through a group.
    It keeps no state.
    """

    def __init__(self, shell: Shell) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window

    def define_groups(self) -> None:
        """Define → Groups: add, rename, recolour or remove groups."""
        project = self._vm.project
        if project is None:
            return
        dlg = GroupsDialog(project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(SetGroupsCommand(self._vm, dlg.groups()))
            self._shell.log(f"Groups set: {len(project.groups)}.")
        except Exception as exc:
            QMessageBox.critical(self._window, "Define Groups failed", str(exc))

    def define_section_cuts(self) -> None:
        """Define → Section Cuts: resultant forces through a group."""
        project = self._vm.project
        if project is None:
            return
        dlg = SectionCutsDialog(project, self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(SetSectionCutsCommand(self._vm, dlg.section_cuts()))
            self._shell.log(f"Section cuts set: {len(project.section_cuts)}. Re-run static cases.")
        except Exception as exc:
            QMessageBox.critical(self._window, "Define Section Cuts failed", str(exc))

    def assign_group(self) -> None:
        """Assign → Assign to Group: add the selection to a group, remove it, or replace."""
        project = self._vm.project
        if project is None:
            return
        sel = self._shell.canvas().selection
        nodes, elements = sorted(sel.nodes), sorted(sel.elements)
        if not nodes and not elements:
            QMessageBox.information(
                self._window, "Assign to Group", "Select joints or elements first."
            )
            return
        dlg = AssignGroupDialog(project, len(nodes), len(elements), self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        group_id, mode = dlg.group_id, dlg.mode
        try:
            self._vm.undo_stack.beginMacro("Assign to group")
            try:
                if group_id == NEW_GROUP:
                    group_id = project.next_group_id()
                    group = Group(
                        id=group_id,
                        name=dlg.new_name.text().strip(),
                        colour=colour_for(len(project.groups)),
                    )
                    self._vm.apply_command(SetGroupsCommand(self._vm, [*project.groups, group]))
                self._vm.apply_command(
                    EditGroupMembersCommand(self._vm, group_id, nodes, elements, mode=mode)
                )
            finally:
                self._vm.undo_stack.endMacro()
            group = next(g for g in project.groups if g.id == group_id)
            self._shell.log(
                f"Group {group.name}: {len(group.node_ids)} joint(s), "
                f"{len(group.element_ids)} element(s)."
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Assign to Group failed", str(exc))
