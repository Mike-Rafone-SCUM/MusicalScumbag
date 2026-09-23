# Arrangement audition concepts

Select every populated non-percussion track, keep the same instrument, mapping and timing, and prepare each arrangement before supervised playback. Compare score retention and listen to the same short passage. More retained notes do not necessarily sound better.

1. Busy full ensemble: melody, bass, sustained pads and loud high accompaniment. Compare Game-optimised against Melody + bass. Listen for a recognisable lead and an uncluttered foundation.
2. Verse-to-solo relay: vocals followed by guitar and then vocals again. Compare Vocal lead focus and Adaptive lead only. Check that the instrumental bridge remains audible and vocals return naturally.
3. Doubled melody: the same lead on several tracks and octaves. Compare sparse modes; check for repeated physical-key collisions in the prepared plan and unnecessary octave jumps by ear.
4. Missing bass: lead with only upper accompaniment. Melody + bass must leave the support slot empty when no lower source note qualifies.
5. Dense chromatic run: all tracks selected, including percussion on channel 10. Keep percussion ignored and existing density limits. Listen for preserved phrase endpoints rather than maximum note count.
6. Sustained harmony under fast lead: compare all three instruments. Check audible release, no stuck notes, and supervised F8/focus-loss cleanup.

Automated coverage accompanies the new modes for settings persistence, deterministic source provenance, one/two-voice ceilings, absent-bass behavior, track handoffs, guidance and chord-control availability. Existing planner snapshots protect established modes. These concepts still require supervised audition in the current SCUM build; automated checks cannot establish musical quality.

Three original synthetic MIDI examples are supplied in `examples/arrangement-concepts/`: busy-ensemble.mid, lead-handoff.mid and missing-bass.mid. Each includes a named channel-10 drum part to exercise percussion exclusion. They are eight-second listening fixtures at 120 BPM.
