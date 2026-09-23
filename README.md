# MusicalScumbag 3.9.0

MusicalScumbag converts MIDI and user-selected audio into a deterministic, auditable SCUM instrument score, and can route a user-played MIDI keyboard to a SCUM instrument in real time. It sends ordinary supervised keyboard input only while SCUM is in the foreground. It does not inject into the game, read game memory, automate gameplay, or edit game files.

The primary workflow uses the untouched `.mid` or `.midi` file downloaded from MIDI Find or another score source. Song Transposer and Audio → MIDI remain optional conversion tools; they are not required for ordinary MIDI playback, and MusicalScumbag never rewrites the imported source file.

## Conversion and playback pipeline

From the moment a MIDI is imported, MusicalScumme now runs one coherent pipeline:

1. **Strict MIDI parse** — tempo changes, sustain, overlapping notes, track names, channels, velocities, and durations are preserved. The only recovery path clips illegal MIDI data bytes when Mido reports that exact error; unrelated corruption remains fatal.
2. **Relationship-aware track analysis** — each populated track is scored as a lead candidate, chord/support track, bass, percussion, or noise/effect using token-safe names, register, activity, coverage, monophony, continuity, and real chord attacks. Exact doubled parts are rejected instead of wasting SCUM polyphony.
3. **Musical selection** — the importer chooses a primary lead, useful sectional solo handoff, bass, and harmonic support by measuring shared attacks, exclusivity, time coverage, register separation, continuity, and duplication instead of ranking tracks in isolation. Remembered user choices remain authoritative.
4. **Source-texture and phrase analysis** — the selected score is classified as single-line melody, light polyphony, chord-led, or dense polyphony using attack and sounding polyphony, exact and rolled source chords, separate musical-onset and physical-note rates, rhythmic variation, phrase boundaries, durations, track count, and pitch span.
5. **Whole-phrase voice intelligence** — a deterministic dynamic program traces one source-backed lead through the complete score. It rewards coherent contour and track continuity, resists loud/high transient theft, and relaxes continuity only at detected phrase boundaries so real register resets survive.
6. **Dynamic Solo Director** — rolling source-time evidence identifies sustained alternate-lead sections even when the primary lead remains active. The solo reserves voice one, competing upper accompaniment is ducked, and only one lower foundation voice may remain.
7. **Source-backed voicing** — bass and harmony retention considers the active lead, prior support voices, consonance, compactness, duration, velocity, and register role. It can discard source notes but never invent a pitch or chord tone.
8. **Optimal Sounding policy** — arrangement, chord recognition, mapping, polyphony, filtering, landmark-aware run reduction, pulse-relative chord roll, note holds, key gaps, density, and octave-bank timing are derived from that score. Playback speed and transpose remain explicit.
9. **SCUM score planning** — real notes are mapped to the 13-key chromatic bank. Accompaniment uses Enhanced Fold while protected solos receive enhanced section-specific pitch fitting and contour banking. Ctrl/Shift octave-bank taps remain standalone and never overlap a musical key.
10. **Guided command deck** — a persistent Load → Review → Prepare → Play rail shows the current prerequisite, selected-track count, plan readiness, dry-run state, and safest next action.
11. **Supervised playback or export** — prepare the result, inspect selectable bullet advisories, export the musical SCUM score or low-level key events, then start playback manually.

The analyser never guesses a key signature, quantises notes to a scale, generates harmony, borrows support notes into Lead melody, or rewrites the source MIDI.

## Optimal Sounding

Optimal Sounding is the product default. Version 3.1 adds section-local solo handoffs to the whole-phrase source-backed trace. It records protected sections, handoffs, ducked accompaniment, retained run landmarks, suppressed stagger, and exact/folded solo mapping alongside the existing phrase and load diagnostics.

| Source character | Arrangement | Mapping | Chord notes | Main behaviour |
|---|---|---:|---:|---|
| Single-line melody | Lead melody | Enhanced Pitch Match | 1 | Preserves contour and fits the complete line into the three-bank register |
| Light accompaniment | Game-optimised | Enhanced Fold | 2 | Keeps the lead plus restrained real support |
| Chord-led | Game-optimised | Enhanced Fold | 3 | Recognises exact and clearly rolled sustained source chords |
| Dense polyphony | Game-optimised | Enhanced Fold | 2 | Reduces collision-heavy passages and caps start density |
| Protected solo section | Solo Focus | Solo-adaptive | 1 + foundation | Fits the solo's register, suppresses stagger, and ducks competing upper voices |

Thresholds are bounded by SCUM reliability limits. The actual effective policy is recorded in every playback plan's diagnostics and summarised in the UI.

**SCUM Safe** remains as the deliberately conservative fallback. **Custom** reveals the full manual arrangement, mapping, filter, chord, and physical-timing controls. Obsolete Guitar Smooth, Balanced, and Maximum Fidelity settings migrate to Optimal Sounding. Custom timing values remain unchanged; retired mapping names migrate to their enhanced equivalents.

