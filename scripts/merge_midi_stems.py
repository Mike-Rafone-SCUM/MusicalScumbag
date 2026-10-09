"""Merge separated stem MIDI files (e.g. vocals and instrumental) into a multi-track MIDI.

This utility loads note events from independent transcribed stem MIDIs,
aligns them along their absolute millisecond timeline, and writes a Type-1
multi-track MIDI. When opened in MusicalScumbag, it can be arranged with the
'Cover song · Vocal + band / 3' recipe for faithful SCUM keyboard playback.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from musical_scumme.stem_merger import merge_stems  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--vocals", type=Path, help="Path to transcribed vocals MIDI file")
    parser.add_argument("-i", "--instrumental", type=Path, help="Path to transcribed instrumental MIDI file")
    parser.add_argument("-b", "--bass", type=Path, help="Optional path to transcribed bass MIDI file")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Path to write the merged Type-1 MIDI")
    parser.add_argument("--bpm", type=float, default=120.0, help="Tempo for the merged MIDI (default: 120.0)")

    args = parser.parse_args()
    out = merge_stems(
        vocals_path=args.vocals,
        instrumental_path=args.instrumental,
        bass_path=args.bass,
        output_path=args.output,
        bpm=args.bpm,
    )
    print(f"Merged MIDI successfully created: {out}")


if __name__ == "__main__":
    main()
