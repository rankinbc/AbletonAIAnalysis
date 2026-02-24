"""
Motif Engine

Production-grade motivic development system:
- Seed generation with genre-appropriate characteristics
- Full transformation library (sequence, inversion, retrograde, etc.)
- Motif memory for coherence across sections
- Intelligent motif selection based on energy/section
- Variation generation that maintains musical identity
"""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum, auto

from .models import (
    Motif, MotifInterval, MotifTransform, NoteEvent,
    Pitch, PitchClass, ArticulationType, ContourShape,
    TensionLevel
)


# =============================================================================
# MOTIF SEED LIBRARY
# =============================================================================

# Pre-defined motif seeds organized by genre and character
# These are the "DNA" from which melodies are built

TRANCE_MOTIFS: Dict[str, List[MotifInterval]] = {
    # Uplifting anthem motifs
    "anthem_rise": [
        MotifInterval(0, 0.5, 0.9),       # Root
        MotifInterval(2, 0.5, 0.85),      # Up a step
        MotifInterval(2, 1.0, 1.0),       # Up another step (arrives on 3rd)
    ],
    "anthem_fall": [
        MotifInterval(0, 0.5, 1.0),       # Start high (5th)
        MotifInterval(-2, 0.5, 0.9),      # Down a step
        MotifInterval(-1, 1.0, 0.85),     # Down a half step
    ],
    "anthem_arch": [
        MotifInterval(0, 0.5, 0.85),
        MotifInterval(2, 0.25, 0.9),
        MotifInterval(2, 0.25, 1.0),      # Peak
        MotifInterval(-2, 0.5, 0.9),
        MotifInterval(-2, 0.5, 0.85),
    ],

    # Driving motifs (for drops)
    "driving_pulse": [
        MotifInterval(0, 0.25, 1.0, ArticulationType.STACCATO),
        MotifInterval(0, 0.25, 0.7, ArticulationType.STACCATO),
        MotifInterval(0, 0.25, 0.85, ArticulationType.STACCATO),
        MotifInterval(2, 0.25, 0.9, ArticulationType.STACCATO),
    ],
    "driving_leap": [
        MotifInterval(0, 0.25, 1.0),
        MotifInterval(7, 0.25, 0.9),      # Perfect 5th up
        MotifInterval(-5, 0.25, 0.85),    # Down
        MotifInterval(-2, 0.25, 0.8),
    ],

    # Emotional motifs (for breakdowns)
    "emotional_sigh": [
        MotifInterval(0, 1.0, 0.8),
        MotifInterval(-1, 1.0, 0.7),      # Half step down (sigh)
        MotifInterval(-2, 2.0, 0.6),      # Continue down, held
    ],
    "emotional_yearning": [
        MotifInterval(0, 0.5, 0.75),
        MotifInterval(5, 1.5, 0.9),       # Leap up (yearning)
        MotifInterval(-2, 1.0, 0.8),      # Step back down
    ],
    "emotional_hold": [
        MotifInterval(0, 2.0, 0.85),      # Long held note
        MotifInterval(2, 2.0, 0.8),       # Step up, hold
    ],

    # Hook motifs
    "hook_question": [
        MotifInterval(0, 0.5, 0.9),
        MotifInterval(4, 0.5, 1.0),       # Major 3rd up
        MotifInterval(3, 0.5, 0.95),      # Minor 3rd up (to 5th)
        MotifInterval(2, 0.5, 0.85),      # Step up (question)
    ],
    "hook_answer": [
        MotifInterval(0, 0.5, 0.85),
        MotifInterval(-2, 0.5, 0.9),
        MotifInterval(-2, 0.5, 0.95),
        MotifInterval(-1, 1.0, 1.0),      # Resolve down
    ],
}

PROGRESSIVE_MOTIFS: Dict[str, List[MotifInterval]] = {
    "hypnotic_loop": [
        MotifInterval(0, 0.5, 0.8),
        MotifInterval(2, 0.5, 0.75),
        MotifInterval(-2, 0.5, 0.8),
        MotifInterval(0, 0.5, 0.7),
    ],
    "minimal_cell": [
        MotifInterval(0, 0.25, 0.85),
        MotifInterval(0, 0.25, 0.6),
        MotifInterval(2, 0.5, 0.9),
    ],
    "evolving_figure": [
        MotifInterval(0, 0.75, 0.8),
        MotifInterval(3, 0.25, 0.9),
        MotifInterval(-1, 0.5, 0.85),
        MotifInterval(2, 0.5, 0.8),
    ],
}

