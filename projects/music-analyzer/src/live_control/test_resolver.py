"""
Test script for DeviceResolver and value conversions.

Run: python test_resolver.py (from live_control directory)
"""

import json
from resolver import DeviceResolver, ResolvedFix, get_resolver, reset_resolver
from conversions import (
    hz_to_normalized, normalized_to_hz,
    db_to_normalized, normalized_to_db,
    ms_to_normalized, normalized_to_ms,
    ratio_to_normalized, normalized_to_ratio,
    volume_db_to_normalized, normalized_to_volume_db,
    q_to_normalized, normalized_to_q,
    percent_to_normalized, normalized_to_percent,
    detect_parameter_type, convert_to_normalized, convert_from_normalized
)


# =============================================================================
# DeviceResolver Tests
# =============================================================================

def test_load_tracks():
    """Test loading tracks from MCP response."""
    print("Testing track loading...")

    resolver = DeviceResolver()

    # Simulate MCP response
    mcp_response = json.dumps({
        "success": True,
        "tracks": [
            {"index": 0, "name": "Kick"},
            {"index": 1, "name": "Bass"},
            {"index": 2, "name": "Lead Synth"},
            {"index": 3, "name": "Vocals"}
        ]
    })

    assert resolver.load_tracks_from_mcp(mcp_response) == True
    assert resolver.track_count == 4
    assert resolver.is_initialized == True

    # Test exact match
    assert resolver.resolve_track("Kick") == 0
    assert resolver.resolve_track("Bass") == 1

    # Test case-insensitive
    assert resolver.resolve_track("kick") == 0
    assert resolver.resolve_track("BASS") == 1

    # Test fuzzy match (needs high similarity)
    assert resolver.resolve_track("Lead Synth") == 2  # Exact match
    assert resolver.resolve_track("Lead synth") == 2  # Case insensitive

    # Test index reference
    assert resolver.resolve_track("#0") == 0
    assert resolver.resolve_track("track 1") == 1

    # Test not found
    assert resolver.resolve_track("Drums") == None

    print("  Track loading OK")


def test_load_devices():
    """Test loading devices from MCP response."""
    print("Testing device loading...")

    resolver = DeviceResolver()

    # Load tracks first
    resolver.load_tracks_from_mcp(json.dumps({
        "success": True,
        "tracks": [{"index": 0, "name": "Bass"}]
    }))

    # Load devices
    mcp_response = json.dumps({
        "success": True,
        "track_index": 0,
        "devices": [
            {"index": 0, "name": "EQ Eight"},
            {"index": 1, "name": "Compressor"},
            {"index": 2, "name": "Saturator"}
        ]
    })

    assert resolver.load_devices_from_mcp(0, mcp_response) == True

    # Test resolution
    assert resolver.resolve_device(0, "EQ Eight") == 0
    assert resolver.resolve_device(0, "Compressor") == 1
    assert resolver.resolve_device(0, "eq eight") == 0  # Case-insensitive

    # Test get devices list
    devices = resolver.get_devices(0)
    assert len(devices) == 3

    # Test not found
    assert resolver.resolve_device(0, "Reverb") == None
    assert resolver.resolve_device(1, "EQ Eight") == None  # Wrong track

    print("  Device loading OK")


def test_load_parameters():
    """Test loading parameters from MCP response."""
    print("Testing parameter loading...")

    resolver = DeviceResolver()

    # Load tracks and devices
    resolver.load_tracks_from_mcp(json.dumps({
        "success": True,
        "tracks": [{"index": 0, "name": "Bass"}]
    }))
    resolver.load_devices_from_mcp(0, json.dumps({
        "success": True,
        "devices": [{"index": 0, "name": "EQ Eight"}]
    }))

    # Load parameters
    mcp_response = json.dumps({
        "success": True,
        "track_index": 0,
        "device_index": 0,
        "parameters": [
            {"index": 0, "name": "Device On"},
            {"index": 1, "name": "Band 1 Frequency"},
            {"index": 2, "name": "Band 1 Gain"},
            {"index": 3, "name": "Band 1 Q"}
        ]
    })

    assert resolver.load_parameters_from_mcp(0, 0, mcp_response) == True

    # Test resolution
    assert resolver.resolve_parameter(0, 0, "Device On") == 0
    assert resolver.resolve_parameter(0, 0, "Band 1 Frequency") == 1

    # Test partial match
    assert resolver.resolve_parameter(0, 0, "Frequency") == 1  # Contains "Frequency"

    # Test case-insensitive
    assert resolver.resolve_parameter(0, 0, "band 1 gain") == 2

    print("  Parameter loading OK")


