# MusicalScumme 3.3.1 validation

## Arrangement and Conversion Fidelity Enhancements

- Mandatory source validation passed: `python -m compileall -q .`, all 226 tests, and `ruff check .`.
- Octave bank seek synchronization: verified batch-level bank tracking (`bank_after`), live seek synchronization taps, deferred synchronization while paused, and loop zero-bank reset.
- Unison C voicing resolution: verified that identical C4 unison attacks stay unified at C4 while distinct source octaves spread across C4 and C5 boundary keys.
- Melody contour landmark protection: verified preservation of local contour peaks, valleys, endpoints, and accents under density caps.
- Audio-to-MIDI transcription cleaning: verified suppression of harmonic body overtone artifacts (+12, +19, +24 st) and sub-bass rumble, micro-strum consolidation (15–35 ms), and IOI-based tempo estimation.
- UI enhancements: verified offscreen construction of `MappingComparisonDialog` and the "Auto / Recommend" transpose control.

## Windows 3.3.1 package

- `build_exe.ps1 -OutputRoot release-staging\3.3.1` completed with PyInstaller 6.22.0 and Python 3.12.10.
- The onedir package contains 219 files / 96,583,010 bytes, including native RtMidi and isolated audio worker resources.
- The executable has SHA-256 `db3659d8a737d6f8fbfcb50a317ac3b92e3aaf977b6508389e20453f0ab48e92` and remained alive through an isolated offscreen smoke launch.
- Portable ZIP: `release-staging\3.3.1\MusicalScumme-3.3.1-Windows.zip`.
- ZIP verification: 219 files, zero backslash paths, size: 38,997,161 bytes, SHA-256: `a4820e0d291ba73bdf1a118db3e49a41c15720b9f96b336746ece4f0823bfd1f`.

Validation date: 2026-09-07

---

# MusicalScumme 3.3.0 validation

## Enhanced mappings and resource optimisation

- Mandatory source validation passed: `python -m compileall -q .`, all 212 tests, and `ruff check .`.
- Offscreen Qt verification covers all maintained windows and dialogs under `QT_QPA_PLATFORM=offscreen`.
- Performance benchmark on 5,400 notes: arrangement time fell from ~0.40s to ~0.21s (~48% reduction) and peak Python allocation dropped by ~16%.
- Seeking event lookup optimized with binary search while strictly preserving seek semantics and dispatch timing.
- Added 45 complete-plan regression snapshots covering all enhanced mappings, three arrangements, and three transpositions. Enhanced Pitch Match additionally exposes global shift and exact/folded counts.
- Packaging hooks excluded unused Qt PDF and virtual-keyboard plugin stacks.

## Windows 3.3.0 package

- `build_exe.ps1 -OutputRoot release-staging\3.3.0` completed with PyInstaller 6.21.0 and Python 3.12.10.
- Recursive PyInstaller inspection confirmed `ui`, `arranger`, `score_optimizer`, `planner`, `instrument_profiles`, `live_midi`, and `song_processor`. The onedir package contains 225 files / 100,208,349 bytes, including native RtMidi and all audio/separation worker, installer, validator, requirements, and constraints resources.
- The executable has SHA-256 `22018975e116b7278e483365040f512ed32abb1d1d988b38c29142ef6678b875` and remained alive through an eight-second isolated offscreen smoke launch.
- Portable ZIP: `release-staging\3.3.0\MusicalScumme-3.3.0-Windows.zip`.
- ZIP verification: one `MusicalScumme/` root, 225 files, zero backslash paths, every required resource present, and all 100,208,349 uncompressed bytes read successfully. ZIP size: 40,495,741 bytes. SHA-256: `8f494775038450899e927912232a1c90dfa698b42796bf41648273f4d1c363c8`.
- `SHA256SUMS.txt` was regenerated as a 105-file source manifest; every listed digest revalidated successfully and build, release, virtual-environment, cache, generated-spec, manifest, and bytecode paths are excluded.
- Current-build SCUM text contrast, translucent readability, compact-HUD placement, focus cleanup, F8 emergency stop, live-controller behavior, and musical output remain unconfirmed until supervised in-game testing.

Validation date: 2026-09-07

---

# MusicalScumme 3.2.0 validation

## Guided Command Deck UX

- Mandatory source validation passed: `python -m compileall -q .`, all 181 tests, and `ruff check .`.
- The 15-test offscreen Qt suite covers all maintained windows plus initial readiness, prerequisite-aware actions, view-only track filtering, selected/visible counts, empty-track protection, double-click selection, relationship-aware recommendation restore, prepared Ready state, inline audio validation, invalid custom-key correction, accessibility metadata, range editing, active-output locking, live MIDI, and compact HUD restoration.
- The main HUD remains exactly 1080×720. Its panes measure 618/439 px, the settings pane has no horizontal scrollbar, and the complete command deck fits without increasing the 996 px minimum-size hint.
- The compact playback overlay continues to show Pause/Resume, Stop, progress, chrome, and hotkey guidance below the maintained 580 px width.
- Song Transposer remains exactly 880×720 when requested. Its settings use a 850×455 px vertical viewport, the vertical scrollbar appears when needed, no horizontal scrollbar appears, and the log/actions remain reachable.
- Prepared output from `examples/scum_test_scale.mid` reached the Ready workflow state with the existing deterministic planner result and readable bullet advisories. No arranger, score optimiser, planner, instrument, input, scheduler, live MIDI, or audio-worker policy changed.
- The available 1,328-note House guitar transcription was reprocessed in memory. Clear Melody retained 865 notes in D2–A4, removed 230 outliers, made 29 octave repairs including nine phrase stabilizations, retained 23 sub-80 ms inter-attack gaps, produced zero lead overlaps and 65 large jumps, and yielded an 865-note / 2,548-event current Optimal plan. Guitar / arpeggio retained the same 865 notes/range/outliers and 23 rapid gaps with zero overlaps, made 20 contextual repairs and no phrase stabilization, preserved 81 structural large jumps, and yielded an 865-note / 2,584-event Optimal plan.

## Windows 3.2.0 package

- `build_exe.ps1 -OutputRoot release-staging\3.2.0` completed with PyInstaller 6.21.0 and Python 3.12.10. Dependency-update network retries were unavailable in the sandbox, but every pinned dependency was already satisfied and the build completed successfully.
- Recursive PyInstaller inspection confirmed `ui`, `arranger`, `score_optimizer`, `planner`, `instrument_profiles`, `live_midi`, and `song_processor`. The onedir package contains 237 files / 121,035,295 bytes, including the native RtMidi extension and every required audio/separation worker, installer, validator, requirements, and constraints resource.
- The 4,421,399-byte executable has SHA-256 `7e794414d4059ac02542b3ef8c76078459761f30020601ce919a237231d32d19` and remained alive through an eight-second isolated offscreen smoke launch.
- The final packaged Basic Pitch validator passed with isolated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model. The packaged UVR validator passed with audio-separator 0.44.3, PyTorch 2.11.0+cu128, CUDA on the RTX 2070 SUPER, ONNX GPU 1.27.0, FFmpeg, and the pinned Viperx model.
- `MusicalScumme-3.2.0-Windows.zip` contains 237 files / 121,035,295 uncompressed bytes, one `MusicalScumme/` root, zero backslash paths, and every required resource. Every entry passed a complete byte read-through. ZIP size: 49,634,805 bytes. SHA-256: `e5dbfdaf688f1e28ff03488a084fd19f253a00e2d610df47f0bc845ef65493c5`.
- `SHA256SUMS.txt` was regenerated as a 101-file source manifest; every listed digest revalidated successfully and build, release, virtual-environment, cache, generated-spec, manifest, and bytecode paths are excluded.
- Audio/separation inference code did not change, so representative MP3, WAV, M4A, and full UVR inference were not rerun. Their installed runtimes and packaged validation resources passed compatibility checks.
- Current-build SCUM text contrast, translucent readability, compact-HUD placement, focus cleanup, F8 emergency stop, live-controller behavior, and musical output remain unconfirmed until supervised in-game testing.

