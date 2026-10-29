"""Apply a trancegen handoff folder (PRP 15, `trancegen-handoff/1`) to the open Live set over AbletonOSC (PRP 15b).

The folder is produced by trancegen (`projects/<id>/handoff/<n>/`): `manifest.json` names the capabilities the
applier needs, `handoff.json` holds the steps (tracks by name, scenes, clips with notes, locators, tempo),
`devices/*.json` and `mixer.json` are applied only when asked. Every step is safe to rerun: `ensure_*` creates
only what is missing and `write_clip` replaces the slot. Everything goes through one synchronous request at a
time (the daemon keys replies by address), and every change lands in `receipt.json` with its previous value so
`undo()` can put it back.

Library use:
    app = Applier(AbletonOSC(), Path(folder), only={"clips", "locators", "tempo"})
    receipt = app.run()            # or app.probe_only()
    app.record(confirm=input_yes)  # optional: fire the scenes into the Arrangement, real time
    undo(AbletonOSC(), Path(folder) / "receipt.json")
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ableton_osc_client import AbletonError  # noqa: E402

FORMAT = "trancegen-handoff/1"
FROZEN = "Is a dialog open or an export running?"
STOP_ADD = "Add {display} named {name} to {track}, then rerun."
NOTE_CHUNK = 100                      # notes per /live/clip/add/notes request
DEFAULT_BACKOFF = (0.5, 1.0, 2.0, 4.0)  # seconds between retries when Live does not answer
CALIBRATION_DIR = Path(__file__).resolve().parent / "snapshots" / "calibration"
GROUPS = ("clips", "locators", "tempo", "devices", "mixer", "automation")
DEFAULT_ONLY = frozenset({"clips", "locators", "tempo"})
FADER_0DB = 0.85                      # Live's track fader over OSC: 0.85 reads 0 dB, 1.0 reads +6 dB
BEATS_PER_BAR = 4

# capability -> (group it serves, a read-only address that answers in a build whose write handler exists, args).
# A reply or an Ableton-side error ("Index out of range" on an empty set) proves the handler file is loaded;
# only silence (a timeout) means the capability is missing.
CAPABILITIES: dict[str, tuple[str, str, list]] = {
    "set_tempo": ("tempo", "/live/song/get/tempo", []),
    "create_midi_track": ("clips", "/live/song/get/num_tracks", []),
    "create_scene": ("clips", "/live/song/get/num_scenes", []),
    "create_clip": ("clips", "/live/clip_slot/get/has_clip", [0, 0]),
    "delete_clip": ("clips", "/live/clip_slot/get/has_clip", [0, 0]),
    "add_notes": ("clips", "/live/clip/get/notes", [0, 0]),
    "add_locator": ("locators", "/live/song/get/cue_points", []),
    "set_device_parameter": ("devices", "/live/device/get/parameters/name", [0, 0]),
    "set_track_volume": ("mixer", "/live/track/get/volume", [0]),
    "set_track_pan": ("mixer", "/live/track/get/panning", [0]),
    "set_send": ("mixer", "/live/track/get/send", [0, 0]),
    "set_mute": ("mixer", "/live/track/get/mute", [0]),
}


class Frozen(RuntimeError):
    """Live did not answer after every retry: an export or a modal dialog holds its API."""


class Stop(RuntimeError):
    """The applier stops on purpose, before changing anything more; the message is for the user."""


# ---------------------------------------------------------------- readouts

_NUM = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)\s*([A-Za-z%°]*)\s*$")
_UNITS = {"khz": ("hz", 1000.0), "hz": ("hz", 1.0), "db": ("db", 1.0), "%": ("%", 1.0), "ms": ("s", 0.001),
          "s": ("s", 1.0), "st": ("st", 1.0), "ct": ("ct", 1.0), "°": ("deg", 1.0), "deg": ("deg", 1.0), "": ("", 1.0)}


def parse_display(text: str) -> tuple[Optional[float], str]:
    """A Live readout as (value in a base unit, unit): "2.20 kHz" -> (2200.0, "hz"), "120 ms" -> (0.12, "s"),
    "-3.0 dB" -> (-3.0, "db"), "On" -> (1.0, "onoff"); a mode name comes back as (None, name)."""
    t = text.strip()
    low = t.lower()
    if low in ("on", "off"):
        return (1.0 if low == "on" else 0.0), "onoff"
    m = _NUM.match(t)
    if not m:
        return None, t
    value, unit = float(m.group(1)), m.group(2).lower()
    if unit not in _UNITS:
        return None, t
    base, scale = _UNITS[unit]
    return value * scale, base


def fader_to_db(v: float) -> float:
    """Live's track fader (0..1 over OSC) in dB: 0.85 is 0 dB, 1.0 is +6 dB, straight in dB down to -18 at 0.4,
    then bending towards silence."""
    if v <= 0.0:
        return -70.0
    if v >= 0.4:
        return 40.0 * v - 34.0
    return max(-70.0, -18.0 + 60.0 * math.log10(v / 0.4))


def db_to_fader(db: float) -> float:
    if db <= -69.9:
        return 0.0
    if db >= -18.0:
        return min(1.0, (db + 34.0) / 40.0)
    return 0.4 * 10 ** ((db + 18.0) / 60.0)


def db_to_send(db: float) -> float:
    """Sends are linear amplitude over OSC: 0 dB is 1.0, -70 dB is 0.0003162."""
    return 0.0 if db <= -69.9 else min(1.0, 10 ** (db / 20.0))


# ---------------------------------------------------------------- the client wrapper

class Live:
    """The OSC client with retries, the phantom-track rule and the few compound operations the steps need."""

    def __init__(self, osc, backoff: Iterable[float] = DEFAULT_BACKOFF, sleep: Callable[[float], None] = time.sleep):
        self.osc = osc
        self.backoff = tuple(backoff)
        self.sleep = sleep

    def q(self, address: str, args: Optional[list] = None) -> list:
        """One request; a timeout is retried with backoff, then raised as Frozen."""
        last: Optional[AbletonError] = None
        for attempt in range(len(self.backoff) + 1):
            try:
                return self.osc.query(address, args or [])
            except AbletonError as e:
                if "Timeout" not in str(e) and "closed connection" not in str(e):
                    raise
                last = e
                if attempt < len(self.backoff):
                    self.sleep(self.backoff[attempt])
        raise Frozen(f"{FROZEN} ({last})")

    def answers(self, address: str, args: list) -> bool:
        """Does this build load the handler? A reply or an Ableton-side error says yes; silence says no."""
        for attempt in range(2):
            try:
                self.osc.query(address, args)
                return True
            except AbletonError as e:
                if "Timeout" not in str(e):
                    return True
                if attempt == 0:
                    self.sleep(self.backoff[0] if self.backoff else 0.0)
        return False

    # ---- tracks
    def real_tracks(self) -> list[dict]:
        """Every track AbletonOSC can write to, confirmed by its device list. `track_names` leaks the returns
        and the master past the real count, so an index is real only when `devices/name` answers for it."""
        n = int(self.q("/live/song/get/num_tracks")[0])
        out = []
        for i in range(n):
            try:
                self.osc.query("/live/track/get/devices/name", [i])
            except AbletonError as e:
                if "Timeout" in str(e):
                    raise Frozen(FROZEN) from e
                continue   # a phantom: not a track the API can reach
            name = self.q("/live/track/get/name", [i])[-1]
            midi = self.osc.try_query("/live/track/get/has_midi_input", [i])
            out.append({"index": i, "name": name, "kind": "midi" if (midi and midi[-1]) else "audio"})
        return out

    def return_names(self) -> list[str]:
        """The returns, in order, read from the tail `track_names` leaks past the real tracks."""
        names = list(self.osc.try_query("/live/song/get/track_names", default=[]) or [])
        n = int(self.q("/live/song/get/num_tracks")[0])
        tail = [str(x) for x in names[n:]]
        if tail and tail[-1] == "Master":
            tail = tail[:-1]
        return tail

    # ---- clips
    def has_clip(self, t: int, s: int) -> bool:
        d = self.q("/live/clip_slot/get/has_clip", [t, s])
        return bool(d[-1]) if d else False

    def clip_notes(self, t: int, s: int) -> list[list]:
        d = self.q("/live/clip/get/notes", [t, s])
        body = list(d[2:]) if len(d) > 2 else []
        return [list(body[k:k + 5]) for k in range(0, len(body) - len(body) % 5, 5)]

    def read_clip(self, t: int, s: int) -> Optional[dict]:
        if not self.has_clip(t, s):
            return None
        name = self.q("/live/clip/get/name", [t, s])[-1]
        length = float(self.q("/live/clip/get/length", [t, s])[-1])
        return {"name": name, "length_beats": length, "notes": self.clip_notes(t, s)}

    def write_clip(self, t: int, s: int, name: str, length: float, notes: list[list]) -> None:
        if self.has_clip(t, s):
            self.q("/live/clip_slot/delete_clip", [t, s])
        self.q("/live/clip_slot/create_clip", [t, s, float(length)])
        flat: list = []
        for n in notes:
            pitch, start, dur, vel = n[0], n[1], n[2], n[3]
            mute = n[4] if len(n) > 4 else 0
            flat.append([int(pitch), float(start), float(dur), int(vel), int(mute)])
        for k in range(0, len(flat), NOTE_CHUNK):
            chunk: list = []
            for n in flat[k:k + NOTE_CHUNK]:
                chunk += n
            self.q("/live/clip/add/notes", [t, s] + chunk)
        self.q("/live/clip/set/name", [t, s, name])

    # ---- cue points (locators)
    def cues(self) -> list[tuple[str, float]]:
        d = self.q("/live/song/get/cue_points")
        return [(str(d[k]), float(d[k + 1])) for k in range(0, len(d) - len(d) % 2, 2)]

    def toggle_cue_at(self, beat: float) -> None:
        self.q("/live/song/set/current_song_time", [float(beat)])
        self.q("/live/song/cue_point/add_or_delete")

    def rename_cue_at(self, beat: float, name: str) -> None:
        ordered = sorted(self.cues(), key=lambda c: c[1])
        for i, (_, t) in enumerate(ordered):
            if abs(t - beat) < 1e-6:
                self.q("/live/song/cue_point/set/name", [i, name])
                return
        raise AbletonError(f"no cue point at beat {beat} to name {name!r}")

    # ---- devices
    def devices(self, t: int) -> list[dict]:
        names = list(self.q("/live/track/get/devices/name", [t])[1:])
        classes = self.osc.try_query("/live/track/get/devices/class_name", [t])
        classes = list(classes[1:]) if classes and len(classes) > 1 else []
        out = []
        for i, name in enumerate(names):
            cls = classes[i] if i < len(classes) else None
            if cls is None:
                one = self.osc.try_query("/live/device/get/class_name", [t, i])
                cls = one[-1] if one else name
            out.append({"index": i, "name": str(name), "class": str(cls)})
        return out

    def param_names(self, t: int, d: int) -> list[str]:
        return [str(x) for x in self.q("/live/device/get/parameters/name", [t, d])[2:]]

    def param_value(self, t: int, d: int, p: int) -> float:
        return float(self.q("/live/device/get/parameter/value", [t, d, p])[-1])

    def set_param(self, t: int, d: int, p: int, value: float) -> None:
        self.q("/live/device/set/parameter/value", [t, d, p, float(value)])

    def readout(self, t: int, d: int, p: int) -> str:
        return str(self.q("/live/device/get/parameter/value_string", [t, d, p])[-1])

    def param_range(self, t: int, d: int, p: int) -> tuple[float, float]:
        lo = self.osc.try_query("/live/device/get/parameters/min", [t, d])
        hi = self.osc.try_query("/live/device/get/parameters/max", [t, d])
        try:
            return float(lo[2 + p]), float(hi[2 + p])
        except (TypeError, IndexError, ValueError):
            return 0.0, 1.0


# ---------------------------------------------------------------- readout matching

class Calibration:
    """The raw-value to readout mapping seen per device class, kept under snapshots/calibration/<class>.json
    so the next match starts from a known point."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def path(self, cls: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", cls) or "device"
        return self.folder / f"{safe}.json"

    def load(self, cls: str) -> dict:
        p = self.path(cls)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def add(self, cls: str, live_name: str, points: list[dict]) -> None:
        data = self.load(cls)
        seen = {(round(pt["raw"], 6), pt["display"]) for pt in data.get(live_name, [])}
        rows = list(data.get(live_name, []))
        for pt in points:
            key = (round(pt["raw"], 6), pt["display"])
            if key not in seen:
                rows.append(pt)
                seen.add(key)
        rows.sort(key=lambda r: r["raw"])
        data[live_name] = rows[-400:]
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path(cls).write_text(json.dumps(data, indent=1), encoding="utf-8")


