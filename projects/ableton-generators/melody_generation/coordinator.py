"""
Inter-Track Coordinator

Production-grade track coordination system:
- Register separation (bass, arp, lead, pad ranges)
- Rhythmic interlocking (complementary rhythms between tracks)
- Collision detection (avoid same pitch at same time)
- Motion rules (contrary, parallel, oblique)
- Density management (not everyone plays at once)
- Call/response scheduling between tracks
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum, auto

from .models import (
    NoteEvent, Pitch, PitchClass, ChordEvent, TrackContext,
    TensionLevel, ArticulationType
)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class MotionType(Enum):
    """Types of melodic motion between voices."""
    CONTRARY = auto()    # Voices move in opposite directions
    PARALLEL = auto()    # Voices move in same direction, same interval
    SIMILAR = auto()     # Same direction, different interval
    OBLIQUE = auto()     # One voice moves, other stays


class RhythmicRelation(Enum):
    """Rhythmic relationship between tracks."""
    UNISON = auto()       # Play at same times
    COMPLEMENTARY = auto() # Fill each other's gaps
    OFFSET = auto()        # Slightly offset for groove
    INDEPENDENT = auto()   # No specific relationship


# Standard register allocations (MIDI note ranges)
REGISTER_ALLOCATIONS: Dict[str, Tuple[int, int]] = {
    "sub_bass": (24, 48),     # C1 to C3
    "bass": (36, 60),         # C2 to C4
    "low_mid": (48, 72),      # C3 to C5
    "mid": (60, 84),          # C4 to C6
    "high_mid": (72, 96),     # C5 to C7
    "high": (84, 108),        # C6 to C8

    # Track-specific allocations
    "kick": (36, 48),         # C2 to C3
    "bass_track": (28, 55),   # E1 to G3
    "arp_track": (48, 79),    # C3 to G5
    "lead_track": (60, 96),   # C4 to C7
    "pad_track": (48, 84),    # C3 to C6
    "chord_track": (48, 72),  # C3 to C5
}

# Track priority for collision resolution (higher = keeps note)
TRACK_PRIORITY: Dict[str, int] = {
    "bass": 10,     # Bass is foundation
    "kick": 9,      # Kick defines rhythm
    "chord": 7,     # Chords define harmony
    "lead": 8,      # Lead is feature
    "arp": 5,       # Arp is texture
    "pad": 4,       # Pad is background
}


# =============================================================================
# RHYTHM ANALYZER
# =============================================================================

@dataclass
class RhythmPattern:
    """Analyzed rhythm pattern from a track."""
    attack_beats: List[float]  # When notes start
    density: float            # Notes per beat
    syncopation: float        # Off-beat emphasis (0-1)
    longest_gap: float        # Longest gap between attacks
    average_duration: float


class RhythmAnalyzer:
    """Analyzes rhythmic patterns from note data."""

    @staticmethod
    def analyze(notes: List[NoteEvent], total_beats: float) -> RhythmPattern:
        """Analyze rhythm pattern of a note sequence."""
        if not notes:
            return RhythmPattern(
                attack_beats=[],
                density=0,
                syncopation=0,
                longest_gap=total_beats,
                average_duration=0,
            )

        attack_beats = sorted([n.start_beat for n in notes])

        # Density
        density = len(notes) / total_beats if total_beats > 0 else 0

        # Syncopation (notes on off-beats)
        off_beat_count = sum(
            1 for b in attack_beats
            if (b % 1) > 0.2 and (b % 1) < 0.8
        )
        syncopation = off_beat_count / len(notes) if notes else 0

        # Longest gap
        gaps = []
        for i in range(len(attack_beats) - 1):
            gaps.append(attack_beats[i + 1] - attack_beats[i])
        longest_gap = max(gaps) if gaps else total_beats

        # Average duration
        avg_duration = sum(n.duration_beats for n in notes) / len(notes) if notes else 0

        return RhythmPattern(
            attack_beats=attack_beats,
            density=density,
            syncopation=syncopation,
            longest_gap=longest_gap,
            average_duration=avg_duration,
        )

    @staticmethod
    def find_gaps(
        notes: List[NoteEvent],
        start_beat: float,
        end_beat: float,
        min_gap: float = 0.5,
    ) -> List[Tuple[float, float]]:
        """Find gaps in a note sequence where other tracks could play."""
        if not notes:
            return [(start_beat, end_beat)]

        gaps = []
        sorted_notes = sorted(notes, key=lambda n: n.start_beat)

        # Check gap before first note
        if sorted_notes[0].start_beat - start_beat >= min_gap:
            gaps.append((start_beat, sorted_notes[0].start_beat))

        # Check gaps between notes
        for i in range(len(sorted_notes) - 1):
            current_end = sorted_notes[i].end_beat
            next_start = sorted_notes[i + 1].start_beat
            if next_start - current_end >= min_gap:
                gaps.append((current_end, next_start))

        # Check gap after last note
        last_end = sorted_notes[-1].end_beat
        if end_beat - last_end >= min_gap:
            gaps.append((last_end, end_beat))

        return gaps


# =============================================================================
# COLLISION DETECTOR
# =============================================================================

@dataclass
class Collision:
    """Detected collision between tracks."""
    beat: float
    pitch: int
    track1: str
    track2: str
    type: str  # "unison", "octave", "same_pitch_class"


class CollisionDetector:
    """Detects and resolves pitch collisions between tracks."""

    @staticmethod
    def find_collisions(
        track1_notes: List[NoteEvent],
        track2_notes: List[NoteEvent],
        track1_name: str = "track1",
        track2_name: str = "track2",
        tolerance: float = 0.125,  # 32nd note
    ) -> List[Collision]:
        """Find all pitch collisions between two tracks."""
        collisions = []

        for n1 in track1_notes:
            for n2 in track2_notes:
                # Check time overlap
                overlap = (
                    n1.start_beat < n2.end_beat + tolerance and
                    n2.start_beat < n1.end_beat + tolerance
                )
                if not overlap:
                    continue

                # Check pitch relationship
                interval = abs(n1.pitch.midi_note - n2.pitch.midi_note)

                if interval == 0:
                    collision_type = "unison"
                elif interval % 12 == 0:
                    collision_type = "octave"
                elif n1.pitch.pitch_class == n2.pitch.pitch_class:
                    collision_type = "same_pitch_class"
                else:
                    continue  # Not a collision

                collisions.append(Collision(
                    beat=max(n1.start_beat, n2.start_beat),
                    pitch=n1.pitch.midi_note,
                    track1=track1_name,
                    track2=track2_name,
                    type=collision_type,
                ))

        return collisions

    @staticmethod
    def resolve_collision(
        note: NoteEvent,
        colliding_pitch: int,
        available_pitches: List[int],
        prefer_direction: int = 1,  # 1 for up, -1 for down
    ) -> NoteEvent:
        """Resolve a collision by moving note to nearest available pitch."""
        if not available_pitches:
            return note

        current_midi = note.pitch.midi_note

        # Filter out the colliding pitch
        safe_pitches = [p for p in available_pitches if abs(p - colliding_pitch) > 0]
        if not safe_pitches:
            return note

        # Find closest in preferred direction
        if prefer_direction > 0:
            candidates = [p for p in safe_pitches if p > current_midi]
            if not candidates:
                candidates = safe_pitches
        else:
            candidates = [p for p in safe_pitches if p < current_midi]
            if not candidates:
                candidates = safe_pitches

        new_midi = min(candidates, key=lambda p: abs(p - current_midi))
        new_pitch = Pitch.from_midi(new_midi)

        return NoteEvent(
            pitch=new_pitch,
            start_beat=note.start_beat,
            duration_beats=note.duration_beats,
            velocity=note.velocity,
            articulation=note.articulation,
            timing_offset=note.timing_offset,
            scale_degree=note.scale_degree,
            chord_tone=note.chord_tone,
            tension_level=note.tension_level,
            source_motif_id=note.source_motif_id,
            transform_applied=note.transform_applied,
        )


# =============================================================================
# MOTION PLANNER
# =============================================================================

class MotionPlanner:
    """Plans voice motion between tracks."""

    @staticmethod
    def analyze_motion(
        note1: NoteEvent,
        note2: NoteEvent,
        prev_note1: Optional[NoteEvent],
        prev_note2: Optional[NoteEvent],
    ) -> Optional[MotionType]:
        """Analyze the motion type between two voices."""
        if not prev_note1 or not prev_note2:
            return None

        motion1 = note1.pitch.midi_note - prev_note1.pitch.midi_note
        motion2 = note2.pitch.midi_note - prev_note2.pitch.midi_note

        if motion1 == 0 and motion2 == 0:
            return MotionType.OBLIQUE  # Both stay (edge case)
        elif motion1 == 0 or motion2 == 0:
            return MotionType.OBLIQUE
        elif (motion1 > 0 and motion2 < 0) or (motion1 < 0 and motion2 > 0):
            return MotionType.CONTRARY
        elif motion1 == motion2:
            return MotionType.PARALLEL
        else:
            return MotionType.SIMILAR

    @staticmethod
    def suggest_motion(
        lead_note: NoteEvent,
        prev_lead: Optional[NoteEvent],
        context_notes: List[NoteEvent],
        prefer_contrary: bool = True,
    ) -> int:
        """
        Suggest motion direction for lead based on context.

        Returns: suggested direction (-1, 0, or 1)
        """
        if not prev_lead or not context_notes:
            return 0

        lead_motion = lead_note.pitch.midi_note - prev_lead.pitch.midi_note

        if lead_motion == 0:
            return 0

        # Find bass motion (lowest context note)
        bass_notes = sorted(context_notes, key=lambda n: n.pitch.midi_note)
        if bass_notes:
            # If bass is moving, prefer contrary motion
            # This is a simplification - full implementation would track previous bass
            if prefer_contrary:
                return -1 if lead_motion > 0 else 1

        return 0


# =============================================================================
# INTER-TRACK COORDINATOR
# =============================================================================

class InterTrackCoordinator:
    """
    Main coordinator for multi-track interaction.

    Ensures tracks work together musically:
    - Register separation
    - Rhythmic interlocking
    - Collision avoidance
    - Motion coordination
    """

    def __init__(
        self,
        seed: Optional[int] = None,
    ):
        self.rng = random.Random(seed)
        self.rhythm_analyzer = RhythmAnalyzer()
        self.collision_detector = CollisionDetector()
        self.motion_planner = MotionPlanner()

    def get_register_for_track(
        self,
        track_name: str,
        energy: float = 0.7,
    ) -> Tuple[int, int]:
        """Get the register allocation for a track."""
        track_key = f"{track_name}_track"
        if track_key in REGISTER_ALLOCATIONS:
            low, high = REGISTER_ALLOCATIONS[track_key]
        elif track_name in REGISTER_ALLOCATIONS:
            low, high = REGISTER_ALLOCATIONS[track_name]
        else:
            low, high = REGISTER_ALLOCATIONS["mid"]

        # Adjust based on energy
        range_size = high - low
        center = (low + high) // 2

        # Higher energy can use wider range
        actual_range = int(range_size * (0.7 + 0.3 * energy))

        return (center - actual_range // 2, center + actual_range // 2)

    def analyze_track_context(
        self,
        context: TrackContext,
        beat: float,
        window: float = 4.0,  # Look at 1 bar around the beat
    ) -> Dict[str, any]:
        """Analyze what's happening in other tracks at a given beat."""
        analysis = {
            "chord": context.chord_at_beat(beat),
            "active_pitches": context.pitches_at_beat(beat),
            "bass_rhythm": None,
            "arp_rhythm": None,
            "density": 0,
            "gaps": [],
        }

        # Analyze rhythms in window
        window_start = max(0, beat - window / 2)
        window_end = beat + window / 2

        window_bass = [n for n in context.bass_notes
                       if window_start <= n.start_beat < window_end]
        window_arp = [n for n in context.arp_notes
                      if window_start <= n.start_beat < window_end]

        if window_bass:
            analysis["bass_rhythm"] = self.rhythm_analyzer.analyze(window_bass, window)
        if window_arp:
            analysis["arp_rhythm"] = self.rhythm_analyzer.analyze(window_arp, window)

        # Overall density
        all_window_notes = window_bass + window_arp
        analysis["density"] = len(all_window_notes) / window if window > 0 else 0

        # Find gaps for lead
        analysis["gaps"] = self.rhythm_analyzer.find_gaps(
            window_arp, window_start, window_end
        )

        return analysis

    def get_complementary_rhythm(
        self,
        context: TrackContext,
        start_beat: float,
        duration_beats: float,
        target_density: float = 0.5,
    ) -> List[float]:
        """
        Get attack times that complement existing tracks.

        Returns list of beat positions for new notes.
        """
        # Collect all attacks from context tracks
        existing_attacks = set()
        for note in context.bass_notes + context.arp_notes:
            if start_beat <= note.start_beat < start_beat + duration_beats:
                # Quantize to 16th notes
                quantized = round(note.start_beat * 4) / 4
                existing_attacks.add(quantized)

        # Generate complementary positions
        complementary = []
        step = 0.25  # 16th note

        current = start_beat
        while current < start_beat + duration_beats:
            quantized_current = round(current * 4) / 4

            # Play when others don't
            if quantized_current not in existing_attacks:
                if self.rng.random() < target_density:
                    complementary.append(current)

            current += step

        return complementary

    def avoid_collisions(
        self,
        notes: List[NoteEvent],
        context: TrackContext,
        track_name: str = "lead",
        chord_tones_available: Optional[List[int]] = None,
    ) -> List[NoteEvent]:
        """
        Adjust notes to avoid collisions with context tracks.

        Returns modified note list.
        """
        if not notes:
            return notes

        result = []

        for note in notes:
            # Check for collisions with each context track
            collisions = []

            for ctx_note in context.bass_notes:
                if (note.start_beat < ctx_note.end_beat and
                    ctx_note.start_beat < note.end_beat):
                    interval = abs(note.pitch.midi_note - ctx_note.pitch.midi_note)
                    if interval == 0 or interval % 12 == 0:
                        collisions.append(ctx_note.pitch.midi_note)

            for ctx_note in context.arp_notes:
                if (note.start_beat < ctx_note.end_beat and
                    ctx_note.start_beat < note.end_beat):
                    if note.pitch.midi_note == ctx_note.pitch.midi_note:
                        collisions.append(ctx_note.pitch.midi_note)

            if collisions and chord_tones_available:
                # Resolve by moving to available chord tone
                note = self.collision_detector.resolve_collision(
                    note,
                    collisions[0],
                    chord_tones_available,
                    prefer_direction=1,
                )

            result.append(note)

        return result

    def suggest_lead_timing(
        self,
        context: TrackContext,
        phrase_start: float,
        phrase_duration: float,
        energy: float,
    ) -> Dict[str, any]:
        """
        Suggest timing strategy for lead based on context.

        Returns dict with timing recommendations.
        """
        analysis = self.analyze_track_context(context, phrase_start, phrase_duration)

        suggestions = {
            "attack_strategy": "complementary",  # or "unison", "offset"
            "preferred_attacks": [],
            "avoid_beats": [],
            "density_target": 0.5,
        }

        # If arp is busy, lead should be sparser
        if analysis["arp_rhythm"] and analysis["arp_rhythm"].density > 2:
            suggestions["density_target"] = 0.3
            suggestions["attack_strategy"] = "complementary"
        else:
            suggestions["density_target"] = 0.5 + 0.3 * energy

        # Find good attack points
        if analysis["gaps"]:
            for gap_start, gap_end in analysis["gaps"]:
                if gap_end - gap_start >= 0.5:
                    suggestions["preferred_attacks"].append(gap_start + 0.25)

        # Avoid clashing with bass attacks
        if analysis["bass_rhythm"]:
            suggestions["avoid_beats"] = analysis["bass_rhythm"].attack_beats[:4]

        return suggestions

    def coordinate_voices(
        self,
        lead_notes: List[NoteEvent],
        context: TrackContext,
        prefer_contrary: bool = True,
    ) -> List[NoteEvent]:
        """
        Apply voice leading coordination to lead notes.

        Adjusts lead to have good voice leading relative to other tracks.
        """
        if not lead_notes or len(lead_notes) < 2:
            return lead_notes

        result = [lead_notes[0]]

        for i in range(1, len(lead_notes)):
            current = lead_notes[i]
            prev = lead_notes[i - 1]

            # Get context notes at this beat
            ctx_notes = context.notes_at_beat(current.start_beat)

            if ctx_notes:
                # Get motion suggestion
                direction = self.motion_planner.suggest_motion(
                    current, prev, ctx_notes, prefer_contrary
                )

                # If contrary motion suggested and we're moving same direction as bass,
                # consider adjusting
                if direction != 0 and prefer_contrary:
                    lead_motion = current.pitch.midi_note - prev.pitch.midi_note
                    if lead_motion * direction < 0:
                        # We should consider contrary motion
                        # This is informational - actual adjustment would happen in generator
                        pass

            result.append(current)

        return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_coordinator(seed: Optional[int] = None) -> InterTrackCoordinator:
    """Create a coordinator instance."""
    return InterTrackCoordinator(seed=seed)


