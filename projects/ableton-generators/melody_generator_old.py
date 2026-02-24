"""
Pattern-based melody generator for trance music.
Drop-in replacement for the original melody_generator.py.

Key improvements over v1:
  - PatternNote dataclass: explicit octave field eliminates magic degree=7 tricks
  - Isolated random.Random(seed) — never pollutes global state, repeatable
  - pattern_bars uses math.ceil — no silent gap every repetition
  - _note_to_midi uses full NOTE_MAP lookup — no accidental double-application of modifiers
  - Velocity humanization with per-beat emphasis + gaussian micro-variation
  - Phrase-boundary resolution: final bar of each phrase lands on root
  - note-off collision guard for overlapping same-pitch notes
  - Section energy curves: velocity and duration shaped by position in section
  - Config magic numbers replaced with named constants
  - All public methods fully type-annotated
"""

from __future__ import annotations

import math
import random
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from mido import MidiFile, MidiTrack, Message

# ---------------------------------------------------------------------------
# Try to import project Config; fall back to a sensible standalone default
# ---------------------------------------------------------------------------
try:
    from config import Config, DEFAULT_CONFIG  # type: ignore
except ImportError:  # running standalone
    @dataclass
    class Config:  # type: ignore[no-redef]
        TICKS_PER_BEAT: int = 480
        OUTPUT_BASE: str = "output"
        DEFAULT_VELOCITY: int = 100
        LEAD_SYNTH_PROGRAM: int = 81   # GM: Lead 2 (sawtooth)
        BREAKDOWN_OCTAVE_SHIFT: int = -1
        DROP_OCTAVE_SHIFT: int = 0
        HUMANIZE_BEAT_EMPHASIS: float = 1.06  # beat-1/3 boost factor
        HUMANIZE_SIGMA: float = 3.0           # gaussian velocity jitter σ

    DEFAULT_CONFIG = Config()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatternNote:
    """One note within a pattern template.

    ``degree``      — scale degree (0 = root, can be negative).
    ``octave``      — octave offset relative to the generator's base octave
                      (0 = base, +1 = one octave up, -1 = one down).
    ``beat``        — start time in beats within the pattern (float).
    ``duration``    — note length in beats (float).
    ``vel_mult``    — velocity multiplier applied on top of base velocity (0–1+).
    """
    degree: int
    octave: int
    beat: float
    duration: float
    vel_mult: float = 1.0


@dataclass
class MelodyNote:
    """A single resolved note ready for MIDI output.  API-compatible with v1."""
    pitch: int        # MIDI note number 0-127
    start: float      # Start time in beats (absolute, from bar 0)
    duration: float   # Duration in beats
    velocity: int     # Velocity 0-127


# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------

# Every entry in a pattern is a PatternNote.
# Using explicit ``octave`` instead of degree=7 tricks makes patterns
# self-documenting and avoids silent wraparound surprises.

