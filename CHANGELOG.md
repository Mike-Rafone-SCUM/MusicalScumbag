## 3.9.1 — 2026-09-23

- Prevent duplicate UI/hotkey instances while the player is hidden or visible.
- Restore full-duration contextual voice budgeting and lead-track plan invalidation.
- Audit outdated tests against current migration, MIDI channel, Simple/Advanced UI,
  Optimal arrangement and guitar roll behavior; details in `docs/TEST_AUDIT.md`.
- Refresh full-plan baselines with independent provenance and bank-safety checks.
- Current-game SCUM audition remains pending.

## 3.5.1 — 2026-09-10

- Numeric fields select the current number on first click and commit typed replacements on Enter or focus loss.
- Play, Prepare and exports commit pending numeric text before using settings or cached plans.
- Existing numeric ranges, arrows, preset switching and playback locks remain intact. Qt typing and shortcut regressions added.

## 3.5.0 — 2026-09-10

- Added Vocal director, Vocal rhythm and Chamber director with full-duration accompaniment budgets and future melody collision checks.
- Protect inferred leads and instrumental fills while held; reset support continuity after actual silence.
- Added indexed duration queries, deterministic tie handling, contextual diagnostics and readable prepared recipe names.
- Added randomized reference checks, musical regressions, five-mapping safety coverage, an offscreen preparation test and a repeatable synthetic benchmark. Existing presets and recipes remain available.
- Current SCUM audition and representative optional audio validation remain pending.
- Verification: 730 tests passed, including offscreen Qt construction and preparation; compileall and Ruff passed.

## 3.4.2 — 2026-09-10

- Correct MIDI all-notes-off, all-sound-off and controller-reset handling, including sustain, repeated attacks and channel isolation.
- Explain unsupported Type 2/SMPTE MIDI timing and reject invalid zero tempos before preparation.
- 637 tests passed, including offscreen Qt windows; compileall and Ruff passed. Current-game playback and optional audio inference remain untested for this build.

## 3.4.1 — 2026-09-10

- Smart auto-select prioritises main vocals, respects suite lead overrides and chooses source layers for the current arrangement.
- Detects real lead rests, compares actual sounding overlap and removes redundant exact/octave parts across selected tracks.
- Fixes ordinary Lead Melody names hiding accompaniment and noise-only recommendations restoring rejected FX.
- Explains every recommendation, preserves saved empty/manual choices and guards selection changes during active output.
- Verification: 624 tests passed; compileall, Ruff and offscreen Qt construction passed.

## 3.4.0 — 2026-09-09

- Added 18 source-backed arrangement recipes: ten vocal styles and eight instrumental styles, with 1–6-layer ceilings.
- Added explicit suite lead-track selection for unnamed vocal parts, main-vocal preference over backing voices, and sustained-vocal ownership between accompaniment attacks.
- Added distinct compact, warm, rhythmic, fifth-oriented, choir and wide support selection without generating harmony or changing stored timing limits.
- Included a full arrangement audition guide and five synthetic vocal-versus-ensemble MIDI fixtures with 1/2/4/8/16 source tracks.
- 580 automated tests pass, including offscreen Qt construction and standalone octave-tap checks. In-game musical audition and optional audio inference remain pending.

# Changelog

## 3.3.1 - Arrangement and Conversion Fidelity Enhancements

- **Octave Bank Seek Synchronization**: Post-batch bank states are now tracked across the playback timeline. Live forward and backward seeking evaluates the destination bank and emits standalone `_sync_octave_bank` taps with configured release and settle delays before playing destination notes. Seeking while paused safely defers synchronization until playback resumes, preventing background keystroke leaks. Loop restarts reset bank state to zero if the previous loop finished non-zero.
- **Unison C Voicing Resolution**: In `fold_smart`, boundary C allocation checks for distinct octave classes in the group. Unison attacks (e.g. C4 + C4 across tracks) remain unified at C4 rather than splitting into an artificial octave C4 + C5. Distinct source octaves (e.g. C3 + C4) continue to spread across C4 and C5 boundary keys.
- **Melody Contour Landmark Protection**: Generalized contour landmark detection from solos to all melody voice runs. Local peaks, valleys, cadence endpoints, and accents are protected with priority bonuses before density limits are enforced. Retrigger filtering now executes before landmark detection to ensure intentional note attacks are not replaced by weak duplicate micro-retriggers.
- **Audio-to-MIDI Transcription Cleaning & Strum Consolidation**:
  - `_suppress_harmonic_ghosts` removes acoustic body overtone artifacts (+12, +19, +24 semitones with lower velocity relative to concurrent fundamentals) and sub-bass transcription rumble.
  - `_consolidate_micro_strums` aligns near-simultaneous guitar string strum rakes (15–35 ms) to the anchor onset time.
  - `estimate_tempo_bpm` estimates musical BPM from inter-onset intervals (IOI) and embeds it into processed MIDI exports instead of the flat 120 BPM default.
- **UI Enhancements**:
  - Added "Auto / Recommend" button beside the Transpose control powered by `recommend_optimal_transpose`, finding the semitone shift ($-12 \dots +12$) that maximizes in-bank C4–C5 and 3-octave SCUM range coverage.
  - Added `MappingComparisonDialog` via "Compare Mappings…", rendering side-by-side comparative scorecards across all 5 enhanced mapping modes (`fold_smart`, `match3_adaptive`, `strict_auto`, `melody3_contour`, `smart3_harmonic`) with direct "Apply" actions.

