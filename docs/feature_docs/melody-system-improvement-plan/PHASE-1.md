# Phase 1: Foundation and Quick Wins

> **Timeline:** Weeks 1–4 (realistically 5–6)
> **GPU Required:** No
> **Training Required:** No
> **Goal:** Working hybrid pipeline (rules + pre-trained ML) producing measurably better melodies than the current system

---

## Step 1.1 — Environment Isolation and Dependency Setup ✅ IMPLEMENTED

**Duration:** 1–2 days
**Status:** Complete — Docker-based approach implemented in `shared/magenta/`

### What and Why

Isolate the Magenta toolchain (Python 3.9 / TensorFlow 2.11) from the host environment using Docker, following the same pattern already used for `shared/allin1` and `shared/openl3`. This avoids the conda complexity, works identically on Windows 11 (via Docker Desktop), Linux, and macOS, and produces a reproducible build that never conflicts with the host Python.

**Why Docker instead of conda (original plan):**

| Concern | Conda approach | Docker approach |
|---------|---------------|-----------------|
| Windows 11 TF 2.11 | GPU requires WSL2 anyway | Runs in Linux container natively |
| Reproducibility | Lock files can drift | Dockerfile = exact reproduction |
| User setup | Must manage conda envs | `docker build` once |
| Persistent service | Flask on port 5050 to manage | Stateless containers, nothing to manage |
| Existing project pattern | New pattern | Matches shared/allin1 + shared/openl3 |

### Implementation (shared/magenta/)

```
shared/magenta/
├── Dockerfile           # Python 3.9 + TF 2.11 + Magenta + pre-trained models
├── magenta_worker.py    # Script run inside container (JSON stdin → JSON stdout)
├── docker_magenta.py    # DockerMagenta wrapper class (host-side API)
└── __init__.py          # Module exports
```

**Pre-trained models baked into the image:**
- `chord_pitches_improv.mag` — Improv RNN (chord-conditioned generation)
- `attention_rnn.mag` — Attention RNN (unconditional generation)
- `mel_2bar_small` — MusicVAE 2-bar (motif variation)
- `mel_16bar_small_q2` — MusicVAE 16-bar (longer-form variation)

### Usage

```python
from shared.magenta import DockerMagenta

magenta = DockerMagenta()

# Generate chord-conditioned melody (Improv RNN)
result = magenta.generate_melody(
    chords=["Am", "F", "C", "G"],
    bars=8, bpm=140, temperature=1.0, num_candidates=5
)
for path in result.midi_paths:
    print(path)  # host filesystem path to generated MIDI

# Motif variation (MusicVAE)
result = magenta.vary_motif("motif.mid", num_variants=4, noise_scale=0.3)

# Interpolation
result = magenta.interpolate("a.mid", "b.mid", steps=8)

# Random sampling from latent space
result = magenta.sample_musicvae(num_samples=4, temperature=0.5)

# Encode to latent vector (for similarity index)
latent = magenta.encode_motif("motif.mid")
```

### Build

```bash
cd shared/magenta
docker build -t magenta:latest .
# ~10-15 minutes first time (downloads TF + Magenta + 4 model checkpoints)
```

### Success Criteria

- [x] Docker image builds without errors
- [x] Wrapper class follows existing shared/ pattern (subprocess + JSON stdout)
- [x] All 6 Magenta operations exposed: generate_melody, generate_attention, vary_motif, interpolate, sample_musicvae, encode_motif
- [x] Health checks: `is_docker_available()`, `is_magenta_image_available()`
- [x] Pre-trained model bundles included in image (no manual download)

### Latency Notes

Per-call latency is ~5–10s due to container startup + model loading. This is acceptable for melody generation (not real-time). For batch operations, use `num_candidates` or `num_variants` parameters to generate multiple outputs in a single container invocation, amortizing startup cost.

---

## Step 1.2 — Replace Hand-Coded Music Theory with music21

**Duration:** 3–5 days

### What and Why

Swap out every hard-coded scale lookup, interval table, chord-tone list, and key detection function with music21 equivalents. This is the single highest-impact change per line of code — it makes the constraint layer more accurate, more maintainable, and immediately capable of things hand-coded rules cannot do (Roman numeral analysis, voice leading evaluation, passing tone detection, non-chord-tone classification).

