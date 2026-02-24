"""
Harmonic Analysis Engine

Production-grade harmonic analysis and chord processing:
- Full chord symbol parsing (Am7b5, Fmaj9/C, Gsus4#11)
- Harmonic function analysis (tonic, subdominant, dominant)
- Voice leading computation between chords
- Tension analysis and resolution suggestions
- Common tone detection
- Modal context awareness
- Key detection (Krumhansl-Schmuckler via music21)
- Non-chord-tone classification (passing, neighbor, suspension, appoggiatura)
- Interval consonance/dissonance scoring
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from music21 import scale as m21scale
from music21 import pitch as m21pitch
from music21 import interval as m21interval
from music21 import key as m21key

from .models import (
    Chord, ChordQuality, ChordEvent, ChordTemplate,
    PitchClass, Pitch, HarmonicFunction, TensionLevel,
    NoteEvent
)


# =============================================================================
# MUSIC21-BACKED SCALE SYSTEM
# =============================================================================

def _m21_pitch_name(pc: PitchClass) -> str:
    """Convert our PitchClass to a music21-compatible pitch name."""
    # music21 prefers flats for certain pitch classes to avoid double-sharps
    return pc.to_name(prefer_flat=False)


def _build_scale_object(tonic_name: str, scale_name: str) -> m21scale.ConcreteScale:
    """Build a music21 scale object from tonic name and scale type string."""
    _SCALE_CLASSES: Dict[str, type] = {
        "major": m21scale.MajorScale,
        "ionian": m21scale.MajorScale,
        "minor": m21scale.MinorScale,
        "aeolian": m21scale.MinorScale,
        "dorian": m21scale.DorianScale,
        "phrygian": m21scale.PhrygianScale,
        "lydian": m21scale.LydianScale,
        "mixolydian": m21scale.MixolydianScale,
        "locrian": m21scale.LocrianScale,
        "harmonic_minor": m21scale.HarmonicMinorScale,
        "melodic_minor": m21scale.MelodicMinorScale,
        "whole_tone": m21scale.WholeToneScale,
        "chromatic": m21scale.ChromaticScale,
    }
    cls = _SCALE_CLASSES.get(scale_name)
    if cls is not None:
        return cls(m21pitch.Pitch(tonic_name))
    # Pentatonic, blues, diminished, augmented — not natively in music21 as
    # named classes; fall back to the legacy interval tuples.
    return None


def _intervals_from_m21_scale(sc: m21scale.ConcreteScale) -> Tuple[int, ...]:
    """Extract semitone intervals (relative to tonic) from a music21 scale."""
    # Use octave-qualified pitches to ensure getPitches returns the full span
    tonic_oct = m21pitch.Pitch(sc.tonic.name + '4')
    upper_oct = m21pitch.Pitch(sc.tonic.name + '5')
    tonic_midi = tonic_oct.midi
    pitches = sc.getPitches(tonic_oct, upper_oct)
    # Exclude the upper octave duplicate
    intervals = []
    for p in pitches:
        semitones = p.midi - tonic_midi
        if 0 <= semitones < 12:
            intervals.append(semitones)
    return tuple(sorted(set(intervals)))


# Legacy fallback for scales music21 doesn't provide named classes for
_LEGACY_SCALE_INTERVALS: Dict[str, Tuple[int, ...]] = {
    "major_pentatonic": (0, 2, 4, 7, 9),
    "minor_pentatonic": (0, 3, 5, 7, 10),
    "blues": (0, 3, 5, 6, 7, 10),
    "diminished": (0, 2, 3, 5, 6, 8, 9, 11),
    "augmented": (0, 3, 4, 7, 8, 11),
}


def get_scale_intervals(tonic_name: str, scale_name: str) -> Tuple[int, ...]:
    """
    Get semitone intervals for any scale type.

    Uses music21 for all standard scales, falls back to hardcoded tuples
    only for exotic scales that music21 doesn't natively support.
    """
    sc = _build_scale_object(tonic_name, scale_name)
    if sc is not None:
        return _intervals_from_m21_scale(sc)
    # Fallback for exotic scales
    if scale_name in _LEGACY_SCALE_INTERVALS:
        return _LEGACY_SCALE_INTERVALS[scale_name]
    # Unknown scale — default to natural minor
    return _intervals_from_m21_scale(m21scale.MinorScale(m21pitch.Pitch(tonic_name)))


# Backwards-compatible constant: pre-computed intervals for all supported
# scales rooted on C. Downstream code that imports SCALE_INTERVALS will
# continue to work, but new code should use get_scale_intervals() instead.
SCALE_INTERVALS: Dict[str, Tuple[int, ...]] = {}
for _name in [
    "major", "ionian", "dorian", "phrygian", "lydian", "mixolydian",
    "minor", "aeolian", "locrian", "harmonic_minor", "melodic_minor",
    "major_pentatonic", "minor_pentatonic", "blues", "whole_tone",
    "diminished", "augmented",
]:
    SCALE_INTERVALS[_name] = get_scale_intervals("C", _name)


# Diatonic chord functions by scale degree (1-indexed)
# Maps scale degree to harmonic function in major key
MAJOR_KEY_FUNCTIONS: Dict[int, HarmonicFunction] = {
    1: HarmonicFunction.TONIC,          # I
    2: HarmonicFunction.PREDOMINANT,    # ii
    3: HarmonicFunction.TONIC,          # iii (weak tonic)
    4: HarmonicFunction.SUBDOMINANT,    # IV
    5: HarmonicFunction.DOMINANT,       # V
    6: HarmonicFunction.TONIC,          # vi (relative minor tonic)
    7: HarmonicFunction.DOMINANT,       # vii° (leading tone)
}

MINOR_KEY_FUNCTIONS: Dict[int, HarmonicFunction] = {
    1: HarmonicFunction.TONIC,          # i
    2: HarmonicFunction.PREDOMINANT,    # ii°
    3: HarmonicFunction.TONIC,          # III (relative major)
    4: HarmonicFunction.SUBDOMINANT,    # iv
    5: HarmonicFunction.DOMINANT,       # v or V
    6: HarmonicFunction.SUBDOMINANT,    # VI
    7: HarmonicFunction.DOMINANT,       # VII or vii°
}


# =============================================================================
# CHORD PARSER
# =============================================================================

class ChordParser:
    """
    Parse chord symbols into Chord objects.

    Handles complex symbols like:
    - Basic: C, Am, G7, Fmaj7
    - Extensions: Am9, Cmaj13, G7#9
    - Alterations: C7b5, G7#5#9
    - Suspensions: Csus4, Dsus2
    - Slash chords: Am/E, C/G
    - Add chords: Cadd9, Am(add11)
    - Diminished/Augmented: Cdim7, Gaug
    """

    # Regex patterns for parsing
    ROOT_PATTERN = r'^([A-G][#b]?)'
    QUALITY_PATTERNS = {
        r'maj': ChordQuality.MAJOR,
        r'min|m(?!aj)': ChordQuality.MINOR,
        r'dim|°': ChordQuality.DIMINISHED,
        r'aug|\+': ChordQuality.AUGMENTED,
        r'sus2': ChordQuality.SUSPENDED_2,
        r'sus4|sus': ChordQuality.SUSPENDED_4,
        r'm7b5|ø': ChordQuality.HALF_DIMINISHED,
        r'5': ChordQuality.POWER,
    }

    @classmethod
    def parse(cls, symbol: str) -> Chord:
        """Parse a chord symbol string into a Chord object."""
        original = symbol
        symbol = symbol.strip()

        # Handle slash chord bass note first
        bass = None
        if '/' in symbol:
            parts = symbol.split('/')
            symbol = parts[0]
            bass = PitchClass.from_name(parts[1])

        # Extract root
        root_match = re.match(cls.ROOT_PATTERN, symbol)
        if not root_match:
            raise ValueError(f"Cannot parse chord root from: {original}")

        root = PitchClass.from_name(root_match.group(1))
        remainder = symbol[root_match.end():]

        # Detect quality
        quality = ChordQuality.MAJOR  # Default
        for pattern, q in cls.QUALITY_PATTERNS.items():
            match = re.search(pattern, remainder, re.IGNORECASE)
            if match:
                quality = q
                remainder = remainder[:match.start()] + remainder[match.end():]
                break

        # Detect extensions (7, 9, 11, 13)
        extensions: Set[int] = set()
        alterations: Set[str] = set()
        add_notes: Set[int] = set()

        # Check for dominant 7 implied by just "7"
        if re.search(r'(?<![a-z])7(?![0-9])', remainder):
            if quality == ChordQuality.MAJOR:
                # If we see "7" without "maj", it's dominant
                if not re.search(r'maj7', symbol, re.IGNORECASE):
                    quality = ChordQuality.DOMINANT
            extensions.add(7)
            remainder = re.sub(r'(?<![a-z])7(?![0-9])', '', remainder)

        # Check for maj7
        if re.search(r'maj7', symbol, re.IGNORECASE):
            extensions.add(7)

        # Check for higher extensions
        for ext in [9, 11, 13]:
            if re.search(rf'(?<![#b]){ext}', remainder):
                extensions.add(ext)
                # 9 implies 7, 11 implies 9+7, 13 implies 11+9+7
                if ext >= 9:
                    extensions.add(7)
                if ext >= 11:
                    extensions.add(9)
                if ext >= 13:
                    extensions.add(11)

        # Check for alterations (#5, b5, #9, b9, #11, b13)
        alteration_patterns = [
            (r'#5|\+5', '#5'),
            (r'b5|-5', 'b5'),
            (r'#9', '#9'),
            (r'b9', 'b9'),
            (r'#11', '#11'),
            (r'b13', 'b13'),
        ]
        for pattern, alt in alteration_patterns:
            if re.search(pattern, remainder):
                alterations.add(alt)

        # Check for add notes
        add_match = re.search(r'add(\d+)', remainder, re.IGNORECASE)
        if add_match:
            add_notes.add(int(add_match.group(1)))

        return Chord(
            root=root,
            quality=quality,
            extensions=frozenset(extensions),
            alterations=frozenset(alterations),
            bass=bass,
            add_notes=frozenset(add_notes),
        )

    @classmethod
    def parse_progression(cls, symbols: List[str]) -> List[Chord]:
        """Parse a list of chord symbols."""
        return [cls.parse(s) for s in symbols]


# =============================================================================
# HARMONIC ANALYZER
# =============================================================================

@dataclass
class VoiceLeadingResult:
    """Result of voice leading analysis between two chords."""
    common_tones: List[PitchClass]
    movements: List[Tuple[PitchClass, PitchClass, int]]  # (from, to, semitones)
    total_movement: int  # Sum of all semitone movements
    smoothness_score: float  # 0-1, higher is smoother
    contrary_motion_possible: bool


@dataclass
class HarmonicAnalysis:
    """Analysis of a chord in harmonic context."""
    chord: Chord
    function: HarmonicFunction
    tension_level: TensionLevel
    scale_degree: int  # 1-7
    is_diatonic: bool
    borrowed_from: Optional[str] = None  # e.g., "parallel minor"
    secondary_dominant_of: Optional[int] = None  # e.g., 5 means V/V


class HarmonicEngine:
    """
    Main harmonic analysis engine.

    Provides:
    - Chord parsing and creation
    - Harmonic function analysis
    - Voice leading computation
    - Tension/resolution analysis
    - Scale/mode context
    - Key detection (Krumhansl-Schmuckler via music21)
    - Non-chord-tone classification
    - Interval consonance/dissonance scoring
    """

    def __init__(
        self,
        key: PitchClass,
        scale: str = "minor",
    ):
        self.key = key
        self.scale = scale

        # Build music21 scale object (if available for this scale type)
        tonic_name = _m21_pitch_name(key)
        self._m21_scale = _build_scale_object(tonic_name, scale)

        # Compute intervals — music21-backed when possible, legacy fallback otherwise
        self.scale_intervals = get_scale_intervals(tonic_name, scale)
        self._build_scale_notes()
        self._build_diatonic_chords()

    def _build_scale_notes(self):
        """Build the scale notes for current key."""
        self.scale_notes = [
            self.key.transpose(interval)
            for interval in self.scale_intervals
        ]

    def _build_diatonic_chords(self):
        """Build diatonic chords for scale degree analysis."""
        # Simplified: build triads on each scale degree
        self.diatonic_roots = {
            note.value: i + 1
            for i, note in enumerate(self.scale_notes)
        }

    def get_scale_degree(self, pitch_class: PitchClass) -> Optional[int]:
        """
        Get the scale degree (1-indexed) of a pitch class, or None if chromatic.

        Uses music21 when available for accurate enharmonic handling.
        """
        if self._m21_scale is not None:
            m21p = m21pitch.Pitch(pitch_class.to_name())
            degree = self._m21_scale.getScaleDegreeFromPitch(m21p)
            return degree  # Returns None if not in scale
        # Fallback
        return self.diatonic_roots.get(pitch_class.value)

    def is_in_scale(self, pitch_class: PitchClass) -> bool:
        """Check if a pitch class belongs to the current scale."""
        return self.get_scale_degree(pitch_class) is not None

    def classify_interval(self, p1: Pitch, p2: Pitch) -> dict:
        """
        Classify the interval between two pitches using music21.

        Returns dict with:
            name: e.g. 'M3', 'P5', 'A4'
            semitones: integer distance
            is_consonant: bool
            quality: 'perfect', 'major', 'minor', 'augmented', 'diminished'
        """
        m21p1 = m21pitch.Pitch(p1.to_name())
        m21p2 = m21pitch.Pitch(p2.to_name())
        ivl = m21interval.Interval(m21p1, m21p2)
        return {
            "name": ivl.directedName,
            "simple_name": ivl.directedSimpleName,
            "semitones": ivl.semitones,
            "is_consonant": ivl.isConsonant(),
            "quality": ivl.specifier if hasattr(ivl, 'specifier') else None,
        }

    def classify_non_chord_tone(
        self,
        note: NoteEvent,
        prev_note: Optional[NoteEvent],
        next_note: Optional[NoteEvent],
        chord: Chord,
    ) -> str:
        """
        Classify a non-chord tone by its melodic context.

        Returns one of:
            'chord_tone', 'passing', 'neighbor', 'suspension',
            'appoggiatura', 'escape', 'anticipation', 'chromatic'
        """
        pc = note.pitch.pitch_class
        if chord.contains_pitch(pc):
            return "chord_tone"

        prev_midi = prev_note.pitch.midi_note if prev_note else None
        next_midi = next_note.pitch.midi_note if next_note else None
        curr_midi = note.pitch.midi_note

        # Need both neighbors for passing/neighbor classification
        if prev_midi is not None and next_midi is not None:
            prev_step = curr_midi - prev_midi
            next_step = next_midi - curr_midi

            # Passing tone: stepwise approach AND departure in same direction
            if (abs(prev_step) <= 2 and abs(next_step) <= 2
                    and prev_step != 0 and next_step != 0
                    and (prev_step > 0) == (next_step > 0)):
                return "passing"

            # Neighbor tone: stepwise departure returning to original pitch area
            if (abs(prev_step) <= 2 and abs(next_step) <= 2
                    and prev_step != 0 and next_step != 0
                    and (prev_step > 0) != (next_step > 0)):
                return "neighbor"

            # Escape tone: stepwise approach, leap away
            if abs(prev_step) <= 2 and abs(next_step) > 2:
                return "escape"

        # Appoggiatura: leap to, stepwise resolution
        if prev_midi is not None and next_midi is not None:
            if abs(prev_midi - curr_midi) > 2 and abs(next_midi - curr_midi) <= 2:
                if next_note and chord.contains_pitch(next_note.pitch.pitch_class):
                    return "appoggiatura"

        # Anticipation: same pitch as next chord tone, short duration
        if next_note and next_note.pitch.pitch_class == pc:
            return "anticipation"

        # Suspension: held from previous, resolves down by step
        if prev_note and prev_note.pitch.pitch_class == pc:
            if next_midi is not None and (curr_midi - next_midi) in (1, 2):
                return "suspension"

        # Check if it's at least a scale tone
        if self.is_in_scale(pc):
            return "passing"  # Default for in-scale NCTs without clear context

        return "chromatic"

    @staticmethod
    def detect_key(midi_path: str) -> Optional[str]:
        """
        Detect the key of a MIDI file using Krumhansl-Schmuckler algorithm.

        Returns a string like 'A minor' or 'C major', or None on failure.
        """
        try:
            from music21 import converter
            score = converter.parse(midi_path)
            result = score.analyze('key')
            return str(result)
        except Exception:
            return None

    def parse_chord(self, symbol: str) -> Chord:
        """Parse a chord symbol."""
        return ChordParser.parse(symbol)

    def parse_progression(
        self,
        symbols: List[str],
        bars_per_chord: float = 2.0,
        start_beat: float = 0.0,
    ) -> List[ChordEvent]:
        """Parse chord progression with timing."""
        events = []
        current_beat = start_beat

        for symbol in symbols:
            chord = self.parse_chord(symbol)
            analysis = self.analyze_chord(chord)

            events.append(ChordEvent(
                chord=chord,
                start_beat=current_beat,
                duration_beats=bars_per_chord * 4,  # 4 beats per bar
                harmonic_function=analysis.function,
                tension_level=analysis.tension_level,
            ))
            current_beat += bars_per_chord * 4

        return events

    def analyze_chord(self, chord: Chord) -> HarmonicAnalysis:
        """Analyze a chord's harmonic function in current key."""
        # Find scale degree
        root_value = chord.root.value
        scale_degree = self.diatonic_roots.get(root_value, 0)

        # Determine if diatonic
        is_diatonic = chord.root in self.scale_notes

        # Determine function based on scale degree
        if self.scale in ("minor", "aeolian", "harmonic_minor", "melodic_minor"):
            func_map = MINOR_KEY_FUNCTIONS
        else:
            func_map = MAJOR_KEY_FUNCTIONS

        function = func_map.get(scale_degree, HarmonicFunction.CHROMATIC)

        # Override for chromatic chords
        if not is_diatonic:
            function = HarmonicFunction.CHROMATIC

        # Check for secondary dominants
        secondary_target = None
        if chord.quality == ChordQuality.DOMINANT and not is_diatonic:
            # Check if this could be V of another scale degree
            potential_target = (root_value + 7) % 12  # Perfect 5th up
            if potential_target in self.diatonic_roots:
                secondary_target = self.diatonic_roots[potential_target]
                function = HarmonicFunction.DOMINANT

        # Determine tension level
        if function == HarmonicFunction.TONIC:
            tension = TensionLevel.STABLE
        elif function == HarmonicFunction.SUBDOMINANT:
            tension = TensionLevel.MILD
        elif function == HarmonicFunction.DOMINANT:
            tension = TensionLevel.HIGH
        else:
            tension = TensionLevel.MODERATE

        # Increase tension for extended/altered chords
        if chord.extensions or chord.alterations:
            if tension.value < TensionLevel.HIGH.value:
                tension = TensionLevel(tension.value + 1)

        return HarmonicAnalysis(
            chord=chord,
            function=function,
            tension_level=tension,
            scale_degree=scale_degree if scale_degree > 0 else 0,
            is_diatonic=is_diatonic,
            secondary_dominant_of=secondary_target,
        )

    def analyze_voice_leading(
        self,
        chord1: Chord,
        chord2: Chord,
    ) -> VoiceLeadingResult:
        """Analyze voice leading possibilities between two chords."""
        tones1 = chord1.pitch_classes
        tones2 = chord2.pitch_classes

        # Find common tones
        common = [t for t in tones1 if t in tones2]

        # Find voice movements (simplified: closest movement for each voice)
        movements = []
        remaining2 = [t for t in tones2 if t not in common]

        for tone1 in tones1:
            if tone1 in common:
                continue

            # Find closest target
            if remaining2:
                closest = min(
                    remaining2,
                    key=lambda t: min(
                        abs(tone1.interval_to(t)),
                        abs(12 - tone1.interval_to(t))
                    )
                )
                interval = tone1.interval_to(closest)
                if interval > 6:
                    interval = interval - 12  # Use smaller interval

                movements.append((tone1, closest, interval))
                remaining2.remove(closest)

        # Calculate total movement
        total = sum(abs(m[2]) for m in movements)

        # Calculate smoothness (inverse of total movement, normalized)
        max_movement = len(movements) * 6  # Max semitones per voice
        smoothness = 1.0 - (total / max_movement) if max_movement > 0 else 1.0

        # Check if contrary motion is naturally possible
        contrary = len(movements) >= 2 and any(m[2] > 0 for m in movements) and any(m[2] < 0 for m in movements)

        return VoiceLeadingResult(
            common_tones=common,
            movements=movements,
            total_movement=total,
            smoothness_score=max(0, smoothness),
            contrary_motion_possible=contrary,
        )

    def get_chord_tones_in_register(
        self,
        chord: Chord,
        low: int = 48,
        high: int = 84,
    ) -> List[Pitch]:
        """Get all chord tones within a MIDI note range."""
        tones = []
        for pitch_class in chord.pitch_classes:
            # Find all octaves within range
            for octave in range(-1, 10):
                pitch = Pitch(pitch_class, octave)
                if low <= pitch.midi_note <= high:
                    tones.append(pitch)
        return sorted(tones, key=lambda p: p.midi_note)

    def get_scale_notes_in_register(
        self,
        low: int = 48,
        high: int = 84,
    ) -> List[Pitch]:
        """Get all scale notes within a MIDI note range."""
        notes = []
        for pitch_class in self.scale_notes:
            for octave in range(-1, 10):
                pitch = Pitch(pitch_class, octave)
                if low <= pitch.midi_note <= high:
                    notes.append(pitch)
        return sorted(notes, key=lambda p: p.midi_note)

    def get_approach_notes(
        self,
        target: Pitch,
        chord: Chord,
        approach_type: str = "chromatic",
    ) -> List[Pitch]:
        """
        Get approach notes to a target pitch.

        Types:
        - chromatic: half-step below and above
        - scalar: scale tones leading to target
        - arpeggio: chord tones leading to target
        """
        approaches = []

        if approach_type == "chromatic":
            approaches = [
                target.transpose(-1),  # Half step below
                target.transpose(1),   # Half step above
            ]
        elif approach_type == "scalar":
            # Find adjacent scale tones
            scale_pitches = self.get_scale_notes_in_register(
                target.midi_note - 4,
                target.midi_note + 4,
            )
            approaches = [p for p in scale_pitches if p.midi_note != target.midi_note]
        elif approach_type == "arpeggio":
            chord_pitches = self.get_chord_tones_in_register(
                chord,
                target.midi_note - 12,
                target.midi_note + 12,
            )
            approaches = [p for p in chord_pitches if p.midi_note != target.midi_note]

        return approaches

    @property
    def scale_pitch_classes(self) -> FrozenSet[int]:
        """Get frozenset of pitch-class integers (0-11) in the current scale."""
        return frozenset(pc.value for pc in self.scale_notes)

    def tension_of_pitch_in_context(
        self,
        pitch: Pitch,
        chord: Chord,
    ) -> TensionLevel:
        """Get tension level of a pitch against chord and scale."""
        # Check if chord tone — pass real scale context for accurate fallback
        if chord.contains_pitch(pitch.pitch_class):
            return chord.tension_of_pitch(pitch.pitch_class, self.scale_pitch_classes)

        # Check if scale tone (using music21-backed membership when available)
        if self.is_in_scale(pitch.pitch_class):
            return TensionLevel.MODERATE

        # Chromatic
        return TensionLevel.CHROMATIC

    def suggest_resolution(
        self,
        tension_pitch: Pitch,
        chord: Chord,
    ) -> Optional[Pitch]:
        """Suggest a resolution pitch for a tension note."""
        if self.tension_of_pitch_in_context(tension_pitch, chord) == TensionLevel.STABLE:
            return None  # Already resolved

        # Find closest chord tone
        chord_tones = self.get_chord_tones_in_register(
            chord,
            tension_pitch.midi_note - 3,
            tension_pitch.midi_note + 3,
        )

        if not chord_tones:
            return None

        # Prefer step-wise resolution
        return min(
            chord_tones,
            key=lambda p: abs(p.midi_note - tension_pitch.midi_note)
        )

    def get_available_tensions(
        self,
        chord: Chord,
        register: Tuple[int, int] = (60, 84),
    ) -> List[Tuple[Pitch, TensionLevel]]:
        """Get available tension notes for a chord with their tension levels."""
        tensions = []
        low, high = register

        for octave in range(-1, 10):
            for pitch_class in self.scale_notes:
                pitch = Pitch(pitch_class, octave)
                if low <= pitch.midi_note <= high:
                    tension = self.tension_of_pitch_in_context(pitch, chord)
                    if tension != TensionLevel.STABLE:
                        tensions.append((pitch, tension))

        return tensions


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def parse_chord(symbol: str) -> Chord:
    """Quick chord parsing without engine."""
    return ChordParser.parse(symbol)


