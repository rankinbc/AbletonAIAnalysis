"""
Repository for YouTube reference track database operations.

Provides CRUD operations for all yt_ tables.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
from contextlib import contextmanager

from .schema import DEFAULT_DB_PATH, check_yt_schema
from .models import (
    YTTrack, YTFeatures, YTSection, YTArrangementStats,
    YTEmbedding, YTStem, TrackSummary, TrackDetail, SimilarTrack
)


class YTRepository:
    """Repository for YouTube track database operations."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def is_initialized(self) -> bool:
        """Check if yt_ tables exist."""
        all_exist, _ = check_yt_schema(self.db_path)
        return all_exist

    # ==================== TRACK OPERATIONS ====================

    def create_track(self, track: YTTrack) -> Tuple[bool, str, Optional[int]]:
        """
        Create a new track record.

        Returns:
            (success, message, track_id)
        """
        if not self.is_initialized():
            return False, "Database not initialized. Run 'yt-analyzer db init' first.", None

        with self.connection() as conn:
            try:
                cursor = conn.execute("""
                    INSERT INTO yt_tracks (
                        youtube_id, youtube_url, title, artist, channel,
                        duration_seconds, local_path, thumbnail_url, upload_date,
                        genre_tag, user_tags, notes, rating
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    track.youtube_id, track.youtube_url, track.title, track.artist,
                    track.channel, track.duration_seconds, track.local_path,
                    track.thumbnail_url, track.upload_date, track.genre_tag,
                    track.user_tags, track.notes, track.rating
                ))
                track_id = cursor.lastrowid
                return True, f"Created track: {track.title or track.youtube_id}", track_id
            except sqlite3.IntegrityError:
                # Track already exists
                cursor = conn.execute(
                    "SELECT id FROM yt_tracks WHERE youtube_id = ?",
                    (track.youtube_id,)
                )
                row = cursor.fetchone()
                if row:
                    return True, f"Track already exists: {track.youtube_id}", row['id']
                return False, f"Integrity error for track: {track.youtube_id}", None

    def get_track_by_youtube_id(self, youtube_id: str) -> Optional[YTTrack]:
        """Get a track by its YouTube ID."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM yt_tracks WHERE youtube_id = ?",
                (youtube_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_track(row)
        return None

    def get_track_by_id(self, track_id: int) -> Optional[YTTrack]:
        """Get a track by its database ID."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM yt_tracks WHERE id = ?",
                (track_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_track(row)
        return None

    def update_track(self, track: YTTrack) -> Tuple[bool, str]:
        """Update an existing track record."""
        if not track.id:
            return False, "Track ID required for update"

        with self.connection() as conn:
            conn.execute("""
                UPDATE yt_tracks SET
                    title = ?, artist = ?, channel = ?, duration_seconds = ?,
                    local_path = ?, thumbnail_url = ?, upload_date = ?,
                    analyzed_at = ?, stems_separated_at = ?, embeddings_generated_at = ?,
                    genre_tag = ?, user_tags = ?, notes = ?, rating = ?
                WHERE id = ?
            """, (
                track.title, track.artist, track.channel, track.duration_seconds,
                track.local_path, track.thumbnail_url, track.upload_date,
                track.analyzed_at, track.stems_separated_at, track.embeddings_generated_at,
                track.genre_tag, track.user_tags, track.notes, track.rating, track.id
            ))
            return True, f"Updated track: {track.title or track.youtube_id}"

    def list_tracks(
        self,
        genre: Optional[str] = None,
        analyzed_only: bool = False,
        not_analyzed_only: bool = False,
        rating: Optional[int] = None,
        min_rating: Optional[int] = None,
        favorites_only: bool = False,
        limit: int = 100
    ) -> List[TrackSummary]:
        """List tracks with optional filters.

        Args:
            genre: Filter by genre tag
            analyzed_only: Only show analyzed tracks
            not_analyzed_only: Only show non-analyzed tracks
            rating: Filter by exact rating (1, 2, or 3)
            min_rating: Filter by minimum rating (e.g., 2 = 2 and 3 stars)
            favorites_only: Shorthand for min_rating=3 (top-tier only)
            limit: Maximum results
        """
        query = """
            SELECT t.*, f.bpm, f.key_name, f.key_camelot
            FROM yt_tracks t
            LEFT JOIN yt_features f ON t.id = f.track_id
            WHERE 1=1
        """
        params = []

        if genre:
            query += " AND t.genre_tag = ?"
            params.append(genre)
        if analyzed_only:
            query += " AND t.analyzed_at IS NOT NULL"
        if not_analyzed_only:
            query += " AND t.analyzed_at IS NULL"
        if favorites_only:
            query += " AND t.rating = 3"
        elif rating is not None:
            query += " AND t.rating = ?"
            params.append(rating)
        elif min_rating is not None:
            query += " AND t.rating >= ?"
            params.append(min_rating)

        query += " ORDER BY t.rating DESC NULLS LAST, t.ingested_at DESC LIMIT ?"
        params.append(limit)

        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_summary(row) for row in cursor.fetchall()]

    def set_rating(self, youtube_id: str, rating: Optional[int]) -> Tuple[bool, str]:
        """
        Set rating for a track.

        Args:
            youtube_id: YouTube ID of the track
            rating: 1-3 stars, or None to clear rating

        Returns:
            (success, message)
        """
        if rating is not None and (rating < 1 or rating > 3):
            return False, "Rating must be 1, 2, or 3 (or None to clear)"

        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT id, title FROM yt_tracks WHERE youtube_id = ?",
                (youtube_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False, f"Track not found: {youtube_id}"

            conn.execute(
                "UPDATE yt_tracks SET rating = ? WHERE youtube_id = ?",
                (rating, youtube_id)
            )

            if rating:
                stars = "*" * rating + "-" * (3 - rating)
                return True, f"Set rating to {stars} for: {row['title'] or youtube_id}"
            else:
                return True, f"Cleared rating for: {row['title'] or youtube_id}"

    def delete_track(self, track_id: int) -> Tuple[bool, str]:
        """Delete a track and all related data (cascade)."""
        with self.connection() as conn:
            cursor = conn.execute("SELECT title, youtube_id FROM yt_tracks WHERE id = ?", (track_id,))
            row = cursor.fetchone()
            if not row:
                return False, f"Track {track_id} not found"

            conn.execute("DELETE FROM yt_tracks WHERE id = ?", (track_id,))
            return True, f"Deleted track: {row['title'] or row['youtube_id']}"

    # ==================== FEATURES OPERATIONS ====================

    def save_features(self, features: YTFeatures) -> Tuple[bool, str]:
        """Save or update features for a track (upsert)."""
        with self.connection() as conn:
            conn.execute("""
                INSERT INTO yt_features (
                    track_id, bpm, bpm_confidence, time_signature,
                    key_name, key_camelot, key_confidence,
                    integrated_lufs, short_term_max_lufs, true_peak_db, loudness_range_lu,
                    spectral_centroid_hz, spectral_bandwidth_hz, spectral_rolloff_hz, spectral_flatness,
                    dynamic_range_db, crest_factor_db,
                    stereo_width, stereo_correlation, mono_compatible
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    bpm = excluded.bpm,
                    bpm_confidence = excluded.bpm_confidence,
                    time_signature = excluded.time_signature,
                    key_name = excluded.key_name,
                    key_camelot = excluded.key_camelot,
                    key_confidence = excluded.key_confidence,
                    integrated_lufs = excluded.integrated_lufs,
                    short_term_max_lufs = excluded.short_term_max_lufs,
                    true_peak_db = excluded.true_peak_db,
                    loudness_range_lu = excluded.loudness_range_lu,
                    spectral_centroid_hz = excluded.spectral_centroid_hz,
                    spectral_bandwidth_hz = excluded.spectral_bandwidth_hz,
                    spectral_rolloff_hz = excluded.spectral_rolloff_hz,
                    spectral_flatness = excluded.spectral_flatness,
                    dynamic_range_db = excluded.dynamic_range_db,
                    crest_factor_db = excluded.crest_factor_db,
                    stereo_width = excluded.stereo_width,
                    stereo_correlation = excluded.stereo_correlation,
                    mono_compatible = excluded.mono_compatible,
                    analyzed_at = CURRENT_TIMESTAMP
            """, (
                features.track_id, features.bpm, features.bpm_confidence, features.time_signature,
                features.key_name, features.key_camelot, features.key_confidence,
                features.integrated_lufs, features.short_term_max_lufs, features.true_peak_db,
                features.loudness_range_lu, features.spectral_centroid_hz, features.spectral_bandwidth_hz,
                features.spectral_rolloff_hz, features.spectral_flatness,
                features.dynamic_range_db, features.crest_factor_db,
                features.stereo_width, features.stereo_correlation,
                1 if features.mono_compatible else 0 if features.mono_compatible is not None else None
            ))

            # Update track's analyzed_at
            conn.execute(
                "UPDATE yt_tracks SET analyzed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (features.track_id,)
            )
            return True, f"Saved features for track {features.track_id}"

    def get_features(self, track_id: int) -> Optional[YTFeatures]:
        """Get features for a track."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM yt_features WHERE track_id = ?",
                (track_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_features(row)
        return None

    # ==================== SECTIONS OPERATIONS ====================

    def save_sections(self, sections: List[YTSection]) -> Tuple[bool, str]:
        """Save sections for a track (replaces existing)."""
        if not sections:
            return True, "No sections to save"

        track_id = sections[0].track_id

        with self.connection() as conn:
            # Delete existing sections
            conn.execute("DELETE FROM yt_sections WHERE track_id = ?", (track_id,))

            # Insert new sections
            for section in sections:
                conn.execute("""
                    INSERT INTO yt_sections (
                        track_id, section_type, original_label, start_time, end_time,
                        start_bar, end_bar, duration_bars, avg_energy, avg_spectral_centroid,
                        section_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    section.track_id, section.section_type, section.original_label,
                    section.start_time, section.end_time, section.start_bar, section.end_bar,
                    section.duration_bars, section.avg_energy, section.avg_spectral_centroid,
                    section.section_index
                ))

            return True, f"Saved {len(sections)} sections for track {track_id}"

    def get_sections(self, track_id: int) -> List[YTSection]:
        """Get all sections for a track."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM yt_sections WHERE track_id = ? ORDER BY section_index",
                (track_id,)
            )
            return [self._row_to_section(row) for row in cursor.fetchall()]

    def delete_sections(self, track_id: int) -> Tuple[int, str]:
        """
        Delete all sections for a track.

        Returns:
            (count_deleted, message)
        """
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM yt_sections WHERE track_id = ?",
                (track_id,)
            )
            count = cursor.rowcount
            return count, f"Deleted {count} sections for track {track_id}"

    def save_structure(
        self,
        track_id: int,
        sections: List[YTSection],
        arrangement: Optional[YTArrangementStats] = None
    ) -> Tuple[bool, str]:
        """
        Save complete structure analysis (sections + arrangement stats).

        Args:
            track_id: Track ID
            sections: List of sections to save
            arrangement: Optional arrangement statistics

        Returns:
            (success, message)
        """
        messages = []

        # Save sections
        if sections:
            success, msg = self.save_sections(sections)
            messages.append(msg)
            if not success:
                return False, msg

        # Save arrangement stats if provided
        if arrangement:
            success, msg = self.save_arrangement_stats(arrangement)
            messages.append(msg)
            if not success:
                return False, msg

        return True, " | ".join(messages)

    # ==================== ARRANGEMENT OPERATIONS ====================

    def save_arrangement_stats(self, stats: YTArrangementStats) -> Tuple[bool, str]:
        """Save arrangement statistics (upsert)."""
        with self.connection() as conn:
            conn.execute("""
                INSERT INTO yt_arrangement_stats (
                    track_id, total_bars, bars_to_first_drop, bars_to_first_breakdown,
                    num_drops, num_breakdowns, num_buildups,
                    avg_buildup_length_bars, max_buildup_length_bars,
                    avg_drop_length_bars, first_drop_energy, drop_intensity_variance,
                    avg_breakdown_length_bars, phrase_length_bars, phrase_regularity,
                    filter_sweeps_json, risers_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    total_bars = excluded.total_bars,
                    bars_to_first_drop = excluded.bars_to_first_drop,
                    bars_to_first_breakdown = excluded.bars_to_first_breakdown,
                    num_drops = excluded.num_drops,
                    num_breakdowns = excluded.num_breakdowns,
                    num_buildups = excluded.num_buildups,
                    avg_buildup_length_bars = excluded.avg_buildup_length_bars,
                    max_buildup_length_bars = excluded.max_buildup_length_bars,
                    avg_drop_length_bars = excluded.avg_drop_length_bars,
                    first_drop_energy = excluded.first_drop_energy,
                    drop_intensity_variance = excluded.drop_intensity_variance,
                    avg_breakdown_length_bars = excluded.avg_breakdown_length_bars,
                    phrase_length_bars = excluded.phrase_length_bars,
                    phrase_regularity = excluded.phrase_regularity,
                    filter_sweeps_json = excluded.filter_sweeps_json,
                    risers_json = excluded.risers_json
            """, (
                stats.track_id, stats.total_bars, stats.bars_to_first_drop,
                stats.bars_to_first_breakdown, stats.num_drops, stats.num_breakdowns,
                stats.num_buildups, stats.avg_buildup_length_bars, stats.max_buildup_length_bars,
                stats.avg_drop_length_bars, stats.first_drop_energy, stats.drop_intensity_variance,
                stats.avg_breakdown_length_bars, stats.phrase_length_bars, stats.phrase_regularity,
                stats.filter_sweeps_json, stats.risers_json
            ))
            return True, f"Saved arrangement stats for track {stats.track_id}"

    def get_arrangement_stats(self, track_id: int) -> Optional[YTArrangementStats]:
        """Get arrangement statistics for a track."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM yt_arrangement_stats WHERE track_id = ?",
                (track_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_arrangement(row)
        return None

    # ==================== DETAIL VIEW ====================

    def get_track_detail(self, youtube_id: str) -> Optional[TrackDetail]:
        """Get full detail view of a track."""
        track = self.get_track_by_youtube_id(youtube_id)
        if not track:
            return None

        return TrackDetail(
            track=track,
            features=self.get_features(track.id),
            sections=self.get_sections(track.id),
            arrangement=self.get_arrangement_stats(track.id),
            stems=self.get_stems(track.id)
        )

    # ==================== STEMS OPERATIONS ====================

    def save_stem(self, stem: YTStem) -> Tuple[bool, str]:
        """Save stem analysis (upsert)."""
        with self.connection() as conn:
            conn.execute("""
                INSERT INTO yt_stems (
                    track_id, stem_type, local_path, peak_db, rms_db,
                    spectral_centroid_hz, dominant_freq_hz, presence_ratio, energy_profile
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id, stem_type) DO UPDATE SET
                    local_path = excluded.local_path,
                    peak_db = excluded.peak_db,
                    rms_db = excluded.rms_db,
                    spectral_centroid_hz = excluded.spectral_centroid_hz,
                    dominant_freq_hz = excluded.dominant_freq_hz,
                    presence_ratio = excluded.presence_ratio,
                    energy_profile = excluded.energy_profile
            """, (
                stem.track_id, stem.stem_type, stem.local_path, stem.peak_db, stem.rms_db,
                stem.spectral_centroid_hz, stem.dominant_freq_hz, stem.presence_ratio,
                stem.energy_profile
            ))

            # Update track's stems_separated_at
            conn.execute(
                "UPDATE yt_tracks SET stems_separated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (stem.track_id,)
            )
            return True, f"Saved {stem.stem_type} stem for track {stem.track_id}"

    def get_stems(self, track_id: int) -> List[YTStem]:
        """Get all stems for a track."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM yt_stems WHERE track_id = ?",
                (track_id,)
            )
            return [self._row_to_stem(row) for row in cursor.fetchall()]

    # ==================== STATS ====================

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self.connection() as conn:
            stats = {}
            stats['tracks'] = conn.execute("SELECT COUNT(*) FROM yt_tracks").fetchone()[0]
            stats['analyzed'] = conn.execute(
                "SELECT COUNT(*) FROM yt_tracks WHERE analyzed_at IS NOT NULL"
            ).fetchone()[0]
            stats['with_stems'] = conn.execute(
                "SELECT COUNT(*) FROM yt_tracks WHERE stems_separated_at IS NOT NULL"
            ).fetchone()[0]
            stats['with_embeddings'] = conn.execute(
                "SELECT COUNT(*) FROM yt_tracks WHERE embeddings_generated_at IS NOT NULL"
            ).fetchone()[0]
            return stats

    # ==================== HELPER METHODS ====================

    def _row_to_track(self, row: sqlite3.Row) -> YTTrack:
        return YTTrack(
            id=row['id'],
            youtube_id=row['youtube_id'],
            youtube_url=row['youtube_url'],
            title=row['title'],
            artist=row['artist'],
            channel=row['channel'],
            duration_seconds=row['duration_seconds'],
            local_path=row['local_path'],
            thumbnail_url=row['thumbnail_url'],
            upload_date=row['upload_date'],
            ingested_at=row['ingested_at'],
            analyzed_at=row['analyzed_at'],
            stems_separated_at=row['stems_separated_at'],
            embeddings_generated_at=row['embeddings_generated_at'],
            genre_tag=row['genre_tag'] or 'trance',
            user_tags=row['user_tags'],
            notes=row['notes'],
            rating=row['rating'] if 'rating' in row.keys() else None
        )

    def _row_to_summary(self, row: sqlite3.Row) -> TrackSummary:
        return TrackSummary(
            id=row['id'],
            youtube_id=row['youtube_id'],
            title=row['title'],
            artist=row['artist'],
            duration_seconds=row['duration_seconds'],
            bpm=row['bpm'] if 'bpm' in row.keys() else None,
            key_name=row['key_name'] if 'key_name' in row.keys() else None,
            key_camelot=row['key_camelot'] if 'key_camelot' in row.keys() else None,
            genre_tag=row['genre_tag'] or 'trance',
            rating=row['rating'] if 'rating' in row.keys() else None,
            is_analyzed=row['analyzed_at'] is not None,
            has_stems=row['stems_separated_at'] is not None,
            has_embeddings=row['embeddings_generated_at'] is not None,
            ingested_at=row['ingested_at']
        )

    def _row_to_features(self, row: sqlite3.Row) -> YTFeatures:
        return YTFeatures(
            id=row['id'],
            track_id=row['track_id'],
            bpm=row['bpm'],
            bpm_confidence=row['bpm_confidence'],
            time_signature=row['time_signature'] or 4,
            key_name=row['key_name'],
            key_camelot=row['key_camelot'],
            key_confidence=row['key_confidence'],
            integrated_lufs=row['integrated_lufs'],
            short_term_max_lufs=row['short_term_max_lufs'],
            true_peak_db=row['true_peak_db'],
            loudness_range_lu=row['loudness_range_lu'],
            spectral_centroid_hz=row['spectral_centroid_hz'],
            spectral_bandwidth_hz=row['spectral_bandwidth_hz'],
            spectral_rolloff_hz=row['spectral_rolloff_hz'],
            spectral_flatness=row['spectral_flatness'],
            dynamic_range_db=row['dynamic_range_db'],
            crest_factor_db=row['crest_factor_db'],
            stereo_width=row['stereo_width'],
            stereo_correlation=row['stereo_correlation'],
            mono_compatible=bool(row['mono_compatible']) if row['mono_compatible'] is not None else None,
            analyzed_at=row['analyzed_at']
        )

    def _row_to_section(self, row: sqlite3.Row) -> YTSection:
        return YTSection(
            id=row['id'],
            track_id=row['track_id'],
            section_type=row['section_type'],
            original_label=row['original_label'],
            start_time=row['start_time'],
            end_time=row['end_time'],
            start_bar=row['start_bar'],
            end_bar=row['end_bar'],
            duration_bars=row['duration_bars'],
            avg_energy=row['avg_energy'],
            avg_spectral_centroid=row['avg_spectral_centroid'],
            section_index=row['section_index'] or 0
        )

    def _row_to_arrangement(self, row: sqlite3.Row) -> YTArrangementStats:
        return YTArrangementStats(
            id=row['id'],
            track_id=row['track_id'],
            total_bars=row['total_bars'],
            bars_to_first_drop=row['bars_to_first_drop'],
            bars_to_first_breakdown=row['bars_to_first_breakdown'],
            num_drops=row['num_drops'] or 0,
            num_breakdowns=row['num_breakdowns'] or 0,
            num_buildups=row['num_buildups'] or 0,
            avg_buildup_length_bars=row['avg_buildup_length_bars'],
            max_buildup_length_bars=row['max_buildup_length_bars'],
            avg_drop_length_bars=row['avg_drop_length_bars'],
            first_drop_energy=row['first_drop_energy'],
            drop_intensity_variance=row['drop_intensity_variance'],
            avg_breakdown_length_bars=row['avg_breakdown_length_bars'],
            phrase_length_bars=row['phrase_length_bars'],
            phrase_regularity=row['phrase_regularity'],
            filter_sweeps_json=row['filter_sweeps_json'],
            risers_json=row['risers_json']
        )

    def _row_to_stem(self, row: sqlite3.Row) -> YTStem:
        return YTStem(
            id=row['id'],
            track_id=row['track_id'],
            stem_type=row['stem_type'],
            local_path=row['local_path'],
            peak_db=row['peak_db'],
            rms_db=row['rms_db'],
            spectral_centroid_hz=row['spectral_centroid_hz'],
            dominant_freq_hz=row['dominant_freq_hz'],
            presence_ratio=row['presence_ratio'],
            energy_profile=row['energy_profile']
        )
