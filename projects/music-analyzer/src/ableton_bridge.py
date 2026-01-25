"""
Ableton Bridge Module

Provides integration with Ableton Live via AbletonOSC/PyLive.
Enables:
- Reading current session state (tracks, devices, parameters)
- Applying parameter changes (single or batched)
- Real-time monitoring of session changes
- Integration with the analysis system for "Apply Fixes" workflow

Requirements:
- AbletonOSC must be installed in Ableton's Remote Scripts folder
- AbletonOSC must be enabled in Ableton's Preferences -> Link/Tempo/MIDI -> Control Surface
- PyLive must be installed: pip install pylive

AbletonOSC listens on port 11000, responds on port 11001
"""

import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
from enum import Enum

try:
    import live
    PYLIVE_AVAILABLE = True
except ImportError:
    PYLIVE_AVAILABLE = False

try:
    from pythonosc import udp_client, dispatcher, osc_server
    import threading
    OSC_AVAILABLE = True
except ImportError:
    OSC_AVAILABLE = False


class ConnectionStatus(Enum):
    """Connection status to Ableton."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class DeviceParameter:
    """A single device parameter."""
    name: str
    value: float  # Normalized 0.0-1.0
    min_value: float
    max_value: float
    device_name: str
    track_name: str
    track_index: int
    device_index: int
    parameter_index: int

    @property
    def display_value(self) -> float:
        """Convert normalized value to actual range."""
        return self.min_value + (self.value * (self.max_value - self.min_value))


@dataclass
class DeviceInfo:
    """Information about an Ableton device."""
    name: str
    class_name: str
    track_index: int
    device_index: int
    is_enabled: bool
    parameters: List[DeviceParameter] = field(default_factory=list)


@dataclass
class TrackInfo:
    """Information about an Ableton track."""
    name: str
    index: int
    volume: float  # Normalized 0.0-1.0 (0.85 = 0dB)
    pan: float  # -1.0 to 1.0
    mute: bool
    solo: bool
    arm: bool
    devices: List[DeviceInfo] = field(default_factory=list)

    @property
    def volume_db(self) -> float:
        """Convert normalized volume to dB (approximate)."""
        if self.volume <= 0:
            return -70.0
        # Ableton's fader is roughly: dB = 20 * log10(normalized * 1.17647)
        # 0.85 normalized = 0dB
        import math
        return 20 * math.log10(self.volume / 0.85 + 0.0001)


@dataclass
class SessionState:
    """Complete snapshot of current Ableton session state."""
    tempo: float
    time_signature_numerator: int
    time_signature_denominator: int
    is_playing: bool
    tracks: List[TrackInfo] = field(default_factory=list)
    master_track: Optional[TrackInfo] = None
    return_tracks: List[TrackInfo] = field(default_factory=list)

    def get_track_by_name(self, name: str) -> Optional[TrackInfo]:
        """Find a track by name (case-insensitive)."""
        name_lower = name.lower()
        for track in self.tracks:
            if track.name.lower() == name_lower:
                return track
        return None


@dataclass
class ParameterChange:
    """A parameter change to apply."""
    track_index: int
    device_index: int
    parameter_index: int
    new_value: float  # Normalized 0.0-1.0
    description: str = ""


@dataclass
class TrackChange:
    """A track-level change to apply."""
    track_index: int
    change_type: str  # 'volume', 'pan', 'mute', 'solo'
    new_value: Any
    description: str = ""


@dataclass
class Fix:
    """A fix recommendation that can be applied to Ableton."""
    id: str
    description: str
    category: str  # 'mixing', 'dynamics', 'frequency', 'stereo', 'mastering'
    severity: str  # 'critical', 'warning', 'suggestion'
    changes: List[Any] = field(default_factory=list)  # ParameterChange or TrackChange

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.description}"


class AbletonBridge:
    """
    Bridge for communicating with Ableton Live via AbletonOSC.

    Usage:
        bridge = AbletonBridge()
        if bridge.connect():
            state = bridge.read_session_state()
            print(f"Tempo: {state.tempo} BPM")
            print(f"Tracks: {len(state.tracks)}")

            # Apply a single change
            bridge.set_track_volume(0, 0.7)

            # Apply batch changes
            changes = [
                TrackChange(0, 'volume', 0.7, "Reduce kick volume"),
                TrackChange(1, 'volume', 0.8, "Reduce bass volume"),
            ]
            bridge.apply_changes(changes)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        send_port: int = 11000,
        receive_port: int = 11001,
        timeout: float = 5.0
    ):
        self.host = host
        self.send_port = send_port
        self.receive_port = receive_port
        self.timeout = timeout

        self._status = ConnectionStatus.DISCONNECTED
        self._live_set = None
        self._osc_client = None
        self._last_error: Optional[str] = None
        self._change_callbacks: List[Callable] = []

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def connect(self) -> bool:
        """
        Establish connection to Ableton via AbletonOSC.

        Returns:
            True if connection successful, False otherwise.
        """
        if not PYLIVE_AVAILABLE:
            self._last_error = "PyLive not installed. Run: pip install pylive"
            self._status = ConnectionStatus.ERROR
            return False

        self._status = ConnectionStatus.CONNECTING

        try:
            # Create PyLive Set object (connects to AbletonOSC)
            self._live_set = live.Set()

            # Scan to verify connection and populate state
            self._live_set.scan()

            # Test connection by reading tempo
            tempo = self._live_set.tempo
            if tempo is None or tempo <= 0:
                raise ConnectionError("Could not read tempo from Ableton")

            self._status = ConnectionStatus.CONNECTED
            self._last_error = None
            return True

        except Exception as e:
            self._last_error = f"Connection failed: {str(e)}. Is Ableton running with AbletonOSC enabled?"
            self._status = ConnectionStatus.ERROR
            return False

    def disconnect(self) -> None:
        """Disconnect from Ableton."""
        self._live_set = None
        self._status = ConnectionStatus.DISCONNECTED

    def read_session_state(self, include_devices: bool = False) -> Optional[SessionState]:
        """
        Read the current state of the Ableton session.

        Args:
            include_devices: If True, read device/parameter info (slower, may timeout).
                           If False, just read track-level info (fast).

        Returns:
            SessionState object with all track/device info, or None if not connected.
        """
        if not self.is_connected or self._live_set is None:
            return None

        try:
            # Rescan to get fresh state
            self._live_set.scan()

            # Build track info
            tracks = []
            for i, track in enumerate(self._live_set.tracks):
                track_info = self._build_track_info(track, i, include_devices=include_devices)
                tracks.append(track_info)

            # Build return track info
            return_tracks = []
            if hasattr(self._live_set, 'return_tracks'):
                for i, track in enumerate(self._live_set.return_tracks):
                    track_info = self._build_track_info(track, i, is_return=True, include_devices=include_devices)
                    return_tracks.append(track_info)

            # Master track
            master_track = None
            if hasattr(self._live_set, 'master_track') and self._live_set.master_track:
                master_track = self._build_track_info(
                    self._live_set.master_track, -1, is_master=True, include_devices=include_devices
                )

            return SessionState(
                tempo=self._live_set.tempo,
                time_signature_numerator=getattr(self._live_set, 'time_signature_numerator', 4),
                time_signature_denominator=getattr(self._live_set, 'time_signature_denominator', 4),
                is_playing=self._live_set.is_playing,
                tracks=tracks,
                master_track=master_track,
                return_tracks=return_tracks
            )

        except Exception as e:
            self._last_error = f"Failed to read session state: {str(e)}"
            return None

    def _build_track_info(
        self,
        track,
        index: int,
        is_return: bool = False,
        is_master: bool = False,
        include_devices: bool = False
    ) -> TrackInfo:
        """Build TrackInfo from a PyLive track object."""
        devices = []

        if include_devices and hasattr(track, 'devices'):
            try:
                for d_idx, device in enumerate(track.devices):
                    device_info = self._build_device_info(device, index, d_idx, track.name)
                    devices.append(device_info)
            except Exception:
                pass  # Skip device info on error

        return TrackInfo(
            name=track.name if hasattr(track, 'name') else f"Track {index}",
            index=index,
            volume=track.volume if hasattr(track, 'volume') else 0.85,
            pan=track.pan if hasattr(track, 'pan') else 0.0,
            mute=track.mute if hasattr(track, 'mute') else False,
            solo=track.solo if hasattr(track, 'solo') else False,
            arm=track.arm if hasattr(track, 'arm') else False,
            devices=devices
        )

    def _build_device_info(
        self,
        device,
        track_index: int,
        device_index: int,
        track_name: str
    ) -> DeviceInfo:
        """Build DeviceInfo from a PyLive device object."""
        parameters = []

        if hasattr(device, 'parameters'):
            for p_idx, param in enumerate(device.parameters):
                param_info = DeviceParameter(
                    name=param.name if hasattr(param, 'name') else f"Param {p_idx}",
                    value=param.value if hasattr(param, 'value') else 0.0,
                    min_value=param.min if hasattr(param, 'min') else 0.0,
                    max_value=param.max if hasattr(param, 'max') else 1.0,
                    device_name=device.name if hasattr(device, 'name') else "Unknown",
                    track_name=track_name,
                    track_index=track_index,
                    device_index=device_index,
                    parameter_index=p_idx
                )
                parameters.append(param_info)

        return DeviceInfo(
            name=device.name if hasattr(device, 'name') else "Unknown",
            class_name=device.class_name if hasattr(device, 'class_name') else "Unknown",
            track_index=track_index,
            device_index=device_index,
            is_enabled=device.is_enabled if hasattr(device, 'is_enabled') else True,
            parameters=parameters
        )

    # ==================== Parameter Setting Methods ====================

    def set_tempo(self, tempo: float) -> bool:
        """Set the session tempo."""
        if not self.is_connected or self._live_set is None:
            return False
        try:
            self._live_set.tempo = tempo
            return True
        except Exception as e:
            self._last_error = f"Failed to set tempo: {str(e)}"
            return False

    def set_track_volume(self, track_index: int, volume: float) -> bool:
        """Set track volume (normalized 0.0-1.0, where 0.85 = 0dB)."""
        if not self.is_connected or self._live_set is None:
            return False
        try:
            self._live_set.tracks[track_index].volume = max(0.0, min(1.0, volume))
            return True
        except Exception as e:
            self._last_error = f"Failed to set track volume: {str(e)}"
            return False

    def set_track_pan(self, track_index: int, pan: float) -> bool:
        """Set track pan (-1.0 to 1.0)."""
        if not self.is_connected or self._live_set is None:
            return False
        try:
            self._live_set.tracks[track_index].pan = max(-1.0, min(1.0, pan))
            return True
        except Exception as e:
            self._last_error = f"Failed to set track pan: {str(e)}"
            return False

    def set_track_mute(self, track_index: int, mute: bool) -> bool:
        """Set track mute state."""
        if not self.is_connected or self._live_set is None:
            return False
        try:
            self._live_set.tracks[track_index].mute = mute
            return True
        except Exception as e:
            self._last_error = f"Failed to set track mute: {str(e)}"
            return False

    def set_device_parameter(
        self,
        track_index: int,
        device_index: int,
        parameter_index: int,
        value: float
    ) -> bool:
        """Set a device parameter value (normalized 0.0-1.0)."""
        if not self.is_connected or self._live_set is None:
            return False
        try:
            device = self._live_set.tracks[track_index].devices[device_index]
            device.parameters[parameter_index].value = max(0.0, min(1.0, value))
            return True
        except Exception as e:
            self._last_error = f"Failed to set device parameter: {str(e)}"
            return False

    def set_master_volume(self, volume: float) -> bool:
        """Set master track volume."""
        if not self.is_connected or self._live_set is None:
            return False
        try:
            self._live_set.master_track.volume = max(0.0, min(1.0, volume))
            return True
        except Exception as e:
            self._last_error = f"Failed to set master volume: {str(e)}"
            return False

    # ==================== Batch Operations ====================

    def apply_change(self, change) -> bool:
        """
        Apply a single change to Ableton.

        Args:
            change: A ParameterChange or TrackChange object

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_connected:
            self._last_error = "Not connected to Ableton"
            return False

        try:
            if isinstance(change, ParameterChange):
                return self.set_device_parameter(
                    change.track_index,
                    change.device_index,
                    change.parameter_index,
                    change.new_value
                )
            elif isinstance(change, TrackChange):
                if change.change_type == 'volume':
                    return self.set_track_volume(change.track_index, change.new_value)
                elif change.change_type == 'pan':
                    return self.set_track_pan(change.track_index, change.new_value)
                elif change.change_type == 'mute':
                    return self.set_track_mute(change.track_index, change.new_value)
                else:
                    self._last_error = f"Unknown change type: {change.change_type}"
                    return False
            else:
                self._last_error = f"Unknown change object type: {type(change)}"
                return False
        except Exception as e:
            self._last_error = str(e)
            return False

    def apply_changes(self, changes: List[Any]) -> Tuple[int, int, List[str]]:
        """
        Apply a batch of changes to Ableton.

        Args:
            changes: List of ParameterChange or TrackChange objects

        Returns:
            Tuple of (successful_count, failed_count, error_messages)
        """
        if not self.is_connected:
            return 0, len(changes), ["Not connected to Ableton"]

        successful = 0
        failed = 0
        errors = []

        for change in changes:
            try:
                if isinstance(change, ParameterChange):
                    success = self.set_device_parameter(
                        change.track_index,
                        change.device_index,
                        change.parameter_index,
                        change.new_value
                    )
                elif isinstance(change, TrackChange):
                    if change.change_type == 'volume':
                        success = self.set_track_volume(change.track_index, change.new_value)
                    elif change.change_type == 'pan':
                        success = self.set_track_pan(change.track_index, change.new_value)
                    elif change.change_type == 'mute':
                        success = self.set_track_mute(change.track_index, change.new_value)
                    else:
                        success = False
                        errors.append(f"Unknown change type: {change.change_type}")
                else:
                    success = False
                    errors.append(f"Unknown change object type: {type(change)}")

                if success:
                    successful += 1
                else:
                    failed += 1
                    if self._last_error:
                        errors.append(self._last_error)

            except Exception as e:
                failed += 1
                errors.append(str(e))

        return successful, failed, errors

    def apply_fix(self, fix: Fix) -> Tuple[bool, str]:
        """
        Apply a single Fix object with all its changes.

        Returns:
            Tuple of (success, message)
        """
        if not fix.changes:
            return True, "No changes to apply"

        successful, failed, errors = self.apply_changes(fix.changes)

        if failed == 0:
            return True, f"Applied {successful} changes: {fix.description}"
        elif successful == 0:
            return False, f"Failed to apply fix: {'; '.join(errors)}"
        else:
            return True, f"Partially applied ({successful}/{successful+failed}): {'; '.join(errors)}"

    def apply_fixes(self, fixes: List[Fix]) -> Dict[str, Any]:
        """
        Apply multiple fixes.

        Returns:
            Summary dict with results for each fix.
        """
        results = {
            'total': len(fixes),
            'successful': 0,
            'partial': 0,
            'failed': 0,
            'details': []
        }

        for fix in fixes:
            success, message = self.apply_fix(fix)
            detail = {
                'id': fix.id,
                'description': fix.description,
                'success': success,
                'message': message
            }
            results['details'].append(detail)

            if success and 'Partially' not in message:
                results['successful'] += 1
            elif success:
                results['partial'] += 1
            else:
                results['failed'] += 1

        return results

    # ==================== Transport Controls ====================

    def play(self) -> bool:
        """Start playback."""
        if not self.is_connected or self._live_set is None:
            return False
        try:
            self._live_set.play()
            return True
        except Exception as e:
            self._last_error = f"Failed to start playback: {str(e)}"
            return False

    def stop(self) -> bool:
        """Stop playback."""
        if not self.is_connected or self._live_set is None:
            return False
        try:
            self._live_set.stop()
            return True
        except Exception as e:
            self._last_error = f"Failed to stop playback: {str(e)}"
            return False

    # ==================== Utility Methods ====================

    def find_device_parameter(
        self,
        device_name: str,
        parameter_name: str,
        track_index: Optional[int] = None
    ) -> Optional[DeviceParameter]:
        """
        Find a specific device parameter by name.

        Args:
            device_name: Name of the device (e.g., "EQ Eight", "Compressor")
            parameter_name: Name of the parameter (e.g., "Threshold", "Ratio")
            track_index: Optional track index to search (None = search all tracks)

        Returns:
            DeviceParameter if found, None otherwise.
        """
        state = self.read_session_state()
        if not state:
            return None

        tracks_to_search = [state.tracks[track_index]] if track_index is not None else state.tracks

        for track in tracks_to_search:
            for device in track.devices:
                if device_name.lower() in device.name.lower():
                    for param in device.parameters:
                        if parameter_name.lower() in param.name.lower():
                            return param

        return None

    def get_master_chain_devices(self) -> List[DeviceInfo]:
        """Get all devices on the master track."""
        state = self.read_session_state()
        if not state or not state.master_track:
            return []
        return state.master_track.devices


# ==================== Convenience Functions ====================

def quick_connect() -> Optional[AbletonBridge]:
    """
    Quick connect to Ableton.

    Returns:
        Connected AbletonBridge instance, or None if connection failed.
    """
    bridge = AbletonBridge()
    if bridge.connect():
        return bridge
    print(f"Failed to connect: {bridge.last_error}")
    return None


def test_connection() -> bool:
    """
    Test if AbletonOSC connection is working.

    Returns:
        True if connection successful, False otherwise.
    """
    bridge = AbletonBridge()
    success = bridge.connect()
    if success:
        state = bridge.read_session_state(include_devices=False)
        if state:
            print(f"Connected to Ableton Live!")
            print(f"  Tempo: {state.tempo} BPM")
            print(f"  Tracks: {len(state.tracks)}")
            print(f"  Return Tracks: {len(state.return_tracks)}")
            print(f"  Playing: {state.is_playing}")
            print(f"\nFirst 5 tracks:")
            for track in state.tracks[:5]:
                print(f"    [{track.index}] {track.name} (vol: {track.volume:.2f}, mute: {track.mute})")
            return True
    print(f"Connection failed: {bridge.last_error}")
    return False


if __name__ == "__main__":
    # Test the connection
    print("Testing Ableton Bridge connection...")
    print("-" * 40)
    test_connection()
