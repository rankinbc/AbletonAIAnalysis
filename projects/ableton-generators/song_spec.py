"""
Data models for song specification.
These dataclasses define the structure that flows through the generation pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import json


class SectionType(Enum):
    """Types of song sections."""
    INTRO = "intro"
    BUILDUP = "buildup"
    BREAKDOWN = "breakdown"
    DROP = "drop"
    BREAK = "break"
    OUTRO = "outro"


@dataclass
class SectionSpec:
    """Specification for a single song section."""
    name: str
    section_type: SectionType
    start_bar: int
    bars: int
    energy: float  # 0.0 - 1.0

    # Which tracks are active in this section
    active_tracks: List[str] = field(default_factory=list)

    # Override default patterns for specific tracks
    # e.g., {"kick": "half", "bass": "stabs"}
    pattern_overrides: Dict[str, str] = field(default_factory=dict)

    # Transition hints
    # exit_transition: what happens at the END of this section
    # Options: "none", "soft", "build", "rush", "break"
    exit_transition: str = "auto"  # "auto" = determine from section types

    # entry_effect: what happens at the START of this section
    # Options: "none", "soft", "crash", "impact"
    entry_effect: str = "auto"

    @property
    def end_bar(self) -> int:
        return self.start_bar + self.bars

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "section_type": self.section_type.value,
            "start_bar": self.start_bar,
            "bars": self.bars,
            "energy": self.energy,
            "active_tracks": self.active_tracks,
            "pattern_overrides": self.pattern_overrides,
            "exit_transition": self.exit_transition,
            "entry_effect": self.entry_effect,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SectionSpec":
        return cls(
            name=data["name"],
            section_type=SectionType(data["section_type"]),
            start_bar=data["start_bar"],
            bars=data["bars"],
            energy=data["energy"],
            active_tracks=data.get("active_tracks", []),
            pattern_overrides=data.get("pattern_overrides", {}),
            exit_transition=data.get("exit_transition", "auto"),
            entry_effect=data.get("entry_effect", "auto"),
        )


@dataclass
class TrackSpec:
    """Specification for a single track."""
    name: str
    track_type: str  # "midi", "audio", "return"
    color: int  # Ableton color index
    default_pattern: str  # Default pattern type for this track

    # Hint for what instrument/sound to use
    instrument_hint: str = ""

    # Send levels to return tracks (0.0 - 1.0)
    send_levels: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "track_type": self.track_type,
            "color": self.color,
            "default_pattern": self.default_pattern,
            "instrument_hint": self.instrument_hint,
            "send_levels": self.send_levels,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrackSpec":
        return cls(
            name=data["name"],
            track_type=data["track_type"],
            color=data["color"],
            default_pattern=data["default_pattern"],
            instrument_hint=data.get("instrument_hint", ""),
            send_levels=data.get("send_levels", {}),
        )


@dataclass
class SongSpec:
    """Complete specification for a song to be generated."""
    name: str

    # Musical parameters
    genre: str = "trance"
    subgenre: str = "uplifting"
    tempo: int = 138
    key: str = "A"
    scale: str = "minor"  # "minor", "major", "harmonic_minor", etc.

    # Mood/style
    mood: str = "euphoric"  # "euphoric", "dark", "melancholic", "aggressive"

    # Structure
    structure: List[SectionSpec] = field(default_factory=list)

    # Tracks
    tracks: List[TrackSpec] = field(default_factory=list)

    # Additional hints from user prompt
    hints: Dict[str, Any] = field(default_factory=dict)

    # Chord progression (if specified)
    # Format: list of chord symbols, e.g., ["Am", "F", "C", "G"]
    chord_progression: List[str] = field(default_factory=list)

    @property
    def total_bars(self) -> int:
        """Total number of bars in the song."""
        if not self.structure:
            return 0
        last = self.structure[-1]
        return last.start_bar + last.bars

    @property
    def duration_seconds(self) -> float:
        """Total duration in seconds."""
        bars = self.total_bars
        beats = bars * 4  # Assuming 4/4 time
        return beats * (60 / self.tempo)

    @property
    def duration_formatted(self) -> str:
        """Duration as MM:SS string."""
        total_seconds = int(self.duration_seconds)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def get_section_at_bar(self, bar: int) -> Optional[SectionSpec]:
        """Get the section that contains the given bar."""
        for section in self.structure:
            if section.start_bar <= bar < section.end_bar:
                return section
        return None

    def get_track_by_name(self, name: str) -> Optional[TrackSpec]:
        """Get a track by its name (case-insensitive)."""
        name_lower = name.lower()
        for track in self.tracks:
            if track.name.lower() == name_lower:
                return track
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "genre": self.genre,
            "subgenre": self.subgenre,
            "tempo": self.tempo,
            "key": self.key,
            "scale": self.scale,
            "mood": self.mood,
            "structure": [s.to_dict() for s in self.structure],
            "tracks": [t.to_dict() for t in self.tracks],
            "hints": self.hints,
            "chord_progression": self.chord_progression,
            "total_bars": self.total_bars,
            "duration": self.duration_formatted,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "SongSpec":
        """Create SongSpec from dictionary."""
        return cls(
            name=data["name"],
            genre=data.get("genre", "trance"),
            subgenre=data.get("subgenre", "uplifting"),
            tempo=data.get("tempo", 138),
            key=data.get("key", "A"),
            scale=data.get("scale", "minor"),
            mood=data.get("mood", "euphoric"),
            structure=[SectionSpec.from_dict(s) for s in data.get("structure", [])],
            tracks=[TrackSpec.from_dict(t) for t in data.get("tracks", [])],
            hints=data.get("hints", {}),
            chord_progression=data.get("chord_progression", []),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SongSpec":
        """Create SongSpec from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: str) -> "SongSpec":
        """Load SongSpec from JSON file."""
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))


