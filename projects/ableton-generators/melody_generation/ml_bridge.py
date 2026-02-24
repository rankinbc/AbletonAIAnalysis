"""
ML Bridge — connects the Docker Magenta service to the melody pipeline.

Phase 1 Steps 1.4 (Improv RNN) and 1.5 (MusicVAE) integration.

This module provides:
  1. MLMelodyGenerator — generates melody candidates via Improv RNN,
     validates with music21, scores with the evaluation framework,
     and returns the best candidate as NoteEvents.
  2. MLMotifVariator — creates motif variations via MusicVAE.
  3. MotifSimilarityIndex — encodes motifs to latent vectors for
     context-aware retrieval.

The rule engine is never bypassed — it serves as the constraint layer.
ML models propose candidates; the rule engine validates; the evaluation
framework scores; the best candidate wins.

Usage:
    from melody_generation.ml_bridge import (
        MLMelodyGenerator,
        MLMotifVariator,
        MotifSimilarityIndex,
    )

    # Generate chord-conditioned melodies (Step 1.4)
    ml_gen = MLMelodyGenerator()
    notes = ml_gen.generate(
        chords=["Am", "F", "C", "G"],
        bars=8, bpm=140, num_candidates=5,
    )

    # Vary a motif (Step 1.5)
    variator = MLMotifVariator()
    variants = variator.vary(motif_notes, num_variants=4, noise_scale=0.3)

    # Build similarity index (Step 1.5)
    index = MotifSimilarityIndex()
    index.add("motif_a.mid", metadata={"section": "drop", "energy": 0.9})
    index.build()
    similar = index.find_similar("query.mid", n=5)
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from .models import (
    NoteEvent,
    Pitch,
    PitchClass,
    ChordEvent,
    TensionLevel,
)
from .tokenizer import notes_to_midi, midi_to_notes
from .evaluation import evaluate_melody, MelodyMetrics


# ---------------------------------------------------------------------------
# Docker Magenta availability check
# ---------------------------------------------------------------------------

def _get_docker_magenta(**kwargs):
    """
    Import and instantiate DockerMagenta.

    Raises ImportError with helpful message if not available.
    """
    try:
        from shared.magenta import DockerMagenta, is_docker_available, is_magenta_image_available
    except ImportError:
        raise ImportError(
            "shared.magenta is not importable. Ensure the shared/ directory "
            "is on your Python path. From the project root:\n"
            "  export PYTHONPATH=$PYTHONPATH:$(pwd)"
        )

    if not is_docker_available():
        raise RuntimeError(
            "Docker is not available. Install Docker Desktop and ensure "
            "the Docker daemon is running."
        )

    if not is_magenta_image_available():
        raise RuntimeError(
            "The magenta:latest Docker image is not built. Build it with:\n"
            "  cd shared/magenta && docker build -t magenta:latest ."
        )

    return DockerMagenta(**kwargs)


# ---------------------------------------------------------------------------
# Step 1.4 — ML Melody Generation (Improv RNN + Attention RNN)
# ---------------------------------------------------------------------------

@dataclass
class CandidateResult:
    """A scored melody candidate from ML generation."""
    notes: List[NoteEvent]
    midi_path: Path
    metrics: MelodyMetrics
    source: str  # "improv_rnn", "attention_rnn", "rule_engine"
    scale_compliance: float = 0.0


class MLMelodyGenerator:
    """
    Generate melody candidates using Magenta models, validate with
    the harmonic engine, and score with the evaluation framework.

    Pipeline:
    1. Improv RNN generates N chord-conditioned candidates
    2. music21-based HarmonicEngine validates scale/key compliance
    3. Evaluation framework scores each candidate
    4. Best candidate is returned as NoteEvent list

    Falls back to rule-based generation if Docker/Magenta is unavailable.

    Usage:
        gen = MLMelodyGenerator()
        result = gen.generate(
            chords=["Am", "F", "C", "G"],
            bars=8, bpm=140, num_candidates=5,
        )
        print(f"Best score: {result.metrics.composite:.3f}")
        print(f"Source: {result.source}")
        for note in result.notes[:5]:
            print(f"  {note.pitch.to_name()} at beat {note.start_beat}")
    """

    def __init__(
        self,
        key: str = "A",
        scale: str = "minor",
        output_dir: Optional[Path] = None,
        use_gpu: bool = False,
        verbose: bool = False,
    ):
        self.key = key
        self.scale = scale
        self.key_root = PitchClass.from_name(key).value
        self.output_dir = output_dir
        self.use_gpu = use_gpu
        self.verbose = verbose

        # Lazy-loaded
        self._magenta = None
        self._harmonic = None

    def _get_magenta(self):
        if self._magenta is None:
            self._magenta = _get_docker_magenta(
                output_dir=self.output_dir,
                use_gpu=self.use_gpu,
                verbose=self.verbose,
            )
        return self._magenta

    def _get_harmonic(self):
        if self._harmonic is None:
            from .harmonic_engine import HarmonicEngine
            self._harmonic = HarmonicEngine(
                PitchClass.from_name(self.key), self.scale
            )
        return self._harmonic

    def generate(
        self,
        chords: List[str],
        bars: int = 8,
        bpm: float = 140.0,
        temperature: float = 1.0,
        num_candidates: int = 5,
        min_scale_compliance: float = 0.65,
        model: str = "improv_rnn",
        timeout: int = 120,
    ) -> CandidateResult:
        """
        Generate and score melody candidates.

        Args:
            chords: Chord symbols, e.g. ["Am", "F", "C", "G"]
            bars: Number of bars
            bpm: Tempo
            temperature: Sampling temperature (0.5=safe, 1.5=wild)
            num_candidates: Number of candidates to generate and rank
            min_scale_compliance: Minimum fraction of in-scale notes (filter)
            model: "improv_rnn" or "attention_rnn"
            timeout: Docker timeout in seconds

        Returns:
            CandidateResult with the best candidate
        """
        magenta = self._get_magenta()
        harmonic = self._get_harmonic()

        # Generate candidates via Docker Magenta
        if model == "improv_rnn":
            result = magenta.generate_melody(
                chords=chords,
                bars=bars,
                bpm=bpm,
                temperature=temperature,
                key=self.key,
                num_candidates=num_candidates,
                timeout=timeout,
            )
        elif model == "attention_rnn":
            result = magenta.generate_attention(
                bars=bars,
                bpm=bpm,
                temperature=temperature,
                num_candidates=num_candidates,
                timeout=timeout,
            )
        else:
            raise ValueError(f"Unknown model: {model}. Use 'improv_rnn' or 'attention_rnn'.")

        if not result.success:
            raise RuntimeError(f"Magenta generation failed: {result.error}")

        if not result.midi_paths:
            raise RuntimeError("Magenta returned no MIDI files")

        # Score each candidate
        candidates: List[CandidateResult] = []

        for midi_path in result.midi_paths:
            notes = midi_to_notes(midi_path, bpm=bpm)

            if not notes:
                continue

            # Validate: compute scale compliance
            compliance = self._compute_scale_compliance(notes)

            if compliance < min_scale_compliance:
                if self.verbose:
                    print(f"  Filtered: {midi_path.name} "
                          f"(compliance={compliance:.1%} < {min_scale_compliance:.1%})")
                continue

            # Score with evaluation framework
            metrics = evaluate_melody(
                notes, key=self.key, scale=self.scale, bpm=bpm,
            )

            candidates.append(CandidateResult(
                notes=notes,
                midi_path=midi_path,
                metrics=metrics,
                source=model,
                scale_compliance=compliance,
            ))

        if not candidates:
            raise RuntimeError(
                f"All {num_candidates} candidates were filtered out "
                f"(scale compliance < {min_scale_compliance:.0%}). "
                "Try lowering min_scale_compliance or increasing temperature."
            )

        # Return best by composite score
        best = max(candidates, key=lambda c: c.metrics.composite)

        if self.verbose:
            print(f"  Best candidate: {best.midi_path.name}")
            print(f"  Composite: {best.metrics.composite:.3f}")
            print(f"  Scale compliance: {best.scale_compliance:.1%}")
            print(f"  Notes: {len(best.notes)}")
            print(f"  Candidates evaluated: {len(candidates)}/{num_candidates}")

        return best

    def generate_and_compare(
        self,
        chords: List[str],
        rule_notes: List[NoteEvent],
        bars: int = 8,
        bpm: float = 140.0,
        num_candidates: int = 5,
        temperature: float = 1.0,
    ) -> Tuple[CandidateResult, CandidateResult]:
        """
        Generate ML candidates and compare against rule-based output.

        Returns:
            Tuple of (ml_best, rule_result)
        """
        # Score the rule-based output
        rule_metrics = evaluate_melody(
            rule_notes, key=self.key, scale=self.scale, bpm=bpm,
        )
        rule_compliance = self._compute_scale_compliance(rule_notes)

        # Write rule output to temp MIDI for reference
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            rule_midi = Path(f.name)
        notes_to_midi(rule_notes, rule_midi, bpm=bpm)

        rule_result = CandidateResult(
            notes=rule_notes,
            midi_path=rule_midi,
            metrics=rule_metrics,
            source="rule_engine",
            scale_compliance=rule_compliance,
        )

        # Generate ML candidates
        ml_best = self.generate(
            chords=chords, bars=bars, bpm=bpm,
            num_candidates=num_candidates, temperature=temperature,
        )

        return ml_best, rule_result

    def _compute_scale_compliance(self, notes: List[NoteEvent]) -> float:
        """Fraction of notes whose pitch is in the current scale."""
        if not notes:
            return 0.0

        harmonic = self._get_harmonic()
        in_scale = sum(
            1 for n in notes
            if harmonic.is_in_scale(n.pitch.pitch_class)
        )
        return in_scale / len(notes)


# ---------------------------------------------------------------------------
# Step 1.5 — MusicVAE Motif Variation
# ---------------------------------------------------------------------------

@dataclass
class VariationResult:
    """Result of motif variation."""
    original_notes: List[NoteEvent]
    variants: List[List[NoteEvent]]
    variant_midi_paths: List[Path]
    noise_scale: float
    latent_dim: int = 0


class MLMotifVariator:
    """
    Create motif variations using MusicVAE's latent space.

    Instead of rule-based transformations (sequence, inversion, etc.),
    this encodes a motif into MusicVAE's latent space, perturbs it,
    and decodes new variants that are musically related but distinct.

    Noise scale guide:
        0.05–0.15: Micro-variation (timing/ornamentation)
        0.2–0.4:   Moderate variation (some pitches change, contour preserved)
        0.5–0.8:   Major variation (new melody, similar style)
        >1.0:       Essentially random sampling from style

    Usage:
        variator = MLMotifVariator()
        variants = variator.vary(motif_notes, num_variants=4, noise_scale=0.3)
        for v in variants.variants:
            print(f"  Variant: {len(v)} notes")
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        use_gpu: bool = False,
        verbose: bool = False,
    ):
        self.output_dir = output_dir
        self.use_gpu = use_gpu
        self.verbose = verbose
        self._magenta = None

    def _get_magenta(self):
        if self._magenta is None:
            self._magenta = _get_docker_magenta(
                output_dir=self.output_dir,
                use_gpu=self.use_gpu,
                verbose=self.verbose,
            )
        return self._magenta

    def vary(
        self,
        notes: List[NoteEvent],
        num_variants: int = 4,
        noise_scale: float = 0.3,
        bpm: float = 140.0,
        bars: int = 2,
        timeout: int = 120,
    ) -> VariationResult:
        """
        Create variations of a NoteEvent motif using MusicVAE.

        Args:
            notes: Original motif as NoteEvent list
            num_variants: Number of variations to generate
            noise_scale: How different (0.1=subtle, 0.8=major)
            bpm: Tempo
            bars: 2 or 16 (determines which MusicVAE model)
            timeout: Docker timeout

        Returns:
            VariationResult with original and variant NoteEvent lists
        """
        magenta = self._get_magenta()

        # Write original motif to temp MIDI
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            input_midi = Path(f.name)
        notes_to_midi(notes, input_midi, bpm=bpm)

        # Call MusicVAE via Docker
        result = magenta.vary_motif(
            input_midi=input_midi,
            num_variants=num_variants,
            noise_scale=noise_scale,
            bars=bars,
            timeout=timeout,
        )

        if not result.success:
            raise RuntimeError(f"MusicVAE variation failed: {result.error}")

        # Convert variant MIDI files back to NoteEvents
        variants = []
        for midi_path in result.midi_paths:
            variant_notes = midi_to_notes(midi_path, bpm=bpm)
            variants.append(variant_notes)

        latent_dim = result.raw.get("latent_dim", 0)

        # Clean up temp file
        input_midi.unlink(missing_ok=True)

        return VariationResult(
            original_notes=notes,
            variants=variants,
            variant_midi_paths=result.midi_paths,
            noise_scale=noise_scale,
            latent_dim=latent_dim,
        )

    def interpolate(
        self,
        notes_a: List[NoteEvent],
        notes_b: List[NoteEvent],
        steps: int = 8,
        bpm: float = 140.0,
        bars: int = 2,
        timeout: int = 120,
    ) -> List[List[NoteEvent]]:
        """
        Interpolate between two motifs in MusicVAE latent space.

        Returns a list of NoteEvent lists, one per interpolation step.
        """
        magenta = self._get_magenta()

        # Write both motifs to temp MIDI
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            midi_a = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            midi_b = Path(f.name)

        notes_to_midi(notes_a, midi_a, bpm=bpm)
        notes_to_midi(notes_b, midi_b, bpm=bpm)

        result = magenta.interpolate(
            input_midi_a=midi_a,
            input_midi_b=midi_b,
            steps=steps,
            bars=bars,
            timeout=timeout,
        )

        if not result.success:
            raise RuntimeError(f"MusicVAE interpolation failed: {result.error}")

        interpolations = []
        for midi_path in result.midi_paths:
            interp_notes = midi_to_notes(midi_path, bpm=bpm)
            interpolations.append(interp_notes)

        # Clean up
        midi_a.unlink(missing_ok=True)
        midi_b.unlink(missing_ok=True)

        return interpolations

    def sample(
        self,
        num_samples: int = 4,
        temperature: float = 0.5,
        bpm: float = 140.0,
        bars: int = 2,
        timeout: int = 120,
    ) -> List[List[NoteEvent]]:
        """
        Sample random melodies from MusicVAE latent space.

        Returns a list of NoteEvent lists.
        """
        magenta = self._get_magenta()

        result = magenta.sample_musicvae(
            num_samples=num_samples,
            temperature=temperature,
            bars=bars,
            timeout=timeout,
        )

        if not result.success:
            raise RuntimeError(f"MusicVAE sampling failed: {result.error}")

        samples = []
        for midi_path in result.midi_paths:
            sample_notes = midi_to_notes(midi_path, bpm=bpm)
            samples.append(sample_notes)

        return samples


