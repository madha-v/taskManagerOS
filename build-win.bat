@echo off
pip install pyinstaller
pyinstaller --onefile --windowed --icon=app_icon.ico --name mini_task_manager main.py
echo Build finished. Check the dist\mini_task_manager folder
pause
