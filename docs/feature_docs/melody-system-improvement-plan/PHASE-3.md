# Phase 3: Structure, Tension, and Humanization

> **Timeline:** Weeks 9–14 (realistically 10–16)
> **GPU Required:** No (algorithmic + lightweight ML)
> **Training Required:** IDyOMpy corpus training only (CPU, minutes)
> **Goal:** Melodies with tension-resolution narratives, long-range section structure, and context-aware humanization

---

## Step 3.1 — Implement Tonal Tension Computation

**Duration:** 4–5 days

### What and Why

Build a real-time tension calculation engine that scores any note or chord in harmonic context. This becomes the backbone for tension-curve-driven generation (Step 3.2), rejection sampling scoring (Step 3.2b), velocity shaping (Step 3.4), and optionally RL reward functions (Step 4.3). Three complementary models capture different dimensions of musical tension.

### Tasks

- [ ] **Implement Lerdahl's Tonal Pitch Space (TPS):**
  - Build the 5-level basic space: chromatic (12), diatonic (7), triadic (3), fifth (2), root (1)
  - Implement chord distance: δ(x,y) = sum of level differences
  - Implement key distance on circle of fifths
  - Use music21 pitch/interval primitives
  - Result: `tps_tension(pitch, chord, key) → float`

- [ ] **Implement Tonal Interval Vectors (TIV):**
  - Represent pitch class sets as 6-dimensional complex vectors in the Tonnetz
  - Compute diatonicity, chromaticity, dissonance from TIV magnitudes
  - Tension = distance from current key/chord center
  - Reference: Bernardes et al. (2016)
  - Result: `tiv_tension(pitch_class_set, reference_key) → float`

- [ ] **Train and integrate IDyOMpy (information-theoretic tension):**
  - Install IDyOMpy (Python reimplementation of IDyOM)
  - Train on the trance corpus from Step 2.1
  - Compute Information Content (surprisal) and entropy per note position
  - High IC = unexpected = tense; low IC = expected = resolved
  - **Fallback:** If IDyOMpy is unmaintained or incompatible, implement a simpler n-gram model trained on the corpus. Compute pitch bigram/trigram probabilities, surprisal = -log(P(note|context)). Gets 80% of the value with zero dependency risk
  - Result: `idyom_tension(note, preceding_context) → float`

- [ ] **Build unified tension function:**
  - `tension_score(note, chord, key, preceding_context) → float [0.0–1.0]`
  - Weighted combination: TPS (0.4), TIV (0.3), IDyOM/n-gram (0.3)
  - Calibrate weights by computing tension profiles on known trance melodies
  - Validate: breakdowns should score low, pre-drop builds should score high

### Implementation Notes

```python
from music21 import pitch, scale, chord as m21chord

class TonalPitchSpace:
    """Simplified Lerdahl TPS implementation."""

    def __init__(self, key_name='C', mode='major'):
        self.key = scale.MajorScale(key_name) if mode == 'major' \
                   else scale.MinorScale(key_name)
        self.tonic = pitch.Pitch(key_name)

    def basic_space_level(self, p):
        if p.name == self.tonic.name:
            return 0  # root — most stable
        fifth = self.tonic.transpose(7)
        if p.name == fifth.name:
            return 1  # fifth
        triad_pitches = [self.tonic.name,
                         self.tonic.transpose(3 if 'minor' in str(self.key) else 4).name,
                         fifth.name]
        if p.name in triad_pitches:
            return 2  # triadic
        scale_pitches = [sp.name for sp in self.key.getPitches()]
        if p.name in scale_pitches:
            return 3  # diatonic
        return 4  # chromatic — most unstable

    def tension(self, p):
        return self.basic_space_level(p) / 4.0


class TensionEngine:
    """Unified tension scoring combining multiple models."""

    def __init__(self, key_name, mode, corpus_path=None):
        self.tps = TonalPitchSpace(key_name, mode)
        self.tiv = TIVTension(key_name, mode)
        self.expectation = self._load_expectation_model(corpus_path)
        self.w_tps = 0.4
        self.w_tiv = 0.3
        self.w_expect = 0.3

    def _load_expectation_model(self, corpus_path):
        try:
            from idyompy import IDyOM
            model = IDyOM()
            model.train(corpus_path)
            return model
        except ImportError:
            # Fallback: n-gram model
            return NGramTensionModel(corpus_path)

    def score(self, note, chord, key, context):
        t_tps = self.tps.tension(note)
        t_tiv = self.tiv.tension(note, chord)
        t_expect = self.expectation.tension(note, context)
        return (self.w_tps * t_tps +
                self.w_tiv * t_tiv +
                self.w_expect * t_expect)
```