## 3.3.0 - Enhanced mappings and resource optimisation

- Removed the five base file-playback mappings and their obsolete planning code. Saved names migrate to enhanced equivalents; Optimal Sounding and protected solos use enhanced components too.
- Preserved custom timing, source notes, instrument ceilings, standalone octave taps, focus protection, F8, and separately supervised live MIDI.
- Reused equivalent phrase analysis and rolling prominence, bounded semantic-name caching, kept only current DP score rows, released redundant buffers, and removed unnecessary note/list copies.
- Replaced linear event lookup during seeking with binary search without changing seek semantics or dispatch timing.
- Added 45 complete-plan regression snapshots covering all enhanced mappings, three arrangements, and three transpositions. Enhanced Pitch Match additionally exposes global shift and exact/folded counts.
- Removed unused Qt PDF, embedded virtual-keyboard, TUIO UDP touch plugin, and PySide6 QtNetwork stacks and unnecessary Mido backend collection from packaging, retaining native rendering and input support.
- Further reduced onset-matching work with a linear scan, cached per-import track relationships, computed group bounds once, replaced repeated octave loops with integer arithmetic, and released private raw MIDI buffers after parsing each track.

## 3.2.0 - Guided Command Deck UX

- Added a persistent four-stage workflow rail for Load MIDI, Review Tracks, Prepare, and Play, with a live readiness pill and concise next-action guidance.
- Made primary actions prerequisite-aware. Prepare, Play, and both CSV exports remain unavailable until an existing MIDI has at least one populated source track selected; live controller arming remains independent.
- Added fast track filtering by track number, name, role, note count, or range; visible and selected counts; double-click selection; disabled empty-track checkboxes; per-row source summaries; and a one-click relationship-aware recommendation restore.
- Reworked the Prepared Song area into a scannable multi-line result plus selectable bullet advisories instead of one dense diagnostic paragraph.
- Added visible indeterminate preparation feedback, wait cursor handling, readable ready/playing/paused/live states, and dry-run guidance without changing planning output.
- Added inline source/destination/runtime validation to Audio-to-MIDI and Song Transposer. Invalid or incomplete workflows now explain the missing prerequisite before an operation can start, and operation inputs lock while asynchronous workers run.
- Made Song Transposer settings vertically scrollable at 880×720 while prohibiting horizontal scrolling; kept its log and command buttons continuously reachable.
- Added inline custom-key validation that keeps the editor open on invalid Windows key names.
- Added Ctrl+P Prepare, Ctrl+L MIDI-path focus, F1 Quick Start, keyboard-shortcut help, safety-oriented About text, Delete for a selected playback section, action status tips, richer tooltips, accessible names/descriptions, and selectable summaries.
- Compacted export commands to Score CSV and Events CSV so the full guided command deck remains inside the maintained 1080×720 HUD and the compact playback overlay stays below 580 px wide.
- Preserved every musical policy, Dynamic Solo Director behavior, Instrument Prep ceiling, public API, SCUM binding, input/scheduler safety boundary, settings mapping, and source-file immutability rule.

## 3.1.0 - Dynamic Solo Director

- Added section-local lead analysis with deterministic look-ahead and switch hysteresis. Sparse guitar, violin, sax, flute, and synth solos can now take ownership from the song's primary lead for a sustained passage without requiring the other selected tracks to become silent.
- Added automatic solo-track recommendation. Import analysis now recognises useful alternate-lead runs from activity, exclusivity, continuity, monophony, register, and token-safe track names, while rejecting simultaneous doubled melodies.
- Added protected solo intervals to Game-optimised arrangement. Solo attacks reserve the lead voice, bypass performed-chord alignment, suppress chord stagger, and duck competing upper accompaniment to at most one source-backed foundation voice.
- Reworked fast-run simplification around musical landmarks. Endpoints, velocity accents, local extrema, direction changes, spacing changes, and regular phrase positions are prioritised before connector notes when SCUM's note-start ceiling requires reduction.
- Added plan-local solo-adaptive mapping for Optimal Sounding. Accompaniment remains on Safe Fold, while each protected solo receives its own whole-octave pitch fit and melody-contour bank sequence with the existing standalone Ctrl/Shift no-overlap safeguards.
- Added visible director reporting and plan diagnostics for detected sections, handoffs, protected solo notes, ducked accompaniment, density reduction, preserved landmarks, suppressed stagger groups, per-section octave shifts, and exact/folded solo mapping.
- Preserved source-only musical material, stored Safe Fold defaults, Custom behavior, Instrument Prep ceilings, public planner compatibility, SCUM bindings, scheduler/input safety, and untouched source MIDI files.

## 3.0.0 - Whole-phrase MIDI intelligence and instrument-aware preparation

