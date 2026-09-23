"""Number editors that allow a complete replacement before committing settings."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QDoubleSpinBox as QtDoubleSpinBox
from PySide6.QtWidgets import QSpinBox as QtSpinBox


class _NumberEditing:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setKeyboardTracking(False)
        self._select_after_click = False
        self.lineEdit().installEventFilter(self)

    def focusInEvent(self, event):
        self._select_after_click = event.reason() == Qt.FocusReason.MouseFocusReason
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._select_after_click = False
        super().focusOutEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.lineEdit():
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._select_after_click = self._select_after_click or not self.hasFocus()
            elif event.type() == QEvent.Type.MouseButtonRelease and self._select_after_click:
                self._select_after_click = False
                self.selectAll()
                return True
        return super().eventFilter(watched, event)

    def wheelEvent(self, event):
        # Settings panels are scrollable. Do not silently change a number just
        # because the pointer happens to be over it while the user scrolls.
        # A deliberate click/focus still enables normal wheel adjustment.
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class QSpinBox(_NumberEditing, QtSpinBox):
    pass


class QDoubleSpinBox(_NumberEditing, QtDoubleSpinBox):
    pass
