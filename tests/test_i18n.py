import ast
from pathlib import Path
from string import Formatter

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox

from kyykka_editor import i18n
from kyykka_editor.app import AboutDialog, MainWindow, ProjectDialog, RenderDialog
from kyykka_editor.model import EditorProject, Impact, default_export_filename
from kyykka_editor.render import RenderError, create_score_card, render_highlights


@pytest.fixture(autouse=True)
def reset_language(qapp):
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def test_language_persistence_and_invalid_setting(tmp_path):
    settings = QSettings(str(tmp_path / "language.ini"), QSettings.Format.IniFormat)
    assert i18n.saved_language(settings) == "en"
    i18n.set_language("fi", persist=True, settings=settings)
    settings.sync()
    reopened = QSettings(str(tmp_path / "language.ini"), QSettings.Format.IniFormat)
    assert i18n.saved_language(reopened) == "fi"
    assert i18n.tr("Current thrower") == "Nykyinen heittäjä"
    settings.setValue("language", "unknown")
    assert i18n.saved_language(settings) == "en"


def test_live_language_switch_preserves_match_and_shortcuts(qapp, monkeypatch, tmp_path):
    settings = QSettings(str(tmp_path / "language.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(
        "kyykka_editor.app.set_language",
        lambda code, persist: i18n.set_language(code, persist=persist, settings=settings),
    )
    window = MainWindow()
    window.project = EditorProject(
        title="Play",
        team_one="Team 1",
        team_one_players=["Play", "Ääkkönen"],
        impacts=[Impact(1000, "Play")],
        round_one_end_ms=2000,
        game_end_ms=3000,
    )
    window.mark_history = [1000]
    window._load_form()
    window.thrower_combo.setCurrentIndex(1)
    window.impact_table.selectRow(1)
    project = window.project
    window.show()
    window.activateWindow()
    qapp.processEvents()
    next(a for a in window.language_group.actions() if a.data() == "fi").trigger()
    assert i18n.saved_language(settings) == "fi"
    assert window.project is project
    assert window.project.title == "Play"
    assert window.project.team_one == "Team 1"
    assert window.mark_history == [1000]
    assert window.thrower_combo.currentText() == "Play"
    assert window.video.name_item.text() == "Play"
    assert window.mark_button.text() == "Merkitse osuma"
    assert window.impact_table.item(0, 0).text() == "Osuma: Play"
    assert window.impact_table.item(1, 0).text() == "1. puolen loppu"
    assert window.impact_table.item(2, 0).text() == "Ottelun loppu"
    assert "1 heitto" in window.export_summary.text()
    assert window.shortcut_actions[","].shortcut().toString() == ","
    window.thrower_combo.setFocus()
    QTest.keyClick(window.thrower_combo, Qt.Key.Key_Comma)
    assert window.thrower_combo.currentText() == "Ääkkönen"
    window.remove_selected()
    assert window.project.round_one_end_ms is None
    assert window.project.impacts == [Impact(1000, "Play")]
    next(a for a in window.language_group.actions() if a.data() == "en").trigger()
    assert window.mark_button.text() == "Mark impact"
    assert window.thrower_combo.currentText() == "Ääkkönen"
    assert window.video.name_item.text() == "Ääkkönen"
    window.close()


def test_finnish_dialogs_and_standard_buttons(qapp):
    from kyykka_editor.app import EditMarkDialog

    i18n.set_language("fi")
    dialog = ProjectDialog(EditorProject(title="Play", team_one_players=["Team 1"]))
    assert dialog.windowTitle() == "Ottelun tiedot"
    assert dialog.title_edit.text() == "Play"
    assert dialog.players_one.toPlainText() == "Team 1"
    assert dialog.players_one.placeholderText() == "Yksi pelaaja riville"
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons.button(QDialogButtonBox.StandardButton.Cancel).text() in {"Peru", "Peruuta"}
    about = AboutDialog()
    assert "Versio:" in about.version_label.text()
    assert "ei ole takuuta" in about.license_text.toPlainText()
    render = RenderDialog(dialog)
    assert render.cancel_button.text() == "Peruuta"
    render.reject()
    assert render.status.text() == "Peruutetaan videon luontia…"
    edit = EditMarkDialog(1000, 2000, 0, 10000, ["Ääkkönen"], "Ääkkönen")
    assert edit.windowTitle() == "Muokkaa heittoa"
    assert edit.use_position_button.text() == "Käytä nykyistä toistokohtaa"
    assert edit.thrower_combo.currentText() == "Ääkkönen"


def test_finnish_export_cards_and_errors(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QPainter

    i18n.set_language("fi")
    labels = []
    original = QPainter.drawText

    def draw_text(painter, *args):
        labels.append(args[-1])
        return original(painter, *args)

    monkeypatch.setattr(QPainter, "drawText", draw_text)
    project = EditorProject(team_one="Play", team_two="Ääkköset", impacts=[Impact(1000)])
    create_score_card(project, tmp_path / "final.png", (640, 360), True)
    create_score_card(project, tmp_path / "round.png", (640, 360), False)
    assert {"Lopputulos", "1. puolen tulos", "Play", "Ääkköset"}.issubset(labels)
    assert default_export_filename(EditorProject()) == "kyykkakooste.mp4"
    monkeypatch.setattr("kyykka_editor.render.find_media_tool", lambda _: None)
    with pytest.raises(RenderError, match="FFmpeg-ohjelmaa ei löytynyt"):
        render_highlights(project, tmp_path / "out.mp4", 10000)


def test_translation_catalog_preserves_placeholders_and_covers_literal_calls():
    def fields(text):
        return {field for _, field, _, _ in Formatter().parse(text) if field is not None}

    for source, translated in i18n.FINNISH.items():
        assert fields(source) == fields(translated), source
        assert translated.strip(), source
    for path in Path(i18n.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                assert node.args[0].value in i18n.FINNISH, node.args[0].value
