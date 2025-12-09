"""
Translation Dialog
Provides UI for selecting target language and initiating translation
Automatically downloads and loads the local LLM model
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QProgressBar, QMessageBox, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from typing import Optional, List, Dict, Any
import fitz  # PyMuPDF


class ModelLoaderThread(QThread):
    """Thread for downloading and loading the translation model"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, service):
        super().__init__()
        self.service = service

    def run(self):
        try:
            result = self.service.load_model(
                progress_callback=lambda msg: self.progress.emit(msg)
            )
            if result:
                self.finished.emit(True, "Model loaded successfully")
            else:
                error = self.service.get_load_error() or "Unknown error"
                self.finished.emit(False, error)
        except Exception as e:
            self.finished.emit(False, str(e))


class FontStyleMapper:
    """Maps and manages font styles for accurate reproduction"""

    # Standard PDF base fonts mapping
    BASE_FONT_MAP = {
        'helv': 'helv',
        'helvetica': 'helv',
        'arial': 'helv',
        'tiro': 'tiro',
        'times': 'tiro',
        'timesnewroman': 'tiro',
        'cour': 'cour',
        'courier': 'cour',
        'couriernew': 'cour',
        'symbol': 'symb',
        'zapfdingbats': 'zadb',
    }

    # Font style indicators
    BOLD_INDICATORS = ['bold', 'black', 'heavy', 'demi', 'semibold', 'medium']
    ITALIC_INDICATORS = ['italic', 'oblique', 'inclined', 'slanted']

    def __init__(self):
        self._font_cache = {}  # Cache for loaded fonts
        self._style_cache = {}  # Cache for detected styles

    def detect_font_style(self, font_name: str) -> dict:
        """
        Detect font style properties from font name

        Returns dict with: base_font, is_bold, is_italic, weight
        """
        if font_name in self._style_cache:
            return self._style_cache[font_name]

        font_lower = font_name.lower().replace('-', '').replace('_', '').replace(' ', '')

        # Detect bold
        is_bold = any(ind in font_lower for ind in self.BOLD_INDICATORS)

        # Detect italic
        is_italic = any(ind in font_lower for ind in self.ITALIC_INDICATORS)

        # Determine base font family
        base_font = 'helv'  # Default
        for key, value in self.BASE_FONT_MAP.items():
            if key in font_lower:
                base_font = value
                break

        # Build appropriate font name for PyMuPDF
        if base_font == 'helv':
            if is_bold and is_italic:
                mapped_font = 'hebo'  # Helvetica Bold Oblique
            elif is_bold:
                mapped_font = 'hebo'  # Helvetica Bold
            elif is_italic:
                mapped_font = 'heit'  # Helvetica Italic
            else:
                mapped_font = 'helv'  # Helvetica
        elif base_font == 'tiro':
            if is_bold and is_italic:
                mapped_font = 'tibi'  # Times Bold Italic
            elif is_bold:
                mapped_font = 'tibo'  # Times Bold
            elif is_italic:
                mapped_font = 'tiit'  # Times Italic
            else:
                mapped_font = 'tiro'  # Times Roman
        elif base_font == 'cour':
            if is_bold and is_italic:
                mapped_font = 'cobi'  # Courier Bold Oblique
            elif is_bold:
                mapped_font = 'cobo'  # Courier Bold
            elif is_italic:
                mapped_font = 'coit'  # Courier Oblique
            else:
                mapped_font = 'cour'  # Courier
        else:
            mapped_font = base_font

        result = {
            'original': font_name,
            'base_font': base_font,
            'mapped_font': mapped_font,
            'is_bold': is_bold,
            'is_italic': is_italic,
        }

        self._style_cache[font_name] = result
        return result

    def get_pymupdf_font(self, font_name: str) -> str:
        """Get the appropriate PyMuPDF font name"""
        style = self.detect_font_style(font_name)
        return style['mapped_font']


