"""
Icon Helper
Utilities for loading and managing SVG icons with automatic theme detection
"""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPalette
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QApplication
import os


class IconHelper:
    """Helper class for loading and managing icons"""

    # Icon directory
    ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'icons')

    # Icon cache
    _icon_cache = {}

    # Theme cache
    _is_dark_theme = None

    @classmethod
    def is_dark_theme(cls) -> bool:
        """
        Detect if the current OS/application theme is dark

        Returns:
            True if dark theme, False if light theme
        """
        if cls._is_dark_theme is not None:
            return cls._is_dark_theme

        try:
            app = QApplication.instance()
            if app:
                palette = app.palette()
                # Check the lightness of the window background color
                # If it's dark (< 128 lightness), it's a dark theme
                bg_color = palette.color(QPalette.ColorRole.Window)
                cls._is_dark_theme = bg_color.lightness() < 128
                return cls._is_dark_theme
        except:
            pass

        # Default to light theme if detection fails
        cls._is_dark_theme = False
        return False

    @classmethod
    def get_theme_color(cls) -> str:
        """
        Get the appropriate icon color for the current theme

        Returns:
            '#FFFFFF' for dark themes, '#000000' for light themes
        """
        return '#FFFFFF' if cls.is_dark_theme() else '#000000'

    @classmethod
    def refresh_theme_cache(cls):
        """Refresh theme detection cache and clear icon cache"""
        cls._is_dark_theme = None
        cls._icon_cache.clear()

    @classmethod
    def get_icon(cls, name: str, color: str = None, size: int = 24, auto_color: bool = True) -> QIcon:
        """
        Get an icon by name

        Args:
            name: Icon name (without .svg extension)
            color: Optional color to recolor the icon (hex format like '#000000')
                  If None and auto_color=True, uses theme-appropriate color
            size: Icon size in pixels (default: 24)
            auto_color: If True and color is None, automatically use theme color

        Returns:
            QIcon object
        """
        # Auto-detect theme color if not specified
        if color is None and auto_color:
            color = cls.get_theme_color()

        cache_key = f"{name}_{color}_{size}"

        # Return cached icon if available
        if cache_key in cls._icon_cache:
            return cls._icon_cache[cache_key]

        # Build icon path
        icon_path = os.path.join(cls.ICONS_DIR, f"{name}.svg")

        if not os.path.exists(icon_path):
            # Return empty icon if not found
            return QIcon()

        # Load SVG
        renderer = QSvgRenderer(icon_path)

        # Create pixmap
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)

        # Render SVG to pixmap
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        # Recolor if requested
        if color:
            pixmap = cls._recolor_pixmap(pixmap, color)

        # Create icon
        icon = QIcon(pixmap)

        # Cache it
        cls._icon_cache[cache_key] = icon

        return icon

    @classmethod
    def _recolor_pixmap(cls, pixmap: QPixmap, color_hex: str) -> QPixmap:
        """Recolor a pixmap to a specific color"""
        # Create a new pixmap with the same size
        colored_pixmap = QPixmap(pixmap.size())
        colored_pixmap.fill(Qt.GlobalColor.transparent)

        # Paint the pixmap with the new color
        painter = QPainter(colored_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(colored_pixmap.rect(), QColor(color_hex))
        painter.end()

        return colored_pixmap

    @classmethod
    def get_pixmap(cls, name: str, size: int = 24, color: str = None, auto_color: bool = True) -> QPixmap:
        """
        Get a pixmap for an icon

        Args:
            name: Icon name (without .svg extension)
            size: Icon size in pixels
            color: Optional color to recolor the icon
                  If None and auto_color=True, uses theme-appropriate color
            auto_color: If True and color is None, automatically use theme color

        Returns:
            QPixmap object
        """
        # Auto-detect theme color if not specified
        if color is None and auto_color:
            color = cls.get_theme_color()

        icon_path = os.path.join(cls.ICONS_DIR, f"{name}.svg")

        if not os.path.exists(icon_path):
            # Return empty pixmap if not found
            return QPixmap()

        # Load SVG
        renderer = QSvgRenderer(icon_path)

        # Create pixmap
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)

        # Render SVG to pixmap
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        # Recolor if requested
        if color:
            pixmap = cls._recolor_pixmap(pixmap, color)

        return pixmap

    @classmethod
    def list_available_icons(cls):
        """List all available icon names"""
        if not os.path.exists(cls.ICONS_DIR):
            return []

        icons = []
        for file in os.listdir(cls.ICONS_DIR):
            if file.endswith('.svg'):
                icons.append(file[:-4])  # Remove .svg extension

        return sorted(icons)

    @classmethod
    def get_icon_path(cls, name: str) -> str:
        """Get the full path to an icon file"""
        return os.path.join(cls.ICONS_DIR, f"{name}.svg")


# Convenience functions
def get_icon(name: str, color: str = None, size: int = 24, auto_color: bool = True) -> QIcon:
    """
    Get an icon by name (convenience function)

    Args:
        name: Icon name (without .svg extension)
        color: Optional color to recolor the icon
              If None and auto_color=True, uses theme-appropriate color
        size: Icon size in pixels (default: 24)
        auto_color: If True and color is None, automatically use theme color

    Returns:
        QIcon object with automatic theme-based coloring
    """
    return IconHelper.get_icon(name, color, size, auto_color)


def get_pixmap(name: str, size: int = 24, color: str = None, auto_color: bool = True) -> QPixmap:
    """
    Get a pixmap for an icon (convenience function)

    Args:
        name: Icon name (without .svg extension)
        size: Icon size in pixels
        color: Optional color to recolor the icon
              If None and auto_color=True, uses theme-appropriate color
        auto_color: If True and color is None, automatically use theme color

    Returns:
        QPixmap object with automatic theme-based coloring
    """
    return IconHelper.get_pixmap(name, size, color, auto_color)


def is_dark_theme() -> bool:
    """Check if the current theme is dark (convenience function)"""
    return IconHelper.is_dark_theme()


def refresh_theme_cache():
    """Refresh theme detection and icon cache (convenience function)"""
    IconHelper.refresh_theme_cache()