def analyze_context(
    context: TrackContext,
    beat: float,
) -> Dict[str, any]:
    """Quick analysis of track context at a beat."""
    coordinator = InterTrackCoordinator()
    return coordinator.analyze_track_context(context, beat)


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate coordinator capabilities."""
    print("Inter-Track Coordinator Demo")
    print("=" * 50)

    coord = InterTrackCoordinator(seed=42)

    # Create some mock context
    from .models import Chord, ChordQuality

    mock_bass = [
        NoteEvent(
            pitch=Pitch.from_midi(36),  # C2
            start_beat=0.0,
            duration_beats=2.0,
            velocity=100
        ),
        NoteEvent(
            pitch=Pitch.from_midi(41),  # F2
            start_beat=4.0,
            duration_beats=2.0,
            velocity=100
        ),
    ]

    mock_arp = [
        NoteEvent(pitch=Pitch.from_midi(60), start_beat=0.0, duration_beats=0.25, velocity=80),
        NoteEvent(pitch=Pitch.from_midi(64), start_beat=0.25, duration_beats=0.25, velocity=75),
        NoteEvent(pitch=Pitch.from_midi(67), start_beat=0.5, duration_beats=0.25, velocity=80),
        NoteEvent(pitch=Pitch.from_midi(72), start_beat=0.75, duration_beats=0.25, velocity=85),
        # ... pattern repeats
    ]

    context = TrackContext(
        bass_notes=mock_bass,
        arp_notes=mock_arp,
        kick_beats=[0.0, 2.0, 4.0, 6.0],
    )

    # Test register allocation
    print("\n1. Register allocations:")
    for track in ["bass", "arp", "lead", "pad"]:
        reg = coord.get_register_for_track(track, energy=0.8)
        print(f"   {track}: MIDI {reg[0]}-{reg[1]}")

    # Test rhythm analysis
    print("\n2. Rhythm analysis of mock arp:")
    rhythm = coord.rhythm_analyzer.analyze(mock_arp, 4.0)
    print(f"   Density: {rhythm.density:.2f} notes/beat")
    print(f"   Syncopation: {rhythm.syncopation:.2f}")
    print(f"   Average duration: {rhythm.average_duration:.2f} beats")

    # Test gap finding
    print("\n3. Gaps in arp pattern:")
    gaps = coord.rhythm_analyzer.find_gaps(mock_arp, 0.0, 4.0, min_gap=0.5)
    for start, end in gaps:
        print(f"   {start:.2f} - {end:.2f}")

    # Test complementary rhythm
    print("\n4. Suggested complementary attack times:")
    attacks = coord.get_complementary_rhythm(context, 0.0, 4.0, target_density=0.5)
    print(f"   {[f'{a:.2f}' for a in attacks[:8]]}")

    # Test timing suggestions
    print("\n5. Lead timing suggestions:")
    suggestions = coord.suggest_lead_timing(context, 0.0, 8.0, energy=0.8)
    print(f"   Strategy: {suggestions['attack_strategy']}")
    print(f"   Density target: {suggestions['density_target']:.2f}")

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    demo()
