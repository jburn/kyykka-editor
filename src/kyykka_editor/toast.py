"""Transient notifications floating above a window's content."""

from PySide6.QtCore import QEvent, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(
            "background: #30343b; color: #f5f5f5; border-radius: 10px; padding: 14px 22px;"
        )
        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.fade = QPropertyAnimation(self.opacity, b"opacity", self)
        self.fade.setDuration(300)
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.fade.finished.connect(self.hide)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade.start)
        parent.installEventFilter(self)
        self.hide()

    def _position(self):
        parent = self.parentWidget()
        self.setMaximumWidth(max(1, parent.width() - 32))
        self.adjustSize()
        self.move(
            max(0, (parent.width() - self.width()) // 2),
            max(0, parent.height() - self.height() - 24),
        )

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self._position()
        return super().eventFilter(watched, event)

    def notify(self, message, duration=3000):
        self.timer.stop()
        self.fade.stop()
        self.opacity.setOpacity(1.0)
        self.setText(message)
        self._position()
        self.show()
        self.raise_()
        self.timer.start(duration)
