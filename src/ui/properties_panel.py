"""
Properties Panel
Shows tool settings and layer properties
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QColorDialog,
                              QSlider, QSpinBox, QHBoxLayout, QGroupBox,
                              QListWidget, QListWidgetItem, QCheckBox, QLineEdit,
                              QStyledItemDelegate, QStyleOptionViewItem, QApplication,
                              QSizePolicy, QFrame, QMenu, QMessageBox, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QSize, QSettings
from PyQt6.QtGui import QColor, QPalette, QCursor, QPixmap, QIcon
from core import LayerManager, Layer
from utils.icon_helper import get_icon
from typing import Optional, List
import copy


class LayerItemDelegate(QStyledItemDelegate):
    """Custom delegate to handle layer name editing"""

    def createEditor(self, parent, option, index):
        """Create editor widget"""
        editor = QLineEdit(parent)
        editor.setFrame(True)
        return editor

    def setEditorData(self, editor, index):
        """Set data in editor"""
        value = index.data(Qt.ItemDataRole.DisplayRole)
        editor.setText(value)

    def setModelData(self, editor, model, index):
        """Save data from editor"""
        model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)


class ColorButton(QPushButton):
    """Button that shows and selects colors"""

    color_changed = pyqtSignal(str)

    def __init__(self, initial_color: str = "#000000"):
        super().__init__()
        self.current_color = initial_color
        self.setFixedSize(60, 30)
        self.update_color(initial_color)
        self.clicked.connect(self.pick_color)

    def update_color(self, color: str):
        """Update button color"""
        self.current_color = color
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 2px solid #333;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border: 2px solid #0078d4;
            }}
        """)

    def pick_color(self):
        """Show color picker"""
        color = QColorDialog.getColor(QColor(self.current_color), self)
        if color.isValid():
            self.update_color(color.name())
            self.color_changed.emit(color.name())


class ColorSwatch(QPushButton):
    """Small color swatch button"""

    color_selected = pyqtSignal(str)

    def __init__(self, color: str = "#FFFFFF", size: int = 20):
        super().__init__()
        self.color = color
        self.setFixedSize(size, size)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.update_color(color)
        self.clicked.connect(self._on_clicked)

    def update_color(self, color: str):
        """Update swatch color"""
        self.color = color
        # Determine border color based on brightness
        qcolor = QColor(color)
        brightness = (qcolor.red() * 299 + qcolor.green() * 587 + qcolor.blue() * 114) / 1000
        border_color = "#555" if brightness > 128 else "#888"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 1px solid {border_color};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                border: 2px solid #00c000;
            }}
        """)

    def _on_clicked(self):
        """Emit color selected signal"""
        self.color_selected.emit(self.color)


class ColorSwatchPanel(QWidget):
    """Panel with recent colors and color picker"""

    color_selected = pyqtSignal(str)
    picker_activated = pyqtSignal()
    picker_deactivated = pyqtSignal()

    MAX_RECENT_COLORS = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recent_colors: List[str] = ["#FFFFFF", "#000000"]  # Default: white and black
        self.picker_active = False

        self.setup_ui()

    def setup_ui(self):
        """Setup the color swatch panel UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(3)

        # Container for color swatches
        self.swatch_container = QWidget()
        swatch_layout = QHBoxLayout(self.swatch_container)
        swatch_layout.setContentsMargins(0, 0, 0, 0)
        swatch_layout.setSpacing(3)

        # Create swatch buttons
        self.swatches: List[ColorSwatch] = []
        for i in range(self.MAX_RECENT_COLORS):
            color = self.recent_colors[i] if i < len(self.recent_colors) else "#CCCCCC"
            swatch = ColorSwatch(color, size=18)
            swatch.color_selected.connect(self._on_swatch_selected)
            self.swatches.append(swatch)
            swatch_layout.addWidget(swatch)

            # Hide swatches beyond initial colors
            if i >= len(self.recent_colors):
                swatch.hide()

        swatch_layout.addStretch()
        layout.addWidget(self.swatch_container)

        # Color picker button
        self.picker_button = QPushButton()
        self.picker_button.setFixedSize(22, 22)
        self.picker_button.setIcon(get_icon("colorpicker"))
        self.picker_button.setIconSize(QSize(16, 16))
        self.picker_button.setToolTip("Pick color from screen")
        self.picker_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._update_picker_button_style()
        self.picker_button.clicked.connect(self._on_picker_clicked)
        layout.addWidget(self.picker_button)

    def _update_picker_button_style(self):
        """Update picker button style based on active state"""
        if self.picker_active:
            self.picker_button.setIcon(get_icon("colorpicker", color="#00c000"))
            self.picker_button.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 192, 0, 0.1);
                    border: 1px solid #00c000;
                    border-radius: 3px;
                }
            """)
        else:
            self.picker_button.setIcon(get_icon("colorpicker"))
            self.picker_button.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #555;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    border: 1px solid #00c000;
                    background-color: rgba(0, 192, 0, 0.1);
                }
            """)

    def _on_picker_clicked(self):
        """Handle picker button click"""
        if self.picker_active:
            self.deactivate_picker()
        else:
            self.activate_picker()

    def activate_picker(self):
        """Activate color picker mode"""
        self.picker_active = True
        self._update_picker_button_style()
        self.picker_activated.emit()

        # Show color dialog
        color = QColorDialog.getColor(QColor("#000000"), self, "Pick Color")
        if color.isValid():
            self.add_recent_color(color.name())
            self.color_selected.emit(color.name())

        # Deactivate after picking
        self.deactivate_picker()

    def deactivate_picker(self):
        """Deactivate color picker mode"""
        self.picker_active = False
        self._update_picker_button_style()
        self.picker_deactivated.emit()

    def _on_swatch_selected(self, color: str):
        """Handle swatch selection"""
        self.color_selected.emit(color)

    def add_recent_color(self, color: str):
        """Add a color to recent colors"""
        color = color.upper()

        # Don't add if it's already the first color
        if self.recent_colors and self.recent_colors[0].upper() == color:
            return

        # Remove if already exists
        self.recent_colors = [c for c in self.recent_colors if c.upper() != color]

        # Add to front
        self.recent_colors.insert(0, color)

        # Keep only MAX_RECENT_COLORS
        self.recent_colors = self.recent_colors[:self.MAX_RECENT_COLORS]

        # Update swatches
        self._update_swatches()

    def _update_swatches(self):
        """Update swatch buttons with current colors"""
        for i, swatch in enumerate(self.swatches):
            if i < len(self.recent_colors):
                swatch.update_color(self.recent_colors[i])
                swatch.show()
            else:
                swatch.hide()


