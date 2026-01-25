#!/usr/bin/env python3
"""
Tests for MIDI Analyzer Module (Story 2.3)

Tests MIDI and arrangement analysis functionality including:
- Empty clip detection
- Short clip detection
- Duplicate clip detection
- Track content detection
- Arrangement structure analysis
- Database persistence
"""

import sys
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# Add the src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

# Import directly from modules
import importlib.util

# Import midi_analyzer module
spec = importlib.util.spec_from_file_location('midi_analyzer', src_path / 'midi_analyzer.py')
midi_analyzer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(midi_analyzer_module)

MIDIAnalyzer = midi_analyzer_module.MIDIAnalyzer
MIDIAnalysisResult = midi_analyzer_module.MIDIAnalysisResult
ClipIssue = midi_analyzer_module.ClipIssue
TrackIssue = midi_analyzer_module.TrackIssue
ArrangementSection = midi_analyzer_module.ArrangementSection
ArrangementAnalysis = midi_analyzer_module.ArrangementAnalysis
MIDIClipStats = midi_analyzer_module.MIDIClipStats
MIDITrackStats = midi_analyzer_module.MIDITrackStats
get_midi_issues = midi_analyzer_module.get_midi_issues

# Import database module
db_spec = importlib.util.spec_from_file_location('database', src_path / 'database.py')
database_module = importlib.util.module_from_spec(db_spec)
db_spec.loader.exec_module(database_module)

db_init = database_module.db_init
Database = database_module.Database
persist_midi_stats = database_module.persist_midi_stats
get_midi_stats = database_module.get_midi_stats
MIDIStats = database_module.MIDIStats


# ==================== MOCK DATA STRUCTURES ====================


@dataclass
class MockMIDINote:
    """Mock MIDI note for testing."""
    pitch: int
    start_time: float
    duration: float
    velocity: int
    mute: bool = False


@dataclass
class MockMIDIClip:
    """Mock MIDI clip for testing."""
    name: str
    start_time: float
    end_time: float
    notes: List[MockMIDINote] = field(default_factory=list)


@dataclass
class MockLocator:
    """Mock locator for testing."""
    name: str
    time: float


@dataclass
class MockProjectStructure:
    """Mock project structure for testing."""
    locators: List[MockLocator] = field(default_factory=list)


@dataclass
class MockTrack:
    """Mock track for testing."""
    name: str
    track_type: str  # 'midi', 'audio', 'return', 'master'
    midi_clips: List[MockMIDIClip] = field(default_factory=list)


@dataclass
class MockALSProject:
    """Mock ALS project for testing."""
    tracks: List[MockTrack] = field(default_factory=list)
    tempo: float = 120.0
    time_signature_numerator: int = 4
    time_signature_denominator: int = 4
    total_duration_beats: float = 128.0
    project_structure: Optional[MockProjectStructure] = None
    midi_analysis: dict = field(default_factory=dict)


# ==================== TESTS ====================


def test_analyze_empty_project():
    """Test analyzing a project with no tracks."""
    project = MockALSProject(tracks=[])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.total_midi_tracks == 0
    assert result.total_midi_clips == 0
    assert result.total_notes == 0
    assert result.total_empty_clips == 0
    assert len(result.clip_issues) == 0
    assert len(result.track_issues) == 0

    return True


def test_detect_empty_clip():
    """Test detection of empty MIDI clips."""
    clip = MockMIDIClip(
        name="Empty Clip",
        start_time=0.0,
        end_time=4.0,
        notes=[]  # No notes = empty
    )
    track = MockTrack(name="Synth", track_type="midi", midi_clips=[clip])
    project = MockALSProject(tracks=[track])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.total_empty_clips == 1
    assert len(result.clip_issues) >= 1

    empty_issues = [i for i in result.clip_issues if i.issue_type == 'empty']
    assert len(empty_issues) == 1
    assert empty_issues[0].track_name == "Synth"
    assert empty_issues[0].clip_name == "Empty Clip"
    assert empty_issues[0].severity == 'warning'

    return True


