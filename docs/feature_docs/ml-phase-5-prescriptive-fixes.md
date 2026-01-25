# Phase 5: Prescriptive Fixes v2

## Overview

**Goal:** Replace generic fix recommendations with profile-aware, specific fixes that move the WIP track toward the learned reference style.

**Duration:** 2-3 weeks

**Dependencies:**
- Phase 1 (Trance DNA Extraction)
- Phase 2 (Reference Profiler)
- Phase 3 (Gap Analyzer)
- Phase 4 (Embeddings) - Optional but enhances recommendations

**Outputs:**
- PrescriptiveFixGenerator class
- Profile-aware fix recommendations
- Feature-to-parameter mapping system
- Enhanced Ableton integration

## The Upgrade: Generic → Prescriptive

### Before (Current System)

```
Issue: Bass too loud
Fix: "Reduce bass volume"
```

### After (Prescriptive System)

```
Issue: Bass 4.2 dB above reference mean (outside acceptable range)
Target: Match reference profile bass level (-8.5 to -5.2 dB relative)
Fix: "Reduce Bass track volume by 3.5 dB (from -4.1 to -7.6 dB)"
     OR "Apply -3 dB low shelf at 120 Hz on Bass EQ Eight"
Device: Track 3 "Bass" → Device 0 "EQ Eight" → Parameter 12 (Band 2 Gain)
Auto-applicable: Yes
Confidence: 0.92
```

## Architecture

### Fix Generation Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                 PRESCRIPTIVE FIX PIPELINE                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Gap Report (from Phase 3)                                  │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  1. Gap-to-Action Mapping                           │    │
│  │     • Identify which gaps are fixable               │    │
│  │     • Map gap type to fix action category           │    │
│  │     • Calculate target adjustment amount            │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  2. Device Discovery                                │    │
│  │     • Query Ableton session for track devices       │    │
│  │     • Match gap to capable device                   │    │
│  │     • Find specific parameter to adjust             │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  3. Value Calculation                               │    │
│  │     • Calculate parameter value change needed       │    │
│  │     • Validate against parameter limits             │    │
│  │     • Convert units (dB → 0-1, Hz → normalized)    │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  4. Fix Generation                                  │    │
│  │     • Create PrescriptiveFix object                 │    │
│  │     • Generate human-readable description           │    │
│  │     • Attach parameter change for auto-apply        │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  5. Validation & Confidence                         │    │
│  │     • Estimate fix impact                           │    │
│  │     • Calculate confidence score                    │    │
│  │     • Flag risky or uncertain fixes                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Structures

### PrescriptiveFix

```python
@dataclass
class PrescriptiveFix:
    """A specific, actionable fix recommendation."""

    # Identity
    fix_id: str
    title: str
    description: str

    # Source
    source_gap: FeatureGap
    gap_feature: str
    gap_severity: str

    # Target
    target_value: float           # What we're aiming for
    target_source: str            # "profile_mean", "cluster_centroid", "percentile"

    # Action
    action_type: FixActionType    # EQ, VOLUME, COMPRESSION, etc.
    action_description: str       # Human-readable action

    # Device targeting
    track_name: str
    track_index: int
    device_name: str
    device_index: int
    parameter_name: str
    parameter_index: int

    # Values
    current_value: float
    new_value: float
    adjustment: float             # Delta (e.g., -3.5 dB)
    adjustment_unit: str          # "dB", "Hz", "%", "ratio"

    # Confidence & Risk
    confidence: float             # 0-1, how sure we are this helps
    risk_level: str               # "safe", "moderate", "risky"
    is_reversible: bool

    # Applicability
    is_automatable: bool
    requires_listening_check: bool
    manual_alternative: str       # What to do if auto-apply fails

    def to_parameter_change(self) -> ParameterChange:
        """Convert to bridge-compatible change object."""
        return ParameterChange(
            track_index=self.track_index,
            device_index=self.device_index,
            parameter_index=self.parameter_index,
            new_value=self.new_value
        )
```

### FixActionType Enum

