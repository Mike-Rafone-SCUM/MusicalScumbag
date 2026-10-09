# MusicalScumme Durable Decisions

## 2026-10-06 — Treat stems before recovering quiet notes

- Keep UVR separation, learned vocal de-echo/dereverb and blended denoise in the isolated UVR worker. Preserve raw separated WAVs, exact stereo frame alignment and a complete provenance receipt; requested treatment must not reuse an older untreated pass.
- Use vocal cleanup models on vocals only. Preserve instrumental details rather than remove source instruments with a singing-specific dereverb model. Keep separation-only and dereverb-only comparisons available.
- Explicitly override the pinned library's segment setting to 256 frames; its default otherwise silently uses 801. Keep the best preset's three aligned offsets and overlapping windows. Segment length is a memory/quality tradeoff, recorded in provenance.
- Release each model before loading the next. A failed treatment preserves raw stems and previous cleaned outputs, invalidates any old success receipt, and never reports completion.
- Quiet-note recovery remains a separate audio-checked transcription option. Strong measured periodicity and local RMS may recover quiet vocal phrases; brief stable non-octave changes and audio-supported reattacks remain eligible. Backing recovery keeps existing model pitches and attacks only, with persistent spectral support and conservative harmonic rejection.
- Preserve native model MIDI and keep source transcription independent of SCUM arrangement, transpose, voice ceilings and keyboard planning. Execution, note counts and synthetic regressions do not establish musical accuracy.

Project-wide durable constraints and historical decisions are recorded in `PROJECT_CONTEXT.md`. Add dated entries here when a task creates or changes an architecture, public API, file layout, fallback, UI constraint, input mapping, performance strategy, dependency, or bug-prevention rule.

## 2026-07-13 — Isolate packaged audio child processes

- Invoke every Python 3.10/3.11 audio-runtime operation that can execute a script beside PyInstaller resources with `-I`, including validation and the audio worker. The main application may be built with a different Python minor version, and its `_internal` extension modules must never enter the child interpreter's import path.
- Treat either a model file or a TensorFlow SavedModel directory containing `saved_model.pb` as a valid Basic Pitch model artifact.
- Use `.musicalscumme-audio-ready-v1` as a success-only readiness marker. The UI must not advertise an unvalidated or partially repaired runtime as available, and repair continues to reuse the existing large dependency stack.

## 2026-07-13 — Dedicated deterministic Song Transposer stage

- Keep transcription cleanup in `musical_scumme/song_processor.py`, between MIDI parsing and the existing arranger/planner. It may write processed MIDI but must not know about Qt widgets, keyboard bindings, input backends, or SCUM focus.
- Use a global melody path rather than selecting a local highest/loudest note at each onset. Rough Basic Pitch stems contain short high harmonics that are individually plausible but musically discontinuous.
- Export the calculated Lead Melody as a monophonic track. Optional support is written separately so the existing Game-optimised stage can still enforce SCUM reliability limits.
- Never overwrite the input MIDI. For audio, require separate user-confirmed raw-transcription and processed-MIDI paths and preserve both outputs.

## 2026-07-13 — Separate melody glitches from structural arpeggio resets

- Clear Melody may stabilize an isolated register spike only when both adjacent jumps exceed one octave, the phrase endpoints remain within a fifth, and a one-octave alternative materially improves the complete contour.
- Solve consecutive eligible spikes together so a correction cannot simply move the discontinuity to the neighbouring note.
- Keep **Guitar / arpeggio stem** as a separate profile with phrase stabilization disabled. Recurring bass-to-treble picking resets are musical structure, not generic transcription defects.
- Consolidate likely transcription double-attacks before melody selection using profile-specific onset windows; do not globally quantize or rewrite expressive source timing.

## 2026-07-13 — Keep audio-worker diagnostics actionable and UTF-8 safe

