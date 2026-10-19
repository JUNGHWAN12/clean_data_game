"""클린 데이터 라벨러 - Arcade 기반 교육형 타이쿤 프로토타입.

실행:
    .\\venv\\Scripts\\python.exe main.py
"""

from __future__ import annotations

import random
import datetime
import sys
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import arcade
import traceback
from arcade.camera import Camera2D
from arcade.types.rect import LBWH, LRBT


# 게임 파일(card.json, assets, ranking.json)이 있는 폴더.
# 실행 파일(.exe)로 만들면 exe 옆 폴더를, 파이썬으로 실행하면 main.py 폴더를 쓴다.
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
# 게임 UI는 논리 좌표계에서 그린 뒤 표준 16:9 화면 전체에 맞춰 표시한다.
UI_WIDTH = 1280
UI_HEIGHT = 800
SCREEN_TITLE = "클린 데이터 라벨러"
# 프로젝트 정책: 카드 정답은 모두 이 이용 목적(교육용·비상업)을 기준으로 정해져 있다.
PROJECT_NAME = "학교 수업용 AI 학습 도우미"
PROJECT_POLICY = "교육용 · 비상업"
# card.json의 점수 값을 기획서 점수 규모로 환산하는 배율
SCORE_SCALE = 10
PENALTY_SCALE = 12
# 글꼴: assets/fonts의 IBM Plex Sans KR(SIL OFL 1.1)을 게임과 함께 배포해 부스 PC에 설치하지 않아도 같은 모양으로 보인다.
# 글꼴 파일이 없으면 Windows 기본 한글 글꼴(맑은 고딕)로 그린다.
FONT_DIR = APP_DIR / "assets" / "fonts"
FONT_FILES = ("IBMPlexSansKR-Regular.ttf", "IBMPlexSansKR-Bold.ttf")
FONT = ("IBM Plex Sans KR", "Malgun Gothic", "맑은 고딕", "Arial")

BG = (10, 16, 31)
PANEL = (20, 29, 49)
PANEL_LIGHT = (28, 40, 65)
WHITE = (239, 244, 255)
MUTED = (151, 166, 194)
CYAN = (67, 220, 216)
GREEN = (77, 218, 145)
YELLOW = (255, 194, 77)
RED = (255, 103, 119)
PURPLE = (182, 126, 255)
BLUE = (89, 170, 255)
ORANGE = (255, 145, 83)


# 자동화 도구: (종류, 단축키, 이름, 비용, 버튼 왼쪽 x, 버튼 아래 y). 그리기와 클릭 판정에 함께 쓴다.
UPGRADES = [
    ("watermark", "Q", "워터마크 스캐너", 300, 814, 156),
    ("privacy", "W", "개인정보 탐지기", 400, 1018, 156),
    ("bias", "E", "편향 감지기", 600, 814, 124),
    ("buffer", "R", "데이터 버퍼 확장", 450, 1018, 124),
    ("license", "A", "라이선스 확인 봇", 500, 814, 92),
    ("deid", "S", "자동 비식별화", 700, 1018, 92),
    ("ai_approve", "D", "AI 자동 승인 모델", 800, 814, 60),
    ("ai_assist", "F", "AI 판단 도우미", 1000, 1018, 60),
]
UPGRADE_WIDTH = 196
UPGRADE_HEIGHT = 28
AI_APPROVE_CHANCE = 0.4    # 안전한 카드 중 AI 자동 승인 모델이 맡는 비율
SOUND_DIR = APP_DIR / "assets" / "sounds"   # tools/make_sounds.py로 만든 소리
SOUND_NAMES = ("correct", "combo", "wrong", "server_error", "buy", "select", "end", "bgm", "bgm_fast")
BGM_VOLUME = 0.35
RUSH_TIME = 10.0       # 마지막 10초: 빠른 배경음으로 바꾼다
IDLE_RETURN = {"result": 40.0, "review": 40.0, "tutorial": 60.0, "paused": 60.0, "idle_paused": 20.0}   # 부스: 방치되면 메뉴로 돌아가는 시간(초)
ROUND_TIME = 180.0     # 기본 한 판 시간(초). 단계·속도 설계의 기준
SHORT_ROUND = 90.0     # 짧은 체험 모드(F7) 한 판 시간
ATTRACT_IDLE = 30.0    # 메뉴가 이 시간 동안 방치되면 대기 화면(소개 슬라이드)을 보여준다
ATTRACT_SLIDE = 7.0    # 대기 화면 슬라이드 한 장의 시간
REVIEW_COUNT = 3       # 오답 복습에서 보여줄 카드 수
NOTICE_TIME = 2.5      # 진행 요원 키 안내 문구 표시 시간
TUTORIAL_PAGES = 3
GAME_IDLE = 45.0       # 게임 중 이 시간 동안 입력이 없으면 자리를 떠난 것으로 보고 일시정지한다
# 3분 라운드 단계(기획서 6.2): (시작 초, 이름, 안내, 등장 난이도 상한, 자주 나오는 위험 유형)
PHASES = [
    (0, "적응 단계", "위험 신호가 자동으로 보입니다", 1, None),
    (25, "기본 검수", "저작권·개인정보 카드가 늘어납니다", 2, ("copyright", "privacy")),
    (60, "혼합 데이터", "한 카드에 여러 문제가 섞여 나옵니다", 3, ("mixed",)),
    (100, "편향 관리", "편향된 문장과 잘못된 라벨을 찾아보세요", 3, ("bias",)),
    (140, "고속 처리", "카드가 더 빨리 들어옵니다", 3, None),
    (170, "데이터 러시", "보너스 카드(점수 2배)가 빠르게 들어옵니다", 3, None),
]
PREFER_CHANCE = 0.5    # 단계별 위험 유형 카드를 우선 뽑을 확률
FAST_SPAWN = 4.0       # 고속 처리 단계의 카드 간격(초)
RUSH_SPAWN = 2.5       # 데이터 러시 단계의 카드 간격(초)
BONUS_MULTIPLIER = 2   # 데이터 러시 보너스 카드 점수 배율
PHASE_TOAST_TIME = 2.5
# 컨베이어 카드 크기: 부스 뒤쪽 관람객도 읽을 수 있도록 카드와 글자를 크게 그린다.
CARD_HALF = 92          # 카드 폭의 절반(카드 폭 184)
CARD_BOTTOM, CARD_TOP = 478, 632
CARD_GAP = 18           # 카드 사이 여백
CARD_START_X = 140.0    # 새 카드가 나오는 위치(카드 가운데)
SERVER_X = 1155         # AI 서버 영역의 왼쪽 끝
# 연타 방지: 처리·선택 직후 잠시 처리 입력(1·2·3 키, 처리 버튼)을 받지 않는다(초).
LOCK_AFTER_PROCESS = 0.5
LOCK_AFTER_AUTO_SELECT = 0.8
LOCK_AFTER_SELECT = 0.4

# 오늘의 랭킹: 등급이 먼저, 같은 등급이면 점수 순. 빠른 AI보다 믿을 수 있는 AI가 위에 온다.
RANK_FILE = APP_DIR / "ranking.json"
RANK_SIZE = 10
RANK_RELOAD = 5.0       # 랭킹 파일을 다시 읽는 간격(초). 매 프레임 읽으면 기록이 쌓일수록 화면이 끊긴다.
NAME_LENGTH = 3
NAME_IDLE = 30.0       # 이니셜 입력을 방치하면 저장하지 않고 결과 화면으로 넘어간다
# 랭킹판에 올릴 수 없는 이니셜. 입력한 영문 3글자와 정확히 같으면 저장하지 않는다.
# 부스의 세 게임(클린 데이터 라벨러, 데이터 패킷 러너 등)이 같은 목록을 쓴다.
BLOCKED_NAMES = {
    # 영어 욕설·비속어
    "FUK", "FUC", "FCK", "FKU", "FKN", "FUQ", "FUX", "WTF", "STF", "GTF", "FFS", "FML", "MFR",
    "SHT", "BCH", "ASS", "AZZ", "SOB",
    "FUU", "CNT", "DMN", "PIS", "POS", "SUX",
    # 성적 표현
    "SEX", "SXY", "XXX", "CUM", "TIT", "PNS", "VAG", "DIK", "DIC", "COK", "COC", "SUK",
    "DCK", "JIZ", "ANL", "FAP", "DTF", "SLT", "PRN", "POR", "NUD", "HOE", "PUS",
    "SXE", "KUM", "TTS",
    # 혐오·차별 표현
    "FAG", "NIG", "NGR", "NGA", "KKK", "NZI", "NAZ", "JAP", "CNK", "GOK", "RTD", "HTL", "GAY", "LES",
    "FGT", "WHR",
    # 자해·폭력
    "KYS", "KMS", "DIE", "KIL",
    # 화장실 말
    "PEE", "POO",
    # 한국어 욕설의 로마자 약어
    "SIB", "SIP", "SBL", "SSB", "CBL", "GSK", "GSE", "BYS", "BSN", "MCN", "JNA", "JOT", "JOS",
    "JRL", "YMB", "NGM", "NOM", "YMN", "JMT", "ILB",
    "SSI", "MCS", "NGB", "DRI", "EMI",
    # 한글 자판 위치로 친 욕설: 한글 자판대로 '시발'을 치면 영문 TLQKF가 입력되어 앞 3글자 TLQ가 된다.
    "TLQ", "QUD", "WHS", "WHW", "RJW", "EKR", "TPR", "QHW", "WKW",
    "ROT", "TOR", "ALC", "WLF", "DOA", "WHF", "SUS", "QUS", "DUT", "QKQ",
    "WJW", "HHH", "EHD",
}
GRADE_ORDER = "SABCD"
GRADE_COLORS = {"S": GREEN, "A": CYAN, "B": YELLOW, "C": ORANGE, "D": RED}
GOOD_METRIC = 70       # 결과 화면 AI 결과물이 '안전'으로 나오는 지표 기준

ADAPT_TIME = 25.0      # 적응 단계: 이 시간 안에 나온 카드는 도구 없이도 위험 신호를 보여준다
AI_ASSIST_ACCURACY = 0.85  # AI 판단 도우미의 추천이 정답일 확률

# 라이선스 확인 봇: 라이선스 문구의 키워드로 이용 조건을 한 줄 요약한다. 위에서부터 먼저 맞는 규칙을 쓴다.
LICENSE_RULES = [
    (("CC0", "퍼블릭 도메인", "공공영역", "공공저작물"), "권리 제한 없음, 자유 이용"),
    (("공공누리 1유형",), "출처 표시하면 자유롭게 이용 가능"),
    (("BY-NC",), "비상업·교육 목적만 이용 가능"),
    (("BY-ND",), "변경 금지, 원본 그대로만"),
    (("BY-SA",), "출처 표시 + 같은 조건 공유"),
    (("CC BY",), "저작자 표시하면 이용 가능"),
    (("MIT",), "고지문 유지하면 이용 가능"),
    (("GPL",), "파생물도 GPL로 공개 필요"),
    (("ODbL",), "출처 표시·동일 조건 공유"),
    (("없음",), "이용·수집 허가가 없음"),
    (("불명",), "허가 여부를 확인할 수 없음"),
    (("비공개", "개인 ", "만료", "삭제 요청", "보호", "홍보용"), "학습 이용 범위를 벗어남"),
    (("인용",), "필요한 부분만 출처와 인용"),
    (("허가", "승인", "동의", "이용권", "소유", "허용"), "허가 범위 안에서 이용 가능"),
]
SOURCE_RULES = [
    (("unknown", "온라인", "검색", "비공식", "커뮤니티", "SNS", "블로그", "댓글"), "출처 신뢰 낮음", RED),
    (("공공", "공식", "국가", "지방자치", "오픈액세스", "공개 연구"), "공식 출처", GREEN),
    (("학생", "교사", "학급", "직접"), "직접 제작·수집", CYAN),
]


def license_summary(license_text: str) -> str:
    for keywords, summary in LICENSE_RULES:
        if any(k in license_text for k in keywords):
            return summary
    return "조건을 직접 확인해야 함"


def source_note(source: str):
    for keywords, note, color in SOURCE_RULES:
        if any(k in source for k in keywords):
            return note, color
    return None
# 위험 신호는 해당 탐지 도구를 구입해야 카드에 표시된다.
RISK_TOOLS = {"copyright": "watermark", "privacy": "privacy", "bias": "bias"}
RISK_LABELS = {"safe": "안전 데이터", "copyright": "저작권 확인 필요",
               "privacy": "개인정보 확인 필요", "bias": "편향 확인 필요", "mixed": "복합 확인 필요"}


def josa(word: str, with_final: str, without_final: str) -> str:
    """받침 유무에 맞는 조사를 붙인다. 예: josa('정제', '으로', '로') -> '정제로'"""
    last = word[-1]
    if not "가" <= last <= "힣":
        return word + without_final
    final = (ord(last) - ord("가")) % 28
    # '으로/로'는 받침이 없거나 ㄹ 받침이면 '로'를 쓴다.
    has_final = final not in (0, 8) if with_final == "으로" else final != 0
    return word + (with_final if has_final else without_final)


def load_fonts():
    for name in FONT_FILES:
        try:
            arcade.load_font(FONT_DIR / name)
        except Exception:
            pass  # 글꼴 파일이 없거나 읽지 못하면 FONT의 다음 글꼴을 쓴다.