```python
class FixActionType(Enum):
    # EQ actions
    EQ_LOW_CUT = "eq_low_cut"
    EQ_HIGH_CUT = "eq_high_cut"
    EQ_BAND_CUT = "eq_band_cut"
    EQ_BAND_BOOST = "eq_band_boost"
    EQ_SHELF_ADJUST = "eq_shelf_adjust"

    # Level actions
    VOLUME_ADJUST = "volume_adjust"
    GAIN_STAGING = "gain_staging"

    # Dynamics actions
    COMPRESSION_ADJUST = "compression_adjust"
    LIMITER_ADJUST = "limiter_adjust"
    SIDECHAIN_ADJUST = "sidechain_adjust"

    # Stereo actions
    WIDTH_ADJUST = "width_adjust"
    PAN_ADJUST = "pan_adjust"

    # Other
    DEVICE_BYPASS = "device_bypass"
    DEVICE_ENABLE = "device_enable"
    MANUAL_REQUIRED = "manual_required"
```

## Gap-to-Action Mapping

### Mapping Rules

```python
GAP_TO_ACTION_MAP = {
    # Frequency balance gaps
    'bass_level': [
        FixActionType.VOLUME_ADJUST,
        FixActionType.EQ_SHELF_ADJUST,
        FixActionType.EQ_LOW_CUT
    ],
    'sub_bass_energy': [
        FixActionType.EQ_BAND_ADJUST,
        FixActionType.EQ_LOW_CUT
    ],
    'low_mid_energy': [
        FixActionType.EQ_BAND_CUT,
        FixActionType.EQ_BAND_BOOST
    ],
    'high_frequency_content': [
        FixActionType.EQ_SHELF_ADJUST,
        FixActionType.EQ_HIGH_CUT
    ],

    # Dynamics gaps
    'loudness_lufs': [
        FixActionType.VOLUME_ADJUST,
        FixActionType.LIMITER_ADJUST
    ],
    'dynamic_range': [
        FixActionType.COMPRESSION_ADJUST
    ],
    'modulation_depth': [
        FixActionType.SIDECHAIN_ADJUST
    ],

    # Stereo gaps
    'stereo_width': [
        FixActionType.WIDTH_ADJUST
    ],
    'stereo_correlation': [
        FixActionType.WIDTH_ADJUST,
        FixActionType.MANUAL_REQUIRED
    ],

    # Cannot be auto-fixed
    'tempo': [FixActionType.MANUAL_REQUIRED],
    'key': [FixActionType.MANUAL_REQUIRED],
    'arrangement': [FixActionType.MANUAL_REQUIRED],
}
```

### Target Calculation

```python
def calculate_target_value(
    gap: FeatureGap,
    profile: ReferenceProfile,
    strategy: str = "mean"  # or "percentile", "cluster"
) -> Tuple[float, str]:
    """
    Determine target value based on profile.

    Strategies:
    - mean: Target the profile mean
    - percentile: Target the 50th percentile (median)
    - cluster: Target the nearest cluster centroid
    - conservative: Target the edge of acceptable range
    """
    stats = profile.feature_stats[gap.feature_name]

    if strategy == "mean":
        return stats.mean, "profile_mean"

    elif strategy == "percentile":
        return stats.p50, "profile_median"

    elif strategy == "cluster":
        # Requires WIP cluster assignment
        cluster = find_nearest_cluster(gap.wip_features, profile)
        return cluster.centroid[gap.feature_name], f"cluster_{cluster.name}"

    elif strategy == "conservative":
        # Move just inside the acceptable range
        low, high = stats.acceptable_range
        if gap.direction == "high":
            return high * 0.95, "acceptable_range_high"
        else:
            return low * 1.05, "acceptable_range_low"
```

## PrescriptiveFixGenerator Class

