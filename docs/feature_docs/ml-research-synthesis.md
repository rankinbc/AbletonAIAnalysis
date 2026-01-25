# ML Research Synthesis

## Overview

This document synthesizes key findings from the four research documents analyzed for the ML implementation plan. It extracts actionable technical specifications, recommended approaches, and critical constraints.

**Source Documents:**
1. `MLMusicResearch.md` - General ML tools for music production
2. `ProductionMusicSimilarityResearch.md` - Similarity system architecture
3. `TranceSpecificAudioFeatureExtractionResearch.md` - Trance feature extraction
4. `compass_artifact_*.md` - Real-time Ableton integration

---

## Key Finding 1: Library Selection

### Recommended Stack

| Purpose | Library | Why |
|---------|---------|-----|
| General Features | **librosa 0.11.0** | Accessible, well-documented, sufficient for offline analysis |
| EDM-Specific | **essentia** | `key_edma` profile for electronic music, 300+ descriptors |
| Beat Tracking | **madmom** | Neural network-based, superior for constant-tempo EDM |
| Stem Separation | **Demucs v4** | State-of-art SDR ~9.2 dB, hybrid transformer architecture |
| Embeddings | **OpenL3** | Music-trained, outperforms PANNs on music tasks |
| Similarity Search | **FAISS** | Sub-millisecond queries, production-ready |
| Metric Learning | **pytorch-metric-learning** | Triplet loss, miners, samplers all included |

### Critical Notes

> "Spotify deprecated its Audio Features API in November 2024 for new applications" - MLMusicResearch.md

Use local analysis only. No external API dependencies.

> "librosa is 5-10× slower than Essentia/audioFlux for batch processing" - compass_artifact

For batch processing (profiling 215 tracks), consider Essentia. For interactive analysis, librosa is acceptable.

---

## Key Finding 2: Embedding Architecture

### OpenL3 Configuration

From ProductionMusicSimilarityResearch.md:

```python
openl3.get_audio_embedding(
    audio, sr,
    content_type="music",      # CRITICAL: use music-trained model
    input_repr="mel128",       # 128-band mel spectrogram
    embedding_size=6144,       # Full resolution for fine-tuning
    hop_size=0.5,              # 500ms for efficiency
    batch_size=32
)
```

**Key insight:** OpenL3 outputs frame-wise embeddings at 10Hz. For global track embedding, use temporal mean pooling.

### Fine-Tuning Network

```
OpenL3 (6144) → Linear(512) → LayerNorm → GELU → Dropout(0.1) → Linear(256) → L2 Normalize
```

**Recommended hyperparameters:**
- Triplet margin: 0.2-0.3
- Mining: Semi-hard (NOT hard - causes collapse)
- Batch size: 64-128
- Samples per class: 4-8
- Learning rate: 1e-4 (head), 1e-5 (backbone)
- Optimizer: AdamW, weight_decay=0.01

### Training Data Requirements

> "Training custom models on your favorite tracks is entirely feasible with 200-500 songs using transfer learning" - MLMusicResearch.md

**215 tracks = GREEN LIGHT** for custom model training.

---

## Key Finding 3: Trance-Specific Features

### Feature Specifications

From TranceSpecificAudioFeatureExtractionResearch.md:

#### Sidechain Pumping
| Metric | Moderate | Heavy |
|--------|----------|-------|
| Modulation Depth (linear) | 0.3-0.6 | >0.6 |
| Modulation Depth (dB) | 4-8 dB | >8 dB |
| Pumping Regularity | <0.15 | <0.1 |

#### 303 Acid Detection
Weighted composite score:
- Filter sweep intensity: 30%
- Resonance metric: 25%
- Glide ratio: 25%
- Accent correlation: 20%

#### Supersaw Analysis
- Stereo width ratio: 0.3-0.8 typical
- Phase correlation: 0.3-0.7 typical (supersaw)
- Detuning: 10-40 cents typical

#### Energy Curves
| Section | RMS Energy | Spectral Centroid | Bass Ratio | Derivative |
|---------|------------|-------------------|------------|------------|
| Breakdown | < 0.3 | Low/stable | < 0.2 | ~0 or negative |
| Buildup | 0.3-0.7 | Rising | 0.2-0.5 | Positive |
| Drop | > 0.7 | High | > 0.5 | ~0 |

