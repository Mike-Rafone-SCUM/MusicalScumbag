"""Collect native desktop rendering without unused PDF/QML plugin stacks.

MusicalScumme uses QWidget and the Windows keyboard, not Qt's embedded virtual
keyboard or PDF image decoding. Keep all other upstream Qt plugins, translations,
and graphics fallbacks so rendering and native input behaviour stay intact.
"""
from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [
    entry for entry in binaries
    if Path(entry[0]).name.lower() not in {"qtvirtualkeyboardplugin.dll", "qpdf.dll", "qtuiotouchplugin.dll"}
]