def disable_ime(window: arcade.Window):
    """한글 입력 상태(한/영 키)에서도 영문 단축키(Q·W·E·R, T, M, 이니셜 등)가 동작하도록 창의 IME를 끈다.

    Windows는 한글 입력 상태에서 영문 키를 IME가 가로채 게임에 다른 키 코드를 보내므로,
    방문객이 한/영 키를 눌러도 단축키가 막히지 않게 한다.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        associate = ctypes.windll.imm32.ImmAssociateContext
        associate.argtypes = (wintypes.HWND, wintypes.HANDLE)
        associate.restype = wintypes.HANDLE
        for hwnd in (getattr(window, "_hwnd", None), getattr(window, "_view_hwnd", None)):
            if hwnd:
                associate(hwnd, None)
    except Exception:
        pass  # IME를 끄지 못해도 게임은 계속한다. 이때는 한/영 키를 영문으로 맞춘다.


def rect(left: float, bottom: float, right: float, top: float, color):
    arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, color)


def outline(left: float, bottom: float, right: float, top: float, color, width=2):
    arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, color, width)


TEXT_CACHE_SIZE = 3000
_TEXT_CACHE: dict = {}


def label(text: str, x: float, y: float, size: float = 16, color=WHITE,
          anchor_x: str = "left", anchor_y: str = "baseline", bold=False):
    # 논리 좌표계에서 그린 글자를 확대하면 흐려지므로, 글자만 실제 창 해상도로 직접 그린다.
    window = arcade.get_window()
    window.default_camera.use()
    scale_x, scale_y = window.width / UI_WIDTH, window.height / UI_HEIGHT
    # 글자 크기는 가로·세로 배율 중 작은 쪽을 따른다. 16:9보다 좁은 모니터(4:3, 5:4)에서도 글자가 상자 밖으로 넘치지 않는다.
    font_scale = min(scale_x, scale_y)
    position = (x * scale_x, y * scale_y)
    # 위치는 저장 기준에서 빼서, 움직이는 카드의 글자도 같은 객체를 옮겨 다시 쓴다.
    key = (str(text), size, tuple(color), anchor_x, anchor_y, bold, window.width, window.height)
    text_object = _TEXT_CACHE.get(key)
    if text_object is None:
        # Text 객체를 만드는 데는 그리는 것보다 수십 배 오래 걸리므로, 한 번 만든 글자는 저장해 다시 쓴다.
        text_object = arcade.Text(str(text), position[0], position[1], color, size * font_scale,
                                  font_name=FONT, anchor_x=anchor_x, anchor_y=anchor_y, bold=bold)
        if len(_TEXT_CACHE) >= TEXT_CACHE_SIZE:
            _TEXT_CACHE.pop(next(iter(_TEXT_CACHE)))  # 가장 오래된 글자부터 버린다.
        _TEXT_CACHE[key] = text_object
    elif text_object.position != position:
        text_object.position = position
    text_object.draw()
    window.camera.use()


def wrapped(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for original_word in paragraph.split(" "):
            word = original_word
            # 공백이 없는 긴 한국어 단어도 박스 너비를 넘지 않도록 자른다.
            while len(word) > max_chars:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:max_chars])
                word = word[max_chars:]
            if not word:
                continue
            candidate = word if not current else f"{current} {word}"
            if len(candidate) > max_chars and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines or [""]


def compact_card_title(text: str, max_chars: int = 10, max_lines: int = 2) -> list[str]:
    """작은 큐 카드 안에 제목을 2줄 이내로 표시하고 넘치는 부분은 생략한다."""
    lines = wrapped(text, max_chars)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:max_chars - 1] + "…"
    return lines


def wrapped_label(text: str, x: float, y: float, max_chars: int, size=15,
                 color=WHITE, line_gap=23, max_lines: Optional[int] = None):
    lines = wrapped(text, max_chars)
    if max_lines:
        lines = lines[:max_lines]
    for index, line in enumerate(lines):
        label(line, x, y - index * line_gap, size, color)


@dataclass
class DataCard:
    title: str
    content_type: str
    source: str
    license: str
    risk_types: tuple[str, ...]
    correct_action: str
    explanation: str
    reward: int
    penalty: int
    difficulty: int
    age: float = 0.0
    x: float = 95.0
    ai_approve: bool = False         # AI 자동 승인 모델이 대신 승인할 카드
    ai_pick: Optional[str] = None    # AI 판단 도우미의 추천 행동(틀릴 수 있음)
    hinted: bool = False             # 적응 단계에 나와 위험 신호를 자동으로 보여줄 카드
    bonus: bool = False              # 데이터 러시 단계의 점수 2배 카드

    @property
    def risk_key(self) -> str:
        if len(self.risk_types) > 1:
            return "mixed"
        return self.risk_types[0]

    @property
    def risk_label(self) -> str:
        # 위험 신호는 '확인할 항목'을 알려줄 뿐, 조건을 갖춘 데이터는 승인이 정답일 수 있다.
        return RISK_LABELS[self.risk_key]

    @property
    def risk_color(self):
        return {"safe": GREEN, "copyright": RED, "privacy": BLUE,
                "bias": PURPLE, "mixed": ORANGE}[self.risk_key]


# 부스 PC별 설정: PC 이름(랭킹판에 표시)과 런처에서 고를 게임 목록. 없으면 런처 없이 이 게임만 쓴다.
BOOTH_FILE = APP_DIR / "booth.json"
PC_NAME_LENGTH = 8
LAUNCHER_GAMES = 3


def load_booth_config() -> dict:
    """booth.json을 읽는다. 없거나 형식이 틀리면 빈 설정을 돌려준다."""
    try:
        with BOOTH_FILE.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    pc_name = data.get("pc_name")
    games = data.get("games")
    return {
        "pc_name": pc_name.strip()[:PC_NAME_LENGTH] if isinstance(pc_name, str) else "",
        "games": [g for g in games if isinstance(g, dict)][:LAUNCHER_GAMES] if isinstance(games, list) else [],
    }


CARD_FILE = APP_DIR / "card.json"
CARD_ERROR_EXIT = 3   # card.json 형식 오류로 끝날 때의 종료 코드(run_booth.bat이 보고 다시 켜지 않는다)
REQUIRED_CARD_FIELDS = {
    "title", "content_type", "source", "license", "risk_types",
    "correct_action", "explanation", "reward", "penalty", "difficulty",
}
VALID_RISK_TYPES = {"safe", "copyright", "privacy", "bias"}
VALID_ACTIONS = {"approve", "refine", "remove"}
# card.json 제목 앞의 카드 번호("001 ")는 카드를 찾고 관리하기 위한 것이라 화면에는 보여주지 않는다.
TITLE_NUMBER = re.compile(r"^\d+\s+")


def load_card_deck() -> list[DataCard]:
    """card.json을 읽어 게임에서 사용할 DataCard 목록으로 변환한다."""
    if not CARD_FILE.exists():
        raise FileNotFoundError(f"카드 파일을 찾을 수 없습니다: {CARD_FILE}")

    with CARD_FILE.open("r", encoding="utf-8-sig") as file:
        raw_cards = json.load(file)

    if not isinstance(raw_cards, list) or not raw_cards:
        raise ValueError("card.json은 하나 이상의 카드 객체를 담은 배열이어야 합니다.")

    loaded_cards: list[DataCard] = []
    for index, item in enumerate(raw_cards, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"card.json의 {index}번째 카드가 객체가 아닙니다.")
        missing = REQUIRED_CARD_FIELDS - item.keys()
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"card.json의 {index}번째 카드에 필드가 없습니다: {names}")

        risks = item["risk_types"]
        if not isinstance(risks, list) or not risks or not set(risks) <= VALID_RISK_TYPES:
            raise ValueError(f"card.json의 {index}번째 카드의 risk_types가 올바르지 않습니다.")
        if item["correct_action"] not in VALID_ACTIONS:
            raise ValueError(f"card.json의 {index}번째 카드의 correct_action이 올바르지 않습니다.")

        try:
            difficulty = int(item["difficulty"])
            reward = int(item["reward"])
            penalty = int(item["penalty"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"card.json의 {index}번째 카드의 숫자 필드가 올바르지 않습니다.") from error
        if difficulty not in (1, 2, 3) or reward < 0 or penalty < 0:
            raise ValueError(f"card.json의 {index}번째 카드의 difficulty/reward/penalty 값이 올바르지 않습니다.")

        loaded_cards.append(DataCard(
            title=TITLE_NUMBER.sub("", str(item["title"])) or str(item["title"]),
            content_type=str(item["content_type"]),
            source=str(item["source"]),
            license=str(item["license"]),
            risk_types=tuple(risks),
            correct_action=item["correct_action"],
            explanation=str(item["explanation"]),
            reward=reward,
            penalty=penalty,
            difficulty=difficulty,
        ))
    return loaded_cards


class CleanDataGame(arcade.Window):
    def __init__(self, card_deck: list[DataCard], fullscreen: bool = False, booth: bool = False,
                 from_launcher: bool = False):
        load_fonts()
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, resizable=False, fullscreen=fullscreen)
        disable_ime(self)
        # card.json의 카드를 게임 덱으로 사용한다.
        self.card_deck = card_deck
        # 부스 모드에서는 Alt+F4나 창 닫기로 꺼지지 않고, 진행 요원 키(Ctrl+Shift+Q)로만 종료한다.
        self.booth = booth
        # 런처에서 실행하면 메뉴의 ESC로 게임 선택 화면(런처)에 돌아간다.
        self.from_launcher = from_launcher
        self.pc_name = load_booth_config().get("pc_name", "")
        self.allow_close = not booth
        self.idle_paused = False
        self.name_warning = ""
        self.round_length = ROUND_TIME
        self.attract_time = 0.0
        self.notice = ""
        self.notice_timer = 0.0
        self.mistakes: list = []
        arcade.set_background_color(BG)
        self.camera = Camera2D(
            # 전체 16:9 화면을 사용해 좌우 레터박스를 제거한다.
            viewport=LBWH(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT),
            projection=LRBT(0, UI_WIDTH, 0, UI_HEIGHT),
            # projection을 (0, 0) 원점으로 사용하므로 카메라 이동은 없다.
            position=(0, 0),
            window=self,
        )
        self.fit_camera()
        self.idle_time = 0.0
        self.sound_on = True
        self.bgm_player = None
        self.bgm_name: Optional[str] = None
        self.sounds = {}
        for name in SOUND_NAMES:
            try:
                self.sounds[name] = arcade.load_sound(SOUND_DIR / f"{name}.wav")
            except Exception:
                pass  # 소리 파일이나 오디오 장치가 없어도 게임은 계속한다.
        self.game_screen = "menu"
        self.tutorial_page = 0
        self.cards: list[DataCard] = []
        self.selected: Optional[DataCard] = None
        self.deck: list[DataCard] = []
        self.deck_index = 0
        self.spawn_timer = 0.0
        self.elapsed = 0.0
        self.time_left = 180.0
        self.score = 0
        self.budget = 0
        self.combo = 0
        self.max_combo = 0
        self.processed = 0
        self.correct = 0
        self.wrong_approved = 0
        self.normal_loss = 0
        self.wrong_method = 0
        self.unreviewed = 0
        self.last_result = None
        self.paused = False
        self.phase_shown = 0
        self.phase_toast = 0.0
        self.action_lock = 0.0
        self.name_input = ""
        self.last_rank: Optional[int] = None
        self.rank_cache: Optional[tuple] = None   # (날짜, 읽은 시각, 오늘의 TOP 10)
        self.privacy_leaks = 0
        self.copyright_issues = 0
        self.bias_issues = 0
        self.metrics = {"copyright": 100.0, "privacy": 100.0, "fairness": 100.0}
        self.upgrades: set[str] = set()
        self.feedback = "카드를 클릭해 상세 정보를 확인하세요."
        self.feedback_color = MUTED
        self.feedback_timer = 0.0

    def on_close(self):
        if self.allow_close:
            super().on_close()

    def staff_quit(self):
        self.allow_close = True
        self.set_bgm(None)
        self.close()

    def fit_camera(self):
        """게임 화면(1280×800 기준)을 현재 창 크기 전체에 맞춘다. 전체 화면 해상도가 달라도 동작한다."""
        self.camera.viewport = LBWH(0, 0, self.width, self.height)

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        self.fit_camera()

    def play(self, name: str, volume: float = 0.6):
        if self.sound_on and name in self.sounds:
            try:
                arcade.play_sound(self.sounds[name], volume=volume)
            except Exception:
                pass

    def set_bgm(self, name: Optional[str]):
        """배경음을 바꾼다. None이면 끈다."""
        if not self.sound_on:
            name = None
        if name == self.bgm_name:
            return
        if self.bgm_player is not None:
            try:
                arcade.stop_sound(self.bgm_player)
            except Exception:
                pass
            self.bgm_player = None
        self.bgm_name = name
        if name and name in self.sounds:
            try:
                self.bgm_player = arcade.play_sound(self.sounds[name], volume=BGM_VOLUME, loop=True)
            except Exception:
                self.bgm_player = None

    def game_bgm(self) -> Optional[str]:
        if self.game_screen != "game" or self.paused:
            return None
        return "bgm_fast" if self.time_left <= RUSH_TIME else "bgm"

    def go_menu(self):
        self.paused = False
        self.idle_paused = False
        self.idle_time = 0.0
        self.game_screen = "menu"
        self.set_bgm(None)

    # ---------------------------------------------------------------- 오늘의 랭킹
    @staticmethod
    def load_ranking() -> list[dict]:
        try:
            with RANK_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        # 진행 요원이 ranking.json을 직접 고치다 형식이 틀린 기록은 건너뛰어, 메뉴 화면에서 꺼지지 않게 한다.
        # 금칙어 목록을 늘리기 전에 저장된 기록도 금칙어 이니셜이면 랭킹판에 보이지 않게 한다.
        return [e for e in data if isinstance(e, dict) and e.get("grade") in tuple(GRADE_ORDER)
                and isinstance(e.get("score"), int) and isinstance(e.get("name"), str)
                and e["name"] not in BLOCKED_NAMES]

    @staticmethod
    def rank_key(entry: dict):
        return (GRADE_ORDER.index(entry["grade"]), -entry["score"])

    def today_ranking(self) -> list[dict]:
        # 메뉴와 대기 화면은 매 프레임 랭킹판을 그리므로, 읽은 결과를 잠시 저장해 두고 다시 쓴다.
        today = datetime.date.today().isoformat()
        now = time.monotonic()
        if self.rank_cache is None or self.rank_cache[0] != today or now - self.rank_cache[1] >= RANK_RELOAD:
            entries = [e for e in self.load_ranking() if e.get("date") == today]
            self.rank_cache = (today, now, sorted(entries, key=self.rank_key)[:RANK_SIZE])
        return self.rank_cache[2]

    def current_entry(self) -> dict:
        return {"date": datetime.date.today().isoformat(), "name": self.name_input,
                "grade": self.result_grade(), "score": self.score, "trust": self.trust_score()}

    def finish_round(self):
        self.set_bgm(None)
        self.play("end", 0.7)
        self.cards = []
        self.selected = None
        self.last_rank = None
        self.rank_cache = None   # TOP 10 진입 여부는 파일을 새로 읽어 판단한다.
        ranking = self.today_ranking()
        entry = self.current_entry()
        qualifies = len(ranking) < RANK_SIZE or self.rank_key(entry) < self.rank_key(ranking[-1])
        if self.processed > 0 and qualifies:
            self.name_input = ""
            self.game_screen = "name"
            self.idle_time = 0.0
        else:
            self.show_result()

    def tutorial_next(self):
        if self.tutorial_page < TUTORIAL_PAGES - 1:
            self.tutorial_page += 1
        else:
            self.go_menu()

    def open_review(self):
        self.game_screen = "review"
        self.idle_time = 0.0

    def type_letter(self, char: str):
        if len(self.name_input) < NAME_LENGTH:
            self.name_input += char
            self.name_warning = ""
            self.play("select", 0.4)

    @staticmethod
    def name_keys():
        """이니셜 화면의 화면 자판: (글자, 왼쪽, 아래, 오른쪽, 위). 마우스만 쓰는 방문객도 입력할 수 있다."""
        keys = []
        for row, letters in enumerate(("ABCDEFGHIJKLM", "NOPQRSTUVWXYZ")):
            bottom = 385 - row * 52
            for i, char in enumerate(letters):
                left = 318 + i * 50
                keys.append((char, left, bottom, left + 44, bottom + 44))
        keys.append(("BACK", 560, 283, 720, 323))
        return keys

    def submit_name(self):
        if len(self.name_input) < NAME_LENGTH:
            # 랭킹에는 영문 이니셜을 꼭 3글자로 남긴다.
            self.name_warning = f"영문 이니셜 {NAME_LENGTH}글자를 모두 입력해 주세요."
            self.play("wrong", 0.4)
            return
        if self.name_input in BLOCKED_NAMES:
            self.name_warning = "사용할 수 없는 이니셜입니다. 다른 글자로 입력해 주세요."
            self.name_input = ""
            self.play("wrong", 0.4)
            return
        self.save_ranking()
        self.show_result()

    def save_ranking(self):
        entry = self.current_entry()
        entries = self.load_ranking() + [entry]
        try:
            with RANK_FILE.open("w", encoding="utf-8") as file:
                json.dump(entries, file, ensure_ascii=False, indent=1)
        except OSError:
            pass  # 저장하지 못해도 결과 화면은 보여준다.
        self.rank_cache = None
        ranking = self.today_ranking()
        self.last_rank = next((i + 1 for i, e in enumerate(ranking) if e == entry), None)
        self.play("buy")

    def show_result(self):
        self.game_screen = "result"
        self.idle_time = 0.0

    def trust_score(self) -> int:
        """최종 AI 신뢰도(0~100): 정확도 40% + 세 신뢰 지표 평균 60%."""
        if self.processed == 0:
            return 0
        accuracy = self.correct / self.processed
        return round(accuracy * 40 + sum(self.metrics.values()) / 3 * 0.6)

    def setup_game(self):
        self.game_screen = "game"
        self.idle_time = 0.0
        self.idle_paused = False
        self.mistakes = []
        self.cards = []
        self.selected = None
        self.deck = [DataCard(c.title, c.content_type, c.source, c.license,
                              c.risk_types, c.correct_action, c.explanation,
                              c.reward, c.penalty, c.difficulty) for c in self.card_deck]
        random.shuffle(self.deck)
        self.deck_index = 0
        self.spawn_timer = 0.0
        self.elapsed = 0.0
        self.time_left = self.round_length
        self.score = self.budget = self.combo = self.max_combo = 0
        self.processed = self.correct = self.wrong_approved = self.normal_loss = self.wrong_method = 0
        self.unreviewed = 0
        self.last_result = None
        self.paused = False
        self.phase_shown = 0
        self.phase_toast = 0.0
        self.action_lock = 0.0
        self.name_input = ""
        self.last_rank = None
        self.privacy_leaks = self.copyright_issues = self.bias_issues = 0
        self.metrics = {"copyright": 100.0, "privacy": 100.0, "fairness": 100.0}
        self.upgrades = set()
        self.feedback = "첫 카드를 선택하세요. 숫자 키 1, 2, 3으로도 처리할 수 있습니다."
        self.feedback_color = CYAN
        self.feedback_timer = 4.0
        self.spawn_card(155)
        self.set_bgm("bgm")

    def progress(self) -> float:
        """기본 3분 판으로 환산한 경과 시간. 짧은 체험 모드에서도 단계·속도가 같은 비율로 진행된다."""
        return self.elapsed * ROUND_TIME / self.round_length

    def round_label(self) -> str:
        return f"{int(self.round_length // 60)}분" if self.round_length % 60 == 0 else f"{int(self.round_length)}초"

    def show_notice(self, text: str):
        self.notice = text
        self.notice_timer = NOTICE_TIME

    def phase_index(self) -> int:
        return max(i for i, phase in enumerate(PHASES) if self.progress() >= phase[0])

    def spawn_card(self, x: Optional[float] = None):
        _start, _name, _desc, allowed, prefer = PHASES[self.phase_index()]
        candidates = [c for c in self.deck[self.deck_index:] if c.difficulty <= allowed]
        if not candidates:
            random.shuffle(self.deck)
            self.deck_index = 0
            candidates = [c for c in self.deck if c.difficulty <= allowed]
        if self.phase_index() == 0:
            # 적응 단계에는 위험 유형이 하나뿐인 카드만 낸다(기획서 6.2 "위험 유형이 명확함").
            candidates = [c for c in candidates if c.risk_key != "mixed"] or candidates
        prototype = candidates[0]
        if prefer and random.random() < PREFER_CHANCE:
            # 단계의 주제에 맞는 위험 유형 카드를 더 자주 내보낸다.
            preferred = [c for c in candidates if c.risk_key in prefer]
            if preferred:
                prototype = preferred[0]
        self.deck_index = self.deck.index(prototype, self.deck_index) + 1
        new_card = DataCard(prototype.title, prototype.content_type, prototype.source,
                            prototype.license, prototype.risk_types,
                            prototype.correct_action, prototype.explanation,
                            prototype.reward, prototype.penalty, prototype.difficulty,
                            x=x if x is not None else CARD_START_X)
        new_card.hinted = self.progress() < ADAPT_TIME
        new_card.bonus = self.phase_index() == len(PHASES) - 1
        if "ai_approve" in self.upgrades and new_card.risk_key == "safe" and random.random() < AI_APPROVE_CHANCE:
            new_card.ai_approve = True
        if new_card.risk_key == "mixed":
            # 추천은 카드가 나올 때 한 번 정해 두어, 볼 때마다 바뀌지 않게 한다.
            other = "remove" if new_card.correct_action == "refine" else "refine"
            new_card.ai_pick = new_card.correct_action if random.random() < AI_ASSIST_ACCURACY else other
        self.cards.append(new_card)

    def on_update(self, delta_time: float):
        # 부스 운영: 결과·튜토리얼·일시정지 화면이 오래 방치되면 다음 방문객을 위해 메뉴로 돌아간다.
        self.idle_time += delta_time
        self.notice_timer = max(0.0, self.notice_timer - delta_time)
        if self.game_screen == "attract":
            self.attract_time += delta_time
            return
        if self.game_screen == "menu" and self.idle_time >= ATTRACT_IDLE:
            # 부스: 메뉴가 방치되면 지나가는 관람객을 위한 소개 슬라이드를 보여준다.
            self.game_screen = "attract"
            self.attract_time = 0.0
            return
        if self.game_screen == "name" and self.idle_time >= NAME_IDLE:
            self.show_result()
            return
        if self.game_screen == "game" and self.paused:
            idle_key = "idle_paused" if self.idle_paused else "paused"
        else:
            idle_key = self.game_screen
        if idle_key in IDLE_RETURN and self.idle_time >= IDLE_RETURN[idle_key]:
            self.go_menu()
            return
        if self.game_screen == "game" and not self.paused and self.idle_time >= GAME_IDLE:
            # 방문객이 게임 도중 자리를 떠나면 일시정지하고, 곧 처음 화면으로 돌아간다.
            self.paused = True
            self.idle_paused = True
            self.idle_time = 0.0
            self.set_bgm(None)
            return
        if self.game_screen != "game" or self.paused:
            return
        self.time_left -= delta_time
        self.elapsed += delta_time
        self.feedback_timer = max(0.0, self.feedback_timer - delta_time)
        self.action_lock = max(0.0, self.action_lock - delta_time)
        if self.time_left <= 0:
            self.time_left = 0
            self.finish_round()
            return
        self.set_bgm(self.game_bgm())
        self.phase_toast = max(0.0, self.phase_toast - delta_time)
        phase = self.phase_index()
        if phase != self.phase_shown:
            # 새 단계가 시작되면 화면 가운데에 잠시 안내한다.
            self.phase_shown = phase
            self.phase_toast = PHASE_TOAST_TIME

        spawn_interval = max(5.0, 8.0 - self.progress() * 0.017)
        if PHASES[phase][1] == "고속 처리":
            spawn_interval = min(spawn_interval, FAST_SPAWN)
        elif PHASES[phase][1] == "데이터 러시":
            spawn_interval = RUSH_SPAWN
        self.spawn_timer += delta_time
        # 카드 폭과 여백을 확보한 뒤에만 새 카드를 생성한다.
        # 생성 주기보다 이동 속도가 빨라지는 후반에도 카드가 겹치지 않는다.
        can_spawn = not self.cards or self.cards[-1].x >= CARD_START_X + 2 * CARD_HALF + CARD_GAP
        # 벨트가 비면 1초 뒤 바로 다음 카드를 보내, 빠른 플레이어가 더 많이 처리할 수 있게 한다.
        wait = 1.0 if not self.cards else spawn_interval
        if self.spawn_timer >= wait and can_spawn and len(self.cards) < 12:
            self.spawn_timer = 0
            self.spawn_card()

        speed = min(95, 40 + self.progress() * 0.3)
        if "buffer" in self.upgrades:
            speed *= 0.7
        for current in self.cards[:]:
            current.x += speed * delta_time
            current.age += delta_time
            if current.ai_approve and current.x >= 450:
                self.ai_auto_approve(current)
            # 카드 오른쪽 끝이 서버 영역(1155)에 닿기 전에 자동 처리한다.
            elif current.x + CARD_HALF > SERVER_X - 4:
                if "deid" in self.upgrades and "privacy" in current.risk_types:
                    self.process_card(current, "refine", automatic=True, actor="자동 비식별화")
                else:
                    self.process_card(current, "approve", automatic=True)

    def ai_auto_approve(self, current: DataCard):
        """AI 자동 승인 모델이 안전한 카드를 대신 승인한다. 점수와 예산은 절반만 받는다."""
        self.cards.remove(current)
        if self.selected is current:
            self.selected = None
        self.processed += 1
        self.correct += 1
        earned = current.reward * SCORE_SCALE // 2
        self.score += earned
        self.budget += earned // 2
        if self.feedback_timer <= 0.5:
            self.feedback = f"AI 자동 승인 모델이 '{current.title}' 카드를 승인했습니다. +{earned}점"
            self.feedback_color = GREEN
            self.feedback_timer = 2.0

    def process_card(self, current: DataCard, action: str, automatic=False, actor: Optional[str] = None):
        if current not in self.cards:
            return
        self.cards.remove(current)
        if self.selected is current:
            self.selected = None
        self.processed += 1
        is_correct = action == current.correct_action
        self.last_result = (current, action, is_correct, automatic, actor)
        if automatic:
            # 검수하지 않고 통과한 카드는 결과가 안전해도 보상하지 않는다.
            self.unreviewed += 1
            self.combo = 0
        if is_correct and automatic and actor:
            self.feedback = f"{actor}: '{current.title}' 정제 완료. 직접 검수하지 않아 점수와 예산은 없습니다."
            self.feedback_color = YELLOW
        elif is_correct and automatic:
            self.feedback = "검수하지 않은 데이터가 자동 승인되었습니다. 문제는 없었지만 점수와 예산은 없습니다."
            self.feedback_color = YELLOW
        elif is_correct:
            self.correct += 1
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            multiplier = 2.0 if self.combo >= 20 else 1.5 if self.combo >= 10 else 1.2 if self.combo >= 5 else 1.0
            speed_bonus = min(50, max(0, int((5.0 - current.age) * 10)))
            # card.json의 reward(10~20)를 기획서 점수 규모(100~200)로 환산한다.
            earned = int(current.reward * SCORE_SCALE * multiplier) + speed_bonus
            if current.bonus:
                earned *= BONUS_MULTIPLIER
            self.score += earned
            self.budget += max(90, earned // 2)
            bonus_text = "보너스 2배! " if current.bonus else ""
            self.feedback = f"정확합니다! {bonus_text}+{earned}점  '{current.title}' {self.action_name(action)} 처리 완료."
            self.feedback_color = GREEN
            self.play("combo" if self.combo in (5, 10, 20) else "correct")
        else:
            self.combo = 0
            lost = self.wrong_penalty(current, action)
            self.mistakes.append((current, action, automatic, actor))
            self.score = max(0, self.score - lost)
            self.apply_metric_penalty(current, action)
            # 집계는 표시된 위험 신호가 아니라 실제 정답을 기준으로 한다.
            # 위험 신호가 있어도 조건을 갖춰 승인이 정답인 카드는 정상 데이터로 본다.
            if action == "approve":
                self.wrong_approved += 1
            elif current.correct_action == "approve":
                self.normal_loss += 1
            else:
                # 정제해야 하는데 제외했거나, 그 반대로 처리한 경우
                self.wrong_method += 1
            if automatic and actor:
                action_word = josa(actor, "으로", "로") + " " + self.action_name(action) + "되어"
            elif automatic:
                action_word = "자동 승인되어"
            else:
                action_word = josa(self.action_name(action), "으로", "로") + " 처리해"
            self.feedback = f"주의: {action_word} 오답입니다. -{lost}점  해설은 위 패널에서 확인하세요."
            self.feedback_color = RED
            # 위험 데이터가 학습 서버로 들어가면 서버 오류음, 그 밖의 오답은 부드러운 경고음
            self.play("server_error" if action == "approve" else "wrong", 0.5)
        self.feedback_timer = 3.2

    @staticmethod
    def wrong_penalty(current: DataCard, action: str) -> int:
        # card.json의 penalty(5~12)를 환산하고, 위험 데이터를 승인한 경우 더 크게 감점한다.
        lost = current.penalty * PENALTY_SCALE
        if action == "approve":
            lost = lost * 3 // 2
        return lost

    def apply_metric_penalty(self, current: DataCard, action: str):
        if current.correct_action == "approve":
            # 문제없는 데이터를 버리면 데이터 다양성만 조금 줄어든다.
            self.metrics["copyright"] = max(0, self.metrics["copyright"] - 2)
            self.metrics["fairness"] = max(0, self.metrics["fairness"] - 2)
            return
        risks = set(current.risk_types)
        if "copyright" in risks:
            self.copyright_issues += 1
            self.metrics["copyright"] -= 17 if action == "approve" else 7
        if "privacy" in risks:
            if action == "approve":
                self.privacy_leaks += 1
            self.metrics["privacy"] -= 25 if action == "approve" else 9
        if "bias" in risks:
            self.bias_issues += 1
            self.metrics["fairness"] -= 18 if action == "approve" else 8
        self.metrics = {key: max(0, min(100, value)) for key, value in self.metrics.items()}

    @staticmethod
    def action_name(action):
        return {"approve": "승인", "refine": "정제", "remove": "제외"}[action]

    def on_key_press(self, key, modifiers):
        self.idle_time = 0.0
        # 진행 요원용 키: Ctrl+Shift+Q 종료, F5 처음 화면으로, F9 소리 켜기/끄기, F11 전체 화면 전환
        if key == arcade.key.Q and modifiers & arcade.key.MOD_CTRL and modifiers & arcade.key.MOD_SHIFT:
            self.staff_quit()
            return
        if key == arcade.key.F5:
            self.go_menu()
            return
        if key == arcade.key.F9:
            self.sound_on = not self.sound_on
            self.set_bgm(self.game_bgm())
            self.show_notice("소리 켬" if self.sound_on else "소리 끔")
            return
        if key == arcade.key.F7:
            # 짧은 체험 모드: 대기 줄이 길 때 한 판 시간을 줄인다. 다음 판부터 적용된다.
            self.round_length = SHORT_ROUND if self.round_length == ROUND_TIME else ROUND_TIME
            self.show_notice(f"한 판 {self.round_label()} 모드 (다음 판부터 적용)")
            return
        if self.game_screen == "attract":
            self.go_menu()
            return
        if key == arcade.key.F11:
            self.set_fullscreen(not self.fullscreen)
            self.fit_camera()
            return
        if self.game_screen == "menu":
            if key in (arcade.key.SPACE, arcade.key.ENTER, arcade.key.NUM_1):
                self.setup_game()
            elif key == arcade.key.T:
                self.game_screen = "tutorial"
                self.tutorial_page = 0
            elif key == arcade.key.ESCAPE and self.from_launcher:
                self.staff_quit()   # 정상 종료(0)하면 런처가 게임 선택 화면을 다시 띄운다.
            return
        if self.game_screen == "tutorial":
            if key == arcade.key.ESCAPE:
                self.go_menu()
            elif key in (arcade.key.RIGHT, arcade.key.SPACE, arcade.key.ENTER):
                self.tutorial_next()
            elif key == arcade.key.LEFT and self.tutorial_page > 0:
                self.tutorial_page -= 1
            return
        if self.game_screen == "name":
            if arcade.key.A <= key <= arcade.key.Z:
                self.type_letter(chr(key).upper())
            elif key == arcade.key.BACKSPACE:
                self.name_input = self.name_input[:-1]
            elif key in (arcade.key.ENTER, arcade.key.NUM_ENTER):
                self.submit_name()
            elif key == arcade.key.ESCAPE:
                self.show_result()
            return
        if self.game_screen == "result":
            if key in (arcade.key.SPACE, arcade.key.ENTER, arcade.key.R):
                self.setup_game()
            elif key == arcade.key.RIGHT and self.mistakes:
                self.open_review()
            elif key == arcade.key.ESCAPE:
                self.go_menu()
            return
        if self.game_screen == "review":
            if key in (arcade.key.SPACE, arcade.key.ENTER, arcade.key.R):
                self.setup_game()
            elif key in (arcade.key.ESCAPE, arcade.key.LEFT, arcade.key.BACKSPACE):
                self.show_result()
            return
        if self.game_screen == "game":
            if self.paused:
                if key == arcade.key.ESCAPE:
                    self.paused = False
                    self.idle_paused = False
                    self.set_bgm(self.game_bgm())
                elif key == arcade.key.M:
                    self.go_menu()
                return
            if key == arcade.key.ESCAPE:
                # 실수로 판이 끝나지 않도록 ESC는 일시정지 화면을 연다.
                self.paused = True
                self.set_bgm(None)
                return
            # 숫자열과 숫자 키패드 모두 지원한다.
            actions = {
                arcade.key.KEY_1: "approve", arcade.key.KEY_2: "refine", arcade.key.KEY_3: "remove",
                arcade.key.NUM_1: "approve", arcade.key.NUM_2: "refine", arcade.key.NUM_3: "remove",
            }
            if key in actions:
                self.process_selected(actions[key])
            elif key in (arcade.key.LEFT, arcade.key.RIGHT):
                self.move_selection(1 if key == arcade.key.LEFT else -1)
            for kind, upgrade_key, *_ in UPGRADES:
                if key == getattr(arcade.key, upgrade_key):
                    self.buy_upgrade(kind)

    def select_card(self, current: DataCard):
        if self.selected is not current:
            self.play("select", 0.4)
            # 카드를 고르자마자 연타로 처리되지 않도록 잠시 기다린다.
            self.action_lock = max(self.action_lock, LOCK_AFTER_SELECT)
        self.selected = current
        self.feedback = "카드가 선택되었습니다. 제목·출처·라이선스를 읽고 처리하세요."
        self.feedback_color = CYAN
        self.feedback_timer = 2.0

    def move_selection(self, step: int):
        """← →로 카드를 고른다. cards[0]이 서버에 가장 가까운 카드다."""
        if not self.cards:
            return
        if self.selected not in self.cards:
            self.select_card(self.cards[0])
            return
        index = self.cards.index(self.selected) + step
        self.select_card(self.cards[max(0, min(len(self.cards) - 1, index))])

    def process_selected(self, action: str):
        if self.action_lock > 0:
            return  # 연타 방지: 직전 처리·선택 직후의 입력은 무시한다.
        if self.selected:
            self.process_card(self.selected, action)
            self.action_lock = LOCK_AFTER_PROCESS
        elif self.cards:
            # 선택 없이 누르면 바로 처리하지 않고, 먼저 카드를 보여준다.
            self.select_card(self.cards[0])
            self.action_lock = LOCK_AFTER_AUTO_SELECT
            self.feedback = "서버에 가장 가까운 카드를 선택했습니다. 내용을 확인하고 다시 누르세요."
            self.feedback_timer = 3.0
        else:
            self.feedback = "처리할 카드가 아직 없습니다."
            self.feedback_color = YELLOW
            self.feedback_timer = 2.0

    def on_mouse_press(self, x, y, button, modifiers):
        # 실제 1920×1080 픽셀 입력을 UI 논리 좌표(1280×800)로 변환한다.
        x, y, _ = self.camera.unproject((x, y))
        self.idle_time = 0.0
        if self.game_screen == "attract":
            self.go_menu()
            return
        if self.game_screen == "menu":
            if 400 < x < 880 and 270 < y < 345:
                self.setup_game()
            elif 400 < x < 880 and 195 < y < 255:
                self.game_screen = "tutorial"
                self.tutorial_page = 0
            return
        if self.game_screen == "tutorial":
            if 150 < x < 440 and 95 < y < 155 and self.tutorial_page > 0:
                self.tutorial_page -= 1
            elif 820 < x < 1130 and 95 < y < 155:
                self.tutorial_next()
            return
        if self.game_screen == "name":
            for char, left, bottom, right, top in self.name_keys():
                if left <= x <= right and bottom <= y <= top:
                    if char == "BACK":
                        self.name_input = self.name_input[:-1]
                    else:
                        self.type_letter(char)
                    return
            if 400 < x < 630 and 150 < y < 210:
                self.submit_name()
            elif 650 < x < 880 and 150 < y < 210:
                self.show_result()
            return
        if self.game_screen == "result":
            if 260 < x < 490 and 60 < y < 125:
                self.setup_game()
            elif 525 < x < 755 and 60 < y < 125 and self.mistakes:
                self.open_review()
            elif 790 < x < 1020 and 60 < y < 125:
                self.go_menu()
            return
        if self.game_screen == "review":
            if 385 < x < 620 and 60 < y < 125:
                self.show_result()
            elif 660 < x < 895 and 60 < y < 125:
                self.setup_game()
            return
        if self.game_screen != "game":
            return
        if self.paused:
            if 440 < x < 840 and 360 < y < 420:
                self.paused = False
                self.idle_paused = False
                self.set_bgm(self.game_bgm())
            elif 440 < x < 840 and 280 < y < 340:
                self.go_menu()
            return
        # 카드 클릭: 컨베이어에 보이는 카드의 중심 좌표를 기준으로 선택한다.
        for current in reversed(self.cards):
            if current.x - CARD_HALF - 2 <= x <= current.x + CARD_HALF + 2 and CARD_BOTTOM <= y <= CARD_TOP:
                self.select_card(current)
                return
        if 38 <= y <= 108:
            for left, action in ((36, "approve"), (278, "refine"), (520, "remove")):
                if left <= x <= left + 230:
                    self.process_selected(action)
                    return
        # 업그레이드는 화면에 그려진 버튼 영역 안을 눌렀을 때만 구입한다.
        for kind, _key, _name, _cost, left, bottom in UPGRADES:
            if left <= x <= left + UPGRADE_WIDTH and bottom <= y <= bottom + UPGRADE_HEIGHT:
                self.buy_upgrade(kind)
                return

    def buy_upgrade(self, kind):
        _kind, _key, name, cost, *_ = next(u for u in UPGRADES if u[0] == kind)
        if kind in self.upgrades:
            self.feedback = f"{josa(name, '은', '는')} 이미 작동 중입니다."
            self.feedback_color = CYAN
        elif self.budget < cost:
            self.feedback = f"예산이 부족합니다. {name}에는 {cost} 예산이 필요합니다."
            self.feedback_color = YELLOW
        else:
            self.budget -= cost
            self.upgrades.add(kind)
            self.play("buy")
            if kind == "buffer":
                self.feedback = f"{name} 작동! 컨베이어가 30% 느려집니다."
            else:
                self.feedback = f"{name} 작동! 신호를 표시하지만 최종 판단은 직접 해야 합니다."
            self.feedback_color = GREEN
        self.feedback_timer = 3.0

    def visible_risks(self, current: DataCard) -> tuple[str, ...]:
        """보유한 탐지 도구로 찾아낸 위험 신호만 돌려준다. 적응 단계 카드는 모두 보여준다."""
        if current.hinted:
            return tuple(r for r in current.risk_types if r != "safe")
        return tuple(r for r in current.risk_types if RISK_TOOLS.get(r) in self.upgrades)

    def has_all_detectors(self) -> bool:
        return set(RISK_TOOLS.values()) <= self.upgrades

    def shown_label(self, current: DataCard):
        """카드에 표시할 라벨과 색. 도구가 없으면 위험 종류를 알려주지 않는다."""
        risks = self.visible_risks(current)
        if len(risks) > 1:
            return RISK_LABELS["mixed"], ORANGE
        if risks:
            return RISK_LABELS[risks[0]], {"copyright": RED, "privacy": BLUE, "bias": PURPLE}[risks[0]]
        if current.risk_key == "safe" and current.hinted:
            return RISK_LABELS["safe"], GREEN
        if current.risk_key == "safe" and self.has_all_detectors():
            return "신호 없음", GREEN
        return "검수 대기", MUTED

    def on_draw(self):
        self.clear()
        self.camera.use()
        if self.game_screen == "menu":
            self.draw_menu()
        elif self.game_screen == "tutorial":
            self.draw_tutorial()
        elif self.game_screen == "game":
            self.draw_game()
        elif self.game_screen == "name":
            self.draw_name_entry()
        elif self.game_screen == "review":
            self.draw_review()
        elif self.game_screen == "attract":
            self.draw_attract()
        else:
            self.draw_result()
        if self.notice_timer > 0:
            # 진행 요원 키 안내: 내용을 가리지 않도록 제목줄 오른쪽에 잠시 보여준다.
            rect(800, 742, 1250, 794, (10, 16, 31, 245))
            outline(800, 742, 1250, 794, YELLOW, 2)
            label(self.notice, 1025, 768, 15, YELLOW, "center", "center", True)

    def draw_header(self, title, subtitle=""):
        rect(0, 735, UI_WIDTH, UI_HEIGHT, (15, 23, 42))
        label(title, 42, 760, 25, WHITE, bold=True)
        if subtitle:
            label(subtitle, 42, 738, 13, MUTED)
        arcade.draw_line(36, 727, 1244, 727, (40, 56, 84), 1)

    def draw_menu(self):
        # 배경 장식: 데이터 노드와 연결선
        for i in range(9):
            x = 70 + i * 145
            arcade.draw_line(x, 70, x + 75, 715, (20, 49, 72), 1)
            arcade.draw_circle_filled(x, 70 + (i % 3) * 190, 3, CYAN)
        label("CLEAN DATA", UI_WIDTH / 2, 638, 18, CYAN, "center", bold=True)
        label("클린 데이터 라벨러", UI_WIDTH / 2, 572, 52, WHITE, "center", bold=True)
        label("좋은 AI는 좋은 데이터에서 시작됩니다.", UI_WIDTH / 2, 528, 21, MUTED, "center")
        # 오늘의 프로젝트와 이용 목적: 카드 정답의 기준이 되므로 시작 전에 보여준다.
        rect(330, 378, 950, 478, (18, 33, 52))
        outline(330, 378, 950, 478, (46, 78, 104), 1)
        label("오늘의 프로젝트", UI_WIDTH / 2, 456, 12, CYAN, "center", "center", True)
        label(PROJECT_NAME, UI_WIDTH / 2, 428, 19, WHITE, "center", "center", True)
        label(f"이용 목적: {PROJECT_POLICY}  ·  이 목적에 맞는 자료만 AI가 배울 수 있습니다",
              UI_WIDTH / 2, 398, 12, MUTED, "center", "center")
        rect(400, 270, 880, 345, (35, 62, 86))
        outline(400, 270, 880, 345, CYAN, 2)
        label("▶  검수 라운드 시작", UI_WIDTH / 2, 308, 25, WHITE, "center", "center", True)
        rect(400, 195, 880, 255, PANEL)
        outline(400, 195, 880, 255, (61, 82, 113), 1)
        label("T  게임 소개 · 튜토리얼", UI_WIDTH / 2, 225, 18, MUTED, "center", "center")
        label(f"{self.round_label()} 동안 승인 · 정제 · 제외로 데이터를 지켜주세요", UI_WIDTH / 2, 146, 15,
              YELLOW if self.round_length != ROUND_TIME else MUTED, "center")
        start_hint = "SPACE / ENTER로 시작  ·  ESC 게임 선택 화면으로" if self.from_launcher else "SPACE / ENTER로 시작"
        label(start_hint, UI_WIDTH / 2, 112, 13, (91, 120, 158), "center")
        self.draw_ranking_board(972, 150, 1250, 560)

    def draw_ranking_board(self, left, bottom, right, top):
        rect(left, bottom, right, top, (16, 28, 46))
        outline(left, bottom, right, top, (46, 78, 104), 1)
        # PC마다 랭킹이 따로 저장되므로, booth.json에 PC 이름이 있으면 함께 보여준다.
        title = f"{self.pc_name} 오늘의 TOP 10" if self.pc_name else "오늘의 TOP 10"
        label(title, left + 16, top - 30, 15, YELLOW, bold=True)
        label("등급·점수 순", right - 14, top - 30, 10, MUTED, "right")
        ranking = self.today_ranking()
        if not ranking:
            wrapped_label("아직 기록이 없습니다. 첫 번째 주인공이 되어 보세요!", left + 16, top - 70, 16, 12, MUTED, 19, 3)
            return
        for index, entry in enumerate(ranking):
            y = top - 66 - index * 33
            color = YELLOW if index < 3 else WHITE
            label(f"{index + 1}", left + 26, y, 13, color, "center", bold=True)
            label(entry["name"], left + 50, y, 14, color, bold=True)
            label(entry["grade"], left + 128, y, 14, GRADE_COLORS.get(entry["grade"], WHITE), "center", bold=True)
            label(f"{entry['score']:,}", right - 16, y, 13, color, "right")

    def draw_tutorial(self):
        self.draw_header("게임 소개 · 튜토리얼", "빠른 판단보다 신뢰할 수 있는 판단이 중요합니다.")
        rect(100, 155, 1180, 675, PANEL)
        if self.tutorial_page == 0:
            self.draw_intro()
        elif self.tutorial_page == 1:
            self.draw_tutorial_cards()
        else:
            self.draw_tutorial_upgrades()
        # 아래쪽 이동 버튼과 쪽 번호
        label(f"{self.tutorial_page + 1} / {TUTORIAL_PAGES}", 640, 172, 12, (91, 120, 158), "center")
        if self.tutorial_page > 0:
            rect(150, 95, 440, 155, PANEL_LIGHT)
            label("◀  이전", 295, 125, 17, WHITE, "center", "center", True)
        last = self.tutorial_page == TUTORIAL_PAGES - 1
        rect(820, 95, 1130, 155, CYAN)
        label("확인했습니다  ·  메뉴로" if last else "다음  ▶", 975, 125, 17, BG, "center", "center", True)

    def draw_intro(self):
        """튜토리얼 첫 쪽: 이 게임이 무엇인지, AI에게 데이터가 왜 중요한지 설명한다."""
        label("이 게임은?  AI는 데이터로 배웁니다", 145, 615, 24, CYAN, bold=True)
        wrapped_label("사람이 책을 읽고 경험하며 배우듯, AI는 수많은 데이터(글·사진·음성)를 보고 배웁니다. "
                      "그래서 AI가 무엇을 배우느냐가 AI가 어떤 답을 하느냐를 결정합니다.", 145, 580, 68, 15, MUTED, 22, 2)
        # 데이터 → AI 학습 → AI의 답
        boxes = [(170, "데이터", "글·사진·음성 자료"), (520, "AI 학습", "데이터 속 규칙을 익힘"),
                 (870, "AI의 답", "배운 대로 대답·그림 생성")]
        for left, title, caption in boxes:
            rect(left, 430, left + 240, 530, (24, 36, 58))
            label(title, left + 120, 512, 14, WHITE, "center", "center", True)
            label(caption, left + 120, 412, 12, MUTED, "center", "center")
        for i in range(3):   # 데이터 카드 묶음
            rect(232 + i * 26, 446 - i * 4, 292 + i * 26, 490 - i * 4, (40, 57, 81))
            rect(232 + i * 26, 482 - i * 4, 292 + i * 26, 490 - i * 4, (CYAN, BLUE, GREEN)[i])
        arcade.draw_circle_outline(640, 466, 26, CYAN, 3)   # AI 학습 서버
        for angle_x, angle_y in ((-38, 0), (38, 0), (0, -38), (0, 38)):
            arcade.draw_line(640 + angle_x * 0.7, 466 + angle_y * 0.7, 640 + angle_x, 466 + angle_y, CYAN, 3)
        arcade.draw_circle_filled(640, 466, 9, CYAN)
        rect(930, 448, 1050, 490, (45, 70, 100))             # AI의 답(말풍선)
        arcade.draw_triangle_filled(948, 448, 966, 448, 950, 436, (45, 70, 100))
        label("안녕하세요!", 990, 469, 13, WHITE, "center", "center")
        for start in (415, 765):                              # 화살표
            arcade.draw_line(start, 480, start + 95, 480, YELLOW, 4)
            arcade.draw_triangle_filled(start + 105, 480, start + 91, 490, start + 91, 470, YELLOW)
        # 문제 있는 데이터를 배우면
        label("그런데 데이터에 문제가 있으면?", 145, 368, 17, WHITE, bold=True)
        problems = [("© 허락 없이 가져온 작품", "AI가 남의 그림·글을 베낀 결과를 만들어요", RED),
                    ("▣ 이름·전화번호 같은 개인정보", "AI가 다른 사람의 개인정보를 말해 버려요", BLUE),
                    ("◈ 한쪽으로 치우친 자료", "AI가 편견이 담긴 답을 해요", PURPLE)]
        for index, (cause, effect, color) in enumerate(problems):
            y = 334 - index * 30
            label(cause, 175, y, 14, color, bold=True)
            label("→", 505, y, 14, MUTED)
            label(effect, 540, y, 14, WHITE)
        rect(145, 178, 1135, 240, (29, 52, 70))
        label("당신의 역할", 175, 214, 14, ORANGE, bold=True)
        wrapped_label(f"AI 회사의 데이터 검수 담당자가 되어, {self.round_label()} 동안 AI 학습 서버로 들어가는 데이터를 "
                      "검사합니다. 좋은 데이터를 고를수록 믿을 수 있는 AI가 완성됩니다.", 290, 218, 52, 14, WHITE, 20, 2)

    def draw_tutorial_cards(self):
        label("데이터 카드 읽는 법", 145, 615, 24, CYAN, bold=True)
        steps = [("01", "카드 선택", "카드를 클릭하거나 ← → 키로 고르면 제목·출처·라이선스를 볼 수 있습니다. 위험 신호는 처음 25초 동안 자동 표시되고, 그 뒤에는 탐지 도구를 사야 표시됩니다.", CYAN),
                 ("02", "행동 선택", "1 승인: 안전하거나 허가·비식별화 등 조건을 갖춘 데이터  ·  2 정제: 개인정보는 마스킹하고 잘못된 분류는 재라벨링  ·  3 제외: 권리·안전 문제가 큰 데이터", YELLOW),
                 ("03", "지표 지키기", "저작권 안전도, 개인정보 보호, 공정성이 모두 높아야 최종 AI가 신뢰를 얻습니다.", GREEN)]
        y = 535
        for number, title, desc, color in steps:
            arcade.draw_circle_filled(180, y + 8, 24, color)
            label(number, 180, y + 8, 13, BG, "center", "center", True)
            label(title, 225, y + 12, 20, WHITE, bold=True)
            wrapped_label(desc, 225, y - 17, 58, 15, MUTED, 23, 2)
            y -= 105
        rect(145, 178, 1135, 248, (29, 52, 70))
        label("TIP", 175, 218, 14, ORANGE, bold=True)
        wrapped_label("마스킹: 전화번호·이메일·번호판처럼 식별 정보를 가립니다. 재라벨링: 잘못된 직업·성별 라벨을 사실에 맞게 고칩니다. 정제 후에도 최종 판단은 직접 합니다.", 225, 222, 52, 14, WHITE, 20, 3)

    def draw_tutorial_upgrades(self):
        label("업그레이드로 검수를 돕기", 145, 615, 24, CYAN, bold=True)
        label("도구는 정답을 대신하지 않습니다. 판단을 더 빠르고 정확하게 만드는 보조 장치입니다.", 145, 580, 15, MUTED)
        colors = {"watermark": RED, "privacy": BLUE, "bias": PURPLE, "buffer": MUTED,
                  "license": YELLOW, "deid": CYAN, "ai_approve": GREEN, "ai_assist": ORANGE}
        descriptions = {
            "watermark": "저작권 신호가 있는 카드에 붉은 테두리와 '저작권 확인 필요' 라벨을 표시합니다.",
            "privacy": "전화번호·이메일·얼굴 같은 개인정보 신호를 라벨로 표시합니다.",
            "bias": "성별·지역·직업을 단정하는 편향 신호를 표시합니다. 탐지기 3종이 모두 있으면 '신호 없음'도 보입니다.",
            "buffer": "컨베이어를 30% 늦춰 카드가 화면에 더 오래 머뭅니다.",
            "license": "라이선스가 무엇을 허락하는지 한 줄로 요약하고, 출처의 신뢰도를 표시합니다.",
            "deid": "서버에 도착한 개인정보 카드를 승인 대신 자동 정제합니다. 제외해야 할 자료도 정제할 수 있습니다.",
            "ai_approve": f"안전한 카드 중 {AI_APPROVE_CHANCE:.0%}를 AI 모델이 대신 승인합니다. 점수는 절반만 받습니다.",
            "ai_assist": "AI가 복합 위험 카드에 추천 행동을 표시합니다. AI 추천도 틀릴 때가 있습니다.",
        }
        # 단축키 순서(Q W E R / A S D F)대로 4×2 격자에 배치한다.
        for index, (kind, key, name, cost, *_pos) in enumerate(UPGRADES):
            left = 135 + (index % 4) * 257
            right = left + 245
            top = 555 - (index // 4) * 175
            rect(left, top - 160, right, top, (29, 44, 64))
            rect(left, top - 36, right, top, colors[kind])
            label(key, left + 18, top - 18, 15, BG, "center", "center", True)
            label(name, left + 34, top - 18, 13, BG, "left", "center", True)
            label(f"{cost:,}", right - 10, top - 18, 12, BG, "right", "center", True)
            wrapped_label(descriptions[kind], left + 16, top - 60, 18, 12, WHITE, 18, 5)
        label("도구는 틀릴 수 있습니다. 표시를 확인한 뒤 최종 판단은 직접 합니다.", 640, 197, 13, ORANGE, "center")

    def draw_metric(self, name, value, x, y, color):
        label(name, x, y + 27, 14, MUTED)
        label(f"{int(value)}", x + 285, y + 25, 18, color, "right", "center", True)
        rect(x, y, x + 285, y + 9, (45, 58, 80))
        rect(x, y, x + 285 * value / 100, y + 9, color)

    def draw_game(self):
        self.draw_header("클린 데이터 라벨러", f"오늘의 프로젝트: {PROJECT_NAME}  ·  {PROJECT_POLICY} 데이터")
        time_color = RED if self.time_left < 20 else YELLOW if self.time_left < 60 else WHITE
        label(f"{int(self.time_left // 60):02d}:{int(self.time_left % 60):02d}", 795, 755, 26, time_color, "center", "center", True)
        label("남은 시간", 795, 775, 11, MUTED, "center", "center")
        label(f"{self.score:,}", 960, 755, 24, WHITE, "center", "center", True)
        label("점수", 960, 775, 11, MUTED, "center", "center")
        label(f"{self.budget:,}", 1110, 755, 24, YELLOW, "center", "center", True)
        label("정제 예산", 1110, 775, 11, MUTED, "center", "center")

        # 하단 상세 카드 패널
        rect(36, 140, 735, 375, PANEL)
        panel_title = "직전 카드 해설" if not self.selected and self.last_result else "선택한 데이터"
        label(panel_title, 60, 343, 16, CYAN, bold=True)
        if self.selected:
            self.draw_detail_card(self.selected)
        elif self.last_result:
            self.draw_last_result()
        else:
            arcade.draw_circle_filled(380, 275, 38, (33, 64, 82))
            label("?", 380, 275, 35, CYAN, "center", "center", True)
            label("카드를 클릭해 검수를 시작하세요", 380, 215, 19, MUTED, "center")
            label("제목·출처·라이선스를 읽은 뒤 아래 버튼을 선택합니다", 380, 185, 14, (96, 115, 145), "center")

        # 컨베이어: 카드 큐는 화면의 전체 너비를 사용한다.
        label("데이터 큐", 60, 665, 14, MUTED)
        _start, phase_name, phase_desc, *_ = PHASES[self.phase_index()]
        if self.progress() < ADAPT_TIME:
            left = int((ADAPT_TIME - self.progress()) * self.round_length / ROUND_TIME) + 1
            label(f"적응 단계 {left}초  ·  지금 나오는 카드는 위험 신호가 자동으로 표시됩니다", 1235, 665, 13, CYAN, "right")
        else:
            rush = phase_name == "데이터 러시"
            label(f"{phase_name}  ·  {phase_desc}", 1235, 665, 13, YELLOW if rush else CYAN, "right")
        rect(45, 450, 1235, 650, (15, 25, 40))
        rect(60, 460, 1135, 475, (37, 54, 74))
        arcade.draw_line(1145, 456, 1145, 648, (66, 82, 111), 2)
        rect(1155, 450, 1235, 650, (25, 55, 67))
        label("AI", 1195, 575, 15, CYAN, "center", "center", True)
        label("서버", 1195, 549, 15, CYAN, "center", "center", True)
        arcade.draw_circle_outline(1195, 513, 22, CYAN, 2)
        arcade.draw_line(1186, 513, 1192, 507, CYAN, 3)
        arcade.draw_line(1192, 507, 1205, 522, CYAN, 3)
        for current in self.cards:
            self.draw_queue_card(current)
        # 우측 지표 패널: 큐와 분리해 가독성을 유지한다.
        rect(785, 56, 1244, 430, PANEL)
        label("AI 신뢰 지표", 814, 405, 16, CYAN, bold=True)
        self.draw_metric("저작권 안전도", self.metrics["copyright"], 814, 355, RED if self.metrics["copyright"] < 60 else GREEN)
        self.draw_metric("개인정보 보호", self.metrics["privacy"], 814, 305, BLUE if self.metrics["privacy"] < 60 else GREEN)
        self.draw_metric("공정성", self.metrics["fairness"], 814, 255, PURPLE if self.metrics["fairness"] < 60 else GREEN)
        label(f"처리량  {self.processed:02d}건", 814, 226, 14, MUTED)
        label(f"콤보  x{self.combo}", 1030, 226, 14, YELLOW if self.combo else MUTED)
        arcade.draw_line(814, 214, 1214, 214, (53, 70, 96), 1)
        label("자동화 도구", 814, 193, 13, WHITE, bold=True)

        # 피드백 / 행동 버튼
        feedback = self.feedback if self.feedback_timer > 0 else "← → 카드 선택  ·  1 승인 · 2 정제 · 3 제외  ·  ESC 일시정지"
        # 상세 패널과 행동 버튼 사이의 전용 간격에 피드백을 표시한다.
        label(feedback, 60, 120, 13, self.feedback_color if self.feedback_timer > 0 else MUTED)
        self.draw_action_button(36, "1", "승인", GREEN)
        self.draw_action_button(278, "2", "정제", YELLOW)
        self.draw_action_button(520, "3", "제외", RED)
        for upgrade in UPGRADES:
            self.draw_upgrade(*upgrade)
        if self.phase_toast > 0 and self.phase_shown > 0:
            _start, name, desc, *_ = PHASES[self.phase_shown]
            rush = name == "데이터 러시"
            rect(340, 505, 940, 595, (10, 16, 31, 235))
            outline(340, 505, 940, 595, YELLOW if rush else CYAN, 2)
            label(name, 640, 565, 24, YELLOW if rush else CYAN, "center", "center", True)
            label(desc, 640, 527, 14, WHITE, "center", "center")
        if self.paused:
            self.draw_pause()

    def draw_pause(self):
        rect(0, 0, UI_WIDTH, UI_HEIGHT, (10, 16, 31, 215))
        rect(390, 250, 890, 560, PANEL)
        outline(390, 250, 890, 560, CYAN, 2)
        if self.idle_paused:
            left = max(0, int(IDLE_RETURN["idle_paused"] - self.idle_time) + 1)
            label("아직 플레이 중인가요?", 640, 500, 26, YELLOW, "center", "center", True)
            label(f"{left}초 뒤 처음 화면으로 돌아갑니다. 계속하려면 ESC를 누르세요.", 640, 458, 14, WHITE, "center", "center")
        else:
            label("일시정지", 640, 500, 28, WHITE, "center", "center", True)
            label("시간과 컨베이어가 멈춰 있습니다.", 640, 458, 14, MUTED, "center", "center")
        rect(440, 360, 840, 420, CYAN)
        label("ESC  계속하기", 640, 390, 18, BG, "center", "center", True)
        rect(440, 280, 840, 340, PANEL_LIGHT)
        label("M  메뉴로 나가기 (진행 내용 사라짐)", 640, 310, 15, WHITE, "center", "center", True)

    def draw_preview(self, content_type: str):
        """카드 유형에 맞는 작은 미리보기 그림을 그린다."""
        rect(82, 185, 214, 270, (40, 57, 81))
        if content_type in ("이미지", "사진", "그림", "만화", "지도", "도면", "도식"):
            arcade.draw_circle_filled(148, 239, 22, (102, 151, 173))
            arcade.draw_line(93, 205, 144, 246, CYAN, 4)
            arcade.draw_line(144, 246, 205, 211, GREEN, 4)
            arcade.draw_circle_filled(177, 228, 7, YELLOW)
        elif content_type == "문서":
            rect(115, 205, 181, 260, WHITE)
            for i in range(4):
                arcade.draw_line(125, 247 - i * 9, 172, 247 - i * 9, (105, 130, 153), 3)
            arcade.draw_circle_outline(148, 223, 11, BLUE, 2)
        elif content_type in ("데이터", "통계", "표", "그래프", "도표"):
            for i, height in enumerate((22, 40, 30, 52)):
                rect(108 + i * 22, 208, 124 + i * 22, 208 + height, (BLUE, CYAN, GREEN, YELLOW)[i])
            arcade.draw_line(100, 206, 196, 206, (91, 119, 145), 2)
        elif content_type == "오디오":
            for i, height in enumerate((10, 26, 42, 20, 34, 14, 28)):
                rect(104 + i * 13, 232 - height / 2, 111 + i * 13, 232 + height / 2, CYAN)
        elif content_type == "영상":
            rect(100, 205, 196, 260, (24, 34, 52))
            arcade.draw_triangle_filled(136, 218, 136, 248, 164, 233, WHITE)
        elif content_type == "코드":
            label("</>", 148, 233, 28, GREEN, "center", "center", True)
        else:
            label("Aa", 148, 235, 32, CYAN, "center", "center", True)
            arcade.draw_line(103, 208, 195, 208, (91, 119, 145), 2)

    def draw_detail_card(self, current: DataCard):
        shown, color = self.shown_label(current)
        rect(60, 150, 711, 365, (27, 40, 62))
        rect(60, 340, 711, 365, color)
        label(shown, 82, 347, 14, BG if color in (GREEN, MUTED) else WHITE, bold=True)
        label(current.title, 82, 314, 19, WHITE, bold=True)
        label(f"{current.content_type}  /  위험도 {current.difficulty}", 82, 288, 13, MUTED)
        self.draw_preview(current.content_type)
        label("DATA", 148, 194, 10, MUTED, "center")
        label("출처", 330, 276, 12, MUTED)
        label(current.source, 430, 276, 13, WHITE)
        label("라이선스", 330, 249, 12, MUTED)
        label(current.license, 430, 249, 13, WHITE)
        label("위험 신호", 330, 222, 12, MUTED)
        # 위험 신호는 보유한 탐지 도구가 찾아낸 것만 보여준다.
        risks = self.visible_risks(current)
        if risks:
            label("  ".join(self.risk_name(r) for r in risks), 430, 222, 13, color)
        elif current.hinted or self.has_all_detectors():
            label("√ 감지된 신호 없음", 430, 222, 13, GREEN)
        elif self.upgrades & set(RISK_TOOLS.values()):
            label("보유한 도구로는 감지되지 않음", 430, 222, 13, MUTED)
        else:
            label("탐지 도구 없음 · 제목과 출처로 판단", 430, 222, 13, MUTED)
        if "license" in self.upgrades:
            label("봇 요약", 330, 194, 12, MUTED)
            label(license_summary(current.license), 430, 194, 13, YELLOW)
            note = source_note(current.source)
            if note:
                label(note[0], 711 - 12, 276, 11, note[1], "right")
        if "ai_assist" in self.upgrades and current.ai_pick:
            label("AI 추천", 330, 166, 12, MUTED)
            label(f"{self.action_name(current.ai_pick)}  · 추천일 뿐, 최종 판단은 직접", 430, 166, 13, ORANGE)
        # 정답 해설은 처리 전에 보여주지 않고, 처리 후 '직전 카드 해설'에서 보여준다.

    def draw_last_result(self):
        """처리가 끝난 카드의 정답과 해설을 다음 카드를 고를 때까지 보여준다."""
        current, action, is_correct, automatic, actor = self.last_result
        answer = self.action_name(current.correct_action)
        if automatic:
            how = f"{josa(actor, '이', '가')} {self.action_name(action)}" if actor else "자동 승인"
            color, verdict = YELLOW, f"검수 없이 {how}  ·  정답은 {answer}"
        elif is_correct:
            color, verdict = GREEN, f"정답  ·  {answer}"
        else:
            color, verdict = RED, f"오답  ·  내 선택 {self.action_name(action)}  →  정답 {answer}"
        rect(60, 150, 711, 330, (27, 40, 62))
        rect(60, 150, 66, 330, color)
        label(verdict, 86, 298, 17, color, bold=True)
        label(current.title, 86, 266, 15, WHITE, bold=True)
        label(f"{current.risk_label}  ·  출처 {current.source}  ·  라이선스 {current.license}", 86, 240, 12, MUTED)
        wrapped_label(current.explanation, 86, 205, 50, 14, WHITE, 21, 2)
        label("다음 카드를 클릭하거나 ← → 키로 골라 검수를 계속하세요.", 86, 162, 12, (96, 115, 145))

    @staticmethod
    def risk_name(risk):
        return {"copyright": "© 저작권", "privacy": "▣ 개인정보", "bias": "◈ 편향", "safe": "√ 안전"}[risk]

    def draw_queue_card(self, current: DataCard):
        shown, color = self.shown_label(current)
        left, right = current.x - CARD_HALF, current.x + CARD_HALF
        bottom, top = CARD_BOTTOM, CARD_TOP
        rect(left + 3, bottom - 3, right + 3, top + 3, (7, 12, 23))
        rect(left, bottom, right, top, (32, 46, 69))
        rect(left, top - 12, right, top, color)
        if current is self.selected:
            outline(left - 4, bottom - 4, right + 4, top + 4, CYAN, 3)
        elif "copyright" in self.visible_risks(current):
            # 워터마크 스캐너: 저작권 신호가 있는 카드에 붉은 테두리
            outline(left - 2, bottom - 2, right + 2, top + 2, RED, 2)
        label(shown, current.x, top - 30, 13, color, "center", "center", True)
        for index, title_line in enumerate(compact_card_title(current.title, max_chars=9)):
            label(title_line, left + 12, top - 64 - index * 21, 15, WHITE, bold=True)
        label(current.content_type, left + 12, bottom + 16, 13, MUTED)
        if current.ai_approve:
            label("AI 승인 대기", right - 12, bottom + 16, 12, CYAN, "right")
        elif current.bonus:
            label("BONUS ×2", right - 12, bottom + 16, 13, YELLOW, "right", bold=True)

    def draw_action_button(self, x, key, name, color):
        rect(x, 38, x + 230, 108, (31, 48, 69))
        outline(x, 38, x + 230, 108, color, 2)
        label(key, x + 26, 73, 24, color, "center", "center", True)
        label(name, x + 125, 73, 20, WHITE, "center", "center", True)
        if self.action_lock > 0:
            # 연타 방지 대기 중에는 버튼을 흐리게 보여준다.
            rect(x, 38, x + 230, 108, (10, 16, 31, 150))

    def draw_upgrade(self, kind, key, name, cost, x, y):
        active = kind in self.upgrades
        affordable = self.budget >= cost
        color = GREEN if active else YELLOW if affordable else MUTED
        rect(x, y, x + UPGRADE_WIDTH, y + UPGRADE_HEIGHT, (25, 67, 61) if active else (29, 44, 64))
        middle = y + UPGRADE_HEIGHT / 2
        label(key, x + 15, middle, 12, color, "center", "center", True)
        label(name, x + 30, middle, 12, WHITE if active or affordable else MUTED, "left", "center")
        label("ON" if active else f"{cost:,}", x + UPGRADE_WIDTH - 8, middle, 12, color, "right", "center")

    def result_grade(self):
        accuracy = self.correct / self.processed if self.processed else 0
        minimum = min(self.metrics.values())
        # 기획서 기준: 심각한 개인정보 유출이 있으면 정확도와 관계없이 D
        if self.privacy_leaks >= 3:
            return "D"
        if accuracy >= .95 and minimum >= 90:
            return "S"
        if accuracy >= .85 and minimum >= 70:
            return "A"
        if accuracy >= .70 and minimum >= 50:
            return "B"
        if accuracy >= .55 and minimum >= 30:
            return "C"
        return "D"

    def result_message(self):
        if self.processed == 0:
            return "검수한 데이터가 없어 AI를 학습시킬 수 없습니다."
        if self.unreviewed * 2 >= self.processed:
            return "검수하지 않은 데이터가 절반 이상 그대로 AI 학습에 들어갔습니다."
        lowest = min(self.metrics, key=self.metrics.get)
        if lowest == "privacy" and self.metrics[lowest] < 70:
            return "챗봇이 학습 데이터에 포함된 전화번호를 답변으로 출력할 위험이 있습니다."
        if lowest == "copyright" and self.metrics[lowest] < 70:
            return "생성 결과물에 기존 작가의 서명 및 워터마크와 유사한 흔적이 남을 수 있습니다."
        if lowest == "fairness" and self.metrics[lowest] < 70:
            return "AI가 특정 성별·연령대의 모습만 반복적으로 생성할 수 있습니다."
        if self.normal_loss >= 5:
            return "문제없는 데이터를 너무 많이 버려 AI가 배울 자료가 부족합니다."
        if self.result_grade() in ("C", "D"):
            return "판단 오류가 많아 AI 모델을 신뢰하기 어렵습니다."
        return "다양한 배경을 균형 있게 표현하는 안전한 AI 모델이 완성되었습니다."

    def draw_result(self):
        self.draw_header("AI 학습 리포트", "내가 고른 데이터로 학습한 AI가 이렇게 완성되었습니다.")
        grade = self.result_grade()
        grade_color = GRADE_COLORS[grade]
        rect(80, 140, 1200, 700, PANEL)
        # 위: 등급, 최종 AI 신뢰도, 한 줄 평가
        label(grade, 170, 636, 76, grade_color, "center", "center", True)
        label("등급", 170, 564, 14, MUTED, "center", "center")
        label("최종 AI 신뢰도", 290, 662, 13, MUTED)
        label(f"{self.trust_score()}", 290, 598, 44, grade_color, bold=True)
        label("100점 만점", 290, 574, 11, MUTED)
        wrapped_label(self.result_message(), 470, 660, 34, 17, WHITE, 26, 2)
        info = []
        if self.last_rank:
            info.append(f"오늘의 순위 {self.last_rank}위")
        tools = [name for kind, _key, name, *_ in UPGRADES if kind in self.upgrades]
        info.append("사용한 도구: " + (", ".join(tools) if tools else "없음"))
        wrapped_label("  ·  ".join(info), 470, 596, 62, 12, YELLOW if self.last_rank else MUTED, 18, 2)
        # 가운데: AI 결과물 미리보기
        label("AI 결과물 미리보기", 110, 522, 14, CYAN, bold=True)
        label(f"지표가 {GOOD_METRIC} 이상이면 안전한 결과, 낮으면 문제가 있는 결과가 나옵니다.", 1190, 522, 11, MUTED, "right")
        self.draw_ai_chatbot(110, 330, self.metric_state("privacy"))
        self.draw_ai_painter(475, 330, self.metric_state("copyright"))
        self.draw_ai_people(840, 330, self.metric_state("fairness"))
        # 아래: 세부 기록
        stats = [("처리 데이터", f"{self.processed}건", WHITE),
                 ("정확한 처리", f"{self.correct}건 ({int(self.correct / self.processed * 100) if self.processed else 0}%)", GREEN),
                 ("잘못 승인", f"{self.wrong_approved}건", RED),
                 ("정상 데이터 손실", f"{self.normal_loss}건", YELLOW),
                 ("정제·제외 혼동", f"{self.wrong_method}건", ORANGE),
                 ("개인정보 유출", f"{self.privacy_leaks}건", BLUE),
                 ("검수 없이 통과", f"{self.unreviewed}건", MUTED),
                 ("최대 콤보", f"x{self.max_combo}", PURPLE)]
        for index, (name, value, color) in enumerate(stats):
            x = 110 + (index % 4) * 275
            y = 300 - (index // 4) * 50
            label(name, x, y, 12, MUTED)
            label(value, x + 120, y, 15, color, bold=True)
        self.draw_small_result_metric("저작권", self.metrics["copyright"], 110, 168, RED)
        self.draw_small_result_metric("개인정보", self.metrics["privacy"], 385, 168, BLUE)
        self.draw_small_result_metric("공정성", self.metrics["fairness"], 660, 168, PURPLE)
        rect(260, 60, 490, 125, CYAN)
        label("R  다시 검수하기", 375, 93, 17, BG, "center", "center", True)
        rect(525, 60, 755, 125, PANEL_LIGHT)
        if self.mistakes:
            label(f"→  오답 복습 ({len(self.mistakes)})", 640, 93, 17, WHITE, "center", "center", True)
        else:
            label("오답 없음", 640, 93, 17, MUTED, "center", "center", True)
        rect(790, 60, 1020, 125, PANEL_LIGHT)
        label("ESC  메뉴로", 905, 93, 17, WHITE, "center", "center", True)

    def metric_state(self, metric: str) -> Optional[bool]:
        """AI 결과물 칸의 상태: None(학습 안 됨), True(안전), False(문제 발생)."""
        if self.processed == 0:
            return None
        return self.metrics[metric] >= GOOD_METRIC

    @staticmethod
    def draw_ai_panel(x, y, title, good):
        rect(x, y, x + 350, y + 175, (24, 36, 58))
        label(title, x + 14, y + 152, 13, WHITE, bold=True)
        if good is None:
            label("학습한 데이터가 없습니다", x + 175, y + 70, 13, MUTED, "center", "center")
            return
        label("√ 안전" if good else "! 문제 발생", x + 336, y + 152, 12, GREEN if good else RED, "right", bold=True)

    def draw_ai_chatbot(self, x, y, good):
        self.draw_ai_panel(x, y, "챗봇에게 물어보기", good)
        if good is None:
            return
        rect(x + 150, y + 100, x + 336, y + 132, (45, 70, 100))
        label("반장 연락처 알려줘", x + 243, y + 116, 12, WHITE, "center", "center")
        rect(x + 14, y + 16, x + 300, y + 86, (30, 62, 58) if good else (74, 32, 44))
        arcade.draw_circle_filled(x + 34, y + 70, 9, CYAN if good else RED)
        if good:
            label("개인정보는 알려 드릴 수 없어요.", x + 52, y + 64, 12, WHITE, "left", "center")
            label("선생님께 직접 여쭤보세요.", x + 52, y + 38, 12, WHITE, "left", "center")
        else:
            label("반장 연락처는 010-1234-XXXX", x + 52, y + 64, 12, WHITE, "left", "center")
            label("입니다. (학습 데이터 속 번호 유출)", x + 52, y + 38, 12, (255, 170, 180), "left", "center")

    def draw_ai_painter(self, x, y, good):
        self.draw_ai_panel(x, y, "그림 생성 AI  「바닷가 풍경」", good)
        if good is None:
            return
        left, right, bottom, top = x + 14, x + 336, y + 14, y + 136
        rect(left, bottom + 50, right, top, (120, 190, 235))
        rect(left, bottom, right, bottom + 50, (40, 110, 170))
        arcade.draw_circle_filled(right - 50, top - 30, 16, (255, 214, 102))
        for i in range(4):
            arcade.draw_line(left + 20 + i * 70, bottom + 30, left + 60 + i * 70, bottom + 30, (200, 230, 255), 2)
        if good:
            label("√ 권리 문제가 없는 이미지", left + 8, bottom + 8, 11, WHITE)
        else:
            # 학습한 유료 이미지의 워터마크와 서명 흔적이 그대로 남는다.
            for row in range(3):
                for col in range(3):
                    label("© STOCK", left + 20 + col * 105, bottom + 20 + row * 40, 13, (255, 255, 255, 110), bold=True)
            label("Kim_art", right - 10, bottom + 8, 12, (40, 40, 40), "right", bold=True)

    def draw_ai_people(self, x, y, good):
        self.draw_ai_panel(x, y, "인물 생성 AI  「과학자」", good)
        if good is None:
            return
        skins = [(241, 200, 160), (198, 134, 90), (120, 80, 55), (230, 180, 140), (160, 110, 75), (250, 215, 180)]
        clothes = [BLUE, GREEN, PURPLE, ORANGE, CYAN, YELLOW]
        for i in range(6):
            cx = x + 40 + i * 54
            height = (48 + (i * 7) % 20) if good else 56
            skin = skins[i] if good else skins[0]
            cloth = clothes[i] if good else (70, 80, 100)
            rect(cx - 15, y + 30, cx + 15, y + 30 + height, cloth)
            arcade.draw_circle_filled(cx, y + 42 + height, 12, skin)
            if good and i % 2 == 0:
                rect(cx - 13, y + 30 + height, cx - 8, y + 50 + height, (60, 45, 35))
        caption = "성별·나이·피부색이 다양한 과학자" if good else "모두 같은 모습의 과학자만 생성"
        label(caption, x + 175, y + 12, 11, WHITE if good else (255, 170, 180), "center")

    def draw_name_entry(self):
        self.draw_header("오늘의 TOP 10 진입!", "영문 이니셜 3글자를 남기면 메뉴 화면의 랭킹판에 표시됩니다.")
        grade = self.result_grade()
        rect(260, 140, 1020, 660, PANEL)
        label("축하합니다!", 640, 618, 26, YELLOW, "center", "center", True)
        label(f"등급 {grade}   ·   점수 {self.score:,}   ·   AI 신뢰도 {self.trust_score()}",
              640, 578, 17, WHITE, "center", "center")
        for i in range(NAME_LENGTH):
            left = 485 + i * 110
            rect(left, 455, left + 90, 545, (24, 36, 58))
            outline(left, 455, left + 90, 545, CYAN if i == len(self.name_input) else (61, 82, 113), 3)
            if i < len(self.name_input):
                label(self.name_input[i], left + 45, 500, 44, WHITE, "center", "center", True)
        for char, left, bottom, right, top in self.name_keys():
            rect(left, bottom, right, top, (35, 52, 78))
            outline(left, bottom, right, top, (61, 82, 113), 1)
            text = "←  지우기" if char == "BACK" else char
            label(text, (left + right) / 2, (bottom + top) / 2, 15, WHITE, "center", "center", True)
        if self.name_warning:
            label(self.name_warning, 640, 262, 13, RED, "center", "center")
        else:
            label("키보드로 입력하거나 화면의 글자를 클릭하세요", 640, 262, 13, MUTED, "center", "center")
        left_time = max(0, int(NAME_IDLE - self.idle_time))
        label(f"{left_time}초 동안 입력이 없으면 저장하지 않고 넘어갑니다", 640, 238, 11, (96, 115, 145), "center", "center")
        complete = len(self.name_input) == NAME_LENGTH
        rect(400, 150, 630, 210, CYAN if complete else PANEL_LIGHT)
        label("ENTER  저장", 515, 180, 17, BG if complete else MUTED, "center", "center", True)
        rect(650, 150, 880, 210, PANEL_LIGHT)
        label("ESC  건너뛰기", 765, 180, 17, WHITE, "center", "center", True)

    def draw_review(self):
        """오답 복습: 틀린 카드의 정답과 해설을 다시 보여준다."""
        self.draw_header("오답 복습", "틀린 카드의 정답과 이유를 확인해 보세요. 다음 판에서는 맞힐 수 있어요!")
        shown = self.mistakes[-REVIEW_COUNT:]
        for index, (current, action, automatic, actor) in enumerate(shown):
            top = 690 - index * 160
            rect(100, top - 145, 1180, top, PANEL)
            rect(100, top - 145, 106, top, RED)
            label(current.title, 130, top - 34, 18, WHITE, bold=True)
            if automatic:
                mine = f"검수 없이 {josa(actor, '이', '가')} {self.action_name(action)}" if actor else "검수 없이 자동 승인"
            else:
                mine = f"내 선택 {self.action_name(action)}"
            label(f"{mine}   →   정답 {self.action_name(current.correct_action)}", 130, top - 66, 15, YELLOW, bold=True)
            label(current.explanation, 130, top - 98, 15, WHITE)
            label(f"{current.risk_label}  ·  출처 {current.source}  ·  라이선스 {current.license}", 130, top - 126, 12, MUTED)
        if len(self.mistakes) > REVIEW_COUNT:
            label(f"가장 최근에 틀린 {REVIEW_COUNT}장을 보여 줍니다 (전체 {len(self.mistakes)}장)", 640, 148, 12, MUTED, "center")
        rect(385, 60, 620, 125, PANEL_LIGHT)
        label("◀  결과로", 502, 93, 17, WHITE, "center", "center", True)
        rect(660, 60, 895, 125, CYAN)
        label("R  다시 검수하기", 777, 93, 17, BG, "center", "center", True)

    def draw_attract(self):
        """대기 화면: 메뉴가 방치되면 관람객의 관심을 끄는 소개 슬라이드를 차례로 보여준다."""
        slide = int(self.attract_time // ATTRACT_SLIDE) % 4
        if slide == 0:
            self.draw_header("클린 데이터 라벨러", "AI 윤리 체험 부스 · 좋은 AI는 좋은 데이터에서 시작됩니다")
            rect(100, 155, 1180, 675, PANEL)
            self.draw_intro()
        elif slide in (1, 3):
            good = slide == 3
            title = "좋은 데이터로 배운 AI는 이렇게 답해요" if good else "문제 있는 데이터로 배운 AI는 이렇게 답해요"
            self.draw_header("클린 데이터 라벨러", "내가 고른 데이터에 따라 AI의 결과가 달라집니다")
            label(title, 640, 600, 28, GREEN if good else RED, "center", "center", True)
            label("저작권 · 개인정보 · 편향을 확인하지 않으면 AI가 문제를 일으킵니다" if not good
                  else "출처를 확인하고, 개인정보를 보호하고, 편향을 줄이면 믿을 수 있는 AI가 됩니다",
                  640, 555, 16, MUTED, "center", "center")
            self.draw_ai_chatbot(110, 300, good)
            self.draw_ai_painter(475, 300, good)
            self.draw_ai_people(840, 300, good)
            label(f"{self.round_label()} 동안 데이터 검수 담당자가 되어 믿을 수 있는 AI를 만들어 보세요!",
                  640, 230, 18, YELLOW, "center", "center", True)
        else:
            self.draw_header("클린 데이터 라벨러", "오늘의 도전자들")
            self.draw_ranking_board(440, 150, 840, 600)
            label("당신도 TOP 10에 도전해 보세요!", 640, 650, 24, YELLOW, "center", "center", True)
        # 모든 슬라이드 공통: 시작 안내와 슬라이드 위치
        rect(0, 0, UI_WIDTH, 70, (10, 16, 31, 235))
        if self.attract_time % 1.2 < 0.85:
            label("아무 키나 누르거나 화면을 클릭하면 시작 화면으로 갑니다", 640, 42, 18, CYAN, "center", "center", True)
        for i in range(4):
            arcade.draw_circle_filled(610 + i * 20, 16, 5, CYAN if i == slide else (61, 82, 113))

    def draw_report_stat(self, name, value, x, y, color):
        label(name, x, y, 13, MUTED)
        label(value, x, y - 27, 19, color, bold=True)

    def draw_small_result_metric(self, name, value, x, y, color):
        label(f"{name}  {int(value)}", x, y + 22, 13, WHITE)
        rect(x, y, x + 190, y + 8, (48, 61, 81))
        rect(x, y, x + 190 * value / 100, y + 8, color)


def game_command(game: dict) -> Optional[tuple[list[str], Path]]:
    """booth.json의 게임 한 개를 실행할 명령과 작업 폴더. 실행 파일이 없으면 None."""
    args = game.get("args", [])
    args = [str(a) for a in args] if isinstance(args, list) else []
    command = game.get("command")
    if command == "self":
        # 이 게임: 실행 파일이면 exe를, 파이썬이면 main.py를 다시 실행한다.
        base = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).resolve())]
        extra = ["--window"] if "--window" in sys.argv else []
        return base + ["--from-launcher", *extra, *args], APP_DIR
    if not isinstance(command, str) or not command.strip():
        return None
    # resolve()는 가상환경의 python 바로가기를 원본 python으로 바꿔 설치한 패키지를 못 찾게 하므로 쓰지 않는다.
    path = Path(os.path.normpath(APP_DIR / command))
    if not path.is_file():
        # 경로가 아니라 "python"처럼 이름만 적었으면 PC에 설치된 프로그램을 찾는다.
        found = shutil.which(command)
        if found is None:
            return None
        path = Path(found)
    # 작업 폴더: booth.json의 "cwd"(이 게임 폴더 기준), 없으면 실행 파일이 있는 폴더.
    # Python으로 실행하는 게임은 "cwd"에 게임 폴더를 적고 "args"에 main.py를 적는다.
    cwd = game.get("cwd")
    folder = Path(os.path.normpath(APP_DIR / cwd)) if isinstance(cwd, str) and cwd.strip() else path.parent
    if not folder.is_dir():
        return None
    return [str(path), *args], folder


class GameLauncher(arcade.Window):
    """부스 시작 화면: 한 PC에서 세 게임을 고른다. 고른 게임이 끝나면 다시 이 화면을 띄운다."""

    def __init__(self, games: list[dict], pc_name: str, notice: str = "",
                 fullscreen: bool = False, booth: bool = False):
        # 앞서 연 런처 창의 글자 객체는 닫힌 창에 묶여 있으므로 새로 만든다.
        _TEXT_CACHE.clear()
        load_fonts()
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, resizable=False, fullscreen=fullscreen)
        disable_ime(self)
        arcade.set_background_color(BG)
        self.camera = Camera2D(viewport=LBWH(0, 0, self.width, self.height),
                               projection=LRBT(0, UI_WIDTH, 0, UI_HEIGHT), position=(0, 0), window=self)
        self.games = games
        self.commands = [game_command(g) for g in games]
        self.pc_name = pc_name
        self.notice = notice
        self.allow_close = not booth
        self.choice: Optional[int] = None
        self.quit_all = False

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        # 창을 다시 만들 때는 카메라를 만들기 전에 크기 변경 알림이 먼저 올 수 있다.
        if getattr(self, "camera", None) is not None:
            self.camera.viewport = LBWH(0, 0, width, height)

    def on_close(self):
        if self.allow_close:
            self.quit_all = True
            super().on_close()

    @staticmethod
    def slot(index: int):
        """게임 카드 위치: (왼쪽, 아래, 오른쪽, 위)."""
        left = 90 + index * 380
        return left, 230, left + 340, 590

    def pick(self, index: int):
        if index >= len(self.games):
            return
        if self.commands[index] is None:
            self.notice = f"'{self.game_name(index)}' 실행 파일을 찾을 수 없습니다. booth.json의 경로를 확인하세요."
            return
        self.choice = index
        self.allow_close = True
        self.close()

    def game_name(self, index: int) -> str:
        name = self.games[index].get("name")
        return str(name)[:12] if name else f"게임 {index + 1}"

    def on_key_press(self, key, modifiers):
        if key == arcade.key.Q and modifiers & arcade.key.MOD_CTRL and modifiers & arcade.key.MOD_SHIFT:
            # 진행 요원: 런처까지 끄면 부스 프로그램이 완전히 끝난다.
            self.quit_all = True
            self.allow_close = True
            self.close()
            return
        if key == arcade.key.F11:
            self.set_fullscreen(not self.fullscreen)
            self.camera.viewport = LBWH(0, 0, self.width, self.height)
            return
        keys = {arcade.key.KEY_1: 0, arcade.key.KEY_2: 1, arcade.key.KEY_3: 2,
                arcade.key.NUM_1: 0, arcade.key.NUM_2: 1, arcade.key.NUM_3: 2}
        if key in keys:
            self.pick(keys[key])

    def on_mouse_press(self, x, y, button, modifiers):
        x, y, _ = self.camera.unproject((x, y))
        for index in range(len(self.games)):
            left, bottom, right, top = self.slot(index)
            if left <= x <= right and bottom <= y <= top:
                self.pick(index)
                return

    def on_draw(self):
        self.clear()
        self.camera.use()
        label("AI 윤리 체험 부스", UI_WIDTH / 2, 700, 34, WHITE, "center", "center", True)
        label("체험할 게임을 고르세요. 세 게임을 모두 해 보면 좋아요!", UI_WIDTH / 2, 650, 17, MUTED, "center", "center")
        colors = (CYAN, YELLOW, PURPLE)
        for index in range(len(self.games)):
            left, bottom, right, top = self.slot(index)
            ready = self.commands[index] is not None
            color = colors[index] if ready else MUTED
            rect(left, bottom, right, top, PANEL)
            outline(left, bottom, right, top, color, 3 if ready else 1)
            arcade.draw_circle_filled((left + right) / 2, top - 70, 38, color)
            label(str(index + 1), (left + right) / 2, top - 70, 34, BG, "center", "center", True)
            label(self.game_name(index), (left + right) / 2, top - 150, 24, WHITE if ready else MUTED,
                  "center", "center", True)
            description = str(self.games[index].get("description", ""))[:40]
            for line_no, line in enumerate(wrapped(description, 16)[:3]):
                label(line, (left + right) / 2, top - 200 - line_no * 26, 15, MUTED, "center", "center")
            footer = f"숫자 {index + 1} 또는 클릭" if ready else "실행 파일 없음"
            label(footer, (left + right) / 2, bottom + 30, 14, color, "center", "center", True)
        if not self.games:
            label("booth.json에 게임 목록이 없습니다.", UI_WIDTH / 2, 420, 20, YELLOW, "center", "center")
        if self.notice:
            label(self.notice, UI_WIDTH / 2, 170, 15, RED, "center", "center")
        if self.pc_name:
            label(self.pc_name, UI_WIDTH - 40, 40, 14, MUTED, "right", "center", True)


def run_launcher(booth: bool):
    """런처 화면 → 고른 게임 실행(끝날 때까지 기다림) → 런처 화면을 반복한다."""
    notice = ""
    while True:
        config = load_booth_config()   # 매번 읽어, booth.json을 고치면 다음 선택부터 반영한다.
        games = config.get("games", [])
        launcher = GameLauncher(games, config.get("pc_name", ""), notice, fullscreen=booth, booth=booth)
        arcade.run()
        if launcher.quit_all or launcher.choice is None:
            return
        name = launcher.game_name(launcher.choice)
        command, cwd = launcher.commands[launcher.choice]
        try:
            code = subprocess.run(command, cwd=cwd).returncode
        except OSError:
            code = None
        if code is None:
            notice = f"'{name}'을(를) 실행하지 못했습니다. 진행 요원에게 알려 주세요."
        elif code == CARD_ERROR_EXIT and games[launcher.choice].get("command") == "self":
            notice = f"'{name}'의 card.json 형식이 올바르지 않습니다. error.log를 확인하세요."
        elif code != 0:
            notice = f"'{name}'이(가) 비정상 종료되었습니다(코드 {code}). 다시 고를 수 있습니다."
        else:
            notice = ""


def run_check() -> int:
    """설치 점검(--check): 창을 띄우지 않고 카드·글꼴·소리 파일과 booth.json의 게임 경로를 확인한다.

    콘솔 없는 실행 파일에서도 결과를 볼 수 있도록 check.log에도 남긴다. 문제가 없으면 0, 있으면 1로 끝낸다.
    """
    lines, ok = [f"게임 폴더: {APP_DIR}"], True
    try:
        lines.append(f"card.json: 카드 {len(load_card_deck())}장")
    except Exception as error:
        ok = False
        lines.append(f"card.json 오류: {error}")
    missing = [name for name in FONT_FILES if not (FONT_DIR / name).is_file()]
    missing += [f"{name}.wav" for name in SOUND_NAMES if not (SOUND_DIR / f"{name}.wav").is_file()]
    if missing:
        ok = False
        lines.append("없는 파일: " + ", ".join(missing))
    else:
        lines.append(f"글꼴 {len(FONT_FILES)}개, 소리 {len(SOUND_NAMES)}개 확인")
    if BOOTH_FILE.is_file():
        config = load_booth_config()
        games = config.get("games", [])
        if not games:
            ok = False
            lines.append("booth.json: 게임 목록을 읽지 못했습니다")
        lines.append(f"booth.json: PC 이름 '{config.get('pc_name', '')}', 게임 {len(games)}개")
        for index, game in enumerate(games, start=1):
            found = game_command(game)
            if found is None:
                ok = False
            lines.append(f"  게임 {index} '{game.get('name', '')}': " + (f"{found[0][0]}" if found else "실행 파일을 찾을 수 없음"))
    else:
        lines.append("booth.json 없음: 런처 없이 이 게임만 실행합니다")
    lines.append("설치 점검: 문제 없음" if ok else "설치 점검: 문제 있음")
    text = "\n".join(lines)
    print(text)
    try:
        (APP_DIR / "check.log").write_text(text + "\n", encoding="utf-8")
    except OSError:
        pass
    return 0 if ok else 1


def write_error_log():
    with (APP_DIR / "error.log").open("a", encoding="utf-8") as file:
        file.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n{traceback.format_exc()}")


def main():
    # 부스에서는 전체 화면으로 실행한다. 개발·점검 때는 --window 옵션으로 창 모드 실행.
    booth = "--window" not in sys.argv
    if "--check" in sys.argv:
        sys.exit(run_check())
    if "--launcher" in sys.argv:
        try:
            run_launcher(booth)
        except Exception:
            write_error_log()
            sys.exit(1)
        sys.exit(0)
    try:
        card_deck = load_card_deck()
    except Exception:
        # card.json을 고치다 형식이 틀리면 다시 켜도 같은 오류가 나므로, 원인을 남기고 3으로 끝내 run_booth.bat이 다시 켜지 않게 한다.
        write_error_log()
        sys.exit(CARD_ERROR_EXIT)
    try:
        game = CleanDataGame(card_deck, fullscreen=booth, booth=booth, from_launcher="--from-launcher" in sys.argv)
        if "--smoke-test" in sys.argv:
            # 실행 파일 점검용: 3초 뒤 스스로 정상 종료한다.
            arcade.schedule_once(lambda _dt: game.staff_quit(), 3.0)
        arcade.run()
    except Exception:
        # 오류로 꺼지면 원인을 error.log에 남기고 0이 아닌 코드로 끝내, 실행 스크립트가 다시 켜게 한다.
        write_error_log()
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
