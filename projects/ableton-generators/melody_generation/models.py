"""
Core data models for production-grade melody generation.

These models represent musical concepts with full professional detail:
- Chords with extensions, alterations, and inversions
- Notes with timing, articulation, and expression
- Phrases with structural metadata
- Motifs with transformation history
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import ClassVar, Dict, List, Optional, Set, Tuple, FrozenSet


# =============================================================================
# ENUMS
# =============================================================================

class ChordQuality(Enum):
    """Chord quality types."""
    MAJOR = "maj"
    MINOR = "min"
    DIMINISHED = "dim"
    AUGMENTED = "aug"
    DOMINANT = "dom"
    HALF_DIMINISHED = "m7b5"
    SUSPENDED_2 = "sus2"
    SUSPENDED_4 = "sus4"
    POWER = "5"


class HarmonicFunction(Enum):
    """Harmonic function in tonal context."""
    TONIC = auto()           # I, i, vi, VI (stable, home)
    SUBDOMINANT = auto()     # IV, iv, ii, II (moving away)
    DOMINANT = auto()        # V, vii° (tension, wants to resolve)
    PREDOMINANT = auto()     # ii, IV leading to V
    CHROMATIC = auto()       # Borrowed, secondary dominants


class TensionLevel(Enum):
    """Musical tension level for a chord or note."""
    STABLE = 1        # Root, 5th - no tension
    MILD = 2          # 3rd, chord tones - slight color
    MODERATE = 3      # 7ths, 9ths - noticeable tension
    HIGH = 4          # 11ths, 13ths, alterations - strong pull
    CHROMATIC = 5     # Outside notes - maximum tension


class MotifTransform(Enum):
    """Types of motivic transformation."""
    ORIGINAL = auto()
    SEQUENCE = auto()          # Same shape, different starting pitch
    INVERSION = auto()         # Flip intervals
    RETROGRADE = auto()        # Reverse order
    RETROGRADE_INVERSION = auto()
    AUGMENTATION = auto()      # Double durations
    DIMINUTION = auto()        # Halve durations
    FRAGMENTATION = auto()     # Use only part of motif
    INTERVALLIC_EXPANSION = auto()   # Widen intervals
    INTERVALLIC_COMPRESSION = auto() # Narrow intervals
    RHYTHMIC_DISPLACEMENT = auto()   # Shift in time


class PhraseType(Enum):
    """Phrase structure types."""
    ANTECEDENT = auto()    # Question phrase (ends on non-tonic)
    CONSEQUENT = auto()    # Answer phrase (ends on tonic)
    SENTENCE = auto()      # 1+1+2 structure
    PERIOD = auto()        # Antecedent + Consequent
    CONTINUATION = auto()  # Development/extension
    CADENTIAL = auto()     # Resolution phrase


class CadenceType(Enum):
    """Cadence types for phrase endings."""
    AUTHENTIC = auto()       # V → I (strongest resolution)
    HALF = auto()            # ends on V (open, questioning)
    PLAGAL = auto()          # IV → I (amen cadence)
    DECEPTIVE = auto()       # V → vi (surprise)
    PHRYGIAN = auto()        # iv6 → V (dark, dramatic)


class ArticulationType(Enum):
    """Note articulation types."""
    LEGATO = auto()      # Connected, sustained
    STACCATO = auto()    # Short, detached
    ACCENT = auto()      # Emphasized
    TENUTO = auto()      # Held full value
    MARCATO = auto()     # Strong accent


class ContourShape(Enum):
    """Melodic contour shapes."""
    ARCH = auto()           # Rise then fall
    INVERSE_ARCH = auto()   # Fall then rise
    ASCENDING = auto()      # Overall upward
    DESCENDING = auto()     # Overall downward
    WAVE = auto()           # Oscillating
    PLATEAU = auto()        # Rise, sustain, fall
    ZIGZAG = auto()         # Sharp alternations
    STATIC = auto()         # Minimal movement


# =============================================================================
# NOTE & PITCH MODELS
# =============================================================================

@dataclass(frozen=True)
class PitchClass:
    """A pitch class (note name without octave)."""
    value: int  # 0-11 (C=0, C#=1, ... B=11)

    NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    FLAT_NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

    @classmethod
    def from_name(cls, name: str) -> 'PitchClass':
        """Parse pitch class from name like 'C', 'F#', 'Bb'."""
        name = name.strip()
        base = name[0].upper()
        base_values = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

        if base not in base_values:
            raise ValueError(f"Invalid note name: {name}")

        value = base_values[base]

        if len(name) > 1:
            modifier = name[1:]
            if modifier in ['#', '♯']:
                value = (value + 1) % 12
            elif modifier in ['b', '♭']:
                value = (value - 1) % 12
            elif modifier == '##':
                value = (value + 2) % 12
            elif modifier == 'bb':
                value = (value - 2) % 12

        return cls(value)

    def to_name(self, prefer_flat: bool = False) -> str:
        """Convert to note name."""
        names = self.FLAT_NAMES if prefer_flat else self.NAMES
        return names[self.value]

    def transpose(self, semitones: int) -> 'PitchClass':
        """Transpose by semitones."""
        return PitchClass((self.value + semitones) % 12)

    def interval_to(self, other: 'PitchClass') -> int:
        """Get interval in semitones to another pitch class (0-11)."""
        return (other.value - self.value) % 12


@dataclass(frozen=True)
class Pitch:
    """A specific pitch with octave."""
    pitch_class: PitchClass
    octave: int

    @property
    def midi_note(self) -> int:
        """Convert to MIDI note number."""
        return (self.octave + 1) * 12 + self.pitch_class.value

    @classmethod
    def from_midi(cls, midi_note: int) -> 'Pitch':
        """Create from MIDI note number."""
        octave = (midi_note // 12) - 1
        pitch_class = PitchClass(midi_note % 12)
        return cls(pitch_class, octave)

    @classmethod
    def from_name(cls, name: str) -> 'Pitch':
        """Parse from name like 'C4', 'F#5', 'Bb3'."""
        # Find where octave number starts
        for i, char in enumerate(name):
            if char.isdigit() or (char == '-' and i > 0):
                pitch_class = PitchClass.from_name(name[:i])
                octave = int(name[i:])
                return cls(pitch_class, octave)
        raise ValueError(f"Invalid pitch name (missing octave): {name}")

    def transpose(self, semitones: int) -> 'Pitch':
        """Transpose by semitones."""
        new_midi = self.midi_note + semitones
        return Pitch.from_midi(new_midi)

    def interval_to(self, other: 'Pitch') -> int:
        """Get interval in semitones to another pitch (signed)."""
        return other.midi_note - self.midi_note

    def to_name(self, prefer_flat: bool = False) -> str:
        """Convert to name like 'C4'."""
        return f"{self.pitch_class.to_name(prefer_flat)}{self.octave}"


# =============================================================================
# CHORD MODELS
# =============================================================================

@dataclass
class ChordTemplate:
    """Template defining intervals for a chord quality."""
    quality: ChordQuality
    intervals: Tuple[int, ...]  # Semitones from root

    # Standard chord interval templates (class-level constant)
    TEMPLATES: ClassVar[Dict[ChordQuality, Tuple[int, ...]]] = {
        ChordQuality.MAJOR: (0, 4, 7),
        ChordQuality.MINOR: (0, 3, 7),
        ChordQuality.DIMINISHED: (0, 3, 6),
        ChordQuality.AUGMENTED: (0, 4, 8),
        ChordQuality.DOMINANT: (0, 4, 7, 10),
        ChordQuality.HALF_DIMINISHED: (0, 3, 6, 10),
        ChordQuality.SUSPENDED_2: (0, 2, 7),
        ChordQuality.SUSPENDED_4: (0, 5, 7),
        ChordQuality.POWER: (0, 7),
    }


@dataclass
class Chord:
    """
    A fully-specified chord with root, quality, extensions, alterations, and bass.

    Examples:
        Am7 = Chord(root=A, quality=MINOR, extensions={7})
        Fmaj9/C = Chord(root=F, quality=MAJOR, extensions={7,9}, bass=C)
        G7#9b13 = Chord(root=G, quality=DOMINANT, extensions={9,13}, alterations={'#9', 'b13'})
    """
    root: PitchClass
    quality: ChordQuality = ChordQuality.MAJOR
    extensions: FrozenSet[int] = field(default_factory=frozenset)  # 7, 9, 11, 13
    alterations: FrozenSet[str] = field(default_factory=frozenset)  # '#5', 'b9', etc.
    bass: Optional[PitchClass] = None  # Slash chord bass note
    add_notes: FrozenSet[int] = field(default_factory=frozenset)  # add9, add11, etc.
    omit_notes: FrozenSet[int] = field(default_factory=frozenset)  # no3, no5, etc.

    @property
    def chord_tones(self) -> List[int]:
        """Get all chord tone intervals from root."""
        # Start with base triad/quality
        base = list(ChordTemplate.TEMPLATES.get(self.quality, (0, 4, 7)))

        # Add extensions
        extension_intervals = {7: 10, 9: 14, 11: 17, 13: 21}  # Default (dominant) intervals
        if self.quality == ChordQuality.MAJOR:
            extension_intervals[7] = 11  # Major 7
        elif self.quality in (ChordQuality.MINOR, ChordQuality.HALF_DIMINISHED):
            extension_intervals[7] = 10  # Minor 7

        for ext in self.extensions:
            if ext in extension_intervals:
                base.append(extension_intervals[ext])

        # Apply alterations
        alteration_map = {
            '#5': (7, 8), 'b5': (7, 6),
            '#9': (14, 15), 'b9': (14, 13),
            '#11': (17, 18), 'b13': (21, 20),
        }
        for alt in self.alterations:
            if alt in alteration_map:
                original, altered = alteration_map[alt]
                if original in base:
                    base.remove(original)
                base.append(altered)

        # Add notes
        for add in self.add_notes:
            if add in extension_intervals:
                interval = extension_intervals[add]
                if interval not in base:
                    base.append(interval)

        # Remove omitted notes (3=4 or 3, 5=7)
        omit_map = {3: [3, 4], 5: [7]}
        for omit in self.omit_notes:
            if omit in omit_map:
                for interval in omit_map[omit]:
                    if interval in base:
                        base.remove(interval)

        return sorted(set(base))

    @property
    def pitch_classes(self) -> List[PitchClass]:
        """Get all pitch classes in this chord."""
        return [self.root.transpose(interval) for interval in self.chord_tones]

    def contains_pitch(self, pitch: PitchClass) -> bool:
        """Check if pitch class is a chord tone."""
        return pitch in self.pitch_classes

    def tension_of_pitch(
        self, pitch: PitchClass, scale_pcs: Optional[FrozenSet[int]] = None,
    ) -> TensionLevel:
        """
        Get tension level of a pitch against this chord.

        Args:
            pitch: The pitch class to evaluate.
            scale_pcs: Optional frozenset of pitch-class integers (0-11)
                belonging to the current scale. When provided, scale membership
                is checked accurately. When omitted, falls back to the union of
                major and natural minor intervals (safe default).
        """
        interval = self.root.interval_to(pitch)

        # Chord tones
        chord_tone_intervals = set(self.chord_tones) | {i % 12 for i in self.chord_tones}
        if interval in chord_tone_intervals:
            if interval in (0, 7):  # Root or 5th
                return TensionLevel.STABLE
            elif interval in (3, 4):  # 3rd
                return TensionLevel.MILD
            else:  # Extensions
                return TensionLevel.MODERATE

        # Scale tones — use provided context or fall back to major ∪ minor union
        if scale_pcs is not None:
            if pitch.value in scale_pcs:
                return TensionLevel.MODERATE
        else:
            # Union of major + natural minor intervals from root
            default_scale = {0, 2, 3, 4, 5, 7, 8, 9, 10, 11}
            if interval in default_scale:
                return TensionLevel.MODERATE

        # Chromatic
        return TensionLevel.CHROMATIC

    def to_symbol(self) -> str:
        """Convert to chord symbol string."""
        symbol = self.root.to_name()

        quality_map = {
            ChordQuality.MAJOR: "",
            ChordQuality.MINOR: "m",
            ChordQuality.DIMINISHED: "dim",
            ChordQuality.AUGMENTED: "aug",
            ChordQuality.DOMINANT: "7",
            ChordQuality.HALF_DIMINISHED: "m7b5",
            ChordQuality.SUSPENDED_2: "sus2",
            ChordQuality.SUSPENDED_4: "sus4",
            ChordQuality.POWER: "5",
        }
        symbol += quality_map.get(self.quality, "")

        if 7 in self.extensions and self.quality not in (ChordQuality.DOMINANT, ChordQuality.HALF_DIMINISHED):
            if self.quality == ChordQuality.MAJOR:
                symbol += "maj7"
            else:
                symbol += "7"

        for ext in sorted(self.extensions):
            if ext != 7:
                symbol += str(ext)

        for alt in sorted(self.alterations):
            symbol += alt

        if self.bass and self.bass != self.root:
            symbol += f"/{self.bass.to_name()}"

        return symbol


@dataclass
class ChordEvent:
    """A chord at a specific time position."""
    chord: Chord
    start_beat: float
    duration_beats: float
    harmonic_function: HarmonicFunction = HarmonicFunction.TONIC
    tension_level: TensionLevel = TensionLevel.STABLE

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats


# =============================================================================
# NOTE EVENT MODELS
# =============================================================================

@dataclass
class NoteEvent:
    """
    A musical note event with full expression data.

    This is the output format for all generators - contains everything
    needed for MIDI export plus musical metadata.
    """
    pitch: Pitch
    start_beat: float
    duration_beats: float
    velocity: int = 100

    # Articulation and expression
    articulation: ArticulationType = ArticulationType.LEGATO

    # Micro-timing adjustments (in beats, small values like -0.02 to +0.02)
    timing_offset: float = 0.0

    # Musical context (for analysis/debugging)
    scale_degree: Optional[int] = None
    chord_tone: bool = False
    tension_level: TensionLevel = TensionLevel.STABLE

    # Transformation tracking
    source_motif_id: Optional[str] = None
    transform_applied: Optional[MotifTransform] = None

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats

    @property
    def actual_start(self) -> float:
        """Start beat with timing offset applied."""
        return self.start_beat + self.timing_offset

    def transpose(self, semitones: int) -> 'NoteEvent':
        """Create transposed copy."""
        return NoteEvent(
            pitch=self.pitch.transpose(semitones),
            start_beat=self.start_beat,
            duration_beats=self.duration_beats,
            velocity=self.velocity,
            articulation=self.articulation,
            timing_offset=self.timing_offset,
            scale_degree=self.scale_degree,
            chord_tone=self.chord_tone,
            tension_level=self.tension_level,
            source_motif_id=self.source_motif_id,
            transform_applied=self.transform_applied,
        )


# =============================================================================
# MOTIF MODELS
# =============================================================================

@dataclass
class MotifInterval:
    """An interval within a motif (relative pitch and rhythm)."""
    interval: int  # Semitones from previous note (or from root for first note)
    duration_beats: float
    velocity_factor: float = 1.0  # Relative to base velocity
    articulation: ArticulationType = ArticulationType.LEGATO


@dataclass
class Motif:
    """
    A melodic motif - a short musical idea that can be transformed.

    Stored as intervals rather than absolute pitches so it can be
    transposed and transformed easily.
    """
    id: str
    intervals: List[MotifInterval]
    total_duration: float = 0.0

    # Metadata
    genre_tags: List[str] = field(default_factory=list)
    energy_range: Tuple[float, float] = (0.0, 1.0)
    section_types: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.total_duration == 0.0:
            self.total_duration = sum(i.duration_beats for i in self.intervals)

    def to_notes(
        self,
        start_pitch: Pitch,
        start_beat: float,
        base_velocity: int = 100,
    ) -> List[NoteEvent]:
        """Render motif to concrete notes starting from given pitch and time."""
        notes = []
        current_pitch = start_pitch
        current_beat = start_beat

        for i, interval in enumerate(self.intervals):
            if i > 0:
                current_pitch = current_pitch.transpose(interval.interval)

            notes.append(NoteEvent(
                pitch=current_pitch,
                start_beat=current_beat,
                duration_beats=interval.duration_beats,
                velocity=int(base_velocity * interval.velocity_factor),
                articulation=interval.articulation,
                source_motif_id=self.id,
            ))
            current_beat += interval.duration_beats

        return notes


# =============================================================================
# PHRASE MODELS
# =============================================================================

@dataclass
class PhraseSpec:
    """Specification for a melodic phrase."""
    phrase_type: PhraseType
    start_beat: float
    duration_beats: float
    target_cadence: Optional[CadenceType] = None
    contour: ContourShape = ContourShape.ARCH
    energy: float = 0.7
    register_center: int = 72  # MIDI note for center of phrase range
    register_range: int = 12   # Semitones above/below center

    # Motif usage
    motif_ids: List[str] = field(default_factory=list)  # Motifs to use
    transform_sequence: List[MotifTransform] = field(default_factory=list)

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats


@dataclass
class Phrase:
    """A complete melodic phrase with notes."""
    spec: PhraseSpec
    notes: List[NoteEvent] = field(default_factory=list)

    # Analysis results
    actual_contour: Optional[ContourShape] = None
    climax_beat: Optional[float] = None
    resolution_achieved: bool = False


# =============================================================================
# TRACK CONTEXT MODELS
# =============================================================================

@dataclass
class TrackContext:
    """
    Context about other tracks for inter-track coordination.

    The lead generator receives this to know what's happening
    in bass, arp, chords, etc.
    """
    # Chord progression with timing
    chord_events: List[ChordEvent] = field(default_factory=list)

    # Other track note events (for collision detection, interlocking)
    bass_notes: List[NoteEvent] = field(default_factory=list)
    arp_notes: List[NoteEvent] = field(default_factory=list)
    chord_notes: List[NoteEvent] = field(default_factory=list)

    # Kick pattern for rhythmic reference
    kick_beats: List[float] = field(default_factory=list)

    # Register allocations (MIDI note ranges)
    bass_register: Tuple[int, int] = (28, 55)    # E1 to G3
    arp_register: Tuple[int, int] = (48, 79)     # C3 to G5
    lead_register: Tuple[int, int] = (60, 96)    # C4 to C7
    pad_register: Tuple[int, int] = (48, 84)     # C3 to C6

    def chord_at_beat(self, beat: float) -> Optional[ChordEvent]:
        """Get the chord playing at a specific beat."""
        for event in self.chord_events:
            if event.start_beat <= beat < event.end_beat:
                return event
        return None

    def notes_at_beat(self, beat: float, tolerance: float = 0.125) -> List[NoteEvent]:
        """Get all notes from other tracks sounding at a beat."""
        all_notes = self.bass_notes + self.arp_notes + self.chord_notes
        return [
            n for n in all_notes
            if n.start_beat - tolerance <= beat < n.end_beat + tolerance
        ]

    def pitches_at_beat(self, beat: float) -> Set[PitchClass]:
        """Get all pitch classes sounding at a beat."""
        notes = self.notes_at_beat(beat)
        return {n.pitch.pitch_class for n in notes}


# =============================================================================
# GENERATION CONFIG
# =============================================================================

@dataclass
class MelodyGenConfig:
    """Configuration for melody generation."""
    # Musical parameters
    key: PitchClass = field(default_factory=lambda: PitchClass.from_name('A'))
    scale_type: str = "minor"
    tempo: int = 138

    # Generation style
    genre: str = "trance"
    subgenre: str = "uplifting"
    energy: float = 0.8

    # Phrase structure
    default_phrase_length: int = 4  # bars
    prefer_motif_development: bool = True

    # Constraints
    min_note_duration: float = 0.125  # 32nd note
    max_note_duration: float = 4.0    # whole note
    velocity_range: Tuple[int, int] = (60, 120)

    # Humanization
    timing_variance: float = 0.02   # Max timing offset in beats
    velocity_variance: float = 0.1  # Max velocity variance (0-1)

    # Inter-track
    avoid_doubling: bool = True     # Avoid same pitch as other tracks
    prefer_contrary_motion: bool = True
