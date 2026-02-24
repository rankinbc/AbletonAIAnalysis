"""
Humanization Engine

Production-grade humanization for MIDI:
- Micro-timing variations (push/pull against grid)
- Velocity curves and dynamics
- Articulation variation
- Groove templates
- Expression automation suggestions

Makes generated MIDI feel performed rather than programmed.
"""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum, auto

from .models import (
    NoteEvent, Pitch, ArticulationType, TensionLevel
)


# =============================================================================
# GROOVE TEMPLATES
# =============================================================================

class GrooveStyle(Enum):
    """Groove style presets."""
    STRAIGHT = auto()      # Perfectly on grid
    SWING_LIGHT = auto()   # Light swing (55%)
    SWING_MEDIUM = auto()  # Medium swing (60%)
    SWING_HEAVY = auto()   # Heavy swing (66%)
    PUSH = auto()          # Slightly ahead of beat
    LAY_BACK = auto()      # Slightly behind beat
    HUMAN = auto()         # Natural human variation
    TRANCE = auto()        # Trance-specific groove
    TECHNO = auto()        # Techno-specific groove


@dataclass
class GrooveTemplate:
    """Defines timing offsets for a groove feel."""
    name: str
    # Timing offsets for each 16th note position in a beat (4 positions per beat)
    # Values are in beats, positive = late, negative = early
    offsets: List[float]
    # Velocity multipliers for each position
    velocity_mults: List[float]

    def get_offset(self, beat: float) -> float:
        """Get timing offset for a beat position."""
        position = int((beat * 4) % 4)  # 16th note position
        return self.offsets[position % len(self.offsets)]

    def get_velocity_mult(self, beat: float) -> float:
        """Get velocity multiplier for a beat position."""
        position = int((beat * 4) % 4)
        return self.velocity_mults[position % len(self.velocity_mults)]


GROOVE_TEMPLATES: Dict[GrooveStyle, GrooveTemplate] = {
    GrooveStyle.STRAIGHT: GrooveTemplate(
        name="Straight",
        offsets=[0.0, 0.0, 0.0, 0.0],
        velocity_mults=[1.0, 0.85, 0.95, 0.8],
    ),

    GrooveStyle.SWING_LIGHT: GrooveTemplate(
        name="Light Swing",
        offsets=[0.0, 0.02, 0.0, 0.02],  # Delay 2nd and 4th 16ths
        velocity_mults=[1.0, 0.75, 0.9, 0.7],
    ),

    GrooveStyle.SWING_MEDIUM: GrooveTemplate(
        name="Medium Swing",
        offsets=[0.0, 0.04, 0.0, 0.04],
        velocity_mults=[1.0, 0.7, 0.85, 0.65],
    ),

    GrooveStyle.SWING_HEAVY: GrooveTemplate(
        name="Heavy Swing",
        offsets=[0.0, 0.06, 0.0, 0.06],
        velocity_mults=[1.0, 0.65, 0.8, 0.6],
    ),

    GrooveStyle.PUSH: GrooveTemplate(
        name="Push",
        offsets=[-0.02, -0.015, -0.01, -0.015],
        velocity_mults=[1.0, 0.85, 0.95, 0.85],
    ),

    GrooveStyle.LAY_BACK: GrooveTemplate(
        name="Lay Back",
        offsets=[0.02, 0.015, 0.01, 0.015],
        velocity_mults=[1.0, 0.8, 0.9, 0.8],
    ),

    GrooveStyle.HUMAN: GrooveTemplate(
        name="Human Feel",
        offsets=[0.0, 0.01, -0.005, 0.015],
        velocity_mults=[1.0, 0.82, 0.92, 0.78],
    ),

    GrooveStyle.TRANCE: GrooveTemplate(
        name="Trance",
        offsets=[0.0, 0.0, -0.01, 0.01],  # Slight push on beat 3
        velocity_mults=[1.0, 0.75, 0.95, 0.7],  # Strong 1 and 3
    ),

    GrooveStyle.TECHNO: GrooveTemplate(
        name="Techno",
        offsets=[0.0, 0.02, 0.0, 0.03],  # Off-beat emphasis
        velocity_mults=[1.0, 0.85, 0.9, 0.9],  # More even velocity
    ),
}


# =============================================================================
# VELOCITY CURVES
# =============================================================================

