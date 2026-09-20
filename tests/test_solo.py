import json

from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFileDialog, QMessageBox

from kyykka_editor.app import MainWindow, ProjectDialog
from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.render import create_score_card, title_card_text
from kyykka_editor.storage import project_data, read_project, write_project


def test_solo_dialog_preserves_hidden_match_data(qapp):
    project = EditorProject(team_one="Player", team_two="Opponent", team_two_players=["Other"])
    dialog = ProjectDialog(project)
    dialog.recording_type.setCurrentIndex(1)
    assert dialog.team_two_edit.isHidden()
    assert dialog.players_one.isHidden()
    assert dialog.scores[1].isHidden()
    dialog.apply_to(project)
    assert project.solo
    assert project.team_two == "Opponent"
    assert project.throwers == ["Player"]
    dialog.recording_type.setCurrentIndex(0)
    assert not dialog.team_two_edit.isHidden()
    dialog.close()


def test_dialog_resizes_only_when_switching_modes(qapp):
    dialog = ProjectDialog(EditorProject())
    dialog.show()
    qapp.processEvents()
    width, match_height = dialog.width(), dialog.height()
    dialog.recording_type.setCurrentIndex(1)
    qapp.processEvents()
    solo_height = dialog.height()
    assert solo_height < match_height
    assert dialog.width() == width
    dialog.team_one_edit.setText("Alice")
    qapp.processEvents()
    assert dialog.height() == solo_height
    dialog.recording_type.setCurrentIndex(0)
    qapp.processEvents()
    assert dialog.height() == match_height
    assert dialog.width() == width
    dialog.close()


def test_solo_cards_use_only_player_result(qapp, tmp_path, monkeypatch):
    import kyykka_editor.render as renderer

    project = EditorProject(
        solo=True,
        team_one="Alice",
        team_two="Hidden",
        team_one_round_one_score=10,
        team_one_round_two_score=14,
        team_two_round_one_score=100,
    )
    assert title_card_text(project) == ("Alice", "")
    assert project.winner is None
    drawn = []
    boxes = []

    class Recorder(QPainter):
        def drawRoundedRect(self, *args):
            boxes.append(args[0])
            return super().drawRoundedRect(*args)

        def drawText(self, *args):
            drawn.append(args[-1])
            return super().drawText(*args)

    monkeypatch.setattr(renderer, "QPainter", Recorder)
    for final, score in ((False, 10), (True, 24)):
        drawn.clear()
        boxes.clear()
        create_score_card(project, tmp_path / "card.png", (640, 360), final)
        assert drawn[-2:] == ["Alice", str(score)]
        assert len(boxes) == 1
        assert all("Hidden" not in text and "vs." not in text for text in drawn)


def test_solo_persistence_and_old_match_migration(tmp_path):
    path = tmp_path / "project.kyykka"
    project = EditorProject(solo=True, team_one="Alice")
    write_project(path, project)
    assert read_project(path).solo
    old = project_data(project)
    old["version"] = 2
    del old["project"]["solo"]
    path.write_text(json.dumps(old))
    assert not read_project(path).solo


def test_solo_does_not_warn_about_second_team(qapp, monkeypatch):
    window = MainWindow()
    window.project = EditorProject(
        solo=True,
        title="Practice",
        team_one="Alice",
        impacts=[Impact(1000)],
        round_one_end_ms=2000,
        game_end_ms=3000,
    )
    prompts = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: prompts.append(args))
    monkeypatch.setattr(QFileDialog, "exec", lambda *args: QFileDialog.DialogCode.Rejected)
    window.export_video()
    assert not prompts
    window.close()
