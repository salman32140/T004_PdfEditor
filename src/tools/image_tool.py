"""
Image Insertion Tool
"""
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent, QPainter, QPixmap, QCursor
from .base_tool import BaseTool, ToolType
from core.layer import Layer, LayerType
from typing import Optional


class ImageTool(BaseTool):
    """Image insertion and manipulation tool"""

    def __init__(self):
        super().__init__(ToolType.IMAGE)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self.image_pixmap: Optional[QPixmap] = None
        self.start_pos: Optional[QPointF] = None
        self.current_pos: Optional[QPointF] = None
        self.is_placing = False
        self.current_layer: Optional[Layer] = None

    def set_image(self, pixmap: QPixmap):
        """Set the image to be placed"""
        self.image_pixmap = pixmap

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton and self.image_pixmap:
            self.is_placing = True
            self.start_pos = pos
            self.current_pos = pos
            return True
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if self.is_placing:
            self.current_pos = pos
            return True
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton and self.is_placing:
            self.is_placing = False
            if self.start_pos and self.current_pos and self.image_pixmap:
                x1, y1 = self.start_pos.x(), self.start_pos.y()
                x2, y2 = self.current_pos.x(), self.current_pos.y()

                x = min(x1, x2)
                y = min(y1, y2)
                w = abs(x2 - x1)
                h = abs(y2 - y1)

                # If size is too small, use default image size
                if w < 10 or h < 10:
                    w = self.image_pixmap.width()
                    h = self.image_pixmap.height()

                layer = Layer(LayerType.IMAGE, page_num, "Image")
                layer.data = {
                    'pixmap': self.image_pixmap,
                    'x': x,
                    'y': y,
                    'width': w,
                    'height': h
                }
                layer.opacity = self.opacity

                self.current_layer = layer
                self.start_pos = None
                self.current_pos = None
                self.image_pixmap = None  # Clear after placing
                return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview of image placement"""
        if self.is_placing and self.start_pos and self.current_pos and self.image_pixmap:
            x1, y1 = self.start_pos.x() * zoom, self.start_pos.y() * zoom
            x2, y2 = self.current_pos.x() * zoom, self.current_pos.y() * zoom

            x = min(x1, x2)
            y = min(y1, y2)
            w = abs(x2 - x1)
            h = abs(y2 - y1)

            if w > 10 and h > 10:
                from PyQt6.QtCore import QRectF
                rect = QRectF(x, y, w, h)
                painter.setOpacity(0.5)
                painter.drawPixmap(rect.toRect(), self.image_pixmap)

    def get_completed_layer(self) -> Optional[Layer]:
        """Get the completed layer"""
        layer = self.current_layer
        self.current_layer = None
        return layer
