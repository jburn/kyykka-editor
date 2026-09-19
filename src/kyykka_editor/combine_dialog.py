"""Independent video ordering dialog and cancellable background jobs."""

from pathlib import Path
from threading import Event

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .combine import can_stream_copy, combine_videos, inspect_videos
from .dialog_style import dialog_layout, heading
from .i18n import tr
from .render import RenderCancelled, RenderError
from .toast import Toast


class CombineWorker(QThread):
    progress_changed = Signal(int)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.cancel_event = Event()
        self.result = None
        self.error = ""
        self.cancelled = False

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            self.result = self.job(self.cancel_event, self.progress_changed.emit)
        except RenderCancelled:
            self.cancelled = True
        except (RenderError, OSError, ValueError) as error:
            self.error = str(error)


class CombineVideosDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Combine videos…"))
        self.resize(660, 460)
        self.worker = None
        self.progress_dialog = None
        layout = dialog_layout(self)
        layout.addWidget(heading("Game order"))
        hint = QLabel(tr("Add exported match videos and arrange them in game order."))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(hint)
        self.videos = QListWidget()
        self.videos.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.videos.setStyleSheet(
            "QListWidget { border: 1px solid palette(mid); }"
            "QListWidget::item { padding: 8px 10px; }"
        )
        self.empty_label = QLabel(
            tr("No videos added yet.\nUse Add videos… to choose the matches to combine."),
            self.videos.viewport(),
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color: palette(placeholder-text);")
        self.empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        empty_layout = QVBoxLayout(self.videos.viewport())
        empty_layout.addWidget(self.empty_label)
        layout.addWidget(self.videos, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.add_button = QPushButton(tr("Add videos…"))
        self.remove_button = QPushButton(tr("Remove"))
        self.up_button = QPushButton(tr("Move up"))
        self.down_button = QPushButton(tr("Move down"))
        for button in (self.add_button, self.remove_button, self.up_button, self.down_button):
            row.addWidget(button)
        layout.addLayout(row)
        self.add_button.clicked.connect(self._add)
        self.remove_button.clicked.connect(self._remove)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(1))
        self.videos.currentRowChanged.connect(self._update_buttons)
        note = QLabel(
            tr(
                "Compatible videos are joined without re-encoding. Other videos require conversion. Only the first video and audio tracks are included."
            )
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(note)
        self.toast = Toast(self)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.combine_button = buttons.addButton(
            tr("Combine and save…"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.combine_button.setProperty("primary", True)
        self.combine_button.clicked.connect(self._inspect)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_buttons()

    def paths(self):
        return [
            Path(self.videos.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.videos.count())
        ]

    def _add(self):
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            tr("Add videos…"),
            "",
            tr("Video files (*.mp4 *.mov *.mkv *.avi *.m4v);;All files (*)"),
        )
        for filename in filenames:
            item = QListWidgetItem(Path(filename).name)
            item.setData(Qt.ItemDataRole.UserRole, str(Path(filename).resolve()))
            item.setToolTip(str(Path(filename).resolve()))
            self.videos.addItem(item)
        if filenames:
            self.videos.setCurrentRow(self.videos.count() - 1)
        self._update_buttons()

    def _remove(self):
        self.videos.takeItem(self.videos.currentRow())
        self._update_buttons()

    def _move(self, offset):
        row = self.videos.currentRow()
        target = row + offset
        if row >= 0 and 0 <= target < self.videos.count():
            item = self.videos.takeItem(row)
            self.videos.insertItem(target, item)
            self.videos.setCurrentRow(target)
        self._update_buttons()

    def _update_buttons(self):
        for index in range(self.videos.count()):
            item = self.videos.item(index)
            item.setText(f"{index + 1}.  {Path(item.data(Qt.ItemDataRole.UserRole)).name}")
        self.empty_label.setVisible(self.videos.count() == 0)
        idle = self.worker is None
        row = self.videos.currentRow()
        self.add_button.setEnabled(idle)
        self.videos.setEnabled(idle)
        self.remove_button.setEnabled(idle and row >= 0)
        self.up_button.setEnabled(idle and row > 0)
        self.down_button.setEnabled(idle and 0 <= row < self.videos.count() - 1)
        self.combine_button.setEnabled(idle and self.videos.count() >= 2)

    def _start(self, job, activity, finished):
        from .app import RenderDialog

        self.toast.hide()
        self.worker = CombineWorker(job, self)
        self.progress_dialog = RenderDialog(self, title="Combine videos…", activity=activity)
        self.progress_dialog.status.setText(tr(activity))
        self.progress_dialog.cancel_requested.connect(self.worker.cancel)
        self.worker.progress_changed.connect(self.progress_dialog.update_progress)
        self.worker.finished.connect(lambda: self._finished(finished))
        self._update_buttons()
        self.progress_dialog.show()
        self.worker.start()

    def _finished(self, finished):
        worker = self.worker
        self.worker = None
        self.progress_dialog.accept()
        self.progress_dialog.deleteLater()
        self.progress_dialog = None
        self._update_buttons()
        worker.deleteLater()
        if worker.error:
            QMessageBox.critical(self, tr("Combine videos…"), worker.error)
        elif worker.cancelled:
            self.toast.notify(tr("Combining cancelled. No output file was replaced."))
        elif not worker.cancelled:
            finished(worker.result)

    def _inspect(self):
        if self.worker is not None or self.videos.count() < 2:
            return
        paths = self.paths()
        self._start(
            lambda cancel, progress: inspect_videos(paths, cancel),
            "Checking videos…",
            self._inspected,
        )

    def _inspected(self, videos):
        convert = not can_stream_copy(videos)
        if convert:
            first = videos[0]
            answer = QMessageBox.question(
                self,
                tr("Convert videos?"),
                tr(
                    "These videos need conversion to a common format. Convert to {width} × {height} at {fps} fps (H.264, with stereo AAC when audio is present)?\n\nVideos are fitted without cropping. Missing audio becomes silence. Conversion takes longer and may slightly reduce quality.",
                    width=first.width,
                    height=first.height,
                    fps=f"{float(first.rate):g}",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        picker = QFileDialog(self, tr("Save combined video"))
        picker.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        picker.setNameFilter(tr("MP4 video (*.mp4)"))
        picker.setDefaultSuffix("mp4")
        picker.selectFile(str(videos[0].path.parent / "series.mp4"))
        if picker.exec() != QDialog.DialogCode.Accepted:
            return
        output = Path(picker.selectedFiles()[0])

        def job(cancel, progress):
            combine_videos(videos, output, convert=convert, cancel=cancel, progress=progress)
            return str(output)

        self._start(job, "Combining videos…", self._saved)

    def _saved(self, filename):
        self.toast.notify(tr("Saved combined video to:\n{path}", path=filename), 6000)

    def reject(self):
        if self.worker is not None:
            self.progress_dialog.reject()
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker is not None:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
