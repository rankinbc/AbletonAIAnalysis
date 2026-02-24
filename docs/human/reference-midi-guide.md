# Reference MIDI Files: What You Need and What To Do With Them

## Quick Summary

You need **20–50 trance melody MIDI files** to unlock the evaluation system. These are not training data — they define "what good trance melodies look like" so the system can score its own output. Collecting even 10 files is enough to get started.

---

## What Counts as a Reference MIDI File

Each file should be a **single monophonic melody line** from a trance track. Think: the main lead melody or hook, not the full arrangement.

**Good examples:**
- The iconic melody from Above & Beyond — Sun & Moon
- The lead synth line from Armin van Buuren — Communication
- The main hook from Tiesto — Adagio for Strings
- Your own melodies that you consider well-written

**Requirements per file:**
- Format: `.mid` (Standard MIDI, Type 0 or 1)
- Content: Single melody line (monophonic or mostly monophonic)
- Length: 8–32 bars preferred (4 bars minimum)
- Tempo: 130–150 BPM (trance range)
- Key: Any key, but natural/harmonic minor preferred (matches trance conventions)
- Quality: Notes should be accurate — correct pitches, reasonable timing

**What to avoid:**
- Full arrangements with drums, bass, pads, etc.
- Chord pads or polyphonic parts (the system expects lead melodies)
- Files with wrong notes or garbled timing
- Non-trance genres (house, techno, DnB) unless intentionally broadening the palette

---

## How Many Files You Need

| Count | What It Unlocks |
|-------|----------------|
| **10** | Minimum viable reference corpus — evaluation scores become meaningful |
| **20–50** | Full reference corpus — reliable metric distributions and KL divergence |
| **50–100** | Tier 1 gold standard — enough for fine-tuning in Phase 2 |

Start with 10. You can always add more later.

---

## Where to Get Them

### Option 1: Transcribe Yourself (Highest Quality)

Open your DAW, listen to a trance track, and transcribe the lead melody onto a MIDI track by ear. Export as `.mid`.

- **Effort:** 10–30 minutes per melody
- **Quality:** Excellent — you verify every note
- **Best for:** Tier 1 gold standard files

### Option 2: Download from MIDI Archives

Sites like midiworld.com, freemidi.org, or bitmidi.com have user-uploaded MIDI files. Quality varies wildly.

- **Effort:** 5 minutes per file (download + inspect)
- **Quality:** Mixed — always inspect in your DAW's piano roll before accepting
- **Best for:** Bulk collection, but expect 50% rejection rate

### Option 3: Extract from Audio (Automated)

The project has tools for this (Demucs source separation + Basic Pitch transcription), but results on layered trance synths are unreliable. This is better suited for Phase 2 Tier 2 data collection.

- **Effort:** Automated, but requires QA review
- **Quality:** 60–70% usable
- **Best for:** Tier 2 bulk data, not Tier 1 reference

### Option 4: Your Own Compositions

Your own MIDI melodies from Ableton projects are excellent reference material — they already reflect your taste and style.

- Export the lead MIDI clip from any of your trance projects
- These can serve as both reference and Tier 1 training data later

---

## What To Do With the Files

### Step 1: Organize

Place your MIDI files in the dataset folder:

```
AbletonAIAnalysis/
└── dataset/
    └── tier1/
        ├── above_and_beyond_sun_moon.mid
        ├── armin_communication.mid
        ├── my_melody_01.mid
        └── ...
```

Create the folder if it doesn't exist:
```bash
mkdir -p dataset/tier1
```

### Step 2: Compute Reference Stats

Once you have files collected, run the evaluation framework to build the reference corpus:

```python
from melody_generation.evaluation import compute_reference_stats
from pathlib import Path

# Gather all MIDI files
midi_files = list(Path("dataset/tier1").glob("*.mid"))
print(f"Found {len(midi_files)} reference files")

# Compute aggregate statistics
ref_stats = compute_reference_stats(midi_files, key="A", scale="minor")

# Save for later use
ref_stats.save("evaluation/reference_stats.json")

print(f"Reference corpus: {ref_stats.num_files} files")
print(f"Mean composite score: {ref_stats.means.get('composite', 'N/A')}")
```

This produces `reference_stats.json` — the benchmark that all generated melodies are scored against.

### Step 3: Record the Rule-Only Baseline

Before any ML improvements, capture what the current rule engine produces:

```python
from melody_generation.evaluation import evaluate_melody, save_baseline
from melody_generation import LeadGenerator, parse_progression

# Generate 50 melodies with rule engine
lead_gen = LeadGenerator(key="A", scale="minor", genre="trance")
chords = parse_progression(["Am", "F", "C", "G"], key="A", scale="minor")

metrics_list = []
for i in range(50):
    melody = lead_gen.generate_for_section(
        section_type="drop", bars=16, energy=0.9
    )
    metrics = evaluate_melody(melody, key="A", scale="minor", chord_events=chords)
    metrics_list.append(metrics)

# Save baseline
save_baseline(metrics_list, "evaluation/baselines/phase_0_rule_only.json")
```

This becomes the comparison point — the hybrid pipeline (Step 1.7) must beat this.

### Step 4: (Optional) Populate the Motif Similarity Index

If you want context-aware motif retrieval, index your reference melodies:

```python
from melody_generation.ml_bridge import MotifSimilarityIndex

index = MotifSimilarityIndex()
for midi_path in midi_files:
    index.add(str(midi_path), {"name": midi_path.stem, "source": "tier1"})
index.build()
index.save("evaluation/motif_index.json")
```

This requires Docker + the Magenta image to be built (for MusicVAE encoding).

---

## How the System Uses Reference Files

### Evaluation Scoring

When the system generates a melody and scores it, two metrics directly depend on the reference corpus:

1. **KL Divergence** (weight: 0.15) — compares the pitch distribution of the generated melody against the reference corpus. Lower = more similar to real trance melodies.

2. **Composite score context** — reference stats provide the "what's normal" baseline for interpreting all other metrics.

Without reference files, these metrics default to uniform distributions, making scores less meaningful.

### Phase Gates

Every phase advancement requires:
- **Automated check:** Generated melodies must score above threshold vs reference
- **Human listening test:** Blind A/B comparison (10 pairs, 3+ listeners, >60% win rate)

The reference corpus provides the "ground truth" for automated checks.

### Future Training (Phase 2)

The same Tier 1 files you collect now become the gold standard training data for fine-tuning ML models in Phase 2. So this effort pays off twice.

---

## File Naming Convention

Use descriptive, lowercase names with underscores:

```
artist_name_track_name.mid          # Transcribed reference
my_melody_description.mid           # Your own compositions
extracted_artist_track.mid           # Audio extraction results
```

---

## Checklist

- [ ] Create `dataset/tier1/` folder
- [ ] Collect 10+ trance melody MIDI files
- [ ] Inspect each file in DAW piano roll (correct notes? monophonic? right tempo?)
- [ ] Create `evaluation/` folder structure
- [ ] Run `compute_reference_stats()` to build `reference_stats.json`
- [ ] Run rule-only baseline generation (50 melodies)
- [ ] Save baseline to `evaluation/baselines/phase_0_rule_only.json`

Once this checklist is done, the evaluation system is fully operational and Step 1.7 (end-to-end pipeline) can produce meaningful scores.
