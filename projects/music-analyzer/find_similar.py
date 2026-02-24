#!/usr/bin/env python3
"""
Find Similar Tracks - Query the similarity index for tracks like yours.

Usage:
    python find_similar.py my_track.wav                    # Basic search
    python find_similar.py my_track.wav --top 10           # Top 10 results
    python find_similar.py my_track.wav --gaps             # Show production gaps vs matches
    python find_similar.py my_track.wav --play             # Open best match in player

The index must be built first with build_index.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import click
from colorama import init, Fore, Style

init()


def format_duration(seconds: float) -> str:
    """Format duration as mm:ss."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def get_similarity_color(similarity: float) -> str:
    """Get color based on similarity percentage."""
    pct = similarity * 100
    if pct >= 80:
        return Fore.GREEN
    elif pct >= 60:
        return Fore.YELLOW
    elif pct >= 40:
        return Fore.WHITE
    else:
        return Fore.RED


@click.command()
@click.argument('query', type=click.Path(exists=True))
@click.option('--index', '-i', type=click.Path(exists=True), default='./similarity_index',
              help='Path to similarity index (default: ./similarity_index)')
@click.option('--top', '-k', type=int, default=5, help='Number of results (default: 5)')
@click.option('--gaps', '-g', is_flag=True,
              help='Show production gaps between query and top match')
@click.option('--profile', '-p', type=click.Path(exists=True),
              help='Reference profile for gap analysis (auto-detects if not specified)')
