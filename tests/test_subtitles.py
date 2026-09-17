import json

import pytest
from PySide6.QtGui import QPainter

from kyykka_editor import render
from kyykka_editor.app import ProjectDialog
from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.storage import project_data, read_project, write_project


@pytest.mark.parametrize("solo", [False, True])
def test_subtitles_render_on_correct_cards(qapp, tmp_path, monkeypatch, solo):
    project = EditorProject(
        solo=solo, title_subtitle="Series 1–0", final_subtitle="Series 2–0", impacts=[Impact(10000)]
    )
    drawn = []

    class Recorder(QPainter):
        def drawText(self, *args):
            drawn.append(args[-1])
            return super().drawText(*args)

    monkeypatch.setattr(render, "QPainter", Recorder)
    assert render.has_title_card(project)
    assert render.estimate_export(project, 30000) == (1, 16000)
    path = tmp_path / "card.png"
    render.create_title_card(project, path, (1280, 720))
    assert "Series 1–0" in drawn
    for final in (False, True):
        drawn.clear()
        render.create_score_card(project, path, (1280, 720), final)
        assert ("Series 2–0" in drawn) == final
        assert "Series 1–0" not in drawn


def test_subtitle_fields_save_and_old_projects_migrate(qapp, tmp_path):
    project = EditorProject()
    dialog = ProjectDialog(project)
    dialog.title_subtitle_edit.setText(" Series 1–0 ")
    dialog.final_subtitle_edit.setText(" Series 2–0 ")
    dialog.apply_to(project)
    assert project.title_subtitle == "Series 1–0"
    assert project.final_subtitle == "Series 2–0"
    path = tmp_path / "project.kyykka"
    write_project(path, project)
    assert project_data(read_project(path)) == project_data(project)
    old = project_data(project)
    old["version"] = 3
    del old["project"]["title_subtitle"]
    del old["project"]["final_subtitle"]
    path.write_text(json.dumps(old))
    restored = read_project(path)
    assert restored.title_subtitle == restored.final_subtitle == ""
    dialog.close()
