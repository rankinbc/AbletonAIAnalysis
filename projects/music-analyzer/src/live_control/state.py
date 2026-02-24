"""
State Tracking for Live DAW Control.

Tracks changes made via MCP tools for undo/redo capability.
Claude calls MCP tools directly - this just remembers what was changed.

Changes are persisted to a JSON file so they survive across Python invocations.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pathlib import Path
import uuid
import json
import os


# Default session file location
DEFAULT_SESSION_FILE = Path.home() / ".claude_ableton_session.json"


@dataclass
class Change:
    """A single change that can be undone."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # What was changed
    track_index: int = 0
    track_name: str = ""
    device_index: Optional[int] = None
    device_name: Optional[str] = None
    parameter_index: Optional[int] = None
    parameter_name: Optional[str] = None

    # Values
    previous_value: float = 0.0
    new_value: float = 0.0

    # Context
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # For track-level changes (volume, pan, mute)
    change_type: Literal["parameter", "volume", "pan", "mute"] = "parameter"

    def __str__(self) -> str:
        return f"{self.description}: {self.previous_value:.3f} → {self.new_value:.3f}"

    def undo_description(self) -> str:
        """Description for undoing this change."""
        return f"Undo: {self.description} (restore {self.previous_value:.3f})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            'id': self.id,
            'track_index': self.track_index,
            'track_name': self.track_name,
            'device_index': self.device_index,
            'device_name': self.device_name,
            'parameter_index': self.parameter_index,
            'parameter_name': self.parameter_name,
            'previous_value': self.previous_value,
            'new_value': self.new_value,
            'description': self.description,
            'timestamp': self.timestamp.isoformat(),
            'change_type': self.change_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Change':
        """Deserialize from dictionary."""
        data = data.copy()
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class ABComparison:
    """State for A/B comparison."""
    description: str
    track_index: int
    device_index: Optional[int]
    parameter_index: Optional[int]
    original_value: float  # A
    fix_value: float       # B
    current_state: Literal['A', 'B'] = 'B'
    change_type: Literal["parameter", "volume", "pan"] = "parameter"

    def toggle(self) -> Literal['A', 'B']:
        """Toggle and return new state."""
        self.current_state = 'A' if self.current_state == 'B' else 'B'
        return self.current_state

    @property
    def current_value(self) -> float:
        """Get value for current state."""
        return self.original_value if self.current_state == 'A' else self.fix_value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            'description': self.description,
            'track_index': self.track_index,
            'device_index': self.device_index,
            'parameter_index': self.parameter_index,
            'original_value': self.original_value,
            'fix_value': self.fix_value,
            'current_state': self.current_state,
            'change_type': self.change_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ABComparison':
        """Deserialize from dictionary."""
        return cls(**data)