def match_display(osc, t: int, d: int, p: int, display: str, backoff: Iterable[float] = DEFAULT_BACKOFF,
                  live: Optional[Live] = None, points: Optional[list] = None) -> tuple[float, str]:
    """Set parameter p until Live's readout matches `display` (within one readout step): a binary search over
    the raw range on the parsed readout, exact string first. Returns (raw value set, readout shown)."""
    L = live or Live(osc, backoff)
    target, unit = parse_display(display)
    lo, hi = L.param_range(t, d, p)
    log: list[dict] = points if points is not None else []

    def probe(raw: float) -> tuple[str, Optional[float]]:
        L.set_param(t, d, p, raw)
        shown = L.readout(t, d, p)
        val, _ = parse_display(shown)
        log.append({"raw": raw, "display": shown, "value": val})
        return shown, val

    if unit == "onoff":
        raw = hi if target else lo
        shown, _ = probe(raw)
        return raw, shown
    if target is None:
        # a mode name: walk the range in small steps until the readout matches
        steps = 128
        for k in range(steps + 1):
            raw = lo + (hi - lo) * k / steps
            shown, _ = probe(raw)
            if shown.strip().lower() == display.strip().lower():
                return raw, shown
        raise AbletonError(f"no readout matches {display!r}")

    s_lo, v_lo = probe(lo)
    if s_lo.strip() == display.strip():
        return lo, s_lo
    s_hi, v_hi = probe(hi)
    if s_hi.strip() == display.strip():
        return hi, s_hi
    if v_lo is None or v_hi is None:
        raise AbletonError(f"readouts {s_lo!r} and {s_hi!r} are not numbers; cannot match {display!r}")
    rising = v_hi >= v_lo
    best = (lo, s_lo, v_lo) if abs(v_lo - target) <= abs(v_hi - target) else (hi, s_hi, v_hi)
    a, b = lo, hi
    for _ in range(48):
        mid = (a + b) / 2.0
        shown, val = probe(mid)
        if val is not None and abs(val - target) < abs(best[2] - target):
            best = (mid, shown, val)
        if shown.strip() == display.strip():
            return mid, shown
        if val is None:
            break
        if (val < target) == rising:
            a = mid
        else:
            b = mid
        if abs(b - a) < 1e-7:
            break
    raw, shown, _ = best
    L.set_param(t, d, p, raw)
    return raw, shown