Validation date: 2026-08-03

---

# MusicalScumme 3.1.0 validation

## Dynamic Solo Director

- Mandatory source validation passed: `python -m compileall -q .`, all 177 tests, and `ruff check .`.
- The complete suite includes offscreen construction of the maintained 1080×720 HUD, Audio-to-MIDI dialog, and Song Transposer; every Guitar/Harmonica/Banjo sustain ceiling; every mapping mode; and the existing parser, scheduler, input, live MIDI, settings, export, and optional-runtime safety regressions.
- New focused coverage proves a solo can take ownership while the primary lead continues, a sparse whole-song primary can still receive Solo Focus, competing upper voices are ducked, the solo track remains monophonic, fast-run endpoints/accents/extrema survive density reduction, sparse handoff tracks are recommended without accepting simultaneous doubles, solo chord stagger is zero, and solo-adaptive bank planning remains deterministic.
- Real-file Optimal Sounding checks used the untouched downloaded Hotel California, Stairway to Heaven, and Free Bird Acoustic MIDI files. Hotel selected tracks 0/4/6 and produced 2,317 planned notes / 4,966 events with five protected passages, 329 solo-mapped notes, 954 ducked competitors, and 166 bank taps. Stairway selected tracks 1/2/3 and produced 2,244 notes / 4,680 events with eight protected passages, 425 solo-mapped notes, 317 ducked competitors, and 96 bank taps. Single-track Free Bird produced its ordinary 1,215-note / 2,430-event Fold plan with no artificial solo segment.
- The real-file checks caught and fixed an early false-positive policy that treated bass/support phrases as fragmented solos. Final unnamed handoffs require sustained monophony, section-local prominence, and a lead-credible register; token-safe explicit solo labels remain eligible at lower registers.

## Windows 3.1.0 package

- `build_exe.ps1 -OutputRoot release-staging\3.1.0` completed with PyInstaller 6.21.0 and Python 3.12.10.
- Recursive PyInstaller inspection confirmed `arranger`, `score_optimizer`, `planner`, `instrument_profiles`, `live_midi`, and `ui`. The onedir package contains 237 files / 121,021,765 bytes, including `_internal\rtmidi\_rtmidi.cp312-win_amd64.pyd` and every required audio/separation worker, installer, validator, requirements, and constraints file.
- The 4,407,869-byte executable has SHA-256 `ec391e4582c4bc6e19b777bfd8850aa7febba5d8f3fcc0314b00d70e4d9234c9` and remained alive through an eight-second isolated offscreen smoke launch.
- The final packaged Basic Pitch validator passed with isolated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model. The packaged UVR validator passed with audio-separator 0.44.3, PyTorch 2.11.0+cu128, CUDA on the RTX 2070 SUPER, ONNX GPU 1.27.0, FFmpeg, and the pinned Viperx model.
- `MusicalScumme-3.1.0-Windows.zip` contains 237 files / 121,021,765 uncompressed bytes, one `MusicalScumme/` root, zero backslash paths, and every required resource. Every entry passed a complete byte read-through. ZIP size: 49,621,652 bytes. SHA-256: `aa4e5f94056dc00b0bd03fbab72753a7bea6753aa86d7c127313b6f5aef0c386`.
- `SHA256SUMS.txt` was regenerated as a 100-file source manifest; every listed digest revalidated successfully and build, release, virtual-environment, cache, generated-spec, manifest, and bytecode paths are excluded.
- Audio and separation inference code did not change, so representative MP3, WAV, M4A, and full UVR inference were not rerun. Their installed runtimes and packaged validation resources passed compatibility checks.
- Current-build SCUM playback, focus cleanup, F8 emergency stop, live-controller behavior, bank-transition audibility, and musical solo balance remain unconfirmed until supervised in-game testing.

Validation date: 2026-08-03

---

# MusicalScumme 3.0.0 validation

## Whole-phrase conversion intelligence

- Mandatory source validation passed: `python -m compileall -q .`, all 172 tests, and `ruff check .`.
- The complete suite includes offscreen construction of the main 1080×720 HUD, Audio-to-MIDI dialog, and Song Transposer, plus every Guitar/Harmonica/Banjo instrument ceiling across Fold, Strict, Pitch Match, Melody Contour, and Smart mapping.
- New focused coverage proves token-safe role names, no forced two-track bass, doubled-part rejection, separate onset/physical-load analysis, transient-resistant whole-phrase tracing, real phrase-boundary register resets, deterministic source-note provenance, and no generated pitches.
- On the selected Rush E source, whole-phrase tracing reduced lead transitions larger than one octave from the former greedy path's 357 to 54, mean interval from 3.716 to 1.592 semitones, and source-track changes from 320 to 28.
- On the raw 1,328-note House guitar transcription, large lead transitions fell from 437 to 221 and mean interval from 16.656 to 10.599 semitones. This remains approximate transcription and is not treated as score reconstruction.
- Planning the 13,358-note recommended Rush selection took approximately 0.6 seconds on the development machine and produced a deterministic 2,152-note / 4,304-event Optimal plan.

## Windows 3.0.0 package

- `build_exe.ps1 -OutputRoot release-staging\3.0.0` completed with PyInstaller 6.21.0 and Python 3.12.10.
- Recursive PyInstaller inspection confirmed `score_optimizer`, `arranger`, `planner`, `instrument_profiles`, `live_midi`, and `ui`. The onedir package contains 237 files / 121,003,476 bytes, including `_internal\rtmidi\_rtmidi.cp312-win_amd64.pyd` and every required audio/separation installer, validator, worker, requirements, and constraints file.
- The 4,389,580-byte executable has SHA-256 `7ab303178dba0576dc945a360da7425cdf7b16ef958eb2a425e33700c6d1838a`.
- The packaged executable stayed alive through an eight-second isolated offscreen launch and logged a clean MusicalScumme 3.0.0 startup.
- `MusicalScumme-3.0.0-Windows.zip` contains 237 files / 121,003,476 uncompressed bytes, one `MusicalScumme/` root, zero backslash paths, and every required resource. Every entry passed a complete byte read-through. ZIP size: 49,601,061 bytes. SHA-256: `3bfd3947c062709245c14ad79bf5d53f7f7a08e16f8c2bcbe17ea3b9c13c1187`.
- `SHA256SUMS.txt` was regenerated as a 99-file source manifest; every listed digest revalidated successfully and build, release, virtual-environment, cache, generated-spec, and bytecode paths are excluded.
- Audio/separation inference code did not change, so representative MP3, WAV, M4A, and UVR inference were not rerun. Their isolated runtimes and bundled launch resources remain covered by the complete automated suite and package inspection.
- Current-build SCUM playback, focus cleanup, F8 emergency stop, live-controller behavior, and musical quality remain unconfirmed until supervised in-game testing.

Validation date: 2026-08-03

---

# MusicalScumme 2.13.0 validation

## Supervised live MIDI keyboard

- Source validation passed: compileall, 155 tests, Ruff, and offscreen Qt construction coverage.
- The live MIDI suite covers balanced note-on/note-off handling, zero-velocity note-on, repeated notes, fold and duplicate-binding collisions, sustain/reset/all-notes controllers, channel filters, transpose, the three-key default limit, late callbacks, blocked dispatch, focus/F8/disconnect/backend/application cleanup, and live/scheduled mutual exclusion.
- Offscreen probes kept the main window at 1080×720, reported a 1009×331 minimum-size hint, retained usable 618/439 px panes, and showed no horizontal scrollbar in the settings pane.
- The pre-package scan found and fixed a stale delayed-startup callback: last-file loading is now owned by the window and cancelled on close. The complete ten-test UI sequence passes without the previous post-close modal race.
- `python-rtmidi==1.5.8` and the packaged `_rtmidi.cp312-win_amd64.pyd` both loaded successfully, reported Windows MultiMedia as the compiled API, and enumerated zero connected input devices. Physical-controller latency and hot-disconnect behavior therefore remain unconfirmed.

