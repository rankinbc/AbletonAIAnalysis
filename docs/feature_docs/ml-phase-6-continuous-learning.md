# Phase 6: Continuous Learning & Feedback Loop

## Overview

**Goal:** Create a feedback system that learns from applied fixes, tracks effectiveness, and continuously improves recommendations.

**Duration:** Ongoing (initial setup: 1-2 weeks)

**Dependencies:**
- Phase 1-5 (all previous phases)

**Outputs:**
- Feedback collection system
- Fix effectiveness tracking
- Profile refinement pipeline
- A/B testing framework

## Why Continuous Learning?

### The Problem with Static Models

A static profile assumes:
- User's taste doesn't evolve
- Reference collection is complete
- All fixes are equally effective

Reality:
- Producers grow and change preferences
- New reference tracks are added
- Some fixes work better than others

### The Solution: Feedback Loop

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTINUOUS LEARNING LOOP                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐             │
│  │ Generate │──────│  Apply  │──────│ Collect │             │
│  │  Fixes   │      │  Fixes  │      │ Feedback│             │
│  └─────────┘      └─────────┘      └─────────┘             │
│       ▲                                  │                   │
│       │                                  ▼                   │
│       │           ┌─────────────────────────┐               │
│       │           │   Analyze Outcomes       │               │
│       │           │   • Did gaps improve?    │               │
│       │           │   • User accepted fix?   │               │
│       │           │   • Track bounced?       │               │
│       │           └─────────────────────────┘               │
│       │                                  │                   │
│       │                                  ▼                   │
│  ┌─────────┐      ┌─────────────────────────┐               │
│  │ Update  │◄─────│   Refine Model           │               │
│  │ Profile │      │   • Adjust targets       │               │
│  └─────────┘      │   • Update confidence    │               │
│                   │   • Retrain embeddings   │               │
│                   └─────────────────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Feedback Collection

### Types of Feedback

| Feedback Type | Source | Signal |
|---------------|--------|--------|
| **Explicit Accept** | User clicks "Apply" | Positive |
| **Explicit Reject** | User clicks "Skip" | Negative |
| **Undo** | User reverses fix | Strong negative |
| **Re-analysis Improvement** | Gap score decreases | Positive |
| **Re-analysis Regression** | Gap score increases | Strong negative |
| **Bounce/Export** | User exports track | Positive (implicit) |
| **Session Save** | User saves project | Positive (implicit) |

### FeedbackEvent Data Structure

```python
@dataclass
class FeedbackEvent:
    """Record of feedback on a fix."""

    event_id: str
    timestamp: datetime

    # Fix identification
    fix_id: str
    fix_type: FixActionType
    feature_name: str

    # Context
    track_path: str
    session_id: str
    profile_version: str

    # Values
    original_value: float
    target_value: float
    applied_value: float

    # Feedback signals
    user_action: str          # "accept", "reject", "undo", "modify"
    was_applied: bool
    was_undone: bool

    # Outcome measurement
    gap_before: float
    gap_after: Optional[float]  # Measured on re-analysis
    improvement_ratio: Optional[float]

    # User modifications
    user_modified_value: Optional[float]  # If user tweaked the fix

    # Implicit signals
    session_saved_after: bool
    track_bounced_after: bool

    # Metadata
    notes: Optional[str]
```

### Feedback Collection Implementation

```python
class FeedbackCollector:
    """Collect and store feedback on applied fixes."""

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.pending_fixes = {}  # Track fixes awaiting feedback

    def record_fix_applied(
        self,
        fix: PrescriptiveFix,
        session_id: str
    ) -> str:
        """Record that a fix was applied, start tracking."""
        event_id = generate_event_id()

        self.pending_fixes[event_id] = FeedbackEvent(
            event_id=event_id,
            timestamp=datetime.now(),
            fix_id=fix.fix_id,
            fix_type=fix.action_type,
            feature_name=fix.gap_feature,
            original_value=fix.current_value,
            target_value=fix.target_value,
            applied_value=fix.new_value,
            gap_before=fix.source_gap.z_score,
            was_applied=True,
            session_id=session_id,
            ...
        )

        return event_id

    def record_user_action(
        self,
        event_id: str,
        action: str,  # "accept", "reject", "undo", "modify"
        modified_value: float = None
    ):
        """Record user's explicit action on a fix."""
        if event_id in self.pending_fixes:
            event = self.pending_fixes[event_id]
            event.user_action = action
            event.was_undone = action == "undo"
            event.user_modified_value = modified_value

    def record_outcome(
        self,
        event_id: str,
        gap_after: float
    ):
        """Record measured outcome after fix application."""
        if event_id in self.pending_fixes:
            event = self.pending_fixes[event_id]
            event.gap_after = gap_after
            event.improvement_ratio = (
                (event.gap_before - gap_after) / event.gap_before
                if event.gap_before != 0 else 0
            )

    def finalize_and_store(self, event_id: str):
        """Store completed feedback event."""
        if event_id in self.pending_fixes:
            event = self.pending_fixes.pop(event_id)
            self._append_to_storage(event)

    def _append_to_storage(self, event: FeedbackEvent):
        """Append event to persistent storage."""
        # JSON lines format for easy streaming
        with open(self.storage_path, 'a') as f:
            f.write(json.dumps(asdict(event)) + '\n')
```

