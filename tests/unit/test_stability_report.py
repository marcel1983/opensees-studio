"""The stability report: what the dialog and the log say, and the CLI round trip."""

from __future__ import annotations

from opensees_studio.services.stability import Mechanism, Mover, StabilityReport


def _report() -> StabilityReport:
    return StabilityReport(
        n_equations=5,
        rank=4,
        mechanisms=[
            Mechanism(
                movers=[Mover(node=4, dof="Ux", amplitude=1.0), Mover(3, "Ux", 1.0)],
                singular_value=0.0,
            )
        ],
        n_mechanisms=1,
        condition=12.5,
    )


def test_a_full_rank_model_is_stable() -> None:
    report = StabilityReport(n_equations=6, rank=6)
    assert report.stable
    assert "statically stable" in report.summary()
    assert report.nodes == []


def test_a_mechanism_names_its_joints_and_dofs() -> None:
    report = _report()
    assert not report.stable
    summary = report.summary()
    assert "1 mechanism(s)" in summary and "rank 4" in summary
    assert "N4 Ux (+1.00), N3 Ux (+1.00)" in summary
    assert report.nodes == [4, 3]


def test_an_unstiffened_dof_alone_makes_the_model_unstable() -> None:
    report = StabilityReport(n_equations=3, rank=3, uncovered=["Node 2, DOF Ry: no element"])
    assert not report.stable
    assert "Node 2, DOF Ry" in report.summary()


def test_more_mechanisms_than_listed_are_counted() -> None:
    report = _report()
    report.n_mechanisms = 9
    assert "… and 8 more." in report.summary()


def test_the_report_survives_the_cli_json() -> None:
    report = _report()
    assert StabilityReport.from_dict(report.to_dict()) == report
