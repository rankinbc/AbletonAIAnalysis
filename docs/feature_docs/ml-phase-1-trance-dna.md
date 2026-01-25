# Phase 1: Trance DNA Extraction

## Overview

**Goal:** Port trance-specific feature extractors from research and establish baseline measurements across the 215 reference tracks.

**Duration:** 2-3 weeks

**Dependencies:** None (foundational phase)

**Outputs:**
- Trance feature extraction module
- TranceScoreCalculator class
- Baseline statistics from 215 reference tracks
- Initial reference profile structure

## Feature Extractors to Implement

### 1. Sidechain Pumping Detection

**Research Source:** TranceSpecificAudioFeatureExtractionResearch.md

**Implementation:**
```python
def extract_pumping_features(audio_path, expected_bpm=138):
    """
    Detect sidechain compression via RMS envelope analysis.

    Returns:
        modulation_depth_linear: 0.3-0.6 = moderate, >0.6 = heavy
        modulation_depth_db: 4-8 dB = moderate, >8 dB = heavy
        pumping_regularity: <0.1 = very consistent
        num_pump_cycles: total detected cycles
    """
```

**Key Parameters:**
- frame_length=2048 (~46ms at 44.1kHz)
- hop_length=512
- Peak distance based on expected BPM

**Validation Criteria:**
- Known heavily-sidechained tracks score > 0.6 modulation
- Tracks without sidechain score < 0.2
- Regularity correlates with quantized vs. unquantized pumping

### 2. TB-303 Acid Bassline Detection

**Research Source:** TranceSpecificAudioFeatureExtractionResearch.md

**Components:**
1. **Filter Sweep Detection** - Spectral centroid movement
2. **Resonance Measurement** - Bandwidth/centroid ratio
3. **Pitch Glide Detection** - pYIN F0 tracking
4. **Accent Pattern Detection** - RMS/brightness correlation

**Implementation:**
```python
def compute_303_score(y, sr):
    """
    Compute overall '303-ness' score (0-1).

    Weights:
        filter_sweep: 0.30
        resonance: 0.25
        glides: 0.25
        accents: 0.20
    """
```

**Validation Criteria:**
- Classic acid tracks (Hardfloor, Emmanuel Top) score > 0.7
- Non-acid trance scores < 0.3
- Component scores individually validated

### 3. Supersaw Stereo Spread Analysis

**Research Source:** TranceSpecificAudioFeatureExtractionResearch.md

**Components:**
1. **Mid-Side Width Ratio** - side_rms / mid_rms
2. **Phase Correlation** - L/R correlation coefficient
3. **Detuning Detection** - Spectral peak clustering

**Implementation:**
```python
def analyze_supersaw_characteristics(y_stereo, sr):
    """
    Analyze supersaw-style stereo spread.

    Returns:
        stereo_width: 0 = mono, 0.3-0.8 = typical supersaw
        phase_correlation: +1 = mono, 0.3-0.7 = supersaw typical
        detuning_detected: bool
        estimated_voices: int (typically 5-9 for supersaw)
        spread_cents: detuning amount (10-40 typical)
    """
```

**Validation Criteria:**
- Known supersaw-heavy tracks (classic Armin) score > 0.5 width
- Mono/narrow tracks score < 0.2 width
- Correlation values match expected ranges

### 4. Energy Curve Extraction

**Research Source:** TranceSpecificAudioFeatureExtractionResearch.md

**Multi-feature energy tracking:**
```python
def extract_energy_curves(y, sr, hop_length=512, smooth_seconds=4):
    """
    Extract energy progression features for structure analysis.

    Returns:
        energy_curve: Combined normalized energy (0-1)
        rms: Smoothed RMS envelope
        centroid: Smoothed spectral centroid
        onset_density: Smoothed onset strength
        bass_ratio: Low-frequency energy ratio
    """
```

