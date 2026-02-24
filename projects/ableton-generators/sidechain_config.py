"""
Sidechain Configuration - Auto-Route Sidechain Compression

Automatically configures sidechain compression routing:
- kick → bass (ducking for clarity)
- kick → pads (pumping effect)
- kick → chords (rhythmic ducking)

Features:
- Genre-specific sidechain presets
- Tempo-synced release times
- Adjustable pumping intensity
- Export to Ableton Compressor format
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum


class SidechainMode(Enum):
    """Sidechain compression intensity modes."""
    OFF = "off"
    SUBTLE = "subtle"       # Light ducking, transparent
    MODERATE = "moderate"   # Noticeable pump
    HEAVY = "heavy"         # Strong pump (EDM style)
    EXTREME = "extreme"     # Very aggressive (future bass/dubstep)


@dataclass
class SidechainRoute:
    """Configuration for a single sidechain routing."""
    source_track: str           # Track providing the trigger (e.g., "kick")
    target_track: str           # Track being compressed (e.g., "bass")
    mode: SidechainMode = SidechainMode.MODERATE

    # Compressor parameters
    ratio: float = 4.0          # Compression ratio
    attack_ms: float = 0.1      # Attack time in ms
    release_ms: float = 100.0   # Release time in ms
    threshold_db: float = -30.0 # Threshold in dB

    # Additional settings
    lookahead_ms: float = 0.0   # Lookahead time
    hold_ms: float = 0.0        # Hold time before release
    knee_db: float = 6.0        # Soft knee width

    # Mix/blend
    dry_wet: float = 100.0      # Wet percentage (0-100)
    makeup_gain_db: float = 0.0 # Makeup gain

    def to_ableton_params(self) -> Dict:
        """Get parameters formatted for Ableton Compressor."""
        return {
            "Threshold": self.threshold_db,
            "Ratio": self.ratio,
            "Attack": self.attack_ms,
            "Release": self.release_ms,
            "Knee": self.knee_db,
            "DryWet": self.dry_wet / 100.0,
            "GainCompensation": self.makeup_gain_db,
            "SidechainOn": True,
            "SidechainSource": self.source_track,
        }

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "source": self.source_track,
            "target": self.target_track,
            "mode": self.mode.value,
            "ratio": self.ratio,
            "attack_ms": self.attack_ms,
            "release_ms": self.release_ms,
            "threshold_db": self.threshold_db,
            "dry_wet": self.dry_wet,
        }


# =============================================================================
# MODE PARAMETERS
# =============================================================================

SIDECHAIN_MODE_PARAMS = {
    SidechainMode.OFF: {
        "ratio": 1.0,
        "attack_ms": 10.0,
        "release_ms": 100.0,
        "threshold_db": 0.0,
        "dry_wet": 0.0,
    },
    SidechainMode.SUBTLE: {
        "ratio": 2.0,
        "attack_ms": 0.5,
        "release_ms": 150.0,
        "threshold_db": -25.0,
        "dry_wet": 50.0,
        "description": "Light ducking, transparent pumping",
    },
    SidechainMode.MODERATE: {
        "ratio": 4.0,
        "attack_ms": 0.1,
        "release_ms": 100.0,
        "threshold_db": -30.0,
        "dry_wet": 100.0,
        "description": "Classic EDM pump, noticeable but musical",
    },
    SidechainMode.HEAVY: {
        "ratio": 8.0,
        "attack_ms": 0.01,
        "release_ms": 80.0,
        "threshold_db": -35.0,
        "dry_wet": 100.0,
        "description": "Strong pump for driving tracks",
    },
    SidechainMode.EXTREME: {
        "ratio": 20.0,
        "attack_ms": 0.01,
        "release_ms": 50.0,
        "threshold_db": -40.0,
        "dry_wet": 100.0,
        "description": "Aggressive ducking (future bass/dubstep)",
    },
}


# =============================================================================
# GENRE PRESETS
# =============================================================================

# Default sidechain routings per genre
# Format: (source, target, mode)
GENRE_SIDECHAIN_PRESETS: Dict[str, List[Tuple[str, str, SidechainMode]]] = {
    "trance": [
        ("kick", "bass", SidechainMode.MODERATE),
        ("kick", "pad", SidechainMode.SUBTLE),
        ("kick", "chords", SidechainMode.SUBTLE),
        ("kick", "arp", SidechainMode.SUBTLE),
    ],
    "uplifting_trance": [
        ("kick", "bass", SidechainMode.MODERATE),
        ("kick", "pad", SidechainMode.MODERATE),
        ("kick", "chords", SidechainMode.SUBTLE),
        ("kick", "arp", SidechainMode.SUBTLE),
        ("kick", "lead", SidechainMode.SUBTLE),
    ],
    "house": [
        ("kick", "bass", SidechainMode.MODERATE),
        ("kick", "chords", SidechainMode.MODERATE),
        ("kick", "pad", SidechainMode.SUBTLE),
    ],
    "deep_house": [
        ("kick", "bass", SidechainMode.SUBTLE),
        ("kick", "chords", SidechainMode.SUBTLE),
        ("kick", "pad", SidechainMode.SUBTLE),
    ],
    "techno": [
        ("kick", "bass", SidechainMode.HEAVY),
        ("kick", "pad", SidechainMode.MODERATE),
        ("kick", "lead", SidechainMode.SUBTLE),
        ("kick", "texture", SidechainMode.SUBTLE),
    ],
    "industrial_techno": [
        ("kick", "bass", SidechainMode.HEAVY),
        ("kick", "pad", SidechainMode.HEAVY),
        ("kick", "lead", SidechainMode.MODERATE),
    ],
    "future_bass": [
        ("kick", "bass", SidechainMode.EXTREME),
        ("kick", "chords", SidechainMode.HEAVY),
        ("kick", "pad", SidechainMode.HEAVY),
        ("kick", "lead", SidechainMode.MODERATE),
    ],
    "dubstep": [
        ("kick", "bass", SidechainMode.EXTREME),
        ("snare", "bass", SidechainMode.MODERATE),
    ],
    "drum_and_bass": [
        ("kick", "bass", SidechainMode.HEAVY),
        ("snare", "bass", SidechainMode.SUBTLE),
    ],
    "progressive": [
        ("kick", "bass", SidechainMode.SUBTLE),
        ("kick", "pad", SidechainMode.SUBTLE),
    ],
    "progressive_house": [
        ("kick", "bass", SidechainMode.MODERATE),
        ("kick", "chords", SidechainMode.SUBTLE),
    ],
    "ambient": [
        # Minimal or no sidechaining for ambient
    ],
    "chillout": [
        ("kick", "bass", SidechainMode.SUBTLE),
    ],
}


# =============================================================================
# SIDECHAIN CONFIGURATOR CLASS
# =============================================================================

class SidechainConfigurator:
    """
    Configures sidechain compression routing for a project.

    Usage:
        config = SidechainConfigurator(genre="trance", tempo=138)
        routes = config.get_routes(tracks=["kick", "bass", "pad"])
        for route in routes:
            print(f"{route.source_track} -> {route.target_track}")
    """

    def __init__(self, genre: str = "trance", tempo: int = 138):
        self.genre = genre.lower()
        self.tempo = tempo
        self._custom_routes: List[Tuple[str, str, SidechainMode]] = []

    def add_route(self, source: str, target: str, mode: SidechainMode = SidechainMode.MODERATE):
        """Add a custom sidechain route."""
        self._custom_routes.append((source, target, mode))

    def remove_route(self, source: str, target: str):
        """Remove a sidechain route."""
        self._custom_routes = [
            (s, t, m) for s, t, m in self._custom_routes
            if not (s == source and t == target)
        ]

    def get_routes(
        self,
        tracks: List[str] = None,
        use_genre_presets: bool = True
    ) -> List[SidechainRoute]:
        """
        Get all sidechain routes.

        Args:
            tracks: Available track names (filters routes)
            use_genre_presets: Include genre-default routes

        Returns:
            List of SidechainRoute objects
        """
        # Collect route tuples
        all_route_tuples = []

        # Add genre presets
        if use_genre_presets:
            genre_routes = GENRE_SIDECHAIN_PRESETS.get(self.genre, [])
            all_route_tuples.extend(genre_routes)

        # Add custom routes
        all_route_tuples.extend(self._custom_routes)

        # Build SidechainRoute objects
        routes = []
        seen = set()

        for source, target, mode in all_route_tuples:
            # Skip duplicates
            key = (source.lower(), target.lower())
            if key in seen:
                continue
            seen.add(key)

            # Filter by available tracks
            if tracks:
                source_exists = any(source.lower() in t.lower() for t in tracks)
                target_exists = any(target.lower() in t.lower() for t in tracks)
                if not (source_exists and target_exists):
                    continue

            # Get mode parameters
            params = SIDECHAIN_MODE_PARAMS.get(mode, SIDECHAIN_MODE_PARAMS[SidechainMode.MODERATE])

            # Calculate tempo-synced release
            release_ms = self._calc_release_for_tempo(params["release_ms"])

            route = SidechainRoute(
                source_track=source,
                target_track=target,
                mode=mode,
                ratio=params["ratio"],
                attack_ms=params["attack_ms"],
                release_ms=release_ms,
                threshold_db=params["threshold_db"],
                dry_wet=params["dry_wet"],
            )

            routes.append(route)

        return routes

    def _calc_release_for_tempo(self, base_release_ms: float) -> float:
        """
        Calculate tempo-synced release time.

        For proper pumping, release should be ~70-90% of a beat.
        """
        beat_ms = 60000 / self.tempo
        ideal_release = beat_ms * 0.8

        # Blend base release with ideal for genre-appropriate feel
        return (base_release_ms + ideal_release) / 2

    def get_pump_curve(self, mode: SidechainMode) -> List[float]:
        """
        Get the gain reduction curve over one beat.

        Returns 16 values (16th note resolution) showing gain reduction.
        """
        params = SIDECHAIN_MODE_PARAMS.get(mode, SIDECHAIN_MODE_PARAMS[SidechainMode.MODERATE])

        beat_ms = 60000 / self.tempo
        sixteenth_ms = beat_ms / 4

        curve = []
        current_reduction = 0.0

        for i in range(16):
            time_ms = i * sixteenth_ms

            if i == 0:
                # Kick hits - instant attack
                attack_factor = params["attack_ms"] / sixteenth_ms
                current_reduction = min(1.0, 1.0 - attack_factor)
            else:
                # Release phase
                release_factor = sixteenth_ms / params["release_ms"]
                current_reduction = max(0.0, current_reduction - release_factor)

            # Convert to dB-ish scale (0 = no reduction, 1 = full reduction)
            curve.append(current_reduction)

        return curve

    def to_dict(self, tracks: List[str] = None) -> Dict:
        """Export configuration as dictionary."""
        routes = self.get_routes(tracks)
        return {
            "genre": self.genre,
            "tempo": self.tempo,
            "routes": [route.to_dict() for route in routes],
        }

    def print_summary(self, tracks: List[str] = None):
        """Print human-readable summary."""
        routes = self.get_routes(tracks)

        print(f"\nSIDECHAIN CONFIGURATION ({self.genre} @ {self.tempo} BPM)")
        print("-" * 50)

        if not routes:
            print("  No sidechain routes configured")
            return

        for route in routes:
            print(f"  {route.source_track:8} -> {route.target_track:8} "
                  f"[{route.mode.value:8}] "
                  f"ratio={route.ratio:.1f}:1, "
                  f"release={route.release_ms:.0f}ms")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_sidechain_routes(
    genre: str = "trance",
    tempo: int = 138,
    tracks: List[str] = None
) -> List[SidechainRoute]:
    """
    Get sidechain routes for a genre.

    Args:
        genre: Music genre
        tempo: BPM for tempo-synced release
        tracks: Filter by available tracks

    Returns:
        List of SidechainRoute objects
    """
    config = SidechainConfigurator(genre=genre, tempo=tempo)
    return config.get_routes(tracks=tracks)


def create_sidechain_route(
    source: str,
    target: str,
    mode: str = "moderate",
    tempo: int = 138
) -> SidechainRoute:
    """
    Create a single sidechain route.

    Args:
        source: Source track name
        target: Target track name
        mode: Mode string (subtle, moderate, heavy, extreme)
        tempo: BPM

    Returns:
        SidechainRoute object
    """
    mode_enum = SidechainMode(mode.lower())
    params = SIDECHAIN_MODE_PARAMS.get(mode_enum, SIDECHAIN_MODE_PARAMS[SidechainMode.MODERATE])

    # Tempo-synced release
    beat_ms = 60000 / tempo
    release_ms = (params["release_ms"] + beat_ms * 0.8) / 2

    return SidechainRoute(
        source_track=source,
        target_track=target,
        mode=mode_enum,
        ratio=params["ratio"],
        attack_ms=params["attack_ms"],
        release_ms=release_ms,
        threshold_db=params["threshold_db"],
        dry_wet=params["dry_wet"],
    )


def get_available_genres() -> List[str]:
    """Get list of genres with sidechain presets."""
    return list(GENRE_SIDECHAIN_PRESETS.keys())


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SIDECHAIN CONFIGURATION - Demo")
    print("=" * 60)

    tracks = ["kick", "bass", "chords", "pad", "lead", "arp", "hats"]

    # Test different genres
    for genre in ["trance", "techno", "future_bass", "progressive"]:
        config = SidechainConfigurator(genre=genre, tempo=138)
        config.print_summary(tracks)

    # Custom configuration example
    print("\n" + "=" * 60)
    print("CUSTOM CONFIGURATION")
    print("=" * 60)

    custom = SidechainConfigurator(genre="house", tempo=124)
    custom.add_route("kick", "vox", SidechainMode.SUBTLE)
    custom.add_route("snare", "lead", SidechainMode.SUBTLE)
    custom.print_summary(tracks + ["vox", "snare"])

    # Single route example
    print("\n--- Single Route ---")
    route = create_sidechain_route("kick", "bass", "heavy", 140)
    print(f"  {route.source_track} -> {route.target_track}")
    print(f"  Ratio: {route.ratio}:1")
    print(f"  Release: {route.release_ms:.0f}ms")
    print(f"  Threshold: {route.threshold_db}dB")

    # Pump curve visualization
    print("\n--- Pump Curve (HEAVY mode @ 138 BPM) ---")
    config = SidechainConfigurator(tempo=138)
    curve = config.get_pump_curve(SidechainMode.HEAVY)
    for i, val in enumerate(curve):
        bar = "#" * int(val * 20)
        print(f"  {i+1:2}/16: {bar}")

    print("\nDone!")
