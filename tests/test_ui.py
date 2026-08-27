from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from kyykka_editor import __version__
from kyykka_editor.app import PROJECT_URL, AboutDialog, MainWindow, ProjectDialog, SeekSlider
from kyykka_editor.model import EditorProject, Impact


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
    assert window.impact_table.verticalHeader().isHidden()
    assert [window.thrower_combo.itemText(i) for i in range(window.thrower_combo.count())] == [
        "",
        "Alice",
        "Bob",
        "Carol",
    ]
    assert window.thrower_combo.currentText() == ""
    assert [window.impact_table.item(row, 1).text() for row in range(4)] == [
        "Impact — Alice",
        "Round 1 end",
        "Impact — Bob",
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


def test_export_progress_state_is_restored(qapp: QApplication) -> None:
    window = MainWindow()
    window.export_button.setEnabled(False)
    window.export_button.setText("Rendering…")
    window.export_progress.show()
    window.export_status.show()
    window._export_finished()
    assert window.export_button.isEnabled()
    assert window.export_button.text() == "Export highlights…"
    assert window.export_progress.isHidden()
    assert window.export_status.isHidden()
    window.close()
