@echo off
rem Clean Data Labeler booth launcher.
rem - Runs the game in fullscreen booth mode.
rem - If the game crashes (non-zero exit code), it restarts after 3 seconds.
rem - If staff quits with Ctrl+Shift+Q (exit code 0), the launcher stops.
rem - If card.json is broken (exit code 3), it shows a message instead of restarting.
chcp 65001 > nul
cd /d "%~dp0"

:loop
if exist "CleanDataLabeler.exe" (
    "CleanDataLabeler.exe"
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" main.py
) else (
    echo 실행할 게임을 찾지 못했습니다. CleanDataLabeler.exe 또는 venv 폴더가 이 폴더에 있는지 확인하세요.
    pause
    goto :eof
)
if %errorlevel%==0 goto end
if %errorlevel%==3 goto card_error
echo 게임이 예기치 않게 종료되었습니다. 3초 뒤 다시 시작합니다. (원인: error.log)
timeout /t 3 > nul
goto loop

:card_error
echo card.json 형식이 올바르지 않아 게임을 시작할 수 없습니다.
echo error.log 맨 아래에서 몇 번째 카드가 문제인지 확인해 고친 뒤 run_booth.bat을 다시 실행하세요.
pause
goto :eof

:end
echo 진행 요원이 게임을 종료했습니다.
