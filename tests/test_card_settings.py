import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QFont, QImage
from PySide6.QtWidgets import QColorDialog, QFileDialog, QInputDialog, QPushButton

from kyykka_editor.card_settings import STYLE_KEYS, CardSettingsDialog
from kyykka_editor.i18n import tr
from kyykka_editor.model import CardStyle, EditorProject
from kyykka_editor.render import RenderError, create_score_card, create_title_card
from kyykka_editor.storage import project_data, read_project, write_project


@pytest.fixture(autouse=True)
def card_settings_store(tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "presets.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("kyykka_editor.card_settings.QSettings", lambda *args: settings)
    return settings


@pytest.fixture
def preset_styles(qapp, tmp_path, card_settings_store):
    background = tmp_path / "background.png"
    image = QImage(30, 50, QImage.Format.Format_RGB32)
    image.fill(QColor("#123456"))
    assert image.save(str(background))
    styles = {
        key: CardStyle(
            font_family=qapp.font().family(),
            text_color=color,
            background_color=color,
            background_mode=mode,
            background_image=str(background),
        )
        for key, color, mode in zip(
            STYLE_KEYS, ("#123456", "#abcdef", "#654321"), ("color", "image", "freeze"), strict=True
        )
    }
    card_settings_store.setValue(
        "card_presets", json.dumps({"Tournament": {k: asdict(v) for k, v in styles.items()}})
    )
    return styles


def test_selecting_preset_loads_all_styles_and_controls(qapp, preset_styles):
    project = EditorProject()
    original = deepcopy(project)
    dialog = CardSettingsDialog(project)
    assert dialog.preset_combo.currentData() is None
    assert not dialog.delete_preset_button.isEnabled()
    dialog.preset_combo.setCurrentIndex(dialog.preset_combo.findData("Tournament"))
    assert dialog.styles == preset_styles
    assert dialog.preset_combo.currentData() == "Tournament"
    assert dialog.delete_preset_button.isEnabled()
    for key, style in preset_styles.items():
        assert dialog.font_fields[key].currentFont().family() == style.font_family
        assert dialog.text_color_fields[key].text() == style.text_color
        _, color, image = dialog.background_fields[key]
        assert color.text() == style.background_color
        assert image.text() == Path(style.background_image).name
        assert dialog.background_modes[key].currentData() == style.background_mode
        assert color.isHidden() == (style.background_mode != "color")
        assert image.isHidden() == (style.background_mode != "image")
    assert project == original
    assert not dialog.apply_current.isChecked()
    dialog.reject()


@pytest.mark.parametrize("key", STYLE_KEYS)
@pytest.mark.parametrize("edit", ["font", "text_color", "background_color", "image", "mode"])
def test_style_edits_select_custom_and_reselection_restores_preset(
    qapp, preset_styles, monkeypatch, tmp_path, key, edit
):
    dialog = CardSettingsDialog(EditorProject())
    dialog.preset_combo.setCurrentIndex(dialog.preset_combo.findData("Tournament"))
    if edit == "font":
        font = dialog.font_fields[key]
        # Offscreen Qt may have no installed fonts; exercise the connected signal.
        font.currentFontChanged.emit(QFont("Preset test font"))
    elif edit in ("text_color", "background_color"):
        monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#fedcba"))
        button = (
            dialog.text_color_fields[key]
            if edit == "text_color"
            else dialog.background_fields[key][1]
        )
        button.click()
    elif edit == "image":
        filename = tmp_path / "replacement.png"
        assert QImage(preset_styles[key].background_image).save(str(filename))
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(filename), ""))
        dialog.background_fields[key][2].click()
    else:
        mode = dialog.background_modes[key]
        mode.setCurrentIndex(mode.findData("video"))
    assert dialog.styles != preset_styles
    assert dialog.preset_combo.currentData() is None
    assert dialog.preset_combo.currentText() == tr("Custom (unsaved)")
    assert not dialog.delete_preset_button.isEnabled()
    assert dialog.presets["Tournament"] == preset_styles
    dialog.preset_combo.setCurrentIndex(dialog.preset_combo.findData("Tournament"))
    assert dialog.styles == preset_styles
    assert dialog.preset_combo.currentData() == "Tournament"
    assert dialog.delete_preset_button.isEnabled()
    dialog.reject()


@pytest.mark.parametrize("matching_defaults", [False, True])
def test_legacy_presets_remain_selected_after_normalization(
    qapp, preset_styles, card_settings_store, matching_defaults
):
    legacy = {key: asdict(style) for key, style in preset_styles.items()}
    legacy["title_style"].update(background_mode="static", background_image="")
    legacy["round_style"]["background_mode"] = "static"
    expected = deepcopy(preset_styles)
    expected["title_style"].background_image = ""
    card_settings_store.setValue("card_presets", json.dumps({"Legacy": legacy}))
    if matching_defaults:
        card_settings_store.setValue("card_styles", json.dumps(legacy))
    dialog = CardSettingsDialog(EditorProject())
    if not matching_defaults:
        dialog.preset_combo.setCurrentIndex(dialog.preset_combo.findData("Legacy"))
    assert dialog.styles == expected
    assert dialog.preset_combo.currentData() == "Legacy"
    assert dialog.delete_preset_button.isEnabled()
    dialog.reject()


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


def test_named_presets_persist_load_and_cancel_deletion(qapp, monkeypatch, card_settings_store):
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Tournament", True))
    dialog = CardSettingsDialog(EditorProject())
    dialog.styles["title_style"].background_color = "#123456"
    dialog.background_modes["round_style"].setCurrentIndex(
        dialog.background_modes["round_style"].findData("freeze")
    )
    next(
        button for button in dialog.findChildren(QPushButton) if button.text() == tr("Save preset…")
    ).click()
    assert dialog.preset_combo.currentData() == "Tournament"
    assert dialog.delete_preset_button.isEnabled()
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#654321"))
    dialog.background_fields["title_style"][1].click()
    dialog.preset_combo.setCurrentIndex(dialog.preset_combo.findData("Tournament"))
    assert dialog.styles["title_style"].background_color == "#123456"
    assert dialog.background_fields["title_style"][1].text() == "#123456"
    assert dialog.styles["round_style"].background_mode == "freeze"
    dialog.accept()
    persisted = card_settings_store.value("card_presets")
    reopened = CardSettingsDialog(EditorProject())
    assert "Tournament" in reopened.presets
    assert reopened.preset_combo.currentData() == "Tournament"
    styles = deepcopy(reopened.styles)
    reopened.delete_preset_button.click()
    assert not reopened.presets
    assert reopened.styles == styles
    assert reopened.preset_combo.currentData() is None
    assert not reopened.delete_preset_button.isEnabled()
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Temporary", True))
    reopened._save_preset()
    reopened.reject()
    assert card_settings_store.value("card_presets") == persisted
    restored = CardSettingsDialog(EditorProject())
    assert set(restored.presets) == {"Tournament"}
    restored.delete_preset_button.click()
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
