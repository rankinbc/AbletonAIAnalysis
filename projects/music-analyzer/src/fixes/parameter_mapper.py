"""
Parameter Mapper Module.

Maps audio feature deltas to specific Ableton Live device parameter changes.
Provides the translation layer between abstract audio analysis and concrete
mix adjustments.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable, Tuple
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ParameterChange:
    """A specific parameter change recommendation."""
    device_type: str  # 'Compressor', 'EQ Eight', 'Utility', etc.
    parameter_name: str  # Human-readable parameter name
    current_value: Optional[float]  # Current value if known
    target_value: float  # Recommended value
    change_amount: float  # Delta to apply
    unit: str  # 'dB', '%', 'ratio', 'Hz', etc.

    # For OSC control
    osc_parameter_index: Optional[int] = None  # Parameter index in device

    # Context
    explanation: str = ""  # Why this change helps

    def format_change(self) -> str:
        """Format change as human-readable string."""
        if self.change_amount >= 0:
            direction = "Increase"
            sign = "+"
        else:
            direction = "Decrease"
            sign = ""

        return f"{direction} {self.parameter_name} by {sign}{self.change_amount:.1f} {self.unit}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'device_type': self.device_type,
            'parameter_name': self.parameter_name,
            'current_value': self.current_value,
            'target_value': self.target_value,
            'change_amount': self.change_amount,
            'unit': self.unit,
            'osc_parameter_index': self.osc_parameter_index,
            'explanation': self.explanation
        }


# Feature to device/parameter mapping
# Each entry defines how to translate a feature gap into a parameter change
FEATURE_TO_DEVICE_MAP: Dict[str, Dict[str, Any]] = {
    # === SIDECHAIN/PUMPING ===
    'pumping_modulation_depth_db': {
        'device': 'Compressor',
        'parameter': 'Threshold',
        'osc_param_index': 2,
        'direction': 'inverse',  # Lower threshold = more compression
        'scale': lambda delta: delta * -0.8,  # Convert dB gap to threshold change
        'unit': 'dB',
        'target_tracks': ['Bass', 'Pad', 'Synth'],  # Typical sidechain targets
        'explanation': "Sidechain compression depth affects the 'pumping' feel. "
                      "Adjusting compressor threshold changes how much the signal ducks."
    },
    'pumping_score': {
        'device': 'Compressor',
        'parameter': 'Ratio',
        'osc_param_index': 3,
        'direction': 'direct',
        'scale': lambda delta: delta * 2.0,  # Score gap to ratio change
        'unit': ':1',
        'target_tracks': ['Bass', 'Pad'],
        'explanation': "Higher compression ratio increases pumping intensity."
    },
    'pumping_regularity': {
        'device': 'Compressor',
        'parameter': 'Release',
        'osc_param_index': 5,
        'direction': 'inverse',
        'scale': lambda delta: delta * -50,  # Convert to ms
        'unit': 'ms',
        'target_tracks': ['Bass', 'Pad'],
        'explanation': "Release time affects pumping rhythm consistency."
    },

    # === STEREO WIDTH ===
    'stereo_width': {
        'device': 'Utility',
        'parameter': 'Width',
        'osc_param_index': 4,
        'direction': 'direct',
        'scale': lambda delta: delta * 200,  # Convert 0-1 to 0-200%
        'unit': '%',
        'target_tracks': ['Lead', 'Pad', 'Synth', 'Master'],
        'explanation': "Stereo width affects the perceived spaciousness. "
                      "Utility Width parameter controls the stereo spread."
    },
    'phase_correlation': {
        'device': 'Utility',
        'parameter': 'Width',
        'osc_param_index': 4,
        'direction': 'inverse',  # Lower correlation often means too wide
        'scale': lambda delta: delta * -50,  # Reduce width if correlation too low
        'unit': '%',
        'target_tracks': ['Master'],
        'explanation': "Phase correlation below 0.3 can cause mono compatibility issues. "
                      "Reduce stereo width to improve mono playback."
    },
    'supersaw_score': {
        'device': 'Chorus',
        'parameter': 'Amount',
        'osc_param_index': 1,
        'direction': 'direct',
        'scale': lambda delta: delta * 50,  # Convert score to percentage
        'unit': '%',
        'target_tracks': ['Lead', 'Pad'],
        'alternative_devices': ['Utility', 'Dimension Expander'],
        'explanation': "Supersaw width comes from detuning and chorus. "
                      "Add chorus or increase existing chorus amount."
    },

    # === FREQUENCY BALANCE ===
    'spectral_brightness': {
        'device': 'EQ Eight',
        'parameter': 'High Shelf Gain',
        'osc_param_index': 14,  # Typical position for band 8
        'direction': 'direct',
        'scale': lambda delta: delta * 6,  # Convert brightness score to dB
        'unit': 'dB',
        'target_tracks': ['Master'],
        'band_config': {
            'type': 'high_shelf',
            'frequency': 8000,
            'q': 0.7
        },
        'explanation': "Spectral brightness is controlled with high-frequency EQ. "
                      "A high shelf at 8kHz affects the overall brightness."
    },

    # === ENERGY/DYNAMICS ===
    'energy_progression': {
        'device': 'Compressor',
        'parameter': 'Makeup Gain',
        'osc_param_index': 7,
        'direction': 'direct',
        'scale': lambda delta: delta * 3,
        'unit': 'dB',
        'target_tracks': ['Master', 'Drum Bus'],
        'is_arrangement_fix': True,  # Primarily an arrangement issue
        'explanation': "Energy progression relates to arrangement contrast. "
                      "Bus compression can help, but arrangement changes may be needed."
    },
    'energy_range': {
        'device': 'Compressor',
        'parameter': 'Threshold',
        'osc_param_index': 2,
        'direction': 'inverse',
        'scale': lambda delta: delta * -2,
        'unit': 'dB',
        'target_tracks': ['Master'],
        'explanation': "Energy range reflects dynamic contrast between sections."
    },

    # === RHYTHM ===
    'four_on_floor_score': {
        'device': 'Volume',  # Track volume adjustment
        'parameter': 'Volume',
        'osc_param_index': 0,
        'direction': 'direct',
        'scale': lambda delta: delta * 3,
        'unit': 'dB',
        'target_tracks': ['Kick', 'Drums'],
        'explanation': "Four-on-the-floor strength is mostly about kick prominence. "
                      "Increase kick volume or add compression to make it punch through."
    },
    'four_on_floor_strength': {
        'device': 'Compressor',
        'parameter': 'Attack',
        'osc_param_index': 4,
        'direction': 'inverse',
        'scale': lambda delta: delta * -10,  # Faster attack for more punch
        'unit': 'ms',
        'target_tracks': ['Kick', 'Drums'],
        'explanation': "Kick punch can be enhanced with faster compressor attack."
    },
    'offbeat_hihat_score': {
        'device': 'Volume',
        'parameter': 'Volume',
        'osc_param_index': 0,
        'direction': 'direct',
        'scale': lambda delta: delta * 4,
        'unit': 'dB',
        'target_tracks': ['Hihat', 'HiHat', 'Hi-Hat', 'Hats'],
        'explanation': "Off-beat hihat drive is essential for trance groove. "
                      "Increase hihat volume or add more prominent offbeat hits."
    },
    'offbeat_hihat_strength': {
        'device': 'Volume',
        'parameter': 'Volume',
        'osc_param_index': 0,
        'direction': 'direct',
        'scale': lambda delta: delta * 3,
        'unit': 'dB',
        'target_tracks': ['Hihat', 'HiHat', 'Hi-Hat', 'Hats'],
        'explanation': "Strengthen offbeat hihats for more rhythmic drive."
    },

    # === ACID/303 ===
    'acid_303_score': {
        'device': 'Auto Filter',
        'parameter': 'Frequency',
        'osc_param_index': 1,
        'direction': 'direct',
        'scale': lambda delta: delta * 2000,  # Convert to Hz
        'unit': 'Hz',
        'target_tracks': ['Bass', '303', 'Acid'],
        'is_sound_design': True,  # Requires sound design changes
        'explanation': "303 acid sound needs resonant filter sweeps. "
                      "Add Auto Filter with high resonance and modulation."
    },
    'acid_filter_sweep_score': {
        'device': 'Auto Filter',
        'parameter': 'LFO Amount',
        'osc_param_index': 6,
        'direction': 'direct',
        'scale': lambda delta: delta * 50,
        'unit': '%',
        'target_tracks': ['Bass', '303', 'Acid'],
        'explanation': "Filter sweeps create the classic acid movement."
    },
    'acid_resonance_score': {
        'device': 'Auto Filter',
        'parameter': 'Resonance',
        'osc_param_index': 2,
        'direction': 'direct',
        'scale': lambda delta: delta * 60,
        'unit': '%',
        'target_tracks': ['Bass', '303', 'Acid'],
        'explanation': "High resonance is key to the acid sound."
    },

    # === TEMPO ===
    'tempo_score': {
        'device': 'Transport',
        'parameter': 'Tempo',
        'osc_param_index': None,  # Special handling
        'direction': 'direct',
        'scale': lambda delta: delta * 10,  # Small adjustments
        'unit': 'BPM',
        'is_project_setting': True,
        'explanation': "Trance typically runs 138-142 BPM. "
                      "Tempo changes require re-rendering."
    },
    'tempo_stability': {
        'device': 'Transport',
        'parameter': 'Tempo',
        'is_project_setting': True,
        'explanation': "Tempo instability usually indicates warping issues or live recording."
    },
}


class ParameterMapper:
    """
    Maps feature gaps to specific Ableton device parameter changes.

    Provides the translation layer between abstract audio analysis
    results and concrete, actionable mix adjustments.
    """

    def __init__(self, custom_mappings: Optional[Dict[str, Dict]] = None):
        """
        Initialize mapper with optional custom mappings.

        Args:
            custom_mappings: Additional or override mappings
        """
        self.mappings = FEATURE_TO_DEVICE_MAP.copy()
        if custom_mappings:
            self.mappings.update(custom_mappings)

    def map_gap_to_parameter(
        self,
        feature_name: str,
        delta: float,
        current_value: Optional[float] = None
    ) -> Optional[ParameterChange]:
        """
        Convert a feature gap to a specific parameter change.

        Args:
            feature_name: Name of the audio feature
            delta: Gap value (WIP - target)
            current_value: Current feature value if known

        Returns:
            ParameterChange or None if feature not mappable
        """
        if feature_name not in self.mappings:
            return None

        mapping = self.mappings[feature_name]

        # Get scale function
        scale_fn = mapping.get('scale', lambda x: x)

        # Apply direction and scale
        direction = mapping.get('direction', 'direct')
        if direction == 'inverse':
            change_amount = scale_fn(-delta)
        else:
            change_amount = scale_fn(delta)

        # Calculate target value (if we have current)
        target_value = change_amount
        if current_value is not None:
            target_value = current_value + change_amount

        return ParameterChange(
            device_type=mapping.get('device', 'Unknown'),
            parameter_name=mapping.get('parameter', 'Unknown'),
            current_value=current_value,
            target_value=target_value,
            change_amount=change_amount,
            unit=mapping.get('unit', ''),
            osc_parameter_index=mapping.get('osc_param_index'),
            explanation=mapping.get('explanation', '')
        )

    def get_target_tracks(self, feature_name: str) -> List[str]:
        """
        Get list of track names typically affected by this feature.

        Args:
            feature_name: Name of the audio feature

        Returns:
            List of typical track names
        """
        if feature_name not in self.mappings:
            return []

        return self.mappings[feature_name].get('target_tracks', [])

    def find_device_on_track(
        self,
        als_data: Dict[str, Any],
        track_name: str,
        device_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a specific device on a track in the ALS project data.

        Args:
            als_data: Parsed ALS project dictionary
            track_name: Name of track to search
            device_type: Type of device to find

        Returns:
            Device info dict or None
        """
        # Handle ALSProject object or dict
        tracks = als_data.get('tracks', [])
        if hasattr(als_data, 'tracks'):
            tracks = als_data.tracks

        for track in tracks:
            # Get track name
            t_name = track.get('name', '') if isinstance(track, dict) else track.name

            # Check if track name matches (case-insensitive, partial match)
            if track_name.lower() in t_name.lower():
                # Get devices
                devices = track.get('devices', []) if isinstance(track, dict) else track.devices

                for i, device in enumerate(devices):
                    d_name = device if isinstance(device, str) else device.get('name', '')
                    if device_type.lower() in d_name.lower():
                        return {
                            'track_name': t_name,
                            'track_index': track.get('id', i) if isinstance(track, dict) else track.id,
                            'device_name': d_name,
                            'device_index': i
                        }

        return None

    def find_matching_track(
        self,
        als_data: Dict[str, Any],
        target_tracks: List[str]
    ) -> Optional[Tuple[str, int]]:
        """
        Find a track matching one of the target track names.

        Args:
            als_data: Parsed ALS project data
            target_tracks: List of track names to search for

        Returns:
            (track_name, track_index) or None
        """
        tracks = als_data.get('tracks', [])
        if hasattr(als_data, 'tracks'):
            tracks = als_data.tracks

        for target in target_tracks:
            for track in tracks:
                t_name = track.get('name', '') if isinstance(track, dict) else track.name
                t_id = track.get('id', 0) if isinstance(track, dict) else track.id

                if target.lower() in t_name.lower():
                    return (t_name, t_id)

        return None

    def is_arrangement_fix(self, feature_name: str) -> bool:
        """Check if this feature primarily requires arrangement changes."""
        if feature_name not in self.mappings:
            return False
        return self.mappings[feature_name].get('is_arrangement_fix', False)

    def is_sound_design_fix(self, feature_name: str) -> bool:
        """Check if this feature primarily requires sound design changes."""
        if feature_name not in self.mappings:
            return False
        return self.mappings[feature_name].get('is_sound_design', False)

    def is_project_setting(self, feature_name: str) -> bool:
        """Check if this feature requires project-level settings change."""
        if feature_name not in self.mappings:
            return False
        return self.mappings[feature_name].get('is_project_setting', False)

    def get_alternative_devices(self, feature_name: str) -> List[str]:
        """Get alternative devices that can address this feature."""
        if feature_name not in self.mappings:
            return []
        return self.mappings[feature_name].get('alternative_devices', [])

    def format_osc_command(
        self,
        track_index: int,
        device_index: int,
        param_index: int,
        value: float
    ) -> str:
        """
        Format an AbletonOSC command for the parameter change.

        Args:
            track_index: Track index (0-based)
            device_index: Device index on track (0-based)
            param_index: Parameter index in device
            value: Target value

        Returns:
            OSC command string
        """
        return f"/live/track/{track_index}/device/{device_index}/parameter/{param_index} set {value:.2f}"
