# Ralph Loop Prompt: ML Phase 6 (Continuous Learning)

You are an autonomous coding agent completing the **final ML phase** for AbletonAIAnalysis.

**Phases 1-5 are DONE.** You are implementing Phase 6: Continuous Learning.

## What Already Exists (DO NOT RECREATE)

```
src/feature_extraction/     # DONE - trance feature extractors
src/profiling/              # DONE - reference profiler, style clusters
src/analysis/               # DONE - gap analyzer, delta reporter
src/embeddings/             # DONE - OpenL3, FAISS similarity
src/fixes/                  # DONE - prescriptive fix generator
```

## Phase 6: Continuous Learning System

Build a feedback loop that learns from user decisions and improves recommendations over time.

### 6.1 Feedback Database (`learning/learning_db.py`)

SQLite-based storage for all feedback data.

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import sqlite3

@dataclass
class FixFeedback:
    """Record of user feedback on a fix recommendation."""
    feedback_id: str
    timestamp: datetime
    track_path: str
    profile_name: str

    # The fix that was recommended
    feature: str
    severity: str
    suggested_change: str
    confidence: float

    # User decision
    accepted: bool  # Did user apply the fix?
    modified: bool  # Did user modify the fix before applying?
    user_notes: Optional[str]

    # Effectiveness (filled in later)
    pre_gap_score: Optional[float]  # Gap score before fix
    post_gap_score: Optional[float]  # Gap score after fix
    improvement: Optional[float]  # Calculated improvement


@dataclass
class SessionRecord:
    """Record of an analysis session."""
    session_id: str
    timestamp: datetime
    track_path: str
    profile_name: str

    initial_similarity: float
    initial_trance_score: float
    fixes_suggested: int
    fixes_accepted: int
    fixes_rejected: int

    final_similarity: Optional[float]
    final_trance_score: Optional[float]


