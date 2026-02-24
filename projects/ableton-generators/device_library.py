"""
Ableton Device Library

Extract, store, and insert devices (instruments/effects) into Ableton projects.

Capabilities:
- Extract devices from existing .als files
- Store device templates in a library
- Insert devices into generated tracks
- Support for: Simpler, Operator, VST plugins, Effects

Usage:
    # Extract devices from a project
    python device_library.py extract project.als

    # List available devices
    python device_library.py list

    # Show device details
    python device_library.py show "My Synth"
"""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import json
import copy
import re


@dataclass
class DeviceTemplate:
    """A stored device configuration."""
    name: str
    device_type: str  # OriginalSimpler, Operator, PluginDevice, etc.
    category: str     # instrument, effect, utility
    xml_element: str  # Serialized XML
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'device_type': self.device_type,
            'category': self.category,
            'xml': self.xml_element,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DeviceTemplate':
        return cls(
            name=data['name'],
            device_type=data['device_type'],
            category=data['category'],
            xml_element=data['xml'],
            metadata=data.get('metadata', {})
        )


# Device type categorization
INSTRUMENT_TYPES = [
    'OriginalSimpler', 'MultiSampler', 'Operator', 'Wavetable',
    'Drift', 'Analog', 'Collision', 'Electric', 'Tension',
    'InstrumentVector', 'DrumGroupDevice', 'InstrumentGroupDevice',
    'PluginDevice'  # VST/AU instruments
]

EFFECT_TYPES = [
    'Eq8', 'Compressor2', 'GlueCompressor', 'MultibandDynamics',
    'Saturator', 'Overdrive', 'Redux2', 'Erosion',
    'Reverb', 'Delay', 'FilterDelay', 'GrainDelay', 'Chorus2',
    'Flanger', 'Phaser', 'FrequencyShifter', 'RingMod',
    'AutoFilter', 'AutoPan', 'Gate', 'Limiter',
    'Vocoder', 'Resonators', 'Corpus', 'Amp',
    'Cabinet', 'Pedal', 'DrumBuss', 'Echo', 'PingPongDelay'
]

UTILITY_TYPES = [
    'AudioEffectGroupDevice', 'MidiEffectGroupDevice',
    'InstrumentImpulse', 'Tuner', 'Spectrum', 'Utility'
]