## Windows 2.13.0 package

- `build_exe.ps1 -OutputRoot release-staging\2.13.0` completed with PyInstaller 6.21.0 and Python 3.12.10.
- Recursive PyInstaller inspection confirmed `musical_scumme.live_midi`, `rtmidi`, and Mido's RtMidi backend. The onedir package contains 241 files / 121,015,633 bytes, including `_internal\rtmidi\_rtmidi.cp312-win_amd64.pyd` and every required audio/separation resource.
- The 4,370,444-byte executable has SHA-256 `4170e3c434c1fc90b9a1a83659b00a792a4bf58be402b8cf24db1e6873038be8`.
- The packaged executable stayed alive through an eight-second isolated offscreen launch and logged a clean MusicalScumme 2.13.0 startup.
- `MusicalScumme-2.13.0-Windows.zip` contains 241 files (264 entries including directories), one `MusicalScumme/` root, no backslash paths, and every required resource. It passed a complete read-through, is 49,612,788 bytes, and has SHA-256 `a85d3d01a4c1e664a6f515969cf383d6cd2e221bbaf34036d51152275f582edb`.
- `SHA256SUMS.txt` was regenerated as a 97-file source manifest; all entries re-hash successfully and build, release, virtual-environment, cache, and bytecode directories are excluded.
- Current-build SCUM playback, live-controller behavior, focus cleanup, F8 emergency stop, latency, and musical quality remain unconfirmed until supervised testing with a physical MIDI keyboard in SCUM.
- Audio inference code did not change; representative MP3, WAV, and M4A conversions were not rerun.

Validation date: 2026-07-30

---

# MusicalScumme 2.12.0 validation

## Windows 2.12.0 package

- `build_exe.ps1 -OutputRoot release-staging\2.12.0` completed with PyInstaller 6.21.0 and Python 3.12.10.
- Source validation passed: compileall, 123 tests, Ruff, and styled offscreen construction coverage for the main window and all maintained dialogs.
- The onedir package contains 236 files / 120,596,122 bytes and all required optional-audio/separation resources.
- Recursive PyInstaller inspection confirmed the UI, MIDI engine, arranger, planner, scheduler, song processor, and audio tools modules.
- The executable SHA-256 is `fc576c0c2c9a5d8767426b735c35eb0858f1b5437e0e4652a776f17d13040b0e`.
- The packaged executable stayed alive through an eight-second isolated offscreen launch and logged a clean 2.12.0 startup.
- A native Windows high-contrast compositing probe confirmed the frameless top-level surface is genuinely translucent.
- `MusicalScumme-2.12.0-Windows.zip` contains 236 entries, one `MusicalScumme/` root, no backslash paths, and every required resource. It passed a complete read-through, is 49,443,168 bytes, and has SHA-256 `b4ca7fa2c241271f80602464ae9a3ebe7f8aa09e22d91a02a2e3bb18c7df8453`.
- Current-build SCUM playback, focus cleanup, Pause/Stop, F8, scheduler timing, and musical quality remain unconfirmed until supervised in-game testing.
- Audio inference code did not change; representative MP3, WAV, and M4A conversions were not rerun.

Validation date: 2026-07-30

---

# MusicalScumme 2.11.0 validation

## Windows 2.11.0 package

- `build_exe.ps1 -OutputRoot release-staging\2.11.0` completed with PyInstaller 6.21.0 and Python 3.12.10.
- Source validation passed: compileall, 122 tests, Ruff, and offscreen construction coverage for the main window and both conversion dialogs.
- The onedir package contains 236 files / 120,590,394 bytes and all required optional-audio/separation resources.
- The executable SHA-256 is `be3404216655f2c181969f570cc7da5c38bbf9192bdc9416393ba6b85a199e11`.
- The packaged executable stayed alive through an eight-second isolated offscreen launch and logged a clean 2.11.0 startup.
- `MusicalScumme-2.11.0-Windows.zip` contains 240 entries, passed a complete read-through, is 49,438,888 bytes, and has SHA-256 `62bf07935bf31a8a1cf5e579d73eeede015ec0ffc09f492daaadd9f437c0c618`.
- Current-build SCUM playback, focus cleanup, F8, musical quality, and the new optional base-bank restoration remain unconfirmed until supervised in-game.
- Audio inference code did not change; representative MP3, WAV, and M4A conversions were not rerun.

Validation date: 2026-07-18

## Original MIDI reliability and workflow

- The complete suite passes 114 tests. New coverage proves every legal `note_off` velocity closes a note, sustain still defers release, zero-velocity `note_on` still releases, parse/planning never modify source bytes, Pause cannot return before an in-flight key-down is cleaned up, and the maintained 1080×720 layout keeps both panes usable.
- The main file row now describes untouched MIDI as the primary input and exposes **Open MIDI**. Song Transposer and Audio to MIDI remain available from the File menu.
- Offscreen geometry retained the requested 1080×720 size with a 613/435 px source/settings split, independent left-pane scrolling, and no settings-pane horizontal scrollbar.

## Real untouched MIDI Find results

- `Matrix (The) — Clubbed to Death [MIDIfind.com].mid`: 15 tracks, 8,473 source notes, 421.41 seconds; Piano, Brass Section, and Bass were selected; Optimal Sounding produced 823 planned notes / 1,646 events.
- `Jackson Michael — Billie Jean [MIDIfind.com].mid`: 11 tracks, 6,095 source notes, 279.88 seconds; three recommended tracks produced 1,696 planned notes / 3,392 events.
- `Zimmer Hans — Interstellar (3) [MIDIfind.com].mid`: three tracks, 452 source notes, 110 seconds; both Steel Guitar tracks produced 365 planned notes / 730 events.
- All three plans had ordered, balanced key events and no final pressed keys. SHA-256 hashes before and after parse, analysis, arrangement, and planning were identical.
- A combined Play/Omit check on Interstellar resolved overlapping Play ranges to 10-25 s, 30-60 s, and 68-90 s. It retained 222 fragments from 452 notes, dropped 230, clipped 17, produced a 68-second timeline with 150 planned notes / 300 events / 300 batches, and ended balanced.

## Windows 2.10.1 package

- `build_exe.ps1 -OutputRoot release-staging\2.10.1` completed with PyInstaller 6.21.0 and Python 3.12.10.
- The onedir bundle contains 236 files / 120,583,252 bytes. `install_audio_tools.ps1`, `validate_audio_runtime.py`, `audio_worker.py`, `requirements-audio.txt`, and `requirements-audio-constraints.txt` are present.
- The executable is 4,335,436 bytes with SHA-256 `f8bf74d9de8ba3d0f45d7fd4d6a6428535ffc5686004d6a50906ecad9da3102e`. It stayed alive through an eight-second hidden/offscreen smoke launch using isolated APPDATA and logged a clean 2.10.1 startup.
- The ZIP has 240 entries / 120,583,252 uncompressed bytes, one `MusicalScumme/` root, no backslash paths, no CRC failure, and no missing required resources. ZIP size: 49,431,745 bytes. SHA-256: `ad61381e6ec4a99c85d6c94b3c9c55c2a1a19b4d9a0397cf3ac3c890382f7bd8`.
- Current-build SCUM playback, focus-loss cleanup, Pause/Stop, F8, and musical quality remain unconfirmed until supervised in-game. No audio code changed, so representative MP3/WAV/M4A inference was not rerun for 2.10.1.

