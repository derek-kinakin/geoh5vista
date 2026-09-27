"""Tests for the curve module."""

import numpy as np
import pytest
import pyvista
from pathlib import Path
from geoh5py.workspace.workspace import Workspace
from geoh5py.objects.curve import Curve

from geoh5vista.curve import (
    curve_geom_to_vtk,
    curve_to_vtk,
    vtk_geom_to_curve,
)

# ---------------------------------------------------------------------------
# Known geometry shared across all tests
# ---------------------------------------------------------------------------
VERTICES = np.array(
    [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 1.0, 0.0], [3.0, 1.0, 0.0]],
    dtype=float,
)
CELLS = np.array([[0, 1], [1, 2], [2, 3]], dtype=int)
FLOAT_VALUES = np.array([0.1, 0.2, 0.3, 0.4], dtype=float)
INT_VALUES = np.array([10, 20, 30, 40], dtype=int)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def geoh5_curve(tmp_path: Path):
    """Create and open a test Curve in a temporary .geoh5 workspace."""
    path = tmp_path / "test_curve.geoh5"
    with Workspace.create(path) as ws:
        crv = Curve.create(
            workspace=ws, name="test_curve", vertices=VERTICES, cells=CELLS
        )
        crv.add_data({
            "elevation": {"type": "float", "association": "VERTEX", "values": FLOAT_VALUES},
            "zone": {"type": "integer", "association": "VERTEX", "values": INT_VALUES},
        })
    # Re-open read-only; yield keeps the workspace alive for the duration of the test
    with Workspace(path) as ws:
        yield ws.get_entity("test_curve")[0]


@pytest.fixture
def vtk_curve() -> pyvista.PolyData:
    """Create a PyVista PolyData with the same known geometry."""
    lines = np.c_[np.full(len(CELLS), 2, dtype=int), CELLS].ravel()
    mesh = pyvista.PolyData()
    mesh.points = VERTICES
    mesh.lines = lines
    mesh["elevation"] = FLOAT_VALUES
    mesh["zone"] = INT_VALUES
    return mesh


# ---------------------------------------------------------------------------
# curve_geom_to_vtk — geometry conversion (read direction)
# ---------------------------------------------------------------------------

def test_curve_geom_to_vtk_point_count(geoh5_curve: Curve):
    result = curve_geom_to_vtk(geoh5_curve)
    assert result.n_points == len(VERTICES)


def test_curve_geom_to_vtk_cell_count(geoh5_curve: Curve):
    result = curve_geom_to_vtk(geoh5_curve)
    assert result.n_cells == len(CELLS)


def test_curve_geom_to_vtk_vertices(geoh5_curve: Curve):
    result = curve_geom_to_vtk(geoh5_curve)
    np.testing.assert_allclose(result.points, VERTICES)


def test_curve_geom_to_vtk_adds_line_index_array(geoh5_curve: Curve):
    # curve_geom_to_vtk derives a "Line Index" from connectivity() —
    # assert the array exists and has one value per cell
    result = curve_geom_to_vtk(geoh5_curve)
    assert "Line Index" in result.array_names
    assert len(result["Line Index"]) == len(CELLS)


# ---------------------------------------------------------------------------
# curve_to_vtk — data and metadata transfer (read direction)
# ---------------------------------------------------------------------------

def test_curve_to_vtk_transfers_float_data(geoh5_curve: Curve):
    result = curve_to_vtk(geoh5_curve)
    assert "elevation" in result.array_names
    np.testing.assert_allclose(result["elevation"], FLOAT_VALUES)


def test_curve_to_vtk_transfers_int_data(geoh5_curve: Curve):
    result = curve_to_vtk(geoh5_curve)
    assert "zone" in result.array_names
    np.testing.assert_array_equal(result["zone"], INT_VALUES)


def test_curve_to_vtk_metadata_name(geoh5_curve: Curve):
    result = curve_to_vtk(geoh5_curve)
    assert result.user_dict["gh5_name"] == "test_curve"


def test_curve_to_vtk_metadata_entity_type(geoh5_curve: Curve):
    result = curve_to_vtk(geoh5_curve)
    assert result.user_dict["gh5_entity_type"] == "Curve"


def test_curve_to_vtk_no_data_does_not_raise(tmp_path: Path):
    """A curve with no data arrays should convert without error."""
    path = tmp_path / "empty.geoh5"
    with Workspace.create(path) as ws:
        crv = Curve.create(
            workspace=ws, name="bare", vertices=VERTICES, cells=CELLS
        )
    with Workspace(path) as ws:
        crv = ws.get_entity("bare")[0]
        result = curve_to_vtk(crv)
    assert result.n_points == len(VERTICES)


# ---------------------------------------------------------------------------
# vtk_geom_to_curve — geometry write (VTK → geoh5 direction)
# ---------------------------------------------------------------------------

def test_vtk_geom_to_curve_vertices(vtk_curve: pyvista.PolyData, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_curve(vtk_curve, ws, "out_curve")
        np.testing.assert_allclose(result.vertices, VERTICES)


def test_vtk_geom_to_curve_cells(vtk_curve: pyvista.PolyData, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_curve(vtk_curve, ws, "out_curve")
        np.testing.assert_array_equal(result.cells, CELLS)


# ---------------------------------------------------------------------------
# Round-trip — write and read back end-to-end
# ---------------------------------------------------------------------------

def test_round_trip_geometry(tmp_path: Path):
    """geoh5 → VTK → geoh5 → assert vertices and cells are preserved."""
    src = tmp_path / "source.geoh5"
    dst = tmp_path / "dest.geoh5"

    with Workspace.create(src) as ws:
        Curve.create(workspace=ws, name="crv", vertices=VERTICES, cells=CELLS)

    with Workspace(src) as ws:
        crv = ws.get_entity("crv")[0]
        vtk = curve_geom_to_vtk(crv)

    with Workspace.create(dst) as ws:
        result = vtk_geom_to_curve(vtk, ws, "crv_rt")
        np.testing.assert_allclose(result.vertices, VERTICES)
        np.testing.assert_array_equal(result.cells, CELLS)
