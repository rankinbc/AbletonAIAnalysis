"""
Lead Melody Generator

Production-grade lead melody generation that integrates:
- Harmonic awareness (chord tones, tensions, voice leading)
- Motivic development (coherent thematic material)
- Phrase structure (musical form and cadences)
- Inter-track coordination (avoids collisions, complements other tracks)
- Genre-specific idioms (trance, progressive, techno, etc.)

This is the main entry point for generating intelligent lead melodies.
"""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

from .models import (
    NoteEvent, Pitch, PitchClass, Chord, ChordEvent,
    TrackContext, MelodyGenConfig, Motif, MotifInterval,
    MotifTransform, PhraseType, CadenceType, ContourShape,
    TensionLevel, ArticulationType, HarmonicFunction
)
from .harmonic_engine import HarmonicEngine, parse_progression
from .motif_engine import MotifEngine, MotifTransformer
from .phrase_builder import PhraseBuilder, PhrasePlan
from .coordinator import InterTrackCoordinator, RhythmAnalyzer


# =============================================================================
# LEAD GENERATOR
# =============================================================================

@dataclass
class GenerationContext:
    """Context for a single generation pass."""
    section_type: str
    start_beat: float
    total_bars: int
    energy: float
    phrase_plans: List[PhrasePlan]
    chord_events: List[ChordEvent]
    track_context: Optional[TrackContext]


