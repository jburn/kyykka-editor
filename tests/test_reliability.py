from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QDialog, QFileDialog

from kyykka_editor import app, card_settings, hotkeys, i18n
from kyykka_editor.model import EditorProject, Impact


@pytest.mark.parametrize("playing", [False, True])
@pytest.mark.parametrize("preview", [False, True])
def test_match_details_preserves_unchanged_video(qapp, tmp_path, monkeypatch, playing, preview):
    window = app.MainWindow()
    window.project.video_path = str(tmp_path / "source.mp4")
    window.project.team_one_players = ["Alice", "Bob"]
    window._load_form(reload_video=False)
    window.thrower_combo.setCurrentText("Bob")
    window.preview_end = 8000 if preview else None
    state = (
        QMediaPlayer.PlaybackState.PlayingState
        if playing
        else QMediaPlayer.PlaybackState.PausedState
    )
    monkeypatch.setattr(window.player, "position", lambda: 4500)
    monkeypatch.setattr(window.player, "playbackState", lambda: state)
    calls = []
    for name in ("stop", "pause", "play", "setSource", "setPosition"):
        monkeypatch.setattr(window.player, name, lambda *args, name=name: calls.append(name))

    def edit(dialog):
        dialog.title_edit.setText("Updated match")
        dialog.scores[0].setValue(12)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(app.ProjectDialog, "exec", edit)
    window.edit_project_details()
    assert not calls
    assert window.project.title == "Updated match"
    assert window.project.team_one_round_one_score == 12
    assert window.thrower_combo.currentText() == "Bob"
    assert window.preview_end == (8000 if preview else None)
    window.close()


def test_match_details_loads_replacement_video(qapp, tmp_path, monkeypatch):
    window = app.MainWindow()
    window.project.video_path = str(tmp_path / "old.mp4")
    replacement = tmp_path / "new.mp4"
    loaded = []
    monkeypatch.setattr(window, "_load_video", loaded.append)

    def edit(dialog):
        dialog.video_path = str(replacement)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(app.ProjectDialog, "exec", edit)
    window.edit_project_details()
    assert loaded == [replacement]
    window.close()


@pytest.mark.parametrize("filename", ["my-export", "my-export.mp4"])
def test_export_picker_supplies_mp4_suffix(qapp, tmp_path, monkeypatch, filename):
    window = app.MainWindow()
    window.project = EditorProject(
        title="Match",
        team_one="One",
        team_two="Two",
        impacts=[Impact(5000)],
        round_one_end_ms=7000,
        game_end_ms=9000,
    )
    monkeypatch.setattr(window.player, "duration", lambda: 10000)
    monkeypatch.setattr(app.RenderThread, "start", lambda self: None)

    def choose(picker):
        picker.setDirectory(str(tmp_path))
        picker.selectFile(filename)
        assert not picker.testOption(QFileDialog.Option.DontConfirmOverwrite)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QFileDialog, "exec", choose)
    window.export_video()
    assert window.render_thread.output == tmp_path / "my-export.mp4"
    window._export_finished()
    window.close()


def test_application_persistence_uses_only_test_locations(
    qapp, tmp_path, isolated_app_state, monkeypatch
):
    for module in (app, card_settings, hotkeys, i18n):
        settings = module.QSettings("KyykkaEditor", "KyykkaEditor")
        assert Path(settings.fileName()).is_relative_to(tmp_path)
    window = app.MainWindow()
    assert window.recovery_path.is_relative_to(tmp_path)
    window.start_session()
    window.project.title = "Temporary project"
    window.project.video_path = str(tmp_path / "video.mp4")
    window.project_path = tmp_path / "project.kyykka"
    monkeypatch.setattr(
        window.player, "source", lambda: QUrl.fromLocalFile(window.project.video_path)
    )
    window._autosave()
    assert window.recovery_path.exists()
    assert window.save_project()
    window.close()
    assert isolated_app_state.contains("workspace/geometry")
    assert any(key.startswith("resume/") for key in isolated_app_state.allKeys())
