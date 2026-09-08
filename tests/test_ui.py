from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from kyykka_editor import __version__
from kyykka_editor.app import PROJECT_URL, AboutDialog, MainWindow, ProjectDialog, SeekSlider
from kyykka_editor.model import EditorProject, Impact


def test_edit_dialog_validates_time_and_preserves_unlisted_thrower(qapp):
    from PySide6.QtWidgets import QDialogButtonBox

    from kyykka_editor.app import EditMarkDialog

    dialog = EditMarkDialog(1234, 5678, 1000, 10000, ["Alice"], "Former player")
    assert dialog.thrower_combo.currentText() == "Former player"
    assert dialog.validation_label.isHidden()
    save = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
    for text in ("00:00:00.999", "00:00:10.001", "00:60:00.000", "incomplete"):
        dialog.timestamp_edit.setText(text)
        assert not save.isEnabled()
        assert dialog.timestamp_ms() is None
        assert not dialog.validation_label.isHidden()
    dialog.use_position_button.click()
    assert dialog.timestamp_ms() == 5678
    assert save.isEnabled()
    assert dialog.validation_label.isHidden()
    dialog.thrower_combo.setCurrentIndex(0)
    assert dialog.thrower_combo.currentText() == ""


def test_timestamp_allows_deleting_and_retyping_in_middle(qapp):
    from PySide6.QtWidgets import QDialogButtonBox

    from kyykka_editor.app import EditMarkDialog

    dialog = EditMarkDialog(1234, 0, 0, 10000, [], None)
    editor = dialog.timestamp_edit
    save = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
    editor.setCursorPosition(8)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.text() == "00:00:0.234"
    assert not save.isEnabled()
    QTest.keyClicks(editor, "2")
    assert editor.text() == "00:00:02.234"
    assert dialog.timestamp_ms() == 2234
    assert save.isEnabled()
    assert dialog.validation_label.isHidden()
    editor.setCursorPosition(2)
    QTest.keyClick(editor, Qt.Key.Key_Delete)
    assert editor.text() == "0000:02.234"
    assert not save.isEnabled()
    QTest.keyClicks(editor, ":")
    assert dialog.timestamp_ms() == 2234
    assert save.isEnabled()


def test_timeline_context_menu_targets_clicked_entry(qapp, monkeypatch):
    from PySide6.QtWidgets import QMenu

    window = MainWindow()
    _set_ready_video(window, monkeypatch)
    window.project.impacts = [Impact(1000, "Alice"), Impact(2000, "Bob")]
    window._refresh_impacts()
    window.show()
    qapp.processEvents()
    window.impact_table.selectRow(0)
    calls = []

    def show_menu(menu, position):
        assert menu.actions() == [window.shortcut_actions["E"], window.shortcut_actions["Delete"]]
        assert all(action.isEnabled() for action in menu.actions())
        assert {index.row() for index in window.impact_table.selectedIndexes()} == {1}
        calls.append(position)
        menu.actions()[1].trigger()

    class TestMenu(QMenu):
        def exec(self, position):
            show_menu(self, position)

    monkeypatch.setattr("kyykka_editor.app.QMenu", TestMenu)
    position = window.impact_table.visualItemRect(window.impact_table.item(1, 0)).center()
    window.impact_table.customContextMenuRequested.emit(position)
    assert len(calls) == 1
    assert [impact.thrower for impact in window.project.impacts] == ["Alice"]
    window._timeline_context_menu(QPoint(-1, -1))
    assert len(calls) == 1
    window.close()


