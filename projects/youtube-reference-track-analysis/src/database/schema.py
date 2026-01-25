"""
Database schema for YouTube reference track analysis.

All tables are prefixed with 'yt_' to avoid conflicts with the existing
als-doctor tables in the shared database (data/projects.db).
"""

import sqlite3
from pathlib import Path
from typing import Optional

# Default database path (shared with als-doctor)
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "projects.db"

# List of all yt_ tables
YT_TABLES = [
    'yt_tracks',
    'yt_features',
    'yt_sections',
    'yt_arrangement_stats',
    'yt_embeddings',
    'yt_stems',
]

SCHEMA_SQL = """
-- YouTube track metadata
CREATE TABLE IF NOT EXISTS yt_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_id TEXT UNIQUE NOT NULL,
    youtube_url TEXT NOT NULL,
    title TEXT,
    artist TEXT,
    channel TEXT,
    duration_seconds REAL,
    local_path TEXT,
    thumbnail_url TEXT,
    upload_date TEXT,

    -- Analysis status
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analyzed_at TIMESTAMP,
    stems_separated_at TIMESTAMP,
    embeddings_generated_at TIMESTAMP,

    -- User metadata
    genre_tag TEXT DEFAULT 'trance',
    user_tags TEXT,
    notes TEXT,

    -- Rating (1-3 stars, NULL = unrated)
    -- 1 = Good reference, 2 = Great reference, 3 = Top-tier favorite
    rating INTEGER CHECK (rating IS NULL OR (rating >= 1 AND rating <= 3))
);

-- Core audio features
CREATE TABLE IF NOT EXISTS yt_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL UNIQUE,

    -- Rhythm
    bpm REAL,
    bpm_confidence REAL,
    time_signature INTEGER DEFAULT 4,

    -- Key
    key_name TEXT,
    key_camelot TEXT,
    key_confidence REAL,

    -- Loudness
    integrated_lufs REAL,
    short_term_max_lufs REAL,
    true_peak_db REAL,
    loudness_range_lu REAL,

    -- Spectral
    spectral_centroid_hz REAL,
    spectral_bandwidth_hz REAL,
    spectral_rolloff_hz REAL,
    spectral_flatness REAL,

    -- Dynamics
    dynamic_range_db REAL,
    crest_factor_db REAL,

    -- Stereo
    stereo_width REAL,
    stereo_correlation REAL,
    mono_compatible INTEGER,

    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (track_id) REFERENCES yt_tracks(id) ON DELETE CASCADE
);

-- Detected sections
CREATE TABLE IF NOT EXISTS yt_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,

    -- Section info
    section_type TEXT NOT NULL,
    original_label TEXT,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    start_bar INTEGER,
    end_bar INTEGER,
    duration_bars INTEGER,

    -- Section metrics
    avg_energy REAL,
    avg_spectral_centroid REAL,

    -- Ordering
    section_index INTEGER,

    FOREIGN KEY (track_id) REFERENCES yt_tracks(id) ON DELETE CASCADE
);

-- Trance-specific arrangement statistics
CREATE TABLE IF NOT EXISTS yt_arrangement_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL UNIQUE,

    -- Structure timing (in bars)
    total_bars INTEGER,
    bars_to_first_drop INTEGER,
    bars_to_first_breakdown INTEGER,

    -- Section counts
    num_drops INTEGER,
    num_breakdowns INTEGER,
    num_buildups INTEGER,

    -- Buildup analysis
    avg_buildup_length_bars REAL,
    max_buildup_length_bars INTEGER,

    -- Drop analysis
    avg_drop_length_bars REAL,
    first_drop_energy REAL,
    drop_intensity_variance REAL,

    -- Breakdown analysis
    avg_breakdown_length_bars REAL,

    -- Phrase structure
    phrase_length_bars INTEGER,
    phrase_regularity REAL,

    -- Detection results (JSON)
    filter_sweeps_json TEXT,
    risers_json TEXT,

    FOREIGN KEY (track_id) REFERENCES yt_tracks(id) ON DELETE CASCADE
);

-- Audio embeddings for similarity search
CREATE TABLE IF NOT EXISTS yt_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,

    embedding_type TEXT NOT NULL,
    section_id INTEGER,

    embedding BLOB NOT NULL,
    embedding_dim INTEGER NOT NULL,

    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (track_id) REFERENCES yt_tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES yt_sections(id) ON DELETE CASCADE,

    UNIQUE(track_id, embedding_type, section_id)
);

-- Stem-level analysis
CREATE TABLE IF NOT EXISTS yt_stems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    stem_type TEXT NOT NULL,

    local_path TEXT,
    peak_db REAL,
    rms_db REAL,
    spectral_centroid_hz REAL,
    dominant_freq_hz REAL,

    presence_ratio REAL,
    energy_profile TEXT,

    FOREIGN KEY (track_id) REFERENCES yt_tracks(id) ON DELETE CASCADE,
    UNIQUE(track_id, stem_type)
);

-- Indexes for common queries (excluding rating - handled in migrations)
CREATE INDEX IF NOT EXISTS idx_yt_tracks_youtube_id ON yt_tracks(youtube_id);
CREATE INDEX IF NOT EXISTS idx_yt_tracks_genre ON yt_tracks(genre_tag);
CREATE INDEX IF NOT EXISTS idx_yt_features_bpm ON yt_features(bpm);
CREATE INDEX IF NOT EXISTS idx_yt_features_key ON yt_features(key_name);
CREATE INDEX IF NOT EXISTS idx_yt_sections_track_type ON yt_sections(track_id, section_type);
CREATE INDEX IF NOT EXISTS idx_yt_embeddings_type ON yt_embeddings(track_id, embedding_type);
"""


