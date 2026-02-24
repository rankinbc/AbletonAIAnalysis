"""
Test script for Reference Integration.

Run: python test_reference.py (from live_control directory)
"""

import json
from reference_integration import (
    ReferenceIntegration,
    FeatureGap,
    GapAnalysis,
    get_reference_integration,
    FEATURE_MAPPING,
    SEVERITY_THRESHOLDS
)


def create_mock_profile() -> dict:
    """Create a mock profile for testing."""
    return {
        'name': 'Test Trance Profile',
        'version': '1.0',
        'created_date': '2024-01-01',
        'track_count': 10,
        'feature_statistics': {
            'integrated_lufs': {
                'mean': -8.0,
                'std': 1.5,
                'min': -12.0,
                'max': -5.0,
                'p10': -10.0,
                'p25': -9.0,
                'p50': -8.0,
                'p75': -7.0,
                'p90': -6.0,
                'confidence_interval_95': [-8.5, -7.5],
                'acceptable_range': [-10.0, -6.0]
            },
            'dynamic_range': {
                'mean': 8.0,
                'std': 2.0,
                'min': 4.0,
                'max': 12.0,
                'p10': 5.0,
                'p25': 6.5,
                'p50': 8.0,
                'p75': 9.5,
                'p90': 11.0,
                'confidence_interval_95': [7.0, 9.0],
                'acceptable_range': [5.0, 11.0]
            },
            'tempo': {
                'mean': 138.0,
                'std': 4.0,
                'min': 130.0,
                'max': 145.0,
                'p10': 132.0,
                'p25': 135.0,
                'p50': 138.0,
                'p75': 141.0,
                'p90': 144.0,
                'confidence_interval_95': [136.0, 140.0],
                'acceptable_range': [132.0, 144.0]
            },
            'stereo_width': {
                'mean': 0.65,
                'std': 0.15,
                'min': 0.3,
                'max': 0.9,
                'p10': 0.45,
                'p25': 0.55,
                'p50': 0.65,
                'p75': 0.75,
                'p90': 0.85,
                'confidence_interval_95': [0.55, 0.75],
                'acceptable_range': [0.45, 0.85]
            },
            'pumping_score': {
                'mean': 0.7,
                'std': 0.1,
                'min': 0.4,
                'max': 0.9,
                'p10': 0.55,
                'p25': 0.62,
                'p50': 0.7,
                'p75': 0.78,
                'p90': 0.85,
                'confidence_interval_95': [0.65, 0.75],
                'acceptable_range': [0.55, 0.85]
            }
        },
        'clusters': [
            {
                'cluster_id': 0,
                'name': 'Uplifting Trance',
                'track_indices': [0, 1, 2],
                'centroid': {'tempo': 140.0, 'pumping_score': 0.75},
                'variance': {'tempo': 4.0, 'pumping_score': 0.05},
                'distinctive_features': ['high_energy', 'melodic'],
                'exemplar_tracks': [0]
            },
            {
                'cluster_id': 1,
                'name': 'Tech Trance',
                'track_indices': [3, 4, 5],
                'centroid': {'tempo': 136.0, 'pumping_score': 0.65},
                'variance': {'tempo': 3.0, 'pumping_score': 0.08},
                'distinctive_features': ['driving_bass', 'minimal'],
                'exemplar_tracks': [3]
            }
        ],
        'track_metadata': []
    }


def test_load_profile():
    """Test loading a profile from dict."""
    print("Testing profile loading...")

    integration = ReferenceIntegration()
    profile_data = create_mock_profile()

    assert integration.load_profile_dict(profile_data) == True
    assert integration.is_loaded == True
    assert integration.profile_name == 'Test Trance Profile'

    print("  Profile loading OK")


def test_get_feature_stats():
    """Test getting feature statistics."""
    print("Testing feature stats...")

    integration = ReferenceIntegration()
    integration.load_profile_dict(create_mock_profile())

    # Direct lookup
    stats = integration.get_feature_stats('tempo')
    assert stats is not None
    assert stats.mean == 138.0
    assert stats.acceptable_range == (132.0, 144.0)

    # Mapped lookup (lufs -> integrated_lufs)
    stats = integration.get_feature_stats('lufs')
    assert stats is not None
    assert stats.mean == -8.0

    # Missing feature
    stats = integration.get_feature_stats('nonexistent')
    assert stats is None

    print("  Feature stats OK")


def test_is_in_range():
    """Test range checking."""
    print("Testing range checking...")

    integration = ReferenceIntegration()
    integration.load_profile_dict(create_mock_profile())

    # In range
    assert integration.is_in_range('tempo', 138.0) == True
    assert integration.is_in_range('tempo', 135.0) == True

    # Out of range
    assert integration.is_in_range('tempo', 125.0) == False
    assert integration.is_in_range('tempo', 150.0) == False

    # Unknown feature (should return True)
    assert integration.is_in_range('unknown', 100.0) == True

    print("  Range checking OK")