### Tasks

- [ ] **Scale/mode operations:** Replace hardcoded arrays with `music21.scale` classes (`MinorScale`, `HarmonicMinorScale`, `PhrygianScale`, `LydianScale`, `MixolydianScale`)
- [ ] **Chord-tone analysis:** Use `music21.harmony.ChordSymbol` for chord membership testing. Enables non-chord-tone classification (passing tones, neighbor tones, suspensions, appoggiaturas) that the current 80/20 rule cannot express
- [ ] **Interval validation:** Replace magic-number interval checks with `music21.interval.Interval` objects
- [ ] **Key detection:** Use Krumhansl-Schmuckler algorithm via `music21.analysis.discrete` for automatic key estimation of imported MIDI
- [ ] **Consonance/dissonance scoring:** Use `interval.isConsonant()` and interval quality properties
- [ ] Write regression tests: existing rule outputs should remain valid under music21

### Implementation Notes

```python
from music21 import scale, pitch, interval, harmony, analysis

# Scale membership (replaces hardcoded arrays)
am_scale = scale.MinorScale('A')
is_in_scale = am_scale.getScaleDegreeFromPitch(pitch.Pitch('C4')) is not None

# Chord-tone analysis (replaces 80/20 rule)
chord = harmony.ChordSymbol('Am')
note = pitch.Pitch('E4')
is_chord_tone = note.name in [p.name for p in chord.pitches]

# Non-chord-tone classification
# Chord tones on strong beats, passing/neighbor tones on weak beats

# Interval validation (replaces magic numbers)
i = interval.Interval(pitch.Pitch('C4'), pitch.Pitch('F#4'))
is_tritone = i.simpleName == 'A4' or i.simpleName == 'd5'

# Key detection from MIDI
score = converter.parse('melody.mid')
key_result = score.analyze('key')
```

### Success Criteria

- All existing scale/interval/chord logic replaced with music21 calls
- Regression tests pass
- New capabilities demonstrated: passing tone detection, Roman numeral analysis

---

## Step 1.3 — Integrate MidiTok for REMI Tokenization ✅ IMPLEMENTED

**Duration:** 1–2 days
**Status:** Complete — implemented in `melody_generation/tokenizer.py`

### What and Why

Standard tokenization layer between MIDI files, NoteEvent lists, and ML models. REMI tokenization encodes metrical structure (Bar, Position) explicitly — critical for trance's rigid 4/4 meter.

### Implementation

**File:** `projects/ableton-generators/melody_generation/tokenizer.py`

Three conversion layers, each working independently:

1. **NoteEvent ↔ MIDI** (uses `mido`, no ML dependency)
   - `notes_to_midi()` / `midi_to_notes()` — bidirectional conversion
   - Works standalone for evaluation, MIDI export, etc.

2. **MIDI ↔ Tokens** (uses `miditok`, optional dependency)
   - `midi_to_tokens()` / `tokens_to_midi()` — REMI tokenization
   - Configured for trance: 32 velocities, 16th-note resolution, 130–150 BPM range

3. **NoteEvent ↔ Tokens** (shortcut through temp MIDI)
   - `notes_to_tokens()` / `tokens_to_notes()` — direct pipeline

Additional capabilities:
- `validate_roundtrip()` — note-by-note comparison with `RoundtripReport`
- `train_bpe()` — BPE vocabulary training on MIDI corpus
- `save_tokenizer()` / `load_tokenizer()` — persist config + vocabulary
- `TokenizerConfig_` — JSON-serializable config with save/load

### Usage

```python
from melody_generation.tokenizer import (
    notes_to_midi, midi_to_notes, midi_to_tokens,
    validate_roundtrip, train_bpe,
)

# NoteEvent list → MIDI
midi_path = notes_to_midi(notes, "output.mid", bpm=140)

# MIDI → tokens (for ML models)
tokens = midi_to_tokens("output.mid")

# Validate roundtrip fidelity
report = validate_roundtrip("melody.mid")
print(f"Pitch match: {report.pitch_match_ratio:.1%}")

# Train BPE on corpus (after dataset is built)
train_bpe("dataset/tier2/", vocab_size=3000, output_dir="tokenizer/")
```

### Success Criteria

