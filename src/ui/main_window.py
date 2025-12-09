"""
Main Window
Application main window with menus, toolbars, and panels
"""
from PyQt6.QtWidgets import (QMainWindow, QToolBar, QStatusBar, QFileDialog,
                              QMessageBox, QMenu, QLabel, QComboBox, QApplication,
                              QDockWidget, QVBoxLayout, QHBoxLayout, QWidget, QInputDialog, QScrollArea,
                              QTabWidget, QTabBar, QFrame, QPushButton, QToolButton, QWidgetAction,
                              QGraphicsDropShadowEffect, QLineEdit)
from PyQt6.QtCore import Qt, QSize, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QPixmap, QCursor, QColor, QPainter, QPen, QFont, QFontMetrics
from core import PDFDocument, LayerManager, HistoryManager
from core.interactive_layer import TextFieldLayer
from tools import (PenTool, RectangleTool, EllipseTool,
                   LineTool, ArrowTool, ImageTool, SelectionTool, TextSelectionTool, TextAnnotationType)
from tools.interactive_text_tool import InteractiveTextTool
from tools.interactive_image_tool import InteractiveImageTool
from tools.symbol_tool import SymbolTool
from .interactive_canvas import InteractivePDFCanvas
from .text_edit_dialog import TextEditDialog
from .thumbnail_panel import ThumbnailPanel
from .properties_panel import PropertiesPanel
from .ai_chat_widget import AIChatWidget
from utils.settings import Settings
from utils.export import PDFExporter
from utils.icon_helper import get_icon
import os


