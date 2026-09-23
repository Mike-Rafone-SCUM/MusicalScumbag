# Arrangement suite: put the singer first

Version 3.5.0 also includes three opt-in **Next** arrangements that budget accompaniment across its full duration. See [Duration-aware arrangement](CONTEXTUAL_ARRANGEMENT.md) for Vocal director, Vocal rhythm and Chamber director, including comparison evidence and limitations.

Start with **Custom → Vocal · Foundation / 2**, select every populated non-percussion track, and keep **Ignore percussion** enabled. Set **Maximum chord notes** to 2. This gives the singer a lower foundation while leaving room to hear the tune. For the clearest reference, compare **Vocal · Spotlight / 1** first.

**Lead track** is the most useful control when the MIDI's singer is difficult to identify. Auto prefers a named main/lead vocal over backing vocals and choir. If the melody is called something generic like `Track 4`, select its track explicitly. The selected lead still needs to be checked in the source track list. If no vocal name is available, Auto falls back to musical lead evidence; MIDI notes alone cannot prove which instrument represents the singer.

Keep the same short passage, instrument, mapping, speed and timing for the first comparison. Prepare each option, then audition under supervision. When the singer is clear, increase the arrangement's layers if the song needs more body.

## Vocal arrangements

| Arrangement | Layer ceiling | Good first comparison | What it selects |
| --- | ---: | --- | --- |
| Vocal · Spotlight | 1 | Any vocal song with a buried tune | Exposed vocal; an instrumental lead can fill actual vocal rests. |
| Vocal · Foundation | 2 | Dense pop, rock, busy full MIDI | Vocal and a lower source foundation. |
| Vocal · Acoustic duet | 2 | Acoustic guitar, folk, singer-songwriter | Vocal and nearby moving guitar/piano support. |
| Vocal · Warm ballad | 3 | Slow pop, piano ballads, sustained phrases | Vocal, bass and sustained lower harmony. |
| Vocal · Pop pocket | 3 | Mainstream pop, tight band arrangements | Vocal and compact lower chord support. |
| Vocal · Rock anthem | 3 | Rock choruses, power ballads | Vocal, bass and source fifth/octave support. |
| Vocal · Dance pulse | 3 | Dance-pop, synth-pop, rhythmic arrangements | Vocal, bass and short accented support. |
| Vocal · Choir blend | 3 | Gospel, harmonised vocals, choir MIDI | Lead with nearby named backing vocals where available. |
| Vocal · Cinematic | 4 | Orchestral pop, soundtrack vocals | Vocal, bass and widely spaced sustained support. |
| Vocal · Wall of sound | 5 | Dense chorus experiments | Vocal-led source texture with bass and spread harmony. |

Vocal recipes protect the preferred singer at its source attacks and reserve its layer while a vocal note sustains. Spotlight leaves that sustain clear instead of replacing it with every piano or synth attack. The other vocal recipes can retain accompaniment in the remaining layers. An instrumental handoff is available when the vocal actually rests.

## Instrumental arrangements

| Arrangement | Layer ceiling | Try on |
| --- | ---: | --- |
| Piano · Intimate | 2 | Piano-led tunes with compact lower accompaniment. |
| Acoustic · Fingerstyle | 3 | Picking patterns and moving guitar accompaniment. |
| Rock · Power trio | 3 | Lead, bass and fifth/octave-oriented source material. |
| Electronic · Pulse | 3 | Short accented synth and sequencer parts. |
| Classical · Chamber | 3 | Sustained close harmony and clear voice movement. |
| Jazz · Compact | 3 | Existing thirds, sixths and sevenths in compact harmony. |
| Orchestral · Ensemble | 4 | Widely spaced sustained orchestral parts. |
| Ensemble · Full score | 6 | Maximum source-texture experiments with a traced melody. |

