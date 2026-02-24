# Evaluation Framework: Metrics, Listening Tests, and Phase Gates

> Every phase gate requires BOTH automated metrics AND human listening tests.
> No metric reliably predicts human preference — listening tests catch what numbers miss.

---

## Automated Metrics

### Core Metrics (computed by MusPy + music21)

| Metric | Description | Target Range (Trance) | Weight |
|--------|-------------|----------------------|--------|
| **Pitch entropy** | Shannon entropy of pitch distribution | 2.5–3.0 bits | 0.10 |
| **Pitch range** | Max pitch - min pitch in octaves | 1.5–2.5 octaves | 0.05 |
| **Chord-tone ratio** | % of notes that are chord tones | >80% | 0.20 |
| **Self-similarity (8-bar)** | Cosine similarity of 8-bar chunks | >0.6 | 0.10 |
| **Self-similarity (16-bar)** | Cosine similarity of 16-bar chunks | >0.4 | 0.05 |
| **Stepwise motion ratio** | % of intervals ≤ M2 | >60% | 0.10 |
| **nPVI** | Normalized pairwise variability index (rhythm) | 30–60 | 0.05 |
| **KL-div vs reference** | KL-divergence of pitch class distribution | Lower is better | 0.15 |
| **Tension correlation** | Pearson r between target and actual tension curve | >0.4 (Phase 3+) | 0.15 |
| **Resolution patterns** | Count of 7→1, 4→3, 2→1 resolutions per phrase | >1 per 8 bars | 0.05 |

**Composite score** = weighted sum, normalized to [0, 1].

### Trance-Specific Metrics

| Metric | Description | How to Compute |
|--------|-------------|---------------|
| **Minor-key adherence** | % of notes in natural/harmonic minor | music21 scale membership |
| **Phrase regularity** | Whether phrases align to 4/8/16-bar boundaries | Onset density analysis |
| **Hook memorability** | Self-similarity of the first 4 bars vs. later occurrences | Chroma cosine similarity |
| **Register consistency** | Standard deviation of pitch within a section | Low = consistent |

### Reference Corpus

- **Size:** 20–50 verified trance MIDI melodies (subset of Tier 1 dataset)
- **Stored as:** `reference_stats.json` containing per-metric distributions (mean, std, percentiles)
- **Updated:** When Tier 1 dataset grows, recompute reference stats

### Baseline Recording

At the start of each phase, generate 50 melodies with the current best configuration and record all metrics. These baselines are the comparison point for improvement.

```python
# Generate and store baseline
baseline = pipeline.generate_batch(n=50, params=standard_trance_params)
metrics = [evaluate_melody(m, reference_stats) for m in baseline]
save_json(f"baselines/phase_{phase_num}_baseline.json", metrics)
```

---

## Human Listening Test Protocol

### When to Run

- **Every phase gate** (end of Phase 1, 2, 3, 4)
- **After any major model swap** (e.g., replacing Melody RNN with midi-model)
- **Before declaring production-ready**

### Test Design

**Format:** Blind A/B forced-choice comparison

**Procedure:**
1. Generate 10 melodies with configuration A (previous best)
2. Generate 10 melodies with configuration B (new candidate)
3. Pair melodies randomly: A1 vs B1, A2 vs B2, etc.
4. Each pair rendered as audio (same synth patch, same tempo, same duration)
5. Listener hears both, answers: **"Which sounds more like a real trance melody?"**
6. Listener does NOT know which is A or B (blind)

**Listeners:** 3–5 people minimum. Can be:
- The user (primary producer)
- Collaborators or friends who listen to trance
- Online music production community members

**Logistics:** ~15–30 minutes per listener per phase gate.

### Scoring

- **Win rate:** % of comparisons where new config is preferred
- **>60%:** Statistically meaningful improvement (proceed to next phase)
- **50–60%:** Marginal improvement (consider iterating before proceeding)
- **<50%:** Regression (do not proceed, investigate why)

**Statistical significance:** With 10 pairs and 3 listeners = 30 comparisons. Binomial test: >60% (18/30) is significant at p<0.05.

### Audio Rendering

To ensure fair comparison, render all test melodies with identical settings:
- Synth: Ableton Analog or a simple saw lead (consistent across all tests)
- Tempo: 140 BPM
- Duration: 16 bars (same length)
- No effects (dry signal only)
- Export as WAV at 44.1kHz

