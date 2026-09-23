# MusicalScumme 2.2.0 implementation report

## Reason for the update

The user confirmed that audio conversion and SCUM playback work, but the result can sound jittery because SCUM does not reliably accept dense, simultaneous, or rapidly retriggered instrument inputs.

## Implemented controls

The main interface now exposes:

- SCUM Safe, Balanced, Maximum Fidelity, and Custom presets.
- Maximum chord notes.
- Per-note chord stagger.
- Minimum played note.
- Physical retrigger gap.
- Maximum note starts per second.
- Modifier release delay.
- Modifier settle delay.
- Playback speed.

Source micro-note filtering, source retrigger filtering, arrangement mode, note-length ratio, maximum note length, and timing jitter remain available.

## Planner changes

- Chords are rolled melody-first instead of pressing all notes simultaneously.
- Bass follows the lead, then inner harmony is ordered by musical strength.
- Same-key reuse is processed after pitch folding, so octave-equivalent source notes cannot bypass the physical retrigger gap.
- If a safe gap cannot fit, the next note is delayed rather than sending an impossible rapid release/press pair.
- Ctrl/Shift transitions release active note keys, wait the configured release interval, switch the modifier, then wait the settle interval before playing.
- A modifier pre-roll protects the first non-base-octave note.
- Duplicate safety events are canonicalised into one coherent key-state timeline.

## Migration

Settings from 2.1.x have no preset identity. They load as Custom and retain their values. New installations start with Balanced.

## Preserved behaviour

- Current `Y I O P G H J K L B N Q E` profile.
- `Q` for B.
- Correct 64-bit/32-bit SendInput ABI.
- Scan-code default, virtual-key fallback, and dry run.
- F8 emergency stop.
- Foreground protection and focus-loss cleanup.
- Isolated Basic Pitch runtime and repaired validator.
- No injection, game-memory access, game-file editing, or anti-cheat bypass.

## Validation

- 37 automated tests passed.
- Python compilation passed.
- Ruff passed.
- Offscreen Qt construction passed.
- Preset application and automatic Custom switching passed in the Qt UI.
- The test MIDI produced valid plans under all three presets.

The new timing behaviour still requires live comparison in the user's current SCUM build.
