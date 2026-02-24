#!/usr/bin/env python3
"""
Trance Template Generator for Ableton Live 11
Generates a fully structured .als file with:
  - 138 BPM, 4/4 time, A minor
  - Kick (4-on-floor), Clap, Open HH, Closed HH
  - Rolling bass (16th notes)
  - Supersaw lead melody
  - Pad chords (A minor progression)
  - Pluck arp
  - White noise riser FX track
  - Return tracks: Reverb, Delay, Chorus
  - All tracks colour-coded by role
"""

import gzip
import textwrap
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# ─────────────────────────────────────────────
# Global ID counter (every node needs unique Id)
# ─────────────────────────────────────────────
_id_counter = 0

def new_id():
    global _id_counter
    _id_counter += 1
    return _id_counter

# ─────────────────────────────────────────────
# Colour palette (Ableton uses integer colours)
# ─────────────────────────────────────────────
COLORS = {
    "kick":    4,   # Orange
    "clap":    5,   # Yellow
    "hh":      9,   # Teal
    "bass":    13,  # Blue
    "lead":    27,  # Purple
    "pad":     22,  # Green
    "pluck":   18,  # Cyan
    "fx":      1,   # Red
    "return":  0,   # Default grey
}

# ─────────────────────────────────────────────
# Trance patterns (2-bar = 8 beats = 32 16ths)
# Time values are in beats (quarter notes)
# ─────────────────────────────────────────────

def four_on_floor(bars=2):
    """Kick on every beat"""
    notes = []
    for bar in range(bars):
        for beat in range(4):
            notes.append((bar * 4.0 + beat, 0.25, 100))
    return notes  # (time, duration, velocity)


def clap_pattern(bars=2):
    """Clap/snare on beats 2 and 4"""
    notes = []
    for bar in range(bars):
        for beat in [1, 3]:
            notes.append((bar * 4.0 + beat, 0.25, 90))
    return notes


def closed_hh_pattern(bars=2):
    """16th-note closed hi-hats with velocity variation"""
    notes = []
    for bar in range(bars):
        for sixteenth in range(16):
            t = bar * 4.0 + sixteenth * 0.25
            vel = 80 if sixteenth % 2 == 0 else 55
            notes.append((t, 0.125, vel))
    return notes


def open_hh_pattern(bars=2):
    """Open hi-hat on off-beats (8th-note upbeats)"""
    notes = []
    for bar in range(bars):
        for beat in range(4):
            t = bar * 4.0 + beat + 0.5
            notes.append((t, 0.25, 70))
    return notes


def rolling_bass(bars=2, root_midi=45):
    """16th-note rolling bass — classic trance staple. Root = A2 (45)"""
    # A minor: A A A A  E E E E  F F F F  G G G G
    pattern = [root_midi] * 8 + [root_midi - 5] * 4 + [root_midi - 4] * 4  # A A E F
    pattern += [root_midi] * 8 + [root_midi - 2] * 4 + [root_midi - 3] * 4  # A A G G#
    notes = []
    for bar in range(bars):
        for i in range(16):
            t = bar * 4.0 + i * 0.25
            pitch = pattern[(bar * 16 + i) % len(pattern)]
            vel = 100 if i % 4 == 0 else 85
            notes.append((t, 0.2, vel, pitch))
    return notes


def supersaw_melody(bars=2, root_midi=69):
    """
    Simple 2-bar trance lead melody over A minor.
    root_midi = A4 (69)
    Returns list of (time, duration, velocity, pitch)
    """
    # Iconic trance-style 8th-note melody fragment
    melody = [
        # Bar 1: A4 C5 E5 A5 | G5 E5 C5 A4
        (0.0,  0.375, 100, 69),
        (0.5,  0.375, 90,  72),
        (1.0,  0.375, 95,  76),
        (1.5,  0.75,  100, 81),
        (2.5,  0.375, 90,  79),
        (3.0,  0.375, 85,  76),
        (3.5,  0.375, 80,  72),
        # Bar 2: A4 B4 C5 E5 | D5 C5 B4 A4
        (4.0,  0.375, 100, 69),
        (4.5,  0.375, 90,  71),
        (5.0,  0.375, 95,  72),
        (5.5,  0.75,  100, 76),
        (6.5,  0.375, 90,  74),
        (7.0,  0.375, 85,  72),
        (7.5,  0.5,   80,  71),
    ]
    # Shift to the requested root (default is already A4)
    shift = root_midi - 69
    return [(t, d, v, p + shift) for (t, d, v, p) in melody]