class TextSpanInfo:
    """Holds comprehensive information about a text span"""

    def __init__(self, span: dict, block_bbox: fitz.Rect, line_bbox: fitz.Rect):
        self.text = span.get("text", "")
        self.bbox = fitz.Rect(span.get("bbox"))
        self.font_name = span.get("font", "helv")
        self.font_size = span.get("size", 12)
        self.flags = span.get("flags", 0)  # Font flags (bold, italic, etc.)
        self.color = span.get("color", 0)
        self.origin = span.get("origin", (self.bbox.x0, self.bbox.y1))
        self.ascender = span.get("ascender", 0.8)
        self.descender = span.get("descender", -0.2)

        # Block and line context for section detection
        self.block_bbox = block_bbox
        self.line_bbox = line_bbox

        # Parse flags for style info
        # Bit 0: superscript, Bit 1: italic, Bit 2: serifed, Bit 3: monospaced
        # Bit 4: bold
        self.is_bold = bool(self.flags & (1 << 4))
        self.is_italic = bool(self.flags & (1 << 1))
        self.is_monospace = bool(self.flags & (1 << 3))
        self.is_serif = bool(self.flags & (1 << 2))
        self.is_superscript = bool(self.flags & (1 << 0))

        # Convert color
        if isinstance(self.color, int):
            r = ((self.color >> 16) & 255) / 255
            g = ((self.color >> 8) & 255) / 255
            b = (self.color & 255) / 255
            self.color_tuple = (r, g, b)
        else:
            self.color_tuple = (0, 0, 0)

    def classify_section_type(self, page_height: float, avg_font_size: float) -> str:
        """Classify what type of section this text belongs to"""
        # Heading detection based on font size relative to average
        size_ratio = self.font_size / avg_font_size if avg_font_size > 0 else 1

        if size_ratio >= 1.8:
            return 'title'
        elif size_ratio >= 1.4:
            return 'heading'
        elif size_ratio >= 1.15:
            return 'subheading'
        elif size_ratio <= 0.85:
            return 'caption'
        else:
            return 'body'


