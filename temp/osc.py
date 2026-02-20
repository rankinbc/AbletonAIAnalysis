import socket
import json
import sys

def send_osc(address, args):
    """Send OSC command to Ableton via daemon."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(('127.0.0.1', 65432))
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "send_message",
            "params": {"address": address, "args": args}
        }
        sock.sendall(json.dumps(request).encode())
        response = sock.recv(8192)
        data = json.loads(response.decode())
        if 'result' in data:
            return data['result']
        return data
    except Exception as e:
        return {"error": str(e)}
    finally:
        sock.close()

def parse_args(args):
    """Parse arguments, converting to int/float where appropriate."""
    result = []
    for arg in args:
        try:
            if '.' in arg:
                result.append(float(arg))
            else:
                result.append(int(arg))
        except ValueError:
            result.append(arg)
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python osc.py <address> [args...]")
        print("")
        print("Examples:")
        print("  python osc.py /live/track/get/devices/name 1")
        print("  python osc.py /live/device/get/parameters/name 1 3")
        print("  python osc.py /live/device/set/parameter/value 1 3 4 0.75")
        print("  python osc.py /live/track/set/volume 1 0.85")
        sys.exit(1)

    address = sys.argv[1]
    args = parse_args(sys.argv[2:]) if len(sys.argv) > 2 else []

    print(f"Sending: {address} {args}")
    result = send_osc(address, args)
    print(f"Result: {json.dumps(result, indent=2)}")
