"""
Selection and Move Tool
Draw a box to select multiple layers, then move them together
"""
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QMouseEvent, QPainter, QCursor, QPen, QColor
from .base_tool import BaseTool, ToolType
from typing import Optional, List


class SelectionTool(BaseTool):
    """Tool for selecting multiple layers with box selection and moving them"""

    def __init__(self):
        super().__init__(ToolType.SELECT)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)

        # Box selection
        self.is_drawing_box = False
        self.box_start_pos: Optional[QPointF] = None
        self.box_current_pos: Optional[QPointF] = None

        # Moving selected layers
        self.is_moving = False
        self.selected_layers: List = []
        self.move_start_pos: Optional[QPointF] = None
        self.layers_start_positions: List[tuple] = []

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse press - start box selection or start moving"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicking inside existing selection to start moving
            if self.selected_layers and self._is_point_in_selection(pos):
                # Start moving
                self.is_moving = True
                self.move_start_pos = pos
                # Store initial positions of all selected layers
                self.layers_start_positions = []
                for layer in self.selected_layers:
                    if hasattr(layer, 'data'):
                        self.layers_start_positions.append((
                            layer.data.get('x', 0),
                            layer.data.get('y', 0)
                        ))
                return True
            else:
                # Start new box selection
                self.is_drawing_box = True
                self.box_start_pos = pos
                self.box_current_pos = pos
                return True
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse move - update box or move layers"""
        if self.is_drawing_box and self.box_start_pos:
            # Update box selection
            self.box_current_pos = pos
            return True
        elif self.is_moving and self.move_start_pos:
            # Move all selected layers
            dx = pos.x() - self.move_start_pos.x()
            dy = pos.y() - self.move_start_pos.y()

            for i, layer in enumerate(self.selected_layers):
                if i < len(self.layers_start_positions):
                    start_x, start_y = self.layers_start_positions[i]
                    if hasattr(layer, 'data'):
                        layer.data['x'] = start_x + dx
                        layer.data['y'] = start_y + dy
            return True
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse release - finalize box selection or stop moving"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_drawing_box:
                # Box selection complete - will be handled by canvas
                self.is_drawing_box = False
                # Don't clear box positions yet - canvas needs them
                return True
            elif self.is_moving:
                # Moving complete
                self.is_moving = False
                self.move_start_pos = None
                self.layers_start_positions = []
                return True
        return False

    def draw_preview(self, painter: QPainter, zoom: float = 1.0):
        """Draw selection box preview - green with transparency"""
        if self.is_drawing_box and self.box_start_pos and self.box_current_pos:
            painter.save()

            # Draw selection rectangle
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

            # Green border with thicker line for visibility
            pen = QPen(QColor(0, 180, 0), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)

            # Semi-transparent green fill
            painter.setBrush(QColor(0, 200, 0, 40))  # Green with transparency
            painter.drawRect(rect)

            painter.restore()

    def get_selection_box(self) -> Optional[QRectF]:
        """Get the selection box rectangle"""
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

    def clear_box_selection(self):
        """Clear box selection state"""
        self.box_start_pos = None
        self.box_current_pos = None

    def set_selected_layers(self, layers: List):
        """Set the currently selected layers"""
        self.selected_layers = layers

    def clear_selected_layers(self):
        """Clear all selected layers"""
        self.selected_layers = []

    def _is_point_in_selection(self, point: QPointF) -> bool:
        """Check if point is inside any selected layer"""
        for layer in self.selected_layers:
            if hasattr(layer, 'get_bounds'):
                bounds = layer.get_bounds(1.0)
                if bounds and bounds.contains(point):
                    return True
        return False

    def reset(self):
        """Reset tool state"""
        self.is_drawing_box = False
        self.is_moving = False
        self.box_start_pos = None
        self.box_current_pos = None
        self.move_start_pos = None
        self.selected_layers = []
        self.layers_start_positions = []
