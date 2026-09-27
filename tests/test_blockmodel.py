"""Tests for the blockmodel module."""

import numpy as np
import pytest
import pyvista
from pathlib import Path
from geoh5py.workspace import Workspace
from geoh5py.objects.block_model import BlockModel

from geoh5vista.blockmodel import (
    get_blockmodel_shape,
    blockmodel_grid_geom_to_structured_vtk,
    blockmodel_to_vtk,
    vtk_geom_to_blockmodel,
    _create_blockmodel_rot_matrix
)

# ---------------------------------------------------------------------------
# Known geometry shared across all tests
# 2 (U) x 3 (V) x 4 (Z) block model with 1m uniform cells
# Total cells = 24
# ---------------------------------------------------------------------------
N_U, N_V, N_Z = 2, 3, 4
N_CELLS = N_U * N_V * N_Z          # 24
CELL_SIZE = 1.0
ORIGIN = (0.0, 0.0, 0.0)

U_DELIMITERS = np.arange(N_U + 1, dtype=float) * CELL_SIZE  # [0, 1, 2]
V_DELIMITERS = np.arange(N_V + 1, dtype=float) * CELL_SIZE  # [0, 1, 2, 3]
Z_DELIMITERS = np.arange(N_Z + 1, dtype=float) * CELL_SIZE  # [0, 1, 2, 3, 4]

# Sequential float values matching geoh5 flat cell ordering (v, u, z) C-order
FLOAT_VALUES = np.arange(N_CELLS, dtype=float)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def geoh5_blockmodel(tmp_path: Path):
    """Create and open a test BlockModel in a temporary .geoh5 workspace."""
    path = tmp_path / "test_bm.geoh5"
    with Workspace.create(path) as ws:
        bm = BlockModel.create(
            ws,
            name="test_bm",
            origin=ORIGIN,
            u_cell_delimiters=U_DELIMITERS,
            v_cell_delimiters=V_DELIMITERS,
            z_cell_delimiters=Z_DELIMITERS,
            rotation=0.0,
        )
        bm.add_data({
            "density": {"type": "float", "association": "CELL", "values": FLOAT_VALUES},
        })
    with Workspace(path) as ws:
        yield ws.get_entity("test_bm")[0]


@pytest.fixture
def geoh5_blockmodel_rotated(tmp_path: Path):
    """Create a BlockModel with a 45° rotation."""
    path = tmp_path / "rotated_bm.geoh5"
    with Workspace.create(path) as ws:
        BlockModel.create(
            ws,
            name="rotated_bm",
            origin=ORIGIN,
            u_cell_delimiters=U_DELIMITERS,
            v_cell_delimiters=V_DELIMITERS,
            z_cell_delimiters=Z_DELIMITERS,
            rotation=45.0,
        )
    with Workspace(path) as ws:
        yield ws.get_entity("rotated_bm")[0]


@pytest.fixture
def vtk_image_data() -> pyvista.ImageData:
    """A pyvista.ImageData matching the known block model geometry."""
    mesh = pyvista.ImageData()
    mesh.origin = ORIGIN
    mesh.spacing = (CELL_SIZE, CELL_SIZE, CELL_SIZE)
    mesh.dimensions = (N_U + 1, N_V + 1, N_Z + 1)   # node count, not cell count
    return mesh


# ---------------------------------------------------------------------------
# get_blockmodel_shape
# ---------------------------------------------------------------------------

def test_get_blockmodel_shape(geoh5_blockmodel: BlockModel):
    shape = get_blockmodel_shape(geoh5_blockmodel)
    assert shape == (N_U, N_V, N_Z)


# ---------------------------------------------------------------------------
# blockmodel_grid_geom_to_vtk — StructuredGrid path
# ---------------------------------------------------------------------------

def test_blockmodel_grid_geom_to_vtk_returns_structured_grid(geoh5_blockmodel: BlockModel):
    result = blockmodel_grid_geom_to_structured_vtk(geoh5_blockmodel)
    assert isinstance(result, pyvista.StructuredGrid)


def test_blockmodel_grid_geom_to_vtk_cell_count(geoh5_blockmodel: BlockModel):
    result = blockmodel_grid_geom_to_structured_vtk(geoh5_blockmodel)
    assert result.n_cells == N_CELLS


