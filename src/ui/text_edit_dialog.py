"""
Text Field Edit Dialog
Interactive dialog for editing text fields with live preview
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
                              QPushButton, QLabel, QFontComboBox, QSpinBox,
                              QCheckBox, QGroupBox, QColorDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class TextEditDialog(QDialog):
    """Dialog for editing text fields"""

    text_changed = pyqtSignal(str, str, int, str, bool, bool, bool)  # text, font, size, color, bold, italic, underline

    def __init__(self, parent=None, initial_text="", initial_font="Arial",
                 initial_size=12, initial_color="#000000",
                 initial_bold=False, initial_italic=False, initial_underline=False):
        super().__init__(parent)

        self.current_color = initial_color

        self.setWindowTitle("Edit Text Field")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.setup_ui(initial_text, initial_font, initial_size,
                     initial_bold, initial_italic, initial_underline)

    def setup_ui(self, text, font_family, font_size, bold, italic, underline):
        """Setup dialog UI"""
        layout = QVBoxLayout()

        # Text input area
        text_group = QGroupBox("Text Content")
        text_layout = QVBoxLayout()

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setMinimumHeight(150)
        self.text_edit.textChanged.connect(self.on_text_changed)
        text_layout.addWidget(self.text_edit)

        text_group.setLayout(text_layout)
        layout.addWidget(text_group)

        # Font settings
        font_group = QGroupBox("Font Settings")
        font_layout = QVBoxLayout()

        # Font family
        font_family_layout = QHBoxLayout()
        font_family_layout.addWidget(QLabel("Font:"))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(font_family))
        self.font_combo.currentFontChanged.connect(self.on_font_changed)
        font_family_layout.addWidget(self.font_combo)
        font_layout.addLayout(font_family_layout)

        # Font size
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("Size:"))
        self.size_spin = QSpinBox()
        self.size_spin.setMinimum(6)
        self.size_spin.setMaximum(200)
        self.size_spin.setValue(int(font_size))
        self.size_spin.valueChanged.connect(self.on_font_changed)
        font_size_layout.addWidget(self.size_spin)
        font_size_layout.addStretch()
        font_layout.addLayout(font_size_layout)

        # Font style
        style_layout = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.bold_check.setChecked(bold)
        self.bold_check.stateChanged.connect(self.on_font_changed)
        style_layout.addWidget(self.bold_check)

        self.italic_check = QCheckBox("Italic")
        self.italic_check.setChecked(italic)
        self.italic_check.stateChanged.connect(self.on_font_changed)
        style_layout.addWidget(self.italic_check)

        self.underline_check = QCheckBox("Underline")
        self.underline_check.setChecked(underline)
        self.underline_check.stateChanged.connect(self.on_font_changed)
        style_layout.addWidget(self.underline_check)

        style_layout.addStretch()
        font_layout.addLayout(style_layout)

        # Color
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_button = QPushButton()
        self.color_button.setFixedSize(60, 30)
        self.update_color_button(self.current_color)
        self.color_button.clicked.connect(self.pick_color)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        font_layout.addLayout(color_layout)

        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()

        self.preview_label = QLabel("Sample Text")
        self.preview_label.setMinimumHeight(60)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: white; border: 1px solid #ccc; padding: 10px;")
        preview_layout.addWidget(self.preview_label)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Initial preview update
        self.update_preview()

    def on_text_changed(self):
        """Handle text change"""
        self.update_preview()
        self.emit_changes()

    def on_font_changed(self):
        """Handle font change"""
        self.update_preview()
        self.emit_changes()

    def pick_color(self):
        """Show color picker"""
        color = QColorDialog.getColor(QColor(self.current_color), self)
        if color.isValid():
            self.current_color = color.name()
            self.update_color_button(self.current_color)
            self.update_preview()
            self.emit_changes()

    def update_color_button(self, color):
        """Update color button appearance"""
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 2px solid #333;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border: 2px solid #0078d4;
            }}
        """)

    def update_preview(self):
        """Update preview label"""
        text = self.text_edit.toPlainText() or "Sample Text"
        font_family = self.font_combo.currentFont().family()
        font_size = self.size_spin.value()
        bold = self.bold_check.isChecked()
        italic = self.italic_check.isChecked()
        underline = self.underline_check.isChecked()

        # Create preview font
        font = QFont(font_family, font_size)
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)

        self.preview_label.setFont(font)
        self.preview_label.setText(text[:50] + "..." if len(text) > 50 else text)
        self.preview_label.setStyleSheet(f"""
            background-color: white;
            border: 1px solid #ccc;
            padding: 10px;
            color: {self.current_color};
        """)

    def emit_changes(self):
        """Emit current settings"""
        self.text_changed.emit(
            self.text_edit.toPlainText(),
            self.font_combo.currentFont().family(),
            self.size_spin.value(),
            self.current_color,
            self.bold_check.isChecked(),
            self.italic_check.isChecked(),
            self.underline_check.isChecked()
        )

    def get_values(self):
        """Get all current values"""
        return {
            'text': self.text_edit.toPlainText(),
            'font': self.font_combo.currentFont().family(),
            'font_size': self.size_spin.value(),
            'color': self.current_color,
            'bold': self.bold_check.isChecked(),
            'italic': self.italic_check.isChecked(),
            'underline': self.underline_check.isChecked()
        }
