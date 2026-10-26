@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
 echo Run START_WINDOWS.bat once first.
 pause
 exit /b 1
)
call ".venv\Scripts\activate.bat"
echo.
echo Install Ultralytics and optional OCR. CUDA-enabled PyTorch may need a separate install
echo using the official PyTorch selector: https://pytorch.org/get-started/locally/
python -m pip install ultralytics easyocr
if errorlevel 1 (
 echo AI dependency installation failed. Read the error above.
 pause
 exit /b 1
)
echo AI packages installed. Verify CUDA in the dashboard before relying on GPU.
pause
