"""
Merge PDF Dialog
Panel-based dialog for selecting, previewing, reordering, and merging multiple PDF files and images
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QFileDialog, QMessageBox, QWidget,
                              QScrollArea, QFrame, QGridLayout, QSizePolicy,
                              QGraphicsDropShadowEffect, QApplication)
from PyQt6.QtCore import Qt, QSize, QMimeData, QPoint, pyqtSignal
from PyQt6.QtGui import QPixmap, QDrag, QColor, QPainter, QPen, QFont, QIcon, QPalette
from utils.icon_helper import get_icon, is_dark_theme
import fitz  # PyMuPDF
import os


# Supported file extensions
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', '.webp'}
PDF_EXTENSIONS = {'.pdf'}


def is_image_file(file_path: str) -> bool:
    """Check if file is an image"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in IMAGE_EXTENSIONS


def is_pdf_file(file_path: str) -> bool:
    """Check if file is a PDF"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in PDF_EXTENSIONS


class PDFThumbnailCard(QFrame):
    """Individual PDF/Image thumbnail card with selection and drag support"""

    clicked = pyqtSignal(object)  # Emits self when clicked

    def __init__(self, file_path: str, thumbnail: QPixmap = None, is_image: bool = False, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.thumbnail = thumbnail
        self.is_image = is_image  # True if this is an image file, False if PDF
        self._selected = False
        self._drag_start_pos = None

        self.setFixedSize(130, 170)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptDrops(True)

        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        """Setup the card UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail image
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(115, 135)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_thumb_style()

        if self.thumbnail and not self.thumbnail.isNull():
            scaled = self.thumbnail.scaled(
                111, 131,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
        else:
            self.thumb_label.setText("IMG" if self.is_image else "PDF")

        layout.addWidget(self.thumb_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Filename label
        self.name_label = QLabel(self._truncate_name(self.file_name, 16))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setToolTip(self.file_path)
        self._update_name_style()
        layout.addWidget(self.name_label)

    def _truncate_name(self, name: str, max_len: int) -> str:
        """Truncate filename if too long"""
        if len(name) <= max_len:
            return name
        return name[:max_len-3] + "..."

    def _update_thumb_style(self):
        """Update thumbnail label style based on theme"""
        if is_dark_theme():
            self.thumb_label.setStyleSheet("""
                QLabel {
                    background-color: #3c3c3c;
                    border: 1px solid #555;
                    border-radius: 3px;
                }
            """)
        else:
            self.thumb_label.setStyleSheet("""
                QLabel {
                    background-color: #ffffff;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                }
            """)

    def _update_name_style(self):
        """Update name label style based on theme"""
        if is_dark_theme():
            self.name_label.setStyleSheet("font-size: 10px; color: #ccc;")
        else:
            self.name_label.setStyleSheet("font-size: 10px; color: #333;")

    def _apply_style(self):
        """Apply styling based on selection state and theme"""
        dark = is_dark_theme()

        if self._selected:
            if dark:
                self.setStyleSheet("""
                    PDFThumbnailCard {
                        background-color: #2d4a5e;
                        border: 2px solid #0078d4;
                        border-radius: 6px;
                    }
                """)
            else:
                self.setStyleSheet("""
                    PDFThumbnailCard {
                        background-color: #e3f2fd;
                        border: 2px solid #0078d4;
                        border-radius: 6px;
                    }
                """)
        else:
            if dark:
                self.setStyleSheet("""
                    PDFThumbnailCard {
                        background-color: #2d2d2d;
                        border: 1px solid #444;
                        border-radius: 6px;
                    }
                    PDFThumbnailCard:hover {
                        background-color: #3a3a3a;
                        border: 1px solid #666;
                    }
                """)
            else:
                self.setStyleSheet("""
                    PDFThumbnailCard {
                        background-color: #ffffff;
                        border: 1px solid #ddd;
                        border-radius: 6px;
                    }
                    PDFThumbnailCard:hover {
                        background-color: #f5f5f5;
                        border: 1px solid #bbb;
                    }
                """)

    @property
    def selected(self):
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self.clicked.emit(self)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_start_pos:
            distance = (event.pos() - self._drag_start_pos).manhattanLength()
            if distance >= 10:  # Start drag threshold
                self._start_drag()
        super().mouseMoveEvent(event)

    def _start_drag(self):
        """Initiate drag operation"""
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.file_path)
        drag.setMimeData(mime_data)

        # Create drag pixmap
        if self.thumbnail and not self.thumbnail.isNull():
            drag_pixmap = self.thumbnail.scaled(
                80, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            drag.setPixmap(drag_pixmap)
            drag.setHotSpot(QPoint(drag_pixmap.width() // 2, drag_pixmap.height() // 2))

        drag.exec(Qt.DropAction.MoveAction)


class ThumbnailGridPanel(QScrollArea):
    """Scrollable grid panel for PDF thumbnails with drag-drop reordering"""

    selection_changed = pyqtSignal()
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = []  # List of PDFThumbnailCard
        self._drop_indicator_index = -1

        self._setup_ui()

    def _setup_ui(self):
        """Setup the panel UI"""
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setAcceptDrops(True)

        # Container widget
        self.container = QWidget()
        self.container.setAcceptDrops(True)
        self.setWidget(self.container)

        # Grid layout
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setContentsMargins(12, 12, 12, 12)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Placeholder label
        self.placeholder = QLabel("Drop files here or click 'Add Files' to get started")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_placeholder_style()
        self.grid_layout.addWidget(self.placeholder, 0, 0, 1, 4)

        self._apply_panel_style()
        self.container.setObjectName("container")

    def _update_placeholder_style(self):
        """Update placeholder style based on theme"""
        if is_dark_theme():
            self.placeholder.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-size: 13px;
                    padding: 50px;
                }
            """)
        else:
            self.placeholder.setStyleSheet("""
                QLabel {
                    color: #999;
                    font-size: 13px;
                    padding: 50px;
                }
            """)

    def _apply_panel_style(self):
        """Apply panel styling based on theme"""
        if is_dark_theme():
            self.setStyleSheet("""
                ThumbnailGridPanel {
                    background-color: #252525;
                    border: 2px dashed #444;
                    border-radius: 8px;
                }
                QWidget#container {
                    background-color: transparent;
                }
            """)
        else:
            self.setStyleSheet("""
                ThumbnailGridPanel {
                    background-color: #f8f8f8;
                    border: 2px dashed #ccc;
                    border-radius: 8px;
                }
                QWidget#container {
                    background-color: transparent;
                }
            """)

    def add_card(self, card: PDFThumbnailCard):
        """Add a thumbnail card to the grid"""
        if self.placeholder.isVisible():
            self.placeholder.hide()

        card.clicked.connect(self._on_card_clicked)
        self.cards.append(card)
        self._refresh_grid()

    def remove_selected(self):
        """Remove all selected cards"""
        to_remove = [card for card in self.cards if card.selected]
        for card in to_remove:
            self.cards.remove(card)
            card.deleteLater()
        self._refresh_grid()
        self.selection_changed.emit()

    def clear_all(self):
        """Remove all cards"""
        for card in self.cards:
            card.deleteLater()
        self.cards.clear()
        self._refresh_grid()
        self.selection_changed.emit()

    def get_selected_cards(self):
        """Get list of selected cards"""
        return [card for card in self.cards if card.selected]

    def get_ordered_file_paths(self):
        """Get file paths in current order"""
        return [card.file_path for card in self.cards]

    def _on_card_clicked(self, card: PDFThumbnailCard):
        """Handle card click - toggle selection"""
        modifiers = QApplication.keyboardModifiers()

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+click: toggle this card's selection
            card.selected = not card.selected
        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            # Shift+click: range selection (simplified - just select this one)
            card.selected = True
        else:
            # Regular click: select only this card
            for c in self.cards:
                c.selected = (c == card)

        self.selection_changed.emit()

    def _refresh_grid(self):
        """Refresh the grid layout with current cards"""
        # Remove all items from grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget() and item.widget() != self.placeholder:
                # Don't delete the widget, just remove from layout
                pass

        # Calculate columns based on width
        cols = max(1, (self.width() - 30) // 145)

        if not self.cards:
            self.placeholder.show()
            self.grid_layout.addWidget(self.placeholder, 0, 0, 1, 4)
        else:
            self.placeholder.hide()
            for i, card in enumerate(self.cards):
                row = i // cols
                col = i % cols
                self.grid_layout.addWidget(card, row, col)

    def resizeEvent(self, event):
        """Handle resize to reflow grid"""
        super().resizeEvent(event)
        self._refresh_grid()

    def dragEnterEvent(self, event):
        """Handle drag enter"""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """Handle drag move - show drop indicator"""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle drop - reorder cards"""
        if event.mimeData().hasText():
            source_path = event.mimeData().text()

            # Find source card
            source_card = None
            source_index = -1
            for i, card in enumerate(self.cards):
                if card.file_path == source_path:
                    source_card = card
                    source_index = i
                    break

            if source_card is None:
                return

            # Find target index based on drop position
            drop_pos = event.position().toPoint()
            target_index = self._get_drop_index(drop_pos)

            if target_index != source_index and target_index >= 0:
                # Reorder
                self.cards.pop(source_index)
                if target_index > source_index:
                    target_index -= 1
                self.cards.insert(target_index, source_card)
                self._refresh_grid()
                self.order_changed.emit()

            event.acceptProposedAction()

    def _get_drop_index(self, pos: QPoint) -> int:
        """Calculate drop index from position"""
        if not self.cards:
            return 0

        cols = max(1, (self.width() - 30) // 145)

        # Calculate which cell the drop is in
        x = pos.x() - 12  # Adjust for margins
        y = pos.y() - 12

        col = max(0, min(cols - 1, x // 145))
        row = max(0, y // 185)

        index = row * cols + col
        return min(index, len(self.cards))


class MergePDFDialog(QDialog):
    """Panel-based dialog for merging multiple PDF files and images"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Merge Files to PDF")
        self.setModal(True)
        self.resize(650, 520)
        self.setMinimumSize(500, 400)

        self.thumbnails = {}  # Cache thumbnails: path -> QPixmap
        self.file_types = {}  # Cache file types: path -> 'pdf' or 'image'

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header = QLabel("Merge Files to PDF")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding-bottom: 2px;")
        layout.addWidget(header)

        # Subtitle
        subtitle = QLabel("Add PDFs and images, drag to reorder, then merge into a single PDF.")
        self._apply_subtitle_style(subtitle)
        layout.addWidget(subtitle)

        # Action buttons row
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        # Add Files button
        self.add_btn = QPushButton("Add Files")
        self.add_btn.setIcon(get_icon("plus"))
        self._apply_button_style(self.add_btn, "primary")
        button_row.addWidget(self.add_btn)

        # Remove button
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setIcon(get_icon("trash"))
        self.remove_btn.setEnabled(False)
        self._apply_button_style(self.remove_btn, "danger")
        button_row.addWidget(self.remove_btn)

        # Clear All button
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setEnabled(False)
        self._apply_button_style(self.clear_btn, "secondary")
        button_row.addWidget(self.clear_btn)

        button_row.addStretch()
        layout.addLayout(button_row)

        # Thumbnail grid panel
        self.grid_panel = ThumbnailGridPanel()
        self.grid_panel.setMinimumHeight(260)
        layout.addWidget(self.grid_panel, 1)

        # Status bar
        self.status_label = QLabel("No files added")
        self._apply_status_style()
        layout.addWidget(self.status_label)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        self._apply_button_style(cancel_btn, "secondary")
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)

        self.merge_btn = QPushButton("Merge to PDF")
        self.merge_btn.setEnabled(False)
        self._apply_button_style(self.merge_btn, "action")
        bottom_row.addWidget(self.merge_btn)

        layout.addLayout(bottom_row)

    def _apply_subtitle_style(self, label: QLabel):
        """Apply subtitle style based on theme"""
        if is_dark_theme():
            label.setStyleSheet("color: #999; margin-bottom: 8px;")
        else:
            label.setStyleSheet("color: #666; margin-bottom: 8px;")

    def _apply_status_style(self):
        """Apply status label style"""
        if is_dark_theme():
            self.status_label.setStyleSheet("color: #888; font-size: 11px; padding: 4px 0;")
        else:
            self.status_label.setStyleSheet("color: #888; font-size: 11px; padding: 4px 0;")

    def _apply_button_style(self, btn: QPushButton, style_type: str):
        """Apply consistent button styling matching the application theme"""
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(32)

        dark = is_dark_theme()

        if style_type == "primary":
            # Green action button (like OK/Confirm)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
                QPushButton:pressed {
                    background-color: #1e7e34;
                }
                QPushButton:disabled {
                    background-color: #555;
                    color: #888;
                }
            """)
        elif style_type == "danger":
            # Red danger button
            if dark:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 6px 16px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background-color: #c82333;
                    }
                    QPushButton:pressed {
                        background-color: #bd2130;
                    }
                    QPushButton:disabled {
                        background-color: #444;
                        color: #666;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 6px 16px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background-color: #c82333;
                    }
                    QPushButton:pressed {
                        background-color: #bd2130;
                    }
                    QPushButton:disabled {
                        background-color: #e0e0e0;
                        color: #999;
                    }
                """)
        elif style_type == "secondary":
            # Neutral secondary button
            if dark:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3c3c3c;
                        color: #ddd;
                        border: 1px solid #555;
                        border-radius: 4px;
                        padding: 6px 16px;
                    }
                    QPushButton:hover {
                        background-color: #4a4a4a;
                        border-color: #666;
                    }
                    QPushButton:pressed {
                        background-color: #333;
                    }
                    QPushButton:disabled {
                        background-color: #2d2d2d;
                        color: #555;
                        border-color: #444;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f0f0f0;
                        color: #333;
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        padding: 6px 16px;
                    }
                    QPushButton:hover {
                        background-color: #e5e5e5;
                        border-color: #bbb;
                    }
                    QPushButton:pressed {
                        background-color: #ddd;
                    }
                    QPushButton:disabled {
                        background-color: #f5f5f5;
                        color: #aaa;
                        border-color: #ddd;
                    }
                """)
        elif style_type == "action":
            # Blue action button (like primary actions)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #006cbd;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
                QPushButton:disabled {
                    background-color: #555;
                    color: #888;
                }
            """ if dark else """
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #006cbd;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
                QPushButton:disabled {
                    background-color: #e0e0e0;
                    color: #999;
                }
            """)

    def _connect_signals(self):
        """Connect signals to slots"""
        self.add_btn.clicked.connect(self.add_files)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear_all)
        self.merge_btn.clicked.connect(self.merge_files)
        self.grid_panel.selection_changed.connect(self._on_selection_changed)
        self.grid_panel.order_changed.connect(self._update_status)

    def add_files(self):
        """Open file dialog to add PDF files and images"""
        file_filter = "All Supported Files (*.pdf *.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif *.webp);;PDF Files (*.pdf);;Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif *.webp);;All Files (*)"
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF Files or Images",
            "",
            file_filter
        )

        existing_paths = set(self.grid_panel.get_ordered_file_paths())

        for path in file_paths:
            if path not in existing_paths:
                self._add_file(path)

        self._update_status()

    def _add_file(self, file_path: str):
        """Add a single PDF or image file to the grid"""
        if not os.path.exists(file_path):
            return

        is_image = is_image_file(file_path)

        # Generate thumbnail
        thumbnail = self._generate_thumbnail(file_path, is_image)
        self.thumbnails[file_path] = thumbnail
        self.file_types[file_path] = 'image' if is_image else 'pdf'

        # Create and add card
        card = PDFThumbnailCard(file_path, thumbnail, is_image=is_image)
        self.grid_panel.add_card(card)

    def _generate_thumbnail(self, file_path: str, is_image: bool = False) -> QPixmap:
        """Generate a thumbnail for a PDF or image file"""
        try:
            if is_image:
                # Load image directly
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    return pixmap
            else:
                # PDF - render first page
                doc = fitz.open(file_path)
                if doc.page_count > 0:
                    page = doc[0]
                    # Render at moderate resolution for thumbnail
                    mat = fitz.Matrix(0.4, 0.4)
                    pix = page.get_pixmap(matrix=mat)

                    # Convert to QPixmap
                    img_data = pix.tobytes("ppm")
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_data)

                    doc.close()
                    return pixmap
        except Exception as e:
            print(f"Error generating thumbnail for {file_path}: {e}")

        return QPixmap()

    def remove_selected(self):
        """Remove selected files from the grid"""
        selected = self.grid_panel.get_selected_cards()
        for card in selected:
            if card.file_path in self.thumbnails:
                del self.thumbnails[card.file_path]
            if card.file_path in self.file_types:
                del self.file_types[card.file_path]

        self.grid_panel.remove_selected()
        self._update_status()

    def clear_all(self):
        """Clear all files from the grid"""
        self.grid_panel.clear_all()
        self.thumbnails.clear()
        self.file_types.clear()
        self._update_status()

    def _on_selection_changed(self):
        """Handle selection change in the grid"""
        selected = self.grid_panel.get_selected_cards()
        has_selection = len(selected) > 0
        self.remove_btn.setEnabled(has_selection)

    def _update_status(self):
        """Update status label and button states"""
        count = len(self.grid_panel.cards)

        if count == 0:
            self.status_label.setText("No files added")
            self.merge_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
        elif count == 1:
            self.status_label.setText("1 file added — add more to merge")
            self.merge_btn.setEnabled(False)
            self.clear_btn.setEnabled(True)
        else:
            self.status_label.setText(f"{count} files ready to merge")
            self.merge_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)

    def merge_files(self):
        """Merge all PDFs and images into a single PDF"""
        ordered_files = self.grid_panel.get_ordered_file_paths()

        if len(ordered_files) < 2:
            QMessageBox.warning(self, "Not Enough Files", "Please add at least 2 files to merge.")
            return

        # Ask for output file
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Merged PDF",
            "merged.pdf",
            "PDF Files (*.pdf)"
        )

        if not output_path:
            return

        if not output_path.lower().endswith('.pdf'):
            output_path += '.pdf'

        try:
            # Create merged PDF
            merged_doc = fitz.open()

            for file_path in ordered_files:
                try:
                    file_type = self.file_types.get(file_path, 'pdf')

                    if file_type == 'image':
                        # Convert image to PDF page
                        self._add_image_as_page(merged_doc, file_path)
                    else:
                        # Insert PDF pages
                        pdf_doc = fitz.open(file_path)
                        merged_doc.insert_pdf(pdf_doc)
                        pdf_doc.close()
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Failed to add {os.path.basename(file_path)}: {e}"
                    )
                    continue

            # Save merged document
            merged_doc.save(output_path)
            merged_doc.close()

            QMessageBox.information(
                self,
                "Merge Complete",
                f"Successfully merged {len(ordered_files)} files into:\n{output_path}"
            )

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Merge Failed",
                f"Failed to merge files: {e}"
            )

    def _add_image_as_page(self, doc: fitz.Document, image_path: str):
        """Add an image as a new page in the PDF document"""
        # Open the image to get its dimensions
        img = fitz.open(image_path)

        # Get image dimensions
        if img.page_count > 0:
            # For multi-page images (like TIFF), add all pages
            for page_num in range(img.page_count):
                img_page = img[page_num]
                pix = img_page.get_pixmap()

                # Create a new page with image dimensions
                # Use A4 as max size, scale down if image is larger
                img_width = pix.width
                img_height = pix.height

                # Calculate page size (fit to A4 if larger)
                a4_width = 595  # A4 width in points
                a4_height = 842  # A4 height in points

                # Scale to fit A4 while maintaining aspect ratio
                scale = min(a4_width / img_width, a4_height / img_height, 1.0)
                page_width = img_width * scale
                page_height = img_height * scale

                # Create new page
                new_page = doc.new_page(width=page_width, height=page_height)

                # Insert image
                rect = fitz.Rect(0, 0, page_width, page_height)
                new_page.insert_image(rect, filename=image_path)

            img.close()
        else:
            # Fallback for simple images
            img.close()

            # Load with pixmap
            pix = fitz.Pixmap(image_path)
            img_width = pix.width
            img_height = pix.height

            # Calculate page size
            a4_width = 595
            a4_height = 842
            scale = min(a4_width / img_width, a4_height / img_height, 1.0)
            page_width = img_width * scale
            page_height = img_height * scale

            # Create new page and insert image
            new_page = doc.new_page(width=page_width, height=page_height)
            rect = fitz.Rect(0, 0, page_width, page_height)
            new_page.insert_image(rect, filename=image_path)