```python
class PrescriptiveFixGenerator:
    """Generate profile-aware, specific fix recommendations."""

    def __init__(
        self,
        profile: ReferenceProfile,
        device_db: DeviceDatabase,
        bridge: AbletonBridge = None
    ):
        self.profile = profile
        self.device_db = device_db
        self.bridge = bridge
        self.parameter_mapper = ParameterMapper(device_db)

    def generate_fixes(
        self,
        gap_report: GapReport,
        session_state: SessionState = None,
        max_fixes: int = 20,
        min_confidence: float = 0.5,
        target_strategy: str = "mean"
    ) -> List[PrescriptiveFix]:
        """
        Generate fixes from gap report.

        Args:
            gap_report: Gap analysis from Phase 3
            session_state: Current Ableton session state
            max_fixes: Maximum fixes to generate
            min_confidence: Minimum confidence threshold
            target_strategy: How to determine target values

        Returns:
            List of PrescriptiveFix objects, sorted by priority
        """
        fixes = []

        for gap in gap_report.prioritized_gaps:
            if gap.severity == "ok":
                continue

            # Get possible actions for this gap type
            actions = GAP_TO_ACTION_MAP.get(gap.feature_name, [])

            for action in actions:
                fix = self._generate_fix_for_action(
                    gap, action, session_state, target_strategy
                )

                if fix and fix.confidence >= min_confidence:
                    fixes.append(fix)
                    break  # One fix per gap

        # Sort by priority and limit
        fixes = sorted(fixes, key=lambda f: -f.confidence)[:max_fixes]

        return fixes

    def _generate_fix_for_action(
        self,
        gap: FeatureGap,
        action: FixActionType,
        session_state: SessionState,
        target_strategy: str
    ) -> Optional[PrescriptiveFix]:
        """Generate a specific fix for a gap+action combination."""

        # Calculate target
        target_value, target_source = calculate_target_value(
            gap, self.profile, target_strategy
        )

        # Calculate adjustment needed
        adjustment = target_value - gap.wip_value

        # Find device to make the change
        device_match = self._find_device_for_action(
            action, gap, session_state
        )

        if not device_match:
            return None

        # Calculate parameter value
        param_value = self._calculate_parameter_value(
            action, adjustment, device_match
        )

        # Generate human-readable description
        description = self._generate_description(
            gap, action, adjustment, device_match
        )

        # Estimate confidence
        confidence = self._estimate_confidence(gap, action, device_match)

        return PrescriptiveFix(
            fix_id=f"fix_{gap.feature_name}_{action.value}",
            title=f"Adjust {gap.feature_name}",
            description=description,
            source_gap=gap,
            gap_feature=gap.feature_name,
            gap_severity=gap.severity,
            target_value=target_value,
            target_source=target_source,
            action_type=action,
            action_description=action.value.replace("_", " ").title(),
            track_name=device_match.track_name,
            track_index=device_match.track_index,
            device_name=device_match.device_name,
            device_index=device_match.device_index,
            parameter_name=device_match.parameter_name,
            parameter_index=device_match.parameter_index,
            current_value=device_match.current_value,
            new_value=param_value,
            adjustment=adjustment,
            adjustment_unit=gap.unit,
            confidence=confidence,
            risk_level="safe" if abs(adjustment) < 6 else "moderate",
            is_reversible=True,
            is_automatable=action != FixActionType.MANUAL_REQUIRED,
            requires_listening_check=action in [
                FixActionType.SIDECHAIN_ADJUST,
                FixActionType.WIDTH_ADJUST
            ],
            manual_alternative=self._generate_manual_alternative(action)
        )

    def _find_device_for_action(
        self,
        action: FixActionType,
        gap: FeatureGap,
        session_state: SessionState
    ) -> Optional[DeviceMatch]:
        """Find appropriate device and parameter for action."""

        # Map action to device types
        device_types = {
            FixActionType.EQ_BAND_CUT: ["EQ Eight", "EQ Three", "Channel EQ"],
            FixActionType.EQ_BAND_BOOST: ["EQ Eight", "EQ Three", "Channel EQ"],
            FixActionType.EQ_SHELF_ADJUST: ["EQ Eight", "Channel EQ"],
            FixActionType.VOLUME_ADJUST: ["Utility", None],  # None = track volume
            FixActionType.COMPRESSION_ADJUST: ["Compressor", "Glue Compressor"],
            FixActionType.WIDTH_ADJUST: ["Utility"],
            FixActionType.SIDECHAIN_ADJUST: ["Compressor", "Glue Compressor"],
        }

        target_devices = device_types.get(action, [])

        # Determine which track to target
        track = self._determine_target_track(gap, session_state)

        # Find device on track
        for device_type in target_devices:
            if device_type is None:
                # Use track volume
                return DeviceMatch(
                    track_name=track.name,
                    track_index=track.index,
                    device_name="Track Volume",
                    device_index=-1,
                    parameter_name="Volume",
                    parameter_index=-1,
                    current_value=track.volume
                )

            device = self.device_db.find_device_on_track(
                track, device_type
            )
            if device:
                param = self._find_parameter_for_action(device, action, gap)
                if param:
                    return DeviceMatch(
                        track_name=track.name,
                        track_index=track.index,
                        device_name=device.name,
                        device_index=device.index,
                        parameter_name=param.name,
                        parameter_index=param.index,
                        current_value=param.value
                    )

        return None
```

## Parameter Value Conversion

### dB to Normalized Value

