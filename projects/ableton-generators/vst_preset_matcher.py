"""
VST Preset Matcher - Intelligent Preset Suggestions

Suggests VST/synth presets based on:
- Descriptive text (e.g., "fat supersaw lead")
- Track type (kick, bass, lead, etc.)
- Genre and subgenre
- Mood/energy

Supports common synths:
- Serum, Sylenth1, Diva, Massive, Vital, Omnisphere
- Native Instruments (Massive, FM8, Reaktor)
- Ableton built-ins (Wavetable, Operator, Analog)

Features:
- Natural language matching
- Tag-based filtering
- Genre-specific recommendations
- Fallback chains for missing synths
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum
import re


class SynthType(Enum):
    """Types of synthesizers."""
    WAVETABLE = "wavetable"
    SUBTRACTIVE = "subtractive"
    FM = "fm"
    ANALOG = "analog"
    HYBRID = "hybrid"
    SAMPLER = "sampler"
    GRANULAR = "granular"


class SoundCategory(Enum):
    """Categories of sounds."""
    LEAD = "lead"
    BASS = "bass"
    PAD = "pad"
    PLUCK = "pluck"
    ARP = "arp"
    CHORD = "chord"
    KEY = "key"
    FX = "fx"
    DRUM = "drum"
    TEXTURE = "texture"
    VOCAL = "vocal"


@dataclass
class PresetInfo:
    """Information about a VST preset."""
    name: str
    synth: str                          # e.g., "Serum", "Sylenth1"
    category: SoundCategory
    tags: List[str] = field(default_factory=list)  # e.g., ["supersaw", "bright", "trance"]
    genres: List[str] = field(default_factory=list)  # e.g., ["trance", "edm"]
    moods: List[str] = field(default_factory=list)   # e.g., ["euphoric", "dark"]
    energy_range: Tuple[float, float] = (0.0, 1.0)   # Min/max energy
    bank: str = ""                      # Preset bank name
    author: str = ""                    # Preset author
    description: str = ""               # Optional description

    def matches_query(self, query: str) -> float:
        """
        Score how well this preset matches a search query.

        Returns 0-1 match score.
        """
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))

        score = 0.0
        max_score = 0.0

        # Name match (high weight)
        max_score += 3.0
        if query_lower in self.name.lower():
            score += 3.0
        else:
            name_words = set(re.findall(r'\w+', self.name.lower()))
            name_overlap = len(query_words & name_words) / max(1, len(query_words))
            score += name_overlap * 2.0

        # Tag matches (high weight)
        max_score += 3.0
        tag_set = set(t.lower() for t in self.tags)
        tag_overlap = len(query_words & tag_set) / max(1, len(query_words))
        score += tag_overlap * 3.0

        # Genre matches
        max_score += 2.0
        genre_set = set(g.lower() for g in self.genres)
        if query_words & genre_set:
            score += 2.0

        # Mood matches
        max_score += 2.0
        mood_set = set(m.lower() for m in self.moods)
        if query_words & mood_set:
            score += 2.0

        # Category match
        max_score += 1.0
        if self.category.value in query_lower:
            score += 1.0

        return score / max_score if max_score > 0 else 0.0

    def matches_tags(self, required_tags: List[str]) -> bool:
        """Check if preset has all required tags."""
        tag_set = set(t.lower() for t in self.tags)
        required_set = set(t.lower() for t in required_tags)
        return required_set.issubset(tag_set)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "synth": self.synth,
            "category": self.category.value,
            "tags": self.tags,
            "genres": self.genres,
            "moods": self.moods,
            "energy_range": list(self.energy_range),
            "bank": self.bank,
            "author": self.author,
            "description": self.description,
        }


@dataclass
class SynthInfo:
    """Information about a synthesizer."""
    name: str
    synth_type: SynthType
    preset_extension: str = ""          # e.g., ".fxp", ".nmsv"
    preset_path: str = ""               # Default preset location
    is_native: bool = False             # Built into DAW
    alternatives: List[str] = field(default_factory=list)  # Fallback synths


# =============================================================================
# SYNTH DATABASE
# =============================================================================

SYNTH_DATABASE: Dict[str, SynthInfo] = {
    # Xfer Records
    "serum": SynthInfo(
        name="Serum",
        synth_type=SynthType.WAVETABLE,
        preset_extension=".fxp",
        alternatives=["vital", "wavetable", "massive"],
    ),

    # LennarDigital
    "sylenth1": SynthInfo(
        name="Sylenth1",
        synth_type=SynthType.SUBTRACTIVE,
        preset_extension=".fxb",
        alternatives=["diva", "analog", "serum"],
    ),

    # u-he
    "diva": SynthInfo(
        name="Diva",
        synth_type=SynthType.ANALOG,
        preset_extension=".h2p",
        alternatives=["sylenth1", "analog", "repro"],
    ),

    # Native Instruments
    "massive": SynthInfo(
        name="Massive",
        synth_type=SynthType.WAVETABLE,
        preset_extension=".nmsv",
        alternatives=["serum", "vital", "massive_x"],
    ),
    "massive_x": SynthInfo(
        name="Massive X",
        synth_type=SynthType.WAVETABLE,
        alternatives=["serum", "massive", "vital"],
    ),
    "fm8": SynthInfo(
        name="FM8",
        synth_type=SynthType.FM,
        alternatives=["operator", "dexed", "sytrus"],
    ),

    # Vital
    "vital": SynthInfo(
        name="Vital",
        synth_type=SynthType.WAVETABLE,
        preset_extension=".vital",
        alternatives=["serum", "massive", "wavetable"],
    ),

    # Spectrasonics
    "omnisphere": SynthInfo(
        name="Omnisphere",
        synth_type=SynthType.HYBRID,
        alternatives=["serum", "massive", "kontakt"],
    ),

    # Ableton Native
    "wavetable": SynthInfo(
        name="Wavetable",
        synth_type=SynthType.WAVETABLE,
        is_native=True,
        alternatives=["serum", "vital"],
    ),
    "operator": SynthInfo(
        name="Operator",
        synth_type=SynthType.FM,
        is_native=True,
        alternatives=["fm8", "dexed"],
    ),
    "analog": SynthInfo(
        name="Analog",
        synth_type=SynthType.ANALOG,
        is_native=True,
        alternatives=["diva", "sylenth1"],
    ),
    "drift": SynthInfo(
        name="Drift",
        synth_type=SynthType.SUBTRACTIVE,
        is_native=True,
        alternatives=["analog", "sylenth1"],
    ),
    "simpler": SynthInfo(
        name="Simpler",
        synth_type=SynthType.SAMPLER,
        is_native=True,
    ),
    "sampler": SynthInfo(
        name="Sampler",
        synth_type=SynthType.SAMPLER,
        is_native=True,
        alternatives=["kontakt"],
    ),

    # Roland
    "juno": SynthInfo(
        name="JUNO-106",
        synth_type=SynthType.ANALOG,
        alternatives=["diva", "analog", "tal_uno"],
    ),
}


# =============================================================================
# PRESET DATABASE
# =============================================================================

# This is a curated database of preset suggestions
# In production, this would be loaded from a JSON file or database

PRESET_DATABASE: List[PresetInfo] = [
    # ==========================================================================
    # LEADS
    # ==========================================================================

    # Supersaw Leads
    PresetInfo(
        name="Trance Supersaw",
        synth="Serum",
        category=SoundCategory.LEAD,
        tags=["supersaw", "bright", "wide", "unison", "detuned"],
        genres=["trance", "edm", "progressive"],
        moods=["euphoric", "uplifting", "energetic"],
        energy_range=(0.6, 1.0),
        bank="Factory",
    ),
    PresetInfo(
        name="Massive Saw Lead",
        synth="Sylenth1",
        category=SoundCategory.LEAD,
        tags=["supersaw", "fat", "warm", "analog"],
        genres=["trance", "house", "edm"],
        moods=["euphoric", "warm"],
        energy_range=(0.5, 1.0),
        bank="Factory",
    ),
    PresetInfo(
        name="Hoover Lead",
        synth="Serum",
        category=SoundCategory.LEAD,
        tags=["hoover", "mentasm", "rave", "aggressive"],
        genres=["hardstyle", "rave", "hardcore"],
        moods=["aggressive", "dark", "intense"],
        energy_range=(0.7, 1.0),
    ),
    PresetInfo(
        name="Pluck Lead",
        synth="Vital",
        category=SoundCategory.LEAD,
        tags=["pluck", "sharp", "bright", "short"],
        genres=["trance", "progressive", "house"],
        moods=["euphoric", "energetic"],
        energy_range=(0.4, 0.9),
    ),
    PresetInfo(
        name="Anthem Lead",
        synth="Serum",
        category=SoundCategory.LEAD,
        tags=["anthem", "supersaw", "epic", "massive"],
        genres=["trance", "bigroom", "festival"],
        moods=["euphoric", "uplifting", "epic"],
        energy_range=(0.8, 1.0),
        description="Classic trance anthem supersaw",
    ),

    # FM Leads
    PresetInfo(
        name="DX7 Electric Piano",
        synth="Operator",
        category=SoundCategory.KEY,
        tags=["fm", "electric_piano", "classic", "80s"],
        genres=["synthwave", "pop", "house"],
        moods=["warm", "nostalgic"],
        energy_range=(0.3, 0.7),
    ),
    PresetInfo(
        name="FM Bell Lead",
        synth="FM8",
        category=SoundCategory.LEAD,
        tags=["fm", "bell", "metallic", "bright"],
        genres=["trance", "techno", "ambient"],
        moods=["ethereal", "bright"],
        energy_range=(0.3, 0.8),
    ),

    # ==========================================================================
    # BASS
    # ==========================================================================

    # Sub Bass
    PresetInfo(
        name="Pure Sub",
        synth="Serum",
        category=SoundCategory.BASS,
        tags=["sub", "sine", "clean", "deep"],
        genres=["all"],
        moods=["all"],
        energy_range=(0.0, 1.0),
        description="Clean sine sub bass",
    ),
    PresetInfo(
        name="808 Sub",
        synth="Serum",
        category=SoundCategory.BASS,
        tags=["808", "sub", "trap", "long"],
        genres=["trap", "hip_hop", "drill"],
        moods=["dark", "hard"],
        energy_range=(0.4, 1.0),
    ),

    # Acid Bass
    PresetInfo(
        name="303 Acid",
        synth="Diva",
        category=SoundCategory.BASS,
        tags=["303", "acid", "squelchy", "resonant"],
        genres=["techno", "acid", "house"],
        moods=["hypnotic", "aggressive"],
        energy_range=(0.5, 1.0),
    ),
    PresetInfo(
        name="Acid Bassline",
        synth="Sylenth1",
        category=SoundCategory.BASS,
        tags=["acid", "rolling", "resonant"],
        genres=["trance", "techno"],
        moods=["hypnotic", "dark"],
        energy_range=(0.5, 0.9),
    ),

    # Wobble/Dubstep Bass
    PresetInfo(
        name="Dubstep Wobble",
        synth="Serum",
        category=SoundCategory.BASS,
        tags=["wobble", "dubstep", "growl", "aggressive"],
        genres=["dubstep", "riddim", "bass_music"],
        moods=["aggressive", "dark", "intense"],
        energy_range=(0.7, 1.0),
    ),
    PresetInfo(
        name="Reese Bass",
        synth="Massive",
        category=SoundCategory.BASS,
        tags=["reese", "dark", "detuned", "dnb"],
        genres=["dnb", "neurofunk", "darkstep"],
        moods=["dark", "aggressive"],
        energy_range=(0.6, 1.0),
    ),

    # Trance Bass
    PresetInfo(
        name="Rolling Trance Bass",
        synth="Sylenth1",
        category=SoundCategory.BASS,
        tags=["rolling", "16th", "trance", "sidechained"],
        genres=["trance", "uplifting"],
        moods=["euphoric", "energetic"],
        energy_range=(0.5, 1.0),
    ),
    PresetInfo(
        name="Psy Bass",
        synth="Serum",
        category=SoundCategory.BASS,
        tags=["psy", "twisted", "modulated", "rolling"],
        genres=["psytrance", "goa"],
        moods=["hypnotic", "psychedelic"],
        energy_range=(0.6, 1.0),
    ),

    # ==========================================================================
    # PADS
    # ==========================================================================

    PresetInfo(
        name="Warm Analog Pad",
        synth="Diva",
        category=SoundCategory.PAD,
        tags=["warm", "analog", "lush", "vintage"],
        genres=["all"],
        moods=["warm", "melancholic", "nostalgic"],
        energy_range=(0.2, 0.7),
    ),
    PresetInfo(
        name="Supersaw Pad",
        synth="Sylenth1",
        category=SoundCategory.PAD,
        tags=["supersaw", "wide", "bright", "trance"],
        genres=["trance", "edm"],
        moods=["euphoric", "uplifting"],
        energy_range=(0.3, 0.8),
    ),
    PresetInfo(
        name="Dark Ambient Pad",
        synth="Omnisphere",
        category=SoundCategory.PAD,
        tags=["dark", "ambient", "evolving", "cinematic"],
        genres=["ambient", "cinematic", "darkwave"],
        moods=["dark", "mysterious", "tense"],
        energy_range=(0.1, 0.5),
    ),
    PresetInfo(
        name="Ethereal Pad",
        synth="Vital",
        category=SoundCategory.PAD,
        tags=["ethereal", "airy", "spacious", "reverb"],
        genres=["ambient", "trance", "chillout"],
        moods=["ethereal", "dreamy", "peaceful"],
        energy_range=(0.1, 0.5),
    ),
    PresetInfo(
        name="Choir Pad",
        synth="Omnisphere",
        category=SoundCategory.PAD,
        tags=["choir", "vocal", "lush", "epic"],
        genres=["trance", "cinematic", "epic"],
        moods=["epic", "euphoric", "emotional"],
        energy_range=(0.3, 0.8),
    ),

    # ==========================================================================
    # PLUCKS / ARPS
    # ==========================================================================

    PresetInfo(
        name="Trance Pluck",
        synth="Serum",
        category=SoundCategory.PLUCK,
        tags=["pluck", "sharp", "bright", "trance"],
        genres=["trance", "progressive"],
        moods=["euphoric", "energetic"],
        energy_range=(0.4, 0.9),
    ),
    PresetInfo(
        name="Soft Pluck",
        synth="Sylenth1",
        category=SoundCategory.PLUCK,
        tags=["pluck", "soft", "warm", "mellow"],
        genres=["house", "deep_house", "progressive"],
        moods=["warm", "mellow", "chill"],
        energy_range=(0.2, 0.6),
    ),
    PresetInfo(
        name="FM Pluck",
        synth="Operator",
        category=SoundCategory.PLUCK,
        tags=["fm", "pluck", "metallic", "bell"],
        genres=["techno", "idm", "electronica"],
        moods=["cold", "digital", "precise"],
        energy_range=(0.3, 0.8),
    ),
    PresetInfo(
        name="Arp Synth",
        synth="Vital",
        category=SoundCategory.ARP,
        tags=["arp", "sequence", "rhythmic", "bright"],
        genres=["trance", "progressive", "edm"],
        moods=["energetic", "driving"],
        energy_range=(0.4, 0.9),
    ),

    # ==========================================================================
    # FX / TEXTURES
    # ==========================================================================

    PresetInfo(
        name="Riser Sweep",
        synth="Serum",
        category=SoundCategory.FX,
        tags=["riser", "sweep", "build", "noise"],
        genres=["all"],
        moods=["all"],
        energy_range=(0.5, 0.9),
    ),
    PresetInfo(
        name="Impact Hit",
        synth="Serum",
        category=SoundCategory.FX,
        tags=["impact", "hit", "crash", "drop"],
        genres=["all"],
        moods=["all"],
        energy_range=(0.8, 1.0),
    ),
    PresetInfo(
        name="Downlifter",
        synth="Serum",
        category=SoundCategory.FX,
        tags=["downlifter", "sweep", "fall", "transition"],
        genres=["all"],
        moods=["all"],
        energy_range=(0.0, 0.5),
    ),
    PresetInfo(
        name="White Noise",
        synth="Wavetable",
        category=SoundCategory.FX,
        tags=["noise", "white", "sweep", "texture"],
        genres=["all"],
        moods=["all"],
        energy_range=(0.0, 1.0),
    ),
    PresetInfo(
        name="Atmosphere Texture",
        synth="Omnisphere",
        category=SoundCategory.TEXTURE,
        tags=["atmosphere", "ambient", "evolving", "background"],
        genres=["all"],
        moods=["ethereal", "mysterious", "dark"],
        energy_range=(0.1, 0.6),
    ),

    # ==========================================================================
    # DRUMS (for reference/layering)
    # ==========================================================================

    PresetInfo(
        name="Trance Kick",
        synth="Sampler",
        category=SoundCategory.DRUM,
        tags=["kick", "punchy", "trance", "4x4"],
        genres=["trance", "edm"],
        moods=["energetic"],
        energy_range=(0.3, 1.0),
    ),
    PresetInfo(
        name="Techno Kick",
        synth="Operator",
        category=SoundCategory.DRUM,
        tags=["kick", "heavy", "techno", "industrial"],
        genres=["techno", "industrial"],
        moods=["dark", "aggressive"],
        energy_range=(0.4, 1.0),
    ),
]


# =============================================================================
# PRESET MATCHER CLASS
# =============================================================================

class VSTPresetMatcher:
    """
    Matches descriptions to VST presets.

    Usage:
        matcher = VSTPresetMatcher()
        results = matcher.search("fat supersaw lead", genre="trance")
        for preset in results:
            print(f"{preset.name} ({preset.synth})")
    """

    def __init__(
        self,
        preset_db: List[PresetInfo] = None,
        synth_db: Dict[str, SynthInfo] = None,
        available_synths: List[str] = None
    ):
        self.presets = preset_db or PRESET_DATABASE
        self.synths = synth_db or SYNTH_DATABASE
        self.available_synths = set(s.lower() for s in (available_synths or []))

    def set_available_synths(self, synths: List[str]):
        """Set which synths are available on this system."""
        self.available_synths = set(s.lower() for s in synths)

    def search(
        self,
        query: str = "",
        category: SoundCategory = None,
        genre: str = None,
        mood: str = None,
        energy: float = None,
        tags: List[str] = None,
        synth: str = None,
        limit: int = 10,
        include_alternatives: bool = True
    ) -> List[PresetInfo]:
        """
        Search for matching presets.

        Args:
            query: Natural language search query
            category: Filter by sound category
            genre: Filter by genre
            mood: Filter by mood
            energy: Filter by energy level (0-1)
            tags: Required tags
            synth: Filter by specific synth
            limit: Maximum results
            include_alternatives: Include presets from alternative synths

        Returns:
            List of matching PresetInfo objects, sorted by relevance
        """
        results = []

        for preset in self.presets:
            score = 0.0

            # Query matching
            if query:
                query_score = preset.matches_query(query)
                if query_score < 0.1:
                    continue
                score += query_score * 5

            # Category filter
            if category and preset.category != category:
                continue
            elif category:
                score += 1.0

            # Genre filter
            if genre:
                genre_lower = genre.lower()
                if genre_lower in [g.lower() for g in preset.genres] or "all" in preset.genres:
                    score += 2.0
                else:
                    score -= 0.5  # Penalty but don't exclude

            # Mood filter
            if mood:
                mood_lower = mood.lower()
                if mood_lower in [m.lower() for m in preset.moods] or "all" in preset.moods:
                    score += 2.0
                else:
                    score -= 0.3

            # Energy filter
            if energy is not None:
                if preset.energy_range[0] <= energy <= preset.energy_range[1]:
                    score += 1.0
                else:
                    continue  # Strict energy filtering

            # Tag filter
            if tags and not preset.matches_tags(tags):
                continue

            # Synth filter
            if synth:
                if preset.synth.lower() != synth.lower():
                    if include_alternatives:
                        synth_info = self.synths.get(synth.lower())
                        if synth_info and preset.synth.lower() not in [a.lower() for a in synth_info.alternatives]:
                            continue
                        score -= 0.5  # Penalty for alternative
                    else:
                        continue
            else:
                score += 1.0

            # Availability bonus
            if self.available_synths:
                if preset.synth.lower() in self.available_synths:
                    score += 2.0
                else:
                    score -= 1.0  # Penalty but still include

            results.append((score, preset))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)

        return [preset for _, preset in results[:limit]]

    def get_preset_for_track(
        self,
        track_type: str,
        genre: str = "trance",
        mood: str = "euphoric",
        energy: float = 0.7,
        hint: str = ""
    ) -> List[PresetInfo]:
        """
        Get preset suggestions for a track type.

        Args:
            track_type: Type of track (kick, bass, lead, etc.)
            genre: Music genre
            mood: Track mood
            energy: Energy level 0-1
            hint: Additional description hint

        Returns:
            List of suggested presets
        """
        # Map track types to categories
        track_to_category = {
            "kick": SoundCategory.DRUM,
            "bass": SoundCategory.BASS,
            "sub": SoundCategory.BASS,
            "lead": SoundCategory.LEAD,
            "chords": SoundCategory.PAD,
            "pad": SoundCategory.PAD,
            "arp": SoundCategory.PLUCK,
            "pluck": SoundCategory.PLUCK,
            "fx": SoundCategory.FX,
            "riser": SoundCategory.FX,
            "impact": SoundCategory.FX,
            "atmosphere": SoundCategory.TEXTURE,
            "texture": SoundCategory.TEXTURE,
        }

        category = track_to_category.get(track_type.lower())

        # Build search query
        query = f"{track_type} {hint}".strip()

        return self.search(
            query=query,
            category=category,
            genre=genre,
            mood=mood,
            energy=energy,
            limit=5
        )

    def suggest_for_song(
        self,
        genre: str = "trance",
        mood: str = "euphoric",
        track_types: List[str] = None
    ) -> Dict[str, List[PresetInfo]]:
        """
        Get preset suggestions for an entire song.

        Args:
            genre: Music genre
            mood: Overall mood
            track_types: List of track types to get presets for

        Returns:
            Dict of track_type -> list of preset suggestions
        """
        if track_types is None:
            track_types = ["kick", "bass", "lead", "pad", "arp", "fx"]

        suggestions = {}

        for track in track_types:
            suggestions[track] = self.get_preset_for_track(
                track_type=track,
                genre=genre,
                mood=mood,
                energy=0.7 if track in ["lead", "bass"] else 0.5
            )

        return suggestions

    def get_synth_alternatives(self, synth: str) -> List[str]:
        """Get alternative synths for a given synth."""
        synth_info = self.synths.get(synth.lower())
        if synth_info:
            return synth_info.alternatives
        return []

    def format_preset_suggestion(self, preset: PresetInfo) -> str:
        """Format a preset suggestion as a readable string."""
        tags_str = ", ".join(preset.tags[:4])
        return f"{preset.name} ({preset.synth}) - [{tags_str}]"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def search_presets(query: str, genre: str = None, mood: str = None) -> List[PresetInfo]:
    """
    Quick preset search.

    Args:
        query: Search query
        genre: Optional genre filter
        mood: Optional mood filter

    Returns:
        List of matching presets
    """
    matcher = VSTPresetMatcher()
    return matcher.search(query=query, genre=genre, mood=mood, limit=10)


def get_preset_for_sound(
    description: str,
    genre: str = "trance"
) -> Optional[PresetInfo]:
    """
    Get best preset match for a sound description.

    Args:
        description: Natural language description (e.g., "fat supersaw lead")
        genre: Genre for context

    Returns:
        Best matching preset or None
    """
    matcher = VSTPresetMatcher()
    results = matcher.search(query=description, genre=genre, limit=1)
    return results[0] if results else None


def suggest_presets_for_track(
    track_name: str,
    track_hint: str = "",
    genre: str = "trance",
    mood: str = "euphoric"
) -> List[Tuple[str, str]]:
    """
    Get preset suggestions as (name, synth) tuples.

    Args:
        track_name: Name of the track
        track_hint: Additional description
        genre: Music genre
        mood: Track mood

    Returns:
        List of (preset_name, synth_name) tuples
    """
    matcher = VSTPresetMatcher()
    presets = matcher.get_preset_for_track(
        track_type=track_name,
        genre=genre,
        mood=mood,
        hint=track_hint
    )
    return [(p.name, p.synth) for p in presets]


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("VST PRESET MATCHER - Demo")
    print("=" * 60)

    matcher = VSTPresetMatcher()

    # Example searches
    print("\n--- Search: 'supersaw lead' (trance) ---")
    results = matcher.search("supersaw lead", genre="trance", limit=5)
    for preset in results:
        print(f"  {matcher.format_preset_suggestion(preset)}")

    print("\n--- Search: 'acid bass' (techno) ---")
    results = matcher.search("acid bass", genre="techno", limit=5)
    for preset in results:
        print(f"  {matcher.format_preset_suggestion(preset)}")

    print("\n--- Search: 'dark pad' (ambient) ---")
    results = matcher.search("dark pad", genre="ambient", mood="dark", limit=5)
    for preset in results:
        print(f"  {matcher.format_preset_suggestion(preset)}")

    print("\n--- Track-based suggestions (trance, euphoric) ---")
    tracks = ["lead", "bass", "pad", "arp"]
    for track in tracks:
        presets = matcher.get_preset_for_track(track, "trance", "euphoric")
        print(f"\n  {track.upper()}:")
        for p in presets[:3]:
            print(f"    - {p.name} ({p.synth})")

    print("\n--- Full song suggestions ---")
    song_presets = matcher.suggest_for_song(
        genre="trance",
        mood="euphoric",
        track_types=["kick", "bass", "lead", "pad", "arp", "fx"]
    )
    print()
    for track, presets in song_presets.items():
        print(f"  {track}:")
        for p in presets[:2]:
            print(f"    - {p.name} ({p.synth})")

    # Show available synth info
    print("\n--- Synth Alternatives ---")
    for synth in ["serum", "sylenth1", "diva"]:
        alts = matcher.get_synth_alternatives(synth)
        print(f"  {synth}: {', '.join(alts)}")

    print("\nDone!")
