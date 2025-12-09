"""
Interactive Image Tool
Creates image frames by drawing an area, then allows image selection
"""
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QMouseEvent, QPainter, QCursor, QPen, QColor
from .base_tool import BaseTool, ToolType
from typing import Optional


class InteractiveImageTool(BaseTool):
    """Interactive image frame creation tool - draw area then add image"""

    def __init__(self):
        super().__init__(ToolType.IMAGE)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self.start_pos: Optional[QPointF] = None
        self.current_pos: Optional[QPointF] = None
        self.is_drawing = False
        self.pending_creation = False
        self.image_frame_rect = None

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse press - start drawing image frame"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = pos
            self.current_pos = pos
            self.is_drawing = True
            self.pending_creation = False
            self.image_frame_rect = None
            return True
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse move - update frame preview"""
        if self.is_drawing and self.start_pos:
            self.current_pos = pos
            return True
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse release - finalize image frame area"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False

            if self.start_pos and pos:
                # Calculate rectangle
                x1, y1 = self.start_pos.x(), self.start_pos.y()
                x2, y2 = pos.x(), pos.y()

                # Ensure minimum size
                width = abs(x2 - x1)
                height = abs(y2 - y1)

                if width < 20:
                    width = 200  # Default width for images
                if height < 20:
                    height = 200   # Default height for images

                x = min(x1, x2)
                y = min(y1, y2)

                # Store the image frame rectangle
                self.image_frame_rect = {
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height
                }

                self.pending_creation = True
                return True

        return False

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw preview of image frame while dragging"""
        if self.is_drawing and self.start_pos and self.current_pos:
            x1 = self.start_pos.x() * zoom
            y1 = self.start_pos.y() * zoom
            x2 = self.current_pos.x() * zoom
            y2 = self.current_pos.y() * zoom

            x = min(x1, x2)
            y = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)

            # Draw dashed rectangle preview
            pen = QPen(QColor(0, 120, 215), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setOpacity(0.7)

            painter.drawRect(int(x), int(y), int(width), int(height))

            # Draw dimension text
            painter.setOpacity(1.0)
            painter.setPen(QColor(0, 120, 215))
            dim_text = f"{int(width/zoom)} x {int(height/zoom)}"
            painter.drawText(int(x + 5), int(y - 5), dim_text)

            # Draw "Image Frame" label
            painter.drawText(int(x + width/2 - 40), int(y + height/2), "Image Frame")

    def get_image_frame_rect(self):
        """Get the drawn image frame rectangle"""
        return self.image_frame_rect

    def get_pending_position(self) -> Optional[QPointF]:
        """Get position for pending image (top-left of frame)"""
        if self.pending_creation and self.image_frame_rect:
            return QPointF(self.image_frame_rect['x'], self.image_frame_rect['y'])
        return None

    def clear_pending(self):
        """Clear pending creation"""
        self.pending_creation = False
        self.is_drawing = False
        self.start_pos = None
        self.current_pos = None
        self.image_frame_rect = None