def test_blockmodel_grid_geom_to_vtk_dimensions(geoh5_blockmodel: BlockModel):
    # Node dimensions = cell count + 1 in each axis
    result = blockmodel_grid_geom_to_structured_vtk(geoh5_blockmodel)
    assert result.dimensions == (N_U + 1, N_V + 1, N_Z + 1)


def test_blockmodel_grid_geom_to_vtk_point_extent(geoh5_blockmodel: BlockModel):
    # With origin=(0,0,0) and unit cells the grid spans exactly the delimiters
    result = blockmodel_grid_geom_to_structured_vtk(geoh5_blockmodel)
    np.testing.assert_allclose(result.points.min(axis=0), [0.0, 0.0, 0.0], atol=1e-6)
    np.testing.assert_allclose(result.points.max(axis=0), [N_U, N_V, N_Z], atol=1e-6)


def test_blockmodel_grid_geom_to_vtk_rotation_moves_points(
    geoh5_blockmodel: BlockModel, geoh5_blockmodel_rotated: BlockModel
):
    """A rotated model should produce a different set of grid points."""
    result_base = blockmodel_grid_geom_to_structured_vtk(geoh5_blockmodel)

    # Build the rotation matrix the same way the library does
    rot = _create_blockmodel_rot_matrix(geoh5_blockmodel_rotated)
    result_rotated_actual = blockmodel_grid_geom_to_structured_vtk(geoh5_blockmodel_rotated, rotation_matrix=rot)

    assert not np.allclose(result_base.points, result_rotated_actual.points)


# ---------------------------------------------------------------------------
# blockmodel_to_vtk — ImageData path (the primary read function)
# ---------------------------------------------------------------------------

def test_blockmodel_to_vtk_returns_image_data(geoh5_blockmodel: BlockModel):
    result = blockmodel_to_vtk(geoh5_blockmodel)
    assert isinstance(result, pyvista.ImageData)


def test_blockmodel_to_vtk_cell_count(geoh5_blockmodel: BlockModel):
    result = blockmodel_to_vtk(geoh5_blockmodel)
    assert result.n_cells == N_CELLS


def test_blockmodel_to_vtk_spacing(geoh5_blockmodel: BlockModel):
    result = blockmodel_to_vtk(geoh5_blockmodel)
    np.testing.assert_allclose(result.spacing, (CELL_SIZE, CELL_SIZE, CELL_SIZE), atol=1e-6)


def test_blockmodel_to_vtk_dimensions(geoh5_blockmodel: BlockModel):
    result = blockmodel_to_vtk(geoh5_blockmodel)
    assert result.dimensions == (N_U + 1, N_V + 1, N_Z + 1)


def test_blockmodel_to_vtk_transfers_float_data(geoh5_blockmodel: BlockModel):
    result = blockmodel_to_vtk(geoh5_blockmodel)
    assert "density" in result.array_names


def test_blockmodel_to_vtk_data_length(geoh5_blockmodel: BlockModel):
    result = blockmodel_to_vtk(geoh5_blockmodel)
    assert len(result["density"]) == N_CELLS


def test_blockmodel_to_vtk_data_all_values_present(geoh5_blockmodel: BlockModel):
    """All original values should survive the reshape/transpose, just reordered."""
    result = blockmodel_to_vtk(geoh5_blockmodel)
    np.testing.assert_array_equal(
        np.sort(result["density"]),
        np.sort(FLOAT_VALUES),
    )


def test_blockmodel_to_vtk_data_reindex_specific_cells(geoh5_blockmodel: BlockModel):
    """Verify the (v,u,z) → VTK reindexing for a handful of known cells.

    geoh5 stores data in (v, u, z) C-order, so flat index = v*N_U*N_Z + u*N_Z + z.
    After reshape+transpose+flatten('F'), VTK cell j corresponds to
    (u = j % N_U,  v = (j // N_U) % N_V,  z = j // (N_U * N_V)).
    With FLOAT_VALUES = arange(N_CELLS), each value equals its geoh5 flat index.
    """
    result = blockmodel_to_vtk(geoh5_blockmodel)
    vtk_values = result["density"]

    def geoh5_index(u, v, z):
        return v * N_U * N_Z + u * N_Z + z

    def vtk_cell(u, v, z):
        return u + v * N_U + z * N_U * N_V

    # spot-check several (u, v, z) triples
    for u, v, z in [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 2, 3)]:
        expected = float(geoh5_index(u, v, z))
        actual = vtk_values[vtk_cell(u, v, z)]
        assert actual == expected, (
            f"Cell (u={u}, v={v}, z={z}): expected {expected}, got {actual}"
        )


