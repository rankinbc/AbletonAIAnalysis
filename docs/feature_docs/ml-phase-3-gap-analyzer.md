# Phase 3: Gap Analyzer

## Overview

**Goal:** Compare any work-in-progress track against the learned reference profile to identify specific gaps and rank issues by importance.

**Duration:** 2 weeks

**Dependencies:**
- Phase 1 (Trance DNA Extraction)
- Phase 2 (Reference Profiler)

**Outputs:**
- GapAnalyzer class
- Delta computation algorithms
- Human-readable gap reports
- Issue prioritization system

## Gap Analysis Concept

### What is a "Gap"?

A gap is the measurable difference between a WIP track's features and the target values derived from the reference profile.

```
Gap = WIP_value - Reference_target

Types:
- Statistical gap: Distance from mean in standard deviations
- Range gap: Outside acceptable range (binary + magnitude)
- Cluster gap: Distance from nearest style cluster
```

### Gap Severity Levels

| Level | Description | Z-Score | Action |
|-------|-------------|---------|--------|
| **Critical** | Far outside acceptable range | > 3σ | Must fix |
| **Warning** | Outside acceptable range | 2-3σ | Should fix |
| **Minor** | Within range but far from mean | 1-2σ | Consider fixing |
| **OK** | Within typical range | < 1σ | No action needed |

## GapAnalyzer Class

```python
class GapAnalyzer:
    """Analyze gaps between WIP track and reference profile."""

    def __init__(self, profile: ReferenceProfile):
        self.profile = profile
        self.extractor = TranceFeatureExtractor()

    def analyze(
        self,
        wip_path: str,
        target_cluster: int = None,  # Compare to specific cluster
        include_stems: bool = False,  # Per-stem analysis
        detail_level: str = "full"    # "summary", "standard", "full"
    ) -> GapReport:
        """
        Analyze WIP track against reference profile.

        Args:
            wip_path: Path to WIP audio file
            target_cluster: Optional cluster to compare against
            include_stems: Whether to analyze separated stems
            detail_level: Amount of detail in report

        Returns:
            Comprehensive gap analysis report
        """

    def compute_feature_gap(
        self,
        wip_value: float,
        feature_stats: FeatureStatistics
    ) -> FeatureGap:
        """Compute gap for a single feature."""

    def find_nearest_cluster(
        self,
        wip_features: Dict[str, float]
    ) -> Tuple[int, float]:
        """Find which style cluster the WIP is closest to."""

    def prioritize_gaps(
        self,
        gaps: List[FeatureGap]
    ) -> List[FeatureGap]:
        """Sort gaps by importance/impact."""
```

## Data Structures

### FeatureGap

```python
@dataclass
class FeatureGap:
    feature_name: str
    wip_value: float
    target_value: float           # Profile mean or cluster centroid
    acceptable_range: Tuple[float, float]

    # Computed metrics
    absolute_delta: float         # Raw difference
    z_score: float                # Standard deviations from mean
    percentile: float             # Where WIP falls in reference distribution

    # Classification
    severity: str                 # "critical", "warning", "minor", "ok"
    is_outside_range: bool
    direction: str                # "high", "low", "ok"

    # Actionability
    is_fixable: bool              # Can be addressed with EQ/compression/etc
    fix_difficulty: str           # "easy", "medium", "hard", "manual"

    # Human-readable
    description: str              # "Bass is 3dB too loud compared to references"
    recommendation: str           # "Reduce bass track volume or apply high-pass filter"
```

### GapReport

```python
@dataclass
class GapReport:
    wip_path: str
    profile_name: str
    analysis_date: str

    # Overall scores
    overall_similarity: float     # 0-1, how close to references
    trance_score: float           # From TranceScoreCalculator
    nearest_cluster: int
    cluster_distance: float

    # Detailed gaps
    all_gaps: List[FeatureGap]
    critical_gaps: List[FeatureGap]
    warning_gaps: List[FeatureGap]

    # Summary statistics
    gap_count_by_severity: Dict[str, int]
    most_problematic_areas: List[str]  # ["bass", "stereo_width", "dynamics"]

    # Per-stem analysis (if requested)
    stem_gaps: Dict[str, List[FeatureGap]]  # {"drums": [...], "bass": [...]}

    # Recommendations
    prioritized_fixes: List[FixRecommendation]
```

## Gap Computation Algorithms

### Statistical Gap

```python
def compute_statistical_gap(
    wip_value: float,
    stats: FeatureStatistics
) -> Tuple[float, str]:
    """
    Compute gap using z-score method.

    Returns:
        z_score: Number of standard deviations from mean
        severity: Classification based on z-score
    """
    z_score = (wip_value - stats.mean) / stats.std

    if abs(z_score) > 3:
        severity = "critical"
    elif abs(z_score) > 2:
        severity = "warning"
    elif abs(z_score) > 1:
        severity = "minor"
    else:
        severity = "ok"

    return z_score, severity
```

### Range Gap

