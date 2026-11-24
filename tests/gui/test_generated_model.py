"""A generated model goes into the project whole, as one undo step, or not at all."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from opensees_studio.commands import AddNodesCommand
from opensees_studio.commands.generated import insert_generated, model_problems
from opensees_studio.core import ElasticUniaxial, Node, Project, TrussElement
from opensees_studio.core.generated import GeneratedModel
from opensees_studio.core.geometry.grid import CoordinateGridSystem
from opensees_studio.core.groups import Group
from opensees_studio.viewmodels import ProjectViewModel


def _vm() -> ProjectViewModel:
    vm = ProjectViewModel()
    vm.new_project()
    return vm


def _bar(first: int = 1, *, material_id: int = 1) -> GeneratedModel:
    """Two joints and the truss bar between them, with its own material."""
    return GeneratedModel(
        materials=[ElasticUniaxial(id=material_id, name="S", E=200e9)],
        nodes=[Node(id=first, coords=(0, 0, 0)), Node(id=first + 1, coords=(1, 0, 0))],
        elements=[
            TrussElement(id=first, nodes=(first, first + 1), area=0.01, material_id=material_id)
        ],
        groups=[Group(id=1, name="Bar", node_ids=[first, first + 1], element_ids=[first])],
        grid=CoordinateGridSystem(name="Bar grid"),
    )


def test_a_model_goes_in_as_one_undo_step() -> None:
    vm = _vm()
    project = vm.project
    assert project is not None
    systems = len(project.coord_systems)
    before = project.model_dump()

    insert_generated(vm, _bar(), text="Create bar")

    assert vm.undo_stack.count() == 1
    assert vm.undo_stack.undoText() == "Create bar"
    assert [n.id for n in project.nodes] == [1, 2]
    assert [e.id for e in project.elements] == [1]
    assert [m.name for m in project.materials] == ["S"]
    assert [g.name for g in project.groups] == ["Bar"]
    assert [c.name for c in project.coord_systems][systems:] == ["Bar grid"]

    vm.undo_stack.undo()
    assert project.model_dump() == before
    vm.undo_stack.redo()
    assert [n.id for n in project.nodes] == [1, 2]


def test_replace_grids_leaves_only_the_generated_grid() -> None:
    vm = _vm()
    project = vm.project
    assert project is not None
    project.coord_systems.append(CoordinateGridSystem(name="Old grid"))
    model = _bar()
    model.replace_grids = True
    insert_generated(vm, model, text="New model")
    # The project itself always keeps a Global system; the old one is gone.
    names = [c.name for c in project.coord_systems]
    assert "Bar grid" in names and "Old grid" not in names

    # Without it the grid is added to the ones there, and a taken name is refused.
    again = GeneratedModel(grid=CoordinateGridSystem(name="Bar grid"))
    assert model_problems(project, again) == [
        "A coordinate system named 'Bar grid' already exists."
    ]
    again.replace_grids = True
    assert model_problems(project, again) == []


def test_a_model_that_does_not_fit_is_refused_before_anything_is_pushed() -> None:
    vm = _vm()
    project = vm.project
    assert project is not None
    insert_generated(vm, _bar(), text="Create bar")
    before = project.model_dump()

    # The same model again: every id and the grid name are taken.
    problems = model_problems(project, _bar())
    for word in ("Material id", "Node id", "Element id", "Group id", "Bar grid"):
        assert any(word in p for p in problems), word
    with pytest.raises(ValueError, match="already in use"):
        insert_generated(vm, _bar(), text="Again")
    assert project.model_dump() == before
    assert vm.undo_stack.count() == 1


def test_a_reference_to_something_that_is_not_there_is_a_problem() -> None:
    project = Project()
    model = GeneratedModel(
        nodes=[Node(id=1, coords=(0, 0, 0))],
        elements=[TrussElement(id=1, nodes=(1, 7), area=0.01, material_id=3)],
    )
    problems = model_problems(project, model)
    assert "Missing material(s): [3]." in problems
    assert "Missing node(s): [7]." in problems
    # What the project already has counts.
    project.materials.append(ElasticUniaxial(id=3, name="S", E=200e9))
    project.nodes.append(Node(id=7, coords=(1, 0, 0)))
    assert model_problems(project, model) == []


def test_a_command_that_refuses_half_way_takes_the_whole_macro_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vm = _vm()
    project = vm.project
    assert project is not None
    vm.apply_command(AddNodesCommand(vm, [Node(id=50, coords=(5, 0, 0))]))
    before = project.model_dump()

    def refuse(self: object) -> None:
        raise ValueError("no elements today")

    # The check runs before the push, after the materials and the nodes went in.
    monkeypatch.setattr(
        "opensees_studio.commands.elements.AddElementsCommand.check", refuse, raising=False
    )
    with pytest.raises(ValueError, match="no elements today"):
        insert_generated(vm, _bar(), text="Create bar")

    assert project.model_dump() == before
    # The half macro is gone from the stack: nothing to redo, the earlier step intact.
    assert (vm.undo_stack.count(), vm.undo_stack.index()) == (1, 1)
    assert not vm.undo_stack.canRedo()
    vm.undo_stack.undo()
    assert project.nodes == []


def test_apply_writes_the_same_model_without_an_undo_stack() -> None:
    project = Project()
    systems = len(project.coord_systems)
    _bar().apply(project)
    assert [n.id for n in project.nodes] == [1, 2]
    assert [m.id for m in project.materials] == [1]
    assert len(project.coord_systems) == systems + 1
    project.validate_references()
