"""
Symbol Selection Dialog
Allows users to select unicode symbols from categorized lists
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QPushButton, QLabel, QComboBox, QSpinBox,
                              QScrollArea, QWidget, QColorDialog, QGroupBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import json
import os


# Symbol categories with comprehensive unicode symbols
SYMBOL_CATEGORIES = {
    'Arrows': [
        '→', '←', '↑', '↓', '↔', '↕', '⇒', '⇐', '⇑', '⇓', '⇔', '⇕',
        '➔', '➜', '➡', '⬅', '⬆', '⬇', '⤴', '⤵', '↩', '↪', '↖', '↗',
        '↘', '↙', '⟲', '⟳', '↺', '↻'
    ],
    'Checkmarks & Crosses': [
        '✓', '✔', '✗', '✘', '✕', '☑', '☒', '✖', '✅', '❌', '❎',
        '✗', '✘', '☓', '⊗', '⊘'
    ],
    'Stars': [
        '★', '☆', '✦', '✧', '✩', '✪', '✫', '✬', '✭', '✮', '✯',
        '✰', '⋆', '✵', '✶', '✷', '✸', '✹', '✺', '✻', '✼', '✽'
    ],
    'Bullets': [
        '•', '‣', '◦', '○', '●', '◉', '◎', '⦿', '⦾', '▪', '▫',
        '■', '□', '◘', '◙', '▸', '▹', '►', '▻', '◂', '◃', '◄', '◅'
    ],
    'Boxes': [
        '□', '■', '▢', '▣', '▤', '▥', '▦', '▧', '▨', '▩', '▪', '▫',
        '▬', '▭', '▮', '▯', '☐', '☑', '☒', '◻', '◼', '◽', '◾'
    ],
    'Circles': [
        '○', '●', '◯', '◎', '◉', '⚫', '⚪', '⭕', '🔴', '🔵',
        '⬤', '◐', '◑', '◒', '◓', '◔', '◕'
    ],
    'Geometry/Shapes': [
        '▲', '△', '▼', '▽', '◆', '◇', '■', '□', '◼', '◻', '▪', '▫',
        '▸', '◂', '▴', '▾', '◊', '⬟', '⬠', '⬡', '⬢', '⬣', '⬤',
        '⬥', '⬦', '⬧', '⬨', '⬩', '⬪', '⬫', '⬬', '⬭', '⬮', '⬯'
    ],
    'Currency': [
        '$', '€', '£', '¥', '₩', '₹', '₽', '₺', '₴', '₦', '₣', '₱',
        '₨', '₫', '₡', '₵', '₢', '₰', '¢', '₪'
    ],
    'Math Symbols': [
        '±', '×', '÷', '≈', '≠', '≤', '≥', '∞', '∑', '∏', '√', '∫',
        '∂', '∆', '∇', '∈', '∉', '∋', '∌', '⊂', '⊃', '⊆', '⊇', '∩',
        '∪', '∧', '∨', '¬', '∀', '∃', '∅', '°', '′', '″', '‰', '‱'
    ],
    'Logic/Technical': [
        '→', '⇒', '⇔', '∴', '∵', '°', 'Ω', 'µ', 'λ', 'π', 'σ', 'α',
        'β', 'γ', 'δ', 'ε', 'θ', 'φ', 'ψ', 'ω', '∞', '≈', '≠', '≡'
    ],
    'Punctuation': [
        '—', '–', '•', '…', '§', '¶', '©', '®', '™', '†', '‡', '‰',
        '′', '″', '‴', '※', '‼', '⁇', '⁈', '⁉', '⁎', '⁑'
    ],
    'Miscellaneous': [
        '⚠', '⚡', '✔', '✖', '★', '☀', '☁', '☂', '☃', '♠', '♥', '♣',
        '♦', '♪', '♫', '☎', '✉', '✂', '✏', '✎', '✍', '❤', '❥',
        '☮', '☯', '☢', '☣', '⚛', '⚙', '⚐', '⚑', '⚒'
    ]
}


class SymbolDialog(QDialog):
    """Dialog for selecting and configuring symbols"""

    def __init__(self, parent=None, initial_symbol=None, initial_font_size=24, initial_color='#000000'):
        super().__init__(parent)
        self.setWindowTitle("Add Symbol")
        self.setModal(True)
        self.resize(600, 500)

        self.selected_symbol = initial_symbol or ''
        self.font_size = initial_font_size
        self.color = initial_color

        # Load recent symbols
        self.recent_symbols = self._load_recent_symbols()

        self._init_ui()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()

        # Category selection
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Category:"))

        self.category_combo = QComboBox()

        # Add "All" category first
        self.category_combo.addItem("All")

        # Add Recent category if there are recent symbols
        if self.recent_symbols:
            self.category_combo.addItem("Recent")

        # Add all other categories
        for category in SYMBOL_CATEGORIES.keys():
            self.category_combo.addItem(category)

        self.category_combo.currentTextChanged.connect(self._on_category_changed)
        category_layout.addWidget(self.category_combo)
        category_layout.addStretch()

        layout.addLayout(category_layout)

        # Symbol grid (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(300)

        self.symbol_widget = QWidget()
        self.symbol_grid = QGridLayout(self.symbol_widget)
        self.symbol_grid.setSpacing(5)
        scroll.setWidget(self.symbol_widget)

        layout.addWidget(scroll)

        # Preview and settings
        settings_group = QGroupBox("Symbol Settings")
        settings_layout = QVBoxLayout()

        # Preview
        preview_layout = QHBoxLayout()
        preview_layout.addWidget(QLabel("Preview:"))
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(60, 60)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid #ccc; background: white;")
        preview_layout.addWidget(self.preview_label)
        preview_layout.addStretch()
        settings_layout.addLayout(preview_layout)

        # Font size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Size:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 200)
        self.size_spin.setValue(self.font_size)
        self.size_spin.setSuffix(" pt")
        self.size_spin.valueChanged.connect(self._update_preview)
        size_layout.addWidget(self.size_spin)
        size_layout.addStretch()
        settings_layout.addLayout(size_layout)

        # Color
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(60, 30)
        self.color_btn.setStyleSheet(f"background-color: {self.color};")
        self.color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()
        settings_layout.addLayout(color_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.ok_btn = QPushButton("OK")
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Load initial category
        self._on_category_changed(self.category_combo.currentText())

        # If initial symbol provided, select it
        if self.selected_symbol:
            self._update_preview()

    def _on_category_changed(self, category: str):
        """Handle category change"""
        # Clear existing symbols
        while self.symbol_grid.count():
            item = self.symbol_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get symbols for selected category
        if category == "All":
            # Combine all symbols from all categories (remove duplicates while preserving order)
            symbols = []
            seen = set()
            for cat_symbols in SYMBOL_CATEGORIES.values():
                for s in cat_symbols:
                    if s not in seen:
                        symbols.append(s)
                        seen.add(s)
        elif category == "Recent":
            symbols = self.recent_symbols
        else:
            symbols = SYMBOL_CATEGORIES.get(category, [])

        # Create symbol buttons
        row = 0
        col = 0
        max_cols = 10

        for symbol in symbols:
            btn = QPushButton(symbol)
            btn.setFixedSize(50, 50)
            btn.setFont(QFont('Arial', 20))
            btn.clicked.connect(lambda checked, s=symbol: self._select_symbol(s))

            self.symbol_grid.addWidget(btn, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _select_symbol(self, symbol: str):
        """Select a symbol"""
        self.selected_symbol = symbol
        self._update_preview()
        self.ok_btn.setEnabled(True)

    def _update_preview(self):
        """Update preview"""
        if self.selected_symbol:
            font_size = self.size_spin.value()
            self.preview_label.setText(self.selected_symbol)
            self.preview_label.setFont(QFont('Arial', font_size))
            self.preview_label.setStyleSheet(f"border: 1px solid #ccc; background: white; color: {self.color};")

    def _choose_color(self):
        """Choose symbol color"""
        color = QColorDialog.getColor(QColor(self.color), self, "Choose Symbol Color")
        if color.isValid():
            self.color = color.name()
            self.color_btn.setStyleSheet(f"background-color: {self.color};")
            self._update_preview()

    def _load_recent_symbols(self) -> list:
        """Load recently used symbols from file"""
        try:
            config_dir = os.path.expanduser('~/.pdf_editor')
            recent_file = os.path.join(config_dir, 'recent_symbols.json')

            if os.path.exists(recent_file):
                with open(recent_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('symbols', [])
        except Exception as e:
            print(f"Error loading recent symbols: {e}")

        return []

    def _save_recent_symbol(self, symbol: str):
        """Save symbol to recent list"""
        try:
            # Add to front of list, remove duplicates
            if symbol in self.recent_symbols:
                self.recent_symbols.remove(symbol)
            self.recent_symbols.insert(0, symbol)

            # Keep only last 30
            self.recent_symbols = self.recent_symbols[:30]

            # Save to file
            config_dir = os.path.expanduser('~/.pdf_editor')
            os.makedirs(config_dir, exist_ok=True)

            recent_file = os.path.join(config_dir, 'recent_symbols.json')
            with open(recent_file, 'w', encoding='utf-8') as f:
                json.dump({'symbols': self.recent_symbols}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving recent symbol: {e}")

    def accept(self):
        """Accept and save recent symbol"""
        if self.selected_symbol:
            self._save_recent_symbol(self.selected_symbol)
        super().accept()

    def get_values(self) -> dict:
        """Get selected values"""
        return {
            'symbol': self.selected_symbol,
            'font_size': self.size_spin.value(),
            'color': self.color
        }
