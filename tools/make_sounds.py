"""게임 효과음과 배경음을 직접 합성해 assets/sounds/에 WAV로 저장한다.

외부 음원을 쓰지 않으므로 저작권 확인이 필요 없다. 소리를 바꾸고 싶으면
이 파일을 고친 뒤 다시 실행한다.

실행:
    .\\venv\\Scripts\\python.exe tools\\make_sounds.py
"""

from __future__ import annotations

import math
import random
import wave
from array import array
from pathlib import Path

RATE = 22050
OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

NOTE_INDEX = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def freq(note: str) -> float:
    """'A4', 'C#5', 'Bb3' 같은 음 이름을 주파수로 바꾼다."""
    name, octave = note[:-1], int(note[-1])
    semitone = NOTE_INDEX[name[0]] + (1 if "#" in name else -1 if "b" in name else 0)
    return 440.0 * 2 ** ((semitone + (octave - 4) * 12) / 12)


def tone(f: float, seconds: float, wave_type="sine", volume=0.5,
         attack=0.01, release=0.08, slide_to: float | None = None) -> list[float]:
    count = int(RATE * seconds)
    samples = []
    phase = 0.0
    for i in range(count):
        t = i / RATE
        current = f if slide_to is None else f + (slide_to - f) * (i / count)
        phase += 2 * math.pi * current / RATE
        if wave_type == "sine":
            value = math.sin(phase)
        elif wave_type == "triangle":
            value = 2 / math.pi * math.asin(math.sin(phase))
        elif wave_type == "square":
            # 귀에 거슬리지 않도록 약하게 다듬은 사각파
            value = math.tanh(3 * math.sin(phase)) * 0.7
        else:  # noise
            value = random.uniform(-1, 1)
        envelope = min(1.0, t / attack) if attack else 1.0
        envelope *= min(1.0, (seconds - t) / release) if release else 1.0
        samples.append(value * envelope * volume)
    return samples


def silence(seconds: float) -> list[float]:
    return [0.0] * int(RATE * seconds)


def mix(*tracks: list[float]) -> list[float]:
    length = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(length)]


def save(name: str, samples: list[float]):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = array("h", (int(max(-1.0, min(1.0, s)) * 32767) for s in samples))
    with wave.open(str(OUT_DIR / f"{name}.wav"), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes(data.tobytes())
    print(f"{name}.wav  {len(samples) / RATE:.2f}초")


def music(tempo: int) -> list[float]:
    """C - Am - F - G 진행을 두 번 반복하는 밝은 배경음. 끝과 처음이 자연스럽게 이어진다."""
    beat = 60 / tempo
    chords = [("C3", ["C5", "E5", "G5", "E5"]), ("A2", ["A4", "C5", "E5", "C5"]),
              ("F2", ["F4", "A4", "C5", "A4"]), ("G2", ["G4", "B4", "D5", "B4"])] * 2
    bass, melody = [], []
    for root, arpeggio in chords:
        bass += tone(freq(root), beat * 4, "triangle", 0.28, 0.02, 0.1)
        for note in arpeggio:
            melody += tone(freq(note), beat, "sine", 0.16, 0.01, beat * 0.6)
    return mix(bass, melody)


def main():
    random.seed(7)
    save("correct", tone(freq("E6"), 0.07, volume=0.45) + tone(freq("A6"), 0.14, volume=0.45))
    save("combo", tone(freq("C6"), 0.07, volume=0.4) + tone(freq("E6"), 0.07, volume=0.4)
         + tone(freq("G6"), 0.07, volume=0.4) + tone(freq("C7"), 0.2, volume=0.4))
    save("wrong", tone(freq("A3"), 0.14, "square", 0.3) + tone(freq("F3"), 0.22, "square", 0.3))
    save("server_error", mix(tone(freq("E3"), 0.45, "square", 0.3, slide_to=freq("E2")),
                             tone(0, 0.45, "noise", 0.08)))
    save("buy", tone(freq("B5"), 0.06, volume=0.4) + tone(freq("E6"), 0.2, volume=0.4))
    save("select", tone(freq("A5"), 0.04, volume=0.25, release=0.03))
    save("end", tone(freq("C5"), 0.12, volume=0.4) + tone(freq("E5"), 0.12, volume=0.4)
         + tone(freq("G5"), 0.12, volume=0.4) + mix(tone(freq("C6"), 0.5, volume=0.35),
                                                     tone(freq("E5"), 0.5, volume=0.2)))
    save("bgm", music(100))
    save("bgm_fast", music(140))


if __name__ == "__main__":
    main()