class ChangeTracker:
    """
    Tracks changes made during a Claude Code conversation.

    Changes are persisted to a JSON file so they survive across
    separate Python invocations within a conversation.

    Usage:
        tracker = ChangeTracker()

        # After Claude calls set_device_parameter via MCP:
        tracker.record(Change(
            track_index=1,
            track_name="Bass",
            device_index=0,
            device_name="EQ Eight",
            parameter_index=4,
            parameter_name="1 Gain",
            previous_value=0.5,
            new_value=0.35,
            description="Reduce Bass EQ band 1 by 3dB"
        ))

        # User says "undo"
        change = tracker.get_undo()
        if change:
            # Claude calls MCP to set parameter back to change.previous_value
            tracker.confirm_undo()
    """

    def __init__(self, session_file: Optional[Path] = None, max_history: int = 50):
        self._session_file = session_file or DEFAULT_SESSION_FILE
        self._max_history = max_history
        self._undo_stack: List[Change] = []
        self._redo_stack: List[Change] = []
        self._ab_comparison: Optional[ABComparison] = None
        self._song_name: Optional[str] = None
        self._load()

    def _load(self) -> None:
        """Load session from file if exists."""
        if not self._session_file.exists():
            return

        try:
            with open(self._session_file, 'r') as f:
                data = json.load(f)

            self._undo_stack = [Change.from_dict(c) for c in data.get('undo_stack', [])]
            self._redo_stack = [Change.from_dict(c) for c in data.get('redo_stack', [])]
            self._song_name = data.get('song_name')

            # Restore A/B comparison if active
            ab_data = data.get('ab_comparison')
            if ab_data:
                self._ab_comparison = ABComparison.from_dict(ab_data)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Start fresh if file is corrupted
            print(f"Warning: Could not load session file, starting fresh: {e}")
            self._undo_stack = []
            self._redo_stack = []
            self._ab_comparison = None

    def _save(self) -> None:
        """Save session to file."""
        data = {
            'version': 1,
            'saved_at': datetime.now().isoformat(),
            'song_name': self._song_name,
            'undo_stack': [c.to_dict() for c in self._undo_stack],
            'redo_stack': [c.to_dict() for c in self._redo_stack],
            'ab_comparison': self._ab_comparison.to_dict() if self._ab_comparison else None,
        }

        # Ensure parent directory exists
        self._session_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self._session_file, 'w') as f:
            json.dump(data, f, indent=2)

    def set_song(self, song_name: str) -> None:
        """Set the current song name for context."""
        self._song_name = song_name
        self._save()

    @property
    def song_name(self) -> Optional[str]:
        """Get the current song name."""
        return self._song_name

    def record(self, change: Change) -> None:
        """Record a change that was made."""
        self._undo_stack.append(change)
        self._redo_stack.clear()  # New change invalidates redo

        # Trim history
        while len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)

        self._save()  # Persist immediately

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def change_count(self) -> int:
        """Number of changes that can be undone."""
        return len(self._undo_stack)

    def get_undo(self) -> Optional[Change]:
        """
        Get the change to undo (doesn't remove it yet).
        Call confirm_undo() after successfully applying the undo.
        """
        if not self._undo_stack:
            return None
        return self._undo_stack[-1]

    def confirm_undo(self) -> Optional[Change]:
        """Confirm undo was applied, move to redo stack."""
        if not self._undo_stack:
            return None
        change = self._undo_stack.pop()
        self._redo_stack.append(change)
        self._save()  # Persist immediately
        return change

    def get_redo(self) -> Optional[Change]:
        """Get the change to redo."""
        if not self._redo_stack:
            return None
        return self._redo_stack[-1]

    def confirm_redo(self) -> Optional[Change]:
        """Confirm redo was applied, move back to undo stack."""
        if not self._redo_stack:
            return None
        change = self._redo_stack.pop()
        self._undo_stack.append(change)
        self._save()  # Persist immediately
        return change

    def get_history(self) -> List[Change]:
        """Get all changes (oldest first)."""
        return list(self._undo_stack)

    def get_last_change(self) -> Optional[Change]:
        """Get most recent change."""
        return self._undo_stack[-1] if self._undo_stack else None

    def clear(self) -> None:
        """Clear all history and delete session file."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._ab_comparison = None
        self._song_name = None

        if self._session_file.exists():
            self._session_file.unlink()

    # =========================================================================
    # A/B Comparison
    # =========================================================================

    def start_ab(
        self,
        description: str,
        track_index: int,
        original_value: float,
        fix_value: float,
        device_index: Optional[int] = None,
        parameter_index: Optional[int] = None,
        change_type: Literal["parameter", "volume", "pan"] = "parameter"
    ) -> ABComparison:
        """
        Start A/B comparison.

        Call this after applying the fix (so we start in state B).
        """
        self._ab_comparison = ABComparison(
            description=description,
            track_index=track_index,
            device_index=device_index,
            parameter_index=parameter_index,
            original_value=original_value,
            fix_value=fix_value,
            current_state='B',
            change_type=change_type
        )
        self._save()  # Persist immediately
        return self._ab_comparison

    @property
    def is_comparing(self) -> bool:
        return self._ab_comparison is not None

    @property
    def ab_state(self) -> Optional[ABComparison]:
        return self._ab_comparison

    def toggle_ab(self) -> Optional[Literal['A', 'B']]:
        """
        Toggle A/B state.
        Returns new state, or None if not comparing.
        Claude should then call MCP to set the value.
        """
        if not self._ab_comparison:
            return None
        result = self._ab_comparison.toggle()
        self._save()  # Persist the toggle
        return result

    def end_ab(self, keep: Literal['A', 'B']) -> Optional[Change]:
        """
        End A/B comparison.

        Returns a Change to record if keeping B (the fix).
        Returns None if keeping A (original) or not comparing.
        """
        if not self._ab_comparison:
            return None

        ab = self._ab_comparison
        self._ab_comparison = None

        if keep == 'B':
            # Record the fix as a change
            change = Change(
                track_index=ab.track_index,
                device_index=ab.device_index,
                parameter_index=ab.parameter_index,
                previous_value=ab.original_value,
                new_value=ab.fix_value,
                description=ab.description,
                change_type=ab.change_type
            )
            self.record(change)  # This will save
            return change

        self._save()  # Save the cleared AB state
        return None

    # =========================================================================
    # Summary
    # =========================================================================

    def summary(self) -> str:
        """Get a summary of current state."""
        lines = []

        if self._song_name:
            lines.append(f"Song: {self._song_name}")
            lines.append("")

        if self._ab_comparison:
            ab = self._ab_comparison
            lines.append(f"A/B Comparison active: {ab.description}")
            lines.append(f"  Current: {ab.current_state} ({ab.current_value:.3f})")
            lines.append(f"  A (original): {ab.original_value:.3f}")
            lines.append(f"  B (fix): {ab.fix_value:.3f}")
            lines.append("")

        lines.append(f"Changes: {len(self._undo_stack)} (undo available: {self.can_undo})")

        if self._undo_stack:
            lines.append("Recent:")
            for change in self._undo_stack[-3:]:
                lines.append(f"  - {change}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Export full state as dictionary (for debugging/inspection)."""
        return {
            'song_name': self._song_name,
            'change_count': len(self._undo_stack),
            'can_undo': self.can_undo,
            'can_redo': self.can_redo,
            'is_comparing': self.is_comparing,
            'changes': [c.to_dict() for c in self._undo_stack],
            'ab_comparison': self._ab_comparison.to_dict() if self._ab_comparison else None,
        }