class DeviceLibrary:
    """Manages a library of device templates."""

    def __init__(self, library_path: str = None):
        self.library_path = Path(library_path) if library_path else \
            Path(__file__).parent / "device_templates"
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.devices: Dict[str, DeviceTemplate] = {}
        self._load_library()

    def _load_library(self):
        """Load all devices from library."""
        index_file = self.library_path / "index.json"
        if index_file.exists():
            with open(index_file, 'r') as f:
                index = json.load(f)
                for name, data in index.items():
                    self.devices[name] = DeviceTemplate.from_dict(data)

    def _save_library(self):
        """Save library index."""
        index_file = self.library_path / "index.json"
        index = {name: dev.to_dict() for name, dev in self.devices.items()}
        with open(index_file, 'w') as f:
            json.dump(index, f, indent=2)

    def extract_from_project(self, als_path: str) -> List[DeviceTemplate]:
        """Extract all devices from an Ableton project.

        Args:
            als_path: Path to .als file

        Returns:
            List of extracted DeviceTemplates
        """
        with gzip.open(als_path, 'rb') as f:
            data = f.read().decode('utf-8')

        root = ET.fromstring(data)
        extracted = []

        # Find all device chains
        for devices_elem in root.findall('.//Devices'):
            for device in devices_elem:
                template = self._extract_device(device)
                if template:
                    extracted.append(template)

        return extracted

    def _extract_device(self, device_elem: ET.Element) -> Optional[DeviceTemplate]:
        """Extract a single device as a template."""
        device_type = device_elem.tag

        # Skip non-device elements
        if device_type in ['Devices']:
            return None

        # Categorize
        if device_type in INSTRUMENT_TYPES:
            category = 'instrument'
        elif device_type in EFFECT_TYPES:
            category = 'effect'
        else:
            category = 'utility'

        # Get device name
        user_name = device_elem.find('.//UserName')
        name = user_name.get('Value') if user_name is not None else None

        # For plugins, get plugin name
        if device_type == 'PluginDevice':
            plugin_name = device_elem.find('.//PluginDesc//VstPluginInfo/PlugName')
            if plugin_name is not None:
                name = plugin_name.get('Value')
            else:
                au_name = device_elem.find('.//PluginDesc//AuPluginInfo/Name')
                if au_name is not None:
                    name = au_name.get('Value')

        if not name:
            name = device_type

        # Extract metadata
        metadata = {
            'device_type': device_type,
        }

        # For Simpler, get sample path
        if device_type == 'OriginalSimpler':
            sample_ref = device_elem.find('.//SampleRef//FileRef/Path')
            if sample_ref is not None:
                metadata['sample_path'] = sample_ref.get('Value')

        # Serialize XML
        xml_str = ET.tostring(device_elem, encoding='unicode')

        return DeviceTemplate(
            name=name,
            device_type=device_type,
            category=category,
            xml_element=xml_str,
            metadata=metadata
        )

    def add_device(self, template: DeviceTemplate, overwrite: bool = False):
        """Add a device to the library."""
        if template.name in self.devices and not overwrite:
            # Generate unique name
            base_name = template.name
            i = 1
            while f"{base_name}_{i}" in self.devices:
                i += 1
            template.name = f"{base_name}_{i}"

        self.devices[template.name] = template
        self._save_library()

    def get_device(self, name: str) -> Optional[DeviceTemplate]:
        """Get a device by name."""
        return self.devices.get(name)

    def list_devices(self, category: str = None) -> List[str]:
        """List all devices, optionally filtered by category."""
        devices = self.devices.values()
        if category:
            devices = [d for d in devices if d.category == category]
        return [d.name for d in devices]

    def get_device_xml(self, name: str, new_id: int = None) -> Optional[ET.Element]:
        """Get device XML element, optionally with new ID."""
        template = self.get_device(name)
        if not template:
            return None

        elem = ET.fromstring(template.xml_element)

        # Convert RelativePath format from Live 9/10 to Live 11 format
        self._convert_relative_path_format(elem)

        # Update IDs if specified
        if new_id is not None:
            self._update_ids(elem, new_id)

        return elem

    def _update_ids(self, elem: ET.Element, base_id: int):
        """Update only the root device ID, not internal IDs.

        Ableton devices have many internal IDs (RelativePathElement, WarpMarker, etc.)
        that should NOT be changed. Only the root device ID needs to be unique.
        """
        # Only update the root element's ID
        if 'Id' in elem.attrib:
            elem.set('Id', str(base_id))
        return base_id + 1

    def _convert_relative_path_format(self, elem: ET.Element):
        """
        Convert Live 9/10 RelativePathElement format to Live 11 Value format.

        Before: <RelativePath><RelativePathElement Dir="Devices"/></RelativePath>
        After:  <RelativePath Value="Devices" />
        """
        for rel_path in elem.iter('RelativePath'):
            children = list(rel_path)
            if children and children[0].tag == 'RelativePathElement':
                # Build path from child elements
                path_parts = []
                for child in children:
                    if child.tag == 'RelativePathElement':
                        dir_val = child.get('Dir', '')
                        if dir_val:
                            path_parts.append(dir_val)
                # Clear children and set Value attribute
                rel_path.clear()
                rel_path.set('Value', '/'.join(path_parts))


class DeviceInserter:
    """Insert devices into Ableton projects."""

    def __init__(self, library: DeviceLibrary = None):
        self.library = library or DeviceLibrary()
        self.id_counter = 100000  # Start high to avoid conflicts

    def _get_next_id(self) -> int:
        self.id_counter += 1
        return self.id_counter

    def insert_device_into_track(self,
                                  track_elem: ET.Element,
                                  device_name: str) -> bool:
        """Insert a device from library into a track.

        Args:
            track_elem: Track XML element
            device_name: Name of device in library

        Returns:
            True if successful
        """
        device_xml = self.library.get_device_xml(device_name, self._get_next_id())
        if device_xml is None:
            return False

        # Find Devices container in track
        devices = track_elem.find('.//DeviceChain/DeviceChain/Devices')
        if devices is None:
            # Try alternative path
            devices = track_elem.find('.//DeviceChain/Devices')

        if devices is None:
            # Create Devices container if missing
            device_chain = track_elem.find('.//DeviceChain/DeviceChain')
            if device_chain is None:
                device_chain = track_elem.find('.//DeviceChain')
            if device_chain is not None:
                devices = ET.SubElement(device_chain, 'Devices')

        if devices is not None:
            devices.append(device_xml)
            return True

        return False

    def create_instrument_track_with_device(self,
                                             device_name: str,
                                             track_name: str = None) -> Optional[ET.Element]:
        """Create a new MIDI track with a device.

        Note: This creates a minimal track structure. For full functionality,
        use the template-based approach from create_trance_template.py
        """
        # This would need a full track template
        # For now, devices should be inserted into existing tracks
        raise NotImplementedError(
            "Use create_trance_template.py to create tracks, "
            "then insert devices with insert_device_into_track()"
        )


