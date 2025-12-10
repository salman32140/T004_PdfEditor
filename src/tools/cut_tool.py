"""
Cut Tool - Select a region and copy it to clipboard as an image
Right-click opens image insert dialog with clipboard image
"""
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QMouseEvent, QPainter, QCursor, QPen, QColor, QPixmap, QImage
from PyQt6.QtWidgets import QApplication
from .base_tool import BaseTool, ToolType
from typing import Optional


class CutTool(BaseTool):
    """Tool for selecting a region and copying it to clipboard as an image"""

    def __init__(self):
        super().__init__(ToolType.SELECT)  # Reuse SELECT type
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)

        # Box selection state
        self.is_drawing_box = False
        self.box_start_pos: Optional[QPointF] = None
        self.box_current_pos: Optional[QPointF] = None

        # Store the last captured region for right-click
        self.last_capture_rect: Optional[QRectF] = None

        # Callback for capturing region (set by canvas)
        self.capture_callback = None

        # Callback for opening image dialog with clipboard (set by canvas)
        self.open_image_dialog_callback = None

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse press - start box selection or handle right-click"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Start new box selection
            self.is_drawing_box = True
            self.box_start_pos = pos
            self.box_current_pos = pos
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            # Right-click - open image dialog with clipboard content
            if self.open_image_dialog_callback:
                self.open_image_dialog_callback(pos)
            return True
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse move - update selection box"""
        if self.is_drawing_box and self.box_start_pos:
            self.box_current_pos = pos
            return True
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse release - capture region to clipboard"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing_box:
            self.is_drawing_box = False

            # Get the selection rectangle
            if self.box_start_pos and self.box_current_pos:
                rect = self.get_selection_box()
                if rect and rect.width() > 5 and rect.height() > 5:
                    # Store the capture rect
                    self.last_capture_rect = rect

                    # Trigger capture callback if set
                    if self.capture_callback:
                        self.capture_callback(rect, page_num)

            # Clear selection box
            self.box_start_pos = None
            self.box_current_pos = None
            return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float = 1.0):
        """Draw selection box preview - blue dashed border"""
        if self.is_drawing_box and self.box_start_pos and self.box_current_pos:
            painter.save()

            # Calculate rectangle in screen coordinates
            x1 = self.box_start_pos.x() * zoom
            y1 = self.box_start_pos.y() * zoom
            x2 = self.box_current_pos.x() * zoom
            y2 = self.box_current_pos.y() * zoom

            rect = QRectF(
                min(x1, x2),
                min(y1, y2),
                abs(x2 - x1),
                abs(y2 - y1)
            )

            # Blue dashed border
            pen = QPen(QColor(0, 120, 215), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)

            # Semi-transparent blue fill
            painter.setBrush(QColor(0, 120, 215, 30))
            painter.drawRect(rect)

            # Draw corner handles
            handle_size = 6
            painter.setBrush(QColor(0, 120, 215))
            painter.setPen(QPen(QColor(255, 255, 255), 1))

            corners = [
                (rect.left(), rect.top()),
                (rect.right(), rect.top()),
                (rect.left(), rect.bottom()),
                (rect.right(), rect.bottom())
            ]

            for cx, cy in corners:
                painter.drawRect(QRectF(
                    cx - handle_size / 2,
                    cy - handle_size / 2,
                    handle_size,
                    handle_size
                ))

            painter.restore()

    def get_selection_box(self) -> Optional[QRectF]:
        """Get the selection box rectangle in page coordinates"""
        if self.box_start_pos and self.box_current_pos:
            x1 = self.box_start_pos.x()
            y1 = self.box_start_pos.y()
            x2 = self.box_current_pos.x()
            y2 = self.box_current_pos.y()

            return QRectF(
                min(x1, x2),
                min(y1, y2),
                abs(x2 - x1),
                abs(y2 - y1)
            )
        return None

    def set_capture_callback(self, callback):
        """Set callback for capturing region to clipboard"""
        self.capture_callback = callback

    def set_open_image_dialog_callback(self, callback):
        """Set callback for opening image dialog with clipboard"""
        self.open_image_dialog_callback = callback

    def get_completed_layer(self):
        """Cut tool doesn't create layers directly - returns None"""
        return None

    def reset(self):
        """Reset tool state"""
        self.is_drawing_box = False
        self.box_start_pos = None
        self.box_current_pos = None
