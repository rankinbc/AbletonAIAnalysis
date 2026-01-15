"""
Reference Storage Module

Stores and retrieves reference track analytics for comparison.
Analytics are stored as JSON files for future combined analysis.

Structure:
  reference_library/
  ├── index.json              # Library index with metadata
  └── analytics/
      └── {track_id}.json     # Full analytics per track
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import numpy as np
import librosa
import soundfile as sf


@dataclass
class TrackMetadata:
    """Metadata for a reference track."""
    track_id: str                   # Unique identifier (hash-based)
    file_path: str                  # Original file path
    file_name: str
    artist: Optional[str] = None
    title: Optional[str] = None
    genre: Optional[str] = None
    subgenre: Optional[str] = None
    tempo_bpm: Optional[float] = None
    key: Optional[str] = None
    duration_seconds: float = 0.0
    sample_rate: int = 44100
    added_timestamp: str = ""
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class StemMetrics:
    """Detailed metrics for a single stem."""
    stem_type: str

    # Loudness metrics
    peak_db: float
    rms_db: float
    integrated_lufs: float

    # Frequency analysis
    spectral_centroid_hz: float
    bass_energy_pct: float          # 20-250 Hz
    low_mid_energy_pct: float       # 250-500 Hz
    mid_energy_pct: float           # 500-2000 Hz
    high_mid_energy_pct: float      # 2000-6000 Hz
    high_energy_pct: float          # 6000-20000 Hz
    frequency_spectrum: List[float] = field(default_factory=list)  # For visualization

    # Stereo metrics
    stereo_width_pct: float = 0.0
    correlation: float = 1.0

    # Dynamics
    dynamic_range_db: float = 0.0
    crest_factor_db: float = 0.0


@dataclass
class ReferenceAnalytics:
    """Complete analytics for a reference track."""
    metadata: TrackMetadata

    # Full mix analysis (dict for flexibility)
    full_mix_metrics: Dict[str, Any] = field(default_factory=dict)

    # Per-stem metrics
    stem_metrics: Dict[str, StemMetrics] = field(default_factory=dict)

    # Frequency spectrum data for visualization
    spectrum_data: Dict[str, Any] = field(default_factory=dict)

    # Analysis metadata
    analysis_version: str = "1.0"
    analyzed_timestamp: str = ""
    stems_separated: bool = False


@dataclass
class ReferenceLibrary:
    """Index of all stored reference tracks."""
    version: str = "1.0"
    last_updated: str = ""
    track_count: int = 0
    tracks: Dict[str, Dict] = field(default_factory=dict)  # track_id -> metadata dict

    # Indexes for efficient lookup
    by_genre: Dict[str, List[str]] = field(default_factory=dict)    # genre -> list of track_ids
    by_tempo_range: Dict[str, List[str]] = field(default_factory=dict)  # "120-130" -> list of track_ids


class ReferenceStorage:
    """Storage and retrieval system for reference track analytics."""

    # Frequency band definitions (Hz) - matching audio_analyzer.py
    FREQ_BANDS = {
        'bass': (20, 250),
        'low_mid': (250, 500),
        'mid': (500, 2000),
        'high_mid': (2000, 6000),
        'high': (6000, 20000)
    }

    def __init__(
        self,
        library_dir: str = "./reference_library",
        verbose: bool = False
    ):
        """
        Initialize storage system.

        Args:
            library_dir: Base directory for reference library
            verbose: Enable verbose output
        """
        self.library_dir = Path(library_dir)
        self.analytics_dir = self.library_dir / "analytics"
        self.index_path = self.library_dir / "index.json"
        self.verbose = verbose

        # Create directories
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self.analytics_dir.mkdir(parents=True, exist_ok=True)

        # Load or create index
        self._index = self._load_index()

    def add_reference(
        self,
        audio_path: str,
        metadata: Optional[Dict] = None,
        stem_metrics: Optional[Dict[str, StemMetrics]] = None,
        full_mix_metrics: Optional[Dict] = None
    ) -> ReferenceAnalytics:
        """
        Add a reference track to the library.

        Args:
            audio_path: Path to reference audio file
            metadata: Optional metadata dict (artist, title, genre, tags, etc.)
            stem_metrics: Pre-computed stem metrics (from ReferenceComparator)
            full_mix_metrics: Pre-computed full mix metrics

        Returns:
            ReferenceAnalytics with complete analysis
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Generate track ID
        track_id = self._generate_track_id(audio_path)

        # Load audio for basic analysis
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)

        # Detect tempo if not provided
        tempo = None
        if metadata and metadata.get('tempo_bpm'):
            tempo = metadata['tempo_bpm']
        else:
            try:
                detected_tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                if isinstance(detected_tempo, np.ndarray):
                    tempo = float(detected_tempo[0]) if len(detected_tempo) > 0 else None
                else:
                    tempo = float(detected_tempo)
            except Exception:
                tempo = None

        # Create metadata
        track_metadata = TrackMetadata(
            track_id=track_id,
            file_path=str(path.absolute()),
            file_name=path.name,
            artist=metadata.get('artist') if metadata else None,
            title=metadata.get('title') if metadata else None,
            genre=metadata.get('genre') if metadata else None,
            subgenre=metadata.get('subgenre') if metadata else None,
            tempo_bpm=tempo,
            key=metadata.get('key') if metadata else None,
            duration_seconds=duration,
            sample_rate=sr,
            added_timestamp=datetime.now().isoformat(),
            tags=metadata.get('tags', []) if metadata else [],
            notes=metadata.get('notes') if metadata else None
        )

        # Analyze full mix if not provided
        if full_mix_metrics is None:
            full_mix_metrics = self._analyze_full_mix(y, sr)

        # Create analytics object
        analytics = ReferenceAnalytics(
            metadata=track_metadata,
            full_mix_metrics=full_mix_metrics,
            stem_metrics={k: asdict(v) if hasattr(v, '__dataclass_fields__') else v
                          for k, v in (stem_metrics or {}).items()},
            spectrum_data=self._compute_spectrum_data(y, sr),
            analysis_version="1.0",
            analyzed_timestamp=datetime.now().isoformat(),
            stems_separated=stem_metrics is not None and len(stem_metrics) > 0
        )

        # Save analytics
        self._save_analytics(analytics)

        # Update index
        self._update_index(track_metadata)

        if self.verbose:
            print(f"Added reference: {track_metadata.file_name} (ID: {track_id})")

        return analytics

    def get_reference(
        self,
        track_id: str
    ) -> Optional[ReferenceAnalytics]:
        """
        Retrieve stored analytics for a reference track.

        Args:
            track_id: Unique track identifier

        Returns:
            ReferenceAnalytics if found, None otherwise
        """
        analytics_path = self.analytics_dir / f"{track_id}.json"

        if not analytics_path.exists():
            return None

        try:
            with open(analytics_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Reconstruct dataclasses
            metadata = TrackMetadata(**data['metadata'])

            # Reconstruct stem metrics
            stem_metrics = {}
            for stem_type, metrics in data.get('stem_metrics', {}).items():
                if isinstance(metrics, dict):
                    stem_metrics[stem_type] = StemMetrics(**metrics)
                else:
                    stem_metrics[stem_type] = metrics

            return ReferenceAnalytics(
                metadata=metadata,
                full_mix_metrics=data.get('full_mix_metrics', {}),
                stem_metrics=stem_metrics,
                spectrum_data=data.get('spectrum_data', {}),
                analysis_version=data.get('analysis_version', '1.0'),
                analyzed_timestamp=data.get('analyzed_timestamp', ''),
                stems_separated=data.get('stems_separated', False)
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            if self.verbose:
                print(f"Error loading analytics for {track_id}: {e}")
            return None

    def list_references(
        self,
        genre: Optional[str] = None,
        tempo_range: Optional[Tuple[int, int]] = None,
        tags: Optional[List[str]] = None
    ) -> List[TrackMetadata]:
        """
        List reference tracks with optional filtering.

        Args:
            genre: Filter by genre
            tempo_range: Filter by tempo (min_bpm, max_bpm)
            tags: Filter by tags (must have all)

        Returns:
            List of matching track metadata
        """
        results = []

        for track_id, track_data in self._index.tracks.items():
            # Apply filters
            if genre and track_data.get('genre', '').lower() != genre.lower():
                continue

            if tempo_range:
                track_tempo = track_data.get('tempo_bpm')
                if track_tempo is None or not (tempo_range[0] <= track_tempo <= tempo_range[1]):
                    continue

            if tags:
                track_tags = set(t.lower() for t in track_data.get('tags', []))
                required_tags = set(t.lower() for t in tags)
                if not required_tags.issubset(track_tags):
                    continue

            # Reconstruct metadata
            results.append(TrackMetadata(
                track_id=track_id,
                file_path=track_data.get('file_path', ''),
                file_name=track_data.get('file_name', ''),
                artist=track_data.get('artist'),
                title=track_data.get('title'),
                genre=track_data.get('genre'),
                subgenre=track_data.get('subgenre'),
                tempo_bpm=track_data.get('tempo_bpm'),
                key=track_data.get('key'),
                duration_seconds=track_data.get('duration_seconds', 0),
                sample_rate=track_data.get('sample_rate', 44100),
                added_timestamp=track_data.get('added_timestamp', ''),
                tags=track_data.get('tags', []),
                notes=track_data.get('notes')
            ))

        return results

    def update_metadata(
        self,
        track_id: str,
        updates: Dict
    ) -> bool:
        """
        Update metadata for an existing reference.

        Args:
            track_id: Track identifier
            updates: Dict of fields to update

        Returns:
            True if successful, False if track not found
        """
        if track_id not in self._index.tracks:
            return False

        # Update index
        for key, value in updates.items():
            if key in ['artist', 'title', 'genre', 'subgenre', 'tempo_bpm',
                       'key', 'tags', 'notes']:
                self._index.tracks[track_id][key] = value

        # Update analytics file
        analytics = self.get_reference(track_id)
        if analytics:
            for key, value in updates.items():
                if hasattr(analytics.metadata, key):
                    setattr(analytics.metadata, key, value)
            self._save_analytics(analytics)

        # Rebuild indexes
        self._rebuild_indexes()
        self._save_index()

        return True

    def remove_reference(
        self,
        track_id: str
    ) -> bool:
        """
        Remove a reference track from the library.

        Args:
            track_id: Track identifier

        Returns:
            True if removed, False if not found
        """
        if track_id not in self._index.tracks:
            return False

        # Remove analytics file
        analytics_path = self.analytics_dir / f"{track_id}.json"
        if analytics_path.exists():
            analytics_path.unlink()

        # Remove from index
        del self._index.tracks[track_id]

        # Rebuild indexes
        self._rebuild_indexes()
        self._save_index()

        return True

    def get_library_stats(self) -> Dict:
        """Get summary statistics for the reference library."""
        if not self._index.tracks:
            return {
                'track_count': 0,
                'genres': {},
                'tempo_range': None,
                'total_duration_minutes': 0
            }

        genres = {}
        tempos = []
        total_duration = 0

        for track_data in self._index.tracks.values():
            genre = track_data.get('genre', 'unknown')
            genres[genre] = genres.get(genre, 0) + 1

            if track_data.get('tempo_bpm'):
                tempos.append(track_data['tempo_bpm'])

            total_duration += track_data.get('duration_seconds', 0)

        return {
            'track_count': len(self._index.tracks),
            'genres': genres,
            'tempo_range': (min(tempos), max(tempos)) if tempos else None,
            'avg_tempo': sum(tempos) / len(tempos) if tempos else None,
            'total_duration_minutes': total_duration / 60
        }

    def _generate_track_id(self, audio_path: str) -> str:
        """Generate unique ID from file hash."""
        hash_md5 = hashlib.md5()
        path = Path(audio_path)
        stat = path.stat()
        hash_input = f"{path.name}:{stat.st_size}:{stat.st_mtime}"
        hash_md5.update(hash_input.encode())
        return hash_md5.hexdigest()[:12]

    def _analyze_full_mix(self, y: np.ndarray, sr: int) -> Dict:
        """Analyze full mix for basic metrics."""
        # Peak and RMS
        peak = np.max(np.abs(y))
        peak_db = float(20 * np.log10(peak + 1e-10))
        rms = np.sqrt(np.mean(y ** 2))
        rms_db = float(20 * np.log10(rms + 1e-10))

        # Dynamic range
        dynamic_range = peak_db - rms_db

        # Approximate LUFS
        integrated_lufs = rms_db - 0.691

        # Spectral features
        spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))

        # Frequency band energies
        D = np.abs(librosa.stft(y, n_fft=4096))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
        total_energy = np.sum(D ** 2) + 1e-10

        band_energies = {}
        for band_name, (low, high) in self.FREQ_BANDS.items():
            mask = (freqs >= low) & (freqs < high)
            band_energy = np.sum(D[mask, :] ** 2)
            band_energies[f"{band_name}_energy_pct"] = float(band_energy / total_energy * 100)

        return {
            'peak_db': peak_db,
            'rms_db': rms_db,
            'dynamic_range_db': dynamic_range,
            'integrated_lufs': integrated_lufs,
            'spectral_centroid_hz': float(spectral_centroid),
            **band_energies
        }

    def _compute_spectrum_data(self, y: np.ndarray, sr: int) -> Dict:
        """Compute frequency spectrum for visualization."""
        D = np.abs(librosa.stft(y, n_fft=4096))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)

        # Average spectrum in dB
        avg_spectrum = np.mean(D, axis=1)
        spectrum_db = 20 * np.log10(avg_spectrum + 1e-10)

        # Downsample for storage (keep 256 points)
        indices = np.linspace(0, len(freqs) - 1, 256, dtype=int)

        return {
            'frequencies': freqs[indices].tolist(),
            'magnitude_db': spectrum_db[indices].tolist()
        }

    def _save_analytics(self, analytics: ReferenceAnalytics) -> str:
        """Save analytics to JSON file."""
        analytics_path = self.analytics_dir / f"{analytics.metadata.track_id}.json"

        # Convert to dict, handling dataclasses
        data = {
            'metadata': asdict(analytics.metadata),
            'full_mix_metrics': analytics.full_mix_metrics,
            'stem_metrics': {k: asdict(v) if hasattr(v, '__dataclass_fields__') else v
                            for k, v in analytics.stem_metrics.items()},
            'spectrum_data': analytics.spectrum_data,
            'analysis_version': analytics.analysis_version,
            'analyzed_timestamp': analytics.analyzed_timestamp,
            'stems_separated': analytics.stems_separated
        }

        with open(analytics_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        return str(analytics_path)

    def _load_index(self) -> ReferenceLibrary:
        """Load library index from file."""
        if not self.index_path.exists():
            return ReferenceLibrary(
                last_updated=datetime.now().isoformat()
            )

        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return ReferenceLibrary(
                version=data.get('version', '1.0'),
                last_updated=data.get('last_updated', ''),
                track_count=data.get('track_count', 0),
                tracks=data.get('tracks', {}),
                by_genre=data.get('by_genre', {}),
                by_tempo_range=data.get('by_tempo_range', {})
            )
        except (json.JSONDecodeError, KeyError):
            return ReferenceLibrary(
                last_updated=datetime.now().isoformat()
            )

    def _save_index(self):
        """Save library index to file."""
        data = {
            'version': self._index.version,
            'last_updated': datetime.now().isoformat(),
            'track_count': len(self._index.tracks),
            'tracks': self._index.tracks,
            'by_genre': self._index.by_genre,
            'by_tempo_range': self._index.by_tempo_range
        }

        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _update_index(self, metadata: TrackMetadata):
        """Update index with new track metadata."""
        # Add to tracks
        self._index.tracks[metadata.track_id] = asdict(metadata)
        self._index.track_count = len(self._index.tracks)

        # Update genre index
        if metadata.genre:
            genre = metadata.genre.lower()
            if genre not in self._index.by_genre:
                self._index.by_genre[genre] = []
            if metadata.track_id not in self._index.by_genre[genre]:
                self._index.by_genre[genre].append(metadata.track_id)

        # Update tempo index
        if metadata.tempo_bpm:
            tempo_bucket = f"{int(metadata.tempo_bpm // 10) * 10}-{int(metadata.tempo_bpm // 10) * 10 + 10}"
            if tempo_bucket not in self._index.by_tempo_range:
                self._index.by_tempo_range[tempo_bucket] = []
            if metadata.track_id not in self._index.by_tempo_range[tempo_bucket]:
                self._index.by_tempo_range[tempo_bucket].append(metadata.track_id)

        self._save_index()

    def _rebuild_indexes(self):
        """Rebuild genre and tempo indexes from scratch."""
        self._index.by_genre = {}
        self._index.by_tempo_range = {}

        for track_id, track_data in self._index.tracks.items():
            genre = track_data.get('genre')
            if genre:
                genre = genre.lower()
                if genre not in self._index.by_genre:
                    self._index.by_genre[genre] = []
                self._index.by_genre[genre].append(track_id)

            tempo = track_data.get('tempo_bpm')
            if tempo:
                bucket = f"{int(tempo // 10) * 10}-{int(tempo // 10) * 10 + 10}"
                if bucket not in self._index.by_tempo_range:
                    self._index.by_tempo_range[bucket] = []
                self._index.by_tempo_range[bucket].append(track_id)
