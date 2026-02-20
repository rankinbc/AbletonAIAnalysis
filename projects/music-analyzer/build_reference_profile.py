#!/usr/bin/env python3
"""
Build reference profile from YouTube reference tracks.

This extracts trance-specific features from all reference tracks
and creates a statistical profile for gap analysis.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from profiling.reference_profiler import ReferenceProfiler, format_profile_info, validate_profile


def progress_callback(stage: str, pct: int, message: str):
    """Print progress updates."""
    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = "#" * filled + "-" * (bar_width - filled)
    print(f"\r[{bar}] {pct:3d}% | {stage:12s} | {message[:50]:50s}", end="", flush=True)
    if pct == 100:
        print()  # Newline at end


def main():
    # Configuration
    reference_dir = Path(__file__).parent.parent / "youtube-reference-track-analysis" / "tracks"
    output_dir = Path(__file__).parent / "profiles"
    output_dir.mkdir(exist_ok=True)

    profile_name = "trance_reference_profile"
    output_path = output_dir / f"{profile_name}.json"

    print("=" * 60)
    print("REFERENCE PROFILE BUILDER")
    print("=" * 60)
    print(f"Reference tracks: {reference_dir}")
    print(f"Output: {output_path}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # Check directory exists
    if not reference_dir.exists():
        print(f"ERROR: Reference directory not found: {reference_dir}")
        sys.exit(1)

    # Count files
    audio_extensions = {'.wav', '.flac', '.mp3', '.m4a', '.aac', '.ogg'}
    audio_files = [f for f in reference_dir.iterdir()
                   if f.suffix.lower() in audio_extensions]

    print(f"Found {len(audio_files)} audio files")
    print()

    if len(audio_files) < 10:
        print("ERROR: Need at least 10 reference tracks")
        sys.exit(1)

    # Build profile
    print("Building profile (this may take 30-60 minutes)...")
    print()

    profiler = ReferenceProfiler(verbose=True)

    try:
        profile = profiler.build_profile(
            reference_dir=str(reference_dir),
            profile_name=profile_name,
            min_tracks=10,
            progress_callback=progress_callback
        )

        print()
        print("=" * 60)
        print("PROFILE COMPLETE")
        print("=" * 60)
        print()

        # Print summary
        print(format_profile_info(profile))
        print()

        # Validate
        warnings = validate_profile(profile)
        if warnings:
            print("Warnings:")
            for w in warnings:
                print(f"  ⚠ {w}")
            print()

        # Save
        profile.save(str(output_path))
        print(f"Profile saved to: {output_path}")
        print()

        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
