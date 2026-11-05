"""Canonical package boundaries and backwards-compatible public imports."""

import ast
import os
import subprocess
import sys
from importlib import import_module
from importlib.util import resolve_name
from pathlib import Path

import pytest

import geoh5vista

CONVERTER_MODULES = (
    "blockmodel",
    "curve",
    "grid2d",
    "label",
    "points",
    "slicer",
    "surface",
)


@pytest.mark.parametrize("name", CONVERTER_MODULES)
def test_legacy_converter_exports_are_identical(name):
    legacy = import_module(f"geoh5vista.{name}")
    canonical = import_module(f"geoh5vista.converters.{name}")
    assert set(legacy.__all__) == set(canonical.__all__)
    for exported in legacy.__all__:
        assert getattr(legacy, exported) is getattr(canonical, exported)


@pytest.mark.parametrize(
    "legacy_name, canonical_name",
    [
        ("catalog", "io.catalog"),
        ("selective", "io.selective"),
    ],
)
def test_legacy_io_exports_are_identical(legacy_name, canonical_name):
    legacy = import_module(f"geoh5vista.{legacy_name}")
    canonical = import_module(f"geoh5vista.{canonical_name}")
    assert legacy.__all__ == canonical.__all__
    for name in legacy.__all__:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_legacy_wrapper_and_root_exports_are_identical():
    from geoh5vista import wrapper
    from geoh5vista.converters import dispatch
    from geoh5vista.io import readers, selective, writers

    functions = {
        "geoh5wrap": dispatch.geoh5wrap,
        "read_geoh5": readers.read_geoh5,
        "read_geoh5_entities": selective.read_geoh5_entities,
        "vtkwrap": dispatch.vtkwrap,
        "write_geoh5": writers.write_geoh5,
    }
    for name, function in functions.items():
        assert getattr(geoh5vista, name) is function
        assert name in dir(geoh5vista)
        if name != "read_geoh5_entities":
            assert getattr(wrapper, name) is function
    assert wrapper.GEOH5WRAPPERS is dispatch.GEOH5WRAPPERS
    assert wrapper.VTKWRAPPERS is dispatch.VTKWRAPPERS
    assert wrapper.entities_to_vtk is dispatch.entities_to_vtk
    assert wrapper.vtk_to_entities is writers.vtk_to_entities
    assert wrapper.MODULE_DISPLAY_NAME == "Wrapper"
    assert wrapper.FUNCTION_DISPLAY_NAMES == {
        "geoh5wrap": "Geoh5 Wrap",
        "read_geoh5": "Read Geoh5",
        "vtkwrap": "VTK Wrap",
        "write_geoh5": "Write Geoh5",
    }


def test_legacy_drillhole_conversion_and_persistence_exports():
    from geoh5vista import drillholes
    from geoh5vista.converters import drillholes as conversions
    from geoh5vista.io import drillhole_vtm

    for name in ("drillhole_to_vtk", "drillholes_to_vtk"):
        assert getattr(drillholes, name) is getattr(conversions, name)
    for name in ("read_drillholes", "save_drillholes"):
        assert getattr(drillholes, name) is getattr(drillhole_vtm, name)
    assert drillholes.MODULE_DISPLAY_NAME == "Drillholes"
    assert drillholes.FUNCTION_DISPLAY_NAMES == {
        "drillhole_to_vtk": "Drillhole to VTK",
        "drillholes_to_vtk": "Drillholes to VTK",
        "save_drillholes": "Save Drillholes",
        "read_drillholes": "Read Drillholes",
    }


def test_legacy_array_and_metadata_exports():
    from geoh5vista import data
    from geoh5vista.converters import arrays, metadata

    for name in arrays.__all__:
        if name not in ("FUNCTION_DISPLAY_NAMES", "MODULE_DISPLAY_NAME"):
            assert getattr(data, name) is getattr(arrays, name)
    for name in ("add_entity_metadata", "restore_entity_metadata"):
        assert getattr(data, name) is getattr(metadata, name)
    assert data.create_value_map is arrays.create_value_map
    assert data.get_data_type is arrays.get_data_type
    assert data.MODULE_DISPLAY_NAME == "Data"
    assert data.FUNCTION_DISPLAY_NAMES == (
        arrays.FUNCTION_DISPLAY_NAMES | metadata.FUNCTION_DISPLAY_NAMES
    )


def test_legacy_hierarchy_helpers_and_registry_exports():
    from geoh5vista import constants, hierarchy, visibility
    from geoh5vista.converters import registry
    from geoh5vista.io import _hdf5
    from geoh5vista.io import hierarchy as discovery
    from geoh5vista.models import EntityMetadata

    for name in ("dataset", "group", "text", "uid"):
        assert getattr(hierarchy, name) is getattr(_hdf5, name)
    for name in (
        "HierarchyNode",
        "concatenated_object_type",
        "concatenated_records",
        "read_hierarchy",
    ):
        assert getattr(hierarchy, name) is getattr(discovery, name)
    assert visibility.project_group is _hdf5.project_group
    assert constants.CONVERTERS is registry.CONVERTERS
    assert constants.SUPPORTED is registry.SUPPORTED
    assert geoh5vista.EntityMetadata is EntityMetadata
    assert geoh5vista.geoh5wrap(None) is None
    assert geoh5vista.vtkwrap(None, "unused.geoh5") is None


def test_metadata_subpackages_do_not_import_vtk_or_loaders():
    code = """
import importlib.abc
import sys

class NoVTK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('pyvista', 'vtk', 'vtkmodules'):
            raise AssertionError('VTK import attempted: ' + fullname)

sys.meta_path.insert(0, NoVTK())
import geoh5vista
import geoh5vista.io
import geoh5vista.converters
import geoh5vista.models
import geoh5vista.converters.registry
import geoh5vista.io.hierarchy
import geoh5vista.io.catalog
import geoh5vista.catalog
import geoh5vista.hierarchy
import geoh5vista.constants
import geoh5vista.visibility
for name in (
    'geoh5vista.wrapper',
    'geoh5vista.data',
    'geoh5vista.converters.dispatch',
    'geoh5vista.converters.arrays',
    'geoh5vista.converters.metadata',
    'geoh5vista.converters.drillholes',
    'geoh5vista.io.readers',
    'geoh5vista.io.selective',
    'geoh5vista.io.writers',
    'geoh5vista.io.drillhole_vtm',
):
    assert name not in sys.modules, name
assert set(geoh5vista.__all__).issubset(dir(geoh5vista))
"""
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1] / "src"))
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_internal_packages_do_not_import_compatibility_modules():
    root = Path(__file__).parents[1] / "src" / "geoh5vista"
    compatibility = {
        f"geoh5vista.{name}"
        for name in (
            *CONVERTER_MODULES,
            "catalog",
            "data",
            "drillholes",
            "hierarchy",
            "selective",
            "wrapper",
        )
    }
    for directory in ("io", "converters"):
        for path in (root / directory).glob("*.py"):
            package = f"geoh5vista.{directory}"
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    module = resolve_name(
                        "." * node.level + (node.module or ""), package
                    )
                    imported = [
                        module,
                        *(f"{module}.{alias.name}" for alias in node.names),
                    ]
                else:
                    continue
                assert not compatibility.intersection(imported), (path.name, imported)
