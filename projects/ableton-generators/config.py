"""
Configuration for the AI Song Generator.
Centralizes all paths and default values.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Config:
    """Central configuration for the song generator."""

    # Output paths
    OUTPUT_BASE: Path = field(
        default_factory=lambda: Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE")
    )

    # Ableton paths
    ABLETON_EXE: Path = field(
        default_factory=lambda: Path(r"C:\ProgramData\Ableton\Live 11 Suite\Program\Ableton Live 11 Suite.exe")
    )
    ABLETON_PREFS: Path = field(
        default_factory=lambda: Path.home() / "AppData/Roaming/Ableton/Live 11.3.11"
    )

    @property
    def DEFAULT_LIVE_SET(self) -> Path:
        """Path to Ableton's default live set template."""
        # Use Generator_WithDevices - pre-configured template with instruments on all tracks
        return Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\Generator_WithDevices Project\Generator_WithDevices.als")

    # MIDI settings
    TICKS_PER_BEAT: int = 480
    DEFAULT_VELOCITY: int = 100
    HUMANIZE_BEAT_EMPHASIS: float = 0.1  # Velocity boost for downbeats
    HUMANIZE_SIGMA: float = 5.0  # Velocity variation std dev

    # Default song parameters
    DEFAULT_TEMPO: int = 138
    DEFAULT_KEY: str = "A"
    DEFAULT_SCALE: str = "minor"
    DEFAULT_GENRE: str = "trance"
    DEFAULT_SUBGENRE: str = "uplifting"

    # Track colors (Ableton color indices)
    TRACK_COLORS: Dict[str, int] = field(default_factory=lambda: {
        "kick": 0,      # Red
        "bass": 1,      # Orange
        "chords": 2,    # Yellow
        "pad": 2,       # Yellow
        "arp": 3,       # Green
        "lead": 4,      # Cyan
        "hats": 5,      # Blue
        "clap": 6,      # Purple
        "perc": 6,      # Purple
        "fx": 7,        # Pink
        "vox": 8,       # White
        # Texture tracks
        "texture": 7,   # Pink
        "riser": 7,     # Pink
        "impact": 0,    # Red
        "atmosphere": 8, # White
        "noise": 5,     # Blue
    })

    # Standard trance structure (bars per section)
    DEFAULT_STRUCTURE: Dict[str, int] = field(default_factory=lambda: {
        "intro": 32,
        "buildup_a": 16,
        "breakdown_1": 32,
        "drop_1": 32,
        "break": 16,
        "breakdown_2": 32,
        "drop_2": 32,
        "outro": 32,
    })

    def get_output_dir(self, song_name: str) -> Path:
        """Get output directory for a specific song."""
        return self.OUTPUT_BASE / song_name

    def get_midi_dir(self, song_name: str) -> Path:
        """Get MIDI output directory for a specific song."""
        return self.get_output_dir(song_name) / "midi"


# Global default config instance
DEFAULT_CONFIG = Config()