- Replaced greedy onset-by-onset melody picking with deterministic whole-phrase dynamic programming that follows source-backed contour, track continuity, rhythmic gaps, and explicit phrase boundaries.
- Rebuilt automatic track recommendation around relationships: token-safe semantic names, onset affinity, temporal coverage, register separation, and exact doubled-part rejection. A second melody track is no longer forced into a bass role merely because only two tracks exist.
- Separated musical onset rate from physical note-start load and added time-weighted sounding polyphony, overlap, phrase-count, and rhythmic-variation analysis for more accurate melody/chord/density classification.
- Made retained bass and harmony voices respond to the traced lead and prior support voice-leading while preserving only real source notes. Generated harmony, scale snapping, and source rewriting remain prohibited.
- Made Optimal Sounding's chord roll pulse-relative, with tighter rolls for dense fast passages and longer bounded separation for slower chord-led material.
- Added auditable plan diagnostics for melody phrases, source-track changes, large lead intervals, sounding polyphony, overlap, onset load, and rhythmic variation.
- Extended source, planner, settings, and UI integration so track names inform arrangement without breaking the existing `build_playback_plan()` calling convention.

- Added explicit Guitar, Harmonica, and Banjo preparation profiles with hard real-time sustain ceilings of 2,000 ms, 4,000 ms, and 1,000 ms.
- Made Optimal Sounding derive source-aware note lengths within the selected instrument limit, with a second final-planning guard after speed and velocity expression.
- Added a persisted, plan-affecting target-instrument selector plus preparation diagnostics for effective hold limits, capped-note counts, and total removed sustain.
- Preserved legacy positional `AppSettings` construction by appending the new setting field, and normalized persisted instrument IDs case-insensitively with surrounding whitespace removed.
- Extended regression coverage across every mapping mode, slow playback, conflicting Custom timing, empty plans, actual emitted key-hold intervals, UI invalidation, and balanced key cleanup.

## 2.13.0 - Supervised live MIDI keyboard

- Added physical/virtual MIDI input discovery, remembered controller selection, manual refresh, channel selection, live transpose, safe fold/strict mapping, and a three-key default live polyphony limit.
- Added a dedicated low-latency live-input service. Native callbacks only decode and enqueue short MIDI messages; one worker owns keyboard dispatch, foreground checks, F8 polling, device checks, and serialized panic cleanup.
- Added correct note-on/off reference counting, zero-velocity note-on releases, sustain pedal CC64, Reset Controllers CC121, and global safety cleanup for All Sound Off/All Notes Off CC120/123.
- Added live HUD controls and activity telemetry while keeping scheduled playback and live input mutually exclusive. Stop, F8, focus loss, device disconnect, backend errors, and application shutdown all release every held key.
- Kept live input in the fixed base 13-key SCUM bank. It never issues automatic Ctrl/Shift octave taps; users explicitly place SCUM in its base octave before arming.
- Added the pinned `python-rtmidi` Windows MultiMedia backend, deterministic frozen-build inclusion, adapter/state-machine/UI tests, and native runtime discovery validation.

## 2.12.0 - Translucent in-game HUD

- Rebuilt the desktop interface as a minimalist, semi-transparent tactical HUD while preserving every playback workflow, shortcut, safety lock, and Windows-standard window operation.
- Added an electric-cyan single-accent system, layered low-opacity charcoal glass, hairline borders, restrained semantic status colors, and a clear title/section/body hierarchy.
- Added dedicated MIDI-source and playback-command decks plus compact foreground-link telemetry.
- Added compact frameless chrome with minimize, maximize/restore, close, native system dragging, and eight-zone native system resizing; extended the translucent treatment to the custom-key, Audio-to-MIDI, and Song Transposer dialogs.
- Preserved the maintained 1080×720 two-pane layout, settings-pane horizontal-scroll prohibition, conversion-tool menu access, source-file immutability, and all planning/input behavior.

## 2.11.0 - Explainable mapping and bank-aware planning

- Added Custom-mode planning priorities for balanced output, register preservation, rhythmic reliability, or minimum octave-bank changes.
- Added a mapping-stability control and an optional rolling octave-bank tap budget. Global look-ahead planning remains deterministic; the budget folds only excess rapid transitions.
- Added explicit lower/upper preference for equivalent C-boundary mappings.
- Added per-note mapping explanations to the auditable SCUM-score CSV and the prepared-plan summary.
- Added visible initial-bank preparation diagnostics and an opt-in safe return to SCUM's base octave bank after every musical key has been released.
- Preserved all existing defaults, mappings, presets, public planning APIs, standalone Ctrl/Shift semantics, and source MIDI immutability.

## 2.10.1 - Original-MIDI reliability and responsive workflow

- Made untouched MIDI files the clear primary workflow. The main window now leads with **Open MIDI**; optional Song Transposer and Audio-to-MIDI tools remain available from the File menu.
- Fixed standard `note_off` messages with non-zero release velocity being ignored until forced track-end cleanup. Direct note releases and sustain-pedal releases now honour every legal release velocity without modifying the source MIDI.
- Reworked the playback-section editor into compact rows and made the source and settings panes independently scrollable. At the maintained 1080×720 default, both panes remain usable and the settings pane no longer collapses or requires horizontal scrolling.
- Prevented Pause or Stop from racing an in-flight keyboard batch. Input dispatch and cleanup now share one serialized scheduler boundary and recheck Pause/Stop before a batch is accepted.
- Added focused raw-MIDI immutability, non-zero release-velocity, pause-race, direct-workflow, and default-window geometry tests. The suite now contains 114 tests.

## 2.10.0 - Safer active playback and faster editing

