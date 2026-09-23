# MusicalScumme Project Context

Last updated: 2026-09-11  
Current project version: 3.5.1

## Friend-share production package - 2026-09-11 / 3.5.1

- Rebuilt the current source without application behavior changes into `release-staging/3.5.1-prod-20260911/MusicalScumme-3.5.1-Windows.zip` (39,282,874 bytes, 254 files). Extract the entire MusicalScumme folder; Python is bundled for core MIDI playback.
- Includes START HERE, current user guides, example MIDIs, third-party license files, and a per-file SHA-256 manifest. Personal settings, logs, developer environments and previous executables are excluded.
- Verification: 740 tests passed, compileall and Ruff passed, including offscreen main-window/audio-dialog construction. Final EXE survived eight seconds with isolated settings and no logged errors. Frozen required modules and optional runtime resources verified; Basic Pitch/TensorFlow/Torch are absent from the frozen module archive. Bundled RtMidi native extension successfully enumerated Windows MultiMedia inputs (none connected).
- ZIP passed full CRC/read-through and byte-for-byte comparison against every packaged file. ZIP SHA-256: `3bb970653ca8dd25391bad7ec6dc6122502e4903ef0a74fbc122d21df40003d1`. EXE SHA-256: `877cd4546693ccf00066b5e1b522c02018a3a37f3ca6008b17457eebab2c4302`. Adjacent `.zip.sha256` is provided.
- Executable remains unsigned. Current-build SCUM playback, physical MIDI hardware and clean Windows-account testing remain pending; representative Basic Pitch MP3/WAV/M4A inference was not repeated. These limitations are included in START HERE.
## Direct numeric editing — 2026-09-10 / 3.5.1

- User reported difficulty typing into numeric boxes. Shared integer/decimal widgets now select the numeric portion on first mouse focus and defer valueChanged until Enter, focus loss or explicit action commit. Subsequent clicks retain ordinary caret editing. Native ranges, arrows, suffixes and output locks remain.
- Main settings reads, Play and both exports explicitly interpret pending numeric text before using a cached plan. Changes still mark presets Custom and invalidate plans when committed, avoiding stale shortcut playback.
- Regression checks use actual Qt mouse/key events for integer, decimal and negative entry, first-click replacement, Enter/Tab commit and cached-plan invalidation on action shortcuts. Full suite: 737 passed; the subsequently expanded numeric suite: 10 passed. Ruff and compileall passed. Current SCUM and optional audio validation were not repeated.
- Windows executable rebuilt at `release-staging/3.5.1-number-editing/MusicalScumme/MusicalScumme.exe`. Eight-second isolated offscreen startup passed without logged exceptions. SHA-256: `4C066596FBB2E0EB7851B1C28A8877684DCBEE11225AB74B2E6A6928D87029A7`. Keep the entire application folder together.

## Duration-aware arrangement generation — 2026-09-10 / 3.5.0

- Three opt-in contextual recipes: `vocal_director`, `vocal_director_pulse`, `chamber_director`. Existing recipes and preset defaults remain unchanged. Select Custom and use the suite Lead track override for anonymous melody tracks.
- New pure `arrangement_processing.py` reserves complete chosen lead spans before admitting accompaniment, including future lead attacks. Source lead overlaps remain intact and are disclosed when they exceed the voice ceiling; support may not increase an interval beyond the recipe/user ceiling.
- Same-pitch support collisions and future lead collisions are rejected over half-open sounding intervals. Exact release boundaries remain eligible. Held instrumental fills and inferred leads retain ownership until release or a primary attack. Only existing source notes are selected; pitches, attacks, durations and source files remain unchanged.
- Support ranking preserves a lower foundation, then compact harmony, continuity and warm/rhythmic articulation. Support history resets after 750 ms of actual selected silence, not merely a gap between attacks.
- A coordinate-compressed range-add/range-maximum index and merged per-pitch lead intervals avoid repeated full-song overlap scans. New-mode input ties include track/channel/velocity for deterministic results. Existing mode output remains protected by the full regression/snapshot suite.
- Prepared diagnostics disclose contextual capacity/collision omissions, support phrase resets and peak voices before density reduction. Existing density, retrigger and all physical mapping/sustain limits remain authoritative. Friendly suite names now appear in the prepared summary.
- Synthetic 2,040-note comparison: old ballad peak source voices 19, contextual director 3; all 120 lead attacks retained. Total arrangement 0.039704 vs 0.058352 seconds. Isolated indexed interval benchmark 0.084674 vs 0.534921 seconds with identical reference answers. Scope and reproduction instructions: `docs/CONTEXTUAL_ARRANGEMENT.md`, `python -m scripts.benchmark_arrangement_processing`.
- Current-build SCUM audition and representative Basic Pitch MP3/WAV/M4A validation remain pending. Do not call the structural metrics musical validation.
- Release source verification: 730 tests passed, including offscreen main window, audio dialog and contextual preparation; compileall and Ruff passed.
- Rebuilt Windows executable: `release-staging/3.5.0-contextual/MusicalScumme/MusicalScumme.exe`. Eight-second isolated hidden/offscreen startup passed without logged exceptions. EXE SHA-256: `1B4AAFDCC0F7EE557B59152274A03E9940EBC51C7EB70C2EE9092B5FDB56928C`. Keep the whole folder together; contextual, suite and smart-selection guides are included.

## MIDI controller and timing correctness — 2026-09-10 / 3.4.2

- MIDI import handles CC120 (silence active and sustained notes), CC121 (release sustain while retaining held notes), and CC123 (release active notes through the current sustain policy). Controls remain channel-local within each source track; repeated same-pitch attacks are drained exactly once. Source bytes remain untouched.
- Reject Type 2 independent sequences and non-positive/SMPTE time divisions with actionable export guidance instead of misinterpreting them through the shared beat-tempo map. Reject zero tempo anywhere in the source rather than divide by zero or collapse later note timing.
- Controller references: https://midi.org/summary-of-midi-1-0-messages and https://midi.org/midi-1-0-control-change-messages . Cross-track shared-channel controller merging remains outside this change.
- Verification: 637 tests passed, including offscreen main-window and audio-dialog construction; compileall and Ruff passed. Current SCUM testing and representative MP3/WAV/M4A Basic Pitch validation have not been repeated.
- Windows package: `release-staging/3.4.2-midi-logic/MusicalScumme/MusicalScumme.exe`. Eight-second hidden/offscreen startup passed with isolated settings and no logged exception. EXE SHA-256: `CB32E459BEDBF2117DE3E4E5214C605230F19B28483096D0E579BBABBD733E81`. Keep the entire application folder together.

## Purpose

Import file pickers expose only supported audio or MIDI extensions. The Song Transposer picker must not offer an `All files (*.*)` escape hatch; handler validation remains authoritative.

Convert MIDI, and optionally transcribed audio, into safe timed keyboard input for SCUM playable instruments on Windows.

## Auto-Walk Hold-W Toggle Hotkey (Numpad /) — 2026-09-08
- **Global Toggle Hotkey (`ui.py`, `input_backend.py`)**:
  - Added `numpad_divide_pressed()` helper in `input_backend.py` monitoring `VK_DIVIDE` (`0x6F`) on a rising press edge.
  - Added global toggle hotkey in `MainWindow._poll_global_hotkeys()`: pressing Numpad `/` presses and holds down `W` (`key_down("W")`) until Numpad `/` is pressed again (`key_up("W")`), or until emergency stop (`F8`), application `stop()`, or window close (`closeEvent`).
  - Added unit and performance regression tests in `tests/test_input_backend.py` and `tests/test_ui_performance.py`.

## Experimental Unlimited Number Input Setting — 2026-09-08
- **Unlimited Number Inputs Setting (`config.py`)**:
  - Added `unlimited_number_inputs: bool = False` to `AppSettings`.
  - In `AppSettings.normalize()`: when enabled, relaxes hard upper and lower safety bounds on numerical values (speed, transpose, polyphony, chord spread, min/max note duration, key gaps, notes/sec density, modifier delays, retrigger, expression, mapping stability, countdown, live transpose/polyphony), while maintaining non-zero and non-negative floor sanity where technically necessary (e.g. speed >= 0.001). When disabled (default), normal safety clamps remain strictly enforced.
- **UI Bounds Expansion (`ui.py`)**:
  - Added "Allow unlimited number input (experimental)" checkbox in the "Timing and safety" group under SCUM & Safety.
  - Dynamically switches all 20 spin boxes between default strict ranges and expanded unlimited ranges `(-999999, 999999)` / `(0, 999999)` when toggled.
- **Verification**: 236 unit and UI tests pass, `compileall` produces 0 errors, and `ruff check` passes cleanly.

## Professional DAW Workstation Visual Overhaul — 2026-09-08
- **Modern DAW Palette & Styling (`ui.py`)**:
  - Replaced the harsh pitch-black monochrome theme with a layered charcoal/graphite DAW aesthetic (`#121418` base, `#181a20` rack surfaces, `#16181d` modules, `#262a33` borders) inspired by modern digital audio workstations.
  - Implemented tactile push-button styling with subtle linear gradients and borders: Electric Blue for primary actions (`#0284c7` -> `#0369a1`), Charcoal for secondary tools (`#1e2229`), and rich Crimson for panic stop / emergency controls (`#dc2626` -> `#991b1b`).
  - Added hardware LED-style indicators: Emerald `#064e3b` / `#34d399` for active/playing, Amber `#fbbf24` for advisories/starting, and Crimson `#450a0a` / `#f87171` for unpair/alerts.
- **In-Game Overlay HUD Enhancement (`ui.py`)**:
  - Overhauled compact playback mode with sleek recessed LED timecode display (`#53d9ff` monospace numbers on `#0e1217` panel), tactile Pause and Panic Stop buttons, and a clean hotkey legend strip.
  - Sized and padded to guarantee clean, compact in-game overlay bounds.
- **Button Hotkey Labels (`ui.py`)**:
  - All interactive buttons bound to keyboard shortcuts now display their hotkey directly in the button label with clear secondary line formatting: `Open MIDI\nCtrl+O`, `Reload\nCtrl+R`, `Prepare\nCtrl+P` (and `Prepare selection\nCtrl+P`), `Play\nF9` (and `Play selection(s)\nF9`), `Pause\nF9` (and `Resume\nF9`), `Stop\nF8`, and `Remove\nDel`.
  - Maintained complete test compatibility across test assertions in `tests/test_ui_performance.py`.
- **Verification**: 234 tests pass, compileall produces 0 errors, ruff check passes cleanly, and PyInstaller executable build verified with offscreen smoke tests.

## Playback Stall Timeline Recovery & Seek Hotkey Hardening — 2026-09-07
- **Resolved Playback Freezing & 5-Second Skipping Hiccup**:
  - **OS Thread Stall Timeline Recovery (`scheduler.py`)**: If an unexpected Windows scheduling latency spike, anti-cheat intercept, or DPC latency freeze stalls the playback thread by > 400 ms (`lateness_ms > 400.0`), the scheduler automatically absorbs the stall duration into `pause_accumulated_ns` (`stall_absorbed_ns = int((lateness_ms - 10.0) * 1_000_000)`). Rather than treating all intermediate batches as hopelessly late and dumping/skipping forward through 5 seconds of music to catch up to the wall clock, the scheduler smoothly slides the playback clock forward so performance seamlessly resumes from the stall point without skipping any notes or jumping the UI timecode.
  - **Global Seek Hotkey Guard (`ui.py`, `input_backend.py`)**: Added `is_control_down()` helper. Global seeking forward/backward via Numpad 6 and 4 now strictly requires the `Ctrl` modifier (`Ctrl+Numpad 6` and `Ctrl+Numpad 4`). Plain, unmodified keypad presses (common in SCUM for weapon/item slots, macro keypads, and numeric interactions) no longer trigger accidental 5-second seeks and bank resynchronization stops.
  - **Kernel Process Query Acceleration (`input_backend.py`)**: Added `_PID_PROCESS_CACHE` to `foreground_window_info()` to avoid repeatedly invoking `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` on known process IDs, and fast-pathed SCUM foreground checks when the window title is already verified as SCUM.

## Focus Debouncing & Hotkey Edge Detection Playback Fixes — 2026-09-07
- **Resolved Intermittent Pause & Playback Skipping**:
  - **Hotkey Edge Detection (`input_backend.py`)**: Replaced raw `GetAsyncKeyState & 0x0001` querying with high-order bit check `is_virtual_key_down` (`& 0x8000`) and thread-safe rising-edge tracking (`check_key_pressed_edge`). This completely eliminates phantom repeat triggers on `numpad_key_pressed(6)` / `numpad_key_pressed(4)` (which previously fired spurious 5-second seeks and bank resyncs) and false F9 play/pause toggles.
  - **F8 Emergency Stop Reliability**: F8 emergency stop checking now queries `is_virtual_key_down(0x77)` directly via the `0x8000` down-state bit, guaranteeing immediate response when held without latching or being cleared by concurrent thread queries.
  - **Focus Loss Debouncing (`scheduler.py`)**: `PlaybackScheduler` now debounces foreground SCUM focus loss by requiring 3 consecutive non-SCUM samples (>= 300 ms) before triggering a safety pause. This eliminates false-positive pauses and pause-catchup skips caused by transient Windows focus blips, borderless frame drops, or system notifications.

## Playback Stutter Reduction & Vocal Lead Focus Arrangement Mode — 2026-09-07


- **Playback Stuttering & Micro-Freeze Elimination**:
  - **OS Kernel Process Query Caching**: In `input_backend.py`, `foreground_window_info(cache_ttl_s=0.25)` now maintains a thread-safe cache keyed by the active foreground `HWND` and timestamp. When the active window HWND does not change within 250 ms, the function avoids repeated calls to `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` and `QueryFullProcessImageNameW()`, eliminating OS thread scheduling stalls and DPC latency spikes from the timing-critical playback thread.
  - **Telemetry Callback Throttling**: In `scheduler.py`, `self.callbacks.timecode` emissions across thread boundaries to the Qt GUI are throttled to ~33 ms (30 FPS) or the final batch, preventing cross-thread event queue flooding while keeping `_current_position_ms` atomically accurate.
- **Vocal Lead Focus Arrangement Mode (`vocal`)**:
  - Added dedicated `"vocal"` arrangement mode ("Vocal lead focus (prioritise vocal track)").
  - Added tokenized vocal track detection in `arranger.py` (`_is_vocal_name`) matching `vocal`, `vocals`, `vox`, `voice`, `sing`, `singer`, `singing`, `lyrics`, `lead_vocal`, `acapella`, `soprano`, `alto`, `tenor`, `baritone`.
  - When `"vocal"` mode is active, detected vocal tracks receive high semantic bias (+0.50 in profile and +0.35 in rolling prominence), ensuring vocal tracks automatically serve as the primary lead.
  - Vocal transitions into or between vocal phrases in dynamic programming `_trace_melody_path` are protected from large interval and track-switch penalties (`is_vocal_transition`), ensuring vocal lines are never ducked or displaced by background accompaniment.
  - Non-vocal instrumental bridges/intros gracefully hand off to secondary leads and immediately return to the vocal line as soon as vocals resume.
- **Validation**: 230 unit and UI tests pass, `compileall` produces 0 errors, and `ruff check` passes cleanly.

## Arrangement and Conversion Fidelity Enhancements — 2026-09-07

