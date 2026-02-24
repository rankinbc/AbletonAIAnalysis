"""
Mix Templates - EQ/Compression Templates Per Track Type

Professional mixing templates for each track type:
- EQ curves (high-pass, shelves, cuts, boosts)
- Compression settings (ratio, attack, release)
- Gain staging targets
- Stereo width recommendations

Features:
- Track-type specific presets
- Genre variations
- Professional starting points
- Export to Ableton device format
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class EQBandType(Enum):
    """Types of EQ bands."""
    HIGH_PASS = "high_pass"       # 12 or 24 dB/oct filter
    LOW_PASS = "low_pass"         # 12 or 24 dB/oct filter
    LOW_SHELF = "low_shelf"       # Shelf boost/cut
    HIGH_SHELF = "high_shelf"     # Shelf boost/cut
    BELL = "bell"                 # Parametric bell
    NOTCH = "notch"               # Narrow cut


class CompressorStyle(Enum):
    """Compressor character styles."""
    TRANSPARENT = "transparent"   # Clean, surgical
    PUNCHY = "punchy"             # Fast attack, snap
    WARM = "warm"                 # Slow attack, smooth
    GLUE = "glue"                 # Bus-style cohesion
    AGGRESSIVE = "aggressive"     # Hard compression
    LIMITING = "limiting"         # Brick wall


@dataclass
class EQBand:
    """Configuration for a single EQ band."""
    band_type: EQBandType
    frequency: float              # Hz
    gain: float = 0.0             # dB
    q: float = 1.0                # Q factor (0.1 - 18)
    enabled: bool = True
    slope: int = 2                # For HP/LP: 1=6dB, 2=12dB, 4=24dB per octave

    def to_ableton_params(self) -> Dict:
        """Convert to Ableton EQ Eight parameters."""
        band_type_map = {
            EQBandType.HIGH_PASS: 1,
            EQBandType.LOW_SHELF: 2,
            EQBandType.BELL: 3,
            EQBandType.NOTCH: 4,
            EQBandType.HIGH_SHELF: 5,
            EQBandType.LOW_PASS: 6,
        }
        return {
            "Mode": band_type_map.get(self.band_type, 3),
            "Freq": self.frequency,
            "Gain": self.gain,
            "Q": self.q,
            "On": self.enabled,
        }

    def to_dict(self) -> Dict:
        return {
            "type": self.band_type.value,
            "frequency": self.frequency,
            "gain": self.gain,
            "q": self.q,
            "enabled": self.enabled,
        }


@dataclass
class CompressorSettings:
    """Configuration for a compressor."""
    style: CompressorStyle
    threshold: float = -20.0      # dB
    ratio: float = 4.0            # :1
    attack: float = 10.0          # ms
    release: float = 100.0        # ms
    knee: float = 6.0             # dB
    makeup_gain: float = 0.0      # dB
    auto_makeup: bool = True

    # Advanced
    peak_mode: bool = False       # True=Peak, False=RMS
    lookahead: float = 0.0        # ms
    dry_wet: float = 100.0        # % (for parallel compression)

    def to_ableton_params(self) -> Dict:
        """Convert to Ableton Compressor parameters."""
        return {
            "Threshold": self.threshold,
            "Ratio": self.ratio,
            "Attack": self.attack,
            "Release": self.release,
            "Knee": self.knee,
            "GainCompensation": self.makeup_gain if not self.auto_makeup else 0,
            "AutoMakeup": self.auto_makeup,
            "Model": 0 if self.peak_mode else 1,
            "DryWet": self.dry_wet / 100.0,
            "Lookahead": self.lookahead,
        }

    def to_dict(self) -> Dict:
        return {
            "style": self.style.value,
            "threshold": self.threshold,
            "ratio": self.ratio,
            "attack": self.attack,
            "release": self.release,
            "knee": self.knee,
            "dry_wet": self.dry_wet,
        }


@dataclass
class MixTemplate:
    """Complete mixing template for a track type."""
    track_type: str
    description: str = ""

    # EQ settings (8 bands max for EQ Eight)
    eq_bands: List[EQBand] = field(default_factory=list)

    # Compression
    compressor: Optional[CompressorSettings] = None

    # Gain staging
    target_peak_db: float = -6.0
    target_rms_db: float = -18.0
    headroom_db: float = 6.0

    # Stereo
    pan: float = 0.0              # -1 (L) to 1 (R)
    width: float = 1.0            # 0 (mono) to 2 (extra wide)

    # Notes for the mixer
    notes: str = ""

    def get_hp_frequency(self) -> Optional[float]:
        """Get high-pass filter frequency if set."""
        for band in self.eq_bands:
            if band.band_type == EQBandType.HIGH_PASS and band.enabled:
                return band.frequency
        return None

    def to_dict(self) -> Dict:
        return {
            "track_type": self.track_type,
            "description": self.description,
            "eq_bands": [b.to_dict() for b in self.eq_bands],
            "compressor": self.compressor.to_dict() if self.compressor else None,
            "target_peak_db": self.target_peak_db,
            "target_rms_db": self.target_rms_db,
            "pan": self.pan,
            "width": self.width,
            "notes": self.notes,
        }


# =============================================================================
# MIX TEMPLATES DATABASE
# =============================================================================

MIX_TEMPLATES: Dict[str, MixTemplate] = {
    # =========================================================================
    # DRUMS
    # =========================================================================
    "kick": MixTemplate(
        track_type="kick",
        description="Punchy kick drum with controlled low end",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 25.0, 0, 0.7),        # Subsonic rumble
            EQBand(EQBandType.LOW_SHELF, 60.0, 2.0, 0.7),      # Sub weight
            EQBand(EQBandType.BELL, 200.0, -2.5, 1.5),         # Mud cut
            EQBand(EQBandType.BELL, 400.0, -3.0, 2.0),         # Boxiness cut
            EQBand(EQBandType.BELL, 3500.0, 2.5, 1.0),         # Click/beater
            EQBand(EQBandType.LOW_PASS, 12000.0, 0, 0.7),      # Fizz removal
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.PUNCHY,
            threshold=-12.0,
            ratio=4.0,
            attack=3.0,
            release=50.0,
            auto_makeup=True,
        ),
        target_peak_db=-6.0,
        target_rms_db=-14.0,
        pan=0.0,
        width=1.0,  # Mono kick
        notes="Keep mono. Cut mud at 200-400Hz. Boost click for punch.",
    ),

    "snare": MixTemplate(
        track_type="snare",
        description="Snappy snare with body and crack",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 80.0, 0, 0.7),
            EQBand(EQBandType.BELL, 200.0, 2.0, 1.0),          # Body
            EQBand(EQBandType.BELL, 400.0, -2.0, 1.5),         # Boxiness
            EQBand(EQBandType.BELL, 900.0, -1.5, 2.0),         # Honk
            EQBand(EQBandType.BELL, 3000.0, 3.0, 1.5),         # Crack
            EQBand(EQBandType.HIGH_SHELF, 8000.0, 2.0, 0.7),   # Air
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.PUNCHY,
            threshold=-15.0,
            ratio=4.0,
            attack=1.0,
            release=80.0,
        ),
        target_peak_db=-10.0,
        pan=0.0,
        width=1.0,
        notes="Boost body at 200Hz, crack at 3kHz. Fast attack for snap.",
    ),

    "clap": MixTemplate(
        track_type="clap",
        description="Crisp clap with presence",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 150.0, 0, 0.7),
            EQBand(EQBandType.BELL, 300.0, -2.0, 1.5),         # Mud
            EQBand(EQBandType.BELL, 1000.0, 1.5, 1.0),         # Body
            EQBand(EQBandType.BELL, 4000.0, 2.5, 1.5),         # Crack
            EQBand(EQBandType.HIGH_SHELF, 10000.0, 2.0, 0.7),  # Air
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.PUNCHY,
            threshold=-18.0,
            ratio=3.0,
            attack=2.0,
            release=80.0,
        ),
        target_peak_db=-10.0,
        pan=0.0,
        width=1.3,
        notes="Slightly wider for impact. High-pass to avoid masking kick.",
    ),

    "hats": MixTemplate(
        track_type="hats",
        description="Crisp hi-hats with shimmer",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 300.0, 0, 0.7),       # Clean cut
            EQBand(EQBandType.BELL, 800.0, -2.0, 1.5),         # Harshness
            EQBand(EQBandType.BELL, 6000.0, 1.5, 1.0),         # Shimmer
            EQBand(EQBandType.HIGH_SHELF, 12000.0, 2.5, 0.7),  # Air/sparkle
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.TRANSPARENT,
            threshold=-20.0,
            ratio=2.0,
            attack=1.0,
            release=40.0,
        ),
        target_peak_db=-14.0,
        pan=0.0,
        width=1.6,
        notes="Wide for stereo interest. Don't over-compress.",
    ),

    "perc": MixTemplate(
        track_type="perc",
        description="Punchy percussion elements",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 200.0, 0, 0.7),
            EQBand(EQBandType.BELL, 1500.0, 2.0, 1.5),
            EQBand(EQBandType.BELL, 5000.0, 2.5, 1.0),
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.PUNCHY,
            threshold=-20.0,
            ratio=3.0,
            attack=3.0,
            release=60.0,
        ),
        target_peak_db=-14.0,
        pan=0.0,
        width=1.8,
        notes="Pan individual elements. Keep punchy.",
    ),

    # =========================================================================
    # BASS
    # =========================================================================
    "bass": MixTemplate(
        track_type="bass",
        description="Tight bass with definition",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 30.0, 0, 0.7),        # Subsonic
            EQBand(EQBandType.LOW_SHELF, 80.0, 2.0, 0.7),      # Sub presence
            EQBand(EQBandType.BELL, 200.0, -3.0, 2.0),         # Mud
            EQBand(EQBandType.BELL, 500.0, -1.5, 1.5),         # Boxiness
            EQBand(EQBandType.BELL, 2000.0, 2.0, 1.0),         # Definition
            EQBand(EQBandType.LOW_PASS, 8000.0, 0, 0.7),       # Remove fizz
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.GLUE,
            threshold=-18.0,
            ratio=4.0,
            attack=10.0,
            release=100.0,
        ),
        target_peak_db=-8.0,
        target_rms_db=-14.0,
        pan=0.0,
        width=0.8,  # Slightly narrow for focus
        notes="Keep mostly mono below 150Hz. Cut mud, boost definition.",
    ),

    "sub": MixTemplate(
        track_type="sub",
        description="Pure sub bass",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 25.0, 0, 0.7),
            EQBand(EQBandType.LOW_SHELF, 50.0, 3.0, 0.5),
            EQBand(EQBandType.LOW_PASS, 120.0, 0, 0.7),        # Pure sub
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.LIMITING,
            threshold=-12.0,
            ratio=10.0,
            attack=1.0,
            release=50.0,
        ),
        target_peak_db=-10.0,
        pan=0.0,
        width=0.0,  # Pure mono
        notes="100% mono. Use limiter to control peaks.",
    ),

    # =========================================================================
    # HARMONY
    # =========================================================================
    "chords": MixTemplate(
        track_type="chords",
        description="Full chords with space for bass and lead",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 150.0, 0, 0.7),       # Clear for bass
            EQBand(EQBandType.BELL, 300.0, -2.5, 1.5),         # Mud
            EQBand(EQBandType.BELL, 800.0, -1.5, 2.0),         # Boxiness
            EQBand(EQBandType.BELL, 3000.0, 1.5, 1.0),         # Presence
            EQBand(EQBandType.HIGH_SHELF, 10000.0, 2.5, 0.7),  # Air
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.GLUE,
            threshold=-20.0,
            ratio=3.0,
            attack=15.0,
            release=150.0,
        ),
        target_peak_db=-12.0,
        pan=0.0,
        width=1.5,
        notes="High-pass to make room for bass. Wide for size.",
    ),

    "pad": MixTemplate(
        track_type="pad",
        description="Lush pad sitting behind the mix",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 200.0, 0, 0.7),       # Aggressive HP
            EQBand(EQBandType.BELL, 400.0, -4.0, 1.5),         # Major mud cut
            EQBand(EQBandType.BELL, 1000.0, -2.0, 2.0),        # Clear mids
            EQBand(EQBandType.BELL, 4000.0, 1.5, 1.0),         # Shimmer
            EQBand(EQBandType.HIGH_SHELF, 12000.0, 2.5, 0.7),  # Air
            EQBand(EQBandType.LOW_PASS, 16000.0, 0, 0.7),      # Smooth top
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.TRANSPARENT,
            threshold=-25.0,
            ratio=2.0,
            attack=30.0,
            release=200.0,
        ),
        target_peak_db=-16.0,
        pan=0.0,
        width=2.0,  # Very wide
        notes="Sits back in mix. Very wide. Heavy low cut.",
    ),

    "arp": MixTemplate(
        track_type="arp",
        description="Defined arpeggio with movement",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 200.0, 0, 0.7),
            EQBand(EQBandType.BELL, 350.0, -2.0, 1.5),
            EQBand(EQBandType.BELL, 1500.0, 2.0, 1.5),         # Definition
            EQBand(EQBandType.BELL, 5000.0, 2.5, 1.0),         # Brightness
            EQBand(EQBandType.HIGH_SHELF, 10000.0, 2.0, 0.7),
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.PUNCHY,
            threshold=-22.0,
            ratio=3.0,
            attack=5.0,
            release=80.0,
        ),
        target_peak_db=-14.0,
        pan=0.0,
        width=1.4,
        notes="Defined with punch. Moderate width.",
    ),

    "pluck": MixTemplate(
        track_type="pluck",
        description="Sharp pluck synth",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 180.0, 0, 0.7),
            EQBand(EQBandType.BELL, 400.0, -2.0, 1.5),
            EQBand(EQBandType.BELL, 2000.0, 2.5, 1.5),
            EQBand(EQBandType.HIGH_SHELF, 8000.0, 2.0, 0.7),
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.PUNCHY,
            threshold=-20.0,
            ratio=4.0,
            attack=2.0,
            release=60.0,
        ),
        target_peak_db=-12.0,
        pan=0.0,
        width=1.3,
        notes="Sharp transients. Fast compression.",
    ),

    # =========================================================================
    # LEADS
    # =========================================================================
    "lead": MixTemplate(
        track_type="lead",
        description="Present lead cutting through mix",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 120.0, 0, 0.7),
            EQBand(EQBandType.BELL, 250.0, -2.5, 1.5),         # Clear mud
            EQBand(EQBandType.BELL, 800.0, -1.5, 2.0),         # Boxiness
            EQBand(EQBandType.BELL, 3000.0, 3.0, 1.0),         # Presence
            EQBand(EQBandType.HIGH_SHELF, 8000.0, 3.0, 0.7),   # Air/brilliance
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.GLUE,
            threshold=-16.0,
            ratio=3.0,
            attack=8.0,
            release=100.0,
        ),
        target_peak_db=-8.0,
        pan=0.0,
        width=1.4,
        notes="Main element. Boost presence at 3kHz. Sits on top.",
    ),

    "vox": MixTemplate(
        track_type="vox",
        description="Clear vocal with presence",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 80.0, 0, 0.7),
            EQBand(EQBandType.BELL, 200.0, -2.5, 2.0),         # Mud
            EQBand(EQBandType.BELL, 500.0, -2.0, 2.0),         # Boxiness
            EQBand(EQBandType.BELL, 2500.0, 2.5, 1.5),         # Presence
            EQBand(EQBandType.HIGH_SHELF, 8000.0, 3.5, 0.7),   # Air
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.WARM,
            threshold=-20.0,
            ratio=4.0,
            attack=8.0,
            release=80.0,
        ),
        target_peak_db=-10.0,
        pan=0.0,
        width=1.2,
        notes="Clear and present. De-ess if needed. Moderate compression.",
    ),

    # =========================================================================
    # FX
    # =========================================================================
    "riser": MixTemplate(
        track_type="riser",
        description="Wide riser effect",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 200.0, 0, 0.7),
            EQBand(EQBandType.BELL, 1000.0, 1.5, 1.5),
            EQBand(EQBandType.HIGH_SHELF, 8000.0, 3.0, 0.7),
        ],
        compressor=None,  # Usually no compression needed
        target_peak_db=-12.0,
        pan=0.0,
        width=2.0,
        notes="Very wide. No compression usually needed.",
    ),

    "impact": MixTemplate(
        track_type="impact",
        description="Punchy impact with sub",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 30.0, 0, 0.7),
            EQBand(EQBandType.LOW_SHELF, 60.0, 4.0, 0.7),      # Sub punch
            EQBand(EQBandType.HIGH_SHELF, 6000.0, 2.5, 0.7),   # Crash
        ],
        compressor=CompressorSettings(
            style=CompressorStyle.LIMITING,
            threshold=-6.0,
            ratio=10.0,
            attack=0.5,
            release=50.0,
        ),
        target_peak_db=-6.0,
        pan=0.0,
        width=1.8,
        notes="Loud and punchy. Limit hard.",
    ),

    "atmosphere": MixTemplate(
        track_type="atmosphere",
        description="Background atmosphere texture",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 300.0, 0, 0.7),       # Stay out of bass
            EQBand(EQBandType.BELL, 500.0, -3.0, 1.5),         # Major mud cut
            EQBand(EQBandType.HIGH_SHELF, 10000.0, 1.5, 0.7),  # Subtle air
            EQBand(EQBandType.LOW_PASS, 14000.0, 0, 0.7),      # Smooth
        ],
        compressor=None,
        target_peak_db=-20.0,
        pan=0.0,
        width=2.0,
        notes="Very background. Heavy filtering. No compression.",
    ),

    "texture": MixTemplate(
        track_type="texture",
        description="Subtle texture layer",
        eq_bands=[
            EQBand(EQBandType.HIGH_PASS, 400.0, 0, 0.7),
            EQBand(EQBandType.BELL, 1000.0, -2.5, 2.0),
            EQBand(EQBandType.HIGH_SHELF, 8000.0, 1.5, 0.7),
        ],
        compressor=None,
        target_peak_db=-22.0,
        pan=0.0,
        width=2.0,
        notes="Very subtle. Sits way back.",
    ),
}


# =============================================================================
# MIX TEMPLATE MANAGER CLASS
# =============================================================================

class MixTemplateManager:
    """
    Manages mix templates for tracks.

    Usage:
        manager = MixTemplateManager()
        template = manager.get_template("lead")
        eq_settings = manager.get_eq_for_track("lead")
    """

    def __init__(self, genre: str = "trance"):
        self.genre = genre.lower()
        self._custom_templates: Dict[str, MixTemplate] = {}

    def get_template(self, track_type: str) -> Optional[MixTemplate]:
        """
        Get mix template for a track type.

        Args:
            track_type: Type of track (kick, bass, lead, etc.)

        Returns:
            MixTemplate or None
        """
        track_lower = track_type.lower()

        # Check custom templates first
        if track_lower in self._custom_templates:
            return self._custom_templates[track_lower]

        # Check built-in templates
        if track_lower in MIX_TEMPLATES:
            return MIX_TEMPLATES[track_lower]

        # Try partial match
        for key in MIX_TEMPLATES:
            if key in track_lower or track_lower in key:
                return MIX_TEMPLATES[key]

        return None

    def add_template(self, template: MixTemplate):
        """Add a custom template."""
        self._custom_templates[template.track_type.lower()] = template

    def get_eq_bands(self, track_type: str) -> List[Dict]:
        """Get EQ band settings for Ableton EQ Eight."""
        template = self.get_template(track_type)
        if not template:
            return []

        return [band.to_ableton_params() for band in template.eq_bands]

    def get_compressor_settings(self, track_type: str) -> Optional[Dict]:
        """Get compressor settings for Ableton Compressor."""
        template = self.get_template(track_type)
        if not template or not template.compressor:
            return None

        return template.compressor.to_ableton_params()

    def get_gain_target(self, track_type: str) -> Tuple[float, float]:
        """Get target peak and RMS levels."""
        template = self.get_template(track_type)
        if not template:
            return (-6.0, -18.0)

        return (template.target_peak_db, template.target_rms_db)

    def get_stereo_settings(self, track_type: str) -> Tuple[float, float]:
        """Get pan and width settings."""
        template = self.get_template(track_type)
        if not template:
            return (0.0, 1.0)

        return (template.pan, template.width)

    def get_hp_frequency(self, track_type: str) -> Optional[float]:
        """Get recommended high-pass filter frequency."""
        template = self.get_template(track_type)
        if template:
            return template.get_hp_frequency()
        return None

    def get_all_settings(self, track_type: str) -> Dict:
        """Get all mix settings for a track."""
        template = self.get_template(track_type)
        if not template:
            return {}

        return {
            "track_type": track_type,
            "eq_bands": self.get_eq_bands(track_type),
            "compressor": self.get_compressor_settings(track_type),
            "target_peak_db": template.target_peak_db,
            "target_rms_db": template.target_rms_db,
            "pan": template.pan,
            "width": template.width,
            "notes": template.notes,
        }

    def print_summary(self, tracks: List[str] = None):
        """Print human-readable summary."""
        if tracks is None:
            tracks = list(MIX_TEMPLATES.keys())

        print(f"\nMIX TEMPLATES")
        print("-" * 60)

        for track in tracks:
            template = self.get_template(track)
            if template:
                print(f"\n  {track.upper()}")
                print(f"    HP: {template.get_hp_frequency() or 'None'} Hz")
                print(f"    Peak: {template.target_peak_db} dB")
                print(f"    Width: {template.width:.1f}")

                if template.compressor:
                    c = template.compressor
                    print(f"    Comp: {c.style.value} "
                          f"({c.ratio:.1f}:1, {c.attack:.0f}ms atk)")

                if template.notes:
                    print(f"    Notes: {template.notes[:50]}...")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_mix_template(track_type: str) -> Optional[MixTemplate]:
    """Get mix template for a track type."""
    manager = MixTemplateManager()
    return manager.get_template(track_type)


def get_eq_for_track(track_type: str) -> List[Dict]:
    """Get EQ settings for a track type."""
    manager = MixTemplateManager()
    return manager.get_eq_bands(track_type)


def get_compression_for_track(track_type: str) -> Optional[Dict]:
    """Get compression settings for a track type."""
    manager = MixTemplateManager()
    return manager.get_compressor_settings(track_type)


def get_hp_frequency(track_type: str) -> Optional[float]:
    """Get recommended high-pass frequency for a track."""
    manager = MixTemplateManager()
    return manager.get_hp_frequency(track_type)


def get_available_templates() -> List[str]:
    """Get list of available template track types."""
    return list(MIX_TEMPLATES.keys())


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MIX TEMPLATES - Demo")
    print("=" * 60)

    manager = MixTemplateManager()

    # Show all templates
    tracks = ["kick", "bass", "lead", "pad", "chords", "hats", "clap"]
    manager.print_summary(tracks)

    # Detailed example
    print("\n" + "=" * 60)
    print("DETAILED: Bass Template")
    print("=" * 60)

    bass = manager.get_template("bass")
    if bass:
        print(f"\n  Description: {bass.description}")
        print(f"\n  EQ Bands:")
        for i, band in enumerate(bass.eq_bands):
            print(f"    {i+1}. {band.band_type.value:12} @ {band.frequency:6.0f}Hz "
                  f"({band.gain:+.1f}dB, Q={band.q:.1f})")

        if bass.compressor:
            c = bass.compressor
            print(f"\n  Compressor ({c.style.value}):")
            print(f"    Threshold: {c.threshold} dB")
            print(f"    Ratio: {c.ratio}:1")
            print(f"    Attack: {c.attack} ms")
            print(f"    Release: {c.release} ms")

        print(f"\n  Targets:")
        print(f"    Peak: {bass.target_peak_db} dB")
        print(f"    RMS: {bass.target_rms_db} dB")
        print(f"    Width: {bass.width}")

        print(f"\n  Notes: {bass.notes}")

    # Quick access functions
    print("\n" + "=" * 60)
    print("QUICK ACCESS")
    print("=" * 60)

    for track in ["kick", "lead", "pad"]:
        hp = get_hp_frequency(track)
        print(f"\n  {track}: HP @ {hp} Hz" if hp else f"\n  {track}: No HP")

        comp = get_compression_for_track(track)
        if comp:
            print(f"    Comp: {comp['Ratio']}:1, {comp['Attack']}ms atk")

    print("\nAvailable templates:", get_available_templates())

    print("\nDone!")
