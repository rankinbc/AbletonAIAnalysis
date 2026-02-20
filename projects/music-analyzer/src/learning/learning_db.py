"""
Learning Database Module.

SQLite-based storage for continuous learning data including
fix feedback, session records, and learned feature weights.
"""

import sqlite3
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path


@dataclass
class FixFeedback:
    """Record of user feedback on a fix recommendation."""
    feedback_id: str
    timestamp: datetime
    track_path: str
    profile_name: str

    # The fix that was recommended
    feature: str
    severity: str
    suggested_change: str
    confidence: float

    # Values
    current_value: float
    target_value: float

    # User decision
    accepted: bool
    modified: bool = False
    user_notes: Optional[str] = None

    # Effectiveness (filled in later)
    pre_gap_score: Optional[float] = None
    post_gap_score: Optional[float] = None
    improvement: Optional[float] = None

    # Session reference
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'feedback_id': self.feedback_id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'track_path': self.track_path,
            'profile_name': self.profile_name,
            'feature': self.feature,
            'severity': self.severity,
            'suggested_change': self.suggested_change,
            'confidence': float(self.confidence),
            'current_value': float(self.current_value),
            'target_value': float(self.target_value),
            'accepted': self.accepted,
            'modified': self.modified,
            'user_notes': self.user_notes,
            'pre_gap_score': float(self.pre_gap_score) if self.pre_gap_score is not None else None,
            'post_gap_score': float(self.post_gap_score) if self.post_gap_score is not None else None,
            'improvement': float(self.improvement) if self.improvement is not None else None,
            'session_id': self.session_id
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'FixFeedback':
        """Create from dict."""
        timestamp = d['timestamp']
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return cls(
            feedback_id=d['feedback_id'],
            timestamp=timestamp,
            track_path=d['track_path'],
            profile_name=d['profile_name'],
            feature=d['feature'],
            severity=d['severity'],
            suggested_change=d['suggested_change'],
            confidence=d['confidence'],
            current_value=d['current_value'],
            target_value=d['target_value'],
            accepted=d['accepted'],
            modified=d.get('modified', False),
            user_notes=d.get('user_notes'),
            pre_gap_score=d.get('pre_gap_score'),
            post_gap_score=d.get('post_gap_score'),
            improvement=d.get('improvement'),
            session_id=d.get('session_id')
        )


@dataclass
class SessionRecord:
    """Record of an analysis session."""
    session_id: str
    timestamp: datetime
    track_path: str
    profile_name: str

    # Initial metrics
    initial_similarity: float
    initial_trance_score: float

    # Fix counts
    fixes_suggested: int
    fixes_accepted: int
    fixes_rejected: int
    fixes_modified: int = 0

    # Final metrics (filled in after re-analysis)
    final_similarity: Optional[float] = None
    final_trance_score: Optional[float] = None

    # Computed improvements
    similarity_improvement: Optional[float] = None
    trance_score_improvement: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'track_path': self.track_path,
            'profile_name': self.profile_name,
            'initial_similarity': float(self.initial_similarity),
            'initial_trance_score': float(self.initial_trance_score),
            'fixes_suggested': self.fixes_suggested,
            'fixes_accepted': self.fixes_accepted,
            'fixes_rejected': self.fixes_rejected,
            'fixes_modified': self.fixes_modified,
            'final_similarity': float(self.final_similarity) if self.final_similarity is not None else None,
            'final_trance_score': float(self.final_trance_score) if self.final_trance_score is not None else None,
            'similarity_improvement': float(self.similarity_improvement) if self.similarity_improvement is not None else None,
            'trance_score_improvement': float(self.trance_score_improvement) if self.trance_score_improvement is not None else None
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SessionRecord':
        """Create from dict."""
        timestamp = d['timestamp']
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return cls(
            session_id=d['session_id'],
            timestamp=timestamp,
            track_path=d['track_path'],
            profile_name=d['profile_name'],
            initial_similarity=d['initial_similarity'],
            initial_trance_score=d['initial_trance_score'],
            fixes_suggested=d['fixes_suggested'],
            fixes_accepted=d['fixes_accepted'],
            fixes_rejected=d['fixes_rejected'],
            fixes_modified=d.get('fixes_modified', 0),
            final_similarity=d.get('final_similarity'),
            final_trance_score=d.get('final_trance_score'),
            similarity_improvement=d.get('similarity_improvement'),
            trance_score_improvement=d.get('trance_score_improvement')
        )


