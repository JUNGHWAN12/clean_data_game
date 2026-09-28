"""부스용 실행 파일(dist/CleanDataLabeler/CleanDataLabeler.exe)을 만든다.

만든 폴더(dist/CleanDataLabeler)를 통째로 부스 PC에 복사하면 Python 없이 실행된다.
card.json과 소리 파일은 exe 옆에 그대로 두므로, 부스에서도 카드 내용을 고칠 수 있다.

실행:
    uv pip install --python venv\\Scripts\\python.exe -r requirements-build.txt
    .\\venv\\Scripts\\python.exe tools\\build_exe.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "CleanDataLabeler"
OUT_DIR = ROOT / "dist" / NAME


def main():
    subprocess.run([
        sys.executable, "-m", "PyInstaller", str(ROOT / "main.py"),
        "--name", NAME,
        "--noconfirm", "--clean",
        "--windowed",                  # 검은 콘솔 창 없이 게임 화면만 띄운다
        "--debug", "noarchive",        # 코드를 exe 안에 묶지 않고 파일로 둔다(실행 중 백신이 exe를 잠가도 동작)
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
    ], check=True)

    # arcade용 PyInstaller 설정이 arcade/VERSION을 파일이 아닌 폴더(VERSION/VERSION)로 만들어
    # 실행 시 버전 경고가 난다. 원래 파일로 바로잡는다.
    version = OUT_DIR / "_internal" / "arcade" / "VERSION"
    if version.is_dir():
        inner = version / "VERSION"
        content = inner.read_bytes() if inner.exists() else b""
        shutil.rmtree(version)
        version.write_bytes(content)

    # 부스에서 고칠 수 있는 파일은 exe 옆에 둔다.
    shutil.copy2(ROOT / "card.json", OUT_DIR / "card.json")
    shutil.copy2(ROOT / "run_booth.bat", OUT_DIR / "run_booth.bat")
    shutil.copytree(ROOT / "assets", OUT_DIR / "assets", dirs_exist_ok=True)
    print(f"\n완료: {OUT_DIR}")
    print("이 폴더를 통째로 부스 PC에 복사한 뒤 run_booth.bat을 실행하세요.")


if __name__ == "__main__":
    main()