@click.option('--play', is_flag=True, help='Open best match in default player')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def main(query, index, top, gaps, profile, play, verbose):
    """
    Find tracks similar to QUERY in the similarity index.

    QUERY is the path to an audio file (WAV, FLAC, MP3).

    \b
    Examples:
        python find_similar.py my_wip.wav
        python find_similar.py my_wip.wav --top 10
        python find_similar.py my_wip.wav --gaps
        python find_similar.py my_wip.wav --gaps --profile trance_profile.json
    """
    query_path = Path(query)
    index_path = Path(index)

    print(f"\n{Fore.CYAN}=== Finding Similar Tracks ==={Style.RESET_ALL}\n")

    # Check index exists
    if not index_path.exists():
        print(f"{Fore.RED}Error: Index not found at {index_path}{Style.RESET_ALL}")
        print(f"Build one first: python build_index.py ./references/")
        sys.exit(1)

    # Load dependencies
    try:
        from embeddings.openl3_extractor import get_extractor
        from embeddings import SimilarityIndex
    except ImportError as e:
        print(f"{Fore.RED}Error: Missing dependencies: {e}{Style.RESET_ALL}")
        print("Install with: pip install openl3 faiss-cpu soundfile")
        sys.exit(1)

    # Load index
    print(f"Query:  {query_path.name}")
    print(f"Index:  {index_path}")
    print()

    print(f"Loading index...")
    idx = SimilarityIndex(dimension=512)
    idx.load(str(index_path))
    print(f"  {idx.size} tracks indexed\n")

    # Extract query embedding
    print(f"Extracting query embedding...")
    extractor = get_extractor(content_type="music", embedding_size=512, verbose=verbose)

    try:
        query_result = extractor.extract(str(query_path))
    except Exception as e:
        print(f"{Fore.RED}Error extracting embedding: {e}{Style.RESET_ALL}")
        sys.exit(1)

    print(f"  Duration: {format_duration(query_result.duration_seconds)}")
    print()

    # Search
    print(f"Searching for similar tracks...\n")
    results = idx.search(query_result.embedding, k=top)

    if not results:
        print(f"{Fore.YELLOW}No similar tracks found{Style.RESET_ALL}")
        sys.exit(0)

    # Display results
    print(f"{Fore.CYAN}=== Similar Tracks ==={Style.RESET_ALL}\n")

    best_match = None
    best_match_path = None

    for i, result in enumerate(results, 1):
        color = get_similarity_color(result.similarity)
        pct = result.similarity * 100

        # Get path from metadata
        path_str = ""
        duration_str = ""
        if result.metadata:
            if 'path' in result.metadata:
                path_str = result.metadata['path']
                if not best_match:
                    best_match = result
                    best_match_path = path_str
            if 'duration' in result.metadata:
                duration_str = f" ({format_duration(result.metadata['duration'])})"

        print(f"  {i}. {color}{result.track_id}{Style.RESET_ALL}{duration_str}")
        print(f"     Similarity: {color}{pct:.1f}%{Style.RESET_ALL}")

        if path_str and verbose:
            print(f"     Path: {path_str}")
        print()

    # Gap analysis
    if gaps and best_match_path:
        print(f"{Fore.CYAN}=== Production Gaps vs Best Match ==={Style.RESET_ALL}\n")

        try:
            from feature_extraction import extract_all_trance_features
            from feature_extraction.trance_features import format_trance_features_report

            print(f"Analyzing query track...")
            query_features = extract_all_trance_features(str(query_path), verbose=verbose)

            print(f"Analyzing best match: {best_match.track_id}...")
            ref_features = extract_all_trance_features(best_match_path, verbose=verbose)

            print()

            # Compare key features
            comparisons = [
                ('Trance Score', 'trance_score', '', 2),
                ('Tempo', 'tempo', ' BPM', 1),
                ('Pumping (Sidechain)', 'pumping_score', '', 2),
                ('Stereo Width', 'stereo_width', '', 2),
                ('Energy Range', 'energy_range', '', 2),
                ('Spectral Brightness', 'spectral_brightness', '', 2),
            ]

            print(f"  {'Feature':<25} {'Yours':<12} {'Reference':<12} {'Delta':<10}")
            print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")

            for label, attr, suffix, decimals in comparisons:
                query_val = getattr(query_features, attr, None)
                ref_val = getattr(ref_features, attr, None)

                if query_val is not None and ref_val is not None:
                    delta = query_val - ref_val
                    delta_color = Fore.GREEN if abs(delta) < 0.1 else Fore.YELLOW if abs(delta) < 0.3 else Fore.RED

                    fmt = f".{decimals}f"
                    print(f"  {label:<25} {query_val:{fmt}}{suffix:<5} {ref_val:{fmt}}{suffix:<5} "
                          f"{delta_color}{delta:+{fmt}}{Style.RESET_ALL}")

            # Suggestions
            print(f"\n  {Fore.YELLOW}Key Differences:{Style.RESET_ALL}")

            if abs(query_features.trance_score - ref_features.trance_score) > 0.15:
                direction = "more" if query_features.trance_score < ref_features.trance_score else "less"
                print(f"    - Reference has {direction} trance character")

            if abs(query_features.pumping_score - ref_features.pumping_score) > 0.2:
                direction = "stronger" if query_features.pumping_score < ref_features.pumping_score else "lighter"
                print(f"    - Reference has {direction} sidechain pumping")

            if abs(query_features.stereo_width - ref_features.stereo_width) > 0.15:
                direction = "wider" if query_features.stereo_width < ref_features.stereo_width else "narrower"
                print(f"    - Reference has {direction} stereo image")

            print()

        except ImportError as e:
            print(f"{Fore.YELLOW}Gap analysis requires feature_extraction module: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}Gap analysis failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()

    # Open best match
    if play and best_match_path:
        import subprocess
        import platform

        print(f"Opening: {best_match.track_id}")
        try:
            if platform.system() == 'Windows':
                subprocess.run(['start', '', best_match_path], shell=True)
            elif platform.system() == 'Darwin':
                subprocess.run(['open', best_match_path])
            else:
                subprocess.run(['xdg-open', best_match_path])
        except Exception as e:
            print(f"{Fore.YELLOW}Could not open file: {e}{Style.RESET_ALL}")

    print()


if __name__ == '__main__':
    main()
