# Phase 2: Reference Profiler

## Overview

**Goal:** Build a comprehensive style profile from the 215 reference tracks that captures what makes them sound professional and characteristic of the user's taste.

**Duration:** 2-3 weeks

**Dependencies:** Phase 1 (Trance DNA Extraction)

**Outputs:**
- ReferenceProfiler class
- Style clustering algorithm
- `trance_profile.json` with learned targets
- Profile validation tools

## Profile Structure

### Statistical Profile

```python
@dataclass
class FeatureStatistics:
    mean: float
    std: float
    min: float
    max: float
    p10: float      # 10th percentile
    p25: float      # 25th percentile (Q1)
    p50: float      # Median
    p75: float      # 75th percentile (Q3)
    p90: float      # 90th percentile
    confidence_interval_95: Tuple[float, float]
    acceptable_range: Tuple[float, float]  # Derived from percentiles

@dataclass
class ReferenceProfile:
    name: str
    created_date: str
    track_count: int

    # Per-feature statistics
    feature_stats: Dict[str, FeatureStatistics]

    # Style clusters
    clusters: List[StyleCluster]

    # Correlation matrix between features
    feature_correlations: np.ndarray

    # Metadata
    track_metadata: List[TrackInfo]  # Optional: artist, title, BPM, key
```

### Style Clusters

```python
@dataclass
class StyleCluster:
    cluster_id: int
    name: str                    # Auto-generated or user-labeled
    track_indices: List[int]
    centroid: Dict[str, float]   # Feature centroid
    variance: Dict[str, float]   # Per-feature variance

    # Identifying characteristics
    distinctive_features: List[str]  # Features that distinguish this cluster

    # Example tracks
    exemplar_tracks: List[int]   # Most representative tracks
```

## ReferenceProfiler Class

```python
class ReferenceProfiler:
    """Build and manage reference style profiles."""

    def __init__(self, feature_extractor: TranceFeatureExtractor):
        self.extractor = feature_extractor
        self.features_cache = {}

    def build_profile(
        self,
        reference_dir: str,
        profile_name: str = "trance_profile",
        n_clusters: int = None,  # Auto-detect if None
        min_tracks: int = 10,
        progress_callback: Callable = None
    ) -> ReferenceProfile:
        """
        Build comprehensive profile from reference tracks.

        Args:
            reference_dir: Directory containing reference audio files
            profile_name: Name for the profile
            n_clusters: Number of style clusters (auto-detect if None)
            min_tracks: Minimum tracks required per cluster
            progress_callback: Optional callback for progress updates

        Returns:
            Complete ReferenceProfile object
        """

    def extract_all_features(self, audio_paths: List[str]) -> pd.DataFrame:
        """Extract features from all tracks, with caching."""

    def compute_statistics(self, features_df: pd.DataFrame) -> Dict[str, FeatureStatistics]:
        """Compute per-feature statistics."""

    def discover_clusters(
        self,
        features_df: pd.DataFrame,
        n_clusters: int = None
    ) -> List[StyleCluster]:
        """Discover style sub-clusters in the reference collection."""

    def save_profile(self, profile: ReferenceProfile, path: str):
        """Save profile to JSON file."""

    @classmethod
    def load_profile(cls, path: str) -> ReferenceProfile:
        """Load profile from JSON file."""
```

## Feature Extraction Pipeline

### Batch Processing

```python
def extract_features_batch(
    audio_paths: List[str],
    extractor: TranceFeatureExtractor,
    cache_dir: str = None,
    n_workers: int = 4,
    progress_callback: Callable = None
) -> pd.DataFrame:
    """
    Extract features from multiple tracks with parallel processing.

    Features extracted per track:
    - All trance features (from Phase 1)
    - Spectral features (centroid, bandwidth, rolloff, flatness)
    - Loudness features (LUFS, dynamic range, crest factor)
    - Harmonic features (key, key confidence)
    - Structural features (section count, avg section length)

    Returns:
        DataFrame with one row per track, features as columns
    """
```

### Feature Normalization

```python
def normalize_features(features_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Normalize features for clustering.

    Uses RobustScaler to handle outliers in audio features.

    Returns:
        Normalized DataFrame
        Scaler parameters for inverse transform
    """
```

## Clustering Algorithm

### Automatic Cluster Count Detection

```python
def detect_optimal_clusters(
    features_normalized: np.ndarray,
    min_clusters: int = 2,
    max_clusters: int = 8
) -> int:
    """
    Determine optimal number of clusters using:
    1. Silhouette score
    2. Elbow method (within-cluster sum of squares)
    3. Gap statistic

    Returns:
        Recommended number of clusters
    """
```