PATTERNS: Dict[str, List[PatternNote]] = {
    "anthem": [
        PatternNote(0, 0, 0.0, 0.50, 1.00),
        PatternNote(2, 0, 0.5, 0.50, 0.90),
        PatternNote(4, 0, 1.0, 1.00, 1.00),
        PatternNote(3, 0, 2.0, 0.50, 0.85),
        PatternNote(2, 0, 2.5, 0.50, 0.90),
        PatternNote(0, 0, 3.0, 1.00, 1.00),
    ],
    "anthem_b": [
        PatternNote(0, 0, 0.0, 0.50, 0.90),
        PatternNote(2, 0, 0.5, 0.50, 0.90),
        PatternNote(3, 0, 1.0, 0.50, 0.95),
        PatternNote(4, 0, 1.5, 1.50, 1.00),
        PatternNote(5, 0, 3.0, 1.00, 0.95),
    ],
    "call_response": [
        # Call (bar 1)
        PatternNote(4, 0, 0.0, 0.50, 1.00),
        PatternNote(3, 0, 0.5, 0.50, 0.90),
        PatternNote(2, 0, 1.0, 0.50, 0.85),
        PatternNote(0, 0, 1.5, 0.50, 0.90),
        # Response (bars 2–4)
        PatternNote(2, 0, 4.0, 0.50, 0.90),
        PatternNote(3, 0, 4.5, 0.50, 0.90),
        PatternNote(4, 0, 5.0, 1.00, 1.00),
        PatternNote(5, 0, 6.0, 2.00, 1.00),
    ],
    "driving": [
        PatternNote(0, 0, 0.00, 0.25, 0.90),
        PatternNote(0, 0, 0.25, 0.25, 0.70),
        PatternNote(2, 0, 0.50, 0.25, 0.90),
        PatternNote(2, 0, 0.75, 0.25, 0.70),
        PatternNote(3, 0, 1.00, 0.25, 1.00),
        PatternNote(2, 0, 1.25, 0.25, 0.80),
        PatternNote(0, 0, 1.50, 0.50, 0.90),
    ],
    "driving_b": [
        # Octave jump version — octave=1 replaces the old degree=7 hack
        PatternNote(0, 0, 0.00, 0.25, 0.85),
        PatternNote(2, 0, 0.25, 0.25, 0.85),
        PatternNote(4, 0, 0.50, 0.25, 0.90),
        PatternNote(0, 1, 0.75, 0.25, 1.00),  # ← one octave up, crystal clear
        PatternNote(4, 0, 1.00, 0.25, 0.90),
        PatternNote(2, 0, 1.25, 0.25, 0.85),
        PatternNote(0, 0, 1.50, 0.50, 0.85),
    ],
    "emotional": [
        PatternNote(0, 0, 0.0, 2.0, 1.00),
        PatternNote(4, 0, 2.0, 2.0, 0.90),
        PatternNote(5, 0, 4.0, 1.0, 1.00),
        PatternNote(4, 0, 5.0, 1.0, 0.90),
        PatternNote(2, 0, 6.0, 2.0, 0.85),
    ],
    "emotional_b": [
        PatternNote(5, 0,  0.0, 1.5, 1.00),
        PatternNote(4, 0,  1.5, 1.5, 0.95),
        PatternNote(2, 0,  3.0, 1.0, 0.90),
        PatternNote(0, 0,  4.0, 2.0, 0.85),
        PatternNote(6, -1, 6.0, 2.0, 0.80),  # below root via octave=-1, degree=6
    ],
    "arp_melody": [
        PatternNote(0, 0, 0.00, 0.25, 0.80),
        PatternNote(2, 0, 0.25, 0.25, 0.80),
        PatternNote(4, 0, 0.50, 0.25, 0.90),
        PatternNote(0, 1, 0.75, 0.25, 1.00),
        PatternNote(4, 0, 1.00, 0.25, 0.90),
        PatternNote(2, 0, 1.25, 0.25, 0.80),
        PatternNote(0, 0, 1.50, 0.50, 0.85),
    ],
    "sustained": [
        PatternNote(0, 0, 0.0, 4.0, 0.90),
        PatternNote(4, 0, 4.0, 4.0, 0.95),
    ],
    "staccato": [
        PatternNote(0, 0, 0.0, 0.125, 1.00),
        PatternNote(0, 0, 0.5, 0.125, 0.80),
        PatternNote(2, 0, 1.0, 0.125, 1.00),
        PatternNote(2, 0, 1.5, 0.125, 0.80),
        PatternNote(4, 0, 2.0, 0.125, 1.00),
        PatternNote(4, 0, 2.5, 0.125, 0.80),
        PatternNote(5, 0, 3.0, 0.125, 1.00),
        PatternNote(5, 0, 3.5, 0.125, 0.80),
    ],
    "climax": [
        PatternNote(0, 0, 0.0, 0.5, 0.70),
        PatternNote(2, 0, 0.5, 0.5, 0.75),
        PatternNote(3, 0, 1.0, 0.5, 0.80),
        PatternNote(4, 0, 1.5, 0.5, 0.85),
        PatternNote(5, 0, 2.0, 0.5, 0.90),
        PatternNote(6, 0, 2.5, 0.5, 0.95),
        PatternNote(0, 1, 3.0, 1.0, 1.00),  # climax = root an octave up
    ],
}

# Section → preferred patterns
SECTION_PATTERNS: Dict[str, List[str]] = {
    "intro":     ["arp_melody", "sustained"],
    "buildup":   ["driving", "driving_b", "staccato"],
    "breakdown": ["emotional", "emotional_b", "sustained"],
    "drop":      ["anthem", "anthem_b", "call_response"],
    "break":     ["driving", "arp_melody"],
    "outro":     ["arp_melody", "sustained", "emotional"],
}

