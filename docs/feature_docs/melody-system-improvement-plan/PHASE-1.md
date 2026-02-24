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

## Step 1.3 — Integrate MidiTok for REMI Tokenization

**Duration:** 1–2 days

### What and Why

Add MidiTok as the standard tokenization layer between MIDI files and any ML model. Configure REMI tokenization — it encodes metrical structure (Bar, Position) explicitly, which is critical for trance's rigid 4/4 meter. This is foundation work for every ML step that follows.

### Tasks

- [ ] Install MidiTok and configure REMI tokenizer with trance-appropriate parameters
- [ ] Build bidirectional MIDI↔token conversion pipeline with roundtrip validation
- [ ] Apply BPE on top of REMI with vocabulary size 1000–5000
- [ ] Create a shared tokenization config file used across all subsequent training and inference steps
- [ ] Test roundtrip fidelity on 10–20 sample trance MIDI files

### Implementation Notes

```python
from miditok import REMI, TokenizerConfig
from pathlib import Path

config = TokenizerConfig(
    num_velocities=32,
    use_chords=True,
    use_programs=False,        # monophonic lead melody
    use_tempos=True,
    use_time_signatures=True,
    beat_res={(0, 4): 4},      # 16th note resolution
    tempo_range=(130, 150),    # trance BPM range
    num_tempos=10,
)
tokenizer = REMI(config)

# Tokenize, decode, validate roundtrip
tokens = tokenizer(Path("melody.mid"))
midi = tokenizer.decode(tokens)
midi.dump_midi(Path("roundtrip.mid"))

# BPE on top
tokenizer.learn_bpe(
    vocab_size=3000,
    files_paths=list(Path("dataset/").glob("*.mid")),
)
tokenizer.save(Path("tokenizer.json"))
```

### Success Criteria

- REMI tokenizer encodes and decodes trance MIDI without loss
- BPE vocabulary trained on sample files
- Tokenization config saved as shareable JSON

---

## Step 1.4 — Integrate Melody RNN and Improv RNN

**Duration:** 3–4 days

> **Note:** These models are Phase 1 stepping stones. They will be replaced by fine-tuned midi-model in Phase 2. Their value is proving the hybrid pipeline architecture works before investing in fine-tuning.

### What and Why

Add Google Magenta's Melody RNN (attention) and Improv RNN as melody suggestion engines. Improv RNN generates melodies conditioned on a chord progression, directly addressing the system's current lack of harmonic awareness. These models run on CPU in under 1 second per melody via the persistent Magenta service.

### Tasks

- [ ] Download pre-trained bundles: `attention_rnn.mag`, `chord_pitches_improv.mag`
- [ ] Add Improv RNN endpoint to the Magenta service (Step 1.1)
- [ ] Wire into the main pipeline: rule engine generates chord progression → Improv RNN generates melody candidates → music21 validates → best candidate proceeds
- [ ] Tune generation parameters: temperature (0.8–1.2 for trance), beam size, steps per chord
- [ ] Test with standard trance progressions (Am–F–C–G, Am–Dm–Em–Am, etc.)

### Implementation Notes

Validation layer in the main pipeline:
```python
from music21 import converter, scale, pitch

def validate_melody(midi_path, key_name, scale_type='minor'):
    score = converter.parse(midi_path)
    target_scale = scale.MinorScale(key_name)

    violations = []
    total_notes = 0
    for note in score.flatten().notes:
        total_notes += 1
        degree = target_scale.getScaleDegreeFromPitch(note.pitch)
        if degree is None:
            violations.append(note)

    compliance = (total_notes - len(violations)) / total_notes
    return compliance, violations
```

### Success Criteria

- Improv RNN generates melodies conditioned on Am–F–C–G at 140 BPM
- Generated melodies pass music21 validation with >75% scale compliance (pre-filtering)
- End-to-end latency <1 second via persistent service
- Temperature parameter visibly affects output character

---

## Step 1.5 — Integrate MusicVAE for Motif Variation and Interpolation

**Duration:** 3–4 days

> **Note:** Unlike Melody RNN, MusicVAE is a long-term dependency. Its latent space for motif variation and interpolation has no PyTorch equivalent. It remains in the pipeline even after midi-model replaces Melody RNN for generation.

### What and Why

MusicVAE's latent space directly solves the repetitiveness problem. Instead of repeating the same motif N times, encode it into latent space, sample nearby points, and decode variations that are musically coherent but distinct. Interpolation between two motifs creates smooth transitions.

### Tasks

- [ ] Download `mel_16bar_flat` checkpoint (~200 MB) and `mel_2bar_small` for short motifs
- [ ] Add MusicVAE endpoints to the Magenta service (encode, decode, vary, interpolate)
- [ ] Build encode→perturb→decode pipeline: motif → latent z → add noise → decode variation
- [ ] Build interpolation pipeline: motif A → motif B → N intermediates
- [ ] **Build motif similarity index:** Encode the entire motif library (and later the training corpus) into MusicVAE latent vectors. Use nearest-neighbor retrieval (cosine similarity) to find seed motifs that are similar to a given harmonic/energy context. This replaces random motif selection with context-aware retrieval
- [ ] Create a motif variation API: `vary(midi, num_variants, variation_intensity)`

### Implementation Notes