def create_spec_from_reference(
    profile: "ReferenceProfile",
    name: str = None,
    target_duration_bars: int = None,
) -> SongSpec:
    """
    Create a SongSpec that matches characteristics of a reference profile.

    Args:
        profile: ReferenceProfile with analyzed reference parameters
        name: Override name (defaults to profile name + "_inspired")
        target_duration_bars: Override duration (defaults to profile's bars or 224)

    Returns:
        SongSpec configured to match reference characteristics
    """
    from reference_profile import ReferenceProfile

    if name is None:
        name = f"{profile.name}_inspired"

    total_bars = target_duration_bars or profile.total_bars or 224

    # Use reference tempo (round to common values)
    tempo = int(round(profile.tempo / 2) * 2)  # Round to even
    if tempo < 100:
        tempo = 128  # Default if too slow
    elif tempo > 160:
        tempo = 140  # Cap for trance

    # Use reference key if available
    key = profile.key or "A"
    scale = profile.scale or "minor"

    # Build structure with reference energy levels
    structure = _build_structure_from_profile(profile, total_bars)

    # Default tracks
    tracks = [
        TrackSpec("Kick", "midi", 0, "four_on_floor", "punchy trance kick"),
        TrackSpec("Bass", "midi", 1, "rolling", "rolling 303-style bass"),
        TrackSpec("Chords", "midi", 2, "sustained", "supersaw pad"),
        TrackSpec("Arp", "midi", 3, "trance", "pluck arpeggio"),
        TrackSpec("Lead", "midi", 4, "melody", "supersaw lead"),
        TrackSpec("Hats", "midi", 5, "offbeat", "open/closed hats"),
        TrackSpec("Clap", "midi", 6, "standard", "layered clap"),
    ]

    # Build hints from reference (ensure native Python types for JSON)
    hints = {
        "reference_name": profile.name,
        "reference_tempo": float(profile.tempo),
    }
    if profile.frequency_balance:
        hints["target_bass_energy"] = float(profile.frequency_balance.bass)
        hints["target_brightness"] = float(profile.frequency_balance.spectral_centroid_hz)
    if profile.dynamics:
        hints["target_lufs"] = float(profile.dynamics.integrated_lufs)
        hints["target_dynamic_range"] = float(profile.dynamics.dynamic_range_db)

    return SongSpec(
        name=name,
        genre=profile.genre,
        subgenre=profile.subgenre,
        tempo=tempo,
        key=key,
        scale=scale,
        mood=profile.mood,
        structure=structure,
        tracks=tracks,
        hints=hints,
        chord_progression=["Am", "F", "C", "G"],  # Default, could be derived
    )


