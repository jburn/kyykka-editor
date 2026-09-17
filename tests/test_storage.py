import json

import pytest

from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.storage import project_data, read_project, write_project


def test_project_round_trip(tmp_path):
    project = EditorProject(
        title="Kyykkä",
        team_one_players=["Ässä"],
        impacts=[Impact(1234, "Ässä", 0, 6000)],
        round_one_end_ms=5000,
        game_end_ms=9000,
    )
    path = tmp_path / "match.kyykka"
    write_project(path, project)
    assert project_data(read_project(path)) == project_data(project)


@pytest.mark.parametrize("value", [None, [], {"version": 2}, {"version": 1, "project": {}}])
def test_invalid_project_rejected(tmp_path, value):
    path = tmp_path / "bad.kyykka"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        read_project(path)


def test_failed_write_keeps_previous_save(tmp_path, monkeypatch):
    path = tmp_path / "match.kyykka"
    write_project(path, EditorProject(title="Original"))

    def fail(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr("kyykka_editor.storage.os.replace", fail)
    with pytest.raises(OSError):
        write_project(path, EditorProject(title="Changed"))
    assert read_project(path).title == "Original"
    assert not list(tmp_path.glob("*.tmp"))


def test_autosave_recovers_unsaved_work(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from kyykka_editor.app import MainWindow

    window = MainWindow()
    window.recovery_path = tmp_path / "recovery.kyykka"
    window.persistence_started = True
    window.project.title = "Recovered match"
    window.project.impacts = [Impact(1000, "Player", 0, 5000)]
    window._autosave()
    restored = MainWindow()
    restored.recovery_path = window.recovery_path
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    restored.start_session()
    assert project_data(restored.project) == project_data(window.project)
    assert restored.project_path is None
    assert restored.recovery_path.exists()
    window.persistence_started = restored.persistence_started = False
    window.close()
    restored.close()


def test_save_and_cancel_protect_unsaved_work(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from kyykka_editor.app import MainWindow

    window = MainWindow()
    window.persistence_started = True
    window.recovery_path = tmp_path / "recovery.kyykka"
    window.project.title = "Unsaved"
    window._autosave()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    assert not window._confirm_replace()
    assert window.recovery_path.exists()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    assert not window._confirm_replace()
    path = tmp_path / "saved.kyykka"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(path), ""))
    assert window._confirm_replace()
    assert read_project(path).title == "Unsaved"
    assert not window.recovery_path.exists()
    window.close()


def test_title_tracks_save_undo_and_timing_changes(qapp, tmp_path):
    from kyykka_editor.app import MainWindow

    window = MainWindow()
    assert not window.windowTitle().startswith("*")
    window._record_undo("Mark impact")
    window.project.add_impact(1000)
    window._refresh_impacts()
    assert window.windowTitle().startswith("* ")
    window.undo_last_action()
    assert not window.windowTitle().startswith("*")
    window.project_path = tmp_path / "match.kyykka"
    window.project.pre_roll_ms = 8000
    window._refresh_export_summary()
    assert window.project.pre_roll_ms == 8000
    assert window.windowTitle().startswith("* match.kyykka")
    assert window.save_project()
    assert window.windowTitle() == "match.kyykka — Kyykkä Editor"
    assert read_project(window.project_path).pre_roll_ms == 8000
    window.recovery_path = tmp_path / "recovery.kyykka"
    window.persistence_started = True
    window.project.post_roll_ms = 9000
    window._refresh_export_summary()
    window._autosave()
    assert window.windowTitle().startswith("*")
    window.project.post_roll_ms = 3000
    window._refresh_export_summary()
    assert not window.windowTitle().startswith("*")
    window.close()


def test_open_restores_both_default_timings(qapp, tmp_path):
    from kyykka_editor.app import MainWindow

    path = tmp_path / "match.kyykka"
    write_project(path, EditorProject(pre_roll_ms=8000, post_roll_ms=9000))
    window = MainWindow()
    assert window._open_project_path(path)
    assert window.project.pre_roll_ms == 8000
    assert window.project.post_roll_ms == 9000
    window.close()
