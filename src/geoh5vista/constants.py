"""Constants used in geoh5vista."""

__all__ = [
    "SUPPORTED",
    "GEOH5SKIP",
    "DATASKIP"
]


SUPPORTED = [
    "Points",
    "Curve",
    "Surface",
    "Grid2D",
    "BlockModel",
    "Drillhole",
    "DrillholeGroup",
    "ConcatenatorDrillholeGroup",
    "Slicer",
]

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
    "ConcatenatedDrillhole",
    "CustomGroup"
]

DATASKIP = [
    'Azimuth',
    'DEPTH (Static-Survey)',
    'Dip',
    'Visual Parameters',
    'UserComments'
]