def test_edit_throw_reorders_exact_entry_and_preserves_current_thrower(qapp, monkeypatch):
    from kyykka_editor.app import EditMarkDialog

    window = MainWindow()
    _set_ready_video(window, monkeypatch)
    first, edited = Impact(1000, "Alice"), Impact(1000, "Bob")
    window.project.impacts = [first, edited, Impact(5000, "Alice")]
    window.project.team_one_players = ["Alice", "Bob"]
    window.thrower_combo.addItems(["", "Alice", "Bob"])
    window.thrower_combo.setCurrentText("Alice")
    window.mark_history = [1000]
    window._refresh_impacts()
    window.impact_table.selectRow(1)
    assert window.edit_button.isEnabled()
    assert window.shortcut_actions["E"].isEnabled()

    def edit(dialog):
        dialog.timestamp_edit.setText("00:00:07.123")
        dialog.thrower_combo.setCurrentText("Alice")
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(EditMarkDialog, "exec", edit)
    window.show()
    window.activateWindow()
    window.impact_table.setFocus()
    qapp.processEvents()
    QTest.keyClick(window.impact_table, Qt.Key.Key_E)
    assert first.timestamp_ms == 1000
    assert window.project.impacts[-1] is edited
    assert (edited.timestamp_ms, edited.thrower) == (7123, "Alice")
    assert {index.row() for index in window.impact_table.selectedIndexes()} == {2}
    assert window.thrower_combo.currentText() == "Alice"
    assert window.video.name_item.text() == "Alice"
    assert not window.mark_history
    window.close()


@pytest.mark.parametrize("accepted", [False, True])
def test_cancel_or_unchanged_edit_preserves_history(qapp, monkeypatch, accepted):
    from PySide6.QtWidgets import QDialog

    from kyykka_editor.app import EditMarkDialog

    window = MainWindow()
    _set_ready_video(window, monkeypatch)
    window.mark_impact()
    window.impact_table.selectRow(0)
    previous = list(window.mark_history)
    monkeypatch.setattr(
        EditMarkDialog,
        "exec",
        lambda _: QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected,
    )
    window.edit_selected()
    assert window.mark_history == previous
    assert window.project.impacts[0].timestamp_ms == 0
    window.close()


def test_edit_pauses_and_restores_playback(qapp, monkeypatch):
    from kyykka_editor.app import EditMarkDialog

    window = MainWindow()
    _set_ready_video(window, monkeypatch)
    window.mark_impact()
    window.impact_table.selectRow(0)
    calls = []
    monkeypatch.setattr(
        window.player, "playbackState", lambda: QMediaPlayer.PlaybackState.PlayingState
    )
    monkeypatch.setattr(window.player, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(window.player, "play", lambda: calls.append("play"))
    monkeypatch.setattr(EditMarkDialog, "exec", lambda _: 0)
    window.edit_selected()
    assert calls == ["pause", "play"]
    window.close()


@pytest.mark.parametrize(
    "kind, row, expected_min, expected_max, value",
    [
        ("round_one_end_ms", 0, 0, 8000, 4000),
        ("game_end_ms", 1, 3000, 10000, 9000),
    ],
)
def test_edit_end_markers_enforces_order(
    qapp, monkeypatch, kind, row, expected_min, expected_max, value
):
    from kyykka_editor.app import EditMarkDialog
    from kyykka_editor.model import format_timestamp

    window = MainWindow()
    _set_ready_video(window, monkeypatch)
    window.project.round_one_end_ms = 3000
    window.project.game_end_ms = 8000
    window._refresh_impacts()
    window.impact_table.selectRow(row)

    def edit(dialog):
        assert dialog.thrower_combo is None
        assert (dialog.minimum_ms, dialog.maximum_ms) == (expected_min, expected_max)
        dialog.timestamp_edit.setText(format_timestamp(value))
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(EditMarkDialog, "exec", edit)
    window.edit_selected()
    assert getattr(window.project, kind) == value
    window.close()


def test_video_overlay_tracks_selection_and_stays_inside_video(qapp: QApplication) -> None:
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtMultimedia import QVideoFrame

    window = MainWindow()
    window.project.team_one_players = ["Alice", "Bob"]
    window._load_form()
    window.show()
    frame = QImage(320, 180, QImage.Format.Format_RGB32)
    frame.fill(QColor("blue"))
    window.video.video_item.videoSink().setVideoFrame(QVideoFrame(frame))
    qapp.processEvents()
    assert not window.video.overlay.isVisible()
    window.cycle_thrower()
    assert window.video.name_item.text() == "Alice"
    assert window.video.overlay.isVisible()
    window.thrower_combo.setCurrentIndex(2)
    assert window.video.name_item.text() == "Bob"
    for width, height in [(1000, 700), (1400, 900)]:
        window.resize(width, height)
        qapp.processEvents()
        video_bounds = window.video.video_item.boundingRect()
        overlay_bounds = window.video.overlay.mapRectToParent(window.video.overlay.rect())
        assert video_bounds.contains(overlay_bounds)
        assert overlay_bounds.center().y() > video_bounds.center().y()
    window.cycle_thrower()
    assert not window.video.overlay.isVisible()
    window.close()


def test_project_dialog_applies_match_details(qapp: QApplication, tmp_path: Path) -> None:
    project = EditorProject()
    dialog = ProjectDialog(project)
    dialog.video_path = str(tmp_path / "match.mp4")
    dialog._refresh_video_label()
    dialog.title_edit.setText("  Playoffs  ")
    dialog.team_one_edit.setText(" One ")
    dialog.team_two_edit.setText("Two")
    dialog.players_one.setPlainText("Alice\n\n Bob ")
    dialog.players_two.setPlainText("Carol\n")
    for score, value in zip(dialog.scores, (-2, -1, 4, 3), strict=True):
        score.setValue(value)

    dialog.apply_to(project)
    assert project.title == "Playoffs"
    assert project.video_path.endswith("match.mp4")
    assert project.team_one_players == ["Alice", "Bob"]
    assert project.team_two_players == ["Carol"]
    assert (
        project.team_one_round_one_score,
        project.team_two_round_one_score,
        project.team_one_round_two_score,
        project.team_two_round_two_score,
    ) == (-2, -1, 4, 3)
    assert dialog.video_label.text() == "match.mp4"


def test_about_dialog_contains_version_license_and_contact(qapp: QApplication) -> None:
    dialog = AboutDialog()
    assert __version__ in dialog.version_label.text()
    assert PROJECT_URL in dialog.contact_label.text()
    assert "FFmpeg" in dialog.license_text.toPlainText()
    assert "GPL-3.0-or-later" in dialog.license_text.toPlainText()
    assert "There is no warranty" in dialog.license_text.toPlainText()
    assert dialog.license_text.isReadOnly()


def test_seek_slider_click_emits_requested_position(qapp: QApplication) -> None:
    slider = SeekSlider(Qt.Orientation.Horizontal)
    slider.resize(400, 30)
    slider.setRange(0, 10_000)
    slider.show()
    qapp.processEvents()
    spy = QSignalSpy(slider.seek_requested)
    QTest.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(300, 15))
    assert spy.count() == 1
    assert 7_000 <= spy.at(0)[0] <= 8_000


