"""
Full Song Generator

Generates complete trance songs by:
1. Analyzing a reference track (optional) for structure
2. Generating MIDI patterns for each section
3. Creating variation based on energy curves
4. Outputting MIDI files ready to drag into Ableton

Usage:
    python song_generator.py                    # Generate with default structure
    python song_generator.py --reference track.wav  # Match reference structure
    python song_generator.py --key Am --tempo 140   # Specify key and tempo
"""

import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import sys
import json

from config import Config, DEFAULT_CONFIG
from midi_generator import MIDIGenerator, GeneratorConfig, note_to_midi

# Add music-analyzer to path for structure detector (optional)
_this_dir = Path(__file__).parent
sys.path.insert(0, str(_this_dir.parent / "music-analyzer" / "src"))

try:
    from structure_detector import StructureDetector, SectionType
    HAS_STRUCTURE_DETECTOR = True
except ImportError:
    HAS_STRUCTURE_DETECTOR = False
    print("Note: structure_detector not available, using default structure")


# =============================================================================
# SONG STRUCTURE DEFINITIONS
# =============================================================================

@dataclass
class SongSection:
    """Represents a section of the song."""
    name: str
    section_type: str  # intro, buildup, breakdown, drop, outro
    start_bar: int
    bars: int
    energy: float  # 0-1, affects pattern intensity

    @property
    def end_bar(self) -> int:
        return self.start_bar + self.bars


@dataclass
class SongStructure:
    """Complete song structure."""
    sections: List[SongSection]
    total_bars: int
    tempo: int
    key: str
    scale: str

    def to_dict(self) -> Dict:
        return {
            'sections': [
                {
                    'name': s.name,
                    'type': s.section_type,
                    'start_bar': s.start_bar,
                    'bars': s.bars,
                    'energy': s.energy
                }
                for s in self.sections
            ],
            'total_bars': self.total_bars,
            'tempo': self.tempo,
            'key': self.key,
            'scale': self.scale
        }


# Default trance structure (matches the template we created)
DEFAULT_TRANCE_STRUCTURE = SongStructure(
    sections=[
        SongSection("Intro", "intro", 1, 16, 0.3),
        SongSection("Buildup A", "buildup", 17, 16, 0.5),
        SongSection("Breakdown 1", "breakdown", 33, 32, 0.4),
        SongSection("Drop 1", "drop", 65, 32, 1.0),
        SongSection("Break", "break", 97, 16, 0.6),
        SongSection("Breakdown 2", "breakdown", 113, 32, 0.5),
        SongSection("Drop 2", "drop", 145, 32, 1.0),
        SongSection("Outro", "outro", 177, 32, 0.3),
    ],
    total_bars=208,
    tempo=138,
    key='A',
    scale='minor'
)


# =============================================================================
# SECTION PATTERN RULES
# =============================================================================

# Define what patterns play in each section type
SECTION_PATTERNS = {
    'intro': {
        'kick': {'active': True, 'pattern': 'four_on_floor', 'energy_mult': 0.7},
        'bass': {'active': False},
        'chords': {'active': False},
        'arp': {'active': False},
        'hats': {'active': True, 'pattern': 'offbeat', 'energy_mult': 0.5},
        'clap': {'active': False},
    },
    'buildup': {
        'kick': {'active': True, 'pattern': 'four_on_floor', 'energy_mult': 0.9},
        'bass': {'active': True, 'pattern': 'sustained', 'energy_mult': 0.7},
        'chords': {'active': False},
        'arp': {'active': True, 'pattern': 'trance', 'energy_mult': 0.6},
        'hats': {'active': True, 'pattern': 'offbeat', 'energy_mult': 0.8},
        'clap': {'active': True, 'energy_mult': 0.7},
    },
    'breakdown': {
        'kick': {'active': False},  # No kick in breakdown!
        'bass': {'active': False},
        'chords': {'active': True, 'pattern': 'sustained', 'energy_mult': 0.8},
        'arp': {'active': True, 'pattern': 'trance', 'energy_mult': 0.5},
        'hats': {'active': False},
        'clap': {'active': False},
    },
    'drop': {
        'kick': {'active': True, 'pattern': 'four_on_floor', 'energy_mult': 1.0},
        'bass': {'active': True, 'pattern': 'sustained', 'energy_mult': 1.0},
        'chords': {'active': True, 'pattern': 'stabs', 'energy_mult': 0.9},
        'arp': {'active': True, 'pattern': 'trance', 'energy_mult': 1.0},
        'hats': {'active': True, 'pattern': 'offbeat', 'energy_mult': 1.0},
        'clap': {'active': True, 'energy_mult': 1.0},
    },
    'break': {
        'kick': {'active': True, 'pattern': 'four_on_floor', 'energy_mult': 0.8},
        'bass': {'active': True, 'pattern': 'sustained', 'energy_mult': 0.6},
        'chords': {'active': False},
        'arp': {'active': False},
        'hats': {'active': True, 'pattern': 'offbeat', 'energy_mult': 0.6},
        'clap': {'active': True, 'energy_mult': 0.6},
    },
    'outro': {
        'kick': {'active': True, 'pattern': 'four_on_floor', 'energy_mult': 0.6},
        'bass': {'active': False},
        'chords': {'active': False},
        'arp': {'active': False},
        'hats': {'active': True, 'pattern': 'offbeat', 'energy_mult': 0.4},
        'clap': {'active': False},
    },
}