def test_resolve_fix():
    """Test resolving a complete fix specification."""
    print("Testing fix resolution...")

    resolver = DeviceResolver()

    # Setup
    resolver.load_tracks_from_mcp(json.dumps({
        "success": True,
        "tracks": [
            {"index": 0, "name": "Kick"},
            {"index": 1, "name": "Bass"}
        ]
    }))
    resolver.load_devices_from_mcp(1, json.dumps({
        "success": True,
        "devices": [{"index": 0, "name": "EQ Eight"}]
    }))
    resolver.load_parameters_from_mcp(1, 0, json.dumps({
        "success": True,
        "parameters": [
            {"index": 0, "name": "Device On"},
            {"index": 4, "name": "1 Frequency"}
        ]
    }))

    # Test parameter fix
    fix = resolver.resolve_fix({
        'track_name': 'Bass',
        'device_name': 'EQ Eight',
        'parameter_name': '1 Frequency',
        'value': 0.3
    })

    assert fix.track_index == 1
    assert fix.device_index == 0
    assert fix.parameter_index == 4
    assert fix.value == 0.3
    assert fix.change_type == 'parameter'

    # Test volume fix
    fix = resolver.resolve_fix({
        'track_name': 'Kick',
        'change_type': 'volume',
        'value': 0.7
    })

    assert fix.track_index == 0
    assert fix.device_index == None
    assert fix.change_type == 'volume'
    assert fix.value == 0.7

    # Test MCP args
    args = fix.to_mcp_args()
    assert args == {'track_index': 0, 'volume': 0.7}

    print("  Fix resolution OK")


def test_resolve_fix_errors():
    """Test error handling in fix resolution."""
    print("Testing fix resolution errors...")

    resolver = DeviceResolver()
    resolver.load_tracks_from_mcp(json.dumps({
        "success": True,
        "tracks": [{"index": 0, "name": "Kick"}]
    }))

    # Test track not found
    try:
        resolver.resolve_fix({'track_name': 'NonExistent', 'change_type': 'volume', 'value': 0.5})
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Track not found" in str(e)

    # Test device not found
    try:
        resolver.resolve_fix({
            'track_name': 'Kick',
            'device_name': 'NonExistent',
            'parameter_name': 'Gain',
            'value': 0.5
        })
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Device not found" in str(e)

    print("  Fix resolution errors OK")


# =============================================================================
# Value Conversion Tests
# =============================================================================

def test_frequency_conversion():
    """Test Hz to normalized conversion."""
    print("Testing frequency conversion...")

    # Test key frequencies
    assert abs(hz_to_normalized(10) - 0.0) < 0.01      # Min
    assert abs(hz_to_normalized(22000) - 1.0) < 0.01  # Max
    assert abs(hz_to_normalized(100) - 0.30) < 0.05   # ~30%
    assert abs(hz_to_normalized(1000) - 0.60) < 0.05  # ~60%

    # Test round-trip
    for hz in [20, 100, 440, 1000, 5000, 10000]:
        normalized = hz_to_normalized(hz)
        back = normalized_to_hz(normalized)
        assert abs(hz - back) < 1, f"Round-trip failed for {hz}Hz"

    print("  Frequency conversion OK")


def test_db_conversion():
    """Test dB to normalized conversion."""
    print("Testing dB conversion...")

    # Test key values
    assert abs(db_to_normalized(-15) - 0.0) < 0.01  # Min
    assert abs(db_to_normalized(15) - 1.0) < 0.01   # Max
    assert abs(db_to_normalized(0) - 0.5) < 0.01    # Center

    # Test round-trip
    for db in [-15, -6, -3, 0, 3, 6, 12]:
        normalized = db_to_normalized(db)
        back = normalized_to_db(normalized)
        assert abs(db - back) < 0.1, f"Round-trip failed for {db}dB"

    print("  dB conversion OK")


