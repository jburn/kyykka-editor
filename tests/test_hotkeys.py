import json

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox, QLineEdit

from kyykka_editor.app import MainWindow
from kyykka_editor.hotkeys import HotkeysDialog, conflicting_bindings, load_bindings


def test_conflicts_and_empty_bindings():
    assert conflicting_bindings({"a": "Ctrl+S", "b": "Ctrl+S"})
    assert not conflicting_bindings({"a": "", "b": ""})
    assert not conflicting_bindings({"a": "M", "b": "Ctrl+M"})


def test_configure_restore_and_persist(qapp, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("kyykka_editor.hotkeys.QSettings", lambda *args: settings)
    window = MainWindow()
    dialog = HotkeysDialog(window.configurable_actions)
    dialog.editors["M"].setKeySequence(QKeySequence("E"))
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    dialog.editors["M"].setKeySequence(QKeySequence("F6"))
    dialog.editors[","].setKeySequence(QKeySequence("F7"))
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    dialog.accept()
    defaults = {key: key for key in window.configurable_actions}
    loaded = load_bindings(defaults)
    assert loaded["M"] == "F6"
    window._apply_hotkeys(loaded)
    assert window.shortcut_actions["M"].shortcut().toString() == "F6"
    assert "F7" in window.thrower_shortcut_hint.text()
    dialog._reset()
    assert dialog.bindings() == {
        key: QKeySequence(value).toString(QKeySequence.SequenceFormat.PortableText)
        for key, value in defaults.items()
    }
    settings.setValue("hotkeys", json.dumps({"M": "E"}))
    assert load_bindings(defaults) == defaults
    window.close()


def test_typing_does_not_trigger_mark_shortcut(qapp):
    window = MainWindow()
    editor = QLineEdit(window)
    editor.show()
    window.show()
    editor.setFocus()
    qapp.processEvents()
    action = window.shortcut_actions["M"]
    action.setEnabled(True)
    triggered = []
    action.triggered.connect(lambda: triggered.append(True))
    QTest.keyClick(editor, Qt.Key.Key_M)
    assert editor.text() == "m"
    assert not triggered
    window.close()