class ShapeToolMenu(QWidget):
    """Floating submenu for shape tool selection"""

    tool_selected = pyqtSignal(str, str)  # tool_name, icon_name

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)

        # Shape tools configuration
        self.shape_tools = [
            ('rectangle', 'rectangle', 'Rectangle'),
            ('ellipse', 'circle', 'Circle'),
            ('line', 'line', 'Line'),
            ('arrow', 'arrow', 'Arrow'),
        ]

        self.setup_ui()

    def setup_ui(self):
        """Setup the submenu UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Create container widget with styled background
        container = QWidget()
        container.setObjectName("shapeMenuContainer")
        container.setStyleSheet("""
            #shapeMenuContainer {
                background-color: #3c3c3c;
                border-radius: 8px;
                border: 1px solid #555555;
            }
        """)

        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(6, 6, 6, 6)
        container_layout.setSpacing(4)

        # Create tool buttons
        for tool_name, icon_name, tooltip in self.shape_tools:
            btn = QToolButton()
            btn.setIcon(get_icon(icon_name))
            btn.setIconSize(QSize(28, 28))
            btn.setFixedSize(40, 40)
            btn.setToolTip(tooltip)
            btn.setStyleSheet("""
                QToolButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                    padding: 4px;
                }
                QToolButton:hover {
                    background-color: #505050;
                }
                QToolButton:pressed {
                    background-color: #0078d4;
                }
            """)
            btn.clicked.connect(lambda checked, t=tool_name, i=icon_name: self._on_tool_clicked(t, i))
            container_layout.addWidget(btn)

        layout.addWidget(container)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(Qt.GlobalColor.black)
        container.setGraphicsEffect(shadow)

    def _on_tool_clicked(self, tool_name: str, icon_name: str):
        """Handle tool button click"""
        self.tool_selected.emit(tool_name, icon_name)
        self.hide()

    def show_at(self, pos: QPoint):
        """Show menu at position with animation"""
        self.move(pos)
        self.show()

        # Fade-in animation
        self.setWindowOpacity(0)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(150)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()


class ShapeToolButton(QToolButton):
    """Unified shape tool button with long-press submenu"""

    tool_changed = pyqtSignal(str)  # tool_name

    LONG_PRESS_DURATION = 400  # ms for long-press detection

    def __init__(self, parent=None):
        super().__init__(parent)

        # Default to rectangle tool
        self.current_tool = 'rectangle'
        self.current_icon_name = 'rectangle'
        self.is_active = False

        # Long-press timer
        self.long_press_timer = QTimer()
        self.long_press_timer.setSingleShot(True)
        self.long_press_timer.timeout.connect(self._on_long_press)

        # Track if we triggered long-press (to prevent normal click)
        self.long_press_triggered = False

        # Setup UI
        self.setIcon(get_icon('tools'))
        self.setIconSize(QSize(32, 32))
        self.setToolTip("Shape Tool (Hold for options)")
        self.setCheckable(True)

        # Add small indicator arrow
        self.setStyleSheet("""
            QToolButton {
                padding-right: 2px;
            }
            QToolButton::menu-indicator {
                image: none;
                width: 0px;
            }
        """)

        # Create submenu
        self.shape_menu = ShapeToolMenu()
        self.shape_menu.tool_selected.connect(self._on_submenu_tool_selected)

    def _on_submenu_tool_selected(self, tool_name: str, icon_name: str):
        """Handle tool selection from submenu"""
        self.current_tool = tool_name
        self.current_icon_name = icon_name
        self.setChecked(True)
        self.is_active = True
        self._update_icon()
        self.tool_changed.emit(tool_name)

    def _update_icon(self):
        """Update icon based on current state"""
        if self.is_active:
            self.setIcon(get_icon(self.current_icon_name, color='#00c000'))
        else:
            self.setIcon(get_icon(self.current_icon_name))

    def set_active(self, active: bool):
        """Set whether this tool is currently active"""
        self.is_active = active
        self.setChecked(active)
        self._update_icon()

    def mousePressEvent(self, event):
        """Handle mouse press - start long-press timer"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.long_press_triggered = False
            self.long_press_timer.start(self.LONG_PRESS_DURATION)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release - check if normal click"""
        self.long_press_timer.stop()

        if event.button() == Qt.MouseButton.LeftButton and not self.long_press_triggered:
            # Normal click - activate current/last tool
            self.is_active = True
            self.setChecked(True)
            self._update_icon()
            self.tool_changed.emit(self.current_tool)

        super().mouseReleaseEvent(event)

    def _on_long_press(self):
        """Handle long press - show submenu"""
        self.long_press_triggered = True

        # Calculate position for submenu (below and slightly to the right of button)
        global_pos = self.mapToGlobal(QPoint(0, self.height() + 5))

        # If toolbar is on left, show menu to the right
        if self.parent():
            toolbar = self.parent()
            if hasattr(toolbar, 'orientation') and callable(toolbar.orientation):
                if toolbar.orientation() == Qt.Orientation.Vertical:
                    global_pos = self.mapToGlobal(QPoint(self.width() + 5, 0))

        self.shape_menu.show_at(global_pos)

    def set_tool_externally(self, tool_name: str, icon_name: str):
        """Set tool from external source (e.g., when another shape tool is clicked elsewhere)"""
        if tool_name in ['rectangle', 'ellipse', 'line', 'arrow']:
            self.current_tool = tool_name
            self.current_icon_name = icon_name
            self._update_icon()


class RulerWidget(QWidget):
    """Widget that displays a ruler (horizontal or vertical)"""

    RULER_SIZE = 20  # Width/height of the ruler

    def __init__(self, orientation: Qt.Orientation, parent=None):
        super().__init__(parent)
        self.orientation = orientation
        self.zoom = 1.0
        self.scroll_offset = 0
        self.vertical_scroll_offset = 0  # Vertical scroll for horizontal ruler to determine current page
        self.canvas_offset = 0  # Offset of canvas within scroll area (for centering)
        self.vertical_canvas_offset = 0  # Vertical canvas offset for horizontal ruler
        self.page_size = (612, 792)  # Current page size in points
        self.continuous_view = False  # Whether in continuous view mode
        self.page_infos = []  # List of (offset_pixels, page_width_points, page_height_points) for each page

        if orientation == Qt.Orientation.Horizontal:
            self.setFixedHeight(self.RULER_SIZE)
        else:
            self.setFixedWidth(self.RULER_SIZE)

        # Background is painted in paintEvent based on theme

    def set_zoom(self, zoom: float):
        """Update zoom level"""
        self.zoom = zoom
        self.update()

    def set_scroll_offset(self, offset: int):
        """Update scroll offset"""
        self.scroll_offset = offset
        self.update()

    def set_page_infos(self, page_infos: list):
        """Set page info list: [(offset_pixels, page_width_points, page_height_points), ...]"""
        self.page_infos = page_infos
        self.update()

    def set_canvas_offset(self, offset: int):
        """Set canvas offset within scroll area (for centering)"""
        self.canvas_offset = offset
        self.update()

    def set_vertical_scroll_offset(self, offset: int):
        """Set vertical scroll offset (used by horizontal ruler to determine current page)"""
        self.vertical_scroll_offset = offset
        self.update()

    def set_vertical_canvas_offset(self, offset: int):
        """Set vertical canvas offset (used by horizontal ruler for page detection)"""
        self.vertical_canvas_offset = offset
        self.update()

    def set_continuous_view(self, enabled: bool):
        """Set continuous view mode"""
        self.continuous_view = enabled
        self.update()

    def set_page_size(self, width: float, height: float):
        """Update current page dimensions"""
        self.page_size = (width, height)
        self.update()

    def paintEvent(self, event):
        """Paint the ruler"""
        from utils.icon_helper import is_dark_theme

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Colors - adapt to theme
        if is_dark_theme():
            bg_color = QColor("#2b2b2b")
            tick_color = QColor("#FFFFFF")
            text_color = QColor("#FFFFFF")
        else:
            bg_color = QColor("#e0e0e0")
            tick_color = QColor("#000000")
            text_color = QColor("#000000")

        # Fill background
        painter.fillRect(self.rect(), bg_color)

        # Font for ruler numbers - smaller size
        font = QFont("Arial", 5)
        painter.setFont(font)
        metrics = QFontMetrics(font)

        # Calculate tick spacing based on zoom
        nice_intervals = [10, 25, 50, 100, 200, 500, 1000]
        major_tick_spacing = 50
        for interval in nice_intervals:
            if interval * self.zoom >= 40:
                major_tick_spacing = interval
                break

        minor_ticks_per_major = 5
        minor_tick_spacing = major_tick_spacing / minor_ticks_per_major

        if self.orientation == Qt.Orientation.Horizontal:
            self._paint_horizontal(painter, metrics, major_tick_spacing, minor_tick_spacing, tick_color, text_color)
        else:
            self._paint_vertical(painter, metrics, major_tick_spacing, minor_tick_spacing, tick_color, text_color)

    def _paint_horizontal(self, painter, metrics, major_spacing, minor_spacing, tick_color, text_color):
        """Paint horizontal ruler - 0 starts at each page's left edge"""
        ruler_height = self.height()

        # Draw bottom border line
        painter.setPen(QPen(tick_color, 1))
        painter.drawLine(0, ruler_height - 1, self.width(), ruler_height - 1)

        if self.continuous_view and self.page_infos:
            # In continuous view, find which page is currently at the top of viewport
            # and use that page's width for the horizontal ruler
            current_page_width = self.page_size[0]  # Default

            # Find the page that is currently visible at the top of the viewport
            # The viewport top in canvas coordinates
            viewport_top = self.vertical_scroll_offset - self.vertical_canvas_offset

            for i, (page_offset_px, page_width_pts, page_height_pts) in enumerate(self.page_infos):
                page_top = page_offset_px
                page_bottom = page_offset_px + int(page_height_pts * self.zoom)

                # Check if this page is visible at the top of viewport
                if page_top <= viewport_top < page_bottom:
                    current_page_width = page_width_pts
                    break
                # If viewport is above first page, use first page
                elif i == 0 and viewport_top < page_top:
                    current_page_width = page_width_pts
                    break
                # If this is the last page and viewport is past it, use last page
                elif i == len(self.page_infos) - 1:
                    current_page_width = page_width_pts

            # Page starts at canvas_offset in viewport, subtract horizontal scroll
            page_screen_start = self.canvas_offset - self.scroll_offset

            # Draw ticks for current page (0 = page left edge)
            x = 0
            while x <= current_page_width:
                screen_x = page_screen_start + int(x * self.zoom)
                if -50 <= screen_x <= self.width() + 50:
                    is_major = abs(x % major_spacing) < 0.001 or abs(major_spacing - (x % major_spacing)) < 0.001
                    tick_height = 8 if is_major else 4

                    painter.setPen(QPen(tick_color, 1))
                    painter.drawLine(screen_x, ruler_height - tick_height, screen_x, ruler_height - 1)

                    # Draw number at major ticks
                    if is_major:
                        label = str(int(x))
                        text_width = metrics.horizontalAdvance(label)
                        painter.setPen(text_color)
                        painter.drawText(screen_x - text_width // 2, ruler_height - 9, label)

                x += minor_spacing
        else:
            # Single page mode
            page_width = self.page_size[0]

            # Page starts at canvas_offset in viewport, subtract horizontal scroll
            page_screen_start = self.canvas_offset - self.scroll_offset

            # Draw ticks relative to page start (0 = page left edge)
            x = 0
            while x <= page_width:
                screen_x = page_screen_start + int(x * self.zoom)
                if -50 <= screen_x <= self.width() + 50:
                    is_major = abs(x % major_spacing) < 0.001 or abs(major_spacing - (x % major_spacing)) < 0.001
                    tick_height = 8 if is_major else 4

                    painter.setPen(QPen(tick_color, 1))
                    painter.drawLine(screen_x, ruler_height - tick_height, screen_x, ruler_height - 1)

                    # Draw number at major ticks
                    if is_major:
                        label = str(int(x))
                        text_width = metrics.horizontalAdvance(label)
                        painter.setPen(text_color)
                        painter.drawText(screen_x - text_width // 2, ruler_height - 9, label)

                x += minor_spacing

    def _paint_vertical(self, painter, metrics, major_spacing, minor_spacing, tick_color, text_color):
        """Paint vertical ruler - 0 starts at each page's top edge"""
        ruler_width = self.width()
        char_height = metrics.height()

        # Draw right border line
        painter.setPen(QPen(tick_color, 1))
        painter.drawLine(ruler_width - 1, 0, ruler_width - 1, self.height())

        if self.page_infos:
            # Draw ruler for each page (works for both continuous and single page)
            for page_offset_px, page_width_pts, page_height_pts in self.page_infos:
                # page_offset_px is already in zoomed pixels
                # Calculate where this page starts on screen (add canvas_offset for centering)
                page_screen_start = self.canvas_offset + page_offset_px - self.scroll_offset

                # Draw ticks for this page (0 = page top edge)
                y = 0
                while y <= page_height_pts:
                    screen_y = page_screen_start + int(y * self.zoom)
                    if -50 <= screen_y <= self.height() + 50:
                        is_major = abs(y % major_spacing) < 0.001 or abs(major_spacing - (y % major_spacing)) < 0.001
                        tick_width = 8 if is_major else 4

                        painter.setPen(QPen(tick_color, 1))
                        painter.drawLine(ruler_width - tick_width, screen_y, ruler_width - 1, screen_y)

                        # Draw number at major ticks - vertically stacked characters
                        if is_major:
                            label = str(int(y))
                            painter.setPen(text_color)
                            # Draw each character stacked vertically
                            for i, char in enumerate(label):
                                char_x = 2
                                char_y = screen_y + 2 + (i * char_height)
                                painter.drawText(char_x, char_y + metrics.ascent(), char)

                    y += minor_spacing
        else:
            # Fallback: single page at origin
            page_height = self.page_size[1]
            page_screen_start = self.canvas_offset - self.scroll_offset

            y = 0
            while y <= page_height:
                screen_y = page_screen_start + int(y * self.zoom)
                if -50 <= screen_y <= self.height() + 50:
                    is_major = abs(y % major_spacing) < 0.001 or abs(major_spacing - (y % major_spacing)) < 0.001
                    tick_width = 8 if is_major else 4

                    painter.setPen(QPen(tick_color, 1))
                    painter.drawLine(ruler_width - tick_width, screen_y, ruler_width - 1, screen_y)

                    if is_major:
                        label = str(int(y))
                        painter.setPen(text_color)
                        # Draw each character stacked vertically
                        for i, char in enumerate(label):
                            char_x = 2
                            char_y = screen_y + 2 + (i * char_height)
                            painter.drawText(char_x, char_y + metrics.ascent(), char)

                y += minor_spacing


class RulerContainer(QWidget):
    """Container widget that wraps a scroll area with rulers"""

    def __init__(self, scroll_area: QScrollArea, canvas_widget, parent=None):
        super().__init__(parent)
        self.scroll_area = scroll_area
        self.canvas_widget = canvas_widget
        self.rulers_visible = True

        # Create rulers
        self.h_ruler = RulerWidget(Qt.Orientation.Horizontal)
        self.v_ruler = RulerWidget(Qt.Orientation.Vertical)

        # Corner widget (where rulers meet)
        from utils.icon_helper import is_dark_theme
        self.corner = QWidget()
        self.corner.setFixedSize(RulerWidget.RULER_SIZE, RulerWidget.RULER_SIZE)
        corner_bg = "#2b2b2b" if is_dark_theme() else "#e0e0e0"
        self.corner.setStyleSheet(f"background-color: {corner_bg};")

        # Layout
        from PyQt6.QtWidgets import QGridLayout
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self.corner, 0, 0)
        layout.addWidget(self.h_ruler, 0, 1)
        layout.addWidget(self.v_ruler, 1, 0)
        layout.addWidget(self.scroll_area, 1, 1)

        # Connect scroll signals to update rulers
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self._on_h_scroll)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_v_scroll)

        # Connect canvas signals
        if hasattr(canvas_widget, 'zoom_changed'):
            canvas_widget.zoom_changed.connect(self._on_zoom_changed)
        if hasattr(canvas_widget, 'page_changed'):
            canvas_widget.page_changed.connect(self._on_page_changed)
        if hasattr(canvas_widget, 'continuous_view_changed'):
            canvas_widget.continuous_view_changed.connect(self._on_continuous_view_changed)

        # Initialize rulers with current zoom
        self.h_ruler.set_zoom(canvas_widget.zoom)
        self.v_ruler.set_zoom(canvas_widget.zoom)

        # Initialize vertical scroll for horizontal ruler
        self.h_ruler.set_vertical_scroll_offset(self.scroll_area.verticalScrollBar().value())

    def _on_h_scroll(self, value):
        """Handle horizontal scroll"""
        self.h_ruler.set_scroll_offset(value)
        self._update_canvas_offset()

    def _on_v_scroll(self, value):
        """Handle vertical scroll"""
        self.v_ruler.set_scroll_offset(value)
        # Also update horizontal ruler with vertical scroll (for continuous view page detection)
        self.h_ruler.set_vertical_scroll_offset(value)
        self._update_canvas_offset()

    def _on_zoom_changed(self, zoom):
        """Handle zoom change"""
        self.h_ruler.set_zoom(zoom)
        self.v_ruler.set_zoom(zoom)
        self._update_page_size()
        self._update_page_offsets()
        self._update_canvas_offset()

    def _on_page_changed(self, page_num):
        """Handle page change"""
        self._update_page_size()
        self._update_page_offsets()
        self._update_canvas_offset()

    def _on_continuous_view_changed(self, enabled):
        """Handle continuous view mode change"""
        self._update_page_offsets()
        self._update_canvas_offset()
        # Update vertical scroll offset for horizontal ruler
        self.h_ruler.set_vertical_scroll_offset(self.scroll_area.verticalScrollBar().value())
        # Hide vertical ruler in continuous view (only show in single page view)
        self._update_vertical_ruler_visibility()

    def _update_canvas_offset(self):
        """Update the canvas offset within the scroll area (for centering)"""
        # Get the position of the canvas widget within the scroll area viewport
        canvas = self.canvas_widget
        viewport = self.scroll_area.viewport()

        if canvas and viewport:
            # Calculate offset - canvas may be centered if smaller than viewport
            canvas_pos = canvas.mapTo(viewport, canvas.rect().topLeft())
            self.h_ruler.set_canvas_offset(canvas_pos.x())
            self.v_ruler.set_canvas_offset(canvas_pos.y())
            # Also pass vertical canvas offset to horizontal ruler for page detection
            self.h_ruler.set_vertical_canvas_offset(canvas_pos.y())

    def _update_page_size(self):
        """Update ruler page size from canvas"""
        if hasattr(self.canvas_widget, 'pdf_doc') and self.canvas_widget.pdf_doc.doc:
            page_size = self.canvas_widget.pdf_doc.get_page_size(self.canvas_widget.current_page)
            if page_size:
                self.h_ruler.set_page_size(page_size[0], page_size[1])
                self.v_ruler.set_page_size(page_size[0], page_size[1])

    def _update_page_offsets(self):
        """Update page offsets for rulers (especially for continuous view)"""
        if not hasattr(self.canvas_widget, 'pdf_doc') or not self.canvas_widget.pdf_doc.doc:
            return

        pdf_doc = self.canvas_widget.pdf_doc
        is_continuous = hasattr(self.canvas_widget, 'continuous_view') and self.canvas_widget.continuous_view

        # Update continuous view state on rulers
        self.h_ruler.set_continuous_view(is_continuous)
        self.v_ruler.set_continuous_view(is_continuous)

        # Build page info list: [(offset_pixels, page_width_points, page_height_points), ...]
        page_infos = []

        if is_continuous:
            # Get page offsets from canvas (already in zoomed pixels)
            canvas_offsets = getattr(self.canvas_widget, 'page_offsets', [])
            for page_num in range(pdf_doc.page_count):
                page_size = pdf_doc.get_page_size(page_num)
                if page_size and page_num < len(canvas_offsets):
                    page_infos.append((canvas_offsets[page_num], page_size[0], page_size[1]))
        else:
            # Single page mode - page starts at 0
            page_size = pdf_doc.get_page_size(self.canvas_widget.current_page)
            if page_size:
                page_infos.append((0, page_size[0], page_size[1]))

        self.h_ruler.set_page_infos(page_infos)
        self.v_ruler.set_page_infos(page_infos)

    def _update_vertical_ruler_visibility(self):
        """Update vertical ruler visibility based on view mode"""
        is_continuous = hasattr(self.canvas_widget, 'continuous_view') and self.canvas_widget.continuous_view
        # Vertical ruler only visible in single page view when rulers are enabled
        self.v_ruler.setVisible(self.rulers_visible and not is_continuous)

    def set_rulers_visible(self, visible: bool):
        """Show or hide rulers"""
        self.rulers_visible = visible
        self.h_ruler.setVisible(visible)
        # Vertical ruler only visible in single page view
        self._update_vertical_ruler_visibility()
        self.corner.setVisible(visible)

    def is_rulers_visible(self) -> bool:
        """Check if rulers are visible"""
        return self.rulers_visible

    def update_rulers(self):
        """Force update of rulers"""
        self._update_page_size()
        self._update_page_offsets()
        self._update_canvas_offset()
        self.h_ruler.set_zoom(self.canvas_widget.zoom)
        self.h_ruler.set_vertical_scroll_offset(self.scroll_area.verticalScrollBar().value())
        self.v_ruler.set_zoom(self.canvas_widget.zoom)
        # Ensure vertical ruler visibility is correct
        self._update_vertical_ruler_visibility()


