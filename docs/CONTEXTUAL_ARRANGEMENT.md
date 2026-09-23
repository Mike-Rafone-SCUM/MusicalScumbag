# Duration-aware arrangement — 3.5.0

Choose **Custom**, select the musical source tracks, then choose one of the new arrangements:

| Arrangement | Selection preference |
| --- | --- |
| Next · Vocal director / 3 | Main vocal, lower foundation and sustained source harmony. |
| Next · Vocal rhythm / 3 | Main vocal with shorter, accented lower accompaniment. |
| Next · Chamber director / 3 | Inferred or explicitly chosen instrumental lead with sustained lower support. |

Set **Lead track** explicitly when the melody has an anonymous or misleading name. Keep **Maximum chord notes** at 1–3. These choices are opt-in; existing recipes and named presets retain their behavior. Smart auto-select understands their lead and three-layer source roles.

## What changes

The older suite admits accompaniment at each onset. Repeated attacks on different keys can leave many earlier source notes sounding. The new processing stage reserves all selected lead durations, then admits support only when its entire duration fits the available voice capacity. A support note can be rejected because of a lead attack that has not happened yet.

Support cannot overlap an existing support note of the same pitch or a future lead note of that pitch. Exact release/start boundaries remain playable. Held lead notes retain ownership between attacks, including inferred instrumental leads and instrumental fills in vocal rests. A returning primary lead still takes precedence.

Support selection favours a lower foundation, then closer harmony, with continuity from earlier support. Voice history resets after at least 750 ms of actual selected silence. These preferences use only existing source notes. There is no generated harmony, attack quantization, duration rewriting or source-file modification.

Source lead overlaps are intentionally retained, even if they alone exceed the selected ceiling. A warning explains this exception. The density, retrigger, mapping and instrument-sustain passes still run afterward and can simplify or delay the result. The reported contextual peak is measured before those passes, not a claim about physical SCUM polyphony.

## Technical changes and evidence

- A separate pure-Python `arrangement_processing.py` owns the contextual processing, without Qt, input or inference dependencies.
- A coordinate-compressed interval index handles duration capacity with logarithmic range queries and updates. Merged per-pitch lead spans allow binary-search collision checks without repeated full-song scans.
- Full tie ordering makes the new modes reproducible when input tracks contain identical onset/pitch/duration combinations.
- Prepared diagnostics expose capacity rejections, pitch-collision rejections, support phrase resets and peak selected voices before density filtering. Prepared UI summaries use readable arrangement names.
- Randomized interval-index tests compare every result with a simple reference calculation. Musical tests cover source provenance, future reservations, exact release boundaries, held fills, duplicate support, deterministic selection and all five physical mappings.

Run `python -m scripts.benchmark_arrangement_processing` from the project directory to repeat the no-input synthetic benchmark. On this development machine, 2,500 long overlapping interval queries/updates took 0.084674 seconds with the index versus 0.534921 seconds for the equivalent simple reference, with identical query results. This measures the interval operation only.

On a synthetic 2,040-note, 60-second ensemble, Warm ballad selected 1,080 notes and peaked at 19 overlapping source voices. Vocal director selected 228 notes and peaked at 3, retaining all 120 original lead attacks. Total arrangement time increased from 0.039704 to 0.058352 seconds because the new policy does more work. These are scoped measurements, not general speed or musical-quality guarantees.

## Supervised comparison

Use the same short passage, source selection, mapping, instrument, speed and timing. Compare Warm ballad against Vocal director; then compare Vocal rhythm on a passage containing both pads and short accompaniment. Listen for sustained pileups, melody clarity, accompaniment gaps and return from an instrumental break. Review the preparation advisories before playback.

Current-build SCUM audition and representative Basic Pitch MP3/WAV/M4A validation have not been repeated for this version.
