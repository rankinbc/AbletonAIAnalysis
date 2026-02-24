#!/usr/bin/env python3
"""
Create Ableton Live Template for Song Generator

Generates a template .als file with properly named tracks ready for MIDI embedding.
"""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import copy


# Track definitions for the template
TEMPLATE_TRACKS = [
    {"name": "Kick", "color": 69, "type": "midi"},
    {"name": "Bass", "color": 20, "type": "midi"},
    {"name": "Chords", "color": 15, "type": "midi"},
    {"name": "Arp", "color": 13, "type": "midi"},
    {"name": "Lead", "color": 3, "type": "midi"},
    {"name": "Hats", "color": 26, "type": "midi"},
    {"name": "Clap", "color": 26, "type": "midi"},
    {"name": "FX", "color": 60, "type": "midi"},
]

RETURN_TRACKS = [
    {"name": "A-Reverb", "color": 8},
    {"name": "B-Delay", "color": 13},
]


class TemplateCreator:
    """Creates Ableton Live templates from a base file."""

    def __init__(self, base_template: Path):
        """
        Initialize with a base template.

        Args:
            base_template: Path to any valid .als file to use as base
        """
        self.base_template = base_template
        self.next_id = 100000  # Start high to avoid conflicts

    def _get_next_id(self) -> int:
        """Get next available ID."""
        id_val = self.next_id
        self.next_id += 1
        return id_val

    def _find_max_id(self, root: ET.Element) -> int:
        """Find maximum ID in document."""
        max_id = 0
        for elem in root.iter():
            if 'Id' in elem.attrib:
                try:
                    id_val = int(elem.attrib['Id'])
                    max_id = max(max_id, id_val)
                except ValueError:
                    pass
        return max_id

    def _set_track_name(self, track: ET.Element, name: str, color: int):
        """Set track name and color."""
        # Set UserName
        name_elem = track.find(".//Name/UserName")
        if name_elem is not None:
            name_elem.set("Value", name)

        # Set EffectiveName
        eff_name = track.find(".//Name/EffectiveName")
        if eff_name is not None:
            eff_name.set("Value", name)

        # Set color
        color_elem = track.find("ColorIndex") or track.find(".//ColorIndex")
        if color_elem is not None:
            color_elem.set("Value", str(color))

    def _update_all_ids(self, element: ET.Element, start_id: int) -> int:
        """Update all IDs in element tree, returns next available ID."""
        current_id = start_id
        id_mapping = {}

        # First pass: collect and remap IDs
        for elem in element.iter():
            if 'Id' in elem.attrib:
                old_id = elem.attrib['Id']
                new_id = str(current_id)
                id_mapping[old_id] = new_id
                elem.set('Id', new_id)
                current_id += 1

        # Second pass: update Pointee references
        for elem in element.iter():
            if elem.tag == 'Pointee' and 'Id' in elem.attrib:
                old_ref = elem.attrib['Id']
                if old_ref in id_mapping:
                    elem.set('Id', id_mapping[old_ref])

        return current_id

    def _clear_clips(self, track: ET.Element):
        """Remove any existing clips from track."""
        # Clear arrangement clips
        events = track.find(".//ClipTimeable/ArrangerAutomation/Events")
        if events is not None:
            for clip in list(events):
                events.remove(clip)

        # Clear session clips
        clip_slots = track.find(".//ClipSlotList")
        if clip_slots is not None:
            for slot in clip_slots.findall(".//ClipSlot"):
                clip_slot_val = slot.find("Value")
                if clip_slot_val is not None:
                    for child in list(clip_slot_val):
                        clip_slot_val.remove(child)

    def create(self, output_path: Path,
               tracks: List[Dict] = None,
               return_tracks: List[Dict] = None,
               tempo: float = 138.0,
               add_devices: bool = False,
               add_synths: bool = False) -> Path:
        """
        Create a new template.

        Args:
            output_path: Where to save the template
            tracks: List of track definitions (name, color, type)
            return_tracks: List of return track definitions
            tempo: Default tempo

        Returns:
            Path to created template
        """
        tracks = tracks or TEMPLATE_TRACKS
        return_tracks = return_tracks or RETURN_TRACKS

        # Load base template
        with gzip.open(self.base_template, 'rt', encoding='utf-8') as f:
            tree = ET.parse(f)
            root = tree.getroot()

        live_set = root.find("LiveSet")
        if live_set is None:
            raise ValueError("Invalid Ableton file: no LiveSet element")

        # Find max ID and set our starting point
        max_id = self._find_max_id(root)
        self.next_id = max_id + 1000

        # Set tempo
        tempo_elem = root.find(".//MasterTrack//Tempo/Manual")
        if tempo_elem is not None:
            tempo_elem.set("Value", str(float(tempo)))

        # Get tracks container
        tracks_elem = root.find(".//Tracks")
        if tracks_elem is None:
            raise ValueError("No Tracks element found")

        # Find existing MIDI tracks to use as template
        existing_midi = tracks_elem.findall("MidiTrack")
        if not existing_midi:
            raise ValueError("No MIDI tracks in base template to copy")

        midi_template = existing_midi[0]

        # Remove all existing tracks
        for track in list(tracks_elem):
            tracks_elem.remove(track)

        # Create new MIDI tracks
        print(f"Creating {len(tracks)} MIDI tracks...")
        for i, track_def in enumerate(tracks):
            new_track = copy.deepcopy(midi_template)

            # Update all IDs
            self.next_id = self._update_all_ids(new_track, self.next_id)

            # Set track ID attribute
            new_track.set("Id", str(self._get_next_id()))

            # Set name and color
            self._set_track_name(new_track, track_def["name"], track_def["color"])

            # Clear any existing clips
            self._clear_clips(new_track)

            # Add to tracks
            tracks_elem.append(new_track)
            print(f"  + {track_def['name']}")

        # Handle return tracks if base has them
        existing_returns = root.findall(".//ReturnTrack")
        if existing_returns and return_tracks:
            returns_container = root.find(".//Returns")
            if returns_container is not None:
                return_template = existing_returns[0]

                # Clear existing returns
                for ret in list(returns_container):
                    returns_container.remove(ret)

                print(f"Creating {len(return_tracks)} return tracks...")
                for ret_def in return_tracks:
                    new_return = copy.deepcopy(return_template)
                    self.next_id = self._update_all_ids(new_return, self.next_id)
                    new_return.set("Id", str(self._get_next_id()))
                    self._set_track_name(new_return, ret_def["name"], ret_def["color"])
                    returns_container.append(new_return)
                    print(f"  + {ret_def['name']}")

        # Update NextPointeeId
        next_pointee = live_set.find("NextPointeeId")
        if next_pointee is not None:
            next_pointee.set("Value", str(self.next_id + 100))

        # Add devices if requested
        if add_devices or add_synths:
            print("Adding devices...")
            from device_library import add_devices_to_template
            self.next_id = add_devices_to_template(
                root, self.next_id, add_synths=add_synths
            )
            # Update NextPointeeId again
            if next_pointee is not None:
                next_pointee.set("Value", str(self.next_id + 100))

        # Clear locators
        locators = root.find(".//Locators/Locators")
        if locators is not None:
            for loc in list(locators):
                locators.remove(loc)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save
        xml_str = ET.tostring(root, encoding='unicode')
        with gzip.open(output_path, 'wt', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_str)

        print(f"\nTemplate saved: {output_path}")
        return output_path

    def validate(self, template_path: Path) -> bool:
        """
        Validate a template has required tracks.

        Args:
            template_path: Path to template to validate

        Returns:
            True if valid
        """
        required_tracks = {"kick", "bass", "chords", "arp", "lead", "hats", "clap"}

        with gzip.open(template_path, 'rt', encoding='utf-8') as f:
            tree = ET.parse(f)
            root = tree.getroot()

        tracks_elem = root.find(".//Tracks")
        if tracks_elem is None:
            print("ERROR: No Tracks element")
            return False

        found_tracks = set()
        for track in tracks_elem.findall("MidiTrack"):
            name_elem = track.find(".//Name/EffectiveName")
            if name_elem is None:
                name_elem = track.find(".//Name/UserName")
            if name_elem is not None:
                found_tracks.add(name_elem.get("Value", "").lower())

        missing = required_tracks - found_tracks
        if missing:
            print(f"ERROR: Missing tracks: {', '.join(missing)}")
            return False

        print(f"OK: Found all required tracks: {', '.join(sorted(found_tracks))}")
        return True


