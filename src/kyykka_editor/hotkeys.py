"""Persistent, conflict-checked keyboard bindings."""

import json

from PySide6.QtCore import QSettings
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .i18n import tr


def conflicting_bindings(bindings: dict[str, str]) -> bool:
    sequences = [QKeySequence(value) for value in bindings.values() if value]
    return any(
        left.matches(right) != QKeySequence.SequenceMatch.NoMatch
        or right.matches(left) != QKeySequence.SequenceMatch.NoMatch
        for index, left in enumerate(sequences)
        for right in sequences[index + 1 :]
    )


def load_bindings(defaults: dict[str, str]) -> dict[str, str]:
    try:
        stored = json.loads(QSettings("KyykkaEditor", "KyykkaEditor").value("hotkeys", "{}"))
        bindings = {key: stored.get(key, value) for key, value in defaults.items()}
        if any(
            not isinstance(value, str)
            or (value and (QKeySequence(value).isEmpty() or QKeySequence(value).count() != 1))
            for value in bindings.values()
        ):
            return defaults.copy()
        return defaults.copy() if conflicting_bindings(bindings) else bindings
    except (TypeError, ValueError, AttributeError):
        return defaults.copy()


class HotkeysDialog(QDialog):
    def __init__(self, actions, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Configure hotkeys"))
        self.resize(500, 600)
        layout = QVBoxLayout(self)
        hint = QLabel(
            tr("Select a shortcut and press the new keys. Clear it to disable the shortcut.")
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        form = QFormLayout(page)
        self.editors = {}
        for key, action in actions.items():
            editor = QKeySequenceEdit(action.shortcut())
            editor.setMaximumSequenceLength(1)
            editor.setClearButtonEnabled(True)
            form.addRow(tr(action.property("translation_source")), editor)
            self.editors[key] = editor
        scroll.setWidget(page)
        layout.addWidget(scroll)
        self.validation = QLabel()
        self.validation.setStyleSheet("color: #c65b5b;")
        self.validation.setMinimumHeight(self.validation.fontMetrics().height() * 2)
        self.validation.setWordWrap(True)
        layout.addWidget(self.validation)
        reset = QPushButton(tr("Restore defaults"))
        reset.clicked.connect(self._reset)
        layout.addWidget(reset)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        for editor in self.editors.values():
            editor.keySequenceChanged.connect(self._validate)
        self._validate()

    def bindings(self) -> dict[str, str]:
        return {
            key: editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            for key, editor in self.editors.items()
        }

    def _reset(self) -> None:
        for key, editor in self.editors.items():
            editor.setKeySequence(QKeySequence(key))

    def _validate(self) -> None:
        conflict = conflicting_bindings(self.bindings())
        self.validation.setText(
            tr("Two actions use the same shortcut. Choose unique shortcuts before saving.")
            if conflict
            else ""
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(not conflict)

    def accept(self) -> None:
        if conflicting_bindings(self.bindings()):
            return
        QSettings("KyykkaEditor", "KyykkaEditor").setValue("hotkeys", json.dumps(self.bindings()))
        super().accept()
