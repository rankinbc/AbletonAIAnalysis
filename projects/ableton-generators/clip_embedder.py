"""
MIDI Clip Embedder for Ableton Live Sets

Converts MIDI files to Ableton's MidiClip XML format and embeds them
directly into .als files so projects are immediately playable.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import mido


@dataclass
class MidiNote:
    """A single MIDI note."""
    pitch: int  # MIDI note number (0-127)
    time: float  # Start time in beats
    duration: float  # Duration in beats
    velocity: int  # Velocity (0-127)


@dataclass
class MidiClipData:
    """Data for a MIDI clip to embed."""
    name: str
    start_time: float  # Position in arrangement (beats)
    end_time: float  # End position in arrangement (beats)
    notes: List[MidiNote] = field(default_factory=list)
    loop_start: float = 0.0
    loop_end: float = 0.0
    color_index: int = 0


def read_midi_file(path: Path, ticks_per_beat: int = 480) -> List[MidiNote]:
    """
    Read a MIDI file and extract notes.

    Args:
        path: Path to .mid file
        ticks_per_beat: Ticks per beat (for conversion)

    Returns:
        List of MidiNote objects
    """
    mid = mido.MidiFile(str(path))
    notes = []

    # Track note-on events to calculate duration
    active_notes: Dict[int, Tuple[float, int]] = {}  # pitch -> (start_time, velocity)
    current_time = 0.0

    for track in mid.tracks:
        current_time = 0.0
        for msg in track:
            # Convert delta time to beats
            current_time += msg.time / ticks_per_beat

            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes[msg.note] = (current_time, msg.velocity)
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    start_time, velocity = active_notes.pop(msg.note)
                    duration = current_time - start_time
                    if duration > 0:
                        notes.append(MidiNote(
                            pitch=msg.note,
                            time=start_time,
                            duration=duration,
                            velocity=velocity
                        ))

    return notes


def create_midi_clip_xml(clip_data: MidiClipData, start_id: int) -> Tuple[ET.Element, int]:
    """
    Create a MidiClip XML element from clip data.

    Args:
        clip_data: MidiClipData with notes and timing
        start_id: Starting unique ID for elements

    Returns:
        Tuple of (ET.Element for the MidiClip, next available ID)
    """
    next_id = start_id

    def get_id() -> str:
        nonlocal next_id
        id_str = str(next_id)
        next_id += 1
        return id_str

    # Calculate clip length in beats
    clip_length = clip_data.end_time - clip_data.start_time
    loop_end = clip_data.loop_end if clip_data.loop_end > 0 else clip_length

    clip = ET.Element("MidiClip", {
        "Id": get_id(),
        "Time": str(clip_data.start_time)
    })

    # Basic properties
    ET.SubElement(clip, "LomId", {"Value": "0"})
    ET.SubElement(clip, "LomIdView", {"Value": "0"})

    # Warp markers (minimal)
    warp_markers = ET.SubElement(clip, "WarpMarkers")
    ET.SubElement(warp_markers, "WarpMarker", {"Id": get_id(), "SecTime": "0", "BeatTime": "0"})
    ET.SubElement(warp_markers, "WarpMarker", {"Id": get_id(), "SecTime": "0.015625", "BeatTime": "0.03125"})

    ET.SubElement(clip, "MarkersGenerated", {"Value": "false"})
    ET.SubElement(clip, "CurrentStart", {"Value": str(clip_data.start_time)})
    ET.SubElement(clip, "CurrentEnd", {"Value": str(clip_data.end_time)})

    # Loop settings
    loop = ET.SubElement(clip, "Loop")
    ET.SubElement(loop, "LoopStart", {"Value": str(clip_data.loop_start)})
    ET.SubElement(loop, "LoopEnd", {"Value": str(loop_end)})
    ET.SubElement(loop, "StartRelative", {"Value": "0"})
    ET.SubElement(loop, "LoopOn", {"Value": "true"})
    ET.SubElement(loop, "OutMarker", {"Value": str(loop_end)})
    ET.SubElement(loop, "HiddenLoopStart", {"Value": "0"})
    ET.SubElement(loop, "HiddenLoopEnd", {"Value": str(loop_end / 2)})

    # Clip metadata
    ET.SubElement(clip, "Name", {"Value": clip_data.name})
    ET.SubElement(clip, "Annotation", {"Value": ""})
    ET.SubElement(clip, "ColorIndex", {"Value": str(clip_data.color_index)})
    ET.SubElement(clip, "LaunchMode", {"Value": "0"})
    ET.SubElement(clip, "LaunchQuantisation", {"Value": "0"})

    # Time signature
    time_sig = ET.SubElement(clip, "TimeSignature")
    time_sigs = ET.SubElement(time_sig, "TimeSignatures")
    remote_ts = ET.SubElement(time_sigs, "RemoteableTimeSignature", {"Id": get_id()})
    ET.SubElement(remote_ts, "Numerator", {"Value": "4"})
    ET.SubElement(remote_ts, "Denominator", {"Value": "4"})
    ET.SubElement(remote_ts, "Time", {"Value": "0"})

    # Envelopes (empty)
    envelopes = ET.SubElement(clip, "Envelopes")
    ET.SubElement(envelopes, "Envelopes")

    # Scroller
    scroller = ET.SubElement(clip, "ScrollerTimePreserver")
    ET.SubElement(scroller, "LeftTime", {"Value": "0"})
    ET.SubElement(scroller, "RightTime", {"Value": str(loop_end)})

    # Time selection
    time_sel = ET.SubElement(clip, "TimeSelection")
    ET.SubElement(time_sel, "AnchorTime", {"Value": "0"})
    ET.SubElement(time_sel, "OtherTime", {"Value": str(loop_end)})

    # Other settings
    ET.SubElement(clip, "Legato", {"Value": "false"})
    ET.SubElement(clip, "Ram", {"Value": "false"})

    groove = ET.SubElement(clip, "GrooveSettings")
    ET.SubElement(groove, "GrooveId", {"Value": "-1"})

    ET.SubElement(clip, "Disabled", {"Value": "false"})
    ET.SubElement(clip, "VelocityAmount", {"Value": "0"})
    ET.SubElement(clip, "FollowTime", {"Value": "4"})
    ET.SubElement(clip, "FollowActionA", {"Value": "0"})
    ET.SubElement(clip, "FollowActionB", {"Value": "0"})
    ET.SubElement(clip, "FollowChanceA", {"Value": "1"})
    ET.SubElement(clip, "FollowChanceB", {"Value": "0"})

    # Grid
    grid = ET.SubElement(clip, "Grid")
    ET.SubElement(grid, "FixedNumerator", {"Value": "1"})
    ET.SubElement(grid, "FixedDenominator", {"Value": "16"})
    ET.SubElement(grid, "GridIntervalPixel", {"Value": "20"})
    ET.SubElement(grid, "Ntoles", {"Value": "2"})
    ET.SubElement(grid, "SnapToGrid", {"Value": "true"})
    ET.SubElement(grid, "Fixed", {"Value": "false"})

    ET.SubElement(clip, "FreezeStart", {"Value": "0"})
    ET.SubElement(clip, "FreezeEnd", {"Value": "0"})
    ET.SubElement(clip, "IsSongTempoMaster", {"Value": "false"})
    ET.SubElement(clip, "IsWarped", {"Value": "true"})

    # Notes - group by pitch into KeyTracks
    notes_elem = ET.SubElement(clip, "Notes")
    key_tracks = ET.SubElement(notes_elem, "KeyTracks")

    # Group notes by pitch
    notes_by_pitch: Dict[int, List[MidiNote]] = {}
    for note in clip_data.notes:
        if note.pitch not in notes_by_pitch:
            notes_by_pitch[note.pitch] = []
        notes_by_pitch[note.pitch].append(note)

    # Create a KeyTrack for each pitch
    for pitch in sorted(notes_by_pitch.keys()):
        pitch_notes = notes_by_pitch[pitch]

        key_track = ET.SubElement(key_tracks, "KeyTrack", {"Id": get_id()})
        notes_container = ET.SubElement(key_track, "Notes")

        for note in sorted(pitch_notes, key=lambda n: n.time):
            # Note time is relative to clip start (internal time)
            relative_time = note.time - clip_data.start_time
            ET.SubElement(notes_container, "MidiNoteEvent", {
                "Time": str(relative_time),
                "Duration": str(note.duration),
                "Velocity": str(note.velocity),
                "OffVelocity": "64",
                "IsEnabled": "true"
            })

        ET.SubElement(key_track, "MidiKey", {"Value": str(pitch)})

    # Remaining clip settings
    ET.SubElement(clip, "BankSelectCoarse", {"Value": "-1"})
    ET.SubElement(clip, "BankSelectFine", {"Value": "-1"})
    ET.SubElement(clip, "ProgramChange", {"Value": "-1"})
    ET.SubElement(clip, "NoteEditorFoldInZoom", {"Value": "-1"})
    ET.SubElement(clip, "NoteEditorFoldInScroll", {"Value": "-1"})
    ET.SubElement(clip, "NoteEditorFoldOutZoom", {"Value": "92"})
    ET.SubElement(clip, "NoteEditorFoldOutScroll", {"Value": "0"})

    return clip, next_id


def embed_clips_in_track(track: ET.Element, clips: List[MidiClipData],
                         start_id: int) -> int:
    """
    Embed MIDI clips into a track's arrangement.

    Args:
        track: MidiTrack or AudioTrack element
        clips: List of MidiClipData to embed
        start_id: Starting ID for clip elements

    Returns:
        Next available ID after all clips
    """
    # Find the Events container
    device_chain = track.find("DeviceChain")
    if device_chain is None:
        return start_id

    main_seq = device_chain.find("MainSequencer")
    if main_seq is None:
        return start_id

    clip_timeable = main_seq.find("ClipTimeable")
    if clip_timeable is None:
        return start_id

    arranger = clip_timeable.find("ArrangerAutomation")
    if arranger is None:
        return start_id

    events = arranger.find("Events")
    if events is None:
        events = ET.SubElement(arranger, "Events")

    # Add clips
    current_id = start_id
    for clip_data in clips:
        clip_elem, current_id = create_midi_clip_xml(clip_data, current_id)
        events.append(clip_elem)

    return current_id


def midi_file_to_clips(midi_path: Path, track_name: str,
                       total_bars: int, ticks_per_beat: int = 480,
                       sections: List[Tuple[str, int, int]] = None) -> List[MidiClipData]:
    """
    Convert a MIDI file to clip data for the full arrangement.

    Args:
        midi_path: Path to .mid file
        track_name: Name for the clip
        total_bars: Total number of bars in the song
        ticks_per_beat: MIDI ticks per beat
        sections: Optional list of (name, start_bar, end_bar) to split into separate clips

    Returns:
        List of MidiClipData (one clip per section if sections provided, else one big clip)
    """
    notes = read_midi_file(midi_path, ticks_per_beat)

    if not notes:
        return []

    # If no sections provided, create one big clip
    if not sections:
        clip_length = total_bars * 4  # bars to beats
        clip = MidiClipData(
            name=track_name,
            start_time=0,
            end_time=clip_length,
            notes=notes,
            loop_start=0,
            loop_end=clip_length,
        )
        return [clip]

    # Split into clips by section
    clips = []
    for section_name, start_bar, end_bar in sections:
        start_beat = start_bar * 4
        end_beat = end_bar * 4

        # Find notes that fall within this section
        section_notes = []
        for note in notes:
            # Note starts within section
            if start_beat <= note.time < end_beat:
                section_notes.append(note)
            # Note starts before but extends into section
            elif note.time < start_beat and note.time + note.duration > start_beat:
                # Clip the note to start at section boundary
                clipped_note = MidiNote(
                    pitch=note.pitch,
                    time=start_beat,
                    duration=min(note.time + note.duration, end_beat) - start_beat,
                    velocity=note.velocity
                )
                section_notes.append(clipped_note)

        # Only create clip if there are notes
        if section_notes:
            clip = MidiClipData(
                name=f"{track_name} - {section_name}",
                start_time=start_beat,
                end_time=end_beat,
                notes=section_notes,
                loop_start=0,
                loop_end=end_beat - start_beat,
            )
            clips.append(clip)

    return clips


class ClipEmbedder:
    """Embeds MIDI clips into Ableton Live Set tracks."""

    def __init__(self, ticks_per_beat: int = 480):
        self.ticks_per_beat = ticks_per_beat

    def embed_midi_files(self, root: ET.Element, midi_dir: Path,
                         track_mapping: Dict[str, str], total_bars: int,
                         start_id: int, sections: List[Tuple[str, int, int]] = None) -> int:
        """
        Embed MIDI files into tracks.

        Args:
            root: Ableton Live Set root element
            midi_dir: Directory containing .mid files
            track_mapping: Dict of track_name -> midi_filename
            total_bars: Total bars in the song
            start_id: Starting ID for clip elements
            sections: Optional list of (name, start_bar, end_bar) to split clips

        Returns:
            Next available ID
        """
        tracks_elem = root.find(".//Tracks")
        if tracks_elem is None:
            return start_id

        current_id = start_id

        # Find tracks by name
        for track in tracks_elem.findall("MidiTrack"):
            name_elem = track.find(".//Name/EffectiveName")
            if name_elem is None:
                name_elem = track.find(".//Name/UserName")

            if name_elem is None:
                continue

            track_name = name_elem.get("Value", "").lower()

            # Check if we have MIDI for this track
            midi_filename = track_mapping.get(track_name)
            if midi_filename is None:
                # Try to find by track name directly
                midi_path = midi_dir / f"{track_name}.mid"
                if not midi_path.exists():
                    continue
            else:
                midi_path = midi_dir / midi_filename
                if not midi_path.exists():
                    continue

            # Convert MIDI to clips
            clips = midi_file_to_clips(
                midi_path,
                track_name.title(),
                total_bars,
                self.ticks_per_beat,
                sections=sections
            )

            if clips:
                current_id = embed_clips_in_track(track, clips, current_id)
                total_notes = sum(len(c.notes) for c in clips)
                if sections:
                    print(f"    Embedded {total_notes} notes in {len(clips)} clips for {track_name}")
                else:
                    print(f"    Embedded {total_notes} notes in {track_name}")

        return current_id


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test MIDI clip embedding")
    parser.add_argument("midi_file", type=Path, help="MIDI file to analyze")

    args = parser.parse_args()

    if not args.midi_file.exists():
        print(f"File not found: {args.midi_file}")
        exit(1)

    notes = read_midi_file(args.midi_file)
    print(f"Read {len(notes)} notes from {args.midi_file.name}")

    if notes:
        print(f"Time range: {min(n.time for n in notes):.2f} - {max(n.time + n.duration for n in notes):.2f} beats")
        print(f"Pitch range: {min(n.pitch for n in notes)} - {max(n.pitch for n in notes)}")
        print(f"\nFirst 10 notes:")
        for note in sorted(notes, key=lambda n: n.time)[:10]:
            print(f"  Time={note.time:.2f} Pitch={note.pitch} Dur={note.duration:.2f} Vel={note.velocity}")
