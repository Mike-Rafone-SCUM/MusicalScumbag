"""Stable arrangement identities and user-facing selection guidance."""

from dataclasses import dataclass

ARRANGEMENT_OPTIONS = {
    "intelligent": ("Game-optimised", "Balances a traced lead, bass and source harmony. Supports performed-chord alignment and protected solo handoffs."),
    "vocal": ("Vocal lead focus", "Prioritises named vocal tracks, with instrumental handoffs and source accompaniment. Supports chord recognition; unnamed vocals cannot be identified by name."),
    "melody": ("Lead melody only", "One note per onset from one inferred lead track. Best for a consistent melody part; other tracks are excluded."),
    "adaptive_lead": ("Adaptive lead only", "One note per onset across selected tracks, following phrase continuity. Useful for instrumental handoffs; no accompaniment or performed-chord alignment."),
    "melody_bass": ("Melody + bass", "For all non-percussion tracks selected: a traced lead plus at most one lower source note, at least three semitones below it. No inner harmony or performed-chord alignment; a one-note limit keeps only the lead."),
    "faithful": ("Faithful / legacy selection", "Retains source selection and attack timing after percussion and short-note filtering. Final pitch mapping, polyphony and physical safety can still remove or delay notes."),
}

CHORD_RECOGNITION_MODES = frozenset({"intelligent", "vocal"})



@dataclass(frozen=True)
class ArrangementRecipe:
    label: str
    description: str
    lead: str
    layers: int
    texture: str
    processing: str = "onset"


ARRANGEMENT_RECIPES = {
    "cover_riff": ArrangementRecipe("Cover song · Riff first / 3", "Protects vocal melody and gives guitar riffs priority over bass and pads. Follows instrumental lead parts in vocal rests, including overlapping fast solo attacks.", "vocal", 3, "cover_riff", "contextual"),
    "cover_song": ArrangementRecipe("Cover song · Vocal + band / 3", "Combines a vocal or chosen lead with separate bass and rhythm pools; reserves rhythmic attacks before sustained harmony. Instrumental melody fills lead rests. Select all useful musical tracks.", "vocal", 3, "cover", "contextual"),
    "vocal_director": ArrangementRecipe("Performance · Vocal director / 3", "Vocal-led arrangement with full-duration voice budgeting, future melody collision checks and phrase-aware support continuity.", "vocal", 3, "warm", "contextual"),
    "vocal_director_pulse": ArrangementRecipe("Performance · Vocal rhythm / 3", "Protects vocal sustains with short, accented source accompaniment and full-duration voice budgeting.", "vocal", 3, "pulse", "contextual"),
    "chamber_director": ArrangementRecipe("Performance · Chamber director / 3", "Inferred or chosen lead with duration-aware bass and sustained harmony; protects instrumental fills between lead phrases.", "auto", 3, "warm", "contextual"),
    "vocal_spotlight": ArrangementRecipe("Vocal · Spotlight / 1", "Exposed vocal melody; instrumental lead fills actual vocal rests.", "vocal", 1, "bass"),
    "vocal_foundation": ArrangementRecipe("Vocal · Foundation / 2", "Vocal plus a lower bass foundation. A clear starting point with every track selected.", "vocal", 2, "bass"),
    "vocal_acoustic": ArrangementRecipe("Vocal · Acoustic duet / 2", "Vocal with a nearby lower guitar or piano voice; prefers moving, short support notes.", "vocal", 2, "arpeggio"),
    "vocal_ballad": ArrangementRecipe("Vocal · Warm ballad / 3", "Vocal, bass and sustained lower harmony. Suits slow songs and long phrases.", "vocal", 3, "warm"),
    "vocal_pop": ArrangementRecipe("Vocal · Pop pocket / 3", "Vocal and compact lower chord support with smooth voice leading.", "vocal", 3, "tight"),
    "vocal_rock": ArrangementRecipe("Vocal · Rock anthem / 3", "Vocal, bass and fifth/octave-oriented support from existing notes.", "vocal", 3, "power"),
    "vocal_pulse": ArrangementRecipe("Vocal · Dance pulse / 3", "Vocal, bass and short accented support; sustained vocal notes retain ownership between attacks.", "vocal", 3, "pulse"),
    "vocal_choir": ArrangementRecipe("Vocal · Choir blend / 3", "Lead vocal plus nearby named backing vocals where available, using distinct pitches.", "vocal", 3, "choir"),
    "vocal_cinematic": ArrangementRecipe("Vocal · Cinematic / 4", "Vocal, bass and wide sustained support. Four layers are experimental in SCUM.", "vocal", 4, "wide"),
    "vocal_wall": ArrangementRecipe("Vocal · Wall of sound / 5", "Vocal-led five-voice source texture with bass and spread harmony. Experimental; review collisions.", "vocal", 5, "wide"),
    "piano_intimate": ArrangementRecipe("Piano · Intimate / 2", "Traced melody with compact lower support for piano-led songs.", "auto", 2, "tight"),
    "acoustic_fingerstyle": ArrangementRecipe("Acoustic · Fingerstyle / 3", "Traced lead and moving lower accompaniment; exact source attacks.", "auto", 3, "arpeggio"),
    "rock_power": ArrangementRecipe("Rock · Power trio / 3", "Traced lead and lower fifth/octave-oriented accompaniment.", "auto", 3, "power"),
    "electronic_pulse": ArrangementRecipe("Electronic · Pulse / 3", "Traced melody, bass and short accented rhythmic support.", "auto", 3, "pulse"),
    "chamber_trio": ArrangementRecipe("Classical · Chamber / 3", "Lead, bass and sustained close harmony with support continuity.", "auto", 3, "warm"),
    "jazz_compact": ArrangementRecipe("Jazz · Compact / 3", "Lead with compact source harmony, favouring thirds, sixths and sevenths.", "auto", 3, "jazz"),
    "cinematic_ensemble": ArrangementRecipe("Orchestral · Ensemble / 4", "Traced lead, bass and widely spaced sustained support. Experimental four-layer texture.", "auto", 4, "wide"),
    "ensemble_max": ArrangementRecipe("Ensemble · Full score / 6", "Six distinct source pitches per attack, led by the traced melody. Experimental; physical mapping may simplify heavily.", "auto", 6, "wide"),
}
for _mode, _recipe in ARRANGEMENT_RECIPES.items():
    ARRANGEMENT_OPTIONS[_mode] = (
        _recipe.label,
        _recipe.description + " Layer count is a ceiling, limited by Maximum chord notes; source notes only. "
        + ("Auto detects named vocals; choose Lead track for unnamed parts. " if _recipe.lead == "vocal" else "")
        + "Exact attacks; existing density, mapping and safety limits still apply.",
    )
    if _recipe.processing == "contextual":
        ARRANGEMENT_OPTIONS[_mode] = (
            _recipe.label,
            ARRANGEMENT_OPTIONS[_mode][1] + " Support is budgeted over its full duration. Source lead overlaps are preserved and reported.",
        )