def test_main_window_timeline_is_sorted_and_player_list_is_fixed(
    qapp: QApplication,
) -> None:
    window = MainWindow()
    window.project = EditorProject(
        team_one_players=["Alice", "Bob"],
        team_two_players=["Carol"],
        impacts=[Impact(5_000, "Bob"), Impact(1_000, "Alice")],
        round_one_end_ms=3_000,
        game_end_ms=8_000,
    )
    window._load_form()
    assert not window.thrower_combo.isEditable()
    assert not window.impact_table.verticalHeader().isHidden()
    assert window.impact_table.columnCount() == 2
    assert [window.impact_table.horizontalHeaderItem(column).text() for column in range(2)] == [
        "Event",
        "Timestamp",
    ]
    assert [window.thrower_combo.itemText(i) for i in range(window.thrower_combo.count())] == [
        "",
        "Alice",
        "Bob",
        "Carol",
    ]
    assert window.thrower_combo.currentText() == ""
    assert [window.impact_table.item(row, 0).text() for row in range(4)] == [
        "Impact: Alice",
        "Round 1 end",
        "Impact: Bob",
        "Game end",
    ]
    window.close()


def test_remove_selected_removes_event_not_neighboring_impact(qapp: QApplication) -> None:
    window = MainWindow()
    window.project = EditorProject(impacts=[Impact(1_000), Impact(5_000)], round_one_end_ms=3_000)
    window._refresh_impacts()
    window.impact_table.selectRow(1)
    window.remove_selected()
    assert window.project.round_one_end_ms is None
    assert [impact.timestamp_ms for impact in window.project.impacts] == [1_000, 5_000]
    window.close()


