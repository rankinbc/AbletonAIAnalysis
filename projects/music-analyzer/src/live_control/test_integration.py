"""
Integration Tests for Live DAW Control.

Tests the complete coaching pipeline flow without requiring Ableton.
Uses mock data to simulate MCP responses.

Run: python test_integration.py (from live_control directory)
"""

import json
import tempfile
from pathlib import Path

# Import all components
from state import (
    ChangeTracker, Change, get_tracker, record_change,
    get_undo_info, confirm_undo, clear_session
)
from resolver import DeviceResolver, get_resolver, reset_resolver
from conversions import (
    hz_to_normalized, db_to_normalized, normalized_to_hz, normalized_to_db,
    convert_to_normalized, convert_from_normalized
)
from reference_integration import (
    ReferenceIntegration, get_reference_integration, GapAnalysis
)
from errors import (
    CoachingError, ErrorCategory, RecoveryAction,
    track_not_found, device_not_found, mcp_timeout,
    format_manual_instructions, can_retry, get_error_handler
)


# =============================================================================
# Mock Data
# =============================================================================

MOCK_TRACKS_RESPONSE = json.dumps({
    "success": True,
    "tracks": [
        {"index": 0, "name": "Kick"},
        {"index": 1, "name": "Bass"},
        {"index": 2, "name": "Lead Synth"},
        {"index": 3, "name": "Pads"},
        {"index": 4, "name": "Master"}
    ]
})

MOCK_DEVICES_BASS = json.dumps({
    "success": True,
    "track_index": 1,
    "devices": [
        {"index": 0, "name": "Serum"},
        {"index": 1, "name": "EQ Eight"},
        {"index": 2, "name": "Compressor"},
        {"index": 3, "name": "Saturator"}
    ]
})

MOCK_PARAMS_EQ = json.dumps({
    "success": True,
    "track_index": 1,
    "device_index": 1,
    "parameters": [
        {"index": 0, "name": "Device On"},
        {"index": 1, "name": "Band 1 Frequency"},
        {"index": 2, "name": "Band 1 Gain"},
        {"index": 3, "name": "Band 1 Q"},
        {"index": 4, "name": "Band 2 Frequency"},
        {"index": 5, "name": "Band 2 Gain"}
    ]
})

MOCK_PROFILE = {
    'name': 'Trance Reference',
    'version': '1.0',
    'created_date': '2024-01-01',
    'track_count': 20,
    'feature_statistics': {
        'integrated_lufs': {
            'mean': -8.0, 'std': 1.5, 'min': -12.0, 'max': -5.0,
            'p10': -10.0, 'p25': -9.0, 'p50': -8.0, 'p75': -7.0, 'p90': -6.0,
            'confidence_interval_95': [-8.5, -7.5],
            'acceptable_range': [-10.0, -6.0]
        },
        'bass_energy': {
            'mean': 0.25, 'std': 0.05, 'min': 0.15, 'max': 0.35,
            'p10': 0.18, 'p25': 0.22, 'p50': 0.25, 'p75': 0.28, 'p90': 0.32,
            'confidence_interval_95': [0.23, 0.27],
            'acceptable_range': [0.18, 0.32]
        },
        'stereo_width': {
            'mean': 0.65, 'std': 0.1, 'min': 0.4, 'max': 0.85,
            'p10': 0.5, 'p25': 0.58, 'p50': 0.65, 'p75': 0.72, 'p90': 0.8,
            'confidence_interval_95': [0.6, 0.7],
            'acceptable_range': [0.5, 0.8]
        }
    },
    'clusters': [],
    'track_metadata': []
}


# =============================================================================
# Integration Tests
# =============================================================================

