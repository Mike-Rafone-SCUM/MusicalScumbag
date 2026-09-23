# SCUM Compatibility Audit and Rebuild Report

Audit date: 2026-07-12  
Old source: uploaded `MusicalScumme.zip`  
Replacement baseline: MusicalScumme 2.0.2
Current enhanced release: MusicalScumme 2.4.2

## Verdict on the old app

It may have worked under a particular custom keybinding setup, but it was not a dependable current-SCUM application.

The main reasons:

1. **Unverified key assumptions.** The old app used `YIOPGHJKLBNQE`. The first rebuild then incorrectly promoted an older community guide's `Z5U6IO7H8J9KL` layout to “current” without checking it against the user's live game screen.
2. **Legacy input injection.** It used `win32api.keybd_event`, an older Windows API that is less suitable for modern game input than scan-code `SendInput`.
3. **No foreground guarantee.** Playback could send notes into any focused program.
4. **Unsafe interruption.** Focus changes and failures could leave a key logically held.
5. **Competing implementations.** The archive contained multiple dated scripts, “clean” copies, test rewrites, Qt copies, and a prebuilt executable without one clear maintained source of truth.
6. **Threading problems.** Worker playback code could update Qt widgets directly instead of using thread-safe signals.
7. **Hidden failures.** Several paths swallowed broad exceptions or silently disabled input when optional modules were missing.
8. **Weak MIDI model.** Behaviour varied between scripts and did not provide one clearly tested tempo/sustain/retrigger pipeline.
9. **No compatibility boundary.** The app did not make clear whether it was using keyboard emulation, virtual MIDI, custom game bindings, or a specific SCUM release assumption.

## Relevant SCUM changes found

- The research snapshot used SCUM build `1.3.1.1.128880`, released in July 2026.
- A public February 2026 report said an existing loopMIDI plus MIDI Player instrument workflow stopped producing sound after the `1.2.1.0.106058` update.
- A 2023 community guide lists `Z, 5, U, 6, I, O, 7, H, 8, J, 9, K, L`, but it is not reliable evidence of the user's current bindings.
- The user-confirmed current binding profile is `Y, I, O, P, G, H, J, K, L, B, N, Q, E`, with Left Ctrl/Left Shift controlling octave.
- The B note is `Q`; the earlier Left Cmd/LWIN interpretation was incorrect.
- Current hotfix notes mention additional anti-cheat detections. This project deliberately contains no anti-cheat bypass, concealment, or injection.

This does not prove that all synthetic keyboard input is accepted by the current game. It explains why the rebuild uses a keyboard scan-code path rather than depending on the reportedly broken external virtual-MIDI workflow.

## Replacement design

### Input

- Primary: Windows `SendInput` using hardware scan codes.
- Fallback: `SendInput` using virtual keys.
- Validation: dry-run backend with no keyboard output.
- Every pressed key is tracked and released during pause, stop, focus loss, error, or application close.

### Game focus

Playback can require the SCUM process/window to be foreground. It waits before starting and pauses safely if focus is lost. Detection recognises common SCUM executable names and the plain `SCUM` window title.

### MIDI

The rebuild parses tempo changes and sustain pedal state, supports track selection, preserves note durations, handles overlapping notes, and clips physical-key retriggers that would otherwise swallow later notes.

### SCUM note conversion

- Safe fold maps everything into one 13-note keyboard octave.
- Strict mode drops notes outside C4-C5.
- Smart three-octave mode selects a single octave window per onset group and safely changes Ctrl/Shift state between groups.

Because SCUM's octave modifier applies globally, simultaneous notes from different octave windows cannot be represented exactly. The app does not pretend otherwise.

### Safety

- F8 emergency stop.
- Optional countdown.
- Foreground-only input by default.
- Safe pause on focus loss.
- No game-file modification.
- No background unattended workflow.
- Rotating diagnostic logs and a previous-settings backup are stored in the user app-data folder.
- No injection or anti-cheat bypass.

## Validation status

Completed in the build environment:

- Source compile pass.
- Automated tests passed, including current/legacy profile preservation, the corrected Q binding, and Win32 `INPUT` ABI validation.
- Qt UI construction smoke test passed.
- Example MIDI generation and parser/planner checks passed.

Not completed:

- Live Windows `SendInput` test.
- Live current-SCUM instrument playback.
- Packaged Windows EXE execution.

