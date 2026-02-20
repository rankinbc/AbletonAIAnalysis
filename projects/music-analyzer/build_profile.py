#!/usr/bin/env python3
"""Build trance reference profile from reference tracks."""

import sys
from pathlib import Path

# Unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from profiling import ReferenceProfiler

def main():
    print("Building trance reference profile...", flush=True)
    print("=" * 60, flush=True)

    profiler = ReferenceProfiler(verbose=True)

    profile = profiler.build_profile(
        'C:/claude-workspace/AbletonAIAnalysis/projects/youtube-reference-track-analysis/tracks',
        'trance_profile'
    )

    profile.save('trance_profile.json')

    print()
    print("=" * 60)
    print(f"DONE: {profile.track_count} tracks analyzed")
    print(f"Clusters discovered: {len(profile.clusters)}")
    for c in profile.clusters:
        print(f"  [{c.cluster_id}] {c.name} ({c.track_count} tracks)")
    print()
    print("Profile saved to: trance_profile.json")

if __name__ == "__main__":
    main()