**Drop Detection:**
```python
def detect_drops(energy_curve, sr, hop_length, threshold_ratio=2.0):
    """
    Detect sudden energy increases (drops) after quiet sections.

    Returns:
        drop_times: Array of timestamps where drops occur
    """
```

**Validation Criteria:**
- Breakdown sections show energy < 0.3
- Buildup sections show positive energy derivative
- Drop detection aligns with audible drops (±2 beats)

### 5. Tempo and Rhythm Analysis

**Research Source:** TranceSpecificAudioFeatureExtractionResearch.md

**Components:**
1. **Trance-Optimized Tempo Detection** - Prior centered at 139 BPM
2. **4-on-the-Floor Kick Detection** - Autocorrelation at beat period
3. **Off-beat Hi-hat Detection** - Energy between beats

**Implementation:**
```python
def detect_trance_tempo(y, sr):
    """
    Tempo detection with trance-specific prior (138-140 BPM).

    Returns:
        tempo: Detected BPM
        beat_times: Array of beat timestamps
        tempo_stability: Consistency measure (0-1)
        is_trance_tempo: bool (128-150 BPM range)
    """

def detect_four_on_floor(y, sr, tempo):
    """
    Verify 4-on-the-floor kick pattern.

    Returns:
        is_four_on_floor: bool (strength > 0.5)
        strength: Autocorrelation strength at beat period
    """
```

**Validation Criteria:**
- Tempo detection within ±1 BPM of labeled value
- 4-on-the-floor detection > 95% accurate on trance
- Stability scores higher for studio tracks vs live recordings

## TranceScoreCalculator Class

**Composite scoring with weighted features:**

```python
class TranceScoreCalculator:
    WEIGHTS = {
        'tempo_score': 0.20,          # BPM in trance range
        'pumping_score': 0.15,        # Sidechain presence
        'energy_progression': 0.15,   # Breakdown/buildup patterns
        'four_on_floor': 0.12,        # Kick pattern
        'supersaw_score': 0.10,       # Stereo characteristics
        'acid_303_score': 0.08,       # 303 elements (optional)
        'offbeat_hihat': 0.08,        # Hi-hat patterns
        'spectral_brightness': 0.07,  # High spectral centroid
        'tempo_stability': 0.05       # Consistent tempo
    }

    def compute_total_score(self, features) -> Tuple[float, Dict]:
        """
        Returns:
            total_score: 0-1 overall trance conformance
            component_scores: Individual feature scores
        """
```

## File Structure

```
src/feature_extraction/
├── __init__.py
├── trance_features.py      # Main trance feature extractor
├── pumping_detector.py     # Sidechain analysis
├── acid_detector.py        # 303 bassline detection
├── supersaw_analyzer.py    # Stereo spread analysis
├── energy_curves.py        # Energy progression
├── rhythm_analyzer.py      # Tempo, kicks, hi-hats
└── trance_scorer.py        # TranceScoreCalculator
```

## Integration with Existing System

### Extend AudioAnalyzer

```python
# In audio_analyzer.py
class AudioAnalyzer:
    def analyze(self, audio_path, include_trance_features=False, ...):
        result = self._base_analysis(audio_path)

        if include_trance_features:
            from feature_extraction.trance_features import extract_all_trance_features
            result.trance_features = extract_all_trance_features(audio_path)
            result.trance_score = TranceScoreCalculator().compute_total_score(
                result.trance_features
            )

        return result
```

### CLI Enhancement

```bash
# New command
python analyze.py --audio track.wav --trance-score

# Output
Trance Score: 0.78 / 1.00

Component Breakdown:
  Tempo (139 BPM):        0.95  [========= ]
  Sidechain Pumping:      0.72  [=======   ]
  Energy Progression:     0.85  [========  ]
  4-on-the-Floor:         0.98  [========= ]
  Supersaw Spread:        0.65  [======    ]
  303 Acid Elements:      0.12  [=         ]
  Off-beat Hi-hats:       0.78  [=======   ]
  Spectral Brightness:    0.70  [=======   ]
  Tempo Stability:        0.92  [=========]
```