class LearningDatabase:
    """
    SQLite database for continuous learning data.

    Stores fix feedback, session records, and computed feature weights.
    """

    def __init__(self, db_path: str = "learning_data.db"):
        """
        Initialize the learning database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Fix feedback table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fix_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    track_path TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    feature TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    suggested_change TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    current_value REAL NOT NULL,
                    target_value REAL NOT NULL,
                    accepted INTEGER NOT NULL,
                    modified INTEGER NOT NULL DEFAULT 0,
                    user_notes TEXT,
                    pre_gap_score REAL,
                    post_gap_score REAL,
                    improvement REAL,
                    session_id TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            ''')

            # Sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    track_path TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    initial_similarity REAL NOT NULL,
                    initial_trance_score REAL NOT NULL,
                    fixes_suggested INTEGER NOT NULL,
                    fixes_accepted INTEGER NOT NULL,
                    fixes_rejected INTEGER NOT NULL,
                    fixes_modified INTEGER NOT NULL DEFAULT 0,
                    final_similarity REAL,
                    final_trance_score REAL,
                    similarity_improvement REAL,
                    trance_score_improvement REAL
                )
            ''')

            # Feature weights table (learned adjustments)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feature_weights (
                    feature TEXT PRIMARY KEY,
                    confidence_adjustment REAL NOT NULL DEFAULT 1.0,
                    priority_adjustment REAL NOT NULL DEFAULT 1.0,
                    last_updated TEXT NOT NULL,
                    sample_count INTEGER NOT NULL DEFAULT 0
                )
            ''')

            # User preferences table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    preference_key TEXT PRIMARY KEY,
                    preference_value TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            ''')

            # Create indexes for common queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_feedback_feature
                ON fix_feedback(feature)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_feedback_session
                ON fix_feedback(session_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sessions_profile
                ON sessions(profile_name)
            ''')

            conn.commit()

    def record_feedback(self, feedback: FixFeedback):
        """
        Record user feedback on a fix.

        Args:
            feedback: FixFeedback object to store
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO fix_feedback (
                    feedback_id, timestamp, track_path, profile_name,
                    feature, severity, suggested_change, confidence,
                    current_value, target_value, accepted, modified,
                    user_notes, pre_gap_score, post_gap_score, improvement,
                    session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                feedback.feedback_id,
                feedback.timestamp.isoformat() if isinstance(feedback.timestamp, datetime) else feedback.timestamp,
                feedback.track_path,
                feedback.profile_name,
                feedback.feature,
                feedback.severity,
                feedback.suggested_change,
                feedback.confidence,
                feedback.current_value,
                feedback.target_value,
                1 if feedback.accepted else 0,
                1 if feedback.modified else 0,
                feedback.user_notes,
                feedback.pre_gap_score,
                feedback.post_gap_score,
                feedback.improvement,
                feedback.session_id
            ))

            conn.commit()

    def record_session(self, session: SessionRecord):
        """
        Record an analysis session.

        Args:
            session: SessionRecord object to store
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO sessions (
                    session_id, timestamp, track_path, profile_name,
                    initial_similarity, initial_trance_score,
                    fixes_suggested, fixes_accepted, fixes_rejected, fixes_modified,
                    final_similarity, final_trance_score,
                    similarity_improvement, trance_score_improvement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session.session_id,
                session.timestamp.isoformat() if isinstance(session.timestamp, datetime) else session.timestamp,
                session.track_path,
                session.profile_name,
                session.initial_similarity,
                session.initial_trance_score,
                session.fixes_suggested,
                session.fixes_accepted,
                session.fixes_rejected,
                session.fixes_modified,
                session.final_similarity,
                session.final_trance_score,
                session.similarity_improvement,
                session.trance_score_improvement
            ))

            conn.commit()

    def update_session_finals(
        self,
        session_id: str,
        final_similarity: float,
        final_trance_score: float
    ):
        """
        Update a session with final metrics after re-analysis.

        Args:
            session_id: Session to update
            final_similarity: Final similarity score
            final_trance_score: Final trance score
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get initial values
            cursor.execute('''
                SELECT initial_similarity, initial_trance_score
                FROM sessions WHERE session_id = ?
            ''', (session_id,))

            row = cursor.fetchone()
            if row:
                initial_sim, initial_trance = row
                sim_improvement = final_similarity - initial_sim
                trance_improvement = final_trance_score - initial_trance

                cursor.execute('''
                    UPDATE sessions SET
                        final_similarity = ?,
                        final_trance_score = ?,
                        similarity_improvement = ?,
                        trance_score_improvement = ?
                    WHERE session_id = ?
                ''', (
                    final_similarity,
                    final_trance_score,
                    sim_improvement,
                    trance_improvement,
                    session_id
                ))

                conn.commit()

    def update_feedback_effectiveness(
        self,
        feedback_id: str,
        pre_score: float,
        post_score: float
    ):
        """
        Update feedback record with effectiveness data.

        Args:
            feedback_id: Feedback to update
            pre_score: Gap score before fix
            post_score: Gap score after fix
        """
        improvement = pre_score - post_score  # Lower gap score is better

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE fix_feedback SET
                    pre_gap_score = ?,
                    post_gap_score = ?,
                    improvement = ?
                WHERE feedback_id = ?
            ''', (pre_score, post_score, improvement, feedback_id))

            conn.commit()

    def get_feature_acceptance_rate(self, feature: str) -> Tuple[float, int]:
        """
        Get acceptance rate for fixes on a specific feature.

        Args:
            feature: Feature name

        Returns:
            Tuple of (acceptance_rate, sample_count)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) as accepted_count
                FROM fix_feedback
                WHERE feature = ?
            ''', (feature,))

            row = cursor.fetchone()
            if row and row[0] > 0:
                total, accepted_count = row
                return accepted_count / total, total
            return 0.0, 0

    def get_feature_effectiveness(self, feature: str) -> Tuple[float, int]:
        """
        Get average improvement when fix is applied for a feature.

        Args:
            feature: Feature name

        Returns:
            Tuple of (avg_improvement, sample_count)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT AVG(improvement), COUNT(*)
                FROM fix_feedback
                WHERE feature = ? AND accepted = 1 AND improvement IS NOT NULL
            ''', (feature,))

            row = cursor.fetchone()
            if row and row[1] > 0:
                return row[0] or 0.0, row[1]
            return 0.0, 0

    def get_all_feedback(
        self,
        limit: int = 100,
        feature: Optional[str] = None,
        accepted_only: bool = False
    ) -> List[FixFeedback]:
        """
        Get recent feedback records.

        Args:
            limit: Maximum records to return
            feature: Filter by feature name (optional)
            accepted_only: Only return accepted fixes

        Returns:
            List of FixFeedback objects
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = '''
                SELECT feedback_id, timestamp, track_path, profile_name,
                       feature, severity, suggested_change, confidence,
                       current_value, target_value, accepted, modified,
                       user_notes, pre_gap_score, post_gap_score, improvement,
                       session_id
                FROM fix_feedback
                WHERE 1=1
            '''
            params = []

            if feature:
                query += ' AND feature = ?'
                params.append(feature)

            if accepted_only:
                query += ' AND accepted = 1'

            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)

            cursor.execute(query, params)

            records = []
            for row in cursor.fetchall():
                records.append(FixFeedback(
                    feedback_id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    track_path=row[2],
                    profile_name=row[3],
                    feature=row[4],
                    severity=row[5],
                    suggested_change=row[6],
                    confidence=row[7],
                    current_value=row[8],
                    target_value=row[9],
                    accepted=bool(row[10]),
                    modified=bool(row[11]),
                    user_notes=row[12],
                    pre_gap_score=row[13],
                    post_gap_score=row[14],
                    improvement=row[15],
                    session_id=row[16]
                ))

            return records

    def get_all_sessions(self, limit: int = 50) -> List[SessionRecord]:
        """
        Get recent session records.

        Args:
            limit: Maximum records to return

        Returns:
            List of SessionRecord objects
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT session_id, timestamp, track_path, profile_name,
                       initial_similarity, initial_trance_score,
                       fixes_suggested, fixes_accepted, fixes_rejected, fixes_modified,
                       final_similarity, final_trance_score,
                       similarity_improvement, trance_score_improvement
                FROM sessions
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

            records = []
            for row in cursor.fetchall():
                records.append(SessionRecord(
                    session_id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    track_path=row[2],
                    profile_name=row[3],
                    initial_similarity=row[4],
                    initial_trance_score=row[5],
                    fixes_suggested=row[6],
                    fixes_accepted=row[7],
                    fixes_rejected=row[8],
                    fixes_modified=row[9],
                    final_similarity=row[10],
                    final_trance_score=row[11],
                    similarity_improvement=row[12],
                    trance_score_improvement=row[13]
                ))

            return records

    def get_feature_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get comprehensive statistics for all features.

        Returns:
            Dict mapping feature name to stats dict
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    feature,
                    COUNT(*) as suggested,
                    SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) as accepted,
                    SUM(CASE WHEN accepted = 0 THEN 1 ELSE 0 END) as rejected,
                    SUM(CASE WHEN modified = 1 THEN 1 ELSE 0 END) as modified,
                    AVG(CASE WHEN accepted = 1 AND improvement IS NOT NULL THEN improvement END) as avg_improvement
                FROM fix_feedback
                GROUP BY feature
                ORDER BY suggested DESC
            ''')

            stats = {}
            for row in cursor.fetchall():
                feature = row[0]
                suggested = row[1]
                accepted = row[2]
                rejected = row[3]
                modified = row[4]
                avg_improvement = row[5]

                acceptance_rate = accepted / suggested if suggested > 0 else 0.0

                stats[feature] = {
                    'suggested': suggested,
                    'accepted': accepted,
                    'rejected': rejected,
                    'modified': modified,
                    'acceptance_rate': acceptance_rate,
                    'avg_improvement': avg_improvement or 0.0
                }

            return stats

    def get_session_by_id(self, session_id: str) -> Optional[SessionRecord]:
        """Get a specific session by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT session_id, timestamp, track_path, profile_name,
                       initial_similarity, initial_trance_score,
                       fixes_suggested, fixes_accepted, fixes_rejected, fixes_modified,
                       final_similarity, final_trance_score,
                       similarity_improvement, trance_score_improvement
                FROM sessions
                WHERE session_id = ?
            ''', (session_id,))

            row = cursor.fetchone()
            if row:
                return SessionRecord(
                    session_id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    track_path=row[2],
                    profile_name=row[3],
                    initial_similarity=row[4],
                    initial_trance_score=row[5],
                    fixes_suggested=row[6],
                    fixes_accepted=row[7],
                    fixes_rejected=row[8],
                    fixes_modified=row[9],
                    final_similarity=row[10],
                    final_trance_score=row[11],
                    similarity_improvement=row[12],
                    trance_score_improvement=row[13]
                )
            return None

    def get_session_feedback(self, session_id: str) -> List[FixFeedback]:
        """Get all feedback records for a session."""
        return self.get_all_feedback(limit=100, feature=None, accepted_only=False)

    def save_feature_weight(
        self,
        feature: str,
        confidence_adjustment: float,
        priority_adjustment: float,
        sample_count: int
    ):
        """
        Save learned feature weight adjustments.

        Args:
            feature: Feature name
            confidence_adjustment: Multiplier for confidence scores
            priority_adjustment: Multiplier for priority scores
            sample_count: Number of samples used to compute
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO feature_weights
                (feature, confidence_adjustment, priority_adjustment, last_updated, sample_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                feature,
                confidence_adjustment,
                priority_adjustment,
                datetime.now().isoformat(),
                sample_count
            ))

            conn.commit()

    def get_feature_weights(self) -> Dict[str, Dict[str, float]]:
        """
        Get all learned feature weight adjustments.

        Returns:
            Dict mapping feature to weight adjustments
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT feature, confidence_adjustment, priority_adjustment, sample_count
                FROM feature_weights
            ''')

            weights = {}
            for row in cursor.fetchall():
                weights[row[0]] = {
                    'confidence_adjustment': row[1],
                    'priority_adjustment': row[2],
                    'sample_count': row[3]
                }

            return weights

    def save_preference(self, key: str, value: Any):
        """Save a user preference."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO user_preferences
                (preference_key, preference_value, last_updated)
                VALUES (?, ?, ?)
            ''', (key, json.dumps(value), datetime.now().isoformat()))

            conn.commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT preference_value FROM user_preferences
                WHERE preference_key = ?
            ''', (key,))

            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return default

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics for the learning database.

        Returns:
            Dict with overall statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Session stats
            cursor.execute('''
                SELECT
                    COUNT(*) as session_count,
                    AVG(fixes_suggested) as avg_suggested,
                    AVG(fixes_accepted) as avg_accepted,
                    AVG(similarity_improvement) as avg_sim_improvement,
                    AVG(trance_score_improvement) as avg_trance_improvement
                FROM sessions
            ''')

            session_row = cursor.fetchone()

            # Feedback stats
            cursor.execute('''
                SELECT
                    COUNT(*) as total_feedback,
                    SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) as total_accepted,
                    AVG(CASE WHEN accepted = 1 AND improvement IS NOT NULL THEN improvement END) as avg_improvement
                FROM fix_feedback
            ''')

            feedback_row = cursor.fetchone()

            return {
                'session_count': session_row[0] or 0,
                'avg_fixes_suggested': session_row[1] or 0,
                'avg_fixes_accepted': session_row[2] or 0,
                'avg_similarity_improvement': session_row[3],
                'avg_trance_score_improvement': session_row[4],
                'total_feedback': feedback_row[0] or 0,
                'total_accepted': feedback_row[1] or 0,
                'overall_acceptance_rate': (feedback_row[1] / feedback_row[0]) if feedback_row[0] > 0 else 0.0,
                'avg_fix_improvement': feedback_row[2]
            }

    def reset(self):
        """Reset all learning data (use with caution)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('DELETE FROM fix_feedback')
            cursor.execute('DELETE FROM sessions')
            cursor.execute('DELETE FROM feature_weights')
            cursor.execute('DELETE FROM user_preferences')

            conn.commit()

    def export_to_json(self, output_path: str):
        """Export all learning data to JSON file."""
        data = {
            'sessions': [s.to_dict() for s in self.get_all_sessions(limit=10000)],
            'feedback': [f.to_dict() for f in self.get_all_feedback(limit=10000)],
            'feature_weights': self.get_feature_weights(),
            'stats': self.get_summary_stats()
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

    def import_from_json(self, input_path: str):
        """Import learning data from JSON file."""
        with open(input_path, 'r') as f:
            data = json.load(f)

        for session_dict in data.get('sessions', []):
            session = SessionRecord.from_dict(session_dict)
            self.record_session(session)

        for feedback_dict in data.get('feedback', []):
            feedback = FixFeedback.from_dict(feedback_dict)
            self.record_feedback(feedback)

        for feature, weights in data.get('feature_weights', {}).items():
            self.save_feature_weight(
                feature,
                weights['confidence_adjustment'],
                weights['priority_adjustment'],
                weights['sample_count']
            )


def generate_feedback_id() -> str:
    """Generate a unique feedback ID."""
    return f"fb_{uuid.uuid4().hex[:12]}"


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return f"sess_{uuid.uuid4().hex[:12]}"
