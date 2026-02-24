"""
Integration Layer

Connects the production-grade melody generation system to the
existing ableton-generators codebase.

Provides:
- MIDI export (NoteEvent → mido messages)
- Adapter for existing MelodyGenerator interface
- Track context builder from existing tracks
- Full generation pipeline (rule-only)
- Hybrid generation pipeline (rule + ML candidates + evaluation scoring)
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# Import mido for MIDI export
try:
    from mido import MidiFile, MidiTrack, Message
except ImportError:
    MidiFile = None
    MidiTrack = None
    Message = None
    print("Warning: mido not installed. MIDI export will not work.")

# Import our components
from .models import (
    NoteEvent, Pitch, PitchClass, ChordEvent, TrackContext,
    ArticulationType
)
from .harmonic_engine import HarmonicEngine, parse_progression
from .lead_generator import LeadGenerator
from .arp_generator import ArpGenerator, ArpStyle
from .humanizer import Humanizer, HumanizeConfig, GrooveStyle
from .evaluation import evaluate_melody, MelodyMetrics, print_metrics, ReferenceStats

logger = logging.getLogger(__name__)


# =============================================================================
# MIDI EXPORTER
# =============================================================================

class MIDIExporter:
    """
    Exports NoteEvent sequences to MIDI files.

    Handles:
    - Timing offset application
    - Velocity clamping
    - Note-off collision resolution
    - Multiple track export
    """

    def __init__(
        self,
        ticks_per_beat: int = 480,
        tempo: int = 138,
    ):
        self.ticks_per_beat = ticks_per_beat
        self.tempo = tempo

    def export_track(
        self,
        notes: List[NoteEvent],
        program: int = 81,  # Lead synth
        channel: int = 0,
    ) -> 'MidiTrack':
        """Export notes to a MidiTrack."""
        if MidiTrack is None:
            raise ImportError("mido is required for MIDI export")

        track = MidiTrack()

        # Add program change
        track.append(Message('program_change', program=program, channel=channel, time=0))

        if not notes:
            return track

        # Build event list (on/off) with actual start times
        events = []
        for note in notes:
            actual_start = note.actual_start
            on_tick = int(actual_start * self.ticks_per_beat)
            off_tick = int((actual_start + note.duration_beats) * self.ticks_per_beat)

            velocity = max(1, min(127, note.velocity))

            events.append(('on', on_tick, note.pitch.midi_note, velocity))
            events.append(('off', off_tick, note.pitch.midi_note, 0))

        # Sort events: by tick, then note-off before note-on
        events.sort(key=lambda e: (e[1], 0 if e[0] == 'off' else 1))

        # Track active notes for collision handling
        active: Dict[int, int] = {}
        current_tick = 0

        for event_type, tick, pitch, velocity in events:
            delta = max(0, tick - current_tick)

            if event_type == 'on':
                active[pitch] = active.get(pitch, 0) + 1
                track.append(Message(
                    'note_on',
                    note=pitch,
                    velocity=velocity,
                    channel=channel,
                    time=delta,
                ))
                current_tick = tick
            else:
                count = active.get(pitch, 0)
                if count > 1:
                    # Another note on same pitch still active
                    active[pitch] = count - 1
                else:
                    active[pitch] = 0
                    track.append(Message(
                        'note_off',
                        note=pitch,
                        velocity=0,
                        channel=channel,
                        time=delta,
                    ))
                    current_tick = tick

        return track

    def export_file(
        self,
        tracks: Dict[str, List[NoteEvent]],
        output_path: str,
        programs: Optional[Dict[str, int]] = None,
    ) -> str:
        """
        Export multiple tracks to a MIDI file.

        Args:
            tracks: Dict of track_name → notes
            output_path: Output file path
            programs: Optional dict of track_name → MIDI program number

        Returns:
            Path to created file
        """
        if MidiFile is None:
            raise ImportError("mido is required for MIDI export")

        if programs is None:
            programs = {
                'lead': 81,    # Lead 2 (sawtooth)
                'arp': 81,
                'bass': 38,    # Synth Bass 1
                'pad': 89,     # Pad 2 (warm)
            }

        midi = MidiFile(ticks_per_beat=self.ticks_per_beat)

        for i, (name, notes) in enumerate(tracks.items()):
            program = programs.get(name, 81)
            track = self.export_track(notes, program=program, channel=i % 16)
            midi.tracks.append(track)

        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        midi.save(output_path)
        return output_path


# =============================================================================
# LEGACY ADAPTER
# =============================================================================

@dataclass
class LegacyMelodyNote:
    """Adapter class matching original MelodyNote interface."""
    pitch: int
    start: float
    duration: float
    velocity: int


class LegacyAdapter:
    """
    Adapter that provides the same interface as the original MelodyGenerator.

    Use this as a drop-in replacement for the old generator.
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
        config: Optional[Any] = None,  # Accept old Config object
    ):
        self.key = key
        self.scale = scale
        self.tempo = tempo
        self._lead_gen = LeadGenerator(key, scale, tempo, "trance")
        self._arp_gen = ArpGenerator(key, scale, tempo)
        self._humanizer = Humanizer()

    def generate(
        self,
        bars: int = 8,
        pattern: str = "anthem",
        energy: float = 1.0,
        variation: float = 0.2,
        octave_offset: int = 0,
        phrase_length: int = 4,
        seed: Optional[int] = None,
    ) -> List[LegacyMelodyNote]:
        """Generate melody (legacy interface)."""
        notes = self._lead_gen.generate_for_section(
            section_type="drop",
            bars=bars,
            energy=energy,
            variation=variation,
        )

        # Humanize
        notes = self._humanizer.humanize(notes)

        # Convert to legacy format
        return [
            LegacyMelodyNote(
                pitch=n.pitch.midi_note,
                start=n.actual_start,
                duration=n.duration_beats,
                velocity=n.velocity,
            )
            for n in notes
        ]

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        variation: float = 0.15,
        seed: Optional[int] = None,
    ) -> List[LegacyMelodyNote]:
        """Generate for section (legacy interface)."""
        notes = self._lead_gen.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            variation=variation,
        )

        notes = self._humanizer.humanize(notes)

        return [
            LegacyMelodyNote(
                pitch=n.pitch.midi_note,
                start=n.actual_start,
                duration=n.duration_beats,
                velocity=n.velocity,
            )
            for n in notes
        ]


