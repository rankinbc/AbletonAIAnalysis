# Phase 1 Completion Checklist

Everything that must be done before moving to Phase 2 (Data Pipeline & Fine-Tuning).

Phase 1 code is complete. What remains is operational work: building infrastructure, collecting data, recording baselines, and running the Phase 1 gate.

---

## 1. Build the Docker Magenta Image

The hybrid pipeline's ML path (Improv RNN, MusicVAE) runs inside a Docker container. The image must be built once on your machine.

**Prerequisites:**
- Docker Desktop installed and running (Windows 11: enable WSL2 backend)

**Steps:**
```bash
cd shared/magenta
docker build -t magenta:latest .
```

**Expected time:** 10-15 minutes (downloads TensorFlow 2.11, Magenta, and 4 model checkpoints totaling ~500MB).

**Verification:**
```bash
docker images | grep magenta
# Should show: magenta    latest    <hash>    <size>
```

Then test from Python:
```python
from shared.magenta import DockerMagenta, is_docker_available, is_magenta_image_available
print(is_docker_available())           # True
print(is_magenta_image_available())    # True

magenta = DockerMagenta()
result = magenta.generate_melody(chords=["Am", "F", "C", "G"], bars=8, bpm=140)
print(result.midi_paths)  # Should show generated MIDI file paths
```

---

## 2. Collect Reference MIDI Files

The evaluation framework needs real trance melodies to compute meaningful scores. See `docs/human/reference-midi-guide.md` for full details.

**Minimum:** 10 files to get started
**Target:** 20-50 files for reliable metric distributions

**What counts:** Single monophonic lead melody lines from trance tracks, 130-150 BPM, .mid format.

**Where to put them:**
```
dataset/tier1/
├── above_and_beyond_sun_moon.mid
├── armin_communication.mid
├── my_melody_01.mid
└── ...
```

**Sources (in order of quality):**
1. Transcribe melodies yourself in your DAW (10-30 min each, highest quality)
2. Export lead MIDI clips from your own Ableton projects
3. Download from MIDI archive sites (inspect each in piano roll before accepting)

---

## 3. Compute Reference Stats

Once you have reference MIDI files, build the reference corpus:

```bash
cd projects/ableton-generators
python -c "
from melody_generation.evaluation import compute_reference_stats
from pathlib import Path

midi_files = list(Path('../../dataset/tier1').glob('*.mid'))
print(f'Found {len(midi_files)} files')

ref = compute_reference_stats(midi_files, key='A', scale='minor')
ref.save('../../evaluation/reference_stats.json')
print(f'Saved reference stats ({ref.num_files} files)')
"
```

This creates `evaluation/reference_stats.json` — the benchmark for all scoring.

---

## 4. Record the Rule-Only Baseline

Before testing the hybrid pipeline, capture what the current rule engine produces on its own. This is the comparison point for the Phase 1 gate.

```bash
cd projects/ableton-generators
python generate.py \
    --batch 50 \
    --output ../../evaluation/baselines \
    --baseline-label phase_0_rule_only \
    --verbose
```

This generates 50 melodies using only the rule engine and saves metrics to `evaluation/baselines/phase_0_rule_only_baseline.json`.

---

## 5. Test the Hybrid Pipeline with ML Candidates

With Docker built and reference stats computed, run the hybrid pipeline:

```bash
# Single generation with ML
python generate.py \
    --ml-candidates 5 \
    --variations 2 \
    --reference-stats ../../evaluation/reference_stats.json \
    --verbose \
    --scorecard

# Batch hybrid baseline
python generate.py \
    --batch 50 \
    --ml-candidates 5 \
    --variations 2 \
    --reference-stats ../../evaluation/reference_stats.json \
    --output ../../evaluation/baselines \
    --baseline-label phase_1_hybrid \
    --verbose
```

Check the output: the `lead_source` field in the log tells you whether ML or rule-engine won each generation.

---

## 6. Compare Baselines

Compare the rule-only and hybrid baselines:

```python
from melody_generation.evaluation import load_baseline, compare_baselines, ReferenceStats

rule = load_baseline("../../evaluation/baselines/phase_0_rule_only_baseline.json")
hybrid = load_baseline("../../evaluation/baselines/phase_1_hybrid_baseline.json")
ref = ReferenceStats.load("../../evaluation/reference_stats.json")

report = compare_baselines(rule, hybrid, ref)
print(f"Composite improvement: {report.composite_improvement:+.1%}")
```

**Phase 1 gate automated check:** Hybrid composite must be **>0%** improvement over rule-only.

---

## 7. Run the Phase 1 Gate Listening Test

This is the final gate before Phase 2. The automated metrics are necessary but not sufficient — human ears catch what numbers miss.

