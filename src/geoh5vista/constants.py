"""Constants used in geoh5vista."""

from .converters.registry import CONVERTERS, SUPPORTED

__all__ = [
    "CONVERTERS",
    "DATASKIP",
    "GEOH5SKIP",
    "SUPPORTED"
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