# ---------------------------------------------------------------- the folder

@dataclass
class Handoff:
    folder: Path
    manifest: dict
    handoff: dict
    devices: list[tuple[str, dict]] = field(default_factory=list)
    mixer: Optional[dict] = None
    automation: list[tuple[str, dict]] = field(default_factory=list)


def load_handoff(folder: Path) -> Handoff:
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    handoff = json.loads((folder / "handoff.json").read_text(encoding="utf-8"))
    for name, data in ((str(folder / "manifest.json"), manifest), (str(folder / "handoff.json"), handoff)):
        if data.get("format") != FORMAT:
            raise ValueError(f"{name}: format {data.get('format')!r} is not {FORMAT}")
    devices = []
    if (folder / "devices").is_dir():
        for p in sorted((folder / "devices").glob("*.json")):
            devices.append((p.name, json.loads(p.read_text(encoding="utf-8"))))
    mixer = json.loads((folder / "mixer.json").read_text(encoding="utf-8")) if (folder / "mixer.json").exists() else None
    automation = []
    if (folder / "automation").is_dir():
        for p in sorted((folder / "automation").glob("*.json")):
            automation.append((p.name, json.loads(p.read_text(encoding="utf-8"))))
    return Handoff(folder, manifest, handoff, devices, mixer, automation)


