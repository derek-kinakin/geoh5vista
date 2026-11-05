"""Compatibility imports; catalog discovery lives in :mod:`geoh5vista.io.catalog`."""

from .io.catalog import EntityMetadata, catalog_geoh5

__all__ = ("EntityMetadata", "catalog_geoh5")