```python
def compute_range_gap(
    wip_value: float,
    acceptable_range: Tuple[float, float]
) -> Tuple[bool, float, str]:
    """
    Compute gap relative to acceptable range.

    Returns:
        is_outside: Whether value is outside range
        distance: How far outside (0 if inside)
        direction: "high", "low", or "ok"
    """
    low, high = acceptable_range

    if wip_value < low:
        return True, low - wip_value, "low"
    elif wip_value > high:
        return True, wip_value - high, "high"
    else:
        return False, 0, "ok"
```

### Cluster Distance

```python
def compute_cluster_distance(
    wip_features: Dict[str, float],
    cluster: StyleCluster,
    feature_weights: Dict[str, float] = None
) -> float:
    """
    Compute weighted Euclidean distance to cluster centroid.

    Uses normalized features to prevent scale bias.
    """
    if feature_weights is None:
        feature_weights = {k: 1.0 for k in wip_features}

    distance = 0
    for feature, wip_val in wip_features.items():
        if feature in cluster.centroid:
            target_val = cluster.centroid[feature]
            weight = feature_weights.get(feature, 1.0)
            distance += weight * (wip_val - target_val) ** 2

    return np.sqrt(distance)
```

## Issue Prioritization

### Prioritization Factors

```python
def calculate_priority_score(gap: FeatureGap) -> float:
    """
    Calculate priority score for fix ordering.

    Factors:
    - Severity (critical > warning > minor)
    - Impact on overall sound (frequency-dependent)
    - Ease of fix (easy fixes first for quick wins)
    - Perceptual importance (some features matter more)
    """
    severity_weight = {"critical": 4, "warning": 2, "minor": 1, "ok": 0}

    # Feature importance weights (based on psychoacoustic research)
    importance_weights = {
        'loudness': 1.0,
        'bass_level': 0.9,
        'stereo_width': 0.8,
        'high_frequency_content': 0.7,
        'modulation_depth': 0.7,
        'dynamics': 0.6,
        'tempo': 0.5,  # Usually intentional
    }

    # Fixability bonus (prefer actionable issues)
    fix_bonus = {"easy": 1.5, "medium": 1.2, "hard": 1.0, "manual": 0.8}

    score = (
        severity_weight[gap.severity] *
        importance_weights.get(gap.feature_name, 0.5) *
        fix_bonus.get(gap.fix_difficulty, 1.0)
    )

    return score
```

### Prioritized Output

```python
def prioritize_gaps(gaps: List[FeatureGap]) -> List[FeatureGap]:
    """
    Sort gaps by priority score, highest first.

    Also groups related gaps (e.g., all bass issues together).
    """
    # Calculate scores
    scored_gaps = [(gap, calculate_priority_score(gap)) for gap in gaps]

    # Sort by score descending
    scored_gaps.sort(key=lambda x: x[1], reverse=True)

    return [gap for gap, score in scored_gaps]
```

## Human-Readable Reports

### Summary Report

```
═══════════════════════════════════════════════════════════
               GAP ANALYSIS REPORT
═══════════════════════════════════════════════════════════

Track: my_wip_track.wav
Profile: My Trance Profile (215 references)
Analysis Date: 2024-01-15 10:30:00

OVERALL ASSESSMENT
──────────────────
Similarity to References: 68%
Trance Score: 0.72 / 1.00
Nearest Style: "Uplifting High-Energy" (cluster 0)

ISSUES FOUND
────────────
Critical: 2    Warning: 4    Minor: 6

TOP PRIORITIES
──────────────
1. [CRITICAL] Bass too loud (+4.2 dB vs references)
   → Reduce bass track by 3-4 dB or apply low shelf cut

2. [CRITICAL] Stereo width too narrow (0.25 vs 0.48 target)
   → Add stereo widening to lead synths (mid-side EQ or chorus)

3. [WARNING] Sidechain pumping too subtle (3.1 dB vs 6.2 dB)
   → Increase compressor ratio or lower threshold on bass

4. [WARNING] High frequencies lacking (-2.1 dB in 8-16kHz)
   → Add high shelf boost on master or brighten hi-hats

Full report: gap_report_20240115_103000.json
```

### Detailed Report

```python
def generate_detailed_report(report: GapReport) -> str:
    """Generate comprehensive human-readable report."""

    sections = [
        generate_header(report),
        generate_overall_assessment(report),
        generate_critical_issues(report),
        generate_warning_issues(report),
        generate_feature_breakdown(report),
        generate_cluster_analysis(report),
        generate_recommendations(report),
    ]

    return "\n\n".join(sections)
```

## Per-Stem Analysis

### With Demucs Integration

```python
def analyze_with_stems(
    wip_path: str,
    profile: ReferenceProfile
) -> Dict[str, List[FeatureGap]]:
    """
    Separate WIP into stems and analyze each.

    Provides more specific recommendations:
    - "Drums: kick too quiet relative to references"
    - "Bass: too much content above 200Hz"
    - "Other: lead synth stereo width below target"
    """
    from demucs.api import Separator

    separator = Separator(model="htdemucs")
    stems = separator.separate_audio_file(wip_path)

    stem_gaps = {}
    for stem_name, stem_audio in stems.items():
        features = extract_stem_features(stem_audio, stem_name)
        gaps = compute_gaps_for_stem(features, profile, stem_name)
        stem_gaps[stem_name] = gaps

    return stem_gaps
```

