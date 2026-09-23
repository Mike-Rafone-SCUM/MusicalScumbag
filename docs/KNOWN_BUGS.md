# MusicalScumme Known Bugs

Record bugs that are found but not fully fixed, plus concrete regression risks that require future work. Do not list general validation limitations as fixed defects.

## Automatic arpeggio transcription remains approximate

- Basic Pitch can still miss or misidentify exposed inner guitar notes even with the 2.4.1 thresholds and reattack cleanup. The matching clean score is materially more coherent than the automatic House of the Rising Sun transcription.
- MusicalScumme does not currently infer missing arpeggio notes from a learned or repeated score template. Prefer the provided `MusicalScumme_2.4.2_ScoreAccurate.mid` when a clean score exists, and audition automatic conversion before SCUM playback.
- Regression risk: lowering thresholds further recovers some weak attacks but rapidly introduces upper harmonics and low spectral artifacts. Do not lower defaults based on note count alone.
- Version 2.5.0's guitar-focused E2-E6 pass improves the supplied stem's strict 90 ms time/pitch reference matches from 61 to 74 and narrows the raw detected range, but it still produces only an approximate melody and leaves 92 structural leaps in the arpeggio-preserving result. Do not present frequency focus as score-level pitch recognition.
- SCUM Pitch Match removes interval distortion by following the real register more faithfully, which increases standalone octave-bank taps on the House references. If those transitions are too audible in the current game build, use Melody contour; do not silently reintroduce per-note folding into Pitch Match.
- UVR materially improves the supplied full-mix opening, but Viperx remains a two-stem separator: its Instrumental output can still contain drums, bass, organ, and piano. Prefer an already clean instrument stem when one exists, and do not describe UVR preprocessing as score reconstruction.
- The Viperx probe used roughly 7.57 GB of the RTX 2070 SUPER's 8.19 GB while SCUM was open. Other GPU-heavy programs can still cause an out-of-memory failure. Keep batch size one/autocast and close unrelated GPU workloads if separation fails; do not silently fall back to a lower-quality model after an OOM.
- Demucs `htdemucs_6s` is the only current catalogue model with a direct Guitar output, but on the House opening its cleaned MIDI matched the user's reference less accurately than Viperx Instrumental. A labelled instrument stem is not proof of better MusicalScumme input.

No other unresolved implementation bugs are recorded at this time.