- Launch the Python 3.11 audio worker with `-I -X utf8`: isolation prevents packaged Python contamination, while explicit UTF-8 prevents Windows `cp1252` pipe output from being misdecoded by Qt.
- Set TensorFlow's native log level before Basic Pitch imports and suppress warnings about absent CoreML, TFLite, and ONNX because the product intentionally uses the validated TensorFlow SavedModel.
- Keep actual exceptions, error-level records, non-zero exits, and runtime-validation failures visible.
- Encode worker protocol records as ASCII-safe JSON; `json.loads` restores Unicode status messages and paths in the main process.

## 2026-07-13 — Recover only out-of-range MIDI data bytes

- Always attempt strict MIDI parsing first.
- If and only if Mido raises `data byte must be in range 0..127`, retry with its supported `clip=True` mode and expose a warning that illegal values were clipped to 127.
- Carry the warning through `MidiProject`, the main-window warning area, and Song Transposer results.
- Do not recover undefined status bytes, invalid chunk structure, truncated tracks, or unrelated corruption.
- Never rewrite the malformed source file; recovery exists only in the in-memory parse and separately exported output.

## 2026-07-13 — Stabilize converted guitar playback without flattening phrases

- Add **Guitar Smooth** as an explicit performance preset rather than changing existing Balanced or user-custom settings. It uses Lead melody only, Smart three-octave mapping, one-note polyphony, a 90 ms source cutoff, a 105 ms physical minimum hold, and conservative retrigger/modifier delays.
- Interpret Lead melody only as a track-level role. Infer the lead with track activity as well as monophony, register, velocity, and duration, then exclude other tracks before onset selection.
- After global smart-register optimisation, fold an enclosed excursion only when it spans at most three onset groups and returns to the same register within 1.2 seconds. Preserve longer bass/high-register phrases and phrase-boundary changes.
- When the same physical SCUM key is needed too soon, delay its next attack enough to preserve the configured hold and key-up interval. Never silently reduce a configured minimum hold to the old 10 ms internal floor.
- Treat librosa's `PySoundFile failed. Trying audioread instead.` message as non-actionable only when its fallback proceeds. Suppress that exact notice and its audioread deprecation warning in the isolated worker; do not suppress decode exceptions or unrelated warnings.

## 2026-07-15 - Preserve tempo, pulse Shift, and keep prepared songs flowing

- Keep the existing Smart three-octave strategy available, but make Guitar Smooth use a separate **Melody contour (three octaves)** mode. In-range register accuracy outranks modifier-switch reduction; Smart mode's short-excursion folding does not apply to Melody contour.
- Superseded later on 2026-07-15: the initial 2.4.1 repair pulsed `LSHIFT` around each upper note, but the user confirmed Ctrl/Shift change a persistent octave bank and must never overlap a musical key. The corrected decision is recorded below.
- Treat a named performance preset as a maintained policy, not a frozen settings snapshot. On load, refresh its controlled values from `PERFORMANCE_PRESETS`; manual edits remain protected because they change the identity to `custom`.
- Guitar Smooth is a flow preset, not a practice preset: 1.12x speed, 18 starts/s, 40 ms source retrigger filtering, 90 ms planned minimum hold, 20 ms physical key gap, and 10/20 ms modifier release/settle. SCUM Safe remains the slower fallback.
- Sort tempo changes by tick only. Stable same-tick discovery order lets a real tick-zero tempo replace the synthetic 120 BPM fallback; sorting the full `(tick, tempo)` tuple is forbidden because it stretches fast songs to 120 BPM.
- Scale Song Transposer's micro-onset consolidation window by `120 / source_bpm`, clamped to 12 ms and the profile maximum. Basic Pitch's 120 BPM output keeps the tested window, while fast scored MIDI retains legitimate sequential attacks.
- A Song Transposer export identified by selected `Lead Melody` / `Light Support` track names bypasses the second source-duration filter during planning. Raw/unprepared MIDI retains that filter.
- Apply same-key and octave-bank timing constraints in one forward group schedule. Bank transitions count as timing boundaries, and emitted note keys must retain the configured safety floor without permanently stretching the source timeline.

