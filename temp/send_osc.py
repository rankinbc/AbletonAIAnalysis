import socket
import json
import sys
import time

def send_osc_command(address, args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(('127.0.0.1', 65432))
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "send_message",
            "params": {
                "address": address,
                "args": args
            }
        }
        sock.sendall(json.dumps(request).encode())
        response = sock.recv(8192)
        print(f"Response: {response.decode()}")
        return json.loads(response.decode())
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        sock.close()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fix_snare"

    if cmd == "fix_snare":
        print("=== FIXING SNARE (CORRECT VALUES) ===\n")

        # Utility is device index 3
        # Width param index 4
        # Current shows 42% - need to go HIGHER for width
        # Try 1.0 for maximum width (200%)
        # Or ~0.75 for 150%

        print("1. Setting Utility width to ~150% (wider)...")
        send_osc_command("/live/device/set/parameter/value", [1, 3, 4, 0.75])
        time.sleep(0.2)

        # EQ Eight device index 2
        # Use Band 6 for 9kHz cut (indices 54-58)
        # 54: 6 Filter On A
        # 55: 6 Filter Type A
        # 56: 6 Frequency A
        # 57: 6 Gain A
        # 58: 6 Resonance A

        print("2. Enabling EQ Band 6...")
        send_osc_command("/live/device/set/parameter/value", [1, 2, 54, 1.0])
        time.sleep(0.1)

        print("3. Setting Band 6 frequency to 9kHz...")
        # 9kHz normalized - try higher value
        send_osc_command("/live/device/set/parameter/value", [1, 2, 56, 0.82])
        time.sleep(0.1)

        print("4. Setting Band 6 gain to -3dB...")
        # Gain: 0.5 = 0dB, lower = cut
        # -3dB out of ±15dB range: 0.5 - (3/30) = 0.4
        send_osc_command("/live/device/set/parameter/value", [1, 2, 57, 0.4])
        time.sleep(0.1)

        print("\n=== DONE ===")

    elif cmd == "max_width":
        # Set maximum width
        print("Setting Utility to max width (200%)...")
        send_osc_command("/live/device/set/parameter/value", [1, 3, 4, 1.0])

    elif cmd == "test_width":
        # Test different width values
        val = float(sys.argv[2]) if len(sys.argv) > 2 else 0.75
        print(f"Setting Utility width to {val}...")
        send_osc_command("/live/device/set/parameter/value", [1, 3, 4, val])

    elif cmd == "get_devices":
        send_osc_command("/live/track/get/devices/name", [1])
