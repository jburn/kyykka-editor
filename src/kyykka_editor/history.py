"""Undo snapshots for timeline edits, independent of playback and match settings."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .model import EditorProject, Impact


@dataclass(slots=True)
class TimelineSnapshot:
    action: str
    impacts: list[Impact]
    round_one_end_ms: int | None
    game_end_ms: int | None
    selected_rows: tuple[int, ...]

    @classmethod
    def capture(
        cls, project: EditorProject, action: str, selected_rows: tuple[int, ...]
    ) -> TimelineSnapshot:
        return cls(
            action,
            deepcopy(project.impacts),
            project.round_one_end_ms,
            project.game_end_ms,
            selected_rows,
        )

    def restore(self, project: EditorProject) -> None:
        project.impacts = deepcopy(self.impacts)
        project.round_one_end_ms = self.round_one_end_ms
        project.game_end_ms = self.game_end_ms
