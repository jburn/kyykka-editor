import json
from dataclasses import asdict

import pytest
from PySide6.QtGui import QColor, QImage

from kyykka_editor.card_settings import STYLE_KEYS, CardSettingsDialog
from kyykka_editor.model import CardStyle, EditorProject
from kyykka_editor.render import RenderError, create_score_card, create_title_card
from kyykka_editor.storage import project_data, read_project, write_project


@pytest.mark.parametrize("key", STYLE_KEYS)
def test_cards_use_their_own_background(qapp, tmp_path, key):
    project = EditorProject()
    setattr(project, key, CardStyle(background_color="#112233"))
    path = tmp_path / "card.png"
    if key == "title_style":
        create_title_card(project, path, (640, 360))
    else:
        create_score_card(project, path, (640, 360), key == "final_style")
    assert QImage(str(path)).pixelColor(0, 0).name() == "#112233"


def test_background_image_and_missing_image(qapp, tmp_path):
    background = tmp_path / "background.png"
    image = QImage(30, 50, QImage.Format.Format_RGB32)
    image.fill(QColor("#123456"))
    assert image.save(str(background))
    project = EditorProject(title_style=CardStyle(background_image=str(background)))
    output = tmp_path / "card.png"
    create_title_card(project, output, (640, 360))
    assert QImage(str(output)).pixelColor(0, 0).name() == "#123456"
    project.title_style.background_image = str(tmp_path / "missing.png")
    with pytest.raises(RenderError):
        create_title_card(project, output, (640, 360))


def test_styles_saved_and_old_projects_keep_original_style(tmp_path):
    project = EditorProject(title_style=CardStyle(font_family="Verdana", text_color="#aabbcc"))
    path = tmp_path / "project.kyykka"
    write_project(path, project)
    assert project_data(read_project(path)) == project_data(project)
    old_data = asdict(project)
    for key in STYLE_KEYS:
        del old_data[key]
    path.write_text(json.dumps({"version": 1, "project": old_data}))
    restored = read_project(path)
    assert all(getattr(restored, key) == CardStyle() for key in STYLE_KEYS)


def test_background_controls_follow_selected_mode(qapp, monkeypatch):
    monkeypatch.setattr(
        "kyykka_editor.card_settings.load_card_defaults",
        lambda: {key: CardStyle() for key in STYLE_KEYS},
    )
    dialog = CardSettingsDialog(EditorProject())
    for key in STYLE_KEYS:
        mode = dialog.background_modes[key]
        _, color, image = dialog.background_fields[key]
        for value in ("color", "image", "video", "freeze"):
            mode.setCurrentIndex(mode.findData(value))
            assert color.isHidden() == (value != "color")
            assert image.isHidden() == (value != "image")
            assert dialog.styles[key].background_mode == value
    dialog.reject()


def test_named_presets_persist_load_and_cancel_deletion(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QInputDialog

    settings = QSettings(str(tmp_path / "presets.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("kyykka_editor.card_settings.QSettings", lambda *args: settings)
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Tournament", True))
    dialog = CardSettingsDialog(EditorProject())
    dialog.styles["title_style"].background_color = "#123456"
    dialog.background_modes["round_style"].setCurrentIndex(
        dialog.background_modes["round_style"].findData("freeze")
    )
    dialog._save_preset()
    dialog.styles["title_style"].background_color = "#654321"
    dialog._load_preset()
    assert dialog.styles["title_style"].background_color == "#123456"
    assert dialog.background_fields["title_style"][1].text() == "#123456"
    assert dialog.styles["round_style"].background_mode == "freeze"
    dialog.accept()
    reopened = CardSettingsDialog(EditorProject())
    assert "Tournament" in reopened.presets
    reopened._delete_preset()
    assert not reopened.presets
    reopened.reject()
    restored = CardSettingsDialog(EditorProject())
    assert "Tournament" in restored.presets
    restored._delete_preset()
    restored.accept()
    final = CardSettingsDialog(EditorProject())
    assert not final.presets
    final.reject()


def test_settings_cancel_keeps_project_unchanged(qapp, monkeypatch):
    monkeypatch.setattr(
        "kyykka_editor.card_settings.load_card_defaults",
        lambda: {key: CardStyle() for key in STYLE_KEYS},
    )
    project = EditorProject()
    dialog = CardSettingsDialog(project)
    dialog.styles["title_style"].background_color = "#000000"
    dialog._preview("title_style")
    assert not dialog.previews["title_style"].pixmap().isNull()
    assert not dialog.apply_current.isChecked()
    dialog.reject()
    assert project.title_style == CardStyle()
