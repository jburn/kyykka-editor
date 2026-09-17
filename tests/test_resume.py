from pathlib import Path

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtMultimedia import QMediaPlayer

from kyykka_editor.app import MainWindow
from kyykka_editor.storage import project_data


def test_resume_is_local_and_waits_for_ready_video(qapp, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "state.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("kyykka_editor.app.QSettings", lambda *args: settings)
    window = MainWindow()
    window.project_path = tmp_path / "match.kyykka"
    window.project.video_path = str(tmp_path / "video.mp4")
    window.thrower_combo.addItem("Alice")
    window.thrower_combo.setCurrentIndex(window.thrower_combo.findText("Alice"))
    window.persistence_started = True
    monkeypatch.setattr(
        window.player, "source", lambda: QUrl.fromLocalFile(window.project.video_path)
    )
    monkeypatch.setattr(window.player, "position", lambda: 12000)
    before = project_data(window.project)
    window._remember_position()
    assert window._read_position() == (12000, "Alice")
    assert project_data(window.project) == before
    window.pending_resume = window._read_position()
    window._restore_position()
    assert window.pending_resume is not None
    positions, pauses = [], []
    monkeypatch.setattr(window.player, "duration", lambda: 10000)
    monkeypatch.setattr(window.player, "isSeekable", lambda: True)
    monkeypatch.setattr(window.player, "mediaStatus", lambda: QMediaPlayer.MediaStatus.LoadedMedia)
    monkeypatch.setattr(window.player, "setPosition", positions.append)
    monkeypatch.setattr(window.player, "pause", lambda: pauses.append(True))
    window._restore_position()
    assert positions == [10000]
    assert pauses == [True]
    assert window.pending_resume is None
    window.project.video_path = str(Path("other.mp4").resolve())
    assert window._read_position() is None
    window.persistence_started = False
    window.close()
