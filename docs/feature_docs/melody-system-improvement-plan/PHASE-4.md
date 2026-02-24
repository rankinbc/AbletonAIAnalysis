# Phase 4: Custom Architecture and Multi-Voice Generation

> **Timeline:** Weeks 15–20 (realistically 20–28)
> **GPU Required:** Yes (24 GB for training)
> **Training Required:** Yes (from scratch + optionally RL)
> **Goal:** Purpose-built models for trance composition with multi-voice coordination
> **Gate:** Only pursue this phase if Phase 2–3 benchmarks reveal persistent quality gaps that fine-tuned off-the-shelf models cannot close.

---

## Step 4.1 — Train a Custom Conditioned Transformer

**Duration:** 7–10 days

### What and Why

Build a small decoder-only Transformer (7–20M parameters) specifically designed for chord-conditioned trance melody generation with built-in tension control. Unlike fine-tuning, this gives full control over architecture, tokenization, conditioning mechanism, and training objective. Small enough to train on a single consumer GPU and run inference on CPU in <2 seconds.

### Tasks

- [ ] **Design architecture:**
  - Decoder-only Transformer (GPT-style)
  - 6–8 layers, 4–8 attention heads, embedding dim 256–512
  - Rotary position embeddings (RoPE)
  - Context length: 2048 tokens (~8 bars with REMI)
  - Target: 7–20M parameters

- [ ] **Design conditioning mechanism:**
  - Prepend conditioning tokens per bar:
    ```
    [KEY=Am] [BPM=140] [TENSION=0.7] [CHORD=Am] [SECTION=build] [BAR]
    Pitch_A4 Duration_8th Velocity_90 Position_0
    ...
    ```
  - Option A (simpler): conditioning tokens in same vocabulary
  - Option B (stronger): separate condition encoder with cross-attention
  - Start with Option A; move to B if conditioning isn't tight enough

- [ ] **Prepare training data:**
  - Full trance dataset tokenized with shared REMI config
  - Add structural tokens: `[BAR]`, `[PHRASE_START]`, `[PHRASE_END]`, `[SECTION=xxx]`
  - Add per-bar conditioning: key, chord, tension (from Step 3.1), BPM

- [ ] **Training:**
  - Loss: cross-entropy next-token prediction
  - Optimizer: AdamW, lr=1e-4, weight_decay=0.01
  - Schedule: cosine annealing with 1000-step warmup
  - Batch size: 32–64
  - Epochs: 50–200 (early stopping patience=10)
  - Hardware: single RTX 3090/4090, 1–7 days

- [ ] **Constrained inference:**
  - Temperature sampling with top-k (50) and top-p (0.95)
  - Scale mask: zero out non-scale pitches
  - Chord-tone boost: multiply chord tone probabilities by 1.5–2.0 on strong beats
  - Tension-guided beam search from Step 3.2

- [ ] **Benchmark:** 100 melodies, compare against Phase 2 models

### Implementation Notes

```python
import torch
import torch.nn as nn

class TranceTransformer(nn.Module):
    def __init__(self, vocab_size=3000, d_model=512, n_heads=8,
                 n_layers=8, max_seq_len=2048, dropout=0.1, n_conditions=32):
        super().__init__()
        self.token_embed = nn.Embedding(vocab_size, d_model)
        self.condition_embed = nn.Embedding(n_conditions, d_model)
        self.pos_embed = RotaryPositionalEmbedding(d_model, max_seq_len)
        self.layers = nn.ModuleList([
            TransformerDecoderLayer(d_model=d_model, nhead=n_heads,
                                   dim_feedforward=d_model * 4,
                                   dropout=dropout, batch_first=True)
            for _ in range(n_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size)

    @torch.no_grad()
    def generate(self, conditions, max_tokens=512, temperature=0.9,
                 top_k=50, scale_mask=None, chord_tone_boost=None):
        tokens = conditions.clone()
        for _ in range(max_tokens):
            logits = self.forward(tokens[:, -self.max_seq_len:])
            logits = logits[:, -1, :] / temperature
            if scale_mask is not None:
                logits[:, scale_mask == 0] = float('-inf')
            if chord_tone_boost is not None:
                logits[:, chord_tone_boost] += 0.5
            top_k_logits, top_k_indices = logits.topk(top_k)
            probs = torch.softmax(top_k_logits, dim=-1)
            next_token = top_k_indices.gather(-1, torch.multinomial(probs, 1))
            tokens = torch.cat([tokens, next_token], dim=-1)
            if next_token.item() == self.eos_token:
                break
        return tokens
```

**Model size options:**