def pad_chords(bars=4, root_midi=57):
    """
    Sustained pad chords — A minor progression over 4 bars:
    Am | F | C | G
    root_midi = A3 (57)
    """
    # Each chord: (bar, [semitone offsets from A3])
    progression = [
        (0, [0, 3, 7, 12]),    # Am  (A C E A)
        (1, [-4, 0, 5, 9]),    # F   (F A C F) relative to A3
        (2, [-9, -5, 0, 3]),   # C   (C E G C) relative to A3
        (3, [-7, -3, 0, 5]),   # G   (G B D G) relative to A3
    ]
    notes = []
    for (bar, intervals) in progression:
        for iv in intervals:
            pitch = root_midi + iv
            notes.append((bar * 4.0, 3.75, 75, pitch))
    return notes


def pluck_arp(bars=2, root_midi=69):
    """
    16th-note arp over Am / F alternating.
    Ascending then descending pattern.
    """
    am_arp = [69, 72, 76, 81, 76, 72, 69, 72,   # A C E A E C A C
              69, 72, 76, 81, 84, 81, 76, 72]    # ascending then down
    f_arp  = [65, 69, 72, 77, 72, 69, 65, 69,
              65, 69, 72, 77, 81, 77, 72, 69]
    arps = [am_arp, f_arp]
    notes = []
    for bar in range(bars):
        arp = arps[bar % 2]
        for i, pitch in enumerate(arp):
            t = bar * 4.0 + i * 0.25
            vel = 90 if i % 4 == 0 else 70
            notes.append((t, 0.2, vel, pitch))
    return notes


# ─────────────────────────────────────────────
# XML helpers
# ─────────────────────────────────────────────

def val(parent, tag, value):
    """<tag Value="value" />"""
    e = SubElement(parent, tag)
    e.set("Value", str(value))
    return e


def manual_param(parent, tag, value, automation_target=None, modulation_target=None):
    """A typical automatable Live parameter block"""
    e = SubElement(parent, tag)
    auto_id = automation_target or new_id()
    mod_id  = modulation_target  or new_id()
    at = SubElement(e, "LomId"); at.set("Value", "0")
    SubElement(e, "Manual").set("Value", str(value))
    mi = SubElement(e, "MidiControllerRange")
    SubElement(mi, "Min").set("Value", "0")
    SubElement(mi, "Max").set("Value", "1")
    aut = SubElement(e, "AutomationTarget"); aut.set("Id", str(auto_id))
    mdt = SubElement(e, "ModulationTarget");  mdt.set("Id", str(mod_id))
    return e


