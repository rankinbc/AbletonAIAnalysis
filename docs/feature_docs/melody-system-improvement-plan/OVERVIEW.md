# ML-Enhanced Melody Generation — Implementation Roadmap

> **System:** Python rule-based MIDI generator → Hybrid AI compositional system
> **Genre:** Trance, 138–145 BPM
> **Output:** MIDI for Ableton Live
> **Realistic Timeline:** ~24–28 weeks across 4 phases (aspirational: 16–20)
> **Current Status:** Phase 1 code complete. Operational tasks (Docker build, reference data collection, listening test) remain before Phase 2.

---

## Guiding Principle

The existing rule engine is never discarded. Each phase wraps it with increasingly capable ML components — from off-the-shelf pre-trained models to fine-tuned genre-specific networks to custom architectures. At every stage, the rule engine serves as a constraint layer ensuring musical validity.

---

## Phase Overview

| Phase | Focus | Timeline | Key Outcome | Status | Detail File |
|-------|-------|----------|-------------|--------|-------------|
| **1** | Foundation + Quick Wins | Weeks 1–4 | Hybrid pipeline operational | **Code complete** — gate pending | [PHASE-1.md](./PHASE-1.md) |
| **2** | Data + Fine-Tuning | Weeks 5–8 | Genre-authentic output | Not started | [PHASE-2.md](./PHASE-2.md) |
| **3** | Structure + Emotion | Weeks 9–14 | Tension-driven composition | Not started | [PHASE-3.md](./PHASE-3.md) |
| **4** | Custom Model + Multi-Voice | Weeks 15–20 | Full compositional system | Not started | [PHASE-4.md](./PHASE-4.md) |

> **Phase 3–4 are optional.** If Phase 2 benchmarks show >90% of reference corpus quality, the system is production-ready.

### Supporting Documents

| Document | Purpose |
|----------|---------|
| [EVALUATION.md](./EVALUATION.md) | Listening tests, metrics, phase gate criteria |
| [DATASET-STRATEGY.md](./DATASET-STRATEGY.md) | Tiered data approach (Tier 1/2/3) |
| [INTEGRATION.md](./INTEGRATION.md) | Compatibility with existing Ableton pipeline |

---

## Dependency Graph

This table shows the critical path. Steps without listed dependencies can be parallelized.

| Step | Name | Depends On | Blocks | Status |
|------|------|------------|--------|--------|
| 1.1 | Environment Setup (Docker) | None | Everything | ✅ Done |
| 1.2 | music21 Integration | 1.1 | 1.4, 1.6, 3.1, 3.4, 4.3 | ✅ Core done (minor items remain) |
| 1.3 | MidiTok REMI Setup | 1.1 | 1.5, 2.1, 4.1 | ✅ Done |
| 1.4 | Melody/Improv RNN | 1.1, 1.2 | 1.7 | ✅ Done |
| 1.5 | MusicVAE Integration | 1.1, 1.3 | 1.7, 3.3 | ✅ Done |
| 1.6 | Evaluation Framework | 1.2 | 1.7, 2.5, all benchmarks | ✅ Done |
| 1.7 | Full Pipeline v1 | 1.1–1.6 | Phase 2 | ✅ Done |
| 2.1 | Trance Dataset (Tiered) | 1.3, 1.7 | 2.2, 2.3, 2.4, 3.1 | Not started |
| 2.2 | Fine-tune Melody RNN | 2.1 | 2.5 |
| 2.3 | Fine-tune MusicVAE | 2.1 | 2.5 |
| 2.4 | Fine-tune midi-model | 2.1 | 2.5 |
| 2.5 | Pipeline v2 Benchmark | 2.2–2.4, 1.6 | Phase 3 |
| 3.1 | Tension Computation | 1.2, 2.1 | 3.2, 3.4, 4.3 |
| 3.2 | Tension Curve Generation | 3.1 | 3.2b, 3.3, 3.4 |
| 3.2b | Rejection Sampling + Reranking | 3.2, 1.6 | 3.3, 4.3 (RL gate) |
| 3.3 | Section-Level Structure | 3.2, 1.5 | 4.1 |
| 3.4 | Advanced Humanization | 3.2, 1.2 | 4.4 |
| 4.1 | Custom Transformer | 2.1, 3.1–3.3 | 4.2, 4.3 |
| 4.2 | Multi-Voice Generation | 4.1 | 4.4 |
| 4.3 | RL Music Theory (gated) | 4.1, 3.1, 3.2b | 4.4 |
| 4.4 | Production Integration | All above | Deployment |

---

## Critical Path

