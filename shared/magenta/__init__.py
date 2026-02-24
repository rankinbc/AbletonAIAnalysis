"""
Shared Magenta Docker service for AbletonAIAnalysis.

This module provides a Docker-based wrapper for Google Magenta
(Melody RNN, Improv RNN, MusicVAE), avoiding Python 3.9/TF 2.11
compatibility issues on modern Python.

Usage:
    from shared.magenta import DockerMagenta

    magenta = DockerMagenta()

    # Chord-conditioned melody generation (Improv RNN)
    result = magenta.generate_melody(
        chords=["Am", "F", "C", "G"], bars=8, bpm=140
    )
    for path in result.midi_paths:
        print(path)

    # Motif variation (MusicVAE)
    result = magenta.vary_motif("motif.mid", num_variants=4, noise_scale=0.3)

    # Interpolation between two melodies (MusicVAE)
    result = magenta.interpolate("a.mid", "b.mid", steps=8)

    # Random sampling from latent space (MusicVAE)
    result = magenta.sample_musicvae(num_samples=4, temperature=0.5)

    # Encode motif to latent vector (for similarity index)
    latent = magenta.encode_motif("motif.mid")
"""

from .docker_magenta import (
    DockerMagenta,
    GenerationResult,
    MelodySummary,
    is_docker_available,
    is_magenta_image_available,
)

__all__ = [
    'DockerMagenta',
    'GenerationResult',
    'MelodySummary',
    'is_docker_available',
    'is_magenta_image_available',
]

__version__ = '1.0.0'
