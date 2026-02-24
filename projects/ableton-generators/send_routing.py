"""
Send Effect Routing - Configure Reverb/Delay Sends

Automatically configures send effect routing with appropriate levels:
- Reverb sends (hall, plate, room, ambient)
- Delay sends (sync quarter, eighth, dotted eighth)
- Per-track send levels based on track type
- Genre-specific effect presets

Features:
- Smart send levels per track type
- Multiple reverb/delay flavors
- Pre/post-fader routing options
- Export to Ableton format
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class SendType(Enum):
    """Types of send effects."""
    REVERB = "reverb"
    DELAY = "delay"
    CHORUS = "chorus"
    DISTORTION = "distortion"
    FILTER = "filter"


class ReverbType(Enum):
    """Reverb character types."""
    HALL = "hall"           # Large space, long decay
    PLATE = "plate"         # Classic, smooth
    ROOM = "room"           # Small, natural
    CHAMBER = "chamber"     # Medium, warm
    AMBIENT = "ambient"     # Very long, washy
    SPRING = "spring"       # Vintage, boingy


class DelayType(Enum):
    """Delay character types."""
    SYNC_QUARTER = "1/4"
    SYNC_EIGHTH = "1/8"
    SYNC_DOTTED_EIGHTH = "1/8D"
    SYNC_SIXTEENTH = "1/16"
    SYNC_TRIPLET = "1/8T"
    SLAPBACK = "slapback"
    PING_PONG = "ping_pong"
    AMBIENT = "ambient"


@dataclass
class EffectParams:
    """Parameters for a send effect."""
    params: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return self.params.copy()


@dataclass
class SendEffect:
    """Configuration for a send effect (return track)."""
    name: str                           # Return track name (e.g., "Reverb A")
    send_type: SendType
    effect_subtype: str = ""            # e.g., "hall", "1/8D"

    # Effect parameters
    params: Dict[str, float] = field(default_factory=dict)

    # Default send levels per track type (0.0 - 1.0)
    # Higher = more effect
    track_levels: Dict[str, float] = field(default_factory=dict)

    # Routing options
    pre_fader: bool = False             # Pre-fader send

    def get_level(self, track_name: str) -> float:
        """Get send level for a track (0-1)."""
        track_lower = track_name.lower()

        # Exact match
        if track_lower in self.track_levels:
            return self.track_levels[track_lower]

        # Partial match
        for key, level in self.track_levels.items():
            if key in track_lower or track_lower in key:
                return level

        return 0.0

    def get_level_db(self, track_name: str) -> float:
        """Get send level in dB (-inf to 0)."""
        level = self.get_level(track_name)
        if level <= 0:
            return -70.0  # Essentially off
        import math
        return 20 * math.log10(level)

    def to_dict(self) -> Dict:
        """Export as dictionary."""
        return {
            "name": self.name,
            "type": self.send_type.value,
            "subtype": self.effect_subtype,
            "params": self.params,
            "track_levels": self.track_levels,
            "pre_fader": self.pre_fader,
        }


# =============================================================================
# EFFECT PRESETS
# =============================================================================

REVERB_PRESETS: Dict[str, Dict] = {
    "hall": {
        "DecayTime": 3.5,
        "RoomSize": 100.0,
        "PreDelay": 20.0,
        "DryWet": 100.0,        # 100% wet on return
        "HighCut": 8000.0,
        "LowCut": 200.0,
        "Diffusion": 80.0,
        "EarlyReflections": 30.0,
        "description": "Large hall reverb, epic and spacious",
    },
    "plate": {
        "DecayTime": 1.8,
        "RoomSize": 60.0,
        "PreDelay": 10.0,
        "DryWet": 100.0,
        "HighCut": 10000.0,
        "LowCut": 150.0,
        "Diffusion": 90.0,
        "description": "Classic plate reverb, smooth and dense",
    },
    "room": {
        "DecayTime": 0.8,
        "RoomSize": 30.0,
        "PreDelay": 5.0,
        "DryWet": 100.0,
        "HighCut": 12000.0,
        "LowCut": 100.0,
        "Diffusion": 70.0,
        "description": "Small room, natural ambience",
    },
    "chamber": {
        "DecayTime": 2.2,
        "RoomSize": 50.0,
        "PreDelay": 15.0,
        "DryWet": 100.0,
        "HighCut": 9000.0,
        "LowCut": 180.0,
        "Diffusion": 75.0,
        "description": "Medium chamber, warm character",
    },
    "ambient": {
        "DecayTime": 6.0,
        "RoomSize": 100.0,
        "PreDelay": 50.0,
        "DryWet": 100.0,
        "HighCut": 6000.0,
        "LowCut": 300.0,
        "Diffusion": 95.0,
        "description": "Very long ambient reverb, washy and atmospheric",
    },
    "trance_hall": {
        "DecayTime": 4.0,
        "RoomSize": 100.0,
        "PreDelay": 25.0,
        "DryWet": 100.0,
        "HighCut": 7000.0,
        "LowCut": 250.0,
        "Diffusion": 85.0,
        "description": "Classic trance reverb, big and emotional",
    },
}

DELAY_PRESETS: Dict[str, Dict] = {
    "1/4": {
        "DelayTime": "1/4",
        "Feedback": 35.0,
        "DryWet": 100.0,
        "HighCut": 6000.0,
        "LowCut": 200.0,
        "PingPong": True,
        "description": "Quarter note ping-pong delay",
    },
    "1/8": {
        "DelayTime": "1/8",
        "Feedback": 30.0,
        "DryWet": 100.0,
        "HighCut": 8000.0,
        "LowCut": 150.0,
        "PingPong": True,
        "description": "Eighth note delay, rhythmic",
    },
    "1/8D": {
        "DelayTime": "1/8D",
        "Feedback": 40.0,
        "DryWet": 100.0,
        "HighCut": 5000.0,
        "LowCut": 300.0,
        "PingPong": True,
        "description": "Dotted eighth, classic trance delay",
    },
    "1/16": {
        "DelayTime": "1/16",
        "Feedback": 25.0,
        "DryWet": 100.0,
        "HighCut": 10000.0,
        "LowCut": 100.0,
        "PingPong": False,
        "description": "Fast sixteenth note slapback",
    },
    "slapback": {
        "DelayTime": "1/32",
        "Feedback": 10.0,
        "DryWet": 100.0,
        "HighCut": 10000.0,
        "LowCut": 100.0,
        "PingPong": False,
        "description": "Short slapback, adds depth",
    },
    "ambient": {
        "DelayTime": "1/4",
        "Feedback": 60.0,
        "DryWet": 100.0,
        "HighCut": 4000.0,
        "LowCut": 400.0,
        "PingPong": True,
        "description": "Long ambient delay, atmospheric",
    },
    "trance": {
        "DelayTime": "1/8D",
        "Feedback": 45.0,
        "DryWet": 100.0,
        "HighCut": 5500.0,
        "LowCut": 250.0,
        "PingPong": True,
        "description": "Classic trance dotted eighth delay",
    },
}


# =============================================================================
# DEFAULT SEND LEVELS PER TRACK TYPE
# =============================================================================

# These are suggested send levels (0-1) for each track type
DEFAULT_REVERB_LEVELS: Dict[str, float] = {
    # Leads and melodic - most reverb
    "lead": 0.35,
    "vox": 0.40,
    "vocal": 0.40,

    # Pads and atmospheres - lots of reverb
    "pad": 0.50,
    "atmosphere": 0.45,
    "texture": 0.40,

    # Chords and arps - moderate reverb
    "chords": 0.30,
    "chord": 0.30,
    "arp": 0.25,
    "pluck": 0.30,

    # Drums - selective reverb
    "clap": 0.20,
    "snare": 0.25,
    "hats": 0.10,
    "perc": 0.15,

    # Bass and kick - NO reverb (keeps low end clean)
    "kick": 0.0,
    "bass": 0.0,
    "sub": 0.0,

    # FX - variable
    "riser": 0.20,
    "impact": 0.15,
}

DEFAULT_DELAY_LEVELS: Dict[str, float] = {
    # Leads - moderate delay
    "lead": 0.20,
    "vox": 0.25,
    "vocal": 0.25,

    # Arps and plucks - good for delay
    "arp": 0.30,
    "pluck": 0.25,

    # Chords - light delay
    "chords": 0.10,
    "chord": 0.10,

    # Pads - usually less delay than reverb
    "pad": 0.15,

    # Drums - snare and clap can have delay
    "clap": 0.15,
    "snare": 0.10,
    "hats": 0.05,

    # No delay on these
    "kick": 0.0,
    "bass": 0.0,
    "sub": 0.0,
}


# =============================================================================
# GENRE SEND PRESETS
# =============================================================================

def _create_reverb_send(
    name: str,
    reverb_type: str,
    level_multiplier: float = 1.0
) -> SendEffect:
    """Create a reverb send with adjusted levels."""
    params = REVERB_PRESETS.get(reverb_type, REVERB_PRESETS["hall"]).copy()
    levels = {k: v * level_multiplier for k, v in DEFAULT_REVERB_LEVELS.items()}
    return SendEffect(
        name=name,
        send_type=SendType.REVERB,
        effect_subtype=reverb_type,
        params=params,
        track_levels=levels,
    )


def _create_delay_send(
    name: str,
    delay_type: str,
    level_multiplier: float = 1.0
) -> SendEffect:
    """Create a delay send with adjusted levels."""
    params = DELAY_PRESETS.get(delay_type, DELAY_PRESETS["1/8D"]).copy()
    levels = {k: v * level_multiplier for k, v in DEFAULT_DELAY_LEVELS.items()}
    return SendEffect(
        name=name,
        send_type=SendType.DELAY,
        effect_subtype=delay_type,
        params=params,
        track_levels=levels,
    )


GENRE_SEND_CONFIGS: Dict[str, Dict[str, SendEffect]] = {
    "trance": {
        "Reverb": _create_reverb_send("Reverb", "trance_hall", 1.0),
        "Delay": _create_delay_send("Delay", "trance", 1.0),
    },
    "uplifting_trance": {
        "Reverb": _create_reverb_send("Reverb", "trance_hall", 1.1),
        "Delay": _create_delay_send("Delay", "1/8D", 1.0),
    },
    "techno": {
        "Reverb": _create_reverb_send("Reverb", "plate", 0.8),
        "Delay": _create_delay_send("Delay", "1/8", 0.9),
    },
    "industrial_techno": {
        "Reverb": _create_reverb_send("Reverb", "room", 0.6),
        "Delay": _create_delay_send("Delay", "1/16", 0.7),
    },
    "house": {
        "Reverb": _create_reverb_send("Reverb", "room", 0.9),
        "Delay": _create_delay_send("Delay", "1/4", 0.8),
    },
    "deep_house": {
        "Reverb": _create_reverb_send("Reverb", "chamber", 1.0),
        "Delay": _create_delay_send("Delay", "1/4", 0.9),
    },
    "progressive": {
        "Reverb": _create_reverb_send("Reverb", "hall", 0.9),
        "Delay": _create_delay_send("Delay", "1/8D", 0.8),
    },
    "ambient": {
        "Reverb": _create_reverb_send("Reverb", "ambient", 1.5),
        "Delay": _create_delay_send("Delay", "ambient", 1.3),
    },
    "chillout": {
        "Reverb": _create_reverb_send("Reverb", "chamber", 1.2),
        "Delay": _create_delay_send("Delay", "1/4", 1.0),
    },
    "dubstep": {
        "Reverb": _create_reverb_send("Reverb", "plate", 0.7),
        "Delay": _create_delay_send("Delay", "1/8", 0.6),
    },
    "drum_and_bass": {
        "Reverb": _create_reverb_send("Reverb", "plate", 0.8),
        "Delay": _create_delay_send("Delay", "1/8", 0.7),
    },
}


# =============================================================================
# SEND ROUTER CLASS
# =============================================================================

class SendRouter:
    """
    Configures send effect routing for a project.

    Usage:
        router = SendRouter(genre="trance")
        sends = router.get_sends()
        for send_name, send in sends.items():
            level = send.get_level("lead")
            print(f"{send_name}: lead @ {level:.0%}")
    """

    def __init__(self, genre: str = "trance"):
        self.genre = genre.lower()
        self._custom_sends: Dict[str, SendEffect] = {}

    def add_send(self, send: SendEffect):
        """Add a custom send effect."""
        self._custom_sends[send.name] = send

    def remove_send(self, name: str):
        """Remove a send effect."""
        if name in self._custom_sends:
            del self._custom_sends[name]

    def get_sends(self, use_genre_presets: bool = True) -> Dict[str, SendEffect]:
        """
        Get all send configurations.

        Args:
            use_genre_presets: Include genre-default sends

        Returns:
            Dict of send_name -> SendEffect
        """
        sends = {}

        # Add genre presets
        if use_genre_presets:
            genre_sends = GENRE_SEND_CONFIGS.get(
                self.genre,
                GENRE_SEND_CONFIGS["trance"]
            )
            sends.update(genre_sends)

        # Add custom sends (override if same name)
        sends.update(self._custom_sends)

        return sends

    def get_levels_for_track(self, track_name: str) -> Dict[str, float]:
        """
        Get all send levels for a specific track.

        Args:
            track_name: Name of the track

        Returns:
            Dict of send_name -> level (0-1)
        """
        sends = self.get_sends()
        levels = {}

        for send_name, send in sends.items():
            level = send.get_level(track_name)
            levels[send_name] = level

        return levels

    def get_send_matrix(self, tracks: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Get complete send level matrix.

        Args:
            tracks: List of track names

        Returns:
            Dict of track -> {send_name -> level}
        """
        matrix = {}

        for track in tracks:
            matrix[track] = self.get_levels_for_track(track)

        return matrix

    def set_track_level(self, send_name: str, track_name: str, level: float):
        """
        Override a specific track's send level.

        Args:
            send_name: Name of the send
            track_name: Name of the track
            level: New level (0-1)
        """
        sends = self.get_sends()
        if send_name in sends:
            sends[send_name].track_levels[track_name.lower()] = level

    def to_dict(self) -> Dict:
        """Export configuration as dictionary."""
        sends = self.get_sends()
        return {
            "genre": self.genre,
            "sends": {name: send.to_dict() for name, send in sends.items()},
        }

    def print_summary(self, tracks: List[str] = None):
        """Print human-readable summary."""
        sends = self.get_sends()

        print(f"\nSEND EFFECT ROUTING ({self.genre})")
        print("-" * 50)

        for send_name, send in sends.items():
            print(f"\n  {send_name} ({send.send_type.value}, {send.effect_subtype}):")

            # Get non-zero levels
            if tracks:
                track_list = tracks
            else:
                track_list = list(send.track_levels.keys())

            levels = [(t, send.get_level(t)) for t in track_list]
            levels = [(t, l) for t, l in levels if l > 0]
            levels.sort(key=lambda x: x[1], reverse=True)

            for track, level in levels:
                bar = "#" * int(level * 20)
                print(f"    {track:12} {level:5.0%} {bar}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_send_levels(
    track_name: str,
    genre: str = "trance"
) -> Dict[str, float]:
    """
    Get send levels for a track.

    Args:
        track_name: Name of the track
        genre: Music genre

    Returns:
        Dict of send_name -> level
    """
    router = SendRouter(genre=genre)
    return router.get_levels_for_track(track_name)