## Effectiveness Analysis

### Fix Effectiveness Metrics

```python
class EffectivenessAnalyzer:
    """Analyze fix effectiveness from feedback data."""

    def __init__(self, feedback_path: str):
        self.feedback = self._load_feedback(feedback_path)

    def compute_fix_type_effectiveness(self) -> Dict[FixActionType, float]:
        """
        Compute effectiveness score per fix type.

        Effectiveness = weighted average of:
        - Accept rate (40%)
        - Improvement ratio (40%)
        - Undo rate inverted (20%)
        """
        results = {}

        for fix_type in FixActionType:
            events = [e for e in self.feedback if e.fix_type == fix_type]
            if not events:
                continue

            accept_rate = sum(1 for e in events if e.user_action == "accept") / len(events)
            avg_improvement = np.mean([
                e.improvement_ratio for e in events
                if e.improvement_ratio is not None
            ] or [0])
            undo_rate = sum(1 for e in events if e.was_undone) / len(events)

            effectiveness = (
                0.4 * accept_rate +
                0.4 * avg_improvement +
                0.2 * (1 - undo_rate)
            )

            results[fix_type] = effectiveness

        return results

    def compute_feature_confidence_adjustment(self) -> Dict[str, float]:
        """
        Compute confidence adjustment factors per feature.

        High effectiveness → increase confidence
        Low effectiveness → decrease confidence
        """
        feature_effectiveness = {}

        for feature in set(e.feature_name for e in self.feedback):
            events = [e for e in self.feedback if e.feature_name == feature]

            # Compute weighted outcome score
            total_weight = 0
            weighted_score = 0

            for event in events:
                weight = 1.0
                if event.user_action == "accept":
                    score = 1.0
                elif event.user_action == "reject":
                    score = 0.0
                elif event.was_undone:
                    score = -0.5
                else:
                    score = 0.5

                if event.improvement_ratio is not None:
                    score = (score + event.improvement_ratio) / 2

                weighted_score += weight * score
                total_weight += weight

            avg_score = weighted_score / total_weight if total_weight > 0 else 0.5

            # Convert to adjustment factor (0.5 = no change, 0 = halve, 1 = double)
            feature_effectiveness[feature] = 0.5 + (avg_score - 0.5) * 0.5

        return feature_effectiveness
```

### Confidence Updating

```python
def update_fix_confidence(
    original_confidence: float,
    feedback_events: List[FeedbackEvent]
) -> float:
    """
    Update confidence based on accumulated feedback.

    Uses Bayesian-style updating:
    - Start with prior (original confidence)
    - Update with evidence (feedback events)
    """
    # Each event shifts confidence
    confidence = original_confidence

    for event in feedback_events:
        if event.user_action == "accept" and event.improvement_ratio and event.improvement_ratio > 0.5:
            # Strong positive: increase confidence
            confidence = confidence + 0.05 * (1 - confidence)
        elif event.was_undone:
            # Strong negative: decrease confidence
            confidence = confidence * 0.9
        elif event.user_action == "reject":
            # Mild negative
            confidence = confidence * 0.95

    return max(0.1, min(0.99, confidence))
```

## Profile Refinement

### Automatic Target Adjustment