- Locked MIDI loading, conversion dialogs, key profiles, source analysis controls, timing controls, track selection, playback ranges, exports, and settings reset while an immutable plan is running. Direct loads and drag/drop are guarded as well as visible buttons and menu actions.
- Added a ten-entry recent MIDI menu that records successful loads only, deduplicates resolved paths, retains temporarily missing files as disabled entries, and can be cleared from the File menu.
- Added Ctrl+O to open a MIDI and Ctrl+R to reload the current MIDI.
- Added in-place playback-range editing. Selecting a row loads its source boundaries into the editors; **Update selected** preserves its Play/Omit role and label, re-sorts the table, invalidates the old plan, and persists the change.
- Added settings and offscreen Qt regression coverage for recent-file normalization, range editing and restoration, shortcuts, and the complete active-playback control lock.

## 2.9.0 - Selective playback and lower-overhead scheduling

- Added persistent per-MIDI Play and Omit ranges. Multiple Play ranges are merged, Omit ranges are subtracted, and the resulting source intervals are rebased into one prepared playback.
- Added deterministic boundary clipping for sustained notes, configurable pauses between non-contiguous sections, selection diagnostics, and selection-aware SCUM score/key-event export.
- Added user-controlled looping of the prepared playback with the existing Stop, F8, focus-loss, and final key-release safety paths.
- Added a compact Playback sections editor with `HH:mm:ss.zzz` range controls, range table, remove/clear actions, loop control, and selection-aware Prepare/Play labels.
- Persisted section ranges by absolute MIDI path without altering remembered track choices or source files.
- Added scheduler precompilation so timestamp batches and integer nanosecond offsets are calculated once and reused across loops.
- Added same-timestamp input batching. Event order is preserved and staggered notes are never collapsed; a 100-triad zero-stagger fixture reduces 600 keyboard events to 200 `SendInput` calls.
- Cached Windows virtual-key/scan-code resolution and enabled 1 ms Windows timer resolution only for the lifetime of the playback thread.
- Added runtime metrics for events, batches, completed loops, late events, and average/maximum dispatch lateness.
- Disabled track, section, Prepare, and export controls during active playback so the running immutable plan cannot be confused with newly edited state.
- Added focused selection, persistence, scheduler, looping, batching, clipping, omission, full-timeline equivalence, and UI regression coverage.

## 2.8.0 - Source-aware conversion overhaul

- Added a deterministic import-time score analyser that classifies track roles from names, register, activity, monophony, and real chord structure.
- Replaced blanket non-percussion selection with a lead-first recommendation of at most one lead, useful bass, and useful harmonic support. The UI now shows each detected track role.
- Added source-character analysis for melody, light polyphony, chord-led, and dense scores using exact attacks, clearly rolled sustained chords, attack polyphony, rhythmic spacing, note durations, and peak density.
- Made **Optimal Sounding** the desktop default. It derives arrangement, chord recognition, mapping, polyphony, note cleanup, chord roll, hold timing, density, retrigger gaps, and octave-bank timing for every selected score.
- Ensured the analyser and planner work on settings copies and never silently mutate saved user configuration.
- Preserved real-source automatic chord recognition without generating harmony, borrowing accompaniment into melody mode, scale quantisation, or source-MIDI rewriting.
- Retained **SCUM Safe** and **Custom**, hid advanced controls until Custom is selected, and removed obsolete timing jitter plus the source-specific Guitar Smooth branch.
- Migrated Guitar Smooth, Balanced, and Maximum Fidelity identities to Optimal Sounding while preserving exact Custom settings.
- Invalidated pre-analysis blanket track selections once, then preserved subsequent user track choices normally.
- Added effective policy and analysis metrics to playback diagnostics and the prepared-song summary.
- Replaced the accumulated release-history README with a concise current workflow; historical details remain in this changelog and project records.

## 2.7.0 - Professional source-backed SCUM score conversion

- Added automatic performed-chord recognition to Game-optimised arrangement. It derives a conservative timing window from the MIDI's own rhythmic spacing, requires meaningful shared sustain, and aligns only real source notes.
- Kept fast material safe: the adaptive window falls back to the existing 12 ms tolerance for dense scores. The current Rush E fixture produces identical notes, key events, timing, duration, and octave-bank taps in automatic and exact-onset modes.
- Added a visible **Chord recognition** selector. **Automatic performed chords** is the recommended default; **Exact MIDI attacks only** preserves the legacy grouping policy.
- Preserved **Lead melody only** as monophonic and left **Faithful / legacy** timing untouched. No chord tone is generated, inferred, or borrowed.
- Added an auditable **SCUM score CSV** with chord group, voice order, source/mapped note, attack/release, octave bank, SCUM key, and velocity. The existing low-level key-event CSV remains separately available.
- Added conversion diagnostics for detected source chords, performed chords, aligned notes, adaptive window, and total alignment, plus focused fast-run, performed-chord, settings, UI, and export regression coverage.

## 2.6.0 - UVR-separated transcription pipeline

