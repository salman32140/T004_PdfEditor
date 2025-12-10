"""
Thumbnail Panel
Shows page thumbnails with modern animated drag-drop reordering
Also supports headings view for document navigation
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
                              QLabel, QGraphicsDropShadowEffect, QApplication,
                              QToolButton, QTreeWidget, QTreeWidgetItem, QStackedWidget)
from PyQt6.QtCore import (Qt, QSize, pyqtSignal, QThread, pyqtSlot, QPoint, QRect,
                          QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
                          QSequentialAnimationGroup, QPointF, pyqtProperty, QRectF)
from PyQt6.QtGui import (QPixmap, QPainter, QColor, QPen, QBrush, QPainterPath,
                         QTransform, QCursor, QMouseEvent)
from core import PDFDocument
from utils.icon_helper import get_icon
from typing import Optional, List, Set, Dict
import math


class ThumbnailLoader(QThread):
    """Thread for loading thumbnails in background"""
    thumbnail_ready = pyqtSignal(int, QPixmap)

    def __init__(self, pdf_doc: PDFDocument, page_num: int):
        super().__init__()
        self.pdf_doc = pdf_doc
        self.page_num = page_num

    def run(self):
        """Load thumbnail"""
        pixmap = self.pdf_doc.get_thumbnail(self.page_num, max_size=150)
        if pixmap:
            self.thumbnail_ready.emit(self.page_num, pixmap)


class AnimatedThumbnailCard(QWidget):
    """Individual thumbnail card with animation support"""

    clicked = pyqtSignal(int, object)  # page_num, event
    drag_started = pyqtSignal(int)  # page_num
    context_menu_requested = pyqtSignal(int, object)  # page_num, position

    CARD_WIDTH = 140
    CARD_HEIGHT = 190
    THUMBNAIL_HEIGHT = 160
    MARGIN = 8

    def __init__(self, page_num: int, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self._pixmap: Optional[QPixmap] = None
        self._is_selected = False
        self._is_current = False
        self._is_dragging = False
        self._is_placeholder = False  # Used during drag to show empty space

        # Animation properties
        self._lift_scale = 1.0
        self._lift_opacity = 1.0
        self._offset_y = 0.0
        self._shake_offset = 0.0
        self._shrink_scale = 1.0  # For non-dragged cards during drag

        # Visual properties
        self._shadow_blur = 5
        self._shadow_offset = 2

        self.setFixedSize(self.CARD_WIDTH + 20, self.CARD_HEIGHT + 30)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # Setup shadow effect
        self._setup_shadow()

        # Drag detection
        self._drag_start_pos: Optional[QPoint] = None
        self._drag_threshold = 10

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _setup_shadow(self):
        """Setup drop shadow effect"""
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(self._shadow_blur)
        self.shadow.setColor(QColor(0, 0, 0, 40))
        self.shadow.setOffset(0, self._shadow_offset)
        self.setGraphicsEffect(self.shadow)

    # Animation properties
    def get_lift_scale(self) -> float:
        return self._lift_scale

    def set_lift_scale(self, value: float):
        self._lift_scale = value
        self.update()

    lift_scale = pyqtProperty(float, get_lift_scale, set_lift_scale)

    def get_lift_opacity(self) -> float:
        return self._lift_opacity

    def set_lift_opacity(self, value: float):
        self._lift_opacity = value
        self.update()

    lift_opacity = pyqtProperty(float, get_lift_opacity, set_lift_opacity)

    def get_offset_y(self) -> float:
        return self._offset_y

    def set_offset_y(self, value: float):
        self._offset_y = value
        self.update()

    offset_y = pyqtProperty(float, get_offset_y, set_offset_y)

    def get_shake_offset(self) -> float:
        return self._shake_offset

    def set_shake_offset(self, value: float):
        self._shake_offset = value
        self.update()

    shake_offset = pyqtProperty(float, get_shake_offset, set_shake_offset)

    def get_shrink_scale(self) -> float:
        return self._shrink_scale

    def set_shrink_scale(self, value: float):
        self._shrink_scale = value
        self.update()

    shrink_scale = pyqtProperty(float, get_shrink_scale, set_shrink_scale)

    def set_pixmap(self, pixmap: QPixmap):
        """Set thumbnail image"""
        self._pixmap = pixmap
        self.update()

    def get_pixmap(self) -> Optional[QPixmap]:
        return self._pixmap

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.update()

    def set_current(self, current: bool):
        self._is_current = current
        self.update()

    def is_selected(self) -> bool:
        return self._is_selected or self._is_current

    def set_placeholder(self, is_placeholder: bool):
        """Set as placeholder (invisible during drag)"""
        self._is_placeholder = is_placeholder
        self.update()

    def update_page_num(self, page_num: int):
        self.page_num = page_num
        self.update()

    def animate_lift(self):
        """Animate card lifting up (for drag start)"""
        # Scale animation
        self.scale_anim = QPropertyAnimation(self, b"lift_scale")
        self.scale_anim.setDuration(150)
        self.scale_anim.setStartValue(1.0)
        self.scale_anim.setEndValue(1.08)
        self.scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Shadow enhancement
        self.shadow.setBlurRadius(20)
        self.shadow.setOffset(0, 8)
        self.shadow.setColor(QColor(0, 0, 0, 80))

        self.scale_anim.start()

    def animate_drop(self):
        """Animate card dropping back (for drag end)"""
        # Scale animation - subtle ease out, no bounce
        self.scale_anim = QPropertyAnimation(self, b"lift_scale")
        self.scale_anim.setDuration(150)
        self.scale_anim.setStartValue(self._lift_scale)
        self.scale_anim.setEndValue(1.0)
        self.scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Reset shadow
        self.shadow.setBlurRadius(5)
        self.shadow.setOffset(0, 2)
        self.shadow.setColor(QColor(0, 0, 0, 40))

        self.scale_anim.start()

    def animate_shift(self, direction: int, duration: int = 200):
        """Animate shifting up or down to make room"""
        target_offset = direction * (self.CARD_HEIGHT + 15)

        self.shift_anim = QPropertyAnimation(self, b"offset_y")
        self.shift_anim.setDuration(duration)
        self.shift_anim.setStartValue(self._offset_y)
        self.shift_anim.setEndValue(target_offset)
        self.shift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.shift_anim.start()

    def animate_reset_shift(self, duration: int = 200):
        """Reset shift animation"""
        self.shift_anim = QPropertyAnimation(self, b"offset_y")
        self.shift_anim.setDuration(duration)
        self.shift_anim.setStartValue(self._offset_y)
        self.shift_anim.setEndValue(0)
        self.shift_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.shift_anim.start()

    def animate_rejection_shake(self):
        """Shake animation for invalid drop"""
        self.shake_anim = QPropertyAnimation(self, b"shake_offset")
        self.shake_anim.setDuration(400)
        self.shake_anim.setKeyValueAt(0, 0)
        self.shake_anim.setKeyValueAt(0.2, 8)
        self.shake_anim.setKeyValueAt(0.4, -6)
        self.shake_anim.setKeyValueAt(0.6, 4)
        self.shake_anim.setKeyValueAt(0.8, -2)
        self.shake_anim.setKeyValueAt(1.0, 0)
        self.shake_anim.start()

    def animate_shrink(self):
        """Shrink card (for non-dragged cards during drag)"""
        self.shrink_anim = QPropertyAnimation(self, b"shrink_scale")
        self.shrink_anim.setDuration(150)
        self.shrink_anim.setStartValue(self._shrink_scale)
        self.shrink_anim.setEndValue(0.85)
        self.shrink_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.shrink_anim.start()

    def animate_unshrink(self):
        """Restore card to normal size"""
        self.shrink_anim = QPropertyAnimation(self, b"shrink_scale")
        self.shrink_anim.setDuration(150)
        self.shrink_anim.setStartValue(self._shrink_scale)
        self.shrink_anim.setEndValue(1.0)
        self.shrink_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.shrink_anim.start()

    def paintEvent(self, event):
        """Custom paint with animations"""
        if self._is_placeholder:
            # Don't draw anything for origin placeholder
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Apply transformations (combine lift scale and shrink scale)
        center = QPointF(self.width() / 2, self.height() / 2)
        painter.translate(center)
        combined_scale = self._lift_scale * self._shrink_scale
        painter.scale(combined_scale, combined_scale)
        painter.translate(-center)

        # Apply offset and shake
        painter.translate(self._shake_offset, self._offset_y)

        # Set opacity
        painter.setOpacity(self._lift_opacity)

        # Card background
        card_rect = QRectF(10, 5, self.CARD_WIDTH, self.CARD_HEIGHT)

        # Draw card background
        path = QPainterPath()
        path.addRoundedRect(card_rect, 8, 8)

        # Border color based on state
        if self._is_current:
            border_color = QColor(0, 120, 212)
            border_width = 3
            bg_color = QColor(255, 255, 255)
        elif self._is_selected:
            border_color = QColor(66, 165, 245)
            border_width = 2
            bg_color = QColor(227, 242, 253)
        else:
            border_color = QColor(200, 200, 200)
            border_width = 1
            bg_color = QColor(255, 255, 255)

        painter.fillPath(path, bg_color)
        painter.setPen(QPen(border_color, border_width))
        painter.drawPath(path)

        # Draw thumbnail
        thumb_rect = QRectF(15, 10, self.CARD_WIDTH - 10, self.THUMBNAIL_HEIGHT)

        if self._pixmap:
            scaled = self._pixmap.scaled(
                int(thumb_rect.width()), int(thumb_rect.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            # Center the thumbnail
            x = thumb_rect.x() + (thumb_rect.width() - scaled.width()) / 2
            y = thumb_rect.y() + (thumb_rect.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "Loading...")

        # Draw page number
        label_rect = QRectF(10, self.THUMBNAIL_HEIGHT + 15, self.CARD_WIDTH, 20)
        painter.setPen(QColor(80, 80, 80))
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, f"Page {self.page_num + 1}")

        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_start_pos and event.buttons() & Qt.MouseButton.LeftButton:
            distance = (event.pos() - self._drag_start_pos).manhattanLength()
            if distance >= self._drag_threshold:
                self.drag_started.emit(self.page_num)
                self._drag_start_pos = None
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos:
            # This was a click, not a drag
            self.clicked.emit(self.page_num, event)
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def _show_context_menu(self, pos):
        self.context_menu_requested.emit(self.page_num, self.mapToGlobal(pos))


class DragOverlay(QWidget):
    """Floating overlay widget that follows cursor during drag"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                           Qt.WindowType.WindowStaysOnTopHint)

        self._pixmaps: List[QPixmap] = []
        self._count = 0
        self._current_pos = QPointF()


    def start_drag(self, pixmaps: List[QPixmap], start_pos: QPoint):
        """Start showing drag overlay"""
        self._pixmaps = pixmaps[:3]  # Max 3 stacked
        self._count = len(pixmaps)
        self._current_pos = QPointF(start_pos)

        # Calculate size based on stack
        base_width = 100
        base_height = 130
        stack_offset = min(len(self._pixmaps) - 1, 2) * 8
        self.setFixedSize(base_width + stack_offset + 40, base_height + stack_offset + 60)

        self._update_geometry()
        self.show()
        self.raise_()

    def update_target(self, pos: QPoint):
        """Update position directly - no momentum"""
        self._current_pos = QPointF(pos)
        self._update_geometry()
        self.update()

    def _update_geometry(self):
        """Update widget geometry based on current position"""
        self.move(int(self._current_pos.x() - self.width() / 2),
                  int(self._current_pos.y() - 20))

    def stop_drag(self):
        """Stop drag overlay"""
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if not self._pixmaps:
            return

        base_width = 100
        base_height = 130

        # Draw stacked cards (back to front)
        for i in range(len(self._pixmaps) - 1, -1, -1):
            offset = i * 6
            opacity = 1.0 - i * 0.15

            painter.setOpacity(opacity)

            # Card shadow
            shadow_rect = QRectF(15 + offset + 3, 10 + offset + 5, base_width, base_height)
            painter.fillPath(self._rounded_rect_path(shadow_rect, 6), QColor(0, 0, 0, 40))

            # Card background
            card_rect = QRectF(15 + offset, 10 + offset, base_width, base_height)
            path = self._rounded_rect_path(card_rect, 6)
            painter.fillPath(path, QColor(255, 255, 255))
            painter.setPen(QPen(QColor(0, 120, 212), 2))
            painter.drawPath(path)

            # Thumbnail
            if i < len(self._pixmaps):
                thumb_rect = QRectF(20 + offset, 15 + offset, base_width - 10, base_height - 25)
                scaled = self._pixmaps[i].scaled(
                    int(thumb_rect.width()), int(thumb_rect.height()),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                x = thumb_rect.x() + (thumb_rect.width() - scaled.width()) / 2
                y = thumb_rect.y() + (thumb_rect.height() - scaled.height()) / 2
                painter.drawPixmap(int(x), int(y), scaled)

        # Draw count badge if more than shown
        if self._count > 1:
            painter.setOpacity(1.0)
            badge_size = 28
            badge_x = 15 + base_width - badge_size / 2
            badge_y = 5

            # Badge shadow
            painter.setBrush(QColor(0, 0, 0, 60))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(badge_x + 2, badge_y + 2, badge_size, badge_size))

            # Badge background
            painter.setBrush(QColor(0, 120, 212))
            painter.drawEllipse(QRectF(badge_x, badge_y, badge_size, badge_size))

            # Badge text
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            text = str(self._count) if self._count < 100 else "99+"
            painter.drawText(QRectF(badge_x, badge_y, badge_size, badge_size),
                           Qt.AlignmentFlag.AlignCenter, text)

        painter.end()

    def _rounded_rect_path(self, rect: QRectF, radius: float) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        return path


