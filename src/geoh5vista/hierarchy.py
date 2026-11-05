"""Compatibility imports; native discovery lives in :mod:`geoh5vista.io.hierarchy`."""

from .io._hdf5 import dataset, group, text, uid
from .io.hierarchy import (
    HierarchyNode,
    concatenated_object_type,
    concatenated_records,
    read_hierarchy,
)

__all__ = (
    "HierarchyNode",
    "concatenated_object_type",
    "concatenated_records",
    "dataset",
    "group",
    "read_hierarchy",
    "text",
    "uid",
)