def find_any_als_file() -> Optional[Path]:
    """Find any .als file to use as base."""
    # Check common locations
    search_paths = [
        Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE"),
        Path.home() / "Music" / "Ableton",
        Path.home() / "Documents" / "Ableton",
    ]

    for search_path in search_paths:
        if search_path.exists():
            for als in search_path.rglob("*.als"):
                # Skip Backup folder
                if "Backup" not in str(als):
                    return als

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Create Ableton template for song generator"
    )
    parser.add_argument(
        "--base", "-b",
        type=Path,
        help="Base .als file to use as template source"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path(r"D:\OneDrive\Music\Projects\Ableton\Ableton Projects\TEMPLATE\Generator_Template\Generator_Template.als"),
        help="Output path for new template"
    )
    parser.add_argument(
        "--tempo", "-t",
        type=float,
        default=138.0,
        help="Default tempo (default: 138)"
    )
    parser.add_argument(
        "--validate", "-v",
        type=Path,
        help="Validate an existing template"
    )
    parser.add_argument(
        "--tracks",
        type=str,
        help="Comma-separated track names (default: Kick,Bass,Chords,Arp,Lead,Hats,Clap,FX)"
    )
    parser.add_argument(
        "--add-devices",
        action="store_true",
        help="Add default Simpler devices to drum tracks (Kick, Clap, Hats)"
    )
    parser.add_argument(
        "--add-synths",
        action="store_true",
        help="Add synths for melodic tracks (Bass, Chords, Arp, Lead) - requires device library"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Add all devices (drums + synths)"
    )

    args = parser.parse_args()

    # Validation mode
    if args.validate:
        if not args.validate.exists():
            print(f"File not found: {args.validate}")
            return 1

        # Need a base just for the class, but won't use it
        base = args.validate
        creator = TemplateCreator(base)
        valid = creator.validate(args.validate)
        return 0 if valid else 1

    # Find base template
    base = args.base
    if not base:
        base = find_any_als_file()
        if not base:
            print("ERROR: No base .als file found. Specify with --base")
            return 1
        print(f"Using base: {base}")

    if not base.exists():
        print(f"ERROR: Base file not found: {base}")
        return 1

    # Parse custom tracks if provided
    tracks = TEMPLATE_TRACKS
    if args.tracks:
        track_names = [t.strip() for t in args.tracks.split(",")]
        tracks = [{"name": name, "color": 15, "type": "midi"} for name in track_names]

    # Create template
    creator = TemplateCreator(base)

    print(f"\n{'='*50}")
    print("  CREATING ABLETON TEMPLATE")
    print(f"{'='*50}\n")

    # Determine device options
    add_devices = args.add_devices or args.full
    add_synths = args.add_synths or args.full

    try:
        output = creator.create(
            args.output,
            tracks=tracks,
            tempo=args.tempo,
            add_devices=add_devices,
            add_synths=add_synths
        )

        print(f"\n{'='*50}")
        print("  VALIDATING")
        print(f"{'='*50}\n")

        creator.validate(output)

        print(f"\n{'='*50}")
        print("  DONE")
        print(f"{'='*50}")
        print(f"\nTemplate ready at:")
        print(f"  {output}")
        print(f"\nTo use this template, update config.py:")
        print(f'  DEFAULT_LIVE_SET = Path(r"{output}")')

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
