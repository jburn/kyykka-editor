from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event

os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
# Keep Qt Multimedia developer diagnostics disabled unless a caller explicitly enables them.
os.environ.setdefault("QT_FFMPEG_DEBUG", "0")
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg.*=false")

from PySide6.QtCore import (
    QEvent,
    QPoint,
    QRectF,
    QSizeF,
    QStandardPaths,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QCloseEvent,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QHelpEvent,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QStyle,
    QStyleOptionSlider,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .i18n import LANGUAGES, language, saved_language, set_language, tr
from .model import EditorProject, default_export_filename, format_timestamp
from .render import RenderCancelled, RenderError, estimate_export, render_highlights

ICON_PATH = Path(__file__).with_name("assets") / "kyykka-editor.png"
PROJECT_URL = "https://github.com/jburn/kyykka-editor"


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("About Kyykkä Editor"))
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.setMinimumSize(540, 440)
        layout = QVBoxLayout(self)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(QIcon(str(ICON_PATH)).pixmap(96, 96))
        layout.addWidget(icon)

        build_kind = (
            tr("Packaged Windows application")
            if getattr(sys, "frozen", False)
            else tr("Development build")
        )
        self.version_label = QLabel(
            tr(
                "<h2>Kyykkä Editor</h2><p><b>Version:</b> {version}<br><b>Build:</b> {build}</p>",
                version=__version__,
                build=build_kind,
            )
        )
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.version_label)

        self.contact_label = QLabel(
            tr('<p><b>Contact and project:</b> <a href="{url}">{url}</a></p>', url=PROJECT_URL)
        )
        self.contact_label.setOpenExternalLinks(True)
        self.contact_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(self.contact_label)

        layout.addWidget(QLabel(tr("License information")))
        self.license_text = QPlainTextEdit()
        self.license_text.setReadOnly(True)
        self.license_text.setPlainText(
            tr(
                "Kyykkä Editor\n"
                "Copyright © 2026 jburn and contributors.\n"
                "Licensed under the GNU General Public License, version 3 or later "
                "(GPL-3.0-or-later). You may use, study, share, and modify the application "
                "under those terms. There is no warranty. See LICENSE in the application "
                "directory for the complete license.\n\n"
                "FFmpeg and FFprobe\n"
                "The packaged Gyan full build is GPL-enabled. The exact obligations depend on "
                "the included build. See THIRD_PARTY_NOTICES.md in the application directory.\n\n"
                "PySide6 / Qt for Python\n"
                "Available under LGPLv3, GPLv3, and commercial licensing terms."
            )
        )
        layout.addWidget(self.license_text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ProjectDialog(QDialog):
    def __init__(self, project: EditorProject, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Match details"))
        self.setMinimumWidth(560)
        form = QFormLayout(self)
        self.title_edit = QLineEdit(project.title)
        self.team_one_edit = QLineEdit(project.team_one)
        self.team_two_edit = QLineEdit(project.team_two)
        self.video_path = project.video_path
        self.video_label = QLabel()
        self.video_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._refresh_video_label()
        browse = QPushButton(tr("Browse…"))
        browse.clicked.connect(self._browse_video)
        video_row = QHBoxLayout()
        video_row.addWidget(self.video_label, 1)
        video_row.addWidget(browse)
        self.players_one = QPlainTextEdit("\n".join(project.team_one_players))
        self.players_two = QPlainTextEdit("\n".join(project.team_two_players))
        for players in (self.players_one, self.players_two):
            players.setPlaceholderText(tr("One player per line"))
            players.setFixedHeight(
                6 * players.fontMetrics().lineSpacing()
                + 2 * players.frameWidth()
                + round(2 * players.document().documentMargin())
            )
        self.scores = [QSpinBox() for _ in range(4)]
        values = (
            project.team_one_round_one_score,
            project.team_two_round_one_score,
            project.team_one_round_two_score,
            project.team_two_round_two_score,
        )
        for score, value in zip(self.scores, values, strict=True):
            score.setRange(-100, 100)
            score.setValue(value)
        form.addRow(tr("Match title"), self.title_edit)
        form.addRow(tr("Video"), video_row)
        form.addRow(tr("Team 1"), self.team_one_edit)
        form.addRow(tr("Team 1 players"), self.players_one)
        form.addRow(tr("Team 2"), self.team_two_edit)
        form.addRow(tr("Team 2 players"), self.players_two)
        score_grid = QGridLayout()
        score_grid.addWidget(QLabel(tr("Round 1")), 0, 1)
        score_grid.addWidget(QLabel(tr("Round 2")), 0, 2)
        self.score_team_one = QLabel(project.team_one or tr("Team 1"))
        self.score_team_two = QLabel(project.team_two or tr("Team 2"))
        self.team_one_edit.textChanged.connect(
            lambda name: self.score_team_one.setText(name.strip() or tr("Team 1"))
        )
        self.team_two_edit.textChanged.connect(
            lambda name: self.score_team_two.setText(name.strip() or tr("Team 2"))
        )
        score_grid.addWidget(self.score_team_one, 1, 0)
        score_grid.addWidget(self.scores[0], 1, 1)
        score_grid.addWidget(self.scores[2], 1, 2)
        score_grid.addWidget(self.score_team_two, 2, 0)
        score_grid.addWidget(self.scores[1], 2, 1)
        score_grid.addWidget(self.scores[3], 2, 2)
        form.addRow(tr("Scores"), score_grid)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _browse_video(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Open video"),
            "",
            tr("Video files (*.mp4 *.mov *.mkv *.avi *.m4v);;All files (*)"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if filename:
            self.video_path = filename
            self._refresh_video_label()

    def _refresh_video_label(self) -> None:
        if self.video_path:
            self.video_label.setText(Path(self.video_path).name)
            self.video_label.setToolTip(self.video_path)
        else:
            self.video_label.setText(tr("No video selected"))
            self.video_label.setToolTip("")

    def apply_to(self, project: EditorProject) -> None:
        project.title = self.title_edit.text().strip()
        project.video_path = self.video_path
        project.team_one = self.team_one_edit.text().strip()
        project.team_two = self.team_two_edit.text().strip()
        project.team_one_players = self._players(self.players_one)
        project.team_two_players = self._players(self.players_two)
        (
            project.team_one_round_one_score,
            project.team_two_round_one_score,
            project.team_one_round_two_score,
            project.team_two_round_two_score,
        ) = (score.value() for score in self.scores)

    @staticmethod
    def _players(editor: QPlainTextEdit) -> list[str]:
        return [line.strip() for line in editor.toPlainText().splitlines() if line.strip()]


class EditMarkDialog(QDialog):
    def __init__(
        self,
        timestamp_ms: int,
        position_ms: int,
        minimum_ms: int,
        maximum_ms: int,
        players: list[str],
        thrower: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Edit throw") if thrower is not None else tr("Edit event"))
        self.minimum_ms, self.maximum_ms = minimum_ms, maximum_ms
        form = QFormLayout(self)
        self.timestamp_edit = QLineEdit(format_timestamp(timestamp_ms))
        self.timestamp_edit.setMaxLength(
            max(len(format_timestamp(timestamp_ms)), len(format_timestamp(maximum_ms)))
        )
        form.addRow(tr("Timestamp"), self.timestamp_edit)
        self.use_position_button = QPushButton(tr("Use current playback position"))
        self.use_position_button.clicked.connect(
            lambda: self.timestamp_edit.setText(format_timestamp(position_ms))
        )
        form.addRow(self.use_position_button)
        self.thrower_combo: QComboBox | None = None
        if thrower is not None:
            self.thrower_combo = QComboBox()
            self.thrower_combo.addItems(list(dict.fromkeys(["", *players])))
            if self.thrower_combo.findText(thrower) < 0:
                self.thrower_combo.addItem(thrower)
            self.thrower_combo.setCurrentText(thrower)
            form.addRow(tr("Thrower"), self.thrower_combo)
        self.validation_label = QLabel(
            tr(
                "Enter a timestamp between {start} and {end} (hh:mm:ss.mmm).",
                start=format_timestamp(minimum_ms),
                end=format_timestamp(maximum_ms),
            )
        )
        self.validation_label.setWordWrap(True)
        error_color = "#e58b8b" if self.palette().window().color().lightness() < 128 else "#b44747"
        self.validation_label.setStyleSheet(f"color: {error_color};")
        validation_policy = self.validation_label.sizePolicy()
        validation_policy.setRetainSizeWhenHidden(True)
        self.validation_label.setSizePolicy(validation_policy)
        validation_area = QWidget()
        validation_layout = QVBoxLayout(validation_area)
        validation_layout.setContentsMargins(0, 0, 0, 0)
        validation_layout.addWidget(self.validation_label)
        form.addRow(validation_area)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        form.addRow(self.buttons)
        self.timestamp_edit.textChanged.connect(self._validate)
        self._validate()

    def timestamp_ms(self) -> int | None:
        if not re.fullmatch(
            r"[0-9]{2,}:[0-5][0-9]:[0-5][0-9]\.[0-9]{3}", self.timestamp_edit.text()
        ):
            return None
        hours, minutes, seconds = self.timestamp_edit.text().split(":")
        seconds, millis = seconds.split(".")
        value = ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis)
        return value if self.minimum_ms <= value <= self.maximum_ms else None

    def _validate(self) -> None:
        valid = self.timestamp_ms() is not None
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(valid)
        self.validation_label.setVisible(not valid)

    def accept(self) -> None:
        if self.timestamp_ms() is not None:
            super().accept()


class SeekSlider(QSlider):
    """Timeline slider that seeks when any point on its track is clicked."""

    seek_requested = Signal(int)

    def __init__(self, orientation: Qt.Orientation, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self.markers: tuple[int, ...] = ()
        self.round_end: int | None = None
        self.game_end: int | None = None
        self.setMinimumHeight(28)

    def set_markers(
        self, timestamps: list[int], round_end: int | None = None, game_end: int | None = None
    ) -> None:
        self.markers = tuple(sorted(set(timestamps)))
        self.round_end, self.game_end = round_end, game_end
        self.update()

    def _marker_positions(self, timestamps: tuple[int, ...] | None = None) -> list[int]:
        if self.maximum() <= self.minimum():
            return []
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderGroove, self
        )
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, self
        )
        span = max(1, groove.right() - handle.width() + 1 - groove.x())
        return [
            groove.x()
            + handle.width() // 2
            + QStyle.sliderPositionFromValue(
                self.minimum(), self.maximum(), timestamp, span, option.upsideDown
            )
            for timestamp in (self.markers if timestamps is None else timestamps)
            if self.minimum() <= timestamp <= self.maximum()
        ]

    def _marker_details(self) -> list[tuple[int, str, int]]:
        markers = [("Impact", timestamp) for timestamp in self.markers]
        if self.round_end is not None:
            markers.append(("Round 1 end", self.round_end))
        if self.game_end is not None:
            markers.append(("Game end", self.game_end))
        markers = [
            (kind, timestamp)
            for kind, timestamp in markers
            if self.minimum() <= timestamp <= self.maximum()
        ]
        positions = self._marker_positions(tuple(timestamp for _, timestamp in markers))
        return [(x, kind, timestamp) for x, (kind, timestamp) in zip(positions, markers)]

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ToolTip and isinstance(event, QHelpEvent):
            labels = [
                f"{tr(kind)}: {format_timestamp(timestamp)}"
                for x, kind, timestamp in self._marker_details()
                if abs(event.pos().x() - x) <= 5
            ]
            if labels:
                QToolTip.showText(event.globalPos(), "\n".join(labels), self)
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        return super().event(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        color = QColor(
            "#e4b66b" if self.palette().window().color().lightness() < 128 else "#a66a20"
        )
        styles = {
            "Impact": (color, 6),
            "Round 1 end": (QColor("#4488cc"), 11),
            "Game end": (QColor("#35a575"), 16),
        }
        for x, kind, _timestamp in self._marker_details():
            marker_color, height = styles[kind]
            if not self.isEnabled():
                marker_color.setAlpha(110)
            painter.setPen(QPen(marker_color, 2))
            painter.drawLine(x, self.height() - height, x, self.height() - 2)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        option = QStyleOptionSlider()
        self.initStyleOption(option)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderGroove,
            self,
        )
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            self,
        )
        slider_length = handle.width()
        slider_min = groove.x()
        slider_max = groove.right() - slider_length + 1
        click_position = round(event.position().x()) - slider_length // 2
        value = QStyle.sliderValueFromPosition(
            self.minimum(),
            self.maximum(),
            click_position - slider_min,
            max(1, slider_max - slider_min),
            option.upsideDown,
        )
        self.setValue(value)
        self.seek_requested.emit(value)
        event.accept()


class RenderDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Rendering highlights"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        self.status = QLabel(tr("Rendering video. This can take several minutes…"))
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        self.cancel_button = QPushButton(tr("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)

    def reject(self) -> None:
        if self.cancel_button.isEnabled():
            self.cancel_button.setEnabled(False)
            self.status.setText(tr("Cancelling render…"))
            self.cancel_requested.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.reject()
        event.ignore()


class RenderThread(QThread):
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, project: EditorProject, output: Path, duration_ms: int) -> None:
        super().__init__()
        self.project = project
        self.output = output
        self.duration_ms = duration_ms
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            render_highlights(self.project, self.output, self.duration_ms, self.cancel_event)
        except RenderCancelled:
            self.cancelled.emit()
        except (RenderError, OSError) as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(str(self.output))


class VideoPreview(QGraphicsView):
    """Compose the video and editing overlay in the same graphics scene."""

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QBrush(QColor("black")))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumSize(160, 90)
        self.video_item = QGraphicsVideoItem()
        self.scene().addItem(self.video_item)
        self.overlay = QGraphicsRectItem(self.video_item)
        self.overlay.setBrush(QBrush(QColor(0, 0, 0, 150)))
        self.overlay.setPen(QPen(Qt.PenStyle.NoPen))
        self.overlay.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.name_item = QGraphicsSimpleTextItem(self.overlay)
        self.name_item.setBrush(QBrush(QColor("white")))
        self.name_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.thrower = ""
        self.overlay.hide()
        self.video_item.nativeSizeChanged.connect(self._layout_video)

    def set_thrower(self, name: str) -> None:
        self.thrower = name
        self._layout_video()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._layout_video()

    def _layout_video(self) -> None:
        available = QSizeF(self.viewport().size())
        native = self.video_item.nativeSize()
        size = (
            native.scaled(available, Qt.AspectRatioMode.KeepAspectRatio)
            if not native.isEmpty()
            else available
        )
        self.setSceneRect(QRectF(0, 0, available.width(), available.height()))
        self.video_item.setSize(size)
        self.video_item.setPos(
            (available.width() - size.width()) / 2, (available.height() - size.height()) / 2
        )
        font = QFont("Arial")
        font.setPixelSize(max(12, round(size.height() / 24)))
        font.setBold(True)
        self.name_item.setFont(font)
        margin = max(6, round(size.width() / 40))
        padding = 8
        text = QFontMetrics(font).elidedText(
            self.thrower,
            Qt.TextElideMode.ElideRight,
            max(0, round(size.width()) - 2 * (margin + padding)),
        )
        self.name_item.setText(text)
        self.name_item.setPos(padding, padding)
        bounds = self.name_item.boundingRect()
        height = bounds.height() + 2 * padding
        self.overlay.setRect(0, 0, bounds.width() + 2 * padding, height)
        self.overlay.setPos(margin, max(0, size.height() - height - margin))
        self.overlay.setVisible(bool(self.thrower))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = EditorProject()
        self.mark_history: list[int] = []
        self.render_thread: RenderThread | None = None
        self.render_dialog: RenderDialog | None = None
        self.render_outcome: tuple[str, str] | None = None
        self.shortcut_actions: dict[str, QAction] = {}
        self.exportable_count = 0
        self.estimated_duration: int | None = None
        self.setWindowTitle("Kyykkä Editor")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1180, 780)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.video = VideoPreview()
        self.player.setVideoOutput(self.video.video_item)

        self._build_ui()
        self._build_menu()
        self._connect_player()
        self._refresh_impacts()

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QHBoxLayout(root)
        left, right = QVBoxLayout(), QVBoxLayout()

        source_row = QHBoxLayout()
        self.video_status = QLabel(tr("No video selected"))
        self.video_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        source_row.addWidget(self.video_status, 1)
        left.addLayout(source_row)
        left.addWidget(self.video, 1)
        timeline = QHBoxLayout()
        self.position_label = QLabel("00:00:00.000")
        self.slider = SeekSlider(Qt.Orientation.Horizontal)
        self.duration_label = QLabel("00:00:00.000")
        slider_option = QStyleOptionSlider()
        self.slider.initStyleOption(slider_option)
        slider_height = max(self.slider.minimumHeight(), self.slider.sizeHint().height())
        slider_option.rect.setHeight(slider_height)
        groove = self.slider.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            slider_option,
            QStyle.SubControl.SC_SliderGroove,
            self.slider,
        )
        # Some native styles keep the track at the top when marker space is added.
        offset = 2 * groove.y() + groove.height() - slider_height
        for label in (self.position_label, self.duration_label):
            label.setContentsMargins(0, max(0, offset), 0, max(0, -offset))
        timeline.addWidget(self.position_label)
        timeline.addWidget(self.slider, 1)
        timeline.addWidget(self.duration_label)
        left.addLayout(timeline)

        controls = QHBoxLayout()
        self.back_button = QPushButton("−3 s")
        self.play_button = QPushButton(tr("Play"))
        self.forward_button = QPushButton("+5 s")
        self.mark_button = QPushButton(tr("Mark impact"))
        self.undo_button = QPushButton(tr("Undo"))
        self.mark_button.setDefault(True)
        for button in (
            self.back_button,
            self.play_button,
            self.forward_button,
            self.mark_button,
            self.undo_button,
        ):
            controls.addWidget(button)
        left.addLayout(controls)

        self.details_button = QPushButton(tr("Match details…"))
        self.details_button.clicked.connect(self.edit_project_details)
        right.addWidget(self.details_button)

        timing_row = QHBoxLayout()
        self.pre_roll, self.post_roll = QSpinBox(), QSpinBox()
        for spin in (self.pre_roll, self.post_roll):
            spin.setRange(0, 30)
            spin.setSuffix(" s")
        self.pre_roll.setValue(4)
        self.post_roll.setValue(3)
        self.before_label = before_label = QLabel(tr("Before impact"))
        before_label.setBuddy(self.pre_roll)
        self.after_label = after_label = QLabel(tr("After impact"))
        after_label.setBuddy(self.post_roll)
        timing_row.addWidget(before_label)
        timing_row.addWidget(self.pre_roll)
        timing_row.addSpacing(12)
        timing_row.addWidget(after_label)
        timing_row.addWidget(self.post_roll)
        right.addLayout(timing_row)

        thrower_form = QFormLayout()
        self.thrower_combo = QComboBox()
        self.thrower_combo.currentTextChanged.connect(self.video.set_thrower)
        thrower_field = QVBoxLayout()
        thrower_field.setSpacing(2)
        thrower_field.addWidget(self.thrower_combo)
        self.thrower_shortcut_hint = QLabel(tr(",=next  .=previous"))
        hint_font = self.thrower_shortcut_hint.font()
        hint_font.setPointSizeF(max(8.0, hint_font.pointSizeF() - 1.0))
        self.thrower_shortcut_hint.setFont(hint_font)
        self.thrower_shortcut_hint.setStyleSheet("color: palette(placeholder-text);")
        thrower_field.addWidget(self.thrower_shortcut_hint)
        self.thrower_label = QLabel(tr("Current thrower"))
        thrower_form.addRow(self.thrower_label, thrower_field)
        right.addLayout(thrower_form)

        event_row = QHBoxLayout()
        self.round_end_button = QPushButton(tr("Mark round 1 end"))
        self.game_end_button = QPushButton(tr("Mark game end"))
        event_row.addWidget(self.round_end_button)
        event_row.addWidget(self.game_end_button)
        right.addLayout(event_row)
        self.timeline_label = QLabel(tr("Timeline events"))
        right.addWidget(self.timeline_label)
        self.impact_table = QTableWidget(0, 2)
        self.impact_table.setAlternatingRowColors(True)
        self.impact_table.setShowGrid(False)
        self.impact_table.setHorizontalHeaderLabels([tr("Event"), tr("Timestamp")])
        self.impact_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.impact_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.impact_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        right.addWidget(self.impact_table, 1)
        self.remove_button = QPushButton(tr("Remove selected"))
        self.edit_button = QPushButton(tr("Edit selected…"))
        self.export_button = QPushButton(tr("Export highlights…"))
        edit_row = QHBoxLayout()
        edit_row.addWidget(self.edit_button)
        edit_row.addWidget(self.remove_button)
        right.addLayout(edit_row)
        self.export_summary = QLabel()
        self.export_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.export_summary.setWordWrap(True)
        self.export_summary.setStyleSheet("color: palette(placeholder-text);")
        right.addWidget(self.export_summary)
        right.addWidget(self.export_button)

        outer.addLayout(left, 3)
        outer.addLayout(right, 1)
        self.setCentralWidget(root)

        self.play_button.clicked.connect(self.toggle_playback)
        self.back_button.clicked.connect(lambda: self.seek_relative(-3_000))
        self.forward_button.clicked.connect(lambda: self.seek_relative(5_000))
        self.mark_button.clicked.connect(self.mark_impact)
        self.undo_button.clicked.connect(self.undo_impact)
        self.remove_button.clicked.connect(self.remove_selected)
        self.edit_button.clicked.connect(self.edit_selected)
        self.export_button.clicked.connect(self.export_video)
        self.pre_roll.valueChanged.connect(self._refresh_export_summary)
        self.post_roll.valueChanged.connect(self._refresh_export_summary)
        self.round_end_button.clicked.connect(self.mark_round_end)
        self.game_end_button.clicked.connect(self.mark_game_end)
        self.slider.sliderMoved.connect(self.player.setPosition)
        self.slider.seek_requested.connect(self.player.setPosition)
        self.impact_table.cellDoubleClicked.connect(self._seek_to_row)
        self.impact_table.itemSelectionChanged.connect(self._update_action_states)
        self.impact_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.impact_table.customContextMenuRequested.connect(self._timeline_context_menu)

        for text, keys, callback in (
            ("Play or pause", "Space", self.toggle_playback),
            ("Mark impact", "M", self.mark_impact),
            ("Next thrower", ",", lambda: self.cycle_thrower()),
            ("Previous thrower", ".", lambda: self.cycle_thrower(-1)),
            ("Undo latest mark", "Ctrl+Z", self.undo_impact),
            ("Seek backward 3 seconds", "Left", lambda: self.seek_relative(-3_000)),
            ("Seek forward 5 seconds", "Right", lambda: self.seek_relative(5_000)),
            ("Remove selected event", "Delete", self.remove_selected),
            ("Edit selected event", "E", self.edit_selected),
            ("Mark round 1 end", "Ctrl+R", self.mark_round_end),
            ("Mark game end", "Ctrl+G", self.mark_game_end),
        ):
            self._add_shortcut(text, keys, callback)

    def _build_menu(self) -> None:
        self.file_menu = menu = self.menuBar().addMenu(tr("&File"))
        for text, shortcut, callback in (
            ("New match…", "Ctrl+N", self.new_project),
            ("Match details…", "Ctrl+D", self.edit_project_details),
        ):
            action = QAction(tr(text), self)
            action.setProperty("translation_source", text)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)

        self.help_menu = help_menu = self.menuBar().addMenu(tr("&Help"))
        self.hotkeys_menu = hotkeys_menu = help_menu.addMenu(tr("&Hotkeys"))
        hotkeys_menu.addActions(self.actions())
        hotkeys_menu.addSeparator()
        hotkeys_menu.addActions(menu.actions())
        self.language_menu = help_menu.addMenu(tr("&Language"))
        self.language_group = QActionGroup(self)
        for code, name in LANGUAGES.items():
            action = self.language_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(code == language())
            action.setData(code)
            self.language_group.addAction(action)
            action.triggered.connect(lambda _checked, code=code: self._change_language(code))
        help_menu.addSeparator()
        self.about_action = about_action = QAction(tr("&About Kyykkä Editor…"), self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_about(self) -> None:
        AboutDialog(self).exec()

    def _change_language(self, code: str) -> None:
        if self.render_thread is not None:
            return
        set_language(code, persist=True)
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        for widget, source in (
            (self.mark_button, "Mark impact"),
            (self.undo_button, "Undo"),
            (self.details_button, "Match details…"),
            (self.before_label, "Before impact"),
            (self.after_label, "After impact"),
            (self.thrower_label, "Current thrower"),
            (self.thrower_shortcut_hint, ",=next  .=previous"),
            (self.round_end_button, "Mark round 1 end"),
            (self.game_end_button, "Mark game end"),
            (self.timeline_label, "Timeline events"),
            (self.remove_button, "Remove selected"),
            (self.edit_button, "Edit selected…"),
            (self.export_button, "Export highlights…"),
            (self.about_action, "&About Kyykkä Editor…"),
        ):
            widget.setText(tr(source))
        self.play_button.setText(
            tr(
                "Pause"
                if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                else "Play"
            )
        )
        for menu, source in (
            (self.file_menu, "&File"),
            (self.help_menu, "&Help"),
            (self.hotkeys_menu, "&Hotkeys"),
            (self.language_menu, "&Language"),
        ):
            menu.setTitle(tr(source))
        for action in self.findChildren(QAction):
            source = action.property("translation_source")
            if source:
                action.setText(tr(source))
        for action in self.language_group.actions():
            action.setChecked(action.data() == language())
        self.impact_table.setHorizontalHeaderLabels([tr("Event"), tr("Timestamp")])
        selected = [(item.row(), item.column()) for item in self.impact_table.selectedItems()]
        self._refresh_impacts()
        for row, column in selected:
            self.impact_table.item(row, column).setSelected(True)
        if not self.project.video_path:
            self.video_status.setText(tr("No video selected"))
        elif self.player.mediaStatus() == QMediaPlayer.MediaStatus.LoadingMedia:
            self.video_status.setText(
                tr("Loading {name}…", name=Path(self.project.video_path).name)
            )
        elif self.player.error() != QMediaPlayer.Error.NoError:
            self.video_status.setText(tr("Could not load video"))
        else:
            source = (
                "Playing: {name}"
                if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                else "Loaded: {name}"
            )
            self.video_status.setText(tr(source, name=Path(self.project.video_path).name))
        self.statusBar().clearMessage()

    def new_project(self) -> None:
        candidate = EditorProject()
        dialog = ProjectDialog(candidate, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dialog.apply_to(candidate)
        self.player.stop()
        self.project = candidate
        self.mark_history.clear()
        self._load_form()

    def edit_project_details(self) -> None:
        dialog = ProjectDialog(self.project, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        current_thrower = self.thrower_combo.currentText()
        dialog.apply_to(self.project)
        self._load_form()
        thrower_index = self.thrower_combo.findText(current_thrower)
        self.thrower_combo.setCurrentIndex(max(0, thrower_index))

    def _add_shortcut(self, text: str, keys: str, callback: Callable[[], None]) -> None:
        action = QAction(tr(text), self)
        action.setProperty("translation_source", text)
        action.setShortcut(QKeySequence(keys))
        action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        action.triggered.connect(callback)
        self.addAction(action)
        self.shortcut_actions[keys] = action

    def _connect_player(self) -> None:
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.mediaStatusChanged.connect(self._media_status_changed)
        self.player.playbackStateChanged.connect(
            lambda state: self.play_button.setText(
                tr("Pause") if state == QMediaPlayer.PlaybackState.PlayingState else tr("Play")
            )
        )
        self.player.errorOccurred.connect(self._playback_error)
        self.player.seekableChanged.connect(self._update_action_states)

    def _load_video(self, path: Path) -> None:
        path = path.resolve()
        if not path.is_file():
            QMessageBox.warning(
                self, tr("Video not found"), tr("The video file does not exist:\n{path}", path=path)
            )
            return
        self.player.stop()
        self.project.video_path = str(path)
        self.video_status.setText(tr("Loading {name}…", name=path.name))
        self.video_status.setToolTip(str(path))
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()
        self.setWindowTitle(f"Kyykkä Editor — {path.name}")

    def _media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            name = Path(self.project.video_path).name
            self.video_status.setText(tr("Loaded: {name}", name=name))
        elif status == QMediaPlayer.MediaStatus.BufferedMedia:
            self.video_status.setText(
                tr("Playing: {name}", name=Path(self.project.video_path).name)
            )
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.video_status.setText(tr("Loaded: {name}", name=Path(self.project.video_path).name))
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.video_status.setText(tr("Could not load video"))
        self._update_action_states()

    def _playback_error(self, _error: QMediaPlayer.Error, message: str) -> None:
        self._update_action_states()
        self.video_status.setText(tr("Could not load video"))
        detail = message or tr("Qt could not decode this video file.")
        QMessageBox.warning(
            self,
            tr("Playback error"),
            tr("{detail}\n\nFile: {path}", detail=detail, path=self.project.video_path),
        )

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def seek_relative(self, milliseconds: int) -> None:
        target = max(0, min(self.player.duration(), self.player.position() + milliseconds))
        self.player.setPosition(target)

    def mark_impact(self) -> None:
        if not self.project.video_path:
            QMessageBox.information(
                self, tr("No video"), tr("Open a video before marking impacts.")
            )
            return
        self.project.add_impact(self.player.position(), self.thrower_combo.currentText())
        self.mark_history.append(self.player.position())
        self._refresh_impacts()

    def undo_impact(self) -> None:
        if not self.mark_history:
            return
        timestamp = self.mark_history.pop()
        for index in range(len(self.project.impacts) - 1, -1, -1):
            if self.project.impacts[index].timestamp_ms == timestamp:
                self.project.remove_impact(index)
                break
        self._refresh_impacts()

    def _timeline_context_menu(self, position: QPoint) -> None:
        item = self.impact_table.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.impact_table.selectRow(item.row())
        self._update_action_states()
        menu = QMenu(self)
        menu.addAction(self.shortcut_actions["E"])
        menu.addAction(self.shortcut_actions["Delete"])
        try:
            menu.exec(self.impact_table.viewport().mapToGlobal(position))
        finally:
            menu.deleteLater()

    def edit_selected(self) -> None:
        if not self.edit_button.isEnabled():
            return
        row = self.impact_table.selectedIndexes()[0].row()
        kind, timestamp, source_index = self._timeline_items()[row]
        impact = self.project.impacts[source_index] if source_index is not None else None
        minimum, maximum = 0, self.player.duration()
        if kind == "Round 1 end" and self.project.game_end_ms is not None:
            maximum = min(maximum, self.project.game_end_ms)
        elif kind == "Game end" and self.project.round_one_end_ms is not None:
            minimum = self.project.round_one_end_ms
        was_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        position = self.player.position()
        self.player.pause()
        try:
            dialog = EditMarkDialog(
                timestamp,
                position,
                minimum,
                maximum,
                self.project.team_one_players + self.project.team_two_players,
                impact.thrower if impact is not None else None,
                self,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            updated_timestamp = dialog.timestamp_ms()
            if updated_timestamp is None:
                return
            if impact is not None:
                assert dialog.thrower_combo is not None
                updated_thrower = dialog.thrower_combo.currentText()
                if (updated_timestamp, updated_thrower) == (impact.timestamp_ms, impact.thrower):
                    return
                impact.timestamp_ms = updated_timestamp
                impact.thrower = updated_thrower
                self.project.impacts.sort()
            elif kind == "Round 1 end":
                if updated_timestamp == timestamp:
                    return
                self.project.round_one_end_ms = updated_timestamp
            else:
                if updated_timestamp == timestamp:
                    return
                self.project.game_end_ms = updated_timestamp
            # Existing undo tracks timestamps of newly added marks, not edits.
            self.mark_history.clear()
            self._refresh_impacts()
            self.impact_table.clearSelection()
            for row, (event_kind, _, index) in enumerate(self._timeline_items()):
                if (
                    impact is not None
                    and index is not None
                    and self.project.impacts[index] is impact
                ) or (impact is None and event_kind == kind):
                    self.impact_table.selectRow(row)
                    self.impact_table.scrollToItem(self.impact_table.item(row, 0))
                    break
        finally:
            if was_playing:
                self.player.play()

    def remove_selected(self) -> None:
        timeline = self._timeline_items()
        rows = sorted({index.row() for index in self.impact_table.selectedIndexes()})
        impact_indices: list[int] = []
        for row in rows:
            kind, _timestamp, source_index = timeline[row]
            if kind.startswith("Impact") and source_index is not None:
                impact_indices.append(source_index)
            elif kind == "Round 1 end":
                self.project.round_one_end_ms = None
            elif kind == "Game end":
                self.project.game_end_ms = None
        for source_index in sorted(impact_indices, reverse=True):
            self.project.remove_impact(source_index)
        self.mark_history.clear()
        self._refresh_impacts()

    def mark_round_end(self) -> None:
        if not self.project.video_path:
            QMessageBox.information(self, tr("No video"), tr("Open a video before marking events."))
            return
        self.project.round_one_end_ms = self.player.position()
        self._refresh_impacts()

    def mark_game_end(self) -> None:
        if not self.project.video_path:
            QMessageBox.information(self, tr("No video"), tr("Open a video before marking events."))
            return
        self.project.game_end_ms = self.player.position()
        self._refresh_impacts()

    def _seek_to_row(self, row: int, _column: int) -> None:
        if self.slider.isEnabled():
            self.player.setPosition(self._timeline_items()[row][1])

    def _timeline_items(self) -> list[tuple[str, int, int | None]]:
        items = [
            (
                f"Impact: {impact.thrower}" if impact.thrower else "Impact",
                impact.timestamp_ms,
                index,
            )
            for index, impact in enumerate(self.project.impacts)
        ]
        if self.project.round_one_end_ms is not None:
            items.append(("Round 1 end", self.project.round_one_end_ms, None))
        if self.project.game_end_ms is not None:
            items.append(("Game end", self.project.game_end_ms, None))
        return sorted(items, key=lambda item: (item[1], item[0]))

    def _refresh_impacts(self) -> None:
        self.slider.set_markers(
            [impact.timestamp_ms for impact in self.project.impacts],
            self.project.round_one_end_ms,
            self.project.game_end_ms,
        )
        timeline = self._timeline_items()
        self.impact_table.setRowCount(len(timeline))
        timestamp_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        base = self.impact_table.palette().base().color()
        for row, (kind, timestamp, source_index) in enumerate(timeline):
            event_text = (
                tr(kind)
                if source_index is None
                else (
                    tr("Impact: {name}", name=self.project.impacts[source_index].thrower)
                    if self.project.impacts[source_index].thrower
                    else tr("Impact")
                )
            )
            event_item = QTableWidgetItem(event_text)
            event_item.setToolTip(event_text)
            time_item = QTableWidgetItem(format_timestamp(timestamp))
            time_item.setFont(timestamp_font)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if source_index is None:
                accent = QColor("#4488cc" if kind == "Round 1 end" else "#35a575")
                background = QColor(
                    round(base.red() * 0.85 + accent.red() * 0.15),
                    round(base.green() * 0.85 + accent.green() * 0.15),
                    round(base.blue() * 0.85 + accent.blue() * 0.15),
                )
                for item in (event_item, time_item):
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setBackground(QBrush(background))
            self.impact_table.setItem(row, 0, event_item)
            self.impact_table.setItem(row, 1, time_item)
        self._refresh_export_summary()

    def _update_action_states(self) -> None:
        idle = self.render_thread is None
        ready = (
            bool(self.project.video_path)
            and self.player.source()
            == QUrl.fromLocalFile(str(Path(self.project.video_path).resolve()))
            and self.player.duration() > 0
            and self.player.error() == QMediaPlayer.Error.NoError
            and self.player.mediaStatus()
            in {
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.BufferingMedia,
                QMediaPlayer.MediaStatus.BufferedMedia,
                QMediaPlayer.MediaStatus.StalledMedia,
                QMediaPlayer.MediaStatus.EndOfMedia,
            }
        )
        seekable = idle and ready and self.player.isSeekable()
        states = (
            ("Space", self.play_button, idle and ready),
            ("M", self.mark_button, idle and ready),
            ("Ctrl+R", self.round_end_button, idle and ready),
            ("Ctrl+G", self.game_end_button, idle and ready),
            ("Left", self.back_button, seekable and self.player.position() > 0),
            (
                "Right",
                self.forward_button,
                seekable and self.player.position() < self.player.duration(),
            ),
            ("Ctrl+Z", self.undo_button, idle and bool(self.mark_history)),
            ("Delete", self.remove_button, idle and bool(self.impact_table.selectedIndexes())),
            (
                "E",
                self.edit_button,
                idle
                and ready
                and len({index.row() for index in self.impact_table.selectedIndexes()}) == 1,
            ),
        )
        for keys, button, enabled in states:
            button.setEnabled(enabled)
            self.shortcut_actions[keys].setEnabled(enabled)
        self.slider.setEnabled(seekable)
        has_players = self.thrower_combo.count() > 1
        self.thrower_combo.setEnabled(idle and has_players)
        for keys in (",", "."):
            self.shortcut_actions[keys].setEnabled(idle and has_players)
        self.export_button.setEnabled(
            idle and ready and self.exportable_count > 0 and self.estimated_duration is not None
        )

    def _refresh_export_summary(self) -> None:
        preview = replace(
            self.project,
            pre_roll_ms=self.pre_roll.value() * 1000,
            post_roll_ms=self.post_roll.value() * 1000,
        )
        count, duration = estimate_export(preview, self.player.duration())
        self.exportable_count, self.estimated_duration = count, duration
        length = (
            tr("unavailable")
            if duration is None
            else format_timestamp(round(duration / 1000) * 1000).split(".")[0]
        )
        source = (
            "{count} highlight · Estimated video: {duration}"
            if count == 1
            else "{count} highlights · Estimated video: {duration}"
        )
        self.export_summary.setText(tr(source, count=count, duration=length))
        invalid_order = (
            self.project.round_one_end_ms is not None
            and self.project.game_end_ms is not None
            and self.project.round_one_end_ms > self.project.game_end_ms
        )
        if invalid_order:
            message = tr(
                "Export unavailable: round 1 ends after the game ends. "
                "Edit either end marker to fix the order."
            )
            self.export_summary.setText(message)
            color = "#e58b8b" if self.palette().window().color().lightness() < 128 else "#b44747"
            self.export_summary.setStyleSheet(f"color: {color};")
        else:
            self.export_summary.setStyleSheet("color: palette(placeholder-text);")
        self._update_action_states()

    def _position_changed(self, position: int) -> None:
        if not self.slider.isSliderDown():
            self.slider.setValue(position)
        self.position_label.setText(format_timestamp(position))
        self._update_action_states()

    def _duration_changed(self, duration: int) -> None:
        self.slider.setRange(0, duration)
        self.duration_label.setText(format_timestamp(duration))
        self._refresh_export_summary()

    def _sync_form(self) -> None:
        self.project.pre_roll_ms = self.pre_roll.value() * 1_000
        self.project.post_roll_ms = self.post_roll.value() * 1_000

    def cycle_thrower(self, direction: int = 1) -> None:
        if self.thrower_combo.count() <= 1:
            return
        current_index = self.thrower_combo.currentIndex()
        next_index = (current_index + direction) % self.thrower_combo.count()
        self.thrower_combo.setCurrentIndex(next_index)

    def _load_form(self) -> None:
        self.thrower_combo.clear()
        self.thrower_combo.addItem("")
        self.thrower_combo.addItems(self.project.team_one_players + self.project.team_two_players)
        self.pre_roll.setValue(self.project.pre_roll_ms // 1_000)
        self.post_roll.setValue(self.project.post_roll_ms // 1_000)
        self._refresh_impacts()
        if self.project.video_path:
            self._load_video(Path(self.project.video_path))
        else:
            self.player.setSource(QUrl())
            self.video_status.setText(tr("No video selected"))
        self._update_action_states()

    def export_video(self) -> None:
        if self.render_thread is not None:
            return
        self._sync_form()
        if not self.project.impacts:
            QMessageBox.information(
                self, tr("No impacts"), tr("Mark at least one impact before exporting.")
            )
            return
        missing_markers = []
        if self.project.round_one_end_ms is None:
            missing_markers.append(tr("Round 1 end (round-one result screen)"))
        if self.project.game_end_ms is None:
            missing_markers.append(tr("Game end (final result/winner screen)"))
        if missing_markers:
            answer = QMessageBox.question(
                self,
                tr("Missing end markers"),
                tr("The following markers have not been added:\n\n")
                + "\n".join(missing_markers)
                + tr("\n\nProceed without these markers and their result screens?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        default_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.MoviesLocation
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export highlights"),
            str(Path(default_dir) / default_export_filename(self.project)),
            tr("MP4 video (*.mp4)"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        self.export_button.setEnabled(False)
        self.export_button.setText(tr("Rendering…"))
        self.statusBar().showMessage(tr("Rendering highlights…"))
        snapshot = deepcopy(self.project)
        self.render_thread = RenderThread(snapshot, Path(filename), self.player.duration())
        self._update_action_states()
        self.render_thread.succeeded.connect(self._export_succeeded)
        self.render_thread.failed.connect(self._export_failed)
        self.render_thread.cancelled.connect(self._export_cancelled)
        self.render_thread.finished.connect(self._export_finished)
        self.render_outcome = None
        self.render_dialog = RenderDialog(self)
        self.render_dialog.cancel_requested.connect(self.render_thread.cancel)
        self.render_dialog.show()
        self.render_thread.start()

    def _export_succeeded(self, filename: str) -> None:
        self.render_outcome = ("success", filename)

    def _export_failed(self, message: str) -> None:
        self.render_outcome = ("error", message)

    def _export_cancelled(self) -> None:
        self.render_outcome = ("cancelled", "")

    def _export_finished(self) -> None:
        if self.render_dialog is not None:
            self.render_dialog.accept()
            self.render_dialog.deleteLater()
            self.render_dialog = None
        if self.render_thread is not None:
            self.render_thread.deleteLater()
            self.render_thread = None
        self._update_action_states()
        self.export_button.setText(tr("Export highlights…"))
        outcome = self.render_outcome
        self.render_outcome = None
        if outcome is not None:
            kind, message = outcome
            if kind == "success":
                self.statusBar().showMessage(tr("Export complete"), 5_000)
                QMessageBox.information(
                    self, tr("Export complete"), tr("Saved highlights to:\n{path}", path=message)
                )
            elif kind == "error":
                self.statusBar().clearMessage()
                QMessageBox.critical(self, tr("Export failed"), message)
            else:
                self.statusBar().showMessage(tr("Export cancelled"), 5_000)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.render_thread is not None:
            if self.render_dialog is not None:
                self.render_dialog.reject()
            event.ignore()
            return
        super().closeEvent(event)


def main() -> int:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OAMK.KyykkaEditor")
    app = QApplication(sys.argv)
    app.setApplicationName("Kyykka Editor")
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    set_language(saved_language())
    window = MainWindow()
    window.show()
    QTimer.singleShot(0, window.new_project)
    return app.exec()
