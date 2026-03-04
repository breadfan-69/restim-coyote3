import sys
import os
import tempfile
import shutil


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.pardir))
    return os.path.join(base_path, relative_path)


def extract_resources_if_needed():
    """Extract resources folder to temp directory if running from PyInstaller one-file bundle"""
    if not hasattr(sys, '_MEIPASS'):
        # Running in development mode, resources are in place
        return
    
    # Running from PyInstaller, need to extract resources
    try:
        import restim_rc  # This registers the Qt resource system
        # Use Qt resource system paths instead
        return
    except ImportError:
        pass


# Initialize resource extraction
extract_resources_if_needed()

phase_diagram_bg = resource_path("resources/phase diagram bg.svg")
phase_diagram_bg_light = resource_path("resources/phase diagram bg light.svg")
favicon = resource_path("resources/favicon.png")