class VelocityCurve(Enum):
    """Velocity curve shapes for phrases."""
    FLAT = auto()          # Constant velocity
    ARCH = auto()          # Rise then fall
    CRESCENDO = auto()     # Gradually louder
    DECRESCENDO = auto()   # Gradually softer
    ACCENT_DOWNBEATS = auto()  # Accent on beats 1 and 3
    RANDOM = auto()        # Random variation


def get_velocity_curve_fn(curve: VelocityCurve) -> Callable[[float], float]:
    """Get velocity curve function (progress 0-1 → multiplier)."""
    curves = {
        VelocityCurve.FLAT: lambda p: 1.0,
        VelocityCurve.ARCH: lambda p: 0.8 + 0.4 * math.sin(p * math.pi),
        VelocityCurve.CRESCENDO: lambda p: 0.7 + 0.3 * p,
        VelocityCurve.DECRESCENDO: lambda p: 1.0 - 0.3 * p,
        VelocityCurve.ACCENT_DOWNBEATS: lambda p: 1.0,  # Handled separately
        VelocityCurve.RANDOM: lambda p: 0.8 + 0.4 * random.random(),
    }
    return curves.get(curve, lambda p: 1.0)


# =============================================================================
# HUMANIZER
# =============================================================================

@dataclass
class HumanizeConfig:
    """Configuration for humanization."""
    # Timing
    groove_style: GrooveStyle = GrooveStyle.HUMAN
    timing_variance: float = 0.015  # Random timing variance (beats)

    # Velocity
    velocity_curve: VelocityCurve = VelocityCurve.ARCH
    velocity_variance: float = 0.1  # Random velocity variance (0-1)

    # Articulation
    vary_articulation: bool = True
    staccato_probability: float = 0.1  # Chance of making a note staccato

    # Duration
    duration_variance: float = 0.05  # Random duration variance (0-1)
    gate_variance: float = 0.1  # Gate length variance


