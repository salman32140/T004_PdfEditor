"""
Symbol Tool
Places unicode symbols with a single click
Left-click: Stamp the current symbol
Right-click: Open symbol selection dialog
"""
from PyQt6.QtCore import Qt, QPointF, QSize
from PyQt6.QtGui import QMouseEvent, QPainter, QCursor, QPixmap, QFont, QColor, QPen
from .base_tool import BaseTool, ToolType
from typing import Optional


class SymbolTool(BaseTool):
    """Tool for placing unicode symbols"""

    # Default symbols to choose from
    DEFAULT_SYMBOLS = ['★', '✓', '✗', '●', '■', '▲', '♥', '♦', '♠', '♣', '→', '←', '↑', '↓']

    def __init__(self):
        super().__init__(ToolType.TEXT)  # Use TEXT type as symbols are text-based
        self._current_symbol = '★'  # Default symbol
        self._symbol_size = 24  # Default size
        self._symbol_color = '#000000'  # Default color
        self.pending_creation = False
        self.click_pos: Optional[QPointF] = None
        self._show_dialog = False  # Flag to show dialog on right-click

        # Create initial cursor
        self._update_cursor()

    def _update_cursor(self):
        """Create cursor with current symbol"""
        cursor_size = 32
        pixmap = QPixmap(cursor_size, cursor_size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Draw symbol
        font = QFont("Segoe UI Symbol", 18)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(self._symbol_color))

        # Draw symbol centered
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, self._current_symbol)

        # Draw small crosshair at center
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        center = cursor_size // 2
        painter.drawLine(center - 4, center, center + 4, center)
        painter.drawLine(center, center - 4, center, center + 4)

        painter.end()

        self.cursor = QCursor(pixmap, cursor_size // 2, cursor_size // 2)

    def set_symbol(self, symbol: str):
        """Set the current symbol"""
        self._current_symbol = symbol
        self._update_cursor()

    def get_symbol(self) -> str:
        """Get current symbol"""
        return self._current_symbol

    def set_symbol_size(self, size: int):
        """Set symbol size"""
        self._symbol_size = size

    def get_symbol_size(self) -> int:
        """Get symbol size"""
        return self._symbol_size

    def set_symbol_color(self, color: str):
        """Set symbol color"""
        self._symbol_color = color
        self._update_cursor()

    def get_symbol_color(self) -> str:
        """Get symbol color"""
        return self._symbol_color

    def set_color(self, color: str):
        """Override base set_color to also update symbol color"""
        super().set_color(color)
        self.set_symbol_color(color)

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse press"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Left click - stamp symbol immediately
            self.click_pos = pos
            self.pending_creation = True
            self._show_dialog = False
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click - show symbol selection dialog
            self.click_pos = pos
            self.pending_creation = True
            self._show_dialog = True
            return True
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """No preview needed for symbol tool"""
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Handle mouse release - symbol dialog will be shown"""
        return False

    def render_preview(self, painter: QPainter, zoom: float = 1.0):
        """No preview rendering needed"""
        pass

    def reset(self):
        """Reset tool state"""
        self.pending_creation = False
        self.click_pos = None
        self._show_dialog = False

    def is_pending_creation(self) -> bool:
        """Check if symbol placement is pending"""
        return self.pending_creation

    def should_show_dialog(self) -> bool:
        """Check if dialog should be shown (right-click)"""
        return self._show_dialog

    def get_click_position(self) -> Optional[QPointF]:
        """Get the click position"""
        return self.click_pos
