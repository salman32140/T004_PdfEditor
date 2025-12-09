"""
Guide Manager for non-printing guides
Manages horizontal and vertical guides that serve as visual workspace references
"""
from PyQt6.QtCore import QObject, pyqtSignal
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class GuideOrientation(Enum):
    HORIZONTAL = "horizontal"  # Horizontal line (created from horizontal ruler, has Y position)
    VERTICAL = "vertical"      # Vertical line (created from vertical ruler, has X position)


@dataclass
class Guide:
    """Represents a single guide line"""
    orientation: GuideOrientation
    position: float  # Position in page points (not screen pixels)
    page_num: int    # Which page this guide belongs to (-1 for all pages)
    locked: bool = False

    def __hash__(self):
        return hash((self.orientation, self.position, self.page_num))


class GuideManager(QObject):
    """Manages all guides in the document"""

    guides_changed = pyqtSignal()  # Emitted when guides are added, removed, or modified

    def __init__(self, parent=None):
        super().__init__(parent)
        self._guides: List[Guide] = []
        self._all_locked = False  # Global lock for all guides
        self._selected_guide: Optional[Guide] = None

    @property
    def guides(self) -> List[Guide]:
        return self._guides

    @property
    def all_locked(self) -> bool:
        return self._all_locked

    @all_locked.setter
    def all_locked(self, value: bool):
        self._all_locked = value
        self.guides_changed.emit()

    @property
    def selected_guide(self) -> Optional[Guide]:
        return self._selected_guide

    @selected_guide.setter
    def selected_guide(self, guide: Optional[Guide]):
        self._selected_guide = guide
        self.guides_changed.emit()

    def add_guide(self, orientation: GuideOrientation, position: float, page_num: int = -1) -> Guide:
        """Add a new guide

        Args:
            orientation: HORIZONTAL or VERTICAL
            position: Position in page points
            page_num: Page number (-1 for global guide visible on all pages)

        Returns:
            The created Guide object
        """
        guide = Guide(orientation=orientation, position=position, page_num=page_num)
        self._guides.append(guide)
        self.guides_changed.emit()
        return guide

    def remove_guide(self, guide: Guide) -> bool:
        """Remove a guide

        Args:
            guide: The guide to remove

        Returns:
            True if guide was removed, False if not found
        """
        if guide in self._guides:
            self._guides.remove(guide)
            if self._selected_guide == guide:
                self._selected_guide = None
            self.guides_changed.emit()
            return True
        return False

    def move_guide(self, guide: Guide, new_position: float) -> bool:
        """Move a guide to a new position

        Args:
            guide: The guide to move
            new_position: New position in page points

        Returns:
            True if guide was moved, False if locked or not found
        """
        if self._all_locked or guide.locked:
            return False

        if guide in self._guides:
            guide.position = new_position
            self.guides_changed.emit()
            return True
        return False

    def toggle_guide_lock(self, guide: Guide) -> bool:
        """Toggle the lock state of a guide

        Args:
            guide: The guide to toggle

        Returns:
            New lock state
        """
        if guide in self._guides:
            guide.locked = not guide.locked
            self.guides_changed.emit()
            return guide.locked
        return False

    def get_guides_for_page(self, page_num: int) -> List[Guide]:
        """Get all guides visible on a specific page

        Args:
            page_num: Page number (0-indexed)

        Returns:
            List of guides for the page (including global guides)
        """
        return [g for g in self._guides if g.page_num == -1 or g.page_num == page_num]

    def get_horizontal_guides(self, page_num: int = -1) -> List[Guide]:
        """Get horizontal guides, optionally filtered by page"""
        guides = self._guides if page_num == -1 else self.get_guides_for_page(page_num)
        return [g for g in guides if g.orientation == GuideOrientation.HORIZONTAL]

    def get_vertical_guides(self, page_num: int = -1) -> List[Guide]:
        """Get vertical guides, optionally filtered by page"""
        guides = self._guides if page_num == -1 else self.get_guides_for_page(page_num)
        return [g for g in guides if g.orientation == GuideOrientation.VERTICAL]

    def clear_all_guides(self):
        """Remove all guides"""
        self._guides.clear()
        self._selected_guide = None
        self.guides_changed.emit()

    def clear_page_guides(self, page_num: int):
        """Remove all guides for a specific page"""
        self._guides = [g for g in self._guides if g.page_num != page_num]
        if self._selected_guide and self._selected_guide.page_num == page_num:
            self._selected_guide = None
        self.guides_changed.emit()

    def find_guide_at_position(self, orientation: GuideOrientation, position: float,
                                page_num: int, tolerance: float = 5.0) -> Optional[Guide]:
        """Find a guide at or near a given position

        Args:
            orientation: Type of guide to look for
            position: Position to search at (in page points)
            page_num: Current page number
            tolerance: How close (in points) the position needs to be

        Returns:
            Guide if found within tolerance, None otherwise
        """
        for guide in self.get_guides_for_page(page_num):
            if guide.orientation == orientation:
                if abs(guide.position - position) <= tolerance:
                    return guide
        return None

    def is_guide_locked(self, guide: Guide) -> bool:
        """Check if a guide is locked (either individually or globally)"""
        return self._all_locked or guide.locked


# Singleton instance for easy access
_guide_manager_instance: Optional[GuideManager] = None


def get_guide_manager() -> GuideManager:
    """Get the global GuideManager instance"""
    global _guide_manager_instance
    if _guide_manager_instance is None:
        _guide_manager_instance = GuideManager()
    return _guide_manager_instance


def reset_guide_manager():
    """Reset the guide manager (useful for testing or new documents)"""
    global _guide_manager_instance
    if _guide_manager_instance:
        _guide_manager_instance.clear_all_guides()
    _guide_manager_instance = GuideManager()
    return _guide_manager_instance