#### Tempo
- Trance range: 128-150 BPM
- Optimal: 138-140 BPM
- Use prior distribution centered at 139 BPM

### Trance Score Weights

```python
WEIGHTS = {
    'tempo_score': 0.20,
    'pumping_score': 0.15,
    'energy_progression': 0.15,
    'four_on_floor': 0.12,
    'supersaw_score': 0.10,
    'acid_303_score': 0.08,
    'offbeat_hihat': 0.08,
    'spectral_brightness': 0.07,
    'tempo_stability': 0.05
}
```

---

## Key Finding 4: Ableton Integration Constraints

### Critical Limitation

> "AbletonOSC cannot access raw audio streams" - compass_artifact

**Implications:**
- Cannot do real-time audio analysis through AbletonOSC
- Must use exported stems for analysis
- Max for Live required for true real-time audio access

### What AbletonOSC CAN Do

- Transport control (tempo, play/stop)
- Track operations (volume, pan, mute, solo)
- Device parameter control (read/write all parameters)
- Clip manipulation
- Output meter levels (requires visible meters)

### Latency Budget

| Component | Typical Latency |
|-----------|-----------------|
| Audio buffer (256 samples) | 5.8ms |
| FFT window (2048 samples) | 46ms |
| OSC round-trip | ~1ms |
| Python processing | 1-5ms |
| **Total pipeline** | **~30-50ms** |

**Acceptable for:** Spectrum visualization (<100ms), EQ guidance (<200ms)
**Not acceptable for:** Live musical performance (<10ms)

### Recommended Architecture

```
Ableton Live
    │
    ├── AbletonOSC (Control Surface)
    │   Port 11000 ↔ 11001
    │   • Parameter control
    │   • Session state queries
    │
    └── [Optional] Max for Live Device
        • plugin~ → fft~ → udpsend
        • Real-time audio access
```

---

## Key Finding 5: Data Augmentation

### Safe Augmentation Ranges

From ProductionMusicSimilarityResearch.md:

| Augmentation | Safe Range | Notes |
|--------------|------------|-------|
| Pitch shift | ±3 semitones | Preserves harmonic relationships |
| Time stretch | 0.9-1.1x (±10%) | Maintains rhythmic integrity |
| Gaussian noise | 0.001-0.015 amplitude | Adds robustness without overwhelming |
| Gain | -6 to +3 dB | Normal production variation |

**Critical warning:**
> "Pitch shifting beyond ±4 semitones risks changing the perceived key so dramatically that tracks from the same production style register as dissimilar" - ProductionMusicSimilarityResearch.md

---

## Key Finding 6: Evaluation Metrics

### Embedding Quality

| Metric | Target | What it measures |
|--------|--------|-----------------|
| Precision@5 | > 0.70 | Retrieval accuracy |
| Silhouette Score | > 0.50 | Cluster separation |
| NMI | > 0.60 | Alignment with labels |

### Classification (if needed)

> "Ensemble methods (Random Forest + Gradient Boosting + SVM) with RobustScaler normalization typically achieve 75-80% accuracy on multi-genre classification tasks" - TranceSpecificAudioFeatureExtractionResearch.md

### Invariance Testing

Test model robustness:
- Tempo invariance: Embeddings stable under time stretch
- Pitch invariance: Embeddings stable under pitch shift
- Level invariance: Embeddings stable under gain changes

---

## Key Finding 7: Commercial Tool Benchmarks

### Reference for Quality Targets

| Tool | What it does well | Limitation |
|------|-------------------|------------|
| iZotope Ozone | Master Assistant, inter-plugin communication | Generic targets, not personalized |
| Sonible smart:EQ | Cross-channel processing, 2000+ bands | Limited to EQ |
| REFERENCE 2 | Spectral matching, stereo analysis | Manual comparison only |
| Metric AB | Comprehensive metering | Analysis only, no fixes |

**Our advantage:** Learn user's specific taste, generate actionable fixes, integrate with Ableton for auto-application.

---

## Key Finding 8: Performance Targets

### From Research Documents

| Operation | Target | Source |
|-----------|--------|--------|
| Demucs separation | ~10s per 3-min track (GPU) | MLMusicResearch.md |
| OpenL3 embedding | ~50ms per clip | compass_artifact |
| FAISS HNSW query | <1ms for million-scale | ProductionMusicSimilarityResearch.md |
| Full track analysis | <60s for 5-min track | Derived |