- [x] REMI tokenizer configured with trance-specific parameters
- [x] Bidirectional conversion: NoteEvent ↔ MIDI ↔ Tokens
- [x] Roundtrip validation with detailed report
- [x] BPE training function ready for Phase 2 dataset
- [x] Config serializable as JSON

---

## Step 1.4 — Integrate Melody RNN and Improv RNN ✅ IMPLEMENTED

**Duration:** 3–4 days
**Status:** Complete — implemented in `melody_generation/ml_bridge.py` (`MLMelodyGenerator`)

> **Note:** These models are Phase 1 stepping stones. They will be replaced by fine-tuned midi-model in Phase 2. Their value is proving the hybrid pipeline architecture works before investing in fine-tuning.

### What and Why

Add Google Magenta's Melody RNN (attention) and Improv RNN as melody suggestion engines. Improv RNN generates melodies conditioned on a chord progression, directly addressing the system's current lack of harmonic awareness. These models run on CPU via the Docker-based Magenta service (Step 1.1).

### Implementation

**File:** `projects/ableton-generators/melody_generation/ml_bridge.py`
**Class:** `MLMelodyGenerator`

The `MLMelodyGenerator` class implements a generate-validate-score pipeline:

1. **Generate candidates** — calls `DockerMagenta.generate_melody()` (Improv RNN) to produce N chord-conditioned melody candidates in a single container invocation
2. **Convert to NoteEvent** — uses tokenizer's `midi_to_notes()` to convert each MIDI candidate into the internal NoteEvent format
3. **Validate scale compliance** — computes fraction of notes that fall within the target scale (using `HarmonicEngine.get_scale_intervals()`)
4. **Score with evaluation framework** — runs `evaluate_melody()` on each candidate, producing a composite score
5. **Return best** — `CandidateResult` dataclass with the best candidate, its score, and all scored candidates for logging

Additional capabilities:
- `generate_and_compare()` — generates ML candidates AND rule-based melody, returns both with scores for A/B comparison
- Configurable temperature (default 1.0), num_candidates (default 5)
- Scale compliance threshold (default 0.6) filters out obviously wrong candidates before expensive evaluation

### Usage

```python
from melody_generation.ml_bridge import MLMelodyGenerator

gen = MLMelodyGenerator(key="A", scale="minor", bpm=140)
result = gen.generate(
    chords=["Am", "F", "C", "G"],
    bars=8,
    temperature=1.0,
    num_candidates=5,
)
print(f"Best score: {result.best_score:.3f}")
print(f"Notes: {len(result.best_notes)}")
print(f"Candidates evaluated: {len(result.all_candidates)}")

# A/B comparison with rule engine
comparison = gen.generate_and_compare(
    chords=["Am", "F", "C", "G"], bars=8
)
print(f"ML score: {comparison['ml'].best_score:.3f}")
print(f"Rule score: {comparison['rule'].score:.3f}")
```

### Success Criteria

- [x] Improv RNN integration via DockerMagenta wrapper
- [x] Multi-candidate generation with batch scoring
- [x] Scale compliance validation before evaluation
- [x] Composite score ranking across candidates
- [x] A/B comparison method (ML vs rule-based)
- [x] CandidateResult dataclass with full audit trail

---

## Step 1.5 — Integrate MusicVAE for Motif Variation and Interpolation ✅ IMPLEMENTED

**Duration:** 3–4 days
**Status:** Complete — implemented in `melody_generation/ml_bridge.py` (`MLMotifVariator` + `MotifSimilarityIndex`)

> **Note:** Unlike Melody RNN, MusicVAE is a long-term dependency. Its latent space for motif variation and interpolation has no PyTorch equivalent. It remains in the pipeline even after midi-model replaces Melody RNN for generation.

### What and Why

MusicVAE's latent space directly solves the repetitiveness problem. Instead of repeating the same motif N times, encode it into latent space, sample nearby points, and decode variations that are musically coherent but distinct. Interpolation between two motifs creates smooth transitions.

### Implementation

**File:** `projects/ableton-generators/melody_generation/ml_bridge.py`

#### MLMotifVariator

Wraps MusicVAE encode→perturb→decode pipeline:

- `vary()` — encode motif NoteEvents to MIDI, send to DockerMagenta, convert results back to NoteEvents. Returns `VariationResult` with original + N variants
- `interpolate()` — two motif NoteEvent lists → N interpolation steps as NoteEvent lists
- `sample()` — random sampling from MusicVAE latent space