def build_midi_clip(clip_id, notes_with_pitch, length_beats, name="Clip", color=0):
    """
    Build a <MidiClip> element.
    notes_with_pitch: list of (time, duration, velocity, pitch)
    """
    clip = Element("MidiClip")
    clip.set("Id", str(clip_id))
    clip.set("Time", "0")

    SubElement(clip, "LomId").set("Value", "0")
    SubElement(clip, "LomIdView").set("Value", "0")
    SubElement(clip, "CurrentStart").set("Value", "0")
    SubElement(clip, "CurrentEnd").set("Value", str(length_beats))
    SubElement(clip, "Loop").set("Value", "1")

    ln = SubElement(clip, "Loop")
    SubElement(ln, "LoopStart").set("Value", "0")
    SubElement(ln, "LoopEnd").set("Value", str(length_beats))
    SubElement(ln, "StartRelative").set("Value", "0")
    SubElement(ln, "LoopOn").set("Value", "true")
    SubElement(ln, "OutMarker").set("Value", str(length_beats))
    SubElement(ln, "HiddenLoopStart").set("Value", "0")
    SubElement(ln, "HiddenLoopEnd").set("Value", str(length_beats))

    SubElement(clip, "Name").set("Value", name)
    SubElement(clip, "Annotation").set("Value", "")
    SubElement(clip, "Color").set("Value", str(color))
    SubElement(clip, "LaunchMode").set("Value", "0")
    SubElement(clip, "LaunchQuantisation").set("Value", "0")

    vel_e = SubElement(clip, "Grid")
    SubElement(vel_e, "FixedNumerator").set("Value", "1")
    SubElement(vel_e, "FixedDenominator").set("Value", "16")
    SubElement(vel_e, "GridIntervalPixel").set("Value", "20")
    SubElement(vel_e, "Ntoles").set("Value", "2")
    SubElement(vel_e, "SnapToGrid").set("Value", "true")
    SubElement(vel_e, "Fixed").set("Value", "false")

    SubElement(clip, "FoldedState").set("Value", "false")
    SubElement(clip, "SelectedNoteExpression").set("Value", "0")
    SubElement(clip, "NoteEditorFoldInZoom").set("Value", "-1")
    SubElement(clip, "NoteEditorFoldInScroll").set("Value", "0")
    SubElement(clip, "NoteEditorFoldOutZoom").set("Value", "1344")
    SubElement(clip, "NoteEditorFoldOutScroll").set("Value", "-799")
    SubElement(clip, "NoteEditorFoldScaleZoom").set("Value", "-1")
    SubElement(clip, "NoteEditorFoldScaleScroll").set("Value", "0")
    SubElement(clip, "ScaleInformation")
    SubElement(clip, "IsWarped").set("Value", "true")
    SubElement(clip, "TakeLanes")
    SubElement(clip, "NoteSpellingPreference").set("Value", "3")
    SubElement(clip, "PreferFlatRootNote").set("Value", "false")
    SubElement(clip, "ExpressionGrid")

    # Group by pitch
    pitch_map = {}
    for (t, dur, vel, pitch) in notes_with_pitch:
        pitch_map.setdefault(pitch, []).append((t, dur, vel))

    notes_el = SubElement(clip, "Notes")
    keytrack_list = SubElement(notes_el, "KeyTracks")
    for pitch in sorted(pitch_map.keys()):
        kt = SubElement(keytrack_list, "KeyTrack")
        kt.set("Id", str(new_id()))
        SubElement(kt, "MidiKey").set("Value", str(pitch))
        notes_inner = SubElement(kt, "Notes")
        for (t, dur, vel) in pitch_map[pitch]:
            ne = SubElement(notes_inner, "MidiNoteEvent")
            ne.set("Time", f"{t:.6f}")
            ne.set("Duration", f"{dur:.6f}")
            ne.set("Velocity", str(int(vel)))
            ne.set("VelocityDeviation", "0")
            ne.set("ReleaseVelocity", "64")
            ne.set("OffVelocity", "64")
            ne.set("Probability", "1")
            ne.set("IsEnabled", "true")
            ne.set("NoteId", str(new_id()))
    SubElement(notes_el, "PerNoteEventStore")
    SubElement(notes_el, "NoteIdGenerator").set("NextId", str(_id_counter + 1))

    SubElement(clip, "BankSelectCoarse").set("Value", "-1")
    SubElement(clip, "BankSelectFine").set("Value", "-1")
    SubElement(clip, "ProgramChange").set("Value", "-1")
    SubElement(clip, "NoteEditorViewState")

    return clip


def drum_notes_to_pitched(note_list, pitch):
    """Convert (time, duration, velocity) list → (time, duration, velocity, pitch)"""
    return [(t, d, v, pitch) for (t, d, v) in note_list]


def build_mixer(volume=1.0, pan=0.0, sends_count=3):
    mx = Element("Mixer")
    SubElement(mx, "LomId").set("Value", "0")
    SubElement(mx, "LomIdView").set("Value", "0")

    is_ex = SubElement(mx, "IsExpanded"); is_ex.set("Value", "true")
    SubElement(mx, "On").set("Value", "true")
    SubElement(mx, "ModulationSourceCount").set("Value", "0")

    p = SubElement(mx, "ParametersListWrapper"); p.set("LomId", "0")
    SubElement(mx, "Pointee").set("Id", str(new_id()))
    SubElement(mx, "LastSelectedTimeableIndex").set("Value", "0")
    SubElement(mx, "LastSelectedClipEnvelopeIndex").set("Value", "0")

    vol = SubElement(mx, "Volume")
    SubElement(vol, "LomId").set("Value", "0")
    SubElement(vol, "Manual").set("Value", str(volume))
    at1 = SubElement(vol, "AutomationTarget"); at1.set("Id", str(new_id()))
    mt1 = SubElement(vol, "ModulationTarget"); mt1.set("Id", str(new_id()))

    pn = SubElement(mx, "Pan")
    SubElement(pn, "LomId").set("Value", "0")
    SubElement(pn, "Manual").set("Value", str(pan))
    at2 = SubElement(pn, "AutomationTarget"); at2.set("Id", str(new_id()))
    mt2 = SubElement(pn, "ModulationTarget"); mt2.set("Id", str(new_id()))

    SubElement(mx, "SpeakerOn").set("Value", "true")
    SubElement(mx, "SoloSink").set("Value", "false")
    SubElement(mx, "PanMode").set("Value", "0")

    sends_el = SubElement(mx, "Sends")
    for i in range(sends_count):
        send = SubElement(sends_el, "TrackSendHolder")
        send.set("Id", str(i))
        s = SubElement(send, "Send")
        SubElement(s, "LomId").set("Value", "0")
        send_val = 0.0 if i > 0 else 0.0  # all sends off by default
        SubElement(s, "Manual").set("Value", str(send_val))
        ats = SubElement(s, "AutomationTarget"); ats.set("Id", str(new_id()))
        mts = SubElement(s, "ModulationTarget"); mts.set("Id", str(new_id()))
        SubElement(send, "Active").set("Value", "true")

    SubElement(mx, "Cue").set("Value", "0")
    return mx


