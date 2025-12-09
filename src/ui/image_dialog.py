"""
Image Dialog
Dialog for selecting images and configuring scaling options with crop functionality
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QComboBox, QFileDialog, QGroupBox, QSizePolicy,
                              QWidget, QCheckBox)
from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, QSize
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QBrush, QCursor
from core import ImageScaleMode
from utils.icon_helper import get_icon
from .image_edit_dialog import ImageEditDialog


class CropPreviewWidget(QWidget):
    """Widget for displaying image with adjustable crop bounding box"""

    HANDLE_SIZE = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setMaximumSize(450, 350)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.original_pixmap = None
        self.display_pixmap = None
        self.scale_factor = 1.0

        # Crop rectangle in image coordinates
        self.crop_rect = QRect()

        # Display offset (for centering image in widget)
        self.image_offset = QPoint(0, 0)

        # Dragging state
        self.dragging = False
        self.drag_handle = None  # 'tl', 'tr', 'bl', 'br', 't', 'b', 'l', 'r', 'move'
        self.drag_start = QPoint()
        self.crop_start = QRect()

        # Aspect ratio lock
        self.lock_aspect_ratio = False
        self.original_aspect_ratio = 1.0

        self.setMouseTracking(True)

    def set_image(self, pixmap: QPixmap):
        """Set the image to display"""
        self.original_pixmap = pixmap
        if pixmap and not pixmap.isNull():
            # Scale to fit widget while maintaining aspect ratio
            available_size = self.size()
            scaled = pixmap.scaled(
                available_size.width() - 20,
                available_size.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.display_pixmap = scaled
            self.scale_factor = scaled.width() / pixmap.width()

            # Center the image
            self.image_offset = QPoint(
                (available_size.width() - scaled.width()) // 2,
                (available_size.height() - scaled.height()) // 2
            )

            # Initialize crop rect to full image
            self.crop_rect = QRect(0, 0, pixmap.width(), pixmap.height())

            # Store original aspect ratio
            self.original_aspect_ratio = pixmap.width() / pixmap.height() if pixmap.height() > 0 else 1.0
        else:
            self.display_pixmap = None
            self.crop_rect = QRect()
            self.original_aspect_ratio = 1.0

        self.update()

    def set_lock_aspect_ratio(self, locked: bool):
        """Set whether to lock aspect ratio during crop"""
        self.lock_aspect_ratio = locked

    def get_crop_rect(self) -> QRect:
        """Get the crop rectangle in original image coordinates"""
        return self.crop_rect

    def _display_to_image_coords(self, pos: QPoint) -> QPoint:
        """Convert display coordinates to image coordinates"""
        if self.scale_factor == 0:
            return QPoint(0, 0)
        x = int((pos.x() - self.image_offset.x()) / self.scale_factor)
        y = int((pos.y() - self.image_offset.y()) / self.scale_factor)
        return QPoint(x, y)

    def _image_to_display_coords(self, pos: QPoint) -> QPoint:
        """Convert image coordinates to display coordinates"""
        x = int(pos.x() * self.scale_factor + self.image_offset.x())
        y = int(pos.y() * self.scale_factor + self.image_offset.y())
        return QPoint(x, y)

    def _get_display_crop_rect(self) -> QRect:
        """Get crop rectangle in display coordinates"""
        if self.crop_rect.isNull():
            return QRect()
        tl = self._image_to_display_coords(self.crop_rect.topLeft())
        br = self._image_to_display_coords(self.crop_rect.bottomRight())
        return QRect(tl, br)

    def _get_handle_at(self, pos: QPoint) -> str:
        """Determine which handle (if any) is at the given position"""
        if not self.display_pixmap:
            return None

        rect = self._get_display_crop_rect()
        hs = self.HANDLE_SIZE

        # Corner handles
        if QRect(rect.left() - hs//2, rect.top() - hs//2, hs, hs).contains(pos):
            return 'tl'
        if QRect(rect.right() - hs//2, rect.top() - hs//2, hs, hs).contains(pos):
            return 'tr'
        if QRect(rect.left() - hs//2, rect.bottom() - hs//2, hs, hs).contains(pos):
            return 'bl'
        if QRect(rect.right() - hs//2, rect.bottom() - hs//2, hs, hs).contains(pos):
            return 'br'

        # Edge handles
        mid_x = (rect.left() + rect.right()) // 2
        mid_y = (rect.top() + rect.bottom()) // 2

        if QRect(mid_x - hs//2, rect.top() - hs//2, hs, hs).contains(pos):
            return 't'
        if QRect(mid_x - hs//2, rect.bottom() - hs//2, hs, hs).contains(pos):
            return 'b'
        if QRect(rect.left() - hs//2, mid_y - hs//2, hs, hs).contains(pos):
            return 'l'
        if QRect(rect.right() - hs//2, mid_y - hs//2, hs, hs).contains(pos):
            return 'r'

        # Inside rect = move
        if rect.contains(pos):
            return 'move'

        return None

    def _update_cursor(self, handle: str):
        """Update cursor based on handle"""
        if handle in ('tl', 'br'):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif handle in ('tr', 'bl'):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif handle in ('t', 'b'):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif handle in ('l', 'r'):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif handle == 'move':
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.display_pixmap:
            handle = self._get_handle_at(event.pos())
            if handle:
                self.dragging = True
                self.drag_handle = handle
                self.drag_start = event.pos()
                self.crop_start = QRect(self.crop_rect)

    def mouseMoveEvent(self, event):
        if not self.display_pixmap:
            return

        if self.dragging:
            # Calculate delta in image coordinates
            delta_display = event.pos() - self.drag_start
            delta_x = int(delta_display.x() / self.scale_factor)
            delta_y = int(delta_display.y() / self.scale_factor)

            new_rect = QRect(self.crop_start)
            img_w = self.original_pixmap.width()
            img_h = self.original_pixmap.height()

            if self.drag_handle == 'move':
                new_rect.translate(delta_x, delta_y)
                # Clamp to image bounds
                if new_rect.left() < 0:
                    new_rect.moveLeft(0)
                if new_rect.top() < 0:
                    new_rect.moveTop(0)
                if new_rect.right() >= img_w:
                    new_rect.moveRight(img_w - 1)
                if new_rect.bottom() >= img_h:
                    new_rect.moveBottom(img_h - 1)

            elif self.drag_handle == 'tl':
                new_rect.setTopLeft(self.crop_start.topLeft() + QPoint(delta_x, delta_y))
                if self.lock_aspect_ratio:
                    new_rect = self._adjust_aspect_ratio(new_rect, 'tl')
            elif self.drag_handle == 'tr':
                new_rect.setTopRight(self.crop_start.topRight() + QPoint(delta_x, delta_y))
                if self.lock_aspect_ratio:
                    new_rect = self._adjust_aspect_ratio(new_rect, 'tr')
            elif self.drag_handle == 'bl':
                new_rect.setBottomLeft(self.crop_start.bottomLeft() + QPoint(delta_x, delta_y))
                if self.lock_aspect_ratio:
                    new_rect = self._adjust_aspect_ratio(new_rect, 'bl')
            elif self.drag_handle == 'br':
                new_rect.setBottomRight(self.crop_start.bottomRight() + QPoint(delta_x, delta_y))
                if self.lock_aspect_ratio:
                    new_rect = self._adjust_aspect_ratio(new_rect, 'br')
            elif self.drag_handle == 't':
                new_rect.setTop(self.crop_start.top() + delta_y)
                if self.lock_aspect_ratio:
                    # Adjust width to maintain aspect ratio
                    new_height = new_rect.height()
                    new_width = int(new_height * self.original_aspect_ratio)
                    center_x = new_rect.center().x()
                    new_rect.setLeft(center_x - new_width // 2)
                    new_rect.setRight(center_x + new_width // 2)
            elif self.drag_handle == 'b':
                new_rect.setBottom(self.crop_start.bottom() + delta_y)
                if self.lock_aspect_ratio:
                    new_height = new_rect.height()
                    new_width = int(new_height * self.original_aspect_ratio)
                    center_x = new_rect.center().x()
                    new_rect.setLeft(center_x - new_width // 2)
                    new_rect.setRight(center_x + new_width // 2)
            elif self.drag_handle == 'l':
                new_rect.setLeft(self.crop_start.left() + delta_x)
                if self.lock_aspect_ratio:
                    # Adjust height to maintain aspect ratio
                    new_width = new_rect.width()
                    new_height = int(new_width / self.original_aspect_ratio)
                    center_y = new_rect.center().y()
                    new_rect.setTop(center_y - new_height // 2)
                    new_rect.setBottom(center_y + new_height // 2)
            elif self.drag_handle == 'r':
                new_rect.setRight(self.crop_start.right() + delta_x)
                if self.lock_aspect_ratio:
                    new_width = new_rect.width()
                    new_height = int(new_width / self.original_aspect_ratio)
                    center_y = new_rect.center().y()
                    new_rect.setTop(center_y - new_height // 2)
                    new_rect.setBottom(center_y + new_height // 2)

            # Normalize and clamp
            new_rect = new_rect.normalized()
            new_rect.setLeft(max(0, new_rect.left()))
            new_rect.setTop(max(0, new_rect.top()))
            new_rect.setRight(min(img_w - 1, new_rect.right()))
            new_rect.setBottom(min(img_h - 1, new_rect.bottom()))

            # Ensure minimum size
            if new_rect.width() >= 10 and new_rect.height() >= 10:
                self.crop_rect = new_rect
                self.update()
        else:
            # Update cursor based on hover
            handle = self._get_handle_at(event.pos())
            self._update_cursor(handle)

    def _adjust_aspect_ratio(self, rect: QRect, handle: str) -> QRect:
        """Adjust rectangle to maintain original aspect ratio based on corner handle"""
        width = rect.width()
        height = rect.height()
        target_ratio = self.original_aspect_ratio

        # Calculate what height should be for current width
        expected_height = int(width / target_ratio)
        # Calculate what width should be for current height
        expected_width = int(height * target_ratio)

        # Use the larger dimension change to determine which to adjust
        if handle in ('tl', 'bl'):
            # Left corners - adjust based on width change, keep right edge fixed
            if abs(width - self.crop_start.width()) > abs(height - self.crop_start.height()):
                new_height = expected_height
                if handle == 'tl':
                    rect.setTop(rect.bottom() - new_height)
                else:
                    rect.setBottom(rect.top() + new_height)
            else:
                new_width = expected_width
                rect.setLeft(rect.right() - new_width)
        else:  # 'tr', 'br'
            # Right corners - adjust based on width change, keep left edge fixed
            if abs(width - self.crop_start.width()) > abs(height - self.crop_start.height()):
                new_height = expected_height
                if handle == 'tr':
                    rect.setTop(rect.bottom() - new_height)
                else:
                    rect.setBottom(rect.top() + new_height)
            else:
                new_width = expected_width
                rect.setRight(rect.left() + new_width)

        return rect

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.drag_handle = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor("#F5F5F5"))

        if not self.display_pixmap:
            # Draw placeholder text
            painter.setPen(QColor("#999999"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No image selected")
            return

        # Draw the image
        painter.drawPixmap(self.image_offset, self.display_pixmap)

        # Draw darkened overlay outside crop area
        display_rect = self._get_display_crop_rect()
        overlay_color = QColor(0, 0, 0, 120)

        # Top
        painter.fillRect(QRect(self.image_offset.x(), self.image_offset.y(),
                               self.display_pixmap.width(), display_rect.top() - self.image_offset.y()),
                        overlay_color)
        # Bottom
        painter.fillRect(QRect(self.image_offset.x(), display_rect.bottom(),
                               self.display_pixmap.width(),
                               self.image_offset.y() + self.display_pixmap.height() - display_rect.bottom()),
                        overlay_color)
        # Left
        painter.fillRect(QRect(self.image_offset.x(), display_rect.top(),
                               display_rect.left() - self.image_offset.x(), display_rect.height()),
                        overlay_color)
        # Right
        painter.fillRect(QRect(display_rect.right(), display_rect.top(),
                               self.image_offset.x() + self.display_pixmap.width() - display_rect.right(),
                               display_rect.height()),
                        overlay_color)

        # Draw crop rectangle border
        pen = QPen(QColor("#00A0FF"), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(display_rect)

        # Draw corner handles
        hs = self.HANDLE_SIZE
        handle_brush = QBrush(QColor("#FFFFFF"))
        handle_pen = QPen(QColor("#00A0FF"), 2)
        painter.setPen(handle_pen)
        painter.setBrush(handle_brush)

        # Corners
        corners = [
            (display_rect.left(), display_rect.top()),
            (display_rect.right(), display_rect.top()),
            (display_rect.left(), display_rect.bottom()),
            (display_rect.right(), display_rect.bottom()),
        ]
        for cx, cy in corners:
            painter.drawRect(cx - hs//2, cy - hs//2, hs, hs)

        # Edge midpoints
        mid_x = (display_rect.left() + display_rect.right()) // 2
        mid_y = (display_rect.top() + display_rect.bottom()) // 2
        edges = [
            (mid_x, display_rect.top()),
            (mid_x, display_rect.bottom()),
            (display_rect.left(), mid_y),
            (display_rect.right(), mid_y),
        ]
        for ex, ey in edges:
            painter.drawRect(ex - hs//2, ey - hs//2, hs, hs)

        # Draw crop dimensions
        painter.setPen(QColor("#FFFFFF"))
        dim_text = f"{self.crop_rect.width()} x {self.crop_rect.height()}"
        text_x = display_rect.center().x() - 30
        text_y = display_rect.bottom() + 18
        painter.fillRect(text_x - 5, text_y - 12, 70, 16, QColor(0, 0, 0, 180))
        painter.drawText(text_x, text_y, dim_text)


class ImageDialog(QDialog):
    """Dialog for image selection and scaling configuration with crop"""

    def __init__(self, parent=None, initial_image_path: str = None,
                 initial_scale_mode: str = None):
        super().__init__(parent)
        self.setWindowTitle("Insert Image")
        self.setModal(True)
        self.resize(520, 680)

        self.selected_pixmap = None
        self.selected_image_path = initial_image_path
        self.scale_mode = initial_scale_mode or ImageScaleMode.FIT.value

        # Load initial image if provided
        if initial_image_path:
            self.selected_pixmap = QPixmap(initial_image_path)

        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout()

        # Title
        title = QLabel("Configure Image")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(title)

        # Image selection group
        image_group = QGroupBox("Image")
        image_layout = QVBoxLayout()

        # Select image button
        select_layout = QHBoxLayout()
        self.image_path_label = QLabel("No image selected")
        self.image_path_label.setStyleSheet("color: #666; padding: 5px;")
        select_layout.addWidget(self.image_path_label)

        select_btn = QPushButton("Browse...")
        select_btn.clicked.connect(self.select_image)
        select_layout.addWidget(select_btn)
        image_layout.addLayout(select_layout)

        # Image preview with crop - header with edit button
        preview_header = QHBoxLayout()
        preview_label = QLabel("Preview (drag handles to crop):")
        preview_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        preview_header.addWidget(preview_label)
        preview_header.addStretch()

        # Edit image button
        self.edit_image_btn = QPushButton()
        self.edit_image_btn.setFixedSize(28, 28)
        self.edit_image_btn.setIcon(get_icon("tools"))
        self.edit_image_btn.setIconSize(QSize(18, 18))
        self.edit_image_btn.setToolTip("Edit image (rotate, adjust, filters)")
        self.edit_image_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.edit_image_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #aaa;
                border-radius: 4px;
            }
            QPushButton:hover {
                border: 1px solid #00c000;
                background-color: rgba(0, 192, 0, 0.1);
            }
        """)
        self.edit_image_btn.clicked.connect(self._open_image_editor)
        preview_header.addWidget(self.edit_image_btn)

        image_layout.addLayout(preview_header)

        self.crop_preview = CropPreviewWidget()
        self.crop_preview.setStyleSheet("""
            QWidget {
                border: 2px solid #CCCCCC;
                background-color: #F5F5F5;
            }
        """)
        image_layout.addWidget(self.crop_preview)

        # Aspect ratio lock and reset crop buttons
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()

        # Aspect ratio lock button
        self.aspect_lock_btn = QPushButton()
        self.aspect_lock_btn.setFixedSize(28, 28)
        self.aspect_lock_btn.setCheckable(True)
        self.aspect_lock_btn.setChecked(False)
        self.aspect_lock_btn.setIcon(get_icon("link"))
        self.aspect_lock_btn.setIconSize(QSize(18, 18))
        self.aspect_lock_btn.setToolTip("Lock aspect ratio for cropping")
        self.aspect_lock_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._update_aspect_lock_style()
        self.aspect_lock_btn.clicked.connect(self._on_aspect_lock_toggled)
        reset_layout.addWidget(self.aspect_lock_btn)

        reset_crop_btn = QPushButton("Reset Crop")
        reset_crop_btn.clicked.connect(self.reset_crop)
        reset_layout.addWidget(reset_crop_btn)
        image_layout.addLayout(reset_layout)

        image_group.setLayout(image_layout)
        layout.addWidget(image_group)

        # Scaling options group
        scale_group = QGroupBox("Scaling Options")
        scale_layout = QVBoxLayout()

        scale_label = QLabel("Scale Mode:")
        scale_layout.addWidget(scale_label)

        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Fit to Frame (Maintain Aspect Ratio)", ImageScaleMode.FIT.value)
        self.scale_combo.addItem("Fill Frame (Maintain Aspect, Crop)", ImageScaleMode.FILL.value)
        self.scale_combo.addItem("Stretch to Frame (Ignore Aspect)", ImageScaleMode.STRETCH.value)
        self.scale_combo.addItem("Actual Size (No Scaling)", ImageScaleMode.ACTUAL.value)

        # Set initial scale mode
        for i in range(self.scale_combo.count()):
            if self.scale_combo.itemData(i) == self.scale_mode:
                self.scale_combo.setCurrentIndex(i)
                break

        self.scale_combo.currentIndexChanged.connect(self.on_scale_mode_changed)
        scale_layout.addWidget(self.scale_combo)

        # Scale mode descriptions
        desc_label = QLabel()
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        desc_label.setText(
            "<b>Fit:</b> Scales image to fit within frame, maintaining aspect ratio.<br>"
            "<b>Fill:</b> Scales to fill entire frame, maintains aspect, may crop edges.<br>"
            "<b>Stretch:</b> Stretches to fill frame exactly, may distort image.<br>"
            "<b>Actual:</b> Uses original image size, no scaling applied."
        )
        scale_layout.addWidget(desc_label)

        scale_group.setLayout(scale_layout)
        layout.addWidget(scale_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Update preview if initial image provided
        if self.selected_pixmap:
            self.crop_preview.set_image(self.selected_pixmap)
            self.image_path_label.setText(self.selected_image_path or "Image loaded")

    def select_image(self):
        """Open file dialog to select image"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.tiff);;All Files (*)"
        )

        if file_path:
            # Load the image
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.selected_pixmap = pixmap
                self.selected_image_path = file_path
                self.image_path_label.setText(file_path.split('/')[-1])
                self.crop_preview.set_image(pixmap)
            else:
                self.image_path_label.setText("Failed to load image")

    def reset_crop(self):
        """Reset crop to full image"""
        if self.selected_pixmap:
            self.crop_preview.set_image(self.selected_pixmap)

    def _on_aspect_lock_toggled(self):
        """Handle aspect ratio lock toggle"""
        is_locked = self.aspect_lock_btn.isChecked()
        self.crop_preview.set_lock_aspect_ratio(is_locked)
        self._update_aspect_lock_style()

    def _update_aspect_lock_style(self):
        """Update aspect lock button style based on state"""
        if self.aspect_lock_btn.isChecked():
            self.aspect_lock_btn.setIcon(get_icon("link", color="#00c000"))
            self.aspect_lock_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 192, 0, 0.1);
                    border: 1px solid #00c000;
                    border-radius: 4px;
                }
            """)
        else:
            self.aspect_lock_btn.setIcon(get_icon("link"))
            self.aspect_lock_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #aaa;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    border: 1px solid #00c000;
                    background-color: rgba(0, 192, 0, 0.1);
                }
            """)

    def on_scale_mode_changed(self, index):
        """Handle scale mode change"""
        self.scale_mode = self.scale_combo.itemData(index)

    def _open_image_editor(self):
        """Open the image editor dialog"""
        if not self.selected_pixmap or self.selected_pixmap.isNull():
            return

        # Open image edit dialog with current pixmap
        editor = ImageEditDialog(self, self.selected_pixmap)
        if editor.exec() == QDialog.DialogCode.Accepted:
            # Get edited pixmap and update
            edited_pixmap = editor.get_edited_pixmap()
            if edited_pixmap and not edited_pixmap.isNull():
                self.selected_pixmap = edited_pixmap
                self.crop_preview.set_image(edited_pixmap)

    def get_values(self):
        """Get dialog values"""
        # Apply crop to pixmap
        cropped_pixmap = self.selected_pixmap
        if self.selected_pixmap and not self.selected_pixmap.isNull():
            crop_rect = self.crop_preview.get_crop_rect()
            if not crop_rect.isNull() and crop_rect.isValid():
                # Check if crop is different from full image
                full_rect = QRect(0, 0, self.selected_pixmap.width(), self.selected_pixmap.height())
                if crop_rect != full_rect:
                    cropped_pixmap = self.selected_pixmap.copy(crop_rect)

        return {
            'pixmap': cropped_pixmap,
            'image_path': self.selected_image_path,
            'scale_mode': self.scale_mode
        }

    def accept(self):
        """Override accept to validate"""
        if not self.selected_pixmap or self.selected_pixmap.isNull():
            # Don't accept if no image selected
            return

        super().accept()
