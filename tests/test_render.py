from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.render import build_intervals


def test_intervals_are_clamped_and_overlaps_are_merged() -> None:
    project = EditorProject(
        pre_roll_ms=4_000,
        post_roll_ms=3_000,
        impacts=[Impact(2_000), Impact(7_000), Impact(19_000)],
    )
    assert build_intervals(project, 20_000) == [(0.0, 10.0), (15.0, 20.0)]


def test_no_impacts_produces_no_intervals() -> None:
    assert build_intervals(EditorProject(), 10_000) == []
