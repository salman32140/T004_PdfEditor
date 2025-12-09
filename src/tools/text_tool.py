"""
Text Editing Tool
"""
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent, QPainter, QFont, QColor, QCursor
from PyQt6.QtWidgets import QInputDialog
from .base_tool import BaseTool, ToolType
from core.layer import Layer, LayerType
from typing import Optional


class TextTool(BaseTool):
    """Text insertion and editing tool"""

    def __init__(self):
        super().__init__(ToolType.TEXT)
        self.cursor = QCursor(Qt.CursorShape.IBeamCursor)
        self.click_pos: Optional[QPointF] = None
        self.current_layer: Optional[Layer] = None

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_pos = pos
            # This will trigger text input dialog in the main application
            return True
        return False

    def create_text_layer(self, page_num: int, pos: QPointF, text: str) -> Layer:
        """Create a text layer"""
        layer = Layer(LayerType.TEXT, page_num, "Text")
        layer.data = {
            'text': text,
            'x': pos.x(),
            'y': pos.y(),
            'font': self.font_name,
            'font_size': self.font_size,
            'color': self.color
        }
        layer.opacity = self.opacity
        return layer

    def get_completed_layer(self) -> Optional[Layer]:
        """Get the completed layer"""
        layer = self.current_layer
        self.current_layer = None
        return layer