def test_export_button_state_is_restored(qapp: QApplication, monkeypatch) -> None:
    window = MainWindow()
    _set_ready_video(window, monkeypatch)
    window.project.add_impact(1000)
    window._refresh_impacts()
    window.export_button.setEnabled(False)
    window.export_button.setText("Rendering…")
    window._export_finished()
    assert window.export_button.isEnabled()
    assert window.export_button.text() == "Export highlights…"
    window.close()


def test_render_dialog_cancel_stays_open_until_worker_finishes(qapp, monkeypatch):
    from kyykka_editor.app import RenderDialog, RenderThread

    window = MainWindow()
    _set_ready_video(window, monkeypatch)
    window.project.add_impact(1000)
    window._refresh_impacts()
    dialog = RenderDialog(window)
    worker = RenderThread(EditorProject(), Path("out.mp4"), 1000)
    window.render_dialog = dialog
    window.render_thread = worker
    dialog.cancel_requested.connect(worker.cancel)
    spy = QSignalSpy(dialog.cancel_requested)
    dialog.show()
    QTest.mouseClick(dialog.cancel_button, Qt.MouseButton.LeftButton)
    assert worker.cancel_event.is_set()
    assert dialog.isVisible()
    assert not dialog.cancel_button.isEnabled()
    dialog.reject()
    assert spy.count() == 1
    window._export_cancelled()
    window._export_finished()
    assert not dialog.isVisible()
    assert window.render_thread is None
    assert window.export_button.isEnabled()
    assert window.statusBar().currentMessage() == "Export cancelled"
    window.close()


def _set_ready_video(window, monkeypatch):
    window.project.video_path = str(Path("match.mp4").resolve())
    monkeypatch.setattr(
        window.player, "source", lambda: QUrl.fromLocalFile(window.project.video_path)
    )
    monkeypatch.setattr(window.player, "duration", lambda: 10000)
    monkeypatch.setattr(window.player, "position", lambda: 0)
    monkeypatch.setattr(window.player, "isSeekable", lambda: True)
    monkeypatch.setattr(window.player, "mediaStatus", lambda: QMediaPlayer.MediaStatus.LoadedMedia)
    window._refresh_export_summary()


def test_actions_follow_video_selection_and_history(qapp, monkeypatch):
    window = MainWindow()
    for button in (
        window.play_button,
        window.mark_button,
        window.round_end_button,
        window.game_end_button,
        window.back_button,
        window.forward_button,
        window.undo_button,
        window.remove_button,
        window.export_button,
    ):
        assert not button.isEnabled()
    assert all(not action.isEnabled() for action in window.shortcut_actions.values())
    _set_ready_video(window, monkeypatch)
    assert window.play_button.isEnabled()
    assert window.mark_button.isEnabled()
    assert window.shortcut_actions["M"].isEnabled()
    assert not window.back_button.isEnabled()
    assert window.forward_button.isEnabled()
    assert not window.export_button.isEnabled()
    window.mark_impact()
    assert window.undo_button.isEnabled()
    assert window.shortcut_actions["Ctrl+Z"].isEnabled()
    assert window.export_button.isEnabled()
    window.impact_table.selectRow(0)
    assert window.remove_button.isEnabled()
    assert window.shortcut_actions["Delete"].isEnabled()
    window.impact_table.clearSelection()
    assert not window.remove_button.isEnabled()
    window.undo_impact()
    assert not window.undo_button.isEnabled()
    assert not window.shortcut_actions["Ctrl+Z"].isEnabled()
    assert not window.export_button.isEnabled()
    monkeypatch.setattr(window.player, "position", lambda: 10000)
    window._position_changed(10000)
    assert window.back_button.isEnabled()
    assert not window.forward_button.isEnabled()
    assert not window.shortcut_actions["Right"].isEnabled()
    monkeypatch.setattr(window.player, "mediaStatus", lambda: QMediaPlayer.MediaStatus.InvalidMedia)
    window._media_status_changed(QMediaPlayer.MediaStatus.InvalidMedia)
    assert not window.mark_button.isEnabled()
    assert not window.play_button.isEnabled()
    assert not window.slider.isEnabled()
    window.close()