```python
class ProfileRefiner:
    """Refine profile based on feedback."""

    def __init__(self, profile: ReferenceProfile, feedback_path: str):
        self.profile = profile
        self.analyzer = EffectivenessAnalyzer(feedback_path)

    def refine_profile(self) -> ReferenceProfile:
        """
        Create refined profile based on feedback.

        Adjustments:
        - Widen acceptable ranges for low-effectiveness features
        - Narrow ranges for high-effectiveness features
        - Adjust feature weights in scoring
        """
        refined = copy.deepcopy(self.profile)

        effectiveness = self.analyzer.compute_feature_confidence_adjustment()

        for feature, factor in effectiveness.items():
            if feature not in refined.feature_stats:
                continue

            stats = refined.feature_stats[feature]

            # Adjust acceptable range based on effectiveness
            range_width = stats.acceptable_range[1] - stats.acceptable_range[0]

            if factor < 0.4:
                # Low effectiveness: widen range (be less strict)
                expansion = range_width * 0.2
                stats.acceptable_range = (
                    stats.acceptable_range[0] - expansion,
                    stats.acceptable_range[1] + expansion
                )
            elif factor > 0.6:
                # High effectiveness: narrow range (be more precise)
                contraction = range_width * 0.1
                stats.acceptable_range = (
                    stats.acceptable_range[0] + contraction,
                    stats.acceptable_range[1] - contraction
                )

        # Update version
        refined.version = f"{self.profile.version}_refined_{datetime.now().strftime('%Y%m%d')}"

        return refined
```

### New Reference Integration

```python
def integrate_new_references(
    profile: ReferenceProfile,
    new_tracks: List[str],
    extractor: TranceFeatureExtractor
) -> ReferenceProfile:
    """
    Add new reference tracks to profile.

    Process:
    1. Extract features from new tracks
    2. Update statistics (incremental mean/std)
    3. Re-evaluate cluster assignments
    4. Update embeddings index
    """
    # Extract features from new tracks
    new_features = []
    for track in new_tracks:
        features = extractor.extract_all(track)
        new_features.append(features)

    new_df = pd.DataFrame(new_features)

    # Incremental statistics update
    for feature in profile.feature_stats:
        if feature not in new_df.columns:
            continue

        old_stats = profile.feature_stats[feature]
        new_values = new_df[feature].values

        # Welford's online algorithm for mean/variance
        old_n = profile.track_count
        new_n = len(new_values)
        total_n = old_n + new_n

        old_mean = old_stats.mean
        new_mean = np.mean(new_values)

        combined_mean = (old_n * old_mean + new_n * new_mean) / total_n

        # Combined variance (more complex)
        old_var = old_stats.std ** 2
        new_var = np.var(new_values)
        combined_var = (
            (old_n * (old_var + (old_mean - combined_mean)**2) +
             new_n * (new_var + (new_mean - combined_mean)**2)) / total_n
        )

        old_stats.mean = combined_mean
        old_stats.std = np.sqrt(combined_var)

        # Update percentiles (approximate)
        all_p50 = (old_stats.p50 * old_n + np.median(new_values) * new_n) / total_n
        old_stats.p50 = all_p50

    profile.track_count = profile.track_count + len(new_tracks)

    return profile
```

## A/B Testing Framework

### Test Definition

```python
@dataclass
class ABTest:
    """Definition of an A/B test."""

    test_id: str
    name: str
    description: str

    # Variants
    control: Dict[str, Any]    # Original configuration
    treatment: Dict[str, Any]  # Modified configuration

    # Assignment
    assignment_ratio: float = 0.5  # Fraction in treatment

    # Duration
    start_date: datetime
    end_date: Optional[datetime]
    min_samples: int = 50

    # Metrics
    primary_metric: str        # e.g., "improvement_ratio"
    secondary_metrics: List[str]

    # Results
    control_results: List[float] = field(default_factory=list)
    treatment_results: List[float] = field(default_factory=list)
```

### Test Examples

```python
# Test 1: Conservative vs Aggressive targeting
test_targeting = ABTest(
    test_id="targeting_strategy_001",
    name="Conservative vs Mean Targeting",
    control={"target_strategy": "conservative"},
    treatment={"target_strategy": "mean"},
    primary_metric="improvement_ratio"
)

# Test 2: Confidence threshold
test_confidence = ABTest(
    test_id="confidence_threshold_001",
    name="50% vs 70% Confidence Threshold",
    control={"min_confidence": 0.5},
    treatment={"min_confidence": 0.7},
    primary_metric="accept_rate"
)
```

