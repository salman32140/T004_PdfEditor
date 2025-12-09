"""
Interactive Layer System
Layers that can be selected, moved, and edited
"""
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPixmap
from .layer import Layer, LayerType
from typing import Optional, Tuple
from enum import Enum


class ResizeHandle(Enum):
    """Resize handle positions"""
    NONE = "none"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class InteractiveLayer(Layer):
    """Enhanced layer with interactive capabilities"""

    def __init__(self, layer_type: LayerType, page_num: int, name: str = None):
        super().__init__(layer_type, page_num, name)
        self.selected = False
        self.draggable = True
        self.editable = True
        self.resizable = False
        self.rotation = 0  # Rotation in degrees

    def get_bounds(self, zoom: float = 1.0) -> Optional[QRectF]:
        """Get bounding rectangle for this layer"""
        if self.type == LayerType.TEXT:
            x = self.data.get('x', 0) * zoom
            y = self.data.get('y', 0) * zoom
            text = self.data.get('text', '')
            font_size = self.data.get('font_size', 12) * zoom

            # Estimate text width (rough approximation)
            char_width = font_size * 0.6
            text_width = len(text) * char_width
            text_height = font_size * 1.5

            return QRectF(x - 5, y - text_height, text_width + 10, text_height + 10)

        return None

    def contains_point(self, point: QPointF, zoom: float = 1.0) -> bool:
        """Check if point is within this layer"""
        bounds = self.get_bounds(zoom)
        if bounds:
            return bounds.contains(point)
        return False

    def is_rotation_handle(self, point: QPointF, zoom: float = 1.0) -> bool:
        """Check if point is on the rotation handle.

        Note: point should be in widget coordinates (not page coordinates)
        since rotation handle offset is in pixels.
        """
        bounds = self.get_bounds(zoom)
        if not bounds:
            return False

        rotation_handle_size = 12  # Slightly larger hit area for easier clicking
        rotation_handle_offset = 20
        center_x = bounds.center().x()
        rotation_y = bounds.top() - rotation_handle_offset

        # Check if point is within rotation handle circle
        dx = point.x() - center_x
        dy = point.y() - rotation_y
        distance = (dx * dx + dy * dy) ** 0.5

        return distance <= rotation_handle_size

    def get_resize_handle_at(self, point: QPointF, zoom: float = 1.0) -> ResizeHandle:
        """Check if point is on a resize handle and return which one.

        Args:
            point: Point in widget coordinates
            zoom: Current zoom level

        Returns:
            ResizeHandle enum value indicating which handle, or NONE
        """
        if not self.resizable:
            return ResizeHandle.NONE

        bounds = self.get_bounds(zoom)
        if not bounds:
            return ResizeHandle.NONE

        handle_size = 12  # Hit area for handles

        # Define corner positions
        corners = {
            ResizeHandle.TOP_LEFT: (bounds.left(), bounds.top()),
            ResizeHandle.TOP_RIGHT: (bounds.right(), bounds.top()),
            ResizeHandle.BOTTOM_LEFT: (bounds.left(), bounds.bottom()),
            ResizeHandle.BOTTOM_RIGHT: (bounds.right(), bounds.bottom()),
        }

        # Check each corner
        for handle, (cx, cy) in corners.items():
            dx = point.x() - cx
            dy = point.y() - cy
            distance = (dx * dx + dy * dy) ** 0.5
            if distance <= handle_size:
                return handle

        return ResizeHandle.NONE

    def resize(self, handle: ResizeHandle, delta_x: float, delta_y: float,
               keep_aspect_ratio: bool = False, zoom: float = 1.0):
        """Resize the layer based on which handle is being dragged.

        Args:
            handle: Which resize handle is being dragged
            delta_x: Change in x position (in page coordinates)
            delta_y: Change in y position (in page coordinates)
            keep_aspect_ratio: Whether to maintain aspect ratio (Shift key)
            zoom: Current zoom level
        """
        if not self.resizable or handle == ResizeHandle.NONE:
            return

        # Get current dimensions
        x = self.data.get('x', 0)
        y = self.data.get('y', 0)
        width = self.data.get('width', 100)
        height = self.data.get('height', 100)

        # Calculate aspect ratio for constraint
        aspect_ratio = width / height if height > 0 else 1.0

        # Minimum size constraints
        min_size = 20

        if handle == ResizeHandle.TOP_LEFT:
            new_x = x + delta_x
            new_y = y + delta_y
            new_width = width - delta_x
            new_height = height - delta_y

            if keep_aspect_ratio:
                # Use the larger delta to maintain aspect ratio
                if abs(delta_x) > abs(delta_y):
                    new_height = new_width / aspect_ratio
                    new_y = y + height - new_height
                else:
                    new_width = new_height * aspect_ratio
                    new_x = x + width - new_width

            if new_width >= min_size and new_height >= min_size:
                self.data['x'] = new_x
                self.data['y'] = new_y
                self.data['width'] = new_width
                self.data['height'] = new_height

        elif handle == ResizeHandle.TOP_RIGHT:
            new_y = y + delta_y
            new_width = width + delta_x
            new_height = height - delta_y

            if keep_aspect_ratio:
                if abs(delta_x) > abs(delta_y):
                    new_height = new_width / aspect_ratio
                    new_y = y + height - new_height
                else:
                    new_width = new_height * aspect_ratio

            if new_width >= min_size and new_height >= min_size:
                self.data['y'] = new_y
                self.data['width'] = new_width
                self.data['height'] = new_height

        elif handle == ResizeHandle.BOTTOM_LEFT:
            new_x = x + delta_x
            new_width = width - delta_x
            new_height = height + delta_y

            if keep_aspect_ratio:
                if abs(delta_x) > abs(delta_y):
                    new_height = new_width / aspect_ratio
                else:
                    new_width = new_height * aspect_ratio
                    new_x = x + width - new_width

            if new_width >= min_size and new_height >= min_size:
                self.data['x'] = new_x
                self.data['width'] = new_width
                self.data['height'] = new_height

        elif handle == ResizeHandle.BOTTOM_RIGHT:
            new_width = width + delta_x
            new_height = height + delta_y

            if keep_aspect_ratio:
                if abs(delta_x) > abs(delta_y):
                    new_height = new_width / aspect_ratio
                else:
                    new_width = new_height * aspect_ratio

            if new_width >= min_size and new_height >= min_size:
                self.data['width'] = new_width
                self.data['height'] = new_height

    def move_to(self, x: float, y: float):
        """Move layer to new position"""
        if self.type == LayerType.TEXT:
            self.data['x'] = x
            self.data['y'] = y

    def move_by(self, dx: float, dy: float):
        """Move layer by delta"""
        if self.type == LayerType.TEXT:
            self.data['x'] = self.data.get('x', 0) + dx
            self.data['y'] = self.data.get('y', 0) + dy

    def render(self, painter: QPainter, zoom: float = 1.0):
        """Render layer with selection indicator"""
        # Call parent render
        super().render(painter, zoom)

        # Draw selection indicator if selected
        if self.selected and self.visible:
            bounds = self.get_bounds(zoom)
            if bounds:
                painter.save()

                # Draw selection rectangle
                pen = QPen(QColor(0, 120, 215), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(bounds)

                # Draw corner handles
                handle_size = 6
                painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.SolidLine))
                painter.setBrush(QColor(255, 255, 255))

                # Top-left handle
                painter.drawRect(int(bounds.left() - handle_size/2),
                               int(bounds.top() - handle_size/2),
                               handle_size, handle_size)

                # Top-right handle
                painter.drawRect(int(bounds.right() - handle_size/2),
                               int(bounds.top() - handle_size/2),
                               handle_size, handle_size)

                # Bottom-left handle
                painter.drawRect(int(bounds.left() - handle_size/2),
                               int(bounds.bottom() - handle_size/2),
                               handle_size, handle_size)

                # Bottom-right handle
                painter.drawRect(int(bounds.right() - handle_size/2),
                               int(bounds.bottom() - handle_size/2),
                               handle_size, handle_size)

                # Draw rotation handle (small circle above top center)
                rotation_handle_size = 8
                rotation_handle_offset = 20  # Distance above the bounding box
                center_x = bounds.center().x()
                rotation_y = bounds.top() - rotation_handle_offset

                # Draw line from top center to rotation handle
                painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.SolidLine))
                painter.drawLine(int(center_x), int(bounds.top()),
                               int(center_x), int(rotation_y))

                # Draw rotation handle as circle
                painter.setBrush(QColor(0, 200, 0))  # Green color for rotation handle
                painter.drawEllipse(int(center_x - rotation_handle_size/2),
                                  int(rotation_y - rotation_handle_size/2),
                                  rotation_handle_size, rotation_handle_size)

                painter.restore()


