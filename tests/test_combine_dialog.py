from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from kyykka_editor.app import MainWindow, RenderDialog
from kyykka_editor.combine import VideoInfo
from kyykka_editor.combine_dialog import CombineVideosDialog
from kyykka_editor.i18n import tr
from kyykka_editor.render import RenderCancelled, RenderError


def finish_worker(qapp, dialog):
    for _ in range(300):
        qapp.processEvents()
        if dialog.worker is None:
            return
        QTest.qWait(10)
    raise AssertionError("Worker did not finish")


def test_file_order_add_remove_and_boundaries(qapp, tmp_path, monkeypatch):
    paths = [tmp_path / "game2.mp4", tmp_path / "game1.mp4", tmp_path / "game3.mp4"]
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames", lambda *args: ([str(p) for p in paths], "")
    )
    dialog = CombineVideosDialog()
    assert not dialog.combine_button.isEnabled()
    dialog.add_button.click()
    assert dialog.paths() == paths
    assert not dialog.down_button.isEnabled()
    dialog.videos.setCurrentRow(1)
    dialog.up_button.click()
    assert dialog.paths() == [paths[1], paths[0], paths[2]]
    assert not dialog.up_button.isEnabled()
    dialog.down_button.click()
    assert dialog.paths() == paths
    dialog.remove_button.click()
    assert dialog.paths() == [paths[0], paths[2]]
    assert dialog.combine_button.isEnabled()
    dialog.remove_button.click()
    assert not dialog.combine_button.isEnabled()
    dialog.reject()


def test_menu_tool_does_not_modify_current_project(qapp, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("kyykka_editor.app.QSettings", lambda *args: settings)
    window = MainWindow()
    window.project.title = "Unrelated match"
    original = deepcopy(window.project)
    calls = []
    monkeypatch.setattr(CombineVideosDialog, "exec", lambda self: calls.append(self))
    action = next(a for a in window.file_menu.actions() if a.text() == tr("Combine videos…"))
    action.trigger()
    assert len(calls) == 1
    assert window.project == original
    assert window.project_path is None
    window.close()


def test_declining_conversion_does_not_open_output_picker(qapp, monkeypatch):
    dialog = CombineVideosDialog()
    video = VideoInfo(Path("example.mp4"), 1, [], 1920, 1080, Fraction(30))
    prompts = []
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: prompts.append(args) or QMessageBox.StandardButton.No
    )
    dialog._inspected([video, video])
    assert prompts
    assert "1920" in prompts[0][2]
    assert dialog.worker is None
    dialog.reject()


def test_combine_worker_reuses_progress_and_waits_for_cancel(qapp):
    dialog = CombineVideosDialog()
    completed = []

    def job(cancel, progress):
        progress(25)
        cancel.wait(3)
        raise RenderCancelled()

    dialog._start(job, "Combining videos…", completed.append)
    assert isinstance(dialog.progress_dialog, RenderDialog)
    assert not dialog.add_button.isEnabled()
    dialog.progress_dialog.reject()
    assert dialog.worker is not None
    assert not dialog.progress_dialog.cancel_button.isEnabled()
    finish_worker(qapp, dialog)
    assert not completed
    assert dialog.progress_dialog is None
    assert dialog.add_button.isEnabled()
    dialog.reject()


def test_worker_reports_errors_and_can_be_reused(qapp, monkeypatch):
    dialog = CombineVideosDialog()
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args))

    def fail(cancel, progress):
        raise RenderError("Bad video")

    completed = []
    dialog._start(fail, "Combining videos…", completed.append)
    finish_worker(qapp, dialog)
    assert errors[0][2] == "Bad video"
    assert not completed
    dialog._start(lambda cancel, progress: "result.mp4", "Combining videos…", completed.append)
    finish_worker(qapp, dialog)
    assert completed == ["result.mp4"]
    dialog.reject()


def test_conversion_confirmation_passes_order_and_output_to_worker(qapp, tmp_path, monkeypatch):
    dialog = CombineVideosDialog()
    videos = [
        VideoInfo(tmp_path / name, 1, [], 160, 90, Fraction(15))
        for name in ("game2.mp4", "game1.mp4")
    ]
    output = tmp_path / "series.mp4"
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QFileDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QFileDialog, "selectedFiles", lambda self: [str(output)])
    calls = []
    monkeypatch.setattr(
        "kyykka_editor.combine_dialog.combine_videos",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args))
    dialog._inspected(videos)
    finish_worker(qapp, dialog)
    assert calls[0][0] == (videos, output)
    assert calls[0][1]["convert"] is True
    assert str(output) in messages[0][2]
    dialog.reject()