# =============================================================================
# CORE LIBRARY SAMPLES
# =============================================================================

@dataclass
class CoreLibrarySample:
    """A sample from Ableton's Core Library."""
    name: str           # Filename without extension
    extension: str      # File extension (wav, aif)
    path_parts: List[str]  # Path within Core Library (e.g., ["Samples", "Drums", "Kick"])


# Default samples for each track type
CORE_LIBRARY_SAMPLES = {
    "kick": CoreLibrarySample("Kick-606", "wav", ["Samples", "Drums", "Kick"]),
    "snare": CoreLibrarySample("Snare-Vinyl01", "wav", ["Samples", "Drums", "Snare"]),
    "clap": CoreLibrarySample("Clap-808", "wav", ["Samples", "Drums", "Clap"]),
    "hats": CoreLibrarySample("Hihat-Closed-808", "wav", ["Samples", "Drums", "Hihat"]),
    "hat_open": CoreLibrarySample("Hihat-Open-808", "wav", ["Samples", "Drums", "Hihat"]),
    "perc": CoreLibrarySample("Conga-Muted", "wav", ["Samples", "Drums", "Percussion"]),
    "rim": CoreLibrarySample("Rim-808", "wav", ["Samples", "Drums", "Rim"]),
}

# Core Library path hints for different Ableton versions
CORE_LIBRARY_PATHS = {
    "win_11": ["ProgramData", "Ableton", "Live 11 Suite", "Resources", "Core Library"],
    "win_10": ["ProgramData", "Ableton", "Live 10 Suite", "Resources", "Core Library"],
    "mac_11": ["Applications", "Ableton Live 11 Suite.app", "Contents", "App-Resources", "Core Library"],
}


