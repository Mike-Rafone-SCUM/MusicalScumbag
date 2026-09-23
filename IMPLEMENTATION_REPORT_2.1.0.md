# MusicalScumme 2.1.0 implementation report

## Objective

Make MIDI playback sound intentional inside SCUM's constrained 13-key instrument system, add optional audio-to-MIDI conversion, and keep the game-input path safe and maintainable.

## Implemented

### Intelligent arranger

A new deterministic arrangement stage runs before SCUM key planning. It analyses track monophony, pitch range, duration, velocity, note continuity, bass separation, and interval diversity. It retains a lead voice, useful bass, and selected harmony rather than simply taking the loudest notes at each timestamp.

It also filters channel-10 percussion, tiny source notes, near-duplicate retriggers, and excessive rolling note density. Every simplification is counted and exposed to the UI.

Three modes are available:

- **Game-optimised** — lead, bass, selected harmony, and reliability controls.
- **Lead melody only** — one lead note per onset.
- **Faithful / legacy** — bypasses intelligent density and retrigger filtering for clean hand-authored MIDI.

### Global octave planning

The three-octave option now uses dynamic programming across the sequence of onset groups. It balances pitch error against modifier-switch cost, reducing needless Left Ctrl/Left Shift changes. Safety releases still occur before any octave-state transition.

### Expressive articulation

MIDI velocity slightly adjusts key hold duration. This does not claim to provide velocity-sensitive volume in SCUM; it provides controlled articulation while respecting minimum and maximum hold limits.

### Audio-to-MIDI

The UI can convert MP3, OGG, WAV, FLAC, or M4A into MIDI through Spotify Basic Pitch. The machine-learning runtime is optional and isolated under `%LOCALAPPDATA%\MusicalScumme\audio-runtime` so it cannot destabilise normal MIDI playback.

The worker runs out of process, reports newline-delimited JSON progress, cleans invalid/overlapping note events, merges near-adjacent same-pitch notes, removes unsupported pitch-bend data, and writes the result atomically.

### UI and operations

- Audio conversion dialog with runtime installation, tuning, logging, cancellation, and automatic loading of completed MIDI.
- Musical-track auto-selection and percussion labels.
- Arrangement, density, retrigger, short-note, expression, polyphony, and pitch-mapping controls.
- Asynchronous process handling; no blocking process waits on the Qt GUI thread.
- Existing F8 stop, SCUM focus protection, safe key release, custom profiles, dry-run mode, CSV export, and settings backups retained.

## Source-of-truth bindings preserved

```text
C     Y
C#    I
D     O
D#    P
E     G
F     H
F#    J
G     K
G#    L
A     B
A#    N
B     Q
C2    E

Octave down   Left Ctrl
Octave up     Left Shift
```

## Validation

- Python compilation passed.
- 19 automated tests passed.
- Ruff lint passed.
- Main window and audio dialog constructed offscreen.
- Win32 `INPUT` ABI regression remains covered.
- Core dependency versions are pinned to the tested set.

Live Windows `SendInput`, current-build SCUM playback, Windows PyInstaller output, and real Basic Pitch inference require validation on the user's Windows/SCUM installation.