class TextFieldLayer(InteractiveLayer):
    """Special layer for editable text fields with text box"""

    MAX_NAME_LENGTH = 25  # Maximum length for layer name display

    def __init__(self, page_num: int, x: float, y: float, text: str = "", width: float = 150, height: float = 40):
        super().__init__(LayerType.TEXT, page_num, "Text Box")
        self._base_name = "Text Box"
        self.data = {
            'text': text,
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'font': 'Arial',
            'font_size': 12,
            'color': '#000000',
            'bold': False,
            'italic': False,
            'underline': False,
            'show_border': True,  # Show text box border
            'border_color': '#CCCCCC',
            'background_color': None  # Transparent by default
        }
        self.editable = True
        self.draggable = True
        self.resizable = True

    @property
    def name(self) -> str:
        """Get layer name based on text content"""
        text = self.data.get('text', '').strip()
        if text:
            # Get first line only
            first_line = text.split('\n')[0].strip()
            if len(first_line) > self.MAX_NAME_LENGTH:
                return first_line[:self.MAX_NAME_LENGTH] + "..."
            return first_line if first_line else self._base_name
        return self._base_name

    @name.setter
    def name(self, value: str):
        """Set base name (used by parent class)"""
        self._base_name = value

    def set_text(self, text: str):
        """Update text content"""
        self.data['text'] = text

    def get_text(self) -> str:
        """Get text content"""
        return self.data.get('text', '')

    def set_font(self, font_family: str, font_size: int):
        """Update font settings"""
        self.data['font'] = font_family
        self.data['font_size'] = font_size

    def set_color(self, color: str):
        """Update text color"""
        self.data['color'] = color

    def set_style(self, bold: bool = None, italic: bool = None, underline: bool = None):
        """Update text style"""
        if bold is not None:
            self.data['bold'] = bold
        if italic is not None:
            self.data['italic'] = italic
        if underline is not None:
            self.data['underline'] = underline

    def get_bounds(self, zoom: float = 1.0) -> QRectF:
        """Get accurate bounding rectangle"""
        x = self.data.get('x', 0) * zoom
        y = self.data.get('y', 0) * zoom
        width = self.data.get('width', 150) * zoom
        height = self.data.get('height', 40) * zoom

        return QRectF(x, y, width, height)

    def render(self, painter: QPainter, zoom: float = 1.0):
        """Render text box with text"""
        if not self.visible:
            return

        painter.save()
        painter.setOpacity(self.opacity)

        # Get box properties
        x = self.data.get('x', 0) * zoom
        y = self.data.get('y', 0) * zoom
        width = self.data.get('width', 150) * zoom
        height = self.data.get('height', 40) * zoom

        box_rect = QRectF(x, y, width, height)

        # Apply rotation if any
        if self.rotation != 0:
            # Rotate around the center of the box
            center_x = x + width / 2
            center_y = y + height / 2
            painter.translate(center_x, center_y)
            painter.rotate(self.rotation)
            painter.translate(-center_x, -center_y)

        # Draw background if specified
        background_color = self.data.get('background_color')
        if background_color:
            painter.fillRect(box_rect, QColor(background_color))

        # Draw border if enabled
        if self.data.get('show_border', True):
            border_color = QColor(self.data.get('border_color', '#CCCCCC'))
            border_pen = QPen(border_color, 1, Qt.PenStyle.SolidLine)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(box_rect)

        # Get text properties
        text = self.data.get('text', '')
        font_name = self.data.get('font', 'Arial')
        font_size = int(self.data.get('font_size', 12) * zoom)
        color = QColor(self.data.get('color', '#000000'))

        # Create and configure font
        font = QFont(font_name, font_size)
        font.setBold(self.data.get('bold', False))
        font.setItalic(self.data.get('italic', False))
        font.setUnderline(self.data.get('underline', False))

        painter.setFont(font)
        painter.setPen(color)

        # Draw text inside the box with padding
        text_rect = QRectF(x + 5, y + 5, width - 10, height - 10)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, text)

        painter.restore()

        # Draw selection if selected
        if self.selected:
            bounds = self.get_bounds(zoom)
            if bounds:
                painter.save()

                # Selection rectangle
                pen = QPen(QColor(0, 120, 215), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(bounds)

                # Corner handles for resizing
                handle_size = 8
                painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.SolidLine))
                painter.setBrush(QColor(255, 255, 255))

                corners = [
                    (bounds.left(), bounds.top()),
                    (bounds.right(), bounds.top()),
                    (bounds.left(), bounds.bottom()),
                    (bounds.right(), bounds.bottom())
                ]

                for cx, cy in corners:
                    painter.drawRect(int(cx - handle_size/2),
                                   int(cy - handle_size/2),
                                   handle_size, handle_size)

                # Draw rotation handle (small circle above top center)
                rotation_handle_size = 8
                rotation_handle_offset = 20  # Distance above the bounding box
                center_x = bounds.center().x()
                rotation_y = bounds.top() - rotation_handle_offset

                # Draw line from top center to rotation handle
                painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.SolidLine))
                painter.drawLine(int(center_x), int(bounds.top()),
                               int(center_x), int(rotation_y))

                # Draw rotation handle as circle
                painter.setBrush(QColor(0, 200, 0))  # Green color for rotation handle
                painter.drawEllipse(int(center_x - rotation_handle_size/2),
                                  int(rotation_y - rotation_handle_size/2),
                                  rotation_handle_size, rotation_handle_size)

                painter.restore()


