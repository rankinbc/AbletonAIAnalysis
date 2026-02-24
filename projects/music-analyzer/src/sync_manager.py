"""
Marker Sync Manager - Bidirectional sync between dashboard and Ableton Live.

Manages marker/cue point synchronization:
- Pull: Fetch markers from Ableton into dashboard
- Push: Send dashboard markers to Ableton
- Diff: Compare states and identify changes
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

try:
    from ableton_bridge import AbletonBridge
except ImportError:
    from src.ableton_bridge import AbletonBridge


class SyncAction(Enum):
    """Type of sync action needed."""
    MATCH = "match"           # Markers match
    ADD_TO_ABLETON = "add"    # Marker exists in dashboard, not in Ableton
    DELETE_FROM_ABLETON = "delete"  # Marker exists in Ableton, not in dashboard
    UPDATE = "update"         # Marker exists in both but differs


@dataclass
class MarkerDiff:
    """Represents a difference between dashboard and Ableton markers."""
    action: SyncAction
    dashboard_marker: Optional[Dict[str, Any]] = None
    ableton_marker: Optional[Dict[str, Any]] = None
    time_diff_beats: float = 0.0  # Difference in beats

    def to_dict(self) -> Dict[str, Any]:
        return {
            'action': self.action.value,
            'dashboard_marker': self.dashboard_marker,
            'ableton_marker': self.ableton_marker,
            'time_diff_beats': round(self.time_diff_beats, 2)
        }


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    message: str
    added: int = 0
    deleted: int = 0
    updated: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'added': self.added,
            'deleted': self.deleted,
            'updated': self.updated,
            'failed': self.failed,
            'errors': self.errors
        }


class MarkerSyncManager:
    """Manages bidirectional marker synchronization between dashboard and Ableton."""

    # Tolerance for considering two markers at the same position (in beats)
    POSITION_TOLERANCE = 0.5

    def __init__(self, bridge: AbletonBridge = None):
        """Initialize the sync manager.

        Args:
            bridge: Optional AbletonBridge instance. Creates new one if not provided.
        """
        self.bridge = bridge or AbletonBridge()
        self._dashboard_state: List[Dict[str, Any]] = []
        self._ableton_state: List[Dict[str, Any]] = []

    @property
    def is_connected(self) -> bool:
        """Check if connected to Ableton."""
        return self.bridge.is_connected

    def connect(self) -> bool:
        """Connect to Ableton if not already connected."""
        if not self.is_connected:
            return self.bridge.connect()
        return True

    def refresh_ableton_state(self) -> List[Dict[str, Any]]:
        """Fetch current markers from Ableton.

        Returns:
            List of marker dicts with 'name' and 'time_beats' keys
        """
        if not self.is_connected:
            return []

        # Get detailed cue points
        cue_points = self.bridge.get_cue_points_detailed()

        # Normalize format
        self._ableton_state = []
        for cp in cue_points:
            self._ableton_state.append({
                'name': cp.get('name', ''),
                'time_beats': cp.get('time_beats', cp.get('time', 0)),
                'index': cp.get('index', -1)
            })

        return self._ableton_state

    def set_dashboard_state(self, markers: List[Dict[str, Any]]) -> None:
        """Set the current dashboard marker state.

        Args:
            markers: List of marker dicts with 'name' and 'time_beats' keys
        """
        self._dashboard_state = []
        for m in markers:
            self._dashboard_state.append({
                'name': m.get('name', ''),
                'time_beats': m.get('time_beats', 0)
            })

    def pull_from_ableton(self) -> Tuple[List[Dict[str, Any]], str]:
        """Pull markers from Ableton to use in dashboard.

        Returns:
            Tuple of (markers, status_message)
        """
        if not self.connect():
            return [], f"Failed to connect: {self.bridge.last_error}"

        markers = self.refresh_ableton_state()

        if not markers:
            return [], "No markers found in Ableton (or cue points not supported)"

        return markers, f"Pulled {len(markers)} markers from Ableton"

    def push_to_ableton(self, markers: List[Dict[str, Any]],
                        clear_first: bool = True) -> SyncResult:
        """Push dashboard markers to Ableton.

        Args:
            markers: List of marker dicts with 'name' and 'time_beats' keys
            clear_first: If True, clears all existing markers first

        Returns:
            SyncResult with operation details
        """
        if not self.connect():
            return SyncResult(
                success=False,
                message=f"Failed to connect: {self.bridge.last_error}"
            )

        result = SyncResult(success=True, message="")

        # Clear existing markers if requested
        if clear_first:
            if self.bridge.clear_locators():
                result.deleted = len(self._ableton_state)
            else:
                result.errors.append(f"Failed to clear: {self.bridge.last_error}")

        # Add all markers
        for marker in markers:
            name = marker.get('name', 'Marker')
            time_beats = marker.get('time_beats', 0)

            if self.bridge.add_locator(name, time_beats):
                result.added += 1
            else:
                result.failed += 1
                result.errors.append(
                    f"Failed to add '{name}' at beat {time_beats}: {self.bridge.last_error}"
                )

        # Build result message
        if result.failed == 0:
            result.message = f"Successfully pushed {result.added} markers to Ableton"
        else:
            result.success = result.added > 0
            result.message = f"Pushed {result.added} markers, {result.failed} failed"

        return result

    def diff(self, dashboard_markers: List[Dict[str, Any]] = None) -> List[MarkerDiff]:
        """Compare dashboard state with Ableton state.

        Args:
            dashboard_markers: Optional markers to compare. Uses stored state if None.

        Returns:
            List of MarkerDiff objects describing differences
        """
        if dashboard_markers:
            self.set_dashboard_state(dashboard_markers)

        # Refresh Ableton state
        self.refresh_ableton_state()

        diffs = []
        matched_ableton_indices = set()

        # Check each dashboard marker
        for dm in self._dashboard_state:
            dm_time = dm.get('time_beats', 0)
            dm_name = dm.get('name', '').upper()

            # Look for matching Ableton marker
            best_match = None
            best_match_idx = -1
            best_time_diff = float('inf')

            for i, am in enumerate(self._ableton_state):
                if i in matched_ableton_indices:
                    continue

                am_time = am.get('time_beats', 0)
                am_name = am.get('name', '').upper()
                time_diff = abs(dm_time - am_time)

                # Check if names match or times are close
                name_match = dm_name == am_name
                time_close = time_diff <= self.POSITION_TOLERANCE

                if name_match and time_close:
                    # Perfect match
                    best_match = am
                    best_match_idx = i
                    best_time_diff = time_diff
                    break
                elif name_match and time_diff < best_time_diff:
                    # Name matches but time differs
                    best_match = am
                    best_match_idx = i
                    best_time_diff = time_diff
                elif time_close and best_match is None:
                    # Time close, different name
                    best_match = am
                    best_match_idx = i
                    best_time_diff = time_diff

            if best_match:
                matched_ableton_indices.add(best_match_idx)

                if best_time_diff <= self.POSITION_TOLERANCE:
                    # Markers match
                    diffs.append(MarkerDiff(
                        action=SyncAction.MATCH,
                        dashboard_marker=dm,
                        ableton_marker=best_match,
                        time_diff_beats=best_time_diff
                    ))
                else:
                    # Markers need update (position differs)
                    diffs.append(MarkerDiff(
                        action=SyncAction.UPDATE,
                        dashboard_marker=dm,
                        ableton_marker=best_match,
                        time_diff_beats=best_time_diff
                    ))
            else:
                # Dashboard marker not in Ableton
                diffs.append(MarkerDiff(
                    action=SyncAction.ADD_TO_ABLETON,
                    dashboard_marker=dm,
                    ableton_marker=None
                ))

        # Check for Ableton markers not in dashboard
        for i, am in enumerate(self._ableton_state):
            if i not in matched_ableton_indices:
                diffs.append(MarkerDiff(
                    action=SyncAction.DELETE_FROM_ABLETON,
                    dashboard_marker=None,
                    ableton_marker=am
                ))

        return diffs

    def sync(self, dashboard_markers: List[Dict[str, Any]],
             direction: str = 'push') -> SyncResult:
        """Perform sync in specified direction.

        Args:
            dashboard_markers: Current dashboard markers
            direction: 'push' (dashboard -> Ableton) or 'pull' (Ableton -> dashboard)

        Returns:
            SyncResult with operation details
        """
        if direction == 'push':
            return self.push_to_ableton(dashboard_markers, clear_first=True)
        elif direction == 'pull':
            markers, message = self.pull_from_ableton()
            return SyncResult(
                success=len(markers) > 0,
                message=message,
                added=len(markers)
            )
        else:
            return SyncResult(
                success=False,
                message=f"Unknown sync direction: {direction}"
            )

    def get_status(self) -> Dict[str, Any]:
        """Get current sync status.

        Returns:
            Status dict with connection info and marker counts
        """
        connected = self.is_connected
        tempo = 0.0

        if connected and self.bridge._live_set:
            try:
                tempo = self.bridge._live_set.tempo
            except:
                pass

        ableton_markers = []
        if connected:
            ableton_markers = self.refresh_ableton_state()

        return {
            'connected': connected,
            'tempo': tempo,
            'ableton_marker_count': len(ableton_markers),
            'ableton_markers': ableton_markers,
            'last_error': self.bridge.last_error
        }


# Convenience functions
def get_sync_manager() -> MarkerSyncManager:
    """Get a sync manager instance."""
    return MarkerSyncManager()


def quick_pull() -> Tuple[List[Dict[str, Any]], str]:
    """Quick pull markers from Ableton."""
    manager = MarkerSyncManager()
    return manager.pull_from_ableton()


def quick_push(markers: List[Dict[str, Any]]) -> SyncResult:
    """Quick push markers to Ableton."""
    manager = MarkerSyncManager()
    return manager.push_to_ableton(markers)
