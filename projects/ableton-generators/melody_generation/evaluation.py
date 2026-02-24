"""
Melody evaluation framework for the ML-enhanced generation pipeline.

Computes automated quality metrics for generated melodies, compares
against a reference corpus, and produces composite scores for phase
gate decisions (Phase 1 Step 1.6).

Works with two input formats:
  1. NoteEvent lists (from the generator directly)
  2. MIDI files (from external sources or decoded tokens)

Metrics follow the specification in EVALUATION.md:
  - Core metrics: pitch entropy, pitch range, chord-tone ratio,
    self-similarity, stepwise motion, nPVI, KL-divergence, resolution patterns
  - Trance-specific: minor-key adherence, phrase regularity,
    hook memorability, register consistency

Usage:
    from melody_generation.evaluation import (
        evaluate_melody,
        evaluate_midi,
        compute_reference_stats,
        compare_baselines,
        MelodyMetrics,
    )

    # Evaluate a NoteEvent list
    metrics = evaluate_melody(notes, key="A", scale="minor",
                              chord_events=chord_events)
    print(f"Composite: {metrics.composite:.3f}")
    print(f"Chord-tone ratio: {metrics.chord_tone_ratio:.1%}")

    # Evaluate a MIDI file
    metrics = evaluate_midi("melody.mid")

    # Build reference corpus stats
    ref_stats = compute_reference_stats(["ref1.mid", "ref2.mid", ...])
    ref_stats.save("reference_stats.json")

    # Compare two sets of metrics
    report = compare_baselines(phase1_metrics, phase2_metrics, ref_stats)
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from .models import (
    NoteEvent,
    ChordEvent,
    Pitch,
    PitchClass,
    TensionLevel,
)


# ---------------------------------------------------------------------------
# Metric weights (from EVALUATION.md)
# ---------------------------------------------------------------------------

METRIC_WEIGHTS = {
    "pitch_entropy": 0.10,
    "pitch_range_octaves": 0.05,
    "chord_tone_ratio": 0.20,
    "self_similarity_8bar": 0.10,
    "self_similarity_16bar": 0.05,
    "stepwise_motion_ratio": 0.10,
    "npvi": 0.05,
    "kl_vs_reference": 0.15,
    "tension_correlation": 0.15,
    "resolution_patterns": 0.05,
}

# Target ranges for trance melodies (from plan)
TRANCE_TARGETS = {
    "pitch_entropy": (2.5, 3.0),
    "pitch_range_octaves": (1.5, 2.5),
    "chord_tone_ratio": (0.80, 1.0),
    "self_similarity_8bar": (0.6, 1.0),
    "self_similarity_16bar": (0.4, 1.0),
    "stepwise_motion_ratio": (0.60, 1.0),
    "npvi": (30.0, 60.0),
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MelodyMetrics:
    """Complete metrics for a single melody."""
    # Core metrics
    pitch_entropy: float = 0.0
    pitch_range_octaves: float = 0.0
    chord_tone_ratio: float = 0.0
    self_similarity_8bar: float = 0.0
    self_similarity_16bar: float = 0.0
    stepwise_motion_ratio: float = 0.0
    npvi: float = 0.0
    kl_vs_reference: float = 0.0
    tension_correlation: float = 0.0
    resolution_patterns: float = 0.0

    # Trance-specific metrics
    minor_key_adherence: float = 0.0
    phrase_regularity: float = 0.0
    hook_memorability: float = 0.0
    register_consistency: float = 0.0

    # Composite score
    composite: float = 0.0

    # Metadata
    num_notes: int = 0
    duration_beats: float = 0.0
    pitch_class_histogram: List[float] = field(default_factory=lambda: [0.0] * 12)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MelodyMetrics":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class ReferenceStats:
    """Aggregate statistics from a reference corpus."""
    num_files: int = 0
    pitch_class_histogram: List[float] = field(default_factory=lambda: [0.0] * 12)

    # Per-metric distributions
    means: Dict[str, float] = field(default_factory=dict)
    stds: Dict[str, float] = field(default_factory=dict)
    percentiles: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def save(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "ReferenceStats":
        with open(path) as f:
            return cls(**json.load(f))


@dataclass
class ComparisonReport:
    """Results of comparing two sets of metrics."""
    metrics_a_name: str
    metrics_b_name: str
    per_metric: Dict[str, Dict[str, float]] = field(default_factory=dict)
    composite_improvement: float = 0.0
    significant_improvements: int = 0
    significant_regressions: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core metric computations
# ---------------------------------------------------------------------------

def _pitch_entropy(pitches: List[int]) -> float:
    """Shannon entropy of pitch distribution (bits)."""
    if not pitches:
        return 0.0
    counts = Counter(pitches)
    total = len(pitches)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def _pitch_class_histogram(pitches: List[int]) -> List[float]:
    """Normalized 12-bin pitch class histogram."""
    if not pitches:
        return [0.0] * 12
    counts = [0] * 12
    for p in pitches:
        counts[p % 12] += 1
    total = sum(counts)
    if total == 0:
        return [0.0] * 12
    return [c / total for c in counts]


def _pitch_range_octaves(pitches: List[int]) -> float:
    """Range of pitches in octaves."""
    if not pitches:
        return 0.0
    return (max(pitches) - min(pitches)) / 12.0


def _chord_tone_ratio(
    notes: List[NoteEvent],
    chord_events: Optional[List[ChordEvent]] = None,
) -> float:
    """
    Fraction of notes that are chord tones.

    If NoteEvent has .chord_tone already set (from generator annotation),
    uses that directly. Otherwise, checks against provided chord_events.
    """
    if not notes:
        return 0.0

    # Try annotation first
    annotated = [n for n in notes if n.chord_tone is not None]
    if annotated and len(annotated) == len(notes):
        return sum(1 for n in notes if n.chord_tone) / len(notes)

    # Fall back to chord_events
    if not chord_events:
        return 0.0

    chord_tones = 0
    for note in notes:
        beat = note.start_beat
        for ce in chord_events:
            if ce.start_beat <= beat < ce.end_beat:
                if ce.chord.contains_pitch(note.pitch.pitch_class):
                    chord_tones += 1
                break

    return chord_tones / len(notes)


def _self_similarity(notes: List[NoteEvent], bars: int, bpm: float = 140.0) -> float:
    """
    Self-similarity: cosine similarity between consecutive N-bar chunks.

    Uses a 12-bin pitch class chroma vector per chunk.
    """
    if not notes:
        return 0.0

    beats_per_bar = 4.0
    beats_per_chunk = bars * beats_per_bar

    # Determine total duration
    max_beat = max(n.end_beat for n in notes)
    num_chunks = int(max_beat / beats_per_chunk)

    if num_chunks < 2:
        return 0.0

    # Build chroma vectors per chunk
    chromas = []
    for chunk_idx in range(num_chunks):
        start = chunk_idx * beats_per_chunk
        end = start + beats_per_chunk
        chunk_pitches = [
            n.pitch.midi_note % 12
            for n in notes
            if start <= n.start_beat < end
        ]
        chroma = [0.0] * 12
        for p in chunk_pitches:
            chroma[p] += 1.0
        total = sum(chroma)
        if total > 0:
            chroma = [c / total for c in chroma]
        chromas.append(chroma)

    # Average cosine similarity between consecutive chunks
    similarities = []
    for i in range(len(chromas) - 1):
        a = np.array(chromas[i])
        b = np.array(chromas[i + 1])
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a > 0 and norm_b > 0:
            similarities.append(float(np.dot(a, b) / (norm_a * norm_b)))

    return float(np.mean(similarities)) if similarities else 0.0


def _stepwise_motion_ratio(pitches: List[int]) -> float:
    """Fraction of intervals that are stepwise (≤ 2 semitones)."""
    if len(pitches) < 2:
        return 0.0
    intervals = [abs(pitches[i + 1] - pitches[i]) for i in range(len(pitches) - 1)]
    stepwise = sum(1 for iv in intervals if iv <= 2)
    return stepwise / len(intervals)


def _npvi(durations: List[float]) -> float:
    """
    Normalized Pairwise Variability Index.

    Measures rhythmic variability. Values:
      0 = perfectly uniform durations
      100+ = extreme variability
    Trance target: 30–60
    """
    if len(durations) < 2:
        return 0.0

    pairs = 0
    total = 0.0
    for i in range(len(durations) - 1):
        d1 = durations[i]
        d2 = durations[i + 1]
        denom = (d1 + d2) / 2.0
        if denom > 0:
            total += abs(d1 - d2) / denom
            pairs += 1

    if pairs == 0:
        return 0.0
    return 100.0 * total / pairs


def _kl_divergence(p: List[float], q: List[float], epsilon: float = 1e-10) -> float:
    """
    KL divergence D(P || Q).

    Lower is better (P is the generated melody, Q is the reference).
    """
    kl = 0.0
    for pi, qi in zip(p, q):
        pi = max(pi, epsilon)
        qi = max(qi, epsilon)
        kl += pi * math.log2(pi / qi)
    return max(0.0, kl)


def _tension_correlation(
    notes: List[NoteEvent],
    target_tension: Optional[List[float]] = None,
) -> float:
    """
    Pearson correlation between actual note tension and target tension curve.

    If no target is provided or notes lack tension annotations, returns 0.
    """
    if not target_tension or not notes:
        return 0.0

    # Map actual tension levels to numeric values
    tension_map = {
        TensionLevel.STABLE: 0.0,
        TensionLevel.MILD: 0.25,
        TensionLevel.MODERATE: 0.5,
        TensionLevel.HIGH: 0.75,
        TensionLevel.CHROMATIC: 1.0,
    }

    actual = [tension_map.get(n.tension_level, 0.5) for n in notes]

    # Resample target to match note count
    if len(target_tension) != len(actual):
        indices = np.linspace(0, len(target_tension) - 1, len(actual))
        target_resampled = np.interp(indices, range(len(target_tension)), target_tension)
    else:
        target_resampled = np.array(target_tension)

    actual_arr = np.array(actual)

    # Pearson correlation
    if np.std(actual_arr) == 0 or np.std(target_resampled) == 0:
        return 0.0

    corr = float(np.corrcoef(actual_arr, target_resampled)[0, 1])
    return corr if not math.isnan(corr) else 0.0


def _resolution_patterns(notes: List[NoteEvent]) -> float:
    """
    Count standard resolution patterns per 8 bars.

    Looks for scale degree movements: 7→1, 4→3, 2→1 (common tonal resolutions).
    """
    if len(notes) < 2:
        return 0.0

    resolution_pairs = {(7, 1), (4, 3), (2, 1)}
    resolutions = 0

    for i in range(len(notes) - 1):
        sd1 = notes[i].scale_degree
        sd2 = notes[i + 1].scale_degree
        if sd1 is not None and sd2 is not None:
            if (sd1, sd2) in resolution_pairs:
                resolutions += 1

    # Normalize per 8 bars
    max_beat = max(n.end_beat for n in notes) if notes else 0
    num_8bar_chunks = max(1, max_beat / 32.0)
    return resolutions / num_8bar_chunks


# ---------------------------------------------------------------------------
# Trance-specific metrics
# ---------------------------------------------------------------------------

def _minor_key_adherence(
    pitches: List[int],
    key_root: int = 9,  # A = 9
) -> float:
    """
    Fraction of notes in the natural or harmonic minor scale.

    Natural minor: 0, 2, 3, 5, 7, 8, 10
    Harmonic minor: 0, 2, 3, 5, 7, 8, 11
    Union: 0, 2, 3, 5, 7, 8, 10, 11
    """
    if not pitches:
        return 0.0

    minor_intervals = {0, 2, 3, 5, 7, 8, 10, 11}  # union of natural + harmonic
    in_scale = 0
    for p in pitches:
        interval = (p - key_root) % 12
        if interval in minor_intervals:
            in_scale += 1

    return in_scale / len(pitches)


def _phrase_regularity(notes: List[NoteEvent]) -> float:
    """
    How well note onsets align to 4/8/16-bar phrase boundaries.

    Measures onset density near boundaries vs. mid-phrase.
    Higher = more phrase-regular (trance is highly regular).
    """
    if not notes:
        return 0.0

    onsets = [n.start_beat for n in notes]
    max_beat = max(n.end_beat for n in notes)

    # Check density of onsets near bar boundaries (beat 0 of each 4-bar group)
    boundary_proximity = 0
    for onset in onsets:
        # Distance to nearest 4-bar boundary
        nearest_boundary = round(onset / 16.0) * 16.0
        distance = abs(onset - nearest_boundary)
        if distance < 1.0:  # within 1 beat of boundary
            boundary_proximity += 1

    # Normalize: in a perfectly regular melody, ~25% of notes start
    # near 4-bar boundaries
    expected_ratio = 0.25
    actual_ratio = boundary_proximity / len(onsets) if onsets else 0
    # Score: 1.0 if ratio >= expected, proportional below
    return min(1.0, actual_ratio / expected_ratio) if expected_ratio > 0 else 0.0


def _hook_memorability(notes: List[NoteEvent], bpm: float = 140.0) -> float:
    """
    Self-similarity of the first 4 bars against later occurrences.

    High score = the opening motif recurs later (hook-based writing).
    """
    if not notes:
        return 0.0

    beats_per_bar = 4.0
    hook_end = 4 * beats_per_bar  # first 4 bars
    max_beat = max(n.end_beat for n in notes)

    # Build chroma of first 4 bars
    hook_pitches = [n.pitch.midi_note % 12 for n in notes if n.start_beat < hook_end]
    if not hook_pitches:
        return 0.0

    hook_chroma = [0.0] * 12
    for p in hook_pitches:
        hook_chroma[p] += 1.0
    total = sum(hook_chroma)
    if total > 0:
        hook_chroma = [c / total for c in hook_chroma]

    # Compare against each subsequent 4-bar chunk
    similarities = []
    chunk_start = hook_end
    while chunk_start + hook_end <= max_beat:
        chunk_pitches = [
            n.pitch.midi_note % 12
            for n in notes
            if chunk_start <= n.start_beat < chunk_start + hook_end
        ]
        if chunk_pitches:
            chunk_chroma = [0.0] * 12
            for p in chunk_pitches:
                chunk_chroma[p] += 1.0
            total = sum(chunk_chroma)
            if total > 0:
                chunk_chroma = [c / total for c in chunk_chroma]

            a = np.array(hook_chroma)
            b = np.array(chunk_chroma)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a > 0 and norm_b > 0:
                similarities.append(float(np.dot(a, b) / (norm_a * norm_b)))

        chunk_start += hook_end

    return float(np.mean(similarities)) if similarities else 0.0


def _register_consistency(pitches: List[int]) -> float:
    """
    Register consistency: inverse of pitch standard deviation.

    Low std = consistent register (typical of trance leads).
    Normalized to 0–1 where 1 = very consistent.
    """
    if len(pitches) < 2:
        return 0.0

    std = float(np.std(pitches))
    # Normalize: 0 semitones std → 1.0, 24 semitones std → 0.0
    return max(0.0, 1.0 - std / 24.0)


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------

def _in_range_score(value: float, target_range: Tuple[float, float]) -> float:
    """
    Score how well a value falls within a target range.

    Returns 1.0 if in range, decays linearly outside.
    """
    low, high = target_range
    if low <= value <= high:
        return 1.0
    elif value < low:
        # How far below? Decay to 0 at 2x distance
        distance = low - value
        span = high - low if high > low else 1.0
        return max(0.0, 1.0 - distance / span)
    else:
        distance = value - high
        span = high - low if high > low else 1.0
        return max(0.0, 1.0 - distance / span)


def _compute_composite(
    metrics: MelodyMetrics,
    reference_stats: Optional[ReferenceStats] = None,
) -> float:
    """
    Compute weighted composite score normalized to [0, 1].

    Uses target ranges for metrics with known ranges, and
    reference corpus statistics for relative metrics.
    """
    scores = {}

    # Metrics with known target ranges
    for metric_name, target in TRANCE_TARGETS.items():
        value = getattr(metrics, metric_name, 0.0)
        scores[metric_name] = _in_range_score(value, target)

    # KL divergence: lower is better, score = 1 / (1 + kl)
    scores["kl_vs_reference"] = 1.0 / (1.0 + metrics.kl_vs_reference)

    # Tension correlation: map [-1, 1] to [0, 1]
    scores["tension_correlation"] = max(0.0, (metrics.tension_correlation + 1.0) / 2.0)

    # Resolution patterns: 1+ per 8 bars is good
    scores["resolution_patterns"] = min(1.0, metrics.resolution_patterns)

    # Weighted sum
    total = 0.0
    weight_sum = 0.0
    for metric_name, weight in METRIC_WEIGHTS.items():
        if metric_name in scores:
            total += weight * scores[metric_name]
            weight_sum += weight

    return total / weight_sum if weight_sum > 0 else 0.0


# ---------------------------------------------------------------------------
# Main evaluation functions
# ---------------------------------------------------------------------------

def evaluate_melody(
    notes: List[NoteEvent],
    key: str = "A",
    scale: str = "minor",
    chord_events: Optional[List[ChordEvent]] = None,
    target_tension: Optional[List[float]] = None,
    reference_stats: Optional[ReferenceStats] = None,
    bpm: float = 140.0,
) -> MelodyMetrics:
    """
    Evaluate a melody (NoteEvent list) on all metrics.

    Args:
        notes: Generated melody as NoteEvent list
        key: Key root name (e.g., "A")
        scale: Scale type (e.g., "minor")
        chord_events: Chord progression for chord-tone analysis
        target_tension: Target tension curve for correlation
        reference_stats: Reference corpus stats for KL divergence
        bpm: Tempo (for time-based calculations)

    Returns:
        MelodyMetrics with all scores computed
    """
    if not notes:
        return MelodyMetrics()

    # Extract raw data
    pitches = [n.pitch.midi_note for n in notes]
    durations = [n.duration_beats for n in notes]
    key_root = PitchClass.from_name(key).value

    # Reference pitch class histogram (use reference or uniform)
    ref_pc_hist = [1.0 / 12] * 12
    if reference_stats and reference_stats.pitch_class_histogram:
        ref_pc_hist = reference_stats.pitch_class_histogram

    pc_hist = _pitch_class_histogram(pitches)

    metrics = MelodyMetrics(
        # Core metrics
        pitch_entropy=_pitch_entropy(pitches),
        pitch_range_octaves=_pitch_range_octaves(pitches),
        chord_tone_ratio=_chord_tone_ratio(notes, chord_events),
        self_similarity_8bar=_self_similarity(notes, bars=8, bpm=bpm),
        self_similarity_16bar=_self_similarity(notes, bars=16, bpm=bpm),
        stepwise_motion_ratio=_stepwise_motion_ratio(pitches),
        npvi=_npvi(durations),
        kl_vs_reference=_kl_divergence(pc_hist, ref_pc_hist),
        tension_correlation=_tension_correlation(notes, target_tension),
        resolution_patterns=_resolution_patterns(notes),

        # Trance-specific
        minor_key_adherence=_minor_key_adherence(pitches, key_root),
        phrase_regularity=_phrase_regularity(notes),
        hook_memorability=_hook_memorability(notes, bpm),
        register_consistency=_register_consistency(pitches),

        # Metadata
        num_notes=len(notes),
        duration_beats=max(n.end_beat for n in notes),
        pitch_class_histogram=pc_hist,
    )

    metrics.composite = _compute_composite(metrics, reference_stats)
    return metrics


def evaluate_midi(
    midi_path: str | Path,
    key: str = "A",
    scale: str = "minor",
    reference_stats: Optional[ReferenceStats] = None,
    bpm: Optional[float] = None,
) -> MelodyMetrics:
    """
    Evaluate a MIDI file on all metrics.

    Args:
        midi_path: Path to MIDI file
        key: Key root name
        scale: Scale type
        reference_stats: Reference corpus stats
        bpm: Override tempo

    Returns:
        MelodyMetrics with all scores computed
    """
    from .tokenizer import midi_to_notes
    notes = midi_to_notes(midi_path, bpm=bpm)
    return evaluate_melody(
        notes, key=key, scale=scale,
        reference_stats=reference_stats,
        bpm=bpm or 140.0,
    )


# ---------------------------------------------------------------------------
# Reference corpus
# ---------------------------------------------------------------------------

def compute_reference_stats(
    midi_paths: List[str | Path],
    key: str = "A",
    scale: str = "minor",
    bpm: Optional[float] = None,
) -> ReferenceStats:
    """
    Compute aggregate statistics from a reference corpus.

    Args:
        midi_paths: List of MIDI file paths
        key: Key root name (assumed same for all)
        scale: Scale type
        bpm: Override tempo

    Returns:
        ReferenceStats with means, stds, percentiles
    """
    all_metrics: List[MelodyMetrics] = []
    all_pc_hists: List[List[float]] = []

    for path in midi_paths:
        try:
            m = evaluate_midi(path, key=key, scale=scale, bpm=bpm)
            all_metrics.append(m)
            all_pc_hists.append(m.pitch_class_histogram)
        except Exception as e:
            print(f"Warning: failed to evaluate {path}: {e}")

    if not all_metrics:
        return ReferenceStats()

    # Average pitch class histogram
    avg_pc_hist = [0.0] * 12
    for hist in all_pc_hists:
        for i in range(12):
            avg_pc_hist[i] += hist[i]
    total = sum(avg_pc_hist)
    if total > 0:
        avg_pc_hist = [h / total for h in avg_pc_hist]

    # Per-metric statistics
    metric_names = [
        "pitch_entropy", "pitch_range_octaves", "chord_tone_ratio",
        "self_similarity_8bar", "self_similarity_16bar",
        "stepwise_motion_ratio", "npvi", "kl_vs_reference",
        "tension_correlation", "resolution_patterns",
        "minor_key_adherence", "phrase_regularity",
        "hook_memorability", "register_consistency", "composite",
    ]

    means = {}
    stds = {}
    percentiles = {}

    for name in metric_names:
        values = [getattr(m, name, 0.0) for m in all_metrics]
        arr = np.array(values)
        means[name] = float(np.mean(arr))
        stds[name] = float(np.std(arr))
        percentiles[name] = {
            "p10": float(np.percentile(arr, 10)),
            "p25": float(np.percentile(arr, 25)),
            "p50": float(np.percentile(arr, 50)),
            "p75": float(np.percentile(arr, 75)),
            "p90": float(np.percentile(arr, 90)),
        }

    return ReferenceStats(
        num_files=len(all_metrics),
        pitch_class_histogram=avg_pc_hist,
        means=means,
        stds=stds,
        percentiles=percentiles,
    )


# ---------------------------------------------------------------------------
# Baseline comparison
# ---------------------------------------------------------------------------

def compare_baselines(
    metrics_a: List[MelodyMetrics],
    metrics_b: List[MelodyMetrics],
    reference_stats: Optional[ReferenceStats] = None,
    name_a: str = "Baseline A",
    name_b: str = "Baseline B",
) -> ComparisonReport:
    """
    Compare two sets of metrics with statistical tests.

    Args:
        metrics_a: First set of melody metrics
        metrics_b: Second set of melody metrics
        reference_stats: Reference corpus (for context)
        name_a: Label for first set
        name_b: Label for second set

    Returns:
        ComparisonReport with per-metric comparisons
    """
    metric_names = [
        "pitch_entropy", "pitch_range_octaves", "chord_tone_ratio",
        "self_similarity_8bar", "self_similarity_16bar",
        "stepwise_motion_ratio", "npvi", "composite",
    ]

    per_metric = {}
    sig_improvements = 0
    sig_regressions = 0

    for name in metric_names:
        values_a = np.array([getattr(m, name, 0.0) for m in metrics_a])
        values_b = np.array([getattr(m, name, 0.0) for m in metrics_b])

        mean_a = float(np.mean(values_a))
        mean_b = float(np.mean(values_b))
        improvement = (mean_b - mean_a) / mean_a if mean_a != 0 else 0.0

        # Simple significance test: non-overlapping confidence intervals
        # (approximation when scipy is not available)
        std_a = float(np.std(values_a))
        std_b = float(np.std(values_b))
        n_a = len(values_a)
        n_b = len(values_b)

        se_diff = math.sqrt(
            (std_a ** 2 / max(n_a, 1)) + (std_b ** 2 / max(n_b, 1))
        )
        # Z-score for difference
        z = abs(mean_b - mean_a) / se_diff if se_diff > 0 else 0.0
        p_approx = 2.0 * (1.0 - _normal_cdf(z))  # two-tailed

        per_metric[name] = {
            "mean_a": mean_a,
            "mean_b": mean_b,
            "improvement": improvement,
            "p_value_approx": p_approx,
            "significant": p_approx < 0.05,
        }

        if p_approx < 0.05:
            if mean_b > mean_a:
                sig_improvements += 1
            else:
                sig_regressions += 1

    # Composite improvement
    comp_a = float(np.mean([m.composite for m in metrics_a]))
    comp_b = float(np.mean([m.composite for m in metrics_b]))
    comp_improvement = (comp_b - comp_a) / comp_a if comp_a != 0 else 0.0

    return ComparisonReport(
        metrics_a_name=name_a,
        metrics_b_name=name_b,
        per_metric=per_metric,
        composite_improvement=comp_improvement,
        significant_improvements=sig_improvements,
        significant_regressions=sig_regressions,
    )


def _normal_cdf(z: float) -> float:
    """Approximate standard normal CDF (no scipy needed)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ---------------------------------------------------------------------------
