#!/usr/bin/env python3
"""
Tests for Pre-Export Checklist functionality (Story 3.4)

Tests the preflight module for verifying projects are ready for export,
including health score checks, solo/mute detection, and limiter verification.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass, field
from typing import List, Optional

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


# ==================== CheckStatus Tests ====================

def test_check_status_enum():
    """Test CheckStatus enum values."""
    from preflight import CheckStatus

    assert CheckStatus.PASS.value == "pass"
    assert CheckStatus.FAIL.value == "fail"
    assert CheckStatus.WARNING.value == "warning"
    assert CheckStatus.SKIPPED.value == "skipped"

    print("  ✓ CheckStatus enum")


# ==================== PreflightCheckItem Tests ====================

def test_preflight_check_item_dataclass():
    """Test PreflightCheckItem dataclass."""
    from preflight import PreflightCheckItem, CheckStatus

    item = PreflightCheckItem(
        name="Test Check",
        description="Test description",
        status=CheckStatus.PASS,
        details="Test details",
        is_blocker=False
    )

    assert item.name == "Test Check"
    assert item.description == "Test description"
    assert item.status == CheckStatus.PASS
    assert item.details == "Test details"
    assert item.is_blocker is False

    print("  ✓ PreflightCheckItem dataclass")


def test_preflight_check_item_blocker():
    """Test PreflightCheckItem as blocker."""
    from preflight import PreflightCheckItem, CheckStatus

    item = PreflightCheckItem(
        name="Critical Check",
        description="Must pass",
        status=CheckStatus.FAIL,
        is_blocker=True
    )

    assert item.is_blocker is True
    assert item.status == CheckStatus.FAIL

    print("  ✓ PreflightCheckItem blocker")


# ==================== PreflightResult Tests ====================

def test_preflight_result_dataclass():
    """Test PreflightResult dataclass."""
    from preflight import PreflightResult, PreflightCheckItem, CheckStatus

    result = PreflightResult(
        als_path="/test/project.als",
        als_filename="project.als",
        health_score=85,
        grade="A",
        is_ready=True,
        min_score=60,
        strict_mode=False
    )

    assert result.als_path == "/test/project.als"
    assert result.als_filename == "project.als"
    assert result.health_score == 85
    assert result.grade == "A"
    assert result.is_ready is True

    print("  ✓ PreflightResult dataclass")


def test_preflight_result_with_checks():
    """Test PreflightResult with check items."""
    from preflight import PreflightResult, PreflightCheckItem, CheckStatus

    passed = PreflightCheckItem("Pass", "ok", CheckStatus.PASS)
    warning = PreflightCheckItem("Warn", "issue", CheckStatus.WARNING)
    blocker = PreflightCheckItem("Block", "fail", CheckStatus.FAIL, is_blocker=True)

    result = PreflightResult(
        als_path="/test.als",
        als_filename="test.als",
        health_score=50,
        grade="C",
        is_ready=False,
        checks=[passed, warning, blocker],
        blockers=[blocker],
        warnings=[warning],
        passed=[passed],
        total_checks=3,
        passed_count=1,
        failed_count=1,
        warning_count=1
    )

    assert len(result.checks) == 3
    assert len(result.blockers) == 1
    assert len(result.warnings) == 1
    assert len(result.passed) == 1

    print("  ✓ PreflightResult with checks")


# ==================== Health Score Check Tests ====================

def test_check_health_score_pass():
    """Test health score check - passing."""
    from preflight import _check_health_score, CheckStatus

    result = _check_health_score(75, "B", min_score=60, strict=False)

    assert result.status == CheckStatus.PASS
    assert result.is_blocker is False
    assert "75" in result.details

    print("  ✓ Health score check - pass")


def test_check_health_score_fail():
    """Test health score check - failing."""
    from preflight import _check_health_score, CheckStatus

    result = _check_health_score(45, "C", min_score=60, strict=False)

    assert result.status == CheckStatus.FAIL
    assert result.is_blocker is True
    assert "45" in result.details
    assert "requires 60" in result.details

    print("  ✓ Health score check - fail")


def test_check_health_score_strict_pass():
    """Test strict mode health score check - passing."""
    from preflight import _check_health_score, CheckStatus

    result = _check_health_score(85, "A", min_score=60, strict=True)

    assert result.status == CheckStatus.PASS
    assert "strict" in result.description.lower() or "Grade A" in result.description

    print("  ✓ Health score strict mode - pass")


def test_check_health_score_strict_fail():
    """Test strict mode health score check - failing."""
    from preflight import _check_health_score, CheckStatus

    result = _check_health_score(75, "B", min_score=60, strict=True)

    assert result.status == CheckStatus.FAIL
    assert result.is_blocker is True
    assert "80" in result.details or "strict" in result.details.lower()

    print("  ✓ Health score strict mode - fail")


# ==================== Critical Issues Check Tests ====================

def test_check_critical_issues_none():
    """Test critical issues check - no issues."""
    from preflight import _check_critical_issues, CheckStatus

    result = _check_critical_issues(0)

    assert result.status == CheckStatus.PASS
    assert result.is_blocker is False

    print("  ✓ Critical issues - none")


def test_check_critical_issues_found():
    """Test critical issues check - issues found."""
    from preflight import _check_critical_issues, CheckStatus

    result = _check_critical_issues(3)

    assert result.status == CheckStatus.FAIL
    assert result.is_blocker is True
    assert "3" in result.details or "3" in result.description

    print("  ✓ Critical issues - found")


# ==================== Solo'd Tracks Check Tests ====================

@dataclass
class MockTrack:
    """Mock track for testing."""
    track_name: str
    track_type: str = "audio"
    is_solo: bool = False
    is_muted: bool = True  # True = active (not muted)
    devices: List = field(default_factory=list)


def test_check_solo_tracks_none():
    """Test solo'd tracks check - no solo."""
    from preflight import _check_solo_tracks, CheckStatus

    tracks = [
        MockTrack("Kick", is_solo=False),
        MockTrack("Bass", is_solo=False),
        MockTrack("Lead", is_solo=False)
    ]

    result = _check_solo_tracks(tracks)

    assert result.status == CheckStatus.PASS
    assert result.is_blocker is False

    print("  ✓ Solo'd tracks - none")