# =============================================================================
# Convenience functions for Claude Code usage
# =============================================================================

def get_tracker() -> ChangeTracker:
    """Get or create the global change tracker."""
    return ChangeTracker()


def record_change(
    track_index: int,
    track_name: str,
    previous_value: float,
    new_value: float,
    description: str,
    change_type: Literal["parameter", "volume", "pan", "mute"] = "volume",
    device_index: Optional[int] = None,
    device_name: Optional[str] = None,
    parameter_index: Optional[int] = None,
    parameter_name: Optional[str] = None,
) -> Change:
    """
    Record a change. Convenience function for Claude Code.

    Returns the recorded Change object.
    """
    tracker = get_tracker()
    change = Change(
        track_index=track_index,
        track_name=track_name,
        device_index=device_index,
        device_name=device_name,
        parameter_index=parameter_index,
        parameter_name=parameter_name,
        previous_value=previous_value,
        new_value=new_value,
        description=description,
        change_type=change_type,
    )
    tracker.record(change)
    return change


def get_undo_info() -> Optional[Dict[str, Any]]:
    """
    Get info about the change that would be undone.
    Returns None if nothing to undo.
    """
    tracker = get_tracker()
    change = tracker.get_undo()
    if change:
        return change.to_dict()
    return None


def confirm_undo() -> Optional[Dict[str, Any]]:
    """
    Confirm that undo was applied.
    Call this AFTER successfully reverting via MCP.
    Returns the undone change info, or None.
    """
    tracker = get_tracker()
    change = tracker.confirm_undo()
    if change:
        return change.to_dict()
    return None


def get_session_summary() -> str:
    """Get a text summary of the current session."""
    tracker = get_tracker()
    return tracker.summary()


def clear_session() -> None:
    """Clear all session data."""
    tracker = get_tracker()
    tracker.clear()
