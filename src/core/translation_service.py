"""
Local LLM Translation Service
Uses a lightweight local model for on-device translation
"""
import os
import threading
from typing import Optional, Callable, List, Dict, Any
from pathlib import Path


class TranslationService:
    """Service for translating text using a local LLM"""

    # Supported languages
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'nl': 'Dutch',
        'ru': 'Russian',
        'zh': 'Chinese',
        'ja': 'Japanese',
        'ko': 'Korean',
        'ar': 'Arabic',
        'hi': 'Hindi',
        'tr': 'Turkish',
        'pl': 'Polish',
        'vi': 'Vietnamese',
        'th': 'Thai',
        'id': 'Indonesian',
        'sv': 'Swedish',
        'da': 'Danish',
        'no': 'Norwegian',
        'fi': 'Finnish',
        'cs': 'Czech',
        'el': 'Greek',
        'he': 'Hebrew',
        'uk': 'Ukrainian',
        'ro': 'Romanian',
        'hu': 'Hungarian',
        'bg': 'Bulgarian',
        'ms': 'Malay',
    }

    # Model configuration - using a small, efficient model
    MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
    MODEL_FILE = "qwen2.5-0.5b-instruct-q4_k_m.gguf"

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._model_loaded = False
        self._loading = False
        self._model_dir = self._get_model_dir()
        self._load_error: Optional[str] = None

    def _get_model_dir(self) -> Path:
        """Get the directory for storing model files"""
        # Store in user's home directory under .pdf_editor/models
        model_dir = Path.home() / '.pdf_editor' / 'models'
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir

    def _get_model_path(self) -> Path:
        """Get the full path to the model file"""
        return self._model_dir / self.MODEL_FILE

    def is_model_downloaded(self) -> bool:
        """Check if the model is already downloaded"""
        model_path = self._get_model_path()
        return model_path.exists() and model_path.stat().st_size > 0

    def is_model_loaded(self) -> bool:
        """Check if the model is loaded in memory"""
        return self._model_loaded

    def is_loading(self) -> bool:
        """Check if model is currently being loaded"""
        return self._loading

    def get_load_error(self) -> Optional[str]:
        """Get any error that occurred during loading"""
        return self._load_error

    def download_model(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """
        Download the model from Hugging Face Hub

        Args:
            progress_callback: Optional callback(downloaded_bytes, total_bytes)

        Returns:
            True if download successful, False otherwise
        """
        try:
            from huggingface_hub import hf_hub_download

            model_path = self._get_model_path()

            # Download from Hugging Face Hub
            downloaded_path = hf_hub_download(
                repo_id=self.MODEL_NAME,
                filename=self.MODEL_FILE,
                local_dir=self._model_dir,
            )

            return True

        except ImportError:
            self._load_error = "huggingface_hub not installed. Run: pip install huggingface_hub"
            return False
        except Exception as e:
            self._load_error = f"Failed to download model: {str(e)}"
            return False

    def load_model(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Load the model into memory

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            True if loaded successfully, False otherwise
        """
        if self._model_loaded:
            return True

        if self._loading:
            return False

        self._loading = True
        self._load_error = None

        try:
            if progress_callback:
                progress_callback("Checking model availability...")

            # Check if model is downloaded
            if not self.is_model_downloaded():
                if progress_callback:
                    progress_callback("Downloading model (this may take a few minutes)...")
                if not self.download_model():
                    self._loading = False
                    return False

            if progress_callback:
                progress_callback("Loading model into memory...")

            # Try to load with llama-cpp-python (preferred for GGUF)
            try:
                from llama_cpp import Llama

                model_path = str(self._get_model_path())

                self._model = Llama(
                    model_path=model_path,
                    n_ctx=2048,  # Context window
                    n_threads=4,  # CPU threads
                    n_gpu_layers=0,  # CPU only for compatibility
                    verbose=False,
                )

                self._model_loaded = True
                self._loading = False

                if progress_callback:
                    progress_callback("Model loaded successfully!")

                return True

            except ImportError:
                self._load_error = "llama-cpp-python not installed. Run: pip install llama-cpp-python"
                self._loading = False
                return False

        except Exception as e:
            self._load_error = f"Failed to load model: {str(e)}"
            self._loading = False
            return False

    def load_model_async(self,
                         progress_callback: Optional[Callable[[str], None]] = None,
                         completion_callback: Optional[Callable[[bool], None]] = None):
        """
        Load the model asynchronously in a background thread

        Args:
            progress_callback: Called with progress messages
            completion_callback: Called with True/False when complete
        """
        def _load():
            result = self.load_model(progress_callback)
            if completion_callback:
                completion_callback(result)

        thread = threading.Thread(target=_load, daemon=True)
        thread.start()

    def set_document_context(self, context: str):
        """
        Set the document context for context-aware translations

        Args:
            context: A summary or sample of the document content
        """
        self._document_context = context

    def get_document_context(self) -> Optional[str]:
        """Get the current document context"""
        return getattr(self, '_document_context', None)

    def clear_document_context(self):
        """Clear the document context"""
        self._document_context = None

    def _should_skip_translation(self, text: str) -> bool:
        """
        Check if text should be skipped (not translated)

        Args:
            text: Text to check

        Returns:
            True if text should not be translated
        """
        if not text:
            return True

        stripped = text.strip()
        if not stripped:
            return True

        # Skip very short text
        if len(stripped) <= 1:
            return True

        # Skip if only digits and punctuation
        if all(c.isdigit() or c in '.,;:/-() ' for c in stripped):
            return True

        # Skip if no letters at all
        if not any(c.isalpha() for c in stripped):
            return True

        # Count actual letters
        letter_count = sum(1 for c in stripped if c.isalpha())
        if letter_count < 2:
            return True

        return False

    def _is_valid_translation(self, translated: str, original: str) -> bool:
        """
        Check if translation is valid (not gibberish)

        Args:
            translated: Translated text
            original: Original text

        Returns:
            True if translation appears valid
        """
        if not translated or not translated.strip():
            return False

        translated = translated.strip()

        # Check for excessive length (hallucination)
        if len(translated) > len(original) * 4:
            return False

        # Check for repetitive characters
        for char in set(translated):
            if char not in ' \n\t' and translated.count(char) > len(translated) * 0.5:
                return False

        # Check for model artifacts
        lower = translated.lower()
        bad_patterns = ['translation:', 'here is', '```', '###', '**']
        for pattern in bad_patterns:
            if pattern in lower:
                return False

        # Check for mostly non-printable
        printable = sum(1 for c in translated if c.isprintable())
        if printable < len(translated) * 0.9:
            return False

        return True

    def _clean_output(self, text: str) -> str:
        """
        Clean LLM output

        Args:
            text: Raw output text

        Returns:
            Cleaned text
        """
        if not text:
            return text

        # Strip whitespace
        text = text.strip()

        # Remove wrapping quotes
        if len(text) >= 2:
            if (text[0] == '"' and text[-1] == '"') or (text[0] == "'" and text[-1] == "'"):
                text = text[1:-1].strip()

        # Remove common LLM prefixes
        prefixes = ['translation:', 'translated:', 'answer:', 'output:']
        lower = text.lower()
        for prefix in prefixes:
            if lower.startswith(prefix):
                text = text[len(prefix):].strip()
                lower = text.lower()

        return text

    def translate_text(self, text: str, target_language: str, source_language: str = 'auto') -> str:
        """
        Translate text to target language

        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'es', 'fr')
            source_language: Source language code or 'auto' for auto-detect

        Returns:
            Translated text
        """
        if not self._model_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Quick check - skip if nothing to translate
        if self._should_skip_translation(text):
            return text

        target_lang_name = self.SUPPORTED_LANGUAGES.get(target_language, target_language)

        # Simple, direct prompt
        prompt = f"Translate to {target_lang_name}: {text.strip()}\n\nTranslation:"

        try:
            response = self._model(
                prompt,
                max_tokens=min(len(text) * 3, 200),
                temperature=0.1,
                top_p=0.9,
                stop=["\n", "Translate", "Translation:"],
                echo=False,
            )

            translated = response['choices'][0]['text']

            # Clean output
            translated = self._clean_output(translated)

            # Validate
            if not self._is_valid_translation(translated, text):
                return text

            return translated

        except Exception as e:
            print(f"Translation error: {e}")
            return text

    def translate_text_blocks(self,
                              text_blocks: List[Dict[str, Any]],
                              target_language: str,
                              progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict[str, Any]]:
        """
        Translate multiple text blocks

        Args:
            text_blocks: List of dicts with 'text' key and other metadata
            target_language: Target language code
            progress_callback: Optional callback(current, total)

        Returns:
            List of text blocks with translated text
        """
        translated_blocks = []
        total = len(text_blocks)

        for i, block in enumerate(text_blocks):
            if progress_callback:
                progress_callback(i + 1, total)

            translated_block = block.copy()
            if 'text' in block and block['text'].strip():
                translated_block['text'] = self.translate_text(block['text'], target_language)

            translated_blocks.append(translated_block)

        return translated_blocks

    def unload_model(self):
        """Unload the model from memory"""
        self._model = None
        self._tokenizer = None
        self._model_loaded = False

    @classmethod
    def get_supported_languages(cls) -> Dict[str, str]:
        """Get dictionary of supported language codes and names"""
        return cls.SUPPORTED_LANGUAGES.copy()


# Singleton instance
_translation_service: Optional[TranslationService] = None


def get_translation_service() -> TranslationService:
    """Get the singleton translation service instance"""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service