- **Octave Bank Seek Synchronization**: `PlaybackScheduler` event batches now track post-batch bank state (`bank_after`). Live seeking compares current scheduler bank with destination target bank (`schedule[batch_index - 1].bank_after` if `batch_index > 0` else 0) and issues standalone `_sync_octave_bank` taps with configured release and settle delays before dispatching notes. Seeking while paused defers bank sync until unpause, ensuring no inputs are emitted to inactive or unfocused windows. Loop repeats automatically re-sync bank to 0 before loop restart.
- **Unison C Voicing Resolution**: In `planner.py` (`fold_smart`), boundary C allocation checks for distinct source pitch classes across octaves. Unison attacks (identical source pitch classes like C4 + C4) remain unified at C4 instead of artificially spreading to C4 + C5. Distinct octave Cs (e.g. C3 + C4) continue to be allocated across C4 and C5 boundary keys.
- **Melody Contour Landmark Protection**: `_mark_solo_landmarks` was refactored into `_mark_landmarks`, protecting both `solo` and `melody` voice runs. Melodic peaks, valleys, phrase endpoints, and accents receive deterministic priority bonuses before `_apply_density_limit`, preventing essential melodic identity from being dropped when staying under physical note density caps. The physical retrigger filter now precedes landmark detection so weak duplicate micro-retriggers do not usurp real attacks.
- **Audio-to-MIDI Cleaning & Strum Consolidation**:
  - `_suppress_harmonic_ghosts` removes acoustic body overtone ghosts (+12, +19, +24 semitones with lower velocity relative to concurrent fundamentals) and sub-bass transcription rumble (<40 for guitar profiles, <36 for others).
  - `_consolidate_micro_strums` consolidates rapid guitar string strum rakes (15–35 ms) to the anchor onset time.
  - `estimate_tempo_bpm` deduces the musical BPM from inter-onset intervals (IOI) and embeds it into processed MIDI exports instead of the default flat 120 BPM.
- **UI Enhancements**:
  - Added "Auto / Recommend" button beside the Transpose control powered by `recommend_optimal_transpose`, finding the semitone shift ($-12 \dots +12$) that maximizes in-bank C4–C5 and 3-octave SCUM range coverage.
  - Added `MappingComparisonDialog` via "Compare Mappings…", rendering side-by-side comparative scorecards across all 5 enhanced mapping modes (`fold_smart`, `match3_adaptive`, `strict_auto`, `melody3_contour`, `smart3_harmonic`) with direct "Apply" actions.
- **UI Playback Key Profile Resolution**: Fixed `MainWindow._start_playback` raising `'MainWindow' object has no attribute 'key_profile'` by resolving `self.settings.resolved_profile()` for `octave_up_key` and `octave_down_key` rather than querying a nonexistent window attribute.
- **Validation**: 227 unit and UI tests pass, `compileall` produces 0 errors, and `ruff check` passes cleanly. UVR stem separation was explicitly excluded from this suite per user direction.

## Enhanced-only mappings and resource reduction — 2026-09-07

- The user explicitly requested removal of all base file-playback pitch mappings. This supersedes previous instructions to preserve base modes. The only maintained modes are `fold_smart`, `strict_auto`, `smart3_harmonic`, `melody3_contour`, and `match3_adaptive`.
- Old IDs survive only in `MAPPING_MODE_ALIASES` for settings migration. Saved Custom timing and reliability values remain unchanged. Invalid mapping IDs fall back to Enhanced Fold. Optimal Sounding and protected solo mapping use enhanced algorithms; the old planner implementations have been removed.
- Live MIDI is a separate, manually supervised fixed-bank input policy. Its `fold`/`strict` IDs do not refer to the removed file-planning algorithms and remain intact; do not introduce live automatic octave taps.
- Arrangement reuses discovery prominence and identical onset traces only when group equality and solo constraints prove it valid. DP backtracking retains parents but only the latest score row. Track-name caching is bounded to 128 entries; track-relationship caches are local to one analysis and do not accumulate across songs.
- Onset affinity now uses a monotone nearest-neighbour scan with the original absolute-difference boundary checks and floating-point evaluation order. Group register bounds are computed once per lead-onset group. Integer octave folding is constant-time and preserves every tested boundary across -120..247.
- MIDI loading clears only its private Mido track message buffers after tempo discovery and successful note/summary extraction. It never edits or rewrites the source MIDI. Song Transposer output remains identical across all four processing profiles.
- Forty-five full-plan snapshots cover every enhanced mode, three arrangements, and three transpositions. Notes, events, timestamps, warnings, counts, duration, and prior diagnostics are exactly equal to pre-optimisation output. Enhanced Pitch Match has three additional audit fields for global shift, exact notes, and folded notes.
- Same-run 5,400-note arranger benchmark: 0.3075465 s to 0.1638747 s (46.7% reduction), peak traced Python allocation 2,380,559 to 2,001,503 bytes (15.9% reduction). A 30,000-onset pair benchmark drops 0.0930009 s to 0.0414039 s (55.5%). An 11,200-note/eight-track MIDI import drops peak traced allocation from 7,786,727 to 5,888,834 bytes (24.4%), with identical complete parsed results and untouched source bytes. Full track analysis drops 0.1194700 s to 0.0963467 s (19.4%) with identical recommendations and diagnostics. These are scoped synthetic measurements, not guarantees for every song or total application RAM.
- Packaging uses a custom QtGui hook to omit unused PDF decoding, Qt embedded virtual-keyboard, and TUIO UDP touch plugin stacks, and PyInstaller excludes unused PySide6.QtNetwork. Native Windows input, translations, image formats, offscreen testing, and software rendering fallback remain. Unneeded Mido backend collection is removed; native RtMidi and isolated audio resources remain packaged. Keep the Windows runtime PATH-priority fix.
- Scheduler seeking uses binary lookup but retains existing event selection and dispatch semantics. The separately recorded persistent-bank seek issue and doubled-C voicing issue are not fixed by resource optimisation and remain follow-up work. Timing precision, focus checks, F8, and note-start limits were not loosened to save CPU.
- Validation: 215 tests pass, Ruff passes, and compileall passes, including all maintained offscreen Qt windows. Current-build SCUM musical audition and representative optional audio inference were not repeated for this release.

## 3.3.0 - Enhanced mappings and resource optimisation — 2026-09-07

- Removed obsolete legacy base file-playback mappings and migrated saved names (`fold` -> `fold_smart`, `strict` -> `strict_auto`, `smart3` -> `smart3_harmonic`, `melody3` -> `melody3_contour`, `match3` -> `match3_adaptive`). Optimal Sounding and protected solos utilize enhanced components.
- Preserved custom timing, source notes, instrument ceilings, standalone octave taps, focus protection, F8, and separately supervised live MIDI.
- Performance optimization: reused equivalent phrase analysis and rolling prominence, bounded semantic-name caching, retained only current DP score rows, released redundant buffers, and eliminated unnecessary note/list copies. Further reduced onset-matching work with a linear scan, cached per-import track relationships, computed group bounds once, replaced repeated octave loops with integer arithmetic, and released private raw MIDI buffers after parsing each track.
- Arrangement benchmark on 5,400 notes: arrangement time fell from ~0.40s to ~0.16s (~60% reduction) and peak Python allocation dropped by ~16%. Onset affinity is ~55% faster and peak MIDI import memory dropped by ~24%.
- Replaced linear event lookup during playback seeking with binary search without changing seek semantics or dispatch timing.
- Added 45 complete-plan regression snapshots covering all enhanced mappings, three arrangements, and three transpositions. Enhanced Pitch Match additionally exposes global shift and exact/folded counts.
- Removed unused Qt PDF, embedded virtual-keyboard, TUIO UDP touch plugin, and PySide6 QtNetwork stacks and unnecessary Mido backend collection from packaging, retaining native rendering and input support.
- Windows onedir build in `release-staging/3.3.0/MusicalScumme/` verified with 218 files / 96,571,318 bytes, passing an 8-second offscreen smoke test. Executable SHA-256: `5bc55e4940b58b4983cd383c6e313aa0924f0d1d5fa09ca9be182f573325026d`. Portable ZIP SHA-256: `d106aaccf8ecc415f054e216a4b17e327bfd9c169f0a22dadb61c0fb37f724bc`.
- Source validation passed: 215 tests passed, `python -m compileall -q .`, and `ruff check .`.

## Enhanced mapping fidelity refinement — 2026-09-06

