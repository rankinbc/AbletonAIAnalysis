# ML System Architecture

## Architecture Overview

The ML-powered production assistant follows a **three-pillar architecture**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PRODUCTION AI SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐ │
│  │   PILLAR 1          │  │   PILLAR 2          │  │   PILLAR 3      │ │
│  │   STYLE DNA         │  │   GAP ANALYSIS      │  │   REMEDIATION   │ │
│  │                     │  │                     │  │                 │ │
│  │  • Feature Extract  │  │  • WIP Analysis     │  │  • Fix Gen      │ │
│  │  • Reference Learn  │  │  • Delta Compute    │  │  • Auto-Apply   │ │
│  │  • Embeddings       │  │  • Issue Ranking    │  │  • Validation   │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────┘ │
│           │                        │                       │            │
│           └────────────┬───────────┴───────────┬───────────┘            │
│                        │                       │                        │
│                        ▼                       ▼                        │
│              ┌─────────────────┐    ┌─────────────────┐                │
│              │  Style Profile  │    │  Ableton Bridge │                │
│              │  (Learned DNA)  │    │  (OSC Control)  │                │
│              └─────────────────┘    └─────────────────┘                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### Layer 1: Feature Extraction

```
┌─────────────────────────────────────────────────────────────┐
│                    FEATURE EXTRACTION LAYER                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   librosa    │  │   essentia   │  │    aubio     │      │
│  │  (General)   │  │  (EDM-tuned) │  │  (Real-time) │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         └────────────┬────┴────────────┬────┘               │
│                      │                 │                    │
│                      ▼                 ▼                    │
│         ┌────────────────────────────────────┐             │
│         │      Trance Feature Extractors      │             │
│         │  • Sidechain Pumping Detection     │             │
│         │  • 303 Bassline Analysis           │             │
│         │  • Supersaw Stereo Measurement     │             │
│         │  • Energy Curve Extraction         │             │
│         │  • Tempo & Rhythm Analysis         │             │
│         └────────────────────────────────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key Libraries:**
- **librosa 0.11.0** - General audio feature extraction
- **essentia** - EDM-optimized key detection, rhythm extraction
- **aubio** - Real-time capable onset/pitch detection
- **scipy** - Signal processing (filtering, correlation)
- **madmom** - Neural beat tracking (offline)

### Layer 2: Embedding & Similarity

```
┌─────────────────────────────────────────────────────────────┐
│                    EMBEDDING LAYER                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │              OpenL3 Base Embeddings               │      │
│  │         (6144-dim, music content type)            │      │
│  └──────────────────────┬───────────────────────────┘      │
│                         │                                   │
│                         ▼                                   │
│  ┌──────────────────────────────────────────────────┐      │
│  │           Fine-tuning Network                     │      │
│  │  ┌────────────────────────────────────────────┐  │      │
│  │  │  Linear(6144, 512) → LayerNorm → GELU      │  │      │
│  │  │  Dropout(0.1) → Linear(512, 256)           │  │      │
│  │  │  L2 Normalize                               │  │      │
│  │  └────────────────────────────────────────────┘  │      │
│  └──────────────────────┬───────────────────────────┘      │
│                         │                                   │
│                         ▼                                   │
│  ┌──────────────────────────────────────────────────┐      │
│  │              FAISS HNSW Index                     │      │
│  │         (Sub-millisecond similarity search)       │      │
│  └──────────────────────────────────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Training Configuration:**
- Triplet loss with margin 0.2-0.3
- Semi-hard negative mining
- Batch size 64, 4 samples per class
- Learning rate 1e-4 (head), 1e-5 (backbone if fine-tuning)
- AdamW optimizer with 0.01 weight decay

### Layer 3: Profile & Comparison