# =============================================================================
# FULL GENERATION PIPELINE
# =============================================================================

@dataclass
class GeneratedTrack:
    """Result of generating a single track."""
    name: str
    notes: List[NoteEvent]
    midi_notes: List[LegacyMelodyNote]


@dataclass
class GenerationResult:
    """Result of full generation pipeline."""
    lead: GeneratedTrack
    arp: GeneratedTrack
    chord_events: List[ChordEvent]
    midi_path: Optional[str] = None


class MelodyGenerationPipeline:
    """
    Full melody generation pipeline.

    Generates lead and arp tracks that work together,
    following a chord progression with proper coordination.
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
        genre: str = "trance",
        output_dir: str = "output",
    ):
        self.key = key
        self.scale = scale
        self.tempo = tempo
        self.genre = genre
        self.output_dir = output_dir

        self.harmonic = HarmonicEngine(PitchClass.from_name(key), scale)
        self.lead_gen = LeadGenerator(key, scale, tempo, genre)
        self.arp_gen = ArpGenerator(key, scale, tempo)
        self.humanizer = Humanizer()
        self.exporter = MIDIExporter(tempo=tempo)

    def generate_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        chord_progression: Optional[List[str]] = None,
        export_midi: bool = True,
    ) -> GenerationResult:
        """
        Generate all tracks for a section.

        Args:
            section_type: Type of section (drop, breakdown, etc.)
            bars: Number of bars
            energy: Energy level 0-1
            chord_progression: Chord symbols (default: Am, F, C, G)
            export_midi: Whether to export MIDI file

        Returns:
            GenerationResult with all tracks
        """
        # Parse chords
        if chord_progression is None:
            chord_progression = ["Am", "F", "C", "G"]

        bars_per_chord = bars / len(chord_progression)
        chord_events = self.harmonic.parse_progression(chord_progression, bars_per_chord)

        # Create track context (initially just chords)
        context = TrackContext(chord_events=chord_events)

        # Generate arp first (lead will coordinate with it)
        arp_style = {
            "intro": ArpStyle.AMBIENT,
            "buildup": ArpStyle.TRANCE,
            "breakdown": ArpStyle.PROGRESSIVE,
            "drop": ArpStyle.TRANCE,
            "break": ArpStyle.CLASSIC,
            "outro": ArpStyle.AMBIENT,
        }.get(section_type, ArpStyle.TRANCE)

        arp_notes = self.arp_gen.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            chord_events=chord_events,
        )

        # Add arp to context so lead can coordinate
        context.arp_notes = arp_notes

        # Generate lead
        lead_notes = self.lead_gen.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            context=context,
        )

        # Humanize both
        groove = GrooveStyle.TRANCE if self.genre == "trance" else GrooveStyle.HUMAN
        lead_notes = self.humanizer.humanize(
            lead_notes,
            HumanizeConfig(groove_style=groove),
        )
        arp_notes = self.humanizer.humanize(
            arp_notes,
            HumanizeConfig(groove_style=groove, timing_variance=0.01),
        )

        # Convert to legacy format
        lead_legacy = [
            LegacyMelodyNote(n.pitch.midi_note, n.actual_start, n.duration_beats, n.velocity)
            for n in lead_notes
        ]
        arp_legacy = [
            LegacyMelodyNote(n.pitch.midi_note, n.actual_start, n.duration_beats, n.velocity)
            for n in arp_notes
        ]

        result = GenerationResult(
            lead=GeneratedTrack("lead", lead_notes, lead_legacy),
            arp=GeneratedTrack("arp", arp_notes, arp_legacy),
            chord_events=chord_events,
        )

        # Export MIDI if requested
        if export_midi:
            filename = f"{section_type}_{bars}bars_{self.key}{self.scale}.mid"
            midi_path = os.path.join(self.output_dir, filename)

            self.exporter.export_file(
                {"lead": lead_notes, "arp": arp_notes},
                midi_path,
            )
            result.midi_path = midi_path

        return result

    def generate_full_song(
        self,
        structure: List[Tuple[str, int, float]],  # (section_type, bars, energy)
        chord_progression: Optional[List[str]] = None,
        export_midi: bool = True,
    ) -> Dict[str, GenerationResult]:
        """
        Generate full song with multiple sections.

        Args:
            structure: List of (section_type, bars, energy) tuples
            chord_progression: Chord symbols to use throughout
            export_midi: Whether to export MIDI

        Returns:
            Dict of section_name → GenerationResult
        """
        results = {}

        for i, (section_type, bars, energy) in enumerate(structure):
            section_name = f"{i+1}_{section_type}"
            results[section_name] = self.generate_section(
                section_type=section_type,
                bars=bars,
                energy=energy,
                chord_progression=chord_progression,
                export_midi=export_midi,
            )

        return results


# =============================================================================
# HYBRID PIPELINE (Step 1.7)
# =============================================================================

@dataclass
class ScoredCandidate:
    """A melody candidate with its evaluation score and source."""
    notes: List[NoteEvent]
    metrics: MelodyMetrics
    source: str  # "rule_engine", "improv_rnn", "attention_rnn", "musicvae_variation"
    scale_compliance: float = 0.0
    midi_path: Optional[str] = None


@dataclass
class HybridResult:
    """Result of the hybrid generation pipeline."""
    # Best lead melody (winner of candidate ranking)
    lead: GeneratedTrack
    lead_metrics: MelodyMetrics
    lead_source: str

    # Arp (always rule-based)
    arp: GeneratedTrack

    # Chord progression used
    chord_events: List[ChordEvent]

    # All candidates that were scored
    all_candidates: List[ScoredCandidate] = field(default_factory=list)

    # Output paths
    midi_path: Optional[str] = None
    log_path: Optional[str] = None

    # Timing
    generation_time_s: float = 0.0

    def to_log_dict(self) -> dict:
        """Serialize generation log for analysis."""
        return {
            "lead_source": self.lead_source,
            "lead_score": self.lead_metrics.composite,
            "lead_notes": self.lead_metrics.num_notes,
            "arp_notes": len(self.arp.notes),
            "num_candidates": len(self.all_candidates),
            "generation_time_s": round(self.generation_time_s, 2),
            "candidates": [
                {
                    "source": c.source,
                    "composite": round(c.metrics.composite, 4),
                    "scale_compliance": round(c.scale_compliance, 3),
                    "num_notes": c.metrics.num_notes,
                    "pitch_entropy": round(c.metrics.pitch_entropy, 3),
                    "chord_tone_ratio": round(c.metrics.chord_tone_ratio, 3),
                    "stepwise_motion": round(c.metrics.stepwise_motion_ratio, 3),
                }
                for c in self.all_candidates
            ],
        }


class HybridPipeline:
    """
    Hybrid melody generation pipeline (Step 1.7).

    Combines rule-based and ML-based generation, scoring all candidates
    with the evaluation framework and returning the best.

    Pipeline:
    1. Parse chord progression
    2. Generate arp track (rule-based, always)
    3. Generate rule-based lead melody
    4. If ML available: generate Improv RNN candidates
    5. If ML available: create MusicVAE variations of best candidates
    6. Score ALL candidates with evaluation framework
    7. Select best lead by composite score
    8. Humanize and export MIDI

    Falls back gracefully to rule-only when Docker/Magenta is unavailable.

    Usage:
        pipeline = HybridPipeline(key="A", scale="minor")
        result = pipeline.generate(
            chords=["Am", "F", "C", "G"],
            bars=16,
            energy=0.9,
        )
        print(f"Source: {result.lead_source}")
        print(f"Score: {result.lead_metrics.composite:.3f}")
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
        genre: str = "trance",
        output_dir: str = "output",
        reference_stats_path: Optional[str] = None,
        verbose: bool = False,
    ):
        self.key = key
        self.scale = scale
        self.tempo = tempo
        self.genre = genre
        self.output_dir = output_dir
        self.verbose = verbose

        # Core components (always available)
        self.harmonic = HarmonicEngine(PitchClass.from_name(key), scale)
        self.lead_gen = LeadGenerator(key, scale, tempo, genre)
        self.arp_gen = ArpGenerator(key, scale, tempo)
        self.humanizer = Humanizer()
        self.exporter = MIDIExporter(tempo=tempo)

        # Reference stats (optional, improves KL divergence scoring)
        self.reference_stats = None
        if reference_stats_path and Path(reference_stats_path).exists():
            self.reference_stats = ReferenceStats.load(reference_stats_path)
            if self.verbose:
                logger.info("Loaded reference stats from %s", reference_stats_path)

        # ML components (lazy, may not be available)
        self._ml_gen = None
        self._ml_variator = None
        self._ml_available = None

    def _check_ml_available(self) -> bool:
        """Check if Docker + Magenta are available for ML generation."""
        if self._ml_available is not None:
            return self._ml_available

        try:
            from shared.magenta import is_docker_available, is_magenta_image_available
            self._ml_available = is_docker_available() and is_magenta_image_available()
        except ImportError:
            self._ml_available = False

        if self.verbose:
            status = "available" if self._ml_available else "not available"
            logger.info("ML generation: %s", status)

        return self._ml_available

    def _get_ml_gen(self):
        if self._ml_gen is None:
            from .ml_bridge import MLMelodyGenerator
            self._ml_gen = MLMelodyGenerator(
                key=self.key,
                scale=self.scale,
                output_dir=Path(self.output_dir),
                verbose=self.verbose,
            )
        return self._ml_gen

    def _get_ml_variator(self):
        if self._ml_variator is None:
            from .ml_bridge import MLMotifVariator
            self._ml_variator = MLMotifVariator(
                output_dir=Path(self.output_dir),
                verbose=self.verbose,
            )
        return self._ml_variator

    def generate(
        self,
        chords: Optional[List[str]] = None,
        section_type: str = "drop",
        bars: int = 16,
        energy: float = 0.9,
        temperature: float = 1.0,
        num_ml_candidates: int = 5,
        num_variations: int = 2,
        variation_noise: float = 0.3,
        export_midi: bool = True,
        save_log: bool = True,
    ) -> HybridResult:
        """
        Generate a melody using the hybrid pipeline.

        Args:
            chords: Chord symbols (default: Am, F, C, G)
            section_type: Section type (drop, breakdown, buildup, etc.)
            bars: Number of bars
            energy: Energy level 0-1
            temperature: ML sampling temperature (0.5=safe, 1.5=wild)
            num_ml_candidates: Number of ML candidates to generate
            num_variations: MusicVAE variations per top candidate
            variation_noise: MusicVAE noise scale
            export_midi: Whether to export MIDI file
            save_log: Whether to save generation log JSON

        Returns:
            HybridResult with best melody, all candidates, and metrics
        """
        t0 = time.time()

        if chords is None:
            chords = ["Am", "F", "C", "G"]

        # --- 1. Parse chords ---
        bars_per_chord = bars / len(chords)
        chord_events = self.harmonic.parse_progression(chords, bars_per_chord)
        context = TrackContext(chord_events=chord_events)

        # --- 2. Generate arp (always rule-based) ---
        arp_notes = self.arp_gen.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            chord_events=chord_events,
        )
        context.arp_notes = arp_notes

        # --- 3. Generate rule-based lead ---
        all_candidates: List[ScoredCandidate] = []

        rule_notes = self.lead_gen.generate_for_section(
            section_type=section_type,
            bars=bars,
            energy=energy,
            context=context,
        )

        rule_metrics = evaluate_melody(
            rule_notes,
            key=self.key,
            scale=self.scale,
            chord_events=chord_events,
            reference_stats=self.reference_stats,
            bpm=float(self.tempo),
        )
        rule_compliance = self._compute_scale_compliance(rule_notes)

        all_candidates.append(ScoredCandidate(
            notes=rule_notes,
            metrics=rule_metrics,
            source="rule_engine",
            scale_compliance=rule_compliance,
        ))

        if self.verbose:
            print(f"  Rule engine: composite={rule_metrics.composite:.3f}, "
                  f"notes={len(rule_notes)}")

        # --- 4. Generate ML candidates (if available) ---
        if self._check_ml_available() and num_ml_candidates > 0:
            ml_candidates = self._generate_ml_candidates(
                chords=chords,
                chord_events=chord_events,
                bars=bars,
                temperature=temperature,
                num_candidates=num_ml_candidates,
            )
            all_candidates.extend(ml_candidates)

            # --- 5. MusicVAE variations of top candidates ---
            if num_variations > 0 and len(all_candidates) > 1:
                variations = self._generate_variations(
                    candidates=all_candidates,
                    chord_events=chord_events,
                    num_variations=num_variations,
                    noise_scale=variation_noise,
                    bars=bars,
                )
                all_candidates.extend(variations)

        # --- 6. Select best by composite score ---
        best = max(all_candidates, key=lambda c: c.metrics.composite)

        if self.verbose:
            print(f"\n  Winner: {best.source} "
                  f"(composite={best.metrics.composite:.3f}, "
                  f"notes={best.metrics.num_notes})")
            print(f"  Total candidates: {len(all_candidates)}")

        # --- 7. Humanize ---
        groove = GrooveStyle.TRANCE if self.genre == "trance" else GrooveStyle.HUMAN
        lead_notes = self.humanizer.humanize(
            best.notes,
            HumanizeConfig(groove_style=groove),
        )
        arp_notes = self.humanizer.humanize(
            arp_notes,
            HumanizeConfig(groove_style=groove, timing_variance=0.01),
        )

        # Convert to legacy format
        lead_legacy = [
            LegacyMelodyNote(n.pitch.midi_note, n.actual_start, n.duration_beats, n.velocity)
            for n in lead_notes
        ]
        arp_legacy = [
            LegacyMelodyNote(n.pitch.midi_note, n.actual_start, n.duration_beats, n.velocity)
            for n in arp_notes
        ]

        generation_time = time.time() - t0

        result = HybridResult(
            lead=GeneratedTrack("lead", lead_notes, lead_legacy),
            lead_metrics=best.metrics,
            lead_source=best.source,
            arp=GeneratedTrack("arp", arp_notes, arp_legacy),
            chord_events=chord_events,
            all_candidates=all_candidates,
            generation_time_s=generation_time,
        )

        # --- 8. Export ---
        if export_midi:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            filename = f"{section_type}_{bars}bars_{self.key}{self.scale}.mid"
            midi_path = os.path.join(self.output_dir, filename)
            self.exporter.export_file(
                {"lead": lead_notes, "arp": arp_notes},
                midi_path,
            )
            result.midi_path = midi_path

        if save_log:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            log_filename = f"{section_type}_{bars}bars_{self.key}{self.scale}_log.json"
            log_path = os.path.join(self.output_dir, log_filename)
            with open(log_path, "w") as f:
                json.dump(result.to_log_dict(), f, indent=2)
            result.log_path = log_path

        return result

    def generate_batch(
        self,
        n: int = 50,
        chords: Optional[List[str]] = None,
        section_type: str = "drop",
        bars: int = 16,
        energy: float = 0.9,
        **kwargs,
    ) -> List[HybridResult]:
        """
        Generate N melodies for baseline recording.

        Args:
            n: Number of melodies to generate
            Other args: same as generate()

        Returns:
            List of HybridResult
        """
        results = []
        for i in range(n):
            if self.verbose:
                print(f"\n--- Generating {i+1}/{n} ---")
            result = self.generate(
                chords=chords,
                section_type=section_type,
                bars=bars,
                energy=energy,
                export_midi=False,
                save_log=False,
                **kwargs,
            )
            results.append(result)
        return results

    def _generate_ml_candidates(
        self,
        chords: List[str],
        chord_events: List[ChordEvent],
        bars: int,
        temperature: float,
        num_candidates: int,
    ) -> List[ScoredCandidate]:
        """Generate and score ML candidates via Improv RNN."""
        candidates = []
        try:
            ml_gen = self._get_ml_gen()
            result = ml_gen.generate(
                chords=chords,
                bars=bars,
                bpm=float(self.tempo),
                temperature=temperature,
                num_candidates=num_candidates,
            )

            # The MLMelodyGenerator already filters and scores internally,
            # but we re-score with chord_events for chord-tone accuracy
            from .tokenizer import midi_to_notes

            # Re-read all MIDI files from the generation for full scoring
            # (ml_gen.generate returns only the best; we want all)
            # Use the magenta output directory to find all candidates
            magenta = ml_gen._get_magenta()
            output_dir = magenta.output_dir if hasattr(magenta, 'output_dir') else None

            # Score the best candidate returned by ml_gen
            ml_metrics = evaluate_melody(
                result.notes,
                key=self.key,
                scale=self.scale,
                chord_events=chord_events,
                reference_stats=self.reference_stats,
                bpm=float(self.tempo),
            )
            candidates.append(ScoredCandidate(
                notes=result.notes,
                metrics=ml_metrics,
                source=result.source,
                scale_compliance=result.scale_compliance,
                midi_path=str(result.midi_path),
            ))

            if self.verbose:
                print(f"  Improv RNN: composite={ml_metrics.composite:.3f}, "
                      f"notes={len(result.notes)}")

        except Exception as e:
            logger.warning("ML generation failed: %s", e)
            if self.verbose:
                print(f"  ML generation failed: {e}")

        return candidates

    def _generate_variations(
        self,
        candidates: List[ScoredCandidate],
        chord_events: List[ChordEvent],
        num_variations: int,
        noise_scale: float,
        bars: int,
    ) -> List[ScoredCandidate]:
        """Generate MusicVAE variations of the best candidate so far."""
        variations = []

        # Vary the current best candidate
        best = max(candidates, key=lambda c: c.metrics.composite)

        try:
            variator = self._get_ml_variator()
            vae_bars = 2 if bars <= 4 else 16
            result = variator.vary(
                notes=best.notes,
                num_variants=num_variations,
                noise_scale=noise_scale,
                bpm=float(self.tempo),
                bars=vae_bars,
            )

            for i, variant_notes in enumerate(result.variants):
                if not variant_notes:
                    continue

                var_metrics = evaluate_melody(
                    variant_notes,
                    key=self.key,
                    scale=self.scale,
                    chord_events=chord_events,
                    reference_stats=self.reference_stats,
                    bpm=float(self.tempo),
                )
                var_compliance = self._compute_scale_compliance(variant_notes)

                variations.append(ScoredCandidate(
                    notes=variant_notes,
                    metrics=var_metrics,
                    source="musicvae_variation",
                    scale_compliance=var_compliance,
                ))

                if self.verbose:
                    print(f"  MusicVAE var {i+1}: "
                          f"composite={var_metrics.composite:.3f}, "
                          f"notes={len(variant_notes)}")

        except Exception as e:
            logger.warning("MusicVAE variation failed: %s", e)
            if self.verbose:
                print(f"  MusicVAE variation failed: {e}")

        return variations

    def _compute_scale_compliance(self, notes: List[NoteEvent]) -> float:
        """Fraction of notes in the current scale."""
        if not notes:
            return 0.0
        in_scale = sum(
            1 for n in notes
            if self.harmonic.is_in_scale(n.pitch.pitch_class)
        )
        return in_scale / len(notes)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_melody(
    section_type: str = "drop",
    bars: int = 16,
    energy: float = 0.8,
    key: str = "A",
    scale: str = "minor",
    chord_progression: Optional[List[str]] = None,
    genre: str = "trance",
    humanize: bool = True,
) -> List[LegacyMelodyNote]:
    """
    Quick function to generate a melody.

    Returns notes in the legacy format for easy integration.
    """
    pipeline = MelodyGenerationPipeline(key, scale, 138, genre)
    result = pipeline.generate_section(
        section_type=section_type,
        bars=bars,
        energy=energy,
        chord_progression=chord_progression,
        export_midi=False,
    )
    return result.lead.midi_notes


