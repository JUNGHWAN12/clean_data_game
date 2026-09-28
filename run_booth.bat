@echo off
rem Clean Data Labeler booth launcher.
rem - Runs the game in fullscreen booth mode.
rem - If the game crashes (non-zero exit code), it restarts after 3 seconds.
rem - If staff quits with Ctrl+Shift+Q (exit code 0), the launcher stops.
chcp 65001 > nul
cd /d "%~dp0"

:loop
if exist "CleanDataLabeler.exe" (
    "CleanDataLabeler.exe"
) else (
    "venv\Scripts\python.exe" main.py
)
if %errorlevel%==0 goto end
echo 게임이 예기치 않게 종료되었습니다. 3초 뒤 다시 시작합니다. (원인: error.log)
timeout /t 3 > nul
goto loop

:end
echo 진행 요원이 게임을 종료했습니다.
