from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .i18n import tr


@dataclass(order=True, slots=True)
class Impact:
    timestamp_ms: int
    thrower: str = field(default="", compare=False)
    pre_roll_ms: int | None = field(default=None, compare=False)
    post_roll_ms: int | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0:
            raise ValueError("An impact timestamp cannot be negative")
        if any(value is not None and value < 0 for value in (self.pre_roll_ms, self.post_roll_ms)):
            raise ValueError("An impact timing override cannot be negative")


@dataclass(slots=True)
class CardStyle:
    font_family: str = "Arial"
    background_color: str = "#2a76bc"
    text_color: str = "#ffffff"
    background_image: str = ""


@dataclass(slots=True)
class EditorProject:
    title_style: CardStyle = field(default_factory=CardStyle)
    round_style: CardStyle = field(default_factory=CardStyle)
    final_style: CardStyle = field(default_factory=CardStyle)
    video_path: str = ""
    title: str = ""
    team_one: str = ""
    team_two: str = ""
    team_one_players: list[str] = field(default_factory=list)
    team_two_players: list[str] = field(default_factory=list)
    team_one_round_one_score: int = 0
    team_two_round_one_score: int = 0
    team_one_round_two_score: int = 0
    team_two_round_two_score: int = 0
    round_one_end_ms: int | None = None
    game_end_ms: int | None = None
    pre_roll_ms: int = 4_000
    post_roll_ms: int = 3_000
    impacts: list[Impact] = field(default_factory=list)

    def add_impact(self, timestamp_ms: int, thrower: str = "") -> Impact:
        impact = Impact(timestamp_ms, thrower.strip())
        self.impacts.append(impact)
        self.impacts.sort()
        return impact

    def remove_impact(self, index: int) -> Impact:
        return self.impacts.pop(index)

    def timing_for(self, impact: Impact) -> tuple[int, int]:
        return (
            self.pre_roll_ms if impact.pre_roll_ms is None else impact.pre_roll_ms,
            self.post_roll_ms if impact.post_roll_ms is None else impact.post_roll_ms,
        )

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


def format_timestamp(milliseconds: int) -> str:
    seconds, millis = divmod(max(0, milliseconds), 1_000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def default_export_filename(project: EditorProject) -> str:
    title = project.title.strip() or tr("Kyykka highlights")
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