## Enhanced pitch mappings

Version 3.3 retains only Enhanced Fold, Enhanced Strict, Enhanced Intelligent,
Enhanced Contour, and Enhanced Pitch Match for file playback. Saved base-mode
names are read only for migration; the old planning implementations are removed.
Inline guidance explains each mode's range, folding, omissions, and bank taps.
The separately supervised live MIDI input keeps its fixed-bank policies because
it cannot use the file planner's look-ahead or automatic octave transitions.

Resource optimisation reuses identical phrase analysis, retains only the current
dynamic-programming score row, releases replaced analysis buffers, and avoids
redundant note copies. Musical decisions and physical timing are regression-checked
against the preceding enhanced implementations. Packaging omits unused Qt PDF
decoding and embedded virtual-keyboard stacks while preserving native Windows
input, translations, image support, and rendering fallbacks.

## Instrument-aware preparation

Choose the SCUM target instrument before preparing a plan:

| Instrument | Maximum played sustain | Preparation character |
|---|---:|---|
| Guitar | 2,000 ms | Connected melody with a firm two-second decay ceiling |
| Harmonica | 4,000 ms | Longer breath-like phrases |
| Banjo | 1,000 ms | Short, percussive articulation |

Optimal Sounding uses the selected ceiling while deriving note lengths from the score. Final planning enforces it again as a wall-clock limit after playback speed and velocity expression, so slow playback or conflicting Custom timing cannot over-sustain the instrument. Preparation changes note releases only: attacks and pitches remain source-backed. The prepared-plan summary reports how many long notes were shortened.

## Current SCUM bindings

The maintained in-game layout is:

`Y I O P G H J K L B N Q E`

These are the 13 chromatic notes from C through the next C. Left Ctrl steps the persistent bank down and Left Shift steps it up. Each bank tap is held for exactly 18 ms, released, and allowed to settle before any note key is pressed.

Historical and custom key profiles remain available. Scan-code `SendInput` is the recommended backend; virtual-key input is retained as a fallback and Dry run emits no keyboard input.

## Live MIDI keyboard

Version 2.13 adds supervised real-time controller input:

1. Connect a USB MIDI keyboard or expose a MIDI input port, then choose **Refresh** under **Live MIDI keyboard**.
2. Select the controller, MIDI channel, transpose, and maximum simultaneous live keys.
3. Put the SCUM instrument into Play mode and set SCUM to its base octave.
4. Choose **Live**. Play the controller normally; choose **Stop** or press F8 to disarm and release every key.

**Safe base-bank fold** is the maintained default. It folds incoming notes into the 13 chromatic C4-C5 SCUM keys. **Strict C4-C5** ignores notes outside that range. Live input never sends Ctrl or Shift: real-time bank changes are global in SCUM, would cut sounding chords, and cannot safely use the file planner's look-ahead.

Note-on/off reference counting prevents folded or repeated notes from releasing a shared SCUM key too early. Sustain pedal CC64 is supported, while CC120/123 perform an immediate all-notes cleanup. Channel 10 is ignored by default and the live polyphony limit defaults to three.

Live input never arms automatically. Scheduled playback and live keyboard routing are mutually exclusive, and controller callbacks never touch Qt widgets directly. Focus loss, device disconnect, MIDI/backend errors, Stop, F8, and application shutdown converge on the same key-release path.

## Playback sections and performance

Version 2.9 adds a per-MIDI playback-section editor:

- Add one or more **Play** ranges to prepare only those source passages.
- Add **Omit** ranges to cut unwanted bars from the complete song or from Play ranges.
- Overlapping ranges are merged and omissions are subtracted deterministically.
- Sustained notes crossing a boundary are clipped and safely re-attacked when playback resumes.
- Non-contiguous ranges are rebased into one prepared performance with a configurable pause.
- Ranges persist for that MIDI and can be cleared without changing the source file.
- The prepared result may loop until Stop or F8.

Selection happens before arrangement and SCUM planning. Every selected passage therefore begins from a known base octave-bank state and receives the normal arrangement, retrigger, chord, density, and focus-safety checks.

The playback worker now precompiles its timed batches, caches Windows key/scan-code resolution, temporarily requests 1 ms Windows timer resolution, and sends only genuinely simultaneous events in one `SendInput` call. Completion reports events, batches, loops, and average/maximum dispatch lateness. Zero-stagger triads reduce 600 individual events to 200 Windows batches; normally staggered or monophonic scores remain deliberately unbatched.

Select an existing playback range to load its boundaries back into the time editors, then choose **Update selected** to correct it without deleting and recreating the range. Its Play/Omit role and saved label are preserved.

The File menu keeps the ten most recently opened MIDI files, newest first. **Ctrl+O** opens a MIDI and **Ctrl+R** reloads the current one. Missing recent files remain visible but disabled so a temporarily disconnected drive does not erase the history.