def test_check_solo_tracks_found():
    """Test solo'd tracks check - solo found."""
    from preflight import _check_solo_tracks, CheckStatus

    tracks = [
        MockTrack("Kick", is_solo=False),
        MockTrack("Bass", is_solo=True),
        MockTrack("Lead", is_solo=False)
    ]

    result = _check_solo_tracks(tracks)

    assert result.status == CheckStatus.FAIL
    assert result.is_blocker is True
    assert "Bass" in result.details

    print("  ✓ Solo'd tracks - found")


def test_check_solo_tracks_multiple():
    """Test solo'd tracks check - multiple solo."""
    from preflight import _check_solo_tracks, CheckStatus

    tracks = [
        MockTrack("Kick", is_solo=True),
        MockTrack("Bass", is_solo=True),
        MockTrack("Lead", is_solo=False)
    ]

    result = _check_solo_tracks(tracks)

    assert result.status == CheckStatus.FAIL
    assert result.is_blocker is True
    assert "2" in result.description  # 2 solo'd tracks

    print("  ✓ Solo'd tracks - multiple")


# ==================== Master Mute Check Tests ====================

def test_check_master_mute_active():
    """Test master mute check - master active."""
    from preflight import _check_master_mute, CheckStatus

    master = MockTrack("Master", track_type="master", is_muted=True)  # True = active

    result = _check_master_mute(master)

    assert result.status == CheckStatus.PASS
    assert result.is_blocker is False

    print("  ✓ Master mute - active")


def test_check_master_mute_muted():
    """Test master mute check - master muted."""
    from preflight import _check_master_mute, CheckStatus

    master = MockTrack("Master", track_type="master", is_muted=False)  # False = muted

    result = _check_master_mute(master)

    assert result.status == CheckStatus.FAIL
    assert result.is_blocker is True

    print("  ✓ Master mute - muted")


def test_check_master_mute_none():
    """Test master mute check - no master track."""
    from preflight import _check_master_mute, CheckStatus

    result = _check_master_mute(None)

    assert result.status == CheckStatus.SKIPPED

    print("  ✓ Master mute - no master")


