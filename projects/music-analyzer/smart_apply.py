#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Apply CLI Tool

Analyzes stems, maps them to Ableton tracks, finds existing devices,
and generates targeted fixes that actually work.

Usage:
    # Analyze stems and show fixes
    python smart_apply.py --stems path/to/stems/

    # Analyze and connect to Ableton for interactive application
    python smart_apply.py --stems path/to/stems/ --connect

    # Auto-apply all automatable fixes
    python smart_apply.py --stems path/to/stems/ --connect --auto-apply
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def print_banner():
    """Print tool banner."""
    print("\n" + "=" * 60)
    print("  SMART FIX APPLICATOR")
    print("  Stems -> Track Analysis -> Targeted Fixes")
    print("=" * 60 + "\n")


def print_analysis_summary(analysis):
    """Print summary of stem analysis."""
    print(f"Analyzed {len(analysis.stems)} stems")
    print("-" * 40)

    for stem in analysis.stems:
        issues_str = f"{len(stem.issues)} issues" if stem.issues else "OK"
        print(f"  {stem.track_name:20s} <- {stem.filename[:25]:25s} [{issues_str}]")

    if analysis.unmapped_stems:
        print(f"\nCould not match {len(analysis.unmapped_stems)} stems:")
        for unmapped in analysis.unmapped_stems[:5]:
            print(f"  ? {unmapped}")
        if len(analysis.unmapped_stems) > 5:
            print(f"  ... and {len(analysis.unmapped_stems) - 5} more")


def print_fixes(fixes):
    """Print fix recommendations grouped by severity."""
    if not fixes:
        print("\nNo issues detected - stems look good!")
        return

    from smart_fix_generator import FixAction

    critical = [f for f in fixes if f.severity == 'critical']
    warnings = [f for f in fixes if f.severity == 'warning']
    suggestions = [f for f in fixes if f.severity == 'suggestion']

    print(f"\nFound {len(fixes)} issues:\n")

    if critical:
        print("CRITICAL (must fix):")
        for fix in critical:
            auto = "[AUTO]" if fix.is_automatable else "[MANUAL]"
            action_emoji = get_action_emoji(fix.action)
            print(f"  {action_emoji} {auto} {fix.title}")
            print(f"       {fix.description}")
            if fix.reason:
                print(f"       Reason: {fix.reason}")

    if warnings:
        print("\nWARNINGS (should fix):")
        for fix in warnings:
            auto = "[AUTO]" if fix.is_automatable else "[MANUAL]"
            action_emoji = get_action_emoji(fix.action)
            print(f"  {action_emoji} {auto} {fix.title}")
            if fix.action == FixAction.DISABLE_DEVICE:
                print(f"       Consider disabling: {fix.device_name}")
            elif fix.manual_steps:
                print(f"       {fix.manual_steps[0]}")

    if suggestions:
        print("\nSUGGESTIONS (consider):")
        for fix in suggestions:
            auto = "[AUTO]" if fix.is_automatable else "[MANUAL]"
            print(f"  {auto} {fix.title}")

    # Summary
    auto_count = len([f for f in fixes if f.is_automatable])
    manual_count = len(fixes) - auto_count
    disable_count = len([f for f in fixes if f.action == FixAction.DISABLE_DEVICE])

    print(f"\nSummary:")
    print(f"  {auto_count} can be auto-applied")
    print(f"  {manual_count} need manual action")
    if disable_count:
        print(f"  {disable_count} recommend REMOVING effects")


def get_action_emoji(action):
    """Get emoji indicator for action type."""
    from smart_fix_generator import FixAction

    action_emojis = {
        FixAction.ADJUST_PARAM: "~",     # Adjust
        FixAction.ENABLE_DEVICE: "+",    # Enable
        FixAction.DISABLE_DEVICE: "-",   # Disable/Remove
        FixAction.BYPASS_DEVICE: "?",    # Test bypass
        FixAction.TRACK_VOLUME: "V",     # Volume
        FixAction.TRACK_PAN: "P",        # Pan
        FixAction.MANUAL_REQUIRED: "*",  # Manual
    }
    return action_emojis.get(action, " ")