def test_detect_short_clip():
    """Test detection of very short MIDI clips (< 1 beat)."""
    clip = MockMIDIClip(
        name="Short Clip",
        start_time=0.0,
        end_time=0.5,  # Only 0.5 beats
        notes=[MockMIDINote(pitch=60, start_time=0.0, duration=0.25, velocity=100)]
    )
    track = MockTrack(name="Bass", track_type="midi", midi_clips=[clip])
    project = MockALSProject(tracks=[track])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.total_short_clips == 1

    short_issues = [i for i in result.clip_issues if i.issue_type == 'very_short']
    assert len(short_issues) == 1
    assert short_issues[0].clip_name == "Short Clip"
    assert short_issues[0].severity == 'suggestion'

    return True


def test_detect_duplicate_clips():
    """Test detection of duplicate MIDI clips with same notes."""
    notes = [
        MockMIDINote(pitch=60, start_time=0.0, duration=1.0, velocity=100),
        MockMIDINote(pitch=64, start_time=1.0, duration=1.0, velocity=100),
        MockMIDINote(pitch=67, start_time=2.0, duration=1.0, velocity=100),
    ]

    clip1 = MockMIDIClip(name="Chord 1", start_time=0.0, end_time=4.0, notes=notes.copy())
    clip2 = MockMIDIClip(name="Chord 2", start_time=4.0, end_time=8.0, notes=notes.copy())

    track = MockTrack(name="Synth", track_type="midi", midi_clips=[clip1, clip2])
    project = MockALSProject(tracks=[track])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.total_duplicate_clips == 1  # One is duplicate of the other
    assert len(result.duplicate_groups) == 1
    assert len(result.duplicate_groups[0]) == 2  # Both clips in the group

    return True


def test_detect_track_without_content():
    """Test detection of tracks with no MIDI content."""
    empty_clip = MockMIDIClip(name="Empty", start_time=0.0, end_time=4.0, notes=[])
    track = MockTrack(name="Lead", track_type="midi", midi_clips=[empty_clip])
    project = MockALSProject(tracks=[track])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.tracks_without_content == 1

    track_issues = [i for i in result.track_issues if i.issue_type == 'no_content']
    assert len(track_issues) == 1
    assert track_issues[0].track_name == "Lead"

    return True


def test_analyze_arrangement_no_markers():
    """Test arrangement analysis with no locators."""
    project = MockALSProject(
        tracks=[],
        project_structure=MockProjectStructure(locators=[])
    )

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.arrangement is not None
    assert result.arrangement.has_arrangement_markers is False
    assert result.arrangement.total_sections == 0
    assert len(result.arrangement.sections) == 0

    return True


def test_analyze_arrangement_with_markers():
    """Test arrangement analysis with locators."""
    locators = [
        MockLocator(name="Intro", time=0.0),
        MockLocator(name="Buildup", time=32.0),
        MockLocator(name="Drop", time=64.0),
        MockLocator(name="Outro", time=96.0),
    ]
    project = MockALSProject(
        tracks=[],
        project_structure=MockProjectStructure(locators=locators),
        total_duration_beats=128.0
    )

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.arrangement is not None
    assert result.arrangement.has_arrangement_markers is True
    assert result.arrangement.total_sections == 4
    assert len(result.arrangement.sections) == 4

    # Check sections
    sections = result.arrangement.sections
    assert sections[0].name == "Intro"
    assert sections[0].start_beat == 0.0
    assert sections[0].end_beat == 32.0
    assert sections[1].name == "Buildup"
    assert sections[2].name == "Drop"
    assert sections[3].name == "Outro"

    return True


def test_detect_edm_structure():
    """Test detection of EDM arrangement structure."""
    locators = [
        MockLocator(name="Intro", time=0.0),
        MockLocator(name="Build", time=32.0),
        MockLocator(name="Drop 1", time=64.0),
        MockLocator(name="Breakdown", time=96.0),
    ]
    project = MockALSProject(
        tracks=[],
        project_structure=MockProjectStructure(locators=locators)
    )

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.arrangement.suggested_structure == 'intro-buildup-drop'

    return True


