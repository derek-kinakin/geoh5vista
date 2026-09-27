"""Tests for the data module."""

from pathlib import Path

import numpy as np
import pytest
import pyvista
from geoh5py.objects.points import Points
from geoh5py.workspace import Workspace

from geoh5vista.data import add_entity_metadata

VERTICES = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], dtype=float)


@pytest.mark.parametrize("visible", [True, False])
def test_add_entity_metadata_visibility_from_file(tmp_path: Path, visible: bool):
    """Visibility read back from file (np.int8) is recorded as a Python bool."""
    path = tmp_path / "vis.geoh5"
    with Workspace.create(path) as ws:
        pts = Points.create(workspace=ws, name="pts", vertices=VERTICES)
        pts.visible = visible

    with Workspace(path) as ws:
        pts = ws.get_entity("pts")[0]
        result = add_entity_metadata(pyvista.PointSet(VERTICES), pts)

    assert result.user_dict["gh5_visible"] is visible
