"""
Texture MIDI Export

Exports texture generator output to MIDI files compatible with Ableton Live.
Integrates the texture_generator.py with the existing MIDI pipeline.
"""

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from config import Config, DEFAULT_CONFIG
from texture_generator import (
    TextureGenerator, TextureType, Mood,
    get_mood_from_string, SECTION_TEXTURE_PRESETS
)
from song_spec import SongSpec, SectionSpec


class TextureMIDIExporter:
    """Exports texture events to MIDI files."""

    def __init__(self, config: Config = None, ticks_per_beat: int = 480):
        self.config = config or DEFAULT_CONFIG
        self.ticks_per_beat = ticks_per_beat

    def events_to_midi_file(
        self,
        events: List[Tuple],
        filename: str,
        tempo: int = 138,
        track_name: str = "Texture"
    ) -> str:
        """
        Convert texture events to a MIDI file.

        Args:
            events: List of tuples from TextureGenerator
            filename: Output path
            tempo: BPM
            track_name: Name for the MIDI track

        Returns:
            Path to created file
        """
        mid = MidiFile(ticks_per_beat=self.ticks_per_beat)
        track = MidiTrack()
        mid.tracks.append(track)

        # Track name and tempo
        track.append(MetaMessage('track_name', name=track_name, time=0))
        tempo_us = mido.bpm2tempo(tempo)
        track.append(MetaMessage('set_tempo', tempo=tempo_us, time=0))

        # Sort events by time
        sorted_events = sorted(events, key=lambda x: x[0])

        current_time = 0

        for event in sorted_events:
            abs_time = event[0]
            msg_type = event[1]
            delta = abs_time - current_time
            current_time = abs_time

            if msg_type == 'note_on':
                note, velocity = event[2], event[3]
                track.append(Message(
                    'note_on', note=note, velocity=velocity, time=delta
                ))
            elif msg_type == 'note_off':
                note = event[2]
                track.append(Message(
                    'note_off', note=note, velocity=0, time=delta
                ))
            elif msg_type == 'cc':
                cc_num, value = event[2], event[3]
                track.append(Message(
                    'control_change', control=cc_num, value=value, time=delta
                ))
            elif msg_type == 'pitch_bend':
                # Convert from -8192..8191 to 0..16383
                value = event[2]
                pitch_val = value + 8192
                pitch_val = max(0, min(16383, pitch_val))
                track.append(Message(
                    'pitchwheel', pitch=value, time=delta
                ))

        # End of track
        track.append(MetaMessage('end_of_track', time=0))

        # Save
        mid.save(filename)
        return filename

    def export_textures_dict(
        self,
        textures: Dict[str, List[Tuple]],
        output_dir: Path,
        tempo: int = 138,
        prefix: str = ""
    ) -> Dict[str, str]:
        """
        Export multiple texture types to separate MIDI files.

        Args:
            textures: Dict of texture_type -> events
            output_dir: Directory to save files
            tempo: BPM
            prefix: Optional filename prefix

        Returns:
            Dict of texture_type -> filepath
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = {}

        for tex_type, events in textures.items():
            if not events:
                continue

            filename = f"{prefix}{tex_type}.mid" if prefix else f"{tex_type}.mid"
            filepath = output_dir / filename

            self.events_to_midi_file(
                events, str(filepath), tempo, tex_type.replace("_", " ").title()
            )
            result[tex_type] = str(filepath)

        return result


def generate_textures_for_song(
    spec: SongSpec,
    output_dir: Path = None
) -> Dict[str, str]:
    """
    Generate all texture MIDI files for a song specification.

    Args:
        spec: SongSpec with structure and mood
        output_dir: Directory for MIDI files (default: spec output dir)

    Returns:
        Dict of texture_type -> filepath
    """
    if output_dir is None:
        output_dir = DEFAULT_CONFIG.get_midi_dir(spec.name)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create texture generator with song parameters
    mood = get_mood_from_string(spec.mood)
    gen = TextureGenerator(
        tempo=spec.tempo,
        key=spec.key,
        scale=spec.scale,
        mood=mood
    )

    # Build structure dict from song spec
    structure = {}
    energy_curve = {}

    for section in spec.structure:
        structure[section.name] = section.bars
        energy_curve[section.name] = section.energy

    # Generate textures
    textures = gen.generate_full_song_textures(structure, energy_curve)

    # Export to MIDI
    exporter = TextureMIDIExporter()
    return exporter.export_textures_dict(
        textures, output_dir, spec.tempo
    )


def generate_texture_track(
    texture_type: str,
    bars: int,
    mood: str = "euphoric",
    key: str = "A",
    tempo: int = 138,
    output_path: str = None
) -> str:
    """
    Generate a single texture track.

    Args:
        texture_type: Type of texture (riser, impact, atmosphere, etc.)
        bars: Length in bars
        mood: Mood string (dark, euphoric, etc.)
        key: Musical key
        tempo: BPM
        output_path: Optional output path

    Returns:
        Path to generated MIDI file
    """
    from texture_generator import generate_texture_for_mood

    events = generate_texture_for_mood(
        texture_type, mood, bars, key, tempo
    )

    if output_path is None:
        output_path = f"{texture_type}_{mood}_{bars}bars.mid"

    exporter = TextureMIDIExporter()
    return exporter.events_to_midi_file(
        events, output_path, tempo, texture_type.title()
    )


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    from song_spec import create_default_trance_spec

    print("=" * 60)
    print("TEXTURE MIDI EXPORT DEMO")
    print("=" * 60)

    # Create a demo song spec
    spec = create_default_trance_spec("TextureDemo")
    spec.mood = "euphoric"

    print(f"\nSong: {spec.name}")
    print(f"Tempo: {spec.tempo} BPM")
    print(f"Key: {spec.key} {spec.scale}")
    print(f"Mood: {spec.mood}")
    print(f"Duration: {spec.duration_formatted}")
    print()

    # Output directory
    output_dir = DEFAULT_CONFIG.OUTPUT_BASE / "texture_demo" / "midi"
    print(f"Output: {output_dir}")
    print()

    # Generate textures
    print("Generating textures...")
    files = generate_textures_for_song(spec, output_dir)

    print("\nGenerated files:")
    for tex_type, filepath in files.items():
        print(f"  {tex_type}: {Path(filepath).name}")

    print()

    # Generate single texture demo
    print("Single texture demos:")

    moods_to_demo = ["dark", "euphoric", "aggressive"]
    texture_types = ["riser", "impact", "atmosphere"]

    for mood in moods_to_demo:
        for tex in texture_types:
            filepath = generate_texture_track(
                tex, 4, mood, "A", 138,
                str(output_dir / f"demo_{tex}_{mood}.mid")
            )
            print(f"  {tex} ({mood}): {Path(filepath).name}")

    print()
    print("Done!")