## CLI Commands

### Analyze Track

```bash
python analyze_gap.py \
    --wip "my_track.wav" \
    --profile "models/trance_profile.json" \
    --output "gap_report.json" \
    --format "detailed"

# Output:
Analyzing: my_track.wav
Against profile: My Trance Profile

Overall Similarity: 68%
Trance Score: 0.72

Critical Issues (2):
  ✗ Bass level: +4.2 dB above reference mean
  ✗ Stereo width: 0.25 (target: 0.40-0.60)

Warnings (4):
  ⚠ Sidechain depth: 3.1 dB (target: 4.0-8.0 dB)
  ⚠ High frequency content: -2.1 dB
  ⚠ Energy progression: 0.42 (target: 0.50-0.70)
  ⚠ Kick presence: 0.65 (target: 0.75-0.90)

Top 3 Recommended Fixes:
  1. Reduce bass track volume by 3-4 dB
  2. Apply stereo widening to lead synths
  3. Increase sidechain compression depth

Full report saved to: gap_report.json
```

### Compare to Specific Cluster

```bash
python analyze_gap.py \
    --wip "my_track.wav" \
    --profile "models/trance_profile.json" \
    --cluster 2 \
    --cluster-name "Tech Trance"

# Compares specifically against the Tech Trance cluster targets
```

## Integration Points

### With Phase 2 (Profile)

```python
profile = ReferenceProfile.load("trance_profile.json")
analyzer = GapAnalyzer(profile)
```

### With Phase 5 (Prescriptive Fixes)

```python
# Gap report feeds directly into fix generation
report = analyzer.analyze("wip_track.wav")
fixes = PrescriptiveFixGenerator(profile).generate_fixes(report)
```

### With Existing System

```python
# Extend existing analysis
from analysis.gap_analyzer import GapAnalyzer

class EnhancedAudioAnalyzer(AudioAnalyzer):
    def analyze_with_gaps(self, audio_path, profile_path):
        base_result = self.analyze(audio_path, include_trance_features=True)

        profile = ReferenceProfile.load(profile_path)
        gap_analyzer = GapAnalyzer(profile)
        gap_report = gap_analyzer.analyze(audio_path)

        base_result.gap_report = gap_report
        return base_result
```

## Testing Strategy

### Unit Tests

```python
def test_z_score_computation():
    """Z-score correctly computed"""
    stats = FeatureStatistics(mean=100, std=10, ...)
    z, severity = compute_statistical_gap(120, stats)
    assert z == 2.0
    assert severity == "warning"

def test_range_gap_inside():
    """Value inside range returns ok"""
    outside, dist, direction = compute_range_gap(50, (40, 60))
    assert not outside
    assert dist == 0
    assert direction == "ok"

def test_range_gap_outside_high():
    """Value above range correctly identified"""
    outside, dist, direction = compute_range_gap(70, (40, 60))
    assert outside
    assert dist == 10
    assert direction == "high"

def test_prioritization_order():
    """Critical issues sorted before warnings"""
    gaps = [
        FeatureGap(severity="warning", ...),
        FeatureGap(severity="critical", ...),
        FeatureGap(severity="minor", ...),
    ]
    sorted_gaps = prioritize_gaps(gaps)
    assert sorted_gaps[0].severity == "critical"
```

### Integration Tests

```python
def test_full_gap_analysis():
    """Complete gap analysis produces valid report"""
    profile = ReferenceProfile.load("test_profile.json")
    analyzer = GapAnalyzer(profile)
    report = analyzer.analyze("test_track.wav")

    assert 0 <= report.overall_similarity <= 1
    assert len(report.all_gaps) > 0
    assert report.nearest_cluster in range(len(profile.clusters))

def test_stem_analysis():
    """Per-stem analysis identifies stem-specific issues"""
    profile = ReferenceProfile.load("test_profile.json")
    analyzer = GapAnalyzer(profile)
    report = analyzer.analyze("test_track.wav", include_stems=True)

    assert "drums" in report.stem_gaps
    assert "bass" in report.stem_gaps
```

## Deliverables Checklist

- [ ] `gap_analyzer.py` - Main analyzer class
- [ ] `delta_reporter.py` - Human-readable report generation
- [ ] `prioritization.py` - Issue prioritization logic
- [ ] `stem_analyzer.py` - Per-stem analysis
- [ ] `analyze_gap.py` - CLI command
- [ ] Unit tests for gap computation
- [ ] Integration tests for full analysis
- [ ] Report templates (summary, detailed, JSON)
- [ ] Documentation with examples

## Success Criteria

1. **Gap detection matches human perception** - Validate on 10 tracks with manual review
2. **Prioritization makes sense** - Critical issues are truly critical
3. **Reports are actionable** - Recommendations map to specific actions
4. **Per-stem analysis works** - Can identify stem-specific issues
5. **Performance:** < 30 seconds for full gap analysis (including stem separation)
6. **All severity levels used** - Distribution across critical/warning/minor/ok
