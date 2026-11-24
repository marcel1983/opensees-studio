"""Parametric generators: a whole structure from a wizard, as one undo step."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from opensees_studio.commands.building import insert_building_plan, plan_problems
from opensees_studio.core.building import (
    BUILDING_NDF,
    GROUPS,
    BuildingLoads,
    BuildingPlan,
    BuildingSpec,
    plan_building,
)
from opensees_studio.core.sections import ElasticSection
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs.building_wizard import BuildingWizard
from opensees_studio.views.i18n import tr


class GeneratorsController(QObject):
    """Define → Create Building: the wizard, the plan and its insertion.

    Everything comes from ``core.building`` (the plan) and ``commands.building``
    (its insertion as one macro, checked before anything is pushed); this only
    asks and reports. It keeps no state.
    """

    def __init__(self, shell: Shell) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window

    def create_building(self) -> None:
        """A multi-storey frame building into the open 3D model, one undo step."""
        project = self._vm.project
        if project is None:
            QMessageBox.information(self._window, "Building", "Open or create a project first.")
            return
        if (project.ndm, project.ndf) != BUILDING_NDF:
            QMessageBox.information(
                self._window,
                "Building",
                tr(
                    "A building needs a 3D frame model (ndm = 3, ndf = 6); this project "
                    "is ndm = {ndm}, ndf = {ndf}."
                ).format(ndm=project.ndm, ndf=project.ndf),
            )
            return
        group_names = {key: tr(name) for key, name in GROUPS.items()}

        def plan_for(
            spec: BuildingSpec, sections: Mapping[str, int | None], loads: BuildingLoads
        ) -> BuildingPlan:
            plan = plan_building(
                project, spec, sections=sections, loads=loads, group_names=group_names
            )
            problems = plan_problems(project, plan)
            if problems:
                raise ValueError(" ".join(problems))
            return plan

        sections = [s for s in project.sections if isinstance(s, ElasticSection)]
        wizard = BuildingWizard(
            sections, units=project.meta.units, planner=plan_for, parent=self._window
        )
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            plan = plan_for(wizard.spec(), wizard.section_choice(), wizard.loads())
            insert_building_plan(self._vm, plan)
        except Exception as exc:
            QMessageBox.critical(self._window, "Cannot create the building", str(exc))
            return
        log = self._shell.log
        log(plan.building.summary())
        if plan.sections:
            log("Sections created: " + ", ".join(s.name for s in plan.sections) + ".")
        if plan.storeys:
            log(f"{len(plan.storeys)} storey(s) and {len(plan.diaphragms)} rigid diaphragm(s).")
        if plan.combinations:
            log(f"{len(plan.combinations)} load combination(s) generated.")
        for note in plan.notes:
            log(note)
        self._shell.canvas().reframe()


__all__ = ["GeneratorsController"]