These are source-selection preferences. They choose among notes the MIDI already contains; they cannot create missing bass, reharmonise a song, or turn a sparse piano score into a full orchestra. All recipes preserve exact source attacks during arrangement, and existing physical planning can still fold, delay or remove notes.

## Source tracks versus output layers

Selecting 16 MIDI tracks does **not** mean pressing 16 keys. It gives the arranger 16 sources to choose from. The number in a recipe name is a ceiling for selected voices at an attack, further limited by **Maximum chord notes**. A 5-layer recipe with Maximum chord notes set to 2 still selects at most 2; a solo source cannot supply five distinct voices.

Keep 1–3 layers for the first auditions. The 4–6 layer recipes are deliberate experiments: SCUM's physical key collisions and octave-bank limitations can reduce the final result substantially. Higher note count does not establish a better arrangement. Existing note-density and timing limits remain authoritative, and no recipe changes them silently.

| Populated source tracks selected | Suggested comparison order |
| ---: | --- |
| 1 | Spotlight or Intimate, then the song's style. Multiple voices require actual source chords. |
| 2 | Spotlight → Foundation → Acoustic duet. Check which track is the melody. |
| 4 | Foundation → Warm ballad / Pop pocket → matching instrumental style. |
| 8 | Spotlight → Foundation → one 3-layer vocal style; check the lead selector. |
| 16 or more | Establish Spotlight first; then 2 and 3 layers. Try 4–6 only after the singer remains recognisable. |

## Listening concepts

1. **Whispered singer, huge band:** quiet mid-register vocal, loud high piano, bass, strings and synths. Add source tracks in groups of 2, 4, 8 and 16. Check that every eligible vocal attack remains present.
2. **Long vocal against a sequencer:** one sustained vocal note over six rapid accompaniment attacks. Spotlight should leave the vocal exposed; Dance pulse can use its remaining support layers without claiming a new lead at each attack.
3. **Verse → guitar break → verse:** start with an instrumental introduction, bring in the singer, leave a real vocal rest for the break, then resume the vocal. Listen for the return to the singer.
4. **Main vocal plus backing choir:** place backing vocals earlier in the file and give them higher velocity. Auto should still prefer the explicitly named main/lead singer. Compare Choir blend with Foundation.
5. **Anonymous singer:** rename the melody track to a generic number while another track has a tempting lead name. Use the explicit Lead track selection, then compare the same verse again.
6. **Acoustic duet versus warm ballad:** give the vocal both a moving short accompaniment and a long lower pad. Compare Acoustic duet's movement with Warm ballad's sustain.
7. **Pop versus power chords:** use a melody, low bass and several lower chord tones. Compare Pop pocket, Rock anthem and Jazz · Compact on the same passage to hear how source support selection changes.
8. **Thin verse, huge chorus:** begin with 2 sources, expand to 8, then 16 at the chorus. Compare 2, 3, 4 and 5-layer ceilings while keeping the preferred singer selected.
9. **No lower foundation:** give the singer only higher accompaniment. Foundation should leave its support slot empty when there is no qualifying lower source note.
10. **Sparse score stress test:** use one monophonic track across all recipes. Each should remain recognisable without fabricated harmony.

The original listening fixtures remain in `examples/arrangement-concepts/`: `busy-ensemble.mid`, `lead-handoff.mid`, and `missing-bass.mid`.

For each audition, note the source-track count, recipe, explicit lead or Auto, Maximum chord notes, and mapping. Score **recognisable singer**, **vocal continuity**, **useful accompaniment**, and **clutter** from 1–5. Keep the best sounding result even if it retains fewer notes.

Automated tests cover source provenance, shuffled input, 1/2/4/8/16 selected source layers, percussion/noise rejection, layer ceilings, vocal priority and sustain, explicit lead selection, fallback, and balanced physical key events. These checks establish software behavior. Musical quality and current-build SCUM playback require supervised audition; Basic Pitch conversion has not been revalidated for this suite.