def generate_arp(
    section_type: str = "drop",
    bars: int = 16,
    energy: float = 0.8,
    key: str = "A",
    scale: str = "minor",
    chord_progression: Optional[List[str]] = None,
    style: str = "trance",
) -> List[LegacyMelodyNote]:
    """Quick function to generate an arp."""
    pipeline = MelodyGenerationPipeline(key, scale, 138, style)
    result = pipeline.generate_section(
        section_type=section_type,
        bars=bars,
        energy=energy,
        chord_progression=chord_progression,
        export_midi=False,
    )
    return result.arp.midi_notes


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate integration capabilities."""
    print("Integration Demo")
    print("=" * 50)

    # Test legacy adapter
    print("\n1. Legacy Adapter (drop-in replacement):")
    adapter = LegacyAdapter(key="A", scale="minor")
    legacy_notes = adapter.generate(bars=8, energy=0.9)
    print(f"   Generated {len(legacy_notes)} notes")
    for note in legacy_notes[:3]:
        print(f"   pitch={note.pitch}, start={note.start:.2f}, "
              f"dur={note.duration:.2f}, vel={note.velocity}")

    # Test full pipeline
    print("\n2. Full Pipeline (with coordination):")
    pipeline = MelodyGenerationPipeline(
        key="A",
        scale="minor",
        genre="trance",
        output_dir="output/integration_demo",
    )

    result = pipeline.generate_section(
        section_type="drop",
        bars=16,
        energy=0.9,
        chord_progression=["Am", "F", "C", "G"],
        export_midi=True,
    )

    print(f"   Lead: {len(result.lead.notes)} notes")
    print(f"   Arp: {len(result.arp.notes)} notes")
    print(f"   Chords: {len(result.chord_events)} changes")
    if result.midi_path:
        print(f"   MIDI exported to: {result.midi_path}")

    # Test full song
    print("\n3. Full Song Generation:")
    song_structure = [
        ("intro", 8, 0.4),
        ("buildup", 8, 0.7),
        ("drop", 16, 0.95),
        ("breakdown", 8, 0.5),
        ("buildup", 8, 0.8),
        ("drop", 16, 1.0),
        ("outro", 8, 0.3),
    ]

    song = pipeline.generate_full_song(
        structure=song_structure,
        chord_progression=["Am", "F", "C", "G"],
        export_midi=True,
    )

    print(f"   Generated {len(song)} sections:")
    total_lead = 0
    total_arp = 0
    for name, res in song.items():
        total_lead += len(res.lead.notes)
        total_arp += len(res.arp.notes)
        print(f"     {name}: lead={len(res.lead.notes)}, arp={len(res.arp.notes)}")

    print(f"   Total: {total_lead} lead notes, {total_arp} arp notes")

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    demo()