TECHNO_MOTIFS: Dict[str, List[MotifInterval]] = {
    "stab": [
        MotifInterval(0, 0.125, 1.0, ArticulationType.STACCATO),
        MotifInterval(0, 0.375, 0.0),  # Rest (velocity 0)
        MotifInterval(0, 0.125, 0.9, ArticulationType.STACCATO),
        MotifInterval(0, 0.375, 0.0),
    ],
    "acid_bend": [
        MotifInterval(0, 0.5, 1.0),
        MotifInterval(1, 0.25, 0.9),     # Chromatic
        MotifInterval(-1, 0.25, 0.85),
        MotifInterval(0, 0.5, 0.8),
    ],
}

# Genre to motif library mapping
GENRE_MOTIFS: Dict[str, Dict[str, List[MotifInterval]]] = {
    "trance": TRANCE_MOTIFS,
    "uplifting": TRANCE_MOTIFS,
    "progressive": PROGRESSIVE_MOTIFS,
    "techno": TECHNO_MOTIFS,
}

# Section type to preferred motif patterns
SECTION_MOTIF_PREFS: Dict[str, List[str]] = {
    "intro": ["hypnotic_loop", "minimal_cell", "emotional_hold"],
    "buildup": ["driving_pulse", "hook_question", "anthem_rise"],
    "breakdown": ["emotional_sigh", "emotional_yearning", "emotional_hold"],
    "drop": ["anthem_rise", "anthem_arch", "driving_leap", "hook_answer"],
    "break": ["evolving_figure", "hypnotic_loop"],
    "outro": ["emotional_sigh", "anthem_fall"],
}


# =============================================================================
# MOTIF TRANSFORMER
# =============================================================================