| Config | Layers | Heads | d_model | Params | Training (4090) | CPU Inference |
|--------|--------|-------|---------|--------|-----------------|---------------|
| Tiny | 4 | 4 | 256 | ~1M | 4–8 hours | <0.5 sec |
| Small | 6 | 4 | 384 | ~7M | 1–2 days | <1 sec |
| Medium | 8 | 8 | 512 | ~20M | 3–7 days | 1–2 sec |

Start with Small (7M). Only scale up if quality plateaus.

### Success Criteria

- Training loss converges without overfitting
- Conditioning works: `[TENSION=0.2]` vs `[TENSION=0.9]` produces audibly different output
- Chord compliance >90%
- Tension correlation >0.5
- CPU inference <3 seconds for 16 bars
- Composite score exceeds best Phase 2 model

---

## Step 4.2 — Multi-Voice Generation: Accompaniment from Lead Melody

**Duration:** 5–7 days

### What and Why

Given a generated lead melody, automatically generate complementary bass lines, arps, and pad voicings. Each new voice is conditioned on all previously generated voices, replacing the current independent-generation-then-fix-collisions approach.

### Tasks

- [ ] **Prepare multi-track training data:**
  - Separate tracks into roles: lead, bass, arp, pad
  - Create paired examples: (lead, bass), (lead, arp), etc.
  - Minimum 200 multi-track examples (augmented to 2,000+)

- [ ] **Approach A — DeepBach-style constrainable generation (recommended):**
  - Adapt bidirectional LSTM for 4 voices (lead, bass, arp, pad)
  - Fix the lead voice (from Step 4.1), generate others via Gibbs sampling
  - Gibbs sampling naturally resolves collisions
  - Training: T4 or better, 6–12 hours

- [ ] **Approach B — Anticipatory Music Transformer infilling:**
  - Provide lead as fixed context
  - Use infilling capability for accompaniment
  - Pre-trained on Lakh MIDI (multi-track), may need less fine-tuning

- [ ] **Voice leading optimization (post-processing):**
  - Tymoczko's minimal voice leading for pad chord transitions
  - Hungarian algorithm on cost matrix of voice movements
  ```python
  from scipy.optimize import linear_sum_assignment

  def optimal_voice_leading(chord_a_pitches, chord_b_pitches):
      candidates = generate_voicings(chord_b_pitches,
                  center=sum(chord_a_pitches) // len(chord_a_pitches), spread=12)
      best_voicing, best_cost = None, float('inf')
      for voicing in candidates:
          n = len(chord_a_pitches)
          cost = np.zeros((n, n))
          for i in range(n):
              for j in range(n):
                  cost[i][j] = abs(chord_a_pitches[i] - voicing[j])
          row_ind, col_ind = linear_sum_assignment(cost)
          total = cost[row_ind, col_ind].sum()
          if total < best_cost:
              best_cost = total
              best_voicing = [voicing[j] for j in col_ind]
      return best_voicing
  ```

- [ ] **Rhythmic interlock validation:**
  - Lead and bass should not play simultaneous 16th notes
  - Arp fills rhythmic gaps left by lead
  - Pad holds don't change during lead phrases
  - Post-process: shift colliding notes by 1 grid position

### Success Criteria

- Bass lines harmonically complement lead (>85% chord/scale tones)
- Arp fills rhythmic gaps without collisions
- Pad uses smooth voice leading (<3 semitones average movement per chord change)
- No simultaneous 16th-note collisions between lead and bass
- Multi-voice output sounds like a coherent arrangement

---

## Step 4.3 — RL-Based Music Theory Enforcement (Gated)

**Duration:** 5–7 days

> **GATE:** Only pursue this step if rejection sampling (Step 3.2b) with N=50 candidates cannot achieve >95% theory compliance AND >0.5 tension correlation. If those thresholds are met, skip this step entirely.

### What and Why

Apply reinforcement learning to fine-tune the custom Transformer, using music theory reward functions. RL teaches the model to internalize rules rather than relying on post-filtering. The key challenge is balancing compliance with novelty.

### Tasks

- [ ] **Define reward functions:**

  | Rule | Reward | Penalty |
  |------|--------|---------|
  | In-scale note | +1.0 | -0.5 out-of-scale |
  | Chord tone on strong beat | +0.3 | — |
  | Stepwise motion (≤M2) | +0.1 | -0.1 for leaps >P5 |
  | Resolution: 7→1, 4→3, 2→1 | +0.5 | — |
  | Phrase repetition at 8 bars | +0.3 | — |
  | Excessive repetition (>4 same) | — | -0.3 |
  | Register C4–C6 | +0.05 | -0.2 outside |
  | Tension matches curve | +0.4 × correlation | — |