class ImageScaleMode(Enum):
    """Image scaling modes"""
    FIT = "fit"  # Fit to frame, maintain aspect ratio
    FILL = "fill"  # Fill frame, maintain aspect ratio, crop if needed
    STRETCH = "stretch"  # Stretch to fill frame, ignore aspect ratio
    ACTUAL = "actual"  # Use actual image size


class ImageLayer(InteractiveLayer):
    """Special layer for images with scaling options"""

    def __init__(self, page_num: int, x: float, y: float, pixmap: QPixmap,
                 width: float = None, height: float = None,
                 image_path: str = None):
        super().__init__(LayerType.IMAGE, page_num, "Image")

        # Use image dimensions if not specified
        if width is None:
            width = pixmap.width()
        if height is None:
            height = pixmap.height()

        self.data = {
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'pixmap': pixmap,
            'image_path': image_path,
            'scale_mode': ImageScaleMode.FIT.value,
            'show_border': True,
            'border_color': '#CCCCCC',
            'rotation': 0,  # Rotation in degrees
        }
        self.editable = True
        self.draggable = True
        self.resizable = True

    def set_scale_mode(self, mode: ImageScaleMode):
        """Set image scaling mode"""
        self.data['scale_mode'] = mode.value

    def get_scale_mode(self) -> ImageScaleMode:
        """Get current scaling mode"""
        return ImageScaleMode(self.data.get('scale_mode', ImageScaleMode.FIT.value))

    def set_image(self, pixmap: QPixmap, image_path: str = None):
        """Update image"""
        self.data['pixmap'] = pixmap
        if image_path:
            self.data['image_path'] = image_path

    def get_bounds(self, zoom: float = 1.0) -> QRectF:
        """Get accurate bounding rectangle"""
        x = self.data.get('x', 0) * zoom
        y = self.data.get('y', 0) * zoom
        width = self.data.get('width', 100) * zoom
        height = self.data.get('height', 100) * zoom

        return QRectF(x, y, width, height)

    def render(self, painter: QPainter, zoom: float = 1.0):
        """Render image with scaling"""
        if not self.visible:
            return

        painter.save()
        painter.setOpacity(self.opacity)

        # Get frame properties
        x = self.data.get('x', 0) * zoom
        y = self.data.get('y', 0) * zoom
        width = self.data.get('width', 100) * zoom
        height = self.data.get('height', 100) * zoom

        frame_rect = QRectF(x, y, width, height)

        # Apply rotation if any
        if self.rotation != 0:
            # Rotate around the center of the frame
            center_x = x + width / 2
            center_y = y + height / 2
            painter.translate(center_x, center_y)
            painter.rotate(self.rotation)
            painter.translate(-center_x, -center_y)

        # Get pixmap
        pixmap = self.data.get('pixmap')
        if not pixmap:
            # Draw placeholder if no image
            painter.setPen(QPen(QColor('#CCCCCC'), 1))
            painter.drawRect(frame_rect)
            painter.drawText(frame_rect, Qt.AlignmentFlag.AlignCenter, "No Image")
            painter.restore()
            return

        # Calculate scaled rectangle based on scale mode
        scale_mode = self.get_scale_mode()
        img_rect = self._calculate_image_rect(pixmap, frame_rect, scale_mode)

        # Draw image
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(img_rect.toRect(), pixmap)

        # Draw border if enabled
        if self.data.get('show_border', True):
            border_color = QColor(self.data.get('border_color', '#CCCCCC'))
            border_pen = QPen(border_color, 1, Qt.PenStyle.SolidLine)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(frame_rect)

        painter.restore()

        # Draw selection if selected
        if self.selected:
            bounds = self.get_bounds(zoom)
            if bounds:
                painter.save()

                # Selection rectangle
                pen = QPen(QColor(0, 120, 215), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(bounds)

                # Corner handles for resizing
                handle_size = 8
                painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.SolidLine))
                painter.setBrush(QColor(255, 255, 255))

                corners = [
                    (bounds.left(), bounds.top()),
                    (bounds.right(), bounds.top()),
                    (bounds.left(), bounds.bottom()),
                    (bounds.right(), bounds.bottom())
                ]

                for cx, cy in corners:
                    painter.drawRect(int(cx - handle_size/2),
                                   int(cy - handle_size/2),
                                   handle_size, handle_size)

                # Draw rotation handle (small circle above top center)
                rotation_handle_size = 8
                rotation_handle_offset = 20  # Distance above the bounding box
                center_x = bounds.center().x()
                rotation_y = bounds.top() - rotation_handle_offset

                # Draw line from top center to rotation handle
                painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.SolidLine))
                painter.drawLine(int(center_x), int(bounds.top()),
                               int(center_x), int(rotation_y))

                # Draw rotation handle as circle
                painter.setBrush(QColor(0, 200, 0))  # Green color for rotation handle
                painter.drawEllipse(int(center_x - rotation_handle_size/2),
                                  int(rotation_y - rotation_handle_size/2),
                                  rotation_handle_size, rotation_handle_size)

                painter.restore()

    def _calculate_image_rect(self, pixmap: QPixmap, frame_rect: QRectF,
                               scale_mode: ImageScaleMode) -> QRectF:
        """Calculate image rectangle based on scaling mode"""
        img_w = pixmap.width()
        img_h = pixmap.height()
        frame_w = frame_rect.width()
        frame_h = frame_rect.height()

        if scale_mode == ImageScaleMode.STRETCH:
            # Stretch to fill entire frame
            return frame_rect

        elif scale_mode == ImageScaleMode.ACTUAL:
            # Use actual image size, centered in frame
            x = frame_rect.x() + (frame_w - img_w) / 2
            y = frame_rect.y() + (frame_h - img_h) / 2
            return QRectF(x, y, img_w, img_h)

        elif scale_mode == ImageScaleMode.FILL:
            # Fill frame, maintain aspect ratio, crop if needed
            scale = max(frame_w / img_w, frame_h / img_h)
            scaled_w = img_w * scale
            scaled_h = img_h * scale
            x = frame_rect.x() + (frame_w - scaled_w) / 2
            y = frame_rect.y() + (frame_h - scaled_h) / 2
            return QRectF(x, y, scaled_w, scaled_h)

        else:  # FIT (default)
            # Fit to frame, maintain aspect ratio
            scale = min(frame_w / img_w, frame_h / img_h)
            scaled_w = img_w * scale
            scaled_h = img_h * scale
            x = frame_rect.x() + (frame_w - scaled_w) / 2
            y = frame_rect.y() + (frame_h - scaled_h) / 2
            return QRectF(x, y, scaled_w, scaled_h)


