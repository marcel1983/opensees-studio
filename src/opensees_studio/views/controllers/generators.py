"""Parametric generators: a whole structure from a wizard, as one undo step."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from PySide6.QtCore import QObject, QSettings
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from opensees_studio.commands.building import insert_building_plan, plan_problems
from opensees_studio.commands.generated import insert_generated
from opensees_studio.core import (
    SUPPORTED_NDF,
    UnitSystem,
    build_portal_frame,
    frame_grid,
    labels_for,
    make_default_section,
    make_default_truss_material,
)
from opensees_studio.core.building import (
    BUILDING_NDF,
    GROUPS,
    BuildingLoads,
    BuildingPlan,
    BuildingSpec,
    plan_building,
)
from opensees_studio.core.generated import GeneratedModel
from opensees_studio.core.materials.library import is_uniaxial
from opensees_studio.core.sections import ElasticSection
from opensees_studio.views.controllers.shell import Shell
from opensees_studio.views.dialogs import FrameWizard
from opensees_studio.views.dialogs.building_wizard import BuildingWizard
from opensees_studio.views.i18n import tr

#: File → New Model: the units chosen last, offered again.
NEW_MODEL_UNITS_KEY = "new_model/units"


class GeneratorsController(QObject):
    """A structure from a few numbers: the wizards of Define and File → New Model.

    Define → Create Portal Frame, Create Truss, Create Warehouse and Create
    Building; File → New Model (units and a template) and New 2D Frame, which
    start a project and then run one of them. The geometry and the plans come
    from ``core`` (``frames``, ``trusses``, ``warehouse``, ``building``,
    ``templates``) and go in as one undo step through ``commands.generated``;
    this only asks and reports. It keeps no state.

    ``confirm_discard`` is the unsaved-changes prompt (a new model replaces the
    open one), ``grid_wizard`` runs Define → Grid Wizard for the grid-only
    template, and ``front_view`` shows a 2D model face on.
    """

    def __init__(
        self,
        shell: Shell,
        *,
        confirm_discard: Callable[[str], bool],
        grid_wizard: Callable[[], None],
        front_view: Callable[[], None],
    ) -> None:
        super().__init__(shell.window)
        self._shell = shell
        self._vm = shell.vm
        self._window = shell.window
        self._confirm_discard = confirm_discard
        self._grid_wizard = grid_wizard
        self._front_view = front_view

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

        wizard = BuildingWizard(
            self._frame_sections(),
            units=project.meta.units,
            planner=plan_for,
            define_sections=self._define_sections,
            parent=self._window,
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

    def new_model(self) -> None:
        """File → New Model: units and a template, as SAP2000 starts a model."""
        from opensees_studio.views.dialogs.new_model import NewModelDialog

        stored = QSettings().value(NEW_MODEL_UNITS_KEY, UnitSystem.SI_M_N.value)
        try:
            units = UnitSystem(stored)
        except ValueError:
            units = UnitSystem.SI_M_N
        dlg = NewModelDialog(units, parent=self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if not self._confirm_discard("Creating a new model"):
            return
        units = dlg.units()
        QSettings().setValue(NEW_MODEL_UNITS_KEY, units.value)
        self.start_template(dlg.template(), units, dlg)

    def start_template(self, key: str, units: UnitSystem, dlg: Any) -> None:
        """Create the model a New Model template asks for, then its wizard or members."""
        from opensees_studio.core.templates import (
            TEMPLATE_NDF,
            TEMPLATES,
            build_beam,
            build_space_frame,
        )

        ndm, ndf = TEMPLATE_NDF[key]
        self._vm.new_project(ndm, ndf, dead_case=True, units=units, default_materials=True)
        self._shell.log(f"New model: {TEMPLATES[key]} ({units.value}).")
        if key == "grid":
            self._grid_wizard()
        elif key == "truss2d":
            self.create_truss()
        elif key == "frame2d":
            self.create_portal_frame(with_grid=True)
        elif key == "warehouse":
            self.create_warehouse()
        elif key == "building":
            self.create_building()
        elif key in ("beam", "frame3d"):
            project = self._vm.project
            assert project is not None
            try:
                section = make_default_section(project.next_section_id(), project)
                if key == "beam":
                    spans, span = dlg.beam_numbers()
                    model = build_beam(spans, span, section_id=section.id)
                else:
                    model = build_space_frame(
                        *dlg.frame_numbers(),
                        column_section_id=section.id,
                        beam_section_id=section.id,
                    )
                insert_generated(
                    self._vm,
                    GeneratedModel(
                        sections=[section],
                        nodes=model.nodes,
                        elements=model.elements,
                        grid=model.grid,
                        replace_grids=True,
                    ),
                    text=f"New model: {TEMPLATES[key]}",
                )
            except Exception as exc:
                QMessageBox.critical(self._window, "Cannot create the model", str(exc))
                return
            self._shell.log(f"{TEMPLATES[key]}: {model.summary()}")
            if key == "beam":
                self._front_view()
            self._shell.canvas().reframe()

    def new_2d_frame(self) -> None:
        """Planar frame model — (ndm=2, ndf=3): Ux, Uz, Ry per joint, then the wizard.

        Right choice when beam-columns are in the mix; for a pure truss use
        'New 2D Truss' so the solver doesn't face unrestrained rotational DOFs.

        An empty 2D frame project is just an empty canvas, and the only plane it
        can build in is the wizard's XZ (Z up), so the wizard opens here: it is what
        turns "new 2D frame" into a frame. Cancelling leaves the empty project,
        which is still the right start for drawing by hand.
        """
        if not self._confirm_discard("Creating a new 2D frame"):
            return
        self._vm.new_project(ndm=2, ndf=3, dead_case=True, default_materials=True)
        self._shell.log("New 2D frame project (ndm = 2, ndf = 3).")
        self.create_portal_frame(with_grid=True)

    def portal_frame(self) -> None:
        """Define → Create Portal Frame: a parametric 2D frame, one undo step.

        This builds a frame into whatever project is open and touches nothing
        else. ``File → New 2D Frame`` (:meth:`new_2d_frame`) asks for the matching
        grid as well, because there the wizard is the whole point of the menu
        entry rather than one of the ways to draw a member.
        """
        self.create_portal_frame(with_grid=False)

    def create_portal_frame(self, *, with_grid: bool) -> None:
        """Collect the wizard's answers and insert the frame (and, if asked, its grid).

        The geometry comes from ``core.frames``; this only collects it, resolves
        the two section choices (creating the canonical default one *inside* the
        macro when the project has none) and inserts the result.
        """
        project = self._vm.project
        if project is None:
            QMessageBox.information(self._window, "Portal frame", "Open or create a project first.")
            return
        if (project.ndm, project.ndf) not in SUPPORTED_NDF:
            QMessageBox.information(
                self._window,
                "Portal frame",
                "A plane frame needs a 2D frame model (ndm = 2, ndf = 3) or a 3D frame "
                f"model (ndm = 3, ndf = 6); this project is ndm = {project.ndm}, "
                f"ndf = {project.ndf}.",
            )
            return

        # The wizard builds ElasticBeamColumns directly; a nonprismatic template
        # is assigned afterwards, when it can subdivide the member and its loads.
        sections = [s for s in project.sections if isinstance(s, ElasticSection)]
        wizard = FrameWizard(
            sections,
            ndm=project.ndm,
            ndf=project.ndf,
            length_unit=labels_for(project.meta.units).length,
            parent=self._window,
        )
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        column_id, rafter_id = wizard.section_choice()

        try:
            new_sections = []
            if column_id is None or rafter_id is None:
                section = make_default_section(project.next_section_id(), project)
                new_sections.append(section)
                column_id = rafter_id = section.id
            spec = wizard.spec(column_section_id=column_id, rafter_section_id=rafter_id)
            frame = build_portal_frame(
                spec,
                ndm=project.ndm,
                ndf=project.ndf,
                first_node_id=project.next_node_id(),
                first_element_id=project.next_element_id(),
            )
            # The same undo step as the frame: one Ctrl+Z takes both back.
            grid = frame_grid(spec) if with_grid else None
            insert_generated(
                self._vm,
                GeneratedModel(
                    sections=new_sections, nodes=frame.nodes, elements=frame.elements, grid=grid
                ),
                text="Create portal frame",
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Cannot create the frame", str(exc))
            return

        # Leave the frame selected: the next thing most users do is copy it.
        self._shell.canvas().selection.clear()
        for node in frame.nodes:
            self._shell.canvas().selection.select_node(node.id, additive=True)
        self._shell.log(f"{frame.summary()} Left selected for Edit → Replicate.")
        if grid is not None:
            lines = (
                len(grid.grid.x_grid_lines)
                + len(grid.grid.y_grid_lines)
                + len(grid.grid.z_grid_lines)
            )
            self._shell.log(
                f"Grid '{grid.name}' created with {lines} line(s) from the same numbers."
            )
            if project.ndm == 2:
                # A 2D model has one plane, X-Z: show it face on.
                self._front_view()

    def create_truss(self) -> None:
        """Define → Create Truss: a parametric plane truss, one undo step.

        The geometry comes from ``core.trusses``; this collects it, resolves the
        material (creating the default truss steel *inside* the macro when the
        project has no uniaxial material) and inserts the result.
        """
        from opensees_studio.core import TRUSS_NDF, build_truss
        from opensees_studio.views.dialogs.truss_wizard import TrussWizard

        project = self._vm.project
        if project is None:
            QMessageBox.information(self._window, "Truss", "Open or create a project first.")
            return
        if (project.ndm, project.ndf) not in TRUSS_NDF:
            QMessageBox.information(
                self._window,
                "Truss",
                "A plane truss needs ndm = 2 (ndf 2 or 3) or ndm = 3 (ndf 3 or 6); "
                f"this project is ndm = {project.ndm}, ndf = {project.ndf}.",
            )
            return
        materials = [m for m in project.materials if is_uniaxial(m)]
        wizard = TrussWizard(
            materials,
            ndm=project.ndm,
            ndf=project.ndf,
            length_unit=labels_for(project.meta.units).length,
            parent=self._window,
        )
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        material_id = wizard.material_choice()

        try:
            new_materials = []
            if material_id is None:
                material = make_default_truss_material(project.next_material_id())
                new_materials.append(material)
                material_id = material.id
            truss = build_truss(
                wizard.spec(material_id=material_id),
                ndm=project.ndm,
                ndf=project.ndf,
                first_node_id=project.next_node_id(),
                first_element_id=project.next_element_id(),
            )
            insert_generated(
                self._vm,
                GeneratedModel(materials=new_materials, nodes=truss.nodes, elements=truss.elements),
                text="Create truss",
            )
        except Exception as exc:
            QMessageBox.critical(self._window, "Cannot create the truss", str(exc))
            return

        self._shell.canvas().selection.set_selection(
            {node.id for node in truss.nodes}, {element.id for element in truss.elements}
        )
        self._shell.log(f"{truss.summary()} Left selected.")

    def create_warehouse(self) -> None:
        """Define → Create Warehouse: a parametric 3D warehouse, one undo step.

        Everything comes from ``core.warehouse`` (the plan) and
        ``commands.warehouse`` (its insertion as one macro, checked before
        anything is pushed); this only asks and reports.
        """
        from opensees_studio.commands.warehouse import insert_warehouse_plan
        from opensees_studio.core.warehouse import GROUPS, WAREHOUSE_NDF, plan_warehouse
        from opensees_studio.views.dialogs.warehouse_wizard import WarehouseWizard

        project = self._vm.project
        if project is None:
            QMessageBox.information(self._window, "Warehouse", "Open or create a project first.")
            return
        if (project.ndm, project.ndf) != WAREHOUSE_NDF:
            QMessageBox.information(
                self._window,
                "Warehouse",
                tr(
                    "A warehouse needs a 3D frame model (ndm = 3, ndf = 6); this project "
                    "is ndm = {ndm}, ndf = {ndf}."
                ).format(ndm=project.ndm, ndf=project.ndf),
            )
            return
        wizard = WarehouseWizard(
            self._frame_sections(),
            units=project.meta.units,
            define_sections=self._define_sections,
            parent=self._window,
        )
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            plan = plan_warehouse(
                project,
                wizard.spec(),
                sections=wizard.section_choice(),
                loads=wizard.loads(),
                group_names={key: tr(name) for key, name in GROUPS.items()},
            )
            insert_warehouse_plan(self._vm, plan)
        except Exception as exc:
            QMessageBox.critical(self._window, "Cannot create the warehouse", str(exc))
            return
        self._shell.log(plan.warehouse.summary())
        if plan.sections:
            self._shell.log("Sections created: " + ", ".join(s.name for s in plan.sections) + ".")
        if plan.combinations:
            self._shell.log(f"{len(plan.combinations)} load combination(s) generated.")
        for note in plan.notes:
            self._shell.log(note)
        self._shell.canvas().reframe()

    def _frame_sections(self) -> list[Any]:
        """The sections a wizard offers for its members: the project's elastic ones."""
        project = self._vm.project
        return [s for s in project.sections if isinstance(s, ElasticSection)] if project else []

    def _define_sections(self, parent: QWidget) -> list[Any]:
        """A wizard's Section Library…: Define → Section Library over it, each addition undoable."""
        from opensees_studio.views.dialogs import SectionLibraryDialog

        SectionLibraryDialog(self._vm, parent).exec()
        return self._frame_sections()


__all__ = ["NEW_MODEL_UNITS_KEY", "GeneratorsController"]
