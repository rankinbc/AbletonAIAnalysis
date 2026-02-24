"""
MIDI Variation Generator

Generates variations of MIDI patterns extracted from Ableton projects.
Supports transposition, timing shifts, humanization, quantization, and more.
"""

import random
import copy
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

try:
    from als_parser import MIDINote, MIDIClip
except ImportError:
    from src.als_parser import MIDINote, MIDIClip


@dataclass
class MIDIVariation:
    """A generated variation of a MIDI clip."""
    name: str
    notes: List[MIDINote]
    variation_type: str  # 'transpose', 'shift', 'humanize', etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    source_clip_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'notes': [self._note_to_dict(n) for n in self.notes],
            'variation_type': self.variation_type,
            'parameters': self.parameters,
            'source_clip_name': self.source_clip_name,
            'note_count': len(self.notes)
        }

    def _note_to_dict(self, note: MIDINote) -> Dict[str, Any]:
        return {
            'pitch': note.pitch,
            'velocity': note.velocity,
            'start_time': round(note.start_time, 4),
            'duration': round(note.duration, 4),
            'mute': note.mute
        }


class MIDIVariationGenerator:
    """Generate variations of MIDI patterns."""

    # Note names for display
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def transpose(self, notes: List[MIDINote], semitones: int) -> List[MIDINote]:
        """Shift all notes up/down by semitones.

        Args:
            notes: List of MIDI notes to transpose
            semitones: Number of semitones to shift (-12 to +12 typical)

        Returns:
            New list of transposed notes
        """
        result = []
        for note in notes:
            new_pitch = note.pitch + semitones
            # Clamp to valid MIDI range
            new_pitch = max(0, min(127, new_pitch))
            result.append(MIDINote(
                pitch=new_pitch,
                velocity=note.velocity,
                start_time=note.start_time,
                duration=note.duration,
                mute=note.mute
            ))
        return result

    def shift_timing(self, notes: List[MIDINote], beats: float) -> List[MIDINote]:
        """Shift all notes forward/backward in time.

        Args:
            notes: List of MIDI notes
            beats: Number of beats to shift (positive = later, negative = earlier)

        Returns:
            New list of time-shifted notes
        """
        result = []
        for note in notes:
            new_start = note.start_time + beats
            # Don't allow negative start times
            if new_start >= 0:
                result.append(MIDINote(
                    pitch=note.pitch,
                    velocity=note.velocity,
                    start_time=new_start,
                    duration=note.duration,
                    mute=note.mute
                ))
        return result

    def humanize(self, notes: List[MIDINote],
                 timing_variance: float = 0.02,
                 velocity_variance: int = 10) -> List[MIDINote]:
        """Add human-like timing and velocity variations.

        Args:
            notes: List of MIDI notes
            timing_variance: Max timing deviation in beats (default 0.02 = subtle)
            velocity_variance: Max velocity deviation (default 10)

        Returns:
            New list of humanized notes
        """
        result = []
        for note in notes:
            # Random timing offset
            timing_offset = random.uniform(-timing_variance, timing_variance)
            new_start = max(0, note.start_time + timing_offset)

            # Random velocity offset
            vel_offset = random.randint(-velocity_variance, velocity_variance)
            new_velocity = max(1, min(127, note.velocity + vel_offset))

            # Slight duration variation (±5%)
            duration_factor = random.uniform(0.95, 1.05)
            new_duration = note.duration * duration_factor

            result.append(MIDINote(
                pitch=note.pitch,
                velocity=new_velocity,
                start_time=new_start,
                duration=new_duration,
                mute=note.mute
            ))
        return result

    def quantize(self, notes: List[MIDINote], grid: float = 0.25) -> List[MIDINote]:
        """Snap notes to grid.

        Args:
            notes: List of MIDI notes
            grid: Grid size in beats (0.25 = 16th notes, 0.5 = 8th, 1.0 = quarter)

        Returns:
            New list of quantized notes
        """
        result = []
        for note in notes:
            # Snap start time to nearest grid point
            new_start = round(note.start_time / grid) * grid

            result.append(MIDINote(
                pitch=note.pitch,
                velocity=note.velocity,
                start_time=new_start,
                duration=note.duration,
                mute=note.mute
            ))
        return result

    def reverse(self, notes: List[MIDINote]) -> List[MIDINote]:
        """Reverse the note order while maintaining relative timing.

        Args:
            notes: List of MIDI notes

        Returns:
            New list with notes reversed in time
        """
        if not notes:
            return []

        # Find the total duration
        max_end = max(n.start_time + n.duration for n in notes)

        result = []
        for note in notes:
            # Mirror the position
            new_start = max_end - note.start_time - note.duration
            new_start = max(0, new_start)

            result.append(MIDINote(
                pitch=note.pitch,
                velocity=note.velocity,
                start_time=new_start,
                duration=note.duration,
                mute=note.mute
            ))

        # Sort by start time
        result.sort(key=lambda n: n.start_time)
        return result

    def change_velocity_curve(self, notes: List[MIDINote],
                              curve: str = 'crescendo') -> List[MIDINote]:
        """Apply velocity curves to notes.

        Args:
            notes: List of MIDI notes
            curve: Type of curve ('crescendo', 'decrescendo', 'accent_downbeats')

        Returns:
            New list with modified velocities
        """
        if not notes:
            return []

        # Sort by time for curve application
        sorted_notes = sorted(notes, key=lambda n: n.start_time)
        min_time = sorted_notes[0].start_time
        max_time = sorted_notes[-1].start_time

        result = []
        for i, note in enumerate(sorted_notes):
            # Calculate position in sequence (0 to 1)
            if max_time > min_time:
                position = (note.start_time - min_time) / (max_time - min_time)
            else:
                position = 0.5

            if curve == 'crescendo':
                # Gradually increase velocity
                vel_factor = 0.6 + (position * 0.4)
            elif curve == 'decrescendo':
                # Gradually decrease velocity
                vel_factor = 1.0 - (position * 0.4)
            elif curve == 'accent_downbeats':
                # Accent notes on beat boundaries
                if note.start_time % 1.0 < 0.1:  # On the beat
                    vel_factor = 1.1
                elif note.start_time % 0.5 < 0.1:  # On half beat
                    vel_factor = 1.0
                else:
                    vel_factor = 0.85
            else:
                vel_factor = 1.0

            new_velocity = int(note.velocity * vel_factor)
            new_velocity = max(1, min(127, new_velocity))

            result.append(MIDINote(
                pitch=note.pitch,
                velocity=new_velocity,
                start_time=note.start_time,
                duration=note.duration,
                mute=note.mute
            ))

        return result

    def octave_double(self, notes: List[MIDINote],
                      octave_offset: int = 1) -> List[MIDINote]:
        """Add octave-doubled notes.

        Args:
            notes: List of MIDI notes
            octave_offset: Octave to add (+1 = octave up, -1 = octave down)

        Returns:
            New list with original and doubled notes
        """
        result = []
        semitones = octave_offset * 12

        for note in notes:
            # Keep original
            result.append(copy.copy(note))

            # Add doubled note if in valid range
            new_pitch = note.pitch + semitones
            if 0 <= new_pitch <= 127:
                result.append(MIDINote(
                    pitch=new_pitch,
                    velocity=int(note.velocity * 0.8),  # Slightly quieter
                    start_time=note.start_time,
                    duration=note.duration,
                    mute=note.mute
                ))

        return result

    def arpeggiate(self, notes: List[MIDINote],
                   direction: str = 'up',
                   note_length: float = 0.25) -> List[MIDINote]:
        """Convert chords to arpeggios.

        Args:
            notes: List of MIDI notes (often chords)
            direction: 'up', 'down', or 'updown'
            note_length: Duration of each arpeggiated note in beats

        Returns:
            New list with arpeggiated notes
        """
        if not notes:
            return []

        # Group notes by start time (find chords)
        time_groups: Dict[float, List[MIDINote]] = {}
        tolerance = 0.05  # Notes within this range are considered simultaneous

        for note in notes:
            # Find matching time group
            found = False
            for time_key in time_groups:
                if abs(note.start_time - time_key) < tolerance:
                    time_groups[time_key].append(note)
                    found = True
                    break
            if not found:
                time_groups[note.start_time] = [note]

        result = []
        for base_time, chord_notes in sorted(time_groups.items()):
            if len(chord_notes) == 1:
                # Single note, keep as is
                result.append(chord_notes[0])
            else:
                # Arpeggiate the chord
                sorted_chord = sorted(chord_notes, key=lambda n: n.pitch)

                if direction == 'down':
                    sorted_chord = sorted_chord[::-1]
                elif direction == 'updown':
                    sorted_chord = sorted_chord + sorted_chord[-2:0:-1]

                for i, note in enumerate(sorted_chord):
                    result.append(MIDINote(
                        pitch=note.pitch,
                        velocity=note.velocity,
                        start_time=base_time + (i * note_length),
                        duration=note_length * 0.9,  # Slight gap
                        mute=note.mute
                    ))

        return result

    def generate_variations(self, clip: MIDIClip,
                           count: int = 4,
                           variation_types: List[str] = None) -> List[MIDIVariation]:
        """Generate multiple variations using different techniques.

        Args:
            clip: Source MIDI clip
            count: Number of variations to generate
            variation_types: Specific types to use (or None for auto-select)

        Returns:
            List of MIDIVariation objects
        """
        if not clip.notes:
            return []

        if variation_types is None:
            # Default variation set
            variation_types = [
                'transpose_up',
                'transpose_down',
                'humanize',
                'quantize',
                'reverse',
                'crescendo',
                'octave_up'
            ]

        variations = []
        used_types = []

        for i in range(count):
            # Pick a variation type we haven't used yet
            available = [t for t in variation_types if t not in used_types]
            if not available:
                available = variation_types  # Reset if exhausted

            var_type = random.choice(available)
            used_types.append(var_type)

            notes = list(clip.notes)  # Copy
            params = {}

            if var_type == 'transpose_up':
                semitones = random.choice([2, 3, 4, 5, 7])  # Musical intervals
                notes = self.transpose(notes, semitones)
                params = {'semitones': semitones}
                name = f"{clip.name} (+{semitones}st)"

            elif var_type == 'transpose_down':
                semitones = random.choice([2, 3, 4, 5, 7])
                notes = self.transpose(notes, -semitones)
                params = {'semitones': -semitones}
                name = f"{clip.name} (-{semitones}st)"

            elif var_type == 'humanize':
                timing_var = random.uniform(0.01, 0.03)
                vel_var = random.randint(5, 15)
                notes = self.humanize(notes, timing_var, vel_var)
                params = {'timing_variance': timing_var, 'velocity_variance': vel_var}
                name = f"{clip.name} (humanized)"

            elif var_type == 'quantize':
                grid = random.choice([0.25, 0.5])
                notes = self.quantize(notes, grid)
                params = {'grid': grid}
                grid_name = '16th' if grid == 0.25 else '8th'
                name = f"{clip.name} (quantized {grid_name})"

            elif var_type == 'reverse':
                notes = self.reverse(notes)
                name = f"{clip.name} (reversed)"

            elif var_type == 'crescendo':
                notes = self.change_velocity_curve(notes, 'crescendo')
                params = {'curve': 'crescendo'}
                name = f"{clip.name} (crescendo)"

            elif var_type == 'decrescendo':
                notes = self.change_velocity_curve(notes, 'decrescendo')
                params = {'curve': 'decrescendo'}
                name = f"{clip.name} (decrescendo)"

            elif var_type == 'octave_up':
                notes = self.octave_double(notes, 1)
                params = {'octave_offset': 1}
                name = f"{clip.name} (+8va)"

            elif var_type == 'octave_down':
                notes = self.octave_double(notes, -1)
                params = {'octave_offset': -1}
                name = f"{clip.name} (-8va)"

            elif var_type == 'arpeggio_up':
                notes = self.arpeggiate(notes, 'up')
                params = {'direction': 'up'}
                name = f"{clip.name} (arp up)"

            elif var_type == 'arpeggio_down':
                notes = self.arpeggiate(notes, 'down')
                params = {'direction': 'down'}
                name = f"{clip.name} (arp down)"

            else:
                # Unknown type, just copy
                name = f"{clip.name} (copy)"

            variations.append(MIDIVariation(
                name=name,
                notes=notes,
                variation_type=var_type,
                parameters=params,
                source_clip_name=clip.name
            ))

        return variations

    def detect_scale(self, notes: List[MIDINote]) -> Optional[str]:
        """Detect the likely scale/key of a set of notes.

        Args:
            notes: List of MIDI notes

        Returns:
            Scale name like 'C Major' or 'A Minor', or None if unclear
        """
        if not notes:
            return None

        # Count pitch classes (0-11)
        pitch_classes = set()
        for note in notes:
            pitch_classes.add(note.pitch % 12)

        # Major scale intervals: [0, 2, 4, 5, 7, 9, 11]
        # Minor scale intervals: [0, 2, 3, 5, 7, 8, 10]
        major_intervals = {0, 2, 4, 5, 7, 9, 11}
        minor_intervals = {0, 2, 3, 5, 7, 8, 10}

        best_match = None
        best_score = 0

        for root in range(12):
            # Check major
            major_shifted = {(i + root) % 12 for i in major_intervals}
            major_score = len(pitch_classes & major_shifted) / max(len(pitch_classes), 1)

            if major_score > best_score:
                best_score = major_score
                best_match = f"{self.NOTE_NAMES[root]} Major"

            # Check minor
            minor_shifted = {(i + root) % 12 for i in minor_intervals}
            minor_score = len(pitch_classes & minor_shifted) / max(len(pitch_classes), 1)

            if minor_score > best_score:
                best_score = minor_score
                best_match = f"{self.NOTE_NAMES[root]} Minor"

        # Only return if reasonably confident
        if best_score >= 0.7:
            return best_match
        return None

    def get_note_stats(self, notes: List[MIDINote]) -> Dict[str, Any]:
        """Get statistics about a set of notes.

        Args:
            notes: List of MIDI notes

        Returns:
            Dictionary with note statistics
        """
        if not notes:
            return {
                'note_count': 0,
                'duration_beats': 0,
                'pitch_range': None,
                'velocity_range': None,
                'scale': None
            }

        pitches = [n.pitch for n in notes]
        velocities = [n.velocity for n in notes]
        end_times = [n.start_time + n.duration for n in notes]

        return {
            'note_count': len(notes),
            'duration_beats': round(max(end_times) - min(n.start_time for n in notes), 2),
            'pitch_range': {
                'min': min(pitches),
                'max': max(pitches),
                'min_name': f"{self.NOTE_NAMES[min(pitches) % 12]}{min(pitches) // 12 - 1}",
                'max_name': f"{self.NOTE_NAMES[max(pitches) % 12]}{max(pitches) // 12 - 1}"
            },
            'velocity_range': {
                'min': min(velocities),
                'max': max(velocities),
                'avg': round(sum(velocities) / len(velocities))
            },
            'scale': self.detect_scale(notes)
        }
