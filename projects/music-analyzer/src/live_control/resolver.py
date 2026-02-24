"""
Device Resolution for Live DAW Control.

Maps track/device/parameter names to numeric indices required by MCP tools.
Supports fuzzy matching and caching for efficient resolution.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from difflib import SequenceMatcher


@dataclass
class ResolvedFix:
    """A fix specification resolved to MCP-ready indices."""
    track_index: int
    track_name: str
    device_index: Optional[int] = None
    device_name: Optional[str] = None
    parameter_index: Optional[int] = None
    parameter_name: Optional[str] = None
    value: Optional[float] = None
    change_type: str = "parameter"  # parameter, volume, pan

    def to_mcp_args(self) -> Dict[str, Any]:
        """Convert to MCP tool arguments."""
        if self.change_type == "volume":
            return {
                "track_index": self.track_index,
                "volume": self.value
            }
        elif self.change_type == "pan":
            return {
                "track_index": self.track_index,
                "pan": self.value
            }
        else:
            return {
                "track_index": self.track_index,
                "device_index": self.device_index,
                "parameter_index": self.parameter_index,
                "value": self.value
            }


class DeviceResolver:
    """
    Resolves track/device/parameter names to MCP indices.

    Usage:
        resolver = DeviceResolver()

        # Load track names (from MCP get_track_names response)
        resolver.load_tracks_from_mcp('{"success": true, "tracks": [...]}')

        # Load devices (from MCP get_track_devices response)
        resolver.load_devices_from_mcp(0, '{"success": true, "devices": [...]}')

        # Resolve a fix
        fix = resolver.resolve_fix({
            'track_name': 'Bass',
            'device_name': 'EQ Eight',
            'parameter_name': '1 Frequency',
            'value': 0.3
        })
    """

    def __init__(self):
        # Track name -> index
        self._track_cache: Dict[str, int] = {}
        # Track index -> {device name -> index}
        self._device_cache: Dict[int, Dict[str, int]] = {}
        # (track_index, device_index) -> {param name -> index}
        self._param_cache: Dict[Tuple[int, int], Dict[str, int]] = {}

        # Store full data for fuzzy matching
        self._tracks: List[Dict[str, Any]] = []
        self._devices: Dict[int, List[Dict[str, Any]]] = {}
        self._parameters: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}

    def load_tracks_from_mcp(self, mcp_response: str) -> bool:
        """
        Load track names from MCP get_track_names response.

        Args:
            mcp_response: JSON string from get_track_names MCP tool

        Returns:
            True if successful
        """
        try:
            data = json.loads(mcp_response)
            if not data.get('success'):
                return False

            self._tracks = data.get('tracks', [])
            self._track_cache = {
                track['name']: track['index']
                for track in self._tracks
            }
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def load_devices_from_mcp(self, track_index: int, mcp_response: str) -> bool:
        """
        Load device names for a track from MCP get_track_devices response.

        Args:
            track_index: The track index
            mcp_response: JSON string from get_track_devices MCP tool

        Returns:
            True if successful
        """
        try:
            data = json.loads(mcp_response)
            if not data.get('success'):
                return False

            devices = data.get('devices', [])
            self._devices[track_index] = devices
            self._device_cache[track_index] = {
                device['name']: device['index']
                for device in devices
            }
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def load_parameters_from_mcp(self, track_index: int, device_index: int,
                                  mcp_response: str) -> bool:
        """
        Load parameter names for a device from MCP get_device_parameters response.

        Args:
            track_index: The track index
            device_index: The device index
            mcp_response: JSON string from get_device_parameters MCP tool

        Returns:
            True if successful
        """
        try:
            data = json.loads(mcp_response)
            if not data.get('success'):
                return False

            params = data.get('parameters', [])
            key = (track_index, device_index)
            self._parameters[key] = params
            self._param_cache[key] = {
                param['name']: param['index']
                for param in params
            }
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def load_from_als_doctor(self, als_data: Dict[str, Any]) -> None:
        """
        Load track and device info from ALS Doctor output.

        Args:
            als_data: Parsed ALS Doctor JSON output
        """
        tracks = als_data.get('tracks', [])
        for track in tracks:
            track_name = track.get('name', '')
            track_index = track.get('index', 0)

            self._track_cache[track_name] = track_index
            self._tracks.append({'index': track_index, 'name': track_name})

            # Load devices
            devices = track.get('devices', [])
            self._devices[track_index] = []
            self._device_cache[track_index] = {}

            for device in devices:
                device_name = device.get('name', '')
                device_index = device.get('index', 0)
                self._devices[track_index].append({
                    'index': device_index,
                    'name': device_name
                })
                self._device_cache[track_index][device_name] = device_index

    # =========================================================================
    # Resolution Methods
    # =========================================================================

    def resolve_track(self, name: str) -> Optional[int]:
        """
        Resolve track name to index.

        Supports:
        - Exact match (case-insensitive)
        - Fuzzy match (similarity > 0.8)
        - Index reference ("track 1" or "#1")

        Returns:
            Track index or None if not found
        """
        # Try index reference first
        index_match = re.match(r'^(?:track\s*)?#?(\d+)$', name.strip(), re.IGNORECASE)
        if index_match:
            idx = int(index_match.group(1))
            # Verify index exists
            if any(t['index'] == idx for t in self._tracks):
                return idx

        # Try exact match (case-insensitive)
        name_lower = name.lower().strip()
        for track_name, index in self._track_cache.items():
            if track_name.lower() == name_lower:
                return index

        # Try fuzzy match
        best_match = self._fuzzy_match(name, list(self._track_cache.keys()))
        if best_match:
            return self._track_cache[best_match]

        return None

    def resolve_device(self, track_index: int, name: str) -> Optional[int]:
        """
        Resolve device name to index on a track.

        Returns:
            Device index or None if not found
        """
        if track_index not in self._device_cache:
            return None

        device_map = self._device_cache[track_index]

        # Try exact match (case-insensitive)
        name_lower = name.lower().strip()
        for device_name, index in device_map.items():
            if device_name.lower() == name_lower:
                return index

        # Try fuzzy match
        best_match = self._fuzzy_match(name, list(device_map.keys()))
        if best_match:
            return device_map[best_match]

        return None

    def resolve_parameter(self, track_index: int, device_index: int,
                          name: str) -> Optional[int]:
        """
        Resolve parameter name to index.

        Returns:
            Parameter index or None if not found
        """
        key = (track_index, device_index)
        if key not in self._param_cache:
            return None

        param_map = self._param_cache[key]

        # Try exact match (case-insensitive)
        name_lower = name.lower().strip()
        for param_name, index in param_map.items():
            if param_name.lower() == name_lower:
                return index

        # Try partial match (parameter names can be long)
        for param_name, index in param_map.items():
            if name_lower in param_name.lower():
                return index

        # Try fuzzy match
        best_match = self._fuzzy_match(name, list(param_map.keys()), threshold=0.6)
        if best_match:
            return param_map[best_match]

        return None

    def resolve_fix(self, fix: Dict[str, Any]) -> ResolvedFix:
        """
        Resolve a fix specification to MCP-ready indices.

        Args:
            fix: Dictionary with keys:
                - track_name: Name of the track
                - device_name: (optional) Name of the device
                - parameter_name: (optional) Name of the parameter
                - value: The value to set
                - change_type: (optional) "parameter", "volume", or "pan"

        Returns:
            ResolvedFix with all indices populated

        Raises:
            ValueError: If track/device/parameter cannot be resolved
        """
        track_name = fix.get('track_name', '')
        track_index = self.resolve_track(track_name)
        if track_index is None:
            raise ValueError(f"Track not found: '{track_name}'")

        change_type = fix.get('change_type', 'parameter')
        value = fix.get('value')

        # Track-level change (volume/pan)
        if change_type in ('volume', 'pan'):
            return ResolvedFix(
                track_index=track_index,
                track_name=self._get_track_name(track_index) or track_name,
                value=value,
                change_type=change_type
            )

        # Device parameter change
        device_name = fix.get('device_name', '')
        device_index = self.resolve_device(track_index, device_name)
        if device_index is None:
            raise ValueError(f"Device not found: '{device_name}' on track '{track_name}'")

        parameter_name = fix.get('parameter_name', '')
        parameter_index = self.resolve_parameter(track_index, device_index, parameter_name)
        if parameter_index is None:
            raise ValueError(
                f"Parameter not found: '{parameter_name}' on '{device_name}'"
            )

        return ResolvedFix(
            track_index=track_index,
            track_name=self._get_track_name(track_index) or track_name,
            device_index=device_index,
            device_name=self._get_device_name(track_index, device_index) or device_name,
            parameter_index=parameter_index,
            parameter_name=self._get_param_name(track_index, device_index, parameter_index) or parameter_name,
            value=value,
            change_type='parameter'
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _fuzzy_match(self, query: str, candidates: List[str],
                     threshold: float = 0.8) -> Optional[str]:
        """Find best fuzzy match above threshold."""
        query_lower = query.lower().strip()
        best_score = 0.0
        best_match = None

        for candidate in candidates:
            score = SequenceMatcher(None, query_lower, candidate.lower()).ratio()
            if score > best_score and score >= threshold:
                best_score = score
                best_match = candidate

        return best_match

    def _get_track_name(self, index: int) -> Optional[str]:
        """Get track name by index."""
        for track in self._tracks:
            if track['index'] == index:
                return track['name']
        return None

    def _get_device_name(self, track_index: int, device_index: int) -> Optional[str]:
        """Get device name by indices."""
        devices = self._devices.get(track_index, [])
        for device in devices:
            if device['index'] == device_index:
                return device['name']
        return None

    def _get_param_name(self, track_index: int, device_index: int,
                        param_index: int) -> Optional[str]:
        """Get parameter name by indices."""
        params = self._parameters.get((track_index, device_index), [])
        for param in params:
            if param['index'] == param_index:
                return param['name']
        return None

    # =========================================================================
    # Cache Management
    # =========================================================================

    def clear(self) -> None:
        """Clear all caches."""
        self._track_cache.clear()
        self._device_cache.clear()
        self._param_cache.clear()
        self._tracks.clear()
        self._devices.clear()
        self._parameters.clear()

    def refresh_tracks(self) -> None:
        """Clear track cache (call when tracks change)."""
        self._track_cache.clear()
        self._tracks.clear()

    def refresh_devices(self, track_index: int) -> None:
        """Clear device cache for a track (call when devices change)."""
        self._device_cache.pop(track_index, None)
        self._devices.pop(track_index, None)
        # Also clear parameter cache for this track's devices
        keys_to_remove = [k for k in self._param_cache if k[0] == track_index]
        for key in keys_to_remove:
            self._param_cache.pop(key, None)
            self._parameters.pop(key, None)

    @property
    def track_count(self) -> int:
        """Number of tracks loaded."""
        return len(self._tracks)

    @property
    def is_initialized(self) -> bool:
        """Whether tracks have been loaded."""
        return len(self._tracks) > 0

    def get_tracks(self) -> List[Dict[str, Any]]:
        """Get list of all loaded tracks."""
        return list(self._tracks)

    def get_devices(self, track_index: int) -> List[Dict[str, Any]]:
        """Get list of devices for a track."""
        return list(self._devices.get(track_index, []))

    def get_parameters(self, track_index: int, device_index: int) -> List[Dict[str, Any]]:
        """Get list of parameters for a device."""
        return list(self._parameters.get((track_index, device_index), []))


# =============================================================================
# Global resolver instance
# =============================================================================

_resolver: Optional[DeviceResolver] = None


def get_resolver() -> DeviceResolver:
    """Get or create the global device resolver."""
    global _resolver
    if _resolver is None:
        _resolver = DeviceResolver()
    return _resolver


def reset_resolver() -> None:
    """Reset the global resolver (for testing)."""
    global _resolver
    _resolver = None
