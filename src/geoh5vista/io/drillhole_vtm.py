"""VTM persistence for drillhole composites and their nested metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import numpy as np
import pyvista

__all__ = ("FUNCTION_DISPLAY_NAMES", "MODULE_DISPLAY_NAME", "read_drillholes", "save_drillholes")

MODULE_DISPLAY_NAME: Final[str] = "Drillhole VTM"
FUNCTION_DISPLAY_NAMES: Final[dict[str, str]] = {
    "save_drillholes": "Save Drillholes",
    "read_drillholes": "Read Drillholes",
}


def save_drillholes(data: pyvista.MultiBlock, filename: str | Path) -> None:
    """Save a composite as VTM, preserving nested container metadata."""
    if not isinstance(data, pyvista.MultiBlock):
        raise TypeError("Expected a MultiBlock drillhole composite.")
    if Path(filename).suffix.lower() != ".vtm":
        raise ValueError("Drillhole composites must be saved as .vtm.")
    packed = data.copy(deep=True)
    if "geoh5vista_nested_metadata" in packed.user_dict:
        raise ValueError("Reserved nested-metadata registry key is already present.")
    registry = {}
    for index, _, block in packed.recursive_iterator("all", node_type="parent"):
        if any(name != "_PYVISTA_USER_DICT" for name in block.field_data):
            raise ValueError("Unexpected nested field data in drillhole composite.")
        if block.user_dict:
            registry["/".join(map(str, index))] = dict(block.user_dict)
        block.clear_field_data()
    for index, _, block in data.recursive_iterator("all", node_type="child"):
        if block is None:
            continue
        if "geoh5vista_boolean_arrays" in block.user_dict:
            raise ValueError("Reserved Boolean-array registry key is already present.")
        boolean_arrays = {
            association: [
                name
                for name, array in getattr(block, association).items()
                if name != "_PYVISTA_USER_DICT" and array.dtype.kind == "b"
            ]
            for association in ("point_data", "cell_data", "field_data")
        }
        if any(boolean_arrays.values()):
            target = packed
            for part in index:
                target = target[part]
            target.user_dict["geoh5vista_boolean_arrays"] = boolean_arrays
    packed.user_dict["geoh5vista_nested_metadata"] = registry
    packed.save(filename)


def _retain_wrappers(data: pyvista.MultiBlock) -> None:
    # Keep Python wrappers alive so Boolean dtype tracking survives nested lookups.
    for index in range(len(data)):
        block = data[index]
        if isinstance(block, pyvista.MultiBlock):
            _retain_wrappers(block)
        name = data.get_block_name(index)
        data[index] = block
        data.set_block_name(index, name)


def read_drillholes(filename: str | Path) -> pyvista.MultiBlock:
    """Read a VTM saved by :func:`save_drillholes` and restore container metadata."""
    data = pyvista.read(filename)
    if not isinstance(data, pyvista.MultiBlock):
        raise TypeError("Expected a MultiBlock drillhole file.")
    _retain_wrappers(data)
    if "geoh5vista_nested_metadata" not in data.user_dict:
        raise ValueError("Missing nested metadata registry; save composites with save_drillholes.")
    registry = data.user_dict.pop("geoh5vista_nested_metadata")
    if not isinstance(registry, dict):
        raise ValueError("Invalid nested drillhole metadata registry.")
    for path, metadata in registry.items():
        if (
            not isinstance(path, str)
            or not all(part.isdecimal() for part in path.split("/"))
            or not isinstance(metadata, dict)
        ):
            raise ValueError("Invalid nested drillhole metadata entry.")
        block = data
        for index in path.split("/"):
            if not isinstance(block, pyvista.MultiBlock) or int(index) >= len(block):
                raise ValueError("Nested drillhole metadata path does not match the file.")
            block = block[int(index)]
        if not isinstance(block, pyvista.MultiBlock):
            raise ValueError("Nested drillhole metadata must refer to a MultiBlock.")
        block.user_dict.update(metadata)
    # VTK XML persists bool arrays as uint8 and does not retain PyVista's bool tracking.
    for block in data.recursive_iterator(node_type="child"):
        if block is None or "geoh5vista_boolean_arrays" not in block.user_dict:
            continue
        boolean_arrays = block.user_dict.pop("geoh5vista_boolean_arrays")
        if not isinstance(boolean_arrays, dict):
            raise ValueError("Invalid Boolean-array registry.")
        for association, names in boolean_arrays.items():
            if association not in ("point_data", "cell_data", "field_data") or not isinstance(
                names, list
            ):
                raise ValueError("Invalid Boolean-array association.")
            arrays = getattr(block, association)
            for name in names:
                if not isinstance(name, str) or name not in arrays:
                    raise ValueError("Boolean-array registry does not match the file.")
                if not np.isin(arrays[name], [0, 1]).all():
                    raise ValueError(f"Invalid Boolean values in {name!r}.")
                arrays[name] = np.asarray(arrays[name]).astype(bool)
    return data