### Clustering Implementation

```python
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.mixture import GaussianMixture

def cluster_references(
    features_normalized: np.ndarray,
    n_clusters: int,
    method: str = "kmeans"  # or "hierarchical", "gmm"
) -> Tuple[np.ndarray, List[int]]:
    """
    Cluster reference tracks by style similarity.

    Methods:
    - kmeans: Fast, spherical clusters (default)
    - hierarchical: Tree-based, good for sub-genre hierarchy
    - gmm: Probabilistic, handles overlap

    Returns:
        Cluster labels per track
        Exemplar indices (tracks closest to centroids)
    """
```

### Cluster Characterization

```python
def characterize_cluster(
    cluster_tracks: pd.DataFrame,
    all_tracks: pd.DataFrame,
    feature_stats: Dict[str, FeatureStatistics]
) -> Dict:
    """
    Identify what makes this cluster distinctive.

    Returns:
        {
            'distinctive_features': ['high_energy_progression', 'heavy_sidechain'],
            'feature_deviations': {
                'modulation_depth': +1.2,  # Standard deviations from global mean
                'tempo': -0.3,
                ...
            },
            'suggested_name': 'High-Energy Uplifting'  # Auto-generated
        }
    """
```

## Acceptable Range Calculation

### Statistical Approach

```python
def calculate_acceptable_range(
    values: np.ndarray,
    method: str = "iqr"  # or "percentile", "std"
) -> Tuple[float, float]:
    """
    Calculate acceptable range for a feature.

    Methods:
    - iqr: Q1 - 1.5*IQR to Q3 + 1.5*IQR (robust to outliers)
    - percentile: P10 to P90 (captures 80% of references)
    - std: mean ± 2*std (assumes normal distribution)

    Returns:
        (lower_bound, upper_bound)
    """
```

### Per-Feature Range Types

| Feature Type | Recommended Method | Rationale |
|--------------|-------------------|-----------|
| Tempo | percentile (P5-P95) | Hard boundaries matter |
| Modulation Depth | iqr | Outliers are meaningful |
| Stereo Width | percentile (P10-P90) | Preference-based |
| Energy Progression | iqr | Production style varies |
| Spectral Features | std | Approximately normal |

## Profile Validation

### Sanity Checks

```python
def validate_profile(profile: ReferenceProfile) -> List[str]:
    """
    Validate profile for common issues.

    Checks:
    - Sufficient track count (>= 50 recommended)
    - No extreme outliers dominating statistics
    - Cluster balance (no cluster < 10% of tracks)
    - Feature variance (no zero-variance features)
    - Correlation sanity (expected correlations present)

    Returns:
        List of warnings/issues found
    """
```

### Cross-Validation

```python
def cross_validate_profile(
    profile: ReferenceProfile,
    n_folds: int = 5
) -> Dict[str, float]:
    """
    Test profile stability via cross-validation.

    For each fold:
    1. Build profile from 80% of tracks
    2. Score remaining 20% against profile
    3. Measure consistency

    Returns:
        {
            'mean_score': Average trance score of held-out tracks
            'score_std': Standard deviation
            'cluster_stability': How often tracks cluster the same
        }
    """
```

## Profile Storage Format

### JSON Schema

```json
{
  "name": "trance_profile",
  "version": "1.0",
  "created_date": "2024-01-15T10:30:00Z",
  "track_count": 215,

  "feature_statistics": {
    "tempo": {
      "mean": 138.5,
      "std": 3.2,
      "min": 128.0,
      "max": 150.0,
      "p10": 134.0,
      "p25": 136.0,
      "p50": 138.0,
      "p75": 140.0,
      "p90": 144.0,
      "confidence_interval_95": [137.8, 139.2],
      "acceptable_range": [132.0, 146.0]
    },
    "modulation_depth_db": {
      "mean": 6.2,
      "std": 2.1,
      "...": "..."
    }
  },

  "clusters": [
    {
      "cluster_id": 0,
      "name": "Uplifting High-Energy",
      "track_count": 85,
      "centroid": {
        "tempo": 139.2,
        "modulation_depth_db": 7.1,
        "energy_progression": 0.72
      },
      "distinctive_features": ["high_energy_progression", "strong_sidechain"],
      "exemplar_tracks": [12, 45, 78]
    },
    {
      "cluster_id": 1,
      "name": "Progressive Melodic",
      "...": "..."
    }
  ],

  "feature_correlations": [
    [1.0, 0.3, -0.1, "..."],
    ["..."]
  ],

  "track_metadata": [
    {
      "index": 0,
      "filename": "armin_track_01.wav",
      "cluster": 0,
      "trance_score": 0.85
    }
  ]
}
```

