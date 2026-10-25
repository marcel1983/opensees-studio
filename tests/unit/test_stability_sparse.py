"""Sparse stability diagnosis on synthetic symmetric matrices."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")

import scipy.sparse as sp

from opensees_studio.services.stability import _diagnose_sparse


def _equation_map(n: int) -> dict[int, tuple[int, str]]:
    return {i: (i + 1, "Ux") for i in range(n)}


def test_sparse_route_finds_a_mechanism_without_going_dense() -> None:
    n = 1_300
    diagonal = np.ones(n)
    diagonal[-1] = 0.0
    matrix = sp.diags(diagonal, format="csr")
    result = _diagnose_sparse(matrix, _equation_map(n), warnings=[])

    assert result["n_equations"] == n
    assert result["classification"] == "mechanism"
    assert result["n_mechanisms"] == 1
    assert result["rank"] == n - 1
    assert result["completion"] == "complete"
    assert result["count_kind"] == "estimate"
    assert result["mechanisms"][0].eigenvalue == pytest.approx(0.0, abs=1e-10)


def test_sparse_route_finds_negative_stiffness() -> None:
    diagonal = np.ones(1_300)
    diagonal[0] = -1.0
    result = _diagnose_sparse(sp.diags(diagonal, format="csr"), _equation_map(1_300), warnings=[])

    assert result["classification"] == "negative_stiffness"
    assert result["n_mechanisms"] == 0
    assert result["rank"] == 1_300


def test_sparse_route_reports_a_stable_matrix() -> None:
    diagonal = np.linspace(1.0, 2.0, 1_300)
    result = _diagnose_sparse(sp.diags(diagonal, format="csr"), _equation_map(1_300), warnings=[])

    assert result["classification"] == "no_mechanisms"
    assert result["n_mechanisms"] == 0
    assert result["rank"] == 1_300
    assert result["completion"] == "complete"


def test_sparse_route_reports_a_lower_bound_when_the_search_is_saturated() -> None:
    n = 1_300
    diagonal = np.ones(n)
    diagonal[:10] = 0.0
    result = _diagnose_sparse(sp.diags(diagonal, format="csr"), _equation_map(n), warnings=[])

    assert result["classification"] == "mechanism"
    assert result["n_mechanisms"] == 8
    assert result["count_kind"] == "lower_bound"
    assert result["completion"] == "partial"
    assert result["rank"] is None


def test_sparse_route_rejects_a_non_symmetric_matrix() -> None:
    matrix = sp.csr_matrix(np.array([[2.0, 1.0], [0.0, 2.0]]))
    result = _diagnose_sparse(matrix, _equation_map(2), warnings=[])

    assert result["completion"] == "unsupported"
    assert result["classification"] == "indeterminate"
    assert "not symmetric" in result["warnings"][-1]
