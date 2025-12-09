"""
Base Tool Class
All editing tools inherit from this
"""
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QPainter, QCursor
from typing import Optional
from enum import Enum


class ToolType(Enum):
    """Types of tools available"""
    SELECT = "select"
    PEN = "pen"
    TEXT = "text"
    IMAGE = "image"
    SHAPE_RECTANGLE = "rectangle"
    SHAPE_ELLIPSE = "ellipse"
    SHAPE_LINE = "line"
    SHAPE_ARROW = "arrow"
    STICKY_NOTE = "sticky_note"
    SIGNATURE = "signature"
    FORM_FIELD = "form_field"


class BaseTool:
    """Base class for all editing tools"""

    def __init__(self, tool_type: ToolType):
        self.type = tool_type
        self.is_active = False
        self.cursor = QCursor(Qt.CursorShape.ArrowCursor)

        # Tool settings
        self.color = "#000000"
        self.width = 2
        self.opacity = 1.0
        self.font_size = 12
        self.font_name = "Arial"

    def activate(self):
        """Called when tool is activated"""
        self.is_active = True

    def deactivate(self):
        """Called when tool is deactivated"""
        self.is_active = False

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """
        Handle mouse press event
        Returns True if event was handled
        """
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """
        Handle mouse move event
        Returns True if event was handled
        """
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """
        Handle mouse release event
        Returns True if event was handled
        """
        return False

    def key_press(self, event: QKeyEvent) -> bool:
        """
        Handle key press event
        Returns True if event was handled
        """
        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview while tool is being used"""
        pass

    def get_cursor(self) -> QCursor:
        """Get cursor for this tool"""
        return self.cursor

    def set_color(self, color: str):
        """Set tool color"""
        self.color = color

    def set_width(self, width: int):
        """Set tool width/thickness"""
        self.width = width

    def set_opacity(self, opacity: float):
        """Set tool opacity"""
        self.opacity = opacity

    def set_font_size(self, size: int):
        """Set font size for text tools"""
        self.font_size = size

    def set_font_name(self, name: str):
        """Set font name for text tools"""
        self.font_name = name