```python
# Render MIDI to audio for listening test
def render_for_listening_test(midi_path, output_wav, synth='analog_saw'):
    """Render MIDI to audio with standardized synth patch."""
    # Use FluidSynth or a fixed Ableton preset
    # Ensure consistent volume normalization
    pass
```

### Recording Results

```json
{
  "phase_gate": "Phase 2",
  "date": "2026-XX-XX",
  "config_a": "Phase 1 hybrid (pre-trained)",
  "config_b": "Phase 2 hybrid (fine-tuned midi-model)",
  "listeners": 3,
  "pairs": 10,
  "total_comparisons": 30,
  "b_wins": 22,
  "a_wins": 8,
  "win_rate_b": 0.733,
  "p_value": 0.008,
  "decision": "proceed_to_phase_3",
  "notes": "Listeners noted B melodies felt more 'trance-like' and had better phrasing."
}
```

---

## Phase Gate Criteria

### Phase 1 Gate (Foundation → Fine-Tuning)

| Criterion | Threshold | Method |
|-----------|-----------|--------|
| Composite score improvement | >0% vs. rule-only baseline | Automated |
| Pipeline operational | Generates 50 melodies without errors | Automated |
| Human preference | >60% vs. rule-only | Listening test |

**Decision:** Proceed to Phase 2 if all three pass. If human preference is <60%, investigate which metric is misleading.

### Phase 2 Gate (Fine-Tuning → Structure/Tension)

| Criterion | Threshold | Method |
|-----------|-----------|--------|
| Composite score improvement | >15% vs. Phase 1 | Automated |
| Statistical significance | p<0.05 on at least 3 of 7 metrics | Wilcoxon |
| Human preference | >60% vs. Phase 1 | Listening test |
| **Production-ready check** | >90% of reference corpus composite | Automated |

**Decision:**
- If production-ready check passes AND human preference >70%: **Declare production-ready.** Phase 3–4 are optional.
- Otherwise: Proceed to Phase 3. Document specific gaps.

### Phase 3 Gate (Structure/Tension → Custom Model)

| Criterion | Threshold | Method |
|-----------|-----------|--------|
| Tension correlation | >0.4 | Automated |
| Section contrast | Audible in A/B test | Listening test |
| Human preference | >60% vs. Phase 2 | Listening test |
| **Rejection sampling gate** | Record best N=50 scores | Automated |

**Decision:**
- If rejection sampling at N=50 achieves >95% theory compliance AND >0.5 tension correlation: **RL (Step 4.3) is not needed.**
- If human preference >70% vs. Phase 2: Consider declaring production-ready.
- Otherwise: Proceed to Phase 4.

### Phase 4 Gate (Final)

| Criterion | Threshold | Method |
|-----------|-----------|--------|
| Multi-voice coherence | Passes rhythmic interlock checks | Automated |
| Total latency | <5 seconds on CPU | Automated |
| Human preference | >60% vs. Phase 3 | Listening test |
| Stability | 100 consecutive generations without crash | Automated |

---

## Metric Storage and Comparison

All metrics are stored in timestamped JSON files:

```
evaluation/
├── reference_stats.json           # Reference corpus distributions
├── baselines/
│   ├── phase_0_rule_only.json     # Rule engine baseline
│   ├── phase_1_hybrid.json
│   ├── phase_2_finetuned.json
│   ├── phase_3_structured.json
│   └── phase_4_custom.json
├── benchmarks/
│   ├── 2026-XX-XX_phase2_comparison.json
│   └── ...
└── listening_tests/
    ├── 2026-XX-XX_phase1_gate.json
    └── ...
```

Comparison script:
```python
def compare_phases(baseline_a, baseline_b, reference_stats):
    """Compare two phase baselines with statistical tests."""
    metrics_a = load_json(baseline_a)
    metrics_b = load_json(baseline_b)

    for metric in CORE_METRICS:
        values_a = [m[metric] for m in metrics_a]
        values_b = [m[metric] for m in metrics_b]

        stat, p_value = wilcoxon(values_a, values_b)
        improvement = (np.mean(values_b) - np.mean(values_a)) / np.mean(values_a)

        print(f"{metric}: {improvement:+.1%} (p={p_value:.4f})")
```
