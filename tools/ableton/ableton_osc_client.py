"""Reusable client for the Ableton OSC daemon (ableton-live-mcp-server).

The daemon (osc_daemon.py) listens on a TCP socket and relays JSON-RPC
`send_message` requests to Ableton via AbletonOSC (UDP 11000), returning the
OSC reply. This module speaks that same wire protocol directly, so scripts can
query/modify Live state without going through the MCP server or Claude.

Wire protocol (one request -> one reply, JSON, no framing delimiter):
    -> {"jsonrpc":"2.0","id":"1","method":"send_message",
        "params":{"address":"/live/song/get/num_tracks","args":[]}}
    <- {"jsonrpc":"2.0","id":"1","result":{"status":"success",
        "address":"/live/song/get/num_tracks","data":[42]}}

NOTE: the daemon keys pending responses by OSC address, so requests MUST be
issued sequentially (one outstanding at a time). This client enforces that by
being fully synchronous.
"""

import json
import socket


class AbletonError(RuntimeError):
    """Raised when Ableton/AbletonOSC returns an error or times out."""


class AbletonOSC:
    def __init__(self, host="127.0.0.1", port=65432, timeout=6.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self._id = 0

    # -- connection ---------------------------------------------------------
    def connect(self):
        if self._sock is not None:
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        try:
            s.connect((self.host, self.port))
        except OSError as e:
            raise AbletonError(
                f"Could not connect to OSC daemon at {self.host}:{self.port}. "
                f"Is osc_daemon.py running? ({e})"
            )
        self._sock = s

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    # -- core request -------------------------------------------------------
    def query(self, address, args=None):
        """Send one OSC message and return its `data` list.

        Raises AbletonError on timeout or an Ableton-side error.
        """
        if self._sock is None:
            self.connect()
        self._id += 1
        req = {
            "jsonrpc": "2.0",
            "id": str(self._id),
            "method": "send_message",
            "params": {"address": address, "args": list(args or [])},
        }
        self._sock.sendall(json.dumps(req).encode())

        # Read until we can parse a complete JSON object (responses are small,
        # but TCP may split/coalesce reads).
        buf = b""
        while True:
            try:
                chunk = self._sock.recv(8192)
            except socket.timeout:
                raise AbletonError(f"Timeout waiting for reply to {address}")
            if not chunk:
                raise AbletonError(f"Daemon closed connection during {address}")
            buf += chunk
            try:
                msg = json.loads(buf.decode())
            except json.JSONDecodeError:
                continue  # partial; keep reading
            break

        if "error" in msg:
            raise AbletonError(f"{address}: {msg['error'].get('message')}")
        result = msg.get("result", {})
        if result.get("status") == "error":
            raise AbletonError(f"{address}: {result.get('error')}")
        return result.get("data", [])

    def try_query(self, address, args=None, default=None):
        """Like query() but returns `default` instead of raising."""
        try:
            return self.query(address, args)
        except AbletonError:
            return default

    # -- convenience getters ------------------------------------------------
    def num_tracks(self):
        data = self.query("/live/song/get/num_tracks")
        return int(data[0]) if data else 0

    def track_name(self, i):
        data = self.query("/live/track/get/name", [i])
        return data[-1] if data else None

    def track_flag(self, i, what):
        """what in {'mute','solo','arm'} -> bool, or None if unavailable."""
        data = self.try_query(f"/live/track/get/{what}", [i])
        if data and len(data) >= 2:
            return bool(data[-1])
        return None

    def track_volume(self, i):
        data = self.try_query("/live/track/get/volume", [i])
        return data[-1] if data and len(data) >= 2 else None

    def track_panning(self, i):
        data = self.try_query("/live/track/get/panning", [i])
        return data[-1] if data and len(data) >= 2 else None

    def device_names(self, track):
        """Return list of device names on a track (in chain order)."""
        data = self.try_query("/live/track/get/devices/name", [track], default=[])
        # data is [track_index, name0, name1, ...]
        return list(data[1:]) if data and len(data) > 1 else []

    def parameter_names(self, track, device):
        data = self.try_query(
            "/live/device/get/parameters/name", [track, device], default=[]
        )
        # data is [track, device, name0, name1, ...]
        return list(data[2:]) if data and len(data) > 2 else []

    def parameter_values(self, track, device):
        data = self.try_query(
            "/live/device/get/parameters/value", [track, device], default=[]
        )
        return list(data[2:]) if data and len(data) > 2 else []

    def parameter_value(self, track, device, param):
        data = self.try_query(
            "/live/device/get/parameter/value", [track, device, param]
        )
        return data[-1] if data and len(data) >= 1 else None

    def device_enabled(self, track, device):
        """Read the 'Device On' state. Returns True/False/None.

        'Device On' is parameter index 0 on every Live device (native and VST),
        with value 1.0 = enabled, 0.0 = bypassed.
        """
        v = self.parameter_value(track, device, 0)
        if v is None:
            return None
        return bool(round(float(v)))