class SymbolLayer(InteractiveLayer):
    """Special layer for unicode symbols"""

    def __init__(self, page_num: int, x: float, y: float, symbol: str, font_size: int = 24):
        super().__init__(LayerType.TEXT, page_num, "Symbol")
        self._base_name = "Symbol"
        # Calculate initial size based on font size
        symbol_size = font_size * 1.2
        self.data = {
            'symbol': symbol,
            'x': x,
            'y': y,
            'width': symbol_size,
            'height': symbol_size,
            'font_size': font_size,
            'color': '#000000',
            'background_color': None,
            'show_border': False,
        }
        self.editable = True
        self.draggable = True
        self.resizable = True

    @property
    def name(self) -> str:
        """Get layer name showing the symbol"""
        symbol = self.data.get('symbol', '')
        if symbol:
            return f"Symbol: {symbol}"
        return self._base_name

    @name.setter
    def name(self, value: str):
        """Set base name (used by parent class)"""
        self._base_name = value

    def set_symbol(self, symbol: str):
        """Update symbol"""
        self.data['symbol'] = symbol

    def get_symbol(self) -> str:
        """Get symbol"""
        return self.data.get('symbol', '')

    def set_font_size(self, font_size: int):
        """Update font size"""
        self.data['font_size'] = font_size

    def set_color(self, color: str):
        """Update symbol color"""
        self.data['color'] = color

    def get_bounds(self, zoom: float = 1.0) -> QRectF:
        """Get accurate bounding rectangle"""
        x = self.data.get('x', 0) * zoom
        y = self.data.get('y', 0) * zoom
        width = self.data.get('width', self.data.get('font_size', 24) * 1.2) * zoom
        height = self.data.get('height', self.data.get('font_size', 24) * 1.2) * zoom

        return QRectF(x, y, width, height)

    def render(self, painter: QPainter, zoom: float = 1.0):
        """Render symbol"""
        if not self.visible:
            return

        painter.save()
        painter.setOpacity(self.opacity)

        # Get symbol properties
        x = self.data.get('x', 0) * zoom
        y = self.data.get('y', 0) * zoom
        width = self.data.get('width', self.data.get('font_size', 24) * 1.2) * zoom
        height = self.data.get('height', self.data.get('font_size', 24) * 1.2) * zoom
        symbol = self.data.get('symbol', '')
        color = QColor(self.data.get('color', '#000000'))

        # Calculate font size based on bounding box (scale with height)
        font_size = int(height * 0.8)  # Font size is 80% of height

        bounds = QRectF(x, y, width, height)

        # Apply rotation if any
        if self.rotation != 0:
            # Rotate around the center
            center_x = x + width / 2
            center_y = y + height / 2
            painter.translate(center_x, center_y)
            painter.rotate(self.rotation)
            painter.translate(-center_x, -center_y)

        # Draw background if specified
        background_color = self.data.get('background_color')
        if background_color:
            painter.fillRect(bounds, QColor(background_color))

        # Create and configure font
        font = QFont('Arial', max(8, font_size))  # Minimum font size of 8
        painter.setFont(font)
        painter.setPen(color)

        # Draw symbol centered in bounds
        painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, symbol)

        painter.restore()

        # Draw selection if selected
        if self.selected:
            bounds = self.get_bounds(zoom)
            if bounds:
                painter.save()

                # Selection rectangle
                pen = QPen(QColor(0, 120, 215), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(bounds)

                # Corner handles
                handle_size = 8
                painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.SolidLine))
                painter.setBrush(QColor(255, 255, 255))

                corners = [
                    (bounds.left(), bounds.top()),
                    (bounds.right(), bounds.top()),
                    (bounds.left(), bounds.bottom()),
                    (bounds.right(), bounds.bottom())
                ]

                for cx, cy in corners:
                    painter.drawRect(int(cx - handle_size/2),
                                   int(cy - handle_size/2),
                                   handle_size, handle_size)

                # Draw rotation handle (small circle above top center)
                rotation_handle_size = 8
                rotation_handle_offset = 20  # Distance above the bounding box
                center_x = bounds.center().x()
                rotation_y = bounds.top() - rotation_handle_offset

                # Draw line from top center to rotation handle
                painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.PenStyle.SolidLine))
                painter.drawLine(int(center_x), int(bounds.top()),
                               int(center_x), int(rotation_y))

                # Draw rotation handle as circle
                painter.setBrush(QColor(0, 200, 0))  # Green color for rotation handle
                painter.drawEllipse(int(center_x - rotation_handle_size/2),
                                  int(rotation_y - rotation_handle_size/2),
                                  rotation_handle_size, rotation_handle_size)

                painter.restore()
