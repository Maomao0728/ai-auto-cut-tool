@echo off
chcp 65001 >nul
cd /d "%~dp0"
call conda activate ai_video
python gradio_app.py
pause
