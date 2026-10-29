"""An in-process stand-in for the OSC daemon plus Live: the applier's tests drive this instead of sockets.

It answers the AbletonOSC addresses the applier uses, with Live's quirks: `track_names` leaks the return tracks
and the master past the real count, an index past the count fails on `devices/name` with "Index out of range",
device parameters have a raw 0..1 value and a readout string Live would show, and any address can be declared
unsupported or frozen to simulate an old build or a modal dialog.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ableton_osc_client import AbletonError  # noqa: E402


class Param:
    """One device parameter: a raw 0..1 value (or min..max) and the readout Live shows for it."""

    def __init__(self, name, curve="linear", lo=0.0, hi=1.0, unit="", value=0.0, decimals=1, modes=None):
        self.name = name
        self.curve = curve      # linear | exp | onoff | modes
        self.lo, self.hi = lo, hi
        self.unit = unit
        self.value = value
        self.decimals = decimals
        self.modes = modes or []

    def display(self) -> str:
        if self.curve == "onoff":
            return "On" if self.value >= 0.5 else "Off"
        if self.curve == "modes":
            return self.modes[min(len(self.modes) - 1, int(self.value * len(self.modes)))]
        if self.curve == "exp":   # frequency-like: 20 Hz .. 20 kHz over raw 0..1
            hz = self.lo * (self.hi / self.lo) ** self.value
            if hz >= 1000:
                return f"{hz / 1000:.2f} kHz"
            return f"{hz:.0f} Hz" if hz >= 100 else f"{hz:.1f} Hz"
        shown = self.lo + (self.hi - self.lo) * self.value
        return f"{shown:.{self.decimals}f} {self.unit}".strip()


class Device:
    def __init__(self, class_name, name=None, params=None):
        self.class_name = class_name
        self.name = name or class_name
        self.params = [Param("Device On", "onoff", value=1.0)] + list(params or [])


class Track:
    def __init__(self, name, kind="midi", devices=None):
        self.name = name
        self.kind = kind
        self.devices = list(devices or [])
        self.clips: dict[int, dict] = {}
        self.volume, self.panning, self.mute = 0.85, 0.0, 0
        self.sends: list[float] = []


class FakeLive:
    """The set behind the fake daemon."""

    def __init__(self, tracks=(), returns=("A Reverb", "B Delay"), scenes=(), tempo=120.0):
        self.tracks = list(tracks)
        self.returns = list(returns)
        self.scenes = [{"name": n} for n in scenes]
        self.tempo = tempo
        self.cues: list[dict] = []   # {"name", "time"}
        self.song_time = 0.0
        self.record_mode = 0
        self.playing = False
        self.fired: list[tuple[int, float]] = []   # (scene, song_time) in firing order
        for t in self.tracks:
            t.sends = [0.0] * len(self.returns)


class FakeOSC:
    """Speaks the client's `query(address, args)` contract over a FakeLive. `unsupported` addresses raise like a
    build without the handler; `freeze_for` makes the next N calls time out like Live behind a dialog."""

    def __init__(self, live: FakeLive, unsupported=(), freeze_for=0):
        self.live = live
        self.unsupported = set(unsupported)
        self.freeze_for = freeze_for
        self.calls: list[tuple[str, list]] = []
        self.writes: list[tuple[str, list]] = []

    # the client surface the applier uses
    def connect(self): ...
    def close(self): ...
    def __enter__(self): return self
    def __exit__(self, *exc): ...

    def try_query(self, address, args=None, default=None):
        try:
            return self.query(address, args)
        except AbletonError:
            return default

    def _track(self, i):
        if not 0 <= int(i) < len(self.live.tracks):
            raise AbletonError(f"/live/track: Index out of range")
        return self.live.tracks[int(i)]

    def query(self, address, args=None):
        args = list(args or [])
        self.calls.append((address, args))
        if self.freeze_for > 0:
            self.freeze_for -= 1
            raise AbletonError(f"Timeout waiting for reply to {address}")
        if address in self.unsupported:
            # a build without the handler never answers: the client times out, exactly like a freeze
            raise AbletonError(f"Timeout waiting for reply to {address}")
        L = self.live
        is_write = "/set/" in address or address.split("/")[-1] in (
            "create_midi_track", "create_scene", "create_clip", "delete_clip", "delete_track", "delete_scene",
            "add_or_delete", "start_playing", "stop_playing", "fire") or "/add/" in address or "/remove/" in address
        if is_write:
            self.writes.append((address, args))
        # ---- song
        if address == "/live/song/get/num_tracks":
            return [len(L.tracks)]
        if address == "/live/song/get/track_names":
            return [t.name for t in L.tracks] + L.returns + ["Master"]
        if address == "/live/song/get/num_scenes":
            return [len(L.scenes)]
        if address == "/live/song/get/tempo":
            return [L.tempo]
        if address == "/live/song/set/tempo":
            L.tempo = float(args[0]); return []
        if address == "/live/song/create_midi_track":
            idx = int(args[0]) if args else -1
            t = Track(f"{len(L.tracks) + 1}-MIDI")
            t.sends = [0.0] * len(L.returns)
            if idx < 0 or idx >= len(L.tracks):
                L.tracks.append(t)
            else:
                L.tracks.insert(idx, t)
            return []
        if address == "/live/song/delete_track":
            self._track(args[0]); L.tracks.pop(int(args[0])); return []
        if address == "/live/song/delete_scene":
            L.scenes.pop(int(args[0])); return []
        if address == "/live/song/create_scene":
            idx = int(args[0]) if args else -1
            s = {"name": ""}
            if idx < 0 or idx >= len(L.scenes):
                L.scenes.append(s)
            else:
                L.scenes.insert(idx, s)
            return []
        if address == "/live/song/get/cue_points":
            out = []
            for c in sorted(L.cues, key=lambda c: c["time"]):
                out += [c["name"], c["time"]]
            return out
        if address == "/live/song/get/current_song_time":
            return [L.song_time]
        if address == "/live/song/set/current_song_time":
            L.song_time = float(args[0]); return []
        if address == "/live/song/cue_point/add_or_delete":
            for c in L.cues:
                if abs(c["time"] - L.song_time) < 1e-6:
                    L.cues.remove(c); return []
            L.cues.append({"name": f"{int(L.song_time // 4) + 1}.1.1", "time": L.song_time}); return []
        if address == "/live/song/cue_point/set/name":
            cues = sorted(L.cues, key=lambda c: c["time"])
            cues[int(args[0])]["name"] = str(args[1]); return []
        if address == "/live/song/get/record_mode":
            return [L.record_mode]
        if address == "/live/song/set/record_mode":
            L.record_mode = int(args[0]); return []
        if address == "/live/song/start_playing":
            L.playing = True; return []
        if address == "/live/song/stop_playing":
            L.playing = False; return []
        if address == "/live/song/get/is_playing":
            return [1 if L.playing else 0]
        # ---- scene
        if address == "/live/scene/get/name":
            return [args[0], L.scenes[int(args[0])]["name"]]
        if address == "/live/scene/set/name":
            L.scenes[int(args[0])]["name"] = str(args[1]); return []
        if address == "/live/scene/fire":
            L.fired.append((int(args[0]), L.song_time)); return []
        # ---- track
        if address == "/live/track/get/name":
            return [args[0], self._track(args[0]).name]
        if address == "/live/track/set/name":
            self._track(args[0]).name = str(args[1]); return []
        if address == "/live/track/get/devices/name":
            t = self._track(args[0]); return [args[0]] + [d.name for d in t.devices]
        if address == "/live/track/get/devices/class_name":
            t = self._track(args[0]); return [args[0]] + [d.class_name for d in t.devices]
        if address == "/live/track/get/has_midi_input":
            return [args[0], 1 if self._track(args[0]).kind == "midi" else 0]
        if address == "/live/track/get/volume":
            return [args[0], self._track(args[0]).volume]
        if address == "/live/track/set/volume":
            self._track(args[0]).volume = float(args[1]); return []
        if address == "/live/track/get/panning":
            return [args[0], self._track(args[0]).panning]
        if address == "/live/track/set/panning":
            self._track(args[0]).panning = float(args[1]); return []
        if address == "/live/track/get/mute":
            return [args[0], self._track(args[0]).mute]
        if address == "/live/track/set/mute":
            self._track(args[0]).mute = int(args[1]); return []
        if address == "/live/track/get/send":
            return [args[0], args[1], self._track(args[0]).sends[int(args[1])]]
        if address == "/live/track/set/send":
            self._track(args[0]).sends[int(args[1])] = float(args[2]); return []
        # ---- clip slots and clips
        if address == "/live/clip_slot/get/has_clip":
            return [args[0], args[1], 1 if int(args[1]) in self._track(args[0]).clips else 0]
        if address == "/live/clip_slot/create_clip":
            t = self._track(args[0])
            if int(args[1]) in t.clips:
                raise AbletonError("create_clip: slot already has a clip")
            if int(args[1]) >= len(L.scenes):
                raise AbletonError("create_clip: Index out of range")
            t.clips[int(args[1])] = {"name": "", "length": float(args[2]), "notes": []}; return []
        if address == "/live/clip_slot/delete_clip":
            self._track(args[0]).clips.pop(int(args[1]), None); return []
        if address == "/live/clip/get/name":
            return [args[0], args[1], self._track(args[0]).clips[int(args[1])]["name"]]
        if address == "/live/clip/set/name":
            self._track(args[0]).clips[int(args[1])]["name"] = str(args[2]); return []
        if address == "/live/clip/get/length":
            return [args[0], args[1], self._track(args[0]).clips[int(args[1])]["length"]]
        if address == "/live/clip/get/notes":
            clip = self._track(args[0]).clips.get(int(args[1]))
            if clip is None:
                raise AbletonError("clip: no clip")
            flat = [args[0], args[1]]
            for n in clip["notes"]:
                flat += list(n)
            return flat
        if address == "/live/clip/add/notes":
            clip = self._track(args[0]).clips[int(args[1])]
            body = args[2:]
            if len(body) % 5:
                raise AbletonError("add/notes: notes are 5-tuples")
            clip["notes"] += [tuple(body[k:k + 5]) for k in range(0, len(body), 5)]
            return []
        if address == "/live/clip/remove/notes":
            self._track(args[0]).clips[int(args[1])]["notes"] = []; return []
        # ---- devices
        if address == "/live/device/get/class_name":
            return [args[0], args[1], self._track(args[0]).devices[int(args[1])].class_name]
        if address == "/live/device/get/name":
            return [args[0], args[1], self._track(args[0]).devices[int(args[1])].name]
        if address == "/live/device/get/parameters/name":
            d = self._track(args[0]).devices[int(args[1])]
            return [args[0], args[1]] + [p.name for p in d.params]
        if address == "/live/device/get/parameters/value":
            d = self._track(args[0]).devices[int(args[1])]
            return [args[0], args[1]] + [p.value for p in d.params]
        if address == "/live/device/get/parameters/min":
            d = self._track(args[0]).devices[int(args[1])]
            return [args[0], args[1]] + [0.0 for _ in d.params]
        if address == "/live/device/get/parameters/max":
            d = self._track(args[0]).devices[int(args[1])]
            return [args[0], args[1]] + [1.0 for _ in d.params]
        if address == "/live/device/get/parameter/value":
            d = self._track(args[0]).devices[int(args[1])]
            return [args[0], args[1], args[2], d.params[int(args[2])].value]
        if address == "/live/device/get/parameter/value_string":
            d = self._track(args[0]).devices[int(args[1])]
            return [args[0], args[1], args[2], d.params[int(args[2])].display()]
        if address == "/live/device/set/parameter/value":
            d = self._track(args[0]).devices[int(args[1])]
            d.params[int(args[2])].value = min(1.0, max(0.0, float(args[3]))); return []
        raise AbletonError(f"{address}: Unknown OSC address")


def eq_eight(name="EQ Eight"):
    """An EQ Eight with the readouts the device file of PRP 15 targets."""
    return Device("Eq8", name, [
        Param("3 Filter On A", "onoff", value=0.0),
        Param("3 Frequency A", "exp", lo=20.0, hi=20000.0, value=0.5),
        Param("3 Gain A", "linear", lo=-15.0, hi=15.0, unit="dB", value=0.5),
        Param("3 Filter Type A", "modes", modes=["Low Cut", "Low Shelf", "Bell", "Notch", "High Shelf", "High Cut"], value=0.4),
    ])


def snapshot(live: FakeLive) -> dict:
    """Everything the applier can change, as plain data, for before/after comparisons."""
    return {
        "tempo": live.tempo,
        "scenes": [s["name"] for s in live.scenes],
        "cues": sorted((c["name"], c["time"]) for c in live.cues),
        "tracks": [{
            "name": t.name, "volume": round(t.volume, 6), "pan": t.panning, "mute": t.mute, "sends": list(t.sends),
            "clips": {k: {"name": v["name"], "length": v["length"], "notes": list(v["notes"])} for k, v in sorted(t.clips.items())},
            "devices": [{"class": d.class_name, "name": d.name, "params": [(p.name, round(p.value, 9)) for p in d.params]} for d in t.devices],
        } for t in live.tracks],
    }
