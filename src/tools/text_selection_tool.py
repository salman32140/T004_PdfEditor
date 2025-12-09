"""
Text Selection Tool
Allows selecting text in PDF and applying highlight, underline, strikethrough
"""
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QObject
from PyQt6.QtGui import QMouseEvent, QCursor, QPainter, QPen, QColor, QBrush
from .base_tool import BaseTool, ToolType
from enum import Enum
from typing import Optional, List, Tuple
import fitz


class TextAnnotationType(Enum):
    """Types of text annotations"""
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"


class TextSelectionTool(BaseTool):
    """Tool for selecting and annotating PDF text"""

    def __init__(self):
        super().__init__(ToolType.SELECT)
        self.cursor = QCursor(Qt.CursorShape.IBeamCursor)

        # Selection state
        self.is_selecting = False
        self.start_pos: Optional[QPointF] = None
        self.current_pos: Optional[QPointF] = None
        self.selected_rects: List[QRectF] = []  # Selected text rectangles
        self.selected_text: str = ""
        self.has_selection = False  # Track if text is currently selected

        # Annotation type (only used when applying annotation)
        self.annotation_type = TextAnnotationType.HIGHLIGHT

        # Colors
        self.highlight_color = "#FFFF00"  # Yellow
        self.underline_color = "#000000"  # Black
        self.strikethrough_color = "#FF0000"  # Red

        # PDF document reference (set by canvas)
        self.pdf_doc = None
        self.current_page = 0

    def set_annotation_type(self, ann_type: TextAnnotationType):
        """Set the annotation type"""
        self.annotation_type = ann_type

    def set_highlight_color(self, color: str):
        """Set highlight color"""
        self.highlight_color = color

    def mouse_press(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Start text selection"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = True
            self.start_pos = pos
            self.current_pos = pos
            self.current_page = page_num
            self.selected_rects = []
            self.selected_text = ""
            self.has_selection = False
            return True
        return False

    def mouse_move(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Update selection"""
        if self.is_selecting and self.start_pos:
            self.current_pos = pos
            # Update selected text rectangles
            self._update_selection(page_num)
            return True
        return False

    def mouse_release(self, event: QMouseEvent, page_num: int, pos: QPointF) -> bool:
        """Complete selection - does NOT apply annotation automatically"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.current_pos = pos
            self._update_selection(page_num)

            # Mark that we have a selection (but don't apply annotation)
            if self.selected_rects:
                self.has_selection = True
                return True  # Signal selection completed

            return True
        return False

    def has_active_selection(self) -> bool:
        """Check if there is an active text selection"""
        return self.has_selection and len(self.selected_rects) > 0

    def _update_selection(self, page_num: int):
        """Update the text selection based on drag area"""
        if not self.pdf_doc or not self.start_pos or not self.current_pos:
            return

        page = self.pdf_doc.get_page(page_num)
        if not page:
            return

        # Create selection rectangle
        x1, y1 = self.start_pos.x(), self.start_pos.y()
        x2, y2 = self.current_pos.x(), self.current_pos.y()

        # Normalize rectangle
        rect = fitz.Rect(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

        # Get text blocks in the selection area
        try:
            # Get text with character-level detail
            text_dict = page.get_text("dict", clip=rect)
            self.selected_rects = []
            self.selected_text = ""

            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_rect = fitz.Rect(span["bbox"])
                            if rect.intersects(span_rect):
                                # Add the span rectangle
                                self.selected_rects.append(QRectF(
                                    span_rect.x0, span_rect.y0,
                                    span_rect.width, span_rect.height
                                ))
                                self.selected_text += span.get("text", "") + " "
        except Exception as e:
            print(f"Error getting text selection: {e}")

    def get_selected_text(self) -> str:
        """Get the selected text"""
        return self.selected_text.strip()

    def get_selection_rects(self) -> List[QRectF]:
        """Get the selection rectangles"""
        return self.selected_rects

    def create_annotation_layer(self):
        """Create annotation layer data for the selected text"""
        if not self.selected_rects:
            return None

        return {
            'type': self.annotation_type.value,
            'rects': [(r.x(), r.y(), r.width(), r.height()) for r in self.selected_rects],
            'color': self._get_annotation_color(),
            'text': self.selected_text.strip()
        }

    def _get_annotation_color(self) -> str:
        """Get color based on annotation type"""
        if self.annotation_type == TextAnnotationType.HIGHLIGHT:
            return self.highlight_color
        elif self.annotation_type == TextAnnotationType.UNDERLINE:
            return self.underline_color
        else:
            return self.strikethrough_color

    def draw_preview(self, painter: QPainter, zoom: float):
        """Draw selection preview - shows neutral selection highlight (no annotation effect)"""
        if not self.selected_rects:
            return

        # Draw selection rectangles with neutral blue selection color
        for rect in self.selected_rects:
            scaled_rect = QRectF(
                rect.x() * zoom,
                rect.y() * zoom,
                rect.width() * zoom,
                rect.height() * zoom
            )

            # Draw neutral selection highlight (light blue, like standard text selection)
            selection_color = QColor("#3399FF")
            selection_color.setAlpha(60)
            painter.fillRect(scaled_rect, selection_color)

            # Draw subtle border around selection
            pen = QPen(QColor("#3399FF"), 1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(scaled_rect)

        # Draw selection box if currently selecting
        if self.is_selecting and self.start_pos and self.current_pos:
            pen = QPen(QColor("#0078d4"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            x1, y1 = self.start_pos.x() * zoom, self.start_pos.y() * zoom
            x2, y2 = self.current_pos.x() * zoom, self.current_pos.y() * zoom

            painter.drawRect(QRectF(
                min(x1, x2), min(y1, y2),
                abs(x2 - x1), abs(y2 - y1)
            ))

    def clear_selection(self):
        """Clear the current selection"""
        self.selected_rects = []
        self.selected_text = ""
        self.start_pos = None
        self.current_pos = None
        self.is_selecting = False
        self.has_selection = False
