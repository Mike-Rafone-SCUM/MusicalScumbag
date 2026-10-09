"""User-selected timed lyric lookup; network work never touches Qt widgets."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .auto_lyrics import filename_metadata
from .lyric_sources import MAX_LYRIC_BYTES, LyricChoice, parse_lrc, search_lyrics


class _SearchSignals(QObject):
    completed = Signal(object, str)


def _search_worker(signals: _SearchSignals, title: str, artist: str) -> None:
    try:
        signals.completed.emit(search_lyrics(title, artist), "")
    except Exception as exc:
        signals.completed.emit([], f"Search failed: {exc}. Try again or load an LRC file.")


class LyricsDialog(QDialog):
    def __init__(self, midi: Path, saved: tuple[str, float, str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find lyrics")
        self.resize(650, 570)
        self.selected_lrc = saved[0] if saved else ""
        self.selected_source = saved[2] if saved else ""
        self.choices: list[LyricChoice] = []
        self.signals = _SearchSignals()
        self.signals.completed.connect(self._search_finished)
        layout = QVBoxLayout(self)
        info = QLabel("Search LRCLIB for timed lyrics or load an .lrc file. Only title and artist are sent online.")
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QFormLayout()
        title, artist = filename_metadata(midi)
        self.title_edit = QLineEdit(title)
        self.artist_edit = QLineEdit(artist)
        self.title_edit.setAccessibleName("Song title for lyric search")
        self.artist_edit.setAccessibleName("Artist for lyric search")
        form.addRow("Song title", self.title_edit)
        form.addRow("Artist", self.artist_edit)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.search_button = QPushButton("Search online")
        self.load_button = QPushButton("Load .lrc file")
        row.addWidget(self.search_button)
        row.addWidget(self.load_button)
        layout.addLayout(row)
        self.status = QLabel("Choose a matching recording. MIDI arrangements may need a timing adjustment.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.results = QListWidget()
        self.results.setAccessibleName("Timed lyric search results")
        self.results.setMaximumHeight(130)
        layout.addWidget(self.results)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Selected lyrics preview")
        layout.addWidget(self.preview, 1)
        timing = QFormLayout()
        self.offset = QDoubleSpinBox()
        self.offset.setRange(-600, 600)
        self.offset.setDecimals(2)
        self.offset.setSingleStep(0.5)
        self.offset.setSuffix(" s")
        self.offset.setValue(saved[1] / 1000 if saved else 0)
        self.offset.setToolTip("Positive values show lyrics later; negative values show them earlier, before playback speed.")
        timing.addRow("Timing adjustment (+ = later)", self.offset)
        layout.addLayout(timing)
        note = QLabel("Lyrics are saved for this MIDI in the app's data folder. Different song structures may not sync.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.use_button = self.buttons.addButton("Use lyrics", QDialogButtonBox.ButtonRole.AcceptRole)
        self.use_button.setEnabled(bool(self.selected_lrc))
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.search_button.clicked.connect(self._search)
        self.load_button.clicked.connect(self._load)
        self.results.currentRowChanged.connect(self._select)
        self.preview.setPlainText(self.selected_lrc)

    def _search(self) -> None:
        if not self.title_edit.text().strip():
            self.status.setText("Enter a song title first.")
            return
        self.search_button.setEnabled(False)
        self.load_button.setEnabled(False)
        self.use_button.setEnabled(False)
        self.status.setText("Searching LRCLIB...")
        self.results.clear()
        self.choices = []
        # The worker owns only immutable inputs and a signal carrier, never this dialog.
        threading.Thread(target=_search_worker, args=(self.signals, self.title_edit.text(),
                         self.artist_edit.text()), daemon=True).start()

    def _search_finished(self, choices: list[LyricChoice], error: str) -> None:
        self.search_button.setEnabled(True)
        self.load_button.setEnabled(True)
        self.use_button.setEnabled(bool(self.selected_lrc))
        self.choices = choices
        self.status.setText(error or ("Select the correct recording below." if choices else
                                     "No timed lyrics found. Check the title/artist or load an .lrc file."))
        for choice in choices:
            self.results.addItem(f"{choice.artist} - {choice.title} | {choice.album} | {choice.duration:.0f} s")

    def _select(self, row: int) -> None:
        if not 0 <= row < len(self.choices):
            return
        choice = self.choices[row]
        self.selected_lrc = choice.lrc
        self.selected_source = f"LRCLIB: {choice.artist} - {choice.title} ({choice.album})"
        self.offset.setValue(0)
        self.preview.setPlainText(choice.lrc)
        self.use_button.setEnabled(True)

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load timed lyrics", "", "Timed lyrics (*.lrc)")
        if path:
            self.load_path(Path(path))

    def load_path(self, path: Path) -> None:
        try:
            if path.stat().st_size > MAX_LYRIC_BYTES:
                raise ValueError("This file is too large.")
            text = path.read_text(encoding="utf-8-sig")
            if not parse_lrc(text):
                raise ValueError("No valid [mm:ss.xx] lyric timestamps found.")
        except (OSError, ValueError) as exc:
            self.status.setText(f"Could not load lyrics: {exc}")
            return
        self.selected_lrc = text
        self.selected_source = path.name
        self.offset.setValue(0)
        self.preview.setPlainText(text)
        self.use_button.setEnabled(True)
        self.status.setText(f"Loaded {path.name}. Choose Use lyrics to save for this MIDI.")
