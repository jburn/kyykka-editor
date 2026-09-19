from copy import deepcopy

import pytest
from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QBoxLayout

from kyykka_editor.app import MainWindow
from kyykka_editor.i18n import set_language, tr


@pytest.fixture
def workspace_settings(tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "workspace.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("kyykka_editor.app.QSettings", lambda *args: settings)
    monkeypatch.setattr("kyykka_editor.card_settings.QSettings", lambda *args: settings)
    return settings


def test_workspace_restores_splitter_and_geometry_without_changing_project(
    qapp, workspace_settings, tmp_path
):
    window = MainWindow()
    window.recovery_path = tmp_path / "recovery.kyykka"
    window.persistence_started = True
    window.resize(900, 650)
    window.show()
    qapp.processEvents()
    window.workspace_splitter.setSizes([320, 540])
    original = deepcopy(window.project)
    assert window.close()
    assert window.project == original
    assert isinstance(workspace_settings.value("workspace/geometry"), QByteArray)
    restored = MainWindow()
    restored.show()
    qapp.processEvents()
    assert restored.project == original
    assert restored.height() == window.height()
    sizes = restored.workspace_splitter.sizes()
    assert sizes[1] > sizes[0]
    assert not restored.workspace_splitter.childrenCollapsible()
    restored.close()


def test_cancelled_close_does_not_save_workspace(qapp, workspace_settings, monkeypatch):
    window = MainWindow()
    window.persistence_started = True
    monkeypatch.setattr(window, "_confirm_replace", lambda: False)
    assert not window.close()
    assert not workspace_settings.contains("workspace/geometry")
    assert not workspace_settings.contains("workspace/splitter")
    window.persistence_started = False
    monkeypatch.setattr(window, "_confirm_replace", lambda: True)
    window.close()


def test_invalid_workspace_settings_are_ignored(qapp, workspace_settings):
    workspace_settings.setValue("workspace/geometry", "invalid")
    workspace_settings.setValue("workspace/splitter", QByteArray(b"invalid"))
    window = MainWindow()
    window.show()
    qapp.processEvents()
    assert all(size > 0 for size in window.workspace_splitter.sizes())
    window.close()


@pytest.mark.parametrize("language", ["en", "fi"])
def test_narrow_workspace_wraps_controls_and_contains_long_names(
    qapp, workspace_settings, language
):
    set_language(language)
    window = MainWindow()
    try:
        window.project.team_one_players = ["Long player name " * 20]
        window._load_form()
        window.thrower_combo.setCurrentIndex(1)
        window.video_status.setText("Playing: " + "long filename " * 40 + ".mp4")
        window.resize(1000, 740)
        window.show()
        qapp.processEvents()
        window.workspace_splitter.setSizes([300, 650])
        qapp.processEvents()
        assert window.playback_controls.row.direction() == QBoxLayout.Direction.TopToBottom
        for group in window.playback_controls.groups:
            assert window.playback_controls.rect().contains(group.geometry())
            for child in group.findChildren(type(window.mark_button)):
                assert group.rect().contains(child.geometry())
        assert window.video_status.width() <= window.video_panel.width()
        assert window.width() == 1000
        assert window.thrower_combo.width() < 800
        assert window.thrower_combo.toolTip() == window.project.team_one_players[0]
        window.resize(1500, 740)
        window.workspace_splitter.setSizes([1100, 350])
        qapp.processEvents()
        assert window.playback_controls.row.direction() == QBoxLayout.Direction.LeftToRight
    finally:
        window.close()
        set_language("en")


def test_transport_icons_have_translated_labels_and_updated_shortcuts(
    qapp, workspace_settings, monkeypatch
):
    window = MainWindow()
    try:
        bindings = {
            key: action.shortcut().toString() for key, action in window.configurable_actions.items()
        }
        bindings["Space"] = "F6"
        window._apply_hotkeys(bindings)
        assert "F6" in window.play_button.toolTip()
        assert window.play_button.accessibleName() == tr("Play")
        assert not window.play_button.icon().isNull()
        assert window.play_button.text() == ""
        monkeypatch.setattr(
            window.player, "playbackState", lambda: QMediaPlayer.PlaybackState.PlayingState
        )
        window.player.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)
        assert window.play_button.accessibleName() == tr("Pause")
        assert "F6" in window.play_button.toolTip()
        set_language("fi")
        window._retranslate_ui()
        assert window.play_button.accessibleName() == tr("Pause")
        assert "F6" in window.play_button.toolTip()
        assert window.play_button.focusPolicy() != Qt.FocusPolicy.NoFocus
    finally:
        window.close()
        set_language("en")
