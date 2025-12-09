#!/usr/bin/env python3
"""
PDF Editor - Professional PDF Editing Application
Main entry point
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui import MainWindow


def main():
    """Main entry point"""
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Editor")
    app.setOrganizationName("PDF Editor Team")

    # Apply style
    app.setStyle("Fusion")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
