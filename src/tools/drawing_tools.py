"""
Drawing Tools: Pen
"""
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent, QPainter, QPen, QColor, QCursor, QPainterPath
from .base_tool import BaseTool, ToolType
from core.layer import Layer, LayerType
from typing import List, Optional


class PenTool(BaseTool):
    """Freehand drawing tool"""

    def __init__(self):
        super().__init__(ToolType.PEN)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self.current_points: List[tuple] = []
        self.is_drawing = False
        self.current_layer: Optional[Layer] = None

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = True
            self.current_points = [(pos.x(), pos.y())]
            return True
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if self.is_drawing:
            self.current_points.append((pos.x(), pos.y()))
            return True
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            if len(self.current_points) > 1:
                # Create a layer for this drawing
                self.current_layer = Layer(LayerType.DRAWING, page_num)
                self.current_layer.data = {
                    'points': self.current_points.copy(),
                    'color': self.color,
                    'width': self.width
                }
                self.current_layer.opacity = self.opacity
                self.current_points.clear()
                return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview of current stroke"""
        if self.is_drawing and len(self.current_points) > 1:
            pen = QPen(QColor(self.color), self.width * zoom, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setOpacity(self.opacity)

            path = QPainterPath()
            path.moveTo(self.current_points[0][0] * zoom, self.current_points[0][1] * zoom)
            for x, y in self.current_points[1:]:
                path.lineTo(x * zoom, y * zoom)

            painter.drawPath(path)

    def get_completed_layer(self) -> Optional[Layer]:
        """Get the completed layer"""
        layer = self.current_layer
        self.current_layer = None
        return layer