### Success Criteria

- Tension values correlate with musical intuition: tonic on strong beat ≈ 0.1–0.2, chromatic passing tone ≈ 0.6–0.8, tritone over dominant ≈ 0.8–0.9
- Tension profiles on 10 reference trance melodies show clear patterns aligned with structure
- Function runs <1ms per note (real-time capable)

---

## Step 3.2 — Tension Curve Planning and Constrained Generation

**Duration:** 5–7 days

### What and Why

Generate a tension trajectory *before* generating any notes, then constrain the melody generator to follow it. This creates section-level narrative arcs — tension rises through a buildup, peaks at the drop, recedes in the breakdown. Without this, melodies lack emotional direction regardless of note quality.

### Tasks

- [ ] **Define trance tension templates:**
  - Parametric curves for standard structures (intro, build, drop, breakdown, climax, outro)
  - User-adjustable control points
  - Cubic spline interpolation for smooth curves

- [ ] **Implement dual-level beam search:**
  - Token level: maintain top-K candidates (K=5–10) by model probability
  - Bar level: re-rank at bar boundaries by tension curve matching
  - Combined: `α * model_probability + (1-α) * tension_match` where α=0.6–0.8

- [ ] **Add tension_curve to the generation API:**
  ```python
  pipeline.generate(
      key="Am", bpm=140,
      chord_progression=["Am", "F", "C", "G"],
      bars=16,
      tension_curve=[0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.7, 0.5,
                     0.3, 0.4, 0.6, 0.8, 0.9, 1.0, 0.6, 0.3],
  )
  ```

- [ ] **Validate:** Pearson correlation >0.4 between input curve and generated melody tension profile

### Implementation Notes

```python
import numpy as np
from scipy.interpolate import CubicSpline

class TensionCurvePlanner:
    TRANCE_TEMPLATES = {
        'standard': {
            'intro':       [(0.0, 0.15), (1.0, 0.25)],
            'build':       [(0.0, 0.25), (0.5, 0.55), (1.0, 0.80)],
            'drop':        [(0.0, 0.85), (0.3, 0.90), (1.0, 0.80)],
            'breakdown':   [(0.0, 0.80), (0.3, 0.40), (1.0, 0.20)],
            'build2':      [(0.0, 0.20), (0.5, 0.60), (1.0, 0.90)],
            'climax_drop': [(0.0, 0.90), (0.3, 0.95), (0.7, 1.00), (1.0, 0.85)],
            'outro':       [(0.0, 0.50), (0.5, 0.30), (1.0, 0.10)],
        },
    }

    def generate_curve(self, sections, bars_per_section, resolution_per_bar=4):
        curve = []
        for section in sections:
            template = self.TRANCE_TEMPLATES['standard'][section]
            n_bars = bars_per_section[section]
            n_points = n_bars * resolution_per_bar
            fractions = [p[0] for p in template]
            tensions = [p[1] for p in template]
            cs = CubicSpline(fractions, tensions, bc_type='clamped')
            x = np.linspace(0, 1, n_points)
            section_curve = np.clip(cs(x), 0, 1)
            curve.extend(section_curve)
        return np.array(curve)
```

### Success Criteria

- Tension curves generate smoothly for all standard trance sections
- Beam search melodies correlate with input curves (Pearson r > 0.4)
- Breakdowns audibly feel "relaxed," builds feel "rising"
- Generation <15 seconds per 16-bar melody with beam search

---

## Step 3.2b — Rejection Sampling with Tension-Aware Scoring

**Duration:** 2–3 days

### What and Why

