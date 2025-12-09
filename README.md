# PDF Editor

A professional PDF editing application built with Python and PyQt6.

## Features

- **PDF Viewing**: Open, view, and navigate PDF documents with zoom controls and continuous/single page view modes
- **Drawing Tools**: Pen, rectangle, ellipse, line, and arrow tools for annotations
- **Text Fields**: Add and edit text with customizable fonts, sizes, colors, and styles
- **Image Insertion**: Insert and resize images with multiple scaling modes
- **Symbol Tool**: Insert unicode symbols with customizable size and color
- **Selection Tool**: Select, move, resize, and rotate multiple layers
- **Text Selection**: Select, copy, highlight, underline, and strikethrough PDF text
- **Layer Management**: Organize annotations with layer panel, visibility toggle, and z-ordering
- **Page Operations**: Insert, delete, duplicate, rotate, and reorder pages via drag-drop
- **Document Translation**: Translate PDF documents using local LLM (llama-cpp)
- **AI Assistant**: Chat with your PDF using local AI models
- **Multi-tab Support**: Work with multiple documents simultaneously
- **Undo/Redo**: Full history support for all operations
- **Export Options**: Save as PDF or export pages as images
- **Theme Support**: Automatic light/dark theme detection

## Requirements

- Python 3.10+
- PyQt6
- PyMuPDF (fitz)
- Pillow
- llama-cpp-python (for AI features)
- huggingface_hub (for model downloads)

## Installation

Run the setup script to create a conda environment with all dependencies:

```bash
chmod +x setup.sh
./setup.sh
```

## Usage

After installation, activate the environment and run the application:

```bash
conda activate pdf_editor
python src/main.py
```

Or use the provided run script:

```bash
./RUN.sh
```

## Project Structure

```
T004_pdf_editor/
├── src/
│   ├── main.py              # Application entry point
│   ├── core/                # Core functionality (PDF, layers, history)
│   ├── ui/                  # User interface components
│   ├── tools/               # Drawing and editing tools
│   ├── utils/               # Utility functions
│   └── resources/icons/     # SVG icons
├── setup.sh                 # Conda environment setup script
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## License

MIT License
