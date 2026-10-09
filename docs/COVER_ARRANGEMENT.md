# MIDI cover arrangement

Choose **Custom**, then **Cover song · Vocal + band / 3** in the advanced arrangement controls. Select all useful non-percussion tracks. Use **Lead track** to identify the vocal melody if the MIDI's track names do not make it clear. Prepare before playing and review the inferred layer list in the advisories.

The cover recipe preserves a vocal or chosen lead, follows instrumental material in its rests, and combines existing bass, rhythm and harmony notes. It reserves full lead durations first, then bass, then rhythm, then harmony. This keeps a sustained pad from consuming the space needed by later offbeat guitar or piano attacks. Each accompaniment role gets at most one sounding note; the total remains at most three, or your lower Maximum chord notes setting. With two voices, bass takes precedence over rhythm.

Track names, pitch register and articulation supply deterministic role hints. Unnamed articulated parts can serve as rhythm; an unnamed low part can serve as bass. These are whole-track hints, not perfect instrument recognition or separation of every voice in a merged piano track. Higher accompaniment within an octave of the lead remains eligible, so low vocals do not automatically remove guitar parts above them. Same-pitch overlaps with the lead are rejected, including future lead attacks.

The recipe selects original notes without changing their pitch, attack or release. Existing source filters, density reduction and physical SCUM planning still apply and can omit notes or alter their played timing. It does not generate missing vocals, chords or drum-to-instrument patterns. A MIDI must contain the tune you want to hear; choosing a vocal-focused recipe cannot recover a vocal absent from the file.

This is a first MIDI cover workflow. Existing presets and arrangement recipes remain available. Automated tests cover structural retention and physical planning, but representative songs still need supervised listening in the current SCUM build before musical quality is confirmed.

## Fast rock and metal

Choose **Cover song · Riff first / 3** when the repeated guitar pattern matters more than the bass foundation. It reserves rhythm before bass, especially useful at a two-note limit. Both cover modes now use declared General MIDI guitar/bass/string programs as well as track names, so low guitars do not disappear into the bass pool. Named instrumental leads take priority in vocal rests, and successive overlapping attacks from the same instrumental lead remain eligible rather than being suppressed until the first note releases.

For the supplied **Fury of the Storm** MIDI, explicitly choose **ZP Theart** as Lead track for the singer: the only recognisable vocal label is **Backing Vocals**. The app now discloses that ambiguity instead of silently presenting the backing selection as a confirmed main vocal. For **Rocky – Gonna Fly Now**, include **Metais** (brass) and choose it as Lead track to emphasise the theme instead of the guitar solo. These choices depend on the source arrangement; artist names are not hard-coded.

On 2026-09-26, the user's saved maximum hold of 0 ms produced zero-duration plans. With permission, it was restored to 850 ms and Rocky's brass track was reselected; the original settings were backed up. The existing transpose, mapping and remaining timing settings were preserved. Source MIDI files were not rewritten.

Static comparisons on the selected source tracks retained 1,964 Guitar 1 notes in the multitrack **Through the Fire and Flames**, versus 276 previously; **Dying in Your Arms** retained 477 notes from Matt's guitar part, versus 55. These counts precede physical planning and do not establish audible quality. Mapping still removes notes and changes registers. The piano-only DragonForce cover does not gain separate guitar/vocal layers from these changes.

The supplied Trivium **Anthem** and **Crusade** files contain invalid zero-tempo events and remain rejected by the parser. This update does not guess replacement tempos or alter those files.