class TranslationThread(QThread):
    """Thread for performing translation with accurate font preservation"""
    progress = pyqtSignal(int, int, str)  # current, total, current_text
    finished = pyqtSignal(bool, object)  # success, result (translated doc or error)

    def __init__(self, service, doc: fitz.Document, target_language: str):
        super().__init__()
        self.service = service
        self.doc = doc
        self.target_language = target_language
        self.font_mapper = FontStyleMapper()

    def _extract_document_context(self) -> str:
        """Extract context from the document to help with translation"""
        # Collect text from first few pages to understand document type
        sample_text = []
        max_pages = min(3, len(self.doc))  # Sample first 3 pages

        for page_num in range(max_pages):
            page = self.doc[page_num]
            text = page.get_text("text")
            if text:
                # Take first 500 chars from each page
                sample_text.append(text[:500])

        combined_text = "\n".join(sample_text)[:1500]  # Limit total context

        # Use the model to identify document type
        if not combined_text.strip():
            return "general document"

        try:
            response = self.service._model(
                f"""Based on this text sample, identify the document type in 5-10 words (e.g., "legal contract", "medical report", "travel visa application form", "technical manual", "passport or ID document", "academic paper").

Text sample:
{combined_text[:800]}

Document type:""",
                max_tokens=30,
                temperature=0.1,
                stop=["\n", "."],
                echo=False,
            )
            doc_type = response['choices'][0]['text'].strip()
            return doc_type if doc_type else "general document"
        except:
            return "general document"

    def _collect_page_spans(self, page: fitz.Page) -> tuple:
        """
        Collect all text spans from a page with full style information

        Returns: (list of TextSpanInfo, average font size)
        """
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        spans = []
        font_sizes = []

        blocks = text_dict.get("blocks", [])
        for block in blocks:
            if block.get("type") == 0:  # Text block
                block_bbox = fitz.Rect(block.get("bbox"))
                for line in block.get("lines", []):
                    line_bbox = fitz.Rect(line.get("bbox"))
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue

                        span_info = TextSpanInfo(span, block_bbox, line_bbox)
                        spans.append(span_info)
                        font_sizes.append(span_info.font_size)

        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12
        return spans, avg_font_size

    def _calculate_text_width(self, text: str, font_size: float, fontname: str = "helv") -> float:
        """Estimate text width based on font size and character count"""
        # Average character width ratio for common fonts
        avg_char_width_ratio = 0.5  # Approximate ratio of char width to font size
        return len(text) * font_size * avg_char_width_ratio

    def run(self):
        try:
            # First, extract document context
            self.progress.emit(0, len(self.doc), "Analyzing document context...")
            doc_context = self._extract_document_context()
            self.service.set_document_context(doc_context)

            # Create a copy of the document to modify
            pdf_bytes = self.doc.tobytes()
            translated_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            total_pages = len(translated_doc)

            for page_num in range(total_pages):
                self.progress.emit(page_num + 1, total_pages, f"Translating page {page_num + 1}...")

                page = translated_doc[page_num]
                page_height = page.rect.height

                # Collect all spans with full style information
                spans, avg_font_size = self._collect_page_spans(page)

                # Prepare replacements with comprehensive style info
                replacements = []

                for span_info in spans:
                    # Classify section type for context
                    section_type = span_info.classify_section_type(page_height, avg_font_size)

                    # Translate the text
                    translated_text = self.service.translate_text(
                        span_info.text, self.target_language
                    )

                    # Get mapped font for accurate style reproduction
                    mapped_font = self.font_mapper.get_pymupdf_font(span_info.font_name)
                    is_bold = span_info.is_bold
                    is_italic = span_info.is_italic

                    # Also check flags for bold/italic override
                    if span_info.is_bold or span_info.is_italic:
                        style_info = self.font_mapper.detect_font_style(span_info.font_name)
                        is_bold = span_info.is_bold or style_info['is_bold']
                        is_italic = span_info.is_italic or style_info['is_italic']

                        base = style_info['base_font']
                        if base == 'helv':
                            if is_bold and is_italic:
                                mapped_font = 'hebo'
                            elif is_bold:
                                mapped_font = 'hebo'
                            elif is_italic:
                                mapped_font = 'heit'
                        elif base == 'tiro':
                            if is_bold and is_italic:
                                mapped_font = 'tibi'
                            elif is_bold:
                                mapped_font = 'tibo'
                            elif is_italic:
                                mapped_font = 'tiit'
                        elif base == 'cour':
                            if is_bold and is_italic:
                                mapped_font = 'cobi'
                            elif is_bold:
                                mapped_font = 'cobo'
                            elif is_italic:
                                mapped_font = 'coit'

                    replacements.append({
                        'span_info': span_info,
                        'translated': translated_text,
                        'mapped_font': mapped_font,
                        'section_type': section_type,
                        'is_bold': is_bold,
                        'is_italic': is_italic,
                    })

                # Apply redactions to remove original text
                for repl in replacements:
                    span_info = repl['span_info']
                    page.add_redact_annot(span_info.bbox)

                # Apply all redactions at once
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

                # Insert translated text back into PDF
                for repl in replacements:
                    span_info = repl['span_info']
                    translated_text = repl['translated']
                    mapped_font = repl['mapped_font']

                    bbox = span_info.bbox
                    original_font_size = span_info.font_size
                    color_tuple = span_info.color_tuple

                    # Calculate appropriate font size
                    adjusted_size = original_font_size
                    original_width = bbox.width
                    estimated_new_width = self._calculate_text_width(
                        translated_text, original_font_size, mapped_font
                    )

                    if estimated_new_width > original_width * 1.1:
                        scale_factor = original_width / estimated_new_width
                        adjusted_size = original_font_size * max(scale_factor, 0.6)

                    # Calculate insertion point
                    if hasattr(span_info, 'origin') and span_info.origin:
                        origin = span_info.origin
                        if isinstance(origin, (list, tuple)) and len(origin) >= 2:
                            insert_point = fitz.Point(origin[0], origin[1])
                        else:
                            baseline_y = bbox.y0 + (bbox.height * span_info.ascender)
                            insert_point = fitz.Point(bbox.x0, baseline_y)
                    else:
                        baseline_y = bbox.y1 - (bbox.height * 0.2)
                        insert_point = fitz.Point(bbox.x0, baseline_y)

                    # Insert text with font settings
                    try:
                        page.insert_text(
                            insert_point,
                            translated_text,
                            fontname=mapped_font,
                            fontsize=adjusted_size,
                            color=color_tuple,
                        )
                    except Exception:
                        try:
                            page.insert_text(
                                insert_point,
                                translated_text,
                                fontname="helv",
                                fontsize=adjusted_size,
                                color=color_tuple,
                            )
                        except Exception:
                            page.insert_text(
                                insert_point,
                                translated_text,
                                fontsize=adjusted_size,
                                color=color_tuple,
                            )

            # Clear document context after translation
            self.service.clear_document_context()

            self.finished.emit(True, translated_doc)

        except Exception as e:
            # Clear document context on error too
            self.service.clear_document_context()
            self.finished.emit(False, str(e))