## Baseline Extraction Process

### Run Against 215 Reference Tracks

```python
def extract_reference_baselines(reference_dir: str) -> dict:
    """
    Process all reference tracks and compute statistics.

    Returns:
        {
            'feature_name': {
                'mean': float,
                'std': float,
                'min': float,
                'max': float,
                'p25': float,
                'p50': float,
                'p75': float,
                'values': [...]  # Per-track values
            },
            ...
        }
    """
```

### Expected Baseline Ranges (From Research)

| Feature | Expected Mean | Expected Range |
|---------|---------------|----------------|
| Tempo | 138-140 BPM | 128-150 BPM |
| Modulation Depth (dB) | 4-8 dB | 2-12 dB |
| Pumping Regularity | < 0.15 | 0.05 - 0.3 |
| Stereo Width | 0.4-0.6 | 0.2 - 0.8 |
| Phase Correlation | 0.4-0.7 | 0.2 - 0.9 |
| Energy Range | > 0.5 | 0.3 - 0.8 |
| 4-on-floor Strength | > 0.7 | 0.5 - 0.95 |

## Testing Strategy

### Unit Tests

```python
# test_trance_features.py

def test_pumping_detection_heavy_sidechain():
    """Track with known heavy sidechain should score > 0.6"""
    result = extract_pumping_features("test_data/heavy_sidechain.wav")
    assert result['modulation_depth_linear'] > 0.6

def test_pumping_detection_no_sidechain():
    """Track without sidechain should score < 0.2"""
    result = extract_pumping_features("test_data/no_sidechain.wav")
    assert result['modulation_depth_linear'] < 0.2

def test_tempo_detection_accuracy():
    """Tempo detection should be within ±1 BPM"""
    result = detect_trance_tempo(load_audio("test_data/138bpm.wav"))
    assert 137 <= result['tempo'] <= 139

def test_trance_score_range():
    """Trance score should always be 0-1"""
    for track in test_tracks:
        score, _ = TranceScoreCalculator().compute_total_score(
            extract_all_features(track)
        )
        assert 0 <= score <= 1
```

### Integration Tests

```python
def test_full_analysis_pipeline():
    """Complete pipeline from audio to trance score"""
    analyzer = AudioAnalyzer()
    result = analyzer.analyze("test_track.wav", include_trance_features=True)

    assert hasattr(result, 'trance_features')
    assert hasattr(result, 'trance_score')
    assert 0 <= result.trance_score[0] <= 1

def test_baseline_extraction_completes():
    """Baseline extraction should process all tracks without error"""
    baselines = extract_reference_baselines("references/")
    assert len(baselines) > 0
    assert all(k in baselines for k in ['tempo', 'modulation_depth_linear'])
```

## Deliverables Checklist

- [ ] `trance_features.py` - Main extraction module
- [ ] `pumping_detector.py` - Sidechain analysis
- [ ] `acid_detector.py` - 303 detection
- [ ] `supersaw_analyzer.py` - Stereo analysis
- [ ] `energy_curves.py` - Energy progression
- [ ] `rhythm_analyzer.py` - Tempo/rhythm
- [ ] `trance_scorer.py` - TranceScoreCalculator
- [ ] Unit tests for all extractors
- [ ] Integration with AudioAnalyzer
- [ ] CLI command for trance scoring
- [ ] Baseline extraction script
- [ ] Initial reference statistics JSON
- [ ] Documentation with usage examples

## Success Criteria

1. **All feature extractors implemented** and match research specifications
2. **Unit test coverage > 80%** for feature extraction modules
3. **Trance score correlates with human judgment** on 10 validation tracks
4. **Baseline statistics extracted** from all 215 reference tracks
5. **Performance target met:** < 30s analysis per 5-minute track
6. **Integrated with existing analyzer** via `include_trance_features` flag
