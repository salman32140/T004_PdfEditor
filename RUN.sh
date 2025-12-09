#!/bin/bash
# Quick run script for PDF Editor

# Check if dependencies are installed
if ! python3 -c "import PyQt6" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Generate demo PDF if it doesn't exist
if [ ! -f "demo/demo_document.pdf" ]; then
    echo "Generating demo PDF..."
    python3 demo/generate_demo.py
fi

# Run the application
echo "Starting PDF Editor..."
python3 src/main.py
