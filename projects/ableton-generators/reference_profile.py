"""
Reference Profile Module

Extracts and stores generation-relevant parameters from reference tracks.
Works with both stored analytics JSON and live audio analysis.
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, List, Any

# Store current path for local imports
_GENERATOR_PATH = Path(__file__).parent
_MUSIC_ANALYZER_PATH = _GENERATOR_PATH.parent / "music-analyzer" / "src"


def _get_generator_config():
    """Get generator config without path conflicts."""
    # Ensure local path is first
    local_path = str(_GENERATOR_PATH)
    if local_path in sys.path:
        sys.path.remove(local_path)
    sys.path.insert(0, local_path)

    from config import DEFAULT_CONFIG
    return DEFAULT_CONFIG


def _get_audio_analyzer():
    """Get audio analyzer with proper path setup."""
    analyzer_path = str(_MUSIC_ANALYZER_PATH)
    if analyzer_path not in sys.path:
        sys.path.append(analyzer_path)

    from audio_analyzer import AudioAnalyzer
    return AudioAnalyzer()


# Get generator config at module load
GENERATOR_CONFIG = _get_generator_config()


@dataclass
class SectionProfile:
    """Profile for a song section (from reference analysis)."""
    section_type: str  # intro, buildup, drop, breakdown, outro
    start_bar: int
    bars: int
    energy: float  # 0.0-1.0
    rms_db: float
    transient_density: float  # transients per second


@dataclass
class FrequencyBalance:
    """Target frequency balance from reference."""
    sub_bass: float  # 20-60 Hz percentage
    bass: float  # 60-250 Hz
    low_mid: float  # 250-500 Hz
    mid: float  # 500-2000 Hz
    high_mid: float  # 2000-6000 Hz
    high: float  # 6000-10000 Hz
    air: float  # 10000-20000 Hz
    spectral_centroid_hz: float


@dataclass
class DynamicsProfile:
    """Target dynamics from reference."""
    peak_db: float
    rms_db: float
    dynamic_range_db: float
    integrated_lufs: float
    is_compressed: bool


@dataclass
class ReferenceProfile:
    """
    Generation-relevant parameters extracted from a reference track.

    Used to inform SongSpec generation to match reference characteristics.
    """
    # Source info
    name: str
    source_file: Optional[str] = None
    source_analytics: Optional[str] = None  # Path to analytics JSON

    # Core musical parameters
    tempo: float = 128.0
    key: Optional[str] = None
    scale: str = "minor"

    # Genre/mood hints (from metadata or detected)
    genre: str = "electronic"
    subgenre: str = "trance"
    mood: str = "energetic"

    # Duration and structure
    duration_seconds: float = 0.0
    total_bars: int = 0
    sections: List[SectionProfile] = field(default_factory=list)

    # Mix targets
    frequency_balance: Optional[FrequencyBalance] = None
    dynamics: Optional[DynamicsProfile] = None
    stereo_width_pct: float = 70.0

    # Section energy curve (for generation)
    intro_energy: float = 0.3
    buildup_energy: float = 0.6
    drop_energy: float = 1.0
    breakdown_energy: float = 0.4
    outro_energy: float = 0.2

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        return result

    def save(self, path: Path):
        """Save profile to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReferenceProfile":
        """Create from dictionary."""
        # Handle nested dataclasses
        if data.get("frequency_balance") and isinstance(data["frequency_balance"], dict):
            data["frequency_balance"] = FrequencyBalance(**data["frequency_balance"])
        if data.get("dynamics") and isinstance(data["dynamics"], dict):
            data["dynamics"] = DynamicsProfile(**data["dynamics"])
        if data.get("sections"):
            data["sections"] = [
                SectionProfile(**s) if isinstance(s, dict) else s
                for s in data["sections"]
            ]
        return cls(**data)

    @classmethod
    def load(cls, path: Path) -> "ReferenceProfile":
        """Load profile from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)


class ReferenceExtractor:
    """Extracts ReferenceProfile from audio files or stored analytics."""

    def __init__(self):
        self._analyzer = None

    @property
    def analyzer(self):
        """Lazy-load audio analyzer."""
        if self._analyzer is None:
            try:
                self._analyzer = _get_audio_analyzer()
            except ImportError:
                raise ImportError(
                    "AudioAnalyzer not available. Install librosa and other dependencies."
                )
        return self._analyzer

    def extract_from_analytics(self, analytics_path: Path) -> ReferenceProfile:
        """
        Extract ReferenceProfile from stored analytics JSON.

        Args:
            analytics_path: Path to analytics JSON file

        Returns:
            ReferenceProfile with extracted parameters
        """
        with open(analytics_path) as f:
            data = json.load(f)

        # Extract metadata
        metadata = data.get("metadata", {})
        full_mix = data.get("full_mix_metrics", {})

        # Build profile
        profile = ReferenceProfile(
            name=metadata.get("title") or Path(analytics_path).stem,
            source_analytics=str(analytics_path),
            source_file=metadata.get("file_path"),
            tempo=metadata.get("tempo_bpm") or full_mix.get("detected_tempo") or 128.0,
            key=metadata.get("key"),
            genre=metadata.get("genre") or "electronic",
            subgenre=metadata.get("subgenre") or "trance",
            duration_seconds=metadata.get("duration_seconds") or 0.0,
        )

        # Calculate total bars from tempo and duration
        if profile.tempo and profile.duration_seconds:
            beats = profile.duration_seconds * profile.tempo / 60
            profile.total_bars = int(beats / 4)

        # Extract frequency balance
        if full_mix:
            profile.frequency_balance = FrequencyBalance(
                sub_bass=full_mix.get("sub_bass_energy", 0) * 100,
                bass=full_mix.get("bass_energy", 0) * 100,
                low_mid=full_mix.get("low_mid_energy", 0) * 100,
                mid=full_mix.get("mid_energy", 0) * 100,
                high_mid=full_mix.get("high_mid_energy", 0) * 100,
                high=full_mix.get("high_energy", 0) * 100,
                air=full_mix.get("air_energy", 0) * 100,
                spectral_centroid_hz=full_mix.get("spectral_centroid_hz", 2000),
            )

            profile.dynamics = DynamicsProfile(
                peak_db=full_mix.get("peak_db", 0),
                rms_db=full_mix.get("rms_db", -12),
                dynamic_range_db=full_mix.get("dynamic_range_db", 12),
                integrated_lufs=full_mix.get("integrated_lufs", -14),
                is_compressed=full_mix.get("is_over_compressed", False),
            )

            profile.stereo_width_pct = full_mix.get("stereo_width_pct", 70)

        # Extract section info if available
        sections_data = data.get("sections", [])
        if sections_data:
            profile.sections = self._parse_sections(sections_data, profile.tempo)
            self._calculate_section_energies(profile)

        return profile

    def extract_from_audio(self, audio_path: Path,
                           genre: str = "trance",
                           subgenre: str = "uplifting") -> ReferenceProfile:
        """
        Analyze audio file and extract ReferenceProfile.

        Args:
            audio_path: Path to audio file (wav, mp3, etc.)
            genre: Genre hint for analysis
            subgenre: Subgenre hint

        Returns:
            ReferenceProfile with analyzed parameters
        """
        # Analyze the audio
        result = self.analyzer.analyze(str(audio_path))

        # Build profile
        profile = ReferenceProfile(
            name=audio_path.stem,
            source_file=str(audio_path),
            tempo=result.detected_tempo or 128.0,
            genre=genre,
            subgenre=subgenre,
            duration_seconds=result.duration_seconds,
        )

        # Calculate bars
        if profile.tempo and profile.duration_seconds:
            beats = profile.duration_seconds * profile.tempo / 60
            profile.total_bars = int(beats / 4)

        # Extract frequency balance
        freq = result.frequency
        profile.frequency_balance = FrequencyBalance(
            sub_bass=freq.sub_bass_energy * 100,
            bass=freq.bass_energy * 100,
            low_mid=freq.low_mid_energy * 100,
            mid=freq.mid_energy * 100,
            high_mid=freq.high_mid_energy * 100,
            high=freq.high_energy * 100,
            air=freq.air_energy * 100,
            spectral_centroid_hz=freq.spectral_centroid_hz,
        )

        # Extract dynamics
        dyn = result.dynamics
        loud = result.loudness
        profile.dynamics = DynamicsProfile(
            peak_db=dyn.peak_db,
            rms_db=dyn.rms_db,
            dynamic_range_db=dyn.dynamic_range_db,
            integrated_lufs=loud.integrated_lufs if loud else -14,
            is_compressed=dyn.is_over_compressed,
        )

        # Stereo width
        if result.stereo:
            profile.stereo_width_pct = result.stereo.width_estimate

        # Try to detect key if harmonic analysis available
        if result.harmonic and hasattr(result.harmonic, 'detected_key'):
            profile.key = result.harmonic.detected_key

        return profile

    def _parse_sections(self, sections_data: List[Dict], tempo: float) -> List[SectionProfile]:
        """Parse section data into SectionProfile objects."""
        profiles = []
        beats_per_second = tempo / 60 if tempo else 2

        for section in sections_data:
            start_time = section.get("start_time", 0)
            end_time = section.get("end_time", start_time + 30)
            duration = end_time - start_time

            start_bar = int((start_time * beats_per_second) / 4)
            bars = max(4, int((duration * beats_per_second) / 4))

            # Estimate energy from RMS
            rms_db = section.get("avg_rms_db", -20)
            # Map RMS roughly: -30dB = 0.2, -15dB = 0.8, -10dB = 1.0
            energy = max(0.1, min(1.0, (rms_db + 35) / 25))

            profiles.append(SectionProfile(
                section_type=section.get("section_type", "unknown"),
                start_bar=start_bar,
                bars=bars,
                energy=energy,
                rms_db=rms_db,
                transient_density=section.get("transient_density", 2.0),
            ))

        return profiles

    def _calculate_section_energies(self, profile: ReferenceProfile):
        """Calculate average energies for each section type."""
        section_energies = {
            "intro": [],
            "buildup": [],
            "drop": [],
            "breakdown": [],
            "outro": [],
        }

        for section in profile.sections:
            stype = section.section_type.lower()
            if stype in section_energies:
                section_energies[stype].append(section.energy)

        # Set average energies
        if section_energies["intro"]:
            profile.intro_energy = sum(section_energies["intro"]) / len(section_energies["intro"])
        if section_energies["buildup"]:
            profile.buildup_energy = sum(section_energies["buildup"]) / len(section_energies["buildup"])
        if section_energies["drop"]:
            profile.drop_energy = sum(section_energies["drop"]) / len(section_energies["drop"])
        if section_energies["breakdown"]:
            profile.breakdown_energy = sum(section_energies["breakdown"]) / len(section_energies["breakdown"])
        if section_energies["outro"]:
            profile.outro_energy = sum(section_energies["outro"]) / len(section_energies["outro"])


def find_reference_analytics(reference_dir: Path = None) -> List[Path]:
    """Find all reference analytics JSON files."""
    if reference_dir is None:
        reference_dir = Path(__file__).parent.parent / "music-analyzer" / "reference_library" / "analytics"

    if not reference_dir.exists():
        return []

    return list(reference_dir.glob("*.json"))


def list_available_profiles(reference_dir: Path = None) -> List[Dict[str, str]]:
    """List available reference profiles with metadata."""
    profiles = []

    for path in find_reference_analytics(reference_dir):
        try:
            with open(path) as f:
                data = json.load(f)

            metadata = data.get("metadata", {})
            profiles.append({
                "path": str(path),
                "name": metadata.get("title") or path.stem,
                "artist": metadata.get("artist", "Unknown"),
                "genre": metadata.get("genre", "unknown"),
                "tempo": metadata.get("tempo_bpm", 0),
            })
        except Exception:
            continue

    return profiles


def generate_from_profile(
    profile: ReferenceProfile,
    name: str = None,
    open_in_ableton: bool = False,
) -> dict:
    """
    Generate a track that matches the reference profile.

    Args:
        profile: ReferenceProfile to match
        name: Track name (defaults to "Match_<reference_name>")
        open_in_ableton: Open project after generation

    Returns:
        Generation result dict
    """
    import subprocess

    # Ensure local path is first for imports
    local_path = str(_GENERATOR_PATH)
    if local_path in sys.path:
        sys.path.remove(local_path)
    sys.path.insert(0, local_path)

    from song_spec import SongSpec, SectionSpec, SectionType, TrackSpec
    from ableton_project import AbletonProject

    if name is None:
        safe_name = profile.name.replace(" ", "_").replace("-", "_")
        name = f"Match_{safe_name}"

    # Map genre to structure type
    structure_type = "standard"
    if profile.subgenre == "progressive":
        structure_type = "progressive"
    elif profile.subgenre == "psytrance":
        structure_type = "psytrance"
    elif profile.genre == "techno":
        structure_type = "techno"
    elif profile.genre == "house":
        structure_type = "progressive_house"

    # Use profile's section structure if available, otherwise use template
    if profile.sections:
        structure = []
        for sec in profile.sections:
            section_type_map = {
                "intro": SectionType.INTRO,
                "buildup": SectionType.BUILDUP,
                "drop": SectionType.DROP,
                "breakdown": SectionType.BREAKDOWN,
                "break": SectionType.BREAK,
                "outro": SectionType.OUTRO,
            }
            stype = section_type_map.get(sec.section_type.lower(), SectionType.BREAK)

            # Determine active tracks based on section type and energy
            if stype == SectionType.INTRO:
                active = ["kick", "hats"]
            elif stype == SectionType.BUILDUP:
                active = ["kick", "bass", "arp", "hats", "clap"]
            elif stype == SectionType.DROP:
                active = ["kick", "bass", "chords", "arp", "lead", "hats", "clap"]
            elif stype == SectionType.BREAKDOWN:
                active = ["chords", "arp", "lead"]
            elif stype == SectionType.OUTRO:
                active = ["kick", "hats"]
            else:
                active = ["kick", "bass", "hats"]

            structure.append(SectionSpec(
                name=sec.section_type.title(),
                section_type=stype,
                start_bar=sec.start_bar,
                bars=sec.bars,
                energy=sec.energy,
                active_tracks=active,
            ))
    else:
        # Use default structure from preset
        from ai_song_generator import create_spec_from_preset
        # Map structure type to preset name
        preset_map = {
            "standard": "uplifting_trance",
            "progressive": "progressive",
            "radio": "radio_edit",
            "techno": "techno",
            "psytrance": "psytrance",
            "progressive_house": "progressive_house",
            "melodic_techno": "melodic_techno",
        }
        preset_name = preset_map.get(structure_type, "uplifting_trance")
        base_spec = create_spec_from_preset(preset_name, name)
        structure = base_spec.structure

    # Create tracks
    tracks = [
        TrackSpec("Kick", "midi", 0, "four_on_floor", "punchy kick"),
        TrackSpec("Bass", "midi", 1, "rolling", "rolling bass"),
        TrackSpec("Chords", "midi", 2, "sustained", "pad chords"),
        TrackSpec("Arp", "midi", 3, "trance", "pluck arpeggio"),
        TrackSpec("Lead", "midi", 4, "melody", "lead synth"),
        TrackSpec("Hats", "midi", 5, "offbeat", "hi-hats"),
        TrackSpec("Clap", "midi", 6, "standard", "clap/snare"),
    ]

    # Build spec
    spec = SongSpec(
        name=name,
        genre=profile.genre,
        subgenre=profile.subgenre,
        tempo=int(round(profile.tempo)),
        key=profile.key or "A",
        scale=profile.scale,
        mood=profile.mood,
        structure=structure,
        tracks=tracks,
        chord_progression=["Am", "F", "C", "G"],  # Default, could be inferred
        hints={
            "reference_name": profile.name,
            "reference_source": profile.source_file or profile.source_analytics,
            "target_dynamics": {
                "rms_db": float(profile.dynamics.rms_db) if profile.dynamics else -12,
                "dynamic_range": float(profile.dynamics.dynamic_range_db) if profile.dynamics else 12,
            },
            "target_frequency_balance": float(profile.frequency_balance.sub_bass) if profile.frequency_balance else None,
        }
    )

    # Generate
    project = AbletonProject(spec, GENERATOR_CONFIG)
    als_path = project.generate()

    result = {
        "success": True,
        "als_path": str(als_path),
        "midi_dir": str(project.midi_dir),
        "project_dir": str(als_path.parent),
        "spec": spec.to_dict(),
        "reference_profile": profile.to_dict(),
        "matched_parameters": {
            "tempo": profile.tempo,
            "key": profile.key,
            "genre": f"{profile.genre}/{profile.subgenre}",
            "sections": len(structure),
        }
    }

    if open_in_ableton:
        try:
            subprocess.Popen([str(GENERATOR_CONFIG.ABLETON_EXE), str(als_path)])
            result["opened_in_ableton"] = True
        except FileNotFoundError:
            result["opened_in_ableton"] = False

    return result


def generate_from_reference_audio(
    audio_path: Path,
    name: str = None,
    open_in_ableton: bool = False,
) -> dict:
    """
    Analyze a reference audio file and generate a matching track.

    Args:
        audio_path: Path to reference audio (mp3, wav)
        name: Track name
        open_in_ableton: Open in Ableton after generation

    Returns:
        Generation result dict
    """
    extractor = ReferenceExtractor()
    profile = extractor.extract_from_audio(Path(audio_path))
    return generate_from_profile(profile, name, open_in_ableton)


def generate_from_reference_analytics(
    analytics_path: Path,
    name: str = None,
    open_in_ableton: bool = False,
) -> dict:
    """
    Load stored analytics and generate a matching track.

    Args:
        analytics_path: Path to analytics JSON
        name: Track name
        open_in_ableton: Open in Ableton after generation

    Returns:
        Generation result dict
    """
    extractor = ReferenceExtractor()
    profile = extractor.extract_from_analytics(Path(analytics_path))
    return generate_from_profile(profile, name, open_in_ableton)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Reference Profile System")
    subparsers = parser.add_subparsers(dest="command")

    # List command
    list_parser = subparsers.add_parser("list", help="List available reference profiles")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze reference and show profile")
    analyze_parser.add_argument("path", type=Path, help="Path to audio or analytics JSON")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate track from reference")
    gen_parser.add_argument("path", type=Path, help="Path to audio or analytics JSON")
    gen_parser.add_argument("--name", "-n", help="Track name")
    gen_parser.add_argument("--open", action="store_true", help="Open in Ableton")

    args = parser.parse_args()

    if args.command == "list":
        print("\nAvailable Reference Profiles:")
        print("-" * 50)
        profiles = list_available_profiles()
        if profiles:
            for p in profiles:
                print(f"  {p['name']}")
                print(f"    Artist: {p['artist']}")
                print(f"    Tempo: {p['tempo']} BPM | Genre: {p['genre']}")
                print(f"    Path: {p['path']}")
                print()
        else:
            print("  No profiles found.")
            print("  Store reference analytics in music-analyzer/reference_library/analytics/")

    elif args.command == "analyze":
        extractor = ReferenceExtractor()
        if args.path.suffix == ".json":
            profile = extractor.extract_from_analytics(args.path)
        else:
            profile = extractor.extract_from_audio(args.path)

        print(f"\nReference Profile: {profile.name}")
        print("-" * 50)
        print(f"  Tempo: {profile.tempo} BPM")
        print(f"  Key: {profile.key} {profile.scale}")
        print(f"  Genre: {profile.genre} / {profile.subgenre}")
        print(f"  Duration: {profile.duration_seconds:.0f}s ({profile.total_bars} bars)")
        if profile.dynamics:
            print(f"  RMS: {profile.dynamics.rms_db:.1f} dB")
            print(f"  Dynamic Range: {profile.dynamics.dynamic_range_db:.1f} dB")
        print(f"  Sections: {len(profile.sections)}")

    elif args.command == "generate":
        print(f"\nAnalyzing reference: {args.path.name}")

        if args.path.suffix == ".json":
            result = generate_from_reference_analytics(args.path, args.name, args.open)
        else:
            result = generate_from_reference_audio(args.path, args.name, args.open)

        if result["success"]:
            print(f"\n[OK] Generated matching track!")
            print(f"  Project: {result['project_dir']}")
            print(f"  Matched: {result['matched_parameters']['tempo']} BPM, "
                  f"{result['matched_parameters']['key']}, "
                  f"{result['matched_parameters']['genre']}")
        else:
            print("\n[FAIL] Generation failed")

    else:
        parser.print_help()