While playback is active, every control that can change the visible file or prepared plan is locked. The running scheduler therefore cannot diverge from the file, mapping, timing, track, or range state shown in the window; Pause, Stop, F8, and final key cleanup remain available.

## Guided Command Deck

Version 3.2 makes readiness visible instead of relying on trial-and-error clicks. The four-stage rail identifies the active workflow step, the command pill reports Load MIDI, Select Tracks, Prepare, Ready, Playing, Paused, or Live Armed, and the right-hand guidance explains the next safe action.

Track search filters large scores by number, name, detected role, note count, or pitch range without changing the selection. The count always distinguishes selected populated tracks from filtered rows. Empty tracks cannot be checked, and double-clicking a populated row toggles it. **Auto-select musical** restores the relationship-aware lead, sectional solo, bass, and support recommendation.

Prepare, Play, Score CSV, and Events CSV activate only when their prerequisites exist. Play still prepares automatically when settings changed. Preparation shows a busy state and never sends keyboard input. Results use a compact multi-line summary plus selectable bullet advisories, while Dry run clearly states that no keyboard output will occur.

Audio-to-MIDI and Song Transposer validate their source, destinations, runtime availability, overwrite separation, and UVR requirements inline. Song Transposer settings scroll vertically at 880×720 while its log and actions remain reachable. Invalid custom key names keep the key editor open with a visible correction message.

Keyboard additions are **Ctrl+P** Prepare, **Ctrl+L** focus MIDI path, **F1** Quick Start, and **Delete** remove selected playback section. Existing Ctrl+O, Ctrl+R, F8, F9, and F11 behavior is unchanged.

## Using the app

For a live MIDI keyboard, follow the **Live MIDI keyboard** steps above. For MIDI-file playback:

1. Launch MusicalScumme.
2. Drop a `.mid` or `.midi` file onto the window, or choose **Open MIDI**.
3. Review the checked tracks and their detected roles. **Auto-select musical** recalculates the recommendation.
4. Optionally define Play and Omit ranges under **Playback sections** and enable looping.
5. Select **Guitar**, **Harmonica**, or **Banjo** as the target instrument.
6. Leave **Optimal Sounding** selected unless the current SCUM instrument needs the slower **SCUM Safe** fallback.
7. Choose **Prepare** or **Prepare selection** and inspect the retained-note count, detected score character, chord count, warnings, and duration.
8. Put the SCUM instrument into Play mode and return SCUM to the foreground.
9. Choose **Play**. F8 is the emergency stop.

Losing SCUM focus pauses safely when the default protection is enabled. Stop, completion, focus loss, and application shutdown all release held keys.

## SCUM score export

**Score CSV** writes one row per performed note with:

- score group and voice order;
- source and mapped pitch/name;
- SCUM key and target octave bank;
- velocity, attack, release, and duration;
- chord size.

This is the musical score. **Events CSV** is the lower-level keyboard timeline for diagnostics. Both exports are deterministic; the SCUM-score export is published through a same-directory temporary file.

## Song Transposer and audio

**Song Transposer** cleans a rough MIDI or transcribed audio source into a separate Lead Melody track and optional Light Support track. It performs deterministic overtone rejection, double-attack consolidation, contextual octave repair, and global melody-path selection. It never overwrites the source.

**Audio → MIDI** uses Spotify Basic Pitch in a separate per-user Python runtime. Full-song audio is an approximation; clean vocals or isolated instruments work best.

Optional UVR-compatible source separation runs in another isolated runtime containing `audio-separator` and PyTorch. The maintained two-stem default is BS-RoFormer Viperx-1297. It publishes visible vocals and instrumental WAV files, then transcribes only the selected stem. Neither ML runtime is imported into the main Qt/playback process.

## Run from source

Requires 64-bit Python 3.11 or newer on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

For development checks:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
```

## Build the Windows release

Run one of:

```powershell
.\build_exe.ps1
.\build_exe.ps1 -OneFile
python build_exe.py
```

The default build is an onedir application. Keep the complete `MusicalScumme` folder together. The packaged application includes the audio/separation installers, validators, workers, and requirement files; model environments and downloaded model weights remain external.

## Safety and validation boundaries

- Playback is foreground-only by default and always user-initiated.
- Live MIDI input is manually armed, never recorded or replayed, and remains muted outside SCUM by default.
- F8 is the emergency stop.
- No injection, hooks, game-memory access, anti-cheat bypass, stealth, gameplay automation, or game-file changes.
- Audio conversion reads one user-selected file and writes only user-confirmed outputs. It never sends SCUM input.
- Static tests and packaged launch checks do not prove musical quality inside the current SCUM build. A release is not **SCUM tested** until it is auditioned in-game on Windows.
- Audio conversion is not fully validated for a release until representative MP3, WAV, and M4A files have run through the installed Basic Pitch runtime.

See [CHANGELOG.md](CHANGELOG.md), [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), and [REGRESSION_CHECKLIST.md](REGRESSION_CHECKLIST.md) for detailed history, constraints, and validation evidence.
