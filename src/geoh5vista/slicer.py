"""This module provides functions for converting geoh5py Slicer objects to PyVista data objects."""


__all__ = [
    "slicer_to_vtk_plane",
]

__displayname__ = "Slicer"


import re
import pyvista
import xml.etree.ElementTree as ET
from typing import Tuple, List, Optional
from geoh5py.objects.slicer import Slicer
from geoh5vista.data import add_entity_metadata

# Archived: improved regex-based extraction
def extract_slicer_position_orientation(slicer_params) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """
    Extract position and orientation data from geoh5py Slicer visual parameters.
    
    Args:
        slicer_params: The formatted_values from slicer's Visual Parameters data
        
    Returns:
        Tuple of (position_values, orientation_values) where each is a list of floats
        Returns (None, None) if extraction fails
    """
    try:
        # Convert bytes to string if necessary
        if isinstance(slicer_params, bytes):
            xml_string = slicer_params.decode('utf-8')
        else:
            xml_string = str(slicer_params)
        
        # Extract position using regex
        position_match = re.search(r'<Position>[^{]*\{([^}]+)\}</Position>', xml_string)
        orientation_match = re.search(r'<Orientation>\{([^}]+)\}</Orientation>', xml_string)
        
        position_values = None
        orientation_values = None
        
        if position_match:
            position_str = position_match.group(1)
            position_values = [float(val.strip()) for val in position_str.split(',')]
            
        if orientation_match:
            orientation_str = orientation_match.group(1)
            orientation_values = [float(val.strip()) for val in orientation_str.split(',')]
            
        return position_values, orientation_values
        
    except Exception as e:
        print(f"Error extracting slicer data: {e}")
        return None, None

# Archived: original fallback method
def extract_slicer_position_orientation_fallback(slicer_params) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """
    Fallback method using line-by-line parsing (your original approach).
    
    Args:
        slicer_params: The formatted_values from slicer's Visual Parameters data
        
    Returns:
        Tuple of (position_values, orientation_values) where each is a list of floats
        Returns (None, None) if extraction fails
    """
    try:
        # Convert to string and split into lines
        if isinstance(slicer_params, bytes):
            lines = slicer_params.decode('utf-8').split('\n')
        else:
            lines = str(slicer_params).split('\n')
        
        position_values = None
        orientation_values = None
        
        # Search through lines for Position and Orientation
        for line in lines:
            line = line.strip()
            if '<Position>' in line and '{' in line and '}' in line:
                # Extract position value from between curly braces
                position_str = line.split('{')[1].split('}')[0]
                position_values = [float(val.strip()) for val in position_str.split(',')]
                
            elif '<Orientation>' in line and '{' in line and '}' in line:
                # Extract orientation value from between curly braces
                orientation_str = line.split('{')[1].split('}')[0]
                orientation_values = [float(val.strip()) for val in orientation_str.split(',')]
                
        return position_values, orientation_values
        
    except Exception as e:
        print(f"Error in fallback extraction: {e}")
        return None, None

# Archived method using XML parsing
def extract_slicer_position_orientation_xml(slicer_params) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """
    Extract position and orientation data using proper XML parsing.
    
    This method uses Python's built-in XML parser for more robust extraction.
    
    Args:
        slicer_params: The formatted_values from slicer's Visual Parameters data
        
    Returns:
        Tuple of (position_values, orientation_values) where each is a list of floats
        Returns (None, None) if extraction fails
    """
    try:
        # Convert bytes to string if necessary
        if isinstance(slicer_params, bytes):
            xml_string = slicer_params.decode('utf-8')
        else:
            xml_string = str(slicer_params)
        
        # Parse the XML
        root = ET.fromstring(xml_string)
        
        position_values = None
        orientation_values = None
        
        # Find Position element
        position_elem = root.find('.//Position')
        if position_elem is not None and position_elem.text:
            # Extract values from between curly braces
            text = position_elem.text.strip()
            if '{' in text and '}' in text:
                position_str = text.split('{')[1].split('}')[0]
                position_values = [float(val.strip()) for val in position_str.split(',')]
        
        # Find Orientation element
        orientation_elem = root.find('.//Orientation')
        if orientation_elem is not None and orientation_elem.text:
            # Extract values from between curly braces
            text = orientation_elem.text.strip()
            if '{' in text and '}' in text:
                orientation_str = text.split('{')[1].split('}')[0]
                orientation_values = [float(val.strip()) for val in orientation_str.split(',')]
        
        return position_values, orientation_values
        
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        return None, None
    except Exception as e:
        print(f"Error in XML extraction: {e}")
        return None, None

# Current preferred method using ElementTree Element
def extract_slicer_position_orientation_from_element(element: ET.Element) -> Tuple[Optional[List[float]], Optional[List[float]]]:
    """
    Extract position and orientation data directly from an XML Element object.
    
    Use this when you already have an ET.Element (e.g., from .xml instead of .formatted_values).
    
    Args:
        element: An xml.etree.ElementTree.Element representing the IParameterList
        
    Returns:
        Tuple of (position_values, orientation_values) where each is a list of floats
        Returns (None, None) if extraction fails
    """
    try:
        position_values = None
        orientation_values = None
        
        # Find Position element - search recursively through the tree
        position_elem = element.find('.//Position')
        if position_elem is not None and position_elem.text:
            # Extract values from between curly braces
            text = position_elem.text.strip()
            if '{' in text and '}' in text:
                position_str = text.split('{')[1].split('}')[0]
                position_values = [float(val.strip()) for val in position_str.split(',')]
        
        # Find Orientation element
        orientation_elem = element.find('.//Orientation')
        if orientation_elem is not None and orientation_elem.text:
            # Extract values from between curly braces
            text = orientation_elem.text.strip()
            if '{' in text and '}' in text:
                orientation_str = text.split('{')[1].split('}')[0]
                orientation_values = [float(val.strip()) for val in orientation_str.split(',')]
        
        return position_values, orientation_values
        
    except Exception as e:
        print(f"Error extracting from Element object: {e}")
        return None, None


def slicer_to_vtk_plane(slicer: Slicer) -> pyvista.DataSet:
    """Convert the Slicer position and orientation to a ``pyvista.PolyData`` object with 
    custom metadata describing the slicer.

    Parameters
    ----------
    slicer : geoh5py.objects.slicer.Slicer
        The slicer to convert.

    Returns
    -------
    pyvista.PolyData
        The slicer geometry as a PolyData object.

    """

    slicer_params = slicer.get_data("Visual Parameters")[0].xml # type: ignore

    # Try the XML-based extraction
    position_values, orientation_values = extract_slicer_position_orientation_from_element(slicer_params)
 
    # Ensure we have valid values before proceeding
    if position_values is None or orientation_values is None:
        raise ValueError(
            "Failed to extract slicer position and orientation from Visual Parameters. "
            "Both primary and fallback methods failed."
        )

    output = pyvista.Plane(center=position_values,
                           direction=orientation_values,
                           )
    
    output = add_entity_metadata(output, slicer)
    output.field_data["normal"] = orientation_values
    output.field_data["origin"] = position_values

    return output
