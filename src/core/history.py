"""
Undo/Redo History System
Supports multi-step operations and snapshots
"""
from typing import Any, Dict, List, Optional
from enum import Enum
import json
import copy


class ActionType(Enum):
    """Types of actions that can be undone/redone"""
    ADD_LAYER = "add_layer"
    REMOVE_LAYER = "remove_layer"
    MODIFY_LAYER = "modify_layer"
    MOVE_LAYER = "move_layer"
    ADD_PAGE = "add_page"
    REMOVE_PAGE = "remove_page"
    ROTATE_PAGE = "rotate_page"
    MOVE_PAGE = "move_page"
    MODIFY_PAGE = "modify_page"


class Action:
    """Represents a single undoable action"""

    def __init__(self, action_type: ActionType, data: Dict[str, Any], description: str = ""):
        self.type = action_type
        self.data = data
        self.description = description or action_type.value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize action"""
        return {
            'type': self.type.value,
            'data': self.data,
            'description': self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Action':
        """Deserialize action"""
        return cls(
            ActionType(data['type']),
            data['data'],
            data['description']
        )


class HistoryManager:
    """Manages undo/redo history"""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.undo_stack: List[Action] = []
        self.redo_stack: List[Action] = []
        self.snapshot_interval = 10  # Take snapshot every N actions
        self.action_count = 0

    def add_action(self, action: Action):
        """Add an action to the history"""
        self.undo_stack.append(action)
        self.redo_stack.clear()  # Clear redo stack when new action is added

        # Limit history size
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

        self.action_count += 1

    def can_undo(self) -> bool:
        """Check if undo is available"""
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available"""
        return len(self.redo_stack) > 0

    def undo(self) -> Optional[Action]:
        """Undo the last action"""
        if not self.can_undo():
            return None

        action = self.undo_stack.pop()
        self.redo_stack.append(action)
        return action

    def redo(self) -> Optional[Action]:
        """Redo the last undone action"""
        if not self.can_redo():
            return None

        action = self.redo_stack.pop()
        self.undo_stack.append(action)
        return action

    def get_undo_description(self) -> str:
        """Get description of the action that would be undone"""
        if self.can_undo():
            return self.undo_stack[-1].description
        return ""

    def get_redo_description(self) -> str:
        """Get description of the action that would be redone"""
        if self.can_redo():
            return self.redo_stack[-1].description
        return ""

    def clear(self):
        """Clear all history"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.action_count = 0

    def get_history_info(self) -> Dict[str, Any]:
        """Get information about current history state"""
        return {
            'undo_count': len(self.undo_stack),
            'redo_count': len(self.redo_stack),
            'total_actions': self.action_count,
            'can_undo': self.can_undo(),
            'can_redo': self.can_redo()
        }


class DocumentState:
    """Represents a complete state of the document for snapshots"""

    def __init__(self, layers_data: Dict[str, Any], metadata: Dict[str, Any]):
        self.layers_data = copy.deepcopy(layers_data)
        self.metadata = copy.deepcopy(metadata)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state"""
        return {
            'layers_data': self.layers_data,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentState':
        """Deserialize state"""
        return cls(data['layers_data'], data['metadata'])


class SnapshotManager:
    """Manages document snapshots for major undo operations"""

    def __init__(self, max_snapshots: int = 20):
        self.max_snapshots = max_snapshots
        self.snapshots: List[DocumentState] = []

    def take_snapshot(self, layers_data: Dict[str, Any], metadata: Dict[str, Any]):
        """Take a snapshot of the current document state"""
        snapshot = DocumentState(layers_data, metadata)
        self.snapshots.append(snapshot)

        # Limit snapshot count
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots.pop(0)

    def get_latest_snapshot(self) -> Optional[DocumentState]:
        """Get the most recent snapshot"""
        if self.snapshots:
            return self.snapshots[-1]
        return None

    def restore_snapshot(self, index: int = -1) -> Optional[DocumentState]:
        """Restore a snapshot"""
        if 0 <= index < len(self.snapshots) or -len(self.snapshots) <= index < 0:
            return self.snapshots[index]
        return None

    def clear(self):
        """Clear all snapshots"""
        self.snapshots.clear()

    def get_snapshot_count(self) -> int:
        """Get number of snapshots"""
        return len(self.snapshots)