```python
def db_to_normalized(db_value: float, db_range: Tuple[float, float]) -> float:
    """
    Convert dB value to 0-1 normalized parameter value.

    Args:
        db_value: Value in dB
        db_range: (min_db, max_db) range for the parameter

    Returns:
        Normalized value 0-1
    """
    min_db, max_db = db_range
    return (db_value - min_db) / (max_db - min_db)


def normalized_to_db(normalized: float, db_range: Tuple[float, float]) -> float:
    """Convert 0-1 normalized value to dB."""
    min_db, max_db = db_range
    return min_db + normalized * (max_db - min_db)


# Device-specific ranges
EQ_EIGHT_GAIN_RANGE = (-15, 15)  # dB
UTILITY_GAIN_RANGE = (-35, 35)   # dB
COMPRESSOR_THRESHOLD_RANGE = (-40, 0)  # dB
```

### Frequency to EQ Parameter

```python
def freq_to_eq_band(frequency: float) -> int:
    """
    Determine which EQ Eight band to use for a frequency.

    Returns band index (1-8).
    """
    bands = [
        (20, 80, 1),     # Sub bass
        (80, 250, 2),    # Bass
        (250, 500, 3),   # Low mids
        (500, 2000, 4),  # Mids
        (2000, 4000, 5), # Upper mids
        (4000, 8000, 6), # Presence
        (8000, 16000, 7),# Brilliance
        (16000, 20000, 8) # Air
    ]

    for low, high, band in bands:
        if low <= frequency < high:
            return band

    return 4  # Default to mids
```

## Confidence Estimation

```python
def estimate_fix_confidence(
    gap: FeatureGap,
    action: FixActionType,
    device_match: DeviceMatch,
    profile: ReferenceProfile
) -> float:
    """
    Estimate how confident we are that this fix will help.

    Factors:
    - Gap severity (higher = more certain fix is needed)
    - Action directness (volume easier than EQ)
    - Device capability (EQ Eight better than EQ Three)
    - Profile consistency (low std = more confident target)
    """
    base_confidence = 0.5

    # Severity bonus
    severity_bonus = {
        "critical": 0.3,
        "warning": 0.2,
        "minor": 0.1
    }
    base_confidence += severity_bonus.get(gap.severity, 0)

    # Action directness
    direct_actions = {
        FixActionType.VOLUME_ADJUST: 0.15,
        FixActionType.EQ_BAND_CUT: 0.10,
        FixActionType.EQ_BAND_BOOST: 0.10,
        FixActionType.COMPRESSION_ADJUST: 0.05,
        FixActionType.WIDTH_ADJUST: 0.05,
    }
    base_confidence += direct_actions.get(action, 0)

    # Device capability
    if "EQ Eight" in device_match.device_name:
        base_confidence += 0.05
    if device_match.device_index == -1:  # Track volume
        base_confidence += 0.10

    # Profile consistency (low std = confident target)
    stats = profile.feature_stats.get(gap.feature_name)
    if stats:
        cv = stats.std / abs(stats.mean) if stats.mean != 0 else 1
        if cv < 0.2:  # Low coefficient of variation
            base_confidence += 0.10

    return min(base_confidence, 1.0)
```

## CLI Commands

### Generate Fixes

```bash
python generate_fixes.py \
    --wip "my_track.wav" \
    --profile "models/trance_profile.json" \
    --session  # Connect to Ableton for device discovery \
    --output "fixes.json"

# Output:
Analyzing gaps against profile...
Discovering devices in Ableton session...

Generated 8 prescriptive fixes:

[1] CRITICAL - Bass Level (confidence: 0.92)
    Gap: +4.2 dB above reference mean
    Fix: Reduce "Bass" track volume by 3.5 dB
    Device: Track 3 → Track Volume
    Auto-applicable: Yes

[2] CRITICAL - Stereo Width (confidence: 0.85)
    Gap: 0.25 vs 0.48 target
    Fix: Increase "Lead Synth" Utility width to 120%
    Device: Track 5 → Utility → Width
    Auto-applicable: Yes

[3] WARNING - Sidechain Depth (confidence: 0.78)
    Gap: 3.1 dB vs 6.2 dB target
    Fix: Lower Compressor threshold on "Bass" by 4 dB
    Device: Track 3 → Compressor → Threshold
    Auto-applicable: Yes (requires listening check)

...

Apply all? [a] All / [s] Select / [n] None:
```

### Apply Fixes

