"""
Settings Management
Handles user preferences and configuration
"""
import json
import os
from typing import Dict, Any


class Settings:
    """Manages application settings"""

    def __init__(self, config_file: str = None):
        if config_file is None:
            # Default to user's home directory
            home = os.path.expanduser("~")
            config_dir = os.path.join(home, ".pdf_editor")
            os.makedirs(config_dir, exist_ok=True)
            config_file = os.path.join(config_dir, "settings.json")

        self.config_file = config_file
        self.settings = self.load()

    def load(self) -> Dict[str, Any]:
        """Load settings from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading settings: {e}")
                return self.get_defaults()
        return self.get_defaults()

    def save(self):
        """Save settings to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get_defaults(self) -> Dict[str, Any]:
        """Get default settings"""
        return {
            'tool_defaults': {
                'color': '#000000',
                'width': 2,
                'opacity': 1.0,
                'font_size': 12,
                'font_family': 'Arial'
            },
            'highlighter_defaults': {
                'color': '#FFFF00',
                'opacity': 0.4
            },
            'recent_files': [],
            'window': {
                'width': 1400,
                'height': 900
            },
            'zoom': {
                'default': 1.0,
                'min': 0.1,
                'max': 5.0
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        keys = key.split('.')
        value = self.settings

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """Set a setting value"""
        keys = key.split('.')
        current = self.settings

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value
        self.save()

    def get_all(self) -> Dict[str, Any]:
        """Get all settings"""
        return self.settings.copy()

    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        self.settings = self.get_defaults()
        self.save()

    def add_recent_file(self, file_path: str):
        """Add file to recent files list"""
        recent = self.get('recent_files', [])

        # Remove if already exists
        if file_path in recent:
            recent.remove(file_path)

        # Add to beginning
        recent.insert(0, file_path)

        # Keep only last 10
        recent = recent[:10]

        self.set('recent_files', recent)

    def get_recent_files(self) -> list:
        """Get recent files list"""
        return self.get('recent_files', [])