## 2026-07-15 - Treat Ctrl and Shift as standalone octave-bank taps

- Keep the 13-key bank chromatic: C, C-sharp, D, D-sharp, E, F, F-sharp, G, G-sharp, A, A-sharp, B, high C. SCUM has no separately labelled flats; use the enharmonic sharp.
- Model SCUM as a persistent three-state octave bank: lower `-1`, base `0`, upper `+1`. Ctrl steps down and Shift steps up. Crossing lower-to-upper or upper-to-lower requires two separate taps.
- Before any bank transition, release every sounding musical key and wait `modifier_release_ms`. Tap each octave key alone for 18 ms, release it, wait `modifier_settle_ms`, and only then press the next musical key.
- Never emit Shift+note or Ctrl+note combinations. Remaining in the same bank emits no octave-control event.
- Retain the `modifier` field and legacy diagnostics for stored-plan compatibility, but interpret them as target octave-bank state rather than a physically held modifier.

## 2026-07-15 - Make melody mode source-first and harmonically complete

- Keep the stored `melody` arrangement identifier for settings compatibility, but present it as **Lead melody + smart chords**.
- Treat the inferred lead track as protected structure: its onset groups define the output rhythm, its selected top note remains the top voice, and accompaniment-only onsets are discarded.
- Fill Maximum chord notes in two passes. First rank real, near-simultaneous support from other selected tracks by consonance, compactness, track quality, duration, and pairwise chord fit. Then calculate only unfilled voices from the locally weighted major/minor triad containing the lead.
- Keep generated notes deterministic, compactly voiced below the lead, slightly quieter, and rhythmically identical to the lead. They remain arranger output and must not alter the source MIDI.
- Interpret Maximum chord notes as one protected lead, lead plus one support, or lead plus two supports. Lead-led mode hard-stops at three voices because SCUM is not reliable above three; other arrangement modes retain their existing global setting behavior.
- In Melody contour mapping, preserve the top lead's octave ahead of support notes. Fold support into the one global SCUM bank when an exact cross-bank chord is physically impossible.

## 2026-07-15 - Revert generated harmony and require output-equivalent optimisation

- Supersede and fully reverse the preceding 2.4.3 smart-chord decision. The live result sounded substantially worse even though individual generated intervals passed static consonance rules.
- Restore **Lead melody only** as an intentionally monophonic mode: infer one lead track, select one lead note per onset, exclude every other track, and ignore Maximum chord notes in this mode. Do not generate or borrow harmony here.
- Keep real-source chord reduction in **Game-optimised** and source-faithful chords in **Faithful / legacy**. The user's successful two-note Rush E result uses Game-optimised arrangement and must not be altered by the melody rollback.
- Permit hot-path optimisation only with complete output-equivalence evidence. Parsed MIDI notes, arranged/planned notes, key events, timestamps, warnings, diagnostics, and Song Transposer results must match the pre-optimisation path.
- Build the tempo map by scanning existing track messages for `set_tempo` events in track order, then stable-sort by tick. Do not use `mido.merge_tracks()` merely for tempo discovery because it clones and validates the complete score.
- Use indexed/tombstoned result replacement for retrigger and density filters, cache per-onset note priority, cache tick-to-millisecond conversion, and aggregate Song Transposer core-range weight into 128 pitch bins. These are performance strategies, not musical-policy changes.

## 2026-07-15 - Match SCUM by global register fit, not scale quantisation