def build_midi_track(track_id, name, color, clip_notes, clip_length,
                     clip_name="Clip", volume=1.0, pan=0.0, sends_count=3,
                     is_drum=False):
    """Full MidiTrack element"""
    trk = Element("MidiTrack")
    trk.set("Id", str(track_id))
    trk.set("LomId", "0")
    trk.set("LomIdView", "0")
    trk.set("IsContentSelectedInDocument", "false")
    trk.set("PreferredContentViewMode", "0")
    SubElement(trk, "TrackDelay")

    # Name
    nm = SubElement(trk, "Name")
    SubElement(nm, "EffectiveName").set("Value", name)
    SubElement(nm, "UserName").set("Value", "")
    SubElement(nm, "Annotation").set("Value", "")
    SubElement(nm, "MemorizedFirstClipName").set("Value", "")

    SubElement(trk, "Color").set("Value", str(color))

    # AutomationEnvelopes
    SubElement(trk, "AutomationEnvelopes")

    # TrackGroupId
    SubElement(trk, "TrackGroupId").set("Value", "-1")
    SubElement(trk, "TrackUnfolded").set("Value", "true")
    SubElement(trk, "DevicesListWrapper").set("LomId", "0")
    SubElement(trk, "ClipSlotsListWrapper").set("LomId", "0")
    SubElement(trk, "ViewData")

    # ClipSlotList with our clip in slot 0
    csl = SubElement(trk, "ClipSlotList")
    for slot_idx in range(8):
        cs_holder = SubElement(csl, "ClipSlot")
        cs_holder.set("Id", str(slot_idx))
        cs = SubElement(cs_holder, "ClipSlot")
        SubElement(cs, "LomId").set("Value", "0")
        SubElement(cs, "HasStop").set("Value", "true")
        SubElement(cs, "NeedRerecord").set("Value", "false")
        val_el = SubElement(cs, "Value")
        if slot_idx == 0 and clip_notes:
            clip_el = build_midi_clip(
                new_id(), clip_notes, clip_length, clip_name, color
            )
            val_el.append(clip_el)

    SubElement(trk, "MonitoringEnum").set("Value", "1")
    SubElement(trk, "CurrentInputRoutingType").set("Value", "-1")
    SubElement(trk, "CurrentInputSubRoutingType").set("Value", "0")
    SubElement(trk, "CurrentOutputRoutingType").set("Value", "0")
    SubElement(trk, "CurrentOutputSubRoutingType").set("Value", "0")

    # DeviceChain
    dc = SubElement(trk, "DeviceChain")
    SubElement(dc, "AutomationLanes")
    SubElement(dc, "ClipEnvelopeChooserViewState")

    # Input/Output
    ias = SubElement(dc, "AudioInputRouting")
    SubElement(ias, "Target").set("Value", "AudioIn/None")
    SubElement(ias, "UpperDisplayString").set("Value", "No Input")
    SubElement(ias, "LowerDisplayString").set("Value", "")

    mir = SubElement(dc, "MidiInputRouting")
    SubElement(mir, "Target").set("Value", "MidiIn/External.All/-1")
    SubElement(mir, "UpperDisplayString").set("Value", "Ext. In")
    SubElement(mir, "LowerDisplayString").set("Value", "All Channels")

    aor = SubElement(dc, "AudioOutputRouting")
    SubElement(aor, "Target").set("Value", "AudioOut/Master")
    SubElement(aor, "UpperDisplayString").set("Value", "Master")
    SubElement(aor, "LowerDisplayString").set("Value", "")

    mor = SubElement(dc, "MidiOutputRouting")
    SubElement(mor, "Target").set("Value", "MidiOut/None")
    SubElement(mor, "UpperDisplayString").set("Value", "No Output")
    SubElement(mor, "LowerDisplayString").set("Value", "")

    # Mixer
    mx = build_mixer(volume, pan, sends_count)
    dc.append(mx)

    SubElement(dc, "MainSequencer")
    SubElement(dc, "FreezeSequencer")
    SubElement(dc, "DeviceChain").set  # will just add Devices below
    dev = SubElement(dc, "Devices")  # placeholder; user adds instruments here

    SubElement(dc, "SignalModulations")

    SubElement(trk, "SavedPlayingSlot").set("Value", "-1")
    SubElement(trk, "SavedPlayingOffset").set("Value", "0")
    SubElement(trk, "Freeze").set("Value", "false")
    SubElement(trk, "VelocityDetail").set("Value", "0")
    SubElement(trk, "NeedArrangerRefreeze").set("Value", "true")
    SubElement(trk, "PostProcessFreezeClips").set("Value", "0")
    SubElement(trk, "DeviceChainOvertakeEnabled").set("Value", "false")

    return trk


