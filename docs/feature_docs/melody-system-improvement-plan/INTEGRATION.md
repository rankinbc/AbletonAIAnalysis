# Integration: Connecting Melody Engine to Existing Ableton Pipeline

> The existing system generates full Ableton `.als` projects with embedded MIDI, track coloring, arrangement markers, sidechain routing, and more. The melody engine produces output that plugs into this assembly pipeline without breaking it.

---

## Current Pipeline Flow

```
SongSpec (song_spec.py)
  ├── TrackSpec per track (name, instrument, pattern type, color)
  ├── SectionSpec per section (type, bars, energy, active tracks)
  │
  ├── midi_generator.py → MIDI files per track
  ├── melody_generation/ → Lead/arp MIDI (hybrid pipeline)
  │
  └── ableton_project.py
      ├── Creates .als from template
      ├── clip_embedder.py → Embeds MIDI clips in .als
      ├── stem_arranger.py → Controls which tracks play per section
      ├── sidechain_config.py → Kick→bass/pad routing
      ├── send_routing.py → Reverb/delay sends
      └── mix_templates.py → EQ/compression per track
```

## Integration Point

The `HybridPipeline` (in `melody_generation/integration.py`) replaces the output of `midi_generator.py` for melodic tracks (lead, arp). Everything downstream (`ableton_project.py`, `clip_embedder.py`, etc.) remains unchanged.

```
                     ┌──────────────────────┐
SongSpec ──────────► │ HybridPipeline       │ ──► MIDI files (same format)
                     │   - Rule engine lead  │         │
                     │   - ML candidates     │         │
                     │   - Arp pattern       │         ▼
                     │   - Evaluation scoring│   ableton_project.py
                     └──────────────────────┘   (unchanged)
```

There is also a standalone CLI for melody generation and baseline recording:

```bash
# Rule-only generation
python generate.py --key Am --bpm 140 --chords "Am F C G" --bars 16

# Hybrid with ML candidates (requires Docker + Magenta image)
python generate.py --ml-candidates 5 --variations 2 --verbose --scorecard

# Batch for baseline recording
python generate.py --batch 50 --output baselines --baseline-label phase_1_hybrid
```

## Compatibility Requirements

### MIDI Output Format

The melody engine must produce MIDI files that `clip_embedder.py` can consume:

- **Format:** Standard MIDI file (Type 0 or Type 1)
- **One file per track** (lead.mid, arp.mid, bass.mid, pad.mid)
- **Tempo:** Embedded in MIDI header, matching SongSpec BPM
- **Time signature:** 4/4
- **Resolution:** 480 ticks per quarter note (matching `config.py` default)
- **Channel:** Channel 0 for all melodic tracks (Ableton ignores MIDI channel in arrangement view)
- **Velocity:** 0–127 range, humanized values acceptable
- **Note names in clips:** When using `--split-sections`, clip names must match section names from SongSpec (e.g., "Lead - Intro", "Lead - Drop 1")

### SongSpec Compatibility

The `HybridPipeline` accepts parameters directly (key, scale, tempo, chords, section type, bars, energy). It does not read from `SongSpec` directly — the calling code maps SongSpec fields to pipeline parameters.

The following `SongSpec` additions are planned for Phase 3+ when section-level structure and tension curves are implemented:

```python
# Future additions to SongSpec (song_spec.py) — Phase 3+
@dataclass
class SongSpec:
    # ... existing fields ...
    tension_curve: Optional[List[float]] = None  # Per-bar tension values (Phase 3)
    melody_model: str = "auto"                    # "auto", "midi_model", "rules", etc.
    variation_level: float = 0.3                   # MusicVAE noise scale
    humanization_intensity: float = 0.5

# Future additions to SectionSpec — Phase 3+
@dataclass
class SectionSpec:
    # ... existing fields ...
    motif_id: str = "A"           # Which motif to use (A=primary, B=secondary)
    motif_variation: float = 0.0  # 0=exact, 1=free variation
```

These additions will be backwards-compatible — existing SongSpecs without these fields use defaults.

### stem_arranger.py Compatibility

The stem arranger controls which tracks are active per section. The melody engine's section-level planning (Phase 3, Step 3.3) must respect the arranger's track activation schedule. Two options:

1. **Engine respects arranger** (recommended): The melody engine generates MIDI for all sections, and the arranger mutes/unmutes as it does now. Simpler, no changes to arranger.
2. **Engine coordinates with arranger**: The engine reads the arranger's activation schedule and only generates MIDI for active sections. Tighter but requires arranger API changes.

Start with option 1. The arranger already handles muting — don't duplicate that logic.

---

## Wiring It In

### Current Implementation (Phase 1)

The `HybridPipeline` in `melody_generation/integration.py` is the primary interface:

```python
from melody_generation.integration import HybridPipeline

def generate_song(song_spec):
    pipeline = HybridPipeline(
        key=song_spec.key,
        scale="minor",
        tempo=song_spec.tempo,
        output_dir=str(output_dir / "midi"),
        reference_stats_path="evaluation/reference_stats.json",
    )

    # Single generation — returns HybridResult with lead + arp MIDI
    result = pipeline.generate(
        chords=["Am", "F", "C", "G"],
        section_type="drop",
        bars=16,
        energy=0.9,
        num_ml_candidates=5,      # 0 for rule-only
        num_variations=2,          # MusicVAE variations per candidate
    )

    # result.midi_path  → Path to exported MIDI file
    # result.lead_source → "rule_engine" or "improv_rnn" or "musicvae_variation"
    # result.lead_metrics → MelodyMetrics with composite score
    # result.all_candidates → All scored candidates for audit

    # Drums and FX still use existing generators
    generate_drums(song_spec, output_dir)
    generate_fx(song_spec, output_dir)

    # Assembly unchanged
    assemble_als(song_spec, output_dir)
```

The pipeline handles candidate competition internally — rule-based and ML candidates are all scored by the evaluation framework, and the best composite score wins.

### Parallel/Comparison Mode (Baseline Testing)

The CLI supports batch generation for comparing rule-only vs hybrid output:

```bash
# Generate 50 rule-only baselines
python generate.py --batch 50 --output baselines --baseline-label rule_only

# Generate 50 hybrid baselines
python generate.py --batch 50 --ml-candidates 5 --output baselines --baseline-label hybrid

# Compare programmatically
from melody_generation.evaluation import load_baseline, compare_baselines
rule = load_baseline("baselines/rule_only_baseline.json")
hybrid = load_baseline("baselines/hybrid_baseline.json")
report = compare_baselines(rule, hybrid)
print(f"Improvement: {report.composite_improvement:+.1%}")
```

---

## What Doesn't Change

These components are unaffected by the melody engine:

- `ableton_project.py` — reads MIDI files, doesn't care how they were generated
- `clip_embedder.py` — embeds whatever MIDI it receives
- `stem_arranger.py` — controls muting, not generation
- `sidechain_config.py` — routing, independent of melody
- `send_routing.py` — effects routing, independent
- `mix_templates.py` — EQ/compression presets, independent
- `texture_generator.py` — textures are separate from melodic content
- `transition_generator.py` — transitions are separate
- `automation_generator.py` — automation is separate

---

## Future: Max for Live Integration

For tighter DAW integration beyond file-based exchange:

1. Run the melody engine as a local FastAPI server
2. Build a Max for Live device that sends HTTP requests to the server
3. Device sends: key, chord, section type, energy level
4. Server returns: MIDI clip data
5. Device creates MIDI clip in Ableton's arrangement

This is a post-Phase-4 enhancement — not part of the core plan. Estimated effort: 1–2 days once the engine API is stable.
