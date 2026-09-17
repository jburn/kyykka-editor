import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from kyykka_editor.app import MainWindow
from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.render import overlapping_highlights


def test_overlap_uses_export_extensions_and_excludes_late_throws():
    project = EditorProject(
        impacts=[Impact(10000), Impact(15000), Impact(40000)], game_end_ms=30000
    )
    assert overlapping_highlights(project, 50000) == [(10000, 15000, 2000)]
    project.impacts[1].pre_roll_ms = 2000
    assert overlapping_highlights(project, 50000) == []
    project.impacts[1].pre_roll_ms = 3000
    assert overlapping_highlights(project, 50000) == [(10000, 15000, 1000)]
    assert overlapping_highlights(project, 0) == []


def test_nested_and_duplicate_intervals_are_detected():
    project = EditorProject(
        impacts=[
            Impact(10000, pre_roll_ms=0, post_roll_ms=20000),
            Impact(15000, pre_roll_ms=0, post_roll_ms=1000),
            Impact(20000, pre_roll_ms=0, post_roll_ms=1000),
        ]
    )
    assert overlapping_highlights(project, 50000) == [(10000, 15000, 1000), (10000, 20000, 4000)]
    project.impacts = [Impact(10000), Impact(10000)]
    assert overlapping_highlights(project, 50000) == [(10000, 10000, 7000)]


@pytest.mark.parametrize("proceed", [False, True])
def test_overlap_warning_allows_cancel_or_proceed(qapp, monkeypatch, proceed):
    window = MainWindow()
    window.project = EditorProject(
        title="Match",
        team_one="A",
        team_two="B",
        impacts=[Impact(10000), Impact(15000)],
        round_one_end_ms=20000,
        game_end_ms=30000,
    )
    monkeypatch.setattr(window.player, "duration", lambda: 40000)
    messages, files = [], []

    def confirm(parent, title, message, *args):
        messages.append(message)
        return QMessageBox.StandardButton.Yes if proceed else QMessageBox.StandardButton.No

    def choose(*args, **kwargs):
        files.append(True)
        return "", ""

    monkeypatch.setattr(QMessageBox, "question", confirm)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose)
    window.export_video()
    assert len(messages) == 1
    assert "00:00:10.000" in messages[0]
    assert "00:00:15.000" in messages[0]
    assert bool(files) == proceed
    window.close()
