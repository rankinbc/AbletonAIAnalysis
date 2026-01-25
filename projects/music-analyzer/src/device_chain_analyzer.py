"""
Device Chain Analyzer for Ableton Live Sets

Extracts detailed device chain information from .als files including:
- Complete device order in signal chain
- Device ON/OFF states
- Full parameter values for native Ableton devices
- VST/AU plugin detection
- Effect chain analysis and issue detection

Designed for Ableton Live 11 Suite (compatible with 10+)
"""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import json


class DeviceCategory(Enum):
    """Categories of audio devices."""
    INSTRUMENT = "instrument"
    EQ = "eq"
    COMPRESSOR = "compressor"
    LIMITER = "limiter"
    SATURATOR = "saturator"
    REVERB = "reverb"
    DELAY = "delay"
    FILTER = "filter"
    MODULATION = "modulation"  # chorus, flanger, phaser
    UTILITY = "utility"  # gain, utility, spectrum
    SIDECHAIN = "sidechain"
    GATE = "gate"
    MULTIBAND = "multiband"
    MAXIMIZER = "maximizer"
    VST = "vst"
    AU = "au"
    MAX4LIVE = "max4live"
    UNKNOWN = "unknown"


# Mapping of Ableton device tags to categories
DEVICE_CATEGORY_MAP = {
    # Instruments
    "OriginalSimpler": DeviceCategory.INSTRUMENT,
    "MultiSampler": DeviceCategory.INSTRUMENT,
    "InstrumentGroupDevice": DeviceCategory.INSTRUMENT,
    "DrumGroupDevice": DeviceCategory.INSTRUMENT,
    "UltraAnalog": DeviceCategory.INSTRUMENT,
    "Collision": DeviceCategory.INSTRUMENT,
    "Operator": DeviceCategory.INSTRUMENT,
    "Wavetable": DeviceCategory.INSTRUMENT,
    "Drift": DeviceCategory.INSTRUMENT,

    # EQ
    "Eq8": DeviceCategory.EQ,
    "Eq3": DeviceCategory.EQ,
    "FilterEQ3": DeviceCategory.EQ,
    "ChannelEq": DeviceCategory.EQ,

    # Dynamics
    "Compressor2": DeviceCategory.COMPRESSOR,
    "GlueCompressor": DeviceCategory.COMPRESSOR,
    "Limiter": DeviceCategory.LIMITER,
    "Gate": DeviceCategory.GATE,
    "MultibandDynamics": DeviceCategory.MULTIBAND,

    # Saturation/Distortion
    "Saturator": DeviceCategory.SATURATOR,
    "Overdrive": DeviceCategory.SATURATOR,
    "Amp": DeviceCategory.SATURATOR,
    "Cabinet": DeviceCategory.SATURATOR,
    "Erosion": DeviceCategory.SATURATOR,
    "Redux": DeviceCategory.SATURATOR,
    "Vinyl": DeviceCategory.SATURATOR,
    "PedalBoard": DeviceCategory.SATURATOR,

    # Time-based
    "Reverb": DeviceCategory.REVERB,
    "Delay": DeviceCategory.DELAY,
    "FilterDelay": DeviceCategory.DELAY,
    "GrainDelay": DeviceCategory.DELAY,
    "PingPongDelay": DeviceCategory.DELAY,
    "Echo": DeviceCategory.DELAY,
    "Hybrid Reverb": DeviceCategory.REVERB,

    # Modulation
    "Chorus2": DeviceCategory.MODULATION,
    "Flanger": DeviceCategory.MODULATION,
    "Phaser": DeviceCategory.MODULATION,
    "FrequencyShifter": DeviceCategory.MODULATION,
    "RingMod": DeviceCategory.MODULATION,

    # Filters
    "AutoFilter": DeviceCategory.FILTER,
    "FilterDelay": DeviceCategory.FILTER,

    # Utility
    "StereoGain": DeviceCategory.UTILITY,
    "Utility": DeviceCategory.UTILITY,
    "Tuner": DeviceCategory.UTILITY,
    "Spectrum": DeviceCategory.UTILITY,
    "CrossDelay": DeviceCategory.UTILITY,

    # External plugins
    "PluginDevice": DeviceCategory.VST,
    "AuPluginDevice": DeviceCategory.AU,
    "MxDeviceAudioEffect": DeviceCategory.MAX4LIVE,
    "MxDeviceInstrument": DeviceCategory.MAX4LIVE,
}


