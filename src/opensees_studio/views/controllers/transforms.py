"""Edit → Copy, Paste, Move, Replicate, Mirror and Extrude."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands import MirrorCommand, MoveNodesCommand, ReplicateCommand
from opensees_studio.core import selection as selection_queries
from opensees_studio.core.units import labels_for
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs.mirror import MirrorDialog
from opensees_studio.views.dialogs.move import MoveDialog
from opensees_studio.views.dialogs.replicate import ReplicateDialog


class TransformsController(QObject):
    """Moves and copies the selection; owns the clipboard and the open offset window.

    ``arm_measure`` switches the viewport to Measure Distance (the Move and
    Replicate windows have a button for it) and ``release_measure`` gives the
    tool back when that window closes; both belong to the window's tool bar.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        arm_measure: Callable[[], None],
        release_measure: Callable[[], None],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._arm_measure = arm_measure
        self._release_measure = release_measure
        #: Edit → Copy: (id of the project, joints, elements).
        self._clipboard: tuple[int, frozenset[int], frozenset[int]] | None = None
        #: Offset of the last paste, offered again by the next one.
        self.paste_offset: tuple[float, float, float] = (0.0, 0.0, 3.0)
        #: Open Move/Replicate window: modeless, so Measure can fill its offset.
        self.offset_dialog: MoveDialog | ReplicateDialog | None = None

    # ── the selection these commands act on ──────────────────────────
    def selection_nodes(self) -> set[int]:
        """Selected nodes, plus the joints of every selected element.

        A frame is defined by its joints, so selecting members and asking to
        move, copy or mirror them means acting on those joints: the user does
        not have to pick the nodes first. A joint shared with a member that is
        not selected still moves, which is how a joint edit behaves in a frame
        program — the connected member follows its joint.
        """
        selection = self._shell.canvas().selection
        project = self._vm.project
        if project is None:
            return set(selection.nodes)
        return selection_queries.implied_node_ids(project, selection.nodes, selection.elements)

    # ── copy and paste ───────────────────────────────────────────────
    def copy(self) -> None:
        """Edit → Copy: remember the selection (joints and the members between them)."""
        project = self._vm.project
        nodes = self.selection_nodes()
        if project is None or not nodes:
            return
        elements = set(self._shell.canvas().selection.elements) or {
            el.id for el in project.elements if all(nid in nodes for nid in el.nodes)
        }
        self._clipboard = (id(project), frozenset(nodes), frozenset(elements))
        self._shell.refresh_actions()
        self._window.statusBar().showMessage(
            f"Copied {len(nodes)} node(s) and {len(elements)} element(s): Edit → Paste "
            "places them at an offset.",
            5000,
        )

    def clipboard_contents(self) -> tuple[set[int], set[int]]:
        """The copied joints and elements that still exist in this project."""
        project = self._vm.project
        if project is None or self._clipboard is None or self._clipboard[0] != id(project):
            return set(), set()
        node_ids = {n.id for n in project.nodes} & self._clipboard[1]
        element_ids = {e.id for e in project.elements} & self._clipboard[2]
        return node_ids, element_ids

    def paste(self) -> None:
        """Edit → Paste: a copy of the copied objects at an offset, then selected."""
        from opensees_studio.views.dialogs.replicate import PasteDialog

        project = self._vm.project
        nodes, elements = self.clipboard_contents()
        if project is None or not nodes:
            return
        dialog = PasteDialog(
            len(nodes),
            len(elements),
            self.paste_offset,
            self._window,
            length_unit=labels_for(project.meta.units).length,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        before_nodes = {n.id for n in project.nodes}
        before_elements = {e.id for e in project.elements}
        try:
            self._vm.apply_command(ReplicateCommand(self._vm, nodes, elements, dialog.offset(), 1))
        except Exception as exc:
            QMessageBox.critical(self._window, "Paste failed", str(exc))
            return
        self.paste_offset = dialog.offset()
        # The pasted copy becomes the selection, ready to move or paste again.
        self._shell.canvas().selection.set_selection(
            {n.id for n in project.nodes} - before_nodes,
            {e.id for e in project.elements} - before_elements,
        )

    # ── move and replicate (one modeless window at a time) ───────────
    def move(self) -> None:
        project = self._vm.project
        sel_nodes = set(self.selection_nodes())
        if project is None or not sel_nodes:
            QMessageBox.information(self._window, "Move", "Select nodes or frame elements first.")
            return
        if self._raise_open_offset_dialog():
            return
        dlg = MoveDialog(
            len(sel_nodes), self._window, length_unit=labels_for(project.meta.units).length
        )
        dlg.measureRequested.connect(lambda d=dlg: self._measure_for_offset_dialog(d))
        dlg.accepted.connect(lambda d=dlg: self._apply_move(d, sel_nodes))
        self._show_offset_dialog(dlg)

    def _apply_move(self, dlg: MoveDialog, sel_nodes: set[int]) -> None:
        try:
            self._vm.apply_command(MoveNodesCommand(self._vm, sel_nodes, dlg.offset()))
        except Exception as exc:
            QMessageBox.critical(self._window, "Move failed", str(exc))

    def replicate(self) -> None:
        project = self._vm.project
        sel_nodes = set(self.selection_nodes())
        sel_elements = set(self._shell.canvas().selection.elements)
        if project is None or not sel_nodes:
            QMessageBox.information(
                self._window, "Replicate", "Select nodes or frame elements first."
            )
            return
        # Forgiving: if the user selected only nodes, include any element whose
        # endpoints are all in the node selection.
        if not sel_elements:
            sel_elements = {
                el.id for el in project.elements if all(nid in sel_nodes for nid in el.nodes)
            }
        if self._raise_open_offset_dialog():
            return
        dlg = ReplicateDialog(
            len(sel_nodes),
            len(sel_elements),
            self._window,
            length_unit=labels_for(project.meta.units).length,
        )
        dlg.measureRequested.connect(lambda d=dlg: self._measure_for_offset_dialog(d))
        dlg.accepted.connect(lambda d=dlg: self._apply_replicate(d, sel_nodes, sel_elements))
        self._show_offset_dialog(dlg)

    def _apply_replicate(
        self, dlg: ReplicateDialog, sel_nodes: set[int], sel_elements: set[int]
    ) -> None:
        try:
            self._vm.apply_command(
                ReplicateCommand(self._vm, sel_nodes, sel_elements, dlg.offset(), dlg.n_copies())
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Replicate failed", str(exc))

    def _show_offset_dialog(self, dialog: MoveDialog | ReplicateDialog) -> None:
        """Show Move/Replicate modeless so the viewport, and Measure, stay usable."""
        dialog.setModal(False)
        dialog.finished.connect(lambda _code, d=dialog: self._on_offset_dialog_closed(d))
        self.offset_dialog = dialog
        dialog.show()

    def _raise_open_offset_dialog(self) -> bool:
        """Bring the open Move/Replicate window forward; one at a time."""
        dialog = self.offset_dialog
        if dialog is None or not dialog.isVisible():
            return False
        dialog.raise_()
        dialog.activateWindow()
        return True

    def _measure_for_offset_dialog(self, dialog: MoveDialog | ReplicateDialog) -> None:
        """Arm Measure Distance to fill ``dialog`` with the next two-joint vector."""
        if not dialog.isVisible():
            return
        self._arm_measure()

    def _on_offset_dialog_closed(self, dialog: MoveDialog | ReplicateDialog) -> None:
        if self.offset_dialog is dialog:
            self.offset_dialog = None
        # Measure no longer has a target, and the tool goes back to Select so a
        # stray click after the window closed does not pick points for nothing.
        self._release_measure()
        dialog.deleteLater()

    # ── extrude and mirror ───────────────────────────────────────────
    def extrude(self) -> None:
        """Edit → Extrude: selected frames into shells, or selected joints into frames."""
        from opensees_studio.commands import ExtrudeCommand
        from opensees_studio.commands.extrude import section_choices
        from opensees_studio.core import FRAME_ELEMENT_CLASSES
        from opensees_studio.views.dialogs.extrude import ExtrudeDialog

        project = self._vm.project
        if project is None:
            return
        selection = self._shell.canvas().selection
        frames = {
            el.id
            for el in project.elements
            if el.id in selection.elements and isinstance(el, FRAME_ELEMENT_CLASSES)
        }
        into_shells = bool(frames)
        nodes = set(selection.nodes)
        sections = section_choices(project, shells=into_shells)
        if not into_shells and not nodes:
            QMessageBox.information(
                self._window,
                "Extrude",
                "Select joints (into frames) or frame members (into shells).",
            )
            return
        if not sections:
            QMessageBox.information(
                self._window,
                "Extrude",
                "Extruding frames into shells needs a plate section"
                if into_shells
                else "Extruding joints into frames needs a frame section",
            )
            return
        dialog = ExtrudeDialog(
            into_shells=into_shells,
            n_objects=len(frames) if into_shells else len(nodes),
            sections=sections,
            parent=self._window,
            length_unit=labels_for(project.meta.units).length,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        command = ExtrudeCommand(
            self._vm,
            nodes,
            frames,
            dialog.offset(),
            dialog.count(),
            dialog.section_id(),
        )
        try:
            self._vm.apply_command(command)
        except Exception as exc:
            QMessageBox.critical(self._window, "Extrude failed", str(exc))
            return
        self._shell.canvas().selection.set_selection(set(), set(command.added_elements))
        self._shell.log(
            f"Extruded into {len(command.added_elements)} "
            f"{'shell' if into_shells else 'frame'}(s), {len(command.added_nodes)} new joint(s)."
        )

    def mirror(self) -> None:
        sel_nodes = self.selection_nodes()
        sel_elements = set(self._shell.canvas().selection.elements)
        if not sel_nodes:
            QMessageBox.information(self._window, "Mirror", "Select nodes or frame elements first.")
            return
        if not sel_elements and self._vm.project is not None:
            sel_elements = {
                el.id
                for el in self._vm.project.elements
                if all(nid in sel_nodes for nid in el.nodes)
            }
        dlg = MirrorDialog(len(sel_nodes), len(sel_elements), self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._vm.apply_command(
                MirrorCommand(self._vm, sel_nodes, sel_elements, dlg.plane())  # type: ignore[arg-type]
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Mirror failed", str(exc))
