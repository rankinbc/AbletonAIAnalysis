"""
Fix Generator Module

Converts analysis issues into actionable Ableton fixes.
Maps common mixing problems to specific parameter changes.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum


class FixCategory(Enum):
    LEVELS = "levels"
    FREQUENCY = "frequency"
    DYNAMICS = "dynamics"
    STEREO = "stereo"
    MASTERING = "mastering"


class FixSeverity(Enum):
    CRITICAL = "critical"      # Must fix - will cause playback issues
    WARNING = "warning"        # Should fix - noticeably degrades quality
    SUGGESTION = "suggestion"  # Could fix - minor improvement


@dataclass
class ParameterTarget:
    """Identifies a specific parameter in Ableton."""
    track_name: str           # Track name or "Master"
    track_index: Optional[int] = None
    device_name: Optional[str] = None
    device_index: Optional[int] = None
    parameter_name: Optional[str] = None
    parameter_index: Optional[int] = None


@dataclass
class FixAction:
    """A single parameter change."""
    target: ParameterTarget
    action: str               # 'set', 'adjust', 'add_device'
    value: Any               # New value or adjustment amount
    unit: str = ""           # 'dB', '%', 'Hz', etc.
    description: str = ""


@dataclass
class Fix:
    """A complete fix recommendation."""
    id: str
    title: str
    description: str
    category: FixCategory
    severity: FixSeverity
    issue_source: str         # Which analyzer identified this
    actions: List[FixAction] = field(default_factory=list)
    requires_device: Optional[str] = None  # Device needed (e.g., "EQ Eight")
    manual_steps: List[str] = field(default_factory=list)  # If can't be automated
    confidence: float = 1.0   # How confident we are this fix is correct

    @property
    def is_automatable(self) -> bool:
        """Can this fix be applied automatically via OSC?"""
        return len(self.actions) > 0 and self.requires_device is None

    def __str__(self) -> str:
        sev = self.severity.value.upper()
        auto = "🤖" if self.is_automatable else "👤"
        return f"[{sev}] {auto} {self.title}"


# Common fix templates
FIX_TEMPLATES = {
    # ===== LEVEL FIXES =====
    "track_too_loud": {
        "title": "Track too loud: {track_name}",
        "category": FixCategory.LEVELS,
        "description": "Track '{track_name}' is {amount}dB louder than optimal",
        "action_template": {
            "action": "adjust",
            "parameter": "volume",
            "unit": "dB"
        }
    },
    "track_too_quiet": {
        "title": "Track too quiet: {track_name}",
        "category": FixCategory.LEVELS,
        "description": "Track '{track_name}' is {amount}dB quieter than optimal",
        "action_template": {
            "action": "adjust",
            "parameter": "volume",
            "unit": "dB"
        }
    },
    "master_clipping": {
        "title": "Master clipping detected",
        "category": FixCategory.MASTERING,
        "description": "Master output is clipping by {amount}dB",
        "action_template": {
            "action": "adjust",
            "target": "Master",
            "parameter": "volume",
            "unit": "dB"
        }
    },

    # ===== FREQUENCY FIXES =====
    "low_end_buildup": {
        "title": "Low-end buildup (200-500Hz)",
        "category": FixCategory.FREQUENCY,
        "description": "Muddy frequencies detected - {amount}% energy in 200-500Hz range",
        "requires_device": "EQ Eight",
        "manual_steps": [
            "Add EQ Eight to affected tracks",
            "Cut 3-4dB at 300Hz with Q=1.0",
            "Or high-pass non-bass tracks at 100-150Hz"
        ]
    },
    "harsh_highs": {
        "title": "Harsh high frequencies (3-8kHz)",
        "category": FixCategory.FREQUENCY,
        "description": "Excessive harshness in 3-8kHz range",
        "requires_device": "EQ Eight",
        "manual_steps": [
            "Add EQ Eight to master or offending tracks",
            "Cut 2-3dB at 4-5kHz with Q=1.5",
            "Consider a de-esser on vocals/leads"
        ]
    },
    "lacking_air": {
        "title": "Lacking high-frequency air",
        "category": FixCategory.FREQUENCY,
        "description": "Mix sounds dull - insufficient energy above 10kHz",
        "requires_device": "EQ Eight",
        "manual_steps": [
            "Add subtle high shelf boost (+2-3dB) at 10kHz on master",
            "Or boost air frequencies on individual synths/cymbals"
        ]
    },
    "excessive_bass": {
        "title": "Excessive bass energy",
        "category": FixCategory.FREQUENCY,
        "description": "Too much energy below 250Hz - mix may sound boomy",
        "requires_device": "EQ Eight",
        "manual_steps": [
            "High-pass all non-bass tracks at 80-120Hz",
            "Check kick and bass aren't competing",
            "Consider sidechain compression on bass"
        ]
    },

    # ===== DYNAMICS FIXES =====
    "over_compressed": {
        "title": "Over-compressed mix",
        "category": FixCategory.DYNAMICS,
        "description": "Crest factor {crest}dB is too low (target: 10-14dB)",
        "requires_device": "Limiter",
        "manual_steps": [
            "Reduce limiter ceiling/threshold on master",
            "Aim for -1dB true peak with more headroom",
            "Consider removing or reducing bus compression"
        ]
    },
    "weak_transients": {
        "title": "Weak transients - lacking punch",
        "category": FixCategory.DYNAMICS,
        "description": "Transient strength {strength} is below optimal",
        "requires_device": "Drum Buss or Compressor",
        "manual_steps": [
            "Add transient shaper to drums",
            "Increase attack on Drum Buss",
            "Or use parallel compression with fast attack"
        ]
    },

    # ===== STEREO FIXES =====
    "phase_issues": {
        "title": "CRITICAL: Phase correlation issues",
        "category": FixCategory.STEREO,
        "description": "Negative phase correlation ({correlation}) - will cancel in mono!",
        "severity": FixSeverity.CRITICAL,
        "manual_steps": [
            "Check for stereo widening plugins (Wider, Dimension Expander)",
            "Check for inverted phase on any tracks",
            "Use Utility to check mono compatibility",
            "Reduce stereo width on bass elements"
        ]
    },
    "too_narrow": {
        "title": "Stereo image too narrow",
        "category": FixCategory.STEREO,
        "description": "Correlation {correlation} - mix sounds mono",
        "requires_device": "Utility",
        "manual_steps": [
            "Add Utility to pads/synths, increase Width to 120-140%",
            "Pan elements left/right for separation",
            "Add stereo reverb/delay to create width"
        ]
    },
    "bass_too_wide": {
        "title": "Bass frequencies too wide",
        "category": FixCategory.STEREO,
        "description": "Low frequencies should be mono for club playback",
        "requires_device": "Utility",
        "manual_steps": [
            "Add Utility to bass track",
            "Enable 'Bass Mono' below 120Hz",
            "Or use Mid/Side EQ to mono the lows"
        ]
    },

    # ===== LOUDNESS FIXES =====
    "too_quiet_for_streaming": {
        "title": "Too quiet for streaming",
        "category": FixCategory.MASTERING,
        "description": "Loudness {lufs} LUFS is {diff}dB below streaming target (-14 LUFS)",
        "manual_steps": [
            "Increase limiter output or reduce threshold",
            "Target -14 LUFS for Spotify/YouTube",
            "Check true peak stays below -1dB"
        ]
    },
    "too_loud_for_streaming": {
        "title": "Too loud for streaming",
        "category": FixCategory.MASTERING,
        "description": "Loudness {lufs} LUFS - streaming platforms will turn it down",
        "manual_steps": [
            "Consider reducing limiter intensity",
            "You're losing dynamic range for no benefit",
            "Platforms normalize to -14 LUFS anyway"
        ]
    },
}


class FixGenerator:
    """
    Generates actionable fixes from analysis results.

    Usage:
        generator = FixGenerator()
        fixes = generator.generate_fixes(analysis_result, session_state)

        for fix in fixes:
            print(fix)
            if fix.is_automatable:
                bridge.apply_fix(fix)
    """

    def __init__(self, strict_mode: bool = False):
        """
        Args:
            strict_mode: If True, only generate fixes we're confident about
        """
        self.strict_mode = strict_mode
        self.min_confidence = 0.7 if strict_mode else 0.5

    def generate_fixes(
        self,
        analysis_result,
        session_state=None
    ) -> List[Fix]:
        """
        Generate fixes from an analysis result.

        Args:
            analysis_result: AnalysisResult from audio_analyzer
            session_state: Optional SessionState from ableton_bridge

        Returns:
            List of Fix objects, sorted by severity
        """
        fixes = []

        # Process each type of issue
        fixes.extend(self._process_clipping(analysis_result))
        fixes.extend(self._process_dynamics(analysis_result))
        fixes.extend(self._process_frequency(analysis_result))
        fixes.extend(self._process_stereo(analysis_result))
        fixes.extend(self._process_loudness(analysis_result))
        fixes.extend(self._process_transients(analysis_result))

        # Filter by confidence
        fixes = [f for f in fixes if f.confidence >= self.min_confidence]

        # Sort by severity (critical first)
        severity_order = {
            FixSeverity.CRITICAL: 0,
            FixSeverity.WARNING: 1,
            FixSeverity.SUGGESTION: 2
        }
        fixes.sort(key=lambda f: severity_order[f.severity])

        return fixes

    def _process_clipping(self, result) -> List[Fix]:
        """Generate fixes for clipping issues."""
        fixes = []
        clipping = result.clipping

        if clipping.has_clipping and clipping.severity in ['moderate', 'severe']:
            # Calculate how much to reduce
            reduction_db = -abs(20 * (clipping.max_peak - 0.95)) - 0.5

            fix = Fix(
                id="master_clipping",
                title="Master clipping detected",
                description=f"Peak at {clipping.max_peak:.3f} ({clipping.clip_count} samples clipped)",
                category=FixCategory.MASTERING,
                severity=FixSeverity.CRITICAL if clipping.severity == 'severe' else FixSeverity.WARNING,
                issue_source="clipping_analyzer",
                actions=[
                    FixAction(
                        target=ParameterTarget(track_name="Master"),
                        action="adjust",
                        value=reduction_db,
                        unit="dB",
                        description=f"Reduce master volume by {abs(reduction_db):.1f}dB"
                    )
                ],
                confidence=0.9
            )
            fixes.append(fix)

        return fixes

    def _process_dynamics(self, result) -> List[Fix]:
        """Generate fixes for dynamics issues."""
        fixes = []
        dynamics = result.dynamics

        if dynamics.is_over_compressed:
            fix = Fix(
                id="over_compressed",
                title="Over-compressed mix",
                description=f"Crest factor {dynamics.crest_factor_db:.1f}dB (target: 10-14dB for trance)",
                category=FixCategory.DYNAMICS,
                severity=FixSeverity.WARNING if dynamics.crest_factor_db > 4 else FixSeverity.CRITICAL,
                issue_source="dynamics_analyzer",
                requires_device="Limiter",
                manual_steps=[
                    f"Reduce limiter threshold by ~{12 - dynamics.crest_factor_db:.0f}dB",
                    "Or reduce input gain to limiter",
                    "Target crest factor: 10-14dB for trance"
                ],
                confidence=0.85
            )
            fixes.append(fix)

        return fixes

    def _process_frequency(self, result) -> List[Fix]:
        """Generate fixes for frequency balance issues."""
        fixes = []
        freq = result.frequency

        # Low-mid buildup (muddy)
        if freq.low_mid_energy > 25:
            fix = Fix(
                id="low_end_buildup",
                title="Low-mid buildup (muddy frequencies)",
                description=f"{freq.low_mid_energy:.1f}% energy in 250-500Hz (target: <20%)",
                category=FixCategory.FREQUENCY,
                severity=FixSeverity.WARNING,
                issue_source="frequency_analyzer",
                requires_device="EQ Eight",
                manual_steps=[
                    "Add EQ Eight to muddy tracks (pads, bass, guitars)",
                    "Cut 3-4dB at 300-400Hz with Q=1.0",
                    "High-pass non-bass tracks at 100-150Hz"
                ],
                confidence=0.8
            )
            fixes.append(fix)

        # Excessive bass
        combined_bass = freq.sub_bass_energy + freq.bass_energy
        if combined_bass > 45:
            fix = Fix(
                id="excessive_bass",
                title="Excessive bass energy",
                description=f"{combined_bass:.1f}% energy below 250Hz (target: 25-40%)",
                category=FixCategory.FREQUENCY,
                severity=FixSeverity.WARNING,
                issue_source="frequency_analyzer",
                requires_device="EQ Eight",
                manual_steps=[
                    "High-pass all non-bass tracks at 80-120Hz",
                    "Check kick and bass separation",
                    "Reduce bass track volume or apply EQ cuts"
                ],
                confidence=0.75
            )
            fixes.append(fix)

        # Lacking highs
        if freq.high_energy + freq.air_energy < 8:
            fix = Fix(
                id="lacking_air",
                title="Mix sounds dull - lacking air",
                description=f"Only {freq.high_energy + freq.air_energy:.1f}% energy above 6kHz",
                category=FixCategory.FREQUENCY,
                severity=FixSeverity.SUGGESTION,
                issue_source="frequency_analyzer",
                requires_device="EQ Eight",
                manual_steps=[
                    "Add gentle high shelf (+2-3dB at 10kHz) on master",
                    "Boost air frequencies on cymbals and synths",
                    "Check if low-pass filters are too aggressive"
                ],
                confidence=0.7
            )
            fixes.append(fix)

        # Harsh highs
        if freq.high_mid_energy > 30:
            fix = Fix(
                id="harsh_highs",
                title="Harsh high-mid frequencies",
                description=f"{freq.high_mid_energy:.1f}% energy in 2-6kHz range",
                category=FixCategory.FREQUENCY,
                severity=FixSeverity.WARNING,
                issue_source="frequency_analyzer",
                requires_device="EQ Eight",
                manual_steps=[
                    "Cut 2-3dB at 3-5kHz on harsh tracks",
                    "Use dynamic EQ or multiband compression",
                    "Check for resonant synth frequencies"
                ],
                confidence=0.75
            )
            fixes.append(fix)

        return fixes

    def _process_stereo(self, result) -> List[Fix]:
        """Generate fixes for stereo/phase issues."""
        fixes = []
        stereo = result.stereo

        if not stereo.is_stereo:
            return fixes

        # Phase issues (CRITICAL)
        if not stereo.phase_safe:
            fix = Fix(
                id="phase_issues",
                title="CRITICAL: Phase correlation negative",
                description=f"Correlation {stereo.correlation:.2f} - mix will cancel in mono!",
                category=FixCategory.STEREO,
                severity=FixSeverity.CRITICAL,
                issue_source="stereo_analyzer",
                manual_steps=[
                    "Check for stereo widening plugins and reduce/remove",
                    "Look for phase-inverted channels",
                    "Use Utility 'Mono' to identify problem tracks",
                    "Bass MUST be mono below 150Hz"
                ],
                confidence=0.95
            )
            fixes.append(fix)

        # Too narrow
        elif stereo.width_category in ['mono', 'narrow']:
            fix = Fix(
                id="too_narrow",
                title="Stereo image too narrow",
                description=f"Correlation {stereo.correlation:.2f} ({stereo.width_category})",
                category=FixCategory.STEREO,
                severity=FixSeverity.SUGGESTION,
                issue_source="stereo_analyzer",
                requires_device="Utility",
                manual_steps=[
                    "Add Utility to pads/synths, set Width to 120-140%",
                    "Pan elements for separation",
                    "Add stereo reverb/delay to create space"
                ],
                confidence=0.7
            )
            fixes.append(fix)

        # Check mono compatibility
        if not stereo.is_mono_compatible and stereo.phase_safe:
            fix = Fix(
                id="mono_compatibility",
                title="Mono compatibility concerns",
                description=f"Some elements may not translate to mono playback",
                category=FixCategory.STEREO,
                severity=FixSeverity.WARNING,
                issue_source="stereo_analyzer",
                requires_device="Utility",
                manual_steps=[
                    "Use Utility with 'Bass Mono' on bass/kick",
                    "Check mix in mono regularly",
                    "Reduce extreme stereo widening"
                ],
                confidence=0.7
            )
            fixes.append(fix)

        return fixes

    def _process_loudness(self, result) -> List[Fix]:
        """Generate fixes for loudness issues."""
        fixes = []
        loudness = result.loudness

        # Too quiet for streaming
        if loudness.spotify_diff_db < -4:
            fix = Fix(
                id="too_quiet_streaming",
                title="Too quiet for streaming platforms",
                description=f"{loudness.integrated_lufs:.1f} LUFS ({abs(loudness.spotify_diff_db):.1f}dB below -14 LUFS target)",
                category=FixCategory.MASTERING,
                severity=FixSeverity.WARNING if loudness.spotify_diff_db > -8 else FixSeverity.SUGGESTION,
                issue_source="loudness_analyzer",
                manual_steps=[
                    f"Increase overall loudness by ~{abs(loudness.spotify_diff_db):.0f}dB",
                    "Use limiter to bring up level",
                    "Target -14 LUFS for Spotify/YouTube"
                ],
                confidence=0.85
            )
            fixes.append(fix)

        # Too loud (over-limited)
        elif loudness.spotify_diff_db > 3:
            fix = Fix(
                id="too_loud_streaming",
                title="Louder than streaming target",
                description=f"{loudness.integrated_lufs:.1f} LUFS - platforms will turn it down anyway",
                category=FixCategory.MASTERING,
                severity=FixSeverity.SUGGESTION,
                issue_source="loudness_analyzer",
                manual_steps=[
                    "Consider reducing limiter intensity",
                    "You may be sacrificing dynamics unnecessarily",
                    "Spotify normalizes to -14 LUFS"
                ],
                confidence=0.7
            )
            fixes.append(fix)

        # True peak too high
        if loudness.true_peak_db > -0.5:
            fix = Fix(
                id="true_peak_high",
                title="True peak may clip after encoding",
                description=f"True peak {loudness.true_peak_db:.1f}dB (target: -1.0dB or lower)",
                category=FixCategory.MASTERING,
                severity=FixSeverity.WARNING,
                issue_source="loudness_analyzer",
                actions=[
                    FixAction(
                        target=ParameterTarget(track_name="Master"),
                        action="adjust",
                        value=loudness.true_peak_db + 1.5,  # Reduce to -1.5dB
                        unit="dB",
                        description="Reduce master to ensure -1dB true peak"
                    )
                ],
                confidence=0.8
            )
            fixes.append(fix)

        return fixes

    def _process_transients(self, result) -> List[Fix]:
        """Generate fixes for transient/punch issues."""
        fixes = []

        if result.transients is None:
            return fixes

        transients = result.transients

        if transients.attack_quality == 'soft':
            fix = Fix(
                id="weak_transients",
                title="Weak transients - drums lack punch",
                description=f"Transient strength {transients.avg_transient_strength:.2f} (target: >0.5)",
                category=FixCategory.DYNAMICS,
                severity=FixSeverity.SUGGESTION,
                issue_source="transient_analyzer",
                requires_device="Drum Buss",
                manual_steps=[
                    "Add Drum Buss to drum group",
                    "Increase 'Transients' knob",
                    "Or use transient shaper plugin",
                    "Consider parallel compression"
                ],
                confidence=0.65
            )
            fixes.append(fix)

        return fixes

    def summarize_fixes(self, fixes: List[Fix]) -> str:
        """Generate a text summary of fixes."""
        if not fixes:
            return "No issues detected - mix looks good!"

        lines = [f"Found {len(fixes)} issues:\n"]

        critical = [f for f in fixes if f.severity == FixSeverity.CRITICAL]
        warnings = [f for f in fixes if f.severity == FixSeverity.WARNING]
        suggestions = [f for f in fixes if f.severity == FixSeverity.SUGGESTION]

        if critical:
            lines.append("🔴 CRITICAL:")
            for f in critical:
                lines.append(f"  • {f.title}")

        if warnings:
            lines.append("\n🟡 WARNINGS:")
            for f in warnings:
                lines.append(f"  • {f.title}")

        if suggestions:
            lines.append("\n🟢 SUGGESTIONS:")
            for f in suggestions:
                lines.append(f"  • {f.title}")

        auto_count = len([f for f in fixes if f.is_automatable])
        if auto_count:
            lines.append(f"\n{auto_count} fix(es) can be applied automatically.")

        return "\n".join(lines)


def generate_fixes_for_analysis(analysis_result) -> Tuple[List[Fix], str]:
    """
    Convenience function to generate fixes and summary.

    Returns:
        Tuple of (fixes list, summary string)
    """
    generator = FixGenerator()
    fixes = generator.generate_fixes(analysis_result)
    summary = generator.summarize_fixes(fixes)
    return fixes, summary