class SimplerBuilder:
    """Builds Simpler device XML with proper structure."""

    def __init__(self, start_id: int = 50000):
        self.next_id = start_id

    def _get_id(self) -> int:
        val = self.next_id
        self.next_id += 1
        return val

    def _create_file_ref(self, sample: CoreLibrarySample) -> ET.Element:
        """Create FileRef element for a Core Library sample."""
        file_ref = ET.Element("FileRef")

        ET.SubElement(file_ref, "HasRelativePath", {"Value": "true"})
        ET.SubElement(file_ref, "RelativePathType", {"Value": "3"})  # 3 = Core Library

        # Relative path within Core Library
        rel_path = ET.SubElement(file_ref, "RelativePath")
        for part in sample.path_parts:
            ET.SubElement(rel_path, "RelativePathElement", {"Dir": part})

        ET.SubElement(file_ref, "Name", {"Value": f"{sample.name}.{sample.extension}"})
        ET.SubElement(file_ref, "Type", {"Value": "1"})
        ET.SubElement(file_ref, "Data")
        ET.SubElement(file_ref, "RefersToFolder", {"Value": "false"})

        # Search hint with full path
        search_hint = ET.SubElement(file_ref, "SearchHint")
        path_hint = ET.SubElement(search_hint, "PathHint")
        for part in CORE_LIBRARY_PATHS["win_11"]:
            ET.SubElement(path_hint, "RelativePathElement", {"Dir": part})
        for part in sample.path_parts:
            ET.SubElement(path_hint, "RelativePathElement", {"Dir": part})

        ET.SubElement(search_hint, "FileSize", {"Value": "0"})
        ET.SubElement(search_hint, "Crc", {"Value": "0"})
        ET.SubElement(search_hint, "MaxCrcSize", {"Value": "0"})
        ET.SubElement(search_hint, "HasExtendedInfo", {"Value": "false"})

        ET.SubElement(file_ref, "LivePackName", {"Value": "Core Library"})
        ET.SubElement(file_ref, "LivePackId", {"Value": "www.ableton.com/0"})

        return file_ref

    def build(self, name: str, sample: CoreLibrarySample) -> ET.Element:
        """
        Build a complete Simpler device element.

        Args:
            name: Device display name
            sample: Core Library sample to load

        Returns:
            OriginalSimpler XML element
        """
        simpler = ET.Element("OriginalSimpler", {"Id": str(self._get_id())})

        # Basic metadata
        ET.SubElement(simpler, "LomId", {"Value": "0"})
        ET.SubElement(simpler, "LomIdView", {"Value": "0"})
        ET.SubElement(simpler, "IsExpanded", {"Value": "true"})

        # On/Off switch with automation
        on_elem = ET.SubElement(simpler, "On")
        ET.SubElement(on_elem, "LomId", {"Value": "0"})
        ET.SubElement(on_elem, "Manual", {"Value": "true"})
        auto_target = ET.SubElement(on_elem, "AutomationTarget", {"Id": str(self._get_id())})
        ET.SubElement(auto_target, "LockEnvelope", {"Value": "0"})
        thresholds = ET.SubElement(on_elem, "MidiCCOnOffThresholds")
        ET.SubElement(thresholds, "Min", {"Value": "64"})
        ET.SubElement(thresholds, "Max", {"Value": "127"})

        ET.SubElement(simpler, "ParametersListWrapper", {"LomId": "0"})
        ET.SubElement(simpler, "LastSelectedTimeableIndex", {"Value": "0"})
        ET.SubElement(simpler, "LastSelectedClipEnvelopeIndex", {"Value": "0"})

        # Empty preset ref
        preset_ref = ET.SubElement(simpler, "LastPresetRef")
        ET.SubElement(preset_ref, "Value")

        ET.SubElement(simpler, "LockedScripts")
        ET.SubElement(simpler, "IsFolded", {"Value": "false"})
        ET.SubElement(simpler, "ShouldShowPresetName", {"Value": "true"})
        ET.SubElement(simpler, "UserName", {"Value": name})
        ET.SubElement(simpler, "Annotation", {"Value": ""})

        source_ctx = ET.SubElement(simpler, "SourceContext")
        ET.SubElement(source_ctx, "Value")

        ET.SubElement(simpler, "OverwriteProtectionNumber", {"Value": "2560"})

        # Player section with sample
        player = ET.SubElement(simpler, "Player")
        multi_map = ET.SubElement(player, "MultiSampleMap")
        sample_parts = ET.SubElement(multi_map, "SampleParts")

        # Sample part
        part = ET.SubElement(sample_parts, "MultiSamplePart", {
            "Id": str(self._get_id()),
            "HasImportedSlicePoints": "false",
            "NeedsAnalysisData": "true"
        })

        ET.SubElement(part, "LomId", {"Value": "0"})
        ET.SubElement(part, "Name", {"Value": sample.name})
        ET.SubElement(part, "Selection", {"Value": "true"})
        ET.SubElement(part, "IsActive", {"Value": "true"})
        ET.SubElement(part, "Solo", {"Value": "false"})

        # Full key range
        key_range = ET.SubElement(part, "KeyRange")
        ET.SubElement(key_range, "Min", {"Value": "0"})
        ET.SubElement(key_range, "Max", {"Value": "127"})
        ET.SubElement(key_range, "CrossfadeMin", {"Value": "0"})
        ET.SubElement(key_range, "CrossfadeMax", {"Value": "127"})

        # Full velocity range
        vel_range = ET.SubElement(part, "VelocityRange")
        ET.SubElement(vel_range, "Min", {"Value": "1"})
        ET.SubElement(vel_range, "Max", {"Value": "127"})
        ET.SubElement(vel_range, "CrossfadeMin", {"Value": "1"})
        ET.SubElement(vel_range, "CrossfadeMax", {"Value": "127"})

        # Selector range
        sel_range = ET.SubElement(part, "SelectorRange")
        ET.SubElement(sel_range, "Min", {"Value": "0"})
        ET.SubElement(sel_range, "Max", {"Value": "127"})
        ET.SubElement(sel_range, "CrossfadeMin", {"Value": "0"})
        ET.SubElement(sel_range, "CrossfadeMax", {"Value": "127"})

        ET.SubElement(part, "RootKey", {"Value": "60"})
        ET.SubElement(part, "Detune", {"Value": "0"})
        ET.SubElement(part, "TuneScale", {"Value": "100"})
        ET.SubElement(part, "Panorama", {"Value": "0"})
        ET.SubElement(part, "Volume", {"Value": "1"})
        ET.SubElement(part, "Link", {"Value": "false"})

        # Sample reference
        sample_ref = ET.SubElement(part, "SampleRef")
        sample_ref.append(self._create_file_ref(sample))
        ET.SubElement(sample_ref, "LastModDate", {"Value": "0"})
        ET.SubElement(sample_ref, "SourceContext")
        ET.SubElement(sample_ref, "SampleUsageHint", {"Value": "0"})
        ET.SubElement(sample_ref, "DefaultDuration", {"Value": "0"})
        ET.SubElement(sample_ref, "DefaultSampleRate", {"Value": "44100"})

        # Empty slice points
        slice_points = ET.SubElement(part, "SlicePoints")
        ET.SubElement(slice_points, "Value")

        ET.SubElement(part, "SampleWarp")
        ET.SubElement(part, "SlicingThreshold", {"Value": "70"})
        ET.SubElement(part, "SlicingBeatGrid", {"Value": "4"})

        ET.SubElement(multi_map, "TriggeredSampleIndex", {"Value": "-1"})

        return simpler