def parse_progression(
    symbols: List[str],
    key: str = "A",
    scale: str = "minor",
    bars_per_chord: float = 2.0,
) -> List[ChordEvent]:
    """Quick progression parsing."""
    engine = HarmonicEngine(PitchClass.from_name(key), scale)
    return engine.parse_progression(symbols, bars_per_chord)


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate harmonic engine capabilities."""
    print("Harmonic Engine Demo")
    print("=" * 50)

    # Initialize engine in A minor
    engine = HarmonicEngine(PitchClass.from_name("A"), "minor")

    # Parse various chord symbols
    test_chords = ["Am", "F", "C", "G", "Am7", "Fmaj9", "Dm7b5", "E7#9", "Am/E"]
    print("\nChord Parsing:")
    for symbol in test_chords:
        chord = engine.parse_chord(symbol)
        analysis = engine.analyze_chord(chord)
        print(f"  {symbol:10} → {chord.to_symbol():10} "
              f"Function: {analysis.function.name:12} "
              f"Tension: {analysis.tension_level.name}")

    # Test progression
    print("\nProgression Analysis:")
    progression = ["Am", "F", "C", "G"]
    events = engine.parse_progression(progression, bars_per_chord=2.0)
    for event in events:
        print(f"  Beat {event.start_beat:5.1f}: {event.chord.to_symbol():6} "
              f"({event.harmonic_function.name})")

    # Voice leading
    print("\nVoice Leading (Am → F):")
    vl = engine.analyze_voice_leading(
        engine.parse_chord("Am"),
        engine.parse_chord("F")
    )
    print(f"  Common tones: {[t.to_name() for t in vl.common_tones]}")
    print(f"  Movements: {[(m[0].to_name(), m[1].to_name(), m[2]) for m in vl.movements]}")
    print(f"  Smoothness: {vl.smoothness_score:.2f}")

    # Chord tones in register
    print("\nChord tones for Am7 (C4-C6):")
    tones = engine.get_chord_tones_in_register(
        engine.parse_chord("Am7"), 60, 84
    )
    print(f"  {[t.to_name() for t in tones]}")

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    demo()