```
1.1 → 1.2 → 1.4 ──┐
1.1 → 1.3 → 1.5 ──┤
1.2 → 1.6 ─────────┤
                    ├→ 1.7 → 2.1 → 2.2/2.3/2.4 → 2.5 → 3.1 → 3.2 → 3.2b → 3.3 → 4.1 → 4.4
```

---

## Model Strategy (Revised)

The Magenta dependency is managed, not eliminated:

| Model | Role | Lifecycle | Rationale |
|-------|------|-----------|-----------|
| **Melody RNN / Improv RNN** | Chord-conditioned generation | Phase 1 only, drop after midi-model fine-tuned | Quick win, replaced by better model |
| **MusicVAE** | Motif variation + interpolation | Keep long-term (inference-only) | Latent space is uniquely valuable, no PyTorch equivalent |
| **SkyTNT midi-model** | Primary generation engine | Long-term primary | PyTorch, ONNX, LoRA, actively maintained |
| **Custom Transformer** | Conditioned trance generation | Phase 4+, if needed | Full control over architecture and conditioning |

MusicVAE stays in a contained TF environment for inference only. When a PyTorch VAE with equivalent latent space capability emerges (or is built in Phase 4), Magenta can be fully dropped.

---

## Key Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| **Magenta dependency hell** | Docker isolation (Step 1.1, `shared/magenta/`). Stateless containers via JSON stdin/stdout — no persistent service needed. MusicVAE inference-only reduces surface area. |
| **Training data scarcity** | Tiered dataset strategy (see [DATASET-STRATEGY.md](./DATASET-STRATEGY.md)). Even 300 Tier 2 files x 12 transpositions = 3,600 training examples. |
| **RL reward collapse** | RL is gated behind rejection sampling (Step 3.2b). Only pursue if rejection sampling with 20–50 candidates can't hit 95% theory compliance. KL penalty against base policy. Monitor pitch entropy; halt if <2.0 bits. |
| **Over-engineering** | Phase 3–4 are optional. Every phase gate includes human listening tests. |
| **Timeline slippage** | Plan for 24–28 weeks internally. Magenta env setup, dataset curation, and beam search tuning always take longer than estimated. |
| **Audio-to-MIDI extraction quality** | Demucs + Basic Pitch on layered trance synths produces mediocre results. Tier 2 requires manual spot-checking. Don't rely on auto-extraction alone. |

---

## Hardware Requirements Summary

| Task | Minimum GPU | Time | Estimated Cost |
|------|-------------|------|---------------|
| Phase 1 (all steps) | None (CPU only) | — | $0 |
| Fine-tune Melody RNN | T4 (16 GB) | ~10 hrs | ~$10 |
| Fine-tune MusicVAE | T4 (16 GB) | 2–4 hrs | ~$5 |
| Fine-tune midi-model (LoRA) | A10 (24 GB) | 12–24 hrs | ~$30–60 |
| Custom Transformer training | RTX 3090/4090 (24 GB) | 1–7 days | ~$100–500 |
| RL training (if needed) | T4 (16 GB) | 12–24 hrs | ~$10–20 |
| **All inference** | **None (CPU)** | **<5 sec** | **$0** |

---

## Key Libraries & Versions

| Library | Version | License | Environment | Purpose |
|---------|---------|---------|-------------|---------|
| magenta | latest | Apache 2.0 | Docker container (Py 3.9) | MusicVAE (long-term), Melody RNN (Phase 1 only) |
| tensorflow | 2.11.0 | Apache 2.0 | Docker container | Magenta backend (inside container only) |
| music21 | 9.9.x | BSD 3-clause | Host (Py 3.11+) | Music theory |
| miditok | 3.0.x | MIT | Host | REMI tokenization |
| mido | 1.3.x | MIT | Host | MIDI I/O |
| numpy | 2.x | BSD | Host | Evaluation metrics, similarity index |
| torch | 2.x | BSD | melody-gen | SkyTNT, custom models |
| onnxruntime | latest | MIT | melody-gen | Optimized inference |
| basic-pitch | latest | Apache 2.0 | melody-gen | Audio-to-MIDI |
| demucs | latest | MIT | melody-gen | Source separation |

---

## Phase Gate Protocol

Every phase boundary includes both automated benchmarks AND human evaluation. See [EVALUATION.md](./EVALUATION.md) for the full protocol. Summary:

1. **Automated metrics** — composite score vs. reference corpus
2. **Human listening test** — 10 melodies per config, blind A/B, 3–5 listeners, forced choice: "which sounds more like a real trance melody?"
3. **Go/no-go decision** — proceed to next phase, iterate on current phase, or declare production-ready