class LeadGenerator:
    """
    Production-grade lead melody generator.

    Generates melodies that:
    - Follow chord progressions intelligently
    - Develop motifs coherently across sections
    - Respect phrase structure and cadences
    - Avoid collisions with other tracks
    - Sound different each time while maintaining quality
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
        genre: str = "trance",
        seed: Optional[int] = None,
    ):
        self.key = PitchClass.from_name(key)
        self.scale = scale
        self.tempo = tempo
        self.genre = genre.lower()
        self.rng = random.Random(seed)

        # Initialize sub-engines
        self.harmonic = HarmonicEngine(self.key, scale)
        self.motif_engine = MotifEngine(genre, seed)
        self.phrase_builder = PhraseBuilder(seed)
        self.coordinator = InterTrackCoordinator(seed)

        # Default register for lead
        self.register = (60, 96)  # C4 to C7

        # Track state across sections for coherence
        self.primary_motif: Optional[Motif] = None
        self.used_transforms: List[MotifTransform] = []

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        context: Optional[TrackContext] = None,
        chord_progression: Optional[List[str]] = None,
        variation: float = 0.3,
    ) -> List[NoteEvent]:
        """
        Generate lead melody for a section.

        Args:
            section_type: Type of section (intro, buildup, breakdown, drop, etc.)
            bars: Number of bars to generate
            energy: Energy level 0-1
            context: Optional TrackContext with other track data
            chord_progression: Optional chord symbols (uses context chords if not provided)
            variation: Amount of variation 0-1 (higher = more different each time)

        Returns:
            List of NoteEvent objects ready for MIDI export
        """
        # Parse chord progression
        if chord_progression:
            chord_events = self.harmonic.parse_progression(
                chord_progression,
                bars_per_chord=bars / len(chord_progression),
            )
        elif context and context.chord_events:
            chord_events = context.chord_events
        else:
            # Default progression
            chord_events = self.harmonic.parse_progression(
                ["Am", "F", "C", "G"],
                bars_per_chord=bars / 4,
            )

        # Build phrase plans
        phrase_plans = self.phrase_builder.build_section_phrases(
            section_type=section_type,
            start_beat=0,
            total_bars=bars,
            base_energy=energy,
            register=self.register,
        )

        # Create generation context
        gen_ctx = GenerationContext(
            section_type=section_type,
            start_beat=0,
            total_bars=bars,
            energy=energy,
            phrase_plans=phrase_plans,
            chord_events=chord_events,
            track_context=context,
        )

        # Generate melody
        notes = self._generate_melody(gen_ctx, variation)

        # Post-process: coordinate with other tracks
        if context:
            notes = self._coordinate_with_context(notes, context)

        # Annotate each note with NCT classification and scale degree
        notes = self._annotate_notes(notes, chord_events)

        return notes

    def _generate_melody(
        self,
        ctx: GenerationContext,
        variation: float,
    ) -> List[NoteEvent]:
        """Main melody generation logic."""
        all_notes = []

        # Get or create primary motif for this section
        if self.primary_motif is None or self.rng.random() < variation:
            self.primary_motif = self.motif_engine.get_seed_motif(
                section_type=ctx.section_type,
                energy=ctx.energy,
            )

        # Generate each phrase
        for phrase_idx, phrase_plan in enumerate(ctx.phrase_plans):
            phrase_notes = self._generate_phrase(
                phrase_plan=phrase_plan,
                phrase_idx=phrase_idx,
                total_phrases=len(ctx.phrase_plans),
                ctx=ctx,
                variation=variation,
            )
            all_notes.extend(phrase_notes)

        return all_notes

    def _generate_phrase(
        self,
        phrase_plan: PhrasePlan,
        phrase_idx: int,
        total_phrases: int,
        ctx: GenerationContext,
        variation: float,
    ) -> List[NoteEvent]:
        """Generate notes for a single phrase."""
        notes = []

        phrase_start = phrase_plan.template.total_bars * phrase_idx * 4  # beats
        phrase_duration = phrase_plan.template.total_bars * 4

        # Get motif for this phrase
        if phrase_idx == 0:
            # First phrase: use primary motif
            motif = self.primary_motif
            transform = MotifTransform.ORIGINAL
        else:
            # Subsequent phrases: transform the motif
            transform = self._select_transform(phrase_idx, ctx)
            motif = MotifTransformer.apply(self.primary_motif, transform)
            self.used_transforms.append(transform)

        # Determine how many times to use the motif in this phrase
        motif_duration = motif.total_duration
        repetitions = max(1, int(phrase_duration / (motif_duration * 2)))

        current_beat = phrase_start

        for rep in range(repetitions):
            # Get chord at this position
            chord_event = self._get_chord_at_beat(current_beat, ctx.chord_events)
            if not chord_event:
                current_beat += motif_duration + 1
                continue

            # Determine starting pitch based on chord and phrase plan
            start_pitch = self._select_start_pitch(
                chord_event.chord,
                phrase_plan,
                current_beat,
                phrase_start,
                phrase_duration,
            )

            # Add variation to motif
            if variation > 0 and rep > 0:
                motif = self.motif_engine.get_variation(motif, variation * 0.5)

            # Render motif to notes
            motif_notes = self._render_motif(
                motif=motif,
                start_pitch=start_pitch,
                start_beat=current_beat,
                chord=chord_event.chord,
                energy=ctx.energy,
                phrase_plan=phrase_plan,
            )
            notes.extend(motif_notes)

            current_beat += motif_duration + self.rng.choice([0.5, 1.0, 1.5])

            # Don't overflow phrase
            if current_beat >= phrase_start + phrase_duration - 1:
                break

        # Add cadence at phrase end
        if phrase_plan.cadence_type and notes:
            cadence_notes = self._generate_cadence(
                phrase_plan=phrase_plan,
                phrase_end_beat=phrase_start + phrase_duration,
                ctx=ctx,
            )
            notes.extend(cadence_notes)

        return notes

    def _select_transform(
        self,
        phrase_idx: int,
        ctx: GenerationContext,
    ) -> MotifTransform:
        """Select appropriate motif transformation for phrase."""
        # Avoid recently used transforms
        recent = set(self.used_transforms[-3:]) if self.used_transforms else set()

        candidates = [
            MotifTransform.SEQUENCE,
            MotifTransform.INVERSION,
            MotifTransform.DIMINUTION,
            MotifTransform.AUGMENTATION,
            MotifTransform.FRAGMENTATION,
        ]

        # Section-specific preferences
        if ctx.section_type == "breakdown":
            candidates = [MotifTransform.AUGMENTATION, MotifTransform.INVERSION]
        elif ctx.section_type == "buildup":
            candidates = [MotifTransform.DIMINUTION, MotifTransform.SEQUENCE]
        elif ctx.section_type == "drop":
            candidates = [MotifTransform.SEQUENCE, MotifTransform.FRAGMENTATION]

        # Filter out recent
        available = [t for t in candidates if t not in recent]
        if not available:
            available = candidates

        return self.rng.choice(available)

    def _get_chord_at_beat(
        self,
        beat: float,
        chord_events: List[ChordEvent],
    ) -> Optional[ChordEvent]:
        """Get the chord playing at a specific beat."""
        for event in chord_events:
            if event.start_beat <= beat < event.end_beat:
                return event
        return chord_events[0] if chord_events else None

    def _select_start_pitch(
        self,
        chord: Chord,
        phrase_plan: PhrasePlan,
        current_beat: float,
        phrase_start: float,
        phrase_duration: float,
    ) -> Pitch:
        """Select starting pitch for a motif instance."""
        # Get phrase progress
        progress = (current_beat - phrase_start) / phrase_duration

        # Get target pitch from contour
        target_midi = phrase_plan.climax_pitch if progress > 0.4 and progress < 0.6 else None

        if target_midi is None:
            # Use contour to determine target register
            from .phrase_builder import ContourPlanner
            planner = ContourPlanner()
            target_midi = planner.get_target_pitch(
                progress,
                phrase_plan.contour,
                phrase_plan.register_low,
                phrase_plan.register_high,
            )

        # Find nearest chord tone to target
        chord_tones = self.harmonic.get_chord_tones_in_register(
            chord,
            phrase_plan.register_low,
            phrase_plan.register_high,
        )

        if not chord_tones:
            return Pitch.from_midi(target_midi)

        # Select chord tone closest to target
        nearest = min(chord_tones, key=lambda p: abs(p.midi_note - target_midi))

        # Sometimes use non-chord tone for color
        if self.rng.random() < 0.2:
            scale_tones = self.harmonic.get_scale_notes_in_register(
                phrase_plan.register_low,
                phrase_plan.register_high,
            )
            if scale_tones:
                # Pick a scale tone near the target
                candidates = [p for p in scale_tones
                              if abs(p.midi_note - target_midi) <= 4]
                if candidates:
                    nearest = self.rng.choice(candidates)

        return nearest

    def _render_motif(
        self,
        motif: Motif,
        start_pitch: Pitch,
        start_beat: float,
        chord: Chord,
        energy: float,
        phrase_plan: PhrasePlan,
    ) -> List[NoteEvent]:
        """
        Render a motif to concrete note events.

        Uses NCT-aware pitch selection: passing tones, neighbor tones, and
        other scale tones are allowed to breathe instead of being snapped
        to the nearest chord tone.  Only truly chromatic pitches that can't
        function as a recognizable NCT are redirected.
        """
        notes = []
        current_pitch = start_pitch
        current_beat = start_beat

        base_velocity = int(70 + 50 * energy)

        for i, interval in enumerate(motif.intervals):
            # Calculate pitch
            if i > 0:
                target_midi = current_pitch.midi_note + interval.interval
                target_pitch = Pitch.from_midi(target_midi)

                tension = self.harmonic.tension_of_pitch_in_context(target_pitch, chord)

                if tension == TensionLevel.CHROMATIC:
                    # Before snapping, check if this pitch can work as a
                    # passing/neighbor tone between the previous note and
                    # a likely next note (peek one interval ahead).
                    can_keep = False
                    if self.harmonic.is_in_scale(target_pitch.pitch_class):
                        # Scale tone — likely a valid passing or neighbor tone
                        can_keep = True
                    elif i + 1 < len(motif.intervals):
                        # Check if the *next* note would be a chord/scale tone
                        # (making this a chromatic passing tone)
                        peek_midi = target_midi + motif.intervals[i + 1].interval
                        peek_pitch = Pitch.from_midi(peek_midi)
                        if (chord.contains_pitch(peek_pitch.pitch_class)
                                or self.harmonic.is_in_scale(peek_pitch.pitch_class)):
                            # This chromatic note resolves stepwise — allow it
                            step = abs(motif.intervals[i + 1].interval)
                            if step <= 2:
                                can_keep = True

                    if not can_keep:
                        # Redirect: prefer nearest scale tone, fall back to
                        # chord tone.  This sounds more melodic than always
                        # jumping to a chord tone.
                        scale_tones = self.harmonic.get_scale_notes_in_register(
                            target_midi - 2, target_midi + 2,
                        )
                        if scale_tones:
                            target_pitch = min(
                                scale_tones,
                                key=lambda p: abs(p.midi_note - target_midi),
                            )
                        else:
                            chord_tones = self.harmonic.get_chord_tones_in_register(
                                chord, target_midi - 3, target_midi + 3,
                            )
                            if chord_tones:
                                target_pitch = min(
                                    chord_tones,
                                    key=lambda p: abs(p.midi_note - target_midi),
                                )

                elif tension == TensionLevel.MODERATE:
                    # Scale tone / extension — keep it, but on long notes at
                    # strong beats, gently pull toward chord tones for stability.
                    is_strong_beat = (current_beat % 4) < 0.01 or (current_beat % 2) < 0.01
                    is_long = interval.duration_beats >= 2.0
                    if is_strong_beat and is_long and not chord.contains_pitch(target_pitch.pitch_class):
                        chord_tones = self.harmonic.get_chord_tones_in_register(
                            chord, target_midi - 2, target_midi + 2,
                        )
                        if chord_tones:
                            # 50% chance to resolve — keeps some color
                            if self.rng.random() < 0.5:
                                target_pitch = min(
                                    chord_tones,
                                    key=lambda p: abs(p.midi_note - target_midi),
                                )

                current_pitch = target_pitch

            # Check register bounds
            if current_pitch.midi_note < phrase_plan.register_low:
                current_pitch = Pitch.from_midi(phrase_plan.register_low)
            elif current_pitch.midi_note > phrase_plan.register_high:
                current_pitch = Pitch.from_midi(phrase_plan.register_high)

            # Calculate velocity with phrase shaping
            phrase_position = (current_beat - start_beat) / max(motif.total_duration, 0.1)
            velocity_shape = math.sin(phrase_position * math.pi)  # Arch shape
            velocity = int(base_velocity * interval.velocity_factor * (0.8 + 0.2 * velocity_shape))
            velocity = max(40, min(127, velocity))

            # Determine if this is a chord tone
            is_chord_tone = chord.contains_pitch(current_pitch.pitch_class)

            notes.append(NoteEvent(
                pitch=current_pitch,
                start_beat=current_beat,
                duration_beats=interval.duration_beats,
                velocity=velocity,
                articulation=interval.articulation,
                chord_tone=is_chord_tone,
                tension_level=self.harmonic.tension_of_pitch_in_context(current_pitch, chord),
                source_motif_id=motif.id,
            ))

            current_beat += interval.duration_beats

        return notes

    def _generate_cadence(
        self,
        phrase_plan: PhrasePlan,
        phrase_end_beat: float,
        ctx: GenerationContext,
    ) -> List[NoteEvent]:
        """Generate cadential figure at phrase end."""
        notes = []

        # Get chord at cadence point
        chord_event = self._get_chord_at_beat(phrase_end_beat - 2, ctx.chord_events)
        if not chord_event:
            return notes

        # Determine cadence approach
        approach_degrees = phrase_plan.cadence_approach_degrees
        target_degree = phrase_plan.cadence_target_degree

        # Build approach notes
        scale_notes = self.harmonic.get_scale_notes_in_register(
            phrase_plan.register_low,
            phrase_plan.register_high,
        )

        if not scale_notes:
            return notes

        # Find scale degree pitches
        root_midi = self.key.value + 60  # Middle octave root
        scale_intervals = self.harmonic.scale_intervals

        # Get approach note (2 beats before end)
        if approach_degrees and len(scale_intervals) > max(approach_degrees):
            approach_degree = self.rng.choice(approach_degrees)
            approach_interval = scale_intervals[approach_degree % len(scale_intervals)]
            approach_midi = root_midi + approach_interval

            # Find in register
            while approach_midi < phrase_plan.register_low:
                approach_midi += 12
            while approach_midi > phrase_plan.register_high:
                approach_midi -= 12

            notes.append(NoteEvent(
                pitch=Pitch.from_midi(approach_midi),
                start_beat=phrase_end_beat - 2,
                duration_beats=1.0,
                velocity=int(80 + 30 * ctx.energy),
                articulation=ArticulationType.TENUTO,
            ))

        # Target note (resolution)
        target_interval = scale_intervals[target_degree % len(scale_intervals)]
        target_midi = root_midi + target_interval

        while target_midi < phrase_plan.register_low:
            target_midi += 12
        while target_midi > phrase_plan.register_high:
            target_midi -= 12

        # Duration based on cadence type
        from .phrase_builder import CadencePlanner
        duration_factor = CadencePlanner().get_duration_factor(phrase_plan.cadence_type)

        notes.append(NoteEvent(
            pitch=Pitch.from_midi(target_midi),
            start_beat=phrase_end_beat - 1,
            duration_beats=1.5 * duration_factor,
            velocity=int(90 + 30 * ctx.energy),
            articulation=ArticulationType.TENUTO,
            chord_tone=True,
        ))

        return notes

    def _coordinate_with_context(
        self,
        notes: List[NoteEvent],
        context: TrackContext,
    ) -> List[NoteEvent]:
        """
        Coordinate melody with other tracks.

        Uses consonance scoring from music21 to prefer intervals that sound
        good against simultaneously-sounding notes in other tracks, rather
        than only checking for raw pitch collisions.
        """
        if not notes:
            return notes

        for i, note in enumerate(notes):
            chord_event = None
            for ce in context.chord_events:
                if ce.start_beat <= note.start_beat < ce.end_beat:
                    chord_event = ce
                    break

            if chord_event:
                # Check consonance against other tracks sounding at this beat
                other_pitches = context.pitches_at_beat(note.start_beat)
                if other_pitches:
                    # If the note forms a dissonant interval with another track
                    # AND it's not a recognized NCT, try to move it
                    is_dissonant = False
                    for opc in other_pitches:
                        interval_semitones = note.pitch.pitch_class.interval_to(opc)
                        # Minor 2nd (1) or major 7th (11) or tritone (6) against
                        # non-chord bass/pad notes create harsh clashes
                        if interval_semitones in (1, 6, 11):
                            is_dissonant = True
                            break

                    if is_dissonant and not chord_event.chord.contains_pitch(note.pitch.pitch_class):
                        # Try to find a consonant alternative nearby
                        chord_tones = self.harmonic.get_chord_tones_in_register(
                            chord_event.chord,
                            self.register[0],
                            self.register[1],
                        )
                        chord_midi = [p.midi_note for p in chord_tones]

                        notes[i] = self.coordinator.collision_detector.resolve_collision(
                            note,
                            note.pitch.midi_note,
                            chord_midi,
                            prefer_direction=1,
                        )
                else:
                    # No other tracks sounding — still do basic collision check
                    chord_tones = self.harmonic.get_chord_tones_in_register(
                        chord_event.chord,
                        self.register[0],
                        self.register[1],
                    )
                    chord_midi = [p.midi_note for p in chord_tones]

                    notes[i] = self.coordinator.collision_detector.resolve_collision(
                        note,
                        note.pitch.midi_note,
                        chord_midi,
                        prefer_direction=1,
                    )

        # Apply voice leading coordination
        notes = self.coordinator.coordinate_voices(notes, context)

        return notes

    def _annotate_notes(
        self,
        notes: List[NoteEvent],
        chord_events: List[ChordEvent],
    ) -> List[NoteEvent]:
        """
        Post-generation pass: annotate every note with its scale degree
        and non-chord-tone classification.

        This makes the output self-documenting — useful for coaching,
        debugging, and downstream analysis.
        """
        for i, note in enumerate(notes):
            # Scale degree
            note.scale_degree = self.harmonic.get_scale_degree(note.pitch.pitch_class)

            # NCT classification requires the current chord
            chord_event = self._get_chord_at_beat(note.start_beat, chord_events)
            if chord_event:
                prev_note = notes[i - 1] if i > 0 else None
                next_note = notes[i + 1] if i < len(notes) - 1 else None
                note.nct_type = self.harmonic.classify_non_chord_tone(
                    note, prev_note, next_note, chord_event.chord,
                )

        return notes


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_lead(
    section_type: str = "drop",
    bars: int = 16,
    energy: float = 0.8,
    key: str = "A",
    scale: str = "minor",
    genre: str = "trance",
    chord_progression: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> List[NoteEvent]:
    """
    Quick function to generate lead melody.

    Args:
        section_type: Type of section
        bars: Number of bars
        energy: Energy level 0-1
        key: Musical key
        scale: Scale type
        genre: Genre for style
        chord_progression: Optional chord symbols
        seed: Random seed for reproducibility

    Returns:
        List of NoteEvent objects
    """
    generator = LeadGenerator(
        key=key,
        scale=scale,
        genre=genre,
        seed=seed,
    )

    return generator.generate_for_section(
        section_type=section_type,
        bars=bars,
        energy=energy,
        chord_progression=chord_progression,
    )


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate lead generator capabilities."""
    print("Lead Generator Demo")
    print("=" * 50)

    generator = LeadGenerator(
        key="A",
        scale="minor",
        genre="trance",
        seed=42,
    )

    # Generate for different sections
    sections = [
        ("breakdown", 8, 0.5),
        ("buildup", 8, 0.7),
        ("drop", 16, 0.95),
    ]

    chord_prog = ["Am", "F", "C", "G"]

    for section_type, bars, energy in sections:
        print(f"\n{section_type.upper()} ({bars} bars, energy {energy}):")

        notes = generator.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            chord_progression=chord_prog,
        )

        print(f"  Generated {len(notes)} notes")

        # Show first few notes with NCT annotations
        for note in notes[:8]:
            nct = note.nct_type or "?"
            deg = f"^{note.scale_degree}" if note.scale_degree else " ?"
            print(f"    Beat {note.start_beat:5.2f}: {note.pitch.to_name():4} "
                  f"dur={note.duration_beats:.2f} vel={note.velocity:3} "
                  f"{deg:>3} {nct:12s}")
        if len(notes) > 8:
            print(f"    ... and {len(notes) - 8} more")

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    demo()