```
┌─────────────────────────────────────────────────────────────┐
│                    PROFILE LAYER                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │              Reference Profile                    │      │
│  │  ┌──────────────────────────────────────────┐   │      │
│  │  │  Feature Statistics:                      │   │      │
│  │  │  • Mean, std, percentiles per feature    │   │      │
│  │  │  • Confidence intervals                   │   │      │
│  │  │  • Acceptable ranges                      │   │      │
│  │  └──────────────────────────────────────────┘   │      │
│  │  ┌──────────────────────────────────────────┐   │      │
│  │  │  Style Clusters:                          │   │      │
│  │  │  • Uplifting vs Progressive vs Tech      │   │      │
│  │  │  • Energy level groupings                │   │      │
│  │  │  • Era/production style clusters         │   │      │
│  │  └──────────────────────────────────────────┘   │      │
│  │  ┌──────────────────────────────────────────┐   │      │
│  │  │  Target Embeddings:                       │   │      │
│  │  │  • Centroid per cluster                  │   │      │
│  │  │  • Variance envelope                     │   │      │
│  │  └──────────────────────────────────────────┘   │      │
│  └──────────────────────────────────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Layer 4: Fix Generation

```
┌─────────────────────────────────────────────────────────────┐
│                    FIX GENERATION LAYER                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Gap Analysis Input:                                        │
│  ┌──────────────────────────────────────────────────┐      │
│  │  Feature: bass_spectral_centroid                  │      │
│  │  WIP Value: 180 Hz                                │      │
│  │  Reference Target: 120 Hz (±15)                   │      │
│  │  Delta: +60 Hz (outside acceptable range)         │      │
│  └──────────────────────┬───────────────────────────┘      │
│                         │                                   │
│                         ▼                                   │
│  Fix Generation:                                            │
│  ┌──────────────────────────────────────────────────┐      │
│  │  1. Map delta to device parameter                 │      │
│  │     bass_spectral_centroid → EQ low-mid cut      │      │
│  │                                                   │      │
│  │  2. Calculate parameter adjustment                │      │
│  │     Target: -3dB shelf at 200Hz                  │      │
│  │                                                   │      │
│  │  3. Find device on track                         │      │
│  │     Track "Bass" → Device "EQ Eight" [0]         │      │
│  │                                                   │      │
│  │  4. Generate ParameterChange                     │      │
│  │     track=2, device=0, param=5, value=0.35       │      │
│  └──────────────────────────────────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Reference Tracks (215)
        │
        ▼
┌───────────────────┐
│ Feature Extraction │──────────────────┐
└───────────────────┘                   │
        │                               │
        ▼                               ▼
┌───────────────────┐         ┌───────────────────┐
│  OpenL3 Embedding  │         │  Trance Features   │
└───────────────────┘         └───────────────────┘
        │                               │
        ▼                               ▼
┌───────────────────┐         ┌───────────────────┐
│   Fine-tune with   │         │  Statistical       │
│   Triplet Loss     │         │  Aggregation       │
└───────────────────┘         └───────────────────┘
        │                               │
        ▼                               ▼
┌───────────────────┐         ┌───────────────────┐
│   FAISS Index      │         │  Style Profile     │
│   (Similarity)     │         │  (Targets)         │
└───────────────────┘         └───────────────────┘
        │                               │
        └───────────┬───────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  Profile Store │
            │  (JSON/Pickle) │
            └───────────────┘


WIP Track Analysis:

WIP Track
    │
    ├────────────────────┬────────────────────┐
    ▼                    ▼                    ▼
┌─────────┐      ┌─────────────┐      ┌─────────────┐
│ Extract  │      │  Extract     │      │   Stem      │
│ Features │      │  Embedding   │      │ Separation  │
└─────────┘      └─────────────┘      └─────────────┘
    │                    │                    │
    ▼                    ▼                    ▼
┌─────────┐      ┌─────────────┐      ┌─────────────┐
│ Compare  │      │  Similarity  │      │  Per-Stem   │
│ to Profile│     │  Search      │      │  Analysis   │
└─────────┘      └─────────────┘      └─────────────┘
    │                    │                    │
    └────────────────────┴────────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │   Gap Report     │
                │   + Fix Recs     │
                └─────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │  Ableton Bridge  │
                │  (Apply Fixes)   │
                └─────────────────┘