**Protocol (from EVALUATION.md):**

1. Generate 10 melodies with the rule-only pipeline (config A)
2. Generate 10 melodies with the hybrid pipeline (config B)
3. Render all 20 as audio using the same synth patch:
   - Synth: Ableton Analog or a simple saw lead
   - Tempo: 140 BPM
   - Duration: 16 bars each
   - No effects (dry signal)
   - Export as WAV at 44.1kHz
4. Pair them randomly: A1 vs B1, A2 vs B2, etc.
5. Have 3-5 listeners hear each pair blind and answer: **"Which sounds more like a real trance melody?"**
6. Record results

**Pass threshold:** >60% win rate for hybrid (B) across all comparisons.

With 10 pairs and 3 listeners = 30 total comparisons, 18+ wins for B is statistically significant at p<0.05.

**Record results in:**
```
evaluation/listening_tests/YYYY-MM-DD_phase1_gate.json
```

Format:
```json
{
  "phase_gate": "Phase 1",
  "date": "2026-XX-XX",
  "config_a": "Rule-only",
  "config_b": "Phase 1 hybrid (pre-trained)",
  "listeners": 3,
  "pairs": 10,
  "total_comparisons": 30,
  "b_wins": 22,
  "a_wins": 8,
  "win_rate_b": 0.733,
  "decision": "proceed_to_phase_2",
  "notes": ""
}
```

---

## 8. Finish Step 1.2 (music21 — Optional but Recommended)

Step 1.2 (replace hand-coded music theory with music21) is partially done. The harmonic engine already uses music21 for scale operations, interval classification, NCT detection, and key detection. The remaining items are lower priority but would strengthen the foundation:

- [ ] **Chord-tone analysis via ChordSymbol** — Currently chord membership uses manual pitch matching. Using `music21.harmony.ChordSymbol` would handle extensions (7ths, 9ths, sus) more robustly.
- [ ] **Consonance/dissonance scoring** — `interval.isConsonant()` could feed into the evaluation framework's tension correlation metric.
- [ ] **Regression tests** — Verify that existing rule engine outputs haven't changed after music21 integration.

These are "nice to have" before Phase 2. They are not blocking.

---

## Phase 1 Gate Summary

All three criteria must pass:

| # | Criterion | Threshold | How to Check |
|---|-----------|-----------|-------------|
| 1 | **Pipeline operational** | Generates 50 melodies without errors | `python generate.py --batch 50` |
| 2 | **Composite score improvement** | Hybrid > rule-only (any amount) | Compare baseline JSONs |
| 3 | **Human preference** | Hybrid wins >60% of blind A/B | Listening test with 3+ people |

**Decision:**
- All three pass: **Proceed to Phase 2.**
- #1 and #2 pass but #3 fails: Investigate which metric is misleading. Iterate on the hybrid pipeline before retesting.
- #1 fails: Debug pipeline issues before anything else.

---

## Phase 2 Prerequisites (from PHASE-2.md)

Once the gate passes, Phase 2 needs:

- [ ] **GPU access** — T4 minimum, A10 for midi-model. Cloud GPU (Colab Pro, Lambda, RunPod) or local.
- [ ] **Reference audio library** — 50-200 trance tracks for Demucs+Basic Pitch extraction (Tier 2 dataset).
- [ ] **HuggingFace CLI** — For downloading GigaMIDI (Tier 3 filtering).
- [ ] **Storage** — ~200 GB for raw dataset + processed output.
- [ ] **Demucs + Basic Pitch** — `pip install demucs basic-pitch`

---

## Checklist (Do These In Order)

```
[ ] 1. Install Docker Desktop, enable WSL2 backend
[ ] 2. Build Magenta image: docker build -t magenta:latest shared/magenta/
[ ] 3. Verify: python -c "from shared.magenta import is_magenta_image_available; print(is_magenta_image_available())"
[ ] 4. Collect 10-50 reference MIDI files into dataset/tier1/
[ ] 5. Create evaluation/ directory structure
[ ] 6. Compute reference stats: reference_stats.json
[ ] 7. Record rule-only baseline: python generate.py --batch 50 ...
[ ] 8. Record hybrid baseline: python generate.py --batch 50 --ml-candidates 5 ...
[ ] 9. Compare baselines: confirm hybrid composite > rule-only
[ ] 10. Render 20 melodies as audio (10 rule, 10 hybrid)
[ ] 11. Run blind A/B listening test with 3+ listeners
[ ] 12. Record listening test results in evaluation/listening_tests/
[ ] 13. If >60% hybrid win rate: Phase 1 gate PASSED — proceed to Phase 2
```