def _build_structure_from_profile(profile: "ReferenceProfile", total_bars: int) -> List[SectionSpec]:
    """Build song structure matching reference energy profile."""
    # Use reference section energies
    intro_energy = profile.intro_energy
    buildup_energy = profile.buildup_energy
    drop_energy = profile.drop_energy
    breakdown_energy = profile.breakdown_energy
    outro_energy = profile.outro_energy

    # Standard trance structure with reference energies
    # Scale section lengths proportionally to total_bars
    scale = total_bars / 224  # 224 is our default length

    def scaled(bars: int) -> int:
        return max(8, int(round(bars * scale / 8) * 8))  # Round to 8-bar phrases

    structure = [
        SectionSpec("Intro", SectionType.INTRO, 0, scaled(32), intro_energy,
                    active_tracks=["kick", "hats"]),
        SectionSpec("Buildup A", SectionType.BUILDUP, scaled(32), scaled(16), buildup_energy,
                    active_tracks=["kick", "bass", "arp", "hats", "clap"]),
        SectionSpec("Breakdown 1", SectionType.BREAKDOWN, scaled(48), scaled(32), breakdown_energy,
                    active_tracks=["chords", "arp", "lead"]),
        SectionSpec("Drop 1", SectionType.DROP, scaled(80), scaled(32), drop_energy,
                    active_tracks=["kick", "bass", "chords", "arp", "lead", "hats", "clap"]),
        SectionSpec("Break", SectionType.BREAK, scaled(112), scaled(16), buildup_energy * 1.2,
                    active_tracks=["kick", "bass", "hats", "clap"]),
        SectionSpec("Breakdown 2", SectionType.BREAKDOWN, scaled(128), scaled(32), breakdown_energy,
                    active_tracks=["chords", "arp", "lead"]),
        SectionSpec("Drop 2", SectionType.DROP, scaled(160), scaled(32), drop_energy,
                    active_tracks=["kick", "bass", "chords", "arp", "lead", "hats", "clap"]),
        SectionSpec("Outro", SectionType.OUTRO, scaled(192), scaled(32), outro_energy,
                    active_tracks=["kick", "hats"]),
    ]

    # Fix start_bars to be sequential
    current_bar = 0
    for section in structure:
        section.start_bar = current_bar
        current_bar += section.bars

    return structure


def create_default_trance_spec(name: str = "Track") -> SongSpec:
    """Create a default trance song specification."""
    from datetime import datetime

    if name == "Track":
        name = f"Track_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Default structure
    structure = [
        SectionSpec("Intro", SectionType.INTRO, 0, 32, 0.3,
                    active_tracks=["kick", "hats", "atmosphere"]),
        SectionSpec("Buildup A", SectionType.BUILDUP, 32, 16, 0.5,
                    active_tracks=["kick", "bass", "arp", "hats", "clap", "riser"]),
        SectionSpec("Breakdown 1", SectionType.BREAKDOWN, 48, 32, 0.4,
                    active_tracks=["chords", "arp", "lead", "atmosphere"]),
        SectionSpec("Drop 1", SectionType.DROP, 80, 32, 1.0,
                    active_tracks=["kick", "bass", "chords", "arp", "lead", "hats", "clap", "impact"]),
        SectionSpec("Break", SectionType.BREAK, 112, 16, 0.6,
                    active_tracks=["kick", "bass", "hats", "clap"]),
        SectionSpec("Breakdown 2", SectionType.BREAKDOWN, 128, 32, 0.4,
                    active_tracks=["chords", "arp", "lead", "atmosphere", "riser"]),
        SectionSpec("Drop 2", SectionType.DROP, 160, 32, 1.0,
                    active_tracks=["kick", "bass", "chords", "arp", "lead", "hats", "clap", "impact"]),
        SectionSpec("Outro", SectionType.OUTRO, 192, 32, 0.2,
                    active_tracks=["kick", "hats", "atmosphere"]),
    ]

    # Default tracks
    tracks = [
        TrackSpec("Kick", "midi", 0, "four_on_floor", "punchy trance kick"),
        TrackSpec("Bass", "midi", 1, "rolling", "rolling 303-style bass"),
        TrackSpec("Chords", "midi", 2, "sustained", "supersaw pad"),
        TrackSpec("Arp", "midi", 3, "trance", "pluck arpeggio"),
        TrackSpec("Lead", "midi", 4, "melody", "supersaw lead"),
        TrackSpec("Hats", "midi", 5, "offbeat", "open/closed hats"),
        TrackSpec("Clap", "midi", 6, "standard", "layered clap"),
        # Texture/FX tracks
        TrackSpec("Riser", "midi", 7, "riser", "sweep/riser synth"),
        TrackSpec("Impact", "midi", 0, "impact", "impact/crash FX"),
        TrackSpec("Atmosphere", "midi", 8, "atmosphere", "ambient pad/texture"),
    ]

    return SongSpec(
        name=name,
        genre="trance",
        subgenre="uplifting",
        tempo=138,
        key="A",
        scale="minor",
        mood="euphoric",
        structure=structure,
        tracks=tracks,
        chord_progression=["Am", "F", "C", "G"],
    )
