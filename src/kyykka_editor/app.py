from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from threading import Event

os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
# Keep Qt Multimedia developer diagnostics disabled unless a caller explicitly enables them.
os.environ.setdefault("QT_FFMPEG_DEBUG", "0")
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg.*=false")

from PySide6.QtCore import (
    QByteArray,
    QElapsedTimer,
    QEvent,
    QMimeData,
    QPoint,
    QRectF,
    QSettings,
    QSize,
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
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QHelpEvent,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QResizeEvent,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
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
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStyle,
    QStyleOptionSlider,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .card_settings import CardSettingsDialog, load_card_defaults
from .dialog_style import dialog_layout, form_layout, heading
from .history import TimelineSnapshot
from .hotkeys import HotkeysDialog, load_bindings
from .i18n import LANGUAGES, language, saved_language, set_language, tr
from .model import EditorProject, default_export_filename, format_timestamp
from .render import (
    RenderCancelled,
    RenderError,
    estimate_export,
    overlapping_highlights,
    preview_bounds,
    render_highlights,
)
from .storage import project_data, read_project, write_project
from .toast import Toast

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
        self.setMinimumWidth(660)
        layout = dialog_layout(self)
        layout.addWidget(heading("Recording"))
        form = form_layout()
        layout.addLayout(form)
        self.title_edit = QLineEdit(project.title)
        self.title_subtitle_edit = QLineEdit(project.title_subtitle)
        self.final_subtitle_edit = QLineEdit(project.final_subtitle)
        for editor in (self.title_subtitle_edit, self.final_subtitle_edit):
            editor.setPlaceholderText(tr("Optional"))
        self.recording_type = QComboBox()
        self.recording_type.addItems([tr("Match"), tr("Solo")])
        self.recording_type.setCurrentIndex(1 if project.solo else 0)
        form.addRow(tr("Recording type"), self.recording_type)
        self.team_one_edit = QLineEdit(project.team_one)
        self.team_two_edit = QLineEdit(project.team_two)
        self.video_path = project.video_path
        self.video_label = ElidedLabel()
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
        form.addRow(tr("Title-screen subtitle"), self.title_subtitle_edit)
        form.addRow(tr("Video"), video_row)
        layout.addSpacing(4)
        layout.addWidget(heading("Participants"))
        participants = QHBoxLayout()
        participants.setSpacing(20)
        first_team, second_team = QWidget(), QWidget()
        first_form, second_form = form_layout(first_team), form_layout(second_team)
        for team_form in (first_form, second_form):
            team_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        first_form.addRow(tr("Team 1"), self.team_one_edit)
        first_form.addRow(tr("Team 1 players"), self.players_one)
        second_form.addRow(tr("Team 2"), self.team_two_edit)
        second_form.addRow(tr("Team 2 players"), self.players_two)
        participants.addWidget(first_team, 1)
        participants.addWidget(second_team, 1)
        layout.addLayout(participants)
        layout.addSpacing(4)
        layout.addWidget(heading("Scores"))
        score_grid = QGridLayout()
        score_grid.setHorizontalSpacing(16)
        score_grid.setVerticalSpacing(8)
        score_grid.addWidget(QLabel(tr("Round 1")), 0, 1)
        score_grid.addWidget(QLabel(tr("Round 2")), 0, 2)
        self.score_team_one = ElidedLabel(project.team_one or tr("Team 1"))
        self.score_team_two = ElidedLabel(project.team_two or tr("Team 2"))
        score_grid.setColumnStretch(0, 1)
        self.team_one_edit.textChanged.connect(
            lambda name: self.score_team_one.setText(
                name.strip() or tr("Player" if self.recording_type.currentIndex() else "Team 1")
            )
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
        layout.addLayout(score_grid)
        result_form = form_layout()
        result_form.addRow(tr("Final-result subtitle"), self.final_subtitle_edit)
        layout.addLayout(result_form)
        field_labels = [
            current.itemAt(row, QFormLayout.ItemRole.LabelRole).widget()
            for current in (form, result_form)
            for row in range(current.rowCount())
        ]
        label_width = max(label.sizeHint().width() for label in field_labels)
        for label in field_labels:
            label.setMinimumWidth(label_width)
        layout.addSpacing(4)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setProperty("primary", True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        tab_order = (
            self.recording_type,
            self.title_edit,
            self.title_subtitle_edit,
            browse,
            self.team_one_edit,
            self.players_one,
            self.team_two_edit,
            self.players_two,
            self.scores[0],
            self.scores[2],
            self.scores[1],
            self.scores[3],
            self.final_subtitle_edit,
            buttons.button(QDialogButtonBox.StandardButton.Save),
            buttons.button(QDialogButtonBox.StandardButton.Cancel),
        )
        for first, second in pairwise(tab_order):
            QWidget.setTabOrder(first, second)

        def update_mode() -> None:
            solo = self.recording_type.currentIndex() == 1
            first_form.labelForField(self.team_one_edit).setText(tr("Player" if solo else "Team 1"))
            first_form.setRowVisible(self.players_one, not solo)
            for widget in (self.team_two_edit, self.players_two):
                second_form.setRowVisible(widget, not solo)
            second_team.setVisible(not solo)
            for widget in (self.score_team_two, self.scores[1], self.scores[3]):
                widget.setVisible(not solo)
            self.score_team_one.setText(
                self.team_one_edit.text().strip() or tr("Player" if solo else "Team 1")
            )
            layout.invalidate()
            layout.activate()
            self.resize(self.width(), self.sizeHint().height())

        self.recording_type.currentIndexChanged.connect(update_mode)
        update_mode()

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
        project.solo = self.recording_type.currentIndex() == 1
        project.title = self.title_edit.text().strip()
        project.title_subtitle = self.title_subtitle_edit.text().strip()
        project.final_subtitle = self.final_subtitle_edit.text().strip()
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
        *,
        pre_roll_ms: int | None = None,
        post_roll_ms: int | None = None,
        default_pre_roll_ms: int = 4000,
        default_post_roll_ms: int = 3000,
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
            self.override_before = QCheckBox(tr("Override"))
            self.override_after = QCheckBox(tr("Override"))
            self.before_spin = QSpinBox()
            self.after_spin = QSpinBox()
            for label, checkbox, spin, override, default in (
                (
                    "Before impact",
                    self.override_before,
                    self.before_spin,
                    pre_roll_ms,
                    default_pre_roll_ms,
                ),
                (
                    "After impact",
                    self.override_after,
                    self.after_spin,
                    post_roll_ms,
                    default_post_roll_ms,
                ),
            ):
                spin.setRange(0, 30)
                spin.setSuffix(" s")
                spin.setValue((default if override is None else override) // 1000)
                checkbox.setChecked(override is not None)
                spin.setEnabled(checkbox.isChecked())
                checkbox.toggled.connect(spin.setEnabled)
                row = QHBoxLayout()
                row.addWidget(checkbox)
                row.addWidget(spin)
                form.addRow(tr(label), row)
            form.addRow(QLabel(tr("Uncheck Override to use the main timing settings.")))
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
        self.selected_markers: set[tuple[str, int]] = set()
        self.setAccessibleName(tr("Video timeline"))
        self.setMinimumHeight(28)

    def set_selected_markers(self, markers: set[tuple[str, int]]) -> None:
        if markers != self.selected_markers:
            self.selected_markers = markers
            self.update()

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
        for x, kind, timestamp in self._marker_details():
            marker_color, height = styles[kind]
            if not self.isEnabled():
                marker_color.setAlpha(110)
            painter.setPen(QPen(marker_color, 2))
            painter.drawLine(x, self.height() - height, x, self.height() - 2)
            if (kind, timestamp) in self.selected_markers:
                painter.setPen(QPen(self.palette().text().color(), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(x - 4, self.height() - 20, 8, 18)
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

    def __init__(
        self,
        parent: QWidget,
        *,
        title: str = "Rendering highlights",
        activity: str = "Rendering highlights…",
    ) -> None:
        super().__init__(parent)
        self.activity = activity
        self.setWindowTitle(tr(title))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        self.status = QLabel(tr("Preparing export…"))
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        self.elapsed_label = QLabel()
        layout.addWidget(self.elapsed_label)
        self.elapsed = QElapsedTimer()
        self.elapsed.start()
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._update_elapsed)
        self.elapsed_timer.start(1000)
        self._update_elapsed()
        self.cancel_button = QPushButton(tr("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)

    def _update_elapsed(self) -> None:
        self.elapsed_label.setText(
            tr("Elapsed: {time}", time=format_timestamp(self.elapsed.elapsed()).split(".")[0])
        )

    def update_progress(self, percent: int) -> None:
        if not self.cancel_button.isEnabled():
            return
        self.progress.setRange(0, 100)
        self.progress.setValue(max(self.progress.value(), min(100, max(0, percent))))
        self.status.setText(tr("Finalizing video…") if percent >= 99 else tr(self.activity))

    def done(self, result: int) -> None:
        self.elapsed_timer.stop()
        super().done(result)

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
    progress_changed = Signal(int)

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
            render_highlights(
                self.project,
                self.output,
                self.duration_ms,
                self.cancel_event,
                self.progress_changed.emit,
            )
        except RenderCancelled:
            self.cancelled.emit()
        except (RenderError, OSError) as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(str(self.output))


class VideoPreview(QGraphicsView):
    """Compose the video and editing overlay in the same graphics scene."""

    details_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setStyleSheet("VideoPreview { border: 1px solid palette(mid); }")
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
        self.empty_label = QLabel(self.viewport())
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color: palette(placeholder-text); border: none;")
        self.details_button = QPushButton(self.viewport())
        self.details_button.clicked.connect(self.details_requested.emit)
        layout = QVBoxLayout(self.viewport())
        layout.addStretch()
        layout.addWidget(self.empty_label)
        layout.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        self.retranslate()
        self.set_video_selected(False)

    def retranslate(self) -> None:
        self.empty_label.setText(tr("No video file selected"))
        self.details_button.setText(tr("Match details"))

    def set_video_selected(self, selected: bool) -> None:
        self.video_item.setVisible(selected)
        self.empty_label.setVisible(not selected)
        self.details_button.setVisible(not selected)
        self.viewport().update()

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(
            rect,
            QBrush(QColor("black"))
            if self.video_item.isVisible()
            else self.window().palette().window(),
        )

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


class ElidedLabel(QLabel):
    """Keep full text accessible while fitting the visible label to available space."""

    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        text = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideMiddle, self.contentsRect().width()
        )
        self.style().drawItemText(
            painter,
            self.contentsRect(),
            self.alignment(),
            self.palette(),
            self.isEnabled(),
            text,
            self.foregroundRole(),
        )

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ToolTip and isinstance(event, QHelpEvent):
            QToolTip.showText(event.globalPos(), self.toolTip() or self.text(), self)
            return True
        return super().event(event)


class WrappingControls(QWidget):
    """Keep control groups together, stacking them when the panel becomes narrow."""

    def __init__(self, *groups: QWidget) -> None:
        super().__init__()
        self.groups = groups
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(12)
        self.row.setSizeConstraint(QBoxLayout.SizeConstraint.SetNoConstraint)
        for group in groups:
            self.row.addWidget(group)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

    def minimumSizeHint(self) -> QSize:
        return QSize(
            max(group.minimumSizeHint().width() for group in self.groups),
            self.row.minimumSize().height(),
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._arrange()

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.LayoutRequest and hasattr(self, "row"):
            self._arrange()
        return super().event(event)

    def _arrange(self) -> None:
        needed = sum(group.sizeHint().width() for group in self.groups)
        needed += self.row.spacing() * (len(self.groups) - 1)
        direction = (
            QBoxLayout.Direction.TopToBottom
            if self.width() < needed
            else QBoxLayout.Direction.LeftToRight
        )
        if direction != self.row.direction():
            self.row.setDirection(direction)
            self.updateGeometry()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = EditorProject()
        settings = QSettings("KyykkaEditor", "KyykkaEditor")

        def skip_seconds(key: str, default: int) -> int:
            try:
                value = int(settings.value(key, default))
                return value if 1 <= value <= 120 else default
            except (TypeError, ValueError):
                return default

        self.skip_backward = skip_seconds("skip_backward_seconds", 3)
        self.skip_forward = skip_seconds("skip_forward_seconds", 5)
        self.project_path: Path | None = None
        self.pending_resume: tuple[int, str] | None = None
        self.saved_project = project_data(self.project)
        self.autosaved_project = self.saved_project
        self.persistence_started = False
        self.recovery_path = (
            Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
            / "recovery.kyykka"
        )
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(5000)
        self.autosave_timer.timeout.connect(self._autosave)
        self.undo_history: list[TimelineSnapshot] = []
        self.render_thread: RenderThread | None = None
        self.render_dialog: RenderDialog | None = None
        self.render_outcome: tuple[str, str] | None = None
        self.shortcut_actions: dict[str, QAction] = {}
        self.preview_end: int | None = None
        self.configurable_actions: dict[str, QAction] = {}
        self.exportable_count = 0
        self.estimated_duration: int | None = None
        self.setWindowTitle("Kyykkä Editor")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1180, 780)
        self.setAcceptDrops(True)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.video = VideoPreview()
        # Let file drops over the graphics viewport reach the main window.
        self.video.setAcceptDrops(False)
        self.player.setVideoOutput(self.video.video_item)
        self.player.sourceChanged.connect(
            lambda source: self.video.set_video_selected(not source.isEmpty())
        )
        self.video.details_requested.connect(self.edit_project_details)

        self._build_ui()
        self._build_menu()
        self._apply_hotkeys(load_bindings({key: key for key in self.configurable_actions}))
        self._connect_player()
        self._refresh_impacts()

        self.toast = Toast(self)
        self._restore_workspace(settings)

    def _restore_workspace(self, settings: QSettings) -> None:
        geometry = settings.value("workspace/geometry")
        splitter = settings.value("workspace/splitter")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        if isinstance(splitter, QByteArray):
            self.workspace_splitter.restoreState(splitter)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if (
            event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange)
            and hasattr(self, "shortcut_actions")
            and "Space" in self.shortcut_actions
        ):
            self._refresh_transport_controls()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("editorRoot")
        root.setStyleSheet(
            "QWidget#editorRoot QPushButton { min-height: 24px; padding: 4px 10px; }"
            "QWidget#editorRoot QComboBox { min-height: 24px; padding: 4px 6px; }"
            "QWidget#editorRoot QPushButton:focus, QWidget#editorRoot QComboBox:focus { "
            "border: 1px solid palette(highlight); border-radius: 4px; }"
            'QPushButton[primary="true"] { background: palette(highlight); '
            "color: palette(highlighted-text); border: 1px solid palette(highlight); "
            "border-radius: 4px; font-weight: 600; }"
            'QPushButton[primary="true"]:hover, QPushButton[primary="true"]:focus { '
            "border-color: palette(highlighted-text); }"
            'QPushButton[primary="true"]:pressed { background: palette(dark); }'
            'QPushButton[primary="true"]:disabled { background: palette(button); '
            "color: palette(placeholder-text); border-color: palette(mid); }"
        )
        outer = QHBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setHandleWidth(12)
        self.workspace_splitter.setStyleSheet(
            "QSplitter::handle:horizontal { background: palette(mid); margin: 12px 5px; }"
            "QSplitter::handle:horizontal:hover { background: palette(highlight); }"
        )
        self.video_panel, self.sidebar = QWidget(), QWidget()
        left, right = QVBoxLayout(self.video_panel), QVBoxLayout(self.sidebar)
        left.setContentsMargins(0, 0, 6, 0)
        right.setContentsMargins(6, 0, 0, 0)
        left.setSpacing(8)
        right.setSpacing(8)

        def section_heading(text: str) -> QLabel:
            label = QLabel(tr(text))
            font = label.font()
            font.setWeight(QFont.Weight.DemiBold)
            font.setPointSizeF(font.pointSizeF() + 1)
            label.setFont(font)
            return label

        def section_break() -> None:
            right.addSpacing(8)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet("background: palette(mid);")
            right.addWidget(line)
            right.addSpacing(8)

        source_row = QHBoxLayout()
        self.video_status = ElidedLabel(tr("No video selected"))
        status_font = self.video_status.font()
        status_font.setPointSizeF(max(8.0, status_font.pointSizeF() - 1.0))
        self.video_status.setFont(status_font)
        self.video_status.setStyleSheet("color: palette(placeholder-text);")
        source_row.addWidget(self.video_status, 1)
        self.preview_indicator = QLabel(tr("Previewing highlight"))
        self.preview_indicator.setStyleSheet("color: palette(placeholder-text);")
        self.preview_indicator.hide()
        source_row.addWidget(self.preview_indicator)
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

        transport = QWidget()
        controls = QHBoxLayout(transport)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        self.back_button = QPushButton("−3 s")
        self.play_button = QPushButton()
        self.play_button.setFixedWidth(44)
        self.back_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSeekBackward)
        )
        self.forward_button = QPushButton("+5 s")
        self.forward_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSeekForward)
        )
        self.playback_speed = QComboBox()
        for rate in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0):
            self.playback_speed.addItem(f"{rate:g}×", rate)
        self.playback_speed.setCurrentIndex(3)
        self.playback_speed.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.playback_speed.setToolTip(tr("Playback speed (export speed is unchanged)"))
        self.playback_speed.setAccessibleName(tr("Playback speed"))
        self.playback_speed.currentIndexChanged.connect(
            lambda: self.player.setPlaybackRate(self.playback_speed.currentData())
        )
        self.mark_button = QPushButton(tr("Mark impact"))
        self.mark_button.setProperty("primary", True)
        self.undo_button = QPushButton(tr("Undo"))
        self.mark_button.setDefault(True)
        for button in (
            self.back_button,
            self.play_button,
            self.forward_button,
            self.playback_speed,
        ):
            controls.addWidget(button)
        controls.addStretch()
        marking = QWidget()
        marking_row = QHBoxLayout(marking)
        marking_row.setContentsMargins(0, 0, 0, 0)
        marking_row.setSpacing(8)
        marking_row.addWidget(self.mark_button)
        marking_row.addWidget(self.undo_button)
        self.playback_controls = WrappingControls(transport, marking)
        left.addWidget(self.playback_controls)

        self.details_button = QPushButton(tr("Match details…"))
        self.details_button.clicked.connect(self.edit_project_details)
        match_row = QHBoxLayout()
        self.match_heading = section_heading("Match")
        match_row.addWidget(self.match_heading, 1)
        match_row.addWidget(self.details_button)
        right.addLayout(match_row)
        self.match_summary = QLabel()
        self.match_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.match_summary.setWordWrap(True)
        self.match_summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.match_summary.setMaximumHeight(self.match_summary.fontMetrics().lineSpacing() * 3)
        self.match_summary.setStyleSheet("color: palette(placeholder-text);")
        right.addWidget(self.match_summary)
        section_break()
        self.marking_heading = section_heading("Marking")
        right.addWidget(self.marking_heading)

        thrower_form = QFormLayout()
        thrower_form.setVerticalSpacing(8)
        thrower_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.thrower_combo = QComboBox()
        self.thrower_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.thrower_combo.setMinimumContentsLength(10)
        self.thrower_combo.currentTextChanged.connect(self.thrower_combo.setToolTip)
        self.thrower_combo.currentTextChanged.connect(self.video.set_thrower)
        thrower_field = QVBoxLayout()
        thrower_field.setSpacing(2)
        thrower_field.addWidget(self.thrower_combo)
        self.thrower_shortcut_hint = QLabel(tr(",=next  .=previous"))
        hint_font = self.thrower_shortcut_hint.font()
        hint_font.setPointSizeF(max(8.0, hint_font.pointSizeF() - 1.0))
        self.thrower_shortcut_hint.setFont(hint_font)
        self.thrower_shortcut_hint.setStyleSheet("color: palette(placeholder-text);")
        self.thrower_shortcut_hint.setWordWrap(True)
        thrower_field.addWidget(self.thrower_shortcut_hint)
        self.thrower_label = QLabel(tr("Current thrower"))
        thrower_form.addRow(self.thrower_label, thrower_field)
        right.addLayout(thrower_form)

        event_row = QHBoxLayout()
        event_row.setSpacing(8)
        self.round_end_button = QPushButton(tr("Mark round 1 end"))
        self.game_end_button = QPushButton(tr("Mark game end"))
        event_row.addWidget(self.round_end_button)
        event_row.addWidget(self.game_end_button)
        right.addLayout(event_row)
        section_break()
        self.timeline_label = section_heading("Highlights")
        right.addWidget(self.timeline_label)
        self.impact_table = QTableWidget(0, 2)
        self.impact_table.setAlternatingRowColors(False)
        self.impact_table.setShowGrid(False)
        self.impact_table.verticalHeader().hide()
        self.impact_table.verticalHeader().setDefaultSectionSize(
            max(34, self.impact_table.fontMetrics().height() + 16)
        )
        self.impact_table.setStyleSheet(
            "QTableWidget { border: 1px solid palette(mid); }"
            "QTableWidget::item { padding: 4px 8px; }"
            "QTableWidget::item:selected { background: palette(highlight); color: palette(highlighted-text); }"
            "QHeaderView::section { padding: 6px 8px; border: none; "
            "border-bottom: 1px solid palette(mid); background: palette(window); }"
        )
        self.impact_table.setHorizontalHeaderLabels([tr("Event"), tr("Timestamp")])
        self.impact_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.impact_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.impact_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.impact_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.impact_table.setAccessibleName(tr("Highlights"))
        self.impact_table.setTabKeyNavigation(False)
        self.empty_highlights = QLabel(self.impact_table.viewport())
        self.empty_highlights.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_highlights.setWordWrap(True)
        self.empty_highlights.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.empty_highlights.setStyleSheet("color: palette(text); padding: 12px;")
        empty_layout = QVBoxLayout(self.impact_table.viewport())
        empty_layout.addWidget(self.empty_highlights)
        right.addWidget(self.impact_table, 1)
        self.preview_button = QPushButton(tr("Preview selected"))
        self.preview_button.clicked.connect(self.preview_highlight)
        right.addWidget(self.preview_button)
        self.remove_button = QPushButton(tr("Remove selected"))
        self.edit_button = QPushButton(tr("Edit selected…"))
        self.export_button = QPushButton(tr("Export highlights…"))
        self.export_button.setProperty("primary", True)
        edit_row = QHBoxLayout()
        edit_row.setSpacing(8)
        edit_row.addWidget(self.edit_button)
        edit_row.addWidget(self.remove_button)
        right.addLayout(edit_row)
        self.action_guidance = QLabel()
        self.action_guidance.setWordWrap(True)
        self.action_guidance.setStyleSheet("color: palette(text);")
        right.addWidget(self.action_guidance)
        right.addSpacing(8)
        self.export_summary = QLabel()
        self.export_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.export_summary.setWordWrap(True)
        self.export_summary.setStyleSheet("color: palette(placeholder-text);")
        right.addWidget(self.export_summary)
        right.addWidget(self.export_button)

        self.workspace_splitter.addWidget(self.video_panel)
        self.workspace_splitter.addWidget(self.sidebar)
        self.workspace_splitter.setStretchFactor(0, 3)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setSizes([840, 300])
        outer.addWidget(self.workspace_splitter)
        self.setCentralWidget(root)
        tab_order = (
            self.video.details_button,
            self.slider,
            self.back_button,
            self.play_button,
            self.forward_button,
            self.playback_speed,
            self.mark_button,
            self.undo_button,
            self.details_button,
            self.thrower_combo,
            self.round_end_button,
            self.game_end_button,
            self.impact_table,
            self.preview_button,
            self.edit_button,
            self.remove_button,
            self.export_button,
        )
        for first, second in pairwise(tab_order):
            QWidget.setTabOrder(first, second)

        self.play_button.clicked.connect(self.toggle_playback)
        self.back_button.clicked.connect(lambda: self.seek_relative(-self.skip_backward * 1000))
        self.forward_button.clicked.connect(lambda: self.seek_relative(self.skip_forward * 1000))
        self.mark_button.clicked.connect(self.mark_impact)
        self.undo_button.clicked.connect(self.undo_last_action)
        self.remove_button.clicked.connect(self.remove_selected)
        self.edit_button.clicked.connect(self.edit_selected)
        self.export_button.clicked.connect(self.export_video)
        self.round_end_button.clicked.connect(self.mark_round_end)
        self.game_end_button.clicked.connect(self.mark_game_end)
        self.slider.sliderMoved.connect(self._manual_seek)
        self.slider.seek_requested.connect(self._manual_seek)
        self.impact_table.cellDoubleClicked.connect(self._seek_to_row)
        self.impact_table.itemSelectionChanged.connect(self._update_action_states)
        self.impact_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.impact_table.customContextMenuRequested.connect(self._timeline_context_menu)

        for text, keys, callback in (
            ("Preview highlight", "P", self.preview_highlight),
            ("Stop highlight preview", "Escape", self.stop_preview),
            ("Play or pause", "Space", self.toggle_playback),
            ("Mark impact", "M", self.mark_impact),
            ("Next thrower", ",", lambda: self.cycle_thrower()),
            ("Previous thrower", ".", lambda: self.cycle_thrower(-1)),
            ("Undo latest change", "Ctrl+Z", self.undo_last_action),
            ("Seek backward", "Left", lambda: self.seek_relative(-self.skip_backward * 1000)),
            ("Seek forward", "Right", lambda: self.seek_relative(self.skip_forward * 1000)),
            ("Remove selected event", "Delete", self.remove_selected),
            ("Edit selected event", "E", self.edit_selected),
            ("Mark round 1 end", "Ctrl+R", self.mark_round_end),
            ("Mark game end", "Ctrl+G", self.mark_game_end),
        ):
            self._add_shortcut(text, keys, callback)

    def _build_menu(self) -> None:
        self.file_menu = menu = self.menuBar().addMenu(tr("&File"))
        for text, shortcut, callback in (
            ("Open project", "Ctrl+O", self.open_project),
            ("Save project", "Ctrl+S", lambda: self.save_project()),
            ("Save project as…", "Ctrl+Shift+S", lambda: self.save_project(save_as=True)),
            ("New match…", "Ctrl+N", self.new_project),
            ("Match details…", "Ctrl+D", self.edit_project_details),
        ):
            action = QAction(tr(text), self)
            action.setProperty("translation_source", text)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)
            self.configurable_actions[shortcut] = action

        menu.addSeparator()
        combine_action = menu.addAction(tr("Combine videos…"))
        combine_action.setProperty("translation_source", "Combine videos…")
        combine_action.triggered.connect(self.combine_videos)

        self.settings_menu = self.menuBar().addMenu(tr("&Settings"))
        preferences_action = self.settings_menu.addAction(tr("Preferences"))
        preferences_action.setProperty("translation_source", "Preferences")
        preferences_action.triggered.connect(self.edit_preferences)
        screen_action = self.settings_menu.addAction(tr("Screen settings"))
        screen_action.setProperty("translation_source", "Screen settings")
        screen_action.triggered.connect(self.edit_card_settings)
        hotkey_action = self.settings_menu.addAction(tr("Configure hotkeys"))
        hotkey_action.setProperty("translation_source", "Configure hotkeys")
        hotkey_action.triggered.connect(self.edit_hotkeys)

        self.help_menu = help_menu = self.menuBar().addMenu(tr("&Help"))
        self.hotkeys_menu = hotkeys_menu = help_menu.addMenu(tr("&Hotkeys"))
        hotkeys_menu.addActions(self.actions())
        hotkeys_menu.addSeparator()
        hotkeys_menu.addActions(
            [action for action in menu.actions() if action in self.configurable_actions.values()]
        )
        self.language_menu = self.settings_menu.addMenu(tr("&Language"))
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

    def edit_hotkeys(self) -> None:
        if self.render_thread is not None:
            return
        dialog = HotkeysDialog(self.configurable_actions, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_hotkeys(dialog.bindings())

    def edit_preferences(self) -> None:
        if self.render_thread is not None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Preferences"))
        dialog.setMinimumWidth(480)
        layout = dialog_layout(dialog)
        layout.addWidget(heading("Playback"))
        playback_hint = QLabel(tr("Application settings. Skip amounts are used in every project."))
        playback_hint.setWordWrap(True)
        playback_hint.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(playback_hint)
        playback_form = form_layout()
        backward, forward = QSpinBox(), QSpinBox()
        for spin, value, label in (
            (backward, self.skip_backward, "Skip backward (seconds)"),
            (forward, self.skip_forward, "Skip forward (seconds)"),
        ):
            spin.setRange(1, 120)
            spin.setValue(value)
            spin.setAccessibleName(tr(label))
            spin.setSuffix(" s")
            spin.setMinimumWidth(100)
            spin.setMaximumWidth(120)
        playback_form.addRow(tr("Backward"), backward)
        playback_form.addRow(tr("Forward"), forward)
        layout.addLayout(playback_form)
        layout.addSpacing(8)
        layout.addWidget(heading("Highlight timing"))
        timing_hint = QLabel(
            tr(
                "Default highlight timing for this project. Individual throw overrides take precedence."
            )
        )
        timing_hint.setWordWrap(True)
        timing_hint.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(timing_hint)
        before, after = QSpinBox(), QSpinBox()
        timing_form = form_layout()
        for spin, value, label in (
            (before, self.project.pre_roll_ms // 1000, "Before impact"),
            (after, self.project.post_roll_ms // 1000, "After impact"),
        ):
            spin.setRange(0, 30)
            spin.setValue(value)
            spin.setAccessibleName(tr(label))
            spin.setSuffix(" s")
            spin.setMinimumWidth(100)
            spin.setMaximumWidth(120)
        timing_form.addRow(tr("Before impact"), before)
        timing_form.addRow(tr("After impact"), after)
        layout.addLayout(timing_form)
        labels = [
            form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget()
            for form in (playback_form, timing_form)
            for row in range(form.rowCount())
        ]
        label_width = max(label.sizeHint().width() for label in labels)
        for label in labels:
            label.setMinimumWidth(label_width)
        layout.addSpacing(8)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setProperty("primary", True)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.skip_backward, self.skip_forward = backward.value(), forward.value()
        self.project.pre_roll_ms = before.value() * 1000
        self.project.post_roll_ms = after.value() * 1000
        self.stop_preview()
        self._refresh_export_summary()
        self._autosave()
        settings = QSettings("KyykkaEditor", "KyykkaEditor")
        settings.setValue("skip_backward_seconds", self.skip_backward)
        settings.setValue("skip_forward_seconds", self.skip_forward)
        self._refresh_skip_labels()

    def _refresh_skip_labels(self) -> None:
        self.back_button.setText(f"−{self.skip_backward} s")
        self.forward_button.setText(f"+{self.skip_forward} s")
        self.shortcut_actions["Left"].setText(
            tr("Seek backward {seconds} seconds", seconds=self.skip_backward)
        )
        self.shortcut_actions["Right"].setText(
            tr("Seek forward {seconds} seconds", seconds=self.skip_forward)
        )
        self._refresh_transport_controls()

    def _refresh_transport_controls(self) -> None:
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        for button, symbol in (
            (
                self.play_button,
                QStyle.StandardPixmap.SP_MediaPause
                if playing
                else QStyle.StandardPixmap.SP_MediaPlay,
            ),
            (self.back_button, QStyle.StandardPixmap.SP_MediaSeekBackward),
            (self.forward_button, QStyle.StandardPixmap.SP_MediaSeekForward),
        ):
            pixmap = self.style().standardIcon(symbol).pixmap(18, 18)
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(
                pixmap.rect(),
                button.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText),
            )
            painter.end()
            button.setIcon(QIcon(pixmap))
        for button, key, label in (
            (self.play_button, "Space", tr("Pause") if playing else tr("Play")),
            (
                self.back_button,
                "Left",
                tr("Seek backward {seconds} seconds", seconds=self.skip_backward),
            ),
            (
                self.forward_button,
                "Right",
                tr("Seek forward {seconds} seconds", seconds=self.skip_forward),
            ),
            (self.mark_button, "M", tr("Mark impact")),
        ):
            shortcut = (
                self.shortcut_actions[key]
                .shortcut()
                .toString(QKeySequence.SequenceFormat.NativeText)
            )
            button.setAccessibleName(label)
            button.setToolTip(f"{label} ({shortcut})" if shortcut else label)

    def _apply_hotkeys(self, bindings: dict[str, str]) -> None:
        for key, action in self.configurable_actions.items():
            action.setShortcut(QKeySequence(bindings[key]))
        self._refresh_hotkey_hint()

    def _refresh_hotkey_hint(self) -> None:
        self.slider.setAccessibleName(tr("Video timeline"))
        self.impact_table.setAccessibleName(tr("Highlights"))
        self._refresh_skip_labels()
        self.thrower_shortcut_hint.setText(
            tr(
                "{next}=next  {previous}=previous",
                next=self.shortcut_actions[","]
                .shortcut()
                .toString(QKeySequence.SequenceFormat.NativeText)
                or tr("Unassigned"),
                previous=self.shortcut_actions["."]
                .shortcut()
                .toString(QKeySequence.SequenceFormat.NativeText)
                or tr("Unassigned"),
            )
        )
        self._update_action_states()

    def _change_language(self, code: str) -> None:
        if self.render_thread is not None:
            return
        set_language(code, persist=True)
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        self.video.retranslate()
        self.playback_speed.setToolTip(tr("Playback speed (export speed is unchanged)"))
        self.playback_speed.setAccessibleName(tr("Playback speed"))
        self.preview_indicator.setText(tr("Previewing highlight"))
        for widget, source in (
            (self.mark_button, "Mark impact"),
            (self.undo_button, "Undo"),
            (self.details_button, "Match details…"),
            (self.thrower_label, "Current thrower"),
            (self.thrower_shortcut_hint, ",=next  .=previous"),
            (self.round_end_button, "Mark round 1 end"),
            (self.game_end_button, "Mark game end"),
            (self.match_heading, "Match"),
            (self.marking_heading, "Marking"),
            (self.timeline_label, "Highlights"),
            (self.preview_button, "Preview selected"),
            (self.remove_button, "Remove selected"),
            (self.edit_button, "Edit selected…"),
            (self.export_button, "Export highlights…"),
            (self.about_action, "&About Kyykkä Editor…"),
        ):
            widget.setText(tr(source))
        self._refresh_transport_controls()
        for menu, source in (
            (self.file_menu, "&File"),
            (self.settings_menu, "&Settings"),
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
        self._refresh_hotkey_hint()

    def _dropped_path(self, mime: QMimeData) -> Path | None:
        if self.render_thread is not None or not mime.hasUrls():
            return None
        urls = mime.urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        if path.suffix.lower() not in (".kyykka", ".mp4", ".mov", ".mkv", ".avi", ".m4v"):
            return None
        return path if path.is_file() else None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._dropped_path(event.mimeData()) is not None:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._dropped_path(event.mimeData())
        if path is None:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        if path.suffix.lower() == ".kyykka":
            self._open_project_path(path)
        else:
            self.new_project(video_path=str(path.resolve()))

    def combine_videos(self) -> None:
        if self.render_thread is not None:
            return
        from .combine_dialog import CombineVideosDialog

        self.player.pause()
        CombineVideosDialog(self).exec()

    def new_project(self, *, video_path: str = "") -> None:
        if self.render_thread is not None:
            return
        candidate = EditorProject(video_path=video_path, **load_card_defaults())
        dialog = ProjectDialog(candidate, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dialog.apply_to(candidate)
        if not self._confirm_replace():
            return
        self._remember_position()
        self.player.stop()
        self.project = candidate
        self.project_path = None
        self.pending_resume = None
        self.saved_project = project_data(EditorProject())
        self.undo_history.clear()
        self._load_form()
        self._autosave()

    def edit_card_settings(self) -> None:
        if self.render_thread is not None:
            return
        dialog = CardSettingsDialog(self.project, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.apply_current.isChecked():
            for key, style in dialog.styles.items():
                setattr(self.project, key, deepcopy(style))
            self._autosave()

    def _confirm_replace(self) -> bool:
        if not self.persistence_started or project_data(self.project) == self.saved_project:
            return True
        choice = QMessageBox.question(
            self,
            tr("Unsaved project"),
            tr("Save changes before continuing?"),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            return self.save_project()
        return choice == QMessageBox.StandardButton.Discard

    def save_project(self, save_as: bool = False) -> bool:
        if self.render_thread is not None:
            return False
        path = None if save_as else self.project_path
        if path is None:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                tr("Save project"),
                str(self.project_path or Path("match.kyykka")),
                tr("Kyykka projects (*.kyykka)"),
            )
            if not filename:
                return False
            path = Path(filename)
            if path.suffix.lower() != ".kyykka":
                path = path.with_suffix(".kyykka")
        try:
            write_project(path, self.project)
        except OSError as error:
            QMessageBox.warning(self, tr("Could not save project"), str(error))
            return False
        self.project_path = path
        self._remember_position()
        self.saved_project = project_data(self.project)
        self._clear_recovery()
        self._update_project_title()
        self.toast.notify(tr("Project saved"))
        return True

    def open_project(self) -> None:
        if self.render_thread is not None:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Open project"), "", tr("Kyykka projects (*.kyykka)")
        )
        if not filename:
            return
        self._open_project_path(Path(filename))

    def _open_project_path(self, path: Path, recovering: bool = False) -> bool:
        try:
            candidate = read_project(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, tr("Could not open project"), str(error))
            return False
        original = project_data(candidate)
        if candidate.video_path and not Path(candidate.video_path).is_file():
            QMessageBox.warning(
                self,
                tr("Video not found"),
                tr(
                    "The project's source video could not be found:\n{path}\n\n"
                    "Locate the video in the next window to continue opening this project.",
                    path=candidate.video_path,
                ),
            )
            filename, _ = QFileDialog.getOpenFileName(
                self, tr("Locate missing source video"), str(Path(candidate.video_path).parent)
            )
            if not filename:
                return False
            candidate.video_path = str(Path(filename).resolve())
        if not recovering and not self._confirm_replace():
            return False
        self._remember_position()
        self.player.stop()
        self.project = candidate
        self.project_path = None if recovering else path
        self.saved_project = project_data(EditorProject()) if recovering else original
        self.undo_history.clear()
        self.pending_resume = self._read_position()
        self._load_form()
        if not recovering:
            self._clear_recovery()
        self._autosave()
        return True

    def _clear_recovery(self) -> None:
        if not self.persistence_started:
            return
        try:
            self.recovery_path.unlink(missing_ok=True)
            self.autosaved_project = None
        except OSError as error:
            QMessageBox.warning(self, tr("Autosave recovery"), str(error))

    def _update_project_title(self) -> None:
        name = self.project_path.name if self.project_path else tr("Untitled project")
        modified = project_data(self.project) != self.saved_project
        self.setWindowTitle(f"{'* ' if modified else ''}{name} - Kyykkä Editor")

    def _autosave(self) -> None:
        self._update_project_title()
        if not self.persistence_started:
            return
        self._remember_position()
        current = project_data(self.project)
        if current == self.saved_project:
            if self.autosaved_project is not None and self.autosaved_project != current:
                self._clear_recovery()
            return
        if current == self.autosaved_project:
            return
        try:
            write_project(self.recovery_path, self.project)
        except OSError as error:
            self.autosave_timer.stop()
            QMessageBox.warning(self, tr("Autosave failed"), str(error))
            return
        self.autosaved_project = current

    def start_session(self) -> None:
        candidates = [
            self.recovery_path,
            *sorted(self.recovery_path.parent.glob("recovery-*.kyykka")),
        ]
        for path in candidates:
            if not path.exists():
                continue
            choice = QMessageBox.question(
                self,
                tr("Autosave recovery"),
                tr("Recover the autosaved project from the previous session?") + f"\n\n{path}",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if choice == QMessageBox.StandardButton.Yes:
                if self._open_project_path(path, recovering=True):
                    self.recovery_path = path
                    break
            elif choice == QMessageBox.StandardButton.No:
                try:
                    path.unlink(missing_ok=True)
                except OSError as error:
                    QMessageBox.warning(self, tr("Autosave recovery"), str(error))
        else:
            # A failed recovery belongs to the previous session. New work must
            # neither overwrite it on autosave nor delete it on save/close.
            if self.recovery_path.exists():
                self.recovery_path = self.recovery_path.with_name(
                    f"recovery-{uuid.uuid4().hex}.kyykka"
                )
        self.persistence_started = True
        self.autosaved_project = None
        self.autosave_timer.start()
        self._autosave()

    def edit_project_details(self) -> None:
        if self.render_thread is not None:
            return
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
        self.configurable_actions[keys] = action

    def _connect_player(self) -> None:
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.mediaStatusChanged.connect(self._media_status_changed)
        self.player.playbackStateChanged.connect(self._refresh_transport_controls)
        self.player.errorOccurred.connect(self._playback_error)
        self.player.seekableChanged.connect(self._update_action_states)
        self.player.seekableChanged.connect(self._restore_position)

    def _load_video(self, path: Path) -> None:
        self.stop_preview()
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
        if self.pending_resume is None:
            self.player.play()
        else:
            self.player.pause()
        self._update_project_title()

    def _media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        self._restore_position()
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
        self.stop_preview(pause=False)
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def seek_relative(self, milliseconds: int) -> None:
        target = max(0, min(self.player.duration(), self.player.position() + milliseconds))
        self._manual_seek(target)

    def _manual_seek(self, position: int) -> None:
        self.stop_preview(pause=False)
        self.player.setPosition(position)

    def _selected_preview_bounds(self) -> tuple[int, int] | None:
        rows = {item.row() for item in self.impact_table.selectedIndexes()}
        if len(rows) != 1:
            return None
        row = next(iter(rows))
        items = self._timeline_items()
        if row >= len(items):
            return None
        _, _, index = items[row]
        return (
            preview_bounds(self.project, index, self.player.duration())
            if index is not None
            else None
        )

    def preview_highlight(self) -> None:
        if not self.shortcut_actions["P"].isEnabled():
            return
        bounds = self._selected_preview_bounds()
        if bounds is None:
            return
        self.stop_preview()
        self.player.setPosition(bounds[0])
        self.preview_end = bounds[1]
        self.preview_indicator.show()
        self.player.play()
        self._update_action_states()

    def stop_preview(self, *, pause: bool = True) -> None:
        if self.preview_end is None:
            return
        self.preview_end = None
        self.preview_indicator.hide()
        if pause:
            self.player.pause()
        self._update_action_states()

    def mark_impact(self) -> None:
        if not self.project.video_path:
            QMessageBox.information(
                self, tr("No video"), tr("Open a video before marking impacts.")
            )
            return
        self._record_undo("Mark impact")
        self.project.add_impact(self.player.position(), self.thrower_combo.currentText())
        self._refresh_impacts()
        self.toast.notify(
            tr("Throw marked at {time}", time=format_timestamp(self.player.position()))
        )

    def _record_undo(self, action: str) -> None:
        selected = tuple(sorted({index.row() for index in self.impact_table.selectedIndexes()}))
        self.undo_history.append(TimelineSnapshot.capture(self.project, action, selected))

    def undo_last_action(self) -> None:
        if not self.undo_history or self.render_thread is not None:
            return
        previous = self.undo_history.pop()
        previous.restore(self.project)
        self._refresh_impacts()
        self.impact_table.clearSelection()
        for row in previous.selected_rows:
            for column in range(self.impact_table.columnCount()):
                item = self.impact_table.item(row, column)
                if item is not None:
                    item.setSelected(True)
        if previous.selected_rows:
            self.impact_table.scrollToItem(self.impact_table.item(previous.selected_rows[0], 0))
        self.toast.notify(tr("Undid: {action}", action=tr(previous.action)))

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
        menu.addAction(self.shortcut_actions["P"])
        try:
            menu.exec(self.impact_table.viewport().mapToGlobal(position))
        finally:
            menu.deleteLater()

    def edit_selected(self) -> None:
        self.stop_preview()
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
                self.project.throwers,
                impact.thrower if impact is not None else None,
                self,
                pre_roll_ms=impact.pre_roll_ms if impact is not None else None,
                post_roll_ms=impact.post_roll_ms if impact is not None else None,
                default_pre_roll_ms=self.project.pre_roll_ms,
                default_post_roll_ms=self.project.post_roll_ms,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            updated_timestamp = dialog.timestamp_ms()
            if updated_timestamp is None:
                return
            if impact is not None:
                assert dialog.thrower_combo is not None
                updated_thrower = dialog.thrower_combo.currentText()
                before = (
                    dialog.before_spin.value() * 1000
                    if dialog.override_before.isChecked()
                    else None
                )
                after = (
                    dialog.after_spin.value() * 1000 if dialog.override_after.isChecked() else None
                )
                if (
                    updated_timestamp,
                    updated_thrower,
                    before,
                    after,
                ) == (
                    impact.timestamp_ms,
                    impact.thrower,
                    impact.pre_roll_ms,
                    impact.post_roll_ms,
                ):
                    return
                self._record_undo("Edit throw")
                impact.timestamp_ms = updated_timestamp
                impact.thrower = updated_thrower
                impact.pre_roll_ms, impact.post_roll_ms = before, after
                self.project.impacts.sort()
            elif kind == "Round 1 end":
                if updated_timestamp == timestamp:
                    return
                self._record_undo("Edit round 1 end")
                self.project.round_one_end_ms = updated_timestamp
            else:
                if updated_timestamp == timestamp:
                    return
                self._record_undo("Edit game end")
                self.project.game_end_ms = updated_timestamp
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
        if not rows or self.render_thread is not None:
            return
        self._record_undo("Delete events")
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
        self._refresh_impacts()

    def mark_round_end(self) -> None:
        if not self.project.video_path:
            QMessageBox.information(self, tr("No video"), tr("Open a video before marking events."))
            return
        if self.project.round_one_end_ms == self.player.position():
            return
        self._record_undo("Mark round 1 end")
        self.project.round_one_end_ms = self.player.position()
        self._refresh_impacts()

    def mark_game_end(self) -> None:
        if not self.project.video_path:
            QMessageBox.information(self, tr("No video"), tr("Open a video before marking events."))
            return
        if self.project.game_end_ms == self.player.position():
            return
        self._record_undo("Mark game end")
        self.project.game_end_ms = self.player.position()
        self._refresh_impacts()

    def _seek_to_row(self, row: int, _column: int) -> None:
        if self.slider.isEnabled():
            self._manual_seek(self._timeline_items()[row][1])

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
        names = (
            [self.project.team_one]
            if self.project.solo
            else [self.project.team_one, self.project.team_two]
        )
        matchup = " vs. ".join(name.strip() for name in names if name.strip())
        title = self.project.title.strip()
        summary = "\n".join(text for text in (title, matchup if matchup != title else "") if text)
        self.match_summary.setText(summary or tr("Untitled project"))
        self.match_summary.setToolTip(summary)
        self.stop_preview()
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
            if source_index is not None:
                impact = self.project.impacts[source_index]
                if impact.pre_roll_ms is not None or impact.post_roll_ms is not None:
                    event_text += tr(" (custom timing)")
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
        self.video.details_button.setEnabled(idle)
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
        self.shortcut_actions["P"].setEnabled(
            seekable and self._selected_preview_bounds() is not None
        )
        self.shortcut_actions["Escape"].setEnabled(self.preview_end is not None)
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
            ("Ctrl+Z", self.undo_button, idle and bool(self.undo_history)),
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
        undo_text = (
            tr("Undo: {action}", action=tr(self.undo_history[-1].action))
            if self.undo_history
            else tr("Undo latest change")
        )
        self.undo_button.setToolTip(undo_text)
        self.shortcut_actions["Ctrl+Z"].setText(undo_text)
        self.slider.setEnabled(seekable)
        self.playback_speed.setEnabled(idle and ready)
        has_players = self.thrower_combo.count() > 1
        self.thrower_combo.setEnabled(idle and has_players)
        for keys in (",", "."):
            self.shortcut_actions[keys].setEnabled(idle and has_players)
        self.export_button.setEnabled(
            idle and ready and self.exportable_count > 0 and self.estimated_duration is not None
        )
        self.preview_button.setEnabled(self.shortcut_actions["P"].isEnabled())
        timeline = self._timeline_items()
        rows = {index.row() for index in self.impact_table.selectedIndexes()}
        self.slider.set_selected_markers(
            {
                ("Impact" if timeline[row][2] is not None else timeline[row][0], timeline[row][1])
                for row in rows
                if row < len(timeline)
            }
        )
        self._refresh_action_guidance(idle, ready, seekable)

    def _refresh_action_guidance(self, idle: bool, ready: bool, seekable: bool) -> None:
        shortcut = (
            self.shortcut_actions["M"].shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        )
        hint = (
            tr("Press {shortcut} or use Mark impact to mark a throw.", shortcut=shortcut)
            if shortcut
            else tr("Use Mark impact to mark a throw.")
        )
        self.empty_highlights.setText(tr("No throws marked yet.") + "\n\n" + hint)
        self.empty_highlights.setVisible(self.impact_table.rowCount() == 0)
        if not idle:
            unavailable = tr("Wait for the export to finish, or cancel it.")
        elif not self.project.video_path:
            unavailable = tr("Choose a video in Match details.")
        elif (
            self.player.error() != QMediaPlayer.Error.NoError
            or self.player.mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia
        ):
            unavailable = tr("The video could not be loaded. Choose another file in Match details.")
        elif not ready:
            unavailable = tr("Wait for the video to finish loading.")
        else:
            unavailable = ""
        preview_reason = unavailable
        if not preview_reason and not seekable:
            preview_reason = tr("This video does not support seeking.")
        if not preview_reason and not self.preview_button.isEnabled():
            preview_reason = tr("Select one throw with a valid clip to preview.")
        export_reason = unavailable
        if not export_reason and not self.export_button.isEnabled():
            if (
                self.project.round_one_end_ms is not None
                and self.project.game_end_ms is not None
                and self.project.round_one_end_ms > self.project.game_end_ms
            ):
                export_reason = tr("Round 1 must end before the game ends.")
            else:
                export_reason = tr(
                    "Mark a throw within the video and check its before/after timing."
                )
        for button, key, reason in (
            (self.preview_button, "P", preview_reason),
            (self.export_button, None, export_reason),
        ):
            text = reason or button.text()
            if key and not reason:
                sequence = (
                    self.shortcut_actions[key]
                    .shortcut()
                    .toString(QKeySequence.SequenceFormat.NativeText)
                )
                if sequence:
                    text += f" ({sequence})"
            button.setToolTip(text)
            button.setAccessibleDescription(reason)
            if key:
                self.shortcut_actions[key].setToolTip(text)
        reasons = []
        if preview_reason:
            reasons.append(tr("Preview: {reason}", reason=preview_reason))
        if export_reason and export_reason != preview_reason:
            reasons.append(tr("Export: {reason}", reason=export_reason))
        self.action_guidance.setText(unavailable or "\n".join(reasons))
        self.action_guidance.setVisible(bool(self.action_guidance.text()))
        for button in (
            self.play_button,
            self.mark_button,
            self.round_end_button,
            self.game_end_button,
        ):
            button.setAccessibleDescription(unavailable)

    def _refresh_export_summary(self) -> None:
        self._update_project_title()
        preview = replace(
            self.project,
            pre_roll_ms=self.project.pre_roll_ms,
            post_roll_ms=self.project.post_roll_ms,
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
        if self.preview_end is not None and position >= self.preview_end:
            end = self.preview_end
            self.stop_preview()
            self.player.setPosition(end)
            position = end
        if not self.slider.isSliderDown():
            self.slider.setValue(position)
        self.position_label.setText(format_timestamp(position))
        self._update_action_states()

    def _duration_changed(self, duration: int) -> None:
        self._restore_position()
        self.slider.setRange(0, duration)
        self.duration_label.setText(format_timestamp(duration))
        self._refresh_export_summary()

    def cycle_thrower(self, direction: int = 1) -> None:
        if self.thrower_combo.count() <= 1:
            return
        current_index = self.thrower_combo.currentIndex()
        next_index = (current_index + direction) % self.thrower_combo.count()
        self.thrower_combo.setCurrentIndex(next_index)

    def _load_form(self) -> None:
        self.thrower_combo.clear()
        self.thrower_combo.addItem("")
        self.thrower_combo.addItems(self.project.throwers)
        if self.pending_resume is not None:
            self.thrower_combo.setCurrentIndex(
                max(0, self.thrower_combo.findText(self.pending_resume[1]))
            )
        self._refresh_impacts()
        if self.project.video_path:
            self._load_video(Path(self.project.video_path))
        else:
            self.player.setSource(QUrl())
            self.video_status.setText(tr("No video selected"))
            self.video_status.setToolTip("")
        self._update_action_states()

    def export_video(self) -> None:
        self.stop_preview()
        if self.render_thread is not None:
            return
        if not self.project.impacts:
            QMessageBox.information(
                self, tr("No impacts"), tr("Mark at least one impact before exporting.")
            )
            return
        missing_markers = []
        for value, label in (
            (self.project.title, "Match title"),
            (self.project.team_one, "Player name" if self.project.solo else "Team 1 name"),
            ("unused" if self.project.solo else self.project.team_two, "Team 2 name"),
        ):
            if not value.strip():
                missing_markers.append(tr(label))
        if self.project.round_one_end_ms is None:
            missing_markers.append(tr("Round 1 end (round-one result screen)"))
        if self.project.game_end_ms is None:
            missing_markers.append(
                tr("End (final result screen)")
                if self.project.solo
                else tr("Game end (final result/winner screen)")
            )
        if missing_markers:
            answer = QMessageBox.question(
                self,
                tr("Missing match information"),
                tr("The following information or markers are missing:\n\n")
                + "\n".join(missing_markers)
                + (
                    tr(
                        "\n\nWithout a title, the title screen uses the player name. If the title, player name and subtitle are empty, it is omitted. Missing end markers omit their result screens.\n\nProceed with export?"
                    )
                    if self.project.solo
                    else tr(
                        "\n\nWithout a title, the title screen uses the supplied team names. If the title, team names and subtitle are empty, it is omitted. Missing end markers omit their result screens.\n\nProceed with export?"
                    )
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        overlaps = overlapping_highlights(self.project, self.player.duration())
        if overlaps:
            details = [
                tr(
                    "{first} / {second}: {seconds} s overlap",
                    first=format_timestamp(first),
                    second=format_timestamp(second),
                    seconds=f"{duration / 1000:g}",
                )
                for first, second, duration in overlaps[:10]
            ]
            if len(overlaps) > 10:
                details.append(tr("…and {count} more overlapping pairs", count=len(overlaps) - 10))
            answer = QMessageBox.question(
                self,
                tr("Overlapping highlights"),
                tr(
                    "Some highlight clips include the same footage, which will be repeated in the export:\n\n"
                )
                + "\n".join(details)
                + tr(
                    "\n\nYou can adjust the before/after timing or individual throw overrides to reduce overlap. Export anyway?"
                ),
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
        snapshot = deepcopy(self.project)
        self.render_thread = RenderThread(snapshot, Path(filename), self.player.duration())
        self._update_action_states()
        self.render_thread.succeeded.connect(self._export_succeeded)
        self.render_thread.failed.connect(self._export_failed)
        self.render_thread.cancelled.connect(self._export_cancelled)
        self.render_thread.finished.connect(self._export_finished)
        self.render_outcome = None
        self.render_dialog = RenderDialog(self)
        self.render_thread.progress_changed.connect(self.render_dialog.update_progress)
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
        self.export_button.setText(tr("Export highlights…"))
        self._update_action_states()
        outcome = self.render_outcome
        self.render_outcome = None
        if outcome is not None:
            kind, message = outcome
            if kind == "success":
                self.toast.notify(tr("Export complete: {path}", path=message), 6000)
            elif kind == "error":
                QMessageBox.critical(self, tr("Export failed"), message)
            else:
                self.toast.notify(tr("Export cancelled"))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.render_thread is not None:
            if self.render_dialog is not None:
                self.render_dialog.reject()
            event.ignore()
            return
        if not self._confirm_replace():
            event.ignore()
            return
        self._remember_position()
        self._clear_recovery()
        self.autosave_timer.stop()
        if self.persistence_started:
            settings = QSettings("KyykkaEditor", "KyykkaEditor")
            settings.setValue("workspace/geometry", self.saveGeometry())
            settings.setValue("workspace/splitter", self.workspace_splitter.saveState())
        super().closeEvent(event)

    def _resume_key(self) -> str | None:
        if self.project_path is None or not self.project.video_path:
            return None
        identity = (
            str(self.project_path.resolve()).casefold()
            + "\n"
            + str(Path(self.project.video_path).resolve()).casefold()
        )
        return "resume/" + hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def _remember_position(self) -> None:
        key = self._resume_key()
        if key is None or self.pending_resume is not None or not self.persistence_started:
            return
        if self.player.source() != QUrl.fromLocalFile(str(Path(self.project.video_path).resolve())):
            return
        QSettings("KyykkaEditor", "KyykkaEditor").setValue(
            key, json.dumps([self.player.position(), self.thrower_combo.currentText()])
        )

    def _read_position(self) -> tuple[int, str] | None:
        key = self._resume_key()
        if key is None:
            return None
        try:
            position, thrower = json.loads(
                QSettings("KyykkaEditor", "KyykkaEditor").value(key, "null")
            )
            if type(position) is int and position >= 0 and isinstance(thrower, str):
                return position, thrower
        except (TypeError, ValueError):
            pass
        return None

    def _restore_position(self) -> None:
        if self.player.source() != QUrl.fromLocalFile(str(Path(self.project.video_path).resolve())):
            return
        if (
            self.pending_resume is None
            or self.player.duration() <= 0
            or not self.player.isSeekable()
        ):
            return
        if self.player.mediaStatus() not in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            return
        position, _ = self.pending_resume
        self.pending_resume = None
        self.player.pause()
        self.player.setPosition(min(position, self.player.duration()))


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
    QTimer.singleShot(0, window.start_session)
    return app.exec()
