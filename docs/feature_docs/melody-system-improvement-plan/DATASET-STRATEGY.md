# Dataset Strategy: Tiered Approach to Trance MIDI Training Data

> **Core principle:** You need both quality AND quantity. A curated gold set prevents garbage-in-garbage-out. A larger noisy set provides the statistical patterns that small transformers need to learn style. Neither alone is sufficient.

---

## The Tiered Dataset

### Tier 1 — Gold Standard (50–100 files)

**What:** Hand-transcribed or manually verified trance melodies from iconic tracks.

**Sources:**
- Personal transcription in a DAW (highest quality, most effort)
- Verified MIDI archives with manual inspection
- Community contributions (with QA review)

**Quality standard:** Every file inspected in a DAW piano roll. Notes are accurate, timing is correct, key/scale matches the original.

**Used for:**
- Final fine-tuning (last epoch or LoRA pass)
- Evaluation reference set (computing target metric distributions)
- Human listening test comparisons (the "real trance melody" standard)

**Why not just use this?** 50 files will overfit any neural network in minutes, even with LoRA. A model trained on 50 melodies x 12 transpositions = 600 examples knows 50 melodic ideas, not trance. It memorizes instead of generalizing.

**Storage:** `dataset/tier1/`

---

### Tier 2 — Verified Extraction (300–500 files)

**What:** Melodies auto-extracted from reference audio tracks, with manual spot-checking.

**Pipeline:**
1. Source separation with Demucs (isolate lead synth)
2. Transcription with Basic Pitch (audio → MIDI)
3. Validation with music21 (reject if >30% out-of-key notes)
4. Manual spot-check: listen to every 5th file, reject batch if >30% have obvious errors

**Realistic expectations:** Demucs + Basic Pitch on layered trance synths produces mediocre results. Reverb tails, stacked saw layers, and sidechained pads confuse the transcriber. Expect 60–70% yield — process 200+ reference tracks to get 300.

**Quality standard:** Not perfect, but "mostly right." The melody is recognizable, key is correct, rhythm is close. Occasional wrong notes are acceptable at this tier.

**Used for:** Main training corpus. This is where the model learns genre patterns.

**Why this matters more than Tier 3 quantity:** Going from 300 to 500 Tier 2 files (more careful extraction, more spot-checking) provides more training value than going from 1,000 to 3,000 Tier 3 files (more augmentation). Invest time here.

**Storage:** `dataset/tier2/`

---

### Tier 3 — Bulk + Augmented (1,000+ files)

**What:** Mixed-quality files from public datasets, synthetic generation, and data augmentation.

**Sources:**
- **GigaMIDI filtering:** 1.4M files on HuggingFace, filtered by electronic genre tags + 130–150 BPM + monophonic. Yield: 200–500 files. Genre tags are unreliable — "electronic" covers ambient to gabber. Expect noise.
- **Synthetic generation:** 200–500 melodies from the Phase 1 hybrid pipeline with maximum parameter variation. Labeled as synthetic in metadata. Caveat: has the same limitations you're trying to fix (generates the old system's biases). Useful for pre-training but not fine-tuning.
- **Data augmentation on ALL tiers:** Applied after collection.

**Quality standard:** Passes automated filters (key/tempo/range/polyphony checks, REMI roundtrip). Not manually verified. Will contain noise.

**Used for:** Pre-training only. General pattern exposure. The model sees enough data to learn "what music looks like" before fine-tuning teaches it "what trance sounds like" via Tier 1–2.

**Storage:** `dataset/tier3/`

---

## Data Augmentation

Applied to all tiers after collection. Augmentation inflates numbers but doesn't add melodic diversity — the same 500 ideas in 12 keys is still 500 ideas. Its value is regularization and pitch invariance, not novelty.

| Transform | Multiplier | Notes |
|-----------|-----------|-------|
| 12-key transposition | x12 | Most impactful. Teaches pitch invariance. |
| Tempo scaling ±10% | x3–5 | Minor rhythmic variation. ±5% and ±10%. |
| Velocity perturbation ±10 | x1 | Applied in-place, not a separate file. |
| Octave shift ±1 | x2–3 | Only where range permits. Skip if result falls outside 1–3 octave range. |