class MotifTransformer:
    """
    Applies musical transformations to motifs.

    Transformations preserve musical identity while creating variation.
    """

    @staticmethod
    def sequence(
        motif: Motif,
        semitones: int = 2,  # Default: sequence up a step
        new_id: Optional[str] = None,
    ) -> Motif:
        """
        Sequence: transpose the entire motif.

        Maintains exact rhythm and interval relationships,
        just starts on a different pitch.
        """
        # Intervals stay the same - sequencing affects starting pitch
        # We just note the transformation for tracking
        return Motif(
            id=new_id or f"{motif.id}_seq{semitones:+d}",
            intervals=motif.intervals.copy(),
            genre_tags=motif.genre_tags,
            energy_range=motif.energy_range,
            section_types=motif.section_types,
        )

    @staticmethod
    def inversion(
        motif: Motif,
        new_id: Optional[str] = None,
    ) -> Motif:
        """
        Inversion: flip all intervals.

        Ascending becomes descending, vice versa.
        Rhythms preserved.
        """
        inverted = []
        for interval in motif.intervals:
            inverted.append(MotifInterval(
                interval=-interval.interval,
                duration_beats=interval.duration_beats,
                velocity_factor=interval.velocity_factor,
                articulation=interval.articulation,
            ))

        return Motif(
            id=new_id or f"{motif.id}_inv",
            intervals=inverted,
            genre_tags=motif.genre_tags,
            energy_range=motif.energy_range,
            section_types=motif.section_types,
        )

    @staticmethod
    def retrograde(
        motif: Motif,
        new_id: Optional[str] = None,
    ) -> Motif:
        """
        Retrograde: reverse the order of notes.

        Intervals are recalculated for reversed direction.
        """
        if len(motif.intervals) < 2:
            return motif

        # Reverse intervals - need to recalculate
        # If original is [0, +2, +3], we want to play notes in reverse
        # but from the original starting point perspective

        reversed_intervals = []
        original_intervals = list(motif.intervals)

        # First note stays at 0
        reversed_intervals.append(MotifInterval(
            interval=0,
            duration_beats=original_intervals[-1].duration_beats,
            velocity_factor=original_intervals[-1].velocity_factor,
            articulation=original_intervals[-1].articulation,
        ))

        # Subsequent notes get negated intervals in reverse
        for i in range(len(original_intervals) - 2, -1, -1):
            reversed_intervals.append(MotifInterval(
                interval=-original_intervals[i + 1].interval,
                duration_beats=original_intervals[i].duration_beats,
                velocity_factor=original_intervals[i].velocity_factor,
                articulation=original_intervals[i].articulation,
            ))

        return Motif(
            id=new_id or f"{motif.id}_ret",
            intervals=reversed_intervals,
            genre_tags=motif.genre_tags,
            energy_range=motif.energy_range,
            section_types=motif.section_types,
        )

    @staticmethod
    def retrograde_inversion(
        motif: Motif,
        new_id: Optional[str] = None,
    ) -> Motif:
        """Retrograde + inversion combined."""
        ret = MotifTransformer.retrograde(motif)
        return MotifTransformer.inversion(ret, new_id or f"{motif.id}_retinv")

    @staticmethod
    def augmentation(
        motif: Motif,
        factor: float = 2.0,
        new_id: Optional[str] = None,
    ) -> Motif:
        """
        Augmentation: stretch durations.

        Notes last longer, motif takes more time.
        """
        augmented = []
        for interval in motif.intervals:
            augmented.append(MotifInterval(
                interval=interval.interval,
                duration_beats=interval.duration_beats * factor,
                velocity_factor=interval.velocity_factor,
                articulation=interval.articulation,
            ))

        return Motif(
            id=new_id or f"{motif.id}_aug",
            intervals=augmented,
            genre_tags=motif.genre_tags,
            energy_range=motif.energy_range,
            section_types=motif.section_types,
        )

    @staticmethod
    def diminution(
        motif: Motif,
        factor: float = 0.5,
        new_id: Optional[str] = None,
    ) -> Motif:
        """
        Diminution: compress durations.

        Notes are shorter, motif is faster.
        """
        return MotifTransformer.augmentation(motif, factor, new_id or f"{motif.id}_dim")

    @staticmethod
    def fragmentation(
        motif: Motif,
        start_idx: int = 0,
        length: int = 2,
        new_id: Optional[str] = None,
    ) -> Motif:
        """
        Fragmentation: extract a portion of the motif.

        Common technique: use just the "head" (first few notes)
        or the "tail" (last few notes).
        """
        fragment = motif.intervals[start_idx:start_idx + length]
        if not fragment:
            fragment = motif.intervals[:2] if len(motif.intervals) >= 2 else motif.intervals

        # Normalize first interval to 0
        normalized = [MotifInterval(
            interval=0,
            duration_beats=fragment[0].duration_beats,
            velocity_factor=fragment[0].velocity_factor,
            articulation=fragment[0].articulation,
        )]
        normalized.extend(fragment[1:])

        return Motif(
            id=new_id or f"{motif.id}_frag",
            intervals=normalized,
            genre_tags=motif.genre_tags,
            energy_range=motif.energy_range,
            section_types=motif.section_types,
        )

    @staticmethod
    def intervallic_expansion(
        motif: Motif,
        factor: float = 1.5,
        new_id: Optional[str] = None,
    ) -> Motif:
        """
        Intervallic expansion: widen all intervals.

        A 2nd becomes a 3rd, a 3rd becomes a 4th/5th, etc.
        Creates more dramatic contour.
        """
        expanded = []
        for interval in motif.intervals:
            new_interval = int(interval.interval * factor)
            expanded.append(MotifInterval(
                interval=new_interval,
                duration_beats=interval.duration_beats,
                velocity_factor=interval.velocity_factor,
                articulation=interval.articulation,
            ))

        return Motif(
            id=new_id or f"{motif.id}_exp",
            intervals=expanded,
            genre_tags=motif.genre_tags,
            energy_range=motif.energy_range,
            section_types=motif.section_types,
        )

    @staticmethod
    def intervallic_compression(
        motif: Motif,
        factor: float = 0.5,
        new_id: Optional[str] = None,
    ) -> Motif:
        """
        Intervallic compression: narrow all intervals.

        Creates more step-wise, lyrical motion.
        """
        compressed = []
        for interval in motif.intervals:
            new_interval = int(interval.interval * factor)
            # Preserve direction even if compressed to 0
            if interval.interval != 0 and new_interval == 0:
                new_interval = 1 if interval.interval > 0 else -1
            compressed.append(MotifInterval(
                interval=new_interval,
                duration_beats=interval.duration_beats,
                velocity_factor=interval.velocity_factor,
                articulation=interval.articulation,
            ))

        return Motif(
            id=new_id or f"{motif.id}_comp",
            intervals=compressed,
            genre_tags=motif.genre_tags,
            energy_range=motif.energy_range,
            section_types=motif.section_types,
        )

    @staticmethod
    def rhythmic_displacement(
        motif: Motif,
        offset_beats: float = 0.5,
        new_id: Optional[str] = None,
    ) -> Motif:
        """
        Rhythmic displacement: shift where motif starts in the bar.

        The intervals/durations stay the same, but when rendered
        the start_beat should be offset.
        """
        # This doesn't change the motif itself, just how it's placed
        # We mark it for the caller to handle
        return Motif(
            id=new_id or f"{motif.id}_disp{offset_beats}",
            intervals=motif.intervals.copy(),
            genre_tags=motif.genre_tags,
            energy_range=motif.energy_range,
            section_types=motif.section_types,
        )

    @classmethod
    def apply(
        cls,
        motif: Motif,
        transform: MotifTransform,
        **kwargs,
    ) -> Motif:
        """Apply a transformation by enum type."""
        transform_map: Dict[MotifTransform, Callable] = {
            MotifTransform.ORIGINAL: lambda m, **kw: m,
            MotifTransform.SEQUENCE: cls.sequence,
            MotifTransform.INVERSION: cls.inversion,
            MotifTransform.RETROGRADE: cls.retrograde,
            MotifTransform.RETROGRADE_INVERSION: cls.retrograde_inversion,
            MotifTransform.AUGMENTATION: cls.augmentation,
            MotifTransform.DIMINUTION: cls.diminution,
            MotifTransform.FRAGMENTATION: cls.fragmentation,
            MotifTransform.INTERVALLIC_EXPANSION: cls.intervallic_expansion,
            MotifTransform.INTERVALLIC_COMPRESSION: cls.intervallic_compression,
            MotifTransform.RHYTHMIC_DISPLACEMENT: cls.rhythmic_displacement,
        }

        transform_fn = transform_map.get(transform, lambda m, **kw: m)
        return transform_fn(motif, **kwargs)