- Treat SCUM's pitch limit as a C3-C6 register and global-bank problem, not a missing-pitch-class problem. The 13-key bank is chromatic, so individual notes must never be snapped to a guessed major/minor scale.
- Add `match3` as a separate mapping mode. Select one duration/velocity-weighted whole-song octave shift that maximises exact C3-C6 coverage, then use the existing contour-aware three-bank planner only for residual outliers and C-boundary choices.
- Preserve Melody contour, Smart three-octave, one-octave Fold, and Strict modes. Existing custom settings and plans do not migrate to `match3`; Guitar Smooth intentionally adopts it for newly prepared monophonic guitar/melody playback.
- Give Basic Pitch a profile-aware frequency focus before inference: E2-E6 for Guitar / arpeggio, C2-C7 for general/vocal work, and an explicit Full model range compatibility option. Never overwrite a focus choice the user selected manually.
- Report the global shift, exact-fit count, and residual fold count. Also disclose the physical tradeoff: exact interval preservation can require more standalone octave-bank taps, so only live SCUM audition determines whether Pitch Match or Melody contour sounds better for a specific song.

## 2026-07-15 - Isolate UVR and choose models by downstream MIDI quality

- Put UVR-compatible separation in its own per-user Python runtime. `audio-separator`, PyTorch, ONNX Runtime, and model weights must never enter the main Qt/playback process or Basic Pitch's TensorFlow environment.
- Use BS-RoFormer Viperx-1297 as the maintained two-stem default. Select it from current supported model scores, then confirm it against the app's real downstream pitch-detection objective rather than trusting stem labels or SDR alone.
- Preserve both vocals and instrumental WAV files at deterministic, user-visible destinations. Transcribe exactly one selected source stem; do not automatically sum stems back together or invent accompaniment.
- Normalize source containers to a known temporary PCM WAV before separation and reject empty/unreadable generated WAVs before publication. Do not trust a zero process exit from the model library as proof that audio export succeeded.
- Keep separation and transcription as consecutive asynchronous `QProcess` operations. A separator completion may start Basic Pitch only after the selected stem exists; no model load, process wait, or song cleanup may block the Qt GUI thread.
- Use a success-only marker and a pointer file for large secondary-drive installs. NVIDIA machines install official pinned CUDA wheels and fail readiness when the GPU is detected but unavailable to PyTorch; non-NVIDIA machines retain an explicit slower CPU fallback.
- Keep the RTX 2070 SUPER-safe MDXC policy at segment 256, overlap 8, batch one, and autocast. Re-evaluate before raising memory use: the real probe used roughly 7.57 GB of 8.19 GB while SCUM was open.
- Do not make Demucs `htdemucs_6s` the guitar default solely because it emits a Guitar-labelled stem. On the user's House reference, Viperx instrumental produced materially better cleaned MIDI attack precision and recall.
- Permit `build_exe.ps1 -OutputRoot <path>` to stage a release away from `dist`. This avoids force-closing a currently supervised MusicalScumme session merely to release packaged DLL locks; the default `dist` layout remains unchanged.

## 2026-07-15 - Recognize performed source chords without generating harmony

- Apply expanded chord recognition only in Game-optimised arrangement. Estimate its window from the score's own inter-onset distribution, clamp it to 45 ms, and require meaningful shared sustain before treating offset attacks as one chord.
- Align accepted real source voices to the earliest selected attack while preserving each note's duration. Do not quantize the complete score, synthesize a missing pitch, or reintroduce 2.4.3 support borrowing/triad completion.
- Keep Lead melody only monophonic and keep Faithful / legacy source-timed. Expose exact-onset grouping as the compatibility fallback.
- Store score-group and voice-order metadata on planned notes. Export the auditable musical SCUM score separately from the low-level key-event timeline, and publish the score CSV through a same-destination temporary file.

## 2026-07-15 - Make source analysis the default conversion policy