def build_return_track(track_id, name, color, sends_count=3):
    trk = Element("ReturnTrack")
    trk.set("Id", str(track_id))
    trk.set("LomId", "0")
    trk.set("LomIdView", "0")
    trk.set("IsContentSelectedInDocument", "false")
    trk.set("PreferredContentViewMode", "0")

    nm = SubElement(trk, "Name")
    SubElement(nm, "EffectiveName").set("Value", name)
    SubElement(nm, "UserName").set("Value", "")
    SubElement(nm, "Annotation").set("Value", "")
    SubElement(nm, "MemorizedFirstClipName").set("Value", "")

    SubElement(trk, "Color").set("Value", str(color))
    SubElement(trk, "AutomationEnvelopes")
    SubElement(trk, "TrackGroupId").set("Value", "-1")
    SubElement(trk, "TrackUnfolded").set("Value", "true")
    SubElement(trk, "DevicesListWrapper").set("LomId", "0")
    SubElement(trk, "ClipSlotsListWrapper").set("LomId", "0")
    SubElement(trk, "ViewData")

    dc = SubElement(trk, "DeviceChain")
    SubElement(dc, "AutomationLanes")
    SubElement(dc, "ClipEnvelopeChooserViewState")

    aor = SubElement(dc, "AudioInputRouting")
    SubElement(aor, "Target").set("Value", "AudioIn/None")
    SubElement(aor, "UpperDisplayString").set("Value", "No Input")
    SubElement(aor, "LowerDisplayString").set("Value", "")

    mor = SubElement(dc, "AudioOutputRouting")
    SubElement(mor, "Target").set("Value", "AudioOut/Master")
    SubElement(mor, "UpperDisplayString").set("Value", "Master")
    SubElement(mor, "LowerDisplayString").set("Value", "")

    mx = build_mixer(0.8, 0.0, sends_count)
    dc.append(mx)

    SubElement(dc, "Devices")
    SubElement(dc, "SignalModulations")

    SubElement(trk, "Freeze").set("Value", "false")
    return trk


# ─────────────────────────────────────────────
# Master Track
# ─────────────────────────────────────────────