# ==================== Limiter Ceiling Check Tests ====================

@dataclass
class MockDevice:
    """Mock device for testing."""
    name: str
    category: str = "unknown"
    is_enabled: bool = True
    parameters: dict = field(default_factory=dict)


def test_check_limiter_ceiling_safe():
    """Test limiter ceiling check - safe level."""
    from preflight import _check_limiter_ceiling, CheckStatus

    limiter = MockDevice(
        name="Limiter",
        category="DeviceCategory.LIMITER",
        parameters={"Ceiling": -0.5}
    )
    master = MockTrack("Master", devices=[limiter])

    result = _check_limiter_ceiling(master)

    assert result.status == CheckStatus.PASS
    assert result.is_blocker is False

    print("  ✓ Limiter ceiling - safe")


def test_check_limiter_ceiling_high():
    """Test limiter ceiling check - too high."""
    from preflight import _check_limiter_ceiling, CheckStatus

    limiter = MockDevice(
        name="Limiter",
        category="DeviceCategory.LIMITER",
        parameters={"Ceiling": 0.0}
    )
    master = MockTrack("Master", devices=[limiter])

    result = _check_limiter_ceiling(master)

    assert result.status == CheckStatus.WARNING
    assert result.is_blocker is False
    assert "0.0" in result.details

    print("  ✓ Limiter ceiling - high")


def test_check_limiter_ceiling_no_limiter():
    """Test limiter ceiling check - no limiter."""
    from preflight import _check_limiter_ceiling, CheckStatus

    eq = MockDevice(name="EQ8", category="DeviceCategory.EQ")
    master = MockTrack("Master", devices=[eq])

    result = _check_limiter_ceiling(master)

    assert result.status == CheckStatus.WARNING
    assert "No active limiter" in result.description

    print("  ✓ Limiter ceiling - no limiter")


def test_check_limiter_ceiling_disabled():
    """Test limiter ceiling check - limiter disabled."""
    from preflight import _check_limiter_ceiling, CheckStatus

    limiter = MockDevice(
        name="Limiter",
        category="DeviceCategory.LIMITER",
        is_enabled=False,
        parameters={"Ceiling": -0.3}
    )
    master = MockTrack("Master", devices=[limiter])

    result = _check_limiter_ceiling(master)

    # Disabled limiter should not count
    assert result.status == CheckStatus.WARNING
    assert "No active limiter" in result.description

    print("  ✓ Limiter ceiling - disabled")


# ==================== Disabled Devices Check Tests ====================

def test_check_disabled_on_master_none():
    """Test master disabled devices - none disabled."""
    from preflight import _check_disabled_on_master, CheckStatus

    devices = [
        MockDevice("EQ8", is_enabled=True),
        MockDevice("Limiter", is_enabled=True)
    ]
    master = MockTrack("Master", devices=devices)

    result = _check_disabled_on_master(master)

    assert result.status == CheckStatus.PASS

    print("  ✓ Master disabled devices - none")


def test_check_disabled_on_master_found():
    """Test master disabled devices - some disabled."""
    from preflight import _check_disabled_on_master, CheckStatus

    devices = [
        MockDevice("EQ8", is_enabled=True),
        MockDevice("Compressor", is_enabled=False),
        MockDevice("Limiter", is_enabled=True)
    ]
    master = MockTrack("Master", devices=devices)

    result = _check_disabled_on_master(master)

    assert result.status == CheckStatus.WARNING
    assert "Compressor" in result.details

    print("  ✓ Master disabled devices - found")


# ==================== Clutter Check Tests ====================

def test_check_clutter_low():
    """Test clutter check - low clutter."""
    from preflight import _check_clutter, CheckStatus

    result = _check_clutter(15.0)

    assert result.status == CheckStatus.PASS

    print("  ✓ Clutter check - low")


def test_check_clutter_high():
    """Test clutter check - high clutter."""
    from preflight import _check_clutter, CheckStatus

    result = _check_clutter(45.0)

    assert result.status == CheckStatus.WARNING
    assert "45.0" in result.details

    print("  ✓ Clutter check - high")


# ==================== Preflight Check Integration Tests ====================