class PDFTab:
    """Container for a single PDF document and its associated components"""

    def __init__(self, parent):
        self.pdf_doc = PDFDocument()
        self.layer_manager = LayerManager()
        self.history_manager = HistoryManager()
        self.exporter = PDFExporter(self.pdf_doc, self.layer_manager)
        self.file_path = None
        self.is_translated = False  # Flag to indicate if document was generated via translation

        # Create canvas
        self.canvas_widget = InteractivePDFCanvas(self.pdf_doc, self.layer_manager, self.history_manager)

        # Wrap in scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas_widget)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2b2b2b;
                border: none;
            }
        """)

        # Wrap scroll area with rulers
        self.ruler_container = RulerContainer(self.scroll_area, self.canvas_widget)


class ClickablePageLabel(QLabel):
    """A page label that becomes editable when clicked"""

    page_requested = pyqtSignal(int)  # Emits the requested page number (0-indexed)

    def __init__(self, text="Page: 0 / 0", parent=None):
        super().__init__(text, parent)
        self._current_page = 0
        self._total_pages = 0
        self._editing = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Overlay line edit (shown when editing)
        self.line_edit = QLineEdit(self)
        self.line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.line_edit.hide()
        self.line_edit.returnPressed.connect(self._on_edit_finished)
        self.line_edit.editingFinished.connect(self._on_edit_finished)

    def setText(self, text: str):
        """Set the label text and parse page info"""
        super().setText(text)
        # Parse "Page: X / Y" format
        try:
            parts = text.replace("Page:", "").strip().split("/")
            if len(parts) == 2:
                self._current_page = int(parts[0].strip())
                self._total_pages = int(parts[1].strip())
        except (ValueError, IndexError):
            pass

    def mousePressEvent(self, event):
        """Switch to edit mode when clicked"""
        if self._total_pages <= 0 or self._editing:
            return

        self._editing = True

        # Position line edit over the page number part
        text = self.text()
        prefix = "Page: "
        fm = self.fontMetrics()
        prefix_width = fm.horizontalAdvance(prefix)

        # Calculate width for the number
        num_width = fm.horizontalAdvance(str(self._total_pages)) + 10

        self.line_edit.setGeometry(prefix_width, 0, num_width, self.height())
        self.line_edit.setText(str(self._current_page))
        self.line_edit.show()
        self.line_edit.setFocus()
        self.line_edit.selectAll()

    def _on_edit_finished(self):
        """Handle edit completion"""
        if not self._editing:
            return

        self._editing = False
        self.line_edit.hide()

        try:
            page_num = int(self.line_edit.text())
            # Clamp to valid range (1 to total_pages for user, 0-indexed internally)
            page_num = max(1, min(page_num, self._total_pages))
            # Emit 0-indexed page number
            self.page_requested.emit(page_num - 1)
        except ValueError:
            pass  # Invalid input, just revert


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Settings
        self.settings = Settings()

        # Tabs for multiple documents
        self.tabs: list[PDFTab] = []
        self.current_tab_index = -1

        # Tools (shared across all tabs)
        self.tools = {
            'select': SelectionTool(),
            'pen': PenTool(),
            'selecttext': TextSelectionTool(),
            'rectangle': RectangleTool(),
            'ellipse': EllipseTool(),
            'line': LineTool(),
            'arrow': ArrowTool(),
            'text': InteractiveTextTool(),
            'image': InteractiveImageTool(),
            'symbol': SymbolTool()
        }

        self.current_tool = None

        self.setup_ui()
        self.connect_signals()
        self.apply_settings()

        self.setWindowTitle("PDF Editor - Professional PDF Editing Tool")
        self.resize(1400, 900)

    @property
    def current_tab(self) -> PDFTab:
        """Get current active tab"""
        if 0 <= self.current_tab_index < len(self.tabs):
            return self.tabs[self.current_tab_index]
        return None

    @property
    def pdf_doc(self):
        """Get current PDF document"""
        tab = self.current_tab
        return tab.pdf_doc if tab else None

    @property
    def layer_manager(self):
        """Get current layer manager"""
        tab = self.current_tab
        return tab.layer_manager if tab else None

    @property
    def history_manager(self):
        """Get current history manager"""
        tab = self.current_tab
        return tab.history_manager if tab else None

    @property
    def exporter(self):
        """Get current exporter"""
        tab = self.current_tab
        return tab.exporter if tab else None

    @property
    def current_file(self):
        """Get current file path"""
        tab = self.current_tab
        return tab.file_path if tab else None

    @current_file.setter
    def current_file(self, value):
        """Set current file path"""
        tab = self.current_tab
        if tab:
            tab.file_path = value

    def setup_ui(self):
        """Setup UI components"""
        # Create main container widget
        main_container = QWidget()
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create tab widget for multiple documents
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #3c3c3c;
                color: #888888;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #3c3c3c;
                color: #00c000;
            }
            QTabBar::tab:hover:!selected {
                background-color: #505050;
            }
            QTabBar::close-button {
                image: none;
                background: transparent;
                border: none;
            }
        """)

        # Set custom close button icons for tabs
        self._setup_tab_close_buttons()

        main_layout.addWidget(self.tab_widget)

        # Create footer bar for navigation and zoom
        self.create_footer_bar()
        main_layout.addWidget(self.footer_bar)

        self.setCentralWidget(main_container)

        # Create panels (will be updated when tabs change)
        self.create_thumbnail_panel()
        self.create_properties_panel()
        self.create_ai_chat_panel()

        # Create menus
        self.create_menus()

        # Create toolbars
        self.create_main_toolbar()
        self.create_tool_toolbar()

        # Create status bar
        self.create_status_bar()

    def get_current_canvas(self):
        """Get current canvas widget"""
        tab = self.current_tab
        return tab.canvas_widget if tab else None

    def create_footer_bar(self):
        """Create footer bar with page navigation and zoom controls"""
        self.footer_bar = QToolBar()
        self.footer_bar.setMovable(False)
        self.footer_bar.setIconSize(QSize(24, 24))

        # Left spacer to center the controls
        left_spacer = QWidget()
        left_spacer.setSizePolicy(left_spacer.sizePolicy().horizontalPolicy(), left_spacer.sizePolicy().verticalPolicy())
        from PyQt6.QtWidgets import QSizePolicy
        left_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.footer_bar.addWidget(left_spacer)

        # Page navigation
        prev_btn = QAction(get_icon("prev"), "Previous", self)
        prev_btn.setToolTip("Previous page")
        prev_btn.triggered.connect(lambda: self.get_current_canvas().previous_page() if self.get_current_canvas() else None)
        self.footer_bar.addAction(prev_btn)

        # Page number display (clickable to edit)
        self.page_label = ClickablePageLabel("Page: 0 / 0")
        self.page_label.page_requested.connect(self._on_page_requested)
        self.footer_bar.addWidget(self.page_label)

        next_btn = QAction(get_icon("next"), "Next", self)
        next_btn.setToolTip("Next page")
        next_btn.triggered.connect(lambda: self.get_current_canvas().next_page() if self.get_current_canvas() else None)
        self.footer_bar.addAction(next_btn)

        self.footer_bar.addSeparator()

        # Zoom controls
        zoom_out_btn = QAction(get_icon("zoom-out"), "Zoom Out", self)
        zoom_out_btn.setToolTip("Zoom out")
        zoom_out_btn.triggered.connect(lambda: self.get_current_canvas().zoom_out() if self.get_current_canvas() else None)
        self.footer_bar.addAction(zoom_out_btn)

        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["25%", "50%", "75%", "100%", "125%", "150%", "200%", "300%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.currentTextChanged.connect(self.on_zoom_combo_changed)
        self.footer_bar.addWidget(self.zoom_combo)

        zoom_in_btn = QAction(get_icon("zoom-in"), "Zoom In", self)
        zoom_in_btn.setToolTip("Zoom in")
        zoom_in_btn.triggered.connect(lambda: self.get_current_canvas().zoom_in() if self.get_current_canvas() else None)
        self.footer_bar.addAction(zoom_in_btn)

        self.footer_bar.addSeparator()

        # Continuous view toggle button (using QAction like zoom buttons)
        # Initially shows pagebreak icon (continuous view disabled by default)
        self.continuous_view_action = QAction(get_icon("pagebreak"), "Continuous View", self)
        self.continuous_view_action.setToolTip("Enable Continuous View (scroll through all pages)")
        self.continuous_view_action.triggered.connect(self.toggle_continuous_view)
        self.footer_bar.addAction(self.continuous_view_action)
        self._continuous_view_enabled = False  # Track state manually (disabled by default)

        # Fit to screen toggle button
        self.fit_to_screen_action = QAction(get_icon("scale_fit"), "Fit to Screen", self)
        self.fit_to_screen_action.setToolTip("Fit document to screen")
        self.fit_to_screen_action.triggered.connect(self.toggle_fit_to_screen)
        self.footer_bar.addAction(self.fit_to_screen_action)
        self._fit_to_screen_enabled = False  # Track state
        self._zoom_before_fit = 1.0  # Store zoom level before fit

        # Right spacer to center the controls
        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.footer_bar.addWidget(right_spacer)

    def create_thumbnail_panel(self):
        """Create thumbnail panel"""
        # Create with None initially - will be updated when tab changes
        self.thumbnail_panel = ThumbnailPanel(None)

        dock = QDockWidget("Pages", self)
        dock.setWidget(self.thumbnail_panel)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                        QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def create_properties_panel(self):
        """Create properties panel"""
        # Create with None initially - will be updated when tab changes
        self.properties_panel = PropertiesPanel(None)

        dock = QDockWidget("Properties", self)
        dock.setWidget(self.properties_panel)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                        QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.properties_dock = dock

    def create_ai_chat_panel(self):
        """Create AI chat panel below the properties panel"""
        self.ai_chat_widget = AIChatWidget()

        dock = QDockWidget("AI Assistant", self)
        dock.setWidget(self.ai_chat_widget)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                        QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.ai_chat_dock = dock

        # Stack it below the properties panel
        if hasattr(self, 'properties_dock'):
            self.splitDockWidget(self.properties_dock, dock, Qt.Orientation.Vertical)
            # Give AI Assistant more space (70% of the height)
            self.resizeDocks([self.properties_dock, dock], [200, 500], Qt.Orientation.Vertical)
            # Set the right dock area to maximum width (400px)
            self.resizeDocks([self.properties_dock], [400], Qt.Orientation.Horizontal)

    def create_menus(self):
        """Create menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_document)
        file_menu.addAction(new_action)

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        export_menu = file_menu.addMenu("&Export")

        export_flatten_action = QAction("Export (Flattened)...", self)
        export_flatten_action.triggered.connect(self.export_flattened)
        export_menu.addAction(export_flatten_action)

        export_image_action = QAction("Export Page as Image...", self)
        export_image_action.triggered.connect(self.export_page_as_image)
        export_menu.addAction(export_image_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        self.undo_action = QAction("&Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("&Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in_action.triggered.connect(lambda: self.get_current_canvas().zoom_in() if self.get_current_canvas() else None)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out_action.triggered.connect(lambda: self.get_current_canvas().zoom_out() if self.get_current_canvas() else None)
        view_menu.addAction(zoom_out_action)

        view_menu.addSeparator()

        fit_width_action = QAction("Fit to &Width", self)
        fit_width_action.triggered.connect(lambda: self.get_current_canvas().fit_to_width() if self.get_current_canvas() else None)
        view_menu.addAction(fit_width_action)

        fit_page_action = QAction("Fit to &Page", self)
        fit_page_action.triggered.connect(lambda: self.get_current_canvas().fit_to_page() if self.get_current_canvas() else None)
        view_menu.addAction(fit_page_action)

        # Page menu
        page_menu = menubar.addMenu("&Page")

        insert_page_action = QAction("&Insert Page...", self)
        insert_page_action.triggered.connect(self.insert_page)
        page_menu.addAction(insert_page_action)

        delete_page_action = QAction("&Delete Page", self)
        delete_page_action.triggered.connect(self.delete_page)
        page_menu.addAction(delete_page_action)

        page_menu.addSeparator()

        rotate_cw_action = QAction("Rotate Clockwise", self)
        rotate_cw_action.triggered.connect(lambda: self.rotate_page(90))
        page_menu.addAction(rotate_cw_action)

        rotate_ccw_action = QAction("Rotate Counter-Clockwise", self)
        rotate_ccw_action.triggered.connect(lambda: self.rotate_page(-90))
        page_menu.addAction(rotate_ccw_action)

        page_menu.addSeparator()

        duplicate_page_action = QAction("Duplicate Page", self)
        duplicate_page_action.triggered.connect(self.duplicate_page)
        page_menu.addAction(duplicate_page_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_main_toolbar(self):
        """Create main toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(toolbar)

        # File operations
        open_btn = QAction(get_icon("open"), "Open", self)
        open_btn.setToolTip("Open PDF file")
        open_btn.triggered.connect(self.open_file)
        toolbar.addAction(open_btn)

        save_btn = QAction(get_icon("save"), "Save", self)
        save_btn.setToolTip("Save PDF file")
        save_btn.triggered.connect(self.save_file)
        toolbar.addAction(save_btn)

        # Ruler toggle
        self.ruler_action = QAction(get_icon("ruler"), "Toggle Rulers", self)
        self.ruler_action.setToolTip("Show/Hide Rulers")
        self.ruler_action.triggered.connect(self.toggle_rulers)
        toolbar.addAction(self.ruler_action)
        self._rulers_enabled = True  # Enabled by default

        toolbar.addSeparator()

        # Undo/Redo
        undo_btn = QAction(get_icon("undo"), "Undo", self)
        undo_btn.setToolTip("Undo (Ctrl+Z)")
        undo_btn.triggered.connect(self.undo)
        toolbar.addAction(undo_btn)

        redo_btn = QAction(get_icon("redo"), "Redo", self)
        redo_btn.setToolTip("Redo (Ctrl+Y)")
        redo_btn.triggered.connect(self.redo)
        toolbar.addAction(redo_btn)

        toolbar.addSeparator()

        # Print/Export button with dropdown
        print_btn = QToolButton()
        print_btn.setIcon(get_icon("print"))
        print_btn.setToolTip("Print / Export options")
        print_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        print_btn.clicked.connect(self.print_document)

        # Create dropdown menu for export options
        print_menu = QMenu(self)

        print_action = print_menu.addAction(get_icon("print"), "Print (Ctrl+P)")
        print_action.setShortcut(QKeySequence.StandardKey.Print)
        print_action.triggered.connect(self.print_document)

        print_menu.addSeparator()

        export_vector_action = print_menu.addAction(get_icon("save"), "Export as PDF (Vector)")
        export_vector_action.triggered.connect(self.save_file_as)

        export_flat_action = print_menu.addAction(get_icon("export"), "Export as PDF (Flattened)")
        export_flat_action.triggered.connect(self.export_flattened)

        print_menu.addSeparator()

        export_image_action = print_menu.addAction(get_icon("image"), "Export Page as Image (PNG/JPG)")
        export_image_action.triggered.connect(self.export_page_as_image)

        print_btn.setMenu(print_menu)
        toolbar.addWidget(print_btn)

        # Translate button
        translate_btn = QToolButton()
        translate_btn.setIcon(get_icon("translate"))
        translate_btn.setToolTip("Translate Document")
        translate_btn.clicked.connect(self.translate_document)
        toolbar.addWidget(translate_btn)

    def create_tool_toolbar(self):
        """Create tool toolbar"""
        toolbar = QToolBar("Tools")
        toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        # Store icon info for each tool action (tool_name -> icon_name)
        self.tool_icon_mapping = {}

        # Selection tool - Draw box to select multiple layers, then move them
        select_btn = QAction(get_icon("edit"), "Select", self)
        select_btn.setToolTip("Select and Move - Draw box to select multiple layers")
        select_btn.setCheckable(True)
        select_btn.triggered.connect(lambda: self.set_tool('select'))
        toolbar.addAction(select_btn)
        self.tool_icon_mapping['select'] = 'edit'

        toolbar.addSeparator()

        # Drawing tools
        pen_btn = QAction(get_icon("pen"), "Pen", self)
        pen_btn.setToolTip("Pen tool")
        pen_btn.setCheckable(True)
        pen_btn.triggered.connect(lambda: self.set_tool('pen'))
        toolbar.addAction(pen_btn)
        self.tool_icon_mapping['pen'] = 'pen'

        selecttext_btn = QAction(get_icon("selectText"), "Select Text", self)
        selecttext_btn.setToolTip("Select text for highlight, underline, or strikethrough")
        selecttext_btn.setCheckable(True)
        selecttext_btn.triggered.connect(lambda: self.set_tool('selecttext'))
        toolbar.addAction(selecttext_btn)
        self.tool_icon_mapping['selecttext'] = 'selectText'

        toolbar.addSeparator()

        # Unified Shape Tool button (replaces individual shape tool buttons)
        self.shape_tool_button = ShapeToolButton()
        self.shape_tool_button.tool_changed.connect(self._on_shape_tool_changed)
        toolbar.addWidget(self.shape_tool_button)

        # Map shape tools to the unified button for icon updates
        self.tool_icon_mapping['rectangle'] = 'rectangle'
        self.tool_icon_mapping['ellipse'] = 'circle'
        self.tool_icon_mapping['line'] = 'line'
        self.tool_icon_mapping['arrow'] = 'arrow'

        toolbar.addSeparator()

        # Text and image
        text_btn = QAction(get_icon("text"), "Text", self)
        text_btn.setToolTip("Text tool")
        text_btn.setCheckable(True)
        text_btn.triggered.connect(lambda: self.set_tool('text'))
        toolbar.addAction(text_btn)
        self.tool_icon_mapping['text'] = 'text'

        image_btn = QAction(get_icon("image"), "Image", self)
        image_btn.setToolTip("Insert image")
        image_btn.setCheckable(True)
        image_btn.triggered.connect(lambda: self.set_tool('image'))
        toolbar.addAction(image_btn)
        self.tool_icon_mapping['image'] = 'image'

        symbol_btn = QAction(get_icon("star"), "Add Symbol", self)
        symbol_btn.setToolTip("Add symbol")
        symbol_btn.setCheckable(True)
        symbol_btn.triggered.connect(lambda: self.set_tool('symbol'))
        toolbar.addAction(symbol_btn)
        self.tool_icon_mapping['symbol'] = 'star'

        # Store toolbar for tool button management
        self.tool_toolbar = toolbar

    def _on_shape_tool_changed(self, tool_name: str):
        """Handle shape tool change from unified button"""
        # Deselect all other tools first
        for action in self.tool_toolbar.actions():
            if action.isCheckable():
                action.setChecked(False)
                # Reset icon to normal color
                action_tool_name = action.text().lower().replace(" ", "_").replace("add_", "")
                if action_tool_name in self.tool_icon_mapping:
                    icon_name = self.tool_icon_mapping[action_tool_name]
                    action.setIcon(get_icon(icon_name))

        # Set the tool
        tool = self.tools.get(tool_name)
        self.current_tool = tool

        # Apply tool to current tab's canvas
        tab = self.current_tab
        if tab:
            tab.canvas_widget.set_tool(tool)

        self.status_bar.showMessage(f"Tool: {tool_name.title()}")

    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _setup_tab_close_buttons(self):
        """Setup custom close button style for tab bar"""
        # This is called once during initialization
        # Individual tab close buttons are set up when tabs are created
        pass

    def _set_tab_close_button(self, tab_index: int):
        """Set custom close button for a specific tab"""
        tab_bar = self.tab_widget.tabBar()
        # Create close button with red close.svg icon
        close_btn = QPushButton()
        close_btn.setFixedSize(16, 16)
        close_btn.setIcon(get_icon("close", color="#ff4444"))
        close_btn.setIconSize(QSize(12, 12))
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 68, 68, 0.2);
                border-radius: 3px;
            }
        """)
        close_btn.clicked.connect(lambda: self.close_tab(tab_index))
        tab_bar.setTabButton(tab_index, QTabBar.ButtonPosition.RightSide, close_btn)

    def create_new_tab(self, file_path=None, title="Untitled"):
        """Create a new tab with a PDF document"""
        tab = PDFTab(self)
        self.tabs.append(tab)

        # Add to tab widget (use ruler_container which wraps the scroll area)
        tab_index = self.tab_widget.addTab(tab.ruler_container, title)
        self.tab_widget.setCurrentIndex(tab_index)
        self.current_tab_index = tab_index

        # Set custom close button for this tab
        self._set_tab_close_button(tab_index)

        # Connect canvas signals
        self.connect_tab_signals(tab)

        return tab

    def connect_tab_signals(self, tab: PDFTab):
        """Connect signals for a specific tab"""
        canvas = tab.canvas_widget

        canvas.page_changed.connect(self.on_page_changed)
        canvas.zoom_changed.connect(self.on_zoom_changed)
        canvas.layer_added.connect(self.on_layer_added)
        canvas.text_field_selected.connect(self.on_text_field_selected)
        canvas.text_field_deselected.connect(self.on_text_field_deselected)
        canvas.color_used.connect(self.on_color_used)

    def connect_panel_signals(self):
        """Connect panel signals to current tab"""
        tab = self.current_tab
        if not tab:
            return

        canvas = tab.canvas_widget

        # Disconnect previous connections (if any) and reconnect
        try:
            self.thumbnail_panel.page_selected.disconnect()
        except:
            pass
        try:
            self.thumbnail_panel.pages_reordered.disconnect()
        except:
            pass

        self.thumbnail_panel.page_selected.connect(canvas.set_page)
        self.thumbnail_panel.page_context_menu.connect(self.show_page_context_menu)
        self.thumbnail_panel.pages_reordered.connect(self._on_pages_reordered)

    def on_tab_changed(self, index):
        """Handle tab change"""
        self.current_tab_index = index

        tab = self.current_tab
        if tab:
            # Update thumbnail panel
            self.thumbnail_panel.pdf_doc = tab.pdf_doc
            self.thumbnail_panel.load_thumbnails()

            # Update properties panel
            self.properties_panel.layer_manager = tab.layer_manager
            self.properties_panel.refresh_layers()

            # Update AI chat panel
            self.ai_chat_widget.set_document(tab.pdf_doc)

            # Reconnect panel signals
            self.connect_panel_signals()

            # Update page label
            if tab.pdf_doc and tab.pdf_doc.doc:
                page_num = tab.canvas_widget.current_page
                self.page_label.setText(f"Page: {page_num + 1} / {tab.pdf_doc.page_count}")
            else:
                self.page_label.setText("Page: 0 / 0")

            # Update zoom display to match current tab's zoom
            zoom_percent = int(tab.canvas_widget.zoom * 100)
            self.zoom_combo.setCurrentText(f"{zoom_percent}%")

            # Apply current tool to new tab's canvas
            if self.current_tool:
                tab.canvas_widget.set_tool(self.current_tool)

            # Sync continuous view state and icon
            if hasattr(self, '_continuous_view_enabled'):
                self._continuous_view_enabled = tab.canvas_widget.is_continuous_view()
                # Update icon to match current tab's state
                if self._continuous_view_enabled:
                    self.continuous_view_action.setIcon(get_icon("pagecontinuous"))
                    self.continuous_view_action.setToolTip("Disable Continuous View (single page view)")
                else:
                    self.continuous_view_action.setIcon(get_icon("pagebreak"))
                    self.continuous_view_action.setToolTip("Enable Continuous View (scroll through all pages)")

            # Reset fit to screen state when switching tabs
            if hasattr(self, '_fit_to_screen_enabled'):
                self._reset_fit_to_screen_state()

            # Update window title
            if tab.file_path:
                self.setWindowTitle(f"PDF Editor - {os.path.basename(tab.file_path)}")
            else:
                self.setWindowTitle("PDF Editor - Untitled")

    def close_tab(self, index):
        """Close a tab"""
        if index < 0 or index >= len(self.tabs):
            return

        tab = self.tabs[index]

        # Ask to save if document has been modified
        if tab.pdf_doc and tab.pdf_doc.doc:
            reply = QMessageBox.question(
                self, "Close Tab",
                f"Do you want to save '{os.path.basename(tab.file_path) if tab.file_path else 'Untitled'}' before closing?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                # Save before closing
                old_index = self.current_tab_index
                self.current_tab_index = index
                self.save_file()
                self.current_tab_index = old_index

        # Close the PDF document
        if tab.pdf_doc:
            tab.pdf_doc.close()

        # Remove tab
        self.tab_widget.removeTab(index)
        self.tabs.pop(index)

        # Update current tab index
        if len(self.tabs) == 0:
            self.current_tab_index = -1
            self.page_label.setText("Page: 0 / 0")
            self.setWindowTitle("PDF Editor - Professional PDF Editing Tool")
            # Clear the thumbnail panel when no documents are open
            self.thumbnail_panel.pdf_doc = None
            self.thumbnail_panel.container.clear_cards()
        else:
            self.current_tab_index = self.tab_widget.currentIndex()

    def connect_signals(self):
        """Connect global signals (properties panel)"""
        # Properties panel signals (these work across all tabs)
        self.properties_panel.color_changed.connect(self.on_tool_color_changed)
        self.properties_panel.width_changed.connect(self.on_tool_width_changed)
        self.properties_panel.opacity_changed.connect(self.on_tool_opacity_changed)
        self.properties_panel.fill_color_changed.connect(self.on_tool_fill_color_changed)
        self.properties_panel.highlight_color_changed.connect(self.on_highlight_color_changed)
        self.properties_panel.layer_visibility_changed.connect(self.on_layer_visibility_changed)
        self.properties_panel.layer_deleted.connect(self.on_layer_deleted)
        self.properties_panel.layer_copied.connect(self.on_layer_copied)
        self.properties_panel.layer_edit_requested.connect(self.on_layer_edit_requested)
        self.properties_panel.text_annotation_requested.connect(self.on_text_annotation_requested)

    def on_layer_deleted(self, layer_id):
        """Handle layer deletion from properties panel"""
        tab = self.current_tab
        if tab:
            tab.canvas_widget.remove_layer(layer_id)

    def on_layer_copied(self, copied_layer):
        """Handle layer copy from properties panel"""
        tab = self.current_tab
        if tab:
            tab.canvas_widget.add_layer(copied_layer)
            tab.canvas_widget.update()

    def set_tool(self, tool_name: str):
        """Set current tool"""
        # Get tool
        tool = self.tools.get(tool_name) if tool_name else None

        # Check if this is a shape tool (handled by unified button)
        shape_tools = ['rectangle', 'ellipse', 'line', 'arrow']
        is_shape_tool = tool_name in shape_tools

        # Update tool buttons - change icon color to green for selected tool
        for action in self.tool_toolbar.actions():
            if action.isCheckable():
                action.setChecked(False)
                # Reset icon to normal color
                action_tool_name = action.text().lower().replace(" ", "_").replace("add_", "")
                if action_tool_name in self.tool_icon_mapping:
                    icon_name = self.tool_icon_mapping[action_tool_name]
                    action.setIcon(get_icon(icon_name))

        # Deactivate shape tool button if selecting a non-shape tool
        if hasattr(self, 'shape_tool_button'):
            if is_shape_tool:
                # Activate the shape tool button with the selected tool
                icon_name = self.tool_icon_mapping.get(tool_name, 'rectangle')
                self.shape_tool_button.set_tool_externally(tool_name, icon_name)
                self.shape_tool_button.set_active(True)
            else:
                # Deactivate shape tool button when another tool is selected
                self.shape_tool_button.set_active(False)

        if tool and not is_shape_tool:
            # Find and check the corresponding action, change icon to green
            for action in self.tool_toolbar.actions():
                if action.text().lower().replace(" ", "_") == tool_name:
                    action.setChecked(True)
                    # Change icon to green
                    if tool_name in self.tool_icon_mapping:
                        icon_name = self.tool_icon_mapping[tool_name]
                        action.setIcon(get_icon(icon_name, color='#00c000'))  # Green color
                    break

        # Clear text selection if switching away from selecttext tool
        if self.current_tool and hasattr(self.current_tool, 'clear_selection'):
            self.current_tool.clear_selection()

        # Show/hide text annotation buttons based on whether selecttext tool is selected
        self.properties_panel.set_text_selection_active(tool_name == 'selecttext')

        self.current_tool = tool

        # Apply tool to current tab's canvas
        tab = self.current_tab
        if tab:
            # Special handling for text selection tool
            if tool_name == 'selecttext' and tool:
                tool.pdf_doc = tab.pdf_doc
                tool.set_highlight_color(self.properties_panel.get_highlight_color())

            tab.canvas_widget.set_tool(tool)

        self.status_bar.showMessage(f"Tool: {tool_name.title() if tool_name else 'Select'}")

    def new_document(self):
        """Create new PDF in a new tab"""
        tab = self.create_new_tab(title="Untitled")
        tab.pdf_doc.create_new()

        # Update panels
        self.thumbnail_panel.pdf_doc = tab.pdf_doc
        self.thumbnail_panel.load_thumbnails()
        self.properties_panel.layer_manager = tab.layer_manager
        self.properties_panel.refresh_layers()
        self.ai_chat_widget.set_document(tab.pdf_doc)

        # Connect panel signals
        self.connect_panel_signals()

        tab.canvas_widget.set_page(0)

        # Update rulers after document is created
        tab.ruler_container.update_rulers()

        # Update zoom display
        zoom_percent = int(tab.canvas_widget.zoom * 100)
        self.zoom_combo.setCurrentText(f"{zoom_percent}%")

        self.setWindowTitle("PDF Editor - Untitled")

    def open_file(self):
        """Open PDF file in a new tab"""
        file_name, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_name:
            # Check if file is already open in another tab
            for i, tab in enumerate(self.tabs):
                if tab.file_path == file_name:
                    # Switch to existing tab
                    self.tab_widget.setCurrentIndex(i)
                    self.status_bar.showMessage(f"Switched to already open file: {file_name}")
                    return

            # Create new tab and open file
            tab = self.create_new_tab(title=os.path.basename(file_name))

            if tab.pdf_doc.open(file_name):
                tab.file_path = file_name

                # Try to load layer metadata from PDF
                self._load_layers_from_pdf(tab)

                # Update panels
                self.thumbnail_panel.pdf_doc = tab.pdf_doc
                self.thumbnail_panel.load_thumbnails()
                self.properties_panel.layer_manager = tab.layer_manager
                self.properties_panel.refresh_layers()
                self.ai_chat_widget.set_document(tab.pdf_doc)

                # Connect panel signals
                self.connect_panel_signals()

                tab.canvas_widget.set_page(0)

                # Update rulers after document is loaded
                tab.ruler_container.update_rulers()

                # Update zoom display
                zoom_percent = int(tab.canvas_widget.zoom * 100)
                self.zoom_combo.setCurrentText(f"{zoom_percent}%")

                self.setWindowTitle(f"PDF Editor - {os.path.basename(file_name)}")
                self.status_bar.showMessage(f"Opened: {file_name}")
            else:
                # Remove failed tab
                self.close_tab(self.current_tab_index)
                QMessageBox.critical(self, "Error", "Failed to open PDF file")

    def save_file(self):
        """Save current file with layers as PDF elements"""
        tab = self.current_tab
        if not tab or not tab.exporter:
            return

        if tab.file_path:
            print("=== Saving PDF with vector/text preservation ===")
            # Use exporter to save layers as actual PDF elements (text, vectors, images)
            success = tab.exporter.save_with_layers(tab.file_path)
            if success:
                print(f"✓ Saved as vector PDF: {tab.file_path}")
                self.status_bar.showMessage(f"Saved (Vector PDF): {tab.file_path}")
            else:
                print("✗ Error saving file")
                self.status_bar.showMessage("Error saving file")
        else:
            self.save_file_as()

    def save_file_as(self):
        """Save file as with layers as PDF elements"""
        tab = self.current_tab
        if not tab or not tab.exporter:
            return

        file_name, _ = QFileDialog.getSaveFileName(self, "Save PDF (Vector/Text)", "", "PDF Files (*.pdf)")
        if file_name:
            print("=== Saving PDF with vector/text preservation ===")
            # Use exporter to save layers as actual PDF elements (text, vectors, images)
            success = tab.exporter.save_with_layers(file_name)
            if success:
                tab.file_path = file_name
                # Update tab title
                self.tab_widget.setTabText(self.current_tab_index, os.path.basename(file_name))
                self.setWindowTitle(f"PDF Editor - {os.path.basename(file_name)}")
                print(f"✓ Saved as vector PDF: {file_name}")
                self.status_bar.showMessage(f"Saved (Vector PDF): {file_name}")
            else:
                print("✗ Error saving file")
                self.status_bar.showMessage("Error saving file")

    def export_flattened(self):
        """Export with flattened annotations - CONVERTS TO IMAGES"""
        from PyQt6.QtWidgets import QMessageBox

        # Warn user that this converts to images
        reply = QMessageBox.question(
            self,
            "Export as Flattened (Images)",
            "This will convert all pages to images.\n\n"
            "Use this ONLY if you need compatibility with old PDF readers.\n\n"
            "For normal saving, use File → Save instead.\n\n"
            "Continue with image export?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export PDF (Flattened as Images) - NOT RECOMMENDED",
            "",
            "PDF Files (*.pdf)"
        )
        if file_name:
            print("=== WARNING: Converting PDF to images (flattened) ===")
            self.exporter.export_flattened(file_name)
            print(f"✓ Exported as image-based PDF: {file_name}")
            self.status_bar.showMessage(f"Exported (Image-based): {file_name}")

    def _load_layers_from_pdf(self, tab):
        """Load layer metadata from PDF if available"""
        try:
            layer_data = PDFExporter.load_layer_metadata(tab.pdf_doc.doc)
            if layer_data:
                # Restore layers from metadata
                restored_manager = LayerManager.from_dict(layer_data)
                tab.layer_manager.layers = restored_manager.layers
                tab.layer_manager._next_z_index = restored_manager._next_z_index
                print(f"  → Restored {len(restored_manager.layers)} editable layer(s) from PDF")
                self.status_bar.showMessage(f"Restored {len(restored_manager.layers)} editable layers")
        except Exception as e:
            print(f"  → Could not restore layers: {e}")

    def export_page_as_image(self):
        """Export current page as image"""
        canvas = self.get_current_canvas()
        if not canvas:
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "Export Page as Image", "",
                                                    "PNG Files (*.png);;JPEG Files (*.jpg)")
        if file_name:
            page_num = canvas.current_page
            self.pdf_doc.export_page_as_image(page_num, file_name)
            self.status_bar.showMessage(f"Exported page {page_num + 1} to: {file_name}")

    def print_document(self):
        """Print the current document"""
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QPainter

        if not self.pdf_doc or not self.pdf_doc.doc:
            QMessageBox.warning(self, "No Document", "Please open a PDF document first.")
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(printer.pageLayout().orientation())

        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Document")

        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            painter = QPainter()
            if painter.begin(printer):
                canvas = self.get_current_canvas()
                current_page = canvas.current_page if canvas else 0

                for page_num in range(self.pdf_doc.page_count):
                    if page_num > 0:
                        printer.newPage()

                    # Render the page
                    pixmap = self.pdf_doc.render_page(page_num, zoom=2.0)
                    if pixmap:
                        # Scale to fit printer page
                        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                        scaled_pixmap = pixmap.scaled(
                            int(page_rect.width()),
                            int(page_rect.height()),
                            aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                            transformMode=Qt.TransformationMode.SmoothTransformation
                        )
                        # Center on page
                        x = int((page_rect.width() - scaled_pixmap.width()) / 2)
                        y = int((page_rect.height() - scaled_pixmap.height()) / 2)
                        painter.drawPixmap(x, y, scaled_pixmap)

                painter.end()
                self.status_bar.showMessage("Document sent to printer")
            else:
                QMessageBox.warning(self, "Print Error", "Failed to initialize printer.")

    def undo(self):
        """Undo"""
        canvas = self.get_current_canvas()
        if canvas:
            canvas.undo()
        self.update_undo_redo_actions()
        self.properties_panel.refresh_layers()

    def redo(self):
        """Redo"""
        canvas = self.get_current_canvas()
        if canvas:
            canvas.redo()
        self.update_undo_redo_actions()
        self.properties_panel.refresh_layers()

    def update_undo_redo_actions(self):
        """Update undo/redo action states"""
        history = self.history_manager
        if history:
            self.undo_action.setEnabled(history.can_undo())
            self.redo_action.setEnabled(history.can_redo())

            if history.can_undo():
                self.undo_action.setText(f"Undo {history.get_undo_description()}")
            else:
                self.undo_action.setText("Undo")

            if history.can_redo():
                self.redo_action.setText(f"Redo {history.get_redo_description()}")
            else:
                self.redo_action.setText("Redo")
        else:
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)
            self.undo_action.setText("Undo")
            self.redo_action.setText("Redo")

    def insert_page(self):
        """Insert a blank page"""
        canvas = self.get_current_canvas()
        if not canvas or not self.pdf_doc:
            return
        page_num = canvas.current_page + 1
        self.pdf_doc.insert_page(page_num)
        self.thumbnail_panel.refresh()
        self.status_bar.showMessage(f"Inserted page at position {page_num + 1}")

    def delete_page(self):
        """Delete current page"""
        canvas = self.get_current_canvas()
        if not canvas or not self.pdf_doc:
            return
        if self.pdf_doc.page_count <= 1:
            QMessageBox.warning(self, "Warning", "Cannot delete the only page")
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     "Are you sure you want to delete this page?")
        if reply == QMessageBox.StandardButton.Yes:
            page_num = canvas.current_page
            self.pdf_doc.delete_page(page_num)
            self.layer_manager.clear_page(page_num)
            self.thumbnail_panel.refresh()

            if page_num >= self.pdf_doc.page_count:
                canvas.set_page(self.pdf_doc.page_count - 1)

            self.status_bar.showMessage(f"Deleted page {page_num + 1}")

    def rotate_page(self, rotation: int):
        """Rotate current page"""
        canvas = self.get_current_canvas()
        if not canvas or not self.pdf_doc:
            return
        page_num = canvas.current_page
        current_page = self.pdf_doc.get_page(page_num)
        if current_page:
            new_rotation = (current_page.rotation + rotation) % 360
            self.pdf_doc.rotate_page(page_num, new_rotation)
            self.thumbnail_panel.refresh()
            canvas.update()
            self.status_bar.showMessage(f"Rotated page {page_num + 1}")

    def duplicate_page(self):
        """Duplicate current page"""
        canvas = self.get_current_canvas()
        if not canvas or not self.pdf_doc:
            return
        page_num = canvas.current_page
        self.pdf_doc.duplicate_page(page_num)
        self.thumbnail_panel.refresh()
        self.status_bar.showMessage(f"Duplicated page {page_num + 1}")

    def show_page_context_menu(self, page_num: int, pos):
        """Show page context menu"""
        menu = QMenu(self)

        insert_action = menu.addAction("Insert Page Here")
        insert_action.triggered.connect(lambda: self.insert_page_at(page_num))

        # Move page up (disabled if already first page)
        move_up_action = menu.addAction("Move Page Up")
        move_up_action.triggered.connect(lambda: self.move_page_up(page_num))
        if page_num == 0:
            move_up_action.setEnabled(False)

        # Move page down (disabled if already last page)
        move_down_action = menu.addAction("Move Page Down")
        move_down_action.triggered.connect(lambda: self.move_page_down(page_num))
        if self.pdf_doc and page_num >= self.pdf_doc.page_count - 1:
            move_down_action.setEnabled(False)

        menu.addSeparator()

        delete_action = menu.addAction("Delete Page")
        delete_action.triggered.connect(lambda: self.delete_page_at(page_num))

        menu.addSeparator()

        rotate_cw = menu.addAction("Rotate Clockwise")
        rotate_cw.triggered.connect(lambda: self.rotate_page_at(page_num, 90))

        rotate_ccw = menu.addAction("Rotate Counter-Clockwise")
        rotate_ccw.triggered.connect(lambda: self.rotate_page_at(page_num, -90))

        menu.addSeparator()

        duplicate_action = menu.addAction("Duplicate Page")
        duplicate_action.triggered.connect(lambda: self.duplicate_page_at(page_num))

        menu.exec(pos)

    def insert_page_at(self, page_num: int):
        """Insert page at position"""
        self.pdf_doc.insert_page(page_num)
        self.thumbnail_panel.refresh(block_context_menu=True)

    def delete_page_at(self, page_num: int):
        """Delete specific page"""
        if self.pdf_doc.page_count <= 1:
            QMessageBox.warning(self, "Warning", "Cannot delete the only page")
            return

        self.pdf_doc.delete_page(page_num)
        self.layer_manager.clear_page(page_num)
        self.thumbnail_panel.refresh(block_context_menu=True)

    def rotate_page_at(self, page_num: int, rotation: int):
        """Rotate specific page"""
        page = self.pdf_doc.get_page(page_num)
        if page:
            new_rotation = (page.rotation + rotation) % 360
            self.pdf_doc.rotate_page(page_num, new_rotation)
            self.thumbnail_panel.refresh(block_context_menu=True)

    def duplicate_page_at(self, page_num: int):
        """Duplicate specific page"""
        self.pdf_doc.duplicate_page(page_num)
        self.thumbnail_panel.refresh(block_context_menu=True)

    def move_page_up(self, page_num: int):
        """Move page up (swap with previous page)"""
        if page_num <= 0:
            return

        self.pdf_doc.move_page(page_num, page_num - 1)
        self.thumbnail_panel.refresh(block_context_menu=True)
        self.thumbnail_panel.set_current_page(page_num - 1)
        self.statusBar().showMessage(f"Moved page {page_num + 1} up", 3000)

    def move_page_down(self, page_num: int):
        """Move page down (swap with next page)"""
        if not self.pdf_doc or page_num >= self.pdf_doc.page_count - 1:
            return

        self.pdf_doc.move_page(page_num, page_num + 2)  # +2 because move_page inserts before target
        self.thumbnail_panel.refresh(block_context_menu=True)
        self.thumbnail_panel.set_current_page(page_num + 1)
        self.statusBar().showMessage(f"Moved page {page_num + 1} down", 3000)

    def _on_pages_reordered(self, source_pages: list, target_position: int):
        """Handle page reordering from drag-drop in thumbnail panel"""
        tab = self.current_tab
        if not tab or not tab.pdf_doc or not tab.pdf_doc.doc:
            return

        pdf_doc = tab.pdf_doc

        # Sort source pages in descending order for safe removal
        # We need to move pages one by one, adjusting target position as we go
        source_pages = sorted(source_pages)

        # Calculate how the target position shifts as we move pages
        # When moving multiple pages, we need to handle the index shifts carefully

        # First, determine the effective target position
        # Count how many source pages are before the target
        pages_before_target = sum(1 for p in source_pages if p < target_position)

        # The actual insertion point after removing all source pages
        adjusted_target = target_position - pages_before_target

        # Move pages starting from the last one (to maintain relative order)
        # We'll move them to consecutive positions starting at adjusted_target
        for i, page_num in enumerate(source_pages):
            # Calculate current position of this page
            # Pages before it in source_pages that were already moved need to be accounted for
            current_pos = page_num

            # Adjust for pages that were already moved
            for prev_page in source_pages[:i]:
                if prev_page < page_num:
                    current_pos -= 1

            # Calculate destination
            dest = adjusted_target + i

            # Only move if positions differ
            if current_pos != dest:
                pdf_doc.move_page(current_pos, dest)

        # Refresh the thumbnail panel
        self.thumbnail_panel.refresh()

        # Update current page view if needed
        canvas = tab.canvas_widget
        if canvas:
            current = canvas.current_page
            # Find where the current page ended up
            if current in source_pages:
                # Current page was moved, find its new position
                new_pos = adjusted_target + source_pages.index(current)
                canvas.set_page(new_pos)
            elif current >= min(source_pages) and current < target_position:
                # Current page shifted down
                shift = len([p for p in source_pages if p < current])
                canvas.set_page(current - shift)
            elif current < min(source_pages) and current >= adjusted_target:
                # Current page shifted up
                canvas.set_page(current + len(source_pages))

        self.statusBar().showMessage(f"Moved {len(source_pages)} page(s)", 3000)

    def on_page_changed(self, page_num: int):
        """Handle page change"""
        self.page_label.setText(f"Page: {page_num + 1} / {self.pdf_doc.page_count}")
        self.thumbnail_panel.set_current_page(page_num)
        self.properties_panel.set_current_page(page_num)

    def _on_page_requested(self, page_num: int):
        """Handle page number request from clickable page label"""
        canvas = self.get_current_canvas()
        if canvas:
            canvas.set_page(page_num)

    def on_zoom_changed(self, zoom: float):
        """Handle zoom change"""
        zoom_percent = int(zoom * 100)
        self.zoom_combo.setCurrentText(f"{zoom_percent}%")

    def on_zoom_combo_changed(self, text: str):
        """Handle zoom combo change"""
        canvas = self.get_current_canvas()
        if not canvas:
            return
        try:
            zoom = int(text.replace("%", "")) / 100.0
            canvas.set_zoom(zoom)
            # Reset fit to screen state when user manually changes zoom
            self._reset_fit_to_screen_state()
        except ValueError:
            pass

    def _reset_fit_to_screen_state(self):
        """Reset fit to screen state to disabled"""
        if self._fit_to_screen_enabled:
            self._fit_to_screen_enabled = False
            self.fit_to_screen_action.setIcon(get_icon("scale_fit"))
            self.fit_to_screen_action.setToolTip("Fit document to screen")

    def toggle_continuous_view(self):
        """Toggle continuous view mode"""
        canvas = self.get_current_canvas()
        if canvas:
            # Toggle the state manually
            self._continuous_view_enabled = not canvas.is_continuous_view()
            canvas.set_continuous_view(self._continuous_view_enabled)

            # Update icon based on state
            if self._continuous_view_enabled:
                self.continuous_view_action.setIcon(get_icon("pagecontinuous"))
                self.continuous_view_action.setToolTip("Disable Continuous View (single page view)")
            else:
                self.continuous_view_action.setIcon(get_icon("pagebreak"))
                self.continuous_view_action.setToolTip("Enable Continuous View (scroll through all pages)")

    def toggle_fit_to_screen(self):
        """Toggle fit to screen mode"""
        canvas = self.get_current_canvas()
        tab = self.current_tab
        if not canvas or not tab:
            return

        pdf_doc = canvas.pdf_doc
        if not pdf_doc or not pdf_doc.doc:
            return

        page_size = pdf_doc.get_page_size(canvas.current_page)
        if not page_size:
            return

        page_width, page_height = page_size

        # Get viewport size (account for rulers if visible)
        if hasattr(tab, 'ruler_container'):
            viewport = tab.ruler_container.scroll_area.viewport()
        else:
            viewport = tab.scroll_area.viewport()

        if not viewport:
            return

        viewport_width = viewport.width()
        viewport_height = viewport.height()

        # Calculate zoom to fit width and height
        zoom_fit_width = viewport_width / page_width
        zoom_fit_height = viewport_height / page_height

        if not self._fit_to_screen_enabled:
            # Fit to screen: zoom to FILL the entire viewport (use larger zoom)
            # This covers all viewport area, page may extend beyond viewport
            fill_zoom = max(zoom_fit_width, zoom_fit_height)
            canvas.set_zoom(fill_zoom)

            self._fit_to_screen_enabled = True
            self.fit_to_screen_action.setIcon(get_icon("scale_shrink"))
            self.fit_to_screen_action.setToolTip("Show complete page")
        else:
            # Original/shrink: zoom to FIT one complete page in window (use smaller zoom)
            # This ensures the full page is visible
            fit_zoom = min(zoom_fit_width, zoom_fit_height)
            canvas.set_zoom(fit_zoom)

            self._fit_to_screen_enabled = False
            self.fit_to_screen_action.setIcon(get_icon("scale_fit"))
            self.fit_to_screen_action.setToolTip("Fit document to screen")

    def toggle_rulers(self):
        """Toggle rulers visibility"""
        tab = self.current_tab
        if tab and hasattr(tab, 'ruler_container'):
            self._rulers_enabled = not tab.ruler_container.is_rulers_visible()
            tab.ruler_container.set_rulers_visible(self._rulers_enabled)

    def on_layer_added(self, layer):
        """Handle layer added"""
        self.properties_panel.refresh_layers()
        self.update_undo_redo_actions()

    def on_tool_color_changed(self, color: str):
        """Handle tool color change"""
        if self.current_tool:
            self.current_tool.set_color(color)

    def on_tool_width_changed(self, width: int):
        """Handle tool width change"""
        if self.current_tool:
            self.current_tool.set_width(width)

    def on_tool_opacity_changed(self, opacity: float):
        """Handle tool opacity change"""
        if self.current_tool:
            self.current_tool.set_opacity(opacity)

    def on_tool_fill_color_changed(self, color: str):
        """Handle fill color change"""
        if self.current_tool and hasattr(self.current_tool, 'set_fill_color'):
            self.current_tool.set_fill_color(color if color else None)

    def on_highlight_color_changed(self, color: str):
        """Handle highlight color change for text selection tool"""
        selecttext_tool = self.tools.get('selecttext')
        if selecttext_tool:
            selecttext_tool.set_highlight_color(color)

    def on_color_used(self, color: str):
        """Handle color used from dialogs (symbol, text, etc.) - update tool settings"""
        self.properties_panel.add_recent_color(color)

    def on_text_annotation_requested(self, annotation_type: str, color: str):
        """Handle text annotation request from properties panel"""
        canvas = self.get_current_canvas()
        if canvas:
            canvas.apply_text_annotation(annotation_type, color)

    def on_layer_visibility_changed(self, layer_id: str, visible: bool):
        """Handle layer visibility change"""
        canvas = self.get_current_canvas()
        if canvas:
            canvas.update()

    def on_layer_edit_requested(self, layer):
        """Handle layer edit request from properties panel"""
        from core.interactive_layer import TextFieldLayer, ImageLayer, SymbolLayer

        canvas = self.get_current_canvas()
        if not canvas:
            return

        # Open appropriate edit dialog based on layer type
        if isinstance(layer, TextFieldLayer):
            canvas.edit_text_field(layer)
        elif isinstance(layer, ImageLayer):
            canvas.edit_image_layer(layer)
        elif isinstance(layer, SymbolLayer):
            canvas.edit_symbol_layer(layer)

    def on_text_field_selected(self, layer):
        """Handle text field selection"""
        # Update properties panel with text field properties
        if hasattr(self.properties_panel, 'show_text_field_properties'):
            self.properties_panel.show_text_field_properties(layer)

    def on_text_field_deselected(self):
        """Handle text field deselection"""
        if hasattr(self.properties_panel, 'hide_text_field_properties'):
            self.properties_panel.hide_text_field_properties()


    def apply_settings(self):
        """Apply saved settings"""
        # Apply default tool settings
        settings = self.settings.get_all()
        tool_settings = settings.get('tool_defaults', {})

        for tool in self.tools.values():
            if 'color' in tool_settings:
                tool.set_color(tool_settings['color'])
            if 'width' in tool_settings:
                tool.set_width(tool_settings['width'])
            if 'opacity' in tool_settings:
                tool.set_opacity(tool_settings['opacity'])
            if 'font_size' in tool_settings:
                tool.set_font_size(tool_settings['font_size'])

        # Sync properties panel values to all tools
        self._sync_tool_settings_from_panel()

    def _sync_tool_settings_from_panel(self):
        """Sync current properties panel values to all tools"""
        # Get current values from properties panel
        color = self.properties_panel.color_button.current_color
        width = self.properties_panel.width_spin.value()
        opacity = self.properties_panel.opacity_slider.value() / 100.0
        fill_color = None if self.properties_panel.no_fill_checkbox.isChecked() else self.properties_panel.fill_color_button.current_color

        # Apply to all tools
        for tool in self.tools.values():
            tool.set_color(color)
            tool.set_width(width)
            tool.set_opacity(opacity)
            if hasattr(tool, 'set_fill_color'):
                tool.set_fill_color(fill_color)

    def translate_document(self):
        """Translate the current document using local LLM"""
        tab = self.current_tab
        if not tab or not tab.pdf_doc or not tab.pdf_doc.doc:
            QMessageBox.warning(self, "No Document", "Please open a PDF document first.")
            return

        from ui.translation_dialog import TranslationDialog

        # Show translation dialog
        dialog = TranslationDialog(self, document=tab.pdf_doc.doc)
        if dialog.exec() == dialog.DialogCode.Accepted:
            translated_doc = dialog.get_translated_document()
            target_language = dialog.get_target_language()

            if translated_doc:
                # Create a new tab for the translated document
                original_name = os.path.basename(tab.file_path) if tab.file_path else "Untitled"
                base_name = os.path.splitext(original_name)[0]
                new_title = f"{base_name} ({target_language})"

                new_tab = self.create_new_tab(title=new_title)
                new_tab.is_translated = True  # Mark as translated document
                new_tab.canvas_widget.is_translated_document = True  # Enable "Convert to Editable Layer"

                # Load the translated document
                if new_tab.pdf_doc.load_from_document(translated_doc):
                    # Update panels
                    self.thumbnail_panel.pdf_doc = new_tab.pdf_doc
                    self.thumbnail_panel.load_thumbnails()
                    self.properties_panel.layer_manager = new_tab.layer_manager
                    self.properties_panel.refresh_layers()
                    self.ai_chat_widget.set_document(new_tab.pdf_doc)

                    # Connect panel signals
                    self.connect_panel_signals()

                    new_tab.canvas_widget.set_page(0)

                    # Update rulers
                    new_tab.ruler_container.update_rulers()

                    self.status_bar.showMessage(f"Document translated to {target_language}")
                else:
                    # Remove failed tab
                    self.close_tab(self.current_tab_index)
                    QMessageBox.critical(self, "Error", "Failed to create translated document")

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About PDF Editor",
                         """<h2>PDF Editor v1.0</h2>
                         <p>A test project for PDF editing with annotation and editing capabilities.</p>
                         <p><b>Author:</b> Salman Zafar<br>
                         <b>Email:</b> <a href="mailto:salman32140@gmail.com">salman32140@gmail.com</a></p>
                         <p><b>Features:</b></p>
                         <ul>
                         <li>AI-powered document translation (local LLM)</li>
                         <li>AI chat assistant for PDF Q&A</li>
                         <li>Drawing and annotation tools</li>
                         <li>Text and image insertion</li>
                         <li>Multi-tab document support</li>
                         </ul>
                         <p>Built with Python, PyQt6, and PyMuPDF</p>
                         <hr>
                         <p><b>Credits:</b><br>
                         Icons by <a href="https://feathericons.com/">Feather Icons</a> (MIT License)</p>
                         """)

    def closeEvent(self, event):
        """Handle window close"""
        # Check if any tabs have open documents
        has_open_docs = any(tab.pdf_doc and tab.pdf_doc.doc for tab in self.tabs)

        if has_open_docs:
            reply = QMessageBox.question(self, "Confirm Exit",
                                        "Do you want to save all open documents before exiting?",
                                        QMessageBox.StandardButton.Yes |
                                        QMessageBox.StandardButton.No |
                                        QMessageBox.StandardButton.Cancel)

            if reply == QMessageBox.StandardButton.Yes:
                # Save all tabs
                for i, tab in enumerate(self.tabs):
                    if tab.pdf_doc and tab.pdf_doc.doc:
                        self.current_tab_index = i
                        self.save_file()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
