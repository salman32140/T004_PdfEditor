"""
Shape Drawing Tools: Rectangle, Ellipse, Line, Arrow
"""
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent, QPainter, QPen, QBrush, QColor, QCursor
from .base_tool import BaseTool, ToolType
from core.layer import Layer, LayerType
from typing import Optional
import math


class ShapeTool(BaseTool):
    """Base class for shape tools"""

    def __init__(self, tool_type: ToolType):
        super().__init__(tool_type)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self.start_pos: Optional[QPointF] = None
        self.current_pos: Optional[QPointF] = None
        self.is_drawing = False
        self.fill_color: Optional[str] = None
        self.current_layer: Optional[Layer] = None

    def set_fill_color(self, color: Optional[str]):
        """Set fill color (None for no fill)"""
        self.fill_color = color

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = True
            self.start_pos = pos
            self.current_pos = pos
            return True
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if self.is_drawing:
            self.current_pos = pos
            # Check if Shift is held for constrained drawing (straight lines for line/arrow tools)
            from PyQt6.QtCore import Qt
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Store modifier state for subclasses to use
                self._shift_held = True
            else:
                self._shift_held = False
            return True
        return False

    def get_completed_layer(self) -> Optional[Layer]:
        """Get the completed layer"""
        layer = self.current_layer
        self.current_layer = None
        return layer


class RectangleTool(ShapeTool):
    """Rectangle drawing tool"""

    def __init__(self):
        super().__init__(ToolType.SHAPE_RECTANGLE)

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            if self.start_pos and self.current_pos:
                x1, y1 = self.start_pos.x(), self.start_pos.y()
                x2, y2 = self.current_pos.x(), self.current_pos.y()

                x = min(x1, x2)
                y = min(y1, y2)
                w = abs(x2 - x1)
                h = abs(y2 - y1)

                layer = Layer(LayerType.SHAPE, page_num, "Rectangle")
                layer.data = {
                    'shape_type': 'rectangle',
                    'rect': [x, y, w, h],
                    'color': self.color,
                    'fill_color': self.fill_color,
                    'width': self.width
                }
                layer.opacity = self.opacity

                self.current_layer = layer
                self.start_pos = None
                self.current_pos = None
                return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview of rectangle"""
        if self.is_drawing and self.start_pos and self.current_pos:
            x1, y1 = self.start_pos.x() * zoom, self.start_pos.y() * zoom
            x2, y2 = self.current_pos.x() * zoom, self.current_pos.y() * zoom

            x = min(x1, x2)
            y = min(y1, y2)
            w = abs(x2 - x1)
            h = abs(y2 - y1)

            pen = QPen(QColor(self.color), self.width * zoom)
            painter.setPen(pen)

            if self.fill_color:
                brush = QBrush(QColor(self.fill_color))
                painter.setBrush(brush)

            painter.setOpacity(self.opacity)
            painter.drawRect(int(x), int(y), int(w), int(h))


class EllipseTool(ShapeTool):
    """Ellipse/Circle drawing tool"""

    def __init__(self):
        super().__init__(ToolType.SHAPE_ELLIPSE)

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            if self.start_pos and self.current_pos:
                x1, y1 = self.start_pos.x(), self.start_pos.y()
                x2, y2 = self.current_pos.x(), self.current_pos.y()

                x = min(x1, x2)
                y = min(y1, y2)
                w = abs(x2 - x1)
                h = abs(y2 - y1)

                layer = Layer(LayerType.SHAPE, page_num, "Ellipse")
                layer.data = {
                    'shape_type': 'ellipse',
                    'rect': [x, y, w, h],
                    'color': self.color,
                    'fill_color': self.fill_color,
                    'width': self.width
                }
                layer.opacity = self.opacity

                self.current_layer = layer
                self.start_pos = None
                self.current_pos = None
                return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview of ellipse"""
        if self.is_drawing and self.start_pos and self.current_pos:
            x1, y1 = self.start_pos.x() * zoom, self.start_pos.y() * zoom
            x2, y2 = self.current_pos.x() * zoom, self.current_pos.y() * zoom

            x = min(x1, x2)
            y = min(y1, y2)
            w = abs(x2 - x1)
            h = abs(y2 - y1)

            pen = QPen(QColor(self.color), self.width * zoom)
            painter.setPen(pen)

            if self.fill_color:
                brush = QBrush(QColor(self.fill_color))
                painter.setBrush(brush)

            painter.setOpacity(self.opacity)
            painter.drawEllipse(int(x), int(y), int(w), int(h))