# ---------------------------------------------------------------- probe

@dataclass
class ProbeResult:
    checked: list[str]
    missing: list[str]
    unknown: list[str]

    def message(self) -> Optional[str]:
        if not self.missing and not self.unknown:
            return None
        parts = []
        if self.missing:
            parts.append("Missing capabilities: " + ", ".join(self.missing))
        if self.unknown:
            parts.append("Unknown capabilities: " + ", ".join(self.unknown))
        return "; ".join(parts) + ". Nothing was changed. Import the files under midi/ by hand instead."


def probe(osc, requires: Iterable[str], backoff: Iterable[float] = DEFAULT_BACKOFF, groups: Optional[set] = None) -> ProbeResult:
    """Check each required capability against this AbletonOSC build. `groups` limits the check to the
    capabilities the chosen groups use."""
    L = Live(osc, backoff)
    L.q("/live/song/get/tempo")   # the daemon and Live answer at all (Frozen otherwise)
    checked, missing, unknown = [], [], []
    for cap in requires:
        if cap not in CAPABILITIES:
            unknown.append(cap)
            continue
        group, address, args = CAPABILITIES[cap]
        if groups is not None and group not in groups:
            continue
        checked.append(cap)
        if not L.answers(address, args):
            missing.append(cap)
    return ProbeResult(checked, missing, unknown)


