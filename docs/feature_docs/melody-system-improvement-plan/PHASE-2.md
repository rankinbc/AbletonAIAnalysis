# Phase 2: Data Pipeline and Genre Fine-Tuning

> **Timeline:** Weeks 5–8 (realistically 5–7 weeks)
> **GPU Required:** Yes (T4 minimum, A10 for midi-model)
> **Training Required:** Yes (fine-tuning only, no training from scratch)
> **Goal:** Genre-authentic trance output from fine-tuned models, measurably closer to reference corpus than generic pre-trained models

---

## Step 2.1 — Build the Trance MIDI Training Dataset (Tiered)

**Duration:** 5–7 days

### What and Why

No large-scale dedicated trance MIDI dataset exists. This is the bottleneck for all fine-tuning work. The strategy uses a tiered dataset approach where data quality and data quantity serve different roles. See [DATASET-STRATEGY.md](./DATASET-STRATEGY.md) for the full rationale.

### Tasks

- [ ] **Tier 1 — Gold Standard (50–100 files):**
  - Hand-transcribe or manually verify 50–100 iconic trance melodies
  - Sources: personal transcription, verified MIDI archives, community contributions
  - Every file inspected in a DAW piano roll for accuracy
  - Used for: final fine-tuning, evaluation reference, human listening test comparisons
  - Store separately in `dataset/tier1/`

- [ ] **Tier 2 — Verified Extraction (300–500 files):**
  - Apply Demucs source separation to isolate lead synth from reference tracks
  - Apply Basic Pitch to transcribe isolated melodies to MIDI
  - Manual spot-check: listen to every 5th file, reject batch if >30% have obvious errors
  - Validate each extraction with music21 (reject if >30% out-of-key notes)
  - Process 200+ reference tracks, expect 60–70% yield
  - Used for: main training corpus
  - Store in `dataset/tier2/`

- [ ] **Tier 3 — Bulk + Augmented (1,000+ files):**
  - GigaMIDI filtering: download from HuggingFace, filter by electronic genre tags, 130–150 BPM, monophonic/lead tracks. Expected yield: 200–500 files
  - Synthetic generation from Phase 1 pipeline (200–500 melodies with parameter variation). Label as synthetic in metadata
  - Data augmentation on ALL tiers:
    - 12-key transposition (x12)
    - Tempo scaling ±10% (x3–5)
    - Velocity perturbation ±10 MIDI units
    - Octave shift (±1 octave where range permits)
  - Used for: pre-training, general pattern exposure
  - Store in `dataset/tier3/`

- [ ] **Quality filtering pipeline:**
  - music21: reject outside target key/tempo range, excessive polyphony, range outside 1–3 octaves
  - MidiTok: tokenize all surviving files, verify REMI roundtrip integrity
  - Manual spot-check: listen to 20–30 random samples per tier

- [ ] **Dataset split:** 80% train / 10% validation / 10% test (stratified by tier)

- [ ] **Convert to training formats:**
  - Magenta NoteSequences (TFRecord) for Melody RNN / MusicVAE
  - REMI token sequences (JSON/binary) for midi-model and custom Transformer
  - Metadata JSON per file: source, tier, original key, BPM, augmentation applied

### Prerequisites

- [ ] Phase 1 complete (hybrid pipeline operational for Tier 3 synthetic generation)
- [ ] MidiTok REMI tokenizer configured (Step 1.3)
- [ ] Demucs installed (`pip install demucs`, MIT license)
- [ ] Basic Pitch installed (`pip install basic-pitch`, Apache 2.0)
- [ ] Reference track audio library accessible (50–200 trance tracks)
- [ ] HuggingFace CLI configured for GigaMIDI download
- [ ] Storage: ~200 GB for raw dataset + processed output

### Implementation Notes

