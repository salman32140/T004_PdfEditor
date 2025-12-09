"""
Enhanced PDF Canvas with Interactive Text Field Support
Supports selecting, editing, moving, and deleting text fields, images, and symbols
"""
from PyQt6.QtWidgets import QMenu, QInputDialog, QApplication
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QAction, QCursor
from .pdf_canvas import PDFCanvasWidget
from .text_edit_dialog import TextEditDialog
from .image_dialog import ImageDialog
from .symbol_dialog import SymbolDialog
from core.interactive_layer import TextFieldLayer, ImageLayer, SymbolLayer, ImageScaleMode, ResizeHandle
from core import Action, ActionType
from core.layer import Layer, LayerType
from tools import BaseTool, TextSelectionTool
from typing import Optional, Dict, Any, List
import fitz


class InteractivePDFCanvas(PDFCanvasWidget):
    """Enhanced canvas with interactive text field support"""

    text_field_selected = pyqtSignal(object)  # Emits selected text field layer
    text_field_deselected = pyqtSignal()
    text_selection_changed = pyqtSignal(bool)  # Emits True when text is selected, False otherwise
    color_used = pyqtSignal(str)  # Emits when a color is used (from dialogs like symbol, text, etc.)
    multi_layer_selection_changed = pyqtSignal(int)  # Emits count of selected layers (for alignment UI)

    def __init__(self, pdf_doc, layer_manager, history_manager):
        super().__init__(pdf_doc, layer_manager, history_manager)

        self.selected_layer: Optional[TextFieldLayer] = None
        self.is_dragging_layer = False
        self.drag_start_pos: Optional[QPointF] = None
        self.layer_start_pos: Optional[tuple] = None
        self.hover_layer: Optional[TextFieldLayer] = None

        # Copy/paste functionality
        self.copied_layers = []

        # Rotation functionality
        self.is_rotating_layer = False
        self.rotation_start_angle = 0
        self.layer_start_rotation = 0
        self.hovering_rotation_handle = False  # Track if hovering over rotation handle

        # Resize functionality
        self.is_resizing_layer = False
        self.resize_handle = ResizeHandle.NONE
        self.resize_start_pos: Optional[QPointF] = None
        self.layer_start_bounds: Optional[dict] = None  # Store original x, y, width, height
        self.hovering_resize_handle = ResizeHandle.NONE  # Track which resize handle is being hovered

        # Retain last used text field settings
        self.last_text_settings = {
            'font': 'Arial',
            'font_size': 12,
            'color': '#000000',
            'bold': False,
            'italic': False,
            'underline': False
        }

        # Flag to indicate if document is from translation (enables "Convert to Editable Layer")
        self.is_translated_document = False

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press with text field selection"""
        # In continuous view, detect which page was clicked and update current page
        if self.continuous_view:
            page_num, pos = self.widget_to_page_coords_with_page(event.position())
            if page_num != self.current_page:
                self.current_page = page_num
                self.page_changed.emit(self.current_page)
        else:
            pos = self.widget_to_page_coords(event.position())

        # Right-click context menu
        if event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.position(), pos)
            return

        # Middle button for panning
        if event.button() == Qt.MouseButton.MiddleButton:
            self.is_panning = True
            self.last_pan_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        # Left click - check tool first, then layer selection
        if event.button() == Qt.MouseButton.LeftButton:
            widget_point = QPointF(event.position().x(), event.position().y())

            # In continuous view, adjust widget_point to be relative to current page
            if self.continuous_view:
                page_y_offset = self.get_page_y_offset(self.current_page)
                widget_point = QPointF(event.position().x(), event.position().y() - page_y_offset)

            # HIGHEST PRIORITY: If hovering over resize handle, start resizing immediately
            if self.hovering_resize_handle != ResizeHandle.NONE:
                resize_layer = None

                if self.selected_layer and self.selected_layer.selected:
                    handle = self.selected_layer.get_resize_handle_at(widget_point, zoom=self.zoom)
                    if handle != ResizeHandle.NONE:
                        resize_layer = self.selected_layer
                        self.resize_handle = handle

                # Check multi-selection layers
                if not resize_layer:
                    from tools.selection_tool import SelectionTool
                    if isinstance(self.current_tool, SelectionTool):
                        if self.current_tool.selected_layers:
                            for layer in self.current_tool.selected_layers:
                                handle = layer.get_resize_handle_at(widget_point, zoom=self.zoom)
                                if handle != ResizeHandle.NONE:
                                    resize_layer = layer
                                    self.resize_handle = handle
                                    break

                # Start resizing if we found the layer
                if resize_layer:
                    self.is_resizing_layer = True
                    self.selected_layer = resize_layer
                    self.resize_start_pos = pos  # Use page coordinates
                    self.layer_start_bounds = {
                        'x': resize_layer.data.get('x', 0),
                        'y': resize_layer.data.get('y', 0),
                        'width': resize_layer.data.get('width', 100),
                        'height': resize_layer.data.get('height', 100)
                    }
                    event.accept()
                    self.update()
                    return

            # SECOND PRIORITY: If hovering over rotation handle, start rotation immediately
            # This flag is set in mouseMoveEvent when cursor shows rotation icon
            if self.hovering_rotation_handle:
                # Find which layer's rotation handle we're over
                rotation_layer = None

                if self.selected_layer and self.selected_layer.selected:
                    if self.selected_layer.is_rotation_handle(widget_point, zoom=self.zoom):
                        rotation_layer = self.selected_layer

                # Check multi-selection layers
                if not rotation_layer:
                    from tools.selection_tool import SelectionTool
                    if isinstance(self.current_tool, SelectionTool):
                        if self.current_tool.selected_layers:
                            for layer in self.current_tool.selected_layers:
                                if layer.is_rotation_handle(widget_point, zoom=self.zoom):
                                    rotation_layer = layer
                                    break

                # Start rotation if we found the layer
                if rotation_layer:
                    self.is_rotating_layer = True
                    self.selected_layer = rotation_layer
                    # Use page coordinates for rotation angle calculation
                    bounds = rotation_layer.get_bounds(zoom=1.0)
                    if bounds:
                        center = bounds.center()
                        import math
                        self.rotation_start_angle = math.atan2(
                            pos.y() - center.y(),
                            pos.x() - center.x()
                        )
                        self.layer_start_rotation = rotation_layer.rotation
                    event.accept()  # BLOCK all other event handling
                    self.update()
                    return

            # Check if selection tool is active
            from tools.selection_tool import SelectionTool
            if isinstance(self.current_tool, SelectionTool):
                # Check if clicking on an existing layer
                clicked_layer = self.find_layer_at_point(pos)

                # If clicked on empty space (not on layer, not on rotation handle), deselect all layers
                if not clicked_layer:
                    self.deselect_all_layers()
                    self.current_tool.clear_selected_layers()
                    self.update()

                # Let selection tool handle all mouse events
                handled = self.current_tool.mouse_press(event, self.current_page, pos)
                if handled:
                    self.update()
                return

            # For non-selection tools: Check if clicking on an existing layer
            clicked_layer = self.find_layer_at_point(pos)

            # If we clicked on a layer, select it and start dragging
            if clicked_layer:
                self.select_layer(clicked_layer)
                self.is_dragging_layer = True
                self.drag_start_pos = pos
                self.layer_start_pos = (
                    clicked_layer.data.get('x', 0),
                    clicked_layer.data.get('y', 0)
                )
                self.update()
                return

            # Deselect if clicking on empty space
            if self.selected_layer:
                self.deselect_layer()
                self.update()

        # Pass to current tool if no selection happened
        if self.current_tool:
            handled = self.current_tool.mouse_press(event, self.current_page, pos)
            if handled:
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move with layer dragging"""
        pos = self.widget_to_page_coords(event.position())
        widget_pos = event.position()  # Keep widget coordinates for rotation handle detection

        # Handle panning
        if self.is_panning:
            delta = event.position() - self.last_pan_pos
            self.last_pan_pos = event.position()

            scroll_area = self.parent()
            from PyQt6.QtWidgets import QScrollArea
            if isinstance(scroll_area, QScrollArea):
                h_bar = scroll_area.horizontalScrollBar()
                v_bar = scroll_area.verticalScrollBar()
                h_bar.setValue(h_bar.value() - int(delta.x()))
                v_bar.setValue(v_bar.value() - int(delta.y()))
            return

        # Handle resizing FIRST (highest priority)
        if self.is_resizing_layer and self.selected_layer and self.resize_start_pos:
            # Calculate delta in page coordinates
            delta_x = pos.x() - self.resize_start_pos.x()
            delta_y = pos.y() - self.resize_start_pos.y()

            # Check if Shift key is pressed for aspect ratio lock
            modifiers = QApplication.keyboardModifiers() if hasattr(QApplication, 'keyboardModifiers') else event.modifiers()
            keep_aspect_ratio = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

            # Restore original bounds before applying new resize
            if self.layer_start_bounds:
                self.selected_layer.data['x'] = self.layer_start_bounds['x']
                self.selected_layer.data['y'] = self.layer_start_bounds['y']
                self.selected_layer.data['width'] = self.layer_start_bounds['width']
                self.selected_layer.data['height'] = self.layer_start_bounds['height']

            # Apply resize
            self.selected_layer.resize(self.resize_handle, delta_x, delta_y, keep_aspect_ratio)
            self.update()
            return

        # Handle rotation (second priority)
        if self.is_rotating_layer and self.selected_layer:
            bounds = self.selected_layer.get_bounds(zoom=1.0)
            if bounds:
                center = bounds.center()
                # Calculate current angle from center to mouse
                import math
                current_angle = math.atan2(
                    pos.y() - center.y(),
                    pos.x() - center.x()
                )
                # Calculate rotation delta in degrees
                angle_delta = math.degrees(current_angle - self.rotation_start_angle)
                # Update layer rotation
                self.selected_layer.rotation = self.layer_start_rotation + angle_delta
                self.update()
            return

        # Check if hovering over resize or rotation handle (highest priority for cursor)
        # This must happen BEFORE selection tool handling to ensure cursor always updates
        # Use widget coordinates and actual zoom since handles are rendered in widget space
        self.hovering_rotation_handle = False
        self.hovering_resize_handle = ResizeHandle.NONE
        from tools.selection_tool import SelectionTool

        # In continuous view, adjust widget_point to be relative to current page
        widget_point = QPointF(widget_pos.x(), widget_pos.y())
        if self.continuous_view:
            page_y_offset = self.get_page_y_offset(self.current_page)
            widget_point = QPointF(widget_pos.x(), widget_pos.y() - page_y_offset)

        # Helper function to get resize cursor based on handle
        def get_resize_cursor(handle: ResizeHandle) -> Qt.CursorShape:
            if handle in (ResizeHandle.TOP_LEFT, ResizeHandle.BOTTOM_RIGHT):
                return Qt.CursorShape.SizeFDiagCursor
            elif handle in (ResizeHandle.TOP_RIGHT, ResizeHandle.BOTTOM_LEFT):
                return Qt.CursorShape.SizeBDiagCursor
            return Qt.CursorShape.ArrowCursor

        # Check selected layer's resize handles FIRST (before rotation)
        if self.selected_layer and self.selected_layer.selected:
            handle = self.selected_layer.get_resize_handle_at(widget_point, zoom=self.zoom)
            if handle != ResizeHandle.NONE:
                self.setCursor(get_resize_cursor(handle))
                self.hovering_resize_handle = handle
                self.update()
                return

        # Check multi-selection layers for resize handles
        if isinstance(self.current_tool, SelectionTool) and self.current_tool.selected_layers:
            for layer in self.current_tool.selected_layers:
                handle = layer.get_resize_handle_at(widget_point, zoom=self.zoom)
                if handle != ResizeHandle.NONE:
                    self.setCursor(get_resize_cursor(handle))
                    self.hovering_resize_handle = handle
                    self.update()
                    return

        # Check selected layer's rotation handle
        if self.selected_layer and self.selected_layer.selected:
            if self.selected_layer.is_rotation_handle(widget_point, zoom=self.zoom):
                self.setCursor(Qt.CursorShape.CrossCursor)  # Cross cursor for rotation
                self.hovering_rotation_handle = True

        # Check all selected layers (for selection tool multi-select) for rotation handle
        if not self.hovering_rotation_handle and isinstance(self.current_tool, SelectionTool):
            if self.current_tool.selected_layers:
                for layer in self.current_tool.selected_layers:
                    if layer.is_rotation_handle(widget_point, zoom=self.zoom):
                        self.setCursor(Qt.CursorShape.CrossCursor)  # Cross cursor for rotation
                        self.hovering_rotation_handle = True
                        break

        # If hovering rotation handle, just update and return
        if self.hovering_rotation_handle:
            self.update()
            return

        # Let selection tool handle its own movement
        if isinstance(self.current_tool, SelectionTool):
            handled = self.current_tool.mouse_move(event, self.current_page, pos)
            if handled:
                self.update()
                return

        # Handle layer dragging (only when selection tool not active)
        if self.is_dragging_layer and self.selected_layer and self.drag_start_pos:
            if self.layer_start_pos:
                dx = pos.x() - self.drag_start_pos.x()
                dy = pos.y() - self.drag_start_pos.y()

                self.selected_layer.data['x'] = self.layer_start_pos[0] + dx
                self.selected_layer.data['y'] = self.layer_start_pos[1] + dy

                self.update()
                return

        # Update hover cursor for layers
        hover_layer = self.find_layer_at_point(pos)
        if hover_layer and not self.current_tool:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.current_tool:
            # Use tool's cursor
            self.setCursor(self.current_tool.get_cursor())
        elif not self.is_panning:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # Pass to current tool
        if self.current_tool and not self.is_dragging_layer:
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

        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_resizing_layer:
                self.is_resizing_layer = False
                self.resize_handle = ResizeHandle.NONE
                self.resize_start_pos = None
                self.layer_start_bounds = None
                return

            if self.is_rotating_layer:
                self.is_rotating_layer = False
                self.rotation_start_angle = 0
                self.layer_start_rotation = 0
                return

            if self.is_dragging_layer:
                self.is_dragging_layer = False
                self.drag_start_pos = None
                self.layer_start_pos = None
                return

        # Handle tool-specific releases
        pos = self.widget_to_page_coords(event.position())

        if self.current_tool:
            from tools.interactive_text_tool import InteractiveTextTool
            from tools.interactive_image_tool import InteractiveImageTool
            from tools.symbol_tool import SymbolTool
            from tools.selection_tool import SelectionTool

            # Handle SelectionTool specially
            if isinstance(self.current_tool, SelectionTool):
                handled = self.current_tool.mouse_release(event, self.current_page, pos)
                if handled:
                    # Check if box selection was completed
                    selection_box = self.current_tool.get_selection_box()
                    if selection_box:
                        # Find all layers within the selection box
                        selected_layers = self.find_layers_in_box(selection_box)

                        # Deselect all previous
                        self.deselect_all_layers()

                        # Select all layers in box
                        for layer in selected_layers:
                            layer.selected = True

                        # Update tool's selected layers
                        self.current_tool.set_selected_layers(selected_layers)

                        # Clear the box selection state
                        self.current_tool.clear_box_selection()

                        # Emit multi-layer selection changed signal
                        self.multi_layer_selection_changed.emit(len(selected_layers))

                    self.update()
                return

            # Handle InteractiveTextTool specially
            if isinstance(self.current_tool, InteractiveTextTool):
                handled = self.current_tool.mouse_release(event, self.current_page, pos)
                if handled and self.current_tool.pending_creation:
                    # Show text edit dialog
                    self.show_text_creation_dialog(pos)
                return

            # Handle InteractiveImageTool specially
            if isinstance(self.current_tool, InteractiveImageTool):
                handled = self.current_tool.mouse_release(event, self.current_page, pos)
                if handled and self.current_tool.pending_creation:
                    # Show image dialog
                    self.show_image_creation_dialog(pos)
                return

            # Handle SymbolTool specially
            if isinstance(self.current_tool, SymbolTool):
                handled = self.current_tool.mouse_press(event, self.current_page, pos)
                if handled and self.current_tool.is_pending_creation():
                    if self.current_tool.should_show_dialog():
                        # Right-click - show symbol selection dialog
                        self.show_symbol_creation_dialog(pos)
                    else:
                        # Left-click - stamp symbol immediately with current settings
                        self.stamp_symbol_at_position(pos)
                return

            # Handle TextSelectionTool specially - only select, don't auto-apply annotation
            if isinstance(self.current_tool, TextSelectionTool):
                handled = self.current_tool.mouse_release(event, self.current_page, pos)
                if handled:
                    # Just update the canvas to show selection - don't create annotation
                    # Annotation will be created when user clicks action button
                    self.update()
                    # Emit signal that text selection changed
                    self.text_selection_changed.emit(self.current_tool.has_active_selection())
                return

            # Handle other tools
            handled = self.current_tool.mouse_release(event, self.current_page, pos)
            if handled:
                # Get completed layer from tool
                layer = self.current_tool.get_completed_layer()
                if layer:
                    self.add_layer(layer)
                self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle double-click to edit text field, image, or symbol"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.widget_to_page_coords(event.position())
            layer = self.find_layer_at_point(pos)

            if layer:
                if isinstance(layer, TextFieldLayer):
                    self.edit_text_field(layer)
                elif isinstance(layer, ImageLayer):
                    self.edit_image_layer(layer)
                elif isinstance(layer, SymbolLayer):
                    self.edit_symbol_layer(layer)

    def find_layer_at_point(self, point: QPointF):
        """Find interactive layer at given point (TextFieldLayer, ImageLayer, or SymbolLayer)"""
        layers = self.layer_manager.get_layers_for_page(self.current_page)

        # Check from top to bottom (reverse order)
        # Point is in page coordinates, so use zoom=1.0
        for layer in reversed(layers):
            if isinstance(layer, (TextFieldLayer, ImageLayer, SymbolLayer)) and layer.visible:
                if layer.contains_point(point, zoom=1.0):
                    return layer

        return None

    def find_pdf_text_at_point(self, point: QPointF) -> Optional[Dict[str, Any]]:
        """
        Find PDF text at the given point

        Args:
            point: Point in page coordinates

        Returns:
            Dict with text info (text, rect, font, size, color) or None
        """
        if not self.pdf_doc or not self.pdf_doc.doc:
            return None

        page = self.pdf_doc.get_page(self.current_page)
        if not page:
            return None

        # Get text blocks with detailed info
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        px, py = point.x(), point.y()

        # Search through blocks -> lines -> spans
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    # Check if point is within this span's bounding box
                    if bbox[0] <= px <= bbox[2] and bbox[1] <= py <= bbox[3]:
                        text = span.get("text", "")
                        if text.strip():
                            # Extract font info
                            font = span.get("font", "helv")
                            size = span.get("size", 12)
                            color_int = span.get("color", 0)
                            flags = span.get("flags", 0)

                            # Convert color int to hex
                            r = (color_int >> 16) & 0xFF
                            g = (color_int >> 8) & 0xFF
                            b = color_int & 0xFF
                            color_hex = f"#{r:02x}{g:02x}{b:02x}"

                            # Parse font flags for bold/italic
                            is_bold = bool(flags & 16)  # Bit 4
                            is_italic = bool(flags & 2)  # Bit 1

                            return {
                                "text": text,
                                "rect": bbox,
                                "font": font,
                                "size": size,
                                "color": color_hex,
                                "bold": is_bold,
                                "italic": is_italic
                            }

        return None

    def find_pdf_text_in_rect(self, selection_rect) -> List[Dict[str, Any]]:
        """
        Find all PDF text spans within a rectangle

        Args:
            selection_rect: QRectF selection rectangle in page coordinates

        Returns:
            List of dicts with text info (text, rect, font, size, color, bold, italic)
        """
        if not self.pdf_doc or not self.pdf_doc.doc:
            return []

        page = self.pdf_doc.get_page(self.current_page)
        if not page:
            return []

        # Get text blocks with detailed info
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        results = []
        sel_x1, sel_y1 = selection_rect.x(), selection_rect.y()
        sel_x2, sel_y2 = sel_x1 + selection_rect.width(), sel_y1 + selection_rect.height()

        # Search through blocks -> lines -> spans
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    text = span.get("text", "")

                    if not text.strip():
                        continue

                    # Check if span is inside or intersects with selection rect
                    span_x1, span_y1, span_x2, span_y2 = bbox

                    # Check if span center is within selection
                    span_cx = (span_x1 + span_x2) / 2
                    span_cy = (span_y1 + span_y2) / 2

                    if sel_x1 <= span_cx <= sel_x2 and sel_y1 <= span_cy <= sel_y2:
                        # Extract font info
                        font = span.get("font", "helv")
                        size = span.get("size", 12)
                        color_int = span.get("color", 0)
                        flags = span.get("flags", 0)

                        # Convert color int to hex
                        r = (color_int >> 16) & 0xFF
                        g = (color_int >> 8) & 0xFF
                        b = color_int & 0xFF
                        color_hex = f"#{r:02x}{g:02x}{b:02x}"

                        # Parse font flags for bold/italic
                        is_bold = bool(flags & 16)  # Bit 4
                        is_italic = bool(flags & 2)  # Bit 1

                        results.append({
                            "text": text,
                            "rect": bbox,
                            "font": font,
                            "size": size,
                            "color": color_hex,
                            "bold": is_bold,
                            "italic": is_italic
                        })

        return results

    def select_layer(self, layer: TextFieldLayer):
        """Select a text field layer"""
        # Deselect previous
        if self.selected_layer:
            self.selected_layer.selected = False

        # Select new
        self.selected_layer = layer
        layer.selected = True

        # Emit signal
        self.text_field_selected.emit(layer)

    def deselect_layer(self):
        """Deselect current layer"""
        if self.selected_layer:
            self.selected_layer.selected = False
            self.selected_layer = None
            self.text_field_deselected.emit()

    def deselect_all_layers(self):
        """Deselect all layers"""
        layers = self.layer_manager.get_layers_for_page(self.current_page)
        for layer in layers:
            if hasattr(layer, 'selected'):
                layer.selected = False

        if self.selected_layer:
            self.selected_layer = None
            self.text_field_deselected.emit()

        # Emit signal to hide alignment UI
        self.multi_layer_selection_changed.emit(0)

    def find_layers_in_box(self, selection_box):
        """Find all interactive layers within the selection box"""
        from PyQt6.QtCore import QRectF

        layers = self.layer_manager.get_layers_for_page(self.current_page)
        selected_layers = []

        for layer in layers:
            if isinstance(layer, (TextFieldLayer, ImageLayer, SymbolLayer)) and layer.visible:
                # Get layer bounds - use zoom 1.0 since selection_box is in page coordinates
                layer_bounds = layer.get_bounds(zoom=1.0)

                if layer_bounds and selection_box.intersects(layer_bounds):
                    selected_layers.append(layer)

        return selected_layers

    def show_text_creation_dialog(self, pos: QPointF):
        """Show dialog to create new text field"""
        from tools.interactive_text_tool import InteractiveTextTool

        # Get text box dimensions if available
        text_box_rect = None
        if isinstance(self.current_tool, InteractiveTextTool):
            text_box_rect = self.current_tool.get_text_box_rect()

        # Use last settings as initial values
        dialog = TextEditDialog(
            self,
            initial_text="",
            initial_font=self.last_text_settings['font'],
            initial_size=self.last_text_settings['font_size'],
            initial_color=self.last_text_settings['color'],
            initial_bold=self.last_text_settings['bold'],
            initial_italic=self.last_text_settings['italic'],
            initial_underline=self.last_text_settings['underline']
        )

        if dialog.exec() == dialog.DialogCode.Accepted:
            values = dialog.get_values()

            # Save settings for next time (regardless of whether text was entered)
            self.last_text_settings = {
                'font': values['font'],
                'font_size': values['font_size'],
                'color': values['color'],
                'bold': values['bold'],
                'italic': values['italic'],
                'underline': values['underline']
            }

            if values['text'].strip():  # Only create if text is not empty
                # Use text box dimensions or defaults
                if text_box_rect:
                    x = text_box_rect['x']
                    y = text_box_rect['y']
                    width = text_box_rect['width']
                    height = text_box_rect['height']
                else:
                    x = pos.x()
                    y = pos.y()
                    width = 150
                    height = 40

                # Create text field layer with box dimensions
                text_layer = TextFieldLayer(
                    self.current_page,
                    x,
                    y,
                    values['text'],
                    width,
                    height
                )

                text_layer.set_font(values['font'], values['font_size'])
                text_layer.set_color(values['color'])
                text_layer.set_style(values['bold'], values['italic'], values['underline'])

                # Add to layer manager
                self.add_layer(text_layer)

                # Select the new layer
                self.select_layer(text_layer)

                # Emit color_used signal to update tool settings
                self.color_used.emit(values['color'])

        # Clear pending from tool
        if self.current_tool:
            if isinstance(self.current_tool, InteractiveTextTool):
                self.current_tool.clear_pending()

    def edit_text_field(self, layer: TextFieldLayer):
        """Open edit dialog for text field"""
        dialog = TextEditDialog(
            self,
            initial_text=layer.get_text(),
            initial_font=layer.data.get('font', 'Arial'),
            initial_size=layer.data.get('font_size', 12),
            initial_color=layer.data.get('color', '#000000'),
            initial_bold=layer.data.get('bold', False),
            initial_italic=layer.data.get('italic', False),
            initial_underline=layer.data.get('underline', False)
        )

        if dialog.exec() == dialog.DialogCode.Accepted:
            values = dialog.get_values()

            # Update layer
            layer.set_text(values['text'])
            layer.set_font(values['font'], values['font_size'])
            layer.set_color(values['color'])
            layer.set_style(values['bold'], values['italic'], values['underline'])

            # Record action
            action = Action(
                ActionType.MODIFY_LAYER,
                {'layer_id': layer.id, 'changes': values},
                f"Edit {layer.name}"
            )
            self.history_manager.add_action(action)

            # Emit color_used signal to update tool settings
            self.color_used.emit(values['color'])

            self.update()

    def show_image_creation_dialog(self, pos: QPointF):
        """Show dialog to create new image layer"""
        from tools.interactive_image_tool import InteractiveImageTool

        # Get image frame dimensions if available
        image_frame_rect = None
        if isinstance(self.current_tool, InteractiveImageTool):
            image_frame_rect = self.current_tool.get_image_frame_rect()

        dialog = ImageDialog(self)

        if dialog.exec() == dialog.DialogCode.Accepted:
            values = dialog.get_values()

            if values['pixmap'] and not values['pixmap'].isNull():
                # Use image frame dimensions or defaults
                if image_frame_rect:
                    x = image_frame_rect['x']
                    y = image_frame_rect['y']
                    width = image_frame_rect['width']
                    height = image_frame_rect['height']
                else:
                    x = pos.x()
                    y = pos.y()
                    width = values['pixmap'].width()
                    height = values['pixmap'].height()

                # Create image layer with frame dimensions
                image_layer = ImageLayer(
                    self.current_page,
                    x,
                    y,
                    values['pixmap'],
                    width,
                    height,
                    values['image_path']
                )

                # Set scale mode
                image_layer.set_scale_mode(ImageScaleMode(values['scale_mode']))

                # Add to layer manager
                self.add_layer(image_layer)

                # Select the new layer
                self.select_layer(image_layer)

        # Clear pending from tool
        if self.current_tool:
            if isinstance(self.current_tool, InteractiveImageTool):
                self.current_tool.clear_pending()

    def edit_image_layer(self, layer: ImageLayer):
        """Open edit dialog for image layer"""
        dialog = ImageDialog(
            self,
            initial_image_path=layer.data.get('image_path'),
            initial_scale_mode=layer.data.get('scale_mode', ImageScaleMode.FIT.value)
        )

        if dialog.exec() == dialog.DialogCode.Accepted:
            values = dialog.get_values()

            # Update layer if new image selected
            if values['pixmap'] and not values['pixmap'].isNull():
                layer.set_image(values['pixmap'], values['image_path'])
                layer.set_scale_mode(ImageScaleMode(values['scale_mode']))

                # Record action
                action = Action(
                    ActionType.MODIFY_LAYER,
                    {'layer_id': layer.id, 'changes': values},
                    f"Edit {layer.name}"
                )
                self.history_manager.add_action(action)

                self.update()

    def stamp_symbol_at_position(self, pos: QPointF):
        """Stamp current symbol at position (left-click)"""
        from tools.symbol_tool import SymbolTool

        if not isinstance(self.current_tool, SymbolTool):
            return

        # Get click position from tool
        click_pos = pos
        tool_pos = self.current_tool.get_click_position()
        if tool_pos:
            click_pos = tool_pos

        # Get symbol settings from tool
        symbol = self.current_tool.get_symbol()
        size = self.current_tool.get_symbol_size()
        color = self.current_tool.get_symbol_color()

        # Calculate symbol bounding box size
        symbol_box_size = size * 1.2  # Same as SymbolLayer uses

        # Offset position so symbol is centered on click point
        # (cursor hotspot is at center, so click_pos is where center should be)
        centered_x = click_pos.x() - symbol_box_size / 2
        centered_y = click_pos.y() - symbol_box_size / 2

        # Create symbol layer
        symbol_layer = SymbolLayer(
            self.current_page,
            centered_x,
            centered_y,
            symbol,
            size
        )

        symbol_layer.set_color(color)

        # Add to layer manager
        self.add_layer(symbol_layer)

        # Clear pending from tool
        self.current_tool.reset()

        self.update()

    def show_symbol_creation_dialog(self, pos: QPointF):
        """Show dialog to create/select symbol (right-click)"""
        from tools.symbol_tool import SymbolTool

        # Get click position from tool
        click_pos = pos
        if isinstance(self.current_tool, SymbolTool):
            tool_pos = self.current_tool.get_click_position()
            if tool_pos:
                click_pos = tool_pos

        # Get current settings from tool for dialog defaults
        initial_symbol = ''
        initial_size = 24
        initial_color = '#000000'
        if isinstance(self.current_tool, SymbolTool):
            initial_symbol = self.current_tool.get_symbol()
            initial_size = self.current_tool.get_symbol_size()
            initial_color = self.current_tool.get_symbol_color()

        dialog = SymbolDialog(
            self,
            initial_symbol=initial_symbol,
            initial_font_size=initial_size,
            initial_color=initial_color
        )

        if dialog.exec() == dialog.DialogCode.Accepted:
            values = dialog.get_values()

            if values['symbol']:
                # Update tool with new symbol settings
                if isinstance(self.current_tool, SymbolTool):
                    self.current_tool.set_symbol(values['symbol'])
                    self.current_tool.set_symbol_size(values['font_size'])
                    self.current_tool.set_symbol_color(values['color'])

                    # Update cursor on canvas
                    self.setCursor(self.current_tool.cursor)

                # Calculate symbol bounding box size
                symbol_box_size = values['font_size'] * 1.2  # Same as SymbolLayer uses

                # Offset position so symbol is centered on click point
                centered_x = click_pos.x() - symbol_box_size / 2
                centered_y = click_pos.y() - symbol_box_size / 2

                # Create symbol layer at centered position
                symbol_layer = SymbolLayer(
                    self.current_page,
                    centered_x,
                    centered_y,
                    values['symbol'],
                    values['font_size']
                )

                symbol_layer.set_color(values['color'])

                # Add to layer manager
                self.add_layer(symbol_layer)

                # Select the new layer
                self.select_layer(symbol_layer)

                # Emit color_used signal to update tool settings
                self.color_used.emit(values['color'])

        # Clear pending from tool
        if self.current_tool:
            if isinstance(self.current_tool, SymbolTool):
                self.current_tool.reset()

    def edit_symbol_layer(self, layer: SymbolLayer):
        """Open edit dialog for symbol"""
        dialog = SymbolDialog(
            self,
            initial_symbol=layer.get_symbol(),
            initial_font_size=layer.data.get('font_size', 24),
            initial_color=layer.data.get('color', '#000000')
        )

        if dialog.exec() == dialog.DialogCode.Accepted:
            values = dialog.get_values()

            # Update layer
            layer.set_symbol(values['symbol'])
            layer.set_font_size(values['font_size'])
            layer.set_color(values['color'])

            # Record action
            action = Action(
                ActionType.MODIFY_LAYER,
                {'layer_id': layer.id, 'changes': values},
                f"Edit {layer.name}"
            )
            self.history_manager.add_action(action)

            # Emit color_used signal to update tool settings
            self.color_used.emit(values['color'])

            self.update()

    def delete_selected_layer(self):
        """Delete the currently selected layer"""
        if self.selected_layer:
            layer_id = self.selected_layer.id
            self.deselect_layer()
            self.remove_layer(layer_id)

    def delete_selected_layers(self):
        """Delete all currently selected layers (for multi-selection)"""
        from tools.selection_tool import SelectionTool

        # Get selected layers from selection tool if active
        if isinstance(self.current_tool, SelectionTool) and self.current_tool.selected_layers:
            for layer in self.current_tool.selected_layers[:]:  # Copy list to avoid modification during iteration
                self.remove_layer(layer.id)
            self.current_tool.clear_selected_layers()
        elif self.selected_layer:
            # Fallback to single selection
            self.delete_selected_layer()

        self.update()

    def align_selected_layers(self, align_type: str):
        """Align selected layers based on alignment type

        Args:
            align_type: One of 'top', 'bottom', 'left', 'right', 'h-center', 'v-center', 'v-spacing'
        """
        from tools.selection_tool import SelectionTool

        # Get selected layers from selection tool
        if not isinstance(self.current_tool, SelectionTool) or len(self.current_tool.selected_layers) < 2:
            return

        layers = self.current_tool.selected_layers

        # Get bounds for each layer
        layer_bounds = []
        for layer in layers:
            if hasattr(layer, 'data'):
                x = layer.data.get('x', 0)
                y = layer.data.get('y', 0)
                width = layer.data.get('width', 0)
                height = layer.data.get('height', 0)
                layer_bounds.append({
                    'layer': layer,
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'right': x + width,
                    'bottom': y + height,
                    'center_x': x + width / 2,
                    'center_y': y + height / 2
                })

        if not layer_bounds:
            return

        if align_type == 'left':
            # Align all layers to the leftmost edge
            min_x = min(b['x'] for b in layer_bounds)
            for b in layer_bounds:
                b['layer'].data['x'] = min_x

        elif align_type == 'right':
            # Align all layers to the rightmost edge
            max_right = max(b['right'] for b in layer_bounds)
            for b in layer_bounds:
                b['layer'].data['x'] = max_right - b['width']

        elif align_type == 'top':
            # Align all layers to the topmost edge
            min_y = min(b['y'] for b in layer_bounds)
            for b in layer_bounds:
                b['layer'].data['y'] = min_y

        elif align_type == 'bottom':
            # Align all layers to the bottommost edge
            max_bottom = max(b['bottom'] for b in layer_bounds)
            for b in layer_bounds:
                b['layer'].data['y'] = max_bottom - b['height']

        elif align_type == 'h-center':
            # Center all layers horizontally (align to shared vertical axis)
            avg_center_x = sum(b['center_x'] for b in layer_bounds) / len(layer_bounds)
            for b in layer_bounds:
                b['layer'].data['x'] = avg_center_x - b['width'] / 2

        elif align_type == 'v-center':
            # Center all layers vertically (align to shared horizontal axis)
            avg_center_y = sum(b['center_y'] for b in layer_bounds) / len(layer_bounds)
            for b in layer_bounds:
                b['layer'].data['y'] = avg_center_y - b['height'] / 2

        elif align_type == 'v-spacing':
            # Distribute layers evenly along vertical axis
            if len(layer_bounds) < 2:
                return

            # Sort by Y position
            layer_bounds.sort(key=lambda b: b['y'])

            # Get top of first layer and bottom of last layer
            top_y = layer_bounds[0]['y']
            bottom_y = layer_bounds[-1]['bottom']

            # Calculate total height of all layers
            total_height = sum(b['height'] for b in layer_bounds)

            # Calculate spacing between layers
            available_space = (bottom_y - top_y) - total_height
            spacing = available_space / (len(layer_bounds) - 1) if len(layer_bounds) > 1 else 0

            # Position each layer
            current_y = top_y
            for b in layer_bounds:
                b['layer'].data['y'] = current_y
                current_y += b['height'] + spacing

        self.update()

    def copy_selected_layers(self):
        """Copy currently selected layers to clipboard"""
        from tools.selection_tool import SelectionTool
        import copy

        self.copied_layers = []

        # Get selected layers from selection tool if active
        if isinstance(self.current_tool, SelectionTool) and self.current_tool.selected_layers:
            for layer in self.current_tool.selected_layers:
                # Deep copy the layer data
                if isinstance(layer, (TextFieldLayer, ImageLayer, SymbolLayer)):
                    self.copied_layers.append(layer)
            print(f"Copied {len(self.copied_layers)} layer(s)")
        elif self.selected_layer:
            # Fallback to single selection
            if isinstance(self.selected_layer, (TextFieldLayer, ImageLayer, SymbolLayer)):
                self.copied_layers = [self.selected_layer]
                print("Copied 1 layer")

    def paste_layers(self):
        """Paste copied layers at offset position"""
        import copy

        if not self.copied_layers:
            print("No layers to paste")
            return

        # Deselect all current selections
        self.deselect_all_layers()

        # Offset for pasted layers (so they don't overlap exactly)
        offset_x = 20
        offset_y = 20

        pasted_layers = []

        for original_layer in self.copied_layers:
            # Create a new layer based on the type
            new_layer = None

            if isinstance(original_layer, TextFieldLayer):
                # Create new text field layer
                new_layer = TextFieldLayer(
                    self.current_page,
                    original_layer.data.get('x', 0) + offset_x,
                    original_layer.data.get('y', 0) + offset_y,
                    original_layer.get_text(),
                    original_layer.data.get('width', 150),
                    original_layer.data.get('height', 40)
                )
                # Copy all styling
                new_layer.data.update({
                    'font': original_layer.data.get('font', 'Arial'),
                    'font_size': original_layer.data.get('font_size', 12),
                    'color': original_layer.data.get('color', '#000000'),
                    'bold': original_layer.data.get('bold', False),
                    'italic': original_layer.data.get('italic', False),
                    'underline': original_layer.data.get('underline', False),
                    'show_border': original_layer.data.get('show_border', True),
                    'border_color': original_layer.data.get('border_color', '#CCCCCC'),
                    'background_color': original_layer.data.get('background_color')
                })
                # Copy rotation
                new_layer.rotation = original_layer.rotation

            elif isinstance(original_layer, ImageLayer):
                # Create new image layer
                new_layer = ImageLayer(
                    self.current_page,
                    original_layer.data.get('x', 0) + offset_x,
                    original_layer.data.get('y', 0) + offset_y,
                    original_layer.data.get('pixmap'),
                    original_layer.data.get('width', 100),
                    original_layer.data.get('height', 100),
                    original_layer.data.get('image_path')
                )
                # Copy scale mode
                new_layer.set_scale_mode(original_layer.get_scale_mode())
                # Copy rotation
                new_layer.rotation = original_layer.rotation

            elif isinstance(original_layer, SymbolLayer):
                # Create new symbol layer
                new_layer = SymbolLayer(
                    self.current_page,
                    original_layer.data.get('x', 0) + offset_x,
                    original_layer.data.get('y', 0) + offset_y,
                    original_layer.get_symbol(),
                    original_layer.data.get('font_size', 24)
                )
                # Copy color
                new_layer.set_color(original_layer.data.get('color', '#000000'))
                # Copy rotation
                new_layer.rotation = original_layer.rotation

            # Add the new layer
            if new_layer:
                self.add_layer(new_layer)
                new_layer.selected = True
                pasted_layers.append(new_layer)

        # Update selection tool with pasted layers
        from tools.selection_tool import SelectionTool
        if isinstance(self.current_tool, SelectionTool):
            self.current_tool.set_selected_layers(pasted_layers)

        print(f"Pasted {len(pasted_layers)} layer(s)")
        self.update()

    def show_context_menu(self, widget_pos, page_pos):
        """Show context menu"""
        from tools.selection_tool import SelectionTool

        layer = self.find_layer_at_point(page_pos)

        if layer:
            menu = QMenu(self)

            # Add appropriate edit action based on layer type
            if isinstance(layer, TextFieldLayer):
                edit_action = QAction("Edit Text", self)
                edit_action.triggered.connect(lambda: self.edit_text_field(layer))
                menu.addAction(edit_action)
            elif isinstance(layer, ImageLayer):
                edit_action = QAction("Change Image", self)
                edit_action.triggered.connect(lambda: self.edit_image_layer(layer))
                menu.addAction(edit_action)
            elif isinstance(layer, SymbolLayer):
                edit_action = QAction("Edit Symbol", self)
                edit_action.triggered.connect(lambda: self.edit_symbol_layer(layer))
                menu.addAction(edit_action)

            delete_action = QAction("Delete", self)
            delete_action.triggered.connect(lambda: self.remove_layer(layer.id))
            menu.addAction(delete_action)

            menu.addSeparator()

            # Bring to front / send to back
            bring_front_action = QAction("Bring to Front", self)
            bring_front_action.triggered.connect(lambda: self.bring_layer_to_front(layer))
            menu.addAction(bring_front_action)

            send_back_action = QAction("Send to Back", self)
            send_back_action.triggered.connect(lambda: self.send_layer_to_back(layer))
            menu.addAction(send_back_action)

            menu.exec(self.mapToGlobal(widget_pos.toPoint()))
        else:
            # "Convert to Editable Layer" is only available for translated documents
            if self.is_translated_document:
                # Check if selection tool has an active selection box
                if isinstance(self.current_tool, SelectionTool):
                    selection_box = self.current_tool.get_selection_box()
                    if selection_box and selection_box.width() > 5 and selection_box.height() > 5:
                        # Find all text in selection box
                        text_items = self.find_pdf_text_in_rect(selection_box)
                        if text_items:
                            menu = QMenu(self)

                            convert_action = QAction(f"Convert to Editable Layer ({len(text_items)} items)", self)
                            convert_action.triggered.connect(lambda: self.convert_pdf_text_box_to_layers(text_items))
                            menu.addAction(convert_action)

                            menu.exec(self.mapToGlobal(widget_pos.toPoint()))
                            return

                # Check if clicking on PDF text (single text span)
                pdf_text_info = self.find_pdf_text_at_point(page_pos)
                if pdf_text_info:
                    menu = QMenu(self)

                    convert_action = QAction("Convert to Editable Layer", self)
                    convert_action.triggered.connect(lambda: self.convert_pdf_text_to_layer(pdf_text_info))
                    menu.addAction(convert_action)

                    menu.exec(self.mapToGlobal(widget_pos.toPoint()))

    def convert_pdf_text_to_layer(self, text_info: Dict[str, Any]):
        """
        Convert PDF text to an editable TextFieldLayer and remove original text

        Args:
            text_info: Dict containing text, rect, font, size, color, bold, italic
        """
        rect = text_info["rect"]
        x, y = rect[0], rect[1]
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]

        # Remove original text from PDF using redaction
        if self.pdf_doc and self.pdf_doc.doc:
            page = self.pdf_doc.get_page(self.current_page)
            if page:
                # Create redaction annotation to remove the text
                redact_rect = fitz.Rect(rect[0], rect[1], rect[2], rect[3])
                # Add redaction with white fill to cover the text
                page.add_redact_annot(redact_rect, fill=(1, 1, 1))
                # Apply redaction (removes the text)
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
                # Clear cache to reflect changes
                self.pdf_doc._clear_cache()

        # Map PDF font to system font
        pdf_font = text_info.get("font", "helv").lower()
        if "arial" in pdf_font or "helv" in pdf_font:
            font_name = "Arial"
        elif "times" in pdf_font:
            font_name = "Times New Roman"
        elif "courier" in pdf_font:
            font_name = "Courier New"
        else:
            font_name = "Arial"

        # Create TextFieldLayer
        text_layer = TextFieldLayer(
            self.current_page,
            x,
            y,
            text_info["text"],
            width + 4,  # Add small padding
            height + 4
        )

        # Set font and style
        text_layer.set_font(font_name, text_info.get("size", 12))
        text_layer.set_color(text_info.get("color", "#000000"))
        text_layer.set_style(
            text_info.get("bold", False),
            text_info.get("italic", False),
            False  # underline
        )

        # Add to layer manager
        self.add_layer(text_layer)

        # Select the new layer
        self.select_layer(text_layer)

        # Record action
        action = Action(
            ActionType.ADD_LAYER,
            {"layer_id": text_layer.id},
            f"Convert text to layer"
        )
        self.history_manager.add_action(action)

        self.update()

    def convert_pdf_text_box_to_layers(self, text_items: List[Dict[str, Any]]):
        """
        Convert multiple PDF text items to editable TextFieldLayers

        Args:
            text_items: List of dicts containing text, rect, font, size, color, bold, italic
        """
        from tools.selection_tool import SelectionTool

        if not text_items:
            return

        # First, add all redaction annotations
        if self.pdf_doc and self.pdf_doc.doc:
            page = self.pdf_doc.get_page(self.current_page)
            if page:
                for text_info in text_items:
                    rect = text_info["rect"]
                    redact_rect = fitz.Rect(rect[0], rect[1], rect[2], rect[3])
                    page.add_redact_annot(redact_rect, fill=(1, 1, 1))

                # Apply all redactions at once
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
                # Clear cache to reflect changes
                self.pdf_doc._clear_cache()

        # Create TextFieldLayers for each text item
        created_layers = []
        for text_info in text_items:
            rect = text_info["rect"]
            x, y = rect[0], rect[1]
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            # Map PDF font to system font
            pdf_font = text_info.get("font", "helv").lower()
            if "arial" in pdf_font or "helv" in pdf_font:
                font_name = "Arial"
            elif "times" in pdf_font:
                font_name = "Times New Roman"
            elif "courier" in pdf_font:
                font_name = "Courier New"
            else:
                font_name = "Arial"

            # Create TextFieldLayer
            text_layer = TextFieldLayer(
                self.current_page,
                x,
                y,
                text_info["text"],
                width + 4,
                height + 4
            )

            # Set font and style
            text_layer.set_font(font_name, text_info.get("size", 12))
            text_layer.set_color(text_info.get("color", "#000000"))
            text_layer.set_style(
                text_info.get("bold", False),
                text_info.get("italic", False),
                False
            )

            # Add to layer manager
            self.add_layer(text_layer)
            created_layers.append(text_layer)

        # Select all created layers
        if isinstance(self.current_tool, SelectionTool):
            self.current_tool.clear_box_selection()
            for layer in created_layers:
                layer.selected = True
            self.current_tool.set_selected_layers(created_layers)

        # Record action
        action = Action(
            ActionType.ADD_LAYER,
            {"layer_ids": [l.id for l in created_layers]},
            f"Convert {len(created_layers)} text items to layers"
        )
        self.history_manager.add_action(action)

        self.update()

    def bring_layer_to_front(self, layer):
        """Bring layer to front"""
        layers = self.layer_manager.layers
        if layer in layers:
            layers.remove(layer)
            layers.append(layer)
            self.layer_manager._reindex_layers()
            self.update()

    def send_layer_to_back(self, layer):
        """Send layer to back"""
        layers = self.layer_manager.layers
        if layer in layers:
            layers.remove(layer)
            layers.insert(0, layer)
            self.layer_manager._reindex_layers()
            self.update()

    def keyPressEvent(self, event):
        """Handle key press events"""
        from PyQt6.QtGui import QKeySequence

        # Copy selected layers (Ctrl+C)
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selected_layers()
            event.accept()
            return

        # Paste copied layers (Ctrl+V)
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste_layers()
            event.accept()
            return

        # Delete selected layers (Delete key)
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_layers()
            event.accept()
            return

        # Escape to deselect
        if event.key() == Qt.Key.Key_Escape:
            if self.selected_layer:
                self.deselect_layer()
                self.update()
            event.accept()
            return

        # Pass to parent
        super().keyPressEvent(event)

    def create_text_annotation_layer(self, annotation_data: dict):
        """Create an annotation layer for text highlight/underline/strikethrough"""
        if not annotation_data or not annotation_data.get('rects'):
            return

        # Create annotation layer
        layer = Layer(LayerType.ANNOTATION, self.current_page)
        layer.name = f"{annotation_data['type'].title()} Annotation"
        layer.data = {
            'annotation_type': annotation_data['type'],
            'rects': annotation_data['rects'],
            'color': annotation_data['color'],
            'text': annotation_data.get('text', '')
        }

        # Add layer
        self.add_layer(layer)

    def apply_text_annotation(self, annotation_type: str, color: str):
        """Apply annotation to current text selection"""
        if not isinstance(self.current_tool, TextSelectionTool):
            return

        if not self.current_tool.has_active_selection():
            return

        # Set the annotation type and color
        from tools.text_selection_tool import TextAnnotationType
        ann_type = TextAnnotationType(annotation_type)
        self.current_tool.set_annotation_type(ann_type)

        # Set color based on annotation type
        if ann_type == TextAnnotationType.HIGHLIGHT:
            self.current_tool.set_highlight_color(color)
        elif ann_type == TextAnnotationType.UNDERLINE:
            self.current_tool.underline_color = color
        else:
            self.current_tool.strikethrough_color = color

        # Create annotation layer from selection
        annotation_data = self.current_tool.create_annotation_layer()
        if annotation_data:
            self.create_text_annotation_layer(annotation_data)
            self.current_tool.clear_selection()
            self.text_selection_changed.emit(False)
            self.update()
