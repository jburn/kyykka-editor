import pytest

from kyykka_editor.model import EditorProject, Impact, format_timestamp


def test_impacts_are_sorted_when_added() -> None:
    project = EditorProject()
    project.add_impact(5_000)
    project.add_impact(1_000)
    assert [impact.timestamp_ms for impact in project.impacts] == [1_000, 5_000]


def test_project_json_round_trip() -> None:
    original = EditorProject(video_path="match.mp4", impacts=[Impact(1_234)])
    assert EditorProject.from_json(original.to_json()) == original


def test_legacy_title_duration_is_ignored() -> None:
    project = EditorProject.from_json('{"title_duration_ms": 9000, "impacts": []}')
    assert project == EditorProject()


def test_negative_impact_is_rejected() -> None:
    with pytest.raises(ValueError):
        Impact(-1)


def test_timestamp_format() -> None:
    assert format_timestamp(3_723_004) == "01:02:03.004"
