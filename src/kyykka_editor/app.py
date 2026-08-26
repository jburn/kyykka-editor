from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
# Keep Qt Multimedia developer diagnostics disabled unless a caller explicitly enables them.
os.environ.setdefault("QT_FFMPEG_DEBUG", "0")
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg.*=false")

from PySide6.QtCore import QStandardPaths, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QKeySequence, QMouseEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QStyle,
    QStyleOptionSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .model import EditorProject, default_export_filename, format_timestamp
from .render import RenderError, render_highlights


class SeekSlider(QSlider):
    """Timeline slider that seeks when any point on its track is clicked."""

    seek_requested = Signal(int)

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


class RenderThread(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, project: EditorProject, output: Path, duration_ms: int) -> None:
        super().__init__()
        self.project = project
        self.output = output
        self.duration_ms = duration_ms

    def run(self) -> None:
        try:
            render_highlights(self.project, self.output, self.duration_ms)
        except (RenderError, OSError) as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(str(self.output))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.project = EditorProject()
        self.project_path: Path | None = None
        self.mark_history: list[int] = []
        self.render_thread: RenderThread | None = None
        self.setWindowTitle("Kyykka Editor")
        self.resize(1180, 780)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.video = QVideoWidget()
        self.player.setVideoOutput(self.video)

        self._build_ui()
        self._build_menu()
        self._connect_player()
        self._refresh_impacts()

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QHBoxLayout(root)
        left, right = QVBoxLayout(), QVBoxLayout()

        source_row = QHBoxLayout()
        self.open_video_button = QPushButton("Open video…")
        self.video_status = QLabel("No video selected")
        self.video_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        source_row.addWidget(self.open_video_button)
        source_row.addWidget(self.video_status, 1)
        left.addLayout(source_row)
        left.addWidget(self.video, 1)
        timeline = QHBoxLayout()
        self.position_label = QLabel("00:00:00.000")
        self.slider = SeekSlider(Qt.Orientation.Horizontal)
        self.duration_label = QLabel("00:00:00.000")
        timeline.addWidget(self.position_label)
        timeline.addWidget(self.slider, 1)
        timeline.addWidget(self.duration_label)
        left.addLayout(timeline)

        controls = QHBoxLayout()
        self.back_button = QPushButton("−3 s")
        self.play_button = QPushButton("Play")
        self.forward_button = QPushButton("+5 s")
        self.mark_button = QPushButton("Mark impact")
        self.undo_button = QPushButton("Undo")
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

        form = QFormLayout()
        self.title_edit, self.team_one_edit, self.team_two_edit = (
            QLineEdit(),
            QLineEdit(),
            QLineEdit(),
        )
        self.pre_roll, self.post_roll = QSpinBox(), QSpinBox()
        for spin in (self.pre_roll, self.post_roll):
            spin.setRange(0, 30)
            spin.setSuffix(" s")
        self.pre_roll.setValue(4)
        self.post_roll.setValue(3)
        form.addRow("Title", self.title_edit)
        form.addRow("Team 1", self.team_one_edit)
        form.addRow("Team 2", self.team_two_edit)
        self.score_spins = [QSpinBox() for _ in range(4)]
        for score in self.score_spins:
            score.setRange(-100, 100)
        form.addRow("Round 1 — Team 1", self.score_spins[0])
        form.addRow("Round 1 — Team 2", self.score_spins[1])
        form.addRow("Round 2 — Team 1", self.score_spins[2])
        form.addRow("Round 2 — Team 2", self.score_spins[3])
        form.addRow("Before impact", self.pre_roll)
        form.addRow("After impact", self.post_roll)
        right.addLayout(form)

        event_row = QHBoxLayout()
        self.round_end_button = QPushButton("Mark round 1 end")
        self.game_end_button = QPushButton("Mark game end")
        event_row.addWidget(self.round_end_button)
        event_row.addWidget(self.game_end_button)
        right.addLayout(event_row)
        right.addWidget(QLabel("Timeline events"))
        self.impact_table = QTableWidget(0, 3)
        self.impact_table.setHorizontalHeaderLabels(["#", "Event", "Timestamp"])
        self.impact_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.impact_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.impact_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        right.addWidget(self.impact_table, 1)
        self.remove_button = QPushButton("Remove selected")
        self.export_button = QPushButton("Export highlights…")
        self.export_progress = QProgressBar()
        self.export_progress.setRange(0, 0)
        self.export_progress.setTextVisible(False)
        self.export_progress.setToolTip("FFmpeg is rendering the highlight video")
        self.export_progress.hide()
        self.export_status = QLabel()
        self.export_status.hide()
        right.addWidget(self.remove_button)
        right.addWidget(self.export_button)
        right.addWidget(self.export_progress)
        right.addWidget(self.export_status)

        outer.addLayout(left, 3)
        outer.addLayout(right, 1)
        self.setCentralWidget(root)

        self.play_button.clicked.connect(self.toggle_playback)
        self.open_video_button.clicked.connect(self.open_video)
        self.back_button.clicked.connect(lambda: self.seek_relative(-3_000))
        self.forward_button.clicked.connect(lambda: self.seek_relative(5_000))
        self.mark_button.clicked.connect(self.mark_impact)
        self.undo_button.clicked.connect(self.undo_impact)
        self.remove_button.clicked.connect(self.remove_selected)
        self.export_button.clicked.connect(self.export_video)
        self.round_end_button.clicked.connect(self.mark_round_end)
        self.game_end_button.clicked.connect(self.mark_game_end)
        self.slider.sliderMoved.connect(self.player.setPosition)
        self.slider.seek_requested.connect(self.player.setPosition)
        self.impact_table.cellDoubleClicked.connect(self._seek_to_row)

        for keys, callback in (
            ("Space", self.toggle_playback),
            ("M", self.mark_impact),
            ("Ctrl+Z", self.undo_impact),
            ("Left", lambda: self.seek_relative(-3_000)),
            ("Right", lambda: self.seek_relative(5_000)),
            ("Delete", self.remove_selected),
            ("Ctrl+R", self.mark_round_end),
            ("Ctrl+G", self.mark_game_end),
        ):
            self._add_shortcut(keys, callback)

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")
        for text, shortcut, callback in (
            ("Open video…", "Ctrl+O", self.open_video),
            ("Open project…", "Ctrl+Shift+O", self.open_project),
            ("Save project", "Ctrl+S", self.save_project),
            ("Save project as…", "Ctrl+Shift+S", self.save_project_as),
        ):
            action = QAction(text, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)

    def _add_shortcut(self, keys: str, callback: Callable[[], None]) -> None:
        action = QAction(self)
        action.setShortcut(QKeySequence(keys))
        action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        action.triggered.connect(callback)
        self.addAction(action)

    def _connect_player(self) -> None:
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.mediaStatusChanged.connect(self._media_status_changed)
        self.player.playbackStateChanged.connect(
            lambda state: self.play_button.setText(
                "Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "Play"
            )
        )
        self.player.errorOccurred.connect(self._playback_error)

    def open_video(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open video", "", "Video files (*.mp4 *.mov *.mkv *.avi *.m4v);;All files (*)"
        )
        if filename:
            self._load_video(Path(filename))

    def _load_video(self, path: Path) -> None:
        path = path.resolve()
        if not path.is_file():
            QMessageBox.warning(self, "Video not found", f"The video file does not exist:\n{path}")
            return
        self.player.stop()
        self.project.video_path = str(path)
        self.video_status.setText(f"Loading {path.name}…")
        self.video_status.setToolTip(str(path))
        self.open_video_button.setEnabled(False)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()
        self.setWindowTitle(f"Kyykka Editor — {path.name}")

    def _media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            name = Path(self.project.video_path).name
            self.video_status.setText(f"Loaded: {name}")
            self.open_video_button.setEnabled(True)
        elif status == QMediaPlayer.MediaStatus.BufferedMedia:
            self.video_status.setText(f"Playing: {Path(self.project.video_path).name}")
            self.open_video_button.setEnabled(True)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.video_status.setText(f"Loaded: {Path(self.project.video_path).name}")
            self.open_video_button.setEnabled(True)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.video_status.setText("Could not load video")
            self.open_video_button.setEnabled(True)

    def _playback_error(self, _error: QMediaPlayer.Error, message: str) -> None:
        self.video_status.setText("Could not load video")
        self.open_video_button.setEnabled(True)
        detail = message or "Qt could not decode this video file."
        QMessageBox.warning(self, "Playback error", f"{detail}\n\nFile: {self.project.video_path}")

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
            QMessageBox.information(self, "No video", "Open a video before marking impacts.")
            return
        self.project.add_impact(self.player.position())
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

    def remove_selected(self) -> None:
        timeline = self._timeline_items()
        rows = sorted({index.row() for index in self.impact_table.selectedIndexes()})
        impact_indices: list[int] = []
        for row in rows:
            kind, _timestamp, source_index = timeline[row]
            if kind == "Impact" and source_index is not None:
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
            QMessageBox.information(self, "No video", "Open a video before marking events.")
            return
        self.project.round_one_end_ms = self.player.position()
        self._refresh_impacts()

    def mark_game_end(self) -> None:
        if not self.project.video_path:
            QMessageBox.information(self, "No video", "Open a video before marking events.")
            return
        self.project.game_end_ms = self.player.position()
        self._refresh_impacts()

    def _seek_to_row(self, row: int, _column: int) -> None:
        self.player.setPosition(self._timeline_items()[row][1])

    def _timeline_items(self) -> list[tuple[str, int, int | None]]:
        items = [
            ("Impact", impact.timestamp_ms, index)
            for index, impact in enumerate(self.project.impacts)
        ]
        if self.project.round_one_end_ms is not None:
            items.append(("Round 1 end", self.project.round_one_end_ms, None))
        if self.project.game_end_ms is not None:
            items.append(("Game end", self.project.game_end_ms, None))
        return sorted(items, key=lambda item: (item[1], item[0]))

    def _refresh_impacts(self) -> None:
        timeline = self._timeline_items()
        self.impact_table.setRowCount(len(timeline))
        for row, (kind, timestamp, _source_index) in enumerate(timeline):
            self.impact_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.impact_table.setItem(row, 1, QTableWidgetItem(kind))
            self.impact_table.setItem(row, 2, QTableWidgetItem(format_timestamp(timestamp)))
        self.undo_button.setEnabled(bool(self.mark_history))

    def _position_changed(self, position: int) -> None:
        if not self.slider.isSliderDown():
            self.slider.setValue(position)
        self.position_label.setText(format_timestamp(position))

    def _duration_changed(self, duration: int) -> None:
        self.slider.setRange(0, duration)
        self.duration_label.setText(format_timestamp(duration))

    def _sync_form(self) -> None:
        self.project.title = self.title_edit.text().strip()
        self.project.team_one = self.team_one_edit.text().strip()
        self.project.team_two = self.team_two_edit.text().strip()
        (
            self.project.team_one_round_one_score,
            self.project.team_two_round_one_score,
            self.project.team_one_round_two_score,
            self.project.team_two_round_two_score,
        ) = (score.value() for score in self.score_spins)
        self.project.pre_roll_ms = self.pre_roll.value() * 1_000
        self.project.post_roll_ms = self.post_roll.value() * 1_000

    def _load_form(self) -> None:
        self.title_edit.setText(self.project.title)
        self.team_one_edit.setText(self.project.team_one)
        self.team_two_edit.setText(self.project.team_two)
        for score, value in zip(
            self.score_spins,
            (
                self.project.team_one_round_one_score,
                self.project.team_two_round_one_score,
                self.project.team_one_round_two_score,
                self.project.team_two_round_two_score,
            ),
            strict=True,
        ):
            score.setValue(value)
        self.pre_roll.setValue(self.project.pre_roll_ms // 1_000)
        self.post_roll.setValue(self.project.post_roll_ms // 1_000)
        self._refresh_impacts()
        if self.project.video_path:
            self._load_video(Path(self.project.video_path))

    def open_project(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", "Kyykka project (*.json)"
        )
        if not filename:
            return
        try:
            self.project = EditorProject.load(Path(filename))
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Cannot open project", str(error))
            return
        self.project_path = Path(filename)
        self.mark_history.clear()
        self._load_form()

    def save_project(self) -> None:
        if self.project_path is None:
            self.save_project_as()
            return
        self._sync_form()
        try:
            self.project.save(self.project_path)
        except OSError as error:
            QMessageBox.critical(self, "Cannot save project", str(error))

    def save_project_as(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save project", "match.json", "Kyykka project (*.json)"
        )
        if filename:
            self.project_path = Path(filename)
            self.save_project()

    def export_video(self) -> None:
        self._sync_form()
        if not self.project.impacts:
            QMessageBox.information(
                self, "No impacts", "Mark at least one impact before exporting."
            )
            return
        default_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.MoviesLocation
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export highlights",
            str(Path(default_dir) / default_export_filename(self.project)),
            "MP4 video (*.mp4)",
        )
        if not filename:
            return
        self.export_button.setEnabled(False)
        self.export_button.setText("Rendering…")
        self.export_progress.show()
        self.export_status.setText("Rendering video. This can take several minutes…")
        self.export_status.show()
        self.statusBar().showMessage("Rendering highlights…")
        snapshot = EditorProject.from_json(self.project.to_json())
        self.render_thread = RenderThread(snapshot, Path(filename), self.player.duration())
        self.render_thread.succeeded.connect(self._export_succeeded)
        self.render_thread.failed.connect(self._export_failed)
        self.render_thread.finished.connect(self._export_finished)
        self.render_thread.start()

    def _export_succeeded(self, filename: str) -> None:
        self.statusBar().showMessage("Export complete", 5_000)
        QMessageBox.information(self, "Export complete", f"Saved highlights to:\n{filename}")

    def _export_failed(self, message: str) -> None:
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "Export failed", message)

    def _export_finished(self) -> None:
        self.export_button.setEnabled(True)
        self.export_button.setText("Export highlights…")
        self.export_progress.hide()
        self.export_status.hide()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Kyykka Editor")
    window = MainWindow()
    window.show()
    return app.exec()