---

# MusicalScumme 2.10.0 validation

Validation date: 2026-07-17

## New 2.10.0 workflow and safety coverage

- All 111 automated tests pass. New cases cover recent-MIDI normalization/deduplication/bounds, Ctrl+O and Ctrl+R actions, successful-load history, playback-range selection and in-place update, restored edited boundaries, and the complete plan-affecting control lock.
- Focused playback-section, scheduler, input-backend, and offscreen UI coverage passes 18 tests. It confirms complete-timeline equivalence, merged Play ranges, Omit subtraction, positive clipped fragments, configured inter-section gaps, ordered equal-time batching, loop cleanup, and runtime metrics.
- `python -m compileall -q .` and `ruff check .` pass in the project build environment.
- The main window, Audio to MIDI dialog, and Song Transposer construct offscreen. A rendered main-window inspection with a selected range confirmed the added **Update selected** control fits the existing playback-section layout.
- Active playback locks the file field and browse/reload/convert actions; track, range, key-profile, input, conversion, mapping, timing, export, and reset controls; and recent-file actions. Direct file loading and drag/drop are also rejected while the scheduler runs.

## Real combined Play/Omit result for 2.10.0

- Source: `E:\Users\james\Downloads\House Of The Rising Sun [ The Animals ].mid` (34,158 notes). Automatic import selected Clean Guitar, Bass, and Church Organ tracks 0/3/8.
- Overlapping Play ranges 30-50 s and 45-60 s merge; Play 90-115 s remains separate. Omit ranges 48-52 s and 98-101 s resolve the source intervals to 30-48 s, 52-60 s, 90-98 s, and 101-115 s.
- With 500 ms between non-contiguous intervals, 2,332 fragments remain, 14,642 selected-track notes are outside the result, and 155 sustained notes are clipped at a boundary. Rebased output duration is 49.5 seconds.
- Optimal Sounding plans 360 notes, 720 key events, and 720 timestamp batches. Simulated key-down/up validation ends balanced with no invalid releases or held keys.

## Windows 2.10.0 packaged-build checks

- `build_exe.ps1 -OutputRoot release-staging\2.10.0` produced the onedir application with PyInstaller 6.21.0 and Python 3.12.10.
- The staged folder contains 236 files / 120,582,311 bytes. Recursive PyInstaller inspection confirmed `ui`, `config`, `playback_sections`, `scheduler`, `input_backend`, `score_optimizer`, `planner`, `song_processor`, `audio_tools`, and `separation_tools`.
- Every required audio/separation worker, installer, validator, and requirements file is present. The packaged EXE remained alive through a six-second hidden/offscreen smoke launch with isolated temporary settings.
- The packaged Basic Pitch validator passed with Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model. The packaged separation validator passed with CUDA on the RTX 2070 SUPER, `audio-separator` 0.44.3, PyTorch 2.11.0+cu128, ONNX Runtime GPU 1.27.0, FFmpeg, and the Viperx model/config.
- The packaged worker converted representative five-second MP3, WAV, and AAC/M4A inputs into strict 23-note MIDI files in MIDI range 41-66 without worker errors, optional-backend warnings, TensorFlow banner noise, or malformed Unicode. Guitar / arpeggio cleanup retained 20 notes; Optimal Sounding produced 20 planned notes / 64 events, a balanced key state, and a 20-row SCUM-score CSV.
- The final ZIP passed a complete 236-entry / 120,582,311-byte read-through with one `MusicalScumme/` root, every required resource, and zero backslash paths. ZIP size: 49,430,942 bytes. SHA-256: `b8e92693f0ca34cc117ea6e35a23a093e01d120214b71a597539992e8b42ff83`.
- The source `SHA256SUMS.txt` was regenerated after the release records were finalized; all 94 listed files re-hash successfully and staged/build/cache directories are excluded.
- The executable is not Authenticode-signed. Current-build SCUM playback, focus-loss cleanup, F8 stop, scheduler lateness, and musical quality remain unconfirmed until this package is supervised in-game.

## New 2.9.0 playback-section coverage

- Automated coverage now contains 109 tests. New cases cover complete-timeline equivalence, overlapping Play-range merging, Omit subtraction, boundary clipping/splitting, invalid saved-range filtering, per-file UI persistence, selection-aware planning, same-timestamp batching, loop-until-stop behavior, and balanced cleanup.
- With no ranges, section processing preserves the complete source `MidiNote` timeline exactly.
- A sustained note crossing an omitted section is clipped into two source-backed fragments; a note fully inside the omission is removed.
- A UI test loads a real two-second MIDI, adds 0.5-1.5 s as a Play range, prepares one selected note, persists the range, and restores it in a new window.
- Scheduler tests confirm equal-timestamp events form one ordered backend batch, different timestamps remain separate, repeated playback completes multiple loops until Stop, and all keys are released.
- A 100-triad zero-stagger fixture produces 600 canonical key events in 200 input batches, reducing `SendInput` calls by 400 / 66.7%. Default monophonic Rush E and House plans retain unique timestamps and are deliberately not coalesced.

## Real combined Play/Omit result

- Source: `the-animals-the-house-of-the-rising-sun_bs6stem_mt_0_guitar.transcribed.mid`.
- Play ranges: 30-50 s and 90-115 s. Omit range: 98-101 s. Gap: 500 ms.
- Resolved source intervals: 30-50 s, 90-98 s, and 101-115 s.
- From 1,328 selected source notes, 227 fragments remain, 1,101 notes are outside the selection, and 18 sustained notes cross a boundary.
- Source span is 42 seconds; rebased output span is 43 seconds.
- Optimal Sounding retains 209 notes and emits 418 key events. Final simulated key state is balanced.

## Windows 2.9.0 packaged-build checks

- `build_exe.ps1 -OutputRoot release-staging\2.9.0` produced the onedir application with PyInstaller 6.21.0 and Python 3.12.10.
- The staged EXE remained running through a six-second offscreen smoke test and was stopped by its exact process ID.
- Recursive PyInstaller inspection confirmed `playback_sections`, `scheduler`, `input_backend`, `score_optimizer`, `planner`, and `ui`.
- The staged folder contains 236 files / 120,577,443 bytes. All required optional-runtime resources are present.
- The final ZIP passed a complete 236-entry / 120,577,443-byte read-through with one `MusicalScumme/` root, all required resources present, and zero backslash entry paths.
- ZIP size: 49,425,234 bytes.
- ZIP SHA-256: `c88f8ad6db57ea5c778633797ce8eaa119932e5c41cba3ba336b169fd8746115`.
- Actual SCUM scheduler lateness, focus-loss cleanup, looping, and musical quality remain unconfirmed until this package is supervised in the current game build.

## New 2.8.0 source-analysis coverage

- Automated coverage now contains 100 tests. New cases verify lead/bass/support recommendation, prepared Song Transposer recognition, melody/chordal/dense classification, rolled sustained chord detection, source-aware policy derivation, settings non-mutation, legacy preset migration, one-time blanket-selection migration, malformed-marker recovery, compact UI state, and unchanged balanced key cleanup.
- The optimiser recognises 0/20/40 ms rolled sustained triads as chordal, selects Game-optimised arrangement with real-source automatic chords, retains all nine source notes, and exports three chord groups. It does not turn a monophonic arpeggio into generated harmony.
- Every repository MIDI artifact was analysed and planned. The 865-note prepared House outputs classify as melody and retain all 865 attacks; the five-second raw probe classifies as melody and retains 21/23 notes after source cleanup; the SCUM test scale classifies chordal and retains all 34 notes.
- The malformed 19,043-note Rush E source recovered through the existing narrow data-byte path. Import recommends Grand Piano plus Electric Piano, classifies 12,072 selected notes as dense, and produces a 2,010-note / two-voice Optimal plan with 568 chord groups.
- The 66,960-note Guitar/Piano/Flute House score recommends Flute plus Electric Piano, classifies dense, and produces an 8,502-note two-voice plan from 44,640 selected notes.
- The 34,158-note multitrack Animals score recommends Clean Guitar, Bass, and Church Organ, classifies dense, and produces a 2,122-note two-voice plan from 16,974 selected notes.
- The raw 1,328-note isolated-guitar transcription classifies chordal and produces a 1,265-note plan with three-note source-chord capacity.