def test_preflight_check_file_not_found():
    """Test preflight check - file not found."""
    from preflight import preflight_check

    result, message = preflight_check("/nonexistent/file.als")

    assert result is None
    assert "not found" in message.lower()

    print("  ✓ Preflight check - file not found")


def test_preflight_check_wrong_extension():
    """Test preflight check - wrong file extension."""
    from preflight import preflight_check
    import tempfile
    import os

    # Create a temp file with wrong extension
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        temp_path = f.name

    try:
        result, message = preflight_check(temp_path)

        assert result is None
        assert ".als" in message
    finally:
        os.unlink(temp_path)

    print("  ✓ Preflight check - wrong extension")


def test_preflight_check_with_mock_analyzer():
    """Test preflight check with mock analyzer."""
    from preflight import preflight_check, PreflightResult
    import tempfile
    import os

    # Create a temp .als file
    with tempfile.NamedTemporaryFile(suffix=".als", delete=False) as f:
        f.write(b"mock data")
        temp_path = f.name

    # Create mock analysis result
    @dataclass
    class MockScanResult:
        als_path: str
        health_score: int = 85
        grade: str = "A"
        total_issues: int = 2
        critical_issues: int = 0
        warning_issues: int = 2
        total_devices: int = 10
        disabled_devices: int = 1
        clutter_percentage: float = 10.0
        issues: List = field(default_factory=list)

    @dataclass
    class MockAnalysis:
        tracks: List = field(default_factory=list)

    def mock_analyzer(path):
        master = MockTrack(
            "Master",
            track_type="master",
            is_muted=True,  # Active
            devices=[MockDevice("Limiter", parameters={"Ceiling": -0.3})]
        )
        analysis = MockAnalysis(tracks=[
            MockTrack("Kick"),
            MockTrack("Bass"),
            master
        ])
        scan_result = MockScanResult(als_path=str(path))
        return analysis, scan_result

    try:
        result, message = preflight_check(temp_path, analyzer_func=mock_analyzer)

        assert result is not None
        assert result.is_ready is True
        assert result.health_score == 85
        assert result.grade == "A"
    finally:
        os.unlink(temp_path)

    print("  ✓ Preflight check - with mock analyzer")


def test_preflight_check_with_blockers():
    """Test preflight check with blocking issues."""
    from preflight import preflight_check, PreflightResult
    import tempfile
    import os

    # Create a temp .als file
    with tempfile.NamedTemporaryFile(suffix=".als", delete=False) as f:
        f.write(b"mock data")
        temp_path = f.name

    @dataclass
    class MockScanResult:
        als_path: str
        health_score: int = 40  # Below threshold
        grade: str = "C"
        total_issues: int = 5
        critical_issues: int = 2  # Has critical issues
        warning_issues: int = 3
        total_devices: int = 10
        disabled_devices: int = 3
        clutter_percentage: float = 35.0
        issues: List = field(default_factory=list)

    @dataclass
    class MockAnalysis:
        tracks: List = field(default_factory=list)

    def mock_analyzer(path):
        master = MockTrack(
            "Master",
            track_type="master",
            is_muted=True,
            devices=[]
        )
        solo_track = MockTrack("Vocals", is_solo=True)  # Solo'd track
        analysis = MockAnalysis(tracks=[solo_track, master])
        scan_result = MockScanResult(als_path=str(path))
        return analysis, scan_result

    try:
        result, message = preflight_check(temp_path, min_score=60, analyzer_func=mock_analyzer)

        assert result is not None
        assert result.is_ready is False
        assert len(result.blockers) > 0  # Should have blockers
    finally:
        os.unlink(temp_path)

    print("  ✓ Preflight check - with blockers")


