"""
Test script for ALS JSON Output module.

Run: python test_als_json.py (from src directory)
"""

import json
from als_json_output import (
    DeviceInfo, TrackInfo, IssueInfo, ALSDoctorJSON,
    create_json_output, format_json_for_resolver
)


def test_device_info():
    """Test DeviceInfo serialization."""
    print("Testing DeviceInfo...")

    device = DeviceInfo(
        index=0,
        name="EQ Eight",
        device_type="Eq8",
        category="eq",
        is_enabled=True
    )

    d = device.to_dict()
    assert d['index'] == 0
    assert d['name'] == "EQ Eight"
    assert d['is_enabled'] == True
    assert 'plugin_name' not in d  # Optional field not included

    # With plugin name
    device_vst = DeviceInfo(
        index=1,
        name="Serum",
        device_type="PluginDevice",
        category="vst",
        is_enabled=True,
        plugin_name="Serum"
    )

    d = device_vst.to_dict()
    assert d['plugin_name'] == "Serum"

    print("  DeviceInfo OK")


def test_track_info():
    """Test TrackInfo serialization."""
    print("Testing TrackInfo...")

    track = TrackInfo(
        index=0,
        name="Kick",
        track_type="audio",
        volume_db=-3.5,
        pan=0.0,
        is_muted=False,
        is_solo=False,
        devices=[
            DeviceInfo(0, "EQ Eight", "Eq8", "eq", True),
            DeviceInfo(1, "Compressor", "Compressor2", "compressor", True)
        ]
    )

    d = track.to_dict()
    assert d['index'] == 0
    assert d['name'] == "Kick"
    assert d['device_count'] == 2
    assert len(d['devices']) == 2
    assert d['devices'][0]['name'] == "EQ Eight"

    print("  TrackInfo OK")


def test_issue_info():
    """Test IssueInfo serialization."""
    print("Testing IssueInfo...")

    issue = IssueInfo(
        track_name="Bass",
        severity="warning",
        category="signal_flow",
        description="EQ after compressor",
        fix_suggestion="Move EQ before compressor"
    )

    d = issue.to_dict()
    assert d['severity'] == "warning"
    assert d['track_name'] == "Bass"
    assert d['fix_suggestion'] is not None

    # Without optional fields
    issue2 = IssueInfo(
        track_name=None,
        severity="critical",
        category="clutter",
        description="Too many disabled devices"
    )

    d2 = issue2.to_dict()
    assert 'track_name' not in d2
    assert 'fix_suggestion' not in d2

    print("  IssueInfo OK")


def test_als_doctor_json():
    """Test full ALSDoctorJSON serialization."""
    print("Testing ALSDoctorJSON...")

    json_output = ALSDoctorJSON(
        als_path="D:/Projects/MySong/MySong_1.als",
        als_filename="MySong_1.als",
        song_name="MySong",
        analyzed_at="2024-01-01T12:00:00",
        ableton_version="11.3.4",
        tempo=138.0,
        health_score=85,
        grade="B",
        total_issues=5,
        critical_issues=1,
        warning_issues=4,
        total_devices=25,
        disabled_devices=3,
        clutter_percentage=12.0,
        tracks=[
            TrackInfo(
                index=0,
                name="Kick",
                track_type="audio",
                volume_db=0.0,
                pan=0.0,
                is_muted=False,
                is_solo=False,
                devices=[
                    DeviceInfo(0, "EQ Eight", "Eq8", "eq", True),
                    DeviceInfo(1, "Compressor", "Compressor2", "compressor", True)
                ]
            ),
            TrackInfo(
                index=1,
                name="Bass",
                track_type="midi",
                volume_db=-3.0,
                pan=0.0,
                is_muted=False,
                is_solo=False,
                devices=[
                    DeviceInfo(0, "Serum", "PluginDevice", "vst", True, "Serum"),
                    DeviceInfo(1, "EQ Eight", "Eq8", "eq", True)
                ]
            )
        ],
        issues=[
            IssueInfo("Bass", "warning", "signal_flow", "EQ after saturator")
        ]
    )

    # Test to_dict
    d = json_output.to_dict()
    assert d['version'] == '1.0'
    assert d['file']['song_name'] == 'MySong'
    assert d['project']['tempo'] == 138.0
    assert d['health']['score'] == 85
    assert len(d['tracks']) == 2
    assert d['tracks'][0]['name'] == 'Kick'
    assert len(d['issues']) == 1

    # Test to_json
    json_str = json_output.to_json()
    parsed = json.loads(json_str)
    assert parsed['health']['grade'] == 'B'

    print("  ALSDoctorJSON OK")