class PropertiesPanel(QWidget):
    """Panel for tool and layer properties"""

    color_changed = pyqtSignal(str)
    width_changed = pyqtSignal(int)
    opacity_changed = pyqtSignal(float)
    fill_color_changed = pyqtSignal(str)
    layer_visibility_changed = pyqtSignal(str, bool)
    layer_deleted = pyqtSignal(str)
    layer_copied = pyqtSignal(object)  # Emits copied layer
    layer_edit_requested = pyqtSignal(object)  # Emits layer to be edited
    layer_renamed = pyqtSignal(str, str)  # layer_id, new_name
    highlight_color_changed = pyqtSignal(str)  # For text selection tool
    text_annotation_requested = pyqtSignal(str, str)  # annotation_type, color

    def __init__(self, layer_manager: LayerManager):
        super().__init__()
        self.layer_manager = layer_manager
        self.current_page = 0
        self._editing_layer_name = False  # Track if we're editing a layer name
        self._skip_delete_confirmation = False  # Track if user wants to skip delete confirmation (session only)
        self._settings = QSettings("PDFEditor", "PDFEditor")
        # Reset delete confirmation preference at start of each session
        self._settings.setValue("skip_delete_confirmation", False)

        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Tool properties group
        tool_group = QGroupBox("Tool Settings")
        tool_layout = QVBoxLayout()

        # Color swatch panel (recent colors + picker)
        self.color_swatch_panel = ColorSwatchPanel()
        self.color_swatch_panel.color_selected.connect(self._on_swatch_color_selected)
        tool_layout.addWidget(self.color_swatch_panel)

        # Color and Fill row
        color_fill_layout = QHBoxLayout()
        color_fill_layout.setSpacing(6)

        # Color
        color_fill_layout.addWidget(QLabel("Color:"))
        self.color_button = ColorButton("#000000")
        self.color_button.setFixedSize(32, 22)
        self.color_button.color_changed.connect(self._on_color_button_changed)
        color_fill_layout.addWidget(self.color_button)

        # Fill
        color_fill_layout.addWidget(QLabel("Fill:"))
        self.fill_color_button = ColorButton("#FFFFFF")
        self.fill_color_button.setFixedSize(32, 22)
        self.fill_color_button.color_changed.connect(self._on_fill_color_changed)
        color_fill_layout.addWidget(self.fill_color_button)
        self.no_fill_checkbox = QCheckBox("None")
        self.no_fill_checkbox.stateChanged.connect(self._on_no_fill_changed)
        color_fill_layout.addWidget(self.no_fill_checkbox)

        color_fill_layout.addStretch()
        tool_layout.addLayout(color_fill_layout)

        # Width and Opacity row
        width_opacity_layout = QHBoxLayout()
        width_opacity_layout.setSpacing(6)

        # Width
        width_opacity_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setMinimum(1)
        self.width_spin.setMaximum(50)
        self.width_spin.setValue(2)
        self.width_spin.setFixedWidth(45)
        self.width_spin.valueChanged.connect(self.width_changed.emit)
        width_opacity_layout.addWidget(self.width_spin)

        # Opacity
        width_opacity_layout.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(60)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        width_opacity_layout.addWidget(self.opacity_slider)
        self.opacity_label = QLabel("100%")
        self.opacity_label.setFixedWidth(32)
        width_opacity_layout.addWidget(self.opacity_label)

        width_opacity_layout.addStretch()
        tool_layout.addLayout(width_opacity_layout)

        # Text annotation section (hidden by default, shown when Select Text tool is selected)
        self.text_annotation_row = QWidget()
        annotation_layout = QVBoxLayout(self.text_annotation_row)
        annotation_layout.setContentsMargins(0, 5, 0, 5)
        annotation_layout.setSpacing(8)

        # Highlight color picker
        highlight_layout = QHBoxLayout()
        highlight_layout.addWidget(QLabel("Highlight:"))
        self.highlight_color_button = ColorButton("#FFFF00")  # Yellow default
        self.highlight_color_button.color_changed.connect(self.highlight_color_changed.emit)
        highlight_layout.addWidget(self.highlight_color_button)
        highlight_layout.addStretch()
        annotation_layout.addLayout(highlight_layout)

        # Apply buttons row
        apply_layout = QHBoxLayout()
        ann_label = QLabel("Apply:")
        ann_label.setStyleSheet("font-size: 11px; color: #666;")
        apply_layout.addWidget(ann_label)

        # Highlight button
        self.highlight_btn = QPushButton()
        self.highlight_btn.setFixedSize(22, 22)
        self.highlight_btn.setIcon(get_icon("text-highlight"))
        self.highlight_btn.setIconSize(QSize(16, 16))
        self.highlight_btn.setToolTip("Apply Highlight")
        self.highlight_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.highlight_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                border: 1px solid #00c000;
                background-color: rgba(0, 192, 0, 0.1);
            }
        """)
        self.highlight_btn.clicked.connect(self._on_highlight_clicked)
        apply_layout.addWidget(self.highlight_btn)

        # Underline button
        self.underline_btn = QPushButton()
        self.underline_btn.setFixedSize(22, 22)
        self.underline_btn.setIcon(get_icon("text-underline"))
        self.underline_btn.setIconSize(QSize(16, 16))
        self.underline_btn.setToolTip("Apply Underline")
        self.underline_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.underline_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                border: 1px solid #00c000;
                background-color: rgba(0, 192, 0, 0.1);
            }
        """)
        self.underline_btn.clicked.connect(self._on_underline_clicked)
        apply_layout.addWidget(self.underline_btn)

        # Strikethrough button
        self.strikethrough_btn = QPushButton()
        self.strikethrough_btn.setFixedSize(22, 22)
        self.strikethrough_btn.setIcon(get_icon("text-strikethrough"))
        self.strikethrough_btn.setIconSize(QSize(16, 16))
        self.strikethrough_btn.setToolTip("Apply Strikethrough")
        self.strikethrough_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.strikethrough_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                border: 1px solid #00c000;
                background-color: rgba(0, 192, 0, 0.1);
            }
        """)
        self.strikethrough_btn.clicked.connect(self._on_strikethrough_clicked)
        apply_layout.addWidget(self.strikethrough_btn)

        apply_layout.addStretch()
        annotation_layout.addLayout(apply_layout)
        tool_layout.addWidget(self.text_annotation_row)
        self.text_annotation_row.hide()  # Hidden by default

        tool_group.setLayout(tool_layout)
        layout.addWidget(tool_group)

        # Layers group
        layers_group = QGroupBox("Layers")
        layers_layout = QVBoxLayout()

        self.layers_list = QListWidget()
        self.layers_list.setMaximumHeight(300)
        self.layers_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)  # Enable multi-selection
        self.layers_list.setItemDelegate(LayerItemDelegate())  # Custom delegate for editing
        self.layers_list.itemChanged.connect(self._on_layer_item_changed)
        self.layers_list.itemDoubleClicked.connect(self._on_layer_double_clicked)
        self.layers_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.layers_list.customContextMenuRequested.connect(self._show_layer_context_menu)
        layers_layout.addWidget(self.layers_list)

        # Layer buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        # Copy button
        copy_btn = QPushButton()
        copy_btn.setFixedSize(22, 22)
        copy_btn.setIcon(get_icon("copy"))
        copy_btn.setIconSize(QSize(16, 16))
        copy_btn.setToolTip("Copy selected layer(s)")
        copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        copy_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                border: 1px solid #00c000;
                background-color: rgba(0, 192, 0, 0.1);
            }
        """)
        copy_btn.clicked.connect(self._copy_selected_layers)
        buttons_layout.addWidget(copy_btn)

        # Delete button
        delete_btn = QPushButton()
        delete_btn.setFixedSize(22, 22)
        delete_btn.setIcon(get_icon("delete"))
        delete_btn.setIconSize(QSize(16, 16))
        delete_btn.setToolTip("Delete selected layer(s)")
        delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QPushButton:hover {
                border: 1px solid #ff4444;
                background-color: rgba(255, 68, 68, 0.1);
            }
        """)
        delete_btn.clicked.connect(self._delete_selected_layer)
        buttons_layout.addWidget(delete_btn)

        layers_layout.addLayout(buttons_layout)
        layers_group.setLayout(layers_layout)
        layout.addWidget(layers_group)

        layout.addStretch()
        self.setLayout(layout)

        self.setMinimumWidth(250)
        self.setMaximumWidth(400)

    def _on_opacity_changed(self, value: int):
        """Handle opacity slider change"""
        opacity = value / 100.0
        self.opacity_label.setText(f"{value}%")
        self.opacity_changed.emit(opacity)

    def _on_no_fill_changed(self, state):
        """Handle no fill checkbox"""
        if state == Qt.CheckState.Checked.value:
            self.fill_color_button.setEnabled(False)
            self.fill_color_changed.emit("")
        else:
            self.fill_color_button.setEnabled(True)
            self.fill_color_changed.emit(self.fill_color_button.current_color)

    def set_color(self, color: str):
        """Set color"""
        self.color_button.update_color(color)

    def set_width(self, width: int):
        """Set width"""
        self.width_spin.setValue(width)

    def set_opacity(self, opacity: float):
        """Set opacity"""
        self.opacity_slider.setValue(int(opacity * 100))

    def refresh_layers(self):
        """Refresh layer list"""
        self.layers_list.clear()
        if not self.layer_manager:
            return
        layers = self.layer_manager.get_layers_for_page(self.current_page)

        for layer in reversed(layers):  # Top to bottom
            item = QListWidgetItem(layer.name)
            # Enable checkable and editable
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            item.setCheckState(Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, layer.id)
            self.layers_list.addItem(item)

    def set_current_page(self, page_num: int):
        """Set current page"""
        self.current_page = page_num
        self.refresh_layers()

    def _on_layer_item_changed(self, item: QListWidgetItem):
        """Handle layer visibility change or name edit"""
        layer_id = item.data(Qt.ItemDataRole.UserRole)
        layer = self.layer_manager.get_layer(layer_id) if self.layer_manager else None
        if not layer:
            return

        # Check if visibility changed
        visible = item.checkState() == Qt.CheckState.Checked
        if layer.visible != visible:
            layer.visible = visible
            self.layer_visibility_changed.emit(layer_id, visible)

        # Check if name changed
        new_name = item.text()
        if layer.name != new_name and new_name.strip():
            layer.name = new_name
            self.layer_renamed.emit(layer_id, new_name)

    def _on_layer_double_clicked(self, item: QListWidgetItem):
        """Handle layer double-click - start editing the layer name"""
        # Start editing the item name
        self.layers_list.editItem(item)

    def _delete_selected_layer(self):
        """Delete selected layer(s) with confirmation dialog"""
        selected_items = self.layers_list.selectedItems()
        if not selected_items:
            return

        # Check if we should skip confirmation
        skip_confirmation = self._settings.value("skip_delete_confirmation", False, type=bool)

        if not skip_confirmation:
            # Show confirmation dialog
            if not self._show_delete_confirmation(len(selected_items)):
                return

        # Delete the layers
        for item in selected_items:
            layer_id = item.data(Qt.ItemDataRole.UserRole)
            self.layer_deleted.emit(layer_id)
        self.refresh_layers()

    def _show_delete_confirmation(self, count: int) -> bool:
        """Show delete confirmation dialog. Returns True if user confirms."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirm Delete")
        msg_box.setText(f"Are you sure you want to delete {count} layer(s)?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        # Add "Do not ask again" checkbox
        checkbox = QCheckBox("Do not ask again")
        msg_box.setCheckBox(checkbox)

        result = msg_box.exec()

        # Save preference if checkbox is checked
        if checkbox.isChecked():
            self._settings.setValue("skip_delete_confirmation", True)

        return result == QMessageBox.StandardButton.Yes

    def _copy_selected_layers(self):
        """Copy selected layer(s)"""
        selected_items = self.layers_list.selectedItems()
        if not selected_items or not self.layer_manager:
            return

        for item in selected_items:
            layer_id = item.data(Qt.ItemDataRole.UserRole)
            original_layer = self.layer_manager.get_layer(layer_id)
            if original_layer:
                # Create a copy of the layer
                copied_layer = self._create_layer_copy(original_layer)
                if copied_layer:
                    self.layer_copied.emit(copied_layer)

        self.refresh_layers()

    def _create_layer_copy(self, original: Layer) -> Optional[Layer]:
        """Create a copy of a layer with '(copy)' appended to the name"""
        from core.layer import LayerType
        from core.interactive_layer import TextFieldLayer, ImageLayer, SymbolLayer, InteractiveLayer
        import uuid

        copied = None

        # Create the appropriate subclass based on original type
        if isinstance(original, TextFieldLayer):
            # Copy TextFieldLayer
            copied = TextFieldLayer(
                page_num=original.page_num,
                x=original.data.get('x', 0) + 20,  # Offset so it's visible
                y=original.data.get('y', 0) + 20,
                text=original.data.get('text', ''),
                width=original.data.get('width', 150),
                height=original.data.get('height', 40)
            )
            # Copy all data properties
            for key, value in original.data.items():
                if key not in ['x', 'y']:  # Already set with offset
                    copied.data[key] = copy.deepcopy(value)
            copied.data['x'] = original.data.get('x', 0) + 20
            copied.data['y'] = original.data.get('y', 0) + 20

        elif isinstance(original, ImageLayer):
            # Copy ImageLayer
            pixmap = original.data.get('pixmap')
            if pixmap:
                pixmap = pixmap.copy()  # Create a copy of the pixmap
            copied = ImageLayer(
                page_num=original.page_num,
                x=original.data.get('x', 0) + 20,
                y=original.data.get('y', 0) + 20,
                pixmap=pixmap,
                width=original.data.get('width'),
                height=original.data.get('height'),
                image_path=original.data.get('image_path')
            )
            # Copy additional data properties
            for key, value in original.data.items():
                if key not in ['x', 'y', 'pixmap', 'width', 'height', 'image_path']:
                    copied.data[key] = copy.deepcopy(value)
            copied.data['x'] = original.data.get('x', 0) + 20
            copied.data['y'] = original.data.get('y', 0) + 20

        elif isinstance(original, SymbolLayer):
            # Copy SymbolLayer
            copied = SymbolLayer(
                page_num=original.page_num,
                x=original.data.get('x', 0) + 20,
                y=original.data.get('y', 0) + 20,
                symbol=original.data.get('symbol', ''),
                font_size=original.data.get('font_size', 24)
            )
            # Copy additional data properties
            for key, value in original.data.items():
                if key not in ['x', 'y', 'symbol', 'font_size']:
                    copied.data[key] = copy.deepcopy(value)
            copied.data['x'] = original.data.get('x', 0) + 20
            copied.data['y'] = original.data.get('y', 0) + 20

        else:
            # Generic Layer copy for basic layers (drawings, shapes, annotations)
            copied = Layer(original.type, original.page_num, f"{original.name} (copy)")
            copied.data = copy.deepcopy(original.data)

        if copied:
            copied.id = str(uuid.uuid4())  # New unique ID
            copied.visible = original.visible
            copied.locked = original.locked
            copied.opacity = original.opacity

            # Copy rotation if it's an interactive layer
            if isinstance(original, InteractiveLayer) and isinstance(copied, InteractiveLayer):
                copied.rotation = original.rotation

        return copied

    def get_highlight_color(self) -> str:
        """Get current highlight color"""
        return self.highlight_color_button.current_color

    def _on_swatch_color_selected(self, color: str):
        """Handle color selection from swatch panel"""
        self.color_button.update_color(color)
        self.color_changed.emit(color)

    def _on_color_button_changed(self, color: str):
        """Handle color button change - add to recent colors"""
        self.color_swatch_panel.add_recent_color(color)
        self.color_changed.emit(color)

    def _on_fill_color_changed(self, color: str):
        """Handle fill color change - add to recent colors"""
        self.color_swatch_panel.add_recent_color(color)
        self.fill_color_changed.emit(color)

    def add_recent_color(self, color: str, update_current: bool = True):
        """Add a color to recent colors (public method for external use)

        Args:
            color: The color to add (hex format like '#FF0000')
            update_current: If True, also update the current color button
        """
        self.color_swatch_panel.add_recent_color(color)
        if update_current:
            self.color_button.update_color(color)

    def set_text_selection_active(self, has_selection: bool):
        """Show or hide text annotation buttons based on selection state"""
        if has_selection:
            self.text_annotation_row.show()
        else:
            self.text_annotation_row.hide()

    def _on_highlight_clicked(self):
        """Apply highlight to selected text"""
        color = self.highlight_color_button.current_color
        self.text_annotation_requested.emit("highlight", color)

    def _on_underline_clicked(self):
        """Apply underline to selected text"""
        color = self.color_button.current_color
        self.text_annotation_requested.emit("underline", color)

    def _on_strikethrough_clicked(self):
        """Apply strikethrough to selected text"""
        color = self.color_button.current_color
        self.text_annotation_requested.emit("strikethrough", color)

    def _show_layer_context_menu(self, position):
        """Show context menu for layer right-click"""
        item = self.layers_list.itemAt(position)
        if not item:
            return

        layer_id = item.data(Qt.ItemDataRole.UserRole)
        layer = self.layer_manager.get_layer(layer_id) if self.layer_manager else None
        if not layer:
            return

        menu = QMenu(self)

        # Edit action
        edit_action = menu.addAction("Edit Layer")
        edit_action.triggered.connect(lambda: self._on_edit_layer(layer))

        # Rename action
        rename_action = menu.addAction("Rename Layer")
        rename_action.triggered.connect(lambda: self.layers_list.editItem(item))

        # Copy action
        copy_action = menu.addAction("Copy Layer")
        copy_action.triggered.connect(lambda: self._on_copy_layer(layer))

        menu.addSeparator()

        # Delete action
        delete_action = menu.addAction("Delete Layer")
        delete_action.triggered.connect(lambda: self._on_delete_layer(layer_id))

        menu.exec(self.layers_list.mapToGlobal(position))

    def _on_edit_layer(self, layer):
        """Handle edit layer from context menu"""
        self.layer_edit_requested.emit(layer)

    def _on_copy_layer(self, layer):
        """Handle copy layer from context menu"""
        copied_layer = self._create_layer_copy(layer)
        if copied_layer:
            self.layer_copied.emit(copied_layer)
            self.refresh_layers()

    def _on_delete_layer(self, layer_id: str):
        """Handle delete layer from context menu"""
        # Check if we should skip confirmation
        skip_confirmation = self._settings.value("skip_delete_confirmation", False, type=bool)

        if not skip_confirmation:
            if not self._show_delete_confirmation(1):
                return

        self.layer_deleted.emit(layer_id)
        self.refresh_layers()
