"""클린 데이터 라벨러 - Arcade 기반 교육형 타이쿤 프로토타입.

실행:
    .\\venv\\Scripts\\python.exe main.py
"""

from __future__ import annotations

import random
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import arcade
from arcade.camera import Camera2D
from arcade.types.rect import LBWH, LRBT


SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
# 게임 UI는 논리 좌표계에서 그린 뒤 표준 16:9 화면 전체에 맞춰 표시한다.
UI_WIDTH = 1280
UI_HEIGHT = 800
TEXT_SCALE_X = SCREEN_WIDTH / UI_WIDTH
TEXT_SCALE_Y = SCREEN_HEIGHT / UI_HEIGHT
SCREEN_TITLE = "클린 데이터 라벨러"
# card.json의 점수 값을 기획서 점수 규모로 환산하는 배율
SCORE_SCALE = 10
PENALTY_SCALE = 12
FONT = ("Malgun Gothic", "맑은 고딕", "Arial")

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
AI_ASSIST_ACCURACY = 0.85  # AI 판단 도우미의 추천이 정답일 확률

# 라이선스 확인 봇: 라이선스 문구의 키워드로 이용 조건을 한 줄 요약한다. 위에서부터 먼저 맞는 규칙을 쓴다.
LICENSE_RULES = [
    (("CC0", "퍼블릭 도메인", "공공영역", "공공저작물"), "권리 제한 없음, 자유 이용"),
    (("공공누리 1유형",), "출처 표시하면 상업 이용 가능"),
    (("BY-NC",), "비상업만 허용, 상업 AI 불가"),
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


def rect(left: float, bottom: float, right: float, top: float, color):
    arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, color)


def outline(left: float, bottom: float, right: float, top: float, color, width=2):
    arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, color, width)


def label(text: str, x: float, y: float, size: float = 16, color=WHITE,
          anchor_x: str = "left", anchor_y: str = "baseline", bold=False):
    # draw_text는 매 프레임 호출 시 느린 경고가 발생하므로 Text 객체를 사용한다.
    # 논리 좌표계에서 그린 글자를 확대하면 흐려지므로, 글자만 실제 창 해상도로 직접 그린다.
    window = arcade.get_window()
    window.default_camera.use()
    arcade.Text(str(text), x * TEXT_SCALE_X, y * TEXT_SCALE_Y, color, size * TEXT_SCALE_Y,
                font_name=FONT, anchor_x=anchor_x, anchor_y=anchor_y, bold=bold).draw()
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


def card(title, content_type, source, license, risks, action, explanation,
         reward, penalty, difficulty):
    return DataCard(title, content_type, source, license, tuple(risks), action,
                    explanation, reward, penalty, difficulty)