def apply_fixes_interactive(fixes, bridge):
    """Interactive fix application."""
    from smart_fix_generator import FixAction

    automatable = [f for f in fixes if f.is_automatable]

    if not automatable:
        print("\nNo automatically applicable fixes available.")
        print("All issues require manual intervention in Ableton.")
        return

    # Group by action type for clearer display
    param_fixes = [f for f in automatable if f.action == FixAction.ADJUST_PARAM]
    disable_fixes = [f for f in automatable if f.action == FixAction.DISABLE_DEVICE]
    volume_fixes = [f for f in automatable if f.action == FixAction.TRACK_VOLUME]
    other_fixes = [f for f in automatable
                   if f.action not in [FixAction.ADJUST_PARAM, FixAction.DISABLE_DEVICE, FixAction.TRACK_VOLUME]]

    print(f"\n{len(automatable)} fix(es) can be applied automatically:")

    idx = 1
    fix_map = {}

    if disable_fixes:
        print("\n  Effects to DISABLE:")
        for fix in disable_fixes:
            print(f"    [{idx}] {fix.title}")
            print(f"        Reason: {fix.reason}")
            fix_map[idx] = fix
            idx += 1

    if param_fixes:
        print("\n  Parameter adjustments:")
        for fix in param_fixes:
            print(f"    [{idx}] {fix.title}")
            fix_map[idx] = fix
            idx += 1

    if volume_fixes:
        print("\n  Volume changes:")
        for fix in volume_fixes:
            print(f"    [{idx}] {fix.title}")
            fix_map[idx] = fix
            idx += 1

    if other_fixes:
        print("\n  Other fixes:")
        for fix in other_fixes:
            print(f"    [{idx}] {fix.title}")
            fix_map[idx] = fix
            idx += 1

    print("\nOptions:")
    print("  [a] Apply all")
    print("  [d] Apply only device disable/remove fixes")
    print("  [p] Apply only parameter adjustments")
    print("  [1,2,3] Apply specific fixes by number")
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

        if choice == 'd':
            fixes_to_apply = disable_fixes
            break

        if choice == 'p':
            fixes_to_apply = param_fixes
            break

        # Parse specific numbers
        try:
            indices = [int(x.strip()) for x in choice.split(',')]
            fixes_to_apply = [fix_map[i] for i in indices if i in fix_map]
            if fixes_to_apply:
                break
            else:
                print("Invalid selection. Try again.")
        except (ValueError, KeyError):
            print("Invalid input. Enter 'a', 'n', 'd', 'p', or numbers like '1,2,3'")

    # Apply selected fixes
    print(f"\nApplying {len(fixes_to_apply)} fix(es)...")

    for fix in fixes_to_apply:
        change = fix.to_bridge_change()
        if change:
            success = bridge.apply_change(change)
            status = "OK" if success else "FAIL"
            print(f"  [{status}] {fix.title}")
        else:
            print(f"  [SKIP] {fix.title} (no bridge change available)")

    print("\nDone! Check Ableton for changes.")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze stems and apply targeted fixes to Ableton Live",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python smart_apply.py --stems ./stems/
  python smart_apply.py --stems ./stems/ --connect
  python smart_apply.py --stems ./stems/ --connect --auto-apply
        """
    )

    parser.add_argument(
        '--stems', '-s',
        required=True,
        help='Path to directory containing stem audio files'
    )
    parser.add_argument(
        '--connect', '-c',
        action='store_true',
        help='Connect to Ableton and offer to apply fixes'
    )
    parser.add_argument(
        '--max-fixes', '-m',
        type=int,
        default=None,
        help='Maximum number of fixes to show/apply'
    )
    parser.add_argument(
        '--auto-apply',
        action='store_true',
        help='Automatically apply all automatable fixes without prompting'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--show-devices',
        action='store_true',
        help='Show devices found on each track'
    )

    args = parser.parse_args()

    # Verify stems directory exists
    stems_dir = Path(args.stems)
    if not stems_dir.exists():
        print(f"Stems directory not found: {stems_dir}")
        sys.exit(1)

    # Count stems
    stem_files = list(stems_dir.glob("*.wav")) + list(stems_dir.glob("*.flac"))
    if not stem_files:
        print(f"No audio files found in: {stems_dir}")
        sys.exit(1)

    print_banner()
    print(f"Found {len(stem_files)} stem files in {stems_dir}")

    # Connect to Ableton (required for smart analysis)
    print("\nConnecting to Ableton...")
    try:
        from ableton_bridge import AbletonBridge
        bridge = AbletonBridge()

        if not bridge.connect():
            print(f"Connection failed: {bridge.last_error}")
            print("\nMake sure Ableton Live is running with AbletonOSC enabled.")
            sys.exit(1)

        # Read session state WITH devices
        session_state = bridge.read_session_state(include_devices=True)
        if not session_state:
            print("Could not read session state from Ableton.")
            sys.exit(1)

        print(f"Connected! Session has {len(session_state.tracks)} tracks at {session_state.tempo} BPM")

    except Exception as e:
        print(f"Connection error: {e}")
        sys.exit(1)

    # Run analysis
    print("\nAnalyzing stems and mapping to tracks...")
    from smart_fix_generator import SmartFixGenerator

    generator = SmartFixGenerator(verbose=args.verbose)

    try:
        analysis = generator.analyze_session(str(stems_dir), bridge)
    except Exception as e:
        print(f"Analysis error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # Print analysis summary
    print_analysis_summary(analysis)

    # Show devices if requested
    if args.show_devices:
        print("\nDevices per track:")
        for stem in analysis.stems:
            devices = analysis.track_device_map.get(stem.track_index, [])
            print(f"  {stem.track_name}:")
            for device in devices:
                enabled = "ON" if device['is_enabled'] else "off"
                print(f"    [{enabled}] {device['name']}")

    # Limit fixes if requested
    fixes = analysis.fixes
    if args.max_fixes and args.max_fixes > 0:
        fixes = fixes[:args.max_fixes]
        print(f"\n(Showing top {args.max_fixes} fixes)")

    # Print fixes
    print_fixes(fixes)

    # Apply fixes if connected
    if args.connect:
        if args.auto_apply:
            # Auto-apply without prompting
            automatable = [f for f in fixes if f.is_automatable]
            if automatable:
                print(f"\nAuto-applying {len(automatable)} fix(es)...")
                for fix in automatable:
                    change = fix.to_bridge_change()
                    if change:
                        success = bridge.apply_change(change)
                        status = "OK" if success else "FAIL"
                        print(f"  [{status}] {fix.title}")
                print("\nDone!")
            else:
                print("\nNo automatically applicable fixes.")
        else:
            apply_fixes_interactive(fixes, bridge)
    else:
        if fixes and any(f.is_automatable for f in fixes):
            print("\nTip: Use --connect to apply fixes to Ableton automatically")


if __name__ == "__main__":
    main()