Before investing in RL (Step 4.3), implement the simpler approach: generate many candidates, score them with the full music theory + tension rule set, keep the best. This is embarrassingly simple and in practice delivers 80% of what RL provides with none of the instability. The pipeline already does candidate ranking (Step 1.7) — this upgrades the scoring function.

### Tasks

- [ ] **Upgrade the candidate scoring function** to include:
  - Scale compliance (from music21)
  - Chord-tone ratio on strong beats
  - Stepwise motion ratio
  - Tension curve correlation (from Step 3.1/3.2)
  - Self-similarity at 8-bar intervals
  - Resolution pattern detection (7→1, 4→3, 2→1)
  - Excessive repetition penalty (>4 consecutive same notes)
  - Register range adherence (C4–C6)

- [ ] **Implement generate-and-rerank:**
  ```python
  def generate_best(pipeline, params, n_candidates=20):
      candidates = [pipeline.generate_single(params) for _ in range(n_candidates)]
      scored = [(c, full_score(c, params)) for c in candidates]
      scored.sort(key=lambda x: x[1], reverse=True)
      return scored[0]
  ```

- [ ] **Tune number of candidates:** Test with N=10, 20, 50. Measure composite score improvement vs. generation time. Find the knee of the curve

- [ ] **Establish RL gate:** Record the best scores achievable with rejection sampling at N=50. If theory compliance is >95% and tension correlation is >0.5, RL (Step 4.3) is unnecessary

### Implementation Notes

```python
class FullScorer:
    """Comprehensive scoring for rejection sampling."""

    def __init__(self, key, scale_type, chord_progression, tension_curve,
                 tension_engine, reference_stats):
        self.key = key
        self.scale = build_scale(key, scale_type)
        self.chords = chord_progression
        self.tension_curve = tension_curve
        self.tension_engine = tension_engine
        self.reference_stats = reference_stats

    def score(self, melody_notes):
        scores = {}

        # Theory compliance
        scores['scale_compliance'] = self._scale_compliance(melody_notes)
        scores['chord_tone_strong'] = self._chord_tone_on_strong_beats(melody_notes)
        scores['stepwise_ratio'] = self._stepwise_motion_ratio(melody_notes)
        scores['resolution_patterns'] = self._count_resolutions(melody_notes)

        # Tension following
        actual_tension = [self.tension_engine.score_bar(bar)
                          for bar in split_into_bars(melody_notes)]
        scores['tension_correlation'] = np.corrcoef(
            actual_tension, self.tension_curve[:len(actual_tension)])[0, 1]

        # Structural quality
        scores['self_similarity_8'] = compute_self_similarity(melody_notes, 8)
        scores['repetition_penalty'] = self._excessive_repetition(melody_notes)
        scores['register_adherence'] = self._register_check(melody_notes)

        # Weighted composite
        weights = {
            'scale_compliance': 0.20,
            'chord_tone_strong': 0.15,
            'stepwise_ratio': 0.10,
            'resolution_patterns': 0.10,
            'tension_correlation': 0.20,
            'self_similarity_8': 0.10,
            'repetition_penalty': 0.10,
            'register_adherence': 0.05,
        }
        scores['composite'] = sum(scores[k] * weights[k] for k in weights)
        return scores
```

### Success Criteria

- Rejection sampling at N=20 improves composite score by ≥15% over single-shot generation
- Diminishing returns visible by N=50 (curve flattens)
- Theory compliance reaches 90%+ with N=20
- **RL gate recorded:** If N=50 achieves >95% compliance and >0.5 tension correlation, document that RL is not needed

---

## Step 3.3 — Long-Range Structure: Section-Level Planning

**Duration:** 4–5 days

### What and Why

Move from bar-by-bar generation to section-level composition. Plan the overall form — sections, motif assignments, transformations across sections — before generating any notes.

### Tasks

- [ ] **Build section planner** with trance arrangement templates:
  - Intro (16–32 bars): sparse, establishing key/motif
  - Build (16 bars): layered, rising energy
  - Drop (32 bars): full energy, main hook
  - Breakdown (16–32 bars): stripped, emotional
  - Second Build (16 bars): more intense
  - Climax Drop (32 bars): maximum energy
  - Outro (16–32 bars): mirror of intro

