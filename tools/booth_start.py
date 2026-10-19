"""부스 시작(START_BOOTH.exe): Booth 폴더 맨 위에서 더블클릭하면 부스 런처를 켠다.

학생들이 CleanDataLabeler 폴더 안의 run_booth.bat을 찾지 않아도 되도록, run_booth.bat과 같은 일을 한다.
- CleanDataLabeler 폴더에 booth.json이 있으면 런처(--launcher), 없으면 클린 데이터 라벨러만 켠다.
- 진행 요원이 Ctrl+Shift+Q로 끄면(종료 코드 0) 끝낸다.
- card.json 형식 오류(종료 코드 3)는 다시 켜도 같으므로 안내 창을 띄우고 끝낸다.
- 그 밖의 오류로 꺼지면 3초 뒤 다시 켠다. 켜자마자 꺼지는 일이 5번 이어지면 안내 창을 띄우고 멈춘다.

빌드: python -m PyInstaller --onefile --windowed --name START_BOOTH tools/booth_start.py
표준 라이브러리만 쓰므로 실행 파일이 작고, 게임 폴더(_internal)가 따로 필요 없다.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

TITLE = "부스 시작"
CARD_ERROR_EXIT = 3        # main.py의 CARD_ERROR_EXIT와 같다
RESTART_DELAY = 3.0
QUICK_CRASH = 20.0         # 켠 뒤 이 시간 안에 오류로 꺼지면 '켜자마자 꺼짐'으로 센다
MAX_QUICK_CRASHES = 5

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
GAME_DIR = ROOT / "CleanDataLabeler"
GAME = GAME_DIR / ("CleanDataLabeler.exe" if sys.platform == "win32" else "CleanDataLabeler")


def message(text: str, error: bool = True):
    """콘솔 없는 실행 파일이므로 Windows 안내 창으로 알린다."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10 if error else 0x40)
    else:
        print(text)


def main() -> int:
    if not GAME.is_file():
        message(f"게임을 찾지 못했습니다.\n\n이 파일과 같은 폴더에 CleanDataLabeler 폴더가 있어야 합니다.\n찾은 위치: {GAME}")
        return 1
    command = [str(GAME)]
    if (GAME_DIR / "booth.json").is_file():
        command.append("--launcher")
    quick_crashes = 0
    while True:
        started = time.monotonic()
        try:
            code = subprocess.run(command, cwd=GAME_DIR).returncode
        except OSError as error:
            message(f"게임을 실행하지 못했습니다.\n\n{error}")
            return 1
        if code == 0:
            return 0
        if code == CARD_ERROR_EXIT:
            message("card.json 형식이 올바르지 않아 게임을 시작할 수 없습니다.\n\n"
                    "CleanDataLabeler 폴더의 error.log에서 몇 번째 카드가 문제인지 확인해 고친 뒤 다시 실행하세요.")
            return CARD_ERROR_EXIT
        quick_crashes = quick_crashes + 1 if time.monotonic() - started < QUICK_CRASH else 0
        if quick_crashes >= MAX_QUICK_CRASHES:
            message("게임이 켜자마자 계속 꺼집니다.\n\nCleanDataLabeler 폴더의 error.log를 확인하고 진행 요원(선생님)에게 알려 주세요.")
            return code
        time.sleep(RESTART_DELAY)


if __name__ == "__main__":
    sys.exit(main())
