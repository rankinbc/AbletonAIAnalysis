"""
Feedback Collector Module.

Interactive feedback collection during fix application sessions.
"""

import sys
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

from .learning_db import (
    LearningDatabase,
    FixFeedback,
    SessionRecord,
    generate_feedback_id,
    generate_session_id
)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class FeedbackCollector:
    """
    Collect user feedback on fix recommendations.

    Manages feedback sessions, records user decisions, and tracks
    which fixes were accepted, modified, or rejected.
    """

    def __init__(
        self,
        db: Optional[LearningDatabase] = None,
        db_path: str = "learning_data.db",
        verbose: bool = False
    ):
        """
        Initialize feedback collector.

        Args:
            db: LearningDatabase instance (creates one if not provided)
            db_path: Path to database file if creating new instance
            verbose: Print verbose output
        """
        self.db = db or LearningDatabase(db_path)
        self.verbose = verbose
        self.current_session: Optional[SessionRecord] = None
        self._session_feedback: List[FixFeedback] = []
        self._fix_id_map: Dict[str, str] = {}  # Maps fix.id to feedback_id

    def start_session(
        self,
        track_path: str,
        profile_name: str,
        gap_report: Any,
        fixes_count: int = 0
    ) -> str:
        """
        Start a new feedback collection session.

        Args:
            track_path: Path to the audio track being analyzed
            profile_name: Name of the reference profile used
            gap_report: GapReport from gap analyzer
            fixes_count: Number of fixes that will be suggested

        Returns:
            Session ID
        """
        session_id = generate_session_id()

        self.current_session = SessionRecord(
            session_id=session_id,
            timestamp=datetime.now(),
            track_path=track_path,
            profile_name=profile_name,
            initial_similarity=gap_report.overall_similarity,
            initial_trance_score=gap_report.trance_score,
            fixes_suggested=fixes_count,
            fixes_accepted=0,
            fixes_rejected=0,
            fixes_modified=0
        )

        self._session_feedback = []
        self._fix_id_map = {}

        if self.verbose:
            print(f"[FeedbackCollector] Started session {session_id}")
            print(f"  Track: {Path(track_path).name}")
            print(f"  Profile: {profile_name}")
            print(f"  Initial Similarity: {gap_report.overall_similarity:.0%}")
            print(f"  Initial Trance Score: {gap_report.trance_score:.2f}")

        return session_id

    def record_fix_decision(
        self,
        fix: Any,
        accepted: bool,
        modified: bool = False,
        notes: Optional[str] = None,
        pre_gap_score: Optional[float] = None
    ) -> str:
        """
        Record user's decision on a fix.

        Args:
            fix: PrescriptiveFix object
            accepted: Whether the user accepted the fix
            modified: Whether the user modified the fix before applying
            notes: Optional user notes
            pre_gap_score: Optional gap score before this fix

        Returns:
            Feedback ID
        """
        if not self.current_session:
            raise RuntimeError("No active session. Call start_session() first.")

        feedback_id = generate_feedback_id()

        feedback = FixFeedback(
            feedback_id=feedback_id,
            timestamp=datetime.now(),
            track_path=self.current_session.track_path,
            profile_name=self.current_session.profile_name,
            feature=fix.feature,
            severity=fix.severity,
            suggested_change=fix.suggested_change,
            confidence=fix.confidence,
            current_value=fix.current_value,
            target_value=fix.target_value,
            accepted=accepted,
            modified=modified,
            user_notes=notes,
            pre_gap_score=pre_gap_score,
            session_id=self.current_session.session_id
        )

        self._session_feedback.append(feedback)
        self._fix_id_map[fix.id] = feedback_id

        # Update session counts
        if accepted:
            self.current_session.fixes_accepted += 1
            if modified:
                self.current_session.fixes_modified += 1
        else:
            self.current_session.fixes_rejected += 1

        if self.verbose:
            status = "ACCEPTED" if accepted else "REJECTED"
            if modified:
                status += " (modified)"
            print(f"  [{status}] {fix.feature}: {fix.suggested_change[:50]}...")

        return feedback_id

    def record_effectiveness(
        self,
        fix_id: str,
        pre_score: float,
        post_score: float
    ):
        """
        Record before/after scores for a fix.

        Args:
            fix_id: The original fix ID (from PrescriptiveFix)
            pre_score: Gap score before fix
            post_score: Gap score after fix
        """
        feedback_id = self._fix_id_map.get(fix_id)
        if not feedback_id:
            if self.verbose:
                print(f"  Warning: No feedback found for fix {fix_id}")
            return

        # Update in-memory feedback
        for fb in self._session_feedback:
            if fb.feedback_id == feedback_id:
                fb.pre_gap_score = pre_score
                fb.post_gap_score = post_score
                fb.improvement = pre_score - post_score  # Positive = better
                break

        if self.verbose:
            improvement = pre_score - post_score
            print(f"  Effectiveness recorded: {improvement:+.3f} improvement")

    def end_session(
        self,
        final_gap_report: Optional[Any] = None
    ) -> SessionRecord:
        """
        End session and save all feedback to database.

        Args:
            final_gap_report: Optional GapReport after fixes applied

        Returns:
            Completed SessionRecord
        """
        if not self.current_session:
            raise RuntimeError("No active session to end.")

        # Update final metrics if provided
        if final_gap_report:
            self.current_session.final_similarity = final_gap_report.overall_similarity
            self.current_session.final_trance_score = final_gap_report.trance_score
            self.current_session.similarity_improvement = (
                final_gap_report.overall_similarity -
                self.current_session.initial_similarity
            )
            self.current_session.trance_score_improvement = (
                final_gap_report.trance_score -
                self.current_session.initial_trance_score
            )

        # Save session to database
        self.db.record_session(self.current_session)

        # Save all feedback to database
        for feedback in self._session_feedback:
            self.db.record_feedback(feedback)

        if self.verbose:
            print(f"\n[FeedbackCollector] Session {self.current_session.session_id} ended")
            print(f"  Fixes suggested: {self.current_session.fixes_suggested}")
            print(f"  Fixes accepted: {self.current_session.fixes_accepted}")
            print(f"  Fixes rejected: {self.current_session.fixes_rejected}")
            if self.current_session.similarity_improvement is not None:
                print(f"  Similarity change: {self.current_session.similarity_improvement:+.0%}")
            if self.current_session.trance_score_improvement is not None:
                print(f"  Trance score change: {self.current_session.trance_score_improvement:+.2f}")

        completed_session = self.current_session
        self.current_session = None
        self._session_feedback = []
        self._fix_id_map = {}

        return completed_session

    def prompt_for_feedback(
        self,
        fix: Any,
        fix_number: int,
        total_fixes: int,
        allow_skip_all: bool = True
    ) -> Dict[str, Any]:
        """
        Interactive CLI prompt for fix feedback.

        Args:
            fix: PrescriptiveFix object
            fix_number: Current fix number (1-indexed)
            total_fixes: Total number of fixes
            allow_skip_all: Allow user to skip all remaining fixes

        Returns:
            Dict with 'accepted', 'modified', 'notes', 'skip_all' keys
        """
        # Display fix details
        severity_icon = {
            'critical': '\033[91m[CRITICAL]\033[0m',
            'warning': '\033[93m[WARNING]\033[0m',
            'minor': '\033[92m[MINOR]\033[0m'
        }.get(fix.severity, '[INFO]')

        print(f"\nFIX {fix_number}/{total_fixes}: {fix.feature.replace('_', ' ').title()} {severity_icon}")
        print(f"  Current: {fix.current_value:.2f} | Target: {fix.target_value:.2f}")
        print(f"  Action: {fix.suggested_change}")
        print(f"  Confidence: {fix.confidence*100:.0f}%")

        if fix.target_track:
            print(f"  Track: \"{fix.target_track}\"")
        if fix.target_device:
            print(f"  Device: {fix.target_device}")

        if fix.manual_steps:
            print("  Steps:")
            for step in fix.manual_steps[:3]:
                print(f"    - {step}")

        # Prompt for decision
        options = "[y]es / [n]o / [m]odified"
        if allow_skip_all:
            options += " / [s]kip all"
        options += " / [q]uit"

        while True:
            print(f"\n  Apply this fix? {options}: ", end='')
            try:
                response = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                response = 'q'

            if response in ('y', 'yes'):
                notes = self._prompt_notes()
                return {'accepted': True, 'modified': False, 'notes': notes, 'skip_all': False}

            elif response in ('n', 'no'):
                notes = self._prompt_notes()
                return {'accepted': False, 'modified': False, 'notes': notes, 'skip_all': False}

            elif response in ('m', 'modified'):
                notes = self._prompt_notes(required=True)
                return {'accepted': True, 'modified': True, 'notes': notes, 'skip_all': False}

            elif response in ('s', 'skip') and allow_skip_all:
                return {'accepted': False, 'modified': False, 'notes': None, 'skip_all': True}

            elif response in ('q', 'quit'):
                return {'accepted': False, 'modified': False, 'notes': None, 'skip_all': True, 'quit': True}

            else:
                print(f"  Invalid option. Please enter one of: {options}")

    def _prompt_notes(self, required: bool = False) -> Optional[str]:
        """Prompt for optional notes."""
        prompt = "  Notes (optional): " if not required else "  Notes (describe modification): "
        print(prompt, end='')
        try:
            notes = input().strip()
            return notes if notes else None
        except (EOFError, KeyboardInterrupt):
            return None

    def collect_batch_feedback(
        self,
        fixes: List[Any],
        track_path: str,
        profile_name: str,
        gap_report: Any,
        auto_accept_confidence: Optional[float] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Collect feedback for a batch of fixes interactively.

        Args:
            fixes: List of PrescriptiveFix objects
            track_path: Path to the audio track
            profile_name: Name of the reference profile
            gap_report: GapReport from gap analyzer
            auto_accept_confidence: Auto-accept fixes above this confidence (optional)
            progress_callback: Optional callback(fix_num, total, fix, decision)

        Returns:
            Dict with session summary and accepted/rejected lists
        """
        if not fixes:
            return {
                'session_id': None,
                'accepted': [],
                'rejected': [],
                'modified': [],
                'skipped': []
            }

        # Start session
        session_id = self.start_session(
            track_path=track_path,
            profile_name=profile_name,
            gap_report=gap_report,
            fixes_count=len(fixes)
        )

        accepted_fixes = []
        rejected_fixes = []
        modified_fixes = []
        skipped_fixes = []

        print("\n" + "=" * 60)
        print("FIX RECOMMENDATIONS")
        print("=" * 60)
        print(f"Track: {Path(track_path).name}")
        print(f"Profile: {profile_name}")
        print(f"Total fixes: {len(fixes)}")
        print("=" * 60)

        for i, fix in enumerate(fixes, 1):
            # Auto-accept high confidence fixes if threshold set
            if auto_accept_confidence and fix.confidence >= auto_accept_confidence:
                print(f"\n[AUTO-ACCEPTED] Fix {i}/{len(fixes)}: {fix.feature} (confidence {fix.confidence:.0%})")
                self.record_fix_decision(fix, accepted=True, modified=False)
                accepted_fixes.append(fix)
                if progress_callback:
                    progress_callback(i, len(fixes), fix, 'auto_accepted')
                continue

            # Interactive prompt
            result = self.prompt_for_feedback(fix, i, len(fixes))

            if result.get('quit'):
                # Mark remaining as skipped
                for remaining_fix in fixes[i:]:
                    skipped_fixes.append(remaining_fix)
                break

            if result.get('skip_all'):
                # Mark remaining as skipped
                skipped_fixes.append(fix)
                for remaining_fix in fixes[i:]:
                    skipped_fixes.append(remaining_fix)
                break

            # Record decision
            self.record_fix_decision(
                fix,
                accepted=result['accepted'],
                modified=result['modified'],
                notes=result.get('notes')
            )

            if result['accepted']:
                if result['modified']:
                    modified_fixes.append(fix)
                else:
                    accepted_fixes.append(fix)
            else:
                rejected_fixes.append(fix)

            if progress_callback:
                status = 'accepted' if result['accepted'] else 'rejected'
                if result['modified']:
                    status = 'modified'
                progress_callback(i, len(fixes), fix, status)

        # End session (without final gap report - that comes later)
        session = self.end_session()

        return {
            'session_id': session_id,
            'session': session,
            'accepted': accepted_fixes,
            'rejected': rejected_fixes,
            'modified': modified_fixes,
            'skipped': skipped_fixes
        }

    def update_session_with_results(
        self,
        session_id: str,
        final_gap_report: Any
    ):
        """
        Update a completed session with re-analysis results.

        Args:
            session_id: Session ID to update
            final_gap_report: GapReport from re-analysis
        """
        self.db.update_session_finals(
            session_id=session_id,
            final_similarity=final_gap_report.overall_similarity,
            final_trance_score=final_gap_report.trance_score
        )

        if self.verbose:
            print(f"\n[FeedbackCollector] Updated session {session_id} with results")
            print(f"  Final similarity: {final_gap_report.overall_similarity:.0%}")
            print(f"  Final trance score: {final_gap_report.trance_score:.2f}")

    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary of a feedback session.

        Args:
            session_id: Session ID

        Returns:
            Summary dict or None if not found
        """
        session = self.db.get_session_by_id(session_id)
        if not session:
            return None

        feedback = self.db.get_all_feedback(limit=100)
        session_feedback = [f for f in feedback if f.session_id == session_id]

        return {
            'session': session.to_dict(),
            'feedback_count': len(session_feedback),
            'feedback': [f.to_dict() for f in session_feedback],
            'acceptance_rate': session.fixes_accepted / session.fixes_suggested if session.fixes_suggested > 0 else 0
        }


def format_session_summary(session: SessionRecord) -> str:
    """
    Format a session record as a human-readable summary.

    Args:
        session: SessionRecord to format

    Returns:
        Formatted string
    """
    lines = [
        "",
        "=" * 50,
        "SESSION SUMMARY",
        "=" * 50,
        f"Session ID: {session.session_id}",
        f"Track: {Path(session.track_path).name}",
        f"Profile: {session.profile_name}",
        f"Date: {session.timestamp.strftime('%Y-%m-%d %H:%M')}",
        "",
        "Fixes:",
        f"  Suggested: {session.fixes_suggested}",
        f"  Accepted:  {session.fixes_accepted} ({100*session.fixes_accepted/session.fixes_suggested:.0f}%)" if session.fixes_suggested > 0 else "  Accepted:  0",
        f"  Rejected:  {session.fixes_rejected}",
    ]

    if session.fixes_modified > 0:
        lines.append(f"  Modified:  {session.fixes_modified}")

    if session.similarity_improvement is not None:
        lines.extend([
            "",
            "Results:",
            f"  Similarity: {session.initial_similarity:.0%} -> {session.final_similarity:.0%} ({session.similarity_improvement:+.0%})",
            f"  Trance Score: {session.initial_trance_score:.2f} -> {session.final_trance_score:.2f} ({session.trance_score_improvement:+.2f})"
        ])

    lines.append("=" * 50)

    return "\n".join(lines)
