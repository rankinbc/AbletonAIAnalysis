"""Probe which AbletonOSC endpoints respond in THIS Live/AbletonOSC build, and
show sample values. Grouped by usefulness for music analysis.

Run after any export has finished (export freezes the OSC API):
    python tools/ableton/probe_capabilities.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ableton_osc_client import AbletonOSC, AbletonError  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# (label, address, args)
SONG = [
    ("tempo (BPM)", "/live/song/get/tempo", []),
    ("time sig numerator", "/live/song/get/signature_numerator", []),
    ("time sig denominator", "/live/song/get/signature_denominator", []),
    ("scale name", "/live/song/get/scale_name", []),
    ("scale mode", "/live/song/get/scale_mode", []),
    ("root note", "/live/song/get/root_note", []),
    ("is playing", "/live/song/get/is_playing", []),
    ("song length", "/live/song/get/song_length", []),
    ("current time", "/live/song/get/current_song_time", []),
    ("loop start", "/live/song/get/loop_start", []),
    ("loop length", "/live/song/get/loop_length", []),
    ("groove amount", "/live/song/get/groove_amount", []),
    ("num scenes", "/live/song/get/num_scenes", []),
    ("track names", "/live/song/get/track_names", []),
]

TRACK = [  # tested on track 0
    ("name", "/live/track/get/name", [0]),
    ("color", "/live/track/get/color", [0]),
    ("has_midi_input (MIDI track?)", "/live/track/get/has_midi_input", [0]),
    ("is foldable (group?)", "/live/track/get/is_foldable", [0]),
    ("is grouped", "/live/track/get/is_grouped", [0]),
    ("num devices", "/live/track/get/num_devices", [0]),
    ("playing slot index", "/live/track/get/playing_slot_index", [0]),
    ("fired slot index", "/live/track/get/fired_slot_index", [0]),
    ("send 0 level", "/live/track/get/send", [0, 0]),
]

CLIP = [  # tested on (track, scene) = (0,0)
    ("clip_slot has_clip", "/live/clip_slot/get/has_clip", [0, 0]),
    ("clip name", "/live/clip/get/name", [0, 0]),
    ("clip length", "/live/clip/get/length", [0, 0]),
    ("clip is_midi_clip", "/live/clip/get/is_midi_clip", [0, 0]),
    ("clip gain", "/live/clip/get/gain", [0, 0]),
    ("clip color", "/live/clip/get/color", [0, 0]),
]


def run(osc, group, title):
    print(f"\n=== {title} ===")
    ok = {}
    for label, addr, args in group:
        try:
            data = osc.query(addr, args)
            s = str(data)
            print(f"  OK   {label:34s} {addr} {args} -> {s[:60]}")
            ok[addr] = data
        except AbletonError as e:
            msg = str(e).split(":")[-1].strip()
            print(f"  --   {label:34s} {addr} {args} -> [{msg}]")
    return ok


def find_midi_clip_and_notes(osc, num_tracks):
    """Scan clip slots for a MIDI clip with notes and dump a sample."""
    print("\n=== MIDI note extraction (the analysis payload) ===")
    for ti in range(num_tracks):
        for si in range(8):  # check first 8 scenes
            has = osc.try_query("/live/clip_slot/get/has_clip", [ti, si])
            if not has or not has[-1]:
                continue
            is_midi = osc.try_query("/live/clip/get/is_midi_clip", [ti, si])
            if not is_midi or not is_midi[-1]:
                continue
            name = osc.try_query("/live/clip/get/name", [ti, si])
            notes = osc.try_query("/live/clip/get/notes", [ti, si])
            nm = name[-1] if name else "?"
            if notes is None:
                print(f"  track {ti} scene {si} '{nm}': /live/clip/get/notes "
                      f"NOT supported in this build")
                return
            # notes payload is [track, scene, pitch, start, dur, vel, mute, ...]
            body = notes[2:] if len(notes) > 2 else []
            ncount = len(body) // 5
            print(f"  MIDI clip: track {ti} scene {si} '{nm}' -> {ncount} notes")
            for k in range(min(ncount, 8)):
                p, st, du, ve, mu = body[k * 5:k * 5 + 5]
                print(f"      pitch={p} start={st} dur={du} vel={ve} mute={mu}")
            print("  (pitch=MIDI note number, start/dur in beats, vel 0-127)")
            return
    print("  No MIDI clips found in first 8 scenes of any track.")


def main():
    with AbletonOSC() as osc:
        song = run(osc, SONG, "SONG / global (musical context)")
        run(osc, TRACK, "TRACK 0 (per-track metadata)")
        run(osc, CLIP, "CLIP (0,0) (per-clip metadata)")
        # bound track scan: track_names length if available, else 28
        names = song.get("/live/song/get/track_names")
        num_tracks = len(names) if names else 28
        find_midi_clip_and_notes(osc, num_tracks)


if __name__ == "__main__":
    main()
