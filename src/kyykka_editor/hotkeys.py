"""Persistent, conflict-checked keyboard bindings."""

import json

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .dialog_style import dialog_layout, form_layout, heading
from .i18n import tr


def conflicting_bindings(bindings: dict[str, str]) -> bool:
    return bool(binding_conflicts(bindings))


def binding_conflicts(bindings: dict[str, str]) -> dict[str, list[str]]:
    sequences = [(key, QKeySequence(value)) for key, value in bindings.items() if value]
    conflicts: dict[str, list[str]] = {}
    for index, (left_key, left) in enumerate(sequences):
        for right_key, right in sequences[index + 1 :]:
            if (
                left.matches(right) != QKeySequence.SequenceMatch.NoMatch
                or right.matches(left) != QKeySequence.SequenceMatch.NoMatch
            ):
                conflicts.setdefault(left_key, []).append(right_key)
                conflicts.setdefault(right_key, []).append(left_key)
    return conflicts


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
        self.resize(620, 660)
        layout = dialog_layout(self)
        hint = QLabel(
            tr("Select a shortcut and press the new keys. Clear it to disable the shortcut.")
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        page = QWidget()
        sections = QVBoxLayout(page)
        sections.setContentsMargins(0, 0, 12, 0)
        sections.setSpacing(12)
        self.editors = {}
        self.conflict_labels = {}
        self.action_names = {}
        self.error_color = (
            "#e58b8b" if self.palette().window().color().lightness() < 128 else "#b44747"
        )
        groups = [
            ("Playback", ("Space", "Left", "Right", "P", "Escape")),
            ("Marking", ("M", ",", ".", "Ctrl+R", "Ctrl+G", "E", "Delete", "Ctrl+Z")),
            ("Project", ("Ctrl+N", "Ctrl+O", "Ctrl+S", "Ctrl+Shift+S", "Ctrl+D")),
        ]
        grouped = {key for _, keys in groups for key in keys}
        groups.append(("Other actions", tuple(key for key in actions if key not in grouped)))
        for title, keys in groups:
            if not any(key in actions for key in keys):
                continue
            sections.addWidget(heading(title))
            form = form_layout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            for key in keys:
                if key not in actions:
                    continue
                action = actions[key]
                name = (
                    action.text()
                    if key in ("Left", "Right")
                    else tr(action.property("translation_source") or action.text())
                )
                self.action_names[key] = name
                editor = QKeySequenceEdit(action.shortcut())
                editor.setAccessibleName(name)
                editor.setMinimumWidth(180)
                editor.setMaximumSequenceLength(1)
                editor.setClearButtonEnabled(True)
                field = QVBoxLayout()
                field.setSpacing(4)
                field.addWidget(editor)
                conflict = QLabel()
                conflict.setWordWrap(True)
                conflict.setStyleSheet(f"color: {self.error_color};")
                field.addWidget(conflict)
                label = QLabel(name)
                label.setWordWrap(True)
                label.setFixedWidth(210)
                label.setBuddy(editor)
                form.addRow(label, field)
                self.editors[key] = editor
                self.conflict_labels[key] = conflict
            sections.addLayout(form)
            sections.addSpacing(8)
        sections.addStretch()
        scroll.setWidget(page)
        layout.addWidget(scroll, 1)
        self.validation = QLabel()
        self.validation.setStyleSheet(f"color: {self.error_color};")
        self.validation.setWordWrap(True)
        layout.addWidget(self.validation)
        reset = QPushButton(tr("Restore defaults"))
        reset.setAutoDefault(False)
        reset.clicked.connect(self._reset)
        reset_hint = QLabel(
            tr("Restored defaults take effect only when you save. Cancel discards changes.")
        )
        reset_hint.setWordWrap(True)
        reset_hint.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(reset_hint)
        footer = QHBoxLayout()
        footer.addWidget(reset)
        footer.addStretch()
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setProperty("primary", True)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        footer.addWidget(self.buttons)
        layout.addLayout(footer)
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
        conflicts = binding_conflicts(self.bindings())
        for key, editor in self.editors.items():
            others = conflicts.get(key, [])
            message = (
                tr(
                    "Conflicts with: {actions}",
                    actions=", ".join(self.action_names[item] for item in others),
                )
                if others
                else ""
            )
            self.conflict_labels[key].setText(message)
            self.conflict_labels[key].setVisible(bool(others))
            editor.setAccessibleDescription(message)
            editor.setStyleSheet(
                f"QKeySequenceEdit {{ border: 1px solid {self.error_color}; }}" if others else ""
            )
        self.validation.setText(
            tr("Two actions use the same shortcut. Choose unique shortcuts before saving.")
            if conflicts
            else ""
        )
        self.validation.setVisible(bool(conflicts))
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(not conflicts)

    def accept(self) -> None:
        if conflicting_bindings(self.bindings()):
            return
        QSettings("KyykkaEditor", "KyykkaEditor").setValue("hotkeys", json.dumps(self.bindings()))
        super().accept()