class LearningDatabase:
    """SQLite database for continuous learning data."""

    def __init__(self, db_path: str = "learning_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        # Tables: fix_feedback, sessions, feature_weights, user_preferences

    def record_feedback(self, feedback: FixFeedback):
        """Record user feedback on a fix."""

    def record_session(self, session: SessionRecord):
        """Record an analysis session."""

    def get_feature_acceptance_rate(self, feature: str) -> float:
        """Get acceptance rate for fixes on a specific feature."""

    def get_feature_effectiveness(self, feature: str) -> float:
        """Get average improvement when fix is applied."""

    def get_all_feedback(self, limit: int = 100) -> List[FixFeedback]:
        """Get recent feedback records."""
```

### 6.2 Feedback Collector (`learning/feedback_collector.py`)

Interactive feedback collection during fix application.

```python
class FeedbackCollector:
    """Collect user feedback on fix recommendations."""

    def __init__(self, db: LearningDatabase):
        self.db = db
        self.current_session: Optional[SessionRecord] = None

    def start_session(self, track_path: str, profile_name: str, gap_report: GapReport):
        """Start a new feedback session."""

    def record_fix_decision(
        self,
        fix: PrescriptiveFix,
        accepted: bool,
        modified: bool = False,
        notes: Optional[str] = None
    ):
        """Record user's decision on a fix."""

    def record_effectiveness(
        self,
        fix_id: str,
        pre_score: float,
        post_score: float
    ):
        """Record before/after scores for a fix."""

    def end_session(self, final_gap_report: Optional[GapReport] = None):
        """End session and compute final stats."""

    def prompt_for_feedback(self, fix: PrescriptiveFix) -> FixFeedback:
        """Interactive CLI prompt for fix feedback."""
        # Print fix details
        # Ask: Accept? (y/n/m for modified)
        # Optional: notes
```

### 6.3 Effectiveness Tracker (`learning/effectiveness_tracker.py`)

Track whether applied fixes actually improved the mix.

```python
class EffectivenessTracker:
    """Track fix effectiveness over time."""

    def __init__(self, db: LearningDatabase):
        self.db = db

    def compute_before_after(
        self,
        track_path: str,
        profile: ReferenceProfile,
        applied_fixes: List[str]  # Fix IDs
    ) -> Dict[str, float]:
        """
        Re-analyze track and compute improvement.

        Returns dict with:
          - similarity_change
          - trance_score_change
          - per_feature_changes
        """

    def get_feature_effectiveness_report(self) -> Dict[str, Dict]:
        """
        Get effectiveness stats per feature.

        Returns:
        {
            'pumping_modulation_depth_db': {
                'times_suggested': 45,
                'times_accepted': 32,
                'acceptance_rate': 0.71,
                'avg_improvement': 0.15,
                'confidence_adjustment': 1.1
            },
            ...
        }
        """

    def identify_ineffective_fixes(self) -> List[str]:
        """Find fix types that rarely help."""
```

### 6.4 Profile Tuner (`learning/profile_tuner.py`)

Adjust profile and weights based on learned preferences.

```python
class ProfileTuner:
    """Tune profile based on user feedback."""

    def __init__(self, db: LearningDatabase):
        self.db = db

    def compute_weight_adjustments(self) -> Dict[str, float]:
        """
        Compute adjusted weights based on acceptance rates.

        Features with high acceptance get boosted.
        Features with low acceptance get reduced.
        """

    def compute_confidence_adjustments(self) -> Dict[str, float]:
        """
        Adjust confidence scores based on effectiveness.

        If a fix type consistently improves scores, boost confidence.
        If it rarely helps, reduce confidence.
        """

    def suggest_profile_updates(self, profile: ReferenceProfile) -> Dict:
        """
        Suggest updates to acceptable ranges based on user behavior.

        If user consistently accepts fixes outside current range,
        maybe the range should be adjusted.
        """

    def apply_tuning(
        self,
        profile: ReferenceProfile,
        apply_weights: bool = True,
        apply_ranges: bool = False  # More conservative
    ) -> ReferenceProfile:
        """Apply learned adjustments to profile."""

    def export_learning_report(self) -> str:
        """Generate human-readable report of learned adjustments."""
```

### 6.5 CLI Integration

Add to `analyze.py`:

```bash
# Run analysis with feedback collection
python analyze.py --audio "wip.wav" --gap-analysis "profile.json" --collect-feedback

# View learning stats
python analyze.py --learning-stats

# Apply learned adjustments to profile
python analyze.py --tune-profile "profile.json" --output "tuned_profile.json"

# Reset learning data
python analyze.py --reset-learning
```

### 6.6 Interactive Feedback Flow

When `--collect-feedback` is used:

```
Gap Analysis Complete
=====================
Similarity: 72% | Trance Score: 0.68

FIX 1/5: Sidechain Compression [CRITICAL]
  Current: 3.2 dB | Target: 6.1 dB
  Action: Lower Compressor threshold by ~4 dB
  Confidence: 92%

  Apply this fix? [y]es / [n]o / [m]odified / [s]kip all: y

  Recording: ACCEPTED

FIX 2/5: Stereo Width [WARNING]
  ...

Session Complete
================
Fixes accepted: 3/5 (60%)
Fixes rejected: 2/5

Re-analyze to measure improvement? [y/n]: y

  Analyzing updated track...

  Improvement Report:
    Similarity: 72% → 81% (+9%)
    Trance Score: 0.68 → 0.74 (+0.06)

  Most effective fix: Sidechain (+0.12 similarity)
  Least effective fix: Hi-hat adjustment (+0.01)

Feedback saved to learning_data.db
```

### 6.7 Learning Stats Output

```
Learning Statistics
===================
Sessions: 23
Total fixes suggested: 187
Total fixes accepted: 134 (72%)

Per-Feature Breakdown:
                              Suggested  Accepted  Rate   Avg Improvement
  pumping_modulation_depth_db       45        38   84%         +0.15
  stereo_width                      32        28   88%         +0.12
  spectral_brightness               28        19   68%         +0.08
  four_on_floor_score               22        14   64%         +0.05
  energy_progression                18         9   50%         +0.03
  offbeat_hihat_score               15         8   53%         +0.02
  acid_303_score                    12         4   33%         +0.01

Recommendations:
  - BOOST confidence for: stereo_width, pumping (high acceptance + improvement)
  - REDUCE confidence for: acid_303_score (low acceptance)
  - Consider removing: offbeat_hihat fixes (low improvement)
```

---

## File Structure to Create

```
src/learning/
├── __init__.py
├── learning_db.py           # SQLite storage
├── feedback_collector.py    # Interactive feedback
├── effectiveness_tracker.py # Before/after tracking
└── profile_tuner.py         # Weight/range adjustments
```

## Process

1. Create `learning_db.py` with SQLite schema
2. Create `feedback_collector.py` for interactive collection
3. Create `effectiveness_tracker.py` for measuring improvement
4. Create `profile_tuner.py` for applying learnings
5. Add CLI flags to `analyze.py`
6. Test the full feedback loop

## Rules

- Use SQLite (no external database dependencies)
- Make feedback collection optional (`--collect-feedback` flag)
- Don't modify existing gap analysis - add on top of it
- Store database in project root or configurable location
- Follow existing code patterns

## Exit

Output DONE when:
- All 4 learning modules implemented
- CLI integration complete
- Feedback loop works end-to-end
- Learning stats display works

DO NOT output DONE until the full continuous learning system works.