### Memory Considerations

| Component | Memory |
|-----------|--------|
| OpenL3-512 embedding | 2KB per track |
| OpenL3-6144 embedding | 24KB per track |
| PANNs embedding | 8KB per track |
| Fine-tuned 256-dim | 1KB per track |

For 215 tracks with 256-dim embeddings: ~215KB total (trivial)

---

## Key Finding 9: Dataset Resources

### For Training/Validation

| Dataset | Size | Use |
|---------|------|-----|
| Beatport EDM Dataset | 3,500 tracks, 35 subgenres | Genre classification |
| HouseX-v2 | Mainstage EDM, soft labels | EDM-specific testing |
| GTZAN | 1,000 tracks, 10 genres | General benchmarking |

### For Reference Material

> "A State of Trance compilations and Beatport's Trance Top 100 provide current genre benchmarks" - TranceSpecificAudioFeatureExtractionResearch.md

---

## Key Finding 10: Risk Factors

### Technical Risks

1. **Model overfitting on small collection**
   - Mitigation: Transfer learning, aggressive augmentation
   - 215 tracks + augmentation → effectively 600+ samples

2. **Feature extraction inconsistency**
   - Mitigation: Pin library versions, comprehensive tests
   - Validate on known reference tracks

3. **Ableton integration fragility**
   - Mitigation: Graceful degradation, offline mode
   - Test across Live versions

### Quality Risks

1. **Fixes make track worse**
   - Mitigation: Confidence thresholds, undo capability
   - Always allow human override

2. **Profile learns wrong patterns**
   - Mitigation: Human validation of profile
   - A/B testing of recommendations

3. **Over-automation removes creativity**
   - Mitigation: User controls depth of automation
   - Always explain reasoning

---

## Implementation Priority Matrix

Based on research findings, prioritized by impact and feasibility:

### Phase 1 Priority (Highest Impact, Most Feasible)
- Trance feature extractors (complete code in research)
- TranceScoreCalculator (weights provided)
- Basic profile statistics

### Phase 2 Priority (High Impact, Feasible)
- Reference profile building
- Statistical analysis
- Clustering for sub-styles

### Phase 3 Priority (High Impact, Moderate Complexity)
- Gap analyzer
- Delta computation
- Prioritization logic

### Phase 4 Priority (Medium Impact, Higher Complexity)
- OpenL3 embedding extraction
- Triplet loss training
- FAISS indexing

### Phase 5 Priority (High Impact, Depends on 1-4)
- Prescriptive fix generation
- Device parameter mapping
- Ableton integration

### Phase 6 Priority (Long-term Value)
- Feedback collection
- Continuous refinement
- A/B testing

---

## Code Snippets Ready for Implementation

The research documents contain near-production-ready code for:

1. **Sidechain pumping detection** - TranceSpecificAudioFeatureExtractionResearch.md lines 15-90
2. **303 acid detection** - TranceSpecificAudioFeatureExtractionResearch.md lines 116-209
3. **Supersaw analysis** - TranceSpecificAudioFeatureExtractionResearch.md lines 215-304
4. **Energy curves** - TranceSpecificAudioFeatureExtractionResearch.md lines 310-378
5. **Tempo detection** - TranceSpecificAudioFeatureExtractionResearch.md lines 385-492
6. **Trance score calculator** - TranceSpecificAudioFeatureExtractionResearch.md lines 580-640
7. **OpenL3 extraction** - ProductionMusicSimilarityResearch.md lines 12-39
8. **Triplet training** - ProductionMusicSimilarityResearch.md lines 49-96, 209-312
9. **FAISS indexing** - ProductionMusicSimilarityResearch.md lines 156-204
10. **Spectrum comparison** - compass_artifact lines 96-117

These can be ported with minimal modification.

---

## Conclusion

The research provides a comprehensive foundation for building the ML-powered production assistant:

1. **Feasible with 215 tracks** - Transfer learning makes this work
2. **Clear technical path** - Libraries, architectures, hyperparameters specified
3. **Trance-specific algorithms** - Not generic, optimized for the genre
4. **Integration constraints understood** - AbletonOSC limitations known
5. **Quality benchmarks defined** - Know what "good enough" looks like

The phased approach allows incremental value delivery while building toward the full vision of an AI co-producer that learns the user's taste and provides prescriptive guidance.
