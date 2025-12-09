"""
Core module for PDF Editor
Contains PDF document handling, layer management, and history system
"""
from .pdf_document import PDFDocument
from .layer import Layer, LayerManager, LayerType
from .history import HistoryManager, Action, ActionType, SnapshotManager
from .interactive_layer import InteractiveLayer, TextFieldLayer, ImageLayer, ImageScaleMode
from .guide_manager import Guide, GuideManager, GuideOrientation, get_guide_manager, reset_guide_manager

__all__ = [
    'PDFDocument',
    'Layer',
    'LayerManager',
    'LayerType',
    'HistoryManager',
    'Action',
    'ActionType',
    'SnapshotManager',
    'InteractiveLayer',
    'TextFieldLayer',
    'ImageLayer',
    'ImageScaleMode',
    'Guide',
    'GuideManager',
    'GuideOrientation',
    'get_guide_manager',
    'reset_guide_manager'
]
