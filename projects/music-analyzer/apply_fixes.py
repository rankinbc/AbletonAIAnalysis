#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apply Fixes CLI Tool

Analyzes audio, generates fix recommendations, and optionally
applies them to Ableton Live via AbletonOSC.

Usage:
    # Analyze and show fixes
    python apply_fixes.py --audio path/to/mix.wav

    # Analyze and connect to Ableton
    python apply_fixes.py --audio path/to/mix.wav --connect

    # Compare against reference profile
    python apply_fixes.py --audio path/to/mix.wav --profile models/trance_profile.json

    # Use existing song from inputs
    python apply_fixes.py --song mysong
"""

import argparse
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from audio_analyzer import AudioAnalyzer
from fix_generator import FixGenerator, Fix, FixSeverity


def print_banner():
    """Print tool banner."""
    print("\n" + "=" * 60)
    print("  🔧 ABLETON FIX APPLICATOR")
    print("  Analyze → Generate Fixes → Apply to Ableton")
    print("=" * 60 + "\n")


def analyze_audio(audio_path: str, genre: str = None) -> dict:
    """Run audio analysis."""
    print(f"📊 Analyzing: {Path(audio_path).name}")
    print("-" * 40)

    analyzer = AudioAnalyzer(verbose=False)
    result = analyzer.analyze(audio_path, genre_preset=genre)

    print(f"  Duration: {result.duration_seconds:.1f}s")
    print(f"  Tempo: {result.detected_tempo:.1f} BPM" if result.detected_tempo else "  Tempo: Unknown")
    print(f"  Loudness: {result.loudness.integrated_lufs:.1f} LUFS")
    print(f"  Crest Factor: {result.dynamics.crest_factor_db:.1f} dB")

    return result


def generate_fixes(analysis_result) -> list:
    """Generate fixes from analysis."""
    print("\n🔍 Generating fixes...")
    print("-" * 40)

    generator = FixGenerator()
    fixes = generator.generate_fixes(analysis_result)

    return fixes


def print_fixes(fixes: list) -> None:
    """Print fix recommendations."""
    if not fixes:
        print("\n✅ No issues detected - your mix looks good!")
        return

    critical = [f for f in fixes if f.severity == FixSeverity.CRITICAL]
    warnings = [f for f in fixes if f.severity == FixSeverity.WARNING]
    suggestions = [f for f in fixes if f.severity == FixSeverity.SUGGESTION]

    print(f"\nFound {len(fixes)} issues:\n")

    if critical:
        print("🔴 CRITICAL (must fix):")
        for i, fix in enumerate(critical, 1):
            auto = "🤖" if fix.is_automatable else "👤"
            print(f"  {i}. {auto} {fix.title}")
            print(f"      {fix.description}")
            if fix.manual_steps:
                print(f"      Steps: {fix.manual_steps[0]}")

    if warnings:
        print("\n🟡 WARNINGS (should fix):")
        for i, fix in enumerate(warnings, len(critical) + 1):
            auto = "🤖" if fix.is_automatable else "👤"
            print(f"  {i}. {auto} {fix.title}")
            print(f"      {fix.description}")

    if suggestions:
        print("\n🟢 SUGGESTIONS (consider fixing):")
        for i, fix in enumerate(suggestions, len(critical) + len(warnings) + 1):
            auto = "🤖" if fix.is_automatable else "👤"
            print(f"  {i}. {auto} {fix.title}")

    # Summary
    auto_count = len([f for f in fixes if f.is_automatable])
    manual_count = len(fixes) - auto_count

    print(f"\n📋 Summary: {auto_count} can be auto-applied 🤖, {manual_count} need manual action 👤")


def connect_to_ableton():
    """Connect to Ableton via AbletonOSC."""
    print("\n🔌 Connecting to Ableton...")

    try:
        from ableton_bridge import AbletonBridge
        bridge = AbletonBridge()

        if bridge.connect():
            state = bridge.read_session_state()
            if state:
                print(f"  ✅ Connected!")
                print(f"  Tempo: {state.tempo} BPM")
                print(f"  Tracks: {len(state.tracks)}")
                return bridge
            else:
                print("  ❌ Connected but couldn't read session state")
                return None
        else:
            print(f"  ❌ Connection failed: {bridge.last_error}")
            return None

    except ImportError:
        print("  ❌ ableton_bridge module not found")
        return None


def apply_fixes_interactive(fixes: list, bridge) -> None:
    """Interactive fix application."""
    if not fixes:
        return

    automatable = [f for f in fixes if f.is_automatable]

    if not automatable:
        print("\n⚠️  No automatically applicable fixes available.")
        print("   All issues require manual intervention in Ableton.")
        return

    print(f"\n🤖 {len(automatable)} fix(es) can be applied automatically:")
    for i, fix in enumerate(automatable, 1):
        print(f"  [{i}] {fix.title}")

    print("\nOptions:")
    print("  [a] Apply all")
    print("  [1,2,3] Apply specific fixes")
    print("  [n] Apply none")
    print("  [q] Quit")

    while True:
        choice = input("\nYour choice: ").strip().lower()

        if choice == 'q':
            print("Exiting without applying fixes.")
            return

        if choice == 'n':
            print("No fixes applied.")
            return

        if choice == 'a':
            fixes_to_apply = automatable
            break

        # Parse specific numbers
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(',')]
            fixes_to_apply = [automatable[i] for i in indices if 0 <= i < len(automatable)]
            if fixes_to_apply:
                break
            else:
                print("Invalid selection. Try again.")
        except (ValueError, IndexError):
            print("Invalid input. Enter 'a', 'n', or numbers like '1,2,3'")

    # Apply selected fixes
    print(f"\n⚙️  Applying {len(fixes_to_apply)} fix(es)...")

    for fix in fixes_to_apply:
        success, message = bridge.apply_fix(fix)
        status = "✅" if success else "❌"
        print(f"  {status} {fix.title}: {message}")

    print("\n✨ Done! Check Ableton for changes.")


def compare_to_profile(analysis_result, profile_path: str) -> None:
    """Compare analysis to a reference profile."""
    print(f"\n📈 Comparing to reference profile...")

    try:
        from reference_profiler import ReferenceProfile, DeltaAnalyzer

        profile = ReferenceProfile.load(profile_path)
        analyzer = DeltaAnalyzer(profile)
        deltas = analyzer.analyze(analysis_result)

        analyzer.print_report(deltas)

    except FileNotFoundError:
        print(f"  ❌ Profile not found: {profile_path}")
    except Exception as e:
        print(f"  ❌ Error loading profile: {e}")


def find_song_audio(song_name: str) -> str:
    """Find audio file for a song in inputs directory."""
    inputs_dir = Path(__file__).parent / "inputs" / song_name

    if not inputs_dir.exists():
        # Try without inputs prefix
        inputs_dir = Path(__file__).parent.parent.parent / "inputs" / song_name

    if not inputs_dir.exists():
        raise FileNotFoundError(f"Song not found in inputs: {song_name}")

    # Look for mix file
    mix_dir = inputs_dir / "mix"
    if mix_dir.exists():
        # Find latest version
        versions = sorted(mix_dir.iterdir(), reverse=True)
        for version in versions:
            if version.is_dir():
                for audio in version.glob("*"):
                    if audio.suffix.lower() in ['.wav', '.flac', '.mp3', '.aiff']:
                        return str(audio)

    # Look for any audio file in root
    for audio in inputs_dir.glob("*"):
        if audio.suffix.lower() in ['.wav', '.flac', '.mp3', '.aiff']:
            return str(audio)

    raise FileNotFoundError(f"No audio file found for song: {song_name}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze audio and apply fixes to Ableton Live",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python apply_fixes.py --audio mix.wav
  python apply_fixes.py --audio mix.wav --connect
  python apply_fixes.py --song mysong --connect
  python apply_fixes.py --audio mix.wav --profile models/trance_profile.json
        """
    )

    parser.add_argument(
        '--audio', '-a',
        help='Path to audio file to analyze'
    )
    parser.add_argument(
        '--song', '-s',
        help='Song name (looks in inputs directory)'
    )
    parser.add_argument(
        '--connect', '-c',
        action='store_true',
        help='Connect to Ableton and offer to apply fixes'
    )
    parser.add_argument(
        '--profile', '-p',
        help='Reference profile JSON to compare against'
    )
    parser.add_argument(
        '--genre', '-g',
        default='trance',
        help='Genre preset for analysis (default: trance)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output'
    )
    parser.add_argument(
        '--max-fixes', '-m',
        type=int,
        default=None,
        help='Maximum number of fixes to show/apply (default: all)'
    )
    parser.add_argument(
        '--auto-apply',
        action='store_true',
        help='Automatically apply all automatable fixes without prompting'
    )

    args = parser.parse_args()

    # Determine audio path
    if args.audio:
        audio_path = args.audio
    elif args.song:
        try:
            audio_path = find_song_audio(args.song)
            print(f"Found audio: {audio_path}")
        except FileNotFoundError as e:
            print(f"❌ {e}")
            sys.exit(1)
    else:
        parser.print_help()
        print("\n❌ Please provide --audio or --song")
        sys.exit(1)

    # Verify audio file exists
    if not Path(audio_path).exists():
        print(f"❌ Audio file not found: {audio_path}")
        sys.exit(1)

    if not args.quiet:
        print_banner()

    # Run analysis
    analysis_result = analyze_audio(audio_path, args.genre)

    # Compare to profile if provided
    if args.profile:
        compare_to_profile(analysis_result, args.profile)

    # Generate and display fixes
    fixes = generate_fixes(analysis_result)

    # Limit fixes if requested
    if args.max_fixes and args.max_fixes > 0:
        fixes = fixes[:args.max_fixes]
        print(f"\n(Showing top {args.max_fixes} fixes)")

    print_fixes(fixes)

    # Connect to Ableton if requested
    if args.connect:
        bridge = connect_to_ableton()
        if bridge:
            if args.auto_apply:
                # Auto-apply without prompting
                automatable = [f for f in fixes if f.is_automatable]
                if automatable:
                    print(f"\n⚙️  Auto-applying {len(automatable)} fix(es)...")
                    for fix in automatable:
                        success, message = bridge.apply_fix(fix)
                        status = "✅" if success else "❌"
                        print(f"  {status} {fix.title}")
                    print("\n✨ Done!")
                else:
                    print("\n⚠️  No automatically applicable fixes.")
            else:
                apply_fixes_interactive(fixes, bridge)
    else:
        if fixes and any(f.is_automatable for f in fixes):
            print("\n💡 Tip: Use --connect to apply fixes to Ableton automatically")


if __name__ == "__main__":
    main()
