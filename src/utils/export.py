"""
PDF Export Utilities
Handles various export formats and options
"""
from core import PDFDocument, LayerManager
from core.layer import LayerType, Layer
from core.interactive_layer import TextFieldLayer, ImageLayer, SymbolLayer
from PyQt6.QtGui import QPainter, QImage, QPixmap
from PyQt6.QtCore import Qt, QRectF, QBuffer, QIODevice
import fitz
from typing import Optional, Dict, Any
import io
import json
import base64
import os
import tempfile
import zipfile


class PDFExporter:
    """Handles PDF export with various options"""

    def __init__(self, pdf_doc: PDFDocument, layer_manager: LayerManager):
        self.pdf_doc = pdf_doc
        self.layer_manager = layer_manager

    def save_with_layers(self, output_path: str) -> bool:
        """
        Save PDF with layers converted to actual PDF elements (text, images, vectors)
        This preserves editability and doesn't convert to images
        """
        if not self.pdf_doc.doc:
            return False

        try:
            print("  → Preserving original PDF content (vectors/text)...")
            # Create a copy of the document
            doc = fitz.open()
            doc.insert_pdf(self.pdf_doc.doc)

            # Process each page
            layer_count = 0
            for page_num in range(doc.page_count):
                page = doc[page_num]
                layers = self.layer_manager.get_layers_for_page(page_num)

                for layer in layers:
                    if not layer.visible:
                        continue

                    # Handle different layer types
                    if isinstance(layer, TextFieldLayer):
                        print(f"  → Adding text layer (page {page_num + 1}): '{layer.get_text()[:30]}...'")
                        self._add_text_to_pdf(page, layer)
                        layer_count += 1
                    elif isinstance(layer, ImageLayer):
                        print(f"  → Adding image layer (page {page_num + 1})")
                        self._add_image_to_pdf(page, layer)
                        layer_count += 1
                    elif isinstance(layer, SymbolLayer):
                        print(f"  → Adding symbol layer (page {page_num + 1}): '{layer.get_symbol()}'")
                        self._add_symbol_to_pdf(page, layer)
                        layer_count += 1
                    elif layer.type == LayerType.DRAWING:
                        print(f"  → Adding drawing layer (page {page_num + 1})")
                        self._add_drawing_to_pdf(page, layer)
                        layer_count += 1
                    elif layer.type == LayerType.SHAPE:
                        print(f"  → Adding shape layer (page {page_num + 1})")
                        self._add_shape_to_pdf(page, layer)
                        layer_count += 1

            print(f"  → Saving PDF with {layer_count} layer(s) as vector/text elements...")
            # Save layer metadata as PDF metadata for later restoration
            self._save_layer_metadata(doc)

            # Save the document
            doc.save(output_path, garbage=4, deflate=True, clean=True)
            doc.close()

            print(f"  ✓ PDF saved successfully (NOT converted to images)")
            return True

        except Exception as e:
            print(f"✗ Error saving PDF with layers: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _add_text_to_pdf(self, page: fitz.Page, layer: TextFieldLayer):
        """Add text layer to PDF as actual text"""
        try:
            text = layer.get_text()
            if not text:
                return

            x = layer.data.get('x', 0)
            y = layer.data.get('y', 0)
            width = layer.data.get('width', 150)
            height = layer.data.get('height', 40)

            font_name = layer.data.get('font', 'Arial')
            font_size = layer.data.get('font_size', 12)
            color_hex = layer.data.get('color', '#000000')
            bold = layer.data.get('bold', False)
            italic = layer.data.get('italic', False)
            rotation = layer.rotation if hasattr(layer, 'rotation') else 0

            # Convert hex color to RGB tuple (0-1 range)
            color = self._hex_to_rgb(color_hex)

            # Check if text contains non-ASCII characters (CJK, Korean, etc.)
            needs_unicode_font = any(ord(c) > 127 for c in text)

            # Create text rectangle
            rect = fitz.Rect(x, y, x + width, y + height)

            if needs_unicode_font:
                # For Unicode text (Korean, Chinese, Japanese, etc.)
                # Render as image for guaranteed proper display
                self._add_text_as_image(page, layer)
            else:
                # Use Base14 fonts for ASCII text (smaller file size)
                # Map font names to PyMuPDF Base14 font names
                if bold and italic:
                    font_map = {
                        'Arial': 'Helvetica-BoldOblique',
                        'Helvetica': 'Helvetica-BoldOblique',
                        'Times New Roman': 'Times-BoldItalic',
                        'Times': 'Times-BoldItalic',
                        'Courier New': 'Courier-BoldOblique',
                        'Courier': 'Courier-BoldOblique'
                    }
                elif bold:
                    font_map = {
                        'Arial': 'Helvetica-Bold',
                        'Helvetica': 'Helvetica-Bold',
                        'Times New Roman': 'Times-Bold',
                        'Times': 'Times-Bold',
                        'Courier New': 'Courier-Bold',
                        'Courier': 'Courier-Bold'
                    }
                elif italic:
                    font_map = {
                        'Arial': 'Helvetica-Oblique',
                        'Helvetica': 'Helvetica-Oblique',
                        'Times New Roman': 'Times-Italic',
                        'Times': 'Times-Italic',
                        'Courier New': 'Courier-Oblique',
                        'Courier': 'Courier-Oblique'
                    }
                else:
                    font_map = {
                        'Arial': 'Helvetica',
                        'Helvetica': 'Helvetica',
                        'Times New Roman': 'Times-Roman',
                        'Times': 'Times-Roman',
                        'Courier New': 'Courier',
                        'Courier': 'Courier'
                    }

                pymupdf_font = font_map.get(font_name, 'Helvetica-Bold' if bold else 'Helvetica')

                if rotation != 0:
                    morph = (
                        fitz.Point(x + width / 2, y + height / 2),
                        fitz.Matrix(rotation)
                    )
                    page.insert_textbox(
                        rect,
                        text,
                        fontsize=font_size,
                        fontname=pymupdf_font,
                        color=color,
                        align=fitz.TEXT_ALIGN_LEFT,
                        morph=morph
                    )
                else:
                    page.insert_textbox(
                        rect,
                        text,
                        fontsize=font_size,
                        fontname=pymupdf_font,
                        color=color,
                        align=fitz.TEXT_ALIGN_LEFT
                    )

        except Exception as e:
            print(f"Error adding text to PDF: {e}")
            import traceback
            traceback.print_exc()

    def _find_unicode_font(self, bold: bool = False, italic: bool = False) -> str:
        """Find a system font that supports Unicode/CJK characters

        Returns the path to a suitable font file, or None if not found.
        """
        import platform
        system = platform.system()

        # Common CJK/Unicode font paths by OS
        font_candidates = []

        if system == "Linux":
            # Linux font paths - prefer Noto fonts for best CJK support
            font_candidates = [
                # Noto Sans CJK (best coverage)
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                # Noto Sans Korean
                "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.otf",
                "/usr/share/fonts/opentype/noto/NotoSansKR-Regular.otf",
                # DejaVu (good Unicode coverage)
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                # Liberation fonts
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                # Ubuntu fonts
                "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
                # Droid fonts
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                # WenQuanYi (Chinese)
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            ]
            if bold:
                font_candidates = [
                    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
                    "/usr/share/fonts/truetype/noto/NotoSansKR-Bold.otf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                ] + font_candidates

        elif system == "Darwin":  # macOS
            font_candidates = [
                # macOS system fonts with CJK support
                "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # Korean
                "/System/Library/Fonts/PingFang.ttc",  # Chinese
                "/System/Library/Fonts/Hiragino Sans GB.ttc",  # Japanese/Chinese
                "/Library/Fonts/Arial Unicode.ttf",
                "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            ]

        elif system == "Windows":
            font_candidates = [
                # Windows fonts with CJK support
                "C:/Windows/Fonts/malgun.ttf",  # Korean (Malgun Gothic)
                "C:/Windows/Fonts/malgunbd.ttf",  # Korean Bold
                "C:/Windows/Fonts/msyh.ttc",  # Chinese (Microsoft YaHei)
                "C:/Windows/Fonts/meiryo.ttc",  # Japanese
                "C:/Windows/Fonts/simsun.ttc",  # Chinese (SimSun)
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/arialuni.ttf",  # Arial Unicode MS
            ]

        # Find first existing font
        for font_path in font_candidates:
            if os.path.exists(font_path):
                return font_path

        return None

    def _add_text_as_image(self, page: fitz.Page, layer: 'TextFieldLayer'):
        """Render text layer as an image for full Unicode support (Korean, Chinese, etc.)"""
        try:
            from PyQt6.QtGui import QImage, QPainter, QFont, QColor, QFontDatabase
            from PyQt6.QtCore import Qt, QRectF

            text = layer.get_text()
            if not text:
                return

            x = layer.data.get('x', 0)
            y = layer.data.get('y', 0)
            width = layer.data.get('width', 150)
            height = layer.data.get('height', 40)
            font_name = layer.data.get('font', 'Arial')
            font_size = layer.data.get('font_size', 12)
            color_hex = layer.data.get('color', '#000000')
            bold = layer.data.get('bold', False)
            italic = layer.data.get('italic', False)
            rotation = layer.rotation if hasattr(layer, 'rotation') else 0

            # Create high-resolution image for better quality
            scale = 4
            img_width = max(1, int(width * scale))
            img_height = max(1, int(height * scale))

            image = QImage(img_width, img_height, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)

            painter = QPainter(image)
            if not painter.isActive():
                print("Error: QPainter failed to initialize")
                return

            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

            # Set font - try to use a font that supports the text
            font = QFont(font_name, int(font_size * scale))
            font.setBold(bold)
            font.setItalic(italic)

            # Set font style strategy to prefer fonts that support the characters
            font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

            painter.setFont(font)
            painter.setPen(QColor(color_hex))

            # Draw text with word wrap
            rect = QRectF(0, 0, img_width, img_height)
            flags = int(Qt.AlignmentFlag.AlignLeft) | int(Qt.AlignmentFlag.AlignTop) | int(Qt.TextFlag.TextWordWrap)
            painter.drawText(rect, flags, text)
            painter.end()

            # Convert QImage to bytes
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")
            img_bytes = bytes(buffer.data())
            buffer.close()

            if len(img_bytes) == 0:
                print("Error: Generated empty image for text")
                return

            # Insert image into PDF
            img_rect = fitz.Rect(x, y, x + width, y + height)

            if rotation != 0:
                # Apply rotation
                center = fitz.Point(x + width / 2, y + height / 2)
                morph = (center, fitz.Matrix(rotation))
                page.insert_image(img_rect, stream=img_bytes, morph=morph)
            else:
                page.insert_image(img_rect, stream=img_bytes)

            print(f"  → Added Unicode text as image: '{text[:20]}...' at ({x}, {y})")

        except Exception as e:
            print(f"Error adding text as image: {e}")
            import traceback
            traceback.print_exc()

    def _add_symbol_to_pdf(self, page: fitz.Page, layer: SymbolLayer):
        """Add symbol layer to PDF by rendering it as an image for full Unicode support"""
        try:
            symbol = layer.get_symbol()
            if not symbol:
                return

            x = layer.data.get('x', 0)
            y = layer.data.get('y', 0)
            width = layer.data.get('width', layer.data.get('font_size', 24) * 1.2)
            height = layer.data.get('height', layer.data.get('font_size', 24) * 1.2)
            color_hex = layer.data.get('color', '#000000')
            rotation = layer.rotation if hasattr(layer, 'rotation') else 0

            # Render the symbol as an image for guaranteed Unicode support
            from PyQt6.QtGui import QImage, QPainter, QFont, QColor
            from PyQt6.QtCore import Qt, QRectF

            # Create a high-resolution image for the symbol
            scale = 4  # Higher resolution for better quality
            img_width = int(width * scale)
            img_height = int(height * scale)

            # Calculate font size to fit in bounds (80% of height like in render)
            font_size = int(height * 0.8 * scale)

            image = QImage(img_width, img_height, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)

            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

            # Set font and color
            font = QFont('Arial', max(8, font_size))
            painter.setFont(font)
            painter.setPen(QColor(color_hex))

            # Draw symbol centered in the image bounds
            rect = QRectF(0, 0, img_width, img_height)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, symbol)
            painter.end()

            # Convert QImage to bytes
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")
            image_data = buffer.data().data()

            # Create PDF rect using the layer bounds
            rect = fitz.Rect(x, y, x + width, y + height)

            # Insert the symbol image
            if rotation != 0:
                page.insert_image(rect, stream=image_data, rotate=int(rotation))
            else:
                page.insert_image(rect, stream=image_data)

        except Exception as e:
            print(f"Error adding symbol to PDF: {e}")
            import traceback
            traceback.print_exc()

    def _add_image_to_pdf(self, page: fitz.Page, layer: ImageLayer):
        """Add image layer to PDF as actual image"""
        try:
            pixmap = layer.data.get('pixmap')
            if not pixmap:
                return

            x = layer.data.get('x', 0)
            y = layer.data.get('y', 0)
            width = layer.data.get('width', 100)
            height = layer.data.get('height', 100)
            rotation = layer.rotation if hasattr(layer, 'rotation') else 0

            # Convert QPixmap to bytes
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            pixmap.save(buffer, "PNG")
            image_data = buffer.data().data()

            # Create rectangle for image
            rect = fitz.Rect(x, y, x + width, y + height)

            # If rotation is applied, calculate center and use overlay with rotation
            if rotation != 0:
                # Calculate center of image
                center_x = x + width / 2
                center_y = y + height / 2

                # Insert image with rotation using overlay parameter
                # The overlay parameter accepts transformation matrix
                page.insert_image(
                    rect,
                    stream=image_data,
                    rotate=int(rotation)  # PyMuPDF expects integer rotation
                )
            else:
                # Insert image normally without rotation
                page.insert_image(rect, stream=image_data)

        except Exception as e:
            print(f"Error adding image to PDF: {e}")
            import traceback
            traceback.print_exc()

    def _add_drawing_to_pdf(self, page: fitz.Page, layer):
        """Add freehand drawing to PDF as vector path"""
        try:
            points = layer.data.get('points', [])
            if len(points) < 2:
                return

            color_hex = layer.data.get('color', '#000000')
            width = layer.data.get('width', 2)

            # Convert hex color to RGB tuple
            color = self._hex_to_rgb(color_hex)

            # Create a shape (path) on the page
            shape = page.new_shape()

            # Move to first point
            shape.draw_line(
                fitz.Point(points[0][0], points[0][1]),
                fitz.Point(points[1][0], points[1][1])
            )

            # Draw lines through all points
            for i in range(1, len(points) - 1):
                shape.draw_line(
                    fitz.Point(points[i][0], points[i][1]),
                    fitz.Point(points[i + 1][0], points[i + 1][1])
                )

            # Finish the shape
            shape.finish(color=color, width=width)
            shape.commit()

        except Exception as e:
            print(f"Error adding drawing to PDF: {e}")

    def _add_shape_to_pdf(self, page: fitz.Page, layer):
        """Add shape to PDF as vector graphics"""
        try:
            shape_type = layer.data.get('shape_type', 'rectangle')
            color_hex = layer.data.get('color', '#000000')
            fill_color_hex = layer.data.get('fill_color')
            width = layer.data.get('width', 2)

            color = self._hex_to_rgb(color_hex)
            fill_color = self._hex_to_rgb(fill_color_hex) if fill_color_hex else None

            shape = page.new_shape()

            if shape_type == 'rectangle':
                rect_data = layer.data.get('rect', [0, 0, 100, 100])
                x, y, w, h = rect_data
                rect = fitz.Rect(x, y, x + w, y + h)
                shape.draw_rect(rect)

            elif shape_type == 'ellipse':
                rect_data = layer.data.get('rect', [0, 0, 100, 100])
                x, y, w, h = rect_data
                rect = fitz.Rect(x, y, x + w, y + h)
                shape.draw_oval(rect)

            elif shape_type == 'line':
                x1 = layer.data.get('x1', 0)
                y1 = layer.data.get('y1', 0)
                x2 = layer.data.get('x2', 100)
                y2 = layer.data.get('y2', 100)
                shape.draw_line(fitz.Point(x1, y1), fitz.Point(x2, y2))

            elif shape_type == 'arrow':
                x1 = layer.data.get('x1', 0)
                y1 = layer.data.get('y1', 0)
                x2 = layer.data.get('x2', 100)
                y2 = layer.data.get('y2', 100)

                # Draw line
                shape.draw_line(fitz.Point(x1, y1), fitz.Point(x2, y2))

                # Draw arrowhead (simple triangle)
                import math
                angle = math.atan2(y2 - y1, x2 - x1)
                arrow_size = 10

                p1_x = x2 - arrow_size * math.cos(angle - math.pi / 6)
                p1_y = y2 - arrow_size * math.sin(angle - math.pi / 6)
                p2_x = x2 - arrow_size * math.cos(angle + math.pi / 6)
                p2_y = y2 - arrow_size * math.sin(angle + math.pi / 6)

                shape.draw_polyline([
                    fitz.Point(p1_x, p1_y),
                    fitz.Point(x2, y2),
                    fitz.Point(p2_x, p2_y)
                ])

            # Finish and commit shape
            shape.finish(
                color=color,
                fill=fill_color,
                width=width
            )
            shape.commit()

        except Exception as e:
            print(f"Error adding shape to PDF: {e}")

    def export_flattened(self, output_path: str, dpi: int = 150):
        """
        Export PDF with all layers flattened into the pages
        """
        if not self.pdf_doc.doc:
            return False

        try:
            # Create new document
            new_doc = fitz.open()

            for page_num in range(self.pdf_doc.page_count):
                # Get original page
                original_page = self.pdf_doc.doc[page_num]
                page_rect = original_page.rect

                # Create new page with same dimensions
                new_page = new_doc.new_page(width=page_rect.width, height=page_rect.height)

                # Render original page with layers to image
                zoom = dpi / 72.0
                width = int(page_rect.width * zoom)
                height = int(page_rect.height * zoom)

                # Create QImage to render everything
                image = QImage(width, height, QImage.Format.Format_RGB888)
                image.fill(Qt.GlobalColor.white)

                painter = QPainter(image)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

                # Draw PDF page
                pixmap = self.pdf_doc.render_page(page_num, zoom, use_cache=False)
                if pixmap:
                    painter.drawPixmap(0, 0, pixmap)

                # Draw all layers
                layers = self.layer_manager.get_layers_for_page(page_num)
                for layer in layers:
                    if layer.visible:
                        layer.render(painter, zoom)

                painter.end()

                # Save image to temporary file
                temp_img_path = f"/tmp/pdf_editor_temp_{page_num}.png"
                image.save(temp_img_path, "PNG")

                # Insert image into new page
                new_page.insert_image(page_rect, filename=temp_img_path)

                # Clean up temp file
                import os
                try:
                    os.remove(temp_img_path)
                except:
                    pass

            # Save new document
            new_doc.save(output_path, garbage=4, deflate=True)
            new_doc.close()

            return True

        except Exception as e:
            print(f"Error exporting flattened PDF: {e}")
            return False

    def export_with_layers(self, output_path: str):
        """
        Export PDF preserving layer information (as annotations)
        """
        if not self.pdf_doc.doc:
            return False

        try:
            # Save current document
            self.pdf_doc.save(output_path)

            # Reopen to add layer annotations
            doc = fitz.open(output_path)

            for page_num in range(doc.page_count):
                page = doc[page_num]
                layers = self.layer_manager.get_layers_for_page(page_num)

                for layer in layers:
                    # Convert layers to PDF annotations where possible
                    self._add_layer_as_annotation(page, layer)

            doc.save(output_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            doc.close()

            return True

        except Exception as e:
            print(f"Error exporting with layers: {e}")
            return False

    def _add_layer_as_annotation(self, page: fitz.Page, layer):
        """Add a layer as a PDF annotation"""
        from core.layer import LayerType

        try:
            if layer.type == LayerType.ANNOTATION:
                ann_type = layer.data.get('annotation_type')
                rect = layer.data.get('rect', [0, 0, 100, 20])
                color = layer.data.get('color', '#FFFF00')

                # Convert color to RGB tuple
                color_rgb = self._hex_to_rgb(color)

                rect_obj = fitz.Rect(rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3])

                if ann_type == 'highlight':
                    annot = page.add_highlight_annot(rect_obj)
                    annot.set_colors(stroke=color_rgb)
                    annot.update()

            elif layer.type == LayerType.TEXT:
                text = layer.data.get('text', '')
                x = layer.data.get('x', 0)
                y = layer.data.get('y', 0)
                font_size = layer.data.get('font_size', 12)
                color = layer.data.get('color', '#000000')

                # Add text annotation
                point = fitz.Point(x, y)
                annot = page.add_text_annot(point, text)
                annot.update()

        except Exception as e:
            print(f"Error adding layer as annotation: {e}")

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))

    def _save_layer_metadata(self, doc: fitz.Document):
        """Save layer data as PDF metadata for later restoration"""
        try:
            # Serialize layers to JSON
            layer_data = self.layer_manager.to_dict()

            # Convert to JSON string
            json_str = json.dumps(layer_data, default=self._json_serializer)

            # Store in PDF metadata using a custom key
            metadata = doc.metadata or {}
            metadata['keywords'] = f"PDFEDITOR_LAYERS:{base64.b64encode(json_str.encode()).decode()}"
            doc.set_metadata(metadata)

            print(f"  → Layer metadata saved ({len(self.layer_manager.layers)} layers)")
        except Exception as e:
            print(f"  → Warning: Could not save layer metadata: {e}")

    def _json_serializer(self, obj):
        """Custom JSON serializer for non-serializable objects"""
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QBuffer, QIODevice

        if isinstance(obj, QPixmap):
            # Convert QPixmap to base64 encoded PNG
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            obj.save(buffer, "PNG")
            return {'_pixmap_base64': base64.b64encode(buffer.data().data()).decode()}
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @staticmethod
    def load_layer_metadata(doc: fitz.Document) -> Optional[dict]:
        """Load layer data from PDF metadata"""
        try:
            metadata = doc.metadata
            if not metadata:
                return None

            keywords = metadata.get('keywords', '')
            if not keywords or not keywords.startswith('PDFEDITOR_LAYERS:'):
                return None

            # Extract and decode layer data
            encoded_data = keywords[len('PDFEDITOR_LAYERS:'):]
            json_str = base64.b64decode(encoded_data).decode()
            layer_data = json.loads(json_str)

            # Restore pixmaps from base64
            PDFExporter._restore_pixmaps(layer_data)

            return layer_data
        except Exception as e:
            print(f"Warning: Could not load layer metadata: {e}")
            return None

    @staticmethod
    def _restore_pixmaps(data):
        """Restore QPixmap objects from base64 encoded data"""
        from PyQt6.QtGui import QPixmap

        if isinstance(data, dict):
            if '_pixmap_base64' in data:
                # This is an encoded pixmap
                pixmap = QPixmap()
                pixmap.loadFromData(base64.b64decode(data['_pixmap_base64']))
                return pixmap

            for key, value in data.items():
                result = PDFExporter._restore_pixmaps(value)
                if result is not None:
                    data[key] = result

        elif isinstance(data, list):
            for i, item in enumerate(data):
                result = PDFExporter._restore_pixmaps(item)
                if result is not None:
                    data[i] = result

        return None

    def export_page_range(self, start_page: int, end_page: int, output_path: str):
        """Export a range of pages"""
        if not self.pdf_doc.doc:
            return False

        try:
            self.pdf_doc.extract_pages(start_page, end_page, output_path)
            return True
        except Exception as e:
            print(f"Error exporting page range: {e}")
            return False

    def export_current_page_as_image(self, page_num: int, output_path: str,
                                     format: str = 'PNG', dpi: int = 300):
        """Export a single page with layers as image"""
        try:
            zoom = dpi / 72.0
            page_size = self.pdf_doc.get_page_size(page_num)

            if not page_size:
                return False

            width = int(page_size[0] * zoom)
            height = int(page_size[1] * zoom)

            # Create image
            image = QImage(width, height, QImage.Format.Format_RGB888)
            image.fill(Qt.GlobalColor.white)

            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            # Draw PDF page
            pixmap = self.pdf_doc.render_page(page_num, zoom, use_cache=False)
            if pixmap:
                painter.drawPixmap(0, 0, pixmap)

            # Draw layers
            layers = self.layer_manager.get_layers_for_page(page_num)
            for layer in layers:
                if layer.visible:
                    layer.render(painter, zoom)

            painter.end()

            # Save image
            image.save(output_path, format)
            return True

        except Exception as e:
            print(f"Error exporting page as image: {e}")
            return False


