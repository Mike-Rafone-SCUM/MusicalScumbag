# MusicalScumme Regression Checklist

Run from the project root with the project development environment active.

## Required for every behavioural change

1. `python -m compileall -q .`
2. `python -m pytest`
3. `ruff check .`

## Required when PySide6 is available

Construct both the main window and audio-conversion dialog with `QT_QPA_PLATFORM=offscreen`. The test suite may satisfy this requirement when it contains and runs the corresponding construction tests.

## Required for MIDI parser changes

1. Confirm an ordinary `note_off` closes its note regardless of the legal release velocity value.
2. Confirm a non-zero-velocity `note_off` under sustain remains pending until pedal release.
3. Confirm zero-velocity `note_on` retains its standard note-release meaning.
4. Confirm parsing and planning do not modify the imported source MIDI.

## Required for main-window layout changes

1. Redirect Windows `APPDATA` and construct the main window with `QT_QPA_PLATFORM=offscreen`.
2. Confirm the maintained 1080×720 window size is not enlarged by its minimum-size hint.
3. Confirm both source and settings panes remain usable and the settings pane has no horizontal scrollbar.
4. Confirm Song Transposer and Audio-to-MIDI remain available from the File menu when they are not shown in the primary file row.

## Required for instrument preparation changes

1. Confirm Guitar, Harmonica, and Banjo cap wall-clock played-note durations at 2,000 ms, 4,000 ms, and 1,000 ms respectively.
2. Confirm the cap is applied after playback speed and velocity expression and cannot be exceeded by a conflicting Custom minimum hold.
3. Confirm preparation preserves note attacks, pitches, mapping, and balanced final key state.
4. Confirm the target instrument persists through settings round-trip, invalid identities fall back to Guitar, and changing the UI selection invalidates the prepared plan.
5. Confirm plan warnings and diagnostics disclose the target instrument, ceiling, capped-note count, and removed sustain.
6. Confirm actual emitted musical-key hold intervals stay within the ceiling in Fold, Strict, Pitch Match, Melody Contour, and Smart modes.
7. Confirm adding an instrument setting does not shift legacy positional `AppSettings` arguments and padded/mixed-case profile IDs normalize canonically.

## Required for playback section or scheduler changes

1. Confirm no-section processing preserves the complete source-note timeline.
2. Confirm overlapping Play ranges merge and Omit ranges subtract correctly.
3. Confirm sustained notes crossing a section boundary are clipped/rebased without negative or zero duration.
4. Confirm multiple non-contiguous sections use the configured gap and produce a balanced final key state.
5. Confirm only equal-timestamp events are batched and their event order is preserved.
6. Confirm looping repeats until Stop/F8 and releases every key between loops and on final cleanup.
7. Confirm runtime metrics report events, batches, completed loops, and dispatch lateness.
8. Process at least one representative real MIDI with combined Play and Omit ranges and report resolved intervals, selected/dropped/clipped notes, output duration, planned notes, events, batches, and balanced key state.
9. Confirm Pause and Stop cannot leave a key-down dispatched after cleanup when they race an in-flight backend batch.

## Required for MIDI parser recovery changes

1. Confirm strict Mido parsing rejects an out-of-range data byte and `load_midi` recovers it with a visible clipping warning.
2. Confirm recovered velocities/pitches/controllers remain inside `0..127`.
3. Confirm unrelated malformed files still fail instead of entering recovery.
4. Confirm Song Transposer propagates the project warning and writes a strictly readable processed MIDI.
5. Process `E:\Users\james\Downloads\Rush E.mid` when available and report source/retained notes, range, cleanup counts, overlaps, remaining large jumps, and Optimal Sounding plan size.

## Required for audio installer or runtime changes

1. Run the focused installer, audio-tools, and UI process-orchestration tests.
2. Confirm `install_audio_tools.ps1`, `validate_audio_runtime.py`, `requirements-audio.txt`, and `requirements-audio-constraints.txt` are included in the packaged application.
3. Validate the packaged audio runtime from a directory that also contains the PyInstaller runtime, so Python-version DLL or extension-module shadowing regressions are covered.
4. Confirm installer and repair processes remain asynchronous in the Qt UI; no blocking `QProcess.waitForStarted` or `waitForFinished` calls may be added.
5. Confirm the audio worker command retains `-I -X utf8` in that order before the script path and that Unicode protocol messages round-trip through ASCII-safe JSON.
6. Run a real Basic Pitch inference when a representative audio file is available and confirm optional CoreML/TFLite/ONNX warnings, TensorFlow's CPU banner, and replacement characters do not appear; real failures must remain visible.
7. If representative MP3, WAV, and M4A conversion is not run with the isolated Basic Pitch runtime on Windows, report each missing format as not validated.

## Required for Song Transposer changes

1. Run the focused song-processor and Qt dialog tests.
2. Confirm overtone rejection, contextual octave repair, global melody selection, monophonic lead output, MIDI round-trip, and source-overwrite protection.
3. Confirm Clear Melody consolidates sub-window micro-attacks and repairs eligible isolated octave spikes without shifting more than one octave.
4. Confirm Guitar / arpeggio stem preserves the same structural register reset that Clear Melody stabilizes.
5. Process the House of the Rising Sun reference MIDI when it is available and report source/retained notes, detected range, removed outliers, octave repairs, phrase stabilizations, sub-80 ms attacks, lead overlap count, large jumps, and final Optimal Sounding plan size for Clear Melody and Guitar / arpeggio stem.
6. Confirm the packaged build includes `musical_scumme.song_processor` and that the Song Transposer dialog constructs offscreen.
7. Treat musical quality in SCUM as unconfirmed until both processed variants are auditioned in the current game build.

## Required for live MIDI keyboard changes

1. Confirm the native input provider enumerates through Windows MultiMedia and a frozen build contains the `rtmidi` extension.
2. Confirm note-on, legal non-zero-velocity note-off, and zero-velocity note-on produce balanced key state.
3. Confirm repeated notes, octave-fold collisions, duplicate custom key bindings, sustain CC64, reset CC121, and all-notes controls CC120/123 cannot release a shared key early or leave it held.
4. Confirm channel selection, channel-10 filtering, transpose, Fold/Strict range behavior, and the default three-key polyphony limit.
5. Confirm callbacks only enqueue and late callbacks after Stop/reconnect cannot send keys.
6. Confirm live and scheduled output are mutually exclusive through both UI locks and direct method guards.
7. Confirm Stop, F8, focus loss, device disconnect, backend failure, and application close release all keys; include a blocked-dispatch race.
8. Construct the live HUD offscreen with no device and with a fake device, then confirm the maintained 1080×720 layout and settings horizontal-scroll constraint.
9. Treat controller latency, hardware disconnect behavior, and musical quality as unconfirmed until tested with a physical MIDI keyboard in the current SCUM build.

## Required before release

1. Build the Windows application with `Build EXE.bat`, `build_exe.ps1`, or `python build_exe.py`.
2. Confirm the packaged executable launches or can construct its UI offscreen.
3. Confirm the packaged build can locate its bundled audio installer, validator, worker, and requirements files.
4. Treat SCUM playback as unconfirmed unless the current build is tested in SCUM on Windows, including focus-loss cleanup and F8 emergency stop.