```python
from melody_generation.ml_bridge import MLMotifVariator

variator = MLMotifVariator(bpm=140)
result = variator.vary(
    motif_notes,           # List[NoteEvent]
    num_variants=4,
    noise_scale=0.3,       # Controls variation intensity
)
for i, variant in enumerate(result.variants):
    print(f"Variant {i}: {len(variant)} notes")

# Interpolation between two motifs
steps = variator.interpolate(motif_a, motif_b, steps=8)
```

#### MotifSimilarityIndex

Context-aware motif retrieval using MusicVAE latent vectors with cosine similarity:

- `add()` / `add_notes()` — encode MIDI files or NoteEvent lists into latent vectors
- `build()` — prepare the index for nearest-neighbor queries
- `find_similar()` / `find_similar_notes()` — retrieve top-K most similar motifs
- `save()` / `load()` — JSON persistence of the index (vectors + metadata)

```python
from melody_generation.ml_bridge import MotifSimilarityIndex

index = MotifSimilarityIndex()
index.add("motif_library/motif_01.mid", {"name": "hook_a", "energy": 0.8})
index.add("motif_library/motif_02.mid", {"name": "hook_b", "energy": 0.5})
index.build()

matches = index.find_similar("query_motif.mid", n=3)
for match in matches:
    print(f"{match.metadata['name']}: similarity={match.similarity:.3f}")

# Persist
index.save("motif_index.json")
loaded = MotifSimilarityIndex.load("motif_index.json")
```

**Noise scale guide for trance:**

| Noise Scale | Effect | Use Case |
|-------------|--------|----------|
| 0.05–0.15 | Micro-variation (timing/ornamentation) | Same phrase repeated with subtle differences |
| 0.2–0.4 | Moderate variation (some pitches change, contour preserved) | Verse → chorus transformation |
| 0.5–0.8 | Major variation (new melody, similar style) | Section contrast |
| >1.0 | Essentially random sampling from style | New material generation |

### Success Criteria

- [x] Encode→perturb→decode pipeline via DockerMagenta
- [x] `MLMotifVariator` with vary(), interpolate(), sample() methods
- [x] `MotifSimilarityIndex` with cosine similarity retrieval
- [x] NoteEvent ↔ MIDI conversion for seamless integration
- [x] `VariationResult` and `SimilarityMatch` dataclasses
- [x] Index persistence (save/load as JSON)
- [ ] Populate index with motif library (blocked on Tier 1 dataset)
- [ ] Tune noise_scale parameters for trance (needs listening tests)

---

## Step 1.6 — Build the Evaluation Framework ✅ IMPLEMENTED

**Duration:** 2–3 days
**Status:** Complete — implemented in `melody_generation/evaluation.py`

### What and Why

Objective measurement before any fine-tuning. Without this, you are flying blind. See [EVALUATION.md](./EVALUATION.md) for the human listening test protocol.

### Implementation

**File:** `projects/ableton-generators/melody_generation/evaluation.py`

**10 core metrics** (from EVALUATION.md specification):

| Metric | Weight | Implementation |
|--------|--------|----------------|
| Pitch entropy | 0.10 | Shannon entropy of pitch distribution |
| Pitch range | 0.05 | Max-min in octaves |
| Chord-tone ratio | 0.20 | Uses NoteEvent.chord_tone annotation or ChordEvent lookup |
| Self-similarity (8-bar) | 0.10 | Cosine similarity of chroma vectors per chunk |
| Self-similarity (16-bar) | 0.05 | Same, 16-bar chunks |
| Stepwise motion ratio | 0.10 | Fraction of intervals ≤ 2 semitones |
| nPVI | 0.05 | Normalized pairwise variability index |
| KL-div vs reference | 0.15 | KL divergence of pitch class histograms |
| Tension correlation | 0.15 | Pearson r against target tension curve |
| Resolution patterns | 0.05 | Count of 7→1, 4→3, 2→1 per 8 bars |

**4 trance-specific metrics:**
- Minor-key adherence (natural + harmonic minor union)
- Phrase regularity (onset alignment to 4/8/16-bar boundaries)
- Hook memorability (first-4-bar chroma vs. later recurrences)
- Register consistency (inverse of pitch std deviation)