def test_get_fix_target():
    """Test getting fix targets."""
    print("Testing fix targets...")

    integration = ReferenceIntegration()
    integration.load_profile_dict(create_mock_profile())

    target = integration.get_fix_target('integrated_lufs')
    assert target is not None
    assert target['target'] == -8.0
    assert target['acceptable_low'] == -10.0
    assert target['acceptable_high'] == -6.0

    # Missing feature
    target = integration.get_fix_target('nonexistent')
    assert target is None

    print("  Fix targets OK")


def test_analyze_gaps_in_range():
    """Test gap analysis with values in range."""
    print("Testing gap analysis (in range)...")

    integration = ReferenceIntegration()
    integration.load_profile_dict(create_mock_profile())

    # All values in range
    analysis_results = {
        'integrated_lufs': -8.0,
        'tempo': 138.0,
        'stereo_width': 0.65,
        'pumping_score': 0.7
    }

    gaps = integration.analyze_gaps(analysis_results, "Test Track")

    assert gaps.total_features == 4
    assert gaps.in_range_count == 4
    assert gaps.gap_count == 0
    assert gaps.overall_score > 80

    # All gaps should be severity 'good'
    for gap in gaps.gaps:
        assert gap.is_in_range == True
        assert gap.severity == 'good'

    print("  Gap analysis (in range) OK")


def test_analyze_gaps_out_of_range():
    """Test gap analysis with values out of range."""
    print("Testing gap analysis (out of range)...")

    integration = ReferenceIntegration()
    integration.load_profile_dict(create_mock_profile())

    # Some values out of range
    analysis_results = {
        'integrated_lufs': -14.0,  # Way too quiet (below -10)
        'tempo': 138.0,            # In range
        'stereo_width': 0.2,       # Too narrow (below 0.45)
        'pumping_score': 0.3       # Too weak (below 0.55)
    }

    gaps = integration.analyze_gaps(analysis_results, "Test Track")

    assert gaps.total_features == 4
    assert gaps.in_range_count == 1  # Only tempo
    assert gaps.gap_count == 3

    # Check prioritized gaps
    prioritized = gaps.get_prioritized_gaps(3)
    assert len(prioritized) == 3

    # Most severe should be first
    assert prioritized[0].priority_score >= prioritized[1].priority_score

    # Check lufs gap
    lufs_gap = next((g for g in gaps.gaps if g.feature_name == 'integrated_lufs'), None)
    assert lufs_gap is not None
    assert lufs_gap.direction == 'below'
    assert lufs_gap.severity in ['moderate', 'significant', 'critical']
    assert lufs_gap.fix_suggestion is not None

    print("  Gap analysis (out of range) OK")


def test_severity_levels():
    """Test severity level assignment."""
    print("Testing severity levels...")

    integration = ReferenceIntegration()
    integration.load_profile_dict(create_mock_profile())

    # Test different deviation levels
    # LUFS: mean=-8, std=1.5, range=[-10, -6]
    test_cases = [
        (-8.0, 'good'),      # 0 std
        (-8.5, 'good'),      # 0.33 std
        (-9.5, 'minor'),     # 1 std
        (-11.0, 'moderate'), # 2 std
        (-12.5, 'significant'), # 3 std
        (-15.0, 'critical'), # > 3 std
    ]

    for value, expected_severity in test_cases:
        analysis = integration.analyze_gaps({'integrated_lufs': value}, "Test")
        gap = analysis.gaps[0]
        assert gap.severity == expected_severity, \
            f"Expected {expected_severity} for {value}, got {gap.severity}"

    print("  Severity levels OK")


def test_summary_generation():
    """Test summary generation."""
    print("Testing summary generation...")

    integration = ReferenceIntegration()
    integration.load_profile_dict(create_mock_profile())

    # Good track
    gaps = integration.analyze_gaps({
        'integrated_lufs': -8.0,
        'tempo': 138.0
    }, "Good Track")
    assert 'well-aligned' in gaps.summary.lower() or gaps.overall_score >= 80

    # Bad track
    gaps = integration.analyze_gaps({
        'integrated_lufs': -20.0,
        'tempo': 100.0
    }, "Bad Track")
    assert gaps.overall_score < 60

    print("  Summary generation OK")


def test_gap_to_dict():
    """Test serialization."""
    print("Testing serialization...")

    integration = ReferenceIntegration()
    integration.load_profile_dict(create_mock_profile())

    gaps = integration.analyze_gaps({
        'integrated_lufs': -12.0,
        'tempo': 138.0
    }, "Test Track")

    # Test to_dict
    data = gaps.to_dict()
    assert 'profile_name' in data
    assert 'gaps' in data
    assert len(data['gaps']) == 2

    # Test to_json
    json_str = gaps.to_json()
    parsed = json.loads(json_str)
    assert parsed['track_name'] == 'Test Track'

    print("  Serialization OK")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("Reference Integration Tests")
    print("="*60 + "\n")

    try:
        test_load_profile()
        test_get_feature_stats()
        test_is_in_range()
        test_get_fix_target()
        test_analyze_gaps_in_range()
        test_analyze_gaps_out_of_range()
        test_severity_levels()
        test_summary_generation()
        test_gap_to_dict()

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