def test_detect_song_structure():
    """Test detection of verse-chorus song structure."""
    locators = [
        MockLocator(name="Verse 1", time=0.0),
        MockLocator(name="Chorus", time=32.0),
        MockLocator(name="Verse 2", time=64.0),
        MockLocator(name="Bridge", time=96.0),
    ]
    project = MockALSProject(
        tracks=[],
        project_structure=MockProjectStructure(locators=locators)
    )

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.arrangement.suggested_structure == 'verse-chorus'

    return True


def test_low_velocity_detection():
    """Test detection of low velocity notes."""
    notes = [
        MockMIDINote(pitch=60, start_time=0.0, duration=1.0, velocity=20),  # Very low
        MockMIDINote(pitch=64, start_time=1.0, duration=1.0, velocity=25),  # Very low
    ]
    clip = MockMIDIClip(name="Quiet", start_time=0.0, end_time=4.0, notes=notes)
    track = MockTrack(name="Keys", track_type="midi", midi_clips=[clip])
    project = MockALSProject(tracks=[track])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    low_vel_issues = [i for i in result.clip_issues if i.issue_type == 'low_velocity']
    assert len(low_vel_issues) == 1
    assert low_vel_issues[0].severity == 'suggestion'

    return True


def test_clip_stats_calculation():
    """Test that clip statistics are calculated correctly."""
    notes = [
        MockMIDINote(pitch=60, start_time=0.0, duration=1.0, velocity=80),
        MockMIDINote(pitch=64, start_time=1.0, duration=1.0, velocity=100),
        MockMIDINote(pitch=67, start_time=2.0, duration=1.0, velocity=90),
    ]
    clip = MockMIDIClip(name="Chord", start_time=0.0, end_time=4.0, notes=notes)
    track = MockTrack(name="Piano", track_type="midi", midi_clips=[clip])
    project = MockALSProject(tracks=[track])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert len(result.track_stats) == 1
    track_stat = result.track_stats[0]
    assert track_stat.total_notes == 3
    assert track_stat.total_clips == 1
    assert track_stat.has_content is True

    clip_stat = track_stat.clip_stats[0]
    assert clip_stat.note_count == 3
    assert clip_stat.unique_pitches == 3
    assert clip_stat.velocity_range == (80, 100)
    assert abs(clip_stat.average_velocity - 90.0) < 0.1

    return True


def test_muted_notes_excluded():
    """Test that muted notes are excluded from analysis."""
    notes = [
        MockMIDINote(pitch=60, start_time=0.0, duration=1.0, velocity=100, mute=False),
        MockMIDINote(pitch=64, start_time=1.0, duration=1.0, velocity=100, mute=True),  # Muted
    ]
    clip = MockMIDIClip(name="Part", start_time=0.0, end_time=4.0, notes=notes)
    track = MockTrack(name="Lead", track_type="midi", midi_clips=[clip])
    project = MockALSProject(tracks=[track])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    # Only 1 note should be counted (the unmuted one)
    assert result.total_notes == 1

    return True


def test_get_midi_issues_format():
    """Test that get_midi_issues returns proper format."""
    clip = MockMIDIClip(name="Empty", start_time=0.0, end_time=4.0, notes=[])
    track = MockTrack(name="Synth", track_type="midi", midi_clips=[clip])
    project = MockALSProject(tracks=[track])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    issues = get_midi_issues(result)

    assert len(issues) >= 1
    assert 'track_name' in issues[0]
    assert 'severity' in issues[0]
    assert 'category' in issues[0]
    assert 'description' in issues[0]
    assert 'fix_suggestion' in issues[0]
    assert issues[0]['category'].startswith('midi_')

    return True


