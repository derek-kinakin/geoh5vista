"""Tests for the surface module."""

import numpy as np
import pytest
import pyvista
from pathlib import Path
from geoh5py.workspace import Workspace
from geoh5py.objects.surface import Surface

from geoh5vista.surface import (
    surface_geom_to_vtk,
    surface_to_vtk,
    vtk_geom_to_surface,
)

# ---------------------------------------------------------------------------
# Known geometry shared across all tests — a simple tetrahedron base
# ---------------------------------------------------------------------------
VERTICES = np.array(
    [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.5, 1.0, 0.0], [0.5, 0.5, 1.0]],
    dtype=float,
)
# Two triangular faces
CELLS = np.array([[0, 1, 2], [0, 1, 3]], dtype=int)
FLOAT_VALUES = np.array([0.5, 1.5, 2.5, 3.5], dtype=float)
INT_VALUES = np.array([1, 2, 3, 4], dtype=int)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def geoh5_surface(tmp_path: Path):
    """Create and open a test Surface in a temporary .geoh5 workspace."""
    path = tmp_path / "test_surface.geoh5"
    with Workspace.create(path) as ws:
        surf = Surface.create(
            workspace=ws, name="test_surface", vertices=VERTICES, cells=CELLS
        )
        surf.add_data({
            "elevation": {"type": "float", "association": "VERTEX", "values": FLOAT_VALUES},
            "zone": {"type": "integer", "association": "VERTEX", "values": INT_VALUES},
        })
    with Workspace(path) as ws:
        yield ws.get_entity("test_surface")[0]


@pytest.fixture
def vtk_surface() -> pyvista.PolyData:
    """Create a PyVista triangular PolyData with the same known geometry."""
    # pyvista.make_tri_mesh is the same helper used by surface_geom_to_vtk
    mesh = pyvista.make_tri_mesh(VERTICES, CELLS)
    mesh["elevation"] = FLOAT_VALUES
    return mesh


# ---------------------------------------------------------------------------
# surface_geom_to_vtk — geometry conversion (read direction)
# ---------------------------------------------------------------------------

def test_surface_geom_to_vtk_point_count(geoh5_surface: Surface):
    result = surface_geom_to_vtk(geoh5_surface)
    assert result.n_points == len(VERTICES)


def test_surface_geom_to_vtk_cell_count(geoh5_surface: Surface):
    result = surface_geom_to_vtk(geoh5_surface)
    assert result.n_cells == len(CELLS)


def test_surface_geom_to_vtk_vertices(geoh5_surface: Surface):
    result = surface_geom_to_vtk(geoh5_surface)
    np.testing.assert_allclose(result.points, VERTICES)


def test_surface_geom_to_vtk_faces(geoh5_surface: Surface):
    # VTK stores faces with a leading count per face: [3, v0, v1, v2, ...]
    result = surface_geom_to_vtk(geoh5_surface)
    recovered_cells = result.faces.reshape((result.n_cells, 4))[:, 1:]
    np.testing.assert_array_equal(recovered_cells, CELLS)


def test_surface_geom_to_vtk_raises_on_missing_geometry(tmp_path: Path):
    """surface_geom_to_vtk should raise ValueError when vertices or cells are absent."""
    path = tmp_path / "empty.geoh5"
    with Workspace.create(path) as ws:
        surf = Surface.create(workspace=ws, name="empty")
    with Workspace(path) as ws:
        surf = ws.get_entity("empty")[0]
        with pytest.raises(ValueError):
            surface_geom_to_vtk(surf)


def test_surface_geom_to_vtk_raises_on_degenerate_placeholder_geometry(tmp_path: Path):
    path = tmp_path / "degenerate.geoh5"
    vertices = np.zeros((3, 3), dtype=float)
    cells = np.array([[0, 1, 2]], dtype=int)

    with Workspace.create(path) as ws:
        Surface.create(workspace=ws, name="degenerate", vertices=vertices, cells=cells)

    with Workspace(path) as ws:
        surf = ws.get_entity("degenerate")[0]
        with pytest.raises(ValueError):
            surface_geom_to_vtk(surf)

# ---------------------------------------------------------------------------
# surface_to_vtk — data and metadata transfer (read direction)
# ---------------------------------------------------------------------------

def test_surface_to_vtk_transfers_float_data(geoh5_surface: Surface):
    result = surface_to_vtk(geoh5_surface)
    assert "elevation" in result.array_names
    np.testing.assert_allclose(result["elevation"], FLOAT_VALUES)


def test_surface_to_vtk_transfers_int_data(geoh5_surface: Surface):
    result = surface_to_vtk(geoh5_surface)
    assert "zone" in result.array_names
    np.testing.assert_array_equal(result["zone"], INT_VALUES)


def test_surface_to_vtk_metadata_name(geoh5_surface: Surface):
    result = surface_to_vtk(geoh5_surface)
    assert result.user_dict["gh5_name"] == "test_surface"


def test_surface_to_vtk_metadata_entity_type(geoh5_surface: Surface):
    result = surface_to_vtk(geoh5_surface)
    assert result.user_dict["gh5_entity_type"] == "Surface"


def test_surface_to_vtk_no_data_does_not_raise(tmp_path: Path):
    """A Surface with no data should convert without error."""
    path = tmp_path / "bare.geoh5"
    with Workspace.create(path) as ws:
        Surface.create(workspace=ws, name="bare", vertices=VERTICES, cells=CELLS)
    with Workspace(path) as ws:
        surf = ws.get_entity("bare")[0]
        result = surface_to_vtk(surf)
    assert result.n_points == len(VERTICES)


# ---------------------------------------------------------------------------
# vtk_geom_to_surface — geometry write (VTK → geoh5 direction)
# ---------------------------------------------------------------------------

def test_vtk_geom_to_surface_vertices(vtk_surface: pyvista.PolyData, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_surface(vtk_surface, ws, "out_surface")
        np.testing.assert_allclose(result.vertices, VERTICES)


def test_vtk_geom_to_surface_cells(vtk_surface: pyvista.PolyData, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_surface(vtk_surface, ws, "out_surface")
        np.testing.assert_array_equal(result.cells, CELLS)


def test_vtk_geom_to_surface_name(vtk_surface: pyvista.PolyData, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_surface(vtk_surface, ws, "my_surface")
        assert result.name == "my_surface"


# ---------------------------------------------------------------------------
# Round-trip — write and read back end-to-end
# ---------------------------------------------------------------------------

def test_round_trip_geometry(tmp_path: Path):
    """geoh5 → VTK → geoh5 → assert vertices and faces are preserved."""
    src = tmp_path / "source.geoh5"
    dst = tmp_path / "dest.geoh5"

    with Workspace.create(src) as ws:
        Surface.create(workspace=ws, name="surf", vertices=VERTICES, cells=CELLS)

    with Workspace(src) as ws:
        surf = ws.get_entity("surf")[0]
        vtk = surface_geom_to_vtk(surf)

    with Workspace.create(dst) as ws:
        result = vtk_geom_to_surface(vtk, ws, "surf_rt")
        np.testing.assert_allclose(result.vertices, VERTICES)
        np.testing.assert_array_equal(result.cells, CELLS)
