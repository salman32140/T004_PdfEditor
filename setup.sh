#!/bin/bash

# PDF Editor - Conda Environment Setup Script
# This script creates a conda environment and installs all required dependencies

set -e

ENV_NAME="pdf_editor"
PYTHON_VERSION="3.11"

echo "=================================="
echo "PDF Editor - Environment Setup"
echo "=================================="

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "Error: conda is not installed or not in PATH"
    echo "Please install Miniconda or Anaconda first"
    exit 1
fi

# Remove existing environment if it exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "Removing existing '${ENV_NAME}' environment..."
    conda env remove -n ${ENV_NAME} -y
fi

# Create new conda environment
echo "Creating conda environment '${ENV_NAME}' with Python ${PYTHON_VERSION}..."
conda create -n ${ENV_NAME} python=${PYTHON_VERSION} -y

# Activate the environment
echo "Activating environment..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate ${ENV_NAME}

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install PyQt6 and related packages
echo "Installing PyQt6..."
pip install PyQt6>=6.6.0 PyQt6-Svg>=6.6.0

# Install PDF handling
echo "Installing PyMuPDF..."
pip install PyMuPDF>=1.23.0

# Install image processing
echo "Installing Pillow..."
pip install Pillow>=10.0.0

# Install AI/LLM dependencies
echo "Installing llama-cpp-python (this may take a while)..."
pip install llama-cpp-python>=0.2.0

echo "Installing huggingface_hub..."
pip install huggingface_hub>=0.20.0

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "To activate the environment, run:"
echo "  conda activate ${ENV_NAME}"
echo ""
echo "To run the PDF Editor, run:"
echo "  python src/main.py"
echo ""