def add_simpler_to_track(track: ET.Element, name: str, sample: CoreLibrarySample,
                         start_id: int = 50000) -> int:
    """
    Add a Simpler device to a MIDI track.

    Args:
        track: MidiTrack XML element
        name: Device display name
        sample: Core Library sample
        start_id: Starting ID for new elements

    Returns:
        Next available ID
    """
    builder = SimplerBuilder(start_id)
    simpler = builder.build(name, sample)

    # Find the Devices container
    # Path varies by template:
    #   - Simple: DeviceChain > DeviceChain > Devices
    #   - Full: DeviceChain > DeviceChain > MidiToAudioDeviceChain > Devices
    device_chain = track.find("DeviceChain")
    if device_chain is None:
        return builder.next_id

    inner_chain = device_chain.find("DeviceChain")
    if inner_chain is None:
        return builder.next_id

    # Try the simple path first (DeviceChain > DeviceChain > Devices)
    devices = inner_chain.find("Devices")

    # If not found, try MidiToAudioDeviceChain path
    if devices is None:
        midi_to_audio = inner_chain.find("MidiToAudioDeviceChain")
        if midi_to_audio is not None:
            devices = midi_to_audio.find("Devices")
            if devices is None:
                devices = ET.SubElement(midi_to_audio, "Devices")

    # If still not found, create Devices under inner_chain
    if devices is None:
        devices = ET.SubElement(inner_chain, "Devices")

    devices.append(simpler)
    return builder.next_id


def add_devices_to_template(root: ET.Element, start_id: int = 50000,
                            add_synths: bool = False) -> int:
    """
    Add default devices to template tracks based on track names.

    Uses pre-extracted devices from the library instead of building from scratch.

    Args:
        root: Ableton Live Set root element
        start_id: Starting ID for new elements
        add_synths: If True, also add synths for melodic tracks

    Returns:
        Next available ID
    """
    # Mapping of track names to library device names (use real extracted devices)
    track_to_library_device = {
        # Drums - use extracted 909 kit devices
        "kick": "Kick 909",
        "clap": "Clap 909",
        "snare": "Snare 909",
        "hats": "Hihat Closed 909",
        # Melodic - only if add_synths is True
        "bass": "Operator",
        "chords": "Elegic Pad",
        "arp": "Plucked",
        "lead": "Operator",
    }

    # Drums are always added, melodic only with add_synths
    drum_tracks = {"kick", "clap", "snare", "hats"}

    tracks_elem = root.find(".//Tracks")
    if tracks_elem is None:
        return start_id

    current_id = start_id
    library = DeviceLibrary()

    for track in tracks_elem.findall("MidiTrack"):
        name_elem = track.find(".//Name/EffectiveName")
        if name_elem is None:
            name_elem = track.find(".//Name/UserName")
        if name_elem is None:
            continue

        track_name = name_elem.get("Value", "").lower()

        # Check if we should add a device for this track
        if track_name not in track_to_library_device:
            continue

        # Skip melodic tracks unless add_synths is True
        if track_name not in drum_tracks and not add_synths:
            continue

        device_name = track_to_library_device[track_name]

        # Check if device exists in library
        if library.get_device(device_name) is None:
            print(f"  ! Device not found in library: {device_name}")
            continue

        prev_id = current_id
        current_id = add_library_device_to_track(
            track, library, device_name, current_id
        )
        if current_id > prev_id:
            print(f"  + Added {device_name} to {track_name}")

    return current_id


