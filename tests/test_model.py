import pytest

from kyykka_editor.model import (
    EditorProject,
    Impact,
    default_export_filename,
    format_timestamp,
)


def test_impacts_are_sorted_when_added() -> None:
    project = EditorProject()
    project.add_impact(5_000, "Second")
    project.add_impact(1_000, "First")
    assert [impact.timestamp_ms for impact in project.impacts] == [1_000, 5_000]
    assert [impact.thrower for impact in project.impacts] == ["First", "Second"]


def test_project_json_round_trip() -> None:
    original = EditorProject(
        video_path="match.mp4",
        team_one_players=["Matti", "Maija"],
        team_two_players=["Liisa"],
        impacts=[Impact(1_234, "Matti")],
    )
    assert EditorProject.from_json(original.to_json()) == original


def test_legacy_title_duration_is_ignored() -> None:
    project = EditorProject.from_json('{"title_duration_ms": 9000, "impacts": []}')
    assert project == EditorProject()


def test_negative_impact_is_rejected() -> None:
    with pytest.raises(ValueError):
        Impact(-1)


def test_timestamp_format() -> None:
    assert format_timestamp(3_723_004) == "01:02:03.004"


def test_export_filename_uses_title_and_teams() -> None:
    project = EditorProject(title="Playoffs (game 3)", team_one="Team 1", team_two="Team 2")
    assert default_export_filename(project) == "playoffs_game_3_team_1_vs_team_2.mp4"


def test_export_filename_does_not_repeat_teams_and_is_windows_safe() -> None:
    project = EditorProject(
        title="Playoffs: Team 1 vs. Team 2 / game 3",
        team_one="Team 1",
        team_two="Team 2",
    )
    assert default_export_filename(project) == "playoffs_team_1_vs_team_2_game_3.mp4"


def test_export_filename_transliterates_accents() -> None:
    project = EditorProject(title="Kyykkäfinaali", team_one="Häme", team_two="Päijät")
    assert default_export_filename(project) == "kyykkafinaali_hame_vs_paijat.mp4"


def test_game_total_and_winner_use_both_rounds() -> None:
    project = EditorProject(
        team_one="One",
        team_two="Two",
        team_one_round_one_score=-4,
        team_two_round_one_score=-2,
        team_one_round_two_score=6,
        team_two_round_two_score=1,
    )
    assert (project.team_one_total, project.team_two_total) == (2, -1)
    assert project.winner == "One"