```python
# Audio-to-MIDI extraction pipeline (Tier 2)
from basic_pitch.inference import predict
from pathlib import Path
import subprocess

def extract_melody_from_audio(audio_path, output_dir):
    """Demucs separation → Basic Pitch transcription → validation"""

    # Step 1: Source separation with Demucs
    subprocess.run([
        "python", "-m", "demucs",
        "--two-stems", "vocals",
        "-o", str(output_dir / "separated"),
        str(audio_path)
    ], check=True)

    stem_path = output_dir / "separated" / "htdemucs" / audio_path.stem / "other.wav"

    # Step 2: Transcribe to MIDI with Basic Pitch
    model_output, midi_data, note_events = predict(str(stem_path))
    midi_path = output_dir / f"{audio_path.stem}_melody.mid"
    midi_data.write(str(midi_path))

    # Step 3: Validate with music21
    from music21 import converter
    score = converter.parse(str(midi_path))
    key = score.analyze('key')

    return midi_path, key
```

**Expected dataset sizes:**

| Source | Raw Files | Post-Filter | Post-Augment | Tier |
|--------|-----------|-------------|--------------|------|
| Hand-transcribed | 50–100 | 50–100 | 600–1,200 | Tier 1 |
| Audio extraction | 200+ | 120–350 | 1,440–4,200 | Tier 2 |
| GigaMIDI filtered | ~1,000 | 200–500 | 2,400–6,000 | Tier 3 |
| Synthetic (Phase 1) | 200–500 | 180–450 | 2,160–5,400 | Tier 3 |
| **Total** | | **550–1,400** | **6,600–16,800** |  |

### Success Criteria

- Minimum 50 Tier 1 files (hand-verified, gold standard)
- Minimum 300 Tier 2 files (auto-extracted, spot-checked)
- Minimum 500 Tier 3 files pre-augmentation
- All files pass MidiTok REMI roundtrip validation
- All files converted to both NoteSequence and REMI token formats
- Reference corpus metrics show training set distribution is similar to reference

---

## Step 2.2 — Fine-Tune Melody RNN (Attention) on Trance Data

**Duration:** 2–3 days

> **Note:** This is a short-term model. It will be replaced by midi-model once 2.4 is complete. Its primary value is as a quick benchmark to validate the fine-tuning pipeline.

### What and Why

Magenta's Melody RNN has the simplest fine-tuning pipeline in the ecosystem and trains fast. This is the lowest-risk fine-tuning step. Expected improvement: 30–50% increase in genre-appropriateness.

### Tasks

- [ ] Convert trance dataset (Tiers 2+3) to NoteSequences
- [ ] Create TFRecord files with `melody_rnn_create_dataset`
- [ ] Fine-tune from `attention_rnn` checkpoint:
  - Learning rate: 0.001 with decay
  - Batch size: 64
  - Steps: 10,000–20,000 (validation loss early stopping)
- [ ] Generate 50 melodies from fine-tuned model and 50 from pre-trained baseline
- [ ] Compare scorecard metrics
- [ ] Export fine-tuned bundle

### Implementation Notes

```bash
# In magenta-env
python -m magenta.scripts.convert_dir_to_note_sequences \
  --input_dir=dataset/tier2/ --input_dir=dataset/tier3/ \
  --output_file=dataset/notesequences.tfrecord --recursive

python -m magenta.models.melody_rnn.melody_rnn_create_dataset \
  --config=attention_rnn \
  --input=dataset/notesequences.tfrecord \
  --output_dir=dataset/melody_rnn/ --eval_ratio=0.1

python -m magenta.models.melody_rnn.melody_rnn_train \
  --config=attention_rnn \
  --run_dir=training/melody_rnn_trance/ \
  --sequence_example_file=dataset/melody_rnn/training_melodies.tfrecord \
  --hparams="batch_size=64,rnn_layer_sizes=[128,128]" \
  --num_training_steps=20000
```

### Success Criteria

- Validation loss decreases and plateaus (no overfitting)
- Chord-tone ratio improves ≥10pp vs. pre-trained baseline
- Pitch class histogram resembles minor-key distribution
- Self-similarity at 8-bar intervals increases

---

## Step 2.3 — Fine-Tune MusicVAE (16-bar Melody) on Trance Data