class Humanizer:
    """
    Applies humanization to MIDI note sequences.

    Makes programmed sequences sound more human by adding
    subtle timing, velocity, and articulation variations.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
    ):
        self.rng = random.Random(seed)

    def humanize(
        self,
        notes: List[NoteEvent],
        config: Optional[HumanizeConfig] = None,
        phrase_duration: Optional[float] = None,
    ) -> List[NoteEvent]:
        """
        Apply humanization to a list of notes.

        Args:
            notes: Input notes to humanize
            config: Humanization configuration
            phrase_duration: Total phrase duration for curve calculations

        Returns:
            Humanized notes (new list, original unchanged)
        """
        if not notes:
            return []

        if config is None:
            config = HumanizeConfig()

        # Calculate phrase duration if not provided
        if phrase_duration is None:
            phrase_duration = max(n.end_beat for n in notes) - min(n.start_beat for n in notes)
            phrase_duration = max(phrase_duration, 1.0)

        phrase_start = min(n.start_beat for n in notes)

        # Get groove template
        groove = GROOVE_TEMPLATES.get(config.groove_style, GROOVE_TEMPLATES[GrooveStyle.STRAIGHT])

        # Get velocity curve function
        vel_curve_fn = get_velocity_curve_fn(config.velocity_curve)

        humanized = []

        for note in notes:
            # Calculate progress through phrase (0-1)
            progress = (note.start_beat - phrase_start) / phrase_duration

            # --- Timing ---
            # Groove offset
            groove_offset = groove.get_offset(note.start_beat)

            # Random timing variance
            timing_variance = self.rng.gauss(0, config.timing_variance)

            total_timing = note.timing_offset + groove_offset + timing_variance

            # --- Velocity ---
            # Groove velocity
            groove_vel = groove.get_velocity_mult(note.start_beat)

            # Phrase curve velocity
            curve_vel = vel_curve_fn(progress)

            # Accent downbeats if that curve is selected
            if config.velocity_curve == VelocityCurve.ACCENT_DOWNBEATS:
                beat_pos = note.start_beat % 1
                if beat_pos < 0.1 or abs(beat_pos - 0.5) < 0.1:
                    curve_vel = 1.1
                else:
                    curve_vel = 0.85

            # Random velocity variance
            vel_variance = 1.0 + self.rng.gauss(0, config.velocity_variance)

            final_velocity = int(note.velocity * groove_vel * curve_vel * vel_variance)
            final_velocity = max(30, min(127, final_velocity))

            # --- Duration ---
            duration_variance = 1.0 + self.rng.gauss(0, config.duration_variance)
            final_duration = note.duration_beats * duration_variance
            final_duration = max(0.05, final_duration)

            # --- Articulation ---
            articulation = note.articulation
            if config.vary_articulation:
                if self.rng.random() < config.staccato_probability:
                    articulation = ArticulationType.STACCATO
                    final_duration *= 0.5

            # Create humanized note
            humanized.append(NoteEvent(
                pitch=note.pitch,
                start_beat=note.start_beat,  # Keep original for sorting
                duration_beats=final_duration,
                velocity=final_velocity,
                articulation=articulation,
                timing_offset=total_timing,
                scale_degree=note.scale_degree,
                chord_tone=note.chord_tone,
                tension_level=note.tension_level,
                source_motif_id=note.source_motif_id,
                transform_applied=note.transform_applied,
            ))

        return humanized

    def apply_groove(
        self,
        notes: List[NoteEvent],
        groove_style: GrooveStyle,
    ) -> List[NoteEvent]:
        """Apply only groove template (no random variation)."""
        groove = GROOVE_TEMPLATES.get(groove_style, GROOVE_TEMPLATES[GrooveStyle.STRAIGHT])

        result = []
        for note in notes:
            offset = groove.get_offset(note.start_beat)
            vel_mult = groove.get_velocity_mult(note.start_beat)

            result.append(NoteEvent(
                pitch=note.pitch,
                start_beat=note.start_beat,
                duration_beats=note.duration_beats,
                velocity=int(note.velocity * vel_mult),
                articulation=note.articulation,
                timing_offset=note.timing_offset + offset,
                scale_degree=note.scale_degree,
                chord_tone=note.chord_tone,
                tension_level=note.tension_level,
                source_motif_id=note.source_motif_id,
                transform_applied=note.transform_applied,
            ))

        return result

    def apply_velocity_curve(
        self,
        notes: List[NoteEvent],
        curve: VelocityCurve,
    ) -> List[NoteEvent]:
        """Apply only velocity curve (no timing changes)."""
        if not notes:
            return []

        phrase_start = min(n.start_beat for n in notes)
        phrase_end = max(n.end_beat for n in notes)
        duration = max(phrase_end - phrase_start, 1.0)

        curve_fn = get_velocity_curve_fn(curve)

        result = []
        for note in notes:
            progress = (note.start_beat - phrase_start) / duration
            mult = curve_fn(progress)

            result.append(NoteEvent(
                pitch=note.pitch,
                start_beat=note.start_beat,
                duration_beats=note.duration_beats,
                velocity=max(30, min(127, int(note.velocity * mult))),
                articulation=note.articulation,
                timing_offset=note.timing_offset,
                scale_degree=note.scale_degree,
                chord_tone=note.chord_tone,
                tension_level=note.tension_level,
                source_motif_id=note.source_motif_id,
                transform_applied=note.transform_applied,
            ))

        return result

    def randomize_timing(
        self,
        notes: List[NoteEvent],
        variance: float = 0.02,
    ) -> List[NoteEvent]:
        """Apply random timing variance only."""
        result = []
        for note in notes:
            offset = self.rng.gauss(0, variance)
            result.append(NoteEvent(
                pitch=note.pitch,
                start_beat=note.start_beat,
                duration_beats=note.duration_beats,
                velocity=note.velocity,
                articulation=note.articulation,
                timing_offset=note.timing_offset + offset,
                scale_degree=note.scale_degree,
                chord_tone=note.chord_tone,
                tension_level=note.tension_level,
                source_motif_id=note.source_motif_id,
                transform_applied=note.transform_applied,
            ))
        return result


# =============================================================================
# EXPRESSION SUGGESTER
# =============================================================================

@dataclass
class ExpressionSuggestion:
    """Suggestion for expression automation."""
    parameter: str  # "filter_cutoff", "modulation", etc.
    start_beat: float
    end_beat: float
    start_value: float  # 0-1
    end_value: float    # 0-1
    curve: str  # "linear", "exponential", "logarithmic"


class ExpressionSuggester:
    """
    Suggests expression automation curves.

    These are suggestions only - actual automation would be
    applied in the DAW or through additional processing.
    """

    def suggest_filter_sweep(
        self,
        notes: List[NoteEvent],
        direction: str = "up",
    ) -> List[ExpressionSuggestion]:
        """Suggest filter sweep for a phrase."""
        if not notes:
            return []

        start = min(n.start_beat for n in notes)
        end = max(n.end_beat for n in notes)

        if direction == "up":
            return [ExpressionSuggestion(
                parameter="filter_cutoff",
                start_beat=start,
                end_beat=end,
                start_value=0.2,
                end_value=0.9,
                curve="exponential",
            )]
        else:
            return [ExpressionSuggestion(
                parameter="filter_cutoff",
                start_beat=start,
                end_beat=end,
                start_value=0.9,
                end_value=0.2,
                curve="logarithmic",
            )]

    def suggest_for_section(
        self,
        section_type: str,
        start_beat: float,
        end_beat: float,
    ) -> List[ExpressionSuggestion]:
        """Suggest expression for a section type."""
        suggestions = []

        if section_type == "buildup":
            # Filter opens
            suggestions.append(ExpressionSuggestion(
                parameter="filter_cutoff",
                start_beat=start_beat,
                end_beat=end_beat,
                start_value=0.3,
                end_value=1.0,
                curve="exponential",
            ))
            # Resonance increases
            suggestions.append(ExpressionSuggestion(
                parameter="filter_resonance",
                start_beat=start_beat,
                end_beat=end_beat,
                start_value=0.2,
                end_value=0.6,
                curve="linear",
            ))

        elif section_type == "breakdown":
            # Filter closes gradually
            suggestions.append(ExpressionSuggestion(
                parameter="filter_cutoff",
                start_beat=start_beat,
                end_beat=end_beat,
                start_value=0.8,
                end_value=0.4,
                curve="linear",
            ))

        elif section_type == "drop":
            # Full open, slight modulation
            pass  # Keep static or suggest LFO

        return suggestions


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def humanize(
    notes: List[NoteEvent],
    groove: GrooveStyle = GrooveStyle.HUMAN,
    intensity: float = 1.0,
    seed: Optional[int] = None,
) -> List[NoteEvent]:
    """
    Quick humanization function.

    Args:
        notes: Notes to humanize
        groove: Groove style
        intensity: How much humanization (0-1)
        seed: Random seed

    Returns:
        Humanized notes
    """
    humanizer = Humanizer(seed=seed)

    config = HumanizeConfig(
        groove_style=groove,
        timing_variance=0.02 * intensity,
        velocity_variance=0.15 * intensity,
    )

    return humanizer.humanize(notes, config)


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate humanizer capabilities."""
    print("Humanizer Demo")
    print("=" * 50)

    humanizer = Humanizer(seed=42)

    # Create test notes (simple arp pattern)
    test_notes = []
    for i in range(16):
        test_notes.append(NoteEvent(
            pitch=Pitch.from_midi(60 + (i % 4) * 4),
            start_beat=i * 0.25,
            duration_beats=0.2,
            velocity=90,
        ))

    print(f"\nOriginal notes: {len(test_notes)}")
    print("First 4 notes (before humanization):")
    for note in test_notes[:4]:
        print(f"  Beat {note.start_beat:.2f}: vel={note.velocity}, timing_offset={note.timing_offset:.4f}")

    # Test different grooves
    grooves = [GrooveStyle.STRAIGHT, GrooveStyle.SWING_MEDIUM, GrooveStyle.TRANCE]

    for groove in grooves:
        print(f"\n{groove.name} groove:")
        humanized = humanizer.apply_groove(test_notes, groove)
        print("First 4 notes (with groove):")
        for note in humanized[:4]:
            print(f"  Beat {note.start_beat:.2f}: vel={note.velocity}, timing_offset={note.timing_offset:.4f}")

    # Full humanization
    print("\n\nFull humanization (HUMAN groove + variance):")
    config = HumanizeConfig(
        groove_style=GrooveStyle.HUMAN,
        timing_variance=0.02,
        velocity_variance=0.1,
        velocity_curve=VelocityCurve.ARCH,
    )
    humanized = humanizer.humanize(test_notes, config)
    print("First 4 notes (fully humanized):")
    for note in humanized[:4]:
        print(f"  Beat {note.start_beat:.2f}: vel={note.velocity}, timing_offset={note.timing_offset:.4f}")

    # Expression suggestions
    print("\n\nExpression suggestions for buildup:")
    suggester = ExpressionSuggester()
    suggestions = suggester.suggest_for_section("buildup", 0, 32)
    for s in suggestions:
        print(f"  {s.parameter}: {s.start_value:.2f} → {s.end_value:.2f} ({s.curve})")

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    demo()
