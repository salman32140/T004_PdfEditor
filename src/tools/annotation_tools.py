"""
Annotation Tools: Sticky Notes, Signatures, Form Fields
"""
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent, QPainter, QCursor, QPixmap
from .base_tool import BaseTool, ToolType
from core.layer import Layer, LayerType
from typing import Optional


class StickyNoteTool(BaseTool):
    """Sticky note annotation tool"""

    def __init__(self):
        super().__init__(ToolType.STICKY_NOTE)
        self.cursor = QCursor(Qt.CursorShape.PointingHandCursor)
        self.click_pos: Optional[QPointF] = None
        self.note_size = 20
        self.color = "#FFFF00"
        self.current_layer: Optional[Layer] = None

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_pos = pos
            # This will trigger note text input dialog in the main application
            return True
        return False

    def create_note_layer(self, page_num: int, pos: QPointF, note_text: str) -> Layer:
        """Create a sticky note layer"""
        layer = Layer(LayerType.STICKY_NOTE, page_num, "Sticky Note")
        layer.data = {
            'x': pos.x(),
            'y': pos.y(),
            'size': self.note_size,
            'color': self.color,
            'text': note_text
        }
        return layer

    def get_completed_layer(self) -> Optional[Layer]:
        """Get the completed layer"""
        layer = self.current_layer
        self.current_layer = None
        return layer


class SignatureTool(BaseTool):
    """Signature tool"""

    def __init__(self):
        super().__init__(ToolType.SIGNATURE)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self.signature_pixmap: Optional[QPixmap] = None
        self.signature_points = []  # For drawn signatures
        self.start_pos: Optional[QPointF] = None
        self.current_pos: Optional[QPointF] = None
        self.is_placing = False
        self.mode = "image"  # "image" or "draw"
        self.current_layer: Optional[Layer] = None

    def set_signature_image(self, pixmap: QPixmap):
        """Set signature as image"""
        self.signature_pixmap = pixmap
        self.mode = "image"

    def set_draw_mode(self):
        """Set to draw signature mode"""
        self.mode = "draw"
        self.signature_points = []

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == "image" and self.signature_pixmap:
                self.is_placing = True
                self.start_pos = pos
                self.current_pos = pos
                return True
            elif self.mode == "draw":
                self.signature_points = [(pos.x(), pos.y())]
                return True
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if self.mode == "image" and self.is_placing:
            self.current_pos = pos
            return True
        elif self.mode == "draw" and self.signature_points:
            self.signature_points.append((pos.x(), pos.y()))
            return True
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == "image" and self.is_placing:
                self.is_placing = False
                if self.start_pos and self.current_pos and self.signature_pixmap:
                    x1, y1 = self.start_pos.x(), self.start_pos.y()
                    x2, y2 = self.current_pos.x(), self.current_pos.y()

                    x = min(x1, x2)
                    y = min(y1, y2)
                    w = abs(x2 - x1)
                    h = abs(y2 - y1)

                    if w < 10 or h < 10:
                        w = self.signature_pixmap.width()
                        h = self.signature_pixmap.height()

                    layer = Layer(LayerType.SIGNATURE, page_num, "Signature")
                    layer.data = {
                        'pixmap': self.signature_pixmap,
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h
                    }

                    self.current_layer = layer
                    self.start_pos = None
                    self.current_pos = None
                    return True

            elif self.mode == "draw" and len(self.signature_points) > 1:
                layer = Layer(LayerType.SIGNATURE, page_num, "Signature")
                layer.data = {
                    'points': self.signature_points.copy(),
                    'color': '#000000',
                    'width': 2
                }
                self.current_layer = layer
                self.signature_points = []
                return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview"""
        if self.mode == "image" and self.is_placing and self.signature_pixmap:
            if self.start_pos and self.current_pos:
                x1, y1 = self.start_pos.x() * zoom, self.start_pos.y() * zoom
                x2, y2 = self.current_pos.x() * zoom, self.current_pos.y() * zoom

                x = min(x1, x2)
                y = min(y1, y2)
                w = abs(x2 - x1)
                h = abs(y2 - y1)

                if w > 10 and h > 10:
                    from PyQt6.QtCore import QRectF
                    rect = QRectF(x, y, w, h)
                    painter.setOpacity(0.7)
                    painter.drawPixmap(rect.toRect(), self.signature_pixmap)

        elif self.mode == "draw" and len(self.signature_points) > 1:
            from PyQt6.QtGui import QPen, QPainterPath
            pen = QPen(Qt.GlobalColor.black, 2 * zoom, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            path = QPainterPath()
            path.moveTo(self.signature_points[0][0] * zoom, self.signature_points[0][1] * zoom)
            for x, y in self.signature_points[1:]:
                path.lineTo(x * zoom, y * zoom)
            painter.drawPath(path)

    def get_completed_layer(self) -> Optional[Layer]:
        """Get the completed layer"""
        layer = self.current_layer
        self.current_layer = None
        return layer


class FormFieldTool(BaseTool):
    """Form field creation tool"""

    def __init__(self):
        super().__init__(ToolType.FORM_FIELD)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self.field_type = "text"  # text, checkbox, radio, dropdown, signature
        self.start_pos: Optional[QPointF] = None
        self.current_pos: Optional[QPointF] = None
        self.is_drawing = False
        self.current_layer: Optional[Layer] = None

    def set_field_type(self, field_type: str):
        """Set the type of form field to create"""
        self.field_type = field_type

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
            return True
        return False

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

                # Minimum size
                if w < 20:
                    w = 100
                if h < 10:
                    h = 30

                layer = Layer(LayerType.FORM_FIELD, page_num, f"{self.field_type.title()} Field")
                layer.data = {
                    'field_type': self.field_type,
                    'rect': [x, y, w, h],
                    'value': '',
                    'name': f'{self.field_type}_field'
                }

                self.current_layer = layer
                self.start_pos = None
                self.current_pos = None
                return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview of form field"""
        if self.is_drawing and self.start_pos and self.current_pos:
            from PyQt6.QtGui import QPen, QColor
            x1, y1 = self.start_pos.x() * zoom, self.start_pos.y() * zoom
            x2, y2 = self.current_pos.x() * zoom, self.current_pos.y() * zoom

            x = min(x1, x2)
            y = min(y1, y2)
            w = abs(x2 - x1)
            h = abs(y2 - y1)

            pen = QPen(QColor("#0000FF"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(int(x), int(y), int(w), int(h))

    def get_completed_layer(self) -> Optional[Layer]:
        """Get the completed layer"""
        layer = self.current_layer
        self.current_layer = None
        return layer
