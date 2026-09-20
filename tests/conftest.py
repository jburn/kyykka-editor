import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture(autouse=True)
def isolated_app_state(tmp_path, monkeypatch, qapp):
    from kyykka_editor import app, card_settings, hotkeys, i18n

    settings = QSettings(str(tmp_path / "app-settings.ini"), QSettings.Format.IniFormat)
    for module in (app, card_settings, hotkeys, i18n):
        monkeypatch.setattr(module, "QSettings", lambda *args: settings)

    def location(kind):
        directory = tmp_path / kind.name
        directory.mkdir(exist_ok=True)
        return str(directory)

    monkeypatch.setattr(app.QStandardPaths, "writableLocation", location)
    i18n.set_language("en")
    yield settings
    i18n.set_language("en")