# ---------------------------------------------------------------- the receipt

@dataclass
class Receipt:
    folder: str
    only: list[str]
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    changes: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    verify: list[dict] = field(default_factory=list)
    probe: Optional[dict] = None
    stopped: Optional[str] = None

    def to_dict(self) -> dict:
        return {"format": "trancegen-receipt/1", "folder": self.folder, "only": self.only, "created": self.created,
                "probe": self.probe, "changes": self.changes, "failures": self.failures, "notes": self.notes,
                "verify": self.verify, "stopped": self.stopped}

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=1), encoding="utf-8")
        return path

    def summary(self) -> str:
        lines = []
        if self.probe:
            lines.append(f"probe: {len(self.probe.get('checked', []))} capabilities checked, missing: {self.probe.get('missing') or 'none'}")
        lines.append(f"changes: {len(self.changes)}, failures: {len(self.failures)}")
        ok = sum(1 for v in self.verify if v.get("ok"))
        if self.verify:
            lines.append(f"verify: {ok}/{len(self.verify)} ok")
        for f in self.failures:
            lines.append(f"  failed: {f.get('op')} {f.get('what', '')}: {f.get('error')}")
        for n in self.notes:
            lines.append(f"  note: {n}")
        if self.stopped:
            lines.append(f"STOPPED: {self.stopped}")
        return "\n".join(lines)


# ---------------------------------------------------------------- the applier