def test_format_for_resolver():
    """Test format_json_for_resolver output."""
    print("Testing format_json_for_resolver...")

    json_output = ALSDoctorJSON(
        als_path="test.als",
        als_filename="test.als",
        song_name="Test",
        analyzed_at="2024-01-01",
        ableton_version="11",
        tempo=140.0,
        health_score=90,
        grade="A",
        total_issues=0,
        critical_issues=0,
        warning_issues=0,
        total_devices=10,
        disabled_devices=0,
        clutter_percentage=0.0,
        tracks=[
            TrackInfo(
                index=0,
                name="Kick",
                track_type="audio",
                volume_db=0.0,
                pan=0.0,
                is_muted=False,
                is_solo=False,
                devices=[
                    DeviceInfo(0, "EQ Eight", "Eq8", "eq", True),
                    DeviceInfo(1, "Compressor", "Compressor2", "compressor", True)
                ]
            ),
            TrackInfo(
                index=1,
                name="Bass",
                track_type="midi",
                volume_db=0.0,
                pan=0.0,
                is_muted=False,
                is_solo=False,
                devices=[
                    DeviceInfo(0, "Saturator", "Saturator", "saturator", True)
                ]
            )
        ],
        issues=[]
    )

    resolver_data = format_json_for_resolver(json_output)

    assert 'tracks' in resolver_data
    assert len(resolver_data['tracks']) == 2
    assert resolver_data['tracks'][0]['name'] == 'Kick'
    assert resolver_data['tracks'][0]['index'] == 0
    assert len(resolver_data['tracks'][0]['devices']) == 2
    assert resolver_data['tracks'][0]['devices'][0]['name'] == 'EQ Eight'
    assert resolver_data['tracks'][0]['devices'][0]['index'] == 0

    print("  format_json_for_resolver OK")


def test_json_structure_for_claude():
    """Test that JSON structure is suitable for Claude Code."""
    print("Testing JSON structure for Claude Code...")

    json_output = ALSDoctorJSON(
        als_path="test.als",
        als_filename="test.als",
        song_name="Test",
        analyzed_at="2024-01-01",
        ableton_version="11",
        tempo=140.0,
        health_score=75,
        grade="C",
        total_issues=3,
        critical_issues=1,
        warning_issues=2,
        total_devices=15,
        disabled_devices=5,
        clutter_percentage=33.3,
        tracks=[
            TrackInfo(0, "Kick", "audio", 0.0, 0.0, False, False, [
                DeviceInfo(0, "EQ Eight", "Eq8", "eq", True)
            ])
        ],
        issues=[
            IssueInfo("Kick", "critical", "clutter", "Too many disabled devices",
                      "Remove or enable unused devices")
        ]
    )

    json_str = json_output.to_json()
    data = json.loads(json_str)

    # Verify Claude can easily parse key info
    assert data['health']['score'] == 75
    assert data['health']['grade'] == 'C'
    assert data['devices']['clutter_percentage'] == 33.3

    # Verify track/device resolution info is accessible
    track = data['tracks'][0]
    assert track['index'] == 0
    assert track['name'] == 'Kick'
    assert track['devices'][0]['index'] == 0
    assert track['devices'][0]['name'] == 'EQ Eight'

    # Verify issues are actionable
    issue = data['issues'][0]
    assert issue['severity'] == 'critical'
    assert issue['fix_suggestion'] is not None

    print("  JSON structure for Claude Code OK")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("ALS JSON Output Tests")
    print("="*60 + "\n")

    try:
        test_device_info()
        test_track_info()
        test_issue_info()
        test_als_doctor_json()
        test_format_for_resolver()
        test_json_structure_for_claude()

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