```

## Module Structure

```
src/
├── feature_extraction/
│   ├── __init__.py
│   ├── trance_features.py      # Sidechain, 303, supersaw, energy
│   ├── spectral_features.py    # FFT-based analysis
│   ├── rhythm_features.py      # Tempo, beat, groove
│   └── stereo_features.py      # Width, correlation, M/S
│
├── embeddings/
│   ├── __init__.py
│   ├── openl3_extractor.py     # Base embedding extraction
│   ├── fine_tuning.py          # Triplet loss training
│   ├── similarity_index.py     # FAISS wrapper
│   └── augmentation.py         # Audio augmentation pipeline
│
├── profiling/
│   ├── __init__.py
│   ├── reference_profiler.py   # Build profile from references
│   ├── style_clusters.py       # Sub-style discovery
│   ├── profile_storage.py      # Save/load profiles
│   └── profile_validator.py    # Sanity checks
│
├── analysis/
│   ├── __init__.py
│   ├── gap_analyzer.py         # WIP vs profile comparison
│   ├── trance_scorer.py        # Genre conformance scoring
│   ├── delta_reporter.py       # Human-readable gap reports
│   └── stem_analyzer.py        # Per-stem analysis
│
├── fixes/
│   ├── __init__.py
│   ├── prescriptive_generator.py  # Profile-aware fix generation
│   ├── fix_prioritizer.py         # Rank fixes by impact
│   ├── parameter_mapper.py        # Feature→device parameter mapping
│   └── fix_validator.py           # Pre-application validation
│
└── integration/
    ├── __init__.py
    ├── ableton_bridge.py       # (existing) OSC communication
    ├── stem_processor.py       # Demucs integration
    └── realtime_monitor.py     # (future) Live monitoring
```

## Technology Stack

### Core ML/Audio
| Component | Library | Version | Purpose |
|-----------|---------|---------|---------|
| Audio I/O | librosa | 0.11.0 | Load, resample, basic features |
| EDM Features | essentia | 2.1+ | Key detection, rhythm |
| Beat Tracking | madmom | 0.16+ | Neural beat/downbeat |
| Stem Separation | demucs | 4.0+ | Drums/bass/other isolation |
| Embeddings | openl3 | 0.4+ | Pre-trained audio embeddings |
| ML Framework | PyTorch | 2.0+ | Fine-tuning, training |
| Metric Learning | pytorch-metric-learning | 2.0+ | Triplet loss, mining |
| Vector Search | faiss-cpu | 1.7+ | Similarity indexing |

### Audio Processing
| Component | Library | Purpose |
|-----------|---------|---------|
| Filtering | scipy.signal | Bandpass, lowpass filters |
| FFT | numpy.fft | Spectral analysis |
| Resampling | librosa/scipy | Sample rate conversion |
| Augmentation | audiomentations | Training data augmentation |

### Integration
| Component | Library | Purpose |
|-----------|---------|---------|
| OSC Client | python-osc | AbletonOSC communication |
| Data Storage | JSON/pickle | Profile persistence |
| Visualization | matplotlib | Debug/analysis plots |

## Performance Targets

| Operation | Target | Constraint |
|-----------|--------|------------|
| Full track analysis | < 60s | 5-minute track |
| Feature extraction | < 10s | Per track |
| Embedding extraction | < 5s | Per track (GPU) |
| Similarity search | < 10ms | 1000 track index |
| Profile comparison | < 2s | Full gap analysis |
| Fix generation | < 1s | All recommendations |
| Fix application | < 100ms | Per parameter |

## Scalability Considerations

### Current Scale (215 tracks)
- In-memory FAISS index (HNSW)
- JSON profile storage
- Single-machine processing
- CPU-only feasible (GPU optional)

### Future Scale (1000+ tracks)
- Consider FAISS IVF index
- SQLite or proper database for metadata
- Batch processing pipeline
- GPU strongly recommended for embeddings

## Security & Privacy

- All processing is local (no cloud dependency)
- Reference tracks remain on user's machine
- Profiles contain statistical aggregates, not raw audio
- No telemetry or data collection

## Integration Points

### Existing System Integration
```python
# Current: audio_analyzer.py
result = analyzer.analyze(audio_path)

# Enhanced: with trance features
result = analyzer.analyze(audio_path,
                          include_trance_features=True,
                          compare_to_profile="trance_profile.json")

# Current: smart_fix_generator.py
fixes = generator.generate_fixes(analysis)

# Enhanced: with profile-aware generation
fixes = generator.generate_fixes(analysis,
                                  style_profile=profile,
                                  target_similarity=0.8)
```

### Ableton Integration
```python
# Current capability
bridge.set_device_parameter(track, device, param, value)

# Enhanced workflow
for fix in prescriptive_fixes:
    if fix.confidence > 0.8:
        bridge.apply_change(fix.to_parameter_change())
```