## Current Song Transposer reference results

- Smooth House: 1,328 source notes to 865 Lead Melody notes in D2-A4; 230 outliers removed, 29 octave repairs, nine phrase stabilisations, 62 sub-80 ms trimmed notes, zero lead overlaps, and 65 remaining large jumps. Optimal retains all 865 notes and emits 2,548 events with SCUM Pitch Match.
- Guitar/arpeggio House: 1,328 source notes to 865 Lead Melody notes in D2-A4; 230 outliers removed, 20 octave repairs, no phrase stabilisation, 62 sub-80 ms trimmed notes, zero lead overlaps, and 81 structural large jumps. Optimal retains all 865 notes and emits 2,584 events with SCUM Pitch Match.
- Smooth Rush E: 19,043 source notes to 1,510 Lead Melody notes in A1-E4; 7,482 short notes, 5,664 outliers, and 493 duplicate attacks removed; 213 octave repairs, zero lead overlaps, and 18 remaining large jumps. Optimal retains 1,370 attacks and emits 3,262 events with SCUM Pitch Match.
- Strict processed MIDI and auditable SCUM-score CSV outputs are stored under `release-staging/2.8.0-validation`.

## Windows 2.8.0 packaged-build checks

- `build_exe.ps1 -OutputRoot release-staging\2.8.0` produced the onedir application with PyInstaller 6.21.0 and Python 3.12.10.
- The staged EXE remained running through a six-second offscreen smoke test and was stopped by its exact process ID.
- Recursive PyInstaller inspection confirmed `score_optimizer`, `arranger`, `planner`, `song_processor`, and `ui` in the executable.
- The staged folder contains 236 files / 120,561,329 bytes. All bundled audio and separation installers, validators, workers, and requirement files are present.
- The final ZIP passed a complete 236-entry / 120,561,329-byte read-through with one `MusicalScumme/` root, all required resources present, and zero backslash entry paths.
- ZIP size: 49,407,451 bytes.
- ZIP SHA-256: `3bfbe59801ffb04d2286f94650031ac1201372e17b8aa2dca011dd135589fb59`.
- Static checks and offscreen launch do not confirm musical quality, focus-loss cleanup, or F8 stop inside the current SCUM build. A supervised 2.8.0 in-game audition remains pending.

## New 2.7.0 SCUM-score conversion coverage

- Synthetic repeated performed triads at 0/25/40 ms are recognized as three source-backed chord groups. Six offset notes align to their chord attacks, all nine source pitches remain real, and every note retains its original duration.
- A 20 ms fast chromatic run keeps the 12 ms exact-onset window and all twelve attacks. Automatic recognition does not collapse it into chords.
- The current selected Rush E fixture produces 4,289 planned notes, 9,064 key events, 243 octave-bank taps, and 299,292.575 ms duration in both automatic and exact-onset modes. Automatic mode derives a 12 ms window and aligns no false chords.
- Selected House tracks 0/2/4 derive the capped 45 ms window and conservatively align six additional source-backed performed chords without changing total plan duration.
- The prepared monophonic Bob Marley fixture retains 622 one-note score groups and introduces no chords.
- SCUM-score CSV regression coverage confirms stable chord group/voice order, source and mapped note names, SCUM keys, chord sizes, UTF-8 CSV output, and same-destination atomic publication.
- Qt construction confirms the automatic/exact selector, arrangement-aware enablement, and separate SCUM-score and key-event export controls.

## Windows 2.7.0 packaged-build checks

- `build_exe.ps1 -OutputRoot release-staging\2.7.0` produced the Windows onedir package with PyInstaller 6.21.0 and Python 3.12.10 without changing the validated 2.6 release.
- The staged EXE remained running through a six-second offscreen smoke test and was then stopped by its exact process ID.
- Recursive PyInstaller archive inspection confirmed `musical_scumme.arranger`, `musical_scumme.planner`, `musical_scumme.song_processor`, and `musical_scumme.ui` in the built executable.
- The packaged Basic Pitch validator confirmed Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model from `_internal`.
- The packaged separation validator confirmed audio-separator 0.44.3, PyTorch 2.11.0+cu128, CUDA on the NVIDIA GeForce RTX 2070 SUPER, ONNX Runtime GPU 1.27.0, FFmpeg, and the Viperx model/config from `_internal`.
- The packaged separation worker converted a representative five-second MP3 to two readable 884,968-byte PCM WAV stems. The packaged Basic Pitch worker produced a strict 23-note MIDI; deterministic Guitar / arpeggio cleanup retained 20 notes; Guitar Smooth planning produced 20 notes / 64 events; and SCUM-score export wrote 20 rows.
- `MusicalScumme_2.7.0_Windows.zip` passed a complete 236-entry / 120,549,542-byte read-through with required resources present, one `MusicalScumme/` root, and no backslash archive paths.
- ZIP SHA-256: `41d1e8caa5c11a1bd1748c5884f617c9a204cfbd586296ca6bd552cd2a0e73d2`.

## New 2.6.0 UVR coverage

- Ultimate Vocal Remover 5.6.0 installed under `E:\Applications\Ultimate Vocal Remover`, registered its uninstaller, launched successfully in an eight-second hidden smoke test, and was then closed. The official GitHub installer was 1,693,745,585 bytes with SHA-256 `3516daea39ccb9fead27e8ba5879375a08b20a428264a7c1be6db1be7765b0fe`; it was not Authenticode-signed.
- The isolated runtime validated Python 3.11.9, audio-separator 0.44.3, PyTorch 2.11.0+cu128, CUDA 12.8, NVIDIA GeForce RTX 2070 SUPER, ONNX Runtime GPU 1.27.0, `TensorrtExecutionProvider`, `CUDAExecutionProvider`, FFmpeg, and the Viperx model/config files.
- BS-RoFormer Viperx-1297 downloaded as a 639,331,213-byte checkpoint with SHA-256 `5b84f37e8d444c8cb30c79d77f613a41c05868ff9c9ac6c7049c00aefae115aa`. The runtime uses a pointer to the E: installation and exposes a CUDA readiness marker.
- The complete installer reran in place without reinstalling the pinned 2.75 GB CUDA wheel or redownloading the model. The temporary pip HTTP cache was purged after installation, restoring C: free space from 6.7 GB to 10.0 GB.
- The isolated source worker split a real 45-second opening from the user's House MP3 into two 45.000-second PCM S16LE/44.1 kHz/stereo WAV stems. CUDA autocast/batch-one processing completed without OOM while SCUM was open and used approximately 7.57/8.19 GB VRAM at peak.
- Basic Pitch E2-E6 detected 194 notes in the original mix and 208 in the separated instrumental. Against the user's existing guitar transcription, exact 90 ms attack matches improved 129 to 159 raw and 117/166 to 145/176 after Guitar / arpeggio cleanup; cleaned precision improved from 70.5% to 82.4% and recall from 50.2% to 62.2%.
- Demucs v4 `htdemucs_6s` was downloaded and evaluated as the only direct-guitar model in the supported catalogue. Its cleaned 182-note output matched 124 reference attacks (68.1% precision, 53.2% recall), so the Viperx instrumental path remains the evidence-backed default.
- A direct 15-second MP3 probe exposed an upstream false-success path: WAV export logged `unsupported encoding`, produced two zero-byte files, and returned success. After the worker's PCM-normalization and RIFF validation fix, the same MP3 produced two readable 15.021-second PCM S16LE/44.1 kHz/stereo stems of 2,649,832 bytes each.

