"""
PDF Canvas Widget
Main viewing and editing canvas with zoom, pan, and layer rendering
"""
from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QInputDialog, QFileDialog
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QWheelEvent, QMouseEvent
from core import PDFDocument, LayerManager, HistoryManager, Layer, Action, ActionType
from tools import BaseTool
from typing import Optional


class PDFCanvasWidget(QWidget):
    """Widget that displays the PDF page with layers"""

    page_changed = pyqtSignal(int)  # Emits when page changes
    layer_added = pyqtSignal(Layer)  # Emits when a layer is added
    zoom_changed = pyqtSignal(float)  # Emits when zoom changes
    continuous_view_changed = pyqtSignal(bool)  # Emits when continuous view mode changes

    # Gap between pages in continuous view (in pixels)
    PAGE_GAP = 20

    def __init__(self, pdf_doc: PDFDocument, layer_manager: LayerManager,
                 history_manager: HistoryManager):
        super().__init__()
        self.pdf_doc = pdf_doc
        self.layer_manager = layer_manager
        self.history_manager = history_manager

        self.current_page = 0
        self.zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        self.current_tool: Optional[BaseTool] = None
        self.is_panning = False
        self.last_pan_pos = QPointF()

        # Continuous view mode (shows all pages vertically)
        self.continuous_view = True  # Enabled by default
        self.page_offsets = []  # Y offsets for each page in continuous view

        # Guide manager for non-printing guides
        self._guide_manager = None
        self._dragging_guide_preview = None  # (orientation, position) during drag from ruler

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Update size when document is loaded
        self.update_size()

    def set_tool(self, tool: Optional[BaseTool]):
        """Set the current editing tool"""
        if self.current_tool:
            self.current_tool.deactivate()

        self.current_tool = tool

        if self.current_tool:
            self.current_tool.activate()
            self.setCursor(self.current_tool.get_cursor())
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_page(self, page_num: int):
        """Set the current page"""
        if 0 <= page_num < self.pdf_doc.page_count:
            self.current_page = page_num
            self.update_size()
            self.update()
            self.page_changed.emit(self.current_page)

            # In continuous view, scroll to the page
            if self.continuous_view:
                self.scroll_to_page(page_num)

    def scroll_to_page(self, page_num: int):
        """Scroll to a specific page in continuous view"""
        if not self.continuous_view:
            return

        # The canvas is inside a QScrollArea viewport, so parent().parent() gets the scroll area
        from PyQt6.QtWidgets import QScrollArea
        parent = self.parent()
        if parent:
            scroll_area = parent.parent() if not isinstance(parent, QScrollArea) else parent
            if isinstance(scroll_area, QScrollArea):
                page_y = self.get_page_y_offset(page_num)
                scroll_area.verticalScrollBar().setValue(int(page_y))

    def next_page(self):
        """Go to next page"""
        if self.current_page < self.pdf_doc.page_count - 1:
            self.set_page(self.current_page + 1)

    def previous_page(self):
        """Go to previous page"""
        if self.current_page > 0:
            self.set_page(self.current_page - 1)

    def set_zoom(self, zoom: float):
        """Set zoom level"""
        self.zoom = max(self.min_zoom, min(self.max_zoom, zoom))
        self.update_size()
        self.update()
        self.zoom_changed.emit(self.zoom)

    def zoom_in(self):
        """Zoom in"""
        self.set_zoom(self.zoom * 1.25)

    def zoom_out(self):
        """Zoom out"""
        self.set_zoom(self.zoom / 1.25)

    def fit_to_width(self):
        """Fit page to canvas width"""
        if self.pdf_doc.doc:
            page_size = self.pdf_doc.get_page_size(self.current_page)
            if page_size:
                parent_width = self.parent().viewport().width() if isinstance(self.parent(), QScrollArea) else self.width()
                zoom = (parent_width - 40) / page_size[0]
                self.set_zoom(zoom)

    def fit_to_page(self):
        """Fit entire page to canvas"""
        if self.pdf_doc.doc:
            page_size = self.pdf_doc.get_page_size(self.current_page)
            if page_size:
                parent = self.parent()
                if isinstance(parent, QScrollArea):
                    viewport = parent.viewport()
                    zoom_w = (viewport.width() - 40) / page_size[0]
                    zoom_h = (viewport.height() - 40) / page_size[1]
                    zoom = min(zoom_w, zoom_h)
                    self.set_zoom(zoom)

    def set_continuous_view(self, enabled: bool):
        """Enable or disable continuous view mode"""
        if self.continuous_view != enabled:
            self.continuous_view = enabled
            self.update_size()
            self.update()
            self.continuous_view_changed.emit(enabled)

    def is_continuous_view(self) -> bool:
        """Check if continuous view is enabled"""
        return self.continuous_view

    def update_size(self):
        """Update widget size based on page size and zoom"""
        if self.pdf_doc.doc:
            if self.continuous_view:
                # Calculate total height for all pages
                self._calculate_page_offsets()
                max_width = 0
                total_height = 0

                for page_num in range(self.pdf_doc.page_count):
                    page_size = self.pdf_doc.get_page_size(page_num)
                    if page_size:
                        width = int(page_size[0] * self.zoom)
                        height = int(page_size[1] * self.zoom)
                        max_width = max(max_width, width)
                        total_height += height + self.PAGE_GAP

                # Remove last gap
                if total_height > 0:
                    total_height -= self.PAGE_GAP

                self.setMinimumSize(max_width, total_height)
                self.resize(max_width, total_height)
            else:
                # Single page mode
                page_size = self.pdf_doc.get_page_size(self.current_page)
                if page_size:
                    width = int(page_size[0] * self.zoom)
                    height = int(page_size[1] * self.zoom)
                    self.setMinimumSize(width, height)
                    self.resize(width, height)

    def _calculate_page_offsets(self):
        """Calculate Y offset for each page in continuous view"""
        self.page_offsets = []
        current_offset = 0

        if not self.pdf_doc.doc:
            return

        for page_num in range(self.pdf_doc.page_count):
            self.page_offsets.append(current_offset)
            page_size = self.pdf_doc.get_page_size(page_num)
            if page_size:
                current_offset += int(page_size[1] * self.zoom) + self.PAGE_GAP

    def get_page_at_position(self, y_pos: float) -> int:
        """Get the page number at a given Y position (in widget coordinates)"""
        if not self.continuous_view or not self.page_offsets:
            return self.current_page

        for page_num in range(len(self.page_offsets) - 1, -1, -1):
            if y_pos >= self.page_offsets[page_num]:
                return page_num

        return 0

    def get_page_y_offset(self, page_num: int) -> int:
        """Get the Y offset for a specific page"""
        if not self.continuous_view or page_num >= len(self.page_offsets):
            return 0
        return self.page_offsets[page_num]

    def paintEvent(self, event):
        """Paint the PDF page and layers"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Fill background with dark gray (gap color)
        painter.fillRect(self.rect(), QColor("#2b2b2b"))

        if self.pdf_doc.doc:
            if self.continuous_view:
                # Draw all pages vertically
                self._paint_continuous_view(painter, event)
            else:
                # Draw single page
                self._paint_single_page(painter)

        # Draw tool preview (only for current page context)
        if self.current_tool:
            if self.continuous_view:
                # Offset preview to current page position
                painter.save()
                painter.translate(0, self.get_page_y_offset(self.current_page))
                self.current_tool.draw_preview(painter, self.zoom)
                painter.restore()
            else:
                self.current_tool.draw_preview(painter, self.zoom)

        # Draw guides on top of everything (non-printing visual aids)
        self._paint_guides(painter)

    def _paint_guides(self, painter: QPainter):
        """Paint non-printing guides on the canvas

        Guides span the full canvas width/height, starting from ruler edge (position 0)
        regardless of where the document is positioned.
        """
        if not self._guide_manager:
            return

        from core.guide_manager import GuideOrientation

        # Guide color - bright green
        guide_color = QColor("#00FF00")
        selected_color = QColor("#FFFF00")  # Yellow for selected guide

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # Crisp lines

        # Get full canvas dimensions for guide lines
        canvas_width = self.width()
        canvas_height = self.height()

        # Get guides for current page (or all pages in continuous view)
        if self.continuous_view:
            guides = set()
            for page_num in range(self.pdf_doc.page_count):
                guides.update(self._guide_manager.get_guides_for_page(page_num))
        else:
            guides = self._guide_manager.get_guides_for_page(self.current_page)

        for guide in guides:
            is_selected = guide == self._guide_manager.selected_guide
            color = selected_color if is_selected else guide_color
            pen = QPen(color, 1, Qt.PenStyle.SolidLine)
            painter.setPen(pen)

            if guide.orientation == GuideOrientation.HORIZONTAL:
                # Horizontal guide - line across entire canvas at Y position
                screen_y = int(guide.position * self.zoom)
                painter.drawLine(0, screen_y, canvas_width, screen_y)
            else:
                # Vertical guide - line down entire canvas at X position
                screen_x = int(guide.position * self.zoom)
                painter.drawLine(screen_x, 0, screen_x, canvas_height)

        # Draw guide preview during drag from ruler
        if self._dragging_guide_preview:
            orientation, position = self._dragging_guide_preview
            pen = QPen(QColor("#00FF00"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)

            if orientation == GuideOrientation.HORIZONTAL:
                screen_y = int(position * self.zoom)
                painter.drawLine(0, screen_y, canvas_width, screen_y)
            else:
                screen_x = int(position * self.zoom)
                painter.drawLine(screen_x, 0, screen_x, canvas_height)

    def set_guide_manager(self, guide_manager):
        """Set the guide manager for this canvas"""
        self._guide_manager = guide_manager
        if guide_manager:
            guide_manager.guides_changed.connect(self.update)

    def set_guide_preview(self, orientation, position):
        """Set a guide preview position (during drag from ruler)"""
        self._dragging_guide_preview = (orientation, position) if position is not None else None
        self.update()

    def clear_guide_preview(self):
        """Clear the guide preview"""
        self._dragging_guide_preview = None
        self.update()

    def _paint_single_page(self, painter: QPainter):
        """Paint a single page (non-continuous mode)"""
        # Fill page background
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        # Draw PDF page
        pixmap = self.pdf_doc.render_page(self.current_page, self.zoom)
        if pixmap:
            painter.drawPixmap(0, 0, pixmap)

        # Draw layers for current page
        layers = self.layer_manager.get_layers_for_page(self.current_page)
        for layer in layers:
            if layer.visible:
                layer.render(painter, self.zoom)

    def _paint_continuous_view(self, painter: QPainter, event):
        """Paint all pages in continuous view mode"""
        # Get visible rect to optimize rendering
        visible_rect = event.rect()

        for page_num in range(self.pdf_doc.page_count):
            page_size = self.pdf_doc.get_page_size(page_num)
            if not page_size:
                continue

            page_y = self.page_offsets[page_num] if page_num < len(self.page_offsets) else 0
            page_width = int(page_size[0] * self.zoom)
            page_height = int(page_size[1] * self.zoom)

            # Check if page is visible
            page_rect = QRectF(0, page_y, page_width, page_height)
            if not page_rect.intersects(QRectF(visible_rect)):
                continue

            # Draw page background (white)
            painter.fillRect(page_rect, QColor("#FFFFFF"))

            # Draw PDF page
            pixmap = self.pdf_doc.render_page(page_num, self.zoom)
            if pixmap:
                painter.drawPixmap(0, int(page_y), pixmap)

            # Draw layers for this page
            painter.save()
            painter.translate(0, page_y)
            layers = self.layer_manager.get_layers_for_page(page_num)
            for layer in layers:
                if layer.visible:
                    layer.render(painter, self.zoom)
            painter.restore()

            # Draw subtle page border
            painter.setPen(QPen(QColor("#CCCCCC"), 1))
            painter.drawRect(page_rect)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press"""
        # In continuous view, detect which page was clicked
        if self.continuous_view:
            page_num, pos = self.widget_to_page_coords_with_page(event.position())
            # Update current page if clicking on a different page
            if page_num != self.current_page:
                self.current_page = page_num
                self.page_changed.emit(self.current_page)
        else:
            pos = self.widget_to_page_coords(event.position())

        # Middle button for panning
        if event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = True
            self.last_pan_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        # Pass to current tool
        if self.current_tool:
            handled = self.current_tool.mouse_press(event, self.current_page, pos)
            if handled:
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move"""
        if self.is_panning:
            # Handle panning
            delta = event.position() - self.last_pan_pos
            self.last_pan_pos = event.position()

            scroll_area = self.parent()
            if isinstance(scroll_area, QScrollArea):
                h_bar = scroll_area.horizontalScrollBar()
                v_bar = scroll_area.verticalScrollBar()
                h_bar.setValue(h_bar.value() - int(delta.x()))
                v_bar.setValue(v_bar.value() - int(delta.y()))
            return

        pos = self.widget_to_page_coords(event.position())

        # Pass to current tool
        if self.current_tool:
            handled = self.current_tool.mouse_move(event, self.current_page, pos)
            if handled:
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        if event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = False
            if self.current_tool:
                self.setCursor(self.current_tool.get_cursor())
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        pos = self.widget_to_page_coords(event.position())

        # Pass to current tool
        if self.current_tool:
            from tools import TextTool, StickyNoteTool
            handled = self.current_tool.mouse_release(event, self.current_page, pos)

            if handled:
                # Check if tool created a layer
                if isinstance(self.current_tool, TextTool):
                    # Show text input dialog
                    text, ok = QInputDialog.getText(self, "Add Text", "Enter text:")
                    if ok and text:
                        layer = self.current_tool.create_text_layer(self.current_page, pos, text)
                        self.add_layer(layer)

                elif isinstance(self.current_tool, StickyNoteTool):
                    # Show note input dialog
                    text, ok = QInputDialog.getMultiLineText(self, "Add Note", "Enter note:")
                    if ok and text:
                        layer = self.current_tool.create_note_layer(self.current_page, pos, text)
                        self.add_layer(layer)

                else:
                    # Get completed layer from tool
                    layer = self.current_tool.get_completed_layer()
                    if layer:
                        self.add_layer(layer)

                self.update()

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming"""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom with Ctrl + Wheel
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            # Let parent handle scrolling
            super().wheelEvent(event)

    def widget_to_page_coords(self, widget_pos) -> QPointF:
        """Convert widget coordinates to page coordinates"""
        if self.continuous_view:
            # In continuous view, we need to offset by the current page's Y position
            page_y_offset = self.get_page_y_offset(self.current_page)
            return QPointF(widget_pos.x() / self.zoom,
                          (widget_pos.y() - page_y_offset) / self.zoom)
        else:
            return QPointF(widget_pos.x() / self.zoom, widget_pos.y() / self.zoom)

    def widget_to_page_coords_with_page(self, widget_pos) -> tuple:
        """Convert widget coordinates to page coordinates and determine which page.
        Returns (page_num, QPointF in page coords)"""
        if self.continuous_view:
            # Determine which page the click is on
            page_num = self.get_page_at_position(widget_pos.y())
            page_y_offset = self.get_page_y_offset(page_num)
            page_coords = QPointF(widget_pos.x() / self.zoom,
                                 (widget_pos.y() - page_y_offset) / self.zoom)
            return (page_num, page_coords)
        else:
            return (self.current_page,
                   QPointF(widget_pos.x() / self.zoom, widget_pos.y() / self.zoom))

    def add_layer(self, layer: Layer):
        """Add a layer and record in history"""
        self.layer_manager.add_layer(layer)
        action = Action(ActionType.ADD_LAYER, {'layer': layer.to_dict()}, f"Add {layer.name}")
        self.history_manager.add_action(action)
        self.layer_added.emit(layer)
        self.update()

    def remove_layer(self, layer_id: str):
        """Remove a layer and record in history"""
        layer = self.layer_manager.get_layer(layer_id)
        if layer:
            action = Action(ActionType.REMOVE_LAYER, {'layer': layer.to_dict()}, f"Remove {layer.name}")
            self.history_manager.add_action(action)
            self.layer_manager.remove_layer(layer_id)
            self.update()

    def undo(self):
        """Undo last action"""
        action = self.history_manager.undo()
        if action:
            self.apply_action_reverse(action)
            self.update()

    def redo(self):
        """Redo last undone action"""
        action = self.history_manager.redo()
        if action:
            self.apply_action(action)
            self.update()

    def apply_action(self, action: Action):
        """Apply an action"""
        if action.type == ActionType.ADD_LAYER:
            layer = Layer.from_dict(action.data['layer'])
            self.layer_manager.add_layer(layer)
        elif action.type == ActionType.REMOVE_LAYER:
            layer_id = action.data['layer']['id']
            self.layer_manager.remove_layer(layer_id)

    def apply_action_reverse(self, action: Action):
        """Apply reverse of an action"""
        if action.type == ActionType.ADD_LAYER:
            layer_id = action.data['layer']['id']
            self.layer_manager.remove_layer(layer_id)
        elif action.type == ActionType.REMOVE_LAYER:
            layer = Layer.from_dict(action.data['layer'])
            self.layer_manager.add_layer(layer)


class PDFCanvas(QScrollArea):
    """Scroll area containing the PDF canvas"""

    def __init__(self, pdf_doc: PDFDocument, layer_manager: LayerManager,
                 history_manager: HistoryManager):
        super().__init__()
        self.canvas = PDFCanvasWidget(pdf_doc, layer_manager, history_manager)
        self.setWidget(self.canvas)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Style
        self.setStyleSheet("""
            QScrollArea {
                background-color: #2b2b2b;
                border: none;
            }
        """)

    def get_canvas(self) -> PDFCanvasWidget:
        """Get the canvas widget"""
        return self.canvas
