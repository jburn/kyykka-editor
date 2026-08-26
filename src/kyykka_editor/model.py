from __future__ import annotations

import json
import re
import unicodedata
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
    team_one_round_one_score: int = 0
    team_two_round_one_score: int = 0
    team_one_round_two_score: int = 0
    team_two_round_two_score: int = 0
    round_one_end_ms: int | None = None
    game_end_ms: int | None = None
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

    @property
    def team_one_total(self) -> int:
        return self.team_one_round_one_score + self.team_one_round_two_score

    @property
    def team_two_total(self) -> int:
        return self.team_two_round_one_score + self.team_two_round_two_score

    @property
    def winner(self) -> str | None:
        if self.team_one_total == self.team_two_total:
            return None
        if self.team_one_total > self.team_two_total:
            return self.team_one or "Team 1"
        return self.team_two or "Team 2"

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


def default_export_filename(project: EditorProject) -> str:
    title = project.title.strip() or "Kyykka highlights"
    teams = [name.strip() for name in (project.team_one, project.team_two) if name.strip()]
    if teams and not all(name.casefold() in title.casefold() for name in teams):
        title = f"{title} - {' vs. '.join(teams)}"

    ascii_name = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    safe_name = re.sub(r"[^a-z0-9]+", "_", ascii_name.casefold()).strip("_")
    safe_name = safe_name[:140].rstrip("_") or "kyykka_highlights"
    reserved = {"con", "prn", "aux", "nul"} | {
        f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
    }
    if safe_name.casefold() in reserved:
        safe_name = f"kyykka_{safe_name}"
    return f"{safe_name}.mp4"