# 실제 개인정보가 아닌 교육용 가상 데이터만 사용한다.
CARD_DECK = [
    card("CC0로 표시된 바닷가 풍경", "이미지", "공개 아카이브", "CC0", ["safe"], "approve", "CC0 자료는 프로젝트 정책에 맞게 사용할 수 있습니다.", 100, 80, 1),
    card("직접 촬영한 상품 이미지", "이미지", "사내 스튜디오", "사내 제작", ["safe"], "approve", "회사가 직접 제작하고 권리를 보유한 데이터입니다.", 100, 80, 1),
    card("비식별화된 만족도 설문", "문서", "내부 설문", "사내 제작", ["safe"], "approve", "개인을 알아볼 수 없고 표본도 고르게 구성되어 있습니다.", 100, 80, 1),
    card("허가받은 폰트로 만든 포스터", "이미지", "디자인팀", "상업 이용 허가", ["safe"], "approve", "이용 범위가 확인된 폰트와 사내 디자인을 사용했습니다.", 100, 80, 1),
    card("다양한 연령의 거리 표정 데이터", "이미지", "현장 촬영팀", "촬영 동의 완료", ["safe"], "approve", "촬영 동의와 대표성 확인이 끝난 데이터입니다.", 110, 80, 1),
    card("야생동물 관찰 기록", "글", "오픈 데이터 포털", "CC BY", ["safe"], "approve", "출처를 기록하면 사용할 수 있는 공개 데이터입니다.", 100, 80, 1),
    card("워터마크가 있는 인물 사진", "이미지", "unknown_sns", "확인 불가", ["copyright"], "remove", "출처와 이용 허가를 확인할 수 없어 상업용 학습에서 제외합니다.", 140, 150, 1),
    card("출처 없는 블로그 글 전문", "글", "개인 블로그", "표기 없음", ["copyright"], "remove", "원문 전체를 허가 없이 수집했을 가능성이 높습니다.", 140, 150, 1),
    card("상업적 이용 금지 라이선스 이미지", "이미지", "사진 커뮤니티", "CC BY-NC", ["copyright"], "remove", "상업용 AI 서비스 정책과 맞지 않는 라이선스입니다.", 140, 150, 1),
    card("작가명 표기가 필요한 이미지", "이미지", "공개 갤러리", "CC BY", ["copyright"], "refine", "저작자 표시를 메타데이터에 추가한 뒤 사용해야 합니다.", 120, 120, 1),
    card("구매하지 않은 유료 폰트 포스터", "이미지", "디자인 커뮤니티", "개인용만 허용", ["copyright"], "remove", "상업용 데이터셋에서 사용할 권한이 없습니다.", 150, 160, 1),
    card("출처 링크가 잘린 기사 캡처", "글", "뉴스 SNS", "일부만 확인", ["copyright"], "remove", "출처와 이용 범위를 먼저 확인할 수 없는 자료입니다.", 140, 150, 2),
    card("이름과 전화번호가 있는 상담 기록", "문서", "고객센터", "내부 문서", ["privacy"], "refine", "이름과 연락처를 마스킹한 뒤 학습 데이터로 사용합니다.", 140, 170, 1),
    card("번호판이 선명한 거리 사진", "이미지", "거리 촬영팀", "촬영 동의 확인", ["privacy"], "refine", "차량 번호판을 블러 처리하면 식별 위험을 줄일 수 있습니다.", 130, 170, 1),
    card("이메일 주소가 포함된 문의 글", "글", "고객 문의함", "내부 문서", ["privacy"], "refine", "이메일 주소를 삭제하거나 가명으로 바꿔야 합니다.", 130, 170, 1),
    card("얼굴과 사원번호가 함께 있는 출입 기록", "문서", "출입 시스템", "민감 내부자료", ["privacy"], "remove", "얼굴과 사원번호가 함께 있어 단순 마스킹만으로 부족합니다.", 160, 200, 2),
    card("학생 이름이 있는 성적표", "문서", "학교 서버", "교육 기록", ["privacy"], "remove", "미성년자의 교육 기록은 이 프로젝트 데이터로 가져오지 않습니다.", 160, 200, 2),
    card("가상 주소가 있는 배송 메모", "문서", "테스트 주문", "테스트 데이터", ["privacy"], "refine", "실제 주소가 아니어도 식별자처럼 보이는 정보는 비식별화합니다.", 120, 170, 2),
    card("‘개발자는 모두 남성’ 라벨", "글", "검색 결과 묶음", "출처 기록", ["bias"], "refine", "성별 고정관념이 담긴 라벨을 중립적인 직무 라벨로 고칩니다.", 145, 150, 2),
    card("CEO 이미지가 모두 중년 남성", "이미지", "이미지 검색", "출처 불명", ["bias"], "refine", "표본의 다양성을 보완하고 대표성 부족을 기록해야 합니다.", 145, 150, 2),
    card("특정 지역 출신을 부정적으로 분류", "글", "커뮤니티 수집", "표기 없음", ["bias"], "remove", "출신 지역을 근거로 한 차별적 판단 데이터는 제외합니다.", 160, 170, 2),
    card("장애인을 모두 ‘도움 필요’로 라벨링", "이미지", "분류 데이터", "내부 제작", ["bias"], "refine", "사람을 한 가지 특성으로만 규정하지 않도록 라벨을 재설계합니다.", 150, 150, 2),
    card("남성이 요리하면 ‘비전문가’ 라벨", "이미지", "검색 데이터", "출처 기록", ["bias"], "refine", "성별과 전문성의 연결을 끊도록 라벨을 재검수합니다.", 145, 150, 2),
    card("특정 억양만 ‘정확한 발음’으로 분류", "음성", "음성 데이터셋", "라이선스 확인", ["bias"], "refine", "말투 차이를 능력의 우열로 라벨링하지 않도록 기준을 고칩니다.", 145, 150, 2),
    card("워터마크 + 얼굴 + 이름의 SNS 캡처", "이미지", "unknown_sns", "확인 불가", ["copyright", "privacy"], "remove", "권리와 식별 정보가 동시에 위험한 복합 데이터입니다.", 200, 240, 3),
    card("편향 문장과 작성자 이메일", "글", "커뮤니티 수집", "확인 불가", ["bias", "privacy"], "remove", "편향 표현과 연락처가 함께 있어 학습에서 제외합니다.", 200, 240, 3),
    card("출처 불명 이미지 + 직업 오라벨", "이미지", "검색 엔진", "확인 불가", ["copyright", "bias"], "remove", "권리 불명 자료이며 직업 라벨도 다시 확인할 수 없습니다.", 210, 240, 3),
    card("전화번호와 상업 이용 금지 이미지", "이미지", "고객 업로드", "CC BY-NC", ["privacy", "copyright"], "remove", "개인정보와 프로젝트 정책 위반이 함께 발견됩니다.", 210, 250, 3),
    card("출처는 있으나 얼굴 비식별화 누락", "이미지", "CC BY 갤러리", "CC BY", ["privacy", "copyright"], "refine", "출처를 유지하고 얼굴을 비식별화한 뒤 사용합니다.", 190, 210, 3),
    card("‘간호사는 여성’으로만 연결된 라벨", "글", "검색 결과 묶음", "출처 기록", ["bias"], "refine", "직업과 성별을 고정적으로 연결하지 않도록 재라벨링합니다.", 150, 150, 2),
    card("기부자 이름이 공개된 명단", "문서", "시민단체 자료", "공개 페이지", ["privacy"], "remove", "공개되어 있어도 이름 목록을 학습에 옮길 필요는 없습니다.", 160, 200, 2),
    card("무료 배포 이미지, 저작자 표기 누락", "이미지", "공개 갤러리", "CC BY", ["copyright"], "refine", "무료라는 말만으로 충분하지 않습니다. 저작자 표시를 보완합니다.", 120, 120, 2),
    card("팀이 촬영했지만 동의 기록 없음", "이미지", "사내 촬영", "기록 누락", ["privacy"], "remove", "촬영 동의 기록이 확인되지 않으면 보류하거나 제외해야 합니다.", 150, 190, 2),
    card("서로 다른 집단이 균형 잡힌 설문", "문서", "연구팀", "연구 동의", ["safe"], "approve", "대표성 검토가 끝난 균형 잡힌 데이터입니다.", 115, 80, 1),
    card("직접 쓴 제품 설명 문장", "글", "콘텐츠팀", "사내 제작", ["safe"], "approve", "회사가 직접 작성한 콘텐츠라 학습 권리를 확인할 수 있습니다.", 100, 80, 1),
]