def test_multiple_tracks_analysis():
    """Test analysis with multiple MIDI tracks."""
    notes1 = [MockMIDINote(pitch=36, start_time=0.0, duration=0.5, velocity=100)]
    notes2 = [MockMIDINote(pitch=60, start_time=0.0, duration=2.0, velocity=80)]

    clip1 = MockMIDIClip(name="Kick", start_time=0.0, end_time=4.0, notes=notes1)
    clip2 = MockMIDIClip(name="Chord", start_time=0.0, end_time=4.0, notes=notes2)
    clip3 = MockMIDIClip(name="Empty", start_time=0.0, end_time=4.0, notes=[])

    track1 = MockTrack(name="Drums", track_type="midi", midi_clips=[clip1])
    track2 = MockTrack(name="Synth", track_type="midi", midi_clips=[clip2, clip3])
    track3 = MockTrack(name="Audio", track_type="audio", midi_clips=[])

    project = MockALSProject(tracks=[track1, track2, track3])

    analyzer = MIDIAnalyzer()
    result = analyzer.analyze(project)

    assert result.total_midi_tracks == 2  # Only MIDI tracks
    assert result.total_midi_clips == 3
    assert result.total_notes == 2
    assert result.total_empty_clips == 1

    return True


# ==================== DATABASE TESTS ====================


def test_midi_stats_schema_exists(tmp_path):
    """Test that midi_stats table is created in schema."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    db = Database(db_path)
    with db.connection() as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='midi_stats'"
        )
        assert cursor.fetchone() is not None, "midi_stats table should exist"

    return True


def test_persist_midi_stats(tmp_path):
    """Test persisting MIDI stats to database."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create a version record first
    db = Database(db_path)
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
            ('/test/project', 'Test Song')
        )
        cursor = conn.execute(
            """INSERT INTO versions (project_id, als_path, als_filename, health_score, grade)
               VALUES (1, '/test/project/song.als', 'song.als', 80, 'A')"""
        )
        version_id = cursor.lastrowid

    stats = MIDIStats(
        version_id=version_id,
        total_midi_tracks=5,
        total_midi_clips=10,
        total_notes=500,
        total_empty_clips=2,
        total_short_clips=1,
        total_duplicate_clips=0,
        tracks_without_content=1,
        has_arrangement_markers=True,
        total_sections=4,
        arrangement_structure='intro-buildup-drop'
    )

    success, message = persist_midi_stats(stats, db_path)
    assert success, f"Failed to persist: {message}"

    return True


def test_get_midi_stats(tmp_path):
    """Test retrieving MIDI stats from database."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create project and version
    db = Database(db_path)
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
            ('/test/project', 'Test Song')
        )
        cursor = conn.execute(
            """INSERT INTO versions (project_id, als_path, als_filename, health_score, grade)
               VALUES (1, '/test/project/song.als', 'song.als', 80, 'A')"""
        )
        version_id = cursor.lastrowid

    # Persist stats
    stats = MIDIStats(
        version_id=version_id,
        total_midi_tracks=5,
        total_midi_clips=10,
        total_notes=500,
        total_empty_clips=2,
        total_short_clips=1,
        total_duplicate_clips=3,
        tracks_without_content=1,
        has_arrangement_markers=True,
        total_sections=4,
        arrangement_structure='verse-chorus'
    )
    persist_midi_stats(stats, db_path)

    # Retrieve stats
    retrieved, message = get_midi_stats(version_id, db_path)

    assert retrieved is not None, f"Failed to get stats: {message}"
    assert retrieved.total_midi_tracks == 5
    assert retrieved.total_midi_clips == 10
    assert retrieved.total_notes == 500
    assert retrieved.total_empty_clips == 2
    assert retrieved.total_short_clips == 1
    assert retrieved.total_duplicate_clips == 3
    assert retrieved.tracks_without_content == 1
    assert retrieved.has_arrangement_markers is True
    assert retrieved.total_sections == 4
    assert retrieved.arrangement_structure == 'verse-chorus'

    return True


def test_midi_stats_upsert(tmp_path):
    """Test that persisting MIDI stats twice updates existing record."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    # Create project and version
    db = Database(db_path)
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
            ('/test/project', 'Test Song')
        )
        cursor = conn.execute(
            """INSERT INTO versions (project_id, als_path, als_filename, health_score, grade)
               VALUES (1, '/test/project/song.als', 'song.als', 80, 'A')"""
        )
        version_id = cursor.lastrowid

    # First persist
    stats1 = MIDIStats(
        version_id=version_id,
        total_midi_tracks=5,
        total_midi_clips=10,
        total_notes=500,
        total_empty_clips=2,
        total_short_clips=1,
        total_duplicate_clips=0,
        tracks_without_content=1,
        has_arrangement_markers=False,
        total_sections=0,
        arrangement_structure=None
    )
    success1, msg1 = persist_midi_stats(stats1, db_path)
    assert success1 and "saved" in msg1.lower()

    # Second persist with different values (should update)
    stats2 = MIDIStats(
        version_id=version_id,
        total_midi_tracks=8,
        total_midi_clips=15,
        total_notes=750,
        total_empty_clips=0,
        total_short_clips=0,
        total_duplicate_clips=2,
        tracks_without_content=0,
        has_arrangement_markers=True,
        total_sections=6,
        arrangement_structure='intro-buildup-drop'
    )
    success2, msg2 = persist_midi_stats(stats2, db_path)
    assert success2 and "updated" in msg2.lower()

    # Verify updated values
    retrieved, _ = get_midi_stats(version_id, db_path)
    assert retrieved.total_midi_tracks == 8
    assert retrieved.total_notes == 750
    assert retrieved.has_arrangement_markers is True
    assert retrieved.total_sections == 6

    return True


