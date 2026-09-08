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
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QLabel,
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
            if not all(isinstance(value, str) for value in asdict(style).values()):
                raise ValueError("Invalid style")
            if (
                not QColor(style.background_color).isValid()
                or not QColor(style.text_color).isValid()
            ):
                raise ValueError("Invalid color")
            result[key] = style
        return result
    except (ValueError, TypeError, AttributeError):
        return {key: CardStyle() for key in STYLE_KEYS}


class CardSettingsDialog(QDialog):
    def __init__(self, project: EditorProject, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Screen settings"))
        self.styles = load_card_defaults()
        self.project = deepcopy(project)
        self.project.title = self.project.title or tr("Match title")
        self.project.team_one = self.project.team_one or tr("Team 1")
        self.project.team_two = self.project.team_two or tr("Team 2")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(tr("Defaults for new projects. Images fill the screen and are cropped to fit."))
        )
        tabs = QTabWidget()
        layout.addWidget(tabs)
        self.previews = {}
        for key, title in zip(
            STYLE_KEYS, ("Title screen", "Round end screen", "Match end screen"), strict=True
        ):
            page = QWidget()
            form = QFormLayout(page)
            font = QFontComboBox()
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
                form.addRow(tr(label), button)
            image = QPushButton(Path(self.styles[key].background_image).name or tr("Choose image…"))
            image.clicked.connect(
                lambda checked=False, key=key, button=image: self._image_changed(key, button)
            )
            form.addRow(tr("Background image"), image)
            clear = QPushButton(tr("Use background color"))
            clear.clicked.connect(
                lambda checked=False, key=key, button=image: self._clear_image(key, button)
            )
            form.addRow("", clear)
            preview = QLabel()
            preview.setFixedSize(560, 315)
            preview.setWordWrap(True)
            self.previews[key] = preview
            form.addRow(preview)
            tabs.addTab(page, tr(title))
            self._preview(key)
        self.apply_current = QCheckBox(tr("Also apply to the current project"))
        layout.addWidget(self.apply_current)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _font_changed(self, key, font) -> None:
        self.styles[key].font_family = font.family()
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
            button.setText(Path(filename).name)
            self._preview(key)

    def _clear_image(self, key, button) -> None:
        self.styles[key].background_image = ""
        button.setText(tr("Choose image…"))
        self._preview(key)

    def _preview(self, key) -> None:
        setattr(self.project, key, deepcopy(self.styles[key]))
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
            if style.background_image and QImage(style.background_image).isNull():
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
        super().accept()