- Supersede the maintained Guitar Smooth, Balanced, and Maximum Fidelity identities with one **Optimal Sounding** policy. Keep SCUM Safe as the conservative fallback and keep all historical arrangement/mapping controls available only through Custom.
- Analyse a MIDI immediately after strict parsing. Score populated tracks from source-backed evidence only: track name, register, activity, monophony, and real chord attacks. Recommend at most one lead, useful bass, and useful harmonic support instead of selecting every non-percussion track.
- Classify the selected score as melody, light polyphony, chord-led, or dense. Derive arrangement, chord recognition, mapping, polyphony, filtering, chord stagger, hold timing, start density, retrigger gap, and octave-bank timing within fixed SCUM safety bounds.
- Do not generate notes, infer harmony, quantise to a scale, rewrite the source MIDI, or use audio/Qt/input state in the analyser. Reuse the arranger's performed-source chord recogniser so rolled sustained chords cannot be misclassified as melody.
- Work on a copy of `AppSettings` in the planner. Effective automatic values belong in plan diagnostics; source analysis must never silently mutate persisted configuration.
- Preserve transpose and playback speed as explicit basic controls. Reveal manual arrangement/mapping/timing controls only for Custom.
- Remove timing jitter. Stable deterministic attacks are a reliability requirement, and every maintained preset already used zero jitter.
- Clear pre-analysis blanket track selections once using `selection_strategy_version = 2`, then preserve later user selections normally.
- Migrate obsolete named presets to Optimal Sounding on load. Never migrate or rewrite Custom values.
- Group project notes by track once before scoring. Import analysis must remain linear in score size rather than rescanning the full note list for every track.

## 2026-07-16 - Select source time before planning and precompile playback batches

- Introduce `playback_sections.py` as a pure source-time selection layer between selected MIDI tracks and arrangement. Play ranges union together; Omit ranges subtract; retained intervals are rebased with one configurable pause.
- Clip source-backed notes at retained interval boundaries. An omitted middle passage may split one sustained note into two fragments, but section processing must never create a pitch, infer harmony, or alter the source file.
- Re-run arrangement and planning on the selected fragments rather than slicing a finished key-event plan. This guarantees every excerpt starts from the base SCUM octave bank and receives current arrangement, density, retrigger, and modifier safeguards.
- Persist ranges per resolved MIDI path, independently of track selection. Invalid saved entries are ignored or clipped without resetting unrelated settings.
- Permit user-controlled repeat of the immutable prepared plan. Countdown occurs once; every loop and all stop/error/focus exits release held keys.
- Precompile timestamp batches and nanosecond offsets once. Reuse them across loops, batch only equal-timestamp events, and preserve canonical order.
- Cache Windows key/scan-code resolution and scope 1 ms timer resolution to the playback thread lifetime.
- Expose measured scheduler metrics instead of describing performance heuristically: events, batches, late events, average/max lateness, and completed loops.
- Lock plan-affecting and export controls during active playback so the UI cannot imply that edits changed the running plan.

## 2026-07-17 - Keep the visible plan immutable during playback

- Treat file loading, drag/drop, conversion dialogs, key profiles, input mode, arrangement, timing, track selection, playback sections, export, and settings reset as plan-affecting operations. Disable their controls while the scheduler is running and keep a direct guard in `load_file` so shortcuts or future callers cannot bypass the lock.
- Keep Pause, Stop, F8, focus-loss handling, application exit, and final key cleanup available. The lock prevents UI/plan divergence; it must not weaken emergency control.
- Store at most ten successfully loaded MIDI paths in newest-first order. Deduplicate resolved paths, do not record failed loads, and show missing paths disabled rather than deleting them automatically because a removable or network drive may be temporarily unavailable.
- Editing a saved playback range replaces only its source boundaries. Preserve the range's Play/Omit mode and label, re-sort it in source order, invalidate the prepared plan, and persist the replacement for that MIDI.

## 2026-07-18 - Treat untouched MIDI files as the primary workflow

- The normal product path is an original `.mid` or `.midi` file, including direct MIDI Find downloads. Parse, analyse, arrange, and plan it in memory without requiring Song Transposer or a `.scum-ready.mid` derivative.
- Never rewrite an imported source MIDI. Optional conversion tools remain supported from the File menu but do not compete with **Open MIDI** in the primary file row.
- A MIDI `note_off` ends the active note regardless of its legal release velocity. Zero-velocity `note_on` retains the equivalent release meaning, and sustain still defers either release until pedal-up.
- Keep both main panes usable at the maintained 1080×720 default. The dense source/section pane may scroll vertically, while descriptive combo-box choices must not force horizontal scrolling or collapse the settings pane.

