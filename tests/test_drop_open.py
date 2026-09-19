from copy import deepcopy

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from kyykka_editor.app import MainWindow, ProjectDialog
from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.storage import read_project, write_project


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("kyykka_editor.app.QSettings", lambda *args: settings)
    monkeypatch.setattr("kyykka_editor.card_settings.QSettings", lambda *args: settings)
    window = MainWindow()
    window.recovery_path = tmp_path / "recovery.kyykka"
    window.persistence_started = True
    yield window
    window.render_thread = None
    window.persistence_started = False
    window.close()


def drop(target, urls):
    mime = QMimeData()
    mime.setUrls(urls)
    enter = QDragEnterEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(target, enter)
    event = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(target, event)
    return enter.isAccepted(), event.isAccepted()


@pytest.mark.parametrize("target", ["window", "video", "table"])
def test_drop_project_loads_from_main_surfaces(window, tmp_path, target):
    project = EditorProject(title="Dropped match", impacts=[Impact(1234)])
    path = tmp_path / "Match Ä.KYYKKA"
    write_project(path, project)
    widget = {
        "window": window,
        "video": window.video.viewport(),
        "table": window.impact_table.viewport(),
    }[target]
    assert drop(widget, [QUrl.fromLocalFile(str(path))]) == (True, True)
    assert window.project == project
    assert window.project_path == path
    assert window.impact_table.rowCount() == 1


@pytest.mark.parametrize("choice", ["Cancel", "Discard", "Save", "cancel_save"])
def test_drop_project_protects_unsaved_work(window, tmp_path, monkeypatch, choice):
    window.project.title = "Unsaved"
    path = tmp_path / "incoming.kyykka"
    saved = tmp_path / "saved.kyykka"
    write_project(path, EditorProject(title="Incoming"))
    answer = (
        QMessageBox.StandardButton.Save
        if choice == "cancel_save"
        else getattr(QMessageBox.StandardButton, choice)
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *args: answer)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args: ("" if choice == "cancel_save" else str(saved), ""),
    )
    drop(window, [QUrl.fromLocalFile(str(path))])
    assert window.project.title == (
        "Unsaved" if choice in ("Cancel", "cancel_save") else "Incoming"
    )
    if choice == "Save":
        assert read_project(saved).title == "Unsaved"


@pytest.mark.parametrize("accepted", [False, True])
def test_drop_video_preselects_new_project_file(window, tmp_path, monkeypatch, accepted):
    path = tmp_path / "Match Ä.MP4"
    path.touch()
    original = deepcopy(window.project)
    loaded = []
    monkeypatch.setattr(window, "_load_video", loaded.append)

    def details(dialog):
        assert dialog.video_path == str(path.resolve())
        dialog.title_edit.setText("New match")
        return QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected

    monkeypatch.setattr(ProjectDialog, "exec", details)
    assert drop(window, [QUrl.fromLocalFile(str(path))]) == (True, True)
    if accepted:
        assert window.project.video_path == str(path.resolve())
        assert window.project.title == "New match"
        assert window.project_path is None
        assert loaded == [path.resolve()]
    else:
        assert window.project == original
        assert not loaded


def test_drop_video_cancel_preserves_existing_marks(window, tmp_path, monkeypatch):
    path = tmp_path / "new.mp4"
    path.touch()
    window.project.title = "Existing match"
    window.project.impacts = [Impact(1000)]
    original = deepcopy(window.project)
    monkeypatch.setattr(ProjectDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    drop(window, [QUrl.fromLocalFile(str(path))])
    assert window.project == original
    assert window.player.source().isEmpty()


@pytest.mark.parametrize(
    "kind", ["multiple", "remote", "directory", "unsupported", "missing", "rendering"]
)
def test_invalid_drops_are_ignored(window, tmp_path, kind):
    path = tmp_path / "match.kyykka"
    write_project(path, EditorProject(title="Incoming"))
    urls = [QUrl.fromLocalFile(str(path))]
    if kind == "multiple":
        urls *= 2
    elif kind == "remote":
        urls = [QUrl("https://example.com/match.kyykka")]
    elif kind == "directory":
        path = tmp_path / "folder.kyykka"
        path.mkdir()
        urls = [QUrl.fromLocalFile(str(path))]
    elif kind == "unsupported":
        path = tmp_path / "notes.txt"
        path.touch()
        urls = [QUrl.fromLocalFile(str(path))]
    elif kind == "missing":
        urls = [QUrl.fromLocalFile(str(tmp_path / "missing.mp4"))]
    else:
        window.render_thread = object()
    original = deepcopy(window.project)
    assert drop(window, urls) == (False, False)
    assert window.project == original


def test_corrupt_dropped_project_keeps_current_work(window, tmp_path, monkeypatch):
    path = tmp_path / "broken.kyykka"
    path.write_text("invalid json")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    original = deepcopy(window.project)
    drop(window, [QUrl.fromLocalFile(str(path))])
    assert warnings
    assert window.project == original