class ProjectManager:
    """Handles saving and loading project files (.pdfproj)

    Project file format is a ZIP archive containing:
    - document.pdf: The original PDF document
    - project.json: Project metadata, layers, guides, and settings
    """

    PROJECT_VERSION = "1.0"
    PROJECT_EXTENSION = ".pdfproj"

    @staticmethod
    def save_project(output_path: str, pdf_doc: PDFDocument, layer_manager: LayerManager,
                     guide_manager=None, settings: Dict[str, Any] = None) -> bool:
        """Save a complete project file

        Args:
            output_path: Path to save the project file
            pdf_doc: The PDF document
            layer_manager: The layer manager with all layers
            guide_manager: Optional guide manager for guides
            settings: Optional additional settings dict

        Returns:
            True if successful, False otherwise
        """
        if not pdf_doc or not pdf_doc.doc:
            print("Error: No PDF document to save")
            return False

        try:
            # Create a temporary directory for project contents
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save the PDF document
                pdf_path = os.path.join(temp_dir, "document.pdf")
                pdf_doc.doc.save(pdf_path)

                # Prepare project data
                project_data = {
                    "version": ProjectManager.PROJECT_VERSION,
                    "layers": ProjectManager._serialize_layers(layer_manager),
                    "guides": ProjectManager._serialize_guides(guide_manager) if guide_manager else [],
                    "settings": settings or {}
                }

                # Save project JSON
                json_path = os.path.join(temp_dir, "project.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, indent=2, default=ProjectManager._json_serializer)

                # Create ZIP archive
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(pdf_path, "document.pdf")
                    zipf.write(json_path, "project.json")

            print(f"Project saved successfully: {output_path}")
            return True

        except Exception as e:
            print(f"Error saving project: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def load_project(project_path: str) -> Optional[Dict[str, Any]]:
        """Load a project file

        Args:
            project_path: Path to the project file

        Returns:
            Dictionary containing:
            - 'pdf_path': Temporary path to extracted PDF
            - 'layers': List of layer data dicts
            - 'guides': List of guide data dicts
            - 'settings': Settings dict
            - 'temp_dir': Temporary directory (caller must clean up)

            Returns None on error
        """
        if not os.path.exists(project_path):
            print(f"Error: Project file not found: {project_path}")
            return None

        try:
            # Create temporary directory for extracted files
            temp_dir = tempfile.mkdtemp(prefix="pdfproj_")

            # Extract ZIP archive
            with zipfile.ZipFile(project_path, 'r') as zipf:
                zipf.extractall(temp_dir)

            # Load project JSON
            json_path = os.path.join(temp_dir, "project.json")
            with open(json_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)

            # Restore pixmaps from base64
            if 'layers' in project_data:
                for layer_data in project_data['layers']:
                    ProjectManager._restore_pixmaps(layer_data)

            return {
                'pdf_path': os.path.join(temp_dir, "document.pdf"),
                'layers': project_data.get('layers', []),
                'guides': project_data.get('guides', []),
                'settings': project_data.get('settings', {}),
                'version': project_data.get('version', '1.0'),
                'temp_dir': temp_dir
            }

        except Exception as e:
            print(f"Error loading project: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def _serialize_layers(layer_manager: LayerManager) -> list:
        """Serialize all layers to a list of dicts"""
        layers_data = []

        for layer in layer_manager.layers:
            layer_dict = {
                'id': layer.id,
                'type': layer.type.value if hasattr(layer.type, 'value') else str(layer.type),
                'page_num': layer.page_num,
                'name': layer.name,
                'visible': layer.visible,
                'locked': layer.locked,
                'opacity': layer.opacity,
                'data': dict(layer.data) if layer.data else {},
                'class': type(layer).__name__
            }

            # Handle rotation for interactive layers
            if hasattr(layer, 'rotation'):
                layer_dict['rotation'] = layer.rotation

            # Handle pixmap in data (convert to base64)
            if 'pixmap' in layer_dict['data'] and layer_dict['data']['pixmap'] is not None:
                pixmap = layer_dict['data']['pixmap']
                if isinstance(pixmap, QPixmap):
                    buffer = QBuffer()
                    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                    pixmap.save(buffer, "PNG")
                    layer_dict['data']['pixmap'] = {
                        '_pixmap_base64': base64.b64encode(buffer.data().data()).decode()
                    }

            layers_data.append(layer_dict)

        return layers_data

    @staticmethod
    def _serialize_guides(guide_manager) -> list:
        """Serialize all guides to a list of dicts"""
        if not guide_manager:
            return []

        guides_data = []
        for guide in guide_manager.guides:
            guides_data.append({
                'orientation': guide.orientation.value,
                'position': guide.position,
                'page_num': guide.page_num,
                'locked': guide.locked
            })

        return guides_data

    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for non-serializable objects"""
        if isinstance(obj, QPixmap):
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            obj.save(buffer, "PNG")
            return {'_pixmap_base64': base64.b64encode(buffer.data().data()).decode()}
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @staticmethod
    def _restore_pixmaps(data):
        """Restore QPixmap objects from base64 encoded data"""
        if isinstance(data, dict):
            if '_pixmap_base64' in data:
                pixmap = QPixmap()
                pixmap.loadFromData(base64.b64decode(data['_pixmap_base64']))
                return pixmap

            for key, value in list(data.items()):
                result = ProjectManager._restore_pixmaps(value)
                if result is not None:
                    data[key] = result

        elif isinstance(data, list):
            for i, item in enumerate(data):
                result = ProjectManager._restore_pixmaps(item)
                if result is not None:
                    data[i] = result

        return None

    @staticmethod
    def restore_layers(layer_manager: LayerManager, layers_data: list):
        """Restore layers from serialized data

        Args:
            layer_manager: The layer manager to add layers to
            layers_data: List of layer data dicts from project file
        """
        from core.layer import LayerType
        from core.interactive_layer import TextFieldLayer, ImageLayer, SymbolLayer

        for layer_data in layers_data:
            layer_class = layer_data.get('class', 'Layer')
            page_num = layer_data.get('page_num', 0)
            data = layer_data.get('data', {})

            layer = None

            if layer_class == 'TextFieldLayer':
                layer = TextFieldLayer(
                    page_num=page_num,
                    x=data.get('x', 0),
                    y=data.get('y', 0),
                    text=data.get('text', ''),
                    width=data.get('width', 150),
                    height=data.get('height', 40)
                )
                # Restore additional text properties
                for key in ['font', 'font_size', 'color', 'bold', 'italic', 'underline']:
                    if key in data:
                        layer.data[key] = data[key]

            elif layer_class == 'ImageLayer':
                pixmap = data.get('pixmap')
                if isinstance(pixmap, dict) and '_pixmap_base64' in pixmap:
                    pm = QPixmap()
                    pm.loadFromData(base64.b64decode(pixmap['_pixmap_base64']))
                    pixmap = pm
                elif not isinstance(pixmap, QPixmap):
                    pixmap = None

                layer = ImageLayer(
                    page_num=page_num,
                    x=data.get('x', 0),
                    y=data.get('y', 0),
                    pixmap=pixmap,
                    width=data.get('width'),
                    height=data.get('height'),
                    image_path=data.get('image_path')
                )

            elif layer_class == 'SymbolLayer':
                layer = SymbolLayer(
                    page_num=page_num,
                    x=data.get('x', 0),
                    y=data.get('y', 0),
                    symbol=data.get('symbol', ''),
                    font_size=data.get('font_size', 24)
                )
                if 'color' in data:
                    layer.data['color'] = data['color']

            else:
                # Generic layer
                layer_type_str = layer_data.get('type', 'DRAWING')
                try:
                    layer_type = LayerType(layer_type_str)
                except ValueError:
                    layer_type = LayerType.DRAWING

                layer = Layer(layer_type, page_num, layer_data.get('name', 'Layer'))
                layer.data = data

            if layer:
                # Restore common properties
                layer.id = layer_data.get('id', layer.id)
                layer.name = layer_data.get('name', layer.name)
                layer.visible = layer_data.get('visible', True)
                layer.locked = layer_data.get('locked', False)
                layer.opacity = layer_data.get('opacity', 1.0)

                if 'rotation' in layer_data and hasattr(layer, 'rotation'):
                    layer.rotation = layer_data['rotation']

                layer_manager.add_layer(layer)

    @staticmethod
    def restore_guides(guide_manager, guides_data: list):
        """Restore guides from serialized data

        Args:
            guide_manager: The guide manager to add guides to
            guides_data: List of guide data dicts from project file
        """
        if not guide_manager or not guides_data:
            return

        from core.guide_manager import GuideOrientation

        guide_manager.clear_all_guides()

        for guide_data in guides_data:
            orientation_str = guide_data.get('orientation', 'horizontal')
            try:
                orientation = GuideOrientation(orientation_str)
            except ValueError:
                orientation = GuideOrientation.HORIZONTAL

            guide = guide_manager.add_guide(
                orientation=orientation,
                position=guide_data.get('position', 0),
                page_num=guide_data.get('page_num', -1)
            )
            guide.locked = guide_data.get('locked', False)