def test_full_coaching_flow():
    """
    Test the complete coaching flow:
    1. Load track names
    2. Load devices
    3. Analyze gaps against reference
    4. Resolve fix to indices
    5. Record change for undo
    """
    print("Testing full coaching flow...")

    # Use temp file for session
    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "test_session.json"
        tracker = ChangeTracker(session_file=session_file)
        resolver = DeviceResolver()
        integration = ReferenceIntegration()

        # Step 1: Load tracks from mock MCP response
        assert resolver.load_tracks_from_mcp(MOCK_TRACKS_RESPONSE)
        assert resolver.track_count == 5

        # Step 2: Load devices for Bass track
        assert resolver.load_devices_from_mcp(1, MOCK_DEVICES_BASS)
        assert len(resolver.get_devices(1)) == 4

        # Step 3: Load parameters for EQ Eight
        assert resolver.load_parameters_from_mcp(1, 1, MOCK_PARAMS_EQ)

        # Step 4: Load reference profile
        assert integration.load_profile_dict(MOCK_PROFILE)

        # Step 5: Analyze user track against reference
        user_metrics = {
            'integrated_lufs': -12.0,  # Too quiet
            'bass_energy': 0.35,        # Too high
            'stereo_width': 0.65        # Good
        }
        gaps = integration.analyze_gaps(user_metrics, "User Track")

        assert gaps.total_features == 3
        assert gaps.in_range_count == 1  # Only stereo_width
        assert gaps.gap_count == 2

        # Step 6: Get prioritized issues
        top_issues = gaps.get_prioritized_gaps(2)
        assert len(top_issues) == 2

        # Step 7: Resolve a fix (reduce bass EQ)
        fix_spec = {
            'track_name': 'Bass',
            'device_name': 'EQ Eight',
            'parameter_name': 'Band 1 Gain',
            'value': db_to_normalized(-3)  # Cut 3dB
        }
        resolved = resolver.resolve_fix(fix_spec)

        assert resolved.track_index == 1
        assert resolved.device_index == 1
        assert resolved.parameter_index == 2  # Band 1 Gain

        # Step 8: Record the change for undo
        # Simulate reading previous value (would come from MCP)
        previous_value = db_to_normalized(0)  # Was at 0dB
        new_value = resolved.value

        change = Change(
            track_index=resolved.track_index,
            track_name=resolved.track_name,
            device_index=resolved.device_index,
            device_name=resolved.device_name,
            parameter_index=resolved.parameter_index,
            parameter_name=resolved.parameter_name,
            previous_value=previous_value,
            new_value=new_value,
            description="Reduce bass EQ band 1 by 3dB",
            change_type="parameter"
        )
        tracker.record(change)

        assert tracker.change_count == 1
        assert tracker.can_undo == True

        # Step 9: Verify undo info
        undo = tracker.get_undo()
        assert undo is not None
        assert undo.previous_value == previous_value

        # Step 10: Verify session persists
        tracker2 = ChangeTracker(session_file=session_file)
        assert tracker2.change_count == 1

    print("  Full coaching flow OK")


def test_value_conversion_roundtrip():
    """Test that value conversions round-trip correctly."""
    print("Testing value conversion roundtrip...")

    # Frequency
    for hz in [50, 100, 500, 1000, 5000, 10000]:
        normalized = hz_to_normalized(hz)
        back = normalized_to_hz(normalized)
        assert abs(hz - back) < 1, f"Hz roundtrip failed: {hz} -> {normalized} -> {back}"

    # dB
    for db in [-15, -10, -6, -3, 0, 3, 6, 10, 15]:
        normalized = db_to_normalized(db)
        back = normalized_to_db(normalized)
        assert abs(db - back) < 0.1, f"dB roundtrip failed: {db}"

    # Auto-detection
    normalized, unit = convert_to_normalized(1000, "Low Frequency")
    assert unit == "Hz"
    assert 0.5 < normalized < 0.7

    value, unit = convert_from_normalized(0.5, "Gain")
    assert unit == "dB"
    assert -1 < value < 1  # Should be around 0dB

    print("  Value conversion roundtrip OK")


def test_error_handling_flow():
    """Test error handling and recovery."""
    print("Testing error handling flow...")

    handler = get_error_handler(verbose=True)
    handler.clear()

    # Test track not found error
    error = track_not_found("NonExistent", ["Kick", "Bass", "Lead"])
    msg = handler.handle(error)

    assert handler.has_errors
    assert handler.error_count == 1
    assert "NonExistent" in msg
    assert can_retry(error) == True  # REFRESH is retriable

    # Test manual instructions
    instructions = format_manual_instructions(
        operation="reduce bass",
        track_name="Bass",
        device_name="EQ Eight",
        parameter_name="Band 1 Gain",
        value=0.4,
        display_value="-3dB"
    )
    assert "Bass" in instructions
    assert "EQ Eight" in instructions
    assert "-3dB" in instructions

    # Test MCP timeout
    error2 = mcp_timeout("set_device_parameter")
    assert error2.recovery_action == RecoveryAction.RETRY
    assert can_retry(error2) == True

    print("  Error handling flow OK")


def test_session_persistence_across_invocations():
    """Test that session state persists correctly."""
    print("Testing session persistence...")

    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "test_session.json"

        # First invocation: create changes
        tracker1 = ChangeTracker(session_file=session_file)
        tracker1.set_song("Test Song")

        tracker1.record(Change(
            track_index=0, track_name="Kick",
            previous_value=0.85, new_value=0.7,
            description="Reduce kick volume",
            change_type="volume"
        ))
        tracker1.record(Change(
            track_index=1, track_name="Bass",
            previous_value=0.0, new_value=-0.2,
            description="Pan bass left",
            change_type="pan"
        ))

        assert tracker1.change_count == 2

        # Second invocation: load and verify
        tracker2 = ChangeTracker(session_file=session_file)
        assert tracker2.song_name == "Test Song"
        assert tracker2.change_count == 2
        assert tracker2.can_undo == True

        # Undo one change
        tracker2.confirm_undo()
        assert tracker2.change_count == 1
        assert tracker2.can_redo == True

        # Third invocation: verify undo persisted
        tracker3 = ChangeTracker(session_file=session_file)
        assert tracker3.change_count == 1
        assert tracker3.can_redo == True

        # Redo
        tracker3.confirm_redo()
        assert tracker3.change_count == 2

    print("  Session persistence OK")


