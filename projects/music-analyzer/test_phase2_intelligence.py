"""
Tests for Phase 2 - Intelligence features.

Tests for change tracking, insights, trend analysis, what-if predictions,
and smart recommendations.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add the src directory to path for direct import (avoiding __init__.py)
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import directly from database module, bypassing src/__init__.py
import importlib.util
spec = importlib.util.spec_from_file_location("database", src_path / "database.py")
database_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database_module)

# Phase 1 imports
Database = database_module.Database
db_init = database_module.db_init
persist_scan_result = database_module.persist_scan_result
ScanResult = database_module.ScanResult
ScanResultIssue = database_module.ScanResultIssue

# Phase 2 imports - Change Tracking (Story 2.1)
track_changes = database_module.track_changes
get_project_changes = database_module.get_project_changes
compute_and_store_all_changes = database_module.compute_and_store_all_changes
ProjectChangesResult = database_module.ProjectChangesResult
VersionComparison = database_module.VersionComparison
VersionChange = database_module.VersionChange

# Phase 2 imports - Insights (Story 2.2)
get_insights = database_module.get_insights
InsightsResult = database_module.InsightsResult
InsightPattern = database_module.InsightPattern
CommonMistake = database_module.CommonMistake
_get_confidence_level = database_module._get_confidence_level

# Phase 2 imports - Trend Analysis (Story 2.3)
analyze_project_trend = database_module.analyze_project_trend
ProjectTrend = database_module.ProjectTrend
TrendPoint = database_module.TrendPoint

# Phase 2 imports - What-If Predictions (Story 2.4)
get_what_if_predictions = database_module.get_what_if_predictions
WhatIfPrediction = database_module.WhatIfPrediction
WhatIfAnalysis = database_module.WhatIfAnalysis

# Phase 2 imports - Smart Recommendations (Story 2.5)
smart_diagnose = database_module.smart_diagnose
SmartDiagnoseResult = database_module.SmartDiagnoseResult
SmartRecommendation = database_module.SmartRecommendation
has_sufficient_history = database_module.has_sufficient_history

# Phase 2 imports - Change Intent (Story 2.1 enhancement)
_determine_change_intent = database_module._determine_change_intent


class TestConfidenceLevel:
    """Tests for confidence level calculation."""

    def test_high_confidence(self):
        """10+ occurrences should be HIGH confidence."""
        assert _get_confidence_level(10) == 'HIGH'
        assert _get_confidence_level(15) == 'HIGH'
        assert _get_confidence_level(100) == 'HIGH'

    def test_medium_confidence(self):
        """5-9 occurrences should be MEDIUM confidence."""
        assert _get_confidence_level(5) == 'MEDIUM'
        assert _get_confidence_level(7) == 'MEDIUM'
        assert _get_confidence_level(9) == 'MEDIUM'

    def test_low_confidence(self):
        """2-4 occurrences should be LOW confidence."""
        assert _get_confidence_level(2) == 'LOW'
        assert _get_confidence_level(3) == 'LOW'
        assert _get_confidence_level(4) == 'LOW'


class TestChangesTableSchema:
    """Tests for the changes table schema (Story 2.1)."""

    def test_changes_table_exists(self, tmp_path):
        """Database should have a changes table after initialization."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='changes'"
        )
        tables = cursor.fetchall()
        conn.close()

        assert len(tables) == 1

    def test_changes_table_schema(self, tmp_path):
        """Changes table should have the correct columns."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(changes)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'id', 'project_id', 'before_version_id', 'after_version_id',
            'change_type', 'track_name', 'device_name', 'device_type',
            'details', 'health_delta', 'recorded_at'
        ]

        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"


class TestGetProjectChanges:
    """Tests for get_project_changes (Story 2.1)."""

    def _setup_project_with_versions(self, tmp_path, db_path):
        """Helper to create a project with multiple versions."""
        db_init(db_path)

        project_dir = tmp_path / "Test Project"
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create scan results for two versions
        scan_result1 = ScanResult(
            als_path=str(project_dir / "v1.als"),
            health_score=60,
            grade="B",
            total_issues=5,
            critical_issues=2,
            warning_issues=2,
            total_devices=20,
            disabled_devices=4,
            clutter_percentage=20.0,
            issues=[]
        )
        scan_result2 = ScanResult(
            als_path=str(project_dir / "v2.als"),
            health_score=75,
            grade="B",
            total_issues=3,
            critical_issues=1,
            warning_issues=1,
            total_devices=18,
            disabled_devices=2,
            clutter_percentage=11.1,
            issues=[]
        )

        persist_scan_result(scan_result1, db_path)
        persist_scan_result(scan_result2, db_path)

        return project_dir

    def test_get_project_changes_fails_without_init(self, tmp_path):
        """get_project_changes should fail if database not initialized."""
        db_path = tmp_path / "uninit.db"

        result, message = get_project_changes("Test", db_path=db_path)

        assert result is None
        assert "not initialized" in message.lower()

    def test_get_project_changes_not_found(self, tmp_path):
        """get_project_changes should fail if project not found."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        result, message = get_project_changes("Nonexistent", db_path=db_path)

        assert result is None
        assert "no project found" in message.lower()

    def test_get_project_changes_requires_two_versions(self, tmp_path):
        """get_project_changes requires at least 2 versions."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        project_dir = tmp_path / "Single Version Project"
        project_dir.mkdir(parents=True, exist_ok=True)

        scan_result = ScanResult(
            als_path=str(project_dir / "v1.als"),
            health_score=70,
            grade="B",
            total_issues=3,
            critical_issues=1,
            warning_issues=1,
            total_devices=15,
            disabled_devices=2,
            clutter_percentage=13.3,
            issues=[]
        )
        persist_scan_result(scan_result, db_path)

        result, message = get_project_changes("Single Version", db_path=db_path)

        assert result is None
        assert "at least 2" in message.lower()

    def test_get_project_changes_returns_comparisons(self, tmp_path):
        """get_project_changes should return comparisons between versions."""
        db_path = tmp_path / "test.db"
        project_dir = self._setup_project_with_versions(tmp_path, db_path)

        result, message = get_project_changes("Test Project", db_path=db_path)

        assert result is not None
        assert message == "OK"
        assert len(result.comparisons) == 1  # One pair: v1 -> v2

        comparison = result.comparisons[0]
        assert comparison.before_health == 60
        assert comparison.after_health == 75
        assert comparison.health_delta == 15
        assert comparison.is_improvement is True

    def test_get_project_changes_fuzzy_match(self, tmp_path):
        """get_project_changes should support fuzzy matching."""
        db_path = tmp_path / "test.db"
        self._setup_project_with_versions(tmp_path, db_path)

        # Partial match should work
        result, _ = get_project_changes("Test", db_path=db_path)
        assert result is not None

        # Case-insensitive should work
        result, _ = get_project_changes("test", db_path=db_path)
        assert result is not None


class TestInsights:
    """Tests for insights/pattern analysis (Story 2.2)."""

    def _populate_changes(self, db_path, num_comparisons=15):
        """Helper to populate the changes table with test data."""
        db = Database(db_path)

        # Create a project and versions
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/test/project", "Test Project")
            )

            # Create versions
            for i in range(num_comparisons + 1):
                conn.execute(
                    """INSERT INTO versions
                       (project_id, als_path, als_filename, health_score, grade, total_issues)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (1, f"/test/project/v{i}.als", f"v{i}.als", 50 + i * 2, "C", 5 - i // 5)
                )

            # Create changes between consecutive versions
            for i in range(num_comparisons):
                # Device removals with positive health delta
                conn.execute(
                    """INSERT INTO changes
                       (project_id, before_version_id, after_version_id,
                        change_type, track_name, device_name, device_type,
                        health_delta)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (1, i + 1, i + 2, "device_removed", "Bass",
                     "Unused Reverb", "Reverb", 3)
                )

                # Device additions with negative health delta
                conn.execute(
                    """INSERT INTO changes
                       (project_id, before_version_id, after_version_id,
                        change_type, track_name, device_name, device_type,
                        health_delta)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (1, i + 1, i + 2, "device_added", "Lead",
                     "Extra Compressor", "Compressor", -2)
                )

    def test_get_insights_fails_without_init(self, tmp_path):
        """get_insights should fail if database not initialized."""
        db_path = tmp_path / "uninit.db"

        result, message = get_insights(db_path)

        assert result is None
        assert "not initialized" in message.lower()

    def test_get_insights_insufficient_data(self, tmp_path):
        """get_insights should report insufficient data when < 10 comparisons."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        # Only create 5 comparisons
        self._populate_changes(db_path, num_comparisons=5)

        result, message = get_insights(db_path)

        assert result is not None
        assert result.insufficient_data is True
        assert result.total_comparisons < 10

    def test_get_insights_returns_patterns(self, tmp_path):
        """get_insights should return patterns when sufficient data exists."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        self._populate_changes(db_path, num_comparisons=15)

        result, message = get_insights(db_path)

        assert result is not None
        assert message == "OK"
        assert result.insufficient_data is False
        assert result.total_comparisons >= 10

    def test_get_insights_identifies_helpful_patterns(self, tmp_path):
        """get_insights should identify patterns that help health."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        self._populate_changes(db_path, num_comparisons=15)

        result, _ = get_insights(db_path)

        # Device removal with positive delta should be in patterns_that_help
        assert len(result.patterns_that_help) > 0
        removal_pattern = next(
            (p for p in result.patterns_that_help
             if p.change_type == 'device_removed' and p.device_type == 'Reverb'),
            None
        )
        assert removal_pattern is not None
        assert removal_pattern.avg_health_delta > 0

    def test_get_insights_identifies_harmful_patterns(self, tmp_path):
        """get_insights should identify patterns that hurt health."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        self._populate_changes(db_path, num_comparisons=15)

        result, _ = get_insights(db_path)

        # Device addition with negative delta should be in patterns_that_hurt
        assert len(result.patterns_that_hurt) > 0
        addition_pattern = next(
            (p for p in result.patterns_that_hurt
             if p.change_type == 'device_added' and p.device_type == 'Compressor'),
            None
        )
        assert addition_pattern is not None
        assert addition_pattern.avg_health_delta < 0


