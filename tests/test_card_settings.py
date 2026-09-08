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