## 2026-07-18 - Serialize scheduler input dispatch and cleanup

- Treat `send_batch` and `release_all` as one serialized backend boundary shared by the playback and UI control threads.
- After acquiring that boundary, recheck Pause and Stop before dispatch. If either state won the race, discard the pending dispatch without advancing the schedule.
- Pause, Stop, focus loss, loop cleanup, and final cleanup all use the same serialized release path so a late key-down cannot land after cleanup and remain held.

## 2026-07-27 - Bound dense-score cleanup allocations without changing output

- Calculate Song Transposer's local ±900 ms pitch median with a monotonic sliding 128-bin histogram. MIDI pitch is a fixed small domain, so this removes repeated window-list creation and sorting while retaining the exact median and correction tie-break rules.
- Evaluate performed-chord candidate prefixes incrementally from pitch-class membership, earliest shared release, and shortest duration. Do not allocate and rescan every growing prefix.
- Require randomized legacy-equivalence tests for both paths. These optimisations may reduce CPU and temporary memory only; they must not change notes, timing, chord grouping, diagnostics, or musical policy.

## 2026-07-28 - Separate timed-note planning from physical event emission

- Preserve `build_playback_plan()` as the public orchestration API while implementing its timing and physical-event phases as independently reviewable private stages.
- Use private immutable stage-result dataclasses instead of parallel lists and dictionaries crossing phase boundaries.
- Require deterministic equality of planned notes, key events, timestamps, warnings, diagnostics, counts, and duration across repeated plans in Fold, Strict, Pitch Match, Melody Contour, and Smart modes.

## 2026-07-28 - Add opt-in explainable mapping policies

- Keep all new mapping controls under Custom settings with legacy-equivalent defaults: unlimited bank taps, automatic C-boundary choice, 50% stability, balanced fidelity, and no final bank restoration.
- Apply fidelity and stability preferences to the existing global register-state look-ahead rather than introducing a greedy per-note mapper.
- Enforce the optional bank-tap budget after global planning and short-excursion stabilization. When the rolling one-second budget would be exceeded, keep the current bank and disclose the folded onset group.
- Permit final base-bank restoration only after all musical keys are released, using standalone octave-control taps.
- Export a human-readable explanation for every planned score note without making explanation text part of musical decision-making.

## 2026-07-30 - Use a translucent electric-cyan HUD visual system

- Use frameless Qt top-level windows because Windows requires `FramelessWindowHint` for real per-pixel translucency. Replace the native frame with compact line-icon chrome while preserving minimize, maximize/restore, close, system drag, and all eight system resize zones.
- Preserve every established workflow while presenting the main surface as a supervised in-game overlay.
- Use one electric-cyan accent, translucent charcoal glass layers, low-opacity hairlines, restrained semantic status colors, and a single geometric Windows UI font stack.
- Keep numeric controls bold and visually stable, static labels lighter, and the title/section/body hierarchy explicit.
- Prefer platform-safe alpha compositing to blurring widget content. Qt does not expose a portable backdrop blur, and the application must never capture or process the game framebuffer to fake one.
- Treat 1080×720 two-pane usability, menu access to conversion tools, and the absence of a settings horizontal scrollbar as fixed layout constraints.

## 2026-07-30 - Isolate supervised live MIDI input

