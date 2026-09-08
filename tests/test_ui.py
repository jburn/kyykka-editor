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


def test_edit_throw_saves_and_resets_timing_overrides(qapp, monkeypatch):
    from kyykka_editor.app import EditMarkDialog

    window = MainWindow()
    _set_ready_video(window, monkeypatch)
    window.project.add_impact(5000, "Alice")
    window._refresh_impacts()
    window.impact_table.selectRow(0)

    def edit(dialog):
        assert dialog.before_spin.value() == 4
        assert not dialog.before_spin.isEnabled()
        dialog.override_before.setChecked(True)
        dialog.before_spin.setValue(0)
        assert not dialog.override_after.isChecked()
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(EditMarkDialog, "exec", edit)
    window.edit_selected()
    impact = window.project.impacts[0]
    assert impact.pre_roll_ms == 0
    assert impact.post_roll_ms is None
    assert "custom timing" in window.impact_table.item(0, 0).text()
    window.pre_roll.setValue(9)
    window.post_roll.setValue(2)
    window._sync_form()
    assert window.project.timing_for(impact) == (0, 2000)

    def reset(dialog):
        assert dialog.override_before.isChecked()
        assert dialog.before_spin.value() == 0
        assert dialog.after_spin.value() == 2
        dialog.override_before.setChecked(False)
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(EditMarkDialog, "exec", reset)
    window.edit_selected()
    assert window.project.timing_for(impact) == (9000, 2000)
    assert impact.pre_roll_ms is None
    assert "custom timing" not in window.impact_table.item(0, 0).text()
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


def test_slider_draws_throw_markers_and_keeps_click_seeking(qapp):
    slider = SeekSlider(Qt.Orientation.Horizontal)
    slider.resize(400, 28)
    slider.setRange(0, 10000)
    slider.set_markers([0, 5000, 10000, 5000, 15000])
    slider.show()
    qapp.processEvents()
    positions = slider._marker_positions()
    assert len(positions) == 3
    assert positions[0] < positions[1] < positions[2]
    assert abs(positions[1] - slider.width() / 2) <= 1
    pixels = slider.grab().toImage()
    for x in positions:
        assert pixels.pixelColor(x, slider.height() - 4) != pixels.pixelColor(
            x + 3, slider.height() - 4
        )
    spy = QSignalSpy(slider.seek_requested)
    QTest.mouseClick(
        slider, Qt.MouseButton.LeftButton, pos=QPoint(positions[1], slider.height() - 4)
    )
    assert spy.count() == 1
    assert abs(spy.at(0)[0] - 5000) <= 20
    slider.resize(800, 28)
    assert slider._marker_positions()[1] > positions[1]
    slider.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    reversed_positions = slider._marker_positions()
    assert reversed_positions[0] > reversed_positions[-1]
    slider.setRange(0, 0)
    assert slider._marker_positions() == []
    slider.close()


def test_slider_end_markers_have_distinct_colors_heights_and_tooltips(qapp):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QToolTip

    from kyykka_editor.i18n import set_language

    slider = SeekSlider(Qt.Orientation.Horizontal)
    slider.resize(400, 28)
    slider.setRange(0, 10000)
    slider.set_markers([2000], 5000, 8000)
    slider.show()
    qapp.processEvents()
    details = {kind: (x, timestamp) for x, kind, timestamp in slider._marker_details()}
    pixels = slider.grab().toImage()
    assert pixels.pixelColor(details["Round 1 end"][0], 18).name() == "#4488cc"
    assert pixels.pixelColor(details["Game end"][0], 13).name() == "#35a575"
    try:
        for code, label in [("en", "Round 1 end"), ("fi", "1. puolen loppu")]:
            set_language(code)
            pos = QPoint(details["Round 1 end"][0], 20)
            event = QHelpEvent(QEvent.Type.ToolTip, pos, slider.mapToGlobal(pos))
            QApplication.sendEvent(slider, event)
            assert QToolTip.text() == f"{label}: 00:00:05.000"
        slider.set_markers([], 0, 0)
        assert {kind for _, kind, _ in slider._marker_details()} == {"Round 1 end", "Game end"}
        slider.set_markers([])
        assert slider._marker_details() == []
    finally:
        QToolTip.hideText()
        set_language("en")
        slider.close()


def test_slider_markers_follow_added_edited_and_removed_throws(qapp, monkeypatch):
    window = MainWindow()
    _set_ready_video(window, monkeypatch)
    window.mark_impact()
    assert window.slider.markers == (0,)
    window.project.impacts[0].timestamp_ms = 1200
    window._refresh_impacts()
    assert window.slider.markers == (1200,)
    window.impact_table.selectRow(0)
    window.remove_selected()
    assert window.slider.markers == ()
    window.project.round_one_end_ms = 4000
    window.project.game_end_ms = 9000
    window._refresh_impacts()
    assert (window.slider.round_end, window.slider.game_end) == (4000, 9000)
    window.impact_table.selectRow(0)
    window.remove_selected()
    assert window.slider.round_end is None
    assert window.slider.game_end == 9000
    window.close()


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


def test_render_dialog_shows_progress_and_keeps_cancellation_status(qapp):
    from kyykka_editor.app import RenderDialog

    window = MainWindow()
    dialog = RenderDialog(window)
    assert dialog.elapsed_timer.isActive()
    assert dialog.progress.maximum() == 0
    dialog.update_progress(25)
    assert dialog.progress.maximum() == 100
    assert dialog.progress.value() == 25
    dialog.update_progress(10)
    assert dialog.progress.value() == 25
    assert dialog.elapsed_label.text().startswith("Elapsed:")
    dialog.reject()
    dialog.update_progress(90)
    assert dialog.progress.value() == 25
    assert dialog.status.text() == "Cancelling render…"
    dialog.accept()
    assert not dialog.elapsed_timer.isActive()
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


@pytest.mark.parametrize(
    "code, message",
    [
        ("en", "round 1 ends after the game ends"),
        ("fi", "1. puoli päättyy ottelun lopun jälkeen"),
    ],
)
def test_invalid_end_order_explains_disabled_export_and_clears_when_fixed(
    qapp, monkeypatch, code, message
):
    from kyykka_editor.i18n import set_language

    set_language(code)
    window = MainWindow()
    try:
        _set_ready_video(window, monkeypatch)
        window.project.add_impact(1000)
        window.project.round_one_end_ms = 8000
        window.project.game_end_ms = 5000
        window._refresh_impacts()
        assert not window.export_button.isEnabled()
        assert message in window.export_summary.text()
        assert not window.export_summary.toolTip()
        assert "placeholder-text" not in window.export_summary.styleSheet()
        window.project.round_one_end_ms = 4000
        window._refresh_impacts()
        assert window.export_button.isEnabled()
        assert message not in window.export_summary.text()
        assert not window.export_summary.toolTip()
        assert "placeholder-text" in window.export_summary.styleSheet()
    finally:
        window.close()
        set_language("en")


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