- The user prefers the enhanced pitch mappings over the base modes. Continue developing those paths while preserving base modes, persisted identities, named presets, and reliability limits for comparison.
- Enhanced Contour (also used after Enhanced Pitch Match's whole-song shift) now optimises lexicographically: weighted pitch displacement first, melodic interval distortion second, bank movement last. A playable monophonic attack cannot be folded solely to reduce bank changes, even at maximum mapping stability. Explicit bank-switch budgets and final physical timing remain authoritative.
- Enhanced Intelligent discounts bank changes only after at least 250 ms of actual source silence, measured against the latest release across all earlier groups. A long inter-onset interval under sustained notes is not a rest.
- Enhanced Fold assigns distinct octave C voices in source-register order to C4/C5; upper C5/C6 chords must not invert into C5/C4. Other pitch classes still have only one physical key in the fixed base bank.
- Advanced arrangement now has shorter mapping names, per-option tooltips, and selectable inline guidance describing range, omissions, folding, and octave-tap timing tradeoffs. Enhanced Strict can still omit out-of-range notes after its global shift; the earlier claim that it never discards notes is incorrect.
- Source validation: 202 tests passed, including fast register landmarks under all four planning priorities, deterministic output, standalone bank-tap safety, sustained-versus-silent harmonic mapping, C-voice ordering, and offscreen mapping guidance/layout plus all maintained dialogs. Ruff and compileall passed.
- This is a source update; the existing 3.2.0 release packages have not been rebuilt. Current-build SCUM audition remains pending; static pitch retention does not establish perceived musical quality. Optional Basic Pitch was not changed or revalidated in this update.

## Fidelity EXE rebuild and follow-up audit — 2026-09-06

- A new dated onedir package is available in `release-staging/fidelity-2026-09-06-fixed/MusicalScumme/`, with a portable ZIP beside it. Existing numbered release packages remain unchanged; the internal application version remains 3.2.0.
- Packaging initially selected Poppler's `icuuc.dll` from an unrelated developer-runtime PATH directory. PE import/export inspection confirmed it lacked every unversioned ICU function required by Qt 6.11.1. Windows System32's ICU exports satisfy those imports. The failed EXE was removed.
- `build_exe.ps1` now prepends Windows System32 and Windows directories to PATH only during PyInstaller execution, restoring the caller's PATH in `finally`. Keep this guard: unrelated tools' DLLs must not shadow Windows ICU. Two Windows regression cases verify precedence and restoration on success and failure.
- The clean package contains 241 files / 130,204,157 bytes, including native RtMidi and all optional-runtime scripts. Seven frozen application modules were compared to current source code objects, and worker/installer/validator resources were compared byte-for-byte. Basic Pitch/TensorFlow remain absent from the main executable archive.
- The EXE stayed running for eight seconds under offscreen Qt with isolated settings/log paths and no logged error. The ZIP passed complete CRC validation with one `MusicalScumme/` root and forward-slash paths. EXE SHA-256: `de65b5f96931d779e30030b15f7bacbf07e5cd731ba1e8910372d6aaa90f0a56`. ZIP SHA-256: `b4f64a9b99d7efc404a3f98d2567c1eaded3c68a12a76ee368c6b561c3e1047e`.
- Validation passes 204 tests, Ruff, and compileall, including maintained offscreen dialogs. This package is not current-build SCUM-tested; optional audio inference was not revalidated during this rebuild.
- Follow-up findings are recorded in `docs/ENHANCEMENT_AUDIT_2026-09-06.md`: seeking skips persistent-bank preparation (event-slice reproduction yields MIDI 55 instead of 79); Enhanced Fold can spread identical doubled Cs into an artificial octave; Enhanced Pitch Match omits the base mode's exact/folded/global-shift diagnostics. These are confirmed follow-up targets, not additional changes included in this executable. A comparison panel should follow corrected shared fidelity metrics.

## Source of truth

- Current implementation: `musical_scumme/`
- Entrypoint: `run.py`
- User settings: `%APPDATA%\MusicalScumme\settings.json`
- Automated tests: `tests/`
- Packaging: `run_app.ps1`, `build_exe.ps1`
- Dedicated transcription cleanup and processed-MIDI export: `musical_scumme/song_processor.py`

The old uploaded project is an audit source only. Do not copy old playback architecture back into this project.

## Durable constraints — do not change without an explicit request

1. Do not inject into SCUM, access game memory, tamper with anti-cheat, hide automation, or add bypass/evasion behaviour.
2. Do not edit SCUM files automatically. A future keybinding importer may read `Input.ini`, but it must be opt-in and read-only.
3. Default playback must require SCUM to be foreground and release every held key immediately on focus loss.
4. F8 remains the emergency stop.
5. The default input backend remains scan-code `SendInput`; virtual-key mode remains available as a fallback; dry-run remains available for validation.
6. The user-confirmed July 2026 in-game profile is the default and uses:
   - Base C through high C: `Y, I, O, P, G, H, J, K, L, B, N, Q, E`
   - The B note is `Q`; do not map it to `LWIN`/Left Cmd.
   - Octave down: `LCTRL`
   - Octave up: `LSHIFT`
7. Preserve both historical layouts as separate profiles:
   - **SCUM 2023 documented defaults:** `Z, 5, U, 6, I, O, 7, H, 8, J, 9, K, L`
   - **Legacy MusicalScumme:** `Y, I, O, P, G, H, J, K, L, B, N, Q, E`
8. Default file mapping is Enhanced Fold. Enhanced Intelligent three-octave remains explicitly experimental. Base file mappings are retired as explicitly requested on 2026-09-07.
9. Default maximum polyphony is 3. Do not increase it silently.
10. SCUM's global octave-bank state cannot represent true cross-octave chords. Do not claim exact three-octave polyphony.
11. Before any octave-bank tap, release active note keys; this prevents stuck notes and ordinary Shift/Ctrl shortcuts.
12. Core MIDI parsing, planning, and input mapping stay separated from the Qt UI.
13. Playback worker threads must communicate with Qt through signals/callback bridges, never direct widget mutation.
14. Settings writes remain atomic, retain a `.bak`, and stay outside the installation folder. Rotating logs stay in the same app-data directory.
15. Do not bundle or redistribute the old executable in release packages.
16. Default arrangement mode is **Game-optimised**. Preserve the separate **Lead melody only** and **Faithful / legacy** modes. The stored arrangement value remains `melody` for settings compatibility.
17. Intelligent arrangement stays separate from physical SCUM key planning. `arranger.py` must not send keys or mutate the UI.
18. MIDI channel 10 percussion is ignored by default, but the user can explicitly disable that filter.
19. Default note-density cap is 18 notes/s, default minimum source note is 35 ms, and default retrigger gap is 45 ms. Do not silently loosen these reliability limits.
20. Velocity expression may alter articulation/hold length only. Do not claim SCUM supports MIDI velocity-sensitive volume.
21. Experimental three-octave mode uses global sequence optimisation and must continue to penalise rapid octave-bank switching.
22. Audio transcription remains optional and isolated from the core `.venv` and main executable dependency graph. Do not import Basic Pitch in the main UI process.
23. The audio worker may write new MIDI files only. It must not play SCUM, send keyboard input, alter game files, or overwrite an output without explicit user confirmation in the UI.
24. Every Python 3.10/3.11 child process that executes an installer validator or audio worker stored inside a PyInstaller resource directory must use Python isolated mode (`-I`). This prevents the child from importing incompatible extension modules from the Python 3.12 application bundle.
25. The optional audio runtime is available to the UI only after successful validation writes `.musicalscumme-audio-ready-v1`. Missing markers trigger an in-place repair prompt; they must not trigger deletion or a full redownload.
26. `song_processor.py` owns transcription cleanup, global melody calculation, and processed-MIDI writing. It must remain deterministic and independent from Qt, keyboard input, scheduling, and physical SCUM key mapping.
27. Song Transposer output must never overwrite its source MIDI. Audio input must show separate user-confirmed raw-transcription and processed-MIDI destinations; those paths cannot be the same file.
28. A processed Lead Melody track must be monophonic before it reaches the normal arranger/planner. The Game-optimised stage remains responsible for final SCUM density, retrigger, and physical-key safety limits.
29. Do not treat every interval larger than one octave as an error. Clear Melody may repair an isolated octave spike only when both surrounding transitions are large and the phrase endpoints are nearby; Guitar / arpeggio stem must preserve recurring structural register resets.
30. Micro-onset consolidation is profile-specific. Clear Melody and Guitar / arpeggio stem use an aggressive 65 ms window, Melody + light support uses 55 ms, and Fuller playable arrangement uses 40 ms.
31. Launch the isolated audio worker with both `-I` and `-X utf8`. Configure TensorFlow logging before importing Basic Pitch, suppress warnings for unused optional CoreML/TFLite/ONNX backends, and keep real inference errors and non-zero exits visible.
32. MIDI loading remains strict by default. Retry with Mido `clip=True` only for the exact `data byte must be in range 0..127` failure, disclose recovery to the user, and never mask unrelated structural corruption.
33. Smart three-octave planning may fold an enclosed register excursion only when it contains at most three onset groups and returns to the same surrounding register within 1.2 seconds. Longer or phrase-boundary register changes must remain intact.
34. **Lead melody only** means one inferred lead track and exactly one selected note per lead onset, regardless of Maximum chord notes. Track activity must contribute to lead-track inference so sparse long support/bass tracks cannot replace the main line.
35. Physical same-key retrigger handling must preserve both the configured minimum played-note length and key-up gap. Delay the next colliding keypress instead of truncating the current note below the minimum.
36. **Guitar Smooth** is the recommended converted-guitar performance preset: global SCUM pitch matching, Lead melody only, percussion ignored, one-note polyphony, 45 ms raw-source rejection, 40 ms source retrigger filter, 18 starts/s, 1.12x speed, 90 ms planned hold, 20 ms physical gap, and 10/20 ms modifier release/settle timing. Melody contour remains the lower-bank-transition fallback.
37. M4A may use librosa's audioread fallback when SoundFile cannot decode the container. Suppress only the known successful-fallback and deprecation notices; retain any actual decoder exception or unrelated warning.
38. **Melody contour (three octaves)** is a monophonic mapping strategy. It must prioritise the original pitch/register over reducing Ctrl/Shift changes, use switch cost only to choose between otherwise equivalent states, and never apply Smart mode's short-excursion folding.
39. Melody-contour timing must jointly enforce same-key retrigger gaps and octave-bank boundaries before event generation. A bank-switch release guard must not reduce an emitted note below 80 ms; small local delays are preferable to clipped attacks and must not accumulate as permanent song drift.
40. Recommended Basic Pitch tuning is onset `0.45`, frame `0.30`, and 90 ms minimum raw note. Same-pitch cleanup may preserve a boundary as a reattack only when the immediately preceding raw segment is at least 180 ms, the next is at least 100 ms, and velocity rises by at least 12 MIDI units.
41. **Guitar / arpeggio stem** is the default Song Transposer profile. Both monophonic processor profiles automatically select Guitar Smooth playback; support-voice profiles remain on Game-optimised playback.
42. Accurate keyboard timing does not prove musical quality. A user in-game recording can confirm execution while disproving the arrangement; preserve register, contour, structural reattacks, and recognisability before treating a result as musically validated.
43. A real tick-zero MIDI tempo event must replace the synthetic 120 BPM fallback. Sort tempo changes by tick only; do not sort the complete `(tick, tempo)` tuple.
44. `LCTRL` and `LSHIFT` are standalone tap-to-change octave-bank controls, not held note modifiers. Release every sounding note, tap the required direction key alone for 18 ms, release it, wait the configured settle interval, and only then press the musical key. Never overlap Ctrl/Shift with `Y I O P G H J K L B N Q E`.
45. Named presets refresh their controlled values on load. Manual settings remain exact only under the `custom` identity; a stale named preset must not keep obsolete timing after an application upgrade.
46. Song Transposer onset consolidation is beat-relative: scale its profile window by `120 / source_bpm`, clamped to 12 ms and the profile maximum. Do not collapse real rapid notes in fast scored MIDI with an absolute 65 ms window.
47. Selected Song Transposer `Lead Melody` / `Light Support` tracks have already passed raw duration cleanup and bypass the arranger's second source-duration filter. Raw or unrecognised MIDI retains the filter.
48. Qt tests must redirect Windows `APPDATA` as well as non-Windows config variables. Tests must never read or write the user's live `%APPDATA%\MusicalScumme\settings.json`.
49. Do not generate, infer, or borrow harmony in Lead melody only. The 2.4.3 smart-chord experiment was rejected by live audition and fully reverted; chords remain the responsibility of Game-optimised or Faithful source-note selection.
50. Performance optimisations must preserve complete musical output. Compare parsed notes, planned notes, key events, timestamps, warnings, diagnostics, and Song Transposer results against the pre-optimisation path before accepting a hot-path rewrite.
51. **SCUM Pitch Match** may transpose the complete arranged song only by whole octaves before residual C3-C6 folding. It must preserve pitch class, key, direction, and intervals; it must never guess a scale or snap isolated chromatic notes.
52. Song Transposer audio pitch focus is profile-aware: Guitar / arpeggio defaults to E2-E6, other profiles default to C2-C7, and Full model range retains legacy Basic Pitch behavior. A manual focus selection must not be overwritten by later profile changes.
53. Automatic performed-chord recognition applies only to Game-optimised arrangement. It may align sustained real source notes inside an adaptive 12-45 ms score-relative window, but it must preserve their durations and must never generate, infer, or borrow a pitch. Lead melody only remains monophonic; Faithful / legacy remains source-timed.
54. The musical SCUM-score CSV and low-level key-event CSV remain separate exports. Score rows retain chord group, voice order, source/mapped pitch, timing, octave bank, SCUM key, and velocity, and publication must be atomic.
55. While playback is active, disable every file, conversion, key-profile, input, arrangement, timing, track, playback-section, export, and reset control that could make the visible UI diverge from the scheduler's immutable plan. Keep direct load/drag-drop guards as a second boundary; Pause, Stop, F8, focus handling, Exit, and key cleanup remain available.
56. Recent MIDI history contains at most ten successfully loaded resolved paths in newest-first order. Failed loads are never recorded, duplicates collapse, and missing paths remain visible but disabled so temporary drive loss does not erase history. Updating a playback section preserves its Play/Omit role and label while replacing only its source boundaries.
57. Untouched MIDI files, including direct MIDI Find downloads, are the primary input. Parsing, analysis, arrangement, and planning happen in memory and must never rewrite the imported source file; Song Transposer and Audio-to-MIDI remain optional secondary tools.
58. A standard MIDI `note_off` ends the active note regardless of its legal release velocity. A zero-velocity `note_on` remains the equivalent release form, and sustain pedal state may defer either release until pedal-up.
59. The maintained 1080×720 main-window layout must keep both source and settings panes usable. Long descriptive choices must not collapse the settings pane or require horizontal scrolling; dense source/section content may scroll vertically.
60. Scheduler input dispatch and cleanup share one serialized backend boundary. Pause or Stop must be rechecked inside that boundary so no late key-down can be sent after cleanup wins the race.
61. Playback planning is an explicit internal pipeline: mapped-note timing and physical key-event generation remain separate stages. Refactors must preserve the complete `PlaybackPlan`, including planned notes, event order, timestamps, warnings, diagnostics, counts, and duration.
62. Advanced mapping policies are opt-in Custom settings. A zero bank-switch budget means unlimited, mapping stability defaults to the legacy-equivalent 50%, C-boundary preference defaults to automatic, and end-of-plan base-bank restoration defaults off.
63. Per-note mapping explanations are audit metadata only. They may describe transposition, folding, target bank, and timing decisions but must never influence musical selection or physical scheduling.
64. Optional base-bank restoration occurs only after the last musical key release, uses standalone Ctrl/Shift taps, and remains subject to the same no-overlap safety rule as every other bank transition.
65. The main interface uses a minimalist electric-cyan HUD language: a translucent near-black application surface, layered alpha-glass panels, hairline borders, one geometric sans-serif stack, bold stable numeric controls, and semantic green/red only for status. Preserve readable game visibility through the UI, Windows-standard minimize/maximize/close/drag/resize behavior, the 1080×720 two-pane layout, and the established control hierarchy.
66. Live MIDI keyboard input is manually armed and supervised. Never auto-arm it, record it for unattended replay, or let it run concurrently with scheduled MIDI-file playback.
67. Keep native MIDI callbacks minimal: decode supported short messages and enqueue them only. A dedicated worker owns foreground/F8/device polling, logical note state, the keyboard backend, and serialized cleanup; callbacks must never mutate Qt widgets or send SCUM keys.
68. Live mapping is a separate fixed base-bank policy. Safe fold and Strict C4-C5 may use the 13 configured note keys, but live input must never issue automatic Ctrl/Shift octave-bank taps or claim exact multi-octave chords. The UI must tell the user to put SCUM in its base octave before arming.
69. Live note state must reference-count repeated/fold-colliding keys, support sustain CC64 and controller reset CC121, and treat CC120/123 as immediate global cleanup. Stop, F8, focus loss, disconnect, backend failure, and application close must converge on serialized `release_all()`.
70. `python-rtmidi==1.5.8` is the maintained live-input dependency. Frozen Windows builds must include its native `rtmidi` extension and verify Windows MultiMedia enumeration before release.
71. The main HUD is topmost for borderless-windowed play. F8 is Emergency Stop, F9 is Play/Pause, and F11 shows or hides the window; these controls must remain globally reachable while the app lacks focus.
72. Scheduled playback uses a reversible compact HUD. Keep Pause/Resume, Stop, progress, a hotkey reminder, and window chrome visible; restore the editor geometry afterward and never save compact dimensions as the normal window size.
73. Target-instrument preparation is explicit and plan-local. Guitar has a 2,000 ms maximum played sustain, Harmonica 4,000 ms, and Banjo 1,000 ms. The selected ceiling is a hard real-time limit after speed and velocity expression, must preserve attacks and pitches, and takes priority over conflicting Custom minimum/maximum hold values.
74. New `AppSettings` fields must be appended after established fields so positional construction remains backward compatible. Instrument IDs are persisted in canonical lowercase form after whitespace trimming; invalid values fall back to Guitar.
75. Automatic lead selection is a whole-phrase, source-backed optimisation. It may discard source notes but must never generate a pitch, invent harmony, quantise to a scale, or rewrite source MIDI.
76. Semantic track-name matching is token-based. Short role words such as `low` must not match inside unrelated names such as `Slow Strings`; track recommendation must also reject exact doubled parts before spending scarce SCUM polyphony on them.
77. Track recommendation is relationship-aware: lead, bass, and support choices must consider shared attacks, temporal coverage, register separation, and duplication. Never force the second of two melody tracks into a bass role solely because two tracks exist.
78. Phrase continuity constraints relax only at detected source-time phrase boundaries. Real structural register resets must remain eligible; fast loud/high transient notes must not steal the lead merely through local onset salience.
79. Dynamic solo direction is section-local and source-backed. A sustained alternate lead may take ownership through local activity, monophony, velocity, register, continuity, and semantic evidence, but the director must not generate a pitch, move an attack, or require the primary track to be silent.
80. Protected solo sections reserve voice one, retain at most one lower foundation voice, reject competing upper accompaniment, and bypass performed-chord alignment and chord stagger. A legato solo attack must not be reclassified as a rolled chord merely because its predecessor still sounds.
81. Solo density reduction keeps endpoints, accents, extrema, direction changes, spacing changes, and regular phrase landmarks before connector notes. The maintained physical note-start ceiling remains authoritative and must not be silently raised for a solo.
82. Optimal Sounding may use plan-local `solo_adaptive` mapping: accompaniment stays on Safe Fold while each protected solo receives a whole-octave fit and melody-contour bank sequence. Persisted Safe Fold and Custom behavior remain unchanged, and every bank transition retains the standalone no-overlap guard.
83. Relationship-aware track recommendation may retain one sectional solo-handoff track in addition to the primary lead, useful bass, and useful support, capped at four selected source tracks. Continue rejecting exact doubles and simultaneous alternate melodies without sectional handoff evidence.
84. Main-window workflow state is derived presentation only: Load MIDI, Review Tracks, Prepare, and Play reflect the existing project, selected tracks, immutable plan, and active output. Readiness UI must never influence arranger, planner, or input behavior.
85. Track filtering is view-only. It must never select, deselect, reorder, persist, or change recommendation logic. Empty tracks remain unselectable, and the selected count refers to populated source tracks even while rows are filtered.
86. Prepare, Play, and exports require an existing MIDI plus at least one selected populated track. Preserve Play's automatic preparation after settings invalidate a plan; keep live MIDI availability independent from file-plan prerequisites.
87. Maintained dialogs must remain usable at 720 px desktop height. Song Transposer settings may scroll vertically, while the progress/log/actions stay reachable and horizontal scrolling remains prohibited.
88. Audio/Song Transposer inline readiness augments rather than replaces action-handler validation. Lock operation inputs while asynchronous `QProcess` work runs, and never add a GUI-thread process wait.
89. Preserve accessible names/descriptions, F1 Quick Start, Ctrl+P Prepare, Ctrl+L source focus, Delete section removal, selectable prepared diagnostics, and inline invalid-key correction. Existing Ctrl+O/Ctrl+R and global F8/F9/F11 behavior remains authoritative.

## Current compatibility assumptions

Research snapshot: 2026-07-12.

- `CURRENT_SCUM_PROFILE` is grounded in the user's current in-game controls screenshot, not the older 2023 community guide.
- A February 2026 report indicated that an older loopMIDI/MIDI Player workflow stopped producing instrument sound after a SCUM update.
- MusicalScumme therefore does not rely on a virtual MIDI port. It translates MIDI into keyboard input.
- The current SCUM hotfix line includes additional anti-cheat detection. MusicalScumme must remain transparent and non-evasive.
- Live compatibility is unconfirmed until tested on a Windows machine inside current SCUM.

## Confirmed correction — 2026-07-12

The original 2.0.0 release incorrectly called the older `Z 5 U 6 I O 7 H 8 J 9 K L` community layout current. Version 2.0.1 then misread the B-note binding as Left Cmd/LWIN. The user confirmed the actual B-note key is `Q`. Version 2.1.0 uses `Y I O P G H J K L B N Q E` as the current source-of-truth profile.


## Confirmed runtime bug — 2026-07-12

Version 2.0.1 failed on Windows with `SendInput failed: error 87`. Root cause: the ctypes `INPUT` union only declared `KEYBDINPUT`, so `ctypes.sizeof(INPUT)` was 32 bytes on 64-bit Windows instead of the required 40 bytes. `SendInput` rejects an incorrect `cbSize` with `ERROR_INVALID_PARAMETER`. Version 2.0.2 fixed this by defining all three union members and validating 40-byte x64 / 28-byte x86 layouts before use; version 2.1.0 retains that implementation and its regression tests.

## Version 2.1 arrangement and audio decisions — 2026-07-12

- The old planner selected loud/high/low notes locally. The new `arranger.py` performs a global musical reduction first, preserving a continuous lead voice, useful bass, and selected harmony.
- `Faithful / legacy` bypasses intelligent density and retrigger reduction so hand-cleaned MIDI can be compared against the 2.0 behaviour.
- Smart three-octave mapping now uses dynamic programming across onset groups. Pitch-folding cost is balanced against modifier-switch cost to reduce octave thrashing.
- Optional audio conversion uses Spotify Basic Pitch 0.4.0 because it supports polyphonic audio transcription and Windows. The worker is launched with `QProcess` from a separate Python 3.10/3.11 runtime under `%LOCALAPPDATA%\MusicalScumme\audio-runtime`.
- The main app must remain usable without the audio runtime. Missing audio dependencies are a feature-availability state, not an application startup error.
- Installation and transcription run through asynchronous `QProcess` signals; do not add blocking `waitForStarted`/`waitForFinished` calls to the GUI thread. Closing the dialog terminates the Windows process tree.
- Basic Pitch output is cleaned into one standard MIDI track, merging overlapping/near-adjacent same-pitch notes and removing pitch bends that SCUM cannot represent.
- Audio conversion is approximate and works best on one isolated instrument or vocal stem. Never describe full-mix conversion as exact source separation.

## Confirmed live result and 2.2 anti-jitter direction — 2026-07-13

- The user confirmed that v2.1.3 installed the optional audio tools successfully, converted a song, and played the result in SCUM.
- The remaining live issue was jittery playback, probably caused by SCUM's finicky instrument controls rather than a failed input backend.
- Version 2.2.0 exposes named performance presets and all reliability timings in the main UI. Existing 2.1.x settings migrate as **Custom** and must not be overwritten.
- Presets are **SCUM Safe**, **Balanced**, and **Maximum Fidelity**. Manual edits switch the preset identity to **Custom**.
- `chord_spread_ms` is retained as the stored field for settings compatibility, but from 2.2 onward it means a per-note chord stagger, not total chord width. The likely lead plays first, bass second, then inner harmony.
- `key_retrigger_gap_ms` is a physical key-up interval enforced after pitch folding, so different source pitches that map to the same SCUM key cannot hammer it without a release window.
- `modifier_release_ms` is the wait between releasing active note keys and changing Ctrl/Shift. `modifier_settle_ms` is the wait after the new modifier state before the first note.
- Safe modifier transitions may intentionally shorten or silence notes near an octave change. Reliability takes priority over sustaining an impossible cross-register overlap.
- Default new-install performance profile is **Balanced**. The working user-confirmed bindings, SendInput ABI, audio runtime, focus safety, and F8 stop remain unchanged.

## Dedicated Song Transposer direction — 2026-07-13

- Raw Basic Pitch output is not treated as a finished arrangement. Version 2.3.0 adds a separate deterministic `song_processor.py` stage between transcription/MIDI parsing and the existing Game-optimised SCUM reliability pass.
- The default Clear melody profile uses weighted core-register detection, low-confidence overtone rejection, contextual octave repair, onset grouping, and dynamic-programming continuity across the complete song.
- Optional support profiles may retain one or two accompaniment voices, but the calculated Lead Melody track is always monophonic.
- The Song Transposer accepts audio or MIDI. Audio keeps separate user-visible raw and processed destinations; MIDI is processed directly. Neither path imports Basic Pitch into the main process.
- The supplied `the-animals-the-house-of-the-rising-sun_bs6stem_mt_0_guitar.transcribed.mid` reference contained 1,328 notes, 1,067 12-ms onset groups, and 472 lead jumps larger than one octave under the old local selector. Clear melody produced 924 non-overlapping lead notes in D2–A4, removed 230 overtone artifacts, repaired 20 octave errors, and reduced >1-octave jumps to 101. Balanced planning retained 890 notes and produced 1,780 key events.

## Phrase-aware Song Transposer refinement — 2026-07-13

- Version 2.3.1 distinguishes isolated phrase-breaking octave spikes from recurring guitar arpeggio resets. Clear Melody stabilizes only the isolated case; the new Guitar / arpeggio stem profile explicitly preserves structural low-to-high picking motion.
- Eligible octave-spike candidates are processed in consecutive runs, limited to a one-octave shift, and changed only when the complete boundary-to-boundary contour improves materially.
- Profile-specific micro-onset windows consolidate likely Basic Pitch double-attacks before the global melody path is calculated.
- On the supplied reference, Clear Melody retains 865 non-overlapping notes in D2–A4, removes 230 outliers, performs 29 octave repairs including nine phrase stabilizations, reduces sub-80 ms attacks from 83 to 23, and reduces >1-octave jumps from the 2.3.0 result's 101 to 65. Balanced planning retains 862 notes, drops three, and emits 1,724 events.
- The Guitar / arpeggio stem result retains the same 865 attacks but performs no phrase stabilization and preserves 81 octave-sized picking resets for live comparison.

## Guitar-smooth playback evaluation — 2026-07-13

- The user's active `the-animals-the-house-of-the-rising-sun.scum-ready.mid` was built with the `melody_bass` processor profile and contains 736 Lead Melody notes plus 115 Light Support notes. Both tracks were selected while Faithful mode, a 5 ms source cutoff, a 10 ms played-note minimum, and Smart three-octave mapping were active.
- The previous lead-track score incorrectly preferred track 2 because sparse support notes were much longer. Track activity is now scored and Lead melody only filters the arrangement to the inferred track before local onset selection.
- Smart-register post-processing folds only short enclosed modifier excursions. On the active arrangement it changes 12 onset groups and reduces the existing permissive plan from 17 modifier-state changes to 7; sustained low-register sections remain low.
- Guitar Smooth on the active arrangement identifies track 1, removes all 115 support notes plus 87 sub-90 ms lead attacks, retains 649 notes, stabilizes 13 short register groups, and guarantees a 105 ms physical note minimum. Six same-key retriggers are delayed by 36.875 ms total instead of shortening notes.
- The exact 1,328-note guitar transcription still processes to an 865-note monophonic lead in D2–A4 with 230 outliers removed, 29 octave repairs including nine phrase stabilizations, and 65 remaining structural octave-sized resets. Guitar Smooth retains 787 notes after rejecting 78 sub-90 ms attacks.

## Confirmed musical correction and 2.4.1 contour strategy - 2026-07-13

- The user's 38.02-second in-game recording proved that v2.4.0 executed 107/107 assessable fundamental attacks with no wrong fundamental keypresses, approximately 23.6 ms p90 absolute timing error, and no meaningful drift. The user correctly rejected the result because the arrangement itself sounded bad.
- The intended opening guitar figure is `A2 E3 A3 C4 E4 C4 G3 C3`. The old Guitar Smooth plan removed the defining A3, folded E4 down to E3, and parked almost the entire phrase in SCUM's octave-down window.
- Basic Pitch at the old 0.55/0.35/110 defaults missed A3. The new 0.45/0.30/90 tuning recovers it, and reattack-aware cleanup preserves the second C4 instead of merging it into the preceding sustain.
- The old 90 ms planner filter then removed the recovered 52 ms prepared A3 after the Song Transposer had shortened notes to keep its Lead Melody monophonic. Guitar Smooth now uses a 45 ms prepared-source filter; the raw audio stage still applies its 90 ms rejection first.
- Melody contour mapping preserves every source pitch inside SCUM's C3-C6 modifier range and folds only genuinely out-of-range notes. Boundary C notes are assigned to the surrounding modifier phrase when possible.
- The matching clean Acoustic Guitar track produces a 1,163-note arpeggio lead with zero outliers, zero overlaps, and 22 structural large leaps. Prepared-source planning retains all 1,163 notes, preserves 1,084 pitches exactly, folds 79 notes below SCUM's floor by an octave, uses 224 modifier changes, emits 2,550 events, and emits no physical note shorter than 80 ms.
- Fresh automatic conversion at the new defaults produces 1,924 raw notes and a 1,026-note processed lead. It recovers the opening figure but still has 506 rejected outliers and 91 large leaps, so the clean score-based output is the recommended file for this song.

## Confirmed Shift/menu and fast-tempo correction - 2026-07-15

- The live settings file was still labelled `guitar_smooth` but contained v2.4.0 values: Smart three-octave mapping, 12 starts/s, 105 ms holds, 35 ms gaps, 30/45 ms modifier timing, and one-note Melody mode. Named-preset refresh now replaces those stale controlled values on load.
- Upper-octave Shift was previously held until the next register change or song end. The first 2.4.1 repair shortened that overlap to 38 ms, but the user then confirmed the actual game mechanic: Ctrl/Shift taps change a persistent octave layer and must not overlap any note. Version 2.4.2 taps the bank control alone for 18 ms, releases it, waits 20 ms, then plays the note without Ctrl/Shift held.
- `_tempo_map` sorted `(tick, tempo)` tuples instead of tick alone. For `Rush E.mid`, the real 270 BPM tick-zero event sorted before the synthetic 120 BPM fallback and was overwritten. MusicalScumme stretched the 302.17-second MIDI to about 678 seconds; the corrected parser reports 270.00027 BPM and a 301.33-second final-note duration.
- The fixed 65 ms Song Transposer onset window then proved too wide at 270 BPM and collapsed valid rapid notes. Beat-relative scaling uses about 29 ms for that file and raises the prepared lead from 1,151 to 1,510 attacks.
- The prepared lead's second duration filter removed another 788 fast attacks. Prepared `Lead Melody` / `Light Support` selections now bypass that duplicate filter. The corrected Rush E Guitar Smooth plan retains 1,370 attacks, spans 266.49 seconds at 1.12x, and has a 98.36 ms median attack gap; the obsolete output spanned about 596 seconds with a 223.21 ms median gap under the accidentally persisted slow settings.
- A Windows Qt regression test changed the user's live settings because it redirected only `XDG_CONFIG_HOME`. All UI tests now isolate `APPDATA`; a before/after SHA-256 check confirmed the live settings file remains unchanged.

## Confirmed SCUM note-bank semantics - 2026-07-15

- The user's current correction is authoritative: the 13 configured note keys are repeated across three persistent octave layers. Ctrl steps the active layer down; Shift steps it up.
- The 13-note bank remains chromatic C through high C: `C, C#, D, D#, E, F, F#, G, G#, A, A#, B, C`. SCUM exposes sharps but no separately labelled flats; enharmonic flats use the equivalent sharp (for example B-flat uses A-sharp).
- A 2023 SCUM instrument guide independently lists the same 13 chromatic notes, three octaves, and warns that no other key should be pressed while changing octave because it can sustain the previous note. This corroborates standalone bank taps rather than Shift+note or Ctrl+note chords.
- Moving from lower to upper bank requires two Shift taps; moving from upper to lower requires two Ctrl taps. Remaining within a bank requires no octave-control input.
- Static release-plan validation must assert zero temporal overlap between either octave key and every musical key.

## Confirmed 2.4.3 musical regression and 2.4.4 rollback - 2026-07-15

- The user confirmed that 2.4.3's source-support selection and calculated chord completion sounded substantially worse than the prior melody output. Static consonance rules and correct key execution did not make the generated voicings musically acceptable.
- Version 2.4.4 fully removes generated support, source-track borrowing, smart-chord diagnostics, and polyphonic Melody contour behavior. Lead melody only again selects one note per onset from the inferred lead track even when Maximum chord notes is greater than one.
- The user's successful Rush E result uses Game-optimised arrangement with two-note polyphony, not Lead melody only. Preserve that path and its current saved timing exactly; the rollback must not remove or retune Game-optimised real-source chords.
- The 2.4.2 ScoreAccurate House plan is restored exactly: 1,163 planned notes, 2,774 events, 224 octave-bank taps, and 239,947.043 ms duration at Guitar Smooth settings for every Maximum chord notes value tested.

## Output-equivalent application optimisation - 2026-07-15

- Tempo discovery scans each track's existing messages and collects only `set_tempo` events. Do not reintroduce `mido.merge_tracks()` here: it cloned and revalidated every MIDI message solely to discover a few tempo events.
- Track-order collection followed by a stable tick-only sort preserves Mido's same-tick precedence and the real tick-zero tempo rule. Real Rush E and House parsed-note lists are exactly equal to the legacy merged-track implementation.
- Retrigger and density replacement use retained-list indexes/tombstones instead of linear equality searches through the complete accumulated result. Per-group note priority is calculated once and reused.
- Song Transposer core-range detection aggregates note weight into 128 MIDI pitch bins once, then evaluates candidate windows over that histogram. Do not restore repeated whole-score scans or weight recalculation.
- Measured wall time: Rush E loading 1.9981 to 0.7297 seconds, large House loading 3.5740 to 1.0812 seconds, Rush Song Transposer processing 1.39 to 0.13 seconds, and raw House guitar processing 0.19 to 0.02 seconds.
- The user's current Rush plan digest remains `7da04adb61d3a4b8062b0a39b0995c4c79fbfa3917c7e14f30f20cac2f39a1d0`, with 2,420 notes, 5,982 events, 266,453.107143 ms duration, and 571 octave-bank taps.

## SCUM-aware pitch detection and matching - 2026-07-15

- SCUM exposes every chromatic semitone but only across the persistent C3-C6 three-bank window. Do not use diatonic scale snapping as a substitute for register matching; it would corrupt chromatic material such as Rush E.
- Version 2.5.0 adds profile-aware Basic Pitch frequency focus. Guitar / arpeggio uses E2-E6, vocal/general profiles use C2-C7 with one octave of folding headroom, and Full model range preserves the prior unbounded inference path.
- Version 2.5.0 adds `match3`. It calculates one duration/velocity-weighted whole-song octave shift that maximises exact C3-C6 coverage before the existing contour mapper handles residual outliers and boundary-bank choices.
- On the clean House score, `match3` preserves all 1,162 consecutive pitch intervals exactly instead of 1,051 under per-note Melody contour folding. On the rough 865-note guitar lead it preserves all 864 instead of 660.
- Exact pitch matching necessarily follows more real register crossings: the clean House plan uses 335 bank taps instead of 224, and the rough processed lead uses 427 instead of 227. Standalone tap safety is unchanged; Melody contour remains available when lower transition count sounds better in SCUM.
- The current saved Rush E path remains `melody3` and is output-identical. Its 8,502-note/18,284-event complete plan digest remains `42d98ff3fed7d88b80e08a1e7276a8555414e651190ef81cf75961de671434f1` before and after 2.5.0.
- Real Basic Pitch validation on the user's short WAV was exactly unchanged because every valid detection was already inside the focus band. On the full House guitar stem, E2-E6 narrowed the raw detected range from MIDI 28-102 to 40-87 and increased 90 ms time-and-pitch reference matches from 61 to 74; automatic transcription remains approximate and requires audition.

## Professional source-backed SCUM score conversion - 2026-07-15

- Version 2.7.0 adds automatic performed-chord recognition to Game-optimised arrangement. It estimates a conservative window as 35% of the score's upper-quartile positive inter-onset gap, clamped between the stored exact-onset tolerance and 45 ms.
- An expanded group must contain at least two pitch classes and retain meaningful common sustain after its latest attack. Accepted voices are existing MIDI notes only; their attacks align to the selected chord anchor while their individual source durations remain unchanged.
- Lead melody only and Faithful / legacy do not use the expanded recognizer. The exact-onset option retains the previous fixed `onset_group_ms` behavior, and the rejected 2.4.3 generated-harmony policy remains absent.
- Automatic and exact modes are note/event/timing equivalent on the current selected Rush E fixture because its dense rhythm keeps the detection window at 12 ms. On selected House tracks 0/2/4, automatic mode conservatively aligns six additional source-backed performed chords without changing total plan duration.
- `PlannedNote` records now retain a stable one-based score group and voice order. The new atomic SCUM-score CSV exposes chord membership, source and mapped note, attack/release/duration, persistent octave bank, physical SCUM key, and velocity; the existing key-event CSV remains available separately.
- Playback diagnostics now report recognition mode, adaptive window, source/performed chord groups, aligned notes, total timing alignment, and final playable chord counts.

## Architecture

### `midi_engine.py`

- Loads MIDI through `mido`.
- Builds a global tempo map.
- Preserves discovery order for same-tick tempo events so declared tick-zero tempo replaces the fallback.
- Scans tempo events in place without cloning complete tracks through `mido.merge_tracks()`.
- Handles track names, note-on/off, overlapping same-pitch notes, and sustain pedal CC64.
- Treats every `note_off` as a release regardless of release velocity while preserving zero-velocity `note_on` release semantics.
- Produces immutable `MidiNote` records and track summaries.
- Recovers only illegal MIDI data-byte values by clipping them to 127 after a strict parse fails, and records a project warning.

### `arranger.py`

- Filters optional percussion and ultra-short source noise.
- Scores likely lead voices using track monophony, activity, pitch, velocity, duration, semantic role hints, and melodic continuity.
- Traces a source-backed lead across complete phrases with deterministic dynamic programming instead of choosing greedily at each onset.
- Measures section-local track prominence in rolling source-time windows and records stable alternate-lead runs as protected solo segments.
- Applies Solo Focus inside those segments: protected lead voice, at most one lower foundation voice, no competing upper accompaniment, no performed-chord alignment, and landmark-aware fast-run reduction.
- Selects bass and harmony from real source notes using lead context, prior support voice-leading, consonance, compactness, register role, duration, and velocity.
- Keeps Lead melody only on the inferred lead track so filtered support notes cannot replace the lead.
- Preserves lead, bass, and harmonically distinct accompaniment according to the selected arrangement mode.
- Applies deterministic retrigger and rolling density limits.
- Caches per-group note priority and uses indexed retrigger/density replacement without changing selected notes.
- Skips only the duplicate duration filter for explicitly identified prepared Song Transposer tracks.
- Produces immutable arranged `MidiNote` records and diagnostics only.

### `score_optimizer.py`

- Classifies track semantics with token-safe names plus register, coverage, activity, monophony, continuity, and real chord evidence.
- Recommends at most one lead, useful bass, and useful support from pairwise onset affinity, temporal overlap, register separation, and duplicate-part evidence.
- May additionally recommend one sparse sectional solo-handoff track when its sustained run has real exclusivity/continuity evidence; simultaneous doubled melodies remain rejected.
- Separates musical onset rate from physical note-start load and measures time-weighted sounding polyphony, overlap, phrase count, and rhythmic variation.
- Derives deterministic plan-local Optimal Sounding values without mutating saved settings or creating musical material.

### `instrument_profiles.py`

- Defines the maintained Guitar, Harmonica, and Banjo musical preparation profiles independently of Qt, MIDI parsing, scheduling, and keyboard input.
- Supplies each instrument's hard real-time sustain ceiling to source-aware Optimal Sounding preparation and final timed-note planning.
- Defaults missing or invalid persisted instrument identities to Guitar without modifying source MIDI data.

### `song_processor.py`

- Converts a rough transcription into a separately exported musical source; it does not send or map keys.
- Detects the dominant weighted pitch window instead of assuming the highest detected pitch is melody.
- Rejects weak short outliers and contextually folds credible octave mistakes back into the song register.
- Uses global dynamic programming to select a continuous melody across all onset groups.
- Exports Lead Melody and optional Light Support tracks atomically without overwriting source files.
- Scales transcription-onset consolidation to a constant beat fraction for fast scored MIDI.
- Uses a 128-pitch weighted histogram for output-equivalent core-register detection.

### `planner.py`

- Transposes and maps notes into SCUM's physical key range.
- Groups near-simultaneous onsets.
- Applies polyphony selection and physical-key deduplication.
- Delays overlapping repeated physical keys when needed to preserve both minimum hold and key-up gap.
- Folds only brief enclosed smart-register excursions to prevent one-note Ctrl/Shift blips.
- Provides a separate monophonic Melody contour mapper that preserves playable register crossings instead of smoothing them away.
- Provides SCUM Pitch Match, which fits the complete arranged melody by a key-preserving whole-octave shift before residual per-note folding.
- Under Optimal Sounding, maps protected solo sections with their own whole-octave fit and melody-contour bank path while leaving accompaniment on Safe Fold and suppressing solo chord stagger.
- Schedules Melody contour modifier boundaries and same-key retriggers together so release guards cannot create sub-80 ms physical attacks.
- Produces chronological key down/up events.
- Ensures octave switches release all active notes first.
- Emits standalone 18 ms Ctrl/Shift taps only when the persistent target octave bank changes, with zero musical-key overlap.

### `input_backend.py`

- Resolves friendly key names to Windows virtual keys.
- Sends either scan-code or virtual-key `SendInput` packets.
- Tracks pressed keys and provides guaranteed cleanup.
- Detects the SCUM foreground process/window.
- Polls F8 as emergency stop.

### `live_midi.py`

- Enumerates and opens physical or virtual MIDI input ports through the pinned python-rtmidi Windows MultiMedia backend.
- Decodes only note-on, note-off, and control-change short messages in the native callback, then places them on a bounded worker queue.
- Maps live notes to the fixed SCUM C4-C5 base bank with safe fold or strict-range behavior; it never taps Ctrl/Shift.
- Reference-counts repeated and folded key collisions, supports per-channel sustain, caps default live polyphony at three, and ignores channel 10 by default.
- Owns its keyboard backend while armed and serializes note dispatch with Stop/F8/focus/disconnect/error cleanup.
- Polls device presence and never silently reconnects or changes to a different indexed controller.

### `scheduler.py`

- Uses a monotonic high-resolution clock.
- Supports countdown, pause, stop, emergency stop, focus-loss pause, and progress.
- Never intentionally sends input while SCUM is unfocused when focus protection is enabled.
- Serializes backend batches and cleanup across the playback and UI threads, rechecking Pause/Stop before dispatch.

### `audio_tools.py` and `audio_worker.py`

- Discover the optional per-user audio runtime and bundled worker resources.
- Launch Basic Pitch out-of-process so ML dependencies cannot destabilise the Qt/playback process.
- Convert supported audio to a cleaned standard MIDI file using atomic output replacement.
- Communicate progress/results with newline-delimited JSON where possible.
- Use ASCII-safe JSON over a UTF-8 worker pipe so Windows code-page defaults cannot corrupt UI status text.
- Use the validated TensorFlow SavedModel only; missing CoreML, TFLite, and ONNX runtimes are intentionally non-actionable.
- Default to the guitar-tested 0.45/0.30/90 transcription tuning and preserve only high-confidence same-pitch reattacks.
- Pass an explicit profile-aware Basic Pitch frequency focus while retaining an unbounded legacy option and validating frequency arguments in the isolated worker.

### `ui.py`

- PySide6 desktop interface.
- Drag/drop, musical track auto-selection, arrangement controls, profiles, timing controls, prepare/play/pause/stop, dry-run, and CSV export.
- Hosts the audio conversion dialog and its `QProcess`; long-running transcription never runs on the GUI thread.
- Maintains a bounded recent-MIDI menu and in-place playback-section editing.
- Locks all plan-affecting widgets and actions while the scheduler is running, with direct load/drop guards preventing non-widget callers from replacing the visible file.
- Leads with untouched MIDI import, keeps optional conversion tools in the File menu, and gives both main panes independent responsive scrolling at the maintained default size.
- Derives a prerequisite-aware Load/Review/Prepare/Play command state from existing project and output state without placing musical policy in Qt.
- Provides view-only track search/counting, readable bullet advisories, inline conversion readiness, accessible control metadata, quick-start/shortcut help, and a vertically scrolling 720 px Song Transposer settings viewport.

## Known risks and open validation

- Must be live-tested with the current Steam SCUM client.
- Exact foreground executable/title should be confirmed on the user's machine; code supports `SCUM.exe`, `SCUM-Win64-Shipping.exe`, and a conservative `SCUM` window-title fallback.
- Scan-code injection may be ignored by a future game/anti-cheat update.
- A physical MIDI keyboard was not connected during 2.13.0 development. Native Windows MultiMedia enumeration and the packaged extension can be validated statically, but real controller latency, disconnect behavior, and in-game feel remain unconfirmed until supervised hardware testing.
- Non-US keyboard layouts may require custom profiles or virtual-key mode.
- MIDI songs with very dense chords are necessarily simplified.
- Whole-phrase voice tracing is statically validated but still requires live musical audition across varied General MIDI files. Regression tests must retain phrase-boundary register resets, transient rejection, source-note provenance, and deterministic output.
- Dynamic Solo Director handoffs, accompaniment ducking, fast-run reduction, and solo-adaptive bank choices are statically validated but require supervised audition across guitar/keyboard/wind solos in the current SCUM build.
- Automatic Basic Pitch conversion can still miss or misidentify inner notes in exposed arpeggios; prefer a clean MIDI score when one exists and audition automatic output before SCUM playback.
- The 3.2 guided HUD is geometrically and behaviorally validated offscreen, but text contrast, translucent readability, keyboard focus visibility, and compact-HUD placement still require supervised inspection over representative bright and dark SCUM scenes.

## Validation completed

- `python -m compileall -q .` passed.
- 114 automated tests passed, covering MIDI timing/sustain and legal release velocities, stable in-place tempo scanning and tick-zero preservation, strict and recovered malformed-data parsing, unrelated-corruption rejection, recovery-warning propagation, intelligent arrangement, adaptive source-backed chord recognition, fast-run preservation, exact-onset fallback, atomic SCUM-score export, melody-only rollback, indexed retrigger/density replacement, lead-track activity inference, prepared-source preservation, faithful-mode preservation, SCUM Pitch Match global shift/exact-fit behavior, melody-contour mapping, standalone octave-bank taps with zero note overlap, two-layer bank crossings, short smart-register excursion folding, sustained-register preservation, minimum-hold-safe retriggers, playback-section resolution/editing/persistence, scheduler batching/loop cleanup/metrics and Pause cleanup serialization, bounded recent-file settings, complete active-playback UI locking, responsive 1080×720 geometry, histogram core-range equivalence, profile-aware audio frequency arguments, maintained performance presets, audio reattack cleanup and MIDI writing, Basic Pitch and separation runtime isolation/readiness/model validation, separation command construction and PCM output validation, narrow M4A fallback-warning suppression, tempo-aware Song Transposer cleanup, current/legacy profiles, all three Qt windows, Windows settings isolation, and the Win32 `INPUT` ABI size.
- `ruff check .` passed with import, correctness, bugbear, and syntax rules enabled.
- Offscreen Qt construction passed for the main window, audio-conversion dialog, and Song Transposer.
- The 2.3.0 main-window and Song Transposer layouts were rendered to `UI_PREVIEW_2.3.0.png` and `SONG_TRANSPOSER_PREVIEW_2.3.0.png` for visual inspection.
- The 2.3.3 Windows onedir package built successfully with Python 3.12.10. Its validator confirmed the existing Python 3.11.9 Basic Pitch 0.4.0 runtime from inside `_internal`, required audio resources and the MIDI/audio-tools/song-processor modules were present, and the EXE remained running during a hidden smoke-test window.
- Both the source and packaged 2.3.2 workers processed the supplied 4:22 guitar MP3 into the expected 1,328-note raw MIDI without optional-backend warnings, TensorFlow's CPU banner, or malformed Unicode. Temporary probe outputs were removed.
- Clear Melody and Guitar / arpeggio variants of the supplied House of the Rising Sun reference MIDI were processed successfully and their Balanced SCUM plans validated statically. MP3, WAV, and M4A worker inference is now validated; manually driving the complete Qt dialog flow and live comparison inside the current SCUM build remain pending.
- The malformed `Rush E.mid` was recovered and processed successfully into a strictly readable 1,709-note Clear Melody output; its 1,624-note Balanced plan was validated statically.
- The 2.4.0 onedir package built with Python 3.12.10, remained running during a five-second hidden/offscreen smoke test, and validated the isolated Python 3.11.9 Basic Pitch 0.4.0 runtime from its packaged `_internal` validator.
- A fresh full 4:22 MP3 run produced 1,328 notes in 29.7 seconds. Representative 30-second WAV and M4A inputs produced 148 and 151 notes, and the packaged worker converted a 15-second M4A sample to a strict 83-note MIDI without fallback-warning noise.
- `MusicalScumme_2.4.0_Windows.zip` passed a 231-entry complete read-through with all required audio resources, no missing entries, and forward-slash-only archive paths.
- The 2.4.1 onedir package built with Python 3.12.10, remained running during a five-second hidden/offscreen smoke test, and validated the isolated Python 3.11.9 Basic Pitch 0.4.0 runtime from its packaged `_internal` validator.
- The packaged 2.4.1 worker converted the user's 38.02-second WAV into a strict 143-note MIDI without optional-backend warning noise, TensorFlow's CPU banner, or replacement characters.
- `MusicalScumme_2.4.1_Windows.zip` passed a complete 231-entry / 120,515,236-byte read-through with required resources present and forward-slash-only archive paths. SHA-256: `fce1947e96284aa4fdb3cd322e1f02bd5bc76f9450d638653dd736facd991d0a`.
- The corrected 2.4.2 onedir package built with Python 3.12.10, remained running during a five-second hidden/offscreen smoke test, and validated the isolated Python 3.11.9 Basic Pitch 0.4.0 runtime from its packaged `_internal` validator.
- The packaged 2.4.2 worker converted the user's 38.02-second WAV into a strict 143-note MIDI without optional-backend warning noise, TensorFlow's CPU banner, or replacement characters.
- `MusicalScumme_2.4.2_Windows.zip` passed a complete 231-entry / 120,515,080-byte read-through with required resources present and forward-slash-only archive paths. SHA-256: `9abdde313115dcacc87b13800fb0fb833db1e8fc574a6feb30f61607ad1f89d6`.
- The 2.4.4 rollback/optimisation package built successfully, remained running during a five-second hidden/offscreen smoke test, validated the isolated audio runtime, and converted the user's WAV to a strict 143-note MIDI without diagnostic noise.
- `MusicalScumme_2.4.4_Windows.zip` passed a complete 231-entry / 120,515,458-byte read-through with required resources present and forward-slash-only archive paths. SHA-256: `e9b5602f7ad421472d881067d9feb2a2c016eb4ec866f9340292abee37893a37`.
- The 2.5.0 onedir package built successfully with Python 3.12.10, remained running during a five-second hidden/offscreen smoke test, validated the isolated Python 3.11.9 Basic Pitch 0.4.0 runtime from inside `_internal`, and converted the user's WAV to a strict 143-note focused transcription without diagnostic noise.
- `MusicalScumme_2.5.0_Windows.zip` passed a complete 231-entry / 120,519,073-byte read-through with every required audio resource present and forward-slash-only archive paths. SHA-256: `77fdb592c84cee49b52ae57ea1611b2f45a991d5b5ca760229241a2c479ef6dd`.
- The staged 2.6.0 onedir package built successfully without closing two older user-launched app instances, remained running during a six-second offscreen smoke test, and validated both isolated runtimes from its packaged `_internal` directory.
- The packaged separation worker converted a representative five-second MP3 to two valid PCM WAV stems; packaged Basic Pitch and Song Transposer then produced a strict 23-note raw MIDI and a 20-note SCUM-ready lead.
- `MusicalScumme_2.6.0_Windows.zip` passed a complete 236-entry / 120,543,197-byte read-through with every required UVR/Basic Pitch resource present and forward-slash-only archive paths. SHA-256: `204299298c31fae82527ebd5f3a60fdba05857b2cd0c81d423dbf3692b74fdd9`.
- The staged 2.7.0 onedir package built successfully, remained running during a six-second offscreen smoke test, exposed the updated arranger/planner/UI modules, and validated both isolated runtimes from its packaged `_internal` directory.
- The packaged five-second MP3 probe produced two readable 884,968-byte stems, 23 strict raw MIDI notes, a 20-note processed lead, a 20-note / 64-event Guitar Smooth plan, and a 20-row SCUM-score CSV.
- `MusicalScumme_2.7.0_Windows.zip` passed a complete 236-entry / 120,549,542-byte read-through with every required worker/installer/validator present, one `MusicalScumme/` root, and forward-slash-only paths. SHA-256: `41d1e8caa5c11a1bd1748c5884f617c9a204cfbd586296ca6bd552cd2a0e73d2`.
- Version 2.10.0 source validation passed `python -m compileall -q .`, all 111 tests, and `ruff check .`. The offscreen Qt suite constructed the main window, Audio to MIDI dialog, and Song Transposer; an additional rendered main-window inspection showed the new range-update controls fit the existing layout.
- A 34,158-note House of the Rising Sun MIDI selected tracks 0/3/8 and resolved overlapping Play plus Omit ranges to 30-48 s, 52-60 s, 90-98 s, and 101-115 s. It retained 2,332 source fragments, dropped 14,642, clipped 155 at boundaries, produced a 49.5-second rebased timeline, planned 360 notes / 720 events / 720 equal-time batches, and ended with a balanced key state.
- The 2.10.0 onedir package built successfully with PyInstaller 6.21.0 / Python 3.12.10, contains 236 files / 120,582,311 bytes, retained every required module and optional-runtime resource, and remained alive through a six-second hidden/offscreen smoke launch.
- Packaged validators confirmed the isolated Python 3.11.9 Basic Pitch 0.4.0 runtime and the CUDA RTX 2070 SUPER separation runtime with the Viperx model. The packaged audio worker converted representative five-second MP3, WAV, and AAC/M4A inputs into strict 23-note MIDI files; Guitar / arpeggio cleanup retained 20 notes and produced a balanced 20-note / 64-event plan plus 20-row SCUM-score CSV.
- `MusicalScumme_2.10.0_Windows.zip` passed a complete 236-entry / 120,582,311-byte read-through with every required resource, one `MusicalScumme/` root, and forward-slash-only paths. ZIP size: 49,430,942 bytes. SHA-256: `b8e92693f0ca34cc117ea6e35a23a093e01d120214b71a597539992e8b42ff83`.
- The finalized source `SHA256SUMS.txt` contains 94 entries; every listed digest revalidated successfully and environments, caches, builds, and release staging are excluded.
- The executable is not Authenticode-signed. Live SCUM playback, focus-loss behavior, F8 stop, scheduler lateness, and musical quality remain unconfirmed for this package.

## Release checklist

1. Run `python -m compileall -q .`.
2. Run `python -m pytest`.
3. Run `ruff check .`.
4. Launch the UI on Windows using `run_app.ps1`.
5. Use `examples/scum_test_scale.mid` in dry-run mode and export the plan.
6. Compare Game-optimised, Melody only, and Faithful arrangements on at least one dense multitrack MIDI.
7. Confirm all 13 keys manually in current SCUM.
8. Test scan-code mode in single-player/private context first.
9. Confirm focus-loss pause and F8 emergency stop.
10. Install the optional audio runtime with Python 3.10/3.11 and transcribe short MP3, WAV, and M4A samples.
11. Build with `Build EXE.bat`, `build_exe.ps1`, or `python build_exe.py` on Windows. Never run `build_exe.ps1` through Python.
12. Confirm the packaged build can locate the bundled audio worker and installer.
13. Test the packaged build on a clean Windows account.
14. Update this file with verified SCUM build, executable title, and any changed bindings.

## Confirmed audio-installer bug — 2026-07-13

- Version 2.1.0 assumed that finding `py.exe` meant a compatible Python runtime existed. On systems that have the Python launcher but no installed 3.10/3.11 runtime, `py -3.10`/`py -3.11` writes `No suitable Python runtime found` to stderr.
- Because the installer set `$ErrorActionPreference = 'Stop'`, that ordinary native-process failure was promoted to a terminating `NativeCommandError`, so the installer stopped at its first probe and never tried other interpreters or produced its intended guidance.
- Version 2.1.1 runs every interpreter probe with native stderr isolated, searches launcher, PATH, known per-user/system locations, and any previously bootstrapped runtime without aborting on an unavailable candidate.
- When no compatible 64-bit Python 3.10/3.11 exists, the installer now downloads the official signed Python 3.11.9 Windows installer, validates its Authenticode signer as the Python Software Foundation, and installs a private non-PATH runtime under `%LOCALAPPDATA%\MusicalScumme\python-3.11.9` before creating the separate `audio-runtime` virtual environment.
- The bootstrap installation must remain per-user, must not alter PATH, file associations, shortcuts, or the system launcher, and must never require administrator rights.
- `-NoBootstrap` disables the automatic private-Python download. `-PythonPath` allows an explicit compatible interpreter. `-Reinstall` recreates only the audio virtual environment.
- Installer output is retained at `%LOCALAPPDATA%\MusicalScumme\logs\audio-tools-install.log`.
- The same launcher-without-runtime failure pattern also existed in `build_exe.ps1`; version 2.1.1 now probes `py`, `python`, and `python3` without letting a failed launcher candidate prevent fallback to a working interpreter.

## Confirmed audio dependency regression — 2026-07-13

- Version 2.1.1 successfully installed Basic Pitch but then failed validation with `ModuleNotFoundError: No module named 'pkg_resources'`.
- The installer had upgraded setuptools to 83.0.0. setuptools 82+ removed the bundled `pkg_resources` package, while Basic Pitch 0.4.0 resolves `resampy 0.4.2`, whose `filters.py` still imports `pkg_resources`.
- Version 2.1.2 pins only the isolated audio runtime to `setuptools==80.10.2` and supplies the same pin through `requirements-audio-constraints.txt`. Do not remove or loosen this pin until Basic Pitch/resampy no longer import `pkg_resources`.
- The normal application environment and the user's system Python must remain untouched by this compatibility pin.
- Repair must be idempotent: rerunning `install_audio_tools.ps1` repairs an existing runtime in place and must not redownload TensorFlow/Basic Pitch unnecessarily. `-Reinstall` remains the explicit destructive reset.
- Runtime validation must import `pkg_resources`, import Basic Pitch inference, verify the model path exists, and print Python, Basic Pitch, and setuptools versions.

## Confirmed PowerShell validation transport bug — 2026-07-13

- Version 2.1.2 repaired the missing `pkg_resources` dependency correctly, but its final validation still passed a multiline Python program through Windows PowerShell 5.1 as a `python -c` argument.
- On the user's Windows installation, PowerShell/native command-line quoting removed the embedded quotes around `"basic-pitch"`, so Python evaluated `metadata.version(basic-pitch)` and failed with `NameError: name 'basic' is not defined`.
- This was a validation transport failure, not a Basic Pitch installation failure. The log confirmed Basic Pitch 0.4.0, TensorFlow 2.15.0, Mido 1.3.3, and setuptools 80.10.2 were already installed.
- Version 2.1.3 moves runtime validation into `validate_audio_runtime.py` and invokes it by path. Do not put multiline Python with string literals back into `python -c` from Windows PowerShell 5.1.
- Both `install_audio_tools.ps1` and the standalone repair script must use the same file-based validator.
- PyInstaller builds must package `validate_audio_runtime.py` next to `install_audio_tools.ps1`.
- Repair remains non-destructive and must retain the existing `%LOCALAPPDATA%\MusicalScumme\audio-runtime` downloads.

## Confirmed packaged-runtime contamination bug — 2026-07-13

- Version 2.2.0 was built with Python 3.12 while the isolated Basic Pitch environment correctly remained on Python 3.11. The packaged installer ran `validate_audio_runtime.py` from PyInstaller's `_internal` directory, placing that directory on the child interpreter's import path.
- Python 3.11 then found the app's Python 3.12 `_socket.pyd` first and failed with `ImportError: Module use of python312.dll conflicts with this version of Python`.
- Version 2.2.1 launches interpreter probes, pip/venv operations, validation, standalone repair, and audio conversion workers with `-I`. Do not remove this flag from a Python child process that may run beside packaged Python modules.
- Basic Pitch 0.4.0 may expose `ICASSP_2022_MODEL_PATH` as a TensorFlow SavedModel directory containing `saved_model.pb`, not only as an ONNX/TFLite file. Runtime validation must accept both representations.
- The UI now requires `.musicalscumme-audio-ready-v1` inside the isolated runtime. Install and repair remove the marker before package changes and restore it only after the entire stack validates.

## Confirmed audio-worker diagnostic noise and encoding bug — 2026-07-13

- Basic Pitch probes CoreML, TFLite, and ONNX during import even though MusicalScumme uses the validated TensorFlow `nmp` SavedModel. Their absence produced misleading root-logger warnings but did not indicate a broken runtime.
- TensorFlow printed an informational CPU feature banner when inference first loaded the model.
- The isolated Python 3.11 worker used Windows `cp1252` for redirected stdout while Qt decoded the pipe as UTF-8, turning the ellipsis in `Analysing audio…` into `�`.
- Version 2.3.2 configures inference logging before importing Basic Pitch, forces `TF_CPP_MIN_LOG_LEVEL=2`, launches the worker with `-I -X utf8`, and emits ASCII-safe JSON. Actual inference errors remain visible.
- A complete run against the supplied 4:22 guitar MP3 finished in 36 seconds without those warnings or malformed text and produced the expected 1,328-note raw MIDI.

## Confirmed malformed third-party MIDI data-byte bug — 2026-07-13

- `E:\Users\james\Downloads\Rush E.mid` failed during Mido parsing with `data byte must be in range 0..127` before Song Transposer processing began.
- The file is a five-track, 19,043-note MIDI. Its first invalid event is a note-on at byte offset 25,410 with pitch 28 and velocity 129; legal MIDI data bytes are limited to 0..127.
- Mido's narrow `clip=True` recovery loads the complete 302.17-second file. Version 2.3.3 retries with that mode only for this exact error and exposes a recovery warning in the project and Song Transposer result.
- Undefined status bytes, invalid chunks, truncation, and all unrelated parse failures remain fatal.
- Clear Melody processes the recovered source into 1,709 non-overlapping notes in A2–E5, with 8,041 outliers removed, 1,109 octave repairs, four phrase stabilizations, and 43 remaining large jumps. Balanced planning retains 1,624 notes, drops 85, and emits 3,248 events.

## Confirmed UVR separation architecture and model choice - 2026-07-15

- Version 2.6.0 adds optional full-mix separation before Basic Pitch. Separation is source preparation only: it reads one selected audio file, atomically writes user-confirmed WAV stems, and never calls the planner, scheduler, input backend, or SCUM.
- Keep `audio-separator` and PyTorch in a second isolated Python 3.10-3.12 runtime. Do not install them into the main PySide application environment or the Basic Pitch/TensorFlow `audio-runtime`.
- The app runtime is `audio-separator 0.44.3`. NVIDIA installs pin official PyTorch `2.11.0+cu128` and torchvision `0.26.0+cu128`; CPU remains the slower fallback when no NVIDIA driver is present. A detected NVIDIA GPU must expose CUDA before the installer writes the readiness marker.
- Use `.musicalscumme-separation-ready-v1` as a success-only marker and `separation-runtime.path` under `%LOCALAPPDATA%\MusicalScumme` as the optional secondary-drive pointer. Repair must reuse installed packages and model files; do not restore `--force-reinstall` for the 2.75 GB CUDA wheel.
- The configured default model is `model_bs_roformer_ep_317_sdr_12.9755.ckpt`, friendly name BS-RoFormer Viperx-1297. Its validated file is 639,331,213 bytes with SHA-256 `5b84f37e8d444c8cb30c79d77f613a41c05868ff9c9ac6c7049c00aefae115aa`.
- Preserve both source-derived stems at deterministic visible paths: `<source>.vocals.wav` and `<source>.instrumental.wav`. Guitar / arpeggio defaults to transcribing instrumental; Smooth lead / vocal defaults to vocals. User-selected stem choices must survive later profile changes.
- A real 45-second House opening used CUDA autocast and batch size one, peaked near 7.57/8.19 GB GPU memory with SCUM also open, and completed without OOM. Keep MDXC segment 256, overlap 8, batch size one, atomic publication, and asynchronous QProcess chaining.
- On that opening, focused Basic Pitch produced 194 notes from the original mix and 208 from the Viperx instrumental. Against the user's existing isolated-guitar transcription, exact 90 ms attack matches improved from 129 to 159 raw; after Guitar / arpeggio cleanup they improved from 117/166 to 145/176, raising exact-match precision from 70.5% to 82.4%.
- Demucs v4 `htdemucs_6s` was also installed and evaluated because it is the only current audio-separator catalogue entry that emits a direct Guitar stem. Its cleaned 182-note lead matched only 124 reference attacks (68.1% precision), so do not replace the Viperx instrumental default merely because a model labels an output `Guitar`.
- UVR GUI 5.6.0 is installed separately at `E:\Applications\Ultimate Vocal Remover`; it is not bundled into MusicalScumme. The official installer SHA-256 is `3516daea39ccb9fead27e8ba5879375a08b20a428264a7c1be6db1be7765b0fe` and is not Authenticode-signed, so provenance remains the official GitHub release URL.

### `separation_tools.py` and `separation_worker.py`

- Discover the pointer-backed isolated runtime, model cache, validated marker, and bundled worker without importing ML packages into Qt.
- Launch the worker with `-I -X utf8`, load the configured model with CUDA autocast only when CUDA is actually available, and keep inference off the GUI thread.
- Publish both WAV stems through same-destination temporary files and replacement. Never silently overwrite them in the UI; one explicit confirmation covers both visible filenames.
- Always decode every supported input through FFmpeg to a temporary PCM S16LE/44.1 kHz/stereo WAV before model inference. `audio-separator` can otherwise inherit MP3's `MPEG_LAYER_III` subtype for a WAV output, log an export failure, leave zero-byte files, and still return success. Validate RIFF readability, frame count, channels, sample rate, and non-empty size before atomic publication.
- Feed only the selected completed stem into the existing audio worker, then run the unchanged deterministic Song Transposer processor. Direct audio-to-MIDI and MIDI-only paths remain available.

## Version 2.8.0 source-aware conversion rules - 2026-07-15

- The desktop default is **Optimal Sounding**. Guitar Smooth, Balanced, and Maximum Fidelity are obsolete policy names and migrate to Optimal Sounding. SCUM Safe and exact Custom settings remain supported.
- MIDI import immediately runs `score_optimizer.py`. It is deterministic, has no Qt/input/scheduler/audio dependencies, and must never generate notes, infer harmony, quantise pitches to a key, or rewrite the source file.
- Import track selection is lead-first and limited to one lead plus useful bass and harmonic support. Track scores use names, register, activity, monophony, and source chord evidence. Percussion-only and confidently named noise/effect tracks are excluded.
- Pre-2.8 remembered track selections are cleared once because they usually represent the old all-non-percussion default. Selections saved with `selection_strategy_version = 2` are user state and must be preserved.
- Score texture is melody, light polyphony, chord-led, or dense. Rolled sustained source chords use the same bounded recogniser as Game-optimised arrangement so they remain eligible for chord treatment.
- Optimal melody uses Lead melody, SCUM Pitch Match, one voice, no chord stagger, and short modifier timing. Light/chordal/dense scores use Game-optimised, automatic real-source chord recognition, Safe fold, and two or three voices based on density.
- Effective automatic values are plan-local. `build_playback_plan` copies `AppSettings`, records the resulting policy in diagnostics, and never mutates persisted settings.
- Playback speed and transpose remain visible basic controls. Full arrangement, mapping, filtering, chord, and physical-timing controls remain available under Custom only.
- Timing jitter is removed. Deterministic source timing is required for auditable score export and repeatable SCUM playback.
- `score_optimizer.analyse_project` groups notes by track once. Do not reintroduce a track-count multiplied by note-count import scan.
- Real-file static evidence: the malformed 19,043-note Rush E source selects Grand Piano plus Electric Piano, classifies dense, and produces a 2,010-note two-voice Optimal plan from 12,072 selected source notes. The 1,328-note isolated House guitar transcription classifies chordal and retains 1,265 notes with three-note chord capacity.
- Static analysis does not confirm in-game musical quality. The 2.8.0 policy and current-build input timing still require a supervised SCUM audition.

## Version 2.9.0 selective playback and scheduler rules - 2026-07-16

- Playback ranges live in `playback_sections.py`, not the scheduler or UI. The module is deterministic and may transform selected `MidiNote` timing only; it must not arrange music, map SCUM keys, send input, or mutate a source MIDI.
- A Play range defines included source time. When one or more Play ranges exist, their merged union is the base playback. Omit ranges are subtracted from that union; without Play ranges, omissions are subtracted from the complete source duration.
- Resolve and merge source intervals before scanning notes. A note overlapping a retained interval is clipped to that interval, and a sustained note crossing an omitted passage may become two source-backed fragments. Never create a new pitch or extend a note beyond its source timing.
- Rebase retained intervals into one playback timeline in source order. Insert `section_gap_ms` only between non-contiguous resolved intervals. The configurable range is 0-5000 ms and the maintained default is 500 ms.
- Apply playback selection before `arranger.py` and `planner.py`. Each excerpt must receive fresh arrangement analysis, a known base octave-bank state, and the complete retrigger/modifier safety schedule.
- Preserve the no-range path exactly. Clearing ranges restores complete selected-track playback without changing the MIDI or remembered track choices.
- Persist ranges by the resolved absolute MIDI path in `playback_sections_by_file`. Invalid, reversed, non-finite, or out-of-bounds saved entries must be ignored or clipped without resetting unrelated settings.
- Looping repeats the immutable prepared plan until Stop, F8, focus-loss stop, or application shutdown. Release all keys after every completed loop and on every exit path. Countdown runs once; `section_gap_ms` is also the repeat pause.
- Compile scheduler batches and integer nanosecond offsets once per start, then reuse them for every loop. Batch only events whose timestamps are equal within 0.0005 ms; preserve canonical event order and never collapse staggered notes.
- The Windows backend caches resolved virtual-key/scan-code data and may send an equal-timestamp batch through one `SendInput` call. Partial sends must update the tracked state only for accepted events so final cleanup can release them.
- Request 1 ms Windows timer resolution only while the playback worker is alive and always balance `timeBeginPeriod(1)` with `timeEndPeriod(1)` in `finally`.
- Record events sent, batches sent, late events, average/max dispatch lateness, and completed loops. Show final metrics in the UI; do not claim improved timing without measured runtime evidence.
- Disable track, section, Prepare, and export controls during active playback. Editing may resume only after the scheduler's finished callback.
- Static real-file evidence: combined House Play/Omit ranges resolve to 30-50 s, 90-98 s, and 101-115 s; 227 fragments remain from 1,328 notes, 1,101 are outside the selection, 18 cross a boundary, output span is 43 s, the Optimal plan retains 209 notes / 418 events, and final key state is balanced.

## Version 2.10.0 workflow safety and editing rules - 2026-07-17

- Active playback now locks the file field and browse/reload/convert actions; track, range, key-profile, input, conversion, mapping, timing, export, and reset controls; and every recent-file action. `load_file`, drag/drop, and conversion-dialog entry points also reject calls while the scheduler reports running.
- The running plan remains immutable and Pause, Stop, F8, focus-loss handling, Exit, and cleanup remain unaffected.
- Successful MIDI loads populate a ten-entry recent list in settings. Paths are resolved and deduplicated, failed loads never enter the list, and unavailable files stay visible as disabled entries rather than being pruned.
- Selecting a playback-section row copies its start/end into the time editors. Updating replaces those boundaries, preserves the range's existing Play/Omit mode and label, re-sorts, invalidates the previous plan, and saves the per-file state.

## Version 2.10.1 original-MIDI reliability and responsive workflow - 2026-07-18

- The user confirmed that ordinary use starts from untouched MIDI Find downloads rather than Song Transposer or `.scum-ready.mid` derivatives. The main window now presents direct MIDI import as the primary path and keeps optional conversion tools in the File menu.
- Standard non-zero MIDI release velocities previously left notes active until forced track-end cleanup. `midi_engine.py` now closes every real `note_off`, while sustain still defers the close until pedal-up and zero-velocity `note_on` remains equivalent.
- At the 1080×720 default, the former layout allocated only 39 px to the settings pane and expanded beyond the requested height. Compact playback-section rows, independent pane scrolling, wrapped forms, and bounded combo sizing now keep a 613/435 px split with no settings-pane horizontal scrollbar in the offscreen geometry test.
- Pause could release the backend while the playback thread was already entering `send_batch`, allowing a late key-down after cleanup. Scheduler backend calls now share one lock and recheck Pause/Stop inside it; the deterministic blocking-backend regression ends with no pressed keys.
- Real direct-MIDI evidence covers three untouched MIDI Find files from 452 to 8,473 source notes and 110 to 421 seconds. Every source SHA-256 remained unchanged and every plan ended with no pressed keys.
- The 2.10.1 Windows onedir package contains 236 files / 120,583,252 bytes, includes every required optional-audio support file, and stayed alive for an eight-second isolated offscreen launch. The validated ZIP SHA-256 is `ad61381e6ec4a99c85d6c94b3c9c55c2a1a19b4d9a0397cf3ac3c890382f7bd8`.
- Static and offscreen validation do not replace a supervised SCUM run. Focus-loss cleanup, Pause/Stop, F8, and musical quality remain unconfirmed in the current game build.

## Output-equivalent low-resource processing - 2026-07-27

- Song Transposer local pitch correction uses one ascending-time sliding histogram over the fixed 128-note MIDI pitch domain. Preserve the inclusive ±900 ms window, exact statistical median (including the mean of the two centre pitches), and existing same-pitch-class tie-breaking; do not restore a per-outlier pitch-list allocation and sort.
- Automatic performed-chord recognition evaluates growing candidate prefixes with incremental pitch-class, minimum-release, and minimum-duration state. This must remain exactly equivalent to the prior prefix-slice predicate and must not widen the recognition window or change which real source notes are grouped.
- These are output-equivalent resource optimisations only. Randomized regression tests compare the optimized paths against the previous formulations. A synthetic 20,000-core-note / 5,000-query median benchmark measured 43.625 s for the legacy list-and-sort path and 0.094 s for the sliding histogram on the development machine; the synthetic ratio is not a claim about whole-application or in-game speed.
- Regression risk: the sliding median relies on nondecreasing query times. `process_song_notes` sorts its working notes before querying; any future caller must preserve that ordering or introduce an order-independent wrapper.

## Planner stage separation - 2026-07-28

- Keep timed-note construction separate from physical SCUM key-event emission inside `planner.py`. The timing stage owns chord staggering, note holds, bank-transition scheduling, and same-key retrigger delays; the event stage owns note key events and standalone persistent-bank taps.
- Carry stage results through private immutable dataclasses rather than parallel local collections. These structures are implementation details and do not change the public planner API or stored plan format.
- Treat complete deterministic `PlaybackPlan` equality across every mapping mode as a refactor regression boundary.

## Explainable bank-aware mapping - 2026-07-28

- Custom planning can prioritise register fidelity, rhythm, or bank stability by adjusting the existing global dynamic-programming costs. No mode may generate pitches, infer harmony, or bypass the physical timing guards.
- An optional rolling bank-tap budget folds a target group into the current bank only when accepting its transition would exceed the configured taps per second. Zero preserves the legacy unlimited policy.
- Equivalent C-boundary mappings may explicitly prefer the lower or upper available bank. Automatic remains the compatibility default.
- SCUM-score rows carry human-readable mapping explanations. Initial bank preparation, budget folding, and final restoration are also reported in plan diagnostics.
- The 2.11.0 Windows onedir package contains 236 files / 120,590,394 bytes and passed an isolated eight-second offscreen launch. The 240-entry ZIP passed a complete read-through; its SHA-256 is `62bf07935bf31a8a1cf5e579d73eeede015ec0ffc09f492daaadd9f437c0c618`.
- Live SCUM behavior remains unconfirmed for the new policies. In particular, final base-bank restoration must be tested under supervision before it is described as validated in the current game build.

## Supervised in-game HUD - 2026-07-30

- Use a frameless Qt top-level window because Windows requires `FramelessWindowHint` for per-pixel translucency. Preserve Windows-standard minimize, maximize/restore, close, system drag, and eight-zone system resize behavior through compact custom chrome.
- Keep existing menus, shortcuts, widgets, and playback lock behavior while restyling the content as a semi-transparent tactical overlay.
- Use electric cyan as the only non-semantic accent. Reserve green and red for foreground/safety state and Stop; avoid additional decorative colors.
- Use layered alpha transparency and low-opacity hairlines for glass depth. Qt has no portable backdrop-filter API, so do not simulate blur by blurring child content or capture the game framebuffer.
- Keep the source deck, two-pane workspace, and playback command deck usable at 1080×720 with no horizontal scrolling in the settings pane.
- The 2.12.0 Windows onedir package contains 236 files / 120,596,122 bytes. The 236-entry ZIP uses one `MusicalScumme/` root, passed a complete read-through, and has SHA-256 `b4ca7fa2c241271f80602464ae9a3ebe7f8aa09e22d91a02a2e3bb18c7df8453`.
- Native Windows compositing was confirmed over a high-contrast test background. Live SCUM readability, focus-loss cleanup, Pause/Stop, F8, scheduler timing, and musical quality remain unconfirmed until supervised in-game testing.

## Supervised live MIDI keyboard - 2026-07-30

- `live_midi.py` is a separate real-time input boundary. The existing MIDI parser remains file-only, the planner remains look-ahead/offline, and `PlaybackScheduler` remains an immutable-plan scheduler.
- `python-rtmidi==1.5.8` supplies the maintained Windows MultiMedia input layer. The selected port is identified by its current index and exact name; a refresh is required after hotplug, and a running session stops instead of silently switching when that identity disappears.
- Native callbacks filter SysEx, timing, and active-sensing traffic, decode supported short messages, and enqueue only. One worker owns foreground checks, F8, device checks, live note state, and the keyboard backend.
- Live mapping is intentionally fixed to SCUM's base C4-C5 bank. Safe fold is the default and Strict C4-C5 is optional. Neither mode sends Ctrl/Shift, so users must put SCUM in its base octave before arming.
- Repeated notes and pitches folded to one physical key are reference-counted. Sustain CC64 is channel-specific, CC121 releases that channel's pedal-latched keys, and CC120/123 clear the complete live state.
- Scheduled playback and live input are mutually exclusive through disabled controls and direct method guards. The armed state is never persisted; only the preferred input name and live mapping controls are saved.
- A blocking-backend race test proves Stop cannot leave a late live key-down after cleanup. Physical hardware and current-build SCUM behavior remain unconfirmed because no MIDI input device was connected during development.
- The 2.13.0 Windows onedir package contains 241 files / 121,015,633 bytes and the native CPython 3.12 RtMidi extension. Its 49,612,788-byte ZIP has one portable `MusicalScumme/` root, passed a complete read-through, and has SHA-256 `a85d3d01a4c1e664a6f515969cf383d6cd2e221bbaf34036d51152275f582edb`.
- Deferred last-file loading uses a window-owned single-shot timer and close events must stop it. A context-free delayed callback can otherwise fire after its window closes and surface a stale modal load error.

## Whole-phrase source-backed conversion intelligence - 2026-08-03

- Version 3.0.0 supersedes greedy per-onset lead selection with deterministic whole-phrase dynamic programming. Candidate salience, pitch interval, source-track continuity, time gap, and phrase boundaries are evaluated together.
- Phrase boundaries are derived from the selected source's onset spacing and relax continuity penalties without moving note times or pitches. This preserves eligible structural register resets while suppressing isolated transient theft inside a phrase.
- Track-role semantics use tokens rather than arbitrary substrings. Automatic recommendation measures lead/support onset affinity, temporal overlap, register difference, and exact doubling before choosing at most one lead, useful bass, and useful support.
- Source texture now distinguishes musical onset rate from physical note-start load and records time-weighted sounding polyphony, overlap ratio, phrase count, and rhythmic variation.
- Secondary voices remain existing MIDI notes and are scored from the traced lead, prior support voice-leading, consonance, compactness, register role, duration, and velocity. Generated harmony remains prohibited.
- Optional track-name metadata was appended to the existing planner/arranger keyword interfaces. Existing callers using only notes, settings, profile, and `prepared_source` remain source-compatible.
- Real static evidence on the selected Rush E source reduced greedy lead transitions larger than one octave from 357 to 54 and source-track switches from 320 to 28. The raw House guitar transcription reduced large transitions from 437 to 221. These metrics prove structural continuity only; in-game musical quality remains unconfirmed until supervised audition.
- Source validation passed `python -m compileall -q .`, all 172 tests, and `ruff check .`. The suite includes offscreen construction of all maintained Qt windows, complete instrument-preparation coverage, source provenance, deterministic voice tracing, token-safe role selection, and the existing parser/planner/input/scheduler/audio safety regressions.
- The 3.0.0 Windows onedir package contains 237 files / 121,003,476 bytes, all required optional-runtime resources, and the native RtMidi extension. Its portable ZIP passed a complete 237-entry read-through with one `MusicalScumme/` root and zero backslash paths; ZIP SHA-256 is `3bfd3947c062709245c14ad79bf5d53f7f7a08e16f8c2bcbe17ea3b9c13c1187`.

## Dynamic Solo Director - 2026-08-03

- Version 3.1.0 adds deterministic rolling-window lead evidence on top of the 3.0 whole-phrase trace. A sparse alternate lead can become a protected solo segment even while the primary vocal or melody continues at the same attacks.
- Solo Focus retains the source solo plus at most one lower foundation voice, excludes competing upper material, bypasses performed-chord alignment, and suppresses planned chord stagger.
- Fast-run reduction keeps endpoints, velocity accents, extrema, direction changes, spacing changes, and regular phrase landmarks ahead of connective attacks while retaining the existing physical density ceiling.
- Optimal Sounding uses plan-local `solo_adaptive` mapping only when protected segments exist: accompaniment remains Safe Fold, each solo receives its own whole-octave fit and melody-contour bank path, and the existing standalone Ctrl/Shift safety schedule remains authoritative.
- Import analysis can retain primary lead, sectional solo handoff, bass, and support as a four-track source set. Exact doubles and two simultaneous lead tracks without sectional evidence remain excluded.
- Source validation passed `python -m compileall -q .`, all 177 tests, and `ruff check .`. Focused tests cover continuous-primary handoff, sparse-primary direction, solo ducking, sparse handoff recommendation, fast-run landmark preservation, exact solo mapping, zero solo stagger, and the complete prior safety suite including offscreen Qt construction.
- Real-file Optimal Sounding probes selected Hotel California tracks 0/4/6 and resolved five broad solo passages with 329 solo-mapped notes, while Stairway to Heaven tracks 1/2/3 resolved eight passages with 425 solo-mapped notes. A single-track Free Bird acoustic score correctly remained on its ordinary non-solo plan. These are static arrangement checks, not in-game auditions.
- The final 3.1.0 Windows onedir package contains 237 files / 121,021,765 bytes, all required optional-runtime resources, and the native RtMidi extension. The executable remained alive through an eight-second offscreen smoke launch and has SHA-256 `ec391e4582c4bc6e19b777bfd8850aa7febba5d8f3fcc0314b00d70e4d9234c9`.
- `MusicalScumme-3.1.0-Windows.zip` contains one `MusicalScumme/` root, 237 files, zero backslash entries, and passed a complete 121,021,765-byte read-through. ZIP size is 49,621,652 bytes; SHA-256 is `aa4e5f94056dc00b0bd03fbab72753a7bea6753aa86d7c127313b6f5aef0c386`.
- The 3.1.0 `SHA256SUMS.txt` source manifest contains 100 files and excludes generated build, release, environment, cache, spec, manifest, and bytecode paths; every listed digest revalidated after the final documentation update.
- Live musical balance, bank-transition audibility, focus cleanup, and F8 behavior remain unconfirmed until the 3.1.0 package is supervised inside the current SCUM build.

## Guided Command Deck UX - 2026-08-03

- Version 3.2.0 derives a four-stage Load MIDI, Review Tracks, Prepare, and Play rail from existing UI state. The readiness pill and next-action text are presentation only and do not enter MIDI parsing, source analysis, arrangement, planning, scheduling, or input.
- Prepare, Play, Score CSV, and Events CSV stay disabled until an existing MIDI has a selected populated track. One-click Play still prepares automatically after plan invalidation, and live-controller arming remains independent from MIDI-file readiness.
- Track filtering searches visible table metadata without changing selection or persistence. The HUD reports selected/populated and filtered-visible counts, disables empty track checkboxes, supports double-click toggling, and preserves relationship-aware recommendation restoration.
- Prepared output is a scannable three-line result with selectable bullet advisories. Planning displays indeterminate progress and a wait cursor but remains a no-output operation.
- Audio-to-MIDI and Song Transposer expose inline readiness for source, destinations, isolated runtimes, overwrite separation, and UVR requirements while retaining defensive validation in their action handlers. Editable operation controls lock during asynchronous workers.
- Custom-key validation runs before dialog acceptance and keeps invalid key names visible for correction.
- Song Transposer settings scroll vertically at 880×720 with no horizontal scrollbar; its progress, log, and commands remain reachable. The main HUD remains exactly 1080×720 with 618/439 px panes and the compact playback overlay remains no wider than 580 px.
- Ctrl+P Prepare, Ctrl+L source focus, F1 Quick Start, Delete section removal, action status tips, accessible names/descriptions, and shortcut/safety help are maintained behaviors. Existing Ctrl+O/Ctrl+R and global F8/F9/F11 behavior is unchanged.
- Source validation currently passes all 181 tests, including 15 offscreen UI tests covering readiness, filtering, inline validation, accessibility, active-output locks, live MIDI, responsive geometry, and every maintained window.
- The final 3.2.0 Windows onedir package contains 237 files / 121,035,295 bytes, all required optional-runtime resources, and the native RtMidi extension. Its 4,421,399-byte executable remained alive through an eight-second offscreen smoke launch and has SHA-256 `7e794414d4059ac02542b3ef8c76078459761f30020601ce919a237231d32d19`.
- `MusicalScumme-3.2.0-Windows.zip` contains one `MusicalScumme/` root, 237 files, zero backslash entries, and passed a complete 121,035,295-byte read-through. ZIP size is 49,634,805 bytes; SHA-256 is `e5dbfdaf688f1e28ff03488a084fd19f253a00e2d610df47f0bc845ef65493c5`.
- The 3.2.0 `SHA256SUMS.txt` source manifest contains 101 files and excludes generated build, release, environment, cache, spec, manifest, and bytecode paths; every listed digest revalidated after the final documentation update.
- The available 1,328-note House guitar transcription revalidated both processor profiles without writing output: Clear Melody retained 865 notes, made 29 octave repairs including nine phrase stabilizations, and kept 65 large jumps; Guitar / arpeggio retained the same notes, made 20 contextual repairs without phrase stabilization, and preserved 81 structural large jumps. Both leads remained monophonic with zero overlaps and produced complete current Optimal plans.
- Live text contrast, overlay readability/placement, keyboard focus visibility, focus cleanup, and F8 behavior remain unconfirmed until the 3.2.0 package is supervised over representative bright and dark current-build SCUM scenes.

## Custom density experiments - 2026-08-12

- Custom mode permits up to 26 source-backed notes per onset, 240 note starts/s, and 250 ms chord stagger. These are opt-in limits; named presets and the default three-note/18-starts-per-second behavior remain unchanged.
- The 26-note ceiling is an experimental source-retention limit; the maintained physical profiles still expose 13 note keys, so notes may collide or be dropped during physical planning. More than three simultaneous keys remains experimental and may cause missed or late SCUM input.
- Custom-mode guidance explains the density/reliability tradeoff and recommends the existing lower defaults for dependable play.

## Instrument-aware sustain preparation - 2026-08-01

- The conversion panel now requires an explicit target instrument: Guitar, Harmonica, or Banjo. The selection is persisted, plan-affecting, and locked with the other conversion controls during playback.
- Optimal Sounding derives its maximum hold from source-note duration up to the selected instrument ceiling instead of using one universal 1,000 ms upper bound.
- Final timed-note planning enforces Guitar 2,000 ms, Harmonica 4,000 ms, and Banjo 1,000 ms as wall-clock played-note ceilings after playback speed and velocity expression are applied.
- Instrument preparation shortens releases only. It never moves an attack, changes a pitch, creates a note, rewrites source MIDI, or bypasses retrigger and octave-bank safety.
- Plans disclose the instrument, hard sustain ceiling, number of capped notes, and total removed sustain in diagnostics and surface a preparation warning when long notes are shortened.
- The prepared-plan UI distinguishes the plan's effective maximum hold from the instrument's hard ceiling and reports total instrument-driven sustain reduction rather than only a capped-note count.
- `target_instrument` remains the final `AppSettings` dataclass field to preserve every pre-existing positional argument. Persisted mixed-case or whitespace-padded values normalize to the same canonical profile.
- Second-pass source validation passed `python -m compileall -q .`, all 165 tests, and `ruff check .`. The offscreen Qt suite constructed the main window and conversion dialogs, retained the 1080×720 layout constraints, and verified plan invalidation, effective-limit reporting, legacy settings compatibility, and emitted key-hold ceilings across every mapping mode.

## GUI Opacity, Auto-Compact Playback & Portable Config Update - 2026-08-21

- The main full GUI is now completely opaque (`#080f14` surface background and solid panel styling), removing transparency while preserving frameless window controls, rounded corners, and the cyan HUD design system.
- Mini mode (compact playback overlay) now uses a much higher opacity dark slate glass (`rgba(7, 13, 18, 220)` surface and `rgba(12, 22, 29, 225)` frames, ~86-88% opacity), providing high contrast and readability over bright in-game scenes rather than being washed out or see-through.
- Pushing Play now automatically displays the small GUI (compact playback HUD) instead of minimizing to the Windows taskbar (`minimize_on_start` defaults to `False`).
- All configuration and log files (`settings.json`, `settings.json.bak`, `musical_scumme.log`) are now stored in the portable application directory alongside the executable / application root (on non-C: drives where the app is installed/run) rather than in `%APPDATA%`.
- Existing configuration files from `%APPDATA%\MusicalScumme` were migrated to the application directory and automatic legacy migration is supported when upgrading.
- Source validation passed `python -m compileall -q .`, all 183 automated tests, and `ruff check .`.

## Output & Handling Quality Upgrade - 2026-08-29

- **Sub-Millisecond Dispatch Precision (`scheduler.py`)**: Replaced quantum-yielding `time.sleep(0)` with a hybrid 1ms high-resolution timer sleep and final micro spin-wait loop (`time.perf_counter_ns()`), reducing dispatch lateness jitter under Windows game load to < 0.05 ms.
- **Real-Time Playback Telemetry (`scheduler.py` & `ui.py`)**: Added `TimecodeCallback` to `SchedulerCallbacks` and `UiSignals.timecode` emitting elapsed milliseconds and plan duration in real time.
- **In-Game Compact HUD Upgrade (`ui.py`)**: The compact overlay HUD (which displays automatically during playback) now features a dedicated tactical telemetry bar with:
  - Active song title badge with automatic length truncation.
  - Live status badge (`PLAYING · LOOP 1`, `PAUSED`, `SCUM UNPAIRED`, `STARTING IN 3s`, `STOPPED`).
  - Real-time timecode formatted as `elapsed / total (-remaining)` (e.g., `01:23 / 03:45 (-02:22)`).
  - One-click `⤢` expand button to easily restore the full editor window during playback without interrupting the song.
- **Track Ergonomics & Filtering (`ui.py`)**:
  - Added "Invert" track selection button (`invert_tracks_button`) alongside "All", "None", and "Auto-select musical".
  - Enabled keyboard Spacebar toggle on the track list (`_track_table_key_press`).
  - Track filter overview reports matching counts dynamically (`e.g., "3 of 12 populated selected · showing 4 of 16"`).
  - Live MIDI session reports real-time activity and triggers live note status updates.
- **Musical Arranger & Voice-Leading Improvements (`arranger.py`)**:
  - Enhanced bass foundation candidate detection to cover close-position chords and lower-register melodies ($\ge 3$ semitones below lead) rather than falling back to unweighted harmony.
  - Expanded consonance interval scoring in support voices to reward octaves, unisons, fifths, fourths, thirds, and sixths without inventing notes.
- **Playback Seeking Hotkeys (Numpad 4 / Numpad 6)**:
  - Added global asynchronous polling and application shortcuts for **Numpad 6** (seek forward +5.0s) and **Numpad 4** (seek backward -5.0s).
  - Implemented `PlaybackScheduler.seek_by(delta_ms)` and `seek_to(target_ms)`.
  - Seeking instantly releases currently held keys (`_release_all()`) to ensure zero stuck notes in SCUM.
  - Seeking works seamlessly both during active playback and while paused (updating timecode, progress bar, and HUD status immediately).
  - Updated compact HUD shortcut hint to `F8 STOP · F9 · 4/6 · F11`.
- **Pitch Mapping Methods Enhancement (`planner.py`, `config.py`, `ui.py`)**:
  - All 5 original mapping modes are preserved 100% intact: `fold`, `strict`, `smart3`, `melody3`, and `match3`.
  - Added 5 enhanced mapping modes available individually:
    1. **`fold_smart` (Enhanced Fold)**: Resolves octave unison chord collisions within C4-C5 range (e.g. C3 bass + C4 lead spreading to 60/72).
    2. **`strict_auto` (Enhanced Strict)**: Automatically centers low/high scores into C4-C5 with optimal global octave transposition so notes are never discarded.
    3. **`smart3_harmonic` (Enhanced Intelligent 3-Octave)**: Rest-aware modifier cost discounting (down by 75% across $\ge 250\text{ms}$ gaps), $2.2\times$ 2-step jump penalty, and $2.2\times$ priority on bass root and melody apex registers.
    4. **`melody3_contour` (Enhanced Melody Contour)**: Preserves scalar melodic continuity and locks apex landmark notes in upper registers.
    5. **`match3_adaptive` (Enhanced Pitch Match)**: Multi-objective density and center-of-mass shift optimization.
- **Verification**: Complete suite passed with 195 automated tests, `python -m compileall -q .`, and `ruff check .`.


## Arrangement selection expansion — 2026-09-09

- User normally selects every non-percussion track. Design selection guidance and audition fixtures around this full-ensemble workflow.
- Added opt-in `adaptive_lead`: whole-phrase lead tracing across selected tracks, one source note per onset. Existing `melody` remains confined to the inferred lead track.
- Added opt-in `melody_bass`: traced lead plus at most one existing lower foundation note (at least three semitones below lead); never fill a missing bass with upper harmony. Maximum polyphony of one still wins. Both new modes retain exact source attacks and existing filtering/density limits.
- Arrangement identities and guidance are centralized in `arrangement_options.py`. Vocal chord recognition is now correctly enabled in the UI, matching existing arranger behavior. Named performance presets remain unchanged; choose Custom for these manual options.
- New automated scenarios and `docs/ARRANGEMENT_TEST_CONCEPTS.md` cover source provenance, voice ceilings, missing bass, track handoffs and supervised full-ensemble comparisons.
- Current SCUM audition and representative MP3/WAV/M4A Basic Pitch conversion have not been repeated.

- Validation: 253 tests passed, Ruff and compileall passed, including offscreen main window and audio dialog construction. Windows onedir executable built in `release-staging/arrangement-20260909/MusicalScumme/` and survived an eight-second isolated offscreen startup with no logged exception. EXE SHA-256: `fd815c8fac80df6bbfccea8076a60953a50ad56965f5eb6434834888c0994135`. Three original eight-second MIDI concepts and audition notes are included alongside the executable.

## Vocal-first arrangement suite — 2026-09-09 / 3.4.0

- User strongly prefers vocal melody-heavy arrangements and generally selects every non-percussion track. Added 18 opt-in style recipes (24 total arrangement choices), including ten vocal recipes and piano, acoustic, rock, electronic, classical, jazz and ensemble textures. Recipe layer ceilings range from one to six notes per attack and remain bounded by Maximum chord notes and existing physical limits.
- Suite choices use exact source attacks, deterministic whole-phrase lead tracing, unique source pitches and texture-specific accompaniment ranking. No generated chords, scale snapping, game input or source MIDI rewriting occurs in arrangement.
- A named main/lead vocal takes precedence over backing vocals and louder instrumental layers. Sustained chosen vocal notes reserve the lead role between attacks; Spotlight omits intermediate accompaniment, while layered recipes retain only support until the vocal actually rests.
- Appended `arrangement_lead_track=-1` for explicit suite lead selection. UI offers selected populated non-percussion tracks; it resets stale choices on another song or deselection, preserves same-file reload, switches to Custom, invalidates preparation and locks during output. This override affects new suite recipes only. Missing named vocals fall back to inferred melody with explicit guidance.
- Four-to-six-layer recipes are opt-in experiments and may lose notes through physical collisions or bank changes. Named presets, prior arrangement modes, default density/retrigger values and optional isolated audio processing remain unchanged.
- Current-game SCUM audition and representative Basic Pitch MP3/WAV/M4A validation remain pending. Automated selection metrics do not establish musical quality.

- Release validation: 580 tests passed; compileall and Ruff passed. Final 3.4.0 Windows executable survived an eight-second isolated offscreen launch. Package: release-staging/3.4.0-vocal-suite/MusicalScumme/ (keep entire folder). EXE SHA-256: A6894124C02B2BCF451D6C809907961B39880052FB772D52458C3B2E4CA1C8A1. Includes arrangement guide and five vocal ensemble MIDI examples for 1/2/4/8/16 source tracks.

## Smart auto track selection — 2026-09-10 / 3.4.1

- User disliked Auto-select musical and prefers vocal melody-heavy arrangements. Smart auto-select now receives the current arrangement settings, prioritises a substantial named main vocal over backing vocals and instrument-name hints, and honours the suite's explicit lead-track choice.
- Source pool size follows the arrangement: Spotlight/lead one, Melody + bass two, and recipe support pools up to six plus one eligible sectional handoff. Source alternatives remain independent from Maximum chord notes; no user timing, polyphony, mapping or preset values are changed.
- Handoff evidence now checks actual held lead notes, so offbeat accompaniment under a sustained singer is not mistaken for a vocal rest. Pairwise support overlap merges sounding intervals rather than using a first/last-note envelope.
- Duplicate screening covers all selected roles and detects mostly identical octave doubles. Whole-track overlap is required so complementary source sections remain eligible. Non-octave harmony remains available.
- Prepared-source shortcut applies only when all eligible musical tracks have recognized prepared names; an ordinary Lead Melody track no longer hides bass and accompaniment. Noise-only source no longer reselects rejected FX tracks as fallback.
- UI shows selected/excluded reasons in track tooltips and overall rationale in advisories. Smart auto-select recomputes on explicit click, has a direct active-output guard and preserves Custom settings. Remembered selections, including deliberately empty selection, remain until the user requests new selection. Do not bump the existing selection migration version or erase saved source choices for this upgrade.
- MIDI source bytes, arranger/planner separation, physical reliability limits and isolated optional audio runtime remain unchanged. Current-build SCUM audition and representative Basic Pitch MP3/WAV/M4A inference are still pending.

- Source verification: 624 tests passed, including all offscreen Qt windows and new smart-selection regressions; compileall and Ruff passed. Source track pools intentionally follow recipe roles independently of the physical polyphony ceiling.

- Packaged release: release-staging/3.4.1-smart-auto/MusicalScumme/MusicalScumme.exe; eight-second isolated offscreen startup passed with no logged error. EXE SHA-256: 8FFFC8FA38B46DBBB30F61D6ECFC69FE9A73BB5F0C41D94F62386FD0E541F3FF. Keep the complete application folder together.


## Single-file sharing option - 2026-09-11 / 3.5.1

- User requested a self-contained executable. Built `release-staging/3.5.1-onefile-20260911/MusicalScumme.exe` using the existing `-OneFile` build option, without application behavior changes. Size: 39,312,524 bytes. SHA-256: `9f13647ffc37b1455dce38e933d79d070dd0bd9f41f6f0c1ddb0d9263f975196` (adjacent checksum file included).
- No adjacent `_internal` folder is required. PyInstaller extracts bundled libraries/resources into a temporary directory at startup. Settings and logs still persist beside the executable; optional audio runtimes remain separately installed.
- Frozen modules, native RtMidi extension presence, and byte-identical optional worker/installer resources verified. Basic Pitch/TensorFlow/Torch remain excluded from the main module archive. Fifteen-second isolated offscreen startup passed without logged errors. Prior same-source 740-test, compileall and Ruff results apply. Unsigned; current-game SCUM, clean-account, physical controller and fresh representative audio inference validation remain pending.
