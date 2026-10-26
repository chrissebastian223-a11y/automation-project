@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo AUTONOVA AI - Windows 11
echo Using Existing Python Installation
echo ==========================================

set "PYTHON=py -3.11"

echo.
echo Checking PyTorch...
%PYTHON% -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.cuda.is_available())"

if errorlevel 1 (
    echo ERROR: PyTorch is not available in Python 3.11.
    pause
    exit /b 1
)

echo.
echo Checking project dependencies...
%PYTHON% -m pip install -r requirements.txt

if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo Starting AUTONOVA AI dashboard...
start "" http://127.0.0.1:8000

%PYTHON% -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo AUTONOVA AI stopped.
pause