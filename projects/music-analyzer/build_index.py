#!/usr/bin/env python3
"""
Build Similarity Index - Create a FAISS index from reference audio files.

Usage:
    python build_index.py                           # Use default reference library
    python build_index.py ./my_references/          # Custom folder
    python build_index.py --output ./custom_index/  # Custom output path

The index enables fast similarity search with find_similar.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import click
from colorama import init, Fore, Style

init()


def find_audio_files(directory: Path) -> list:
    """Find all audio files in directory recursively."""
    audio_files = []
    for ext in ['*.wav', '*.flac', '*.mp3', '*.WAV', '*.FLAC', '*.MP3']:
        audio_files.extend(directory.glob(f'**/{ext}'))
    return sorted(audio_files)


@click.command()
@click.argument('source', type=click.Path(exists=True), required=False)
@click.option('--output', '-o', type=click.Path(), default='./similarity_index',
              help='Output directory for the index (default: ./similarity_index)')
@click.option('--dimension', '-d', type=int, default=512,
              help='Embedding dimension: 512 (fast) or 6144 (detailed)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def main(source, output, dimension, verbose):
    """
    Build a similarity index from reference audio files.

    SOURCE is the directory containing reference audio files.
    If not specified, uses the reference_library from ReferenceStorage.

    \b
    Examples:
        python build_index.py                        # Default reference library
        python build_index.py ./references/          # Custom folder
        python build_index.py -o ./my_index ./refs/  # Custom output
    """
    print(f"\n{Fore.CYAN}=== Building Similarity Index ==={Style.RESET_ALL}\n")

    # Determine source directory
    if source:
        source_dir = Path(source)
    else:
        # Try to find reference library
        from reference_storage import ReferenceStorage
        storage = ReferenceStorage()
        refs = storage.list_references()

        if refs:
            # Use paths from reference library
            print(f"Using reference library ({len(refs)} tracks)")
            audio_files = [Path(r.file_path) for r in refs if Path(r.file_path).exists()]
        else:
            # Fallback to default references folder
            project_root = Path(__file__).parent.parent.parent
            source_dir = project_root / "references"
            if not source_dir.exists():
                print(f"{Fore.RED}Error: No source specified and no reference library found{Style.RESET_ALL}")
                print(f"Usage: python build_index.py ./path/to/references/")
                sys.exit(1)
            audio_files = find_audio_files(source_dir)

    if source:
        audio_files = find_audio_files(source_dir)

    if not audio_files:
        print(f"{Fore.RED}Error: No audio files found{Style.RESET_ALL}")
        sys.exit(1)

    output_dir = Path(output)

    print(f"Source: {source_dir if source else 'reference_library'}")
    print(f"Output: {output_dir}")
    print(f"Files:  {len(audio_files)}")
    print(f"Dimension: {dimension}")
    print()

    # Initialize extractor and index
    try:
        from embeddings.openl3_extractor import get_extractor
        from embeddings import SimilarityIndex
    except ImportError as e:
        print(f"{Fore.RED}Error: Missing dependencies: {e}{Style.RESET_ALL}")
        print("Install with: pip install openl3 faiss-cpu soundfile")
        sys.exit(1)

    print(f"Loading OpenL3 model...")
    extractor = get_extractor(content_type="music", embedding_size=dimension, verbose=verbose)
    index = SimilarityIndex(dimension=dimension, index_type="flat")

    # Process each file
    success_count = 0
    failed_files = []

    print(f"\nExtracting embeddings:\n")
    for i, audio_path in enumerate(audio_files):
        progress = f"[{i+1:3}/{len(audio_files)}]"

        try:
            result = extractor.extract(str(audio_path))
            track_id = audio_path.stem

            index.add(
                result.embedding,
                track_id,
                metadata={
                    'path': str(audio_path.absolute()),
                    'duration': result.duration_seconds,
                    'name': audio_path.name
                }
            )

            print(f"  {progress} {Fore.GREEN}OK{Style.RESET_ALL} {audio_path.name} ({result.duration_seconds:.0f}s)")
            success_count += 1

        except Exception as e:
            print(f"  {progress} {Fore.YELLOW}SKIP{Style.RESET_ALL} {audio_path.name}: {e}")
            failed_files.append((audio_path.name, str(e)))

    # Save index
    print(f"\nSaving index...")
    output_dir.mkdir(parents=True, exist_ok=True)
    index.save(str(output_dir))

    # Summary
    print(f"\n{Fore.CYAN}=== Complete ==={Style.RESET_ALL}")
    print(f"  Indexed: {success_count}/{len(audio_files)} tracks")
    print(f"  Output:  {output_dir.absolute()}")

    if failed_files:
        print(f"\n  {Fore.YELLOW}Skipped {len(failed_files)} files:{Style.RESET_ALL}")
        for name, err in failed_files[:5]:
            print(f"    - {name}: {err}")
        if len(failed_files) > 5:
            print(f"    ... and {len(failed_files) - 5} more")

    print(f"\n{Fore.GREEN}Next: python find_similar.py <track.wav>{Style.RESET_ALL}\n")


if __name__ == '__main__':
    main()
