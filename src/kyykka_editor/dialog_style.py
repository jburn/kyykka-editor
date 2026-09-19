"""Shared spacing and hierarchy for editor settings dialogs."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QVBoxLayout

from .i18n import tr


def dialog_layout(dialog: QDialog) -> QVBoxLayout:
    dialog.setObjectName("editorDialog")
    dialog.setStyleSheet(
        "QDialog#editorDialog QPushButton { min-height: 24px; padding: 4px 10px; }"
        "QDialog#editorDialog QLineEdit, QDialog#editorDialog QComboBox, "
        "QDialog#editorDialog QSpinBox { min-height: 24px; }"
        "QDialog#editorDialog QPushButton:focus, QDialog#editorDialog QLineEdit:focus, "
        "QDialog#editorDialog QComboBox:focus, QDialog#editorDialog QSpinBox:focus { "
        "border: 1px solid palette(highlight); border-radius: 3px; }"
        'QPushButton[primary="true"] { background: palette(highlight); '
        "color: palette(highlighted-text); border: 1px solid palette(highlight); "
        "border-radius: 4px; font-weight: 600; }"
        'QPushButton[primary="true"]:hover, QPushButton[primary="true"]:focus { '
        "border-color: palette(highlighted-text); }"
        'QPushButton[primary="true"]:disabled { background: palette(button); '
        "color: palette(placeholder-text); border-color: palette(mid); }"
    )
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(12)
    return layout


def heading(text: str) -> QLabel:
    label = QLabel(tr(text))
    font = label.font()
    font.setWeight(QFont.Weight.DemiBold)
    font.setPointSizeF(font.pointSizeF() + 1)
    label.setFont(font)
    return label


def form_layout(parent=None) -> QFormLayout:
    form = QFormLayout(parent)
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(8)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return form