### Statistical Analysis

```python
from scipy import stats

def analyze_ab_test(test: ABTest) -> Dict[str, Any]:
    """
    Analyze A/B test results.

    Returns:
        Statistical significance and effect size
    """
    control = np.array(test.control_results)
    treatment = np.array(test.treatment_results)

    # Basic stats
    control_mean = np.mean(control)
    treatment_mean = np.mean(treatment)

    # T-test for significance
    t_stat, p_value = stats.ttest_ind(control, treatment)

    # Effect size (Cohen's d)
    pooled_std = np.sqrt(
        ((len(control)-1)*np.var(control) + (len(treatment)-1)*np.var(treatment))
        / (len(control) + len(treatment) - 2)
    )
    cohens_d = (treatment_mean - control_mean) / pooled_std

    # Decision
    significant = p_value < 0.05
    meaningful = abs(cohens_d) > 0.2

    return {
        'control_mean': control_mean,
        'treatment_mean': treatment_mean,
        'lift': (treatment_mean - control_mean) / control_mean,
        'p_value': p_value,
        'significant': significant,
        'cohens_d': cohens_d,
        'meaningful': meaningful,
        'recommendation': 'adopt_treatment' if significant and cohens_d > 0.2 else 'keep_control'
    }
```

## CLI Commands

### View Feedback Summary

```bash
python feedback_summary.py --since 30d

# Output:
Feedback Summary (Last 30 Days)
===============================

Total Fixes Applied: 342
Accept Rate: 78.4%
Undo Rate: 4.7%
Average Improvement: 0.62

By Fix Type:
  Volume Adjust:      85.2% effective (156 samples)
  EQ Band Cut:        72.1% effective (89 samples)
  Compression:        68.4% effective (43 samples)
  Width Adjust:       61.2% effective (31 samples)

By Feature:
  bass_level:         82.1% effective
  stereo_width:       71.3% effective
  modulation_depth:   65.8% effective

Recommendations:
  ✓ Volume adjustments working well
  ⚠ Consider widening stereo_width acceptable range
  ⚠ Lower confidence for modulation_depth fixes
```

### Refine Profile

```bash
python refine_profile.py \
    --profile "models/trance_profile.json" \
    --feedback "feedback/feedback.jsonl" \
    --output "models/trance_profile_refined.json"

# Output:
Analyzing 342 feedback events...

Adjustments:
  bass_level: Narrowing acceptable range (high effectiveness)
  stereo_width: Widening acceptable range (low effectiveness)
  modulation_depth: No change

Confidence Updates:
  Volume fixes: 0.85 → 0.89
  EQ fixes: 0.78 → 0.76
  Compression fixes: 0.72 → 0.70

Refined profile saved to: models/trance_profile_refined.json
```

### Run A/B Test

```bash
python ab_test.py --test targeting_strategy_001 --status

# Output:
A/B Test: Conservative vs Mean Targeting
========================================

Status: Running
Started: 2024-01-01
Samples: Control=127, Treatment=134

Current Results:
  Control (conservative):   0.58 avg improvement
  Treatment (mean):         0.64 avg improvement
  Lift: +10.3%

Statistical Analysis:
  P-value: 0.023 (significant at p<0.05)
  Cohen's d: 0.31 (small-medium effect)

Recommendation: ADOPT TREATMENT (mean targeting)
```

## Deliverables Checklist

- [ ] `feedback_collector.py` - Feedback collection system
- [ ] `effectiveness_analyzer.py` - Analyze fix outcomes
- [ ] `profile_refiner.py` - Profile refinement logic
- [ ] `ab_testing.py` - A/B test framework
- [ ] `feedback_summary.py` - CLI for feedback review
- [ ] `refine_profile.py` - CLI for refinement
- [ ] `ab_test.py` - CLI for A/B tests
- [ ] Unit tests for all modules
- [ ] Feedback storage schema
- [ ] Documentation

## Success Criteria

1. **Feedback collection working** - Events captured and stored
2. **Effectiveness metrics computed** - Per fix type and feature
3. **Profile refinement automated** - Runs without manual intervention
4. **A/B testing framework functional** - Can run and analyze tests
5. **Improvements measurable** - Refined profile outperforms original
6. **No data loss** - Feedback persists across sessions