class TranslationDialog(QDialog):
    """Dialog for translating PDF documents - auto-downloads model"""

    def __init__(self, parent=None, document: fitz.Document = None):
        super().__init__(parent)
        self.document = document
        self.translated_doc = None
        self._loader_thread = None
        self._translation_thread = None
        self._model_ready = False

        self.setWindowTitle("Translate Document")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(300)

        self._init_ui()

        # Auto-start model loading after dialog is shown
        QTimer.singleShot(100, self._auto_load_model)

    def _init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)

        # Language selection group
        lang_group = QGroupBox("Translation Settings")
        lang_layout = QVBoxLayout()

        # Target language selection
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Translate to:"))

        self.target_combo = QComboBox()
        self._populate_languages()
        self.target_combo.setCurrentText("Spanish")
        target_layout.addWidget(self.target_combo, 1)
        lang_layout.addLayout(target_layout)

        # Document info
        if self.document:
            info_label = QLabel(f"Pages: {len(self.document)}")
            info_label.setStyleSheet("color: gray; font-style: italic;")
            lang_layout.addWidget(info_label)

        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)

        # Model status group
        model_group = QGroupBox("Local LLM Status")
        model_layout = QVBoxLayout()

        self.model_status_label = QLabel("Initializing...")
        model_layout.addWidget(self.model_status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate initially
        model_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("Preparing translation model...")
        self.progress_label.setStyleSheet("color: gray;")
        model_layout.addWidget(self.progress_label)

        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # Info text
        info_text = QLabel(
            "Using local AI model (Qwen2.5-0.5B). First run downloads ~400MB.\n"
            "No internet required after initial download."
        )
        info_text.setStyleSheet("color: gray; font-style: italic;")
        info_text.setWordWrap(True)
        layout.addWidget(info_text)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.translate_btn = QPushButton("Translate")
        self.translate_btn.setEnabled(False)
        self.translate_btn.clicked.connect(self._start_translation)
        button_layout.addWidget(self.translate_btn)

        layout.addLayout(button_layout)

    def _populate_languages(self):
        """Populate the language combo box"""
        from core.translation_service import TranslationService

        languages = TranslationService.get_supported_languages()

        # Sort by language name
        sorted_langs = sorted(languages.items(), key=lambda x: x[1])

        for code, name in sorted_langs:
            self.target_combo.addItem(name, code)

    def _auto_load_model(self):
        """Automatically download and load the model"""
        from core.translation_service import get_translation_service

        service = get_translation_service()

        # Check if already loaded
        if service.is_model_loaded():
            self._on_load_finished(True, "Model already loaded")
            return

        # Start loading
        self.model_status_label.setText("Preparing translation model...")

        if not service.is_model_downloaded():
            self.progress_label.setText("Downloading model (~400MB)... This may take a few minutes.")
        else:
            self.progress_label.setText("Loading model into memory...")

        self._loader_thread = ModelLoaderThread(service)
        self._loader_thread.progress.connect(self._on_load_progress)
        self._loader_thread.finished.connect(self._on_load_finished)
        self._loader_thread.start()

    def _on_load_progress(self, message: str):
        """Handle model loading progress"""
        self.progress_label.setText(message)

    def _on_load_finished(self, success: bool, message: str):
        """Handle model loading completion"""
        if success:
            self._model_ready = True
            self.model_status_label.setText("✓ Model ready")
            self.model_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.progress_bar.setVisible(False)
            self.progress_label.setText("Ready to translate")
            self.translate_btn.setEnabled(True)
        else:
            self.model_status_label.setText("✗ Model loading failed")
            self.model_status_label.setStyleSheet("color: red;")
            self.progress_bar.setVisible(False)
            self.progress_label.setText(f"Error: {message}")
            self.progress_label.setStyleSheet("color: red;")

            QMessageBox.critical(
                self,
                "Model Loading Failed",
                f"Failed to load the translation model:\n\n{message}\n\n"
                "Please ensure you have the required packages installed:\n"
                "pip install llama-cpp-python huggingface_hub"
            )

    def _start_translation(self):
        """Start the translation process"""
        if not self.document:
            QMessageBox.warning(self, "No Document", "No document to translate.")
            return

        if not self._model_ready:
            QMessageBox.warning(self, "Model Not Ready", "Please wait for the model to load.")
            return

        from core.translation_service import get_translation_service
        service = get_translation_service()

        # Get target language
        target_code = self.target_combo.currentData()

        # Disable UI during translation
        self.translate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.target_combo.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.document))
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)
        self.progress_label.setStyleSheet("color: gray;")

        # Start translation thread
        self._translation_thread = TranslationThread(service, self.document, target_code)
        self._translation_thread.progress.connect(self._on_translation_progress)
        self._translation_thread.finished.connect(self._on_translation_finished)
        self._translation_thread.start()

    def _on_translation_progress(self, current: int, total: int, message: str):
        """Handle translation progress"""
        self.progress_bar.setValue(current)
        self.progress_label.setText(message)

    def _on_translation_finished(self, success: bool, result):
        """Handle translation completion"""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.cancel_btn.setEnabled(True)
        self.target_combo.setEnabled(True)

        if success:
            self.translated_doc = result
            self.accept()
        else:
            self.translate_btn.setEnabled(True)
            QMessageBox.critical(
                self,
                "Translation Failed",
                f"Failed to translate document:\n\n{result}"
            )

    def get_translated_document(self) -> Optional[fitz.Document]:
        """Get the translated document"""
        return self.translated_doc

    def get_target_language(self) -> str:
        """Get the selected target language name"""
        return self.target_combo.currentText()

    def closeEvent(self, event):
        """Handle dialog close"""
        # Stop any running threads
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.terminate()
            self._loader_thread.wait()

        if self._translation_thread and self._translation_thread.isRunning():
            self._translation_thread.terminate()
            self._translation_thread.wait()

        super().closeEvent(event)