**Duration:** 2–3 days

> **Note:** Unlike Melody RNN, MusicVAE is a long-term dependency. Fine-tuning creates a trance-specific latent space where sampling and interpolation inherently produce genre-appropriate results.

### What and Why

Fine-tuning MusicVAE creates a trance-specific latent space. After this, sampling from the latent space inherently produces trance-like melodies, and every motif variation it produces will be genre-native. The motif similarity index (Step 1.5) also improves because the latent vectors become genre-meaningful.

### Tasks

- [ ] Prepare 16-bar melody segments from trance dataset (trim/pad to 256 steps at 16th-note resolution)
- [ ] Fine-tune from `mel_16bar_flat` checkpoint:
  - Learning rate: 0.0001
  - KL weight: anneal 0.0 → 0.1 over first 5,000 steps
  - Batch size: 32
  - Steps: 10,000–15,000
- [ ] Validate latent space: sample 100 random points, decode, score
- [ ] Test interpolation: two known-good trance melodies, 10 intermediates
- [ ] Compare variation quality: same motif varied with pre-trained vs. fine-tuned

### Implementation Notes

```bash
python -m magenta.models.music_vae.music_vae_train \
  --config=cat-mel_16bar_big_q2 \
  --run_dir=training/musicvae_trance/ \
  --mode=train \
  --examples_path=dataset/musicvae/training.tfrecord \
  --hparams="batch_size=32,learning_rate=0.0001,free_bits=256,max_beta=0.1" \
  --num_steps=15000
```

**Latent space validation:**
```python
# Random sampling — should produce trance-like melodies
samples = model.sample(n=100, length=256, temperature=0.5)

# Reconstruction test
z, _, _ = model.encode([original])
reconstructed = model.decode(z, length=256)
```

### Success Criteria

- Random samples from latent space sound recognizably trance (minor key, stepwise, appropriate range)
- Interpolation produces smooth transitions without garbage intermediates
- Motif variation at noise_scale=0.2 produces genre-appropriate variants
- Reconstruction loss is low: encode→decode preserves melody identity
- Motif similarity index returns more contextually relevant results

---

## Step 2.4 — Integrate SkyTNT midi-model with LoRA Fine-Tuning

**Duration:** 4–5 days

> **Note:** This becomes the primary generation engine long-term, replacing Melody RNN / Improv RNN.

### What and Why

SkyTNT/midi-model is a 200M-parameter Transformer with the highest-quality multi-track MIDI generation among open-source models. It has proven LoRA fine-tuning paths and ONNX export for fast CPU inference. This is the long-term bet — PyTorch ecosystem, actively maintained, actively developed.

### Tasks

- [ ] Download base model from HuggingFace (`skytnt/midi-model`, ~800 MB)
- [ ] Prepare trance dataset in native tokenization format
- [ ] Configure LoRA fine-tuning:
  - LoRA rank: 16–32
  - Target modules: attention query/value projections
  - Learning rate: 2e-4
  - QLoRA (4-bit quantization during training) for 24 GB VRAM
  - Steps: 5,000–10,000
- [ ] Export to ONNX with KV-cache optimization
- [ ] Benchmark CPU inference: target <5 seconds for 16-bar melody
- [ ] Apply INT8 dynamic quantization if needed
- [ ] A/B test against fine-tuned Melody RNN and MusicVAE

### Implementation Notes

```python
from peft import LoraConfig, get_peft_model, TaskType
from transformers import AutoModelForCausalLM, TrainingArguments, Trainer

model = AutoModelForCausalLM.from_pretrained(
    "skytnt/midi-model", load_in_4bit=True, device_map="auto")

lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM, r=16, lora_alpha=32,
    target_modules=["q_proj", "v_proj"], lora_dropout=0.05,
)
model = get_peft_model(model, lora_config)
# Expected: ~2% of total parameters trainable

training_args = TrainingArguments(
    output_dir="training/midi_model_trance_lora",
    per_device_train_batch_size=4,
    gradient_accumulation_steps=8,
    num_train_epochs=5,
    learning_rate=2e-4,
    warmup_steps=500,
    fp16=True,
)
Trainer(model=model, args=training_args, train_dataset=trance_dataset).train()
```