def build_master_track():
    mt = Element("MasterTrack")
    mt.set("Id", str(new_id()))
    mt.set("LomId", "0")

    nm = SubElement(mt, "Name")
    SubElement(nm, "EffectiveName").set("Value", "Master")
    SubElement(nm, "UserName").set("Value", "")
    SubElement(nm, "Annotation").set("Value", "")
    SubElement(nm, "MemorizedFirstClipName").set("Value", "")

    SubElement(mt, "Color").set("Value", "0")
    SubElement(mt, "AutomationEnvelopes")
    SubElement(mt, "TrackGroupId").set("Value", "-1")
    SubElement(mt, "TrackUnfolded").set("Value", "true")
    SubElement(mt, "DevicesListWrapper").set("LomId", "0")
    SubElement(mt, "ClipSlotsListWrapper").set("LomId", "0")
    SubElement(mt, "ViewData")

    dc = SubElement(mt, "DeviceChain")
    SubElement(dc, "AutomationLanes")

    aor = SubElement(dc, "AudioOutputRouting")
    SubElement(aor, "Target").set("Value", "AudioOut/Master")
    SubElement(aor, "UpperDisplayString").set("Value", "Master Out")
    SubElement(aor, "LowerDisplayString").set("Value", "")

    mx = SubElement(dc, "Mixer")
    SubElement(mx, "LomId").set("Value", "0")
    vol = SubElement(mx, "Volume")
    SubElement(vol, "LomId").set("Value", "0")
    SubElement(vol, "Manual").set("Value", "1.0")
    at = SubElement(vol, "AutomationTarget"); at.set("Id", str(new_id()))

    pn = SubElement(mx, "Pan")
    SubElement(pn, "LomId").set("Value", "0")
    SubElement(pn, "Manual").set("Value", "0")
    at2 = SubElement(pn, "AutomationTarget"); at2.set("Id", str(new_id()))

    SubElement(mx, "Tempo").set("Value", "138")
    SubElement(dc, "Devices")
    return mt


# ─────────────────────────────────────────────
# Top-level LiveSet / Ableton root
# ─────────────────────────────────────────────

