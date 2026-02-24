"""
Phrase Builder & Contour Planner

Production-grade melodic phrase construction:
- Phrase structure (sentence form, period form, antecedent-consequent)
- Cadence planning (authentic, half, deceptive, plagal)
- Contour shaping (arch, wave, ascending, descending)
- Climax placement based on energy curves
- Register management with breathing room
- Tension/release curves across phrases
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable

from .models import (
    PhraseSpec, PhraseType, CadenceType, ContourShape,
    Motif, MotifInterval, MotifTransform, NoteEvent,
    Pitch, PitchClass, ChordEvent, TensionLevel,
    ArticulationType
)


# =============================================================================
# PHRASE STRUCTURE TEMPLATES
# =============================================================================

@dataclass
class PhraseTemplate:
    """Template for a phrase structure."""
    name: str
    total_bars: int
    segments: List[Tuple[int, str]]  # (bars, segment_type)
    cadence_points: List[Tuple[int, CadenceType]]  # (bar, cadence_type)
    energy_curve: List[float]  # Energy at each bar


# Classic phrase structures
PHRASE_TEMPLATES: Dict[str, PhraseTemplate] = {
    # 4-bar sentence: 1+1+2 structure
    "sentence_4": PhraseTemplate(
        name="4-bar sentence",
        total_bars=4,
        segments=[(1, "statement"), (1, "restatement"), (2, "continuation")],
        cadence_points=[(4, CadenceType.AUTHENTIC)],
        energy_curve=[0.7, 0.75, 0.85, 0.9],
    ),

    # 8-bar sentence: 2+2+4 structure
    "sentence_8": PhraseTemplate(
        name="8-bar sentence",
        total_bars=8,
        segments=[(2, "statement"), (2, "restatement"), (4, "continuation")],
        cadence_points=[(4, CadenceType.HALF), (8, CadenceType.AUTHENTIC)],
        energy_curve=[0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95],
    ),

    # Period: antecedent + consequent
    "period_8": PhraseTemplate(
        name="8-bar period",
        total_bars=8,
        segments=[(4, "antecedent"), (4, "consequent")],
        cadence_points=[(4, CadenceType.HALF), (8, CadenceType.AUTHENTIC)],
        energy_curve=[0.7, 0.75, 0.8, 0.7, 0.75, 0.8, 0.85, 0.9],
    ),

    # Double period: 16 bars
    "double_period_16": PhraseTemplate(
        name="16-bar double period",
        total_bars=16,
        segments=[
            (4, "antecedent_1"), (4, "consequent_1"),
            (4, "antecedent_2"), (4, "consequent_2"),
        ],
        cadence_points=[
            (4, CadenceType.HALF),
            (8, CadenceType.AUTHENTIC),
            (12, CadenceType.HALF),
            (16, CadenceType.AUTHENTIC),
        ],
        energy_curve=[0.6, 0.65, 0.7, 0.65, 0.7, 0.75, 0.8, 0.75,
                      0.7, 0.75, 0.8, 0.75, 0.8, 0.85, 0.9, 0.95],
    ),

    # Call and response (EDM style)
    "call_response_4": PhraseTemplate(
        name="4-bar call-response",
        total_bars=4,
        segments=[(2, "call"), (2, "response")],
        cadence_points=[(2, CadenceType.HALF), (4, CadenceType.AUTHENTIC)],
        energy_curve=[0.8, 0.85, 0.75, 0.9],
    ),

    # Build phrase (for buildups)
    "build_8": PhraseTemplate(
        name="8-bar build",
        total_bars=8,
        segments=[(2, "establish"), (2, "develop"), (2, "intensify"), (2, "climax")],
        cadence_points=[(8, CadenceType.HALF)],  # Unresolved for tension
        energy_curve=[0.5, 0.55, 0.6, 0.7, 0.75, 0.85, 0.9, 1.0],
    ),

    # Release phrase (for post-drop)
    "release_4": PhraseTemplate(
        name="4-bar release",
        total_bars=4,
        segments=[(1, "impact"), (1, "sustain"), (2, "settle")],
        cadence_points=[(4, CadenceType.AUTHENTIC)],
        energy_curve=[1.0, 0.9, 0.8, 0.7],
    ),

    # Breakdown phrase (emotional, drawn out)
    "breakdown_8": PhraseTemplate(
        name="8-bar breakdown",
        total_bars=8,
        segments=[(4, "exploration"), (4, "resolution")],
        cadence_points=[(4, CadenceType.DECEPTIVE), (8, CadenceType.PLAGAL)],
        energy_curve=[0.4, 0.45, 0.5, 0.55, 0.5, 0.45, 0.4, 0.35],
    ),
}

# Section type to preferred phrase templates
SECTION_PHRASE_PREFS: Dict[str, List[str]] = {
    "intro": ["sentence_4", "call_response_4"],
    "buildup": ["build_8", "sentence_8"],
    "breakdown": ["breakdown_8", "period_8"],
    "drop": ["sentence_8", "call_response_4", "release_4"],
    "break": ["call_response_4", "sentence_4"],
    "outro": ["breakdown_8", "sentence_4"],
}


# =============================================================================
# CONTOUR PLANNER
# =============================================================================

class ContourPlanner:
    """
    Plans melodic contour for phrases.

    Determines:
    - Overall shape (arch, wave, ascending, etc.)
    - Climax placement
    - Register boundaries
    - Breathing points (rests, long notes)
    """

    # Contour shape functions: progress (0-1) → relative pitch (0-1)
    CONTOUR_FUNCTIONS: Dict[ContourShape, Callable[[float], float]] = {
        ContourShape.ARCH: lambda p: math.sin(p * math.pi),
        ContourShape.INVERSE_ARCH: lambda p: 1 - math.sin(p * math.pi),
        ContourShape.ASCENDING: lambda p: p,
        ContourShape.DESCENDING: lambda p: 1 - p,
        ContourShape.WAVE: lambda p: 0.5 + 0.5 * math.sin(p * math.pi * 2),
        ContourShape.PLATEAU: lambda p: (
            p * 2 if p < 0.25 else
            1.0 if p < 0.75 else
            (1 - p) * 4
        ),
        ContourShape.ZIGZAG: lambda p: abs((p * 4) % 2 - 1),
        ContourShape.STATIC: lambda p: 0.5,
    }

    def __init__(
        self,
        seed: Optional[int] = None,
    ):
        self.rng = random.Random(seed)

    def select_contour(
        self,
        section_type: str,
        phrase_position: float,  # 0-1 within section
        energy: float,
    ) -> ContourShape:
        """Select appropriate contour shape based on context."""

        # Section-based preferences
        section_contours = {
            "intro": [ContourShape.ASCENDING, ContourShape.WAVE],
            "buildup": [ContourShape.ASCENDING, ContourShape.ARCH],
            "breakdown": [ContourShape.DESCENDING, ContourShape.INVERSE_ARCH, ContourShape.WAVE],
            "drop": [ContourShape.ARCH, ContourShape.ZIGZAG, ContourShape.PLATEAU],
            "break": [ContourShape.WAVE, ContourShape.STATIC],
            "outro": [ContourShape.DESCENDING, ContourShape.INVERSE_ARCH],
        }

        candidates = section_contours.get(section_type, [ContourShape.ARCH])

        # Adjust based on phrase position
        if phrase_position > 0.8:  # End of section
            if ContourShape.DESCENDING in candidates:
                return ContourShape.DESCENDING
        elif phrase_position < 0.2:  # Start of section
            if ContourShape.ASCENDING in candidates:
                return ContourShape.ASCENDING

        return self.rng.choice(candidates)

    def get_target_pitch(
        self,
        progress: float,
        contour: ContourShape,
        register_low: int,
        register_high: int,
    ) -> int:
        """Get target MIDI pitch for a given progress through phrase."""
        contour_fn = self.CONTOUR_FUNCTIONS.get(contour, lambda p: 0.5)
        normalized = contour_fn(progress)

        # Map 0-1 to register range
        pitch = register_low + normalized * (register_high - register_low)
        return int(round(pitch))

    def find_climax_position(
        self,
        contour: ContourShape,
        phrase_duration_beats: float,
        energy_curve: Optional[List[float]] = None,
    ) -> float:
        """Find the beat position of the melodic climax."""

        # Default climax positions based on contour
        default_positions = {
            ContourShape.ARCH: 0.5,           # Middle
            ContourShape.INVERSE_ARCH: 0.0,   # Start (highest) or end
            ContourShape.ASCENDING: 0.9,      # Near end
            ContourShape.DESCENDING: 0.1,     # Near start
            ContourShape.WAVE: 0.25,          # First peak
            ContourShape.PLATEAU: 0.5,        # Middle of plateau
            ContourShape.ZIGZAG: 0.5,         # Various peaks
            ContourShape.STATIC: 0.5,         # No real climax
        }

        climax_progress = default_positions.get(contour, 0.5)

        # Adjust based on energy curve if provided
        if energy_curve:
            max_energy_idx = energy_curve.index(max(energy_curve))
            climax_progress = (max_energy_idx + 0.5) / len(energy_curve)

        return climax_progress * phrase_duration_beats

    def plan_breathing_points(
        self,
        phrase_duration_beats: float,
        density: float = 0.7,  # 0-1, higher = more notes, fewer rests
    ) -> List[Tuple[float, float]]:
        """
        Plan breathing points (rests) within a phrase.

        Returns list of (start_beat, duration) for rest areas.
        """
        breathing_points = []

        # Less density = more breathing
        rest_probability = 1 - density

        # Check at each bar boundary
        beats_per_bar = 4
        num_bars = int(phrase_duration_beats / beats_per_bar)

        for bar in range(num_bars):
            bar_start = bar * beats_per_bar

            # More likely to breathe at phrase midpoints
            is_midpoint = bar == num_bars // 2 or bar == num_bars - 1

            if is_midpoint or self.rng.random() < rest_probability:
                # Place a rest somewhere in the last beat of the bar
                rest_start = bar_start + 3 + self.rng.random() * 0.5
                rest_duration = 0.25 + self.rng.random() * 0.5

                # Don't extend past phrase
                if rest_start + rest_duration <= phrase_duration_beats:
                    breathing_points.append((rest_start, rest_duration))

        return breathing_points

    def calculate_register_envelope(
        self,
        base_low: int,
        base_high: int,
        energy: float,
        section_type: str,
    ) -> Tuple[int, int]:
        """
        Calculate the actual register to use based on energy and section.

        Higher energy → higher register and wider range.
        Breakdowns → lower register.
        """
        range_size = base_high - base_low
        center = (base_low + base_high) // 2

        # Energy affects range size
        actual_range = int(range_size * (0.5 + 0.5 * energy))

        # Section affects center
        section_offsets = {
            "intro": -3,
            "buildup": 0,
            "breakdown": -5,
            "drop": 3,
            "break": 0,
            "outro": -3,
        }
        offset = section_offsets.get(section_type, 0)
        center += offset

        return (center - actual_range // 2, center + actual_range // 2)


# =============================================================================
# CADENCE PLANNER
# =============================================================================

class CadencePlanner:
    """
    Plans cadences (phrase endings) for proper tension and resolution.
    """

    # Cadence characteristics
    CADENCE_INFO: Dict[CadenceType, Dict] = {
        CadenceType.AUTHENTIC: {
            "resolution": "strong",
            "target_degree": 0,      # Resolve to root
            "approach_degrees": [4, 6, 7],  # V-I common approach
            "duration_factor": 1.5,  # Hold the resolution
        },
        CadenceType.HALF: {
            "resolution": "open",
            "target_degree": 4,      # End on 5th scale degree (V)
            "approach_degrees": [2, 3],
            "duration_factor": 1.0,
        },
        CadenceType.PLAGAL: {
            "resolution": "gentle",
            "target_degree": 0,      # IV-I
            "approach_degrees": [3, 5],
            "duration_factor": 2.0,  # Very held
        },
        CadenceType.DECEPTIVE: {
            "resolution": "surprise",
            "target_degree": 5,      # V-vi (to 6th degree)
            "approach_degrees": [4, 6, 7],
            "duration_factor": 1.2,
        },
        CadenceType.PHRYGIAN: {
            "resolution": "dark",
            "target_degree": 4,      # iv6-V
            "approach_degrees": [3, 5],
            "duration_factor": 1.3,
        },
    }

    def get_cadence_target(
        self,
        cadence_type: CadenceType,
    ) -> int:
        """Get the scale degree to end on for this cadence type."""
        return self.CADENCE_INFO[cadence_type]["target_degree"]

    def get_approach_degrees(
        self,
        cadence_type: CadenceType,
    ) -> List[int]:
        """Get good scale degrees to approach the cadence from."""
        return self.CADENCE_INFO[cadence_type]["approach_degrees"]

    def get_duration_factor(
        self,
        cadence_type: CadenceType,
    ) -> float:
        """Get the duration multiplier for the final note."""
        return self.CADENCE_INFO[cadence_type]["duration_factor"]

    def select_cadence_for_context(
        self,
        phrase_type: PhraseType,
        is_final_phrase: bool,
        energy: float,
    ) -> CadenceType:
        """Select appropriate cadence type for context."""

        if is_final_phrase:
            # Final phrases should resolve strongly
            return CadenceType.AUTHENTIC

        if phrase_type == PhraseType.ANTECEDENT:
            # Questions end open
            return CadenceType.HALF

        if phrase_type == PhraseType.CONTINUATION:
            # Building tension
            if energy > 0.7:
                return CadenceType.HALF
            else:
                return CadenceType.DECEPTIVE

        # Default to authentic
        return CadenceType.AUTHENTIC


# =============================================================================
# PHRASE BUILDER
# =============================================================================

@dataclass
class PhrasePlan:
    """Complete plan for a phrase."""
    template: PhraseTemplate
    contour: ContourShape
    register_low: int
    register_high: int
    climax_beat: float
    climax_pitch: int
    breathing_points: List[Tuple[float, float]]
    cadence_type: CadenceType
    cadence_approach_degrees: List[int]
    cadence_target_degree: int
    energy_curve: List[float]


class PhraseBuilder:
    """
    Main phrase building engine.

    Combines:
    - Phrase structure templates
    - Contour planning
    - Cadence planning
    - Register management
    """

    def __init__(
        self,
        seed: Optional[int] = None,
    ):
        self.rng = random.Random(seed)
        self.contour_planner = ContourPlanner(seed)
        self.cadence_planner = CadencePlanner()

    def select_template(
        self,
        section_type: str,
        available_bars: int,
        energy: float,
    ) -> PhraseTemplate:
        """Select appropriate phrase template for context."""

        # Get preferred templates for section
        preferred = SECTION_PHRASE_PREFS.get(section_type, ["sentence_4"])

        # Filter by available bars
        valid_templates = [
            PHRASE_TEMPLATES[name]
            for name in preferred
            if name in PHRASE_TEMPLATES and PHRASE_TEMPLATES[name].total_bars <= available_bars
        ]

        if not valid_templates:
            # Fall back to any template that fits
            valid_templates = [
                t for t in PHRASE_TEMPLATES.values()
                if t.total_bars <= available_bars
            ]

        if not valid_templates:
            # Last resort: create a simple template
            return PhraseTemplate(
                name="simple",
                total_bars=available_bars,
                segments=[(available_bars, "simple")],
                cadence_points=[(available_bars, CadenceType.AUTHENTIC)],
                energy_curve=[0.7] * available_bars,
            )

        # Weight selection by energy
        # Higher energy → prefer more dynamic templates
        if energy > 0.7:
            # Prefer call-response, build
            weighted = [t for t in valid_templates if "call" in t.name or "build" in t.name]
            if weighted:
                return self.rng.choice(weighted)

        return self.rng.choice(valid_templates)

    def build_phrase_plan(
        self,
        section_type: str,
        start_beat: float,
        available_bars: int,
        energy: float,
        phrase_position: float,  # 0-1 within section
        is_final_phrase: bool,
        register: Tuple[int, int] = (60, 84),
    ) -> PhrasePlan:
        """
        Build a complete phrase plan.

        Args:
            section_type: Type of section (drop, breakdown, etc.)
            start_beat: Starting beat position
            available_bars: How many bars available for this phrase
            energy: Energy level 0-1
            phrase_position: Position within section (0-1)
            is_final_phrase: Whether this is the last phrase in section
            register: (low, high) MIDI note range

        Returns:
            Complete PhrasePlan for melody generation
        """
        # Select template
        template = self.select_template(section_type, available_bars, energy)

        # Calculate actual register based on context
        reg_low, reg_high = self.contour_planner.calculate_register_envelope(
            register[0], register[1], energy, section_type
        )

        # Select contour
        contour = self.contour_planner.select_contour(
            section_type, phrase_position, energy
        )

        # Find climax
        phrase_duration = template.total_bars * 4  # beats
        climax_beat = self.contour_planner.find_climax_position(
            contour, phrase_duration, template.energy_curve
        )
        climax_pitch = self.contour_planner.get_target_pitch(
            climax_beat / phrase_duration, contour, reg_low, reg_high
        )

        # Plan breathing
        density = 0.5 + 0.4 * energy  # Higher energy = fewer rests
        breathing = self.contour_planner.plan_breathing_points(phrase_duration, density)

        # Select cadence
        # Determine phrase type from template
        if "antecedent" in template.segments[-1][1]:
            phrase_type = PhraseType.ANTECEDENT
        elif "consequent" in template.segments[-1][1]:
            phrase_type = PhraseType.CONSEQUENT
        else:
            phrase_type = PhraseType.SENTENCE

        cadence = self.cadence_planner.select_cadence_for_context(
            phrase_type, is_final_phrase, energy
        )

        return PhrasePlan(
            template=template,
            contour=contour,
            register_low=reg_low,
            register_high=reg_high,
            climax_beat=start_beat + climax_beat,
            climax_pitch=climax_pitch,
            breathing_points=[(start_beat + b, d) for b, d in breathing],
            cadence_type=cadence,
            cadence_approach_degrees=self.cadence_planner.get_approach_degrees(cadence),
            cadence_target_degree=self.cadence_planner.get_cadence_target(cadence),
            energy_curve=template.energy_curve,
        )

    def build_section_phrases(
        self,
        section_type: str,
        start_beat: float,
        total_bars: int,
        base_energy: float,
        register: Tuple[int, int] = (60, 84),
    ) -> List[PhrasePlan]:
        """
        Build phrase plans for an entire section.

        Automatically divides the section into appropriate phrases
        with coherent structure.
        """
        phrases = []
        current_beat = start_beat
        remaining_bars = total_bars
        phrase_count = 0

        while remaining_bars > 0:
            phrase_position = 1 - (remaining_bars / total_bars)
            is_final = remaining_bars <= 8  # Last phrase(s)

            # Determine phrase length
            # Prefer 4 or 8 bar phrases
            if remaining_bars >= 8:
                phrase_bars = self.rng.choice([4, 8])
            elif remaining_bars >= 4:
                phrase_bars = 4
            else:
                phrase_bars = remaining_bars

            # Adjust energy through section
            if section_type == "buildup":
                phrase_energy = base_energy * (0.7 + 0.3 * phrase_position)
            elif section_type == "breakdown":
                phrase_energy = base_energy * (1.0 - 0.3 * phrase_position)
            elif section_type == "drop":
                # High energy throughout, slight dip in middle
                mid_distance = abs(phrase_position - 0.5)
                phrase_energy = base_energy * (0.85 + 0.15 * mid_distance * 2)
            else:
                phrase_energy = base_energy

            # Build phrase plan
            plan = self.build_phrase_plan(
                section_type=section_type,
                start_beat=current_beat,
                available_bars=phrase_bars,
                energy=phrase_energy,
                phrase_position=phrase_position,
                is_final_phrase=is_final and remaining_bars <= phrase_bars,
                register=register,
            )
            phrases.append(plan)

            current_beat += phrase_bars * 4
            remaining_bars -= phrase_bars
            phrase_count += 1

        return phrases


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_phrase_builder(seed: Optional[int] = None) -> PhraseBuilder:
    """Create a phrase builder instance."""
    return PhraseBuilder(seed=seed)


def plan_section_phrases(
    section_type: str,
    total_bars: int,
    energy: float = 0.8,
    start_beat: float = 0.0,
) -> List[PhrasePlan]:
    """Convenience function to plan phrases for a section."""
    builder = PhraseBuilder()
    return builder.build_section_phrases(
        section_type=section_type,
        start_beat=start_beat,
        total_bars=total_bars,
        base_energy=energy,
    )


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate phrase builder capabilities."""
    print("Phrase Builder Demo")
    print("=" * 50)

    builder = PhraseBuilder(seed=42)

    # Build phrases for a drop section
    print("\n1. Plan 16-bar DROP section phrases:")
    drop_phrases = builder.build_section_phrases(
        section_type="drop",
        start_beat=0,
        total_bars=16,
        base_energy=0.9,
    )

    for i, phrase in enumerate(drop_phrases):
        print(f"\n   Phrase {i+1}:")
        print(f"     Template: {phrase.template.name}")
        print(f"     Contour: {phrase.contour.name}")
        print(f"     Register: {phrase.register_low}-{phrase.register_high}")
        print(f"     Climax: beat {phrase.climax_beat:.1f}, pitch {phrase.climax_pitch}")
        print(f"     Cadence: {phrase.cadence_type.name}")
        print(f"     Breathing points: {len(phrase.breathing_points)}")

    # Build phrases for breakdown
    print("\n\n2. Plan 8-bar BREAKDOWN section phrases:")
    breakdown_phrases = builder.build_section_phrases(
        section_type="breakdown",
        start_beat=64,
        total_bars=8,
        base_energy=0.5,
    )

    for i, phrase in enumerate(breakdown_phrases):
        print(f"\n   Phrase {i+1}:")
        print(f"     Template: {phrase.template.name}")
        print(f"     Contour: {phrase.contour.name}")
        print(f"     Register: {phrase.register_low}-{phrase.register_high}")
        print(f"     Energy curve: {[f'{e:.2f}' for e in phrase.energy_curve]}")

    # Test contour planner directly
    print("\n\n3. Contour shapes at different progress points:")
    contour_planner = ContourPlanner()
    for contour in [ContourShape.ARCH, ContourShape.WAVE, ContourShape.ASCENDING]:
        print(f"\n   {contour.name}:")
        for progress in [0.0, 0.25, 0.5, 0.75, 1.0]:
            pitch = contour_planner.get_target_pitch(progress, contour, 60, 84)
            print(f"     {progress:.2f} → pitch {pitch}")

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    demo()
