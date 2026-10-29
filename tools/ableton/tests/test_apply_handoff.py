"""PRP 15b: the trancegen handoff applier, driven against the fake daemon. Nothing here opens a socket or Live."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import handoff_applier as ha
from fake_daemon import FakeLive, FakeOSC, Track, eq_eight, snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "handoff_3x3"
FAST = (0.0, 0.0, 0.0)  # no real backoff in tests


def folder(tmp_path: Path, devices: list[dict] | None = None) -> Path:
    """A copy of the 3-track, 3-scene fixture, optionally with device files added."""
    dst = tmp_path / "handoff"
    shutil.copytree(FIXTURE, dst)
    for d in devices or []:
        (dst / "devices").mkdir(exist_ok=True)
        (dst / "devices" / f"{d['track']} {d['device']['name']}.json").write_text(json.dumps(d), encoding="utf-8")
    return dst


def pad_eq_file(if_missing="ask_to_add") -> dict:
    return {
        "format": "trancegen-device/1",
        "why": "PAD covers LEAD 1-3 kHz in Drop 1 (38% of LEAD's energy there).",
        "evidence": [{"metric": "masking_share", "value": 0.38, "expected_range": [0, 0.2], "bars": [97, 128]}],
        "track": "PAD",
        "device": {"class": "Eq8", "display": "EQ Eight", "name": "TG Pad EQ", "index_among_same": 0, "if_missing": if_missing, "native": True},
        "params": [
            {"live_name": "3 Filter On A", "value": 1, "display": "On"},
            {"live_name": "3 Frequency A", "display": "2.20 kHz"},
            {"live_name": "3 Gain A", "display": "-3.0 dB"},
            {"live_name": "3 Filter Type A", "display": "Bell"},
        ],
    }


def empty_live() -> FakeLive:
    return FakeLive(tracks=[], scenes=[], tempo=120.0)


def run(osc: FakeOSC, path: Path, tmp_path: Path, **kw) -> ha.Receipt:
    app = ha.Applier(osc, path, calibration_dir=tmp_path / "cal", backoff=FAST, **kw)
    return app.run()


# ---------------------------------------------------------------- probe

def test_probe_failure_changes_nothing(tmp_path):
    live = empty_live()
    osc = FakeOSC(live, unsupported={"/live/clip/get/notes"})   # a build without clip notes: add_notes is missing
    before = snapshot(live)
    receipt = run(osc, folder(tmp_path), tmp_path)
    assert receipt.stopped and "add_notes" in receipt.stopped and "midi/" in receipt.stopped
    assert osc.writes == []
    assert snapshot(live) == before


def test_probe_lists_every_capability_of_the_manifest(tmp_path):
    osc = FakeOSC(empty_live())
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    result = ha.probe(osc, manifest["requires"], backoff=FAST)
    assert result.missing == []
    assert set(result.checked) == set(manifest["requires"])


# ---------------------------------------------------------------- apply and rerun

def test_apply_then_rerun_gives_the_same_state(tmp_path):
    live = empty_live()
    osc = FakeOSC(live)
    path = folder(tmp_path)
    first = run(osc, path, tmp_path)
    assert first.stopped is None, first.stopped
    assert [t.name for t in live.tracks] == ["LEAD", "PAD", "BASS"]
    assert [s["name"] for s in live.scenes] == ["intro", "drop1", "outro"]
    assert live.tempo == 138.0
    lead, pad, bass = live.tracks
    assert sorted(lead.clips) == [0, 1] and len(lead.clips[0]["notes"]) == 16 and lead.clips[0]["name"] == "LEAD L1 lp"
    assert sorted(pad.clips) == [0, 1, 2] and len(pad.clips[2]["notes"]) == 6
    assert sorted(bass.clips) == [1, 2] and len(bass.clips[1]["notes"]) == 32
    assert sorted((c["name"], c["time"]) for c in live.cues) == [("drop1", 32.0), ("intro", 0.0), ("outro", 64.0)]
    assert all(v["ok"] for v in first.verify), first.verify
    after_first = snapshot(live)

    osc.writes.clear()
    second = run(osc, path, tmp_path)
    assert second.stopped is None
    assert snapshot(live) == after_first
    created = [a for a, _ in osc.writes if a.endswith(("create_midi_track", "create_scene", "add_or_delete"))]
    assert created == [], created   # nothing is made twice


def test_write_clip_replaces_the_slot(tmp_path):
    live = empty_live()
    osc = FakeOSC(live)
    path = folder(tmp_path)
    run(osc, path, tmp_path)
    live.tracks[0].clips[1]["notes"].append((60, 0.0, 1.0, 100, 0))   # someone edited the clip in Live
    run(osc, path, tmp_path)
    assert len(live.tracks[0].clips[1]["notes"]) == 16   # the slot holds the handoff's clip again


def test_notes_go_out_in_chunks_of_about_100(tmp_path):
    path = folder(tmp_path)
    h = json.loads((path / "handoff.json").read_text(encoding="utf-8"))
    big = [[60 + (k % 12), k * 0.25, 0.25, 100] for k in range(250)]
    h["steps"] = [s for s in h["steps"] if s["op"] != "write_clip" or s["track"] != "LEAD"]
    h["steps"].insert(8, {"op": "write_clip", "track": "LEAD", "scene": 0, "name": "big", "length_beats": 64, "notes": big})
    h["verify"] = [{"check": "clip_note_count", "track": "LEAD", "scene": 0, "expect": 250}]
    (path / "handoff.json").write_text(json.dumps(h), encoding="utf-8")
    live = empty_live()
    osc = FakeOSC(live)
    receipt = run(osc, path, tmp_path)
    assert receipt.stopped is None
    adds = [args for a, args in osc.writes if a == "/live/clip/add/notes" and args[0] == 0 and args[1] == 0]
    assert [(len(args) - 2) // 5 for args in adds] == [100, 100, 50]
    assert len(live.tracks[0].clips[0]["notes"]) == 250
    assert receipt.verify[0]["ok"]


# ---------------------------------------------------------------- track resolution

def test_phantom_tracks_are_skipped(tmp_path):
    # track_names leaks the returns and the master: a return named PAD must not be taken for the PAD track
    live = FakeLive(tracks=[Track("LEAD")], returns=["PAD", "B Delay"], scenes=[], tempo=120.0)
    osc = FakeOSC(live)
    app = ha.Applier(osc, folder(tmp_path), calibration_dir=tmp_path / "cal", backoff=FAST)
    assert [t["name"] for t in app.real_tracks()] == ["LEAD"]
    receipt = app.run()
    assert receipt.stopped is None
    assert [t.name for t in live.tracks] == ["LEAD", "PAD", "BASS"]
    assert all(args[0] < 3 for a, args in osc.writes if a.startswith(("/live/track/", "/live/clip")))


# ---------------------------------------------------------------- devices

def test_device_missing_stops_with_the_exact_message(tmp_path):
    live = FakeLive(tracks=[Track("LEAD"), Track("PAD"), Track("BASS")], scenes=["intro", "drop1", "outro"])
    osc = FakeOSC(live)
    before = snapshot(live)
    receipt = run(osc, folder(tmp_path, [pad_eq_file()]), tmp_path, only={"devices"})
    assert receipt.stopped == "Add EQ Eight named TG Pad EQ to PAD, then rerun."
    assert snapshot(live) == before


def test_device_missing_with_skip_is_noted_not_fatal(tmp_path):
    live = FakeLive(tracks=[Track("LEAD"), Track("PAD"), Track("BASS")], scenes=["intro", "drop1", "outro"])
    osc = FakeOSC(live)
    receipt = run(osc, folder(tmp_path, [pad_eq_file("skip")]), tmp_path, only={"devices"})
    assert receipt.stopped is None
    assert any("TG Pad EQ" in n for n in receipt.notes)


def test_readout_matching_hits_the_display(tmp_path):
    pad = Track("PAD", devices=[eq_eight("TG Pad EQ")])
    live = FakeLive(tracks=[Track("LEAD"), pad, Track("BASS")], scenes=["intro", "drop1", "outro"])
    osc = FakeOSC(live)
    receipt = run(osc, folder(tmp_path, [pad_eq_file()]), tmp_path, only={"devices"})
    assert receipt.stopped is None, receipt.stopped
    eq = pad.devices[0]
    by_name = {p.name: p for p in eq.params}
    assert by_name["3 Filter On A"].display() == "On"
    assert by_name["3 Frequency A"].display() == "2.20 kHz"
    assert by_name["3 Gain A"].display() == "-3.0 dB"
    assert by_name["3 Filter Type A"].display() == "Bell"
    # the receipt keeps what each parameter was
    changes = {c["param"]: c for c in receipt.changes if c["op"] == "set_device_parameter"}
    assert changes["3 Frequency A"]["previous"] == 0.5 and changes["3 Frequency A"]["display"] == "2.20 kHz"
    # the readout mapping is cached per class
    cal = json.loads((tmp_path / "cal" / "Eq8.json").read_text(encoding="utf-8"))
    assert any(abs(pt["value"] - 2200.0) < 1 for pt in cal["3 Frequency A"])


def test_readout_matching_is_within_one_readout_step(tmp_path):
    # a target between two readouts lands on the nearer one, never further than one step away
    pad = Track("PAD", devices=[eq_eight("TG Pad EQ")])
    live = FakeLive(tracks=[pad], scenes=[])
    osc = FakeOSC(live)
    raw, shown = ha.match_display(osc, 0, 0, 3, "-3.04 dB", backoff=FAST)   # param 3: "3 Gain A" (0 is Device On)
    assert shown == "-3.0 dB" and abs(raw - 0.4) < 0.005   # -3 dB on a -15..15 linear curve is raw 0.4; one 0.1 dB step is 0.0033


def test_devices_and_mixer_are_not_applied_unless_asked(tmp_path):
    pad = Track("PAD", devices=[eq_eight("TG Pad EQ")])
    live = FakeLive(tracks=[Track("LEAD"), pad, Track("BASS")], scenes=["intro", "drop1", "outro"])
    osc = FakeOSC(live)
    receipt = run(osc, folder(tmp_path, [pad_eq_file()]), tmp_path)   # default: clips, locators, tempo
    assert receipt.stopped is None
    assert pad.devices[0].params[2].value == 0.5 and pad.volume == 0.85
    assert not any(a.startswith("/live/device/set") or a == "/live/track/set/volume" for a, _ in osc.writes)


# ---------------------------------------------------------------- mixer

def test_mixer_maps_db_to_the_fader_and_skips_returns(tmp_path):
    live = FakeLive(tracks=[Track("LEAD"), Track("PAD"), Track("BASS")], scenes=["intro", "drop1", "outro"])
    osc = FakeOSC(live)
    receipt = run(osc, folder(tmp_path), tmp_path, only={"mixer"})
    assert receipt.stopped is None, receipt.stopped
    assert live.tracks[0].volume == pytest.approx(0.85, abs=1e-6)      # 0 dB
    assert ha.fader_to_db(live.tracks[1].volume) == pytest.approx(-3.0, abs=0.05)
    assert any("return" in n.lower() for n in receipt.notes)


def test_fader_curve_anchors():
    assert ha.fader_to_db(0.85) == pytest.approx(0.0)
    assert ha.fader_to_db(1.0) == pytest.approx(6.0)
    assert ha.db_to_fader(ha.fader_to_db(0.3)) == pytest.approx(0.3, abs=1e-6)
    assert ha.db_to_fader(-70.0) == pytest.approx(0.0, abs=1e-3)


# ---------------------------------------------------------------- receipt and undo

def test_undo_restores_every_previous_value(tmp_path):
    pad = Track("PAD", devices=[eq_eight("TG Pad EQ")])
    live = FakeLive(tracks=[Track("LEAD"), pad], scenes=["intro"], tempo=120.0)
    live.tracks[0].clips[0] = {"name": "old lead", "length": 16.0, "notes": [(60, 0.0, 1.0, 90, 0)]}
    osc = FakeOSC(live)
    before = snapshot(live)
    path = folder(tmp_path, [pad_eq_file()])
    receipt = run(osc, path, tmp_path, only={"clips", "locators", "tempo", "devices", "mixer"})
    assert receipt.stopped is None, receipt.stopped
    assert snapshot(live) != before
    receipt_path = path / "receipt.json"
    assert receipt_path.exists()
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert data["changes"] and all("previous" in c for c in data["changes"])
    ha.undo(osc, receipt_path, backoff=FAST)
    assert snapshot(live) == before


# ---------------------------------------------------------------- freezes

def test_a_short_freeze_is_retried(tmp_path):
    live = empty_live()
    osc = FakeOSC(live, freeze_for=2)
    receipt = run(osc, folder(tmp_path), tmp_path)
    assert receipt.stopped is None
    assert live.tempo == 138.0


def test_a_long_freeze_stops_with_the_question(tmp_path):
    live = empty_live()
    osc = FakeOSC(live, freeze_for=50)
    receipt = run(osc, folder(tmp_path), tmp_path)
    assert receipt.stopped == ha.FROZEN
    assert receipt.stopped == "Is a dialog open or an export running?"


# ---------------------------------------------------------------- readouts

@pytest.mark.parametrize("text,value,unit", [
    ("2.20 kHz", 2200.0, "hz"), ("800 Hz", 800.0, "hz"), ("-3.0 dB", -3.0, "db"), ("35 %", 35.0, "%"),
    ("120 ms", 0.12, "s"), ("1.50 s", 1.5, "s"), ("On", 1.0, "onoff"), ("Off", 0.0, "onoff"), ("Bell", None, "Bell"),
])
def test_parse_display(text, value, unit):
    assert ha.parse_display(text) == (value, unit)


# ---------------------------------------------------------------- verify and record

def test_verify_flags_a_wrong_count(tmp_path):
    live = empty_live()
    osc = FakeOSC(live)
    path = folder(tmp_path)
    run(osc, path, tmp_path)
    live.tracks[1].clips[0]["notes"].pop()
    app = ha.Applier(osc, path, calibration_dir=tmp_path / "cal", backoff=FAST)
    rows = app.verify()
    bad = [r for r in rows if not r["ok"]]
    assert len(bad) == 1 and bad[0]["track"] == "PAD" and bad[0]["got"] == 5


def test_record_fires_scenes_in_arrangement_order(tmp_path):
    live = empty_live()
    osc = FakeOSC(live)
    path = folder(tmp_path)
    app = ha.Applier(osc, path, calibration_dir=tmp_path / "cal", backoff=FAST)
    app.run()
    waits: list[float] = []
    app.record(confirm=lambda text: True, sleep=waits.append)
    assert [s for s, _ in live.fired] == [0, 1, 2]
    assert [t for _, t in live.fired] == [0.0, 32.0, 64.0]
    assert waits == pytest.approx([32 * 60 / 138.0] * 3)
    assert live.record_mode == 0 and live.playing is False


def test_record_needs_a_yes(tmp_path):
    live = empty_live()
    osc = FakeOSC(live)
    app = ha.Applier(osc, folder(tmp_path), calibration_dir=tmp_path / "cal", backoff=FAST)
    app.run()
    app.record(confirm=lambda text: False, sleep=lambda s: None)
    assert live.fired == [] and live.record_mode == 0


def test_only_filter_limits_the_steps(tmp_path):
    live = empty_live()
    osc = FakeOSC(live)
    receipt = run(osc, folder(tmp_path), tmp_path, only={"tempo"})
    assert receipt.stopped is None
    assert live.tempo == 138.0 and live.tracks == [] and live.cues == []
