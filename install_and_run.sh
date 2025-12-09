#!/bin/bash
# Install dependencies and run PDF Editor

echo "==================================="
echo "  PDF Editor - Setup & Run"
echo "==================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found: Python $python_version"
echo ""

# Install dependencies
echo "Installing dependencies..."
echo "This may take a few minutes..."
echo ""

pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Dependencies installed successfully!"
    echo ""
    echo "==================================="
    echo "  Starting PDF Editor..."
    echo "==================================="
    echo ""
    python3 src/main.py
else
    echo ""
    echo "❌ Error installing dependencies"
    echo "Please check the error messages above"
    echo ""
    echo "Try manually:"
    echo "  pip3 install PyQt6 PyMuPDF Pillow"
    exit 1
fi