## Automated checks

```text
python -m compileall -q .
python -m pytest
ruff check .
```

Result:

```text
93 passed
Python compilation passed
Ruff passed
```

## Windows 2.6.0 packaged-build checks

- `build_exe.ps1 -OutputRoot release-staging\2.6.0` produced the Windows onedir package with PyInstaller 6.21.0 and Python 3.12.10 while two older user-launched MusicalScumme processes remained untouched.
- The staged EXE remained running through a six-second offscreen smoke test and was then stopped cleanly.
- The packaged Basic Pitch validator confirmed Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model from `_internal`.
- The packaged separation validator confirmed audio-separator 0.44.3, CUDA on the NVIDIA GeForce RTX 2070 SUPER, FFmpeg, the configured Viperx checkpoint, and the required inference providers from `_internal`.
- The packaged separation worker converted a representative five-second MP3 to two valid 884,968-byte PCM WAV stems. The packaged Basic Pitch worker then produced a strict 23-note MIDI and the Song Transposer produced a 20-note SCUM-ready lead.
- `MusicalScumme_2.6.0_Windows.zip` passed a complete 236-entry / 120,543,197-byte read-through with every required worker, installer, validator, and requirements resource present, one `MusicalScumme/` root, and no backslash archive paths.
- ZIP SHA-256: `204299298c31fae82527ebd5f3a60fdba05857b2cd0c81d423dbf3692b74fdd9`.

## New 2.5.0 coverage

- SCUM Pitch Match selects a single `+12` semitone octave shift for the reference A2-E4 figure and maps every note/interval exactly. It selects zero shift for an already playable C4-C5 phrase.
- The existing Melody contour behavior remains unchanged. The user's currently saved Rush E selection produces the same 8,502 notes, 18,284 events, 312,900.1885 ms duration, warnings, diagnostics, and digest `42d98ff3fed7d88b80e08a1e7276a8555414e651190ef81cf75961de671434f1` before and after the feature.
- The 1,163-note clean House lead improves from 1,051/1,162 exact consecutive intervals under per-note Melody contour folding to 1,162/1,162 under Pitch Match. It uses a `+12` octave shift, zero residual folds, and 335 standalone bank taps versus 224.
- The 865-note rough House guitar lead improves from 660/864 exact consecutive intervals to 864/864. It uses a `+12` shift, zero residual folds, and 427 standalone bank taps versus 227.
- Audio command tests confirm `-I -X utf8` remains in order and that the selected `--minimum-frequency` / `--maximum-frequency` values reach the isolated Basic Pitch worker.
- Song Transposer Qt tests confirm Guitar / arpeggio defaults to E2-E6, other profiles automatically choose C2-C7, and a manual Full model range choice survives later profile changes.
- Real isolated inference passed twice on the user's 36.78-second WAV. Full and C2-C7 focus produced exactly equal 143-note raw MIDI files; deterministic guitar cleanup retained 103 exact C3-C6 notes with zero residual folds.
- Real isolated inference passed on the full House guitar MP3. Guitar E2-E6 produced 1,594 raw notes in MIDI 40-87, compared with the legacy file's 1,328 notes in 28-102. The arpeggio processor retained 1,016 lead notes, and strict 90 ms time/pitch matches against the clean score increased from 61 to 74. This metric is algorithmic evidence, not an in-game musical-quality claim.
- A representative 15-second AAC/M4A created from the user's WAV completed under guitar focus with 43 strict MIDI notes and no optional-backend warning, TensorFlow CPU banner, fallback chatter, replacement character, or non-zero exit.
- The 2.5.0 Windows onedir package built with PyInstaller 6.21.0 / Python 3.12.10, stayed alive for a five-second offscreen smoke test, exposed the pitch-matcher/audio-tools/song-processor/UI modules, and contained every required audio installer/validator/worker/requirements resource.
- The isolated Python 3.11.9 runtime validated Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model from the packaged `_internal` directory. The packaged worker converted the user's WAV under E2-E6 focus to the expected strict 143-note MIDI without diagnostic noise.
- `MusicalScumme_2.5.0_Windows.zip` passed a complete 231-entry / 120,519,073-byte read-through with zero missing resources and zero backslash paths. SHA-256: `77fdb592c84cee49b52ae57ea1611b2f45a991d5b5ca760229241a2c479ef6dd`.

## New 2.4.4 coverage

- The 2.4.3 smart-chord implementation is absent. Lead melody only keeps one inferred lead-track note per onset at Maximum chord notes values 1, 3, and 8.
- The clean ScoreAccurate House plan is restored exactly at every tested chord limit: 1,163 planned notes, 2,774 events, 224 octave-bank taps, and 239,947.043 ms duration.
- The user's current Game-optimised two-note Rush plan is unchanged: complete plan digest `7da04adb61d3a4b8062b0a39b0995c4c79fbfa3917c7e14f30f20cac2f39a1d0`, 2,420 planned notes, 5,982 events, 571 bank taps, and 266,453.107143 ms duration.
- The in-place tempo scan matches the legacy stable merged-track tempo map, including same-tick events across multiple tracks. Every parsed Rush and House note is equal to the legacy implementation.
- Indexed retrigger replacement preserves higher-priority later notes and ordering. Indexed density replacement evicts support before melody while preserving the previous selection.
- Histogram core-register detection matches the legacy whole-note window scan. Full Rush and raw House processed-song digests are unchanged.
- Measured wall-time improvements: Rush load 1.9981 to 0.7297 seconds, large House load 3.5740 to 1.0812 seconds, Rush processing 1.39 to 0.13 seconds, and raw House guitar processing 0.19 to 0.02 seconds.

## New 2.4.2 coverage

- A target octave is treated as persistent bank state. Two consecutive upper-bank notes emit one standalone Shift tap before the first note, not a Shift+note chord and not a second redundant tap.
- Every octave-key hold is exactly 18 ms. A complete event-state simulation asserts that neither Ctrl nor Shift is ever down while any of the 13 musical keys is down.
- A lower-to-upper transition emits two separate Shift down/up pairs; an upper-to-lower transition emits two separate Ctrl down/up pairs.
- The clean score-derived House release retains all 1,163 notes, emits 2,774 events including 224 bank taps, spans 239.947 seconds, and has zero octave-key/note-key overlaps.
- The audio-recovered House release retains 1,025/1,026 notes, emits 2,612 events including 281 bank taps, spans 234.513 seconds, and has zero octave-key/note-key overlaps.
- The tempo-fixed Rush release remains 270.00027 BPM, retains 1,370 notes, emits 2,866 events including 63 bank taps, spans 266.501 seconds, keeps a 98.357 ms median attack gap, and has zero octave-key/note-key overlaps.
- All three complete plans finish with an empty pressed-key state.

## Historical 2.4.1 coverage

