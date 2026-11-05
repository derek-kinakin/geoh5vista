"""Lightweight conversion capabilities, without importing converter implementations."""

__all__ = ("CONVERTERS", "SUPPORTED")


CONVERTERS: dict[str, tuple[str, str]] = {
    "Points": ("points", "points_to_vtk"),
    "Curve": ("curve", "curve_to_vtk"),
    "Surface": ("surface", "surface_to_vtk"),
    "Grid2D": ("grid2d", "grid2d_to_vtk"),
    "BlockModel": ("blockmodel", "blockmodel_to_vtk"),
    "Drillhole": ("drillholes", "drillhole_to_vtk"),
    "DrillholeGroup": ("drillholes", "drillholes_to_vtk"),
    "ConcatenatorDrillholeGroup": ("drillholes", "drillholes_to_vtk"),
    "ConcatenatedDrillhole": ("drillholes", "drillhole_to_vtk"),
    "Slicer": ("slicer", "slicer_to_vtk_plane"),
    "Label": ("label", "label_to_vtk"),
}

SUPPORTED = list(CONVERTERS)
