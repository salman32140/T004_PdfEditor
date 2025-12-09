@echo off
REM Quick run script for PDF Editor (Windows)

echo Checking dependencies...
python -c "import PyQt6" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo Checking for demo PDF...
if not exist "demo\demo_document.pdf" (
    echo Generating demo PDF...
    python demo\generate_demo.py
)

echo Starting PDF Editor...
python src\main.py
pause