- Installed Ultimate Vocal Remover 5.6 and added a current UVR-model-compatible programmatic runtime using `audio-separator 0.44.3`.
- Selected **BS-RoFormer Viperx-1297** (`model_bs_roformer_ep_317_sdr_12.9755.ckpt`) as the single-model vocals/instrumental default. This avoids the time and 8 GB VRAM pressure of a multi-model ensemble while retaining both real stems.
- Added asynchronous full-mix separation before Basic Pitch in Song Transposer. Users explicitly select the instrumental/backing or vocals/lead stem to transcribe, while both WAV stems remain visible on disk.
- Guitar / arpeggio automatically prefers instrumental; Smooth lead / vocal prefers vocals. Manual stem selection is sticky during later profile changes.
- Added a separate runtime, model cache, readiness marker, secondary-drive pointer, CUDA 12.8 PyTorch pin, FFmpeg/GPU/model validator, and install/repair entry points.
- Detected and corrected a CPU-only PyTorch resolution during installation; NVIDIA systems are now explicitly switched to official CUDA wheels and must expose CUDA before the runtime is marked ready.
- Preserved direct Basic Pitch conversion, MIDI-only Song Transposer processing, the monophonic Lead Melody contract, SCUM input safety, and current Rush E behavior.
- Added atomic stem publication, overwrite confirmation, worker command isolation, process-chain UI tests, packaged resources, and installer/runtime regression tests.
- Fixed a real direct-MP3 export failure found during validation: audio-separator inherited the MP3 subtype for WAV output, logged an unsupported-encoding error, wrote zero-byte stems, and returned success. The worker now decodes every source to stable PCM first and validates each WAV before atomic publication.

## 2.5.0 - SCUM-aware pitch detection and global register matching

- Added selectable Basic Pitch detection focus: guitar E2-E6, general SCUM C2-C7, and the legacy full model range. Guitar / arpeggio selects the tighter guitar band by default; manual choices remain untouched when the arrangement profile changes.
- Added **SCUM Pitch Match**, a new mapping mode that chooses one whole-song octave shift before applying residual three-bank folding. This preserves intervals that per-note octave folding can collapse.
- Kept pitch matching chromatic and deterministic. It never infers a scale, rewrites isolated pitch classes, or changes the song's key.
- Updated Guitar Smooth to use the new matcher while retaining Melody contour, Smart three-octave, Fold, and Strict modes as explicit fallbacks.
- Added diagnostics for the automatic octave shift, exactly represented notes, and residual octave-folded notes.
- On the 1,163-note clean House lead, exact consecutive-interval preservation improves from 1,051/1,162 to 1,162/1,162. On the 865-note rough guitar lead it improves from 660/864 to 864/864.
- Real isolated Basic Pitch validation passed on the user's WAV and full House guitar MP3. Guitar focus narrowed the stem's detected range from MIDI 28-102 to 40-87 and raised time/pitch-matched reference attacks from 61 to 74.
- Proved existing `melody3` behavior is output-equivalent with the user's currently saved Rush E plan: digest `42d98ff3fed7d88b80e08a1e7276a8555414e651190ef81cf75961de671434f1` before and after the feature.

## 2.4.4 - Melody rollback and output-equivalent optimisation

- Fully reverted 2.4.3's source-support selection, generated chord tones, lead-led diagnostics, and polyphonic Melody contour changes after the user confirmed they sounded substantially worse in SCUM.
- Restored **Lead melody only** to the proven 2.4.2 contract: one inferred lead-track note per onset regardless of Maximum chord notes.
- Preserved the user's successful Game-optimised Rush E path exactly, including two-note selection, current timing, register mapping, key events, and standalone Ctrl/Shift bank taps.
- Replaced Mido's full merged-track clone with a stable in-place tempo scan. Rush E loads 63.5% faster and the large multitrack House score 69.7% faster, with every parsed note exactly equal to the legacy implementation.
- Made retrigger and rolling-density replacement constant-time in the retained output list and cached per-group note priorities. Dense Rush planning fell from roughly 0.55 seconds to roughly 0.40 seconds with an identical complete plan digest.
- Replaced Song Transposer's repeated whole-score core-window scans with a 128-pitch weighted histogram. Rush processing fell from 1.39 seconds to 0.13 seconds and the raw House guitar from 0.19 seconds to 0.02 seconds, with identical processed-note and diagnostic digests.
- Added regression coverage for melody-only behavior at high polyphony settings, stable same-tick tempo precedence, retrigger replacement, melody-protected density replacement, and histogram equivalence.

## 2.4.3 - Lead-led smart chord arrangement (withdrawn)

- This experiment was rejected after in-game audition and is fully reverted in 2.4.4. It is retained here only as release history.

- Reworked **Lead melody + smart chords** into a protected-lead pipeline: infer the main track once, preserve its top melody note at every lead onset, and discard accompaniment-only onsets.
- When multiple tracks are selected, chooses only near-simultaneous, consonant real support below the lead. Source thirds and fifths are preferred over distant, dissonant, or melody-obscuring notes.
- Calculates missing major/minor triad tones from a weighted 1.8-second local harmonic context only after useful real support has been exhausted.
- Honours **Maximum chord notes** at one or two voices and enforces a hard three-voice ceiling for this SCUM-focused mode, even if a higher global value is selected.
- Keeps calculated support below the melody, slightly quieter, rhythmically aligned, and within a compact voicing. The one-note Guitar Smooth default remains unchanged.
- Makes Melody contour mapping protect the lead's original octave when a chord crosses a global SCUM octave-bank boundary; support folds into that bank instead of dragging the melody into the wrong register.
- Adds diagnostics for real and generated support counts plus regression coverage for source-first selection, calculated fills, dissonance rejection, hard voice limits, discarded support-only onsets, and lead-register protection.

