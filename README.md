# 클린 데이터 라벨러

기획서 `기획.md`를 바탕으로 만든 Python + Arcade 교육형 타이쿤 게임 프로토타입입니다.
게임 창 해상도는 표준 16:9인 1920×1080이며, UI는 화면 전체에 확대 표시됩니다.

카드 데이터는 `card.json`에서 불러옵니다. 카드 내용을 추가하거나 수정한 뒤 게임을 다시 실행하면 자동으로 반영됩니다. 실행 시 필수 필드와 `difficulty(1~3)`, `penalty(0 이상)` 등의 형식도 검사합니다.

## 실행

PowerShell에서 프로젝트 폴더를 연 뒤 실행합니다.

uv를 사용하면 Python 3.12가 없는 환경에서도 필요한 버전을 설치할 수 있습니다.

```powershell
uv python install 3.12
uv venv --python 3.12
uv pip install -r requirements.txt
uv run --python 3.12 main.py
```

프로젝트의 `.python-version` 파일에 Python 3.12가 지정되어 있어 uv가 프로젝트 버전을 자동으로 인식합니다.

```powershell
.\venv\Scripts\python.exe main.py
```

Arcade가 설치되지 않은 새 환경이라면 다음을 먼저 실행합니다.

```powershell
pip install -r requirements.txt
```

## 조작

- 메뉴: `SPACE` 또는 `ENTER`로 시작, `T`로 튜토리얼
- 튜토리얼: 1페이지에서 `SPACE` / `ENTER` / `→`로 업그레이드 설명 보기, `←`로 이전 페이지
- 게임: 컨베이어 카드 클릭 → 키보드 숫자열 또는 숫자 키패드 `1 승인` / `2 정제` / `3 제외`
- 업그레이드: `Q` 워터마크 스캐너, `W` 개인정보 탐지기, `E` 편향 감지기
- 결과 화면: `R` 재시작, `ESC` 메뉴

카드가 오른쪽 AI 학습 서버에 도착하면 승인으로 자동 처리됩니다. 위험 데이터를 승인하면 안전 지표가 크게 떨어지므로 카드의 출처와 라이선스를 함께 확인해야 합니다.
