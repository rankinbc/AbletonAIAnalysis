"""
Trance Template Generator with Samples

Creates a complete Ableton trance template with:
- 8 tracks (6 MIDI + 2 Audio)
- Arrangement markers for all sections
- Simpler instruments loaded with Imba Goa Trance samples
- Ready to start producing

Usage:
    python create_trance_with_samples.py
    python create_trance_with_samples.py --kick 5 --clap 3 --hat 10
"""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
import copy
import argparse

from sample_generator import SampleGenerator, IMBA_GOA_TRANCE_PATH

# Template configuration
TRANCE_TRACKS = [
    {"name": "Kick", "color": 69, "type": "midi"},
    {"name": "Bass", "color": 20, "type": "midi"},
    {"name": "Perc", "color": 26, "type": "midi"},
    {"name": "Pad", "color": 15, "type": "midi"},
    {"name": "Lead", "color": 3, "type": "midi"},
    {"name": "Arp", "color": 13, "type": "midi"},
    {"name": "FX", "color": 60, "type": "audio"},
    {"name": "Vox", "color": 8, "type": "audio"},
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
        if 'Id' in elem.attrib:
            try:
                val = int(elem.attrib['Id'])
                if val > max_id:
                    max_id = val
            except ValueError:
                pass
    return max_id


def update_ids_in_element(elem, id_offset):
    """Update all numeric IDs in an element tree by adding offset."""
    for e in elem.iter():
        if 'Id' in e.attrib:
            try:
                old_id = int(e.attrib['Id'])
                e.set('Id', str(old_id + id_offset))
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


def find_devices_container(track):
    """Find the Devices container in a track."""
    # Try different paths that Ableton uses
    paths = [
        ".//DeviceChain/DeviceChain/Devices",
        ".//DeviceChain/Devices",
    ]
    for path in paths:
        devices = track.find(path)
        if devices is not None:
            return devices

    # Create if not found
    device_chain = track.find(".//DeviceChain/DeviceChain")
    if device_chain is None:
        device_chain = track.find(".//DeviceChain")
    if device_chain is not None:
        devices = ET.SubElement(device_chain, "Devices")
        return devices

    return None


def insert_device_xml(track, device_xml_str):
    """Insert a device XML string into a track."""
    devices = find_devices_container(track)
    if devices is None:
        print("  Warning: Could not find Devices container")
        return False

    # Parse the device XML
    device_elem = ET.fromstring(device_xml_str)

    # Insert the device
    devices.append(device_elem)
    return True


def main():
    parser = argparse.ArgumentParser(description='Create Trance Template with Samples')
    parser.add_argument('--kick', '-k', type=int, default=1, help='Kick sample number (1-64)')
    parser.add_argument('--clap', '-c', type=int, default=1, help='Clap sample number (1-13)')
    parser.add_argument('--hat', '-H', type=int, default=1, help='Hat sample number (1-56)')
    parser.add_argument('--snare', '-s', type=int, default=1, help='Snare sample number (1-58)')
    parser.add_argument('--output', '-o', type=str, default=None, help='Output path')
    parser.add_argument('--no-samples', action='store_true', help='Skip adding samples')

    args = parser.parse_args()

    # Source: Ableton's factory default
    source_path = "C:/Users/badmin/AppData/Roaming/Ableton/Live 11.3.11/Preferences/Crash/2026_01_14__12_50_06_BaseFiles/DefaultLiveSet.als"

    # Output path
    if args.output:
        output_path = args.output
    else:
        output_path = "C:/Users/badmin/Music/Trance_Template/Trance_With_Samples.als"

    print("=" * 60)
    print("TRANCE TEMPLATE GENERATOR (with Samples)")
    print("=" * 60)
    print()

    # Verify sample kit exists
    sample_base = Path(IMBA_GOA_TRANCE_PATH)
    if not sample_base.exists():
        print(f"Warning: Sample folder not found: {sample_base}")
        print("Proceeding without samples...")
        args.no_samples = True
    else:
        print(f"Sample Kit: {sample_base.name}")
        print(f"  Kick #{args.kick}, Clap #{args.clap}, Hat #{args.hat}, Snare #{args.snare}")
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

    midi_template = midi_tracks[0]
    audio_template = audio_tracks[0]

    # Get current max ID
    max_id = get_max_id(root)
    id_increment = 1000

    # Remove existing MIDI and Audio tracks (keep Returns)
    for track in midi_tracks + audio_tracks:
        tracks_elem.remove(track)

    # Sample generator
    gen = SampleGenerator()

    # Store created tracks for device insertion
    created_tracks = {}

    # Create MIDI tracks (6)
    print("\nCreating MIDI tracks:")
    midi_count = sum(1 for t in TRANCE_TRACKS if t["type"] == "midi")
    for i in range(midi_count):
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

        created_tracks[TRANCE_TRACKS[i]["name"]] = new_track
        print(f"  + {TRANCE_TRACKS[i]['name']}")

    # Create Audio tracks (2)
    print("\nCreating Audio tracks:")
    audio_count = sum(1 for t in TRANCE_TRACKS if t["type"] == "audio")
    for i in range(audio_count):
        track_idx = midi_count + i
        new_track = copy.deepcopy(audio_template)
        update_ids_in_element(new_track, (track_idx + 1) * id_increment)
        new_track.set("Id", str(max_id + (track_idx + 1) * 100))
        set_track_name(new_track, TRANCE_TRACKS[track_idx]["name"], TRANCE_TRACKS[track_idx]["color"])

        # Insert before return tracks
        return_tracks = tracks_elem.findall("ReturnTrack")
        if return_tracks:
            idx = list(tracks_elem).index(return_tracks[0])
            tracks_elem.insert(idx, new_track)
        else:
            tracks_elem.append(new_track)

        created_tracks[TRANCE_TRACKS[track_idx]["name"]] = new_track
        print(f"  + {TRANCE_TRACKS[track_idx]['name']}")

    # Add sample-based instruments
    if not args.no_samples:
        print("\nAdding instruments with samples:")

        # Kick track - single kick sample in Simpler
        kick_path = sample_base / f"Kicks/Imba Kick {args.kick:02d}.wav"
        if kick_path.exists():
            kick_xml = gen.create_simpler_with_sample(str(kick_path), "Goa Kick")
            if insert_device_xml(created_tracks["Kick"], kick_xml):
                print(f"  + Kick: Imba Kick {args.kick:02d}")
        else:
            print(f"  ! Kick sample not found: {kick_path.name}")

        # Perc track - Drum rack with clap, snare, hats
        print(f"  + Perc: Drum Rack with clap, snare, hats")
        perc_samples = {}

        # Clap on D#1 (39)
        clap_path = sample_base / f"Claps/Imba Clap {args.clap:02d}.wav"
        if clap_path.exists():
            perc_samples[39] = str(clap_path)

        # Snare on D1 (38)
        snare_path = sample_base / f"Snares/Imba Snare {args.snare:02d}.wav"
        if snare_path.exists():
            perc_samples[38] = str(snare_path)

        # Closed hat on F#1 (42)
        hat_path = sample_base / f"Closed Hats/Imba Closed Hat {args.hat:02d}.wav"
        if hat_path.exists():
            perc_samples[42] = str(hat_path)

        if perc_samples:
            drum_rack_xml = gen.create_drum_rack(perc_samples, name="Perc Rack")
            insert_device_xml(created_tracks["Perc"], drum_rack_xml)

    # Set tempo
    tempo_elem = root.find(".//MasterTrack//Tempo/Manual")
    if tempo_elem is not None:
        tempo_elem.set("Value", str(TEMPO))
        print(f"\nTempo: {TEMPO} BPM")

    # Add locators (arrangement markers)
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
    print("To open in Ableton:")
    print(f'"C:\\ProgramData\\Ableton\\Live 11 Suite\\Program\\Ableton Live 11 Suite.exe" "{output_path}"')


if __name__ == "__main__":
    main()