## CLI Commands

### Build Profile

```bash
python build_profile.py \
    --references "D:/OneDrive/Music/References/" \
    --output "models/trance_profile.json" \
    --name "My Trance Profile" \
    --clusters auto \
    --verbose

# Output:
Building reference profile from 215 tracks...
Extracting features: [████████████████████] 215/215
Computing statistics...
Discovering clusters: Found 4 optimal clusters
  Cluster 0: "Uplifting High-Energy" (85 tracks)
  Cluster 1: "Progressive Melodic" (62 tracks)
  Cluster 2: "Tech Trance" (43 tracks)
  Cluster 3: "Vocal Trance" (25 tracks)
Validating profile...
  ✓ Sufficient track count
  ✓ No extreme outliers
  ✓ Clusters balanced
  ✓ All features have variance
Profile saved to: models/trance_profile.json
```

### Profile Info

```bash
python profile_info.py --profile models/trance_profile.json

# Output:
Profile: My Trance Profile
Created: 2024-01-15
Tracks: 215

Feature Ranges:
  tempo:              134.0 - 146.0 BPM (mean: 138.5)
  modulation_depth:   3.1 - 9.3 dB (mean: 6.2)
  stereo_width:       0.28 - 0.72 (mean: 0.48)
  energy_progression: 0.35 - 0.82 (mean: 0.58)

Clusters:
  [0] Uplifting High-Energy (85 tracks, 39.5%)
  [1] Progressive Melodic (62 tracks, 28.8%)
  [2] Tech Trance (43 tracks, 20.0%)
  [3] Vocal Trance (25 tracks, 11.6%)
```

## Integration Points

### With Phase 1

```python
# Use trance features from Phase 1
from feature_extraction.trance_features import TranceFeatureExtractor

extractor = TranceFeatureExtractor()
profiler = ReferenceProfiler(extractor)
profile = profiler.build_profile("references/")
```

### With Phase 3 (Gap Analyzer)

```python
# Profile provides targets for gap analysis
profile = ReferenceProfile.load("trance_profile.json")
gap_analyzer = GapAnalyzer(profile)
gaps = gap_analyzer.analyze(wip_track)
```

## Testing Strategy

### Unit Tests

```python
def test_statistics_computation():
    """Statistics correctly computed from known values"""
    values = np.array([1, 2, 3, 4, 5])
    stats = compute_statistics(values)
    assert stats.mean == 3.0
    assert stats.p50 == 3.0

def test_clustering_reproducibility():
    """Same input produces same clusters"""
    features = load_test_features()
    labels1 = cluster_references(features, n_clusters=3)
    labels2 = cluster_references(features, n_clusters=3)
    assert np.array_equal(labels1, labels2)

def test_acceptable_range_covers_majority():
    """Acceptable range should cover most reference tracks"""
    profile = build_test_profile()
    for feature, stats in profile.feature_stats.items():
        low, high = stats.acceptable_range
        in_range = sum(1 for v in test_values if low <= v <= high)
        assert in_range / len(test_values) >= 0.7
```

### Integration Tests

```python
def test_full_profile_build():
    """Complete profile build from directory"""
    profile = ReferenceProfiler().build_profile("test_references/")
    assert profile.track_count > 0
    assert len(profile.feature_stats) > 10
    assert len(profile.clusters) >= 2

def test_profile_save_load_roundtrip():
    """Profile survives save/load cycle"""
    original = build_test_profile()
    original.save("test_profile.json")
    loaded = ReferenceProfile.load("test_profile.json")
    assert original.track_count == loaded.track_count
    assert original.feature_stats.keys() == loaded.feature_stats.keys()
```

## Deliverables Checklist

- [ ] `reference_profiler.py` - Main profiler class
- [ ] `style_clusters.py` - Clustering algorithms
- [ ] `profile_storage.py` - Save/load functionality
- [ ] `profile_validator.py` - Validation checks
- [ ] `build_profile.py` - CLI for profile building
- [ ] `profile_info.py` - CLI for profile inspection
- [ ] Unit tests for all modules
- [ ] Integration tests for full pipeline
- [ ] `trance_profile.json` from 215 reference tracks
- [ ] Documentation with usage examples

## Success Criteria

1. **Profile successfully built** from 215 reference tracks
2. **Meaningful clusters discovered** (2-6 clusters with distinctive characteristics)
3. **Acceptable ranges validated** (cover 70-90% of reference tracks)
4. **Profile validates without warnings** (no data quality issues)
5. **Cross-validation stable** (score std < 0.1)
6. **Performance:** < 5 minutes to build profile from 215 tracks
7. **Profile size reasonable** (< 10MB JSON file)