class LineTool(ShapeTool):
    """Line drawing tool"""

    def __init__(self):
        super().__init__(ToolType.SHAPE_LINE)
        self._shift_held = False

    def _constrain_to_straight_line(self, start: QPointF, current: QPointF) -> QPointF:
        """Constrain line to horizontal or vertical if Shift is held"""
        if not self._shift_held or not start:
            return current

        dx = abs(current.x() - start.x())
        dy = abs(current.y() - start.y())

        # Determine if more horizontal or vertical
        if dx > dy:
            # Make horizontal
            return QPointF(current.x(), start.y())
        else:
            # Make vertical
            return QPointF(start.x(), current.y())

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Override to apply line constraint"""
        if self.is_drawing:
            # Check for Shift key
            from PyQt6.QtCore import Qt
            self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

            # Apply constraint if Shift is held
            self.current_pos = self._constrain_to_straight_line(self.start_pos, pos)
            return True
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            if self.start_pos and self.current_pos:
                layer = Layer(LayerType.SHAPE, page_num, "Line")
                layer.data = {
                    'shape_type': 'line',
                    'x1': self.start_pos.x(),
                    'y1': self.start_pos.y(),
                    'x2': self.current_pos.x(),
                    'y2': self.current_pos.y(),
                    'color': self.color,
                    'width': self.width
                }
                layer.opacity = self.opacity

                self.current_layer = layer
                self.start_pos = None
                self.current_pos = None
                return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview of line"""
        if self.is_drawing and self.start_pos and self.current_pos:
            pen = QPen(QColor(self.color), self.width * zoom)
            painter.setPen(pen)
            painter.setOpacity(self.opacity)

            x1 = self.start_pos.x() * zoom
            y1 = self.start_pos.y() * zoom
            x2 = self.current_pos.x() * zoom
            y2 = self.current_pos.y() * zoom

            painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class ArrowTool(ShapeTool):
    """Arrow drawing tool"""

    def __init__(self):
        super().__init__(ToolType.SHAPE_ARROW)
        self._shift_held = False

    def _constrain_to_straight_line(self, start: QPointF, current: QPointF) -> QPointF:
        """Constrain arrow to horizontal or vertical if Shift is held"""
        if not self._shift_held or not start:
            return current

        dx = abs(current.x() - start.x())
        dy = abs(current.y() - start.y())

        # Determine if more horizontal or vertical
        if dx > dy:
            # Make horizontal
            return QPointF(current.x(), start.y())
        else:
            # Make vertical
            return QPointF(start.x(), current.y())

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Override to apply arrow constraint"""
        if self.is_drawing:
            # Check for Shift key
            from PyQt6.QtCore import Qt
            self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

            # Apply constraint if Shift is held
            self.current_pos = self._constrain_to_straight_line(self.start_pos, pos)
            return True
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            if self.start_pos and self.current_pos:
                layer = Layer(LayerType.SHAPE, page_num, "Arrow")
                layer.data = {
                    'shape_type': 'arrow',
                    'x1': self.start_pos.x(),
                    'y1': self.start_pos.y(),
                    'x2': self.current_pos.x(),
                    'y2': self.current_pos.y(),
                    'color': self.color,
                    'width': self.width
                }
                layer.opacity = self.opacity

                self.current_layer = layer
                self.start_pos = None
                self.current_pos = None
                return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview of arrow"""
        if self.is_drawing and self.start_pos and self.current_pos:
            pen = QPen(QColor(self.color), self.width * zoom)
            painter.setPen(pen)
            painter.setOpacity(self.opacity)

            x1 = self.start_pos.x() * zoom
            y1 = self.start_pos.y() * zoom
            x2 = self.current_pos.x() * zoom
            y2 = self.current_pos.y() * zoom

            # Draw line
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            # Draw arrowhead
            angle = math.atan2(y2 - y1, x2 - x1)
            arrow_size = 10 * zoom

            arrow_p1_x = x2 - arrow_size * math.cos(angle - math.pi / 6)
            arrow_p1_y = y2 - arrow_size * math.sin(angle - math.pi / 6)
            arrow_p2_x = x2 - arrow_size * math.cos(angle + math.pi / 6)
            arrow_p2_y = y2 - arrow_size * math.sin(angle + math.pi / 6)

            from PyQt6.QtGui import QPainterPath
            path = QPainterPath()
            path.moveTo(x2, y2)
            path.lineTo(arrow_p1_x, arrow_p1_y)
            path.lineTo(arrow_p2_x, arrow_p2_y)
            path.closeSubpath()

            painter.fillPath(path, QColor(self.color))