```bash
# ONNX export + quantization
python app_onnx.py --export --model-path training/midi_model_trance_lora/
python -c "
from onnxruntime.quantization import quantize_dynamic, QuantType
quantize_dynamic('model.onnx', 'model_int8.onnx', weight_type=QuantType.QInt8)
"
```

### Success Criteria

- LoRA fine-tuning completes without OOM on 24 GB GPU
- ONNX export produces working model with KV-cache
- CPU inference <5 seconds for 16-bar melody
- Generated melodies score higher than fine-tuned Melody RNN on composite metric
- Melodies recognizably in trance style

---

## Step 2.5 — Update Pipeline with Fine-Tuned Models and Benchmark

**Duration:** 2–3 days

### What and Why

Swap pre-trained models for fine-tuned versions. Run comprehensive evaluation to determine the default generator. This is the moment of truth.

### Tasks

- [ ] Swap Melody RNN / Improv RNN to fine-tuned versions
- [ ] Swap MusicVAE to fine-tuned version
- [ ] Add midi-model (ONNX) as primary generation backend
- [ ] Generate 100 melodies from each of 4 configurations:
  1. Rule-only baseline (Phase 0)
  2. Phase 1 hybrid (pre-trained ML)
  3. Phase 2 hybrid (fine-tuned ML)
  4. midi-model standalone
- [ ] Score all 400 melodies with evaluation framework
- [ ] Run statistical significance tests (Wilcoxon signed-rank)
- [ ] **Run human listening test** (see [EVALUATION.md](./EVALUATION.md))
- [ ] Select best model as default; drop Melody RNN / Improv RNN if midi-model wins
- [ ] Document findings in benchmark report

### Implementation Notes

```python
configs = {
    'rule_only': {'model_backend': 'rules'},
    'phase1_pretrained': {'model_backend': 'improv_rnn', 'checkpoint': 'pretrained'},
    'phase2_finetuned': {'model_backend': 'improv_rnn', 'checkpoint': 'finetuned'},
    'midi_model': {'model_backend': 'midi_model_onnx'},
}

results = {}
for name, config in configs.items():
    pipeline = MelodyPipeline(**config)
    melodies = [pipeline.generate(
        key="Am", bpm=140,
        chord_progression=["Am", "F", "C", "G"], bars=16
    ) for _ in range(100)]
    results[name] = benchmark(melodies, reference_corpus)

# Statistical comparison
for pair in [('rule_only', 'phase2_finetuned'),
             ('phase1_pretrained', 'phase2_finetuned'),
             ('phase2_finetuned', 'midi_model')]:
    p_value = statistical_tests(results[pair[0]], results[pair[1]])
    print(f"{pair[0]} vs {pair[1]}: p={p_value:.4f}")
```

**Expected outcome table (fill with actual values):**

| Metric | Rule-Only | Phase 1 | Phase 2 | midi-model |
|--------|-----------|---------|---------|------------|
| Pitch entropy | ___ | ___ | ___ | ___ |
| Chord-tone ratio | ___ | ___ | ___ | ___ |
| Self-similarity (8-bar) | ___ | ___ | ___ | ___ |
| KL-div vs reference | ___ | ___ | ___ | ___ |
| Composite score | ___ | ___ | ___ | ___ |
| Human preference (%) | ___ | ___ | ___ | ___ |

### Phase 2 Gate Decision

- **If best model achieves >90% of reference corpus quality AND wins >70% of human listening comparisons:** Declare production-ready. Phase 3–4 are optional improvements.
- **If quality gaps remain:** Proceed to Phase 3. Document specific gaps to target.
- **Model retirement:** If midi-model outperforms Melody RNN on all metrics, remove Melody RNN / Improv RNN from the pipeline. Keep MusicVAE regardless (different role: variation, not generation).
