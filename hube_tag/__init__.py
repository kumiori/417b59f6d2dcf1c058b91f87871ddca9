"""HUBE gesture reconstruction. Rendering needs only Python's standard library.

Computer-vision dependencies are imported only by the offline pipeline modules.
"""
from .raster import render
from .animation import animate, splash

__all__ = ['render', 'animate', 'splash']
