# MusicalScumme 2.11.0 implementation report

Date: 2026-07-28

## Outcome

Version 2.11.0 adds an opt-in, explainable mapping-policy layer while preserving the existing source-backed arrangement, physical timing safeguards, key profiles, presets, and default output.

## Mapping and planning changes

- The existing dynamic-programming register planner remains the global look-ahead engine.
- Custom mode now exposes planning priorities for balanced output, register preservation, rhythmic reliability, or minimum bank changes.
- Mapping stability adjusts the cost of changing persistent SCUM octave banks without introducing greedy per-note remapping.
- An optional rolling bank-switch budget limits accepted Ctrl/Shift taps per second. Zero remains unlimited and therefore preserves existing behavior.
- Equivalent C-boundary notes can prefer the lower or upper available bank; Automatic remains the compatibility default.
- Every planned note carries an audit explanation covering transposition, folding, and its target SCUM bank.
- Prepared-plan diagnostics disclose initial bank preparation, budget folding, final bank state, and restoration.
- Optional base-bank restoration runs only after every musical note is released and uses standalone octave-control taps.

## Compatibility and safety

- No source MIDI is rewritten.
- No pitch, harmony, or accompaniment is generated.
- Ctrl and Shift remain standalone persistent-bank controls and never overlap a musical key.
- Optimal Sounding, SCUM Safe, old Custom settings, profile names, input backends, focus requirements, F8, and cleanup semantics are retained.
- New stored fields have legacy-equivalent defaults.

## Validation

- `python -m compileall -q .`: passed.
- `python -m pytest`: 122 passed.
- `ruff check .`: passed.
- Main window, Audio-to-MIDI dialog, and Song Transposer dialog constructed with the offscreen Qt platform through the test suite.
- The Windows onedir package was built with Python 3.12.10, PyInstaller 6.21.0, PySide6 6.11.1, and Mido 1.3.3.
- The packaged executable remained alive through an eight-second isolated offscreen smoke launch and logged `Starting MusicalScumme 2.11.0`.
- All ten required audio/separation installer, worker, validator, and requirements resources were present.
- `musical_scumme.song_processor` is present in the PyInstaller analysis.
- The distributable ZIP passed a complete 240-entry read-through.

## Package

- Folder: `release-staging/2.11.0/MusicalScumme`
- Folder files: 236
- Folder bytes: 120,590,394
- Executable SHA-256: `be3404216655f2c181969f570cc7da5c38bbf9192bdc9416393ba6b85a199e11`
- ZIP: `release-staging/2.11.0/MusicalScumme-2.11.0-Windows.zip`
- ZIP bytes: 49,438,888
- ZIP SHA-256: `62bf07935bf31a8a1cf5e579d73eeede015ec0ffc09f492daaadd9f437c0c618`

## Remaining live limitations

SCUM playback, focus-loss cleanup, Pause/Stop, F8, musical quality, the subjective value of each mapping policy, and final base-bank restoration remain unconfirmed in the current SCUM build until supervised in-game testing. No audio inference logic changed, so representative MP3, WAV, and M4A inference was not rerun.
