"""
Test script for ChangeTracker file-based persistence.

Run: python test_state.py (from live_control directory)
"""

import sys
import tempfile
from pathlib import Path

# Import directly from the state module in the same directory
from state import (
    Change, ABComparison, ChangeTracker,
    record_change, get_undo_info, confirm_undo, get_session_summary, clear_session
)


def test_change_serialization():
    """Test that Change can be serialized and deserialized."""
    print("Testing Change serialization...")

    change = Change(
        track_index=1,
        track_name="Bass",
        device_index=0,
        device_name="EQ Eight",
        parameter_index=4,
        parameter_name="1 Gain",
        previous_value=0.5,
        new_value=0.35,
        description="Reduce Bass EQ band 1 by 3dB",
        change_type="parameter"
    )

    # Serialize
    data = change.to_dict()
    assert 'id' in data
    assert data['track_index'] == 1
    assert data['track_name'] == "Bass"
    assert data['device_name'] == "EQ Eight"
    assert data['previous_value'] == 0.5
    assert data['new_value'] == 0.35

    # Deserialize
    restored = Change.from_dict(data)
    assert restored.track_index == change.track_index
    assert restored.track_name == change.track_name
    assert restored.previous_value == change.previous_value
    assert restored.new_value == change.new_value

    print("  Change serialization OK")


def test_ab_comparison_serialization():
    """Test that ABComparison can be serialized and deserialized."""
    print("Testing ABComparison serialization...")

    ab = ABComparison(
        description="Test fix",
        track_index=0,
        device_index=1,
        parameter_index=2,
        original_value=0.5,
        fix_value=0.3,
        current_state='B',
        change_type="parameter"
    )

    # Serialize
    data = ab.to_dict()
    assert data['description'] == "Test fix"
    assert data['original_value'] == 0.5
    assert data['fix_value'] == 0.3
    assert data['current_state'] == 'B'

    # Deserialize
    restored = ABComparison.from_dict(data)
    assert restored.description == ab.description
    assert restored.original_value == ab.original_value
    assert restored.fix_value == ab.fix_value

    print("  ABComparison serialization OK")


def test_tracker_persistence():
    """Test that ChangeTracker persists and reloads correctly."""
    print("Testing ChangeTracker persistence...")

    # Use a temp file for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "test_session.json"

        # Create tracker and record some changes
        tracker1 = ChangeTracker(session_file=session_file)
        tracker1.set_song("Test Song")

        tracker1.record(Change(
            track_index=0,
            track_name="Kick",
            previous_value=0.85,
            new_value=0.7,
            description="Reduce kick volume",
            change_type="volume"
        ))

        tracker1.record(Change(
            track_index=1,
            track_name="Bass",
            previous_value=0.0,
            new_value=-0.2,
            description="Pan bass left",
            change_type="pan"
        ))

        assert tracker1.change_count == 2
        assert tracker1.can_undo == True
        assert tracker1.song_name == "Test Song"

        # Verify file was created
        assert session_file.exists()

        # Create new tracker instance (simulates new Python invocation)
        tracker2 = ChangeTracker(session_file=session_file)

        # Should have loaded the previous state
        assert tracker2.change_count == 2
        assert tracker2.can_undo == True
        assert tracker2.song_name == "Test Song"

        # Get last change
        last = tracker2.get_last_change()
        assert last is not None
        assert last.track_name == "Bass"
        assert last.description == "Pan bass left"

        print("  ChangeTracker persistence OK")


def test_undo_redo():
    """Test undo/redo functionality with persistence."""
    print("Testing undo/redo...")

    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "test_session.json"

        tracker = ChangeTracker(session_file=session_file)
        tracker.record(Change(
            track_index=0,
            track_name="Kick",
            previous_value=0.85,
            new_value=0.7,
            description="Reduce kick volume",
            change_type="volume"
        ))

        # Undo
        undo_change = tracker.get_undo()
        assert undo_change is not None
        assert undo_change.previous_value == 0.85

        tracker.confirm_undo()
        assert tracker.change_count == 0
        assert tracker.can_undo == False
        assert tracker.can_redo == True

        # Reload and check redo is available
        tracker2 = ChangeTracker(session_file=session_file)
        assert tracker2.can_redo == True

        # Redo
        redo_change = tracker2.get_redo()
        assert redo_change is not None
        assert redo_change.new_value == 0.7

        tracker2.confirm_redo()
        assert tracker2.change_count == 1
        assert tracker2.can_undo == True
        assert tracker2.can_redo == False

        print("  Undo/redo OK")


def test_ab_comparison():
    """Test A/B comparison functionality."""
    print("Testing A/B comparison...")

    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "test_session.json"

        tracker = ChangeTracker(session_file=session_file)

        # Start A/B comparison
        ab = tracker.start_ab(
            description="EQ fix",
            track_index=0,
            original_value=0.5,
            fix_value=0.3,
            device_index=0,
            parameter_index=4
        )

        assert tracker.is_comparing == True
        assert ab.current_state == 'B'
        assert ab.current_value == 0.3

        # Toggle to A
        new_state = tracker.toggle_ab()
        assert new_state == 'A'
        assert tracker.ab_state.current_value == 0.5

        # Reload and check AB state persists
        tracker2 = ChangeTracker(session_file=session_file)
        assert tracker2.is_comparing == True
        assert tracker2.ab_state.current_state == 'A'

        # End AB, keeping B (should record as a change)
        tracker2.toggle_ab()  # Back to B
        change = tracker2.end_ab('B')
        assert change is not None
        assert tracker2.is_comparing == False
        assert tracker2.change_count == 1

        print("  A/B comparison OK")


def test_convenience_functions():
    """Test the convenience functions for Claude Code."""
    print("Testing convenience functions...")

    with tempfile.TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "test_session.json"

        # Clear any existing session
        tracker = ChangeTracker(session_file=session_file)
        tracker.clear()

        # Create fresh tracker pointing to test file
        # Note: convenience functions use default file, so we test the tracker directly
        tracker = ChangeTracker(session_file=session_file)

        # Record a change
        change = Change(
            track_index=0,
            track_name="Test",
            previous_value=1.0,
            new_value=0.5,
            description="Test change",
            change_type="volume"
        )
        tracker.record(change)

        # Get summary
        summary = tracker.summary()
        assert "Changes: 1" in summary
        assert "Test change" in summary

        # Export to dict
        state = tracker.to_dict()
        assert state['change_count'] == 1
        assert state['can_undo'] == True

        print("  Convenience functions OK")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("ChangeTracker Persistence Tests")
    print("="*60 + "\n")

    try:
        test_change_serialization()
        test_ab_comparison_serialization()
        test_tracker_persistence()
        test_undo_redo()
        test_ab_comparison()
        test_convenience_functions()

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
    success = run_all_tests()
    sys.exit(0 if success else 1)
