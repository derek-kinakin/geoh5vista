"""Constants used in geoh5vista."""

__all__ = [
    "CONVERTERS",
    "DATASKIP",
    "GEOH5SKIP",
    "SUPPORTED"
]


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

GEOH5SKIP = [
    "ReferencedData",
    "TextData",
    "FloatData",
    "IntegerData",
    "FilenameData",
    "ContainerGroup",
    "VisualParameters",
    "GeometricDataConstants",
    "GeoImage",
    "Octree",
    "DrapeModel",
    "AirborneMagnetics",
    "PotentialElectrode",
    "AirborneEMSurvey",
    "AirborneTEMSurvey",
    "AirborneTEMReceivers",
    "AirborneFEMTransmitters",
    "VP Model",
    "UIJsonGroup",
    "InterpretationSection",
    "BooleanData",
    "PropertyGroup",
    "CommentsData",
    "CustomGroup",
    "Maxwell plate",
    "ioGAS Points"
]

DATASKIP = [
    'Azimuth',
    'DEPTH (Static-Survey)',
    'Dip',
    'Visual Parameters',
    'UserComments',
    '__SAVED_CROSSPLOT_VISUAL_PARAMETERS__',
    'ioGAS Points',
    'Maxwell plate',
    'Loop radius'
]
