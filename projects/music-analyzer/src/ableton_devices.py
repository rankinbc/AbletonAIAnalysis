"""
Ableton Device Parameter Database

Maps common Ableton devices to their parameter names and indices,
enabling targeted parameter adjustments for fixes.

Note: Parameter indices can vary by device version. These are based on
Live 11 Suite. The code falls back to parameter name matching when possible.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class DeviceCategory(Enum):
    EQ = "eq"
    COMPRESSOR = "compressor"
    LIMITER = "limiter"
    UTILITY = "utility"
    FILTER = "filter"
    SATURATOR = "saturator"
    REVERB = "reverb"
    DELAY = "delay"
    OTHER = "other"


@dataclass
class ParameterInfo:
    """Information about a device parameter."""
    name: str
    index: int  # Typical index (may vary)
    min_value: float = 0.0
    max_value: float = 1.0
    default_value: float = 0.5
    unit: str = ""
    description: str = ""


@dataclass
class DeviceTemplate:
    """Template for a known Ableton device."""
    name: str
    class_name: str  # Internal Ableton class name
    category: DeviceCategory
    parameters: Dict[str, ParameterInfo] = field(default_factory=dict)

    # For EQs: band structure
    num_bands: int = 0
    band_params: List[str] = field(default_factory=list)  # Per-band param names


# Known Ableton devices and their parameters
DEVICE_TEMPLATES: Dict[str, DeviceTemplate] = {
    # ==================== EQ DEVICES ====================
    "EQ Eight": DeviceTemplate(
        name="EQ Eight",
        class_name="Eq8",
        category=DeviceCategory.EQ,
        num_bands=8,
        band_params=["Frequency", "Gain", "Q", "Type"],  # Per band
        parameters={
            "Device On": ParameterInfo("Device On", 0, 0, 1, 1),
            # Band 1
            "1 Filter On": ParameterInfo("1 Filter On", 1, 0, 1, 1),
            "1 Filter Type": ParameterInfo("1 Filter Type", 2, 0, 1, 0),
            "1 Frequency": ParameterInfo("1 Frequency", 3, 0, 1, 0.2, "Hz"),
            "1 Gain": ParameterInfo("1 Gain", 4, 0, 1, 0.5, "dB", "-15 to +15"),
            "1 Resonance": ParameterInfo("1 Resonance", 5, 0, 1, 0.4),
            # Band 2
            "2 Filter On": ParameterInfo("2 Filter On", 6, 0, 1, 1),
            "2 Filter Type": ParameterInfo("2 Filter Type", 7, 0, 1, 0),
            "2 Frequency": ParameterInfo("2 Frequency", 8, 0, 1, 0.3, "Hz"),
            "2 Gain": ParameterInfo("2 Gain", 9, 0, 1, 0.5, "dB"),
            "2 Resonance": ParameterInfo("2 Resonance", 10, 0, 1, 0.4),
            # Band 3
            "3 Filter On": ParameterInfo("3 Filter On", 11, 0, 1, 1),
            "3 Filter Type": ParameterInfo("3 Filter Type", 12, 0, 1, 0),
            "3 Frequency": ParameterInfo("3 Frequency", 13, 0, 1, 0.4, "Hz"),
            "3 Gain": ParameterInfo("3 Gain", 14, 0, 1, 0.5, "dB"),
            "3 Resonance": ParameterInfo("3 Resonance", 15, 0, 1, 0.4),
            # Band 4
            "4 Filter On": ParameterInfo("4 Filter On", 16, 0, 1, 1),
            "4 Filter Type": ParameterInfo("4 Filter Type", 17, 0, 1, 0),
            "4 Frequency": ParameterInfo("4 Frequency", 18, 0, 1, 0.5, "Hz"),
            "4 Gain": ParameterInfo("4 Gain", 19, 0, 1, 0.5, "dB"),
            "4 Resonance": ParameterInfo("4 Resonance", 20, 0, 1, 0.4),
            # Continue for bands 5-8...
            "Scale": ParameterInfo("Scale", 33, 0, 1, 1.0, "%", "Output scale"),
        }
    ),

    "EQ Three": DeviceTemplate(
        name="EQ Three",
        class_name="FilterEQ3",
        category=DeviceCategory.EQ,
        parameters={
            "Device On": ParameterInfo("Device On", 0, 0, 1, 1),
            "LowOn": ParameterInfo("LowOn", 1, 0, 1, 1),
            "MidOn": ParameterInfo("MidOn", 2, 0, 1, 1),
            "HighOn": ParameterInfo("HighOn", 3, 0, 1, 1),
            "GainLo": ParameterInfo("GainLo", 4, 0, 1, 0.5, "dB"),
            "GainMid": ParameterInfo("GainMid", 5, 0, 1, 0.5, "dB"),
            "GainHi": ParameterInfo("GainHi", 6, 0, 1, 0.5, "dB"),
            "FreqLo": ParameterInfo("FreqLo", 7, 0, 1, 0.3, "Hz"),
            "FreqHi": ParameterInfo("FreqHi", 8, 0, 1, 0.7, "Hz"),
        }
    ),

    "Channel EQ": DeviceTemplate(
        name="Channel EQ",
        class_name="ChannelEq",
        category=DeviceCategory.EQ,
        parameters={
            "Highpass On": ParameterInfo("Highpass On", 1, 0, 1, 0),
            "Highpass Freq": ParameterInfo("Highpass Freq", 2, 0, 1, 0.1, "Hz"),
            "Low Gain": ParameterInfo("Low Gain", 3, 0, 1, 0.5, "dB"),
            "Mid Gain": ParameterInfo("Mid Gain", 4, 0, 1, 0.5, "dB"),
            "Mid Freq": ParameterInfo("Mid Freq", 5, 0, 1, 0.5, "Hz"),
            "High Gain": ParameterInfo("High Gain", 6, 0, 1, 0.5, "dB"),
            "Output Gain": ParameterInfo("Output Gain", 7, 0, 1, 0.5, "dB"),
        }
    ),

    # ==================== DYNAMICS ====================
    "Compressor": DeviceTemplate(
        name="Compressor",
        class_name="Compressor2",
        category=DeviceCategory.COMPRESSOR,
        parameters={
            "Device On": ParameterInfo("Device On", 0, 0, 1, 1),
            "Threshold": ParameterInfo("Threshold", 1, 0, 1, 0.7, "dB"),
            "Ratio": ParameterInfo("Ratio", 2, 0, 1, 0.3),
            "Attack": ParameterInfo("Attack", 3, 0, 1, 0.3, "ms"),
            "Release": ParameterInfo("Release", 4, 0, 1, 0.5, "ms"),
            "Knee": ParameterInfo("Knee", 5, 0, 1, 0.5, "dB"),
            "Model": ParameterInfo("Model", 6, 0, 1, 0),
            "Output Gain": ParameterInfo("Output Gain", 7, 0, 1, 0.5, "dB"),
            "Dry/Wet": ParameterInfo("Dry/Wet", 8, 0, 1, 1.0),
        }
    ),

    "Glue Compressor": DeviceTemplate(
        name="Glue Compressor",
        class_name="GlueCompressor",
        category=DeviceCategory.COMPRESSOR,
        parameters={
            "Threshold": ParameterInfo("Threshold", 1, 0, 1, 0.7, "dB"),
            "Ratio": ParameterInfo("Ratio", 2, 0, 1, 0.3),
            "Attack": ParameterInfo("Attack", 3, 0, 1, 0.3, "ms"),
            "Release": ParameterInfo("Release", 4, 0, 1, 0.5, "ms"),
            "Makeup": ParameterInfo("Makeup", 5, 0, 1, 0.5, "dB"),
            "Dry/Wet": ParameterInfo("Dry/Wet", 6, 0, 1, 1.0),
            "Peak Clip In": ParameterInfo("Peak Clip In", 7, 0, 1, 0),
        }
    ),

    "Limiter": DeviceTemplate(
        name="Limiter",
        class_name="Limiter",
        category=DeviceCategory.LIMITER,
        parameters={
            "Device On": ParameterInfo("Device On", 0, 0, 1, 1),
            "Gain": ParameterInfo("Gain", 1, 0, 1, 0.5, "dB", "Input gain"),
            "Ceiling": ParameterInfo("Ceiling", 2, 0, 1, 0.95, "dB", "Output ceiling"),
            "Release": ParameterInfo("Release", 3, 0, 1, 0.5, "ms"),
            "Auto Release": ParameterInfo("Auto Release", 4, 0, 1, 1),
        }
    ),

    # ==================== UTILITY ====================
    "Utility": DeviceTemplate(
        name="Utility",
        class_name="StereoGain",
        category=DeviceCategory.UTILITY,
        parameters={
            "Device On": ParameterInfo("Device On", 0, 0, 1, 1),
            "Mute": ParameterInfo("Mute", 1, 0, 1, 0),
            "Left Inv": ParameterInfo("Left Inv", 2, 0, 1, 0),
            "Right Inv": ParameterInfo("Right Inv", 3, 0, 1, 0),
            "Channel Mode": ParameterInfo("Channel Mode", 4, 0, 1, 0),  # 0=stereo, 0.5=swap, etc
            "Stereo Width": ParameterInfo("Stereo Width", 5, 0, 1, 0.5, "%", "0=mono, 0.5=100%, 1=200%"),
            "Mono": ParameterInfo("Mono", 6, 0, 1, 0),
            "Bass Mono": ParameterInfo("Bass Mono", 7, 0, 1, 0),
            "Bass Mono Freq": ParameterInfo("Bass Mono Freq", 8, 0, 1, 0.3, "Hz"),
            "Balance": ParameterInfo("Balance", 9, 0, 1, 0.5, "", "L/R balance"),
            "Gain": ParameterInfo("Gain", 10, 0, 1, 0.5, "dB"),
            "DC Filter": ParameterInfo("DC Filter", 11, 0, 1, 0),
        }
    ),

    # ==================== FILTERS ====================
    "Auto Filter": DeviceTemplate(
        name="Auto Filter",
        class_name="AutoFilter",
        category=DeviceCategory.FILTER,
        parameters={
            "Device On": ParameterInfo("Device On", 0, 0, 1, 1),
            "Filter Type": ParameterInfo("Filter Type", 1, 0, 1, 0),
            "Frequency": ParameterInfo("Frequency", 2, 0, 1, 0.5, "Hz"),
            "Resonance": ParameterInfo("Resonance", 3, 0, 1, 0.3),
            "Env Amount": ParameterInfo("Env Amount", 4, 0, 1, 0.5),
            "Env Attack": ParameterInfo("Env Attack", 5, 0, 1, 0.3, "ms"),
            "Env Release": ParameterInfo("Env Release", 6, 0, 1, 0.5, "ms"),
            "LFO Amount": ParameterInfo("LFO Amount", 7, 0, 1, 0),
            "LFO Rate": ParameterInfo("LFO Rate", 8, 0, 1, 0.5, "Hz"),
        }
    ),

    # ==================== SATURATOR ====================
    "Saturator": DeviceTemplate(
        name="Saturator",
        class_name="Saturator",
        category=DeviceCategory.SATURATOR,
        parameters={
            "Device On": ParameterInfo("Device On", 0, 0, 1, 1),
            "Drive": ParameterInfo("Drive", 1, 0, 1, 0.5, "dB"),
            "Type": ParameterInfo("Type", 2, 0, 1, 0),
            "Output": ParameterInfo("Output", 3, 0, 1, 0.5, "dB"),
            "Dry/Wet": ParameterInfo("Dry/Wet", 4, 0, 1, 1.0),
        }
    ),

    # ==================== DRUM BUSS ====================
    "Drum Buss": DeviceTemplate(
        name="Drum Buss",
        class_name="DrumBuss",
        category=DeviceCategory.COMPRESSOR,
        parameters={
            "Drive": ParameterInfo("Drive", 1, 0, 1, 0.3),
            "Crunch": ParameterInfo("Crunch", 2, 0, 1, 0),
            "Boom": ParameterInfo("Boom", 3, 0, 1, 0.5),
            "Transients": ParameterInfo("Transients", 4, 0, 1, 0.5, "", "Transient shaping"),
            "Damping": ParameterInfo("Damping", 5, 0, 1, 0.5, "Hz"),
            "Output Gain": ParameterInfo("Output Gain", 6, 0, 1, 0.5, "dB"),
            "Dry/Wet": ParameterInfo("Dry/Wet", 7, 0, 1, 1.0),
        }
    ),
}


class DeviceFinder:
    """
    Finds and identifies devices on Ableton tracks.
    """

    def __init__(self):
        self.templates = DEVICE_TEMPLATES

    def identify_device(self, device_name: str, class_name: str = None) -> Optional[DeviceTemplate]:
        """
        Identify a device by name and optionally class name.

        Returns matching DeviceTemplate or None.
        """
        # Direct name match
        if device_name in self.templates:
            return self.templates[device_name]

        # Fuzzy match by name
        device_lower = device_name.lower()
        for name, template in self.templates.items():
            if name.lower() in device_lower or device_lower in name.lower():
                return template

        # Match by class name
        if class_name:
            for template in self.templates.values():
                if template.class_name == class_name:
                    return template

        return None

    def find_parameter(
        self,
        device_template: DeviceTemplate,
        param_name: str
    ) -> Optional[ParameterInfo]:
        """Find a parameter in a device template by name."""
        # Direct match
        if param_name in device_template.parameters:
            return device_template.parameters[param_name]

        # Fuzzy match
        param_lower = param_name.lower()
        for name, info in device_template.parameters.items():
            if param_lower in name.lower() or name.lower() in param_lower:
                return info

        return None

    def get_eq_devices_on_track(self, track_devices: List[dict]) -> List[Tuple[int, DeviceTemplate]]:
        """
        Find all EQ devices on a track.

        Args:
            track_devices: List of device info dicts with 'name' and optionally 'class_name'

        Returns:
            List of (device_index, DeviceTemplate) tuples
        """
        eq_devices = []
        for i, device in enumerate(track_devices):
            template = self.identify_device(
                device.get('name', ''),
                device.get('class_name')
            )
            if template and template.category == DeviceCategory.EQ:
                eq_devices.append((i, template))
        return eq_devices

    def get_utility_on_track(self, track_devices: List[dict]) -> Optional[Tuple[int, DeviceTemplate]]:
        """Find Utility device on a track."""
        for i, device in enumerate(track_devices):
            template = self.identify_device(
                device.get('name', ''),
                device.get('class_name')
            )
            if template and template.category == DeviceCategory.UTILITY:
                return (i, template)
        return None

    def get_compressor_on_track(self, track_devices: List[dict]) -> Optional[Tuple[int, DeviceTemplate]]:
        """Find compressor/limiter on a track."""
        for i, device in enumerate(track_devices):
            template = self.identify_device(
                device.get('name', ''),
                device.get('class_name')
            )
            if template and template.category in [DeviceCategory.COMPRESSOR, DeviceCategory.LIMITER]:
                return (i, template)
        return None


# Frequency to normalized EQ parameter conversion (approximate for EQ Eight)
def freq_to_eq_param(freq_hz: float) -> float:
    """Convert frequency in Hz to EQ Eight normalized parameter (0-1)."""
    # EQ Eight frequency range is roughly 20Hz to 20kHz on a log scale
    import math
    min_freq = 20
    max_freq = 20000

    freq_hz = max(min_freq, min(max_freq, freq_hz))
    normalized = (math.log10(freq_hz) - math.log10(min_freq)) / (math.log10(max_freq) - math.log10(min_freq))
    return normalized


def gain_db_to_eq_param(gain_db: float) -> float:
    """Convert gain in dB to EQ Eight normalized parameter (0-1)."""
    # EQ Eight gain range is roughly -15dB to +15dB
    # 0.5 = 0dB, 0 = -15dB, 1 = +15dB
    gain_db = max(-15, min(15, gain_db))
    return (gain_db + 15) / 30


def width_pct_to_utility_param(width_pct: float) -> float:
    """Convert stereo width percentage to Utility parameter (0-1)."""
    # Utility: 0 = 0%, 0.5 = 100%, 1 = 200%
    width_pct = max(0, min(200, width_pct))
    return width_pct / 200
