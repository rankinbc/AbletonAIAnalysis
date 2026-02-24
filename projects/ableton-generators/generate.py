#!/usr/bin/env python3
"""
Hybrid Melody Generation CLI (Phase 1, Step 1.7)

Generates trance melodies using the hybrid pipeline (rule engine + ML models),
scores all candidates with the evaluation framework, and exports the best as MIDI.

Usage:
    # Basic generation (rule-only if Docker/Magenta not available)
    python generate.py --key Am --bpm 140 --chords "Am F C G" --bars 16

    # Full hybrid with ML candidates
    python generate.py --key Am --bpm 140 --chords "Am F C G" --bars 16 --ml-candidates 5

    # Specify section type and energy
    python generate.py --section drop --energy 0.95 --bars 16

    # Generate batch for baseline recording
    python generate.py --batch 50 --output baselines/phase1

    # Verbose output with evaluation scorecard
    python generate.py --verbose --scorecard

    # Use reference stats for better scoring
    python generate.py --reference-stats evaluation/reference_stats.json
"""

import argparse
import sys
import os

# Add project root to path so melody_generation and shared are importable
_project_root = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(os.path.dirname(_project_root))
for _path in [_project_root, _repo_root]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from melody_generation.integration import HybridPipeline, HybridResult
from melody_generation.evaluation import (
    print_metrics,
    save_baseline,
    MelodyMetrics,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate trance melodies with the hybrid pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate.py
  python generate.py --key Am --chords "Am F C G" --bars 16 --section drop
  python generate.py --ml-candidates 5 --variations 3 --verbose
  python generate.py --batch 50 --output baselines/phase1_hybrid
        """,
    )

    # Musical parameters
    parser.add_argument("--key", default="A", help="Key root (default: A)")
    parser.add_argument("--scale", default="minor", help="Scale type (default: minor)")
    parser.add_argument("--bpm", type=int, default=138, help="Tempo (default: 138)")
    parser.add_argument(
        "--chords",
        default="Am F C G",
        help='Chord progression as space-separated symbols (default: "Am F C G")',
    )
    parser.add_argument("--section", default="drop",
                        help="Section type: drop, breakdown, buildup, intro, outro (default: drop)")
    parser.add_argument("--bars", type=int, default=16, help="Number of bars (default: 16)")
    parser.add_argument("--energy", type=float, default=0.9,
                        help="Energy level 0.0-1.0 (default: 0.9)")
    parser.add_argument("--genre", default="trance", help="Genre (default: trance)")

    # ML parameters
    parser.add_argument("--ml-candidates", type=int, default=0,
                        help="Number of ML candidates (0=rule-only, default: 0)")
    parser.add_argument("--temperature", type=float, default=1.0,
                        help="ML sampling temperature (default: 1.0)")
    parser.add_argument("--variations", type=int, default=0,
                        help="MusicVAE variations per candidate (default: 0)")
    parser.add_argument("--variation-noise", type=float, default=0.3,
                        help="MusicVAE noise scale (default: 0.3)")

    # Output
    parser.add_argument("--output", "-o", default="output",
                        help="Output directory (default: output)")
    parser.add_argument("--no-midi", action="store_true",
                        help="Skip MIDI export")
    parser.add_argument("--no-log", action="store_true",
                        help="Skip generation log")

    # Evaluation
    parser.add_argument("--reference-stats", default=None,
                        help="Path to reference_stats.json for better scoring")
    parser.add_argument("--scorecard", action="store_true",
                        help="Print full evaluation scorecard")

    # Batch mode
    parser.add_argument("--batch", type=int, default=0,
                        help="Generate N melodies for baseline recording")
    parser.add_argument("--baseline-label", default="",
                        help="Label for baseline file (used with --batch)")

    # General
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    return parser.parse_args()


def print_summary(result: HybridResult, verbose: bool = False):
    """Print a concise summary of the generation result."""
    print(f"\n{'=' * 56}")
    print(f"  Hybrid Pipeline Result")
    print(f"{'=' * 56}")
    print(f"  Winner:     {result.lead_source}")
    print(f"  Score:      {result.lead_metrics.composite:.3f}")
    print(f"  Lead notes: {len(result.lead.notes)}")
    print(f"  Arp notes:  {len(result.arp.notes)}")
    print(f"  Candidates: {len(result.all_candidates)}")
    print(f"  Time:       {result.generation_time_s:.1f}s")

    if result.midi_path:
        print(f"  MIDI:       {result.midi_path}")
    if result.log_path:
        print(f"  Log:        {result.log_path}")

    if verbose and len(result.all_candidates) > 1:
        print(f"\n{'─' * 56}")
        print(f"  {'Source':<24} {'Score':>8}  {'Notes':>6}  {'Scale%':>7}")
        print(f"{'─' * 56}")
        ranked = sorted(result.all_candidates,
                       key=lambda c: c.metrics.composite, reverse=True)
        for c in ranked:
            marker = " *" if c.source == result.lead_source and c.metrics.composite == result.lead_metrics.composite else "  "
            print(f"{marker}{c.source:<22} {c.metrics.composite:>8.3f}"
                  f"  {c.metrics.num_notes:>6}"
                  f"  {c.scale_compliance:>6.1%}")

    print(f"{'=' * 56}")


def main():
    args = parse_args()
    chords = args.chords.split()

    pipeline = HybridPipeline(
        key=args.key,
        scale=args.scale,
        tempo=args.bpm,
        genre=args.genre,
        output_dir=args.output,
        reference_stats_path=args.reference_stats,
        verbose=args.verbose,
    )

    if args.batch > 0:
        # Batch mode: generate N melodies for baseline recording
        print(f"Generating {args.batch} melodies for baseline...")
        results = pipeline.generate_batch(
            n=args.batch,
            chords=chords,
            section_type=args.section,
            bars=args.bars,
            energy=args.energy,
            temperature=args.temperature,
            num_ml_candidates=args.ml_candidates,
            num_variations=args.variations,
            variation_noise=args.variation_noise,
        )

        # Collect metrics
        metrics_list = [r.lead_metrics for r in results]

        # Print summary stats
        scores = [m.composite for m in metrics_list]
        sources = {}
        for r in results:
            sources[r.lead_source] = sources.get(r.lead_source, 0) + 1

        print(f"\n{'=' * 56}")
        print(f"  Batch Results ({args.batch} melodies)")
        print(f"{'=' * 56}")
        print(f"  Composite: mean={sum(scores)/len(scores):.3f}, "
              f"min={min(scores):.3f}, max={max(scores):.3f}")
        print(f"  Sources: {sources}")

        # Save baseline
        label = args.baseline_label or f"batch_{args.batch}_{args.section}"
        baseline_path = os.path.join(args.output, f"{label}_baseline.json")
        os.makedirs(args.output, exist_ok=True)
        save_baseline(metrics_list, baseline_path, label=label)
        print(f"  Baseline saved: {baseline_path}")
        print(f"{'=' * 56}")

    else:
        # Single generation
        result = pipeline.generate(
            chords=chords,
            section_type=args.section,
            bars=args.bars,
            energy=args.energy,
            temperature=args.temperature,
            num_ml_candidates=args.ml_candidates,
            num_variations=args.variations,
            variation_noise=args.variation_noise,
            export_midi=not args.no_midi,
            save_log=not args.no_log,
        )

        print_summary(result, verbose=args.verbose)

        if args.scorecard:
            print_metrics(result.lead_metrics, label=f"{args.section} lead ({result.lead_source})")


if __name__ == "__main__":
    main()
