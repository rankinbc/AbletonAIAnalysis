#!/usr/bin/env python3
"""
Scheduled Scan Wrapper Script for ALS Doctor

This script is designed to be called by cron (Linux/macOS) or Task Scheduler (Windows)
to run scheduled batch scans.

Usage:
    python run_scheduled_scans.py              # Run all due schedules
    python run_scheduled_scans.py --all        # Force run all schedules
    python run_scheduled_scans.py --id <id>    # Run specific schedule
    python run_scheduled_scans.py --quiet      # Suppress output

Example cron entry (run due schedules every hour):
    0 * * * * /usr/bin/python3 /path/to/run_scheduled_scans.py >> /path/to/cron.log 2>&1

Example Windows Task Scheduler:
    Program: python.exe
    Arguments: /path/to/run_scheduled_scans.py
    Start in: /path/to/AbletonAIAnalysis/projects/music-analyzer
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def main():
    parser = argparse.ArgumentParser(
        description="Run scheduled ALS Doctor scans"
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Force run all schedules (ignore due time)'
    )
    parser.add_argument(
        '--id', '-i',
        type=str,
        default=None,
        help='Run specific schedule by ID or name'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress output'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all schedules and exit'
    )

    args = parser.parse_args()

    try:
        from scheduler import (
            list_schedules, run_schedule, run_due_schedules,
            check_due_schedules, get_schedule_by_id
        )
        from database import get_db
    except ImportError as e:
        print(f"Error importing modules: {e}", file=sys.stderr)
        sys.exit(1)

    # List mode
    if args.list:
        schedules, msg = list_schedules()
        if not schedules:
            print("No schedules configured.")
            sys.exit(0)

        print("Configured Schedules:")
        print("-" * 70)
        for schedule in schedules:
            status = "enabled" if schedule.enabled else "disabled"
            last_run = schedule.last_run_at[:16] if schedule.last_run_at else "never"
            print(f"  [{schedule.id}] {schedule.name}")
            print(f"      Folder: {schedule.folder_path}")
            print(f"      Frequency: {schedule.frequency} | Status: {status}")
            print(f"      Last run: {last_run}")
            print()
        sys.exit(0)

    # Check database
    db = get_db()
    if not db.is_initialized():
        if not args.quiet:
            print("Error: Database not initialized. Run 'als-doctor db init' first.",
                  file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Run specific schedule
    if args.id:
        if not args.quiet:
            print(f"[{timestamp}] Running schedule: {args.id}")

        result, msg = run_schedule(args.id, quiet=args.quiet)

        if result.success:
            if not args.quiet:
                print(f"[{timestamp}] Completed: {result.summary}")
            sys.exit(0)
        else:
            if not args.quiet:
                print(f"[{timestamp}] Failed: {result.error_message}", file=sys.stderr)
            sys.exit(1)

    # Run all schedules (force)
    if args.all:
        schedules, msg = list_schedules()
        if not schedules:
            if not args.quiet:
                print(f"[{timestamp}] No schedules configured.")
            sys.exit(0)

        if not args.quiet:
            print(f"[{timestamp}] Running all {len(schedules)} schedule(s)")

        success_count = 0
        fail_count = 0

        for schedule in schedules:
            if not schedule.enabled:
                if not args.quiet:
                    print(f"  Skipping disabled schedule: {schedule.name}")
                continue

            if not args.quiet:
                print(f"  Running: {schedule.name}")

            result, msg = run_schedule(schedule.id, quiet=args.quiet)

            if result.success:
                success_count += 1
                if not args.quiet:
                    print(f"    Completed: {result.summary}")
            else:
                fail_count += 1
                if not args.quiet:
                    print(f"    Failed: {result.error_message}")

        if not args.quiet:
            print(f"[{timestamp}] Finished: {success_count} succeeded, {fail_count} failed")

        sys.exit(0 if fail_count == 0 else 1)

    # Run due schedules (default)
    due_schedules = check_due_schedules()

    if not due_schedules:
        if not args.quiet:
            print(f"[{timestamp}] No schedules due to run.")
        sys.exit(0)

    if not args.quiet:
        print(f"[{timestamp}] Running {len(due_schedules)} due schedule(s)")

    results = run_due_schedules(quiet=args.quiet)

    success_count = sum(1 for r in results if r.success)
    fail_count = sum(1 for r in results if not r.success)

    if not args.quiet:
        print(f"[{timestamp}] Finished: {success_count} succeeded, {fail_count} failed")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == '__main__':
    main()