## 2.4.2 - Standalone SCUM octave-bank taps

- Corrected the physical input model after the user clarified that Ctrl and Shift step a persistent three-layer octave bank; they are not modifiers that should overlap the note.
- Releases all sounding musical keys, waits the configured release interval, taps Ctrl/Shift alone for 18 ms, releases it, waits for the bank to settle, and only then plays the next note.
- Eliminates every generated Shift+note and Ctrl+note combination, including accidental Shift+I menu activation.
- Emits no octave input while notes remain in the same bank. A two-layer crossing emits two discrete taps in the required direction.
- Retains the chromatic C-to-C pitch bank. SCUM exposes sharps but no separately labelled flats; enharmonic flats map to the equivalent sharp.
- Added regression coverage for persistent bank selection, two-step crossings, exact 18 ms tap holds, balanced key state, and zero octave-key/note-key overlap.

## 2.4.1 - Tempo, Shift, and musical-flow correction (superseded Shift interpretation)

- Fixed same-tick tempo ordering so a real tick-zero tempo replaces the synthetic 120 BPM fallback instead of being overwritten by it. The reported `Rush E.mid` now parses and exports at 270 BPM rather than playing at practice speed.
- Replaced phrase-latched upper-octave Shift with a per-onset pulse. Guitar Smooth presses Shift 20 ms before an upper attack and releases it 18 ms after note-on, limiting the normal hold to 38 ms and preventing Shift from leaking into later `I`/menu combinations.
- Added **Melody contour (three octaves)** for monophonic parts. It preserves the source register throughout SCUM's representable range instead of applying Smart mode's short-excursion folding.
- Changed Guitar Smooth from a conservative practice preset to a flowing playback preset: 1.12x speed, 18 starts/s, 40 ms source retrigger filtering, 90 ms planned holds, 20 ms key gaps, and 10/20 ms modifier release/settle timing.
- Refreshes maintained named-preset values when settings are loaded, while preserving manual settings under the `custom` identity.
- Scales Song Transposer's micro-onset window by source tempo, retaining legitimate fast sequential attacks in scored MIDI.
- Prevents prepared `Lead Melody` / `Light Support` exports from being filtered a second time by the arranger's raw source-duration cutoff.
- Updated Basic Pitch defaults to onset 0.45, frame 0.30, and 90 ms minimum raw note, and preserves only strong same-pitch reattacks rather than fragmented transcription tails.
- Reordered Song Transposer profiles so **Guitar / arpeggio stem** is the recommended default and **Smooth lead / vocal** is the explicit contour-smoothing alternative.
- Added regression coverage for 270 BPM tick-zero tempo, short Shift pulses, stale named-preset migration, tempo-aware onset grouping, prepared-source planning, reattack cleanup, and Qt settings isolation.

## 2.4.0 — Guitar-smooth musical planning

- Added a dedicated **Guitar Smooth** playback preset with lead-only arrangement, 90 ms source-note rejection, one-note polyphony, stable smart-register mapping, 105 ms minimum holds, and conservative key/modifier timing.
- Added a post-optimisation smart-register guard that folds enclosed one-to-three-onset octave detours into their surrounding register when they return within 1.2 seconds; longer register phrases are preserved.
- Fixed **Lead melody only** occasionally selecting a sparse Light Support/bass track because its longer notes outweighed the real, denser lead track.
- Added track-activity scoring and made melody mode stay entirely on the inferred lead track.
- Fixed the physical retrigger guard violating the UI's minimum played-note promise by cutting a note back to 10 ms. Colliding retriggers are now delayed enough to preserve both the configured hold and key-up gap.
- Added visible risk warnings for multitrack Faithful playback, sub-35 ms source filters, and sub-45 ms played-note settings.
- Suppressed only librosa's successful M4A decoder-fallback/deprecation notices; actual decode failures still surface.
- Renamed the recommended transposer choice to **Smooth in-game guitar** and automatically applies the matching playback preset when that output is loaded.
- On the active 851-note House of the Rising Sun arrangement, Guitar Smooth rejects 87 short lead attacks, excludes all 115 support notes, retains 649 lead notes, guarantees a 105 ms physical minimum, and stabilizes 13 brief register groups.
- Under the user's existing permissive settings, the smart-register guard reduces the same arrangement from 17 modifier-state changes to 7 without deleting its support notes or sustained register phrases.
- Added regression coverage for short register-excursion folding, sustained-register preservation, lead-track inference, the new preset, and minimum-hold-safe retriggers.

## 2.3.3 — Malformed MIDI data-byte recovery

- Fixed `data byte must be in range 0..127` when loading third-party MIDI files containing illegal note/controller values.
- Kept strict parsing as the first attempt and enabled Mido's narrow `clip=True` recovery only for that exact out-of-range data-byte error.
- Undefined status bytes, broken chunks, truncated tracks, and unrelated corruption still fail normally.
- Added a visible warning to recovered projects and propagated it through Song Transposer results.
- Recovered the user's `Rush E.mid`, whose first invalid event was a note-on velocity of 129 at file offset 25,410.
- Processed all 19,043 source notes into a 1,709-note monophonic Clear Melody; Balanced playback retains 1,624 notes and emits 3,248 events.
- Added parser, recovery-warning, unrelated-corruption, and transposer-propagation regression coverage.