def add_library_device_to_track(track: ET.Element, library: 'DeviceLibrary',
                                 device_name: str, start_id: int) -> int:
    """
    Add a device from the library to a track.

    Args:
        track: MidiTrack XML element
        library: DeviceLibrary instance
        device_name: Name of device in library
        start_id: Starting ID for new elements

    Returns:
        Next available ID
    """
    device_xml = library.get_device_xml(device_name, start_id)
    if device_xml is None:
        return start_id

    # Count IDs in the device to calculate next_id
    id_count = sum(1 for e in device_xml.iter() if 'Id' in e.attrib)
    next_id = start_id + id_count + 10

    # Find the Devices container
    device_chain = track.find("DeviceChain")
    if device_chain is None:
        return start_id

    inner_chain = device_chain.find("DeviceChain")
    if inner_chain is None:
        return start_id

    # Try simple path first
    devices = inner_chain.find("Devices")
    if devices is None:
        midi_to_audio = inner_chain.find("MidiToAudioDeviceChain")
        if midi_to_audio is not None:
            devices = midi_to_audio.find("Devices")
            if devices is None:
                devices = ET.SubElement(midi_to_audio, "Devices")
    if devices is None:
        devices = ET.SubElement(inner_chain, "Devices")

    devices.append(device_xml)
    return next_id


# =============================================================================
# PRESET DEVICES (Built-in defaults)
# =============================================================================

def create_default_simpler(sample_path: str = None) -> str:
    """Create a basic Simpler device XML (legacy function)."""
    # Minimal Simpler structure
    xml = f'''<OriginalSimpler Id="0">
        <LomId Value="0" />
        <LomIdView Value="0" />
        <IsExpanded Value="true" />
        <On>
            <LomId Value="0" />
            <Manual Value="true" />
            <AutomationTarget Id="1">
                <LockEnvelope Value="0" />
            </AutomationTarget>
        </On>
        <ModulationSourceCount Value="0" />
        <ParametersListWrapper LomId="0" />
        <Pointee Id="2" />
        <LastSelectedTimeableIndex Value="0" />
        <LastSelectedClipEnvelopeIndex Value="0" />
        <LastPresetRef>
            <Value>
                <AbletonDefaultPresetRef Id="1">
                    <FileRef>
                        <RelativePathType Value="0" />
                        <RelativePath Value="" />
                        <Path Value="" />
                        <Type Value="1" />
                    </FileRef>
                    <DeviceId Name="OriginalSimpler" />
                </AbletonDefaultPresetRef>
            </Value>
        </LastPresetRef>
        <LockedScripts />
        <IsFolded Value="false" />
        <ShouldShowPresetName Value="true" />
        <UserName Value="" />
        <Annotation Value="" />
        <Player>
            <MultiSampleMap>
                <SampleParts />
            </MultiSampleMap>
        </Player>
    </OriginalSimpler>'''
    return xml


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Ableton Device Library')
    subparsers = parser.add_subparsers(dest='command')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract devices from .als')
    extract_parser.add_argument('als_file', help='Path to .als file')

    # List command
    list_parser = subparsers.add_parser('list', help='List devices in library')
    list_parser.add_argument('--category', '-c', choices=['instrument', 'effect', 'utility'])

    # Show command
    show_parser = subparsers.add_parser('show', help='Show device details')
    show_parser.add_argument('name', help='Device name')

    args = parser.parse_args()

    library = DeviceLibrary()

    if args.command == 'extract':
        print(f"Extracting devices from: {args.als_file}")
        templates = library.extract_from_project(args.als_file)
        print(f"Found {len(templates)} devices:")
        for t in templates:
            print(f"  [{t.category}] {t.name} ({t.device_type})")
            library.add_device(t)
        print(f"\nDevices saved to library at: {library.library_path}")

    elif args.command == 'list':
        devices = library.list_devices(args.category)
        category_str = f" ({args.category})" if args.category else ""
        print(f"Devices in library{category_str}:")
        for name in devices:
            dev = library.get_device(name)
            print(f"  [{dev.category}] {name}")

    elif args.command == 'show':
        dev = library.get_device(args.name)
        if dev:
            print(f"Name: {dev.name}")
            print(f"Type: {dev.device_type}")
            print(f"Category: {dev.category}")
            print(f"Metadata: {json.dumps(dev.metadata, indent=2)}")
            print(f"\nXML Preview (first 500 chars):")
            print(dev.xml_element[:500])
        else:
            print(f"Device not found: {args.name}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