- Keep controller input in `live_midi.py`, separate from file parsing, offline arrangement/planning, and scheduled playback. Native callbacks may decode and enqueue supported short messages only; one worker owns all output and safety state.
- Use pinned `python-rtmidi==1.5.8` instead of adding another project-owned Win32 callback ABI. Windows release builds explicitly include its native extension and must verify Windows MultiMedia device enumeration.
- Keep live mapping in SCUM's fixed base 13-key bank. Safe fold is the default and Strict C4-C5 is optional; live mode never changes the persistent Ctrl/Shift octave bank because doing so would release sounding controller chords and requires offline look-ahead.
- Require manual arming and mutual exclusion with scheduled playback. Never persist an armed state or silently reconnect to a different indexed device.
- Reference-count repeated/fold-colliding keys, support per-channel sustain, and route Stop, F8, focus loss, disconnect, callback/backend failure, and application close through one serialized panic cleanup boundary.
- Own deferred startup work with the main window and cancel it during close. In particular, last-file loading must not use a context-free callback that can outlive its window and show a stale modal error.

## 2026-08-01 - Keep playback controls globally reachable in a compact topmost HUD

- F8 remains the scheduler/live-worker emergency-stop poll. Add F9 as global Play/Pause and F11 as global Show/Hide without consuming or weakening F8.
- Mark the main frameless HUD as always-on-top so it remains above normal and borderless-windowed applications. Exclusive fullscreen behavior remains outside Qt's overlay guarantee.
- During scheduled playback, collapse the editor to a compact HUD containing window chrome, Pause/Resume, Stop, progress, and a hotkey reminder. Restore the pre-playback editor panes and requested geometry when playback ends.
- Never persist the compact HUD dimensions as the normal editor size, including when the application is closed during playback.

## 2026-08-01 - Prepare note sustains for the selected SCUM instrument

- Model Guitar, Harmonica, and Banjo as explicit target-instrument profiles with hard real-time sustain ceilings of 2,000 ms, 4,000 ms, and 1,000 ms respectively.
- Keep this musical knowledge in `instrument_profiles.py`; do not place instrument policy in Qt, the MIDI parser, scheduler, or input backend.
- Let Optimal Sounding choose source-aware note lengths up to the target ceiling, then enforce the same ceiling again in final timed-note planning after speed and velocity expression.
- Treat the instrument ceiling as a physical constraint that outranks conflicting Custom minimum or maximum holds. Preserve note attacks and pitches, and disclose every applied cap through plan warnings and diagnostics.
- Persist the target instrument independently of the sound-policy identity. Changing instruments invalidates the prepared plan but does not silently convert Custom settings to a named preset.
- Append new persisted `AppSettings` fields after all established fields so legacy positional construction remains source-compatible. Normalize target-instrument IDs by trimming whitespace and folding case before applying the Guitar fallback.

## 2026-08-03 - Trace source-backed voices across complete phrases

- Replace local onset-by-onset lead guessing with a deterministic dynamic program across the complete arranged source. Local salience remains evidence, but interval size, source-track continuity, rhythmic gaps, and detected phrase boundaries determine the coherent path.
- Relax continuity penalties at source-time phrase boundaries so a real register reset remains eligible. Do not globally flatten octave movement merely to reduce a diagnostic leap count.
- Keep every selected melody, bass, and harmony note source-backed. Voice intelligence may remove notes only; it must never create a pitch, infer a missing chord tone, quantise to a scale, or rewrite imported MIDI.
- Let secondary voice selection use the traced lead plus prior support pitches for voice-leading, consonance, compactness, register role, duration, and velocity. SCUM's configured polyphony and physical density limits remain final authorities.

## 2026-08-03 - Select tracks by musical relationship, not isolated labels

- Match semantic track names by tokens or safe long-word prefixes. Do not allow short substrings such as `low` inside `Slow` to manufacture a bass label.
- Choose the lead from semantic, register, activity, coverage, monophony, and continuity evidence. Admit bass/support only when their onset affinity, temporal coverage, register relationship, and role evidence make them useful beside that lead.
- Reject exact doubled parts before recommending support. Never force a second high melody track into bass merely because the project contains two candidates.
- Analyse musical onset rate independently from physical note-start load, and use time-weighted sounding polyphony, overlap, phrase count, and rhythmic variation in source texture classification.
- Keep the existing public planner call compatible. Optional track-name metadata may improve the source-backed arranger, but callers that provide notes/settings/profile only remain valid.

