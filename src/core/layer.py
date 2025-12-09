"""
Layer Management System
Each annotation, drawing, or object exists on its own layer
"""
from typing import Dict, Any, List, Optional
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap, QPainterPath
from enum import Enum
import uuid


class LayerType(Enum):
    """Types of layers"""
    DRAWING = "drawing"
    TEXT = "text"
    IMAGE = "image"
    ANNOTATION = "annotation"
    SHAPE = "shape"
    SIGNATURE = "signature"
    FORM_FIELD = "form_field"
    STICKY_NOTE = "sticky_note"


class Layer:
    """Represents a single layer with drawing/annotation data"""

    def __init__(self, layer_type: LayerType, page_num: int, name: str = None):
        self.id = str(uuid.uuid4())
        self.type = layer_type
        self.page_num = page_num
        self.name = name or f"{layer_type.value.title()} {self.id[:8]}"
        self.visible = True
        self.locked = False
        self.opacity = 1.0
        self.data: Dict[str, Any] = {}
        self.z_index = 0  # For layer ordering

    def render(self, painter: QPainter, zoom: float = 1.0):
        """Render this layer on the given painter"""
        if not self.visible:
            return

        # Save painter state
        painter.save()
        painter.setOpacity(self.opacity)

        # Render based on layer type
        if self.type == LayerType.DRAWING:
            self._render_drawing(painter, zoom)
        elif self.type == LayerType.TEXT:
            self._render_text(painter, zoom)
        elif self.type == LayerType.IMAGE:
            self._render_image(painter, zoom)
        elif self.type == LayerType.ANNOTATION:
            self._render_annotation(painter, zoom)
        elif self.type == LayerType.SHAPE:
            self._render_shape(painter, zoom)
        elif self.type == LayerType.SIGNATURE:
            self._render_signature(painter, zoom)
        elif self.type == LayerType.STICKY_NOTE:
            self._render_sticky_note(painter, zoom)

        # Restore painter state
        painter.restore()

    def _render_drawing(self, painter: QPainter, zoom: float):
        """Render freehand drawing"""
        points = self.data.get('points', [])
        if len(points) < 2:
            return

        color = QColor(self.data.get('color', '#000000'))
        width = self.data.get('width', 2) * zoom

        pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # Draw path
        path = QPainterPath()
        path.moveTo(points[0][0] * zoom, points[0][1] * zoom)
        for x, y in points[1:]:
            path.lineTo(x * zoom, y * zoom)

        painter.drawPath(path)

    def _render_text(self, painter: QPainter, zoom: float):
        """Render text"""
        text = self.data.get('text', '')
        x = self.data.get('x', 0) * zoom
        y = self.data.get('y', 0) * zoom
        font_name = self.data.get('font', 'Arial')
        font_size = int(self.data.get('font_size', 12) * zoom)
        color = QColor(self.data.get('color', '#000000'))

        font = QFont(font_name, font_size)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(int(x), int(y), text)

    def _render_image(self, painter: QPainter, zoom: float):
        """Render image"""
        pixmap = self.data.get('pixmap')
        if not pixmap:
            return

        x = self.data.get('x', 0) * zoom
        y = self.data.get('y', 0) * zoom
        width = self.data.get('width', pixmap.width()) * zoom
        height = self.data.get('height', pixmap.height()) * zoom

        rect = QRectF(x, y, width, height)
        painter.drawPixmap(rect.toRect(), pixmap)

    def _render_annotation(self, painter: QPainter, zoom: float):
        """Render text annotation (highlight, underline, strikethrough)"""
        ann_type = self.data.get('annotation_type', 'highlight')
        color = QColor(self.data.get('color', '#FFFF00'))

        # Support multiple rectangles for text selection
        rects = self.data.get('rects', [])
        if not rects:
            # Fallback to single rect for backwards compatibility
            rect = self.data.get('rect', [0, 0, 100, 20])
            rects = [rect]

        for rect in rects:
            x, y, w, h = rect
            rect_obj = QRectF(x * zoom, y * zoom, w * zoom, h * zoom)

            if ann_type == 'highlight':
                highlight_color = QColor(color)
                highlight_color.setAlpha(100)
                painter.fillRect(rect_obj, highlight_color)
            elif ann_type == 'underline':
                pen = QPen(color, 1.5 * zoom)
                painter.setPen(pen)
                painter.drawLine(int(rect_obj.left()), int(rect_obj.bottom()),
                               int(rect_obj.right()), int(rect_obj.bottom()))
            elif ann_type == 'strikethrough':
                pen = QPen(color, 1.5 * zoom)
                painter.setPen(pen)
                painter.drawLine(int(rect_obj.left()), int(rect_obj.center().y()),
                               int(rect_obj.right()), int(rect_obj.center().y()))

    def _render_shape(self, painter: QPainter, zoom: float):
        """Render shapes (rectangle, circle, arrow, line)"""
        shape_type = self.data.get('shape_type', 'rectangle')
        color = QColor(self.data.get('color', '#000000'))
        fill_color = self.data.get('fill_color')
        width = self.data.get('width', 2) * zoom

        pen = QPen(color, width)
        painter.setPen(pen)

        if fill_color:
            brush = QBrush(QColor(fill_color))
            painter.setBrush(brush)

        if shape_type == 'rectangle':
            rect = self.data.get('rect', [0, 0, 100, 100])
            x, y, w, h = rect
            painter.drawRect(int(x * zoom), int(y * zoom), int(w * zoom), int(h * zoom))

        elif shape_type == 'ellipse':
            rect = self.data.get('rect', [0, 0, 100, 100])
            x, y, w, h = rect
            painter.drawEllipse(int(x * zoom), int(y * zoom), int(w * zoom), int(h * zoom))

        elif shape_type == 'line':
            x1 = self.data.get('x1', 0) * zoom
            y1 = self.data.get('y1', 0) * zoom
            x2 = self.data.get('x2', 100) * zoom
            y2 = self.data.get('y2', 100) * zoom
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        elif shape_type == 'arrow':
            self._draw_arrow(painter, zoom)

    def _draw_arrow(self, painter: QPainter, zoom: float):
        """Draw an arrow"""
        x1 = self.data.get('x1', 0) * zoom
        y1 = self.data.get('y1', 0) * zoom
        x2 = self.data.get('x2', 100) * zoom
        y2 = self.data.get('y2', 100) * zoom

        # Draw line
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Draw arrowhead
        import math
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_size = 10 * zoom

        arrow_p1_x = x2 - arrow_size * math.cos(angle - math.pi / 6)
        arrow_p1_y = y2 - arrow_size * math.sin(angle - math.pi / 6)
        arrow_p2_x = x2 - arrow_size * math.cos(angle + math.pi / 6)
        arrow_p2_y = y2 - arrow_size * math.sin(angle + math.pi / 6)

        path = QPainterPath()
        path.moveTo(x2, y2)
        path.lineTo(arrow_p1_x, arrow_p1_y)
        path.lineTo(arrow_p2_x, arrow_p2_y)
        path.closeSubpath()

        painter.fillPath(path, painter.pen().color())

    def _render_signature(self, painter: QPainter, zoom: float):
        """Render signature"""
        # Signatures are typically rendered as images or paths
        if 'pixmap' in self.data:
            self._render_image(painter, zoom)
        elif 'points' in self.data:
            self._render_drawing(painter, zoom)

    def _render_sticky_note(self, painter: QPainter, zoom: float):
        """Render sticky note"""
        x = self.data.get('x', 0) * zoom
        y = self.data.get('y', 0) * zoom
        size = self.data.get('size', 20) * zoom
        color = QColor(self.data.get('color', '#FFFF00'))

        # Draw note icon
        rect = QRectF(x, y, size, size)
        painter.fillRect(rect, color)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawRect(rect)

        # Draw fold
        fold_size = size * 0.3
        path = QPainterPath()
        path.moveTo(x + size - fold_size, y)
        path.lineTo(x + size, y + fold_size)
        path.lineTo(x + size - fold_size, y + fold_size)
        path.closeSubpath()
        painter.fillPath(path, color.darker(120))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize layer to dictionary"""
        # Create a copy of data without QPixmap (not serializable)
        data_copy = {}
        for key, value in self.data.items():
            if isinstance(value, QPixmap):
                # Store pixmap as bytes
                from PyQt6.QtCore import QBuffer, QIODevice
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                value.save(buffer, "PNG")
                data_copy[key] = {'_pixmap_bytes': buffer.data().data()}
            else:
                data_copy[key] = value

        return {
            'id': self.id,
            'type': self.type.value,
            'page_num': self.page_num,
            'name': self.name,
            'visible': self.visible,
            'locked': self.locked,
            'opacity': self.opacity,
            'z_index': self.z_index,
            'data': data_copy
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Layer':
        """Deserialize layer from dictionary"""
        layer = cls(LayerType(data['type']), data['page_num'], data['name'])
        layer.id = data['id']
        layer.visible = data['visible']
        layer.locked = data['locked']
        layer.opacity = data['opacity']
        layer.z_index = data['z_index']

        # Restore pixmaps
        layer_data = data['data'].copy()
        for key, value in layer_data.items():
            if isinstance(value, dict) and '_pixmap_bytes' in value:
                pixmap = QPixmap()
                pixmap.loadFromData(bytes(value['_pixmap_bytes']))
                layer_data[key] = pixmap

        layer.data = layer_data
        return layer


class LayerManager:
    """Manages all layers in the document"""

    def __init__(self):
        self.layers: List[Layer] = []
        self._next_z_index = 0

    def add_layer(self, layer: Layer):
        """Add a new layer"""
        layer.z_index = self._next_z_index
        self._next_z_index += 1
        self.layers.append(layer)

    def remove_layer(self, layer_id: str):
        """Remove a layer"""
        self.layers = [l for l in self.layers if l.id != layer_id]

    def get_layer(self, layer_id: str) -> Optional[Layer]:
        """Get a layer by ID"""
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def get_layers_for_page(self, page_num: int) -> List[Layer]:
        """Get all layers for a specific page"""
        return sorted(
            [l for l in self.layers if l.page_num == page_num],
            key=lambda x: x.z_index
        )

    def move_layer(self, layer_id: str, new_index: int):
        """Move a layer to a new position"""
        layer = self.get_layer(layer_id)
        if layer:
            self.layers.remove(layer)
            self.layers.insert(new_index, layer)
            self._reindex_layers()

    def _reindex_layers(self):
        """Reindex all layers"""
        for i, layer in enumerate(self.layers):
            layer.z_index = i

    def clear_page(self, page_num: int):
        """Remove all layers from a page"""
        self.layers = [l for l in self.layers if l.page_num != page_num]

    def clear_all(self):
        """Remove all layers"""
        self.layers.clear()
        self._next_z_index = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all layers"""
        return {
            'layers': [layer.to_dict() for layer in self.layers],
            'next_z_index': self._next_z_index
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LayerManager':
        """Deserialize layers"""
        manager = cls()
        manager.layers = [Layer.from_dict(l) for l in data['layers']]
        manager._next_z_index = data['next_z_index']
        return manager
