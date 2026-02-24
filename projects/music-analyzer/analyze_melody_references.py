#!/usr/bin/env python3
"""
Analyze YouTube reference tracks with melody extraction.
Stores results in the SQLite database.
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from reference_analyzer import ReferenceAnalyzer, MelodyAnalysis


DB_PATH = Path(__file__).parent.parent.parent / "data" / "projects.db"


def setup_melody_table(conn: sqlite3.Connection):
    """Create melody analysis table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS yt_melody (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER NOT NULL,
            youtube_id TEXT NOT NULL,
            analyzed_at TIMESTAMP,

            -- Overall metrics
            detected INTEGER,
            confidence REAL,
            pitch_range_semitones INTEGER,
            lowest_note TEXT,
            highest_note TEXT,
            avg_pitch_hz REAL,
            pitch_std_hz REAL,
            note_count INTEGER,
            note_density_per_bar REAL,
            avg_note_duration_ms REAL,

            -- Interval analysis
            most_common_intervals TEXT,  -- JSON array
            interval_distribution TEXT,  -- JSON object

            -- Contour
            contour_direction TEXT,
            contour_complexity REAL,

            -- Scale detection
            detected_scale TEXT,
            scale_confidence REAL,
            in_scale_percentage REAL,

            -- Phrase analysis
            phrase_count INTEGER,
            avg_phrase_length_bars REAL,

            -- Per-section data (JSON)
            section_melody_data TEXT,

            -- Raw pitch contour (JSON, downsampled)
            pitch_contour_hz TEXT,
            pitch_contour_times TEXT,

            FOREIGN KEY (track_id) REFERENCES yt_tracks(id)
        )
    """)

    # Create index
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_yt_melody_track_id ON yt_melody(track_id)
    """)

    conn.commit()
    print("Melody table ready.")


def get_tracks_to_analyze(conn: sqlite3.Connection, limit: int = None) -> list:
    """Get tracks that haven't been melody-analyzed yet."""
    cursor = conn.cursor()

    query = """
        SELECT t.id, t.youtube_id, t.title, t.local_path
        FROM yt_tracks t
        LEFT JOIN yt_melody m ON t.id = m.track_id
        WHERE t.local_path IS NOT NULL
        AND m.id IS NULL
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    return cursor.fetchall()


def save_melody_analysis(
    conn: sqlite3.Connection,
    track_id: int,
    youtube_id: str,
    melody: MelodyAnalysis
):
    """Save melody analysis to database."""
    cursor = conn.cursor()

    overall = melody.overall

    cursor.execute("""
        INSERT INTO yt_melody (
            track_id, youtube_id, analyzed_at,
            detected, confidence, pitch_range_semitones,
            lowest_note, highest_note, avg_pitch_hz, pitch_std_hz,
            note_count, note_density_per_bar, avg_note_duration_ms,
            most_common_intervals, interval_distribution,
            contour_direction, contour_complexity,
            detected_scale, scale_confidence, in_scale_percentage,
            phrase_count, avg_phrase_length_bars,
            section_melody_data, pitch_contour_hz, pitch_contour_times
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        track_id,
        youtube_id,
        datetime.now().isoformat(),
        1 if overall.detected else 0,
        overall.confidence,
        overall.pitch_range_semitones,
        overall.lowest_note,
        overall.highest_note,
        overall.avg_pitch_hz,
        overall.pitch_std_hz,
        overall.note_count,
        overall.note_density_per_bar,
        overall.avg_note_duration_ms,
        json.dumps(overall.most_common_intervals),
        json.dumps(overall.interval_distribution),
        overall.contour_direction,
        overall.contour_complexity,
        overall.detected_scale,
        overall.scale_confidence,
        overall.in_scale_percentage,
        overall.phrase_count,
        overall.avg_phrase_length_bars,
        json.dumps({
            str(k): {
                'detected': v.detected,
                'note_count': v.note_count,
                'contour_direction': v.contour_direction,
                'detected_scale': v.detected_scale,
            } for k, v in melody.by_section.items()
        }),
        json.dumps(overall.pitch_contour_hz[:100]),  # Limit size
        json.dumps(overall.pitch_contour_times[:100]),
    ))

    conn.commit()


def analyze_tracks(limit: int = None, verbose: bool = True):
    """Main analysis function."""
    conn = sqlite3.connect(str(DB_PATH))

    # Setup table
    setup_melody_table(conn)

    # Get tracks to analyze
    tracks = get_tracks_to_analyze(conn, limit)

    if not tracks:
        print("No tracks to analyze (all already have melody data).")
        return

    print(f"Found {len(tracks)} tracks to analyze")
    print("=" * 60)

    # Create analyzer with melody enabled
    analyzer = ReferenceAnalyzer(
        include_stems=False,  # Skip stems for speed
        include_melody=True,
        verbose=False
    )

    success_count = 0
    fail_count = 0
    no_melody_count = 0

    for i, (track_id, youtube_id, title, local_path) in enumerate(tracks):
        print(f"\n[{i+1}/{len(tracks)}] {title[:50]}...")

        if not Path(local_path).exists():
            print(f"  SKIP: File not found")
            fail_count += 1
            continue

        try:
            # Analyze
            result = analyzer.analyze(local_path)

            if not result.success:
                print(f"  FAIL: {result.error_message}")
                fail_count += 1
                continue

            if result.melody_analysis is None:
                print(f"  NO MELODY: Could not extract melody")
                no_melody_count += 1
                continue

            # Save to database
            save_melody_analysis(conn, track_id, youtube_id, result.melody_analysis)

            # Print summary
            m = result.melody_analysis.overall
            print(f"  OK: {m.note_count} notes, range={m.pitch_range_semitones} semitones")
            print(f"      Scale: {m.detected_scale} ({m.scale_confidence*100:.0f}% confidence)")
            print(f"      Contour: {m.contour_direction}, complexity={m.contour_complexity:.2f}")

            success_count += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            fail_count += 1

    conn.close()

    print("\n" + "=" * 60)
    print(f"COMPLETE: {success_count} success, {no_melody_count} no melody, {fail_count} failed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze melody from YouTube reference tracks")
    parser.add_argument("--limit", type=int, help="Limit number of tracks to analyze")
    parser.add_argument("--all", action="store_true", help="Analyze all tracks (no limit)")

    args = parser.parse_args()

    limit = None if args.all else (args.limit or 5)  # Default: 5 tracks

    print(f"Melody Reference Analysis")
    print(f"Analyzing {'all' if limit is None else limit} tracks...")
    print()

    analyze_tracks(limit=limit)
