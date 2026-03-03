#!/usr/bin/env python3
"""
Embed custom MIDI files into an existing Ableton Live project.
"""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
import json
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from clip_embedder import ClipEmbedder
from xml_utils import analyze_ids, update_next_pointee_id
from song_spec import SongSpec


def embed_midi_into_als(
    als_path: Path,
    midi_dir: Path,
    spec_path: Path = None,
    split_sections: bool = True,
    ticks_per_beat: int = 480
):
    """
    Embed MIDI files into an existing .als file.

    Args:
        als_path: Path to .als file
        midi_dir: Directory containing .mid files
        spec_path: Path to song_spec.json (for section info)
        split_sections: Whether to split clips by section
        ticks_per_beat: MIDI ticks per beat
    """
    print(f"Loading: {als_path}")

    # Load .als file (gzip compressed XML)
    with gzip.open(als_path, 'rb') as f:
        xml_content = f.read()

    root = ET.fromstring(xml_content)

    # Load song spec for section info
    spec = None
    if spec_path and spec_path.exists():
        with open(spec_path) as f:
            spec_data = json.load(f)
            spec = SongSpec.from_dict(spec_data)
        print(f"Loaded song spec: {spec.name}")

    # Get current max ID
    analysis = analyze_ids(root)
    start_id = max(analysis.max_numeric_id, analysis.next_pointee_id) + 1

    # Create embedder
    embedder = ClipEmbedder(ticks_per_beat=ticks_per_beat)

    # Build track name -> MIDI file mapping
    track_mapping = {}
    for midi_file in midi_dir.glob("*.mid"):
        track_name = midi_file.stem.lower()
        track_mapping[track_name] = midi_file.name
        print(f"  Found: {track_name} -> {midi_file.name}")

    # Build sections list if splitting is enabled
    sections = None
    total_bars = 224  # Default

    if spec:
        total_bars = spec.total_bars
        if split_sections and spec.structure:
            sections = [
                (section.name, section.start_bar, section.end_bar)
                for section in spec.structure
            ]
            print(f"  Splitting into {len(sections)} sections")

    # Embed clips
    print(f"\nEmbedding {len(track_mapping)} MIDI files...")
    next_id = embedder.embed_midi_files(
        root,
        midi_dir,
        track_mapping,
        total_bars,
        start_id,
        sections=sections
    )

    # Update NextPointeeId
    update_next_pointee_id(root, next_id + 1)

    # Save updated .als file
    output_path = als_path.parent / f"{als_path.stem}_embedded.als"

    # Add XML declaration like the original generator does
    xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
    with gzip.open(output_path, 'wb') as f:
        f.write(xml_string.encode('utf-8'))

    print(f"\nSaved: {output_path}")
    return output_path


if __name__ == "__main__":
    # BabyBoomers_Final project
    project_dir = Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\BabyBoomers_Final")

    als_path = project_dir / "BabyBoomers_Final.als"
    midi_dir = project_dir / "midi"
    spec_path = project_dir / "song_spec.json"

    embed_midi_into_als(
        als_path=als_path,
        midi_dir=midi_dir,
        spec_path=spec_path,
        split_sections=True
    )