class TestTrendAnalysis:
    """Tests for trend analysis (Story 2.3)."""

    def _setup_project_with_trend(self, tmp_path, db_path, scores):
        """Helper to create a project with version history."""
        db_init(db_path)

        project_dir = tmp_path / "Trending Project"
        project_dir.mkdir(parents=True, exist_ok=True)

        for i, score in enumerate(scores):
            grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D" if score >= 20 else "F"
            scan_result = ScanResult(
                als_path=str(project_dir / f"v{i+1}.als"),
                health_score=score,
                grade=grade,
                total_issues=max(0, 10 - score // 10),
                critical_issues=0,
                warning_issues=0,
                total_devices=15,
                disabled_devices=0,
                clutter_percentage=0.0,
                issues=[]
            )
            persist_scan_result(scan_result, db_path)

        return project_dir

    def test_analyze_trend_fails_without_init(self, tmp_path):
        """analyze_project_trend should fail if database not initialized."""
        db_path = tmp_path / "uninit.db"

        result, message = analyze_project_trend("Test", db_path)

        assert result is None
        assert "not initialized" in message.lower()

    def test_analyze_trend_not_found(self, tmp_path):
        """analyze_project_trend should fail if project not found."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        result, message = analyze_project_trend("Nonexistent", db_path)

        assert result is None
        assert "no project found" in message.lower()

    def test_analyze_trend_requires_two_versions(self, tmp_path):
        """analyze_project_trend requires at least 2 versions."""
        db_path = tmp_path / "test.db"
        self._setup_project_with_trend(tmp_path, db_path, [70])

        result, message = analyze_project_trend("Trending", db_path)

        assert result is None
        assert "at least 2" in message.lower()

    def test_analyze_trend_improving(self, tmp_path):
        """analyze_project_trend should detect improving trend."""
        db_path = tmp_path / "test.db"
        # Scores increasing: 50 -> 60 -> 70 -> 80 -> 90
        self._setup_project_with_trend(tmp_path, db_path, [50, 60, 70, 80, 90])

        result, message = analyze_project_trend("Trending", db_path)

        assert result is not None
        assert message == "OK"
        assert result.trend_direction == 'improving'
        assert result.first_health == 50
        assert result.latest_health == 90
        assert result.avg_delta_per_version > 0

    def test_analyze_trend_declining(self, tmp_path):
        """analyze_project_trend should detect declining trend."""
        db_path = tmp_path / "test.db"
        # Scores decreasing: 90 -> 80 -> 70 -> 60 -> 50
        self._setup_project_with_trend(tmp_path, db_path, [90, 80, 70, 60, 50])

        result, message = analyze_project_trend("Trending", db_path)

        assert result is not None
        assert result.trend_direction == 'declining'
        assert result.avg_delta_per_version < 0

    def test_analyze_trend_stable(self, tmp_path):
        """analyze_project_trend should detect stable trend."""
        db_path = tmp_path / "test.db"
        # Scores stable: 70 -> 71 -> 69 -> 70 -> 71
        self._setup_project_with_trend(tmp_path, db_path, [70, 71, 69, 70, 71])

        result, message = analyze_project_trend("Trending", db_path)

        assert result is not None
        assert result.trend_direction == 'stable'

    def test_analyze_trend_timeline(self, tmp_path):
        """analyze_project_trend should include timeline."""
        db_path = tmp_path / "test.db"
        scores = [60, 65, 70, 75, 80]
        self._setup_project_with_trend(tmp_path, db_path, scores)

        result, _ = analyze_project_trend("Trending", db_path)

        assert len(result.timeline) == len(scores)
        assert result.timeline[0].health_score == 60
        assert result.timeline[-1].health_score == 80

        # Check deltas are calculated
        assert result.timeline[0].delta_from_previous == 0  # First has no delta
        assert result.timeline[1].delta_from_previous == 5  # 65 - 60

    def test_analyze_trend_metrics(self, tmp_path):
        """analyze_project_trend should calculate all metrics."""
        db_path = tmp_path / "test.db"
        scores = [50, 40, 80, 60, 90]  # Variable scores
        self._setup_project_with_trend(tmp_path, db_path, scores)

        result, _ = analyze_project_trend("Trending", db_path)

        assert result.best_health == 90
        assert result.worst_health == 40
        assert result.biggest_improvement == 40  # 40 -> 80
        assert result.biggest_regression == 20  # 80 -> 60


class TestWhatIfPredictions:
    """Tests for what-if predictions (Story 2.4)."""

    def _setup_project_with_history(self, tmp_path, db_path):
        """Helper to create a project with historical change data."""
        db_init(db_path)
        db = Database(db_path)

        project_dir = tmp_path / "Prediction Project"
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create project
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                (str(project_dir), "Prediction Project")
            )

            # Create versions
            conn.execute(
                """INSERT INTO versions
                   (project_id, als_path, als_filename, health_score, grade)
                   VALUES (?, ?, ?, ?, ?)""",
                (1, str(project_dir / "current.als"), "current.als", 65, "B")
            )

            # Add historical change patterns (10+ for high confidence)
            for i in range(12):
                conn.execute(
                    """INSERT INTO changes
                       (project_id, before_version_id, after_version_id,
                        change_type, track_name, device_name, device_type,
                        health_delta)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (1, 1, 1, "device_removed", "Bass",
                     f"Unused EQ {i}", "Eq8", 5)  # Positive pattern
                )

        return str(project_dir / "current.als")

    def test_get_whatif_fails_without_init(self, tmp_path):
        """get_what_if_predictions should fail if database not initialized."""
        db_path = tmp_path / "uninit.db"

        result, message = get_what_if_predictions("/fake/path.als", db_path)

        assert result is None
        assert "not initialized" in message.lower()

    def test_get_whatif_file_not_scanned(self, tmp_path):
        """get_what_if_predictions should fail if file not in database."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        result, message = get_what_if_predictions("/fake/path.als", db_path)

        assert result is None
        assert "not scanned" in message.lower()

    def test_get_whatif_returns_predictions(self, tmp_path):
        """get_what_if_predictions should return predictions based on history."""
        db_path = tmp_path / "test.db"
        als_path = self._setup_project_with_history(tmp_path, db_path)

        result, message = get_what_if_predictions(als_path, db_path)

        assert result is not None
        assert message == "OK"
        assert result.current_health == 65
        assert len(result.predictions) > 0

    def test_get_whatif_high_confidence(self, tmp_path):
        """Predictions with 10+ samples should have HIGH confidence."""
        db_path = tmp_path / "test.db"
        als_path = self._setup_project_with_history(tmp_path, db_path)

        result, _ = get_what_if_predictions(als_path, db_path)

        # Find the Eq8 removal prediction (we added 12 samples)
        eq8_pred = next(
            (p for p in result.predictions if p.device_type == 'Eq8'),
            None
        )
        assert eq8_pred is not None
        assert eq8_pred.confidence == 'HIGH'
        assert eq8_pred.sample_size >= 10


class TestSmartDiagnose:
    """Tests for smart recommendations (Story 2.5)."""

    def _setup_project_with_issues(self, tmp_path, db_path):
        """Helper to create a project with issues for smart diagnosis."""
        db_init(db_path)

        project_dir = tmp_path / "Smart Project"
        project_dir.mkdir(parents=True, exist_ok=True)

        scan_result = ScanResult(
            als_path=str(project_dir / "current.als"),
            health_score=55,
            grade="C",
            total_issues=5,
            critical_issues=2,
            warning_issues=2,
            total_devices=25,
            disabled_devices=10,
            clutter_percentage=40.0,
            issues=[
                ScanResultIssue(
                    track_name="Bass",
                    severity="critical",
                    category="clutter",
                    description="40% of devices are disabled",
                    fix_suggestion="Delete disabled devices"
                ),
                ScanResultIssue(
                    track_name="Lead",
                    severity="warning",
                    category="chain_order",
                    description="EQ after compressor",
                    fix_suggestion="Move EQ before compressor"
                )
            ]
        )
        persist_scan_result(scan_result, db_path)

        return str(project_dir / "current.als")

    def test_smart_diagnose_fails_without_init(self, tmp_path):
        """smart_diagnose should fail if database not initialized."""
        db_path = tmp_path / "uninit.db"

        result, message = smart_diagnose("/fake/path.als", db_path=db_path)

        assert result is None
        assert "not initialized" in message.lower()

    def test_smart_diagnose_file_not_scanned(self, tmp_path):
        """smart_diagnose should fail if file not in database."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        result, message = smart_diagnose("/fake/path.als", db_path=db_path)

        assert result is None
        assert "not found" in message.lower()

    def test_smart_diagnose_returns_recommendations(self, tmp_path):
        """smart_diagnose should return prioritized recommendations."""
        db_path = tmp_path / "test.db"
        als_path = self._setup_project_with_issues(tmp_path, db_path)

        result, message = smart_diagnose(als_path, db_path=db_path)

        assert result is not None
        assert message == "OK"
        assert result.health_score == 55
        assert result.grade == "C"
        assert len(result.recommendations) > 0

    def test_smart_diagnose_severity_counts(self, tmp_path):
        """smart_diagnose should count issues by severity."""
        db_path = tmp_path / "test.db"
        als_path = self._setup_project_with_issues(tmp_path, db_path)

        result, _ = smart_diagnose(als_path, db_path=db_path)

        assert result.critical_count == 1  # We added 1 critical (clutter only gets one)
        assert result.total_issues == 5

    def test_smart_diagnose_prioritizes_critical(self, tmp_path):
        """smart_diagnose should prioritize critical issues."""
        db_path = tmp_path / "test.db"
        als_path = self._setup_project_with_issues(tmp_path, db_path)

        result, _ = smart_diagnose(als_path, db_path=db_path)

        # Critical issues should be at the top
        if len(result.recommendations) > 0:
            first_rec = result.recommendations[0]
            assert first_rec.severity == 'critical'


