"""Tests for the blockmodel module."""

import numpy as np
import pytest
import pyvista
from pathlib import Path
from geoh5py.workspace import Workspace
from geoh5py.objects.block_model import BlockModel

from geoh5vista.blockmodel import (
    get_blockmodel_shape,
    blockmodel_grid_geom_to_image_vtk,
    blockmodel_grid_geom_to_structured_vtk,
    blockmodel_to_vtk,
    vtk_geom_to_blockmodel,
    vtk_to_blockmodel,
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
# Variable-spacing geometry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("axis", ["u", "v", "z"])
@pytest.mark.parametrize("reopen", [False, True])
def test_image_helper_rejects_variable_spacing(
    tmp_path: Path, axis: str, reopen: bool
):
    path = tmp_path / "variable.geoh5"
    delimiters = {
        "u_cell_delimiters": U_DELIMITERS.copy(),
        "v_cell_delimiters": V_DELIMITERS.copy(),
        "z_cell_delimiters": Z_DELIMITERS.copy(),
    }
    delimiters[f"{axis}_cell_delimiters"][-1] += 1.0
    with Workspace.create(path) as ws:
        bm = BlockModel.create(
            ws, name="variable", origin=(650000.123, 5500000.234, 1000.0),
            **delimiters,
        )
        if not reopen:
            with pytest.raises(ValueError, match=f"variable cell spacing along the {axis} axis"):
                blockmodel_grid_geom_to_image_vtk(bm)
            assert isinstance(blockmodel_to_vtk(bm), pyvista.StructuredGrid)
    if reopen:
        with Workspace(path) as ws:
            bm = ws.get_entity("variable")[0]
            with pytest.raises(ValueError, match=f"variable cell spacing along the {axis} axis"):
                blockmodel_grid_geom_to_image_vtk(bm)
            assert isinstance(blockmodel_to_vtk(bm), pyvista.StructuredGrid)


VARIABLE_U = np.array([100.0, 101.0, 104.0])
VARIABLE_V = np.array([-40.0, -38.0, -33.0, -25.0])
VARIABLE_Z = np.array([-50.0, -51.0, -54.0, -59.0, -66.0])


@pytest.mark.parametrize("rotation", [0.0, 30.0, -90.0])
@pytest.mark.parametrize(
    "signs",
    [(1, 1, 1), (1, 1, -1), (-1, 1, 1), (1, -1, 1), (-1, -1, -1)],
)
def test_variable_spacing_structured_geometry_data_and_roundtrip(
    tmp_path: Path, rotation: float, signs: tuple
):
    origin = (650000.123456, 5500000.234567, 1200.345678)
    path = tmp_path / "variable_geometry.geoh5"
    with Workspace.create(path) as ws:
        bm = BlockModel.create(
            ws, name="variable", origin=origin, rotation=rotation,
            u_cell_delimiters=VARIABLE_U[0] + (VARIABLE_U - VARIABLE_U[0]) * signs[0],
            v_cell_delimiters=VARIABLE_V[0] + (VARIABLE_V - VARIABLE_V[0]) * signs[1],
            z_cell_delimiters=VARIABLE_Z[0] - (VARIABLE_Z - VARIABLE_Z[0]) * signs[2],
        )
        bm.add_data({
            "cell_id": {
                "association": "CELL",
                "values": np.arange(bm.n_cells, dtype=np.int32),
            },
        })

    with Workspace(path) as ws:
        model = ws.get_entity("variable")[0]
        mesh = blockmodel_to_vtk(model)
        assert isinstance(mesh, pyvista.StructuredGrid)
        assert mesh.dimensions == (3, 4, 5)
        assert mesh.user_dict["gh5_entity_type"] == "BlockModel"
        ids = mesh.cell_data["cell_id"]
        np.testing.assert_array_equal(np.sort(ids), np.arange(model.n_cells))
        np.testing.assert_allclose(
            mesh.cell_centers().points, model.centroids[ids], rtol=0, atol=1e-8
        )
        volumes = mesh.compute_cell_sizes().cell_data["Volume"]
        expected_volumes = np.einsum(
            "i,j,k->ijk",
            np.abs(model.u_cells), np.abs(model.v_cells), np.abs(model.z_cells),
        )
        assert np.all(volumes > 0)
        np.testing.assert_allclose(np.sort(volumes), np.sort(expected_volumes.ravel()))
        model_centroids = model.centroids.copy()

    export_path = tmp_path / "variable_export.geoh5"
    with Workspace.create(export_path) as ws:
        exported = vtk_to_blockmodel(mesh, ws, "exported")
        exported_ids = exported.get_data("cell_id")[0].values
        np.testing.assert_allclose(
            exported.centroids, model_centroids[exported_ids], rtol=0, atol=1e-8
        )
    with Workspace(export_path) as ws:
        restored = blockmodel_to_vtk(ws.get_entity("exported")[0])
        assert isinstance(restored, pyvista.StructuredGrid)
        np.testing.assert_allclose(
            restored.points, mesh.points, rtol=0, atol=1e-8
        )
        np.testing.assert_array_equal(restored["cell_id"], mesh["cell_id"])


def test_structured_helper_optional_rotation(tmp_path: Path):
    from geoh5py.shared.utils import xy_rotation_matrix

    origin = np.array([650000.0, 5500000.0, 1200.0])
    with Workspace.create(tmp_path / "structured_helper.geoh5") as ws:
        bm = BlockModel.create(
            ws, origin=origin, rotation=30.0,
            u_cell_delimiters=VARIABLE_U,
            v_cell_delimiters=VARIABLE_V,
            z_cell_delimiters=VARIABLE_Z,
        )
        unrotated = blockmodel_grid_geom_to_structured_vtk(bm)
        rotation = xy_rotation_matrix(np.deg2rad(30.0))
        rotated = blockmodel_grid_geom_to_structured_vtk(bm, rotation_matrix=rotation)
        np.testing.assert_allclose(
            rotated.points - origin, (unrotated.points - origin) @ rotation.T,
            rtol=0, atol=1e-8,
        )


def test_structured_grid_supports_common_filters(tmp_path: Path):
    with Workspace.create(tmp_path / "filters.geoh5") as ws:
        bm = BlockModel.create(
            ws, rotation=30.0,
            u_cell_delimiters=VARIABLE_U,
            v_cell_delimiters=VARIABLE_V,
            z_cell_delimiters=VARIABLE_Z,
        )
        bm.add_data({
            "grade": {
                "association": "CELL", "values": np.arange(bm.n_cells, dtype=float),
            },
        })
        mesh = blockmodel_to_vtk(bm)
    assert mesh.threshold([2, 8], scalars="grade").n_cells == 7
    assert mesh.slice(normal="z", origin=mesh.center).n_cells > 0
    assert mesh.clip(normal="x", origin=mesh.center).n_cells > 0
    assert mesh.cell_centers().n_points == mesh.n_cells
    subset = mesh.extract_subset((0, 1, 0, 2, 0, 3))
    assert isinstance(subset, pyvista.StructuredGrid)
    with Workspace.create(tmp_path / "subset.geoh5") as ws:
        exported = vtk_to_blockmodel(subset, ws, "subset")
        assert exported.shape == (1, 2, 3)


def test_uniform_spacing_can_differ_between_axes(tmp_path: Path):
    with Workspace.create(tmp_path / "anisotropic.geoh5") as ws:
        bm = BlockModel.create(
            ws, origin=ORIGIN,
            u_cell_delimiters=U_DELIMITERS * 10,
            v_cell_delimiters=V_DELIMITERS * 20,
            z_cell_delimiters=Z_DELIMITERS * 5,
        )
        result = blockmodel_to_vtk(bm)
        assert isinstance(result, pyvista.ImageData)
        assert result.spacing == (10.0, 20.0, 5.0)
        assert result.n_cells == N_CELLS


@pytest.mark.parametrize(
    "delimiters",
    [
        np.array([0.0, 0.0, 1.0]),
        np.array([0.0, np.nan, 2.0]),
        np.array([0.0, 1.0, np.inf]),
    ],
)
def test_invalid_spacing_rejected(tmp_path: Path, delimiters: np.ndarray):
    with Workspace.create(tmp_path / "invalid.geoh5") as ws:
        bm = BlockModel.create(
            ws, u_cell_delimiters=delimiters,
            v_cell_delimiters=V_DELIMITERS,
            z_cell_delimiters=Z_DELIMITERS,
        )
        with pytest.raises(ValueError, match="finite, nonzero cell spacing along the u axis"):
            blockmodel_to_vtk(bm)


def test_small_but_real_spacing_variation_uses_structured_grid(tmp_path: Path):
    with Workspace.create(tmp_path / "near_uniform.geoh5") as ws:
        bm = BlockModel.create(
            ws, u_cell_delimiters=np.array([0.0, 10.0, 20.00005]),
            v_cell_delimiters=V_DELIMITERS,
            z_cell_delimiters=Z_DELIMITERS,
        )
        assert isinstance(blockmodel_to_vtk(bm), pyvista.StructuredGrid)


def test_non_monotonic_delimiters_rejected(tmp_path: Path):
    with Workspace.create(tmp_path / "non_monotonic.geoh5") as ws:
        bm = BlockModel.create(
            ws, u_cell_delimiters=np.array([0.0, 2.0, 1.0]),
            v_cell_delimiters=V_DELIMITERS,
            z_cell_delimiters=Z_DELIMITERS,
        )
        with pytest.raises(ValueError, match="monotonic cell delimiters along the u axis"):
            blockmodel_to_vtk(bm)


@pytest.mark.parametrize(
    "modify",
    ["tilt", "shear", "warp", "duplicate", "non_finite"],
)
def test_structured_grid_export_rejects_non_block_geometry(
    tmp_path: Path, modify: str
):
    grid = pyvista.RectilinearGrid(VARIABLE_U, VARIABLE_V, VARIABLE_Z)
    grid = grid.cast_to_structured_grid()
    points = grid.points.copy()
    if modify == "tilt":
        grid = grid.rotate_x(10, inplace=False)
        points = grid.points.copy()
    elif modify == "shear":
        points[:, 0] += 0.1 * points[:, 1]
    elif modify == "warp":
        points[7, 2] += 0.1
    elif modify == "duplicate":
        nodes = points.reshape((*grid.dimensions, 3), order="F")
        nodes[1, :, :, 0] = nodes[0, :, :, 0]
        points = nodes.reshape((-1, 3), order="F")
    else:
        points[0, 0] = np.nan
    grid.points = points
    with Workspace.create(tmp_path / "unsupported.geoh5") as ws:
        with pytest.raises(ValueError):
            vtk_geom_to_blockmodel(grid, ws, "unsupported")
        assert ws.get_entity("unsupported") == [None]


@pytest.mark.parametrize("converter", [vtk_geom_to_blockmodel, vtk_to_blockmodel])
def test_unsupported_export_type_rejected(tmp_path: Path, converter):
    grid = pyvista.RectilinearGrid(U_DELIMITERS, V_DELIMITERS, Z_DELIMITERS)
    with Workspace.create(tmp_path / "unsupported.geoh5") as ws:
        with pytest.raises(TypeError, match="ImageData or pyvista.StructuredGrid"):
            converter(grid, ws, "unsupported")
        assert ws.get_entity("unsupported") == [None]


# ---------------------------------------------------------------------------
# blockmodel_to_vtk — ImageData path (the primary read function)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rotation", [0.0, 30.0, 90.0, -30.0])
@pytest.mark.parametrize("origin", [ORIGIN, (650000.123456, 5500000.234567, 1200.345678)])
@pytest.mark.parametrize("offset", [(0.0, 0.0, 0.0), (100.0, -40.0, -50.0)])
@pytest.mark.parametrize(
    "signs",
    [(1, 1, 1), (1, 1, -1), (-1, 1, 1), (1, -1, 1), (-1, -1, -1)],
)
def test_blockmodel_centers_match_geoh5py(
    tmp_path: Path, rotation: float, origin: tuple, offset: tuple, signs: tuple
):
    path = tmp_path / "geometry.geoh5"
    with Workspace.create(path) as ws:
        bm = BlockModel.create(
            ws, name="geometry", origin=origin, rotation=rotation,
            u_cell_delimiters=offset[0] + U_DELIMITERS * 10 * signs[0],
            v_cell_delimiters=offset[1] + V_DELIMITERS * 20 * signs[1],
            z_cell_delimiters=offset[2] + Z_DELIMITERS * 5 * signs[2],
        )
        bm.add_data({
            "cell_id": {
                "association": "CELL",
                "values": np.arange(N_CELLS, dtype=np.int32),
            },
        })

        def assert_geometry(model, label):
            mesh = blockmodel_to_vtk(model)
            assert isinstance(mesh, pyvista.ImageData)
            assert mesh.dimensions == (N_U + 1, N_V + 1, N_Z + 1)
            assert mesh.spacing == (10.0, 20.0, 5.0)
            ids = mesh.cell_data["cell_id"]
            np.testing.assert_array_equal(np.sort(ids), np.arange(N_CELLS))
            np.testing.assert_allclose(
                mesh.cell_centers().points, model.centroids[ids],
                rtol=0, atol=1e-8,
            )
            np.testing.assert_allclose(
                mesh.points[0], model.uvw_to_xyz(np.array([offset]))[0],
                rtol=0, atol=1e-8,
            )
            export_path = tmp_path / f"export_{label}.geoh5"
            with Workspace.create(export_path) as export_ws:
                exported = vtk_to_blockmodel(mesh, export_ws, "exported")
                np.testing.assert_allclose(
                    exported.centroids, model.centroids, rtol=0, atol=1e-8
                )
                np.testing.assert_array_equal(
                    exported.get_data("cell_id")[0].values, np.arange(N_CELLS)
                )
                exported_centroids = exported.centroids.copy()
            with Workspace(export_path) as export_ws:
                exported = export_ws.get_entity("exported")[0]
                np.testing.assert_allclose(
                    exported.centroids, exported_centroids, rtol=0, atol=1e-8
                )
                restored = blockmodel_to_vtk(exported)
                np.testing.assert_allclose(
                    restored.cell_centers().points, mesh.cell_centers().points,
                    rtol=0, atol=1e-8,
                )
                np.testing.assert_array_equal(
                    restored.cell_data["cell_id"], mesh.cell_data["cell_id"]
                )

        assert_geometry(bm, "created")
    with Workspace(path) as ws:
        assert_geometry(ws.get_entity("geometry")[0], "reopened")


@pytest.mark.parametrize("apply_rotation", [False, True])
def test_geometry_helper_optional_rotation(tmp_path: Path, apply_rotation: bool):
    from geoh5py.shared.utils import xy_rotation_matrix

    origin = (650000.123456, 5500000.234567, 1200.345678)
    with Workspace.create(tmp_path / "helper.geoh5") as ws:
        bm = BlockModel.create(
            ws, origin=origin, rotation=30.0,
            u_cell_delimiters=100.0 + U_DELIMITERS * 10,
            v_cell_delimiters=-40.0 + V_DELIMITERS * 20,
            z_cell_delimiters=-50.0 - Z_DELIMITERS * 5,
        )
        rotation = xy_rotation_matrix(np.deg2rad(30.0))
        mesh = blockmodel_grid_geom_to_image_vtk(
            bm, rotation_matrix=rotation if apply_rotation else None
        )
        u, v, z = np.meshgrid(
            bm.local_axis_centers("u"),
            bm.local_axis_centers("v"),
            bm.local_axis_centers("z"),
            indexing="ij",
        )
        local = np.column_stack([axis.ravel(order="F") for axis in (u, v, z)])
        expected = local @ rotation.T if apply_rotation else local
        np.testing.assert_allclose(
            mesh.cell_centers().points, expected + np.array(origin),
            rtol=0, atol=1e-8,
        )
        np.testing.assert_allclose(
            mesh.direction_matrix,
            (rotation if apply_rotation else np.eye(3)) @ np.diag([1, 1, -1]),
            rtol=0, atol=1e-15,
        )


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


@pytest.mark.parametrize(
    "direction",
    [
        np.array([[1., 0., 0.], [0., 0., -1.], [0., 1., 0.]]),
        np.array([[1., 0.2, 0.], [0., 1., 0.], [0., 0., 1.]]),
        np.diag([2., 1., 1.]),
        np.diag([1., 0., 0.]),
        np.diag([1., 1., np.nan]),
    ],
)
def test_export_rejects_unsupported_directions(tmp_path: Path, direction: np.ndarray):
    mesh = pyvista.ImageData(dimensions=(3, 4, 5))
    mesh.SetDirectionMatrix(direction.ravel().tolist())
    with Workspace.create(tmp_path / "invalid_direction.geoh5") as ws:
        with pytest.raises(ValueError):
            vtk_geom_to_blockmodel(mesh, ws, "invalid")
        assert ws.get_entity("invalid") == [None]


@pytest.mark.parametrize("dimensions", [(1, 4, 5), (3, 1, 5), (3, 4, 1)])
def test_export_requires_3d_cells(tmp_path: Path, dimensions: tuple):
    mesh = pyvista.ImageData(dimensions=dimensions)
    with Workspace.create(tmp_path / "invalid_dimensions.geoh5") as ws:
        with pytest.raises(ValueError, match="at least one cell in each axis"):
            vtk_geom_to_blockmodel(mesh, ws, "invalid")


@pytest.mark.parametrize("spacing", [(0., 1., 1.), (1., np.inf, 1.)])
def test_export_rejects_invalid_spacing(tmp_path: Path, spacing: tuple):
    mesh = pyvista.ImageData(dimensions=(3, 4, 5))
    mesh.SetSpacing(*spacing)
    with Workspace.create(tmp_path / "invalid_spacing.geoh5") as ws:
        with pytest.raises(ValueError, match="finite geometry and nonzero spacing"):
            vtk_geom_to_blockmodel(mesh, ws, "invalid")


def test_export_negative_spacing(tmp_path: Path):
    mesh = pyvista.ImageData(dimensions=(3, 4, 5))
    mesh.SetSpacing(-10., 20., -5.)
    with Workspace.create(tmp_path / "negative_spacing.geoh5") as ws:
        exported = vtk_geom_to_blockmodel(mesh, ws, "negative_spacing")
        restored = blockmodel_to_vtk(exported)
        np.testing.assert_allclose(
            restored.cell_centers().points, mesh.cell_centers().points,
            rtol=0, atol=1e-8,
        )


def test_export_nonzero_extent(tmp_path: Path):
    from geoh5py.shared.utils import xy_rotation_matrix

    mesh = pyvista.ImageData(
        dimensions=(3, 4, 5),
        origin=(650000.123456, 5500000.234567, 1200.345678),
        spacing=(10., 20., 5.),
        direction_matrix=xy_rotation_matrix(np.deg2rad(30.)) @ np.diag([1., 1., -1.]),
    )
    mesh.extent = (2, 4, -3, 0, 4, 8)
    mesh.cell_data["cell_id"] = np.arange(mesh.n_cells, dtype=np.int32)
    with Workspace.create(tmp_path / "extent.geoh5") as ws:
        exported = vtk_to_blockmodel(mesh, ws, "extent")
        restored = blockmodel_to_vtk(exported)
        np.testing.assert_allclose(
            restored.cell_centers().points, mesh.cell_centers().points,
            rtol=0, atol=1e-8,
        )
        np.testing.assert_array_equal(restored["cell_id"], mesh["cell_id"])


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