def test_preflight_check_strict_mode():
    """Test preflight check in strict mode."""
    from preflight import preflight_check, PreflightResult
    import tempfile
    import os

    # Create a temp .als file
    with tempfile.NamedTemporaryFile(suffix=".als", delete=False) as f:
        f.write(b"mock data")
        temp_path = f.name

    @dataclass
    class MockScanResult:
        als_path: str
        health_score: int = 75  # Grade B - not strict enough
        grade: str = "B"
        total_issues: int = 2
        critical_issues: int = 0
        warning_issues: int = 2
        total_devices: int = 10
        disabled_devices: int = 0
        clutter_percentage: float = 5.0
        issues: List = field(default_factory=list)

    @dataclass
    class MockAnalysis:
        tracks: List = field(default_factory=list)

    def mock_analyzer(path):
        master = MockTrack("Master", track_type="master", is_muted=True, devices=[])
        analysis = MockAnalysis(tracks=[master])
        scan_result = MockScanResult(als_path=str(path))
        return analysis, scan_result

    try:
        result, message = preflight_check(temp_path, strict=True, analyzer_func=mock_analyzer)

        assert result is not None
        assert result.is_ready is False  # Should fail strict mode
        assert result.strict_mode is True
        # Health score check should be a blocker
        health_blockers = [b for b in result.blockers if "Health" in b.name]
        assert len(health_blockers) > 0
    finally:
        os.unlink(temp_path)

    print("  ✓ Preflight check - strict mode")


# ==================== Summary Function Tests ====================

def test_get_preflight_summary_ready():
    """Test preflight summary - ready to export."""
    from preflight import PreflightResult, PreflightCheckItem, CheckStatus, get_preflight_summary

    result = PreflightResult(
        als_path="/test.als",
        als_filename="test.als",
        health_score=90,
        grade="A",
        is_ready=True,
        passed=[PreflightCheckItem("Test", "ok", CheckStatus.PASS)],
        total_checks=1,
        passed_count=1
    )

    summary = get_preflight_summary(result)

    assert "GO" in summary
    assert "Ready to export" in summary
    assert "90" in summary

    print("  ✓ Preflight summary - ready")


def test_get_preflight_summary_not_ready():
    """Test preflight summary - not ready."""
    from preflight import PreflightResult, PreflightCheckItem, CheckStatus, get_preflight_summary

    blocker = PreflightCheckItem("Critical", "fail", CheckStatus.FAIL, "Must fix", is_blocker=True)

    result = PreflightResult(
        als_path="/test.als",
        als_filename="test.als",
        health_score=40,
        grade="C",
        is_ready=False,
        blockers=[blocker],
        total_checks=1,
        failed_count=1
    )

    summary = get_preflight_summary(result)

    assert "NO-GO" in summary
    assert "BLOCKERS" in summary

    print("  ✓ Preflight summary - not ready")


# ==================== Run All Tests ====================

def run_tests():
    """Run all preflight tests."""
    print("=" * 60)
    print("Pre-Export Checklist Tests (Story 3.4)")
    print("=" * 60)
    print("")

    tests = [
        # Enum and dataclass tests
        test_check_status_enum,
        test_preflight_check_item_dataclass,
        test_preflight_check_item_blocker,
        test_preflight_result_dataclass,
        test_preflight_result_with_checks,

        # Health score tests
        test_check_health_score_pass,
        test_check_health_score_fail,
        test_check_health_score_strict_pass,
        test_check_health_score_strict_fail,

        # Critical issues tests
        test_check_critical_issues_none,
        test_check_critical_issues_found,

        # Solo'd tracks tests
        test_check_solo_tracks_none,
        test_check_solo_tracks_found,
        test_check_solo_tracks_multiple,

        # Master mute tests
        test_check_master_mute_active,
        test_check_master_mute_muted,
        test_check_master_mute_none,

        # Limiter ceiling tests
        test_check_limiter_ceiling_safe,
        test_check_limiter_ceiling_high,
        test_check_limiter_ceiling_no_limiter,
        test_check_limiter_ceiling_disabled,

        # Disabled devices tests
        test_check_disabled_on_master_none,
        test_check_disabled_on_master_found,

        # Clutter tests
        test_check_clutter_low,
        test_check_clutter_high,

        # Integration tests
        test_preflight_check_file_not_found,
        test_preflight_check_wrong_extension,
        test_preflight_check_with_mock_analyzer,
        test_preflight_check_with_blockers,
        test_preflight_check_strict_mode,

        # Summary tests
        test_get_preflight_summary_ready,
        test_get_preflight_summary_not_ready,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  X {test.__name__}: {e}")

    print("")
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
