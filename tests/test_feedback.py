from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from kyykka_editor.app import MainWindow, ProjectDialog
from kyykka_editor.i18n import tr
from kyykka_editor.model import EditorProject, Impact


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("kyykka_editor.app.QSettings", lambda *args: settings)
    monkeypatch.setattr("kyykka_editor.hotkeys.QSettings", lambda *args: settings)
    window = MainWindow()
    yield window
    window.render_thread = None
    window.close()


def ready(window, monkeypatch):
    window.project.video_path = str(Path("test.mp4").resolve())
    monkeypatch.setattr(
        window.player, "source", lambda: QUrl.fromLocalFile(window.project.video_path)
    )
    monkeypatch.setattr(window.player, "duration", lambda: 10000)
    monkeypatch.setattr(window.player, "error", lambda: QMediaPlayer.Error.NoError)
    monkeypatch.setattr(window.player, "mediaStatus", lambda: QMediaPlayer.MediaStatus.LoadedMedia)
    monkeypatch.setattr(window.player, "isSeekable", lambda: True)
    window.slider.setRange(0, 10000)
    window._refresh_impacts()


def test_empty_guidance_tracks_custom_and_unassigned_shortcuts(window):
    assert not window.empty_highlights.isHidden()
    bindings = {
        key: action.shortcut().toString() for key, action in window.configurable_actions.items()
    }
    bindings["M"] = "F8"
    window._apply_hotkeys(bindings)
    assert "F8" in window.empty_highlights.text()
    bindings["M"] = ""
    window._apply_hotkeys(bindings)
    assert tr("Use Mark impact to mark a throw.") in window.empty_highlights.text()
    window.project.impacts = [Impact(1000)]
    window._refresh_impacts()
    assert window.empty_highlights.isHidden()
    window.project.impacts.clear()
    window._refresh_impacts()
    assert not window.empty_highlights.isHidden()


def test_action_guidance_covers_missing_loading_failed_and_ready_video(window, monkeypatch):
    assert tr("Choose a video in Match details.") in window.action_guidance.text()
    ready(window, monkeypatch)
    assert (
        tr("Mark a throw within the video and check its before/after timing.")
        in window.export_button.toolTip()
    )
    window.project.impacts = [Impact(5000)]
    window._refresh_impacts()
    window.impact_table.selectRow(0)
    assert window.preview_button.isEnabled()
    assert window.export_button.isEnabled()
    assert window.action_guidance.isHidden()
    monkeypatch.setattr(window.player, "mediaStatus", lambda: QMediaPlayer.MediaStatus.LoadingMedia)
    window._update_action_states()
    assert tr("Wait for the video to finish loading.") == window.action_guidance.text()
    monkeypatch.setattr(window.player, "mediaStatus", lambda: QMediaPlayer.MediaStatus.InvalidMedia)
    window._update_action_states()
    assert not window.preview_button.isEnabled()
    assert (
        tr("The video could not be loaded. Choose another file in Match details.")
        == window.action_guidance.text()
    )


def test_selection_marks_matching_timeline_events_and_clears(window, monkeypatch, qapp):
    ready(window, monkeypatch)
    window.project.impacts = [Impact(1000), Impact(5000)]
    window.project.round_one_end_ms = 7000
    window._refresh_impacts()
    window.show()
    qapp.processEvents()
    before = window.slider.grab().toImage()
    window.impact_table.selectRow(1)
    assert window.slider.selected_markers == {("Impact", 5000)}
    after = window.slider.grab().toImage()
    assert before != after
    window.impact_table.selectRow(2)
    assert window.slider.selected_markers == {("Round 1 end", 7000)}
    assert not window.preview_button.isEnabled()
    window.impact_table.clearSelection()
    assert not window.slider.selected_markers


def test_keyboard_tab_leaves_table_for_preview(window, monkeypatch, qapp):
    ready(window, monkeypatch)
    window.project.impacts = [Impact(5000)]
    window._refresh_impacts()
    window.impact_table.selectRow(0)
    window.show()
    window.activateWindow()
    window.impact_table.setFocus()
    qapp.processEvents()
    QTest.keyClick(window.impact_table, Qt.Key.Key_Tab)
    assert window.preview_button.hasFocus()
    QTest.keyClick(window.preview_button, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert window.impact_table.hasFocus()


def test_export_success_and_cancellation_use_nonblocking_feedback(window, monkeypatch):
    popups = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: popups.append(args))
    window.render_outcome = ("success", "result.mp4")
    window._export_finished()
    assert "result.mp4" in window.toast.text()
    assert not window.toast.isHidden()
    assert not window.statusBar().currentMessage()
    assert not popups
    window.render_outcome = ("cancelled", "")
    window._export_finished()
    assert window.toast.text() == tr("Export cancelled")


@pytest.mark.parametrize("solo", [False, True])
def test_match_details_tab_order_follows_visible_fields(qapp, solo):
    dialog = ProjectDialog(EditorProject(solo=solo))
    dialog.show()
    dialog.activateWindow()
    dialog.team_one_edit.setFocus()
    qapp.processEvents()
    QTest.keyClick(dialog.team_one_edit, Qt.Key.Key_Tab)
    if solo:
        assert dialog.scores[0].hasFocus()
    else:
        assert dialog.players_one.hasFocus()
    dialog.reject()


def test_marking_uses_toast_without_status_text(window, monkeypatch):
    ready(window, monkeypatch)
    window.mark_impact()
    assert not window.toast.isHidden()
    assert window.toast.text()
    assert not window.statusBar().currentMessage()
    assert len(window.project.impacts) == 1


def test_toast_restarts_and_dismisses_without_taking_focus(window, qapp):
    window.show()
    window.activateWindow()
    window.impact_table.setFocus()
    qapp.processEvents()
    focused = qapp.focusWidget()
    window.toast.notify("First", 1)
    QTest.qWait(80)
    window.toast.notify("Second", 1000)
    assert window.toast.text() == "Second"
    assert window.toast.opacity.opacity() == 1.0
    assert qapp.focusWidget() is focused
    assert window.toast.geometry().right() < window.width()
    window.toast.notify("Last", 1)
    QTest.qWait(450)
    assert window.toast.isHidden()