def test_ms_conversion():
    """Test ms to normalized conversion."""
    print("Testing ms conversion...")

    # Test round-trip with attack range
    for ms in [0.1, 1, 10, 100, 500]:
        normalized = ms_to_normalized(ms, 0.01, 1000)
        back = normalized_to_ms(normalized, 0.01, 1000)
        assert abs(ms - back) / ms < 0.01, f"Round-trip failed for {ms}ms"

    print("  ms conversion OK")


def test_ratio_conversion():
    """Test ratio to normalized conversion."""
    print("Testing ratio conversion...")

    # Test key values
    assert abs(ratio_to_normalized(1) - 0.0) < 0.01   # No compression
    assert abs(ratio_to_normalized(20) - 1.0) < 0.01  # Max

    # Test round-trip
    for ratio in [1, 2, 4, 8, 10, 20]:
        normalized = ratio_to_normalized(ratio)
        back = normalized_to_ratio(normalized)
        assert abs(ratio - back) < 0.1, f"Round-trip failed for {ratio}:1"

    print("  Ratio conversion OK")


def test_volume_conversion():
    """Test volume dB to fader conversion."""
    print("Testing volume conversion...")

    # Test key values
    assert volume_db_to_normalized(-70) == 0.0  # Silence
    assert abs(volume_db_to_normalized(0) - 0.85) < 0.05  # Unity
    assert volume_db_to_normalized(6) == 1.0  # Max

    # Test reasonable round-trip (not perfect due to curve approximation)
    for db in [-60, -30, -12, -6, 0, 3, 6]:
        normalized = volume_db_to_normalized(db)
        back = normalized_to_volume_db(normalized)
        assert abs(db - back) < 3, f"Round-trip too far off for {db}dB"

    print("  Volume conversion OK")


def test_q_conversion():
    """Test Q factor conversion."""
    print("Testing Q conversion...")

    # Test round-trip
    for q in [0.5, 1, 2, 4, 10]:
        normalized = q_to_normalized(q)
        back = normalized_to_q(normalized)
        assert abs(q - back) < 0.1, f"Round-trip failed for Q={q}"

    print("  Q conversion OK")


def test_percent_conversion():
    """Test percentage conversion."""
    print("Testing percentage conversion...")

    assert percent_to_normalized(0) == 0.0
    assert percent_to_normalized(50) == 0.5
    assert percent_to_normalized(100) == 1.0

    assert normalized_to_percent(0.0) == 0.0
    assert normalized_to_percent(0.5) == 50.0
    assert normalized_to_percent(1.0) == 100.0

    print("  Percentage conversion OK")


def test_auto_detection():
    """Test automatic parameter type detection."""
    print("Testing auto-detection...")

    assert detect_parameter_type("Band 1 Frequency") == "frequency"
    assert detect_parameter_type("1 Gain") == "gain"
    assert detect_parameter_type("Attack Time") == "attack"
    assert detect_parameter_type("Release") == "release"
    assert detect_parameter_type("Ratio") == "ratio"
    assert detect_parameter_type("Threshold") == "threshold"
    assert detect_parameter_type("Q Factor") == "q"
    assert detect_parameter_type("Unknown Param") == None

    # Test auto-conversion
    normalized, unit = convert_to_normalized(1000, "Frequency")
    assert unit == "Hz"
    assert 0.5 < normalized < 0.7  # 1000Hz should be around 60%

    normalized, unit = convert_to_normalized(-3, "Gain")
    assert unit == "dB"
    assert 0.3 < normalized < 0.5  # -3dB should be around 40%

    print("  Auto-detection OK")


# =============================================================================
# Run All Tests
# =============================================================================

def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("DeviceResolver and Conversions Tests")
    print("="*60 + "\n")

    try:
        # DeviceResolver tests
        test_load_tracks()
        test_load_devices()
        test_load_parameters()
        test_resolve_fix()
        test_resolve_fix_errors()

        # Conversion tests
        test_frequency_conversion()
        test_db_conversion()
        test_ms_conversion()
        test_ratio_conversion()
        test_volume_conversion()
        test_q_conversion()
        test_percent_conversion()
        test_auto_detection()

        print("\n" + "="*60)
        print("ALL TESTS PASSED")
        print("="*60 + "\n")
        return True

    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