**Expected totals after augmentation:**

| Tier | Raw Files | Post-Augment |
|------|-----------|-------------|
| Tier 1 | 50–100 | 600–1,200 |
| Tier 2 | 300–500 | 3,600–6,000 |
| Tier 3 | 500–1,000 | 6,000–12,000 |
| **Total** | **850–1,600** | **10,200–19,200** |

---

## Training Data Usage by Phase

| Phase | Tier 1 | Tier 2 | Tier 3 |
|-------|--------|--------|--------|
| **Phase 2.2** (Melody RNN) | Evaluation only | Training | Pre-training |
| **Phase 2.3** (MusicVAE) | Evaluation only | Training | Pre-training |
| **Phase 2.4** (midi-model LoRA) | Final LoRA pass | Training | Pre-training |
| **Phase 3.1** (IDyOMpy) | Corpus training | Corpus training | — |
| **Phase 4.1** (Custom Transformer) | Final epoch | Training | Pre-training |

**Training strategy for each model:**
1. Pre-train on Tier 3 (learn general music patterns)
2. Fine-tune on Tier 2 (learn trance-specific patterns)
3. Final pass on Tier 1 (polish with gold-standard examples)
4. Evaluate against Tier 1 held-out set (never trained on)

---

## Quality Filtering Pipeline

Every file passes through this pipeline regardless of tier:

```python
def quality_filter(midi_path, tier):
    """Returns True if file passes quality checks for its tier."""
    score = converter.parse(str(midi_path))
    key = score.analyze('key')

    # Universal checks (all tiers)
    pitches = [n.pitch.midi for n in score.flatten().notes]
    if not pitches:
        return False
    pitch_range = (max(pitches) - min(pitches)) / 12
    if pitch_range < 0.5 or pitch_range > 3.5:
        return False  # too narrow or too wide

    # Tempo check
    tempo = get_tempo(midi_path)
    if tempo and not (120 <= tempo <= 160):
        return False

    # Polyphony check (lead melodies should be mostly monophonic)
    if compute_polyphony_ratio(score) > 0.3:
        return False

    # Scale compliance (tier-dependent threshold)
    scale_compliance = compute_scale_compliance(score, key)
    thresholds = {'tier1': 0.90, 'tier2': 0.70, 'tier3': 0.60}
    if scale_compliance < thresholds[tier]:
        return False

    # REMI roundtrip check
    if not verify_remi_roundtrip(midi_path):
        return False

    return True
```

---

## Metadata Format

Every file gets a metadata sidecar:

```json
{
  "path": "dataset/tier2/above_and_beyond_sun_moon_melody.mid",
  "tier": 2,
  "source": "audio_extraction",
  "original_track": "Above & Beyond - Sun & Moon",
  "original_key": "Ab minor",
  "original_bpm": 138,
  "augmentations_applied": [],
  "scale_compliance": 0.82,
  "pitch_range_octaves": 1.8,
  "extraction_method": "demucs_v4 + basic_pitch",
  "manually_verified": false,
  "spot_checked": true,
  "date_added": "2026-03-01"
}
```

---

## Copyright Considerations

- **Tier 1 (transcriptions):** Melody transcriptions are derivative works. For training ML models on private infrastructure with no public distribution of generated output, this falls under fair use in most jurisdictions. Do not distribute the training MIDI files.
- **Tier 2 (audio extraction):** Same as Tier 1 — extracted from owned/licensed reference tracks.
- **Tier 3 (GigaMIDI):** CC-BY-SA 4.0 license. Check attribution requirements.
- **Plagiarism detection:** After training, run generated output through a similarity check against the training corpus. Flag any generation with >90% cosine similarity (on pitch-class sequences) to any training example.

```python
def check_plagiarism(generated_midi, training_corpus, threshold=0.9):
    """Flag generated melodies too similar to training data."""
    gen_features = extract_pitch_class_sequence(generated_midi)
    for training_file in training_corpus:
        train_features = extract_pitch_class_sequence(training_file)
        similarity = cosine_similarity(gen_features, train_features)
        if similarity > threshold:
            return True, training_file, similarity
    return False, None, 0.0
```
