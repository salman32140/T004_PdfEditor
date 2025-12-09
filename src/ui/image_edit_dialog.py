"""
Image Edit Dialog
Non-destructive image editing tools with real-time preview
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QSlider, QGroupBox, QWidget, QScrollArea,
                              QSizePolicy, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QImage, QColor, QCursor, QTransform
from utils.icon_helper import get_icon
from PIL import Image, ImageEnhance, ImageFilter
import io


class ImagePreviewWidget(QWidget):
    """Widget for displaying image preview"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.pixmap = None

    def set_pixmap(self, pixmap: QPixmap):
        """Set the pixmap to display"""
        self.pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Fill background
        painter.fillRect(self.rect(), QColor("#2a2a2a"))

        if self.pixmap and not self.pixmap.isNull():
            # Scale pixmap to fit while maintaining aspect ratio
            scaled = self.pixmap.scaled(
                self.width() - 20,
                self.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Center the image
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.setPen(QColor("#666666"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No image")


class ImageEditDialog(QDialog):
    """Dialog for non-destructive image editing"""

    def __init__(self, parent=None, pixmap: QPixmap = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Image")
        self.setModal(True)
        self.resize(700, 600)

        # Store original image
        self.original_pixmap = pixmap
        self.original_pil_image = None
        self.edited_pixmap = pixmap

        # Convert QPixmap to PIL Image for editing
        if pixmap and not pixmap.isNull():
            self.original_pil_image = self._qpixmap_to_pil(pixmap)

        # Edit parameters (non-destructive)
        self.rotation = 0
        self.flip_h = False
        self.flip_v = False
        self.brightness = 1.0
        self.contrast = 1.0
        self.sharpness = 1.0
        self.blur = 0.0
        self.hue = 0
        self.saturation = 1.0
        self.grayscale = False

        self.setup_ui()
        self._apply_edits()

    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QHBoxLayout()

        # Left side - Preview
        preview_layout = QVBoxLayout()

        preview_label = QLabel("Preview")
        preview_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #ccc;")
        preview_layout.addWidget(preview_label)

        self.preview_widget = ImagePreviewWidget()
        self.preview_widget.setStyleSheet("""
            QWidget {
                border: 2px solid #444;
                border-radius: 4px;
                background-color: #2a2a2a;
            }
        """)
        preview_layout.addWidget(self.preview_widget, 1)

        layout.addLayout(preview_layout, 3)

        # Right side - Controls
        controls_widget = QWidget()
        controls_widget.setFixedWidth(260)
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(10, 0, 0, 0)

        # Scroll area for controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #2a2a2a;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 4px;
            }
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)

        # Transform group
        transform_group = QGroupBox("Transform")
        transform_group.setStyleSheet(self._group_style())
        transform_layout = QVBoxLayout()

        # Rotate buttons
        rotate_layout = QHBoxLayout()
        rotate_label = QLabel("Rotate:")
        rotate_label.setStyleSheet("color: #aaa;")
        rotate_layout.addWidget(rotate_label)
        rotate_layout.addStretch()

        self.rotate_ccw_btn = QPushButton()
        self.rotate_ccw_btn.setFixedSize(32, 32)
        self.rotate_ccw_btn.setIcon(get_icon("rotate-ccw"))
        self.rotate_ccw_btn.setIconSize(QSize(18, 18))
        self.rotate_ccw_btn.setToolTip("Rotate 90° counter-clockwise")
        self.rotate_ccw_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.rotate_ccw_btn.setStyleSheet(self._button_style())
        self.rotate_ccw_btn.clicked.connect(lambda: self._rotate(-90))
        rotate_layout.addWidget(self.rotate_ccw_btn)

        self.rotate_cw_btn = QPushButton()
        self.rotate_cw_btn.setFixedSize(32, 32)
        self.rotate_cw_btn.setIcon(get_icon("rotate-cw"))
        self.rotate_cw_btn.setIconSize(QSize(18, 18))
        self.rotate_cw_btn.setToolTip("Rotate 90° clockwise")
        self.rotate_cw_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.rotate_cw_btn.setStyleSheet(self._button_style())
        self.rotate_cw_btn.clicked.connect(lambda: self._rotate(90))
        rotate_layout.addWidget(self.rotate_cw_btn)

        transform_layout.addLayout(rotate_layout)

        # Flip buttons
        flip_layout = QHBoxLayout()
        flip_label = QLabel("Flip:")
        flip_label.setStyleSheet("color: #aaa;")
        flip_layout.addWidget(flip_label)
        flip_layout.addStretch()

        self.flip_h_btn = QPushButton()
        self.flip_h_btn.setFixedSize(32, 32)
        self.flip_h_btn.setIcon(get_icon("flip-horizontal"))
        self.flip_h_btn.setIconSize(QSize(18, 18))
        self.flip_h_btn.setToolTip("Flip horizontal")
        self.flip_h_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.flip_h_btn.setCheckable(True)
        self.flip_h_btn.setStyleSheet(self._toggle_button_style())
        self.flip_h_btn.clicked.connect(self._flip_horizontal)
        flip_layout.addWidget(self.flip_h_btn)

        self.flip_v_btn = QPushButton()
        self.flip_v_btn.setFixedSize(32, 32)
        self.flip_v_btn.setIcon(get_icon("flip-vertical"))
        self.flip_v_btn.setIconSize(QSize(18, 18))
        self.flip_v_btn.setToolTip("Flip vertical")
        self.flip_v_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.flip_v_btn.setCheckable(True)
        self.flip_v_btn.setStyleSheet(self._toggle_button_style())
        self.flip_v_btn.clicked.connect(self._flip_vertical)
        flip_layout.addWidget(self.flip_v_btn)

        transform_layout.addLayout(flip_layout)
        transform_group.setLayout(transform_layout)
        scroll_layout.addWidget(transform_group)

        # Adjustments group
        adjust_group = QGroupBox("Adjustments")
        adjust_group.setStyleSheet(self._group_style())
        adjust_layout = QVBoxLayout()

        # Brightness
        self.brightness_slider = self._create_slider("Brightness", -100, 100, 0)
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        adjust_layout.addLayout(self._create_slider_row("Brightness", self.brightness_slider))

        # Contrast
        self.contrast_slider = self._create_slider("Contrast", -100, 100, 0)
        self.contrast_slider.valueChanged.connect(self._on_contrast_changed)
        adjust_layout.addLayout(self._create_slider_row("Contrast", self.contrast_slider))

        # Sharpness
        self.sharpness_slider = self._create_slider("Sharpness", -100, 100, 0)
        self.sharpness_slider.valueChanged.connect(self._on_sharpness_changed)
        adjust_layout.addLayout(self._create_slider_row("Sharpness", self.sharpness_slider))

        # Blur
        self.blur_slider = self._create_slider("Blur", 0, 100, 0)
        self.blur_slider.valueChanged.connect(self._on_blur_changed)
        adjust_layout.addLayout(self._create_slider_row("Blur", self.blur_slider))

        adjust_group.setLayout(adjust_layout)
        scroll_layout.addWidget(adjust_group)

        # Color group
        color_group = QGroupBox("Color")
        color_group.setStyleSheet(self._group_style())
        color_layout = QVBoxLayout()

        # Hue
        self.hue_slider = self._create_slider("Hue", -180, 180, 0)
        self.hue_slider.valueChanged.connect(self._on_hue_changed)
        color_layout.addLayout(self._create_slider_row("Hue", self.hue_slider))

        # Saturation
        self.saturation_slider = self._create_slider("Saturation", -100, 100, 0)
        self.saturation_slider.valueChanged.connect(self._on_saturation_changed)
        color_layout.addLayout(self._create_slider_row("Saturation", self.saturation_slider))

        # Black & White toggle
        bw_layout = QHBoxLayout()
        bw_label = QLabel("Black & White:")
        bw_label.setStyleSheet("color: #aaa;")
        bw_layout.addWidget(bw_label)
        bw_layout.addStretch()

        self.bw_btn = QPushButton("B&W")
        self.bw_btn.setFixedSize(50, 28)
        self.bw_btn.setCheckable(True)
        self.bw_btn.setToolTip("Convert to black and white")
        self.bw_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.bw_btn.setStyleSheet(self._toggle_button_style())
        self.bw_btn.clicked.connect(self._toggle_grayscale)
        bw_layout.addWidget(self.bw_btn)

        color_layout.addLayout(bw_layout)
        color_group.setLayout(color_layout)
        scroll_layout.addWidget(color_group)

        # Reset button
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        self.reset_btn = QPushButton("Reset to Original")
        self.reset_btn.setFixedHeight(32)
        self.reset_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: #fff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #555;
                border-color: #666;
            }
        """)
        self.reset_btn.clicked.connect(self._reset_to_original)
        reset_layout.addWidget(self.reset_btn)
        reset_layout.addStretch()
        scroll_layout.addLayout(reset_layout)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        controls_layout.addWidget(scroll)

        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: #fff;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.setFixedSize(80, 32)
        apply_btn.setDefault(True)
        apply_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #fff;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
        """)
        apply_btn.clicked.connect(self.accept)
        button_layout.addWidget(apply_btn)

        controls_layout.addLayout(button_layout)
        layout.addWidget(controls_widget)

        self.setLayout(layout)

        # Apply dark theme to dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
            }
            QLabel {
                color: #ccc;
            }
        """)

    def _group_style(self):
        """Get group box style"""
        return """
            QGroupBox {
                font-weight: bold;
                color: #aaa;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """

    def _button_style(self):
        """Get button style"""
        return """
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #454545;
                border-color: #666;
            }
            QPushButton:pressed {
                background-color: #505050;
            }
        """

    def _toggle_button_style(self):
        """Get toggle button style"""
        return """
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #454545;
                border-color: #666;
            }
            QPushButton:checked {
                background-color: rgba(0, 192, 0, 0.2);
                border-color: #00c000;
            }
        """

    def _create_slider(self, name: str, min_val: int, max_val: int, default: int) -> QSlider:
        """Create a styled slider"""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #444;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #1084d8;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border-radius: 2px;
            }
        """)
        return slider

    def _create_slider_row(self, label_text: str, slider: QSlider) -> QVBoxLayout:
        """Create a labeled slider row"""
        layout = QVBoxLayout()
        layout.setSpacing(2)

        header = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet("color: #aaa; font-size: 11px;")
        header.addWidget(label)

        value_label = QLabel("0")
        value_label.setStyleSheet("color: #888; font-size: 11px;")
        value_label.setFixedWidth(35)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(value_label)

        # Connect slider to update value label
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))

        layout.addLayout(header)
        layout.addWidget(slider)

        return layout

    def _qpixmap_to_pil(self, pixmap: QPixmap) -> Image.Image:
        """Convert QPixmap to PIL Image"""
        # Convert QPixmap to QImage
        image = pixmap.toImage()
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)

        # Get image data
        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(height * width * 4)

        # Create PIL Image
        pil_image = Image.frombytes("RGBA", (width, height), bytes(ptr), "raw", "RGBA")
        return pil_image

    def _pil_to_qpixmap(self, pil_image: Image.Image) -> QPixmap:
        """Convert PIL Image to QPixmap"""
        # Ensure RGBA mode
        if pil_image.mode != "RGBA":
            pil_image = pil_image.convert("RGBA")

        # Convert to bytes
        data = pil_image.tobytes("raw", "RGBA")
        width, height = pil_image.size

        # Create QImage
        qimage = QImage(data, width, height, width * 4, QImage.Format.Format_RGBA8888)

        # Need to keep reference to data
        qimage = qimage.copy()

        return QPixmap.fromImage(qimage)

    def _rotate(self, degrees: int):
        """Rotate image"""
        self.rotation = (self.rotation + degrees) % 360
        self._apply_edits()

    def _flip_horizontal(self):
        """Toggle horizontal flip"""
        self.flip_h = self.flip_h_btn.isChecked()
        self._apply_edits()

    def _flip_vertical(self):
        """Toggle vertical flip"""
        self.flip_v = self.flip_v_btn.isChecked()
        self._apply_edits()

    def _on_brightness_changed(self, value: int):
        """Handle brightness change"""
        # Convert -100..100 to 0.0..2.0 (1.0 = no change)
        self.brightness = 1.0 + (value / 100.0)
        self._apply_edits()

    def _on_contrast_changed(self, value: int):
        """Handle contrast change"""
        self.contrast = 1.0 + (value / 100.0)
        self._apply_edits()

    def _on_sharpness_changed(self, value: int):
        """Handle sharpness change"""
        self.sharpness = 1.0 + (value / 50.0)  # Range 0..3
        self._apply_edits()

    def _on_blur_changed(self, value: int):
        """Handle blur change"""
        self.blur = value / 10.0  # Range 0..10
        self._apply_edits()

    def _on_hue_changed(self, value: int):
        """Handle hue change"""
        self.hue = value
        self._apply_edits()

    def _on_saturation_changed(self, value: int):
        """Handle saturation change"""
        self.saturation = 1.0 + (value / 100.0)
        self._apply_edits()

    def _toggle_grayscale(self):
        """Toggle grayscale mode"""
        self.grayscale = self.bw_btn.isChecked()
        self._apply_edits()

    def _reset_to_original(self):
        """Reset all edits to original"""
        self.rotation = 0
        self.flip_h = False
        self.flip_v = False
        self.brightness = 1.0
        self.contrast = 1.0
        self.sharpness = 1.0
        self.blur = 0.0
        self.hue = 0
        self.saturation = 1.0
        self.grayscale = False

        # Reset UI controls
        self.flip_h_btn.setChecked(False)
        self.flip_v_btn.setChecked(False)
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(0)
        self.sharpness_slider.setValue(0)
        self.blur_slider.setValue(0)
        self.hue_slider.setValue(0)
        self.saturation_slider.setValue(0)
        self.bw_btn.setChecked(False)

        self._apply_edits()

    def _apply_edits(self):
        """Apply all edits and update preview"""
        if not self.original_pil_image:
            return

        # Start with original
        img = self.original_pil_image.copy()

        # Apply rotation
        if self.rotation != 0:
            img = img.rotate(-self.rotation, expand=True, resample=Image.Resampling.BICUBIC)

        # Apply flips
        if self.flip_h:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if self.flip_v:
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        # Apply brightness
        if self.brightness != 1.0:
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(self.brightness)

        # Apply contrast
        if self.contrast != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(self.contrast)

        # Apply sharpness
        if self.sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(self.sharpness)

        # Apply blur
        if self.blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=self.blur))

        # Apply hue shift
        if self.hue != 0:
            img = self._shift_hue(img, self.hue)

        # Apply saturation
        if self.saturation != 1.0:
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(self.saturation)

        # Apply grayscale
        if self.grayscale:
            img = img.convert("L").convert("RGBA")

        # Convert to QPixmap and update preview
        self.edited_pixmap = self._pil_to_qpixmap(img)
        self.preview_widget.set_pixmap(self.edited_pixmap)

    def _shift_hue(self, img: Image.Image, degrees: int) -> Image.Image:
        """Shift the hue of an image"""
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Split into channels
        r, g, b, a = img.split()

        # Convert to HSV
        hsv_img = img.convert("HSV")
        h, s, v = hsv_img.split()

        # Shift hue
        h_data = list(h.getdata())
        h_shifted = [(val + int(degrees * 255 / 360)) % 256 for val in h_data]
        h.putdata(h_shifted)

        # Merge back
        hsv_shifted = Image.merge("HSV", (h, s, v))
        rgb_shifted = hsv_shifted.convert("RGB")

        # Re-add alpha channel
        r, g, b = rgb_shifted.split()
        return Image.merge("RGBA", (r, g, b, a))

    def get_edited_pixmap(self) -> QPixmap:
        """Get the edited pixmap"""
        return self.edited_pixmap
