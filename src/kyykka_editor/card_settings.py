"""Application defaults and preview controls for export cards."""

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .i18n import tr
from .model import CardStyle, EditorProject
from .render import RenderError, create_score_card, create_title_card

STYLE_KEYS = ("title_style", "round_style", "final_style")


def load_card_defaults() -> dict[str, CardStyle]:
    try:
        values = json.loads(QSettings("KyykkaEditor", "KyykkaEditor").value("card_styles", "{}"))
        result = {}
        for key in STYLE_KEYS:
            style = CardStyle(**values.get(key, {}))
            if style.background_mode not in ("static", "color", "image", "video", "freeze"):
                raise ValueError("Invalid background mode")
            if not all(isinstance(value, str) for value in asdict(style).values()):
                raise ValueError("Invalid style")
            if (
                not QColor(style.background_color).isValid()
                or not QColor(style.text_color).isValid()
            ):
                raise ValueError("Invalid color")
            if style.background_mode == "static":
                style.background_mode = "image" if style.background_image else "color"
            result[key] = style
        return result
    except (ValueError, TypeError, AttributeError):
        return {key: CardStyle() for key in STYLE_KEYS}


class CardSettingsDialog(QDialog):
    def __init__(self, project: EditorProject, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Screen settings"))
        self.styles = load_card_defaults()
        self.presets = {}
        try:
            saved = json.loads(
                QSettings("KyykkaEditor", "KyykkaEditor").value("card_presets", "{}")
            )
            for name, values in saved.items():
                try:
                    styles = {key: CardStyle(**values[key]) for key in STYLE_KEYS}
                    if not name.strip() or any(
                        not all(isinstance(value, str) for value in asdict(style).values())
                        or style.background_mode
                        not in ("static", "color", "image", "video", "freeze")
                        or not QColor(style.background_color).isValid()
                        or not QColor(style.text_color).isValid()
                        for style in styles.values()
                    ):
                        continue
                    for style in styles.values():
                        if style.background_mode == "static":
                            style.background_mode = "image" if style.background_image else "color"
                    self.presets[name] = styles
                except (TypeError, KeyError):
                    continue
        except (TypeError, ValueError, AttributeError):
            pass
        self.project = deepcopy(project)
        self.project.title = self.project.title or tr("Match title")
        self.project.team_one = self.project.team_one or tr("Team 1")
        self.project.team_two = self.project.team_two or tr("Team 2")
        layout = QVBoxLayout(self)
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel(tr("Style preset")))
        self.preset_combo = QComboBox()
        preset_row.addWidget(self.preset_combo, 1)
        save_preset = QPushButton(tr("Save preset…"))
        save_preset.clicked.connect(self._save_preset)
        preset_row.addWidget(save_preset)
        self.delete_preset_button = QPushButton(tr("Delete preset"))
        self.delete_preset_button.clicked.connect(self._delete_preset)
        preset_row.addWidget(self.delete_preset_button)
        layout.addLayout(preset_row)
        preset_hint = QLabel(
            tr("Presets include all three screens. Save this dialog to keep preset changes.")
        )
        preset_hint.setWordWrap(True)
        layout.addWidget(preset_hint)
        self._refresh_presets()
        self.preset_combo.currentIndexChanged.connect(self._load_preset)
        layout.addWidget(
            QLabel(tr("Defaults for new projects. Images fill the screen and are cropped to fit."))
        )
        tabs = QTabWidget()
        layout.addWidget(tabs)
        self.previews = {}
        self.preview_notes = {}
        self.background_modes = {}
        self.background_fields = {}
        self.font_fields = {}
        self.text_color_fields = {}
        for key, title in zip(
            STYLE_KEYS, ("Title screen", "Round end screen", "Match end screen"), strict=True
        ):
            page = QWidget()
            form = QFormLayout(page)
            mode = QComboBox()
            for label, value in (
                ("Color", "color"),
                ("Image", "image"),
                ("Dimmed + blurred video", "video"),
                ("Dimmed freeze-frame", "freeze"),
            ):
                mode.addItem(tr(label), value)
            if self.styles[key].background_mode == "static":
                self.styles[key].background_mode = (
                    "image" if self.styles[key].background_image else "color"
                )
            mode.setCurrentIndex(mode.findData(self.styles[key].background_mode))
            self.background_modes[key] = mode
            form.addRow(tr("Background"), mode)
            font = QFontComboBox()
            self.font_fields[key] = font
            font.setCurrentFont(QFont(self.styles[key].font_family))
            font.currentFontChanged.connect(lambda value, key=key: self._font_changed(key, value))
            form.addRow(tr("Font"), font)
            for field, label in (
                ("text_color", "Text color"),
                ("background_color", "Background color"),
            ):
                button = QPushButton(getattr(self.styles[key], field))
                button.clicked.connect(
                    lambda checked=False, key=key, field=field, button=button: self._color_changed(
                        key, field, button
                    )
                )
                if field == "background_color":
                    form.insertRow(1, tr(label), button)
                    color_button = button
                else:
                    self.text_color_fields[key] = button
                    form.addRow(tr(label), button)
            image = QPushButton(Path(self.styles[key].background_image).name or tr("Choose image…"))
            image.clicked.connect(
                lambda checked=False, key=key, button=image: self._image_changed(key, button)
            )
            form.insertRow(2, tr("Background image"), image)
            self.background_fields[key] = (form, color_button, image)
            preview = QLabel()
            preview.setFixedSize(560, 315)
            preview.setWordWrap(True)
            self.previews[key] = preview
            form.addRow(preview)
            note = QLabel()
            note.setWordWrap(True)
            note.setMaximumWidth(560)
            note.setStyleSheet("color: palette(placeholder-text);")
            self.preview_notes[key] = note
            form.addRow(note)
            tabs.addTab(page, tr(title))
            mode.currentIndexChanged.connect(lambda index, key=key: self._mode_changed(key))
            self._mode_changed(key)
        self.apply_current = QCheckBox(tr("Also apply to the current project"))
        layout.addWidget(self.apply_current)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        matching = next(
            (name for name, styles in self.presets.items() if styles == self.styles), ""
        )
        self._refresh_presets(matching)

    def _refresh_presets(self, selected: str = "") -> None:
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem(tr("Custom (unsaved)"), None)
        for name in sorted(self.presets, key=str.casefold):
            self.preset_combo.addItem(name, name)
        if selected:
            self.preset_combo.setCurrentIndex(self.preset_combo.findData(selected))
        self.preset_combo.blockSignals(False)
        self.delete_preset_button.setEnabled(self.preset_combo.currentData() in self.presets)

    def _save_preset(self) -> None:
        name, accepted = QInputDialog.getText(self, tr("Save preset…"), tr("Preset name"))
        name = name.strip()
        if not accepted or not name:
            return
        existing = next((item for item in self.presets if item.casefold() == name.casefold()), None)
        if existing is not None:
            if (
                QMessageBox.question(
                    self,
                    tr("Replace preset"),
                    tr("Replace preset {name}?", name=existing),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            name = existing
        self.presets[name] = deepcopy(self.styles)
        self._refresh_presets(name)

    def _delete_preset(self) -> None:
        name = self.preset_combo.currentData()
        if name in self.presets:
            del self.presets[name]
            self._refresh_presets()

    def _load_preset(self) -> None:
        name = self.preset_combo.currentData()
        self.delete_preset_button.setEnabled(name in self.presets)
        if name not in self.presets:
            return
        self.styles = deepcopy(self.presets[name])
        for key, style in self.styles.items():
            if style.background_mode == "static":
                style.background_mode = "image" if style.background_image else "color"
            font = self.font_fields[key]
            font.blockSignals(True)
            font.setCurrentFont(QFont(style.font_family))
            font.blockSignals(False)
            self.text_color_fields[key].setText(style.text_color)
            _, color, image = self.background_fields[key]
            color.setText(style.background_color)
            image.setText(Path(style.background_image).name or tr("Choose image…"))
            mode = self.background_modes[key]
            mode.blockSignals(True)
            mode.setCurrentIndex(mode.findData(style.background_mode))
            mode.blockSignals(False)
            self._mode_changed(key)

    def _font_changed(self, key, font) -> None:
        self.styles[key].font_family = font.family()
        self._preview(key)

    def _mode_changed(self, key) -> None:
        self.styles[key].background_mode = self.background_modes[key].currentData()
        form, color_button, image = self.background_fields[key]
        form.setRowVisible(color_button, self.styles[key].background_mode == "color")
        form.setRowVisible(image, self.styles[key].background_mode == "image")
        self._preview(key)

    def _color_changed(self, key, field, button) -> None:
        color = QColorDialog.getColor(QColor(getattr(self.styles[key], field)), self)
        if color.isValid():
            setattr(self.styles[key], field, color.name())
            button.setText(color.name())
            self._preview(key)

    def _image_changed(self, key, button) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Choose image…"), "", tr("Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        )
        if filename:
            self.styles[key].background_image = str(Path(filename).resolve())
            self.background_modes[key].setCurrentIndex(self.background_modes[key].findData("image"))
            button.setText(Path(filename).name)
            self._preview(key)

    def _preview(self, key) -> None:
        name = self.preset_combo.currentData()
        if name in self.presets and self.styles != self.presets[name]:
            self._refresh_presets()
        setattr(self.project, key, deepcopy(self.styles[key]))
        # The settings preview shows typography; source-video backgrounds are composed on export.
        if self.styles[key].background_mode in ("video", "freeze"):
            preview_style = getattr(self.project, key)
            preview_style.background_mode = "static"
            preview_style.background_image = ""
            preview_style.background_color = "#292929"
            self.previews[key].setToolTip(
                tr(
                    "Video backgrounds appear during export. This preview shows text on a dim background."
                )
            )
        else:
            self.previews[key].setToolTip("")
        self.preview_notes[key].setText(self.previews[key].toolTip())
        self.background_fields[key][0].setRowVisible(
            self.preview_notes[key], bool(self.previews[key].toolTip())
        )
        with TemporaryDirectory(prefix="kyykka-preview-") as directory:
            path = Path(directory) / "preview.png"
            try:
                if key == "title_style":
                    create_title_card(self.project, path, (1120, 630))
                else:
                    create_score_card(self.project, path, (1120, 630), key == "final_style")
                self.previews[key].setPixmap(QPixmap.fromImage(QImage(str(path))).scaled(560, 315))
            except RenderError as error:
                self.previews[key].setText(str(error))

    def accept(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        for style in self.styles.values():
            if style.background_mode == "image" and QImage(style.background_image).isNull():
                QMessageBox.warning(
                    self,
                    tr("Screen settings"),
                    tr("Could not load card background: {path}", path=style.background_image),
                )
                return
        settings = QSettings("KyykkaEditor", "KyykkaEditor")
        settings.setValue(
            "card_styles", json.dumps({key: asdict(style) for key, style in self.styles.items()})
        )
        settings.setValue(
            "card_presets",
            json.dumps(
                {
                    name: {key: asdict(style) for key, style in styles.items()}
                    for name, styles in self.presets.items()
                }
            ),
        )
        super().accept()