def create_reverb_send(
    reverb_type: str = "hall",
    name: str = "Reverb"
) -> SendEffect:
    """
    Create a reverb send effect.

    Args:
        reverb_type: Type of reverb (hall, plate, room, etc.)
        name: Name for the send

    Returns:
        SendEffect object
    """
    return _create_reverb_send(name, reverb_type, 1.0)


def create_delay_send(
    delay_type: str = "1/8D",
    name: str = "Delay"
) -> SendEffect:
    """
    Create a delay send effect.

    Args:
        delay_type: Type of delay (1/4, 1/8, 1/8D, etc.)
        name: Name for the send

    Returns:
        SendEffect object
    """
    return _create_delay_send(name, delay_type, 1.0)


def get_available_reverb_types() -> List[str]:
    """Get list of available reverb types."""
    return list(REVERB_PRESETS.keys())


def get_available_delay_types() -> List[str]:
    """Get list of available delay types."""
    return list(DELAY_PRESETS.keys())


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SEND EFFECT ROUTING - Demo")
    print("=" * 60)

    tracks = ["kick", "bass", "chords", "pad", "lead", "arp", "clap", "hats"]

    # Test different genres
    for genre in ["trance", "techno", "ambient"]:
        router = SendRouter(genre=genre)
        router.print_summary(tracks)

    # Send matrix example
    print("\n" + "=" * 60)
    print("SEND MATRIX (Trance)")
    print("=" * 60)

    router = SendRouter(genre="trance")
    matrix = router.get_send_matrix(tracks)

    # Print header
    sends = list(router.get_sends().keys())
    print(f"\n{'Track':<12}", end="")
    for send in sends:
        print(f"{send:>10}", end="")
    print()
    print("-" * (12 + len(sends) * 10))

    # Print levels
    for track in tracks:
        print(f"{track:<12}", end="")
        for send in sends:
            level = matrix[track].get(send, 0)
            print(f"{level:>9.0%}", end=" ")
        print()

    # Custom send example
    print("\n" + "=" * 60)
    print("CUSTOM SENDS")
    print("=" * 60)

    custom = SendRouter(genre="house")
    custom.add_send(SendEffect(
        name="Long Verb",
        send_type=SendType.REVERB,
        effect_subtype="ambient",
        params=REVERB_PRESETS["ambient"],
        track_levels={"pad": 0.7, "lead": 0.5, "vox": 0.6},
    ))
    custom.print_summary(["pad", "lead", "vox", "bass"])

    print("\nAvailable reverb types:", get_available_reverb_types())
    print("Available delay types:", get_available_delay_types())

    print("\nDone!")