- [ ] **Motif assignment and transformation tracking:**
  - Assign primary (hook) and secondary (counter) motifs to sections
  - Track motif identity across sections using MusicVAE latent space
  - Same motif in drop vs. breakdown: controlled latent perturbation (noise varies by section)
  - Ensure motif A in climax drop is recognizably related to motif A in first drop

- [ ] **Self-similarity enforcement:**
  - Compute self-similarity matrices after generation
  - If repetition falls below reference corpus threshold, regenerate with constrained copy
  - Apply MusicVAE micro-variation to repeated phrases (noise_scale 0.05–0.15)

- [ ] **Structure API:**
  ```python
  pipeline.generate(
      structure=[
          {'section': 'intro', 'bars': 16, 'motif': 'A', 'variation': 0.1},
          {'section': 'build', 'bars': 16, 'motif': 'A', 'variation': 0.3},
          {'section': 'drop', 'bars': 32, 'motif': 'A', 'variation': 0.0},
          {'section': 'breakdown', 'bars': 16, 'motif': 'B', 'variation': 0.2},
          {'section': 'build2', 'bars': 16, 'motif': 'A', 'variation': 0.4},
          {'section': 'climax', 'bars': 32, 'motif': 'A', 'variation': 0.15},
      ]
  )
  ```

### Success Criteria

- Generated 128+ bar arrangements have audible section contrast
- Self-similarity matrices show repetition patterns matching reference trance
- Motif identity preserved across sections (the hook is recognizable in both drops)
- Section transitions don't have jarring discontinuities

---

## Step 3.4 — Advanced Humanization: Beyond Random Jitter

**Duration:** 4–6 days

### What and Why

Replace random timing/velocity offsets with context-aware humanization that correlates timing, velocity, and articulation with harmonic and melodic context. At 138–145 BPM, most humanization in trance comes through velocity variation and note duration, not timing offsets.

### Tasks

- [ ] **Rule-based expressive mapping** (no ML needed):
  - Ascending passages: accelerate +2–5ms, crescendo +3–5 velocity
  - Accented beats (1 and 3): arrive early -5–10ms, louder +10–20 velocity
  - Phrase endings: decelerate, decrescendo
  - Melodic peaks: louder +10–15 velocity, slightly early -5ms
  - Repeated notes: slight velocity decrease (anti-machine-gun)

- [ ] **Tension-driven velocity curves:**
  - `velocity = base_velocity + tension_score * dynamic_range`
  - High tension → higher average velocity + wider dynamics
  - Low tension → softer + more uniform

- [ ] **GrooVAE integration** (drums only, if applicable):
  - `groovae_2bar_humanize` model from Magenta
  - Outputs learned timing + velocity variations

- [ ] **Trance-specific constraints:**
  - 16th note = 103–109ms at 138–145 BPM
  - Timing deviations: ±2–5ms maximum (tighter than most genres)
  - Zero swing (trance is straight 16ths)
  - Breakdown: legato (90–100% duration), Drop: staccato (60–80%)

- [ ] **Correlated parameter mapping:**
  ```python
  def humanize_note(note, context):
      timing_offset = 0
      velocity_offset = 0
      duration_factor = 1.0

      if context.melodic_direction > 0:  # ascending
          timing_offset -= 2
          velocity_offset += 3
      if context.is_local_maximum:  # melodic peak
          timing_offset -= 5
          velocity_offset += 12

      velocity_offset += int(context.tension_score * 20)
      duration_factor = 0.6 + (1.0 - context.tension_score) * 0.35

      return timing_offset, velocity_offset, duration_factor
  ```

### Success Criteria

- A/B listening: humanized output sounds more "alive" than grid-quantized
- Velocity curves visually follow tension shape in DAW piano roll
- No audible timing artifacts at 140 BPM
- **Phase 3 Gate:** Run human listening test. If structured + humanized melodies win >70% vs. Phase 2 output, proceed to Phase 4. Otherwise, iterate on Phase 3 or declare production-ready