- A synthetic upper-register phrase emits a separate Shift down/up pair for every attack. Under Guitar Smooth each Shift hold is exactly 38 ms: 20 ms before note-on through 18 ms after note-on. Shift is already up while the note remains held.
- A real tick-zero 270 BPM tempo remains 270 BPM. The reported malformed `Rush E.mid` now parses at 270.00027 BPM with a 302.17-second source length instead of being stretched to 120 BPM.
- Tempo-relative Song Transposer grouping uses a 29 ms onset window for the 270 BPM Rush source. Clear Melody retains 1,510 non-overlapping notes in A1-E4, removes 7,482 ultra-short notes and 5,664 outliers, performs 213 octave repairs, collapses 493 duplicates, and leaves 18 structural jumps larger than one octave.
- The exported Rush prepared source contains 1,510 notes. Guitar Smooth retains 1,370, removes 140 only through the 18 starts/s density guard, drops no short or retrigger notes, produces 2,804 events, spans 266.493 seconds, and has a 98.357 ms median attack gap.
- Prepared Song Transposer tracks bypass the second raw-duration filter. The clean score-derived House release retains all 1,163 notes, emits 2,550 key events, and spans 239.911 seconds at 1.12x.
- The exact 1,328-note House guitar reference still produces an 865-note monophonic lead in D2-A4 under both evaluated profiles. Smooth lead removes 230 outliers, performs 29 octave repairs including nine phrase stabilizations, retains 23 sub-80 ms attacks, has zero overlaps, and leaves 65 large jumps. Guitar / arpeggio performs 20 contextual octave repairs, no phrase stabilization, has zero overlaps, and preserves 81 structural register resets. Prepared Balanced planning retains all 865 notes and emits 1,730 events for either variant.
- A stale named Guitar Smooth settings snapshot is refreshed to the maintained 2.4.1 values on load. Manual settings remain protected under the `custom` identity.
- Windows Qt tests redirect both `APPDATA` and `XDG_CONFIG_HOME`; a hash check confirmed that offscreen tests do not mutate the user's live settings file.
- The full MP3, representative WAV, and representative M4A all completed through the isolated Basic Pitch runtime with the new 0.45/0.30/90 defaults and without optional-backend warnings, TensorFlow's CPU banner, or replacement characters.

## New 2.4.0 coverage

- Guitar Smooth applies Lead melody only, Smart three-octave mapping, one-note polyphony, a 90 ms source cutoff, 105 ms minimum hold, 35 ms physical gap, and 30/45 ms modifier release/settle timing.
- Brief enclosed one-to-three-onset register excursions are folded into their surrounding register only when they return within 1.2 seconds; a four-note register phrase remains unchanged.
- Lead melody mode includes track activity in its inference and stays entirely on the inferred track. The active 736-note Lead Melody now wins over the sparse 115-note Light Support track.
- Same-key collisions delay the next note rather than truncating the current note below the configured minimum.
- M4A's exact successful SoundFile-to-audioread fallback/deprecation notices are suppressed, while a synthetic unrelated decoder warning remains visible.
- The active 851-note House of the Rising Sun arrangement under Guitar Smooth retains 649 lead notes, rejects 87 short lead attacks plus all 115 support notes, stabilizes 13 brief register groups, delays six colliding retriggers by 36.875 ms total, and guarantees a 105 ms minimum.
- Under the user's existing permissive custom timing, the register guard changes 12 onset groups and reduces modifier-state changes from 17 to 7.
- The exact 1,328-note reference produces an 865-note monophonic lead in D2-A4. Smooth in-game guitar removes 230 outliers, performs 29 octave repairs including nine phrase stabilizations, retains 23 sub-80 ms onset gaps, has zero lead overlaps, and leaves 65 structural large jumps. Balanced retains 862 notes/1,724 events; Guitar Smooth retains 787 notes/1,594 events.
- Guitar / arpeggio retains 865 notes with 20 contextual octave repairs, zero phrase stabilizations, 23 sub-80 ms onset gaps, zero overlaps, and 81 structural register resets. Its Balanced plan is also 862 notes/1,724 events.

## New 2.3.3 coverage

- Strict parsing rejects an illegal velocity of 129, while `load_midi` narrowly recovers it by clipping data bytes to 127 and recording a visible warning.
- Unrelated structural corruption remains fatal.
- Song Transposer propagates the recovery warning and exports a strictly readable MIDI.
- The actual `Rush E.mid` loads as five tracks, 19,043 source notes, and 302.17 seconds. Clear Melody retains 1,709 non-overlapping notes in A2-E5, removes 8,041 outliers, performs 1,109 octave repairs including four phrase stabilizations, and leaves 43 large jumps.
- Balanced planning of the recovered result retains 1,624 notes, drops 85, and emits 3,248 events.

## New 2.3.2 coverage

- Audio worker commands retain Python isolated mode and explicitly enable UTF-8 with `-I -X utf8` before the worker path.
- Worker protocol records remain ASCII-safe while Unicode messages round-trip through JSON unchanged.
- Inference logging is configured before Basic Pitch imports; real error-level logs and non-zero exits remain visible.
- The source and packaged workers both processed the supplied 4:22 guitar MP3 into the expected 1,328-note, 10,014-byte raw MIDI without optional CoreML/TFLite/ONNX warnings, TensorFlow's CPU feature banner, or replacement characters.
- Temporary probe outputs were removed after validation.

## New 2.3.1 coverage

- Profile-specific consolidation of likely transcription double-attacks.
- Isolated octave-spike eligibility and one-octave shift limit.
- Joint contour solving for consecutive eligible octave spikes.
- Guitar / arpeggio preservation of structural register resets.
- Song Transposer UI exposure of the new guitar profile.
- The supplied reference's Clear Melody result contains 865 non-overlapping notes in D2-A4, removes 230 outliers, performs 29 octave repairs including nine phrase stabilizations, retains 23 sub-80 ms attacks, and contains 65 large jumps. Balanced planning retains 862 notes, drops three, and emits 1,724 events.
- The Guitar / arpeggio result contains 865 non-overlapping notes, performs no phrase stabilizations, preserves 81 structural register resets, and produces the same 862-note Balanced plan.

## New 2.3.0 coverage

- Weighted core-register detection and rejection of low-confidence overtone artifacts.
- Contextual octave repair and global melody-path selection.
- Guaranteed monophonic Lead Melody output.
- Clear melody, light-support, and fuller arrangement profiles.
- MIDI round-trip, tempo preservation, atomic export, and overwrite protection.
- Song Transposer construction offscreen and main-window entry-point coverage.
- The supplied House of the Rising Sun reference produced 924 lead notes in D2-A4, removed 230 outliers, repaired 20 octave errors, and reduced lead jumps larger than one octave from 472 to 101.

## New 2.2.1 coverage

- Installer probes, pip/venv operations, runtime validation, standalone repair, and the audio worker retain Python isolated mode.
- The runtime UI status requires a successful validation marker.
- Basic Pitch model validation accepts both model files and TensorFlow SavedModel directories.
- The main window, audio-conversion dialog, and Song Transposer construct offscreen.

## New 2.2 coverage

- SCUM Safe preset values.
- Existing settings migration to Custom.
- Melody-first chord order.
- Per-note chord stagger timing.
- Physical retrigger-gap enforcement after octave folding.
- Modifier release and settle timing.
- Existing smart-register safety behaviour under the new transition timeline.
- Preset diagnostics in playback plans.

## Qt UI smoke test

Using `QT_QPA_PLATFORM=offscreen` with PySide6 6.11.1:

- `MainWindow` constructed and closed successfully.
- Balanced loaded as the new-install default.
- All new SCUM performance controls were present.
- Selecting SCUM Safe applied the expected values.
- Manually editing a preset-controlled value changed the profile to Custom.
- `UI_PREVIEW_2.2.0.png` rendered successfully at 1420×930.

## Historical Windows 2.4.0 packaged-build checks