**Infrastructure:**
- `MelodyMetrics` — dataclass with all scores + composite
- `ReferenceStats` — aggregate corpus stats with save/load
- `ComparisonReport` — A/B comparison with approximate significance tests
- `evaluate_melody()` — works directly on NoteEvent lists (no MIDI export needed)
- `evaluate_midi()` — works on MIDI files via tokenizer.midi_to_notes()
- `compute_reference_stats()` — builds reference corpus from MIDI files
- `compare_baselines()` — statistical comparison of two metric sets
- `save_baseline()` / `load_baseline()` — JSON persistence
- `print_metrics()` — formatted scorecard output

### Usage

```python
from melody_generation.evaluation import (
    evaluate_melody, compute_reference_stats, compare_baselines, print_metrics,
)

# Evaluate a generated melody (NoteEvent list from LeadGenerator)
metrics = evaluate_melody(notes, key="A", scale="minor", chord_events=chords)
print_metrics(metrics, label="Drop melody")

# Build reference corpus stats
ref = compute_reference_stats(["ref1.mid", "ref2.mid", ...])
ref.save("reference_stats.json")

# Compare phase baselines
report = compare_baselines(phase1_metrics, phase2_metrics)
print(f"Composite improvement: {report.composite_improvement:+.1%}")
```

### Remaining Work

- [ ] Build reference corpus: need 20–50 trance MIDI files (Tier 1 dataset, Phase 2.1)
- [ ] Record rule-only baseline: generate 50 melodies, save metrics
- [ ] Human listening test logistics (documented in EVALUATION.md)

### Success Criteria

- [x] All 10 core metrics implemented with correct weights
- [x] All 4 trance-specific metrics implemented
- [x] Composite score computation with target ranges
- [x] Reference corpus stats computation and persistence
- [x] Baseline comparison with significance testing
- [x] Works on both NoteEvent lists and MIDI files
- [ ] Reference corpus built (blocked on Tier 1 dataset)
- [ ] Rule-only baseline recorded

---

## Step 1.7 — Wire the Complete Hybrid Pipeline (End-to-End)

**Duration:** 3–4 days

### What and Why

Connect all Phase 1 components into a single callable pipeline. After this step, you have a generation pipeline that takes musical parameters as input → generates multiple candidates using both rules and ML → validates and scores all → returns the best as MIDI.

### Tasks

- [ ] Build the full pipeline flow:
  1. Input parameters: key, BPM, chord_progression, energy_curve, bar_count
  2. Rule engine generates structural template
  3. Improv RNN generates 3–5 melody candidates conditioned on chords
  4. MusicVAE creates 2–3 variations of each candidate
  5. music21 filters all candidates against scale/key/interval constraints
  6. Evaluation framework scores survivors
  7. Top candidate output as MIDI
- [ ] Implement candidate ranking: weighted composite score
- [ ] Add logging: all candidates, scores, selection rationale (training signal for later)
- [ ] End-to-end test: generate 50 melodies, compare against reference corpus and rule-only baseline
- [ ] Create CLI: `python generate.py --key Am --bpm 140 --chords "Am F C G" --bars 16`

### Implementation Notes

```python
from pipeline import MelodyPipeline

pipeline = MelodyPipeline(
    magenta_service_url="http://localhost:5050",
    tokenizer_config="tokenizer.json",
    reference_stats="reference_stats.json",
)

result = pipeline.generate(
    key="Am",
    bpm=140,
    chord_progression=["Am", "F", "C", "G"],
    bars=16,
    num_candidates=10,
    temperature=1.0,
    variation_intensity=0.3,
)

print(f"Selected melody: {result.midi_path}")
print(f"Composite score: {result.score:.3f}")
print(f"Candidates evaluated: {result.num_evaluated}")
result.save_log("generation_logs/")
```

### Success Criteria

- Single CLI command generates a trance melody end-to-end
- Generated melodies score higher on composite metric than rule-only baseline
- Pipeline runs in <10 seconds on CPU
- Generation logs capture full candidate evaluation data
- **Phase 1 Gate:** Run human listening test (10 melodies, A/B vs. rule-only). Proceed to Phase 2 if hybrid wins >60% of blind comparisons
