# How to apply this handoff

Folder: `C:\Users\badmin\AppData\Local\Temp\h2t_handoff_ujip285c\s15b\handoff\1`
Written by trancegen with clips, locators, tempo, mixer on.

1. Check that Live is open with the set you mean, the OSC daemon is running and AbletonOSC responds.
2. Run `python tools/ableton/apply_handoff.py "C:\Users\badmin\AppData\Local\Temp\h2t_handoff_ujip285c\s15b\handoff\1" --probe`, read what it says, then the same without `--probe`.
3. Report the verify results and the receipt it writes.
4. Never apply `devices/` or `mixer.json` unless the user says so in this conversation.
5. If a capability in `manifest.requires` is missing, stop and point the user to `midi/`: one file per part and `song.mid`.

## Capabilities needed

- set_tempo
- create_midi_track
- create_scene
- create_clip
- add_notes
- delete_clip
- add_locator
- set_track_volume
- set_track_pan
- set_send
- set_mute

## Files

- `HOW_TO_APPLY.md`
- `handoff.json`
- `manifest.json`
- `midi/01 LEAD.mid`
- `midi/02 PAD.mid`
- `midi/03 BASS.mid`
- `midi/song.mid`
- `mixer.json`
- `report.json`
- `sounds.md`
- `words.md`

## By hand

- Master chain and return FX are never written: they are not reachable over OSC.
- Arrangement: record or drag the scenes in the order handoff.json gives under arrangement.

Arrangement: `handoff.json` `arrangement` is the scene order; record or drag the scenes into the Arrangement in that order.
