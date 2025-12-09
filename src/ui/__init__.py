"""
UI module for PDF Editor
Contains all user interface components
"""
from .main_window import MainWindow
from .pdf_canvas import PDFCanvas, PDFCanvasWidget
from .interactive_canvas import InteractivePDFCanvas
from .thumbnail_panel import ThumbnailPanel
from .properties_panel import PropertiesPanel
from .text_edit_dialog import TextEditDialog
from .image_dialog import ImageDialog
from .ai_chat_widget import AIChatWidget

__all__ = [
    'MainWindow',
    'PDFCanvas',
    'PDFCanvasWidget',
    'InteractivePDFCanvas',
    'ThumbnailPanel',
    'PropertiesPanel',
    'TextEditDialog',
    'ImageDialog',
    'AIChatWidget'
]