# Batch evaluation utilities
# ---------------------------------------------------------------------------

def evaluate_batch(
    note_lists: List[List[NoteEvent]],
    key: str = "A",
    scale: str = "minor",
    reference_stats: Optional[ReferenceStats] = None,
    bpm: float = 140.0,
) -> List[MelodyMetrics]:
    """Evaluate a batch of melodies."""
    return [
        evaluate_melody(notes, key=key, scale=scale,
                        reference_stats=reference_stats, bpm=bpm)
        for notes in note_lists
    ]


def save_baseline(
    metrics: List[MelodyMetrics],
    path: str | Path,
    label: str = "",
):
    """Save a set of metrics as a baseline JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "label": label,
        "num_melodies": len(metrics),
        "metrics": [m.to_dict() for m in metrics],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_baseline(path: str | Path) -> List[MelodyMetrics]:
    """Load a baseline from JSON."""
    with open(path) as f:
        data = json.load(f)
    return [MelodyMetrics.from_dict(m) for m in data["metrics"]]


def print_metrics(metrics: MelodyMetrics, label: str = "Melody"):
    """Pretty-print a MelodyMetrics summary."""
    print(f"\n{'=' * 50}")
    print(f"  {label}")
    print(f"{'=' * 50}")
    print(f"  Notes: {metrics.num_notes}  |  Duration: {metrics.duration_beats:.1f} beats")
    print(f"  Composite Score: {metrics.composite:.3f}")
    print(f"{'─' * 50}")
    print(f"  {'Metric':<28} {'Value':>8}  {'Target':>12}")
    print(f"{'─' * 50}")

    rows = [
        ("Pitch entropy", f"{metrics.pitch_entropy:.2f}", "2.5–3.0"),
        ("Pitch range (oct)", f"{metrics.pitch_range_octaves:.2f}", "1.5–2.5"),
        ("Chord-tone ratio", f"{metrics.chord_tone_ratio:.1%}", ">80%"),
        ("Self-sim (8-bar)", f"{metrics.self_similarity_8bar:.2f}", ">0.6"),
        ("Self-sim (16-bar)", f"{metrics.self_similarity_16bar:.2f}", ">0.4"),
        ("Stepwise motion", f"{metrics.stepwise_motion_ratio:.1%}", ">60%"),
        ("nPVI", f"{metrics.npvi:.1f}", "30–60"),
        ("KL vs reference", f"{metrics.kl_vs_reference:.3f}", "lower"),
        ("Tension corr.", f"{metrics.tension_correlation:.2f}", ">0.4"),
        ("Resolutions/8bar", f"{metrics.resolution_patterns:.2f}", ">1"),
        ("Minor adherence", f"{metrics.minor_key_adherence:.1%}", ">90%"),
        ("Phrase regularity", f"{metrics.phrase_regularity:.2f}", "high"),
        ("Hook memorability", f"{metrics.hook_memorability:.2f}", "high"),
        ("Register consistency", f"{metrics.register_consistency:.2f}", "high"),
    ]

    for name, value, target in rows:
        print(f"  {name:<28} {value:>8}  {target:>12}")

    print(f"{'=' * 50}\n")