class TestHasSufficientHistory:
    """Tests for sufficient history check."""

    def test_has_sufficient_history_empty(self, tmp_path):
        """has_sufficient_history should return False for empty database."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        result = has_sufficient_history(db_path)

        assert result is False

    def test_has_sufficient_history_with_data(self, tmp_path):
        """has_sufficient_history should return True with enough versions."""
        db_path = tmp_path / "test.db"
        db_init(db_path)
        db = Database(db_path)

        # Create 25 versions (threshold is typically 20)
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/test", "Test")
            )
            for i in range(25):
                conn.execute(
                    """INSERT INTO versions
                       (project_id, als_path, als_filename, health_score, grade)
                       VALUES (?, ?, ?, ?, ?)""",
                    (1, f"/test/v{i}.als", f"v{i}.als", 70, "B")
                )

        result = has_sufficient_history(db_path)

        assert result is True


class TestVersionChangeDataclass:
    """Tests for VersionChange dataclass."""

    def test_version_change_fields(self):
        """VersionChange should have all required fields."""
        change = VersionChange(
            id=1,
            project_id=1,
            before_version_id=1,
            after_version_id=2,
            change_type="device_removed",
            track_name="Bass",
            device_name="Reverb",
            device_type="AudioEffect",
            details="Removed unused reverb",
            health_delta=5,
            recorded_at=datetime.now(),
            likely_helped=True
        )

        assert change.id == 1
        assert change.change_type == "device_removed"
        assert change.likely_helped is True


class TestInsightPatternDataclass:
    """Tests for InsightPattern dataclass."""

    def test_insight_pattern_fields(self):
        """InsightPattern should have all required fields."""
        pattern = InsightPattern(
            change_type="device_removed",
            device_type="Reverb",
            device_name="Room Reverb",
            occurrence_count=15,
            avg_health_delta=3.5,
            total_health_delta=52,
            helps_health=True,
            confidence="HIGH"
        )

        assert pattern.change_type == "device_removed"
        assert pattern.helps_health is True
        assert pattern.confidence == "HIGH"


class TestTrendPointDataclass:
    """Tests for TrendPoint dataclass."""

    def test_trend_point_fields(self):
        """TrendPoint should have all required fields."""
        point = TrendPoint(
            version_id=1,
            als_filename="v1.als",
            health_score=75,
            scanned_at=datetime.now(),
            delta_from_previous=5
        )

        assert point.version_id == 1
        assert point.health_score == 75
        assert point.delta_from_previous == 5


class TestVersionChangeDataclass:
    """Tests for VersionChange dataclass fields including change_intent."""

    def test_version_change_has_intent_field(self):
        """VersionChange should have change_intent field."""
        change = VersionChange(
            id=1,
            project_id=1,
            before_version_id=1,
            after_version_id=2,
            change_type='device_removed',
            track_name='Kick',
            device_name='Eq8',
            device_type='Eq8',
            details='Removed EQ from kick track',
            health_delta=5,
            recorded_at=datetime.now()
        )

        # Default intent should be 'unknown'
        assert hasattr(change, 'change_intent')
        assert change.change_intent == 'unknown'

        # Should have addressed_issue field
        assert hasattr(change, 'addressed_issue')
        assert change.addressed_issue is None

    def test_version_change_intent_can_be_set(self):
        """VersionChange intent should be settable to 'likely_fix' or 'experiment'."""
        change = VersionChange(
            id=1,
            project_id=1,
            before_version_id=1,
            after_version_id=2,
            change_type='device_removed',
            track_name='Kick',
            device_name='Eq8',
            device_type='Eq8',
            details='Removed EQ',
            health_delta=5,
            recorded_at=datetime.now(),
            change_intent='likely_fix',
            addressed_issue='Addressed: Redundant EQ on kick track'
        )

        assert change.change_intent == 'likely_fix'
        assert change.addressed_issue is not None
        assert 'Redundant EQ' in change.addressed_issue

    def test_version_change_experiment_intent(self):
        """VersionChange can have 'experiment' intent."""
        change = VersionChange(
            id=1,
            project_id=1,
            before_version_id=1,
            after_version_id=2,
            change_type='device_added',
            track_name='Lead',
            device_name='Reverb',
            device_type='Reverb',
            details='Added reverb to lead',
            health_delta=-2,
            recorded_at=datetime.now(),
            change_intent='experiment',
            addressed_issue=None
        )

        assert change.change_intent == 'experiment'
        assert change.addressed_issue is None


class TestDetermineChangeIntent:
    """Tests for _determine_change_intent function."""

    def test_determine_intent_function_exists(self):
        """_determine_change_intent function should exist."""
        assert hasattr(database_module, '_determine_change_intent')

    def test_experiment_when_no_issues(self, tmp_path):
        """Changes when there are no issues should be experiments."""
        db_path = tmp_path / "test.db"
        db_init(db_path)

        # Create a project and version without issues
        db = Database(db_path)
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO projects (folder_path, song_name) VALUES (?, ?)",
                ("/test/project", "Test Project")
            )
            project_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """INSERT INTO versions (
                    project_id, als_path, als_filename, health_score, grade,
                    total_issues, critical_issues, warning_issues,
                    total_devices, disabled_devices, clutter_percentage
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (project_id, "/test/v1.als", "v1.als", 85, "A", 0, 0, 0, 10, 0, 0.0)
            )
            version_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Test intent determination
        _determine_change_intent = database_module._determine_change_intent
        intent, addressed = _determine_change_intent(
            'device_removed', 'Kick', 'Eq8', 'Eq8', version_id, db_path
        )

        # No issues = experiment
        assert intent == 'experiment'
        assert addressed is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