# =============================================================================
# SONG GENERATOR
# =============================================================================

class SongGenerator:
    """Generates complete songs with MIDI patterns."""

    def __init__(self, structure: SongStructure = None):
        self.structure = structure or DEFAULT_TRANCE_STRUCTURE
        self.config = GeneratorConfig(
            key=self.structure.key,
            scale=self.structure.scale,
            tempo=self.structure.tempo
        )
        self.generator = MIDIGenerator(self.config)

    def generate_track(self, track_name: str) -> List:
        """Generate a complete track following the song structure.

        Args:
            track_name: 'kick', 'bass', 'chords', 'arp', 'hats', 'clap'

        Returns:
            List of MIDI events for the entire song
        """
        all_events = []

        for section in self.structure.sections:
            pattern_config = SECTION_PATTERNS.get(section.section_type, {}).get(track_name, {})

            if not pattern_config.get('active', False):
                continue  # Track not active in this section

            pattern_type = pattern_config.get('pattern', None)
            energy_mult = pattern_config.get('energy_mult', 1.0)
            energy = section.energy * energy_mult

            # Calculate bar offset
            bar_offset = (section.start_bar - 1) * self.generator.ticks_per_bar

            # Generate pattern for this section
            if track_name == 'kick':
                events = self.generator.generate_kick(
                    bars=section.bars,
                    energy=energy,
                    pattern_type=pattern_type or 'four_on_floor'
                )
            elif track_name == 'bass':
                events = self.generator.generate_bass(
                    bars=section.bars,
                    energy=energy,
                    pattern_type=pattern_type or 'rolling'
                )
            elif track_name == 'chords':
                events = self.generator.generate_chords(
                    bars=section.bars,
                    energy=energy,
                    pattern_type=pattern_type or 'sustained'
                )
            elif track_name == 'arp':
                events = self.generator.generate_arp(
                    bars=section.bars,
                    energy=energy,
                    pattern_type=pattern_type or 'trance'
                )
            elif track_name == 'hats':
                events = self.generator.generate_hats(
                    bars=section.bars,
                    energy=energy,
                    pattern_type=pattern_type or 'offbeat'
                )
            elif track_name == 'clap':
                events = self.generator.generate_clap(
                    bars=section.bars,
                    energy=energy
                )
            else:
                continue

            # Offset events to correct position
            for event in events:
                time, msg_type, *params = event
                all_events.append((time + bar_offset, msg_type, *params))

        return all_events

    def generate_full_song(self, output_dir: str) -> Dict[str, str]:
        """Generate all tracks for a complete song.

        Args:
            output_dir: Directory to save MIDI files

        Returns:
            Dict mapping track names to file paths
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        tracks = ['kick', 'bass', 'chords', 'arp', 'hats', 'clap']
        output_files = {}

        for track_name in tracks:
            events = self.generate_track(track_name)

            if events:  # Only save if there are events
                filename = output_path / f"{track_name}_full.mid"
                self.generator.create_midi_file([(track_name, events)], str(filename))
                output_files[track_name] = str(filename)

        # Also save structure info
        structure_file = output_path / "song_structure.json"
        with open(structure_file, 'w') as f:
            json.dump(self.structure.to_dict(), f, indent=2)
        output_files['structure'] = str(structure_file)

        return output_files

    def generate_combined_midi(self, output_file: str) -> str:
        """Generate a single MIDI file with all tracks.

        Args:
            output_file: Output file path

        Returns:
            Path to generated file
        """
        tracks_data = []
        track_names = ['kick', 'bass', 'chords', 'arp', 'hats', 'clap']

        for track_name in track_names:
            events = self.generate_track(track_name)
            if events:
                tracks_data.append((track_name, events))

        self.generator.create_midi_file(tracks_data, output_file)
        return output_file


# =============================================================================
# REFERENCE ANALYZER
# =============================================================================

def analyze_reference(audio_path: str) -> Optional[SongStructure]:
    """Analyze a reference track to extract structure.

    Args:
        audio_path: Path to audio file

    Returns:
        SongStructure based on analysis, or None if analysis fails
    """
    if not HAS_STRUCTURE_DETECTOR:
        print("Structure detector not available, using default structure")
        return None

    try:
        detector = StructureDetector()
        result = detector.detect(audio_path)

        if not result.success:
            print(f"Structure detection failed: {result.error}")
            return None

        # Convert detected sections to SongSections
        sections = []
        for i, section in enumerate(result.sections):
            # Map section type
            section_type_map = {
                SectionType.INTRO: 'intro',
                SectionType.BUILDUP: 'buildup',
                SectionType.DROP: 'drop',
                SectionType.BREAKDOWN: 'breakdown',
                SectionType.OUTRO: 'outro',
            }
            section_type = section_type_map.get(section.section_type, 'drop')

            # Calculate energy based on section type
            energy_map = {
                'intro': 0.3,
                'buildup': 0.6,
                'breakdown': 0.4,
                'drop': 1.0,
                'outro': 0.3,
            }
            energy = energy_map.get(section_type, 0.7)

            sections.append(SongSection(
                name=section.name or f"Section {i+1}",
                section_type=section_type,
                start_bar=section.start_bar,
                bars=section.duration_bars,
                energy=energy
            ))

        total_bars = sum(s.bars for s in sections)

        return SongStructure(
            sections=sections,
            total_bars=total_bars,
            tempo=int(result.tempo_bpm),
            key='A',  # Would need key detection
            scale='minor'
        )

    except Exception as e:
        print(f"Error analyzing reference: {e}")
        return None


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Generate a full trance song')
    parser.add_argument('--reference', '-r', type=str, help='Reference audio file for structure')
    parser.add_argument('--key', '-k', type=str, default='A', help='Musical key (default: A)')
    parser.add_argument('--scale', '-s', type=str, default='minor', help='Scale (default: minor)')
    parser.add_argument('--tempo', '-t', type=int, default=138, help='Tempo in BPM (default: 138)')
    parser.add_argument('--output', '-o', type=str, default=None, help='Output directory')
    parser.add_argument('--combined', '-c', action='store_true', help='Output single combined MIDI file')

    args = parser.parse_args()

    print("=" * 60)
    print("TRANCE SONG GENERATOR")
    print("=" * 60)
    print()

    # Determine structure
    if args.reference and Path(args.reference).exists():
        print(f"Analyzing reference: {args.reference}")
        structure = analyze_reference(args.reference)
        if structure is None:
            print("Using default structure")
            structure = DEFAULT_TRANCE_STRUCTURE
    else:
        structure = DEFAULT_TRANCE_STRUCTURE

    # Override key/scale/tempo if specified
    structure.key = args.key
    structure.scale = args.scale
    structure.tempo = args.tempo

    print(f"\nSong Configuration:")
    print(f"  Key: {structure.key} {structure.scale}")
    print(f"  Tempo: {structure.tempo} BPM")
    print(f"  Total bars: {structure.total_bars}")
    print(f"  Duration: ~{structure.total_bars * 4 * 60 / structure.tempo:.1f} seconds")
    print()

    print("Song Structure:")
    for section in structure.sections:
        print(f"  Bar {section.start_bar:3} - {section.end_bar:3}: {section.name:15} "
              f"({section.section_type}, energy: {section.energy:.1f})")
    print()

    # Generate
    generator = SongGenerator(structure)

    output_dir = args.output or str(DEFAULT_CONFIG.OUTPUT_BASE / "generated_song")

    if args.combined:
        output_file = str(Path(output_dir) / "full_song.mid")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        result = generator.generate_combined_midi(output_file)
        print(f"Generated combined MIDI: {result}")
    else:
        results = generator.generate_full_song(output_dir)
        print("Generated tracks:")
        for track, path in results.items():
            print(f"  {track}: {path}")

    print()
    print("Drag these MIDI files into Ableton to use them!")
    print(f"Output directory: {output_dir}")


if __name__ == '__main__':
    main()