## 2026-08-03 - Direct solos as protected section-local lead handoffs

- Keep one whole-song primary lead for structural continuity, but evaluate selected tracks again in symmetric beat-relative local windows. Activity, monophony, velocity, register, continuity, semantic role, and deterministic look-ahead may transfer lead ownership for a sustained source-backed passage without requiring silence from the primary track.
- Represent accepted handoffs as immutable source-time solo segments. Game-optimised arrangement reserves the solo as voice one, retains at most one lower foundation voice, rejects competing upper accompaniment, and never creates or retimes a solo attack.
- Do not apply performed-chord alignment or chord stagger to protected solo attacks. A legato solo note sounding over its successor is not evidence that the successor belongs to a rolled chord.
- When the physical start-density ceiling requires solo reduction, prefer endpoints, accents, local extrema, direction changes, spacing changes, and regular phrase landmarks over connector notes. Do not silently raise the maintained SCUM density ceiling.
- Let import analysis recommend one useful sectional solo-handoff track in addition to the primary lead, useful bass, and useful support. Cap the relationship-aware recommendation at four source tracks and continue rejecting exact doubles and simultaneous alternate melodies without sectional evidence.
- Under Optimal Sounding only, keep accompaniment on Safe Fold while applying a whole-octave fit plus melody-contour bank planning to each protected solo segment. This is a plan-local `solo_adaptive` result, not a new persisted default or a rewrite of Custom mapping.
- Every solo bank transition retains the existing standalone Ctrl/Shift release, tap, settle, and no-musical-key-overlap safeguards. Instrument sustain preparation, scheduler cleanup, SCUM bindings, and source-MIDI immutability remain unchanged.

## 2026-08-03 - Make output readiness explicit and prerequisite-aware

- Model the main workflow visibly as Load MIDI, Review Tracks, Prepare, and Play. The active step, output-readiness pill, and next-action guidance are presentation state derived from the existing project, track selection, immutable plan, and output session; they must never alter musical decisions.
- Disable Prepare, Play, and exports until an existing MIDI has at least one selected populated track. Preserve one-click Play by allowing it to prepare an invalidated plan automatically once those prerequisites exist. Live MIDI arming remains independent from file-plan readiness.
- Treat track filtering as view state only. Filtering must never select, deselect, reorder, persist, or otherwise change source-track choices. Empty tracks cannot be selected; recommended-track restoration remains relationship-aware and source-backed.
- Keep preparation visibly busy but output-free. An indeterminate progress state and wait cursor may communicate synchronous deterministic planning, but preparation must never send keyboard input or mutate the source MIDI.
- Validate conversion sources, destinations, runtime readiness, and overwrite separation inline before enabling an operation. Keep the existing defensive validation inside the action handlers as a second boundary.
- Lock conversion inputs while asynchronous child processes run. Do not block the Qt thread, change `QProcess` isolation, or make editable controls imply that a running operation adopted later changes.
- Keep all maintained dialogs usable on a 720 px-high desktop. Song Transposer settings may scroll vertically, but its log/actions remain reachable and horizontal scrolling remains prohibited.
- Treat accessible names/descriptions, keyboard help, action status tips, selectable diagnostics, and invalid-key correction as maintained UX behavior. Existing global F8/F9/F11 safety semantics remain unchanged.
# 2026-08-08 - Restrict import file pickers to supported source types

- Remove the catch-all `All files (*.*)` option from the Song Transposer import picker.
- Keep the picker limited to the supported audio and MIDI extensions; validation remains in the action handler as a second boundary.

# 2026-08-12 - Expand opt-in Custom density controls

- Widen Custom-mode ceilings to 26 chord notes, 240 note starts/s, and 250 ms chord stagger so experiments can retain denser source-backed passages.
- Keep named presets, default values, physical 13-key constraints, and planner safety warnings unchanged. Explain that values above three simultaneous notes trade reliability for density.
