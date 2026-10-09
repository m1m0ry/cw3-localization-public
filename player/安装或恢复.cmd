@echo off
chcp 65001 >nul
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
echo Python 3.10 or later is required. No additional Python packages are needed.
echo Install Python, then run this file again.
set "cw3_exit_code=1"
goto done
:use_py
py -3 "%~dp0install.py"
set "cw3_exit_code=%errorlevel%"
goto done
:use_python
python "%~dp0install.py"
set "cw3_exit_code=%errorlevel%"
:done
pause
exit /b %cw3_exit_code%
