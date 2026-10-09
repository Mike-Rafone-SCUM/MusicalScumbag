"""Compact, non-interactive karaoke presentation for the playback HUD."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QTextCharFormat, QTextLayout, QTextOption
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from .lyrics import KaraokeFrame


class KaraokeLine(QLabel):
    def __init__(self):
        super().__init__()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAccessibleName("Current karaoke line")
        self.setMinimumHeight(112)
        self.setMaximumHeight(112)
        self.highlight = 0.0
        self._layout_key = None
        self._text_layout = None
        self.line_count = 0

    def set_highlight(self, value: float) -> None:
        if self.highlight != value:
            self.highlight = value
            self.update()

    def paintEvent(self, event) -> None:
        width = max(1, self.width() - 24)
        key = (self.text(), width, self.height())
        if key != self._layout_key:
            for pixels in range(28, 12, -1):
                font = QFont("Segoe UI")
                font.setPixelSize(pixels)
                font.setWeight(QFont.Weight.DemiBold)
                layout = QTextLayout(self.text(), font)
                option = QTextOption(Qt.AlignmentFlag.AlignHCenter)
                option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
                layout.setTextOption(option)
                layout.beginLayout()
                y = 0.0
                count = 0
                while True:
                    line = layout.createLine()
                    if not line.isValid():
                        break
                    line.setLineWidth(width)
                    line.setPosition(QPointF(0, y))
                    y += line.height() + 3
                    count += 1
                layout.endLayout()
                if y <= self.height() - 8:
                    break
            self._layout_key = key
            self._text_layout = layout
            self._layout_height = y
            self.line_count = count
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setPen(QColor("#e8efec"))
        selection = QTextLayout.FormatRange()
        selection.start = 0
        # Qt offsets are UTF-16 code units; Python string indices are code points.
        selection.length = len(self.text()[:max(0, int(self.highlight))].encode("utf-16-le")) // 2
        selection.format = QTextCharFormat()
        selection.format.setForeground(QColor("#63f0be"))
        self._text_layout.draw(painter, QPointF(12, max(4, (self.height() - self._layout_height) / 2)),
                               [selection])
        painter.end()


class KaraokeView(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("karaokeView")
        self.setStyleSheet("QFrame#karaokeView { background: #131c1c; border: 1px solid #30443e; border-radius: 10px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(5)
        top = QHBoxLayout()
        self.mode = QLabel("KARAOKE")
        self.mode.setStyleSheet("color: #8dada4; font-size: 10px; font-weight: 600; letter-spacing: 2px;")
        self.countdown = QLabel()
        self.countdown.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.countdown.setStyleSheet("color: #63f0be; font-size: 11px;")
        top.addWidget(self.mode)
        top.addStretch()
        top.addWidget(self.countdown)
        layout.addLayout(top)
        self.previous = self._label("#61766f", 12, 22)
        self.current = KaraokeLine()
        self.upcoming = self._label("#b4c8c1", 16, 48)
        self.following = self._label("#71887e", 13, 38)
        for widget in (self.previous, self.current, self.upcoming, self.following):
            layout.addWidget(widget)
        self.line_progress = QProgressBar()
        self.line_progress.setRange(0, 1000)
        self.line_progress.setTextVisible(False)
        self.line_progress.setFixedHeight(3)
        self.line_progress.setAccessibleName("Current lyric line progress")
        self.line_progress.setStyleSheet("QProgressBar { border: 0; background: #24352f; } "
                                        "QProgressBar::chunk { background: #63f0be; }")
        layout.addWidget(self.line_progress)
        self.setToolTip("Line sync estimates the highlight between line timestamps. Word sync uses supplied timings.")

    @staticmethod
    def _label(color: str, size: int, height: int) -> QLabel:
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedHeight(height)
        label.setStyleSheet(f"color: {color}; font-size: {size}px; border: none; background: transparent;")
        return label

    def show_frame(self, frame: KaraokeFrame, message: str = "") -> None:
        self.previous.setText(frame.previous)
        self.current.setText(frame.current or message or "Instrumental")
        self.current.set_highlight(frame.highlight if frame.current else 0)
        self.upcoming.setText(frame.upcoming)
        self.following.setText(frame.following)
        self.line_progress.setValue(round(frame.progress * 1000))
        self.mode.setText("KARAOKE  /  WORD SYNC" if frame.timed_words else "KARAOKE  /  LINE SYNC")
        self.countdown.setText(f"IN {math.ceil(frame.countdown_ms / 1000)}s" if frame.countdown_ms > 0 else "")
