"""
ALS Doctor - Unified CLI for Ableton Project Analysis

Commands:
  diagnose <file.als>           - Full diagnosis of a single project
  compare <before.als> <after.als> - Compare two versions
  scan <directory>              - Batch scan and rank projects
  quick <file.als>              - Quick health check (just the score)

Examples:
  python als_doctor.py diagnose "D:/Music/MyProject/project.als"
  python als_doctor.py compare "v1.als" "v2.als"
  python als_doctor.py scan "D:/Ableton Projects" --limit 20
  python als_doctor.py quick "project.als"
"""

import sys
import argparse
from pathlib import Path


def cmd_diagnose(args):
    """Run full diagnosis on a project."""
    from effect_chain_doctor import diagnose_project, EffectChainDoctor

    print(f"Analyzing: {args.file}")
    diagnosis = diagnose_project(args.file, verbose=args.verbose)
    doctor = EffectChainDoctor()
    print(doctor.generate_report(diagnosis))

    if args.json:
        import json
        with open(args.json, 'w') as f:
            # Simple JSON export
            data = {
                "file": diagnosis.file_path,
                "health_score": diagnosis.overall_health,
                "total_issues": diagnosis.total_issues,
                "critical_issues": diagnosis.critical_issues,
                "warning_issues": diagnosis.warning_issues,
                "total_devices": diagnosis.total_devices,
                "disabled_devices": diagnosis.total_disabled,
                "clutter_percentage": diagnosis.clutter_percentage
            }
            json.dump(data, f, indent=2)
        print(f"\nJSON saved to: {args.json}")


def cmd_compare(args):
    """Compare two project versions."""
    from project_differ import compare_projects, ProjectDiffer

    print(f"Comparing:")
    print(f"  BEFORE: {args.before}")
    print(f"  AFTER:  {args.after}")
    print()

    diff = compare_projects(args.before, args.after, verbose=args.verbose)
    differ = ProjectDiffer()
    print(differ.generate_report(diff))


def cmd_scan(args):
    """Batch scan projects in a directory."""
    from batch_scanner import BatchScanner
    import re

    print(f"Scanning: {args.directory}")
    if args.limit:
        print(f"Limit: {args.limit} files")
    if args.min_number:
        print(f"Filter: Projects numbered {args.min_number}+")
    print()

    scanner = BatchScanner(verbose=args.verbose)
    path = Path(args.directory)

    # Get all als files
    als_files = list(path.rglob("*.als"))

    # Filter by project number if specified
    if args.min_number:
        filtered = []
        for f in als_files:
            # Extract number from parent folder name (e.g., "35 Project" -> 35)
            parent = f.parent.name
            match = re.match(r'^(\d+)', parent)
            if match:
                num = int(match.group(1))
                if num >= args.min_number:
                    filtered.append(f)
        als_files = filtered
        print(f"Found {len(als_files)} projects numbered {args.min_number}+")

    # Apply limit
    if args.limit:
        als_files = als_files[:args.limit]

    if not als_files:
        print("No matching projects found.")
        return

    result = scanner.scan_files([str(f) for f in als_files])
    print(scanner.generate_report(result))


def cmd_quick(args):
    """Quick health check - just the score."""
    from effect_chain_doctor import diagnose_project

    diagnosis = diagnose_project(args.file, verbose=False)

    # Determine grade
    score = diagnosis.overall_health
    if score >= 80:
        grade = "A"
        status = "GREAT"
    elif score >= 60:
        grade = "B"
        status = "GOOD"
    elif score >= 40:
        grade = "C"
        status = "NEEDS WORK"
    elif score >= 20:
        grade = "D"
        status = "SIGNIFICANT ISSUES"
    else:
        grade = "F"
        status = "MAJOR PROBLEMS"

    print(f"[{grade}] {score}/100 - {status}")
    print(f"    {diagnosis.total_issues} issues ({diagnosis.critical_issues} critical, {diagnosis.warning_issues} warnings)")
    print(f"    {diagnosis.total_devices} devices, {diagnosis.total_disabled} disabled ({diagnosis.clutter_percentage:.0f}% clutter)")


def main():
    parser = argparse.ArgumentParser(
        description="ALS Doctor - Ableton Project Health Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s diagnose project.als
  %(prog)s compare old.als new.als
  %(prog)s scan "D:/Ableton Projects" --limit 20
  %(prog)s quick project.als
        """
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Diagnose command
    p_diagnose = subparsers.add_parser('diagnose', help='Full diagnosis of a project')
    p_diagnose.add_argument('file', help='Path to .als file')
    p_diagnose.add_argument('--json', help='Export results to JSON file')
    p_diagnose.set_defaults(func=cmd_diagnose)

    # Compare command
    p_compare = subparsers.add_parser('compare', help='Compare two project versions')
    p_compare.add_argument('before', help='Path to earlier version')
    p_compare.add_argument('after', help='Path to later version')
    p_compare.set_defaults(func=cmd_compare)

    # Scan command
    p_scan = subparsers.add_parser('scan', help='Batch scan directory')
    p_scan.add_argument('directory', help='Directory to scan')
    p_scan.add_argument('--limit', type=int, help='Limit number of files to scan')
    p_scan.add_argument('--min-number', type=int, help='Only scan projects with folder names starting with this number or higher (e.g., --min-number 22)')
    p_scan.add_argument('--no-recursive', action='store_true', help='Do not scan subdirectories')
    p_scan.set_defaults(func=cmd_scan)

    # Quick command
    p_quick = subparsers.add_parser('quick', help='Quick health check')
    p_quick.add_argument('file', help='Path to .als file')
    p_quick.set_defaults(func=cmd_quick)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        args.func(args)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
