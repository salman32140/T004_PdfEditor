from setuptools import setup, find_packages

setup(
    name="pdf_editor",
    version="1.0.0",
    description="Professional PDF Editor with full editing and annotation capabilities",
    author="PDF Editor Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "PyQt6>=6.6.0",
        "PyMuPDF>=1.23.0",
        "Pillow>=10.0.0",
    ],
    entry_points={
        "console_scripts": [
            "pdf-editor=main:main",
        ],
    },
    python_requires=">=3.8",
)
