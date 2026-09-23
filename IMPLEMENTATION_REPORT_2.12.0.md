# MusicalScumme 2.12.0 implementation report

Date: 2026-07-30

## Outcome

Version 2.12.0 rebuilds the Qt interface as a translucent electric-cyan in-game HUD while preserving the complete MIDI, arrangement, planning, input, scheduler, audio, settings, and safety behavior.

## Pre-release improvement scan

- Reduced persistent surface and card fills to low-opacity charcoal glass so the game remains visible through the interface.
- Corrected a Windows-specific translucency risk: Qt top-level alpha now uses `FramelessWindowHint` together with `WA_TranslucentBackground`.
- Added compact line-icon minimize, maximize/restore, and close controls.
- Delegated dragging and all eight edge/corner resize zones to Qt's native Windows system-move/system-resize APIs.
- Extended the translucent chrome to the custom-key, Audio-to-MIDI, and Song Transposer dialogs.
- Bumped the release identity from 2.11.0 to 2.12.0 rather than replacing the existing validated package.
- Replaced the initial PowerShell ZIP because it stored Windows backslashes; the final archive uses portable forward-slash paths.

## Compatibility and safety

- No playback, MIDI parsing, arrangement, planning, input mapping, scheduler, or audio inference policy changed.
- No source MIDI is rewritten.
- Foreground focus protection, serialized cleanup, Pause, Stop, F8, and playback-time control locks remain intact.
- The maintained 1080×720 layout retains both panes and has no settings horizontal scrollbar.
- Song Transposer and Audio-to-MIDI remain in the File menu.

## Validation

- `python -m compileall -q .`: passed.
- `python -m pytest`: 123 passed.
- `ruff check .`: passed.
- Main window, Keymap dialog, Audio-to-MIDI dialog, and Song Transposer dialog construct with the offscreen Qt platform.
- Resize coverage checks every edge/corner mask and diagonal cursor.
- A native Windows compositing probe rendered the HUD over a high-contrast magenta window and confirmed the background remained visible through the live top-level surface.
- The Windows onedir package was built with Python 3.12.10, PyInstaller 6.21.0, PySide6 6.11.1, and Mido 1.3.3.
- The packaged executable remained alive through an eight-second isolated offscreen smoke launch and logged `Starting MusicalScumme 2.12.0`.
- All ten required audio/separation installer, worker, validator, and requirements resources are present.
- Recursive PyInstaller inspection confirmed the UI, MIDI engine, arranger, planner, scheduler, song processor, and audio tools modules.
- The distributable ZIP passed a complete 236-entry read-through with one `MusicalScumme/` root and no backslash paths.

## Package

- Folder: `release-staging/2.12.0/MusicalScumme`
- Folder files: 236
- Folder bytes: 120,596,122
- Executable SHA-256: `fc576c0c2c9a5d8767426b735c35eb0858f1b5437e0e4652a776f17d13040b0e`
- ZIP: `release-staging/2.12.0/MusicalScumme-2.12.0-Windows.zip`
- ZIP entries: 236
- ZIP bytes: 49,443,168
- ZIP SHA-256: `b4ca7fa2c241271f80602464ae9a3ebe7f8aa09e22d91a02a2e3bb18c7df8453`

## Remaining live limitations

SCUM playback, focus-loss cleanup, Pause/Stop, F8, scheduler timing, and musical quality remain unconfirmed in the current SCUM build until supervised in-game testing. No audio inference logic changed, so representative MP3, WAV, and M4A inference was not rerun.

The executable is not Authenticode-signed and retains PyInstaller's default icon/version-resource behavior. Signing, branded iconography, deterministic build-tool pinning, and package/checksum automation remain possible packaging improvements rather than defects in this release.
