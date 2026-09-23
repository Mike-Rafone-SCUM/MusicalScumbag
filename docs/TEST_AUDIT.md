# Test audit — 2026-09-23 / 3.9.1

The starting tree had 29 reproducible failures (647 passing), plus a scheduler
telemetry check that failed intermittently. These expectations and implementation
paths predate the new single-instance startup guard.

## Implementation regressions corrected

- Thirteen contextual-arrangement failures exposed release rewriting before the
  duration budget was checked. That contradicted the processor's documented
  source-note/full-duration contract and admitted support by prematurely cutting
  lead and support notes. Restore selection of unchanged source notes, reserve
  complete lead intervals, and leave physical sustain shaping to the planner.
- Changing the suite lead updated the setting but did not invalidate the cached
  plan or select Custom. Restore both actions; retain the existing UI regression.
- Duplicate application startups now exit before constructing a window/hotkey
  listener. Four regressions cover exclusion, unlock/restart, crash recovery and
  the duplicate UI path. Close older builds once before using this protection.

## Outdated expectations corrected

- Two packaging probes expected a removed optional OneFile branch. Probe the
  current single-file script's actual try/finally PATH guard instead.
- Two settings tests expected migration version 2 and blanket selection deletion.
  Version 3 preserves multitrack choices and handles ambiguous legacy Type-0 [0]
  selections separately. Do not revert the migration to satisfy older tests.
- Two live MIDI tests expected controller CC120/123 from an unrelated channel to
  silence every channel. The maintained channel-local release/reference-counting
  behavior is intentional; F8/Stop remain global cleanup mechanisms.
- Four numeric tests sent input to hidden controls in Simple view. Select Advanced
  and the correct Song/Timing tab, keeping the value and focus assertions.
- Optimal now selects named-vocal or chamber contextual recipes. Its vocal policy
  protects the singer over a simultaneous louder instrumental solo; it does not
  use the older intelligent mode's solo-adaptive policy. Preserve a separate
  Custom/intelligent test for performed-chord recognition and alignment.
- Faithful guitar accompaniment without an identified lead intentionally rolls
  low-to-high. A traced lead/solo still has priority in the physical roll.
- A 10 ms song may deliver only the final telemetry update if an initial batch
  is late. Assert exact final position and monotonic callbacks rather than a
  minimum of two callbacks inside the 33 ms UI throttle interval.

## Complete-plan baseline

The 45 hashes dated from the pre-3.9 planner and omitted some diagnostics. They
cannot provide a readable field diff; old full payloads were not stored. The
current planner includes physical rhythm shortening, lead articulation,
instrument-aware chord roll ordering and additional diagnostics. Do not describe
this refresh as proof of equivalence to the older release.

After reviewing focused behavior tests, regenerate all 45 full-payload hashes,
including every diagnostic. Each fixture also checks source pitch provenance,
positive bounded sustain, bank/pitch consistency, chronological events, standalone
octave taps and final key release independently of its hash. Use
`python -m scripts.update_plan_snapshots` to inspect differences; `--write` is an
explicit maintenance operation and is never run by pytest.

The earlier harmonic change is a small bank preference, not a guarantee that all
songs will sound lower. Added coverage for a near-balanced chord (which distinguishes
0.22 from the prior 0.05 penalty) and for preserving genuinely high source pitches.

Current-game SCUM audition remains pending. Audio conversion modules/dialogs are
absent from this streamlined checkout; no Basic Pitch validation is claimed.

## Final verification

- 681 tests passed, including offscreen main-window construction; Ruff passed.
- Whole-tree compileall returned success with a warning for the inaccessible
  `.pytest_cache` directory; explicit compilation of application, scripts, tests
  and `run.py` completed without warnings or errors.
- Built 3.9.1 with `build_exe.ps1` and its System32-first PATH guard. Bypassing
  that guard reproduced a QtCore DLL startup failure in an intermediate build;
  that artifact was replaced by the verified build. Always use the guarded script.
- Frozen EXE survived eight seconds offscreen with isolated dry-run settings;
  a second launch exited successfully, the first stayed alive, and logs contained
  no errors. The smoke check terminated only its own test process tree.
- `release/MusicalScumbag.exe`: 39,320,807 bytes, Windows version 3.9.1.0.
  SHA-256: `60d269aca3d4b48697192d475284ed61f3f681d2b924b1b125f729923adaaafd`.