```bash
python apply_prescriptive_fixes.py \
    --fixes "fixes.json" \
    --auto-apply \
    --backup  # Create undo points

# Output:
Applying 8 fixes to Ableton session...

[1/8] Reducing Bass track volume by 3.5 dB... ✓
[2/8] Adjusting Lead Synth Utility width... ✓
[3/8] Lowering Bass Compressor threshold... ✓
...

All fixes applied successfully!

To undo: python apply_prescriptive_fixes.py --undo "fixes_backup_20240115.json"
```

## Integration with Existing System

### Upgrade Path

```python
# Old system
from smart_fix_generator import SmartFixGenerator
fixes = SmartFixGenerator().generate_fixes(analysis)

# New system (drop-in replacement with profile)
from prescriptive_fixes import PrescriptiveFixGenerator
profile = ReferenceProfile.load("trance_profile.json")
generator = PrescriptiveFixGenerator(profile, device_db, bridge)
fixes = generator.generate_fixes(gap_report, session_state)

# Fixes are now profile-aware with specific targets
```

### Backward Compatibility

```python
class PrescriptiveFixGenerator:
    def generate_fixes_legacy(self, analysis_result) -> List[Fix]:
        """
        Generate fixes in old format for backward compatibility.

        Converts PrescriptiveFix to legacy Fix objects.
        """
        prescriptive_fixes = self.generate_fixes(...)

        legacy_fixes = []
        for pf in prescriptive_fixes:
            legacy_fixes.append(Fix(
                title=pf.title,
                description=pf.description,
                severity=pf.gap_severity,
                is_automatable=pf.is_automatable,
                # ... map other fields
            ))

        return legacy_fixes
```

## Testing Strategy

### Unit Tests

```python
def test_gap_to_action_mapping():
    """Correct actions mapped for each gap type"""
    assert FixActionType.VOLUME_ADJUST in GAP_TO_ACTION_MAP['bass_level']
    assert FixActionType.MANUAL_REQUIRED in GAP_TO_ACTION_MAP['tempo']

def test_target_calculation_mean():
    """Mean strategy returns profile mean"""
    gap = FeatureGap(feature_name='bass_level', ...)
    profile = create_test_profile(bass_level_mean=-6.0)
    target, source = calculate_target_value(gap, profile, 'mean')
    assert target == -6.0
    assert source == 'profile_mean'

def test_db_to_normalized():
    """dB conversion is accurate"""
    assert db_to_normalized(0, (-15, 15)) == 0.5
    assert db_to_normalized(-15, (-15, 15)) == 0.0
    assert db_to_normalized(15, (-15, 15)) == 1.0

def test_confidence_critical_gap():
    """Critical gaps get higher confidence"""
    critical_gap = FeatureGap(severity='critical', ...)
    minor_gap = FeatureGap(severity='minor', ...)

    critical_conf = estimate_fix_confidence(critical_gap, ...)
    minor_conf = estimate_fix_confidence(minor_gap, ...)

    assert critical_conf > minor_conf
```

### Integration Tests

```python
def test_full_fix_generation():
    """Complete pipeline generates valid fixes"""
    profile = ReferenceProfile.load("test_profile.json")
    gap_report = GapAnalyzer(profile).analyze("test_track.wav")
    generator = PrescriptiveFixGenerator(profile, device_db)

    fixes = generator.generate_fixes(gap_report)

    assert len(fixes) > 0
    for fix in fixes:
        assert fix.confidence > 0
        assert fix.track_index >= 0 or fix.track_index == -1
        if fix.is_automatable:
            assert fix.to_parameter_change() is not None
```

## Deliverables Checklist

- [ ] `prescriptive_fixes.py` - Main generator class
- [ ] `gap_to_action.py` - Mapping rules
- [ ] `parameter_mapper.py` - Feature→parameter mapping
- [ ] `value_conversion.py` - Unit conversions
- [ ] `confidence.py` - Confidence estimation
- [ ] `generate_fixes.py` - CLI for generation
- [ ] `apply_prescriptive_fixes.py` - CLI for application
- [ ] Unit tests for all modules
- [ ] Integration tests with Ableton
- [ ] Documentation with examples

## Success Criteria

1. **Fixes are specific** - Include exact dB/Hz/% values
2. **Fixes reference profile** - Tied to learned targets
3. **Device targeting works** - Correct device/parameter identified
4. **Confidence is meaningful** - Higher confidence = better outcomes
5. **Auto-apply success > 90%** - Fixes apply without errors
6. **Fixes improve gaps** - Re-analysis shows reduced gap scores
7. **Human-readable** - Clear descriptions of what and why
