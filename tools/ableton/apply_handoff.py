"""Apply a trancegen handoff folder to the open Live set through the OSC daemon (PRP 15b).

    python tools/ableton/apply_handoff.py <folder> --probe
    python tools/ableton/apply_handoff.py <folder>
    python tools/ableton/apply_handoff.py <folder> --only clips,locators,tempo,devices,mixer,automation
    python tools/ableton/apply_handoff.py <folder> --record
    python tools/ableton/apply_handoff.py <folder> --undo <folder>/receipt.json

Clips, locators and tempo are applied by default. Devices, mixer and automation are applied only when named in
--only, and only when the user said so. Every change lands in <folder>/receipt.json with its previous value.
Needs Live open with AbletonOSC as a Control Surface and osc_daemon.py running (TCP 127.0.0.1:65432).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ableton_osc_client import AbletonOSC, AbletonError  # noqa: E402
from handoff_applier import DEFAULT_ONLY, FROZEN, GROUPS, Applier, Frozen, undo  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Apply a trancegen handoff folder to the open Live set over AbletonOSC.")
    ap.add_argument("folder", type=Path, help="projects/<id>/handoff/<n>/ written by trancegen")
    ap.add_argument("--probe", action="store_true", help="check the capabilities and change nothing")
    ap.add_argument("--only", default=None, help=f"comma list of {', '.join(GROUPS)} (default: {','.join(sorted(DEFAULT_ONLY))})")
    ap.add_argument("--record", action="store_true", help="after applying, fire the scenes into the Arrangement in real time (asks first)")
    ap.add_argument("--yes", action="store_true", help="answer yes to the --record question")
    ap.add_argument("--undo", type=Path, default=None, help="restore the previous values a receipt.json recorded")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=65432)
    a = ap.parse_args(argv)

    only = {s.strip() for s in a.only.split(",") if s.strip()} if a.only else None
    try:
        with AbletonOSC(a.host, a.port) as osc:
            if a.undo:
                done = undo(osc, a.undo)
                print(f"undone {len(done)} changes from {a.undo}")
                return 0
            app = Applier(osc, a.folder, only=only)
            receipt = app.probe_only() if a.probe else app.run()
            print(receipt.summary())
            if receipt.stopped:
                return 2
            if a.record:
                def confirm(text: str) -> bool:
                    if a.yes:
                        print(text + "yes (--yes)")
                        return True
                    return input(text).strip().lower() in ("y", "yes")
                if app.record(confirm):
                    print("recorded; the receipt notes it")
                    receipt.save(a.folder / "receipt.json")
            print(f"receipt: {a.folder / 'receipt.json'}")
            return 1 if receipt.failures else 0
    except Frozen:
        print(f"STOPPED: {FROZEN}")
        return 2
    except AbletonError as e:
        print(f"STOPPED: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