- `build_exe.ps1` produced `dist\MusicalScumme\MusicalScumme.exe` with PyInstaller 6.21.0 and Python 3.12.10 after one stale older packaged process was closed to release its `qwindows.dll` file lock.
- The packaged EXE remained running through a five-second hidden/offscreen smoke-test window and was then stopped cleanly.
- The packaged `_internal\validate_audio_runtime.py`, launched with Python `-I`, validated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` SavedModel.
- The packaged installer, validator, worker, requirements, and constraints resources are present; `musical_scumme.song_processor` is present in `PYZ-00.toc`.
- The packaged worker converted a representative 15-second M4A to a strictly readable 83-note MIDI with no M4A fallback/deprecation warning noise.
- `MusicalScumme_2.4.0_Windows.zip` passed a complete 231-entry byte read-through. Required resources were present and no entry used a backslash path.
- ZIP SHA-256: `348307907d8a23bc273efa2b21d5fddff0007b695c7893e2909dc4c15570ad67`.

## Windows 2.4.4 packaged-build checks

- `build_exe.ps1` produced `dist\MusicalScumme\MusicalScumme.exe` with PyInstaller 6.21.0 and Python 3.12.10.
- The 2.4.4 packaged EXE remained running through a five-second hidden/offscreen smoke-test window and was then stopped cleanly.
- The packaged `_internal\validate_audio_runtime.py`, launched from `_internal` with Python `-I`, validated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` SavedModel.
- The packaged installer, validator, worker, requirements, and constraints resources are present. `musical_scumme.midi_engine`, `musical_scumme.arranger`, `musical_scumme.song_processor`, `musical_scumme.planner`, and `musical_scumme.ui` are present in `PYZ-00.toc`.
- The packaged worker converted the user's 38.02-second WAV to a strict 143-note MIDI without optional-backend warnings, TensorFlow's CPU banner, or replacement characters.
- `MusicalScumme_2.4.4_Windows.zip` passed a complete 231-entry / 120,515,458-byte read-through. Required resources were present and no entry used a backslash path.
- ZIP SHA-256: `e9b5602f7ad421472d881067d9feb2a2c016eb4ec866f9340292abee37893a37`.

## Historical Windows 2.4.3 packaged-build checks - withdrawn musical experiment

- `build_exe.ps1` produced `dist\MusicalScumme\MusicalScumme.exe` with PyInstaller 6.21.0 and Python 3.12.10.
- The 2.4.3 packaged EXE remained running through a five-second hidden/offscreen smoke-test window and was then stopped cleanly.
- The packaged `_internal\validate_audio_runtime.py`, launched from `_internal` with Python `-I`, validated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` SavedModel.
- The packaged installer, validator, worker, requirements, and constraints resources are present. `musical_scumme.arranger`, `musical_scumme.song_processor`, and `musical_scumme.ui` are present in `PYZ-00.toc`.
- The packaged worker converted the user's 38.02-second WAV to a strict 143-note MIDI without optional-backend warnings, TensorFlow's CPU banner, or replacement characters.
- `MusicalScumme_2.4.3_Windows.zip` passed a complete 231-entry / 120,521,472-byte read-through. Required resources were present and no entry used a backslash path.
- ZIP SHA-256: `1cf538a28a1ffcf5cd0751e5887221ac34fbe23d26e0c31cd4e7aa24944de75f`.

## Historical Windows 2.4.2 packaged-build checks

- `build_exe.ps1` produced `dist\MusicalScumme\MusicalScumme.exe` with PyInstaller 6.21.0 and Python 3.12.10.
- The 2.4.2 packaged EXE remained running through a five-second hidden/offscreen smoke-test window and was then stopped cleanly.
- The packaged `_internal\validate_audio_runtime.py`, launched from `_internal` with Python `-I`, validated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` SavedModel.
- The packaged installer, validator, worker, requirements, and constraints resources are present. `musical_scumme.song_processor`, `musical_scumme.midi_engine`, and the corrected `musical_scumme.planner` are present in `PYZ-00.toc`.
- The packaged worker converted the user's 38.02-second WAV to a strict 143-note MIDI in 16 seconds without optional-backend warnings, TensorFlow's CPU banner, or replacement characters.
- `MusicalScumme_2.4.2_Windows.zip` passed a complete 231-entry / 120,515,080-byte read-through. Required resources were present and no entry used a backslash path.
- ZIP SHA-256: `9abdde313115dcacc87b13800fb0fb833db1e8fc574a6feb30f61607ad1f89d6`.

## Historical Windows 2.4.1 packaged-build checks

- `build_exe.ps1` produced `dist\MusicalScumme\MusicalScumme.exe` with PyInstaller 6.21.0 and Python 3.12.10 after the verified stale 2.4.0 packaged process was closed.
- The 2.4.1 packaged EXE remained running through a five-second hidden/offscreen smoke-test window and was then stopped cleanly.
- The packaged `_internal\validate_audio_runtime.py`, launched from `_internal` with Python `-I`, validated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` SavedModel.
- The packaged installer, validator, worker, requirements, and constraints resources are present. `musical_scumme.song_processor`, `musical_scumme.midi_engine`, and `musical_scumme.planner` are present in `PYZ-00.toc`.
- The packaged worker converted the user's 38.02-second WAV to a strict 143-note MIDI in 17 seconds. MIDI data bytes remain inside `0..127`; optional CoreML/TFLite/ONNX warnings, TensorFlow's CPU banner, and replacement characters were absent.
- `MusicalScumme_2.4.1_Windows.zip` passed a complete 231-entry / 120,515,236-byte read-through. Required resources were present and no entry used a backslash path.
- ZIP SHA-256: `fce1947e96284aa4fdb3cd322e1f02bd5bc76f9450d638653dd736facd991d0a`.

## Historical Windows 2.3.3 packaged-build checks

- `build_exe.ps1` produced `dist\MusicalScumme\MusicalScumme.exe` with PyInstaller 6.21.0 and Python 3.12.10.
- Running the newly packaged `_internal\install_audio_tools.ps1` repaired the existing runtime in place and passed validation with Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` SavedModel directory.
- The readiness marker was present after validation.
- The packaged audio worker completed the supplied MP3 under Python 3.11 isolated and UTF-8 modes.
- The packaged installer, validator, worker, requirements, and constraints resources were present.
- `musical_scumme.song_processor` was present in the packaged Python archive.
- `musical_scumme.midi_engine` with the narrow recovery path was present in the packaged Python archive.
- The packaged EXE remained running through a four-second hidden smoke-test window.
- `MusicalScumme_2.3.3_Windows.zip` passed a complete 231-entry read-through; all required resources were present and no entry used a backslash path.

## Test MIDI plan checks

`examples/scum_test_scale.mid` produced valid, chronological plans under SCUM Safe, Balanced, and Maximum Fidelity. No plan left a modifier or note key logically pressed at completion.

## Live validation status

The user confirmed the previous 2.1.3 build:

- Installed the audio runtime successfully.
- Converted a song.
- Played the song in SCUM.

The user's 38.02-second v2.4.0 in-game recording later confirmed accurate physical execution—107/107 assessable fundamental attacks, no wrong fundamental attacks, and no meaningful drift—but the user correctly rejected the musical arrangement. Version 2.4.1 repaired the arrangement, tempo, and preset paths but still treated Shift as a note modifier. Version 2.4.2 implements the user's corrected persistent-bank semantics. The user then rejected 2.4.3's calculated harmony after live audition; 2.4.4 fully removes it while preserving the successful Game-optimised Rush path. The restored melody-only path and optimised build still require current-build SCUM confirmation.

## Not validated here

- The complete Qt dialog was not manually clicked through for all three audio formats, although real isolated worker inference passed for a full 4:22 MP3 and representative 30-second WAV/M4A inputs, and deterministic processing passed on the resulting MP3 transcription.
- Windows SendInput execution for the new timings and musical auditioning inside the current SCUM build.
- Current SCUM instrument response to each preset.
- Live musical comparison of the Clear Melody and Guitar / arpeggio reference outputs inside the current SCUM build.
- Server-policy or anti-cheat acceptance.
