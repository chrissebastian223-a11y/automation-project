@echo off
cd /d "%~dp0"
echo Python launcher:
where py
echo Python version:
py --version
echo NVIDIA driver (if installed):
nvidia-smi
echo If nvidia-smi is not recognized, check the NVIDIA driver installation.
pause
