"""
AI Chat Widget for PDF Q&A
Uses the local LLM to answer questions about the PDF content
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QRadioButton, QButtonGroup, QSpinBox,
    QFrame, QScrollArea, QSizePolicy, QToolButton
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont
from typing import Optional
from utils.icon_helper import get_icon
import fitz


class ChatBubble(QFrame):
    """A single chat message bubble"""

    def __init__(self, message: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.setup_ui(message)

    def setup_ui(self, message: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Create the bubble
        bubble = QLabel(message)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        bubble.setMaximumWidth(350)

        if self.is_user:
            # User message - right aligned
            bubble.setStyleSheet("""
                QLabel {
                    background-color: #3c3c3c;
                    border-radius: 12px;
                    padding: 10px 14px;
                    font-size: 13px;
                    border: 1px solid #555555;
                }
            """)
            layout.addStretch()
            layout.addWidget(bubble)
        else:
            # AI message - left aligned
            bubble.setStyleSheet("""
                QLabel {
                    background-color: #2d2d2d;
                    border-radius: 12px;
                    padding: 10px 14px;
                    font-size: 13px;
                    border: 1px solid #444444;
                }
            """)
            layout.addWidget(bubble)
            layout.addStretch()


class ChatThread(QThread):
    """Thread for generating AI responses"""
    response_chunk = pyqtSignal(str)  # Emits response chunks for streaming
    finished_response = pyqtSignal(str)  # Emits complete response
    error = pyqtSignal(str)

    def __init__(self, model, prompt: str, context: str):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.context = context

    def run(self):
        try:
            # Build the full prompt with context
            full_prompt = f"""Answer the question briefly based on this document. Be concise.

Document:
{self.context}

Question: {self.prompt}