```python
# MusicVAE service endpoints
def vary_motif(input_midi_path, num_variants=4, noise_scale=0.3):
    ns = note_seq.midi_file_to_note_sequence(input_midi_path)
    z, mu, sigma = model.encode([ns])

    variants = []
    for _ in range(num_variants):
        z_perturbed = z + np.random.normal(0, noise_scale, z.shape)
        decoded = model.decode(z_perturbed, length=256)
        variants.append(decoded[0])
    return variants

def interpolate_motifs(midi_a_path, midi_b_path, steps=8):
    ns_a = note_seq.midi_file_to_note_sequence(midi_a_path)
    ns_b = note_seq.midi_file_to_note_sequence(midi_b_path)
    return model.interpolate(ns_a, ns_b, num_steps=steps)
```

**Motif similarity index:**
```python
import numpy as np
from sklearn.neighbors import NearestNeighbors

class MotifIndex:
    """Context-aware motif retrieval using MusicVAE latent vectors."""

    def __init__(self, musicvae_model):
        self.model = musicvae_model
        self.vectors = []
        self.metadata = []

    def add_motif(self, midi_path, metadata):
        ns = note_seq.midi_file_to_note_sequence(midi_path)
        z, _, _ = self.model.encode([ns])
        self.vectors.append(z.flatten())
        self.metadata.append(metadata)

    def build_index(self):
        self.nn = NearestNeighbors(n_neighbors=5, metric='cosine')
        self.nn.fit(np.array(self.vectors))

    def find_similar(self, query_midi, n=5):
        ns = note_seq.midi_file_to_note_sequence(query_midi)
        z, _, _ = self.model.encode([ns])
        distances, indices = self.nn.kneighbors(z.reshape(1, -1), n)
        return [(self.metadata[i], distances[0][j])
                for j, i in enumerate(indices[0])]
```

**Noise scale guide for trance:**

| Noise Scale | Effect | Use Case |
|-------------|--------|----------|
| 0.05–0.15 | Micro-variation (timing/ornamentation) | Same phrase repeated with subtle differences |
| 0.2–0.4 | Moderate variation (some pitches change, contour preserved) | Verse → chorus transformation |
| 0.5–0.8 | Major variation (new melody, similar style) | Section contrast |
| >1.0 | Essentially random sampling from style | New material generation |

### Success Criteria

- Encode→decode roundtrip produces recognizable melody (noise_scale=0)
- Variants at noise_scale=0.2 are audibly different but related
- Interpolation produces 8 musically valid intermediates
- Motif similarity index returns contextually appropriate seed motifs
- All outputs pass music21 scale validation

---

## Step 1.6 — Build the Evaluation Framework

**Duration:** 2–3 days

### What and Why

Establish objective measurement before any fine-tuning. This lets you prove (or disprove) that each change improves output quality. Without this, you are flying blind. See [EVALUATION.md](./EVALUATION.md) for the complete evaluation protocol including human listening tests.

### Tasks

- [ ] Install MusPy and implement per-melody scoring: pitch entropy, pitch class histogram, rhythmic complexity (nPVI), empty-beat ratio, polyphony ratio
- [ ] Implement trance-specific metrics (see table below)
- [ ] Create a reference corpus: select 20–50 trance MIDI files and compute all metrics to establish target distributions
- [ ] Build automated A/B comparison script: generated MIDI vs. reference corpus → scorecard
- [ ] Store baseline metrics from the current rule-only system
- [ ] **Set up human listening test protocol** (see [EVALUATION.md](./EVALUATION.md))

**Target metric ranges for trance melodies:**

| Metric | Target Range | Why |
|--------|-------------|-----|
| Pitch entropy | 2.5–3.0 bits | Focused pitch content in minor keys |
| Pitch range | 1.5–2.5 octaves | Centered C4–C6 for lead synths |
| Chord-tone ratio | >80% | Trance heavily emphasizes chord tones |
| Self-similarity (8-bar) | >0.6 | Trance is highly repetitive |
| Self-similarity (16-bar) | >0.4 | Section-level repetition |
| Stepwise motion ratio | >60% | Trance favors conjunct motion |
| nPVI | 30–60 | Structured but not mechanical |

### Implementation Notes

```python
import muspy
import numpy as np

def evaluate_melody(midi_path, reference_stats):
    music = muspy.read_midi(midi_path)
    scores = {}

    scores['pitch_entropy'] = muspy.pitch_entropy(music)
    scores['npvi'] = compute_npvi(music)
    scores['self_similarity_8bar'] = compute_self_similarity(music, bars=8)
    scores['chord_tone_ratio'] = compute_chord_tone_ratio(midi_path)

    pitches = [n.pitch for track in music.tracks for n in track.notes]
    if pitches:
        scores['pitch_range_octaves'] = (max(pitches) - min(pitches)) / 12

    scores['kl_vs_reference'] = kl_divergence(
        muspy.pitch_class_entropy(music), reference_stats['pc_hist'])

    scores['composite'] = weighted_composite(scores, reference_stats)
    return scores
```

### Success Criteria

- All metrics compute correctly on reference corpus
- Reference corpus statistics stored as JSON baseline
- Current rule-only system baselined (scores recorded)
- Human listening test protocol documented and ready to run

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