CARD_FILE = Path(__file__).with_name("card.json")
REQUIRED_CARD_FIELDS = {
    "title", "content_type", "source", "license", "risk_types",
    "correct_action", "explanation", "reward", "penalty", "difficulty",
}
VALID_RISK_TYPES = {"safe", "copyright", "privacy", "bias"}
VALID_ACTIONS = {"approve", "refine", "remove"}


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
            title=str(item["title"]),
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


# 기존 예시 덱 대신 외부 카드 데이터 파일을 실제 게임 덱으로 사용한다.
CARD_DECK = load_card_deck()


class CleanDataGame(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, resizable=False)
        arcade.set_background_color(BG)
        self.camera = Camera2D(
            # 전체 16:9 화면을 사용해 좌우 레터박스를 제거한다.
            viewport=LBWH(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT),
            projection=LRBT(0, UI_WIDTH, 0, UI_HEIGHT),
            # projection을 (0, 0) 원점으로 사용하므로 카메라 이동은 없다.
            position=(0, 0),
            window=self,
        )
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
        self.privacy_leaks = 0
        self.copyright_issues = 0
        self.bias_issues = 0
        self.metrics = {"copyright": 100.0, "privacy": 100.0, "fairness": 100.0}
        self.upgrades: set[str] = set()
        self.feedback = "카드를 클릭해 상세 정보를 확인하세요."
        self.feedback_color = MUTED
        self.feedback_timer = 0.0

    def setup_game(self):
        self.game_screen = "game"
        self.cards = []
        self.selected = None
        self.deck = [DataCard(c.title, c.content_type, c.source, c.license,
                              c.risk_types, c.correct_action, c.explanation,
                              c.reward, c.penalty, c.difficulty) for c in CARD_DECK]
        random.shuffle(self.deck)
        self.deck_index = 0
        self.spawn_timer = 0.0
        self.elapsed = 0.0
        self.time_left = 180.0
        self.score = self.budget = self.combo = self.max_combo = 0
        self.processed = self.correct = self.wrong_approved = self.normal_loss = self.wrong_method = 0
        self.unreviewed = 0
        self.last_result = None
        self.paused = False
        self.privacy_leaks = self.copyright_issues = self.bias_issues = 0
        self.metrics = {"copyright": 100.0, "privacy": 100.0, "fairness": 100.0}
        self.upgrades = set()
        self.feedback = "첫 카드를 선택하세요. 숫자 키 1, 2, 3으로도 처리할 수 있습니다."
        self.feedback_color = CYAN
        self.feedback_timer = 4.0
        self.spawn_card(155)

    def spawn_card(self, x: Optional[float] = None):
        allowed = min(3, 1 + int(self.elapsed // 48))
        candidates = [c for c in self.deck[self.deck_index:] if c.difficulty <= allowed]
        if not candidates:
            random.shuffle(self.deck)
            self.deck_index = 0
            candidates = [c for c in self.deck if c.difficulty <= allowed]
        prototype = candidates[0]
        self.deck_index = self.deck.index(prototype, self.deck_index) + 1
        new_card = DataCard(prototype.title, prototype.content_type, prototype.source,
                            prototype.license, prototype.risk_types,
                            prototype.correct_action, prototype.explanation,
                            prototype.reward, prototype.penalty, prototype.difficulty,
                            x=x if x is not None else 140.0)
        if "ai_approve" in self.upgrades and new_card.risk_key == "safe" and random.random() < AI_APPROVE_CHANCE:
            new_card.ai_approve = True
        if new_card.risk_key == "mixed":
            # 추천은 카드가 나올 때 한 번 정해 두어, 볼 때마다 바뀌지 않게 한다.
            other = "remove" if new_card.correct_action == "refine" else "refine"
            new_card.ai_pick = new_card.correct_action if random.random() < AI_ASSIST_ACCURACY else other
        self.cards.append(new_card)

    def on_update(self, delta_time: float):
        if self.game_screen != "game" or self.paused:
            return
        self.time_left -= delta_time
        self.elapsed += delta_time
        self.feedback_timer = max(0.0, self.feedback_timer - delta_time)
        if self.time_left <= 0:
            self.time_left = 0
            self.game_screen = "result"
            return

        spawn_interval = max(5.0, 8.0 - self.elapsed * 0.017)
        self.spawn_timer += delta_time
        # 카드 폭(152)과 여백(18)을 확보한 뒤에만 새 카드를 생성한다.
        # 생성 주기보다 이동 속도가 빨라지는 후반에도 카드가 겹치지 않는다.
        can_spawn = not self.cards or self.cards[-1].x >= 310
        # 벨트가 비면 1초 뒤 바로 다음 카드를 보내, 빠른 플레이어가 더 많이 처리할 수 있게 한다.
        wait = 1.0 if not self.cards else spawn_interval
        if self.spawn_timer >= wait and can_spawn and len(self.cards) < 12:
            self.spawn_timer = 0
            self.spawn_card()

        speed = min(95, 40 + self.elapsed * 0.3)
        if "buffer" in self.upgrades:
            speed *= 0.7
        for current in self.cards[:]:
            current.x += speed * delta_time
            current.age += delta_time
            if current.ai_approve and current.x >= 450:
                self.ai_auto_approve(current)
            # 카드 오른쪽 끝이 서버 영역(1155)에 닿기 전에 자동 처리한다.
            elif current.x > 1079:
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
            self.score += earned
            self.budget += max(90, earned // 2)
            self.feedback = f"정확합니다! +{earned}점  '{current.title}' {self.action_name(action)} 처리 완료."
            self.feedback_color = GREEN
        else:
            self.combo = 0
            lost = self.wrong_penalty(current, action)
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
        if self.game_screen == "menu":
            if key in (arcade.key.SPACE, arcade.key.ENTER, arcade.key.NUM_1):
                self.setup_game()
            elif key == arcade.key.T:
                self.game_screen = "tutorial"
                self.tutorial_page = 0
            return
        if self.game_screen == "tutorial":
            if key == arcade.key.ESCAPE:
                self.game_screen = "menu"
            elif key in (arcade.key.RIGHT, arcade.key.SPACE, arcade.key.ENTER):
                if self.tutorial_page == 0:
                    self.tutorial_page = 1
                else:
                    self.game_screen = "menu"
            elif key == arcade.key.LEFT and self.tutorial_page == 1:
                self.tutorial_page = 0
            return
        if self.game_screen == "result":
            if key in (arcade.key.SPACE, arcade.key.ENTER, arcade.key.R):
                self.setup_game()
            elif key == arcade.key.ESCAPE:
                self.game_screen = "menu"
            return
        if self.game_screen == "game":
            if self.paused:
                if key == arcade.key.ESCAPE:
                    self.paused = False
                elif key == arcade.key.M:
                    self.paused = False
                    self.game_screen = "menu"
                return
            if key == arcade.key.ESCAPE:
                # 실수로 판이 끝나지 않도록 ESC는 일시정지 화면을 연다.
                self.paused = True
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
        if self.selected:
            self.process_card(self.selected, action)
        elif self.cards:
            # 선택 없이 누르면 바로 처리하지 않고, 먼저 카드를 보여준다.
            self.select_card(self.cards[0])
            self.feedback = "서버에 가장 가까운 카드를 선택했습니다. 내용을 확인하고 다시 누르세요."
            self.feedback_timer = 3.0
        else:
            self.feedback = "처리할 카드가 아직 없습니다."
            self.feedback_color = YELLOW
            self.feedback_timer = 2.0

    def on_mouse_press(self, x, y, button, modifiers):
        # 실제 1920×1080 픽셀 입력을 UI 논리 좌표(1280×800)로 변환한다.
        x, y, _ = self.camera.unproject((x, y))
        if self.game_screen == "menu":
            if 400 < x < 880 and 270 < y < 345:
                self.setup_game()
            elif 400 < x < 880 and 195 < y < 255:
                self.game_screen = "tutorial"
                self.tutorial_page = 0
            return
        if self.game_screen == "tutorial":
            if self.tutorial_page == 0 and 430 < x < 850 and 95 < y < 160:
                self.tutorial_page = 1
            elif self.tutorial_page == 1:
                if 150 < x < 440 and 95 < y < 160:
                    self.tutorial_page = 0
                elif 820 < x < 1130 and 95 < y < 160:
                    self.game_screen = "menu"
            return
        if self.game_screen == "result":
            if 385 < x < 620 and 90 < y < 155:
                self.setup_game()
            elif 660 < x < 895 and 90 < y < 155:
                self.game_screen = "menu"
            return
        if self.game_screen != "game":
            return
        if self.paused:
            if 440 < x < 840 and 360 < y < 420:
                self.paused = False
            elif 440 < x < 840 and 280 < y < 340:
                self.paused = False
                self.game_screen = "menu"
            return
        # 카드 클릭: 컨베이어에 보이는 카드의 중심 좌표를 기준으로 선택한다.
        for current in reversed(self.cards):
            if current.x - 78 <= x <= current.x + 78 and 480 <= y <= 602:
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
            if kind == "buffer":
                self.feedback = f"{name} 작동! 컨베이어가 30% 느려집니다."
            else:
                self.feedback = f"{name} 작동! 신호를 표시하지만 최종 판단은 직접 해야 합니다."
            self.feedback_color = GREEN
        self.feedback_timer = 3.0

    def visible_risks(self, current: DataCard) -> tuple[str, ...]:
        """보유한 탐지 도구로 찾아낸 위험 신호만 돌려준다."""
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
        else:
            self.draw_result()

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
        rect(400, 270, 880, 345, (35, 62, 86))
        outline(400, 270, 880, 345, CYAN, 2)
        label("▶  검수 라운드 시작", UI_WIDTH / 2, 308, 25, WHITE, "center", "center", True)
        rect(400, 195, 880, 255, PANEL)
        outline(400, 195, 880, 255, (61, 82, 113), 1)
        label("T  10초 튜토리얼 보기", UI_WIDTH / 2, 225, 18, MUTED, "center", "center")
        label("3분 동안 승인 · 정제 · 제외로 데이터를 지켜주세요", UI_WIDTH / 2, 146, 15, MUTED, "center")
        label("SPACE / ENTER로 시작", UI_WIDTH / 2, 112, 13, (91, 120, 158), "center")

    def draw_tutorial(self):
        self.draw_header("검수 튜토리얼", "빠른 판단보다 신뢰할 수 있는 판단이 중요합니다.")
        if self.tutorial_page == 1:
            self.draw_tutorial_upgrades()
            return
        rect(100, 155, 1180, 675, PANEL)
        label("데이터 카드 읽는 법", 145, 615, 24, CYAN, bold=True)
        steps = [("01", "카드 선택", "카드를 클릭하거나 ← → 키로 고르면 제목·출처·라이선스를 볼 수 있습니다. 위험 신호는 탐지 도구를 사야 표시됩니다.", CYAN),
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
        rect(430, 95, 850, 155, CYAN)
        label("다음: 업그레이드 보기  ▶", 640, 125, 18, BG, "center", "center", True)

    def draw_tutorial_upgrades(self):
        rect(100, 155, 1180, 675, PANEL)
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
        label("2 / 2", 640, 172, 12, (91, 120, 158), "center")
        rect(150, 95, 440, 155, PANEL_LIGHT)
        label("◀  이전 페이지", 295, 125, 17, WHITE, "center", "center", True)
        rect(820, 95, 1130, 155, CYAN)
        label("확인했습니다  ·  메뉴로", 975, 125, 17, BG, "center", "center", True)

    def draw_metric(self, name, value, x, y, color):
        label(name, x, y + 27, 14, MUTED)
        label(f"{int(value)}", x + 285, y + 25, 18, color, "right", "center", True)
        rect(x, y, x + 285, y + 9, (45, 58, 80))
        rect(x, y, x + 285 * value / 100, y + 9, color)

    def draw_game(self):
        self.draw_header("클린 데이터 라벨러", "상업용 AI 서비스 데이터셋 · 책임 있는 데이터 파이프라인")
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
        if self.paused:
            self.draw_pause()

    def draw_pause(self):
        rect(0, 0, UI_WIDTH, UI_HEIGHT, (10, 16, 31, 215))
        rect(390, 250, 890, 560, PANEL)
        outline(390, 250, 890, 560, CYAN, 2)
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
        elif self.has_all_detectors():
            label("✓ 감지된 신호 없음", 430, 222, 13, GREEN)
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
        return {"copyright": "© 저작권", "privacy": "▣ 개인정보", "bias": "⚖ 편향", "safe": "✓ 안전"}[risk]

    def draw_queue_card(self, current: DataCard):
        shown, color = self.shown_label(current)
        left, right = current.x - 76, current.x + 76
        rect(left + 3, 477, right + 3, 605, (7, 12, 23))
        rect(left, 480, right, 602, (32, 46, 69))
        rect(left, 592, right, 602, color)
        if current is self.selected:
            outline(left - 4, 476, right + 4, 606, CYAN, 3)
        elif "copyright" in self.visible_risks(current):
            # 워터마크 스캐너: 저작권 신호가 있는 카드에 붉은 테두리
            outline(left - 2, 478, right + 2, 604, RED, 2)
        label(shown, current.x, 580, 11, color, "center", "center", True)
        for index, title_line in enumerate(compact_card_title(current.title)):
            label(title_line, left + 10, 555 - index * 14, 11, WHITE)
        label(current.content_type, left + 10, 506, 11, MUTED)
        if current.ai_approve:
            label("AI 승인 대기", right - 10, 506, 10, CYAN, "right")

    def draw_action_button(self, x, key, name, color):
        rect(x, 38, x + 230, 108, (31, 48, 69))
        outline(x, 38, x + 230, 108, color, 2)
        label(key, x + 26, 73, 24, color, "center", "center", True)
        label(name, x + 125, 73, 20, WHITE, "center", "center", True)

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
        self.draw_header("AI 학습 리포트", "이번 라운드에서 데이터 파이프라인이 남긴 기록입니다.")
        grade = self.result_grade()
        grade_color = {"S": GREEN, "A": CYAN, "B": YELLOW, "C": ORANGE, "D": RED}[grade]
        rect(80, 125, 1200, 680, PANEL)
        label("FINAL MODEL", 140, 625, 14, CYAN, bold=True)
        label(grade, 185, 495, 150, grade_color, "center", "center", True)
        label("등급", 185, 345, 18, MUTED, "center")
        label(self.result_message(), 350, 590, 20, WHITE, bold=True)
        wrapped_label("좋은 AI는 많은 데이터를 모으는 것만으로 완성되지 않습니다. 출처를 확인하고, 개인정보를 보호하며, 편향을 줄이는 정제 과정이 필요합니다.", 350, 550, 49, 15, MUTED, 24, 3)
        self.draw_report_stat("처리 데이터", f"{self.processed}건", 350, 430, WHITE)
        self.draw_report_stat("정확한 처리", f"{self.correct}건 ({int(self.correct / self.processed * 100) if self.processed else 0}%)", 590, 430, GREEN)
        self.draw_report_stat("잘못 승인", f"{self.wrong_approved}건", 350, 380, RED)
        self.draw_report_stat("정상 데이터 손실", f"{self.normal_loss}건", 590, 380, YELLOW)
        self.draw_report_stat("정제·제외 혼동", f"{self.wrong_method}건", 830, 380, ORANGE)
        self.draw_report_stat("개인정보 유출", f"{self.privacy_leaks}건", 350, 330, BLUE)
        self.draw_report_stat("최대 콤보", f"x{self.max_combo}", 590, 330, PURPLE)
        self.draw_report_stat("검수 없이 통과", f"{self.unreviewed}건", 830, 330, MUTED)
        arcade.draw_line(350, 292, 1115, 292, (57, 74, 101), 1)
        label("최종 신뢰 지표", 350, 260, 14, MUTED)
        self.draw_small_result_metric("저작권", self.metrics["copyright"], 350, 218, RED)
        self.draw_small_result_metric("개인정보", self.metrics["privacy"], 590, 218, BLUE)
        self.draw_small_result_metric("공정성", self.metrics["fairness"], 830, 218, PURPLE)
        rect(385, 60, 620, 125, CYAN)
        label("R  다시 검수하기", 502, 93, 17, BG, "center", "center", True)
        rect(660, 60, 895, 125, PANEL_LIGHT)
        label("ESC  메뉴로", 777, 93, 17, WHITE, "center", "center", True)

    def draw_report_stat(self, name, value, x, y, color):
        label(name, x, y, 13, MUTED)
        label(value, x, y - 27, 19, color, bold=True)

    def draw_small_result_metric(self, name, value, x, y, color):
        label(f"{name}  {int(value)}", x, y + 22, 13, WHITE)
        rect(x, y, x + 190, y + 8, (48, 61, 81))
        rect(x, y, x + 190 * value / 100, y + 8, color)


def main():
    CleanDataGame()
    arcade.run()


if __name__ == "__main__":
    main()