@dataclass
class DeviceParameter:
    """A single device parameter with its value."""
    name: str
    value: Any
    display_value: Optional[str] = None  # Human-readable version
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@dataclass
class Device:
    """Represents a single device in the effect chain."""
    index: int  # Position in chain (0-based)
    device_type: str  # Raw Ableton tag (Eq8, Compressor2, etc.)
    category: DeviceCategory
    name: str  # User-assigned name or default
    is_enabled: bool
    parameters: Dict[str, DeviceParameter] = field(default_factory=dict)

    # Plugin-specific
    plugin_name: Optional[str] = None  # VST/AU name
    plugin_vendor: Optional[str] = None

    # Analysis flags
    issues: List[str] = field(default_factory=list)


@dataclass
class TrackDeviceChain:
    """Complete device chain for a single track."""
    track_name: str
    track_type: str  # midi, audio, return, master, group
    track_index: int
    volume_db: float
    pan: float  # -1 to 1
    is_muted: bool
    is_solo: bool
    devices: List[Device] = field(default_factory=list)

    # Analysis results
    issues: List[str] = field(default_factory=list)
    disabled_device_count: int = 0
    total_device_count: int = 0

    @property
    def enabled_devices(self) -> List[Device]:
        return [d for d in self.devices if d.is_enabled]

    @property
    def disabled_devices(self) -> List[Device]:
        return [d for d in self.devices if not d.is_enabled]


@dataclass
class ProjectDeviceAnalysis:
    """Complete device analysis for an Ableton project."""
    file_path: str
    ableton_version: str
    tempo: float
    tracks: List[TrackDeviceChain] = field(default_factory=list)

    # Aggregate stats
    total_devices: int = 0
    total_disabled_devices: int = 0
    total_issues: int = 0
    all_plugins: List[str] = field(default_factory=list)

    # Per-category counts
    device_category_counts: Dict[str, int] = field(default_factory=dict)