# =============================================================================
# MOTIF ENGINE
# =============================================================================

@dataclass
class MotifMemory:
    """Tracks motifs used in the current piece for coherence."""
    primary_motif: Optional[Motif] = None
    secondary_motif: Optional[Motif] = None
    motifs_by_section: Dict[str, List[Motif]] = field(default_factory=dict)
    transformation_history: List[Tuple[str, MotifTransform]] = field(default_factory=list)

    def record_usage(self, motif: Motif, section: str, transform: MotifTransform = MotifTransform.ORIGINAL):
        """Record that a motif was used in a section."""
        if section not in self.motifs_by_section:
            self.motifs_by_section[section] = []
        self.motifs_by_section[section].append(motif)
        self.transformation_history.append((motif.id, transform))

    def get_recent_transforms(self, n: int = 3) -> List[MotifTransform]:
        """Get the last N transformations used."""
        return [t for _, t in self.transformation_history[-n:]]


class MotifEngine:
    """
    Main motif generation and development engine.

    Responsibilities:
    - Generate genre-appropriate motif seeds
    - Apply intelligent transformations
    - Track motif usage for coherence
    - Select motifs based on energy/section
    - Create variation while maintaining identity
    """

    def __init__(
        self,
        genre: str = "trance",
        seed: Optional[int] = None,
    ):
        self.genre = genre.lower()
        self.rng = random.Random(seed)
        self.transformer = MotifTransformer()
        self.memory = MotifMemory()

        # Load genre-specific motif library
        self.motif_library = GENRE_MOTIFS.get(self.genre, TRANCE_MOTIFS)

    def _create_motif(
        self,
        name: str,
        intervals: List[MotifInterval],
        energy_range: Tuple[float, float] = (0.0, 1.0),
        section_types: Optional[List[str]] = None,
    ) -> Motif:
        """Create a Motif object from interval list."""
        return Motif(
            id=name,
            intervals=intervals,
            genre_tags=[self.genre],
            energy_range=energy_range,
            section_types=section_types or [],
        )

    def get_seed_motif(
        self,
        section_type: str = "drop",
        energy: float = 0.8,
        character: Optional[str] = None,
    ) -> Motif:
        """
        Get an appropriate seed motif for the context.

        Args:
            section_type: Type of section (intro, buildup, breakdown, drop, etc.)
            energy: Energy level 0-1
            character: Optional specific character (e.g., "anthem", "emotional")

        Returns:
            A suitable Motif to use as basis for development
        """
        candidates = []

        # If specific character requested, look for matching motifs
        if character:
            for name, intervals in self.motif_library.items():
                if character.lower() in name.lower():
                    candidates.append((name, intervals))

        # Otherwise use section-based preferences
        if not candidates:
            preferred_names = SECTION_MOTIF_PREFS.get(section_type, ["anthem_rise"])
            for name in preferred_names:
                if name in self.motif_library:
                    candidates.append((name, self.motif_library[name]))

        # Fallback to any motif in library
        if not candidates:
            candidates = list(self.motif_library.items())

        # Select based on energy
        # Higher energy → prefer motifs with more movement/shorter notes
        if energy > 0.7:
            # Prefer driving, rhythmic motifs
            driving = [(n, i) for n, i in candidates if "driving" in n or "hook" in n]
            if driving:
                candidates = driving
        elif energy < 0.4:
            # Prefer emotional, sustained motifs
            emotional = [(n, i) for n, i in candidates if "emotional" in n or "hold" in n]
            if emotional:
                candidates = emotional

        # Random selection from candidates
        name, intervals = self.rng.choice(candidates)

        motif = self._create_motif(
            name=name,
            intervals=intervals,
            energy_range=(max(0, energy - 0.3), min(1, energy + 0.3)),
            section_types=[section_type],
        )

        # Set as primary if none exists
        if self.memory.primary_motif is None:
            self.memory.primary_motif = motif

        return motif

    def generate_random_motif(
        self,
        length: int = 4,
        energy: float = 0.7,
        contour: ContourShape = ContourShape.ARCH,
    ) -> Motif:
        """
        Generate a completely new random motif.

        Uses musical rules to create coherent melodic cells:
        - Contour shapes guide overall direction
        - Step-wise motion preferred with occasional leaps
        - Rhythmic patterns based on energy
        """
        intervals = []

        # Determine rhythmic density based on energy
        if energy > 0.7:
            base_durations = [0.25, 0.25, 0.5, 0.25]
        elif energy > 0.4:
            base_durations = [0.5, 0.5, 0.75, 1.0]
        else:
            base_durations = [1.0, 1.5, 2.0, 1.0]

        # Generate notes following contour
        for i in range(length):
            progress = i / (length - 1) if length > 1 else 0

            # Determine interval based on contour
            if contour == ContourShape.ARCH:
                if progress < 0.5:
                    preferred_direction = 1  # Ascending
                else:
                    preferred_direction = -1  # Descending
            elif contour == ContourShape.ASCENDING:
                preferred_direction = 1
            elif contour == ContourShape.DESCENDING:
                preferred_direction = -1
            elif contour == ContourShape.WAVE:
                preferred_direction = 1 if (i % 2 == 0) else -1
            else:
                preferred_direction = self.rng.choice([-1, 1])

            # Interval size (prefer steps, occasional leaps)
            interval_weights = [
                (1, 4),   # Step - most common
                (2, 3),   # Whole step
                (3, 2),   # Minor 3rd
                (4, 1),   # Major 3rd
                (5, 1),   # Perfect 4th
                (7, 0.5), # Perfect 5th (rare)
            ]
            intervals_list, weights = zip(*interval_weights)
            size = self.rng.choices(intervals_list, weights=weights)[0]

            if i == 0:
                interval_value = 0  # First note
            else:
                interval_value = size * preferred_direction
                # Occasionally go opposite direction for interest
                if self.rng.random() < 0.2:
                    interval_value = -interval_value

            # Duration
            duration = self.rng.choice(base_durations)

            # Velocity emphasis on first and midpoint
            if i == 0:
                vel_factor = 1.0
            elif i == length // 2:
                vel_factor = 0.95
            else:
                vel_factor = 0.8 + self.rng.random() * 0.15

            intervals.append(MotifInterval(
                interval=interval_value,
                duration_beats=duration,
                velocity_factor=vel_factor,
            ))

        return Motif(
            id=f"random_{self.rng.randint(1000, 9999)}",
            intervals=intervals,
            genre_tags=[self.genre],
            energy_range=(max(0, energy - 0.2), min(1, energy + 0.2)),
        )

    def develop_motif(
        self,
        motif: Motif,
        development_length: int = 4,
        transforms: Optional[List[MotifTransform]] = None,
    ) -> List[Motif]:
        """
        Develop a motif through a sequence of transformations.

        Creates a musically coherent series of related motifs.

        Args:
            motif: The seed motif to develop
            development_length: Number of variations to create
            transforms: Optional specific transforms to use

        Returns:
            List of transformed motifs including original
        """
        developed = [motif]

        if transforms is None:
            # Choose intelligent transformation sequence
            # Avoid repeating recent transforms
            recent = set(self.memory.get_recent_transforms())

            all_transforms = [
                MotifTransform.SEQUENCE,
                MotifTransform.INVERSION,
                MotifTransform.RETROGRADE,
                MotifTransform.AUGMENTATION,
                MotifTransform.DIMINUTION,
                MotifTransform.FRAGMENTATION,
                MotifTransform.INTERVALLIC_EXPANSION,
            ]

            available = [t for t in all_transforms if t not in recent]
            if len(available) < development_length:
                available = all_transforms

            transforms = self.rng.sample(available, min(development_length - 1, len(available)))

        # Apply transformations
        current = motif
        for transform in transforms:
            # Add sequence transposition for variety
            kwargs = {}
            if transform == MotifTransform.SEQUENCE:
                # Sequence up a 3rd, 4th, or 5th
                kwargs['semitones'] = self.rng.choice([3, 4, 5, 7])
            elif transform == MotifTransform.FRAGMENTATION:
                kwargs['length'] = min(2, len(current.intervals))

            transformed = self.transformer.apply(current, transform, **kwargs)
            developed.append(transformed)
            self.memory.record_usage(transformed, "development", transform)
            current = transformed

        return developed

    def create_question_answer(
        self,
        question_motif: Optional[Motif] = None,
        energy: float = 0.7,
    ) -> Tuple[Motif, Motif]:
        """
        Create a question-answer motif pair.

        Musical question-answer: first phrase ends "open" (non-tonic),
        second phrase ends "closed" (on tonic).
        """
        if question_motif is None:
            question_motif = self.get_seed_motif(
                section_type="drop",
                energy=energy,
                character="hook_question"
            )

        # Answer is typically inversion or sequence down
        if self.rng.random() < 0.5:
            answer_motif = self.transformer.inversion(question_motif, f"{question_motif.id}_answer")
        else:
            answer_motif = self.transformer.sequence(question_motif, -5, f"{question_motif.id}_answer")

        return question_motif, answer_motif

    def select_transform_for_section(
        self,
        from_section: str,
        to_section: str,
    ) -> MotifTransform:
        """
        Select an appropriate transformation when moving between sections.

        E.g., buildup → drop might use diminution (make faster)
        breakdown → buildup might use augmentation first, then diminution
        """
        transitions = {
            ("intro", "buildup"): MotifTransform.SEQUENCE,
            ("buildup", "drop"): MotifTransform.DIMINUTION,
            ("drop", "breakdown"): MotifTransform.AUGMENTATION,
            ("breakdown", "drop"): MotifTransform.DIMINUTION,
            ("breakdown", "buildup"): MotifTransform.SEQUENCE,
        }

        return transitions.get(
            (from_section, to_section),
            self.rng.choice([MotifTransform.SEQUENCE, MotifTransform.INVERSION])
        )

    def get_variation(
        self,
        motif: Motif,
        variation_amount: float = 0.3,
    ) -> Motif:
        """
        Create a subtle variation of a motif.

        For maintaining coherence while avoiding exact repetition.
        Variation amount 0-1 controls how different the result is.
        """
        varied_intervals = []

        for interval in motif.intervals:
            new_interval = interval.interval
            new_duration = interval.duration_beats
            new_velocity = interval.velocity_factor

            # Possibly alter interval
            if self.rng.random() < variation_amount:
                # Small adjustment ±1-2 semitones
                adjustment = self.rng.choice([-2, -1, 1, 2])
                new_interval = interval.interval + adjustment

            # Possibly alter duration
            if self.rng.random() < variation_amount * 0.5:
                # Slight duration change
                factor = self.rng.choice([0.75, 1.0, 1.5])
                new_duration = interval.duration_beats * factor

            # Slight velocity variation
            if self.rng.random() < variation_amount:
                new_velocity = interval.velocity_factor + self.rng.uniform(-0.1, 0.1)
                new_velocity = max(0.5, min(1.0, new_velocity))

            varied_intervals.append(MotifInterval(
                interval=new_interval,
                duration_beats=new_duration,
                velocity_factor=new_velocity,
                articulation=interval.articulation,
            ))

        return Motif(
            id=f"{motif.id}_var",
            intervals=varied_intervals,
            genre_tags=motif.genre_tags,
            energy_range=motif.energy_range,
            section_types=motif.section_types,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_motif_engine(genre: str = "trance", seed: Optional[int] = None) -> MotifEngine:
    """Create a motif engine for a genre."""
    return MotifEngine(genre=genre, seed=seed)


def develop_melody_motifs(
    seed_motif: Motif,
    bars: int = 8,
    phrases_per_bar: float = 0.5,
    engine: Optional[MotifEngine] = None,
) -> List[Motif]:
    """Convenience function to develop motifs for a section."""
    if engine is None:
        engine = MotifEngine()

    num_phrases = max(1, int(bars * phrases_per_bar))
    return engine.develop_motif(seed_motif, development_length=num_phrases)


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate motif engine capabilities."""
    print("Motif Engine Demo")
    print("=" * 50)

    engine = MotifEngine(genre="trance", seed=42)

    # Get a seed motif for drop section
    print("\n1. Get seed motif for DROP section:")
    seed = engine.get_seed_motif(section_type="drop", energy=0.9)
    print(f"   Motif: {seed.id}")
    print(f"   Intervals: {[(i.interval, i.duration_beats) for i in seed.intervals]}")

    # Develop the motif
    print("\n2. Develop motif (4 variations):")
    developed = engine.develop_motif(seed, development_length=4)
    for i, m in enumerate(developed):
        print(f"   {i+1}. {m.id}: {[(iv.interval, iv.duration_beats) for iv in m.intervals]}")

    # Create question-answer pair
    print("\n3. Create question-answer pair:")
    q, a = engine.create_question_answer(energy=0.8)
    print(f"   Question: {q.id}")
    print(f"   Answer: {a.id}")

    # Apply specific transformations
    print("\n4. Apply transformations to seed:")
    transforms = [
        MotifTransform.INVERSION,
        MotifTransform.RETROGRADE,
        MotifTransform.AUGMENTATION,
        MotifTransform.FRAGMENTATION,
    ]
    for t in transforms:
        result = MotifTransformer.apply(seed, t)
        print(f"   {t.name}: {[(i.interval, i.duration_beats) for i in result.intervals]}")

    # Generate random motif
    print("\n5. Generate random motif (arch contour):")
    random_motif = engine.generate_random_motif(length=4, energy=0.6, contour=ContourShape.ARCH)
    print(f"   {random_motif.id}: {[(i.interval, i.duration_beats) for i in random_motif.intervals]}")

    # Get variation
    print("\n6. Create subtle variation:")
    variation = engine.get_variation(seed, variation_amount=0.3)
    print(f"   Original: {[(i.interval, i.duration_beats) for i in seed.intervals]}")
    print(f"   Variation: {[(i.interval, i.duration_beats) for i in variation.intervals]}")

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    demo()