def build_als(output_path="trance_template.als", bpm=138):
    root = Element("Ableton")
    root.set("MajorVersion", "11")
    root.set("MinorVersion", "11.0.2c3")
    root.set("SchemaChangeCount", "3")
    root.set("Creator", "Ableton Live 11.0.2")
    root.set("Revision", "")

    liveset = SubElement(root, "LiveSet")

    # ── Tempo & Time Sig ─────────────────────
    tempo_el = SubElement(liveset, "Tempo")
    SubElement(tempo_el, "LomId").set("Value", "0")
    SubElement(tempo_el, "Manual").set("Value", str(bpm))
    at_t = SubElement(tempo_el, "AutomationTarget"); at_t.set("Id", str(new_id()))
    mt_t = SubElement(tempo_el, "ModulationTarget"); mt_t.set("Id", str(new_id()))

    ts = SubElement(liveset, "TimeSignature")
    ts_id = SubElement(ts, "TimeSignatures")
    tse = SubElement(ts_id, "RemoteableTimeSignature")
    tse.set("Id", "0")
    SubElement(tse, "Numerator").set("Value", "4")
    SubElement(tse, "Denominator").set("Value", "4")
    SubElement(tse, "Time").set("Value", "0")

    # ── Global groove / root key / scale ─────
    SubElement(liveset, "GlobalGrooveAmount").set("Value", "1.0")
    SubElement(liveset, "KeySignatures")

    scale = SubElement(liveset, "ScaleInformation")
    SubElement(scale, "RootNote").set("Value", "9")   # A
    SubElement(scale, "Name").set("Value", "Minor")

    SubElement(liveset, "InKey").set("Value", "true")
    SubElement(liveset, "SmpteFormat").set("Value", "0")

    # ── Loop / punch ─────────────────────────
    loop = SubElement(liveset, "Loop")
    SubElement(loop, "LoopStart").set("Value", "0")
    SubElement(loop, "LoopEnd").set("Value", "32")
    SubElement(loop, "LoopOn").set("Value", "false")
    SubElement(loop, "OutMarker").set("Value", "32")
    SubElement(loop, "HiddenLoopStart").set("Value", "0")
    SubElement(loop, "HiddenLoopEnd").set("Value", "32")

    # ── Tracks ───────────────────────────────
    #
    # Drum pattern notes (all pitched relative to GM drum map for display,
    # though without a drum rack loaded Live will show raw pitch numbers)
    # Standard GM: 36=kick, 38=snare, 42=closed HH, 46=open HH
    #
    # Chord voicings:  all in (time, dur, vel, pitch) format

    track_defs = [
        # (name,  color_key,  clip_notes_fn,  clip_len, clip_name)
        ("Kick",        "kick",  drum_notes_to_pitched(four_on_floor(2), 36),       8, "4onfloor"),
        ("Clap",        "clap",  drum_notes_to_pitched(clap_pattern(2), 38),        8, "Clap 2&4"),
        ("Closed HH",   "hh",    drum_notes_to_pitched(closed_hh_pattern(2), 42),   8, "CHH 16ths"),
        ("Open HH",     "hh",    drum_notes_to_pitched(open_hh_pattern(2), 46),     8, "OHH off-beat"),
        ("Bass",        "bass",  rolling_bass(2, 45),                               8, "Roll Bass"),
        ("Supersaw",    "lead",  supersaw_melody(2, 69),                            8, "Lead Melody"),
        ("Pad",         "pad",   pad_chords(4, 57),                                16, "Am-F-C-G"),
        ("Pluck",       "pluck", pluck_arp(2, 69),                                  8, "Arp 16th"),
    ]

    returns = [
        ("Reverb",  "return"),
        ("Delay",   "return"),
        ("Chorus",  "return"),
    ]
    num_returns = len(returns)

    tracks_el = SubElement(liveset, "Tracks")

    for i, (name, color_key, notes, clip_len, clip_name) in enumerate(track_defs):
        trk = build_midi_track(
            track_id=i,
            name=name,
            color=COLORS[color_key],
            clip_notes=notes,
            clip_length=clip_len,
            clip_name=clip_name,
            volume=1.0,
            pan=0.0,
            sends_count=num_returns,
        )
        tracks_el.append(trk)

    for i, (rname, rcolor_key) in enumerate(returns):
        rt = build_return_track(
            track_id=100 + i,
            name=rname,
            color=COLORS[rcolor_key],
            sends_count=num_returns,
        )
        tracks_el.append(rt)

    # Master
    master = build_master_track()
    liveset.append(master)

    # ── Pre-Hearing / Scene list ───────────────
    SubElement(liveset, "PreHearTrack")

    scenes = SubElement(liveset, "Scenes")
    for i in range(8):
        sc = SubElement(scenes, "Scene")
        sc.set("Id", str(i))
        SubElement(sc, "Name").set("Value", f"Scene {i+1}" if i > 0 else "MAIN")
        SubElement(sc, "Annotation").set("Value", "")
        SubElement(sc, "Color").set("Value", "-1")
        SubElement(sc, "Tempo").set("Value", str(bpm))
        SubElement(sc, "IsTempoEnabled").set("Value", "false")
        SubElement(sc, "TimeSignatureId").set("Value", "0")
        SubElement(sc, "IsTimeSignatureEnabled").set("Value", "false")
        SubElement(sc, "LomId").set("Value", "0")
        SubElement(sc, "ClipSlotsListWrapper").set("LomId", "0")

    # Misc required fields
    SubElement(liveset, "Transport")
    SubElement(liveset, "SongMasterValues")
    SubElement(liveset, "GlobalQuantisation").set("Value", "4")
    SubElement(liveset, "AutoQuantisation").set("Value", "0")

    SubElement(liveset, "Grid")
    SubElement(liveset, "ScaleMidi").set("Value", "false")
    SubElement(liveset, "CanShowScaleMidi").set("Value", "false")
    SubElement(liveset, "UseWarper").set("Value", "true")
    SubElement(liveset, "VideoWindowRect")
    SubElement(liveset, "ShowVideoWindow").set("Value", "false")
    SubElement(liveset, "TrackHeaderWidth").set("Value", "155")
    SubElement(liveset, "ViewStateSessionMixerHeight").set("Value", "120")
    SubElement(liveset, "MixerSectionExtents")
    SubElement(liveset, "AutoColorPickerForPlayerAndGroupTracks").set("Value", "true")
    SubElement(liveset, "ContentSplitterPosition").set("Value", "1126")
    SubElement(liveset, "ViewStates")
    SubElement(liveset, "SendsPre").set("Value", "false")

    # Serialize
    raw = tostring(root, encoding="unicode")
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw
    xml_bytes = xml_str.encode("utf-8")

    with gzip.open(output_path, "wb") as f:
        f.write(xml_bytes)

    print(f"✅  Saved: {output_path}")
    print(f"    Tracks: {len(track_defs)} MIDI + {num_returns} Returns + Master")
    print(f"    BPM:    {bpm}")
    print(f"    Key:    A minor")
    print(f"    Total XML IDs allocated: {_id_counter}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate an Ableton 11 trance template .als")
    parser.add_argument("-o", "--output", default="trance_template.als", help="Output .als path")
    parser.add_argument("--bpm", type=int, default=138, help="BPM (default 138)")
    args = parser.parse_args()
    build_als(args.output, args.bpm)
