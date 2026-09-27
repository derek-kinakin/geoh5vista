"""Tests for the points module."""

import numpy as np
import pytest
import pyvista
from pathlib import Path
from geoh5py.workspace import Workspace
from geoh5py.objects.points import Points

from geoh5vista.points import (
    points_geom_to_vtk,
    points_to_vtk,
    vtk_geom_to_points,
)

# ---------------------------------------------------------------------------
# Known geometry shared across all tests
# ---------------------------------------------------------------------------
VERTICES = np.array(
    [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],
    dtype=float,
)
FLOAT_VALUES = np.array([1.1, 2.2, 3.3, 4.4], dtype=float)
INT_VALUES = np.array([10, 20, 30, 40], dtype=int)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def geoh5_points(tmp_path: Path):
    """Create and open a test Points object in a temporary .geoh5 workspace."""
    path = tmp_path / "test_points.geoh5"
    with Workspace.create(path) as ws:
        pts = Points.create(workspace=ws, name="test_points", vertices=VERTICES)
        pts.add_data({
            "elevation": {"type": "float", "association": "VERTEX", "values": FLOAT_VALUES},
            "zone": {"type": "integer", "association": "VERTEX", "values": INT_VALUES},
        })
    with Workspace(path) as ws:
        yield ws.get_entity("test_points")[0]


@pytest.fixture
def vtk_points() -> pyvista.PointSet:
    """Create a PyVista PointSet with the same known geometry."""
    mesh = pyvista.PointSet(VERTICES)
    mesh["elevation"] = FLOAT_VALUES
    return mesh


# ---------------------------------------------------------------------------
# points_geom_to_vtk — geometry conversion (read direction)
# ---------------------------------------------------------------------------

def test_points_geom_to_vtk_point_count(geoh5_points: Points):
    result = points_geom_to_vtk(geoh5_points)
    assert result.n_points == len(VERTICES)


def test_points_geom_to_vtk_positions(geoh5_points: Points):
    result = points_geom_to_vtk(geoh5_points)
    np.testing.assert_allclose(result.points, VERTICES)


def test_points_geom_to_vtk_returns_pointset(geoh5_points: Points):
    result = points_geom_to_vtk(geoh5_points)
    assert isinstance(result, pyvista.PointSet)


# ---------------------------------------------------------------------------
# points_to_vtk — data and metadata transfer (read direction)
# ---------------------------------------------------------------------------

def test_points_to_vtk_transfers_float_data(geoh5_points: Points):
    result = points_to_vtk(geoh5_points)
    assert "elevation" in result.array_names
    np.testing.assert_allclose(result["elevation"], FLOAT_VALUES)


def test_points_to_vtk_transfers_int_data(geoh5_points: Points):
    result = points_to_vtk(geoh5_points)
    assert "zone" in result.array_names
    np.testing.assert_array_equal(result["zone"], INT_VALUES)


def test_points_to_vtk_metadata_name(geoh5_points: Points):
    result = points_to_vtk(geoh5_points)
    assert result.user_dict["gh5_name"] == "test_points"


def test_points_to_vtk_metadata_entity_type(geoh5_points: Points):
    result = points_to_vtk(geoh5_points)
    assert result.user_dict["gh5_entity_type"] == "Points"


def test_points_to_vtk_no_data_does_not_raise(tmp_path: Path):
    """A Points object with no data should convert without error."""
    path = tmp_path / "bare.geoh5"
    with Workspace.create(path) as ws:
        Points.create(workspace=ws, name="bare", vertices=VERTICES)
    with Workspace(path) as ws:
        pts = ws.get_entity("bare")[0]
        result = points_to_vtk(pts)
    assert result.n_points == len(VERTICES)


# ---------------------------------------------------------------------------
# vtk_geom_to_points — geometry write (VTK → geoh5 direction)
# ---------------------------------------------------------------------------

def test_vtk_geom_to_points_vertices(vtk_points: pyvista.PointSet, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_points(vtk_points, ws, "out_points")
        np.testing.assert_allclose(result.vertices, VERTICES)


def test_vtk_geom_to_points_name(vtk_points: pyvista.PointSet, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_points(vtk_points, ws, "my_points")
        assert result.name == "my_points"


# ---------------------------------------------------------------------------
# Round-trip — write and read back end-to-end
# ---------------------------------------------------------------------------

def test_round_trip_geometry(tmp_path: Path):
    """geoh5 → VTK → geoh5 → assert vertex positions are preserved."""
    src = tmp_path / "source.geoh5"
    dst = tmp_path / "dest.geoh5"

    with Workspace.create(src) as ws:
        Points.create(workspace=ws, name="pts", vertices=VERTICES)

    with Workspace(src) as ws:
        pts = ws.get_entity("pts")[0]
        vtk = points_geom_to_vtk(pts)

    with Workspace.create(dst) as ws:
        result = vtk_geom_to_points(vtk, ws, "pts_rt")
        np.testing.assert_allclose(result.vertices, VERTICES)