def _run_migrations(conn: sqlite3.Connection) -> None:
    """
    Run schema migrations for existing tables.

    Adds any new columns that may be missing from existing installations.
    """
    # Check if rating column exists in yt_tracks
    cursor = conn.execute("PRAGMA table_info(yt_tracks)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'rating' not in columns:
        conn.execute("""
            ALTER TABLE yt_tracks
            ADD COLUMN rating INTEGER CHECK (rating IS NULL OR (rating >= 1 AND rating <= 3))
        """)

    # Create rating index (safe to run multiple times)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_yt_tracks_rating ON yt_tracks(rating)")

    # Add other migrations here as needed


def init_yt_schema(db_path: Optional[Path] = None) -> tuple[bool, str]:
    """
    Initialize YouTube reference track tables in the database.

    Creates all yt_ prefixed tables. Safe to call multiple times
    (uses CREATE TABLE IF NOT EXISTS).

    Args:
        db_path: Path to database file. Defaults to data/projects.db

    Returns:
        Tuple of (success: bool, message: str)
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    db_path = Path(db_path)

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")

        # Execute schema
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        # Run migrations for existing tables (add columns that may be missing)
        _run_migrations(conn)
        conn.commit()

        # Verify tables were created
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'yt_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        conn.close()

        if len(tables) >= len(YT_TABLES):
            return True, f"YouTube schema initialized at {db_path}\n  Tables: {', '.join(sorted(tables))}"
        else:
            return False, f"Schema incomplete. Found tables: {tables}"

    except sqlite3.Error as e:
        return False, f"Database error: {e}"
    except Exception as e:
        return False, f"Error initializing schema: {e}"


def check_yt_schema(db_path: Optional[Path] = None) -> tuple[bool, list[str]]:
    """
    Check if YouTube tables exist in the database.

    Returns:
        Tuple of (all_tables_exist: bool, existing_tables: list)
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    db_path = Path(db_path)

    if not db_path.exists():
        return False, []

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'yt_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        all_exist = all(t in tables for t in YT_TABLES)
        return all_exist, tables

    except sqlite3.Error:
        return False, []
