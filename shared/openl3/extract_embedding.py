#!/usr/bin/env python3
"""
OpenL3 embedding extraction script for Docker container.

Outputs JSON with embedding vectors for easy parsing from host.
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf


def extract_embedding(
    audio_path: str,
    content_type: str = "music",
    embedding_size: int = 512,
    input_repr: str = "mel256",
    hop_size: float = 0.5,
    aggregation: str = "mean"
) -> dict:
    """
    Extract OpenL3 embedding from audio file.

    Returns dict with embedding and metadata.
    """
    import openl3

    # Load audio
    audio, sr = sf.read(audio_path)

    # Handle stereo by converting to mono
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)

    duration_seconds = len(audio) / sr

    # Load model
    model = openl3.models.load_audio_embedding_model(
        content_type=content_type,
        input_repr=input_repr,
        embedding_size=embedding_size
    )

    # Extract embeddings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        embeddings, timestamps = openl3.get_audio_embedding(
            audio,
            sr,
            model=model,
            content_type=content_type,
            input_repr=input_repr,
            embedding_size=embedding_size,
            hop_size=hop_size,
            center=True,
            verbose=False
        )

    n_frames = embeddings.shape[0]

    # Aggregate embeddings
    if aggregation == "mean":
        embedding = np.mean(embeddings, axis=0)
    elif aggregation == "max":
        embedding = np.max(embeddings, axis=0)
    elif aggregation == "none":
        embedding = embeddings  # Return all frames
    else:
        raise ValueError(f"Unknown aggregation method: {aggregation}")

    return {
        "audio_path": str(audio_path),
        "duration_seconds": float(duration_seconds),
        "sample_rate": int(sr),
        "embedding_size": int(embedding_size),
        "content_type": content_type,
        "aggregation": aggregation,
        "n_frames": int(n_frames),
        "embedding": embedding.tolist() if aggregation != "none" else embeddings.tolist()
    }


def extract_batch(
    audio_paths: list,
    content_type: str = "music",
    embedding_size: int = 512,
    input_repr: str = "mel256",
    hop_size: float = 0.5,
    aggregation: str = "mean"
) -> list:
    """Extract embeddings from multiple audio files."""
    import openl3

    # Load model once for efficiency
    model = openl3.models.load_audio_embedding_model(
        content_type=content_type,
        input_repr=input_repr,
        embedding_size=embedding_size
    )

    results = []
    for path in audio_paths:
        try:
            audio, sr = sf.read(path)

            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)

            duration_seconds = len(audio) / sr

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                embeddings, timestamps = openl3.get_audio_embedding(
                    audio,
                    sr,
                    model=model,
                    content_type=content_type,
                    input_repr=input_repr,
                    embedding_size=embedding_size,
                    hop_size=hop_size,
                    center=True,
                    verbose=False
                )

            n_frames = embeddings.shape[0]

            if aggregation == "mean":
                embedding = np.mean(embeddings, axis=0)
            elif aggregation == "max":
                embedding = np.max(embeddings, axis=0)
            else:
                embedding = embeddings

            results.append({
                "audio_path": str(path),
                "duration_seconds": float(duration_seconds),
                "sample_rate": int(sr),
                "embedding_size": int(embedding_size),
                "content_type": content_type,
                "aggregation": aggregation,
                "n_frames": int(n_frames),
                "embedding": embedding.tolist() if aggregation != "none" else embeddings.tolist(),
                "success": True
            })
        except Exception as e:
            results.append({
                "audio_path": str(path),
                "success": False,
                "error": str(e)
            })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Extract OpenL3 audio embeddings"
    )
    parser.add_argument(
        "audio_paths",
        nargs="+",
        help="Path(s) to audio file(s)"
    )
    parser.add_argument(
        "--content-type",
        choices=["music", "env"],
        default="music",
        help="Content type for embedding model (default: music)"
    )
    parser.add_argument(
        "--embedding-size",
        type=int,
        choices=[512, 6144],
        default=512,
        help="Embedding dimension (default: 512)"
    )
    parser.add_argument(
        "--input-repr",
        choices=["mel128", "mel256"],
        default="mel256",
        help="Input representation (default: mel256)"
    )
    parser.add_argument(
        "--hop-size",
        type=float,
        default=0.5,
        help="Hop size in seconds (default: 0.5)"
    )
    parser.add_argument(
        "--aggregation",
        choices=["mean", "max", "none"],
        default="mean",
        help="Embedding aggregation method (default: mean)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output JSON file (default: stdout)"
    )

    args = parser.parse_args()

    # Single file or batch
    if len(args.audio_paths) == 1:
        result = extract_embedding(
            args.audio_paths[0],
            content_type=args.content_type,
            embedding_size=args.embedding_size,
            input_repr=args.input_repr,
            hop_size=args.hop_size,
            aggregation=args.aggregation
        )
    else:
        result = extract_batch(
            args.audio_paths,
            content_type=args.content_type,
            embedding_size=args.embedding_size,
            input_repr=args.input_repr,
            hop_size=args.hop_size,
            aggregation=args.aggregation
        )

    # Output
    output_json = json.dumps(result, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