class DestinationPlaceholder(QWidget):
    """Green placeholder showing where pages will be dropped with '+' icon"""

    CARD_WIDTH = 140
    CARD_HEIGHT = 190

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(self.CARD_WIDTH + 20, self.CARD_HEIGHT + 30)
        self._num_pages = 1

    def set_num_pages(self, num: int):
        """Set number of pages being dropped"""
        self._num_pages = num
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Green color for destination
        green = QColor(40, 167, 69)

        # Draw placeholder box with dashed border
        painter.setPen(QPen(QColor(40, 167, 69, 180), 2, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(40, 167, 69, 40))
        rect = QRectF(10, 10, self.CARD_WIDTH, self.CARD_HEIGHT)
        painter.drawRoundedRect(rect, 8, 8)

        # Draw '+' icon in center
        center_x = 10 + self.CARD_WIDTH / 2
        center_y = 10 + self.CARD_HEIGHT / 2

        painter.setPen(QPen(green, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

        # Horizontal line of '+'
        plus_size = 24
        painter.drawLine(int(center_x - plus_size/2), int(center_y),
                        int(center_x + plus_size/2), int(center_y))
        # Vertical line of '+'
        painter.drawLine(int(center_x), int(center_y - plus_size/2),
                        int(center_x), int(center_y + plus_size/2))

        # Draw page count badge if multiple pages
        if self._num_pages > 1:
            badge_size = 24
            badge_x = 10 + self.CARD_WIDTH - badge_size / 2
            badge_y = 5

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(green)
            painter.drawEllipse(QRectF(badge_x, badge_y, badge_size, badge_size))

            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            text = str(self._num_pages) if self._num_pages < 100 else "99+"
            painter.drawText(QRectF(badge_x, badge_y, badge_size, badge_size),
                           Qt.AlignmentFlag.AlignCenter, text)

        painter.end()


class ThumbnailContainer(QWidget):
    """Container for animated thumbnail cards with drag-drop support"""

    pages_reordered = pyqtSignal(list, int)
    page_selected = pyqtSignal(int)
    page_context_menu = pyqtSignal(int, object)

    CARD_SPACING = 15
    PADDING = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: List[AnimatedThumbnailCard] = []
        self.selected_pages: Set[int] = set()
        self.current_page = 0
        self._last_clicked_page = -1

        # Drag state
        self._is_dragging = False
        self._drag_pages: List[int] = []
        self._drag_start_positions: Dict[int, QPoint] = {}
        self._drop_index = -1
        self._last_drop_index = -1

        # Drag overlay
        self._drag_overlay = DragOverlay()

        # Destination placeholder (green box with '+')
        self._destination_placeholder = DestinationPlaceholder(self)
        self._destination_placeholder.hide()

        # Animation group for momentum drop
        self._drop_animations: Optional[QParallelAnimationGroup] = None

        # Flag to block context menu during refresh
        self._context_menu_blocked = False

        self.setMinimumWidth(160)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

    def add_card(self, page_num: int) -> AnimatedThumbnailCard:
        """Add a new thumbnail card"""
        card = AnimatedThumbnailCard(page_num, self)
        card.clicked.connect(self._on_card_clicked)
        card.drag_started.connect(self._on_drag_started)
        card.context_menu_requested.connect(self._on_context_menu_requested)

        self.cards.append(card)
        self._update_layout()
        card.show()
        return card

    def _on_context_menu_requested(self, page_num: int, pos):
        """Handle context menu request, but only if not blocked"""
        if not self._context_menu_blocked:
            self.page_context_menu.emit(page_num, pos)

    def clear_cards(self):
        """Remove all cards"""
        for card in self.cards:
            card.deleteLater()
        self.cards.clear()
        self.selected_pages.clear()

    def update_thumbnail(self, page_num: int, pixmap: QPixmap):
        """Update a specific page's thumbnail

        Args:
            page_num: The page number to update (0-indexed)
            pixmap: The new thumbnail pixmap
        """
        if 0 <= page_num < len(self.cards):
            self.cards[page_num].set_pixmap(pixmap)
            self.cards[page_num].update()

    def block_context_menu(self, duration_ms: int = 300):
        """Block context menu for a specified duration"""
        self._context_menu_blocked = True
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(duration_ms, self._unblock_context_menu)

    def _unblock_context_menu(self):
        """Unblock context menu after refresh"""
        self._context_menu_blocked = False

    def _update_layout(self, animated: bool = False):
        """Update card positions"""
        y = self.PADDING
        for i, card in enumerate(self.cards):
            if card._is_placeholder:
                continue

            target_y = y + card._offset_y

            if animated and hasattr(card, '_position_anim'):
                # Animate to new position
                card._position_anim = QPropertyAnimation(card, b"pos")
                card._position_anim.setDuration(200)
                card._position_anim.setStartValue(card.pos())
                card._position_anim.setEndValue(QPoint(self.PADDING, int(target_y)))
                card._position_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                card._position_anim.start()
            else:
                card.move(self.PADDING, int(target_y))

            y += card.height() + self.CARD_SPACING

        # Update container size
        total_height = y + self.PADDING
        self.setMinimumHeight(total_height)

    def _on_card_clicked(self, page_num: int, event):
        """Handle card click with modifier support"""
        modifiers = event.modifiers()

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self._toggle_selection(page_num)
        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            self._select_range(page_num)
        else:
            self._clear_selection()
            self._select_page(page_num)
            self.set_current_page(page_num)
            self.page_selected.emit(page_num)

        self._last_clicked_page = page_num

    def _toggle_selection(self, page_num: int):
        if page_num in self.selected_pages:
            self.selected_pages.discard(page_num)
            if 0 <= page_num < len(self.cards):
                self.cards[page_num].set_selected(False)
        else:
            self._select_page(page_num)

    def _select_page(self, page_num: int):
        self.selected_pages.add(page_num)
        if 0 <= page_num < len(self.cards):
            self.cards[page_num].set_selected(True)

    def _select_range(self, page_num: int):
        if self._last_clicked_page < 0:
            self._select_page(page_num)
            return

        start = min(self._last_clicked_page, page_num)
        end = max(self._last_clicked_page, page_num)
        for p in range(start, end + 1):
            self._select_page(p)

    def _clear_selection(self):
        for page_num in self.selected_pages:
            if 0 <= page_num < len(self.cards):
                self.cards[page_num].set_selected(False)
        self.selected_pages.clear()

    def set_current_page(self, page_num: int):
        """Set current page"""
        if 0 <= self.current_page < len(self.cards):
            self.cards[self.current_page].set_current(False)

        self.current_page = page_num
        if 0 <= page_num < len(self.cards):
            self.cards[page_num].set_current(True)

    def _on_drag_started(self, page_num: int):
        """Handle drag start from a card"""
        if self._is_dragging:
            return

        # Get pages to drag (selected or just the clicked one)
        if page_num in self.selected_pages:
            self._drag_pages = sorted(self.selected_pages)
        else:
            self._drag_pages = [page_num]

        if not self._drag_pages:
            return

        self._is_dragging = True

        # Store original positions
        self._drag_start_positions = {p: self.cards[p].pos() for p in self._drag_pages}

        # Animate lift on dragged cards and shrink non-dragged cards
        pixmaps = []
        for i, card in enumerate(self.cards):
            if i in self._drag_pages:
                card.animate_lift()
                card.set_placeholder(True)
                if card.get_pixmap():
                    pixmaps.append(card.get_pixmap())
            else:
                # Shrink non-dragged cards
                card.animate_shrink()

        # Set destination placeholder page count
        self._destination_placeholder.set_num_pages(len(self._drag_pages))

        # Show drag overlay
        cursor_pos = QCursor.pos()
        self._drag_overlay.start_drag(pixmaps, cursor_pos)

        # Collapse the gap left by dragged cards
        self._collapse_layout()

        # Grab mouse
        self.grabMouse()
        self.setMouseTracking(True)

    def _collapse_layout(self):
        """Collapse layout to fill gaps left by dragged cards"""
        y = self.PADDING
        for i, card in enumerate(self.cards):
            if i in self._drag_pages:
                # Hide placeholder cards
                card.hide()
                continue

            # Animate card to new position
            card._collapse_anim = QPropertyAnimation(card, b"pos")
            card._collapse_anim.setDuration(150)
            card._collapse_anim.setStartValue(card.pos())
            card._collapse_anim.setEndValue(QPoint(self.PADDING, y))
            card._collapse_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            card._collapse_anim.start()

            y += card.height() + self.CARD_SPACING

        # Update container size
        self.setMinimumHeight(y + self.PADDING)

    def mouseMoveEvent(self, event):
        if not self._is_dragging:
            super().mouseMoveEvent(event)
            return

        # Update drag overlay position
        global_pos = self.mapToGlobal(event.pos())
        self._drag_overlay.update_target(global_pos)

        # Calculate drop position
        local_y = event.pos().y()
        new_drop_index = self._calculate_drop_index(local_y)

        # Check if drop position changed
        if new_drop_index != self._last_drop_index:
            self._update_drop_preview(new_drop_index)
            self._last_drop_index = new_drop_index

        self.update()

    def _calculate_drop_index(self, y: int) -> int:
        """Calculate which index to drop at based on y position"""
        # Build list of visible cards with their current positions
        visible_cards = [(i, card) for i, card in enumerate(self.cards) if i not in self._drag_pages]

        for idx, (i, card) in enumerate(visible_cards):
            card_top = card.pos().y()
            card_center = card_top + card.height() / 2

            if y < card_center:
                return i

        # After all visible cards
        return len(self.cards)

    def _update_drop_preview(self, drop_index: int):
        """Update the visual preview of where items will drop"""
        if drop_index < 0:
            self._destination_placeholder.hide()
            # Reset layout to collapsed state
            self._collapse_layout()
            return

        is_valid = self._is_valid_drop(drop_index)

        if not is_valid:
            self._destination_placeholder.hide()
            self._drop_index = drop_index
            # Reset layout to collapsed state
            self._collapse_layout()
            return

        # Calculate positions with space for destination placeholder
        y = self.PADDING
        placeholder_y = self.PADDING
        placeholder_height = self._destination_placeholder.height()

        # Get visible cards (non-dragged)
        visible_cards = [(i, card) for i, card in enumerate(self.cards) if i not in self._drag_pages]

        for idx, (i, card) in enumerate(visible_cards):
            # Check if placeholder goes before this card
            if i >= drop_index and idx == 0 or (idx > 0 and visible_cards[idx-1][0] < drop_index <= i):
                placeholder_y = y
                y += placeholder_height + self.CARD_SPACING

            # Animate card to position
            card._collapse_anim = QPropertyAnimation(card, b"pos")
            card._collapse_anim.setDuration(150)
            card._collapse_anim.setStartValue(card.pos())
            card._collapse_anim.setEndValue(QPoint(self.PADDING, y))
            card._collapse_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            card._collapse_anim.start()

            y += card.height() + self.CARD_SPACING

        # If drop is at the end
        if drop_index >= len(self.cards) or (visible_cards and drop_index > visible_cards[-1][0]):
            placeholder_y = y

        # Show green destination placeholder
        self._destination_placeholder.move(self.PADDING, int(placeholder_y))
        self._destination_placeholder.show()
        self._destination_placeholder.raise_()
        self._drop_index = drop_index

        # Update container size
        total_height = y + placeholder_height + self.PADDING
        self.setMinimumHeight(int(total_height))

    def _is_valid_drop(self, drop_index: int) -> bool:
        """Check if drop at index is valid"""
        # Can't drop in the middle of selection
        if not self._drag_pages:
            return True

        min_drag = min(self._drag_pages)
        max_drag = max(self._drag_pages)

        # Invalid if dropping within the dragged range
        return drop_index <= min_drag or drop_index > max_drag + 1

    def mouseReleaseEvent(self, event):
        if not self._is_dragging:
            super().mouseReleaseEvent(event)
            return

        self.releaseMouse()
        self._is_dragging = False
        self._destination_placeholder.hide()
        self._drag_overlay.stop_drag()

        # Unshrink all non-dragged cards
        for i, card in enumerate(self.cards):
            if i not in self._drag_pages:
                card.animate_unshrink()

        # Check if valid drop
        if self._drop_index >= 0 and self._is_valid_drop(self._drop_index):
            # Perform the reorder
            self._animate_drop_completion()
        else:
            # Invalid drop - shake and reset
            self._animate_rejection()

    def _animate_drop_completion(self):
        """Animate pages settling into new positions"""
        # Show and reset dragged cards
        for p in self._drag_pages:
            self.cards[p].show()
            self.cards[p].set_placeholder(False)
            self.cards[p].animate_drop()

        # Reset all shift offsets
        for card in self.cards:
            card._offset_y = 0

        # Emit reorder signal
        self.pages_reordered.emit(sorted(self._drag_pages), self._drop_index)

        # Reset drag state
        self._drag_pages = []
        self._drag_start_positions = {}
        self._drop_index = -1
        self._last_drop_index = -1

    def _animate_rejection(self):
        """Animate rejection for invalid drop"""
        # Show and reset dragged cards with rejection animation
        for p in self._drag_pages:
            card = self.cards[p]
            card.show()
            card.set_placeholder(False)
            card.animate_drop()
            card.animate_rejection_shake()

        # Restore original layout
        self._update_layout()

        # Reset drag state
        self._drag_pages = []
        self._drag_start_positions = {}
        self._drop_index = -1
        self._last_drop_index = -1

    def get_selected_pages(self) -> List[int]:
        if not self.selected_pages:
            return [self.current_page]
        return sorted(self.selected_pages)


class HeadingsWidget(QWidget):
    """Widget showing document headings/outline"""

    heading_clicked = pyqtSignal(int, float)  # page_num, y_position

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_doc = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(15)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                background-color: transparent;
            }
            QTreeWidget::item {
                padding: 5px 8px;
            }
            QTreeWidget::item:hover {
                background-color: #e0e0e0;
            }
            QTreeWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)
        layout.addWidget(self.tree)

    def load_headings(self, pdf_doc):
        """Load headings from PDF document"""
        self.pdf_doc = pdf_doc
        self.tree.clear()

        if not pdf_doc or not pdf_doc.doc:
            self._show_no_headings()
            return

        toc = pdf_doc.doc.get_toc()

        if not toc:
            self._show_no_headings()
            return

        # Build tree from TOC
        # TOC format: [level, title, page_num, ...]
        parent_stack = [self.tree.invisibleRootItem()]

        for entry in toc:
            level = entry[0]
            title = entry[1]
            page_num = entry[2] - 1  # Convert to 0-indexed

            # Get destination details if available
            y_pos = 0
            if len(entry) > 3 and isinstance(entry[3], dict):
                y_pos = entry[3].get('to', 0)

            # Adjust parent stack based on level
            while len(parent_stack) > level:
                parent_stack.pop()

            # Create item
            item = QTreeWidgetItem(parent_stack[-1])
            item.setText(0, title)
            item.setData(0, Qt.ItemDataRole.UserRole, (page_num, y_pos))
            item.setToolTip(0, f"Page {page_num + 1}")

            # Add to stack for potential children
            parent_stack.append(item)

        self.tree.expandAll()

    def _show_no_headings(self):
        """Show message when no headings found"""
        item = QTreeWidgetItem(self.tree)
        item.setText(0, "No headings found")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(0, QColor(128, 128, 128))

    def _on_item_clicked(self, item, column):
        """Handle heading item click"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            page_num, y_pos = data
            self.heading_clicked.emit(page_num, y_pos)


class ThumbnailPanel(QWidget):
    """Panel showing page thumbnails with modern animated drag-drop reordering"""

    page_selected = pyqtSignal(int)
    page_context_menu = pyqtSignal(int, object)
    pages_reordered = pyqtSignal(list, int)
    heading_selected = pyqtSignal(int, float)  # page_num, y_position

    VIEW_PAGES = 0
    VIEW_HEADINGS = 1

    def __init__(self, pdf_doc: PDFDocument):
        super().__init__()
        self.pdf_doc = pdf_doc
        self.loaders: List[ThumbnailLoader] = []
        self.current_page = 0
        self.current_view = self.VIEW_PAGES

        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with view toggle buttons
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(4)

        # Pages view button
        self.pages_btn = QToolButton()
        self.pages_btn.setIcon(get_icon("pages", color="#00aa00"))
        self.pages_btn.setIconSize(QSize(18, 18))
        self.pages_btn.setFixedSize(28, 28)
        self.pages_btn.setCheckable(True)
        self.pages_btn.setChecked(True)
        self.pages_btn.setToolTip("Pages View")
        self.pages_btn.clicked.connect(lambda: self._switch_view(self.VIEW_PAGES))
        self.pages_btn.setStyleSheet("""
            QToolButton {
                border: none;
                border-radius: 4px;
                padding: 4px;
                background-color: transparent;
            }
            QToolButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        header_layout.addWidget(self.pages_btn)

        # Headings view button
        self.headings_btn = QToolButton()
        self.headings_btn.setIcon(get_icon("bullets"))
        self.headings_btn.setIconSize(QSize(18, 18))
        self.headings_btn.setFixedSize(28, 28)
        self.headings_btn.setCheckable(True)
        self.headings_btn.setToolTip("Headings View")
        self.headings_btn.clicked.connect(lambda: self._switch_view(self.VIEW_HEADINGS))
        self.headings_btn.setStyleSheet("""
            QToolButton {
                border: none;
                border-radius: 4px;
                padding: 4px;
                background-color: transparent;
            }
            QToolButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        header_layout.addWidget(self.headings_btn)

        header_layout.addStretch()
        layout.addWidget(header)

        # Stacked widget for views
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Pages view
        self.pages_widget = QWidget()
        pages_layout = QVBoxLayout(self.pages_widget)
        pages_layout.setContentsMargins(0, 0, 0, 0)
        pages_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #fafafa;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #ccc;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #aaa;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.container = ThumbnailContainer()
        self.container.page_selected.connect(self._on_page_selected)
        self.container.page_context_menu.connect(self.page_context_menu.emit)
        self.container.pages_reordered.connect(self._on_pages_reordered)

        self.scroll_area.setWidget(self.container)
        pages_layout.addWidget(self.scroll_area)

        self.stack.addWidget(self.pages_widget)

        # Headings view
        self.headings_widget = HeadingsWidget()
        self.headings_widget.heading_clicked.connect(self._on_heading_clicked)
        self.stack.addWidget(self.headings_widget)

        self.setMinimumWidth(180)
        self.setMaximumWidth(250)

    def _switch_view(self, view: int):
        """Switch between pages and headings view"""
        self.current_view = view
        self.stack.setCurrentIndex(view)

        # Update button states
        self.pages_btn.setChecked(view == self.VIEW_PAGES)
        self.headings_btn.setChecked(view == self.VIEW_HEADINGS)

        # Update icon colors - green for active, default for inactive
        if view == self.VIEW_PAGES:
            self.pages_btn.setIcon(get_icon("pages", color="#00aa00"))
            self.headings_btn.setIcon(get_icon("bullets"))
        else:
            self.pages_btn.setIcon(get_icon("pages"))
            self.headings_btn.setIcon(get_icon("bullets", color="#00aa00"))

        # Load headings if switching to headings view
        if view == self.VIEW_HEADINGS:
            self.headings_widget.load_headings(self.pdf_doc)

    def _on_heading_clicked(self, page_num: int, y_pos: float):
        """Handle heading click"""
        self.current_page = page_num
        self.heading_selected.emit(page_num, y_pos)
        self.page_selected.emit(page_num)

    def load_thumbnails(self):
        """Load all thumbnails"""
        self.container.clear_cards()

        if not self.pdf_doc or not self.pdf_doc.doc:
            return

        for page_num in range(self.pdf_doc.page_count):
            card = self.container.add_card(page_num)

            # Load thumbnail in background
            loader = ThumbnailLoader(self.pdf_doc, page_num)
            loader.thumbnail_ready.connect(self._on_thumbnail_ready)
            loader.start()
            self.loaders.append(loader)

    @pyqtSlot(int, QPixmap)
    def _on_thumbnail_ready(self, page_num: int, pixmap: QPixmap):
        """Handle thumbnail loaded"""
        if 0 <= page_num < len(self.container.cards):
            self.container.cards[page_num].set_pixmap(pixmap)

    def _on_page_selected(self, page_num: int):
        """Handle page selection"""
        self.current_page = page_num
        self.page_selected.emit(page_num)

    def _on_pages_reordered(self, source_pages: List[int], target_position: int):
        """Handle page reorder"""
        self.pages_reordered.emit(source_pages, target_position)

    def set_current_page(self, page_num: int):
        """Set current page"""
        self.current_page = page_num
        self.container.set_current_page(page_num)

        # Scroll to make card visible
        if 0 <= page_num < len(self.container.cards):
            card = self.container.cards[page_num]
            self.scroll_area.ensureWidgetVisible(card)

    def get_selected_pages(self) -> List[int]:
        """Get selected pages"""
        return self.container.get_selected_pages()

    def update_thumbnail(self, page_num: int):
        """Update a specific page's thumbnail

        Args:
            page_num: The page number to update (0-indexed)
        """
        if not self.pdf_doc or not self.pdf_doc.doc:
            return

        if page_num < 0 or page_num >= self.pdf_doc.page_count:
            return

        # Render the updated thumbnail
        pixmap = self.pdf_doc.render_page(page_num, zoom=0.2)
        if pixmap:
            # Update the thumbnail in the container
            self.container.update_thumbnail(page_num, pixmap)

    def refresh(self, block_context_menu: bool = False):
        """Refresh thumbnails

        Args:
            block_context_menu: If True, block context menu for 300ms to prevent
                               spurious menu popups after page operations
        """
        if block_context_menu:
            self.container.block_context_menu(300)

        # Stop existing loaders
        for loader in self.loaders:
            if loader.isRunning():
                loader.terminate()
        self.loaders.clear()

        # Reload
        self.load_thumbnails()