## 2.3.2 — Clean audio-worker diagnostics

- Removed misleading Basic Pitch warnings about absent CoreML, TFLite, and ONNX runtimes. MusicalScumme uses its validated TensorFlow `nmp` SavedModel and does not require those optional backends.
- Suppressed TensorFlow's informational CPU feature banner by setting its native log level before Basic Pitch imports.
- Forced the isolated audio worker to start with `-X utf8` as well as `-I`, fixing Windows `cp1252` output being decoded by Qt as `�`.
- Made the worker's newline-delimited JSON ASCII-safe while preserving the original Unicode text after `json.loads`.
- Continued to expose actual inference errors and non-zero worker exits.
- Validated the complete 4:22 House of the Rising Sun guitar MP3: inference completed in 36 seconds, emitted no optional-backend or CPU-banner noise, and wrote the expected 1,328-note raw MIDI.

## 2.3.1 — Phrase cleanup and guitar-aware processing

- Consolidated likely Basic Pitch double-attacks within a profile-specific micro-onset window instead of passing them downstream as jittery extra notes.
- Added phrase-aware octave stabilization for isolated register spikes. Consecutive spike candidates are solved together and shifts are limited to one octave.
- Added a dedicated **Guitar / arpeggio stem** profile that removes transcription noise while preserving recurring bass-to-treble picking resets.
- Kept structural arpeggio resets separate from genuine isolated octave glitches instead of treating every large interval as an error.
- On the supplied reference, Clear Melody now retains 865 lead notes, reduces sub-80 ms attacks from 83 to 23, repairs nine additional phrase spikes, and reduces large jumps from 101 to 65.
- Balanced planning of the Clear Melody result now retains 862/865 notes and emits 1,724 events, compared with 890/924 notes and 1,780 events in 2.3.0.
- Added regression coverage for micro-attack consolidation, phrase octave stabilization, and preservation of guitar arpeggio resets.

## 2.3.0 — Dedicated Song Transposer

- Added a first-class Song Transposer for combined audio transcription and deterministic SCUM-ready MIDI preparation.
- Added Clear melody, Melody + light support, and Fuller playable arrangement profiles.
- Added weighted core-register detection, low-confidence overtone suppression, contextual octave repair, onset consolidation, and dynamic-programming global melody selection.
- Exported lead tracks are truly monophonic; a lead note ends before the next attack rather than sustaining accidental transcription polyphony.
- Audio workflows retain both user-confirmed outputs: the raw transcription and the processed MIDI.
- Existing MIDI files can be processed directly without invoking Basic Pitch.
- The source file cannot be selected as the processed destination, and raw/processed audio outputs must be distinct.
- Processed MIDI loads through the existing Game-optimised reliability stage; input scheduling and SCUM key mapping remain separate.
- Added engine, MIDI round-trip, overwrite-safety, dialog, and main-window regression coverage.
- Processed the supplied House of the Rising Sun guitar transcription from 1,328 raw notes into a 924-note monophonic lead, removing 230 overtone artifacts and repairing 20 octave errors.

## 2.2.1 — Packaged Audio Runtime Isolation Hotfix

- Fixed `ImportError: Module use of python312.dll conflicts with this version of Python` during packaged audio-runtime validation.
- Root cause: running a Python 3.10/3.11 validator or worker by path inside PyInstaller's Python 3.12 `_internal` directory placed incompatible packaged `.pyd` files on the child interpreter's import path.
- Added Python isolated mode to interpreter probes, virtual-environment creation, pip repair, validation, standalone repair, and audio conversion worker launches.
- Fixed a second validator failure that rejected Basic Pitch's valid TensorFlow SavedModel directory because it expected a single model file.
- Added a validated-runtime marker; an incomplete or failed repair is no longer advertised as ready for audio conversion.
- Kept repair non-destructive and reduced repetitive pip output in the in-app installer log.
- Added regression coverage for cross-version isolation, SavedModel directories, readiness state, and worker commands.

## 2.2.0 — SCUM Performance Controls and Anti-Jitter Planning

- Added visible **SCUM Safe**, **Balanced**, **Maximum Fidelity**, and **Custom** performance presets.
- Added configurable maximum chord notes, per-note chord stagger, minimum played note, physical retrigger gap, maximum note starts, modifier release delay, modifier settle delay, and playback speed.
- Changed chord timing from a total-width spread to a true per-note stagger.
- Rolled chords now play the likely melody first, then bass, then inner harmony.
- Added a physical key reuse planner that clips or delays conflicting notes to guarantee the configured key-up gap.
- Added safe Ctrl/Shift transition guards with separate note-release and modifier-settle windows.
- Added modifier pre-roll so the first transposed note is not sent before the octave state has settled.
- Existing 2.1.x settings migrate as Custom instead of being overwritten by a named preset.
- Added diagnostics for preset, chord stagger, retrigger gap, modifier delays, and modifier-switch count.
- Added UI regression coverage and rendered a new 2.2 interface preview.
- 37 automated tests pass; Python compilation, Ruff, and offscreen Qt preset behaviour pass.

## 2.1.3 — Windows PowerShell Validation Quoting Repair