- [ ] **Implement RL-Tuner:**
  - Base policy: custom Transformer (frozen)
  - Q-network adjusts token probabilities
  - KL penalty: `total_reward = rule_reward - λ_KL * KL(π_RL || π_base)`
  - Training: 50–100K episodes, 12–24 hours on T4

- [ ] **Monitor for collapse:**

  | Metric | Healthy | Red Flag |
  |--------|---------|----------|
  | Pitch entropy | 2.5–3.2 bits | <2.0 (diversity collapse) |
  | Scale compliance | 90–98% | >99% (over-constrained) |
  | KL divergence | 0.1–1.0 | >2.0 (diverging) |

- [ ] **Calibrate reward weights:** Expect 3–5 calibration runs minimum

### Success Criteria

- Scale compliance 80% → 95%
- Pitch entropy stays >2.5 bits
- Tension correlation improves ≥0.1 over base model
- Chord-tone ratio on strong beats >90%
- Melodies sound tighter without sounding mechanical

---

## Step 4.4 — Full System Integration and Production Hardening

**Duration:** 3–5 days

### What and Why

Assemble everything into a production-grade system with clean API, model versioning, fallback mechanisms, and comprehensive logging.

### Tasks

- [ ] **Unified API:**
  ```python
  from melody_engine import MelodyEngine

  engine = MelodyEngine(config="production.yaml")

  result = engine.generate(
      key="Am", bpm=140,
      chord_progression=["Am", "F", "C", "G"],
      structure=[
          {"section": "build", "bars": 16},
          {"section": "drop", "bars": 32},
      ],
      tension_curve="auto",
      variation_level=0.3,
      humanization_intensity=0.5,
      model_backend="auto",
      accompaniment=True,
      num_candidates=10,
  )

  result.save_midi("output/")
  result.save_combined("output/combined.mid")
  result.print_scorecard()
  ```

- [ ] **Model fallback chain:**
  1. Custom Transformer (RL-tuned if applicable) — primary
  2. SkyTNT midi-model (fine-tuned, ONNX) — secondary
  3. MusicVAE (generation mode) — tertiary
  4. Rule-based engine — guaranteed fallback
  - Auto-fallback if scale compliance <70%

- [ ] **ONNX export and optimization:**
  - `torch.onnx.export()` + INT8 dynamic quantization
  - Target <5 seconds total latency for 16-bar lead + accompaniment

- [ ] **Comprehensive evaluation:**
  - 200 melodies across all section types
  - Full metric comparison against all prior phases
  - Final human listening test

- [ ] **Production hardening:**
  - Model versioning with training metadata
  - Rollback capability
  - Generation logging (params, model, scores, timing)
  - YAML config — no hardcoded values

### Implementation Notes

```yaml
# production.yaml
models:
  primary:
    type: custom_transformer
    checkpoint: models/trance_transformer_v3.onnx
    quantization: int8
    max_latency_ms: 3000
  secondary:
    type: midi_model
    checkpoint: models/midi_model_trance_lora.onnx
    quantization: int8
    max_latency_ms: 5000
  variation:   # MusicVAE stays for variation/interpolation
    type: musicvae
    checkpoint: models/musicvae_trance/
    env: magenta-env
    service_url: http://localhost:5050
  fallback:
    type: rule_based
    config: rules/trance_v2.yaml
```

**Latency budget (target <5 seconds):**
```
Structure planning:     ~50ms
Tension curve:          ~20ms
Lead melody (ONNX):    ~1500ms
Bass line:              ~800ms
Arp pattern:            ~800ms
Pad voicing:            ~200ms (algorithmic)
Voice leading opt:      ~50ms
Humanization:           ~30ms
Validation:             ~100ms
MIDI export:            ~50ms
────────────────────────────────
Total:                  ~3600ms
```

### Success Criteria

- Single API call generates complete multi-voice trance arrangement
- Total latency <5 seconds on CPU
- Fallback chain works (sabotage primary → secondary takes over)
- 200-melody evaluation shows significant improvement over Phase 3
- All runs logged with full parameter and metric capture
- 100 consecutive generations without crashes

---

## Post-Phase 4: Ongoing Improvement

Once Phase 4 is complete, further improvements shift from architecture to data:

- **Expand training data continuously.** Good generations can be added to training set (human-in-the-loop)
- **Genre variant LoRA adapters:** psytrance, progressive, uplifting, tech trance. Same base model, different adapters swapped at inference
- **User feedback loop:** Log kept vs. discarded generations as preference signal
- **Model scouting:** At each phase boundary, check if newer open-source models have emerged that outperform current choices (Anticipatory Music Transformer, ChatMusician, etc.)
- **PyTorch VAE replacement:** If a PyTorch VAE with MusicVAE-equivalent latent space emerges, drop the Magenta dependency entirely