class DeviceChainAnalyzer:
    """
    Analyzes Ableton Live Set device chains for mixing issues.

    Extracts complete device information including parameters,
    identifies potential problems, and provides actionable feedback.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # Parameter extraction definitions for native devices
        self.parameter_maps = {
            "Compressor2": [
                "Threshold", "Ratio", "Attack", "Release", "Knee",
                "GainCompensation", "Model", "LookAhead", "DryWet"
            ],
            "GlueCompressor": [
                "Threshold", "Ratio", "Attack", "Release", "Makeup",
                "Range", "DryWet", "PeakClipIn"
            ],
            "Eq8": [
                "GlobalGain", "Scale", "Oversampling"
            ],
            "Limiter": [
                "Gain", "Ceiling", "Release", "LinkChannels"
            ],
            "Saturator": [
                "Drive", "Type", "Output", "DryWet", "PreDrive",
                "DriveBase", "ToneBase"
            ],
            "Gate": [
                "Threshold", "Return", "Attack", "Hold", "Release", "FlipMode"
            ],
            "Reverb": [
                "DecayTime", "RoomSize", "PreDelay", "DryWet",
                "StereoWidth", "HighShelf", "LowShelf"
            ],
            "Delay": [
                "DelayTime", "Feedback", "DryWet", "Filter"
            ],
            "AutoFilter": [
                "Frequency", "Resonance", "FilterType", "LfoAmount",
                "LfoRate", "Envelope", "DryWet"
            ],
            "Utility": [
                "Gain", "Width", "Mute", "PhaseInvertL", "PhaseInvertR",
                "ChannelMode", "MidSide", "BassMono", "BassFreq"
            ],
            "StereoGain": [
                "Gain", "Mute"
            ],
            "MultibandDynamics": [
                "BelowThreshold", "AboveThreshold", "BelowRatio", "AboveRatio",
                "Attack", "Release"
            ],
        }

    def analyze(self, als_path: str) -> ProjectDeviceAnalysis:
        """
        Analyze an Ableton Live Set file for device chain information.

        Args:
            als_path: Path to the .als file

        Returns:
            ProjectDeviceAnalysis with complete device chain data
        """
        path = Path(als_path)
        if not path.exists():
            raise FileNotFoundError(f"ALS file not found: {als_path}")

        # Read and decompress
        try:
            with gzip.open(als_path, 'rb') as f:
                xml_content = f.read()
        except gzip.BadGzipFile:
            with open(als_path, 'rb') as f:
                xml_content = f.read()

        root = ET.fromstring(xml_content)

        # Extract basic project info
        version = self._get_version(root)
        tempo = self._get_tempo(root)

        # Analyze all tracks
        tracks = []
        all_plugins = set()
        total_devices = 0
        total_disabled = 0
        category_counts: Dict[str, int] = {}

        # Process each track type
        track_index = 0

        for track_elem in root.findall(".//MidiTrack"):
            chain = self._analyze_track(track_elem, track_index, "midi")
            if chain:
                tracks.append(chain)
                track_index += 1
                total_devices += chain.total_device_count
                total_disabled += chain.disabled_device_count
                for device in chain.devices:
                    if device.plugin_name:
                        all_plugins.add(device.plugin_name)
                    cat_name = device.category.value
                    category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

        for track_elem in root.findall(".//AudioTrack"):
            chain = self._analyze_track(track_elem, track_index, "audio")
            if chain:
                tracks.append(chain)
                track_index += 1
                total_devices += chain.total_device_count
                total_disabled += chain.disabled_device_count
                for device in chain.devices:
                    if device.plugin_name:
                        all_plugins.add(device.plugin_name)
                    cat_name = device.category.value
                    category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

        for i, track_elem in enumerate(root.findall(".//ReturnTrack")):
            chain = self._analyze_track(track_elem, 100 + i, "return")
            if chain:
                tracks.append(chain)
                total_devices += chain.total_device_count
                total_disabled += chain.disabled_device_count

        # Master track
        master_elem = root.find(".//MasterTrack")
        if master_elem is not None:
            chain = self._analyze_track(master_elem, 999, "master")
            if chain:
                tracks.append(chain)
                total_devices += chain.total_device_count
                total_disabled += chain.disabled_device_count

        # Count total issues
        total_issues = sum(len(t.issues) for t in tracks)
        total_issues += sum(len(d.issues) for t in tracks for d in t.devices)

        return ProjectDeviceAnalysis(
            file_path=str(path.absolute()),
            ableton_version=version,
            tempo=tempo,
            tracks=tracks,
            total_devices=total_devices,
            total_disabled_devices=total_disabled,
            total_issues=total_issues,
            all_plugins=sorted(list(all_plugins)),
            device_category_counts=category_counts
        )

    def _analyze_track(self, track_elem: ET.Element, index: int,
                       track_type: str) -> Optional[TrackDeviceChain]:
        """Analyze a single track's device chain."""
        try:
            # Get track name
            name = self._get_track_name(track_elem, f"{track_type.title()} {index + 1}")

            # Get volume/pan
            volume_db, pan = self._get_volume_pan(track_elem)

            # Get mute/solo
            is_muted, is_solo = self._get_mute_solo(track_elem)

            # Extract devices
            devices = self._extract_devices(track_elem)

            chain = TrackDeviceChain(
                track_name=name,
                track_type=track_type,
                track_index=index,
                volume_db=volume_db,
                pan=pan,
                is_muted=is_muted,
                is_solo=is_solo,
                devices=devices,
                total_device_count=len(devices),
                disabled_device_count=len([d for d in devices if not d.is_enabled])
            )

            return chain

        except Exception as e:
            if self.verbose:
                print(f"Error analyzing track: {e}")
            return None

    def _extract_devices(self, track_elem: ET.Element) -> List[Device]:
        """Extract all devices from a track's device chain."""
        devices = []

        # Try multiple possible device chain locations
        for device_path in [
            ".//DeviceChain/DeviceChain/Devices",
            ".//DeviceChain/Devices"
        ]:
            device_chain = track_elem.find(device_path)
            if device_chain is not None and len(device_chain) > 0:
                for i, device_elem in enumerate(device_chain):
                    device = self._parse_device(device_elem, i)
                    if device:
                        devices.append(device)
                break

        return devices

    def _parse_device(self, device_elem: ET.Element, index: int) -> Optional[Device]:
        """Parse a single device element."""
        tag = device_elem.tag

        # Skip container elements
        if tag in ['Devices']:
            return None

        # Get category
        category = DEVICE_CATEGORY_MAP.get(tag, DeviceCategory.UNKNOWN)

        # Get user name
        user_name_elem = device_elem.find(".//UserName")
        user_name = ""
        if user_name_elem is not None:
            user_name = user_name_elem.attrib.get("Value", "")

        # Get ON/OFF state
        on_elem = device_elem.find("On/Manual")
        is_enabled = True
        if on_elem is not None:
            is_enabled = on_elem.attrib.get("Value", "true").lower() == "true"

        # Check for plugin info
        plugin_name = None
        plugin_vendor = None

        # VST plugin
        vst_name_elem = device_elem.find(".//PluginDesc/VstPluginInfo/PlugName")
        if vst_name_elem is not None:
            plugin_name = vst_name_elem.attrib.get("Value", "")
            category = DeviceCategory.VST

        vst_vendor_elem = device_elem.find(".//PluginDesc/VstPluginInfo/Manufacturer")
        if vst_vendor_elem is not None:
            plugin_vendor = vst_vendor_elem.attrib.get("Value", "")

        # AU plugin
        au_name_elem = device_elem.find(".//PluginDesc/AuPluginInfo/Name")
        if au_name_elem is not None:
            plugin_name = au_name_elem.attrib.get("Value", "")
            category = DeviceCategory.AU

        # Determine display name
        if plugin_name:
            name = plugin_name
        elif user_name:
            name = user_name
        else:
            name = tag

        # Extract parameters
        parameters = self._extract_parameters(device_elem, tag)

        return Device(
            index=index,
            device_type=tag,
            category=category,
            name=name,
            is_enabled=is_enabled,
            parameters=parameters,
            plugin_name=plugin_name,
            plugin_vendor=plugin_vendor
        )

    def _extract_parameters(self, device_elem: ET.Element,
                           device_type: str) -> Dict[str, DeviceParameter]:
        """Extract parameters for a device."""
        parameters = {}

        # Get parameter names to look for
        param_names = self.parameter_maps.get(device_type, [])

        for param_name in param_names:
            # Try to find the parameter
            elem = device_elem.find(f".//{param_name}/Manual")
            if elem is not None and "Value" in elem.attrib:
                try:
                    raw_value = elem.attrib["Value"]
                    # Try to convert to number
                    try:
                        if "." in raw_value:
                            value = float(raw_value)
                        else:
                            value = int(raw_value) if raw_value.lstrip('-').isdigit() else raw_value
                    except (ValueError, AttributeError):
                        value = raw_value

                    parameters[param_name] = DeviceParameter(
                        name=param_name,
                        value=value
                    )
                except Exception:
                    pass

        # For EQ8, also extract band information
        if device_type == "Eq8":
            self._extract_eq8_bands(device_elem, parameters)

        return parameters

    def _extract_eq8_bands(self, device_elem: ET.Element,
                          parameters: Dict[str, DeviceParameter]) -> None:
        """Extract EQ8 band settings."""
        bands = device_elem.find(".//Bands")
        if bands is None:
            return

        for i, band_elem in enumerate(bands):
            band_data = {}

            # Get band enabled state
            enabled_elem = band_elem.find("ParameterA/Manual")
            if enabled_elem is not None:
                band_data["enabled"] = enabled_elem.attrib.get("Value", "true") == "true"

            # Get frequency
            freq_elem = band_elem.find("ParameterB/Manual")
            if freq_elem is not None:
                try:
                    band_data["freq"] = float(freq_elem.attrib.get("Value", 0))
                except ValueError:
                    pass

            # Get gain
            gain_elem = band_elem.find("Gain/Manual")
            if gain_elem is not None:
                try:
                    band_data["gain"] = float(gain_elem.attrib.get("Value", 0))
                except ValueError:
                    pass

            # Get Q
            q_elem = band_elem.find("Q/Manual")
            if q_elem is not None:
                try:
                    band_data["q"] = float(q_elem.attrib.get("Value", 0.71))
                except ValueError:
                    pass

            if band_data:
                parameters[f"Band{i+1}"] = DeviceParameter(
                    name=f"Band{i+1}",
                    value=band_data
                )

    def _get_track_name(self, track_elem: ET.Element, default: str) -> str:
        """Extract track name."""
        name_elem = track_elem.find(".//Name/EffectiveName")
        if name_elem is not None and "Value" in name_elem.attrib:
            return name_elem.attrib["Value"]

        user_name = track_elem.find(".//Name/UserName")
        if user_name is not None and "Value" in user_name.attrib:
            name = user_name.attrib["Value"]
            if name:
                return name

        return default

    def _get_volume_pan(self, track_elem: ET.Element) -> Tuple[float, float]:
        """Extract volume and pan."""
        volume_db = 0.0
        pan = 0.0

        vol_elem = track_elem.find(".//DeviceChain/Mixer/Volume/Manual")
        if vol_elem is not None and "Value" in vol_elem.attrib:
            try:
                vol_linear = float(vol_elem.attrib["Value"])
                if vol_linear > 0:
                    # Ableton uses 0-1 scale approximately
                    if vol_linear >= 0.85:
                        volume_db = 20 * (vol_linear - 0.85) / 0.15
                    else:
                        volume_db = -70 * (1 - vol_linear / 0.85)
                else:
                    volume_db = -float('inf')
            except ValueError:
                pass

        pan_elem = track_elem.find(".//DeviceChain/Mixer/Pan/Manual")
        if pan_elem is not None and "Value" in pan_elem.attrib:
            try:
                pan = float(pan_elem.attrib["Value"])
            except ValueError:
                pass

        return (round(volume_db, 1), round(pan, 2))

    def _get_mute_solo(self, track_elem: ET.Element) -> Tuple[bool, bool]:
        """Extract mute and solo state."""
        is_muted = False
        is_solo = False

        mute_elem = track_elem.find(".//DeviceChain/Mixer/Speaker/Manual")
        if mute_elem is not None and "Value" in mute_elem.attrib:
            is_muted = mute_elem.attrib["Value"].lower() == "false"

        solo_elem = track_elem.find(".//DeviceChain/Mixer/Solo/Manual")
        if solo_elem is not None and "Value" in solo_elem.attrib:
            is_solo = solo_elem.attrib["Value"].lower() == "true"

        return (is_muted, is_solo)

    def _get_version(self, root: ET.Element) -> str:
        """Extract Ableton version."""
        ableton_elem = root.find(".//Ableton")
        if ableton_elem is not None:
            major = ableton_elem.get("MajorVersion", "")
            minor = ableton_elem.get("MinorVersion", "")
            if major or minor:
                return f"{major}.{minor}"
        return "Unknown"

    def _get_tempo(self, root: ET.Element) -> float:
        """Extract project tempo."""
        tempo_paths = [
            ".//Tempo/Manual",
            ".//MasterTrack/DeviceChain/Mixer/Tempo/Manual",
        ]
        for path in tempo_paths:
            elem = root.find(path)
            if elem is not None and "Value" in elem.attrib:
                try:
                    return float(elem.attrib["Value"])
                except ValueError:
                    continue
        return 120.0

    def to_summary(self, analysis: ProjectDeviceAnalysis) -> str:
        """Generate a human-readable summary of the analysis."""
        lines = []
        lines.append(f"=" * 60)
        lines.append(f"PROJECT DEVICE ANALYSIS: {Path(analysis.file_path).name}")
        lines.append(f"=" * 60)
        lines.append(f"Ableton Version: {analysis.ableton_version}")
        lines.append(f"Tempo: {analysis.tempo} BPM")
        lines.append(f"Total Devices: {analysis.total_devices}")
        lines.append(f"Disabled Devices: {analysis.total_disabled_devices}")
        lines.append(f"Tracks: {len(analysis.tracks)}")
        lines.append("")

        for track in analysis.tracks:
            if not track.devices:
                continue

            mute_str = " [MUTED]" if track.is_muted else ""
            solo_str = " [SOLO]" if track.is_solo else ""
            lines.append(f"\n--- {track.track_name} ({track.track_type}){mute_str}{solo_str} ---")
            lines.append(f"    Volume: {track.volume_db:+.1f} dB | Pan: {track.pan:+.2f}")

            for device in track.devices:
                status = "ON " if device.is_enabled else "OFF"
                plugin_str = f" [{device.plugin_name}]" if device.plugin_name else ""
                lines.append(f"  {device.index+1}. [{status}] {device.name} ({device.category.value}){plugin_str}")

                # Show key parameters
                if device.parameters:
                    param_strs = []
                    for name, param in list(device.parameters.items())[:5]:
                        if name.startswith("Band"):
                            continue  # Skip EQ band details in summary
                        if isinstance(param.value, float):
                            param_strs.append(f"{name}={param.value:.2f}")
                        else:
                            param_strs.append(f"{name}={param.value}")
                    if param_strs:
                        lines.append(f"      {', '.join(param_strs)}")

        return "\n".join(lines)

    def to_json(self, analysis: ProjectDeviceAnalysis) -> str:
        """Convert analysis to JSON."""
        def serialize(obj):
            if hasattr(obj, '__dict__'):
                d = {}
                for k, v in obj.__dict__.items():
                    if isinstance(v, Enum):
                        d[k] = v.value
                    elif isinstance(v, list):
                        d[k] = [serialize(item) for item in v]
                    elif isinstance(v, dict):
                        d[k] = {key: serialize(val) for key, val in v.items()}
                    else:
                        d[k] = v
                return d
            return obj

        return json.dumps(serialize(analysis), indent=2)


def analyze_als_devices(als_path: str, verbose: bool = False) -> ProjectDeviceAnalysis:
    """Quick function to analyze device chains in an ALS file."""
    analyzer = DeviceChainAnalyzer(verbose=verbose)
    return analyzer.analyze(als_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        analysis = analyze_als_devices(sys.argv[1], verbose=True)
        analyzer = DeviceChainAnalyzer()
        print(analyzer.to_summary(analysis))