- Fixed audio-runtime validation failing with `NameError: name 'basic' is not defined` after all dependencies had installed successfully.
- Root cause: Windows PowerShell 5.1 corrupted embedded quotes in the multiline `python -c` validation argument, changing `metadata.version("basic-pitch")` into `metadata.version(basic-pitch)` before Python received it.
- Replaced inline validation code with the dedicated `validate_audio_runtime.py` helper, invoked by file path so PowerShell cannot rewrite Python string literals.
- Updated both the normal installer and the standalone repair path to use the same validator.
- Added explicit checks for the pinned setuptools version, `pkg_resources`, Mido, Basic Pitch inference, and the packaged model file.
- Reduced irrelevant TensorFlow and optional-backend noise during validation while preserving actionable failures.
- Added the validation helper to PyInstaller resources and expanded regression tests to prevent a return to fragile inline native-process code.
- Existing Basic Pitch/TensorFlow downloads are retained; this repair does not require reinstalling the audio environment.

## 2.1.2 — Basic Pitch Runtime Compatibility Repair

- Fixed audio-runtime validation failing with `ModuleNotFoundError: No module named 'pkg_resources'`.
- Root cause: setuptools 82+ removed `pkg_resources`, while Basic Pitch 0.4.0 currently resolves `resampy 0.4.2`, which still imports it at runtime.
- Pinned the isolated audio runtime to setuptools 80.10.2, the final compatible release line before removal.
- Added a constraints file so later dependency resolution cannot silently upgrade setuptools back to an incompatible version.
- Added an idempotent in-place repair path that preserves the already-downloaded TensorFlow/Basic Pitch environment.
- Changed `Repair Audio Tools.bat` to repair in place instead of deleting and redownloading the complete runtime.
- Expanded validation to check `pkg_resources`, Basic Pitch import, the packaged model path, and installed versions.
- Added regression tests covering the compatibility pin, repair behaviour, and packaged constraint resource.

## 2.1.1 — Audio Runtime Bootstrap Repair

- Fixed `py.exe : No suitable Python runtime found` terminating the audio-tools installer before fallback detection could run.
- Added non-terminating probes for Python 3.10/3.11 through the launcher, PATH, known installation folders, an explicit `-PythonPath`, and the private MusicalScumme runtime.
- Added automatic per-user bootstrap of official signed Python 3.11.9 when no compatible runtime is installed.
- Added Authenticode signer validation before executing the downloaded Python installer.
- The private bootstrap does not alter PATH, file associations, shortcuts, or the system launcher.
- Added automatic repair of incomplete audio virtual environments and persistent installation logs.
- Added `-NoBootstrap`, `-PythonPath`, and reliable `-Reinstall` installer controls.
- Fixed the same `py.exe`-exists-but-has-no-runtime fallback bug in `build_exe.ps1`.

## 2.1.0 — Intelligent Arrangement and Audio Transcription

### Added

- New deterministic `arranger.py` stage between MIDI parsing and SCUM key planning.
- **Game-optimised arrangement** mode that preserves a lead voice, useful bass, and selected harmony.
- **Lead melody only** mode for maximum playback clarity.
- **Faithful / legacy** mode for comparison with the previous selection behaviour.
- MIDI channel 10 percussion detection, default filtering, and musical-track auto-selection.
- Configurable note-density cap, minimum source-note length, retrigger gap, and velocity-based articulation.
- Dynamic-programming three-octave register planner to reduce rapid Ctrl/Shift switching.
- Optional MP3/WAV/FLAC/OGG/M4A to MIDI conversion using Spotify Basic Pitch.
- Isolated per-user audio runtime under `%LOCALAPPDATA%\MusicalScumme\audio-runtime`.
- Out-of-process audio worker with JSON progress reporting and atomic MIDI output.
- Audio runtime installer scripts and PyInstaller resource packaging.
- Ruff configuration and release linting.
- Pinned tested core dependencies and third-party notices.
- Regression tests for intelligent arrangement, audio MIDI writing, register planning, and velocity expression.

### Changed

- Default arrangement is now **Game-optimised** while pitch mapping remains safe one-octave fold.
- The prepared-song summary now identifies the arrangement mode and reports all simplification causes.
- Percussion-only tracks are labelled and excluded from automatic track selection.
- Smart three-octave mode now plans modifier state globally instead of choosing an octave greedily per onset.
- Core and audio dependencies are deliberately separated to keep normal startup lightweight and reliable.

### Preserved

- User-confirmed key profile `Y I O P G H J K L B N Q E`.
- `Q` as the B-note binding.
- Scan-code `SendInput` default and corrected Win32 `INPUT` ABI.
- F8 emergency stop, foreground protection, focus-loss cleanup, custom profiles, dry run, CSV export, and atomic settings backups.

### Validation status

- 19 automated tests pass.
- Python compilation passes.
- Ruff passes.
- Main window and audio dialog construct offscreen.
- Windows SCUM playback and live Basic Pitch inference still require user-machine validation.

## 2.0.2 — SendInput ABI and Q Binding Hotfix

- Corrected the full Win32 `INPUT` union to 40 bytes on x64 / 28 bytes on x86.
- Fixed `SendInput failed: error 87` caused by an undersized ctypes structure.
- Corrected the B-note binding to `Q`.