Those require the user's Windows/SCUM installation. The project includes a one-click source launcher and a Windows PyInstaller build script so that validation can happen locally without relying on the old executable.

## 2.0.1 correction

- Corrected the default profile to the live bindings shown by the user.
- Added `LWIN`, `RWIN`, `Left Cmd`, `Left Command`, and related aliases to the Windows input layer.
- Retained the older 2023 layout and the original MusicalScumme layout as clearly named legacy profiles.
- Made **Copy / edit keys** available from every selected profile so a custom mapping can be seeded without retyping all 15 controls.
- Added `Build EXE.bat` and a Python wrapper, `build_exe.py`, because a PowerShell `.ps1` file cannot be executed by the Python interpreter.

## 2.0.2 runtime correction

- Fixed Windows error 87 from `SendInput`. The earlier ctypes declaration made `INPUT` smaller than the real Win32 structure because its union contained only the keyboard member.
- The replacement now declares `MOUSEINPUT`, `KEYBDINPUT`, and `HARDWAREINPUT`, yielding the required 40-byte structure on 64-bit Windows and 28-byte structure on 32-bit Windows.
- Corrected the B-note key to `Q`.
- Existing installations using the built-in current profile receive the corrected mapping without deleting `%APPDATA%\MusicalScumme\settings.json`.

## 2.1.0 intelligent arrangement and audio transcription

- Added a deterministic musical arranger that identifies likely lead, bass, and harmony material before converting notes to SCUM keys.
- Added melody-only and faithful/legacy modes, percussion filtering, short-note rejection, retrigger cleanup, density control, and velocity-based articulation.
- Reworked smart three-octave mapping to choose octave windows across the whole phrase, reducing unnecessary Ctrl/Shift changes.
- Added optional local audio-to-MIDI transcription for MP3, OGG, WAV, FLAC, and M4A. The model runtime is isolated from the main application so MIDI playback remains lightweight and usable without it.
- Audio transcription is an approximation, not source separation. It is most reliable with an isolated instrument or vocal stem and is cleaned again by the SCUM arranger before playback.


## Optional audio-runtime compatibility

Basic Pitch 0.4.0 currently requires an isolated compatibility pin to setuptools 80.10.2 because its resampy dependency imports `pkg_resources`, which setuptools 82+ removed. This affects only audio transcription and does not affect SCUM input playback.

## 2.4.1 Shift and tempo correction (superseded input interpretation)

- Upper-octave Left Shift is no longer latched across a phrase. It is pulsed per required onset, settling 20 ms before note-on and releasing 18 ms after note-on under Guitar Smooth.
- Left Ctrl remains phrase-scoped. All note keys are still released before an actual modifier-state transition, and cleanup still releases every tracked key on pause, stop, focus loss, error, or close.
- The user's confirmed `Y I O P G H J K L B N Q E` note mapping and Left Ctrl/Left Shift octave bindings are unchanged.
- A real tick-zero MIDI tempo now overrides the parser's synthetic 120 BPM fallback. The reported 270 BPM Rush file is no longer stretched to 120 BPM.
- Melody contour mapping preserves monophonic register detail. Safe one-octave fold remains available when modifier-free playback is preferred over octave accuracy.
- Static Shift timing and package execution are validated. Live Shift+I/menu behaviour, focus-loss cleanup, F8, and subjective pacing remain pending in the current SCUM build.

## 2.4.2 persistent octave-bank correction

- The user confirmed that Left Ctrl and Left Shift step a persistent lower/base/upper octave bank. They must be tapped alone rather than held across or around a musical note.
- Before changing bank, MusicalScumme releases every sounding note and waits the configured release interval. It taps the direction key for 18 ms, releases it, waits for the new bank to settle, and then sends the musical note.
- Generated Shift+I, Shift+note, Ctrl+I, and Ctrl+note combinations are forbidden. Static full-plan simulation confirms zero temporal overlap between octave controls and musical keys.
- The 13-key mapping remains chromatic C through high C, including C-sharp, D-sharp, F-sharp, G-sharp, and A-sharp. SCUM does not label separate flats; their enharmonic sharp is used.
- Remaining in one bank emits no extra octave input. Moving across two layers emits two discrete taps.
- Live current-SCUM confirmation is still pending; static planning cannot prove how the present game build persists or resets its bank when instrument mode is entered or exited.
