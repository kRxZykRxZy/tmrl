@echo off
setlocal
python -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%
python main.py
endlocal