Answer:"""

            # Generate response
            response = self.model(
                full_prompt,
                max_tokens=150,
                temperature=0.3,
                top_p=0.9,
                repeat_penalty=1.2,
                stop=["\n\n", "Question:", "Document:", "[End", "[end"],
                echo=False,
            )

            answer = response['choices'][0]['text'].strip()

            # Clean up any remaining artifacts
            if "[End" in answer:
                answer = answer.split("[End")[0].strip()
            if "[end" in answer:
                answer = answer.split("[end")[0].strip()

            self.finished_response.emit(answer)

        except Exception as e:
            self.error.emit(str(e))


class AIChatWidget(QWidget):
    """Widget for chatting with AI about the PDF"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_doc = None
        self.translation_service = None
        self.chat_thread = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Page range selection
        range_frame = QFrame()
        range_frame.setFrameShape(QFrame.Shape.StyledPanel)
        range_layout = QVBoxLayout(range_frame)
        range_layout.setContentsMargins(8, 8, 8, 8)
        range_layout.setSpacing(4)

        # Radio buttons for page selection - all in one row
        self.page_group = QButtonGroup(self)

        range_row = QHBoxLayout()
        range_row.setSpacing(6)

        self.all_pages_radio = QRadioButton("All Pages")
        self.all_pages_radio.setChecked(True)
        self.page_group.addButton(self.all_pages_radio)
        range_row.addWidget(self.all_pages_radio)

        # Specific range option
        self.range_radio = QRadioButton("Pages:")
        self.page_group.addButton(self.range_radio)
        range_row.addWidget(self.range_radio)

        self.from_spin = QSpinBox()
        self.from_spin.setMinimum(1)
        self.from_spin.setMaximum(1)
        self.from_spin.setValue(1)
        self.from_spin.setFixedWidth(45)
        range_row.addWidget(self.from_spin)

        range_row.addWidget(QLabel("to"))

        self.to_spin = QSpinBox()
        self.to_spin.setMinimum(1)
        self.to_spin.setMaximum(1)
        self.to_spin.setValue(1)
        self.to_spin.setFixedWidth(45)
        range_row.addWidget(self.to_spin)

        range_row.addStretch()
        range_layout.addLayout(range_row)

        layout.addWidget(range_frame)

        # Chat display area - scrollable container for bubbles
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container for chat bubbles
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(5, 5, 5, 5)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()  # Push messages to top initially

        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll, 1)

        # Input area
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 8, 0, 0)
        input_layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask about the PDF...")
        self.input_field.returnPressed.connect(self.send_message)
        self.input_field.setStyleSheet("""
            QLineEdit {
                border: 1px solid #555555;
                border-radius: 15px;
                padding: 8px 12px;
            }
        """)
        input_layout.addWidget(self.input_field)

        self.send_btn = QToolButton()
        self.send_btn.setIcon(get_icon("send"))
        self.send_btn.setIconSize(QSize(18, 18))
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setStyleSheet("""
            QToolButton {
                background-color: #006600;
                border: none;
                border-radius: 16px;
            }
            QToolButton:hover {
                background-color: #008800;
            }
            QToolButton:pressed {
                background-color: #004400;
            }
            QToolButton:disabled {
                background-color: #444444;
            }
        """)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(input_layout)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.status_label)

        # Connect radio buttons to enable/disable spinboxes
        self.all_pages_radio.toggled.connect(self._update_range_state)
        self._update_range_state()

    def _update_range_state(self):
        """Enable/disable range spinboxes based on selection"""
        enabled = self.range_radio.isChecked()
        self.from_spin.setEnabled(enabled)
        self.to_spin.setEnabled(enabled)

    def set_document(self, pdf_doc):
        """Set the PDF document to chat about"""
        self.pdf_doc = pdf_doc
        if pdf_doc and pdf_doc.doc:
            page_count = pdf_doc.page_count
            self.from_spin.setMaximum(page_count)
            self.to_spin.setMaximum(page_count)
            self.to_spin.setValue(page_count)
            self.status_label.setText(f"{page_count} pages loaded")
        else:
            self.from_spin.setMaximum(1)
            self.to_spin.setMaximum(1)
            self.status_label.setText("")

    def _get_pdf_context(self) -> str:
        """Extract text from selected pages for context"""
        if not self.pdf_doc or not self.pdf_doc.doc:
            return ""

        doc = self.pdf_doc.doc

        # Determine page range
        if self.all_pages_radio.isChecked():
            start_page = 0
            end_page = len(doc) - 1
        else:
            start_page = self.from_spin.value() - 1  # Convert to 0-indexed
            end_page = self.to_spin.value() - 1

        # Extract text from pages
        text_parts = []
        for page_num in range(start_page, end_page + 1):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                text_parts.append(f"[Page {page_num + 1}]\n{text}")

        # Limit context size to avoid token limits
        full_text = "\n\n".join(text_parts)
        max_chars = 4000  # Limit to ~1000 tokens
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n...[truncated]"

        return full_text

    def _ensure_model_loaded(self) -> bool:
        """Ensure the translation model is loaded"""
        from core.translation_service import get_translation_service

        if self.translation_service is None:
            self.translation_service = get_translation_service()

        if not self.translation_service.is_model_loaded():
            self.status_label.setText("Loading AI model...")
            self.send_btn.setEnabled(False)
            self.input_field.setEnabled(False)

            # Load model synchronously for simplicity
            def on_progress(msg):
                self.status_label.setText(msg)

            success = self.translation_service.load_model(on_progress)

            self.send_btn.setEnabled(True)
            self.input_field.setEnabled(True)

            if not success:
                error = self.translation_service.get_load_error()
                self.status_label.setText(f"Error: {error}")
                return False

        return True

    def send_message(self):
        """Send message to AI"""
        message = self.input_field.text().strip()
        if not message:
            return

        if not self.pdf_doc or not self.pdf_doc.doc:
            self._append_message("Please open a PDF document first.", is_user=False)
            return

        # Clear input
        self.input_field.clear()

        # Show user message
        self._append_message(message, is_user=True)

        # Ensure model is loaded
        if not self._ensure_model_loaded():
            self._append_message("Failed to load AI model.", is_user=False)
            return

        # Get PDF context
        context = self._get_pdf_context()
        if not context:
            self._append_message("No text found in the selected pages.", is_user=False)
            return

        # Disable input while processing
        self.send_btn.setEnabled(False)
        self.input_field.setEnabled(False)
        self.status_label.setText("Thinking...")

        # Start chat thread
        self.chat_thread = ChatThread(
            self.translation_service._model,
            message,
            context
        )
        self.chat_thread.finished_response.connect(self._on_response)
        self.chat_thread.error.connect(self._on_error)
        self.chat_thread.start()

    def _on_response(self, response: str):
        """Handle AI response"""
        self._append_message(response, is_user=False)
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.status_label.setText("")
        self.input_field.setFocus()

    def _on_error(self, error: str):
        """Handle error"""
        self._append_message(f"Error: {error}", is_user=False)
        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.status_label.setText("")

    def _append_message(self, message: str, is_user: bool):
        """Append a message bubble to the chat"""
        # Remove the stretch at the end
        stretch_item = self.chat_layout.takeAt(self.chat_layout.count() - 1)

        # Add the new bubble
        bubble = ChatBubble(message, is_user)
        self.chat_layout.addWidget(bubble)

        # Re-add the stretch
        self.chat_layout.addStretch()

        # Scroll to bottom
        self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        )

        # Force scroll update after widget is added
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    def clear_chat(self):
        """Clear the chat history"""
        # Remove all bubbles except the stretch
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