# Scale intervals from root
SCALES: Dict[str, List[int]] = {
    "minor":          [0, 2, 3, 5, 7, 8, 10],
    "major":          [0, 2, 4, 5, 7, 9, 11],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor":  [0, 2, 3, 5, 7, 9, 11],
    "dorian":         [0, 2, 3, 5, 7, 9, 10],
    "phrygian":       [0, 1, 3, 5, 7, 8, 10],
}

# Full note-name → semitone map (no partial lookups needed)
NOTE_MAP: Dict[str, int] = {
    "C": 0,  "C#": 1,  "Db": 1,
    "D": 2,  "D#": 3,  "Eb": 3,
    "E": 4,
    "F": 5,  "F#": 6,  "Gb": 6,
    "G": 7,  "G#": 8,  "Ab": 8,
    "A": 9,  "A#": 10, "Bb": 10,
    "B": 11,
}


# ---------------------------------------------------------------------------
# Main generator class
# ---------------------------------------------------------------------------

class MelodyGenerator:
    """Pattern-based trance melody generator.

    Drop-in replacement for v1 MelodyGenerator.  All public method signatures
    are preserved; behaviour is improved throughout.
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        tempo: int = 138,
        config: Optional[Config] = None,
    ) -> None:
        self.key = key
        self.scale = scale
        self.tempo = tempo
        self.config = config if config is not None else DEFAULT_CONFIG
        self.root = self._note_to_midi(key, octave=4)
        self.scale_intervals = SCALES.get(scale, SCALES["minor"])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _note_to_midi(self, note: str, octave: int = 4) -> int:
        """Convert a note name (e.g. 'A', 'C#', 'Bb') to a MIDI number.

        Uses the full NOTE_MAP so 'Bb', 'A#', 'C#', etc. all resolve
        correctly without double-applying any modifier.
        """
        normalized = note[0].upper() + note[1:] if len(note) > 1 else note.upper()
        if normalized not in NOTE_MAP:
            raise ValueError(
                f"Unknown note name: '{note}'. "
                f"Valid values: {sorted(NOTE_MAP.keys())}"
            )
        return NOTE_MAP[normalized] + (octave + 1) * 12

    def _degree_to_midi(
        self,
        degree: int,
        octave_offset: int = 0,
        extra_octave: int = 0,
    ) -> int:
        """Resolve a scale degree (possibly negative or > len(scale)) to MIDI.

        ``octave_offset``  — caller-level shift (e.g. breakdown = -1 octave).
        ``extra_octave``   — per-note octave from PatternNote.octave field.
        """
        n = len(self.scale_intervals)
        # Normalise degree to [0, n) tracking how many octaves we wrapped
        wrapped_octaves = 0
        while degree < 0:
            degree += n
            wrapped_octaves -= 1
        while degree >= n:
            degree -= n
            wrapped_octaves += 1

        semitone = self.scale_intervals[degree]
        total_octave = wrapped_octaves + octave_offset + extra_octave
        return self.root + semitone + total_octave * 12

    def _humanize_velocity(
        self,
        base: int,
        beat_in_bar: float,
        rng: random.Random,
    ) -> int:
        """Apply beat emphasis and gaussian micro-variation to a velocity."""
        beat_emphasis = getattr(self.config, 'HUMANIZE_BEAT_EMPHASIS', 1.08)
        humanize_sigma = getattr(self.config, 'HUMANIZE_SIGMA', 3.0)
        emphasis = (
            beat_emphasis
            if beat_in_bar % 2 < 0.02   # beats 1 and 3 of 4/4
            else 1.0
        )
        jitter = rng.gauss(0, humanize_sigma)
        return max(40, min(127, int(base * emphasis + jitter)))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        bars: int = 8,
        pattern: str = "anthem",
        energy: float = 1.0,
        variation: float = 0.2,
        octave_offset: int = 0,
        phrase_length: int = 4,
        seed: Optional[int] = None,
    ) -> List[MelodyNote]:
        """Generate a melody for ``bars`` bars.

        Parameters
        ----------
        bars:
            Total bars to fill.
        pattern:
            Key from PATTERNS.  Falls back to 'anthem' with a warning if unknown.
        energy:
            0.0–1.0 scales all velocities.
        variation:
            0.0–1.0 probability of nudging a degree ±1 scale step each note.
        octave_offset:
            Shift the whole melody up/down N octaves.
        phrase_length:
            Every ``phrase_length`` bars the final note resolves to the root
            to give the melody a natural cadence.
        seed:
            If given, uses an isolated ``random.Random(seed)`` so this call
            never affects global random state.
        """
        rng = random.Random(seed)

        if pattern not in PATTERNS:
            warnings.warn(
                f"Unknown pattern '{pattern}', falling back to 'anthem'.",
                UserWarning,
                stacklevel=2,
            )
            pattern = "anthem"

        base_pattern = PATTERNS[pattern]

        # ---- fix: use math.ceil, not int(x/4)+1 -------------------------
        pattern_end = max(pn.beat + pn.duration for pn in base_pattern)
        pattern_bars = math.ceil(pattern_end / 4)
        if pattern_bars == 0:
            pattern_bars = 1

        notes: List[MelodyNote] = []
        current_bar = 0

        while current_bar < bars:
            bar_end = current_bar + pattern_bars
            is_phrase_boundary = (bar_end % phrase_length == 0)

            for i, pn in enumerate(base_pattern):
                beat = current_bar * 4 + pn.beat
                if beat >= bars * 4:
                    break

                # Resolve degree with optional variation
                degree = pn.degree
                if variation > 0 and rng.random() < variation:
                    degree += rng.choice([-1, 0, 0, 1])  # bias towards staying

                # On phrase boundaries, resolve the last note of the pattern to root
                is_last_in_pattern = (i == len(base_pattern) - 1)
                if is_phrase_boundary and is_last_in_pattern:
                    degree = 0
                    duration = pn.duration * 1.5  # held resolution
                else:
                    duration = pn.duration

                pitch = self._degree_to_midi(degree, octave_offset, pn.octave)
                pitch = max(0, min(127, pitch))

                default_vel = getattr(self.config, 'DEFAULT_VELOCITY', 100)
                base_vel = int(
                    default_vel * pn.vel_mult * (0.5 + 0.5 * energy)
                )
                velocity = self._humanize_velocity(base_vel, pn.beat % 4, rng)

                notes.append(MelodyNote(
                    pitch=pitch,
                    start=beat,
                    duration=duration,
                    velocity=velocity,
                ))

            current_bar += pattern_bars

        return notes

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        energy: float,
        variation: float = 0.15,
        seed: Optional[int] = None,
    ) -> List[MelodyNote]:
        """Choose an appropriate pattern for ``section_type`` and generate.

        Warns (rather than silently defaulting) on unknown section types.
        """
        key = section_type.lower()
        if key not in SECTION_PATTERNS:
            warnings.warn(
                f"Unknown section type '{section_type}', defaulting to 'drop'.",
                UserWarning,
                stacklevel=2,
            )
            key = "drop"

        rng = random.Random(seed)
        pattern = rng.choice(SECTION_PATTERNS[key])

        # Section-specific octave shaping
        octave_offset = getattr(self.config, "BREAKDOWN_OCTAVE_SHIFT", -1) \
            if key == "breakdown" else \
            getattr(self.config, "DROP_OCTAVE_SHIFT", 0)

        return self.generate_procedural(
            bars=bars,
            section_type=key,
            energy=energy,
            octave_offset=octave_offset,
            seed=seed,
        )

    def generate_procedural(
        self,
        bars: int = 8,
        section_type: str = "drop",
        energy: float = 1.0,
        octave_offset: int = 0,
        seed: Optional[int] = None,
    ) -> List[MelodyNote]:
        """Generate melody procedurally - different every time.

        Uses musical rules instead of fixed templates:
        - Contour shapes (arch, wave, rise, fall)
        - Weighted scale degree probabilities
        - Rhythmic variation based on energy
        - Phrase structure with cadences
        - Tension/release curves
        """
        rng = random.Random(seed)
        notes: List[MelodyNote] = []

        # Section-specific parameters
        if section_type == "breakdown":
            note_density = 0.3 + energy * 0.3  # Sparse, emotional
            prefer_long = True
            contour_types = ["arch", "descend", "wave"]
            rest_probability = 0.3
        elif section_type == "drop":
            note_density = 0.6 + energy * 0.4  # Dense, driving
            prefer_long = False
            contour_types = ["ascend", "arch", "zigzag", "wave"]
            rest_probability = 0.1
        else:
            note_density = 0.5
            prefer_long = False
            contour_types = ["wave", "arch"]
            rest_probability = 0.2

        # Scale degree weights (root, 2nd, 3rd, 4th, 5th, 6th, 7th)
        degree_weights = [3, 1, 2, 2, 3, 1, 1]  # Favor root and 5th

        # Generate phrase by phrase (4 bars each)
        phrase_length = 4
        current_beat = 0.0
        total_beats = bars * 4

        while current_beat < total_beats:
            phrase_end = min(current_beat + phrase_length * 4, total_beats)
            phrase_beats = phrase_end - current_beat

            # Choose contour for this phrase
            contour = rng.choice(contour_types)

            # Generate notes for this phrase
            phrase_notes = self._generate_phrase(
                rng=rng,
                start_beat=current_beat,
                phrase_beats=phrase_beats,
                contour=contour,
                note_density=note_density,
                prefer_long=prefer_long,
                rest_probability=rest_probability,
                degree_weights=degree_weights,
                energy=energy,
                octave_offset=octave_offset,
            )
            notes.extend(phrase_notes)

            current_beat = phrase_end

        return notes

    def _generate_phrase(
        self,
        rng: random.Random,
        start_beat: float,
        phrase_beats: float,
        contour: str,
        note_density: float,
        prefer_long: bool,
        rest_probability: float,
        degree_weights: List[int],
        energy: float,
        octave_offset: int,
    ) -> List[MelodyNote]:
        """Generate a single melodic phrase."""
        notes: List[MelodyNote] = []

        # Rhythm options based on density
        if prefer_long:
            durations = [2.0, 1.5, 1.0, 0.75]
            duration_weights = [3, 2, 2, 1]
        else:
            durations = [0.5, 0.25, 0.75, 1.0, 0.375]
            duration_weights = [3, 2, 2, 1, 1]

        # Start positions for notes (quantized)
        step = 0.25 if energy > 0.7 else 0.5

        current_beat = start_beat
        prev_degree = 0
        note_count = 0
        max_notes = int(phrase_beats * note_density * 2)

        while current_beat < start_beat + phrase_beats and note_count < max_notes:
            # Rest?
            if rng.random() < rest_probability and note_count > 0:
                current_beat += rng.choice([0.5, 1.0])
                continue

            # Calculate target degree based on contour and position
            progress = (current_beat - start_beat) / phrase_beats
            target_degree = self._contour_degree(contour, progress, rng)

            # Smooth movement from previous note
            if notes:
                step_size = rng.choice([-2, -1, -1, 0, 1, 1, 2])
                degree = prev_degree + step_size
                # Pull towards contour target
                if degree < target_degree - 2:
                    degree += 1
                elif degree > target_degree + 2:
                    degree -= 1
            else:
                degree = target_degree

            # Keep in reasonable range
            degree = max(-2, min(7, degree))

            # Resolve to root at phrase end
            if progress > 0.85:
                degree = rng.choice([0, 0, 0, 2, 4])  # Favor root

            # Duration
            dur = rng.choices(durations, weights=duration_weights)[0]
            # Don't overflow phrase
            dur = min(dur, start_beat + phrase_beats - current_beat)
            if dur < 0.125:
                break

            # Velocity with energy and contour shaping
            base_vel = int(80 + 40 * energy)
            # Accent on beat 1 and 3
            if current_beat % 2 < 0.1:
                base_vel = int(base_vel * 1.1)
            # Phrase peak
            if 0.4 < progress < 0.7:
                base_vel = int(base_vel * 1.05)

            velocity = self._humanize_velocity(base_vel, current_beat % 4, rng)

            # Create note
            pitch = self._degree_to_midi(degree, octave_offset, 0)
            pitch = max(36, min(96, pitch))  # Keep in reasonable range

            notes.append(MelodyNote(
                pitch=pitch,
                start=current_beat,
                duration=dur,
                velocity=velocity,
            ))

            prev_degree = degree
            current_beat += dur + rng.choice([0, 0, 0.25, 0.5]) * (1 - note_density)
            note_count += 1

        return notes

    def _contour_degree(self, contour: str, progress: float, rng: random.Random) -> int:
        """Get target scale degree based on contour shape and position."""
        if contour == "arch":
            # Rise then fall: 0 -> 4/5 -> 0
            if progress < 0.5:
                return int(progress * 10)  # 0 to 5
            else:
                return int((1 - progress) * 10)  # 5 to 0
        elif contour == "ascend":
            # Gradual rise: 0 -> 5/6
            return int(progress * 6) + rng.randint(-1, 1)
        elif contour == "descend":
            # Start high, fall: 5 -> 0
            return int((1 - progress) * 5) + rng.randint(-1, 1)
        elif contour == "wave":
            # Oscillate: sine-like
            import math
            return int(3 + 3 * math.sin(progress * math.pi * 2))
        elif contour == "zigzag":
            # Sharp ups and downs
            cycle = int(progress * 4) % 2
            return 5 if cycle == 0 else 1
        else:
            return rng.randint(0, 4)

    # ------------------------------------------------------------------
    # MIDI export
    # ------------------------------------------------------------------

    def to_midi_track(
        self,
        notes: List[MelodyNote],
        ticks_per_beat: Optional[int] = None,
        program: Optional[int] = None,
    ) -> MidiTrack:
        """Convert ``notes`` to a mido MidiTrack.

        Handles overlapping notes on the same pitch via a reference counter
        so early note-offs never cut a still-sounding instance.
        """
        tpb = ticks_per_beat if ticks_per_beat is not None else self.config.TICKS_PER_BEAT
        prog = program if program is not None else getattr(
            self.config, "LEAD_SYNTH_PROGRAM", 81
        )

        track = MidiTrack()
        track.append(Message("program_change", program=prog, time=0))

        if not notes:
            return track

        # Build raw on/off event list
        events: List[Tuple[str, int, int, int]] = []
        for note in notes:
            on_tick  = int(note.start * tpb)
            off_tick = int((note.start + note.duration) * tpb)
            events.append(("on",  on_tick,  note.pitch, note.velocity))
            events.append(("off", off_tick, note.pitch, 0))

        # Sort: ascending tick; note-off before note-on at the same tick
        events.sort(key=lambda e: (e[1], 0 if e[0] == "off" else 1))

        # Emit MIDI messages, guarding against premature note-off collisions
        active: Dict[int, int] = {}   # pitch → count of sounding instances
        current_tick = 0

        for event_type, tick, pitch, velocity in events:
            delta = tick - current_tick
            if event_type == "on":
                active[pitch] = active.get(pitch, 0) + 1
                track.append(Message("note_on", note=pitch, velocity=velocity, time=delta))
                current_tick = tick
            else:
                count = active.get(pitch, 0)
                if count > 1:
                    # Another instance is still sounding — skip this note-off
                    active[pitch] = count - 1
                else:
                    active[pitch] = 0
                    track.append(Message("note_off", note=pitch, velocity=0, time=delta))
                    current_tick = tick

        return track

    def to_midi_file(
        self,
        notes: List[MelodyNote],
        output_path: str,
        ticks_per_beat: Optional[int] = None,
    ) -> str:
        """Save ``notes`` to a MIDI file and return the path."""
        tpb = ticks_per_beat if ticks_per_beat is not None else self.config.TICKS_PER_BEAT
        mid = MidiFile(ticks_per_beat=tpb)
        mid.tracks.append(self.to_midi_track(notes, tpb))
        mid.save(output_path)
        return output_path


# ---------------------------------------------------------------------------
# Demo — preserved from v1 with minor cleanups
# ---------------------------------------------------------------------------

def demo() -> None:
    from pathlib import Path

    print("Melody Generator Demo (v2)")
    print("=" * 40)

    gen = MelodyGenerator(key="A", scale="minor", tempo=138)

    output_dir = Path(DEFAULT_CONFIG.OUTPUT_BASE) / "melody_demo"
    output_dir.mkdir(parents=True, exist_ok=True)

    for pattern_name in ["anthem", "emotional", "driving", "call_response"]:
        print(f"\nGenerating '{pattern_name}' …")
        notes = gen.generate(bars=8, pattern=pattern_name, energy=0.9, seed=42)
        print(f"  {len(notes)} notes generated")
        for n in notes[:5]:
            print(f"    beat {n.start:.2f}  pitch={n.pitch}  "
                  f"dur={n.duration:.3f}  vel={n.velocity}")
        if len(notes) > 5:
            print(f"    … and {len(notes) - 5} more")

        out = output_dir / f"melody_{pattern_name}.mid"
        gen.to_midi_file(notes, str(out))
        print(f"  → {out}")

    print("\n" + "=" * 40)
    print("Demo complete.")


if __name__ == "__main__":
    demo()