def test_blockmodel_to_vtk_metadata_name(geoh5_blockmodel: BlockModel):
    result = blockmodel_to_vtk(geoh5_blockmodel)
    assert result.user_dict["gh5_name"] == "test_bm"


def test_blockmodel_to_vtk_metadata_entity_type(geoh5_blockmodel: BlockModel):
    result = blockmodel_to_vtk(geoh5_blockmodel)
    assert result.user_dict["gh5_entity_type"] == "BlockModel"


def test_blockmodel_to_vtk_no_data_does_not_raise(tmp_path: Path):
    """A BlockModel with no data arrays should convert without error."""
    path = tmp_path / "bare_bm.geoh5"
    with Workspace.create(path) as ws:
        BlockModel.create(
            ws,
            name="bare",
            origin=ORIGIN,
            u_cell_delimiters=U_DELIMITERS,
            v_cell_delimiters=V_DELIMITERS,
            z_cell_delimiters=Z_DELIMITERS,
            rotation=0.0,
        )
    with Workspace(path) as ws:
        bm = ws.get_entity("bare")[0]
        result = blockmodel_to_vtk(bm)
    assert result.n_cells == N_CELLS


# ---------------------------------------------------------------------------
# vtk_geom_to_blockmodel — write direction (VTK → geoh5)
# NOTE: vtk_geom_to_blockmodel expects pyvista.ImageData with uniform cell sizes.
# ---------------------------------------------------------------------------

def test_vtk_geom_to_blockmodel_cell_count(vtk_image_data: pyvista.ImageData, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_blockmodel(vtk_image_data, ws, "out_bm")
        assert result.n_cells == N_CELLS


def test_vtk_geom_to_blockmodel_shape(vtk_image_data: pyvista.ImageData, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_blockmodel(vtk_image_data, ws, "out_bm")
        assert result.shape == (N_U, N_V, N_Z)


def test_vtk_geom_to_blockmodel_name(vtk_image_data: pyvista.ImageData, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_blockmodel(vtk_image_data, ws, "my_bm")
        assert result.name == "my_bm"


def test_vtk_geom_to_blockmodel_cell_sizes(vtk_image_data: pyvista.ImageData, tmp_path: Path):
    with Workspace.create(tmp_path / "out.geoh5") as ws:
        result = vtk_geom_to_blockmodel(vtk_image_data, ws, "out_bm")
        np.testing.assert_allclose(result.u_cells, np.full(N_U, CELL_SIZE), atol=1e-6)
        np.testing.assert_allclose(result.v_cells, np.full(N_V, CELL_SIZE), atol=1e-6)
        np.testing.assert_allclose(np.abs(result.z_cells), np.full(N_Z, CELL_SIZE), atol=1e-6)


# ---------------------------------------------------------------------------
# Round-trip — write and read back end-to-end
# ---------------------------------------------------------------------------

def test_round_trip_geometry(tmp_path: Path):
    """geoh5 → ImageData → geoh5 → assert cell count and shape are preserved."""
    src = tmp_path / "source.geoh5"
    dst = tmp_path / "dest.geoh5"

    with Workspace.create(src) as ws:
        BlockModel.create(
            ws,
            name="bm",
            origin=ORIGIN,
            u_cell_delimiters=U_DELIMITERS,
            v_cell_delimiters=V_DELIMITERS,
            z_cell_delimiters=Z_DELIMITERS,
            rotation=0.0,
        )

    with Workspace(src) as ws:
        bm = ws.get_entity("bm")[0]
        vtk = blockmodel_to_vtk(bm)

    with Workspace.create(dst) as ws:
        result = vtk_geom_to_blockmodel(vtk, ws, "bm_rt")
        assert result.n_cells == N_CELLS
        assert result.shape == (N_U, N_V, N_Z)
        np.testing.assert_allclose(result.u_cells, np.full(N_U, CELL_SIZE), atol=1e-6)
        np.testing.assert_allclose(result.v_cells, np.full(N_V, CELL_SIZE), atol=1e-6)