class Applier:
    def __init__(self, osc, folder: Path, only: Optional[Iterable[str]] = None, calibration_dir: Path = CALIBRATION_DIR,
                 backoff: Iterable[float] = DEFAULT_BACKOFF, sleep: Callable[[float], None] = time.sleep):
        self.osc = osc
        self.folder = Path(folder)
        self.only = set(only) if only is not None else set(DEFAULT_ONLY)
        bad = self.only - set(GROUPS)
        if bad:
            raise ValueError(f"unknown --only groups: {sorted(bad)} (choose from {', '.join(GROUPS)})")
        self.live = Live(osc, backoff, sleep)
        self.cal = Calibration(calibration_dir)
        self.backoff = tuple(backoff)
        self.h = load_handoff(self.folder)
        self.receipt = Receipt(str(self.folder), sorted(self.only))
        self._tracks: Optional[list[dict]] = None

    # ---- helpers
    def real_tracks(self) -> list[dict]:
        if self._tracks is None:
            self._tracks = self.live.real_tracks()
        return self._tracks

    def refresh(self) -> None:
        self._tracks = None

    def track_index(self, name: str) -> Optional[int]:
        for t in self.real_tracks():
            if t["name"] == name:
                return t["index"]
        return None

    def change(self, **row) -> None:
        self.receipt.changes.append(row)

    def fail(self, op: str, what: str, error: str) -> None:
        self.receipt.failures.append({"op": op, "what": what, "error": error})

    # ---- entry points
    def probe_only(self) -> Receipt:
        try:
            result = probe(self.osc, self.h.manifest.get("requires", []), self.backoff, self.only)
        except Frozen:
            self.receipt.stopped = FROZEN
            return self.receipt
        self.receipt.probe = {"checked": result.checked, "missing": result.missing, "unknown": result.unknown}
        self.receipt.stopped = result.message()
        return self.receipt

    def run(self) -> Receipt:
        r = self.probe_only()
        if r.stopped:
            return r
        try:
            self._apply()
            self.receipt.verify = self.verify()
        except Stop as e:
            self.receipt.stopped = str(e)
        except Frozen:
            self.receipt.stopped = FROZEN
        finally:
            try:
                self.receipt.save(self.folder / "receipt.json")
            except OSError as e:   # a read-only folder still gets the summary on stdout
                self.receipt.notes.append(f"receipt not written: {e}")
        return self.receipt

    # ---- steps
    def _apply(self) -> None:
        for step in self.h.handoff.get("steps", []):
            op = step["op"]
            group = {"set_tempo": "tempo", "add_locator": "locators"}.get(op, "clips")
            if group not in self.only:
                continue
            try:
                getattr(self, "_op_" + op)(step)
            except Frozen:
                raise
            except AbletonError as e:
                self.fail(op, json.dumps({k: v for k, v in step.items() if k != "notes"}), str(e))
        if "devices" in self.only:
            for name, data in self.h.devices:
                self._device_file(name, data)
        if "mixer" in self.only and self.h.mixer:
            self._mixer(self.h.mixer)
        if "automation" in self.only and self.h.automation:
            for name, _ in self.h.automation:
                self.receipt.notes.append(f"automation/{name}: AbletonOSC sets values, not envelopes; draw this move by hand.")

    def _op_set_tempo(self, step: dict) -> None:
        before = float(self.live.q("/live/song/get/tempo")[0])
        if abs(before - float(step["bpm"])) > 1e-6:
            self.live.q("/live/song/set/tempo", [float(step["bpm"])])
            self.change(op="set_tempo", previous=before, value=float(step["bpm"]))

    def _op_ensure_midi_track(self, step: dict) -> None:
        if self.track_index(step["name"]) is not None:
            return
        n_before = len(self.real_tracks())
        self.live.q("/live/song/create_midi_track", [-1])
        self.refresh()
        tracks = self.real_tracks()
        new = tracks[-1] if len(tracks) > n_before else None
        if new is None:
            raise AbletonError(f"create_midi_track: the new track for {step['name']!r} did not appear")
        self.live.q("/live/track/set/name", [new["index"], step["name"]])
        self.refresh()
        self.change(op="create_midi_track", index=new["index"], name=step["name"], previous=None)

    def _op_ensure_scene(self, step: dict) -> None:
        idx = int(step["index"])
        n = int(self.live.q("/live/song/get/num_scenes")[0])
        while n <= idx:
            self.live.q("/live/song/create_scene", [-1])
            self.change(op="create_scene", index=n, previous=None)
            n += 1
        current = str(self.live.q("/live/scene/get/name", [idx])[-1])
        if current != step["name"]:
            self.live.q("/live/scene/set/name", [idx, step["name"]])
            self.change(op="set_scene_name", index=idx, previous=current, value=step["name"])

    def _slot(self, step: dict) -> tuple[int, int]:
        t = self.track_index(step["track"])
        if t is None:
            raise AbletonError(f"no track named {step['track']!r} (ensure_midi_track comes first)")
        return t, int(step["scene"])

    def _op_write_clip(self, step: dict) -> None:
        t, s = self._slot(step)
        previous = self.live.read_clip(t, s)
        self.live.write_clip(t, s, step.get("name", ""), float(step["length_beats"]), step["notes"])
        self.change(op="write_clip", track=step["track"], index=t, scene=s, previous=previous, notes=len(step["notes"]))

    def _op_clear_clip(self, step: dict) -> None:
        t, s = self._slot(step)
        previous = self.live.read_clip(t, s)
        if previous is None:
            return
        self.live.q("/live/clip_slot/delete_clip", [t, s])
        self.change(op="clear_clip", track=step["track"], index=t, scene=s, previous=previous)

    def _op_add_locator(self, step: dict) -> None:
        name, beat = str(step["name"]), float(step["beat"])
        cues = self.live.cues()
        at_beat = [n for n, t in cues if abs(t - beat) < 1e-6]
        if name in at_beat:
            return
        same_name = [t for n, t in cues if n == name]
        if at_beat:   # Live keeps one cue per time: this one takes the handoff's name
            self.live.rename_cue_at(beat, name)
            self.change(op="add_locator", name=name, beat=beat, previous=at_beat[0], previous_time=None)
            return
        previous_time = None
        if same_name:   # the same locator at another time moves here
            previous_time = same_name[0]
            self.live.toggle_cue_at(previous_time)
        self.live.toggle_cue_at(beat)
        self.live.rename_cue_at(beat, name)
        self.change(op="add_locator", name=name, beat=beat, previous=None, previous_time=previous_time)

    # ---- devices
    def _find_device(self, t: int, spec: dict) -> Optional[dict]:
        wanted_class = str(spec.get("class", "")).lower()
        wanted_display = str(spec.get("display", "")).lower()
        same = [d for d in self.live.devices(t)
                if d["class"].lower() == wanted_class or d["name"].lower() == wanted_display or d["class"].lower() == wanted_display]
        if not same:
            return None
        named = [d for d in same if d["name"] == spec.get("name")]
        if named:
            return named[0]
        k = int(spec.get("index_among_same", 0))
        return same[k] if k < len(same) else None

    def _device_file(self, filename: str, data: dict) -> None:
        if data.get("format") != "trancegen-device/1":
            self.fail("device", filename, f"format {data.get('format')!r} is not trancegen-device/1")
            return
        track = data["track"]
        t = self.track_index(track)
        spec = data["device"]
        if t is None:
            self.fail("device", filename, f"no track named {track!r}")
            return
        dev = self._find_device(t, spec)
        if dev is None:
            if spec.get("if_missing", "ask_to_add") == "skip":
                self.receipt.notes.append(f"devices/{filename}: {spec.get('display')} named {spec.get('name')!r} is not on {track}; skipped.")
                return
            raise Stop(STOP_ADD.format(display=spec.get("display"), name=spec.get("name"), track=track))
        names = self.live.param_names(t, dev["index"])
        for prm in data.get("params", []):
            live_name = prm["live_name"]
            if live_name not in names:
                self.fail("set_device_parameter", f"{track} / {dev['name']} / {live_name}", "no parameter with that Live name")
                continue
            p = names.index(live_name)
            previous = self.live.param_value(t, dev["index"], p)
            points: list[dict] = []
            try:
                if "value" in prm and prm["value"] is not None:
                    raw = float(prm["value"])
                    self.live.set_param(t, dev["index"], p, raw)
                    shown = self.live.readout(t, dev["index"], p)
                else:
                    raw, shown = match_display(self.osc, t, dev["index"], p, prm["display"], self.backoff, self.live, points)
            except AbletonError as e:
                self.live.set_param(t, dev["index"], p, previous)
                self.fail("set_device_parameter", f"{track} / {dev['name']} / {live_name}", str(e))
                continue
            if points:
                self.cal.add(spec.get("class", dev["class"]), live_name, points)
            self.change(op="set_device_parameter", track=track, index=t, device=dev["index"], device_name=dev["name"],
                        param=live_name, param_index=p, previous=previous, value=raw, display=shown, wanted=prm.get("display"))

    # ---- mixer
    def _mixer(self, mixer: dict) -> None:
        if mixer.get("format") != "trancegen-mixer/1":
            self.fail("mixer", "mixer.json", f"format {mixer.get('format')!r} is not trancegen-mixer/1")
            return
        self.receipt.notes.append("Return and master tracks are not reachable over OSC: the mixer file never names them and they were skipped.")
        returns = None
        for row in mixer.get("tracks", []):
            t = self.track_index(row["name"])
            if t is None:
                self.fail("mixer", row["name"], "no track with that name")
                continue
            self._set_track_value(t, row["name"], "volume", "/live/track/get/volume", "/live/track/set/volume", db_to_fader(float(row["volume_db"])))
            self._set_track_value(t, row["name"], "pan", "/live/track/get/panning", "/live/track/set/panning", float(row["pan"]))
            self._set_track_value(t, row["name"], "mute", "/live/track/get/mute", "/live/track/set/mute", 1 if row.get("mute") else 0)
            for send in row.get("sends", []):
                if returns is None:
                    returns = self.live.return_names()
                if send["return"] not in returns:
                    self.receipt.notes.append(f"{row['name']}: send to {send['return']!r} skipped, no return of that name is visible over OSC.")
                    continue
                k = returns.index(send["return"])
                before = float(self.live.q("/live/track/get/send", [t, k])[-1])
                value = db_to_send(float(send["db"]))
                if abs(before - value) > 1e-6:
                    self.live.q("/live/track/set/send", [t, k, value])
                    self.change(op="set_send", track=row["name"], index=t, send=k, previous=before, value=value)

    def _set_track_value(self, t: int, name: str, what: str, get: str, set_: str, value: float) -> None:
        before = self.live.q(get, [t])[-1]
        before = float(before) if what != "mute" else int(bool(before))
        if abs(float(before) - float(value)) <= 1e-6:
            return
        self.live.q(set_, [t, value])
        self.change(op=f"set_track_{what}", track=name, index=t, previous=before, value=value)

    # ---- verify
    def verify(self) -> list[dict]:
        rows = []
        for v in self.h.handoff.get("verify", []):
            got: object = None
            try:
                if v["check"] == "clip_note_count":
                    t = self.track_index(v["track"])
                    got = len(self.live.clip_notes(t, int(v["scene"]))) if t is not None and self.live.has_clip(t, int(v["scene"])) else 0
                elif v["check"] == "tempo":
                    got = float(self.live.q("/live/song/get/tempo")[0])
                elif v["check"] == "scene_name":
                    n = int(self.live.q("/live/song/get/num_scenes")[0])
                    got = str(self.live.q("/live/scene/get/name", [int(v["scene"])])[-1]) if int(v["scene"]) < n else None
                elif v["check"] == "locator":
                    got = dict(self.live.cues()).get(v["name"])
            except AbletonError as e:
                got = f"error: {e}"
            expect = v["expect"]
            ok = (abs(float(got) - float(expect)) < 1e-6) if isinstance(got, (int, float)) and isinstance(expect, (int, float)) else got == expect
            rows.append({**v, "got": got, "ok": bool(ok)})
        return rows

    # ---- record
    def record(self, confirm: Callable[[str], bool], sleep: Callable[[float], None] = time.sleep) -> bool:
        """Fire the scenes in `arrangement` order with Arrangement record on, in real time."""
        arrangement = self.h.handoff.get("arrangement", [])
        if not arrangement:
            return False
        total_bars = sum(int(a["bars"]) for a in arrangement)
        text = (f"Record {len(arrangement)} scenes ({total_bars} bars) into the Arrangement of the open set now? "
                f"This runs in real time and overwrites what is on those tracks there. [y/N] ")
        if not confirm(text):
            return False
        tempo = float(self.live.q("/live/song/get/tempo")[0])
        self.live.q("/live/song/set/record_mode", [1])
        self.live.q("/live/song/set/current_song_time", [0.0])
        self.live.q("/live/song/start_playing")
        try:
            for a in sorted(arrangement, key=lambda a: int(a["start_bar"])):
                start_beat = (int(a["start_bar"]) - 1) * BEATS_PER_BAR
                self.live.q("/live/song/set/current_song_time", [float(start_beat)])
                self.live.q("/live/scene/fire", [int(a["scene"])])
                sleep(int(a["bars"]) * BEATS_PER_BAR * 60.0 / tempo)
        finally:
            self.live.q("/live/song/stop_playing")
            self.live.q("/live/song/set/record_mode", [0])
        self.receipt.notes.append(f"recorded {len(arrangement)} scenes into the Arrangement at {tempo:g} BPM")
        return True