def test_midi_stats_not_found(tmp_path):
    """Test retrieving MIDI stats for non-existent version."""
    db_path = tmp_path / 'test.db'
    db_init(db_path)

    result, message = get_midi_stats(999, db_path)

    assert result is None
    # Message is "No MIDI stats found for version 999"
    assert "no midi stats found" in message.lower() or "not found" in message.lower()

    return True


def test_midi_stats_uninit_db(tmp_path):
    """Test MIDI stats operations on uninitialized database."""
    db_path = tmp_path / 'uninit.db'

    stats = MIDIStats(
        version_id=1,
        total_midi_tracks=5,
        total_midi_clips=10,
        total_notes=500,
        total_empty_clips=0,
        total_short_clips=0,
        total_duplicate_clips=0,
        tracks_without_content=0,
        has_arrangement_markers=False,
        total_sections=0,
        arrangement_structure=None
    )

    success, message = persist_midi_stats(stats, db_path)
    assert not success
    assert "not initialized" in message.lower()

    result, message = get_midi_stats(1, db_path)
    assert result is None
    assert "not initialized" in message.lower()

    return True


# ==================== TEST RUNNER ====================


def run_tests():
    """Run all tests."""
    tests = [
        # MIDI Analysis tests
        ("Empty project", test_analyze_empty_project),
        ("Detect empty clip", test_detect_empty_clip),
        ("Detect short clip", test_detect_short_clip),
        ("Detect duplicate clips", test_detect_duplicate_clips),
        ("Detect track without content", test_detect_track_without_content),
        ("Arrangement no markers", test_analyze_arrangement_no_markers),
        ("Arrangement with markers", test_analyze_arrangement_with_markers),
        ("EDM structure detection", test_detect_edm_structure),
        ("Song structure detection", test_detect_song_structure),
        ("Low velocity detection", test_low_velocity_detection),
        ("Clip stats calculation", test_clip_stats_calculation),
        ("Muted notes excluded", test_muted_notes_excluded),
        ("Get MIDI issues format", test_get_midi_issues_format),
        ("Multiple tracks analysis", test_multiple_tracks_analysis),
        # Database tests
        ("MIDI stats schema exists", test_midi_stats_schema_exists),
        ("Persist MIDI stats", test_persist_midi_stats),
        ("Get MIDI stats", test_get_midi_stats),
        ("MIDI stats upsert", test_midi_stats_upsert),
        ("MIDI stats not found", test_midi_stats_not_found),
        ("MIDI stats uninit DB", test_midi_stats_uninit_db),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("MIDI Analyzer Tests (Story 2.3)")
    print("=" * 60)
    print()

    for name, test_func in tests:
        try:
            # Create temp directory for tests that need it
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                # Check if test needs tmp_path
                if 'tmp_path' in test_func.__code__.co_varnames:
                    result = test_func(tmp_path)
                else:
                    result = test_func()

            if result:
                print(f"  \u2713 {name}")
                passed += 1
            else:
                print(f"  \u2717 {name} (returned False)")
                failed += 1
        except Exception as e:
            print(f"  \u2717 {name}")
            print(f"      Error: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
