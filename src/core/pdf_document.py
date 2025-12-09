"""
Core PDF Document Model
Handles PDF loading, rendering, and page management
"""
import fitz  # PyMuPDF
from typing import List, Optional, Tuple
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QSize
import io
from PIL import Image

# Suppress MuPDF warnings about minor PDF syntax issues
fitz.TOOLS.mupdf_display_errors(False)


class PDFDocument:
    """Main PDF document handler"""

    def __init__(self):
        self.doc: Optional[fitz.Document] = None
        self.file_path: Optional[str] = None
        self.page_count: int = 0
        self._page_cache = {}  # Cache rendered pages
        self._thumbnail_cache = {}  # Cache thumbnails

    def open(self, file_path: str) -> bool:
        """Open a PDF file"""
        try:
            self.doc = fitz.open(file_path)
            self.file_path = file_path
            self.page_count = len(self.doc)
            self._page_cache.clear()
            self._thumbnail_cache.clear()
            return True
        except Exception as e:
            print(f"Error opening PDF: {e}")
            return False

    def load_from_document(self, doc: fitz.Document, file_path: Optional[str] = None) -> bool:
        """Load from an existing fitz.Document object"""
        try:
            self.doc = doc
            self.file_path = file_path
            self.page_count = len(self.doc)
            self._page_cache.clear()
            self._thumbnail_cache.clear()
            return True
        except Exception as e:
            print(f"Error loading document: {e}")
            return False

    def close(self):
        """Close the current document"""
        if self.doc:
            self.doc.close()
            self.doc = None
            self.file_path = None
            self.page_count = 0
            self._page_cache.clear()
            self._thumbnail_cache.clear()

    def get_page(self, page_num: int) -> Optional[fitz.Page]:
        """Get a specific page"""
        if self.doc and 0 <= page_num < self.page_count:
            return self.doc[page_num]
        return None

    def render_page(self, page_num: int, zoom: float = 1.0, use_cache: bool = True) -> Optional[QPixmap]:
        """Render a page to QPixmap"""
        cache_key = (page_num, zoom)

        if use_cache and cache_key in self._page_cache:
            return self._page_cache[cache_key]

        page = self.get_page(page_num)
        if not page:
            return None

        try:
            # Render at specified zoom level
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert to QImage
            img_data = pix.samples
            img = QImage(img_data, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(img)

            if use_cache:
                self._page_cache[cache_key] = pixmap

            return pixmap
        except Exception as e:
            print(f"Error rendering page {page_num}: {e}")
            return None

    def get_thumbnail(self, page_num: int, max_size: int = 150) -> Optional[QPixmap]:
        """Get thumbnail for a page"""
        if page_num in self._thumbnail_cache:
            return self._thumbnail_cache[page_num]

        page = self.get_page(page_num)
        if not page:
            return None

        try:
            # Calculate zoom to fit max_size
            rect = page.rect
            zoom = min(max_size / rect.width, max_size / rect.height)

            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert to QImage
            img_data = pix.samples
            img = QImage(img_data, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(img)

            self._thumbnail_cache[page_num] = pixmap
            return pixmap
        except Exception as e:
            print(f"Error generating thumbnail for page {page_num}: {e}")
            return None

    def get_page_size(self, page_num: int) -> Optional[Tuple[float, float]]:
        """Get page size in points"""
        page = self.get_page(page_num)
        if page:
            rect = page.rect
            return (rect.width, rect.height)
        return None

    def insert_page(self, page_num: int, width: float = 612, height: float = 792):
        """Insert a blank page"""
        if self.doc:
            self.doc.insert_page(page_num, width=width, height=height)
            self.page_count = len(self.doc)
            self._clear_cache()

    def delete_page(self, page_num: int):
        """Delete a page"""
        if self.doc and 0 <= page_num < self.page_count:
            self.doc.delete_page(page_num)
            self.page_count = len(self.doc)
            self._clear_cache()

    def rotate_page(self, page_num: int, rotation: int):
        """Rotate a page (rotation in degrees: 90, 180, 270)"""
        page = self.get_page(page_num)
        if page:
            page.set_rotation(rotation)
            self._clear_cache()

    def move_page(self, from_page: int, to_page: int):
        """Move a page to a new position"""
        if self.doc:
            self.doc.move_page(from_page, to_page)
            self._clear_cache()

    def duplicate_page(self, page_num: int):
        """Duplicate a page"""
        if self.doc and 0 <= page_num < self.page_count:
            self.doc.copy_page(page_num, page_num + 1)
            self.page_count = len(self.doc)
            self._clear_cache()

    def extract_pages(self, start_page: int, end_page: int, output_path: str):
        """Extract pages to a new PDF"""
        if self.doc:
            new_doc = fitz.open()
            new_doc.insert_pdf(self.doc, from_page=start_page, to_page=end_page)
            new_doc.save(output_path)
            new_doc.close()

    def merge_pdf(self, other_pdf_path: str, at_page: int):
        """Merge another PDF into this document"""
        if self.doc:
            other_doc = fitz.open(other_pdf_path)
            self.doc.insert_pdf(other_doc, start_at=at_page)
            other_doc.close()
            self.page_count = len(self.doc)
            self._clear_cache()

    def save(self, output_path: Optional[str] = None, flatten: bool = False):
        """Save the PDF"""
        if self.doc:
            save_path = output_path or self.file_path
            if flatten:
                # Flatten annotations by rendering and creating new PDF
                self._save_flattened(save_path)
            else:
                # Check if saving to the same file that's currently open
                if save_path == self.file_path and self.file_path:
                    # Use incremental save for same file
                    self.doc.save(save_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
                else:
                    # Normal save for different file
                    self.doc.save(save_path, garbage=4, deflate=True)

    def _save_flattened(self, output_path: str):
        """Save PDF with flattened annotations"""
        if self.doc:
            # Create new document and render all pages
            new_doc = fitz.open()
            for page_num in range(self.page_count):
                page = self.doc[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

                # Create new page with same dimensions
                new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)

                # Insert rendered image
                img_bytes = pix.tobytes("png")
                new_page.insert_image(page.rect, stream=img_bytes)

            new_doc.save(output_path)
            new_doc.close()

    def export_page_as_image(self, page_num: int, output_path: str, dpi: int = 300):
        """Export a page as an image"""
        page = self.get_page(page_num)
        if page:
            zoom = dpi / 72  # 72 DPI is standard
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pix.save(output_path)

    def _clear_cache(self):
        """Clear all caches"""
        self._page_cache.clear()
        self._thumbnail_cache.clear()

    def create_new(self, width: float = 612, height: float = 792):
        """Create a new blank PDF"""
        self.close()
        self.doc = fitz.open()
        self.doc.insert_page(0, width=width, height=height)
        self.file_path = None
        self.page_count = 1