# ---------------------------------------------------------------- undo

def undo(osc, receipt_path: Path, backoff: Iterable[float] = DEFAULT_BACKOFF) -> list[dict]:
    """Put back every previous value a receipt recorded, newest change first."""
    data = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    L = Live(osc, backoff)
    done = []
    for c in reversed(data.get("changes", [])):
        op = c["op"]
        if op == "set_tempo":
            L.q("/live/song/set/tempo", [float(c["previous"])])
        elif op == "create_midi_track":
            L.q("/live/song/delete_track", [int(c["index"])])
        elif op == "create_scene":
            L.q("/live/song/delete_scene", [int(c["index"])])
        elif op == "set_scene_name":
            L.q("/live/scene/set/name", [int(c["index"]), c["previous"]])
        elif op in ("write_clip", "clear_clip"):
            t, s = int(c["index"]), int(c["scene"])
            if L.has_clip(t, s):
                L.q("/live/clip_slot/delete_clip", [t, s])
            prev = c.get("previous")
            if prev:
                L.write_clip(t, s, prev["name"], float(prev["length_beats"]), prev["notes"])
        elif op == "add_locator":
            beat = float(c["beat"])
            if c.get("previous") is not None:       # renamed an existing cue: name it back
                L.rename_cue_at(beat, c["previous"])
            else:
                L.toggle_cue_at(beat)
                if c.get("previous_time") is not None:   # it had been moved: put it back where it was
                    L.toggle_cue_at(float(c["previous_time"]))
                    L.rename_cue_at(float(c["previous_time"]), c["name"])
        elif op == "set_device_parameter":
            L.set_param(int(c["index"]), int(c["device"]), int(c["param_index"]), float(c["previous"]))
        elif op == "set_track_volume":
            L.q("/live/track/set/volume", [int(c["index"]), float(c["previous"])])
        elif op == "set_track_pan":
            L.q("/live/track/set/panning", [int(c["index"]), float(c["previous"])])
        elif op == "set_track_mute":
            L.q("/live/track/set/mute", [int(c["index"]), int(c["previous"])])
        elif op == "set_send":
            L.q("/live/track/set/send", [int(c["index"]), int(c["send"]), float(c["previous"])])
        else:
            continue
        done.append(c)
    return done