# ---------------------------------------------------------------------------
# Step 1.5 — Motif Similarity Index
# ---------------------------------------------------------------------------

@dataclass
class SimilarityMatch:
    """A match from the similarity index."""
    midi_path: str
    metadata: Dict[str, Any]
    distance: float  # 0 = identical, higher = more different


class MotifSimilarityIndex:
    """
    Context-aware motif retrieval using MusicVAE latent vectors.

    Encodes motifs into MusicVAE's latent space and uses cosine
    similarity for nearest-neighbor retrieval. This replaces random
    motif selection with context-aware retrieval.

    Usage:
        index = MotifSimilarityIndex()

        # Add motifs to the index
        index.add("motif_drop.mid", {"section": "drop", "energy": 0.9})
        index.add("motif_breakdown.mid", {"section": "breakdown", "energy": 0.4})

        # Build the index (must call after adding all motifs)
        index.build()

        # Query
        matches = index.find_similar("query.mid", n=3)
        for m in matches:
            print(f"{m.midi_path}: distance={m.distance:.3f}")

        # Save/load
        index.save("motif_index.json")
        index = MotifSimilarityIndex.load("motif_index.json")
    """

    def __init__(
        self,
        use_gpu: bool = False,
        verbose: bool = False,
    ):
        self.use_gpu = use_gpu
        self.verbose = verbose
        self._magenta = None

        # Index data
        self._vectors: List[np.ndarray] = []
        self._metadata: List[Dict[str, Any]] = []
        self._midi_paths: List[str] = []
        self._built = False

    def _get_magenta(self):
        if self._magenta is None:
            self._magenta = _get_docker_magenta(
                use_gpu=self.use_gpu,
                verbose=self.verbose,
            )
        return self._magenta

    def add(
        self,
        midi_path: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
        bars: int = 2,
    ):
        """
        Add a motif to the index.

        Args:
            midi_path: Path to MIDI file
            metadata: Arbitrary metadata (section, energy, genre tags, etc.)
            bars: 2 or 16 (must match query)
        """
        magenta = self._get_magenta()
        result = magenta.encode_motif(
            input_midi=midi_path,
            bars=bars,
        )

        if not result.get("success", False) and "mu" not in result:
            raise RuntimeError(f"Failed to encode {midi_path}: {result.get('error')}")

        mu = np.array(result["mu"])
        self._vectors.append(mu)
        self._metadata.append(metadata or {})
        self._midi_paths.append(str(midi_path))
        self._built = False

    def add_notes(
        self,
        notes: List[NoteEvent],
        metadata: Optional[Dict[str, Any]] = None,
        bpm: float = 140.0,
        bars: int = 2,
    ):
        """Add a motif from NoteEvent list (writes temp MIDI internally)."""
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            tmp = Path(f.name)
        notes_to_midi(notes, tmp, bpm=bpm)

        try:
            self.add(tmp, metadata=metadata, bars=bars)
        finally:
            tmp.unlink(missing_ok=True)

    def build(self):
        """Build the nearest-neighbor index. Must call after adding motifs."""
        if len(self._vectors) < 2:
            raise ValueError("Need at least 2 motifs to build an index")

        self._matrix = np.array(self._vectors)
        # Normalize for cosine similarity
        norms = np.linalg.norm(self._matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._matrix_normalized = self._matrix / norms
        self._built = True

    def find_similar(
        self,
        query_midi: Union[str, Path],
        n: int = 5,
        bars: int = 2,
    ) -> List[SimilarityMatch]:
        """
        Find the N most similar motifs to a query.

        Args:
            query_midi: Path to query MIDI file
            n: Number of results
            bars: Must match what was used during add()

        Returns:
            List of SimilarityMatch sorted by distance (ascending)
        """
        if not self._built:
            raise RuntimeError("Index not built. Call build() first.")

        magenta = self._get_magenta()
        result = magenta.encode_motif(input_midi=query_midi, bars=bars)

        if "mu" not in result:
            raise RuntimeError(f"Failed to encode query: {result.get('error')}")

        query_vec = np.array(result["mu"])
        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_normalized = query_vec / query_norm
        else:
            query_normalized = query_vec

        # Cosine similarity (dot product of normalized vectors)
        similarities = self._matrix_normalized @ query_normalized
        # Convert to distance (1 - similarity)
        distances = 1.0 - similarities

        # Get top N
        n = min(n, len(self._vectors))
        top_indices = np.argsort(distances)[:n]

        matches = []
        for idx in top_indices:
            matches.append(SimilarityMatch(
                midi_path=self._midi_paths[idx],
                metadata=self._metadata[idx],
                distance=float(distances[idx]),
            ))

        return matches

    def find_similar_notes(
        self,
        notes: List[NoteEvent],
        n: int = 5,
        bpm: float = 140.0,
        bars: int = 2,
    ) -> List[SimilarityMatch]:
        """Find similar motifs from a NoteEvent list query."""
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            tmp = Path(f.name)
        notes_to_midi(notes, tmp, bpm=bpm)

        try:
            return self.find_similar(tmp, n=n, bars=bars)
        finally:
            tmp.unlink(missing_ok=True)

    def save(self, path: Union[str, Path]):
        """Save the index to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "num_motifs": len(self._vectors),
            "vectors": [v.tolist() for v in self._vectors],
            "metadata": self._metadata,
            "midi_paths": self._midi_paths,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Union[str, Path], **kwargs) -> "MotifSimilarityIndex":
        """Load an index from JSON (does not require Docker to load)."""
        with open(path) as f:
            data = json.load(f)

        index = cls(**kwargs)
        index._vectors = [np.array(v) for v in data["vectors"]]
        index._metadata = data["metadata"]
        index._midi_paths = data["midi_paths"]

        if len(index._vectors) >= 2:
            index.build()

        return index
