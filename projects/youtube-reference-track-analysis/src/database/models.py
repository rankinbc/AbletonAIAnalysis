"""
Data models for YouTube reference track analysis.

Dataclasses representing database entities and query results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import json


@dataclass
class YTTrack:
    """A YouTube track in the database."""
    id: Optional[int] = None
    youtube_id: str = ""
    youtube_url: str = ""
    title: Optional[str] = None
    artist: Optional[str] = None
    channel: Optional[str] = None
    duration_seconds: Optional[float] = None
    local_path: Optional[str] = None
    thumbnail_url: Optional[str] = None
    upload_date: Optional[str] = None

    # Status
    ingested_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    stems_separated_at: Optional[datetime] = None
    embeddings_generated_at: Optional[datetime] = None

    # User metadata
    genre_tag: str = "trance"
    user_tags: Optional[str] = None
    notes: Optional[str] = None

    # Rating (1-3 stars, None = unrated)
    # 1 = Good reference, 2 = Great reference, 3 = Top-tier favorite
    rating: Optional[int] = None

    @property
    def rating_stars(self) -> str:
        """Get rating as star string."""
        if self.rating is None:
            return "---"
        return "*" * self.rating + "-" * (3 - self.rating)

    @property
    def tags_list(self) -> List[str]:
        """Get user_tags as a list."""
        if not self.user_tags:
            return []
        return [t.strip() for t in self.user_tags.split(",")]

    @property
    def is_analyzed(self) -> bool:
        return self.analyzed_at is not None

    @property
    def has_stems(self) -> bool:
        return self.stems_separated_at is not None

    @property
    def has_embeddings(self) -> bool:
        return self.embeddings_generated_at is not None


@dataclass
class YTFeatures:
    """Audio features for a track."""
    id: Optional[int] = None
    track_id: int = 0

    # Rhythm
    bpm: Optional[float] = None
    bpm_confidence: Optional[float] = None
    time_signature: int = 4

    # Key
    key_name: Optional[str] = None
    key_camelot: Optional[str] = None
    key_confidence: Optional[float] = None

    # Loudness
    integrated_lufs: Optional[float] = None
    short_term_max_lufs: Optional[float] = None
    true_peak_db: Optional[float] = None
    loudness_range_lu: Optional[float] = None

    # Spectral
    spectral_centroid_hz: Optional[float] = None
    spectral_bandwidth_hz: Optional[float] = None
    spectral_rolloff_hz: Optional[float] = None
    spectral_flatness: Optional[float] = None

    # Dynamics
    dynamic_range_db: Optional[float] = None
    crest_factor_db: Optional[float] = None

    # Stereo
    stereo_width: Optional[float] = None
    stereo_correlation: Optional[float] = None
    mono_compatible: Optional[bool] = None

    analyzed_at: Optional[datetime] = None


@dataclass
class YTSection:
    """A detected section in a track."""
    id: Optional[int] = None
    track_id: int = 0

    section_type: str = ""  # intro, buildup, drop, breakdown, outro
    original_label: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    start_bar: Optional[int] = None
    end_bar: Optional[int] = None
    duration_bars: Optional[int] = None

    avg_energy: Optional[float] = None
    avg_spectral_centroid: Optional[float] = None

    section_index: int = 0

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time


@dataclass
class YTArrangementStats:
    """Trance-specific arrangement statistics."""
    id: Optional[int] = None
    track_id: int = 0

    # Structure timing
    total_bars: Optional[int] = None
    bars_to_first_drop: Optional[int] = None
    bars_to_first_breakdown: Optional[int] = None

    # Section counts
    num_drops: int = 0
    num_breakdowns: int = 0
    num_buildups: int = 0

    # Buildup analysis
    avg_buildup_length_bars: Optional[float] = None
    max_buildup_length_bars: Optional[int] = None

    # Drop analysis
    avg_drop_length_bars: Optional[float] = None
    first_drop_energy: Optional[float] = None
    drop_intensity_variance: Optional[float] = None

    # Breakdown analysis
    avg_breakdown_length_bars: Optional[float] = None

    # Phrase structure
    phrase_length_bars: Optional[int] = None
    phrase_regularity: Optional[float] = None

    # JSON fields
    filter_sweeps_json: Optional[str] = None
    risers_json: Optional[str] = None

    @property
    def filter_sweeps(self) -> List[dict]:
        if not self.filter_sweeps_json:
            return []
        return json.loads(self.filter_sweeps_json)

    @property
    def risers(self) -> List[dict]:
        if not self.risers_json:
            return []
        return json.loads(self.risers_json)


@dataclass
class YTEmbedding:
    """Audio embedding for similarity search."""
    id: Optional[int] = None
    track_id: int = 0
    embedding_type: str = ""  # panns, openl3
    section_id: Optional[int] = None
    embedding: bytes = b""
    embedding_dim: int = 0
    generated_at: Optional[datetime] = None


@dataclass
class YTStem:
    """Stem-level analysis data."""
    id: Optional[int] = None
    track_id: int = 0
    stem_type: str = ""  # drums, bass, vocals, other

    local_path: Optional[str] = None
    peak_db: Optional[float] = None
    rms_db: Optional[float] = None
    spectral_centroid_hz: Optional[float] = None
    dominant_freq_hz: Optional[float] = None

    presence_ratio: Optional[float] = None
    energy_profile: Optional[str] = None  # JSON array

    @property
    def energy_over_time(self) -> List[float]:
        if not self.energy_profile:
            return []
        return json.loads(self.energy_profile)


# Query result models

@dataclass
class TrackSummary:
    """Summary of a track for list display."""
    id: int
    youtube_id: str
    title: Optional[str]
    artist: Optional[str]
    duration_seconds: Optional[float]
    bpm: Optional[float]
    key_name: Optional[str]
    key_camelot: Optional[str]
    genre_tag: str
    rating: Optional[int]
    is_analyzed: bool
    has_stems: bool
    has_embeddings: bool
    ingested_at: datetime

    @property
    def rating_stars(self) -> str:
        """Get rating as star string."""
        if self.rating is None:
            return "---"
        return "*" * self.rating + "-" * (3 - self.rating)


@dataclass
class TrackDetail:
    """Full detail view of a track."""
    track: YTTrack
    features: Optional[YTFeatures] = None
    sections: List[YTSection] = field(default_factory=list)
    arrangement: Optional[YTArrangementStats] = None
    stems: List[YTStem] = field(default_factory=list)


@dataclass
class SimilarTrack:
    """Result from similarity search."""
    track_id: int
    youtube_id: str
    title: Optional[str]
    artist: Optional[str]
    similarity_score: float  # 0-1, higher is more similar
    bpm: Optional[float] = None
    key_name: Optional[str] = None