def test_ab_comparison_flow():
    """Test A/B comparison workflow."""
    print("Testing A/B comparison flow...")

    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "test_session.json"
        tracker = ChangeTracker(session_file=session_file)

        # Start A/B comparison
        original_value = 0.5
        fix_value = 0.3

        ab = tracker.start_ab(
            description="Test EQ fix",
            track_index=1,
            original_value=original_value,
            fix_value=fix_value,
            device_index=0,
            parameter_index=4
        )

        assert tracker.is_comparing == True
        assert ab.current_state == 'B'
        assert ab.current_value == fix_value

        # Toggle to A
        new_state = tracker.toggle_ab()
        assert new_state == 'A'
        assert tracker.ab_state.current_value == original_value

        # Toggle back to B
        tracker.toggle_ab()
        assert tracker.ab_state.current_state == 'B'

        # End comparison, keeping B
        change = tracker.end_ab('B')
        assert change is not None
        assert tracker.is_comparing == False
        assert tracker.change_count == 1

        # Verify change was recorded
        last = tracker.get_last_change()
        assert last.previous_value == original_value
        assert last.new_value == fix_value

    print("  A/B comparison flow OK")


def test_resolver_with_als_doctor_json():
    """Test DeviceResolver loading from ALS Doctor JSON format."""
    print("Testing resolver with ALS Doctor JSON...")

    # Simulate ALS Doctor JSON output structure
    als_doctor_data = {
        'tracks': [
            {
                'index': 0,
                'name': 'Kick',
                'type': 'audio',
                'devices': [
                    {'index': 0, 'name': 'EQ Eight', 'type': 'Eq8'},
                    {'index': 1, 'name': 'Compressor', 'type': 'Compressor2'}
                ]
            },
            {
                'index': 1,
                'name': 'Bass',
                'type': 'midi',
                'devices': [
                    {'index': 0, 'name': 'Serum', 'type': 'PluginDevice'},
                    {'index': 1, 'name': 'EQ Eight', 'type': 'Eq8'}
                ]
            }
        ]
    }

    resolver = DeviceResolver()
    resolver.load_from_als_doctor(als_doctor_data)

    assert resolver.track_count == 2
    assert resolver.resolve_track("Kick") == 0
    assert resolver.resolve_track("Bass") == 1
    assert resolver.resolve_device(0, "EQ Eight") == 0
    assert resolver.resolve_device(0, "Compressor") == 1
    assert resolver.resolve_device(1, "Serum") == 0

    print("  Resolver with ALS Doctor JSON OK")


def test_gap_analysis_recommendations():
    """Test that gap analysis generates useful recommendations."""
    print("Testing gap analysis recommendations...")

    integration = ReferenceIntegration()
    integration.load_profile_dict(MOCK_PROFILE)

    # Simulate a track with issues
    user_metrics = {
        'integrated_lufs': -15.0,  # Way too quiet
        'bass_energy': 0.10,        # Way too low
        'stereo_width': 0.65        # Good
    }

    gaps = integration.analyze_gaps(user_metrics, "Problem Track")

    # Should identify 2 issues
    assert gaps.gap_count == 2

    # Get prioritized gaps
    top = gaps.get_prioritized_gaps(2)
    assert len(top) == 2

    # Check that fix suggestions are generated
    for gap in top:
        assert gap.fix_suggestion is not None
        assert len(gap.fix_suggestion) > 0

    # Check severity levels
    lufs_gap = next(g for g in gaps.gaps if g.feature_name == 'integrated_lufs')
    assert lufs_gap.severity in ('significant', 'critical')
    assert lufs_gap.direction == 'below'

    print("  Gap analysis recommendations OK")


def test_mcp_json_parsing():
    """Test parsing of MCP JSON responses."""
    print("Testing MCP JSON parsing...")

    # Successful responses
    success_cases = [
        ('{"success": true, "tracks": [{"index": 0, "name": "Kick"}]}', True),
        ('{"success": true, "track_index": 0, "volume": 0.85}', True),
        ('{"success": false, "error": "Track not found"}', False),
    ]

    for json_str, expected_success in success_cases:
        data = json.loads(json_str)
        assert data.get('success') == expected_success

    # DeviceResolver should handle these
    resolver = DeviceResolver()

    # Good response
    assert resolver.load_tracks_from_mcp(
        '{"success": true, "tracks": [{"index": 0, "name": "Test"}]}'
    ) == True

    # Error response
    assert resolver.load_tracks_from_mcp(
        '{"success": false, "error": "Connection failed"}'
    ) == False

    # Invalid JSON
    assert resolver.load_tracks_from_mcp('not json') == False

    print("  MCP JSON parsing OK")


# =============================================================================
# Run All Tests
# =============================================================================

def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("Live Control Integration Tests")
    print("="*60 + "\n")

    try:
        test_full_coaching_flow()
        test_value_conversion_roundtrip()
        test_error_handling_flow()
        test_session_persistence_across_invocations()
        test_ab_comparison_flow()
        test_resolver_with_als_doctor_json()
        test_gap_analysis_recommendations()
        test_mcp_json_parsing()

        print("\n" + "="*60)
        print("ALL INTEGRATION TESTS PASSED")
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
