from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(order=True, slots=True)
class Impact:
    timestamp_ms: int

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0:
            raise ValueError("An impact timestamp cannot be negative")


@dataclass(slots=True)
class EditorProject:
    video_path: str = ""
    title: str = ""
    team_one: str = ""
    team_two: str = ""
    pre_roll_ms: int = 4_000
    post_roll_ms: int = 3_000
    impacts: list[Impact] = field(default_factory=list)

    def add_impact(self, timestamp_ms: int) -> Impact:
        impact = Impact(timestamp_ms)
        self.impacts.append(impact)
        self.impacts.sort()
        return impact

    def remove_impact(self, index: int) -> Impact:
        return self.impacts.pop(index)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> EditorProject:
        raw = json.loads(value)
        raw.pop("title_duration_ms", None)
        raw["impacts"] = [Impact(**impact) for impact in raw.get("impacts", [])]
        return cls(**raw)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> EditorProject:
        return cls.from_json(path.read_text(encoding="utf-8"))


def format_timestamp(milliseconds: int) -> str:
    seconds, millis = divmod(max(0, milliseconds), 1_000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
