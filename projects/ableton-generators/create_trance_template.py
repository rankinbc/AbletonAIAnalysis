"""
Trance Template Generator v4

Uses Ableton's factory DefaultLiveSet.als as the base.
This is the cleanest possible starting point.
"""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
import copy
import re

# Template configuration
TRANCE_TRACKS = [
    {"name": "Kick", "color": 69},
    {"name": "Bass", "color": 20},
    {"name": "Perc", "color": 26},
    {"name": "Pad", "color": 15},
    {"name": "Lead", "color": 3},
    {"name": "Arp", "color": 13},
    {"name": "FX", "color": 60},
    {"name": "Vox", "color": 8},
]

TRANCE_SECTIONS = [
    {"name": "INTRO", "beat": 0},
    {"name": "BUILDUP A", "beat": 64},
    {"name": "BREAKDOWN 1", "beat": 128},
    {"name": "DROP 1", "beat": 256},
    {"name": "BREAK", "beat": 384},
    {"name": "BREAKDOWN 2", "beat": 448},
    {"name": "DROP 2", "beat": 576},
    {"name": "OUTRO", "beat": 704},
]

TEMPO = 138.0


def get_max_id(root):
    """Find the maximum numeric ID in the document."""
    max_id = 0
    for elem in root.iter():
        for attr in ['Id']:
            if attr in elem.attrib:
                try:
                    val = int(elem.attrib[attr])
                    if val > max_id:
                        max_id = val
                except ValueError:
                    pass
    return max_id


def update_ids_in_element(elem, id_offset):
    """Update all numeric IDs in an element tree by adding offset."""
    for e in elem.iter():
        for attr in ['Id']:
            if attr in e.attrib:
                try:
                    old_id = int(e.attrib[attr])
                    e.set(attr, str(old_id + id_offset))
                except ValueError:
                    pass


def set_track_name(track, name, color):
    """Set the track name and color."""
    name_elem = track.find(".//Name")
    if name_elem is not None:
        eff = name_elem.find("EffectiveName")
        if eff is not None:
            eff.set("Value", name)
        user = name_elem.find("UserName")
        if user is not None:
            user.set("Value", name)

    color_elem = track.find("Color")
    if color_elem is not None:
        color_elem.set("Value", str(color))


def main():
    # Source: Ableton's factory default
    source_path = "C:/Users/badmin/AppData/Roaming/Ableton/Live 11.3.11/Preferences/Crash/2026_01_14__12_50_06_BaseFiles/DefaultLiveSet.als"
    output_path = "C:/Users/badmin/Music/Trance_Template/Trance_Blueprint.als"

    print("=" * 60)
    print("TRANCE TEMPLATE GENERATOR v4")
    print("Using factory DefaultLiveSet.als as base")
    print("=" * 60)
    print()

    # Load the default set
    print("Loading factory default...")
    with gzip.open(source_path, 'rb') as f:
        xml_content = f.read().decode('utf-8')

    root = ET.fromstring(xml_content)
    live_set = root.find("LiveSet")
    tracks_elem = live_set.find("Tracks")

    # Get template tracks
    midi_tracks = tracks_elem.findall("MidiTrack")
    audio_tracks = tracks_elem.findall("AudioTrack")

    print(f"  Found {len(midi_tracks)} MIDI, {len(audio_tracks)} Audio tracks")

    # We need 6 MIDI + 2 Audio tracks
    # Default has 2 MIDI + 2 Audio
    # So we need to duplicate MIDI tracks 4 more times

    midi_template = midi_tracks[0]
    audio_template = audio_tracks[0]

    # Get current max ID
    max_id = get_max_id(root)
    id_increment = 1000

    # Remove existing MIDI and Audio tracks (keep Returns)
    for track in midi_tracks + audio_tracks:
        tracks_elem.remove(track)

    # Create 6 MIDI tracks
    print("\nCreating MIDI tracks:")
    for i in range(6):
        new_track = copy.deepcopy(midi_template)
        update_ids_in_element(new_track, (i + 1) * id_increment)
        new_track.set("Id", str(max_id + (i + 1) * 100))
        set_track_name(new_track, TRANCE_TRACKS[i]["name"], TRANCE_TRACKS[i]["color"])

        # Insert before return tracks
        return_tracks = tracks_elem.findall("ReturnTrack")
        if return_tracks:
            idx = list(tracks_elem).index(return_tracks[0])
            tracks_elem.insert(idx, new_track)
        else:
            tracks_elem.append(new_track)

        print(f"  + {TRANCE_TRACKS[i]['name']}")

    # Create 2 Audio tracks
    print("\nCreating Audio tracks:")
    for i in range(2):
        new_track = copy.deepcopy(audio_template)
        update_ids_in_element(new_track, (i + 7) * id_increment)
        new_track.set("Id", str(max_id + (i + 7) * 100))
        set_track_name(new_track, TRANCE_TRACKS[i + 6]["name"], TRANCE_TRACKS[i + 6]["color"])

        # Insert before return tracks
        return_tracks = tracks_elem.findall("ReturnTrack")
        if return_tracks:
            idx = list(tracks_elem).index(return_tracks[0])
            tracks_elem.insert(idx, new_track)
        else:
            tracks_elem.append(new_track)

        print(f"  + {TRANCE_TRACKS[i + 6]['name']}")

    # Set tempo
    tempo_elem = root.find(".//MasterTrack//Tempo/Manual")
    if tempo_elem is not None:
        tempo_elem.set("Value", str(TEMPO))
        print(f"\nTempo: {TEMPO} BPM")

    # Add locators
    locators_container = live_set.find("Locators")
    if locators_container is None:
        locators_container = ET.SubElement(live_set, "Locators")

    locators = locators_container.find("Locators")
    if locators is None:
        locators = ET.SubElement(locators_container, "Locators")

    # Clear existing locators
    for loc in list(locators):
        locators.remove(loc)

    # Add arrangement markers
    print("\nArrangement markers:")
    for i, section in enumerate(TRANCE_SECTIONS):
        loc = ET.SubElement(locators, "Locator", {"Id": str(i)})
        ET.SubElement(loc, "LomId", {"Value": "0"})
        ET.SubElement(loc, "Time", {"Value": str(section["beat"])})
        ET.SubElement(loc, "Name", {"Value": section["name"]})
        ET.SubElement(loc, "Annotation", {"Value": ""})
        ET.SubElement(loc, "IsSongStart", {"Value": "true" if i == 0 else "false"})
        print(f"  Bar {section['beat'] // 4 + 1:3}: {section['name']}")

    # Update NextPointeeId
    next_pointee = live_set.find("NextPointeeId")
    if next_pointee is not None:
        next_pointee.set("Value", str(max_id + 100000))

    # Save
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')

    with gzip.open(output_path, 'wb') as f:
        f.write(xml_str.encode('utf-8'))

    print(f"\n{'=' * 60}")
    print(f"SAVED: {output_path}")
    print(f"{'=' * 60}")
    print()
    print("To open:")
    print(f'"C:\\ProgramData\\Ableton\\Live 11 Suite\\Program\\Ableton Live 11 Suite.exe" "{output_path}"')


if __name__ == "__main__":
    main()
