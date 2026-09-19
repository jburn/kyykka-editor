import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QDialog

from kyykka_editor.app import MainWindow, ProjectDialog
from kyykka_editor.i18n import set_language, tr


@pytest.mark.parametrize("background", ["#eeeeee", "#242424"])
def test_empty_video_tracks_palette_and_source(qapp, background):
    window = MainWindow()
    preview = window.video
    palette = preview.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    window.setPalette(palette)
    window.show()
    qapp.processEvents()
    assert preview.empty_label.isVisible()
    assert preview.details_button.isVisible()
    assert not preview.video_item.isVisible()
    assert preview.viewport().grab().toImage().pixelColor(2, 2) == QColor(background)
    border_width = preview.frameWidth()
    assert border_width == 1
    # Exercise source notifications without starting a media decoder.
    window.player.sourceChanged.emit(QUrl.fromLocalFile("/selected.mp4"))
    assert preview.empty_label.isHidden()
    assert preview.details_button.isHidden()
    assert preview.video_item.isVisible()
    assert preview.viewport().grab().toImage().pixelColor(2, 2) == QColor("black")
    assert preview.frameWidth() == border_width
    window.player.sourceChanged.emit(QUrl())
    assert preview.empty_label.isVisible()
    assert preview.details_button.isVisible()
    assert not preview.video_item.isVisible()
    assert preview.viewport().grab().toImage().pixelColor(2, 2) == QColor(background)
    assert preview.frameWidth() == border_width
    window.close()


def test_empty_video_button_opens_details_and_translates(qapp, monkeypatch):
    window = MainWindow()
    calls = []

    def details(dialog):
        calls.append(dialog)
        assert dialog.video_path == ""
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ProjectDialog, "exec", details)
    try:
        for language in ("fi", "en"):
            set_language(language)
            window._retranslate_ui()
            assert tr("No video file selected") in window.video.empty_label.text()
            assert window.video.details_button.text() == tr("Match details")
        window.video.details_button.click()
        assert len(calls) == 1
        assert window.project.video_path == ""
    finally:
        set_language("en")
        window.close()
