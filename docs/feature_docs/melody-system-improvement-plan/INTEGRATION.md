# Integration: Connecting New Melody Engine to Existing Ableton Pipeline

> The existing system already generates full Ableton `.als` projects with embedded MIDI, track coloring, arrangement markers, sidechain routing, and more. The new melody engine must produce output that plugs into this assembly pipeline without breaking it.

---

## Current Pipeline Flow

```
SongSpec (song_spec.py)
  ├── TrackSpec per track (name, instrument, pattern type, color)
  ├── SectionSpec per section (type, bars, energy, active tracks)
  │
  ├── midi_generator.py → MIDI files per track
  ├── melody_generation/ → Lead/arp MIDI (current rule-based system)
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

The new `MelodyEngine` replaces the output of `midi_generator.py` and `melody_generation/` for melodic tracks (lead, arp, potentially bass). Everything downstream (`ableton_project.py`, `clip_embedder.py`, etc.) remains unchanged.

```
                     ┌─────────────────────┐
SongSpec ──────────► │ NEW: MelodyEngine   │ ──► MIDI files (same format)
                     │   - Lead melody      │         │
                     │   - Arp pattern      │         │
                     │   - Bass line        │         ▼
                     │   - Pad voicing      │   ableton_project.py
                     └─────────────────────┘   (unchanged)
```

## Compatibility Requirements

### MIDI Output Format

The new engine must produce MIDI files that `clip_embedder.py` can consume:

- **Format:** Standard MIDI file (Type 0 or Type 1)
- **One file per track** (lead.mid, arp.mid, bass.mid, pad.mid)
- **Tempo:** Embedded in MIDI header, matching SongSpec BPM
- **Time signature:** 4/4
- **Resolution:** 480 ticks per quarter note (matching `config.py` default)
- **Channel:** Channel 0 for all melodic tracks (Ableton ignores MIDI channel in arrangement view)
- **Velocity:** 0–127 range, humanized values acceptable
- **Note names in clips:** When using `--split-sections`, clip names must match section names from SongSpec (e.g., "Lead - Intro", "Lead - Drop 1")

### SongSpec Compatibility

The new engine reads from the existing `SongSpec` and `SectionSpec` dataclasses. New fields needed:

```python
# Additions to SongSpec (song_spec.py)
@dataclass
class SongSpec:
    # ... existing fields ...
    tension_curve: Optional[List[float]] = None  # Per-bar tension values
    melody_model: str = "auto"                    # "auto", "midi_model", "rules", etc.
    variation_level: float = 0.3                   # MusicVAE noise scale
    humanization_intensity: float = 0.5

# Additions to SectionSpec
@dataclass
class SectionSpec:
    # ... existing fields ...
    motif_id: str = "A"           # Which motif to use (A=primary, B=secondary)
    motif_variation: float = 0.0  # 0=exact, 1=free variation
```

These additions are backwards-compatible — existing SongSpecs without these fields use defaults.

### stem_arranger.py Compatibility

The stem arranger controls which tracks are active per section. The new engine's section-level planning (Phase 3, Step 3.3) must respect the arranger's track activation schedule. Two options:

1. **Engine respects arranger** (recommended): The melody engine generates MIDI for all sections, and the arranger mutes/unmutes as it does now. Simpler, no changes to arranger.
2. **Engine coordinates with arranger**: The engine reads the arranger's activation schedule and only generates MIDI for active sections. Tighter but requires arranger API changes.

Start with option 1. The arranger already handles muting — don't duplicate that logic.

---

## Wiring It In

### Option A: Drop-in Replacement (Phase 1–2)

Replace the `midi_generator.py` call for melodic tracks with the new pipeline:

```python
# In the generation orchestrator (ai_song_generator.py or similar)
from melody_engine import MelodyEngine

def generate_song(song_spec):
    engine = MelodyEngine(config="production.yaml")

    # Generate melodic tracks with new engine
    melodic_midi = engine.generate(
        key=song_spec.key,
        bpm=song_spec.tempo,
        chord_progression=song_spec.chord_progression,
        structure=[{
            'section': s.section_type.value,
            'bars': s.bars,
            'motif': s.motif_id,
            'variation': s.motif_variation,
        } for s in song_spec.sections],
        tension_curve=song_spec.tension_curve or "auto",
    )

    # Write MIDI files in expected locations
    melodic_midi.save_track("lead", output_dir / "midi" / "lead.mid")
    melodic_midi.save_track("arp", output_dir / "midi" / "arp.mid")
    melodic_midi.save_track("bass", output_dir / "midi" / "bass.mid")

    # Drums and FX still use existing generators
    generate_drums(song_spec, output_dir)
    generate_fx(song_spec, output_dir)

    # Assembly unchanged
    assemble_als(song_spec, output_dir)
```

### Option B: Parallel Mode (Testing)

Run both old and new generators side by side, compare output:

```python
# Generate with both, compare
old_lead = old_midi_generator.generate_lead(song_spec)
new_lead = melody_engine.generate(song_spec).get_track("lead")

# Score both
old_score = evaluate_melody(old_lead, reference_stats)
new_score = evaluate_melody(new_lead, reference_stats)

# Use the better one (or always use new if it's above threshold)
if new_score['composite'] > old_score['composite']:
    use_midi = new_lead
else:
    use_midi = old_lead
```

---

## What Doesn't Change

These components are unaffected by the melody engine upgrade:

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
