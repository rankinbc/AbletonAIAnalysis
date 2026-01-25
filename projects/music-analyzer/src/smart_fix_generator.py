"""
Smart Fix Generator

Analyzes stems, maps them to Ableton tracks, and generates targeted fixes
that can actually be applied - including recommendations to REMOVE effects.

Key features:
- Stem-by-stem analysis to find per-track issues
- Matches stem filenames to Ableton track names
- Finds existing devices on tracks that can address issues
- Recommends enabling/disabling/removing effects
- Generates precise parameter changes
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from enum import Enum


class FixAction(Enum):
    """Types of fix actions."""
    ADJUST_PARAM = "adjust_parameter"      # Change an existing parameter
    ENABLE_DEVICE = "enable_device"        # Turn on a disabled device
    DISABLE_DEVICE = "disable_device"      # Turn off a device (remove its effect)
    BYPASS_DEVICE = "bypass_device"        # Suggest bypassing (A/B test)
    TRACK_VOLUME = "track_volume"          # Adjust track volume
    TRACK_PAN = "track_pan"                # Adjust track pan
    MANUAL_REQUIRED = "manual"             # Can't be automated


@dataclass
class SmartFix:
    """A targeted fix for a specific track and device."""
    id: str
    track_name: str
    track_index: int
    device_name: Optional[str]
    device_index: Optional[int]

    action: FixAction
    parameter_name: Optional[str] = None
    parameter_index: Optional[int] = None
    current_value: Optional[float] = None
    target_value: Optional[float] = None

    severity: str = "warning"  # critical, warning, suggestion
    title: str = ""
    description: str = ""
    reason: str = ""           # Why we recommend this
    manual_steps: List[str] = field(default_factory=list)

    # For comparison
    analysis_value: Optional[float] = None
    target_range: Optional[Tuple[float, float]] = None

    @property
    def is_automatable(self) -> bool:
        return self.action not in [FixAction.MANUAL_REQUIRED]

    def to_bridge_change(self):
        """Convert to ableton_bridge change format."""
        if self.action == FixAction.ADJUST_PARAM and self.parameter_index is not None:
            from ableton_bridge import ParameterChange
            return ParameterChange(
                track_index=self.track_index,
                device_index=self.device_index,
                parameter_index=self.parameter_index,
                new_value=self.target_value,
                description=self.title
            )
        elif self.action == FixAction.TRACK_VOLUME:
            from ableton_bridge import TrackChange
            return TrackChange(
                track_index=self.track_index,
                change_type='volume',
                new_value=self.target_value,
                description=self.title
            )
        elif self.action in [FixAction.ENABLE_DEVICE, FixAction.DISABLE_DEVICE]:
            from ableton_bridge import ParameterChange
            # Device On is typically parameter 0
            return ParameterChange(
                track_index=self.track_index,
                device_index=self.device_index,
                parameter_index=0,  # "Device On" parameter
                new_value=1.0 if self.action == FixAction.ENABLE_DEVICE else 0.0,
                description=self.title
            )
        return None


@dataclass
class StemAnalysis:
    """Analysis results for a single stem."""
    filename: str
    track_name: str  # Matched Ableton track name
    track_index: int  # Matched track index

    # Issues found
    issues: List[Dict] = field(default_factory=list)

    # Raw analysis data
    loudness_lufs: float = 0
    crest_factor_db: float = 0
    bass_energy_pct: float = 0
    low_mid_energy_pct: float = 0
    high_energy_pct: float = 0
    stereo_correlation: float = 1.0
    stereo_width_pct: float = 0


@dataclass
class SessionAnalysis:
    """Complete analysis of session with stems mapped to tracks."""
    stems: List[StemAnalysis]
    unmapped_stems: List[str]  # Stems that couldn't match to tracks
    track_device_map: Dict[int, List[Dict]]  # track_index -> list of devices
    fixes: List[SmartFix] = field(default_factory=list)


class StemTrackMatcher:
    """Matches stem filenames to Ableton track names."""

    # Common stem naming patterns
    STEM_PATTERNS = [
        # Exact patterns
        r'^kick[s]?',
        r'^bass',
        r'^sub',
        r'^lead[s]?',
        r'^pad[s]?',
        r'^synth[s]?',
        r'^vocal[s]?',
        r'^vox',
        r'^drum[s]?',
        r'^perc',
        r'^hat[s]?',
        r'^hihat[s]?',
        r'^snare[s]?',
        r'^clap[s]?',
        r'^fx',
        r'^atmo',
        r'^string[s]?',
        r'^piano',
        r'^guitar',
        r'^pluck[s]?',
        r'^arp',
    ]

    def __init__(self):
        pass

    def match_stems_to_tracks(
        self,
        stem_files: List[str],
        track_names: List[str]
    ) -> Dict[str, Tuple[str, int]]:
        """
        Match stem filenames to Ableton track names.

        Returns:
            Dict mapping stem filename -> (track_name, track_index)
        """
        matches = {}

        for stem_file in stem_files:
            stem_name = self._clean_stem_name(stem_file)
            best_match = self._find_best_match(stem_name, track_names)
            if best_match:
                track_name, track_index = best_match
                matches[stem_file] = (track_name, track_index)

        return matches

    def _clean_stem_name(self, filename: str) -> str:
        """Extract clean stem name from filename."""
        # Remove extension
        name = Path(filename).stem

        # Remove common prefixes like "01_", "Track_", etc.
        name = re.sub(r'^[\d]+[_\-\s]*', '', name)
        name = re.sub(r'^track[_\-\s]*', '', name, flags=re.IGNORECASE)

        # Remove common suffixes like "_stem", "_export", etc.
        name = re.sub(r'[_\-\s]*(stem|export|bounce|audio|final)$', '', name, flags=re.IGNORECASE)

        return name.lower().strip()

    def _find_best_match(
        self,
        stem_name: str,
        track_names: List[str]
    ) -> Optional[Tuple[str, int]]:
        """Find the best matching track for a stem name."""
        stem_lower = stem_name.lower()

        # Score each track
        best_score = 0
        best_match = None

        for i, track_name in enumerate(track_names):
            track_lower = track_name.lower()

            # Clean track name (remove number prefix if present)
            track_clean = re.sub(r'^[\d]+[_\-\s]*', '', track_lower)

            score = self._calculate_match_score(stem_lower, track_clean)

            if score > best_score:
                best_score = score
                best_match = (track_name, i)

        # Only return if score is above threshold
        if best_score >= 0.5:
            return best_match

        return None

    def _calculate_match_score(self, stem: str, track: str) -> float:
        """Calculate match score between stem and track names."""
        # Exact match
        if stem == track:
            return 1.0

        # One contains the other
        if stem in track:
            return 0.9
        if track in stem:
            return 0.85

        # Check for common instrument keywords
        stem_keywords = self._extract_keywords(stem)
        track_keywords = self._extract_keywords(track)

        if stem_keywords and track_keywords:
            common = stem_keywords.intersection(track_keywords)
            if common:
                return 0.7 + (0.2 * len(common) / max(len(stem_keywords), len(track_keywords)))

        # Fuzzy match - check if significant portion of characters match
        common_chars = set(stem).intersection(set(track))
        if len(common_chars) > 3:
            return 0.3 * len(common_chars) / max(len(stem), len(track))

        return 0

    def _extract_keywords(self, name: str) -> set:
        """Extract instrument/element keywords from a name."""
        keywords = set()
        patterns = {
            'kick': ['kick', 'bd', 'bassdrum'],
            'bass': ['bass', 'sub', 'low'],
            'snare': ['snare', 'sd', 'clap'],
            'hihat': ['hat', 'hihat', 'hh', 'cymbal'],
            'lead': ['lead', 'melody', 'main'],
            'pad': ['pad', 'atmosphere', 'atmo', 'ambient'],
            'synth': ['synth', 'synths'],
            'vocal': ['vocal', 'vox', 'voice'],
            'drums': ['drum', 'drums', 'perc', 'percussion'],
            'fx': ['fx', 'effect', 'riser', 'impact'],
            'arp': ['arp', 'arpegg'],
            'pluck': ['pluck'],
            'string': ['string', 'strings'],
        }

        for keyword, aliases in patterns.items():
            for alias in aliases:
                if alias in name:
                    keywords.add(keyword)

        return keywords


class SmartFixGenerator:
    """
    Generates targeted fixes by analyzing stems and mapping to Ableton session.

    Usage:
        generator = SmartFixGenerator()

        # Analyze stems and session
        analysis = generator.analyze_session(
            stems_dir="path/to/stems/",
            bridge=connected_ableton_bridge
        )

        # Get fixes
        for fix in analysis.fixes:
            print(fix.title)
            if fix.is_automatable:
                bridge.apply_fix(fix)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.matcher = StemTrackMatcher()
        self._audio_analyzer = None
        self._device_finder = None

    def _get_audio_analyzer(self):
        if self._audio_analyzer is None:
            from audio_analyzer import AudioAnalyzer
            self._audio_analyzer = AudioAnalyzer(verbose=False)
        return self._audio_analyzer

    def _get_device_finder(self):
        if self._device_finder is None:
            from ableton_devices import DeviceFinder
            self._device_finder = DeviceFinder()
        return self._device_finder

    def analyze_session(
        self,
        stems_dir: str,
        bridge,  # AbletonBridge instance
        reference_profile=None
    ) -> SessionAnalysis:
        """
        Analyze stems and map to Ableton session.

        Args:
            stems_dir: Directory containing stem audio files
            bridge: Connected AbletonBridge instance
            reference_profile: Optional ReferenceProfile for comparison

        Returns:
            SessionAnalysis with all findings and fixes
        """
        # Get session state from Ableton
        session_state = bridge.read_session_state(include_devices=True)
        if not session_state:
            raise RuntimeError("Could not read Ableton session state")

        # Get track names
        track_names = [t.name for t in session_state.tracks]

        # Find stem files
        stems_dir = Path(stems_dir)
        stem_files = list(stems_dir.glob("*.wav")) + list(stems_dir.glob("*.flac"))
        stem_filenames = [f.name for f in stem_files]

        if self.verbose:
            print(f"Found {len(stem_files)} stems")
            print(f"Found {len(track_names)} Ableton tracks")

        # Match stems to tracks
        matches = self.matcher.match_stems_to_tracks(stem_filenames, track_names)

        if self.verbose:
            print(f"Matched {len(matches)} stems to tracks")

        # Analyze each stem
        stem_analyses = []
        unmapped = []

        for stem_file in stem_files:
            if stem_file.name in matches:
                track_name, track_index = matches[stem_file.name]

                # Analyze the stem
                analysis = self._analyze_stem(
                    stem_file,
                    track_name,
                    track_index,
                    reference_profile
                )
                stem_analyses.append(analysis)
            else:
                unmapped.append(stem_file.name)

        # Build track -> devices map
        track_device_map = {}
        for track in session_state.tracks:
            devices = []
            for device in track.devices:
                devices.append({
                    'name': device.name,
                    'class_name': device.class_name,
                    'is_enabled': device.is_enabled,
                    'index': device.device_index,
                    'parameters': device.parameters
                })
            track_device_map[track.index] = devices

        # Generate fixes
        fixes = self._generate_fixes(stem_analyses, track_device_map, session_state)

        return SessionAnalysis(
            stems=stem_analyses,
            unmapped_stems=unmapped,
            track_device_map=track_device_map,
            fixes=fixes
        )

    def _analyze_stem(
        self,
        stem_path: Path,
        track_name: str,
        track_index: int,
        reference_profile
    ) -> StemAnalysis:
        """Analyze a single stem file."""
        analyzer = self._get_audio_analyzer()
        result = analyzer.analyze(str(stem_path))

        # Build issues list
        issues = []

        # Check for stem-specific issues
        stem_type = self._classify_stem_type(track_name)

        # Issue: Bass stem with excessive low-mid mud
        if stem_type == 'bass' and result.frequency.low_mid_energy > 20:
            issues.append({
                'type': 'low_mid_buildup',
                'severity': 'warning',
                'value': result.frequency.low_mid_energy,
                'message': f"Muddy low-mids ({result.frequency.low_mid_energy:.1f}%)"
            })

        # Issue: Kick with weak sub
        if stem_type == 'kick' and result.frequency.sub_bass_energy < 10:
            issues.append({
                'type': 'weak_sub',
                'severity': 'suggestion',
                'value': result.frequency.sub_bass_energy,
                'message': f"Weak sub bass ({result.frequency.sub_bass_energy:.1f}%)"
            })

        # Issue: Lead/synth competing in vocal range
        if stem_type in ['lead', 'synth'] and result.frequency.high_mid_energy > 35:
            issues.append({
                'type': 'harsh_presence',
                'severity': 'warning',
                'value': result.frequency.high_mid_energy,
                'message': f"Harsh presence range ({result.frequency.high_mid_energy:.1f}%)"
            })

        # Issue: Pad/atmosphere too wide (may cause phase issues)
        if stem_type in ['pad', 'atmosphere'] and result.stereo.correlation < 0.3:
            issues.append({
                'type': 'too_wide',
                'severity': 'warning',
                'value': result.stereo.correlation,
                'message': f"Very wide stereo (corr: {result.stereo.correlation:.2f})"
            })

        # Issue: Any stem with phase problems
        if result.stereo.is_stereo and result.stereo.correlation < 0:
            issues.append({
                'type': 'phase_issue',
                'severity': 'critical',
                'value': result.stereo.correlation,
                'message': f"Phase cancellation (corr: {result.stereo.correlation:.2f})"
            })

        # Issue: Over-compressed stem
        if result.dynamics.crest_factor_db < 6:
            issues.append({
                'type': 'over_compressed',
                'severity': 'warning',
                'value': result.dynamics.crest_factor_db,
                'message': f"Over-compressed ({result.dynamics.crest_factor_db:.1f}dB crest)"
            })

        # Issue: Excessively loud stem
        if result.loudness.integrated_lufs > -8:
            issues.append({
                'type': 'too_loud',
                'severity': 'warning',
                'value': result.loudness.integrated_lufs,
                'message': f"Very loud stem ({result.loudness.integrated_lufs:.1f} LUFS)"
            })

        return StemAnalysis(
            filename=stem_path.name,
            track_name=track_name,
            track_index=track_index,
            issues=issues,
            loudness_lufs=result.loudness.integrated_lufs,
            crest_factor_db=result.dynamics.crest_factor_db,
            bass_energy_pct=result.frequency.bass_energy + result.frequency.sub_bass_energy,
            low_mid_energy_pct=result.frequency.low_mid_energy,
            high_energy_pct=result.frequency.high_energy + result.frequency.air_energy,
            stereo_correlation=result.stereo.correlation,
            stereo_width_pct=result.stereo.width_estimate
        )

    def _classify_stem_type(self, track_name: str) -> str:
        """Classify what type of stem this is based on track name."""
        name_lower = track_name.lower()

        if any(k in name_lower for k in ['kick', 'bd']):
            return 'kick'
        if any(k in name_lower for k in ['bass', 'sub']):
            return 'bass'
        if any(k in name_lower for k in ['snare', 'clap', 'sd']):
            return 'snare'
        if any(k in name_lower for k in ['hat', 'hihat', 'hh']):
            return 'hihat'
        if any(k in name_lower for k in ['lead', 'melody']):
            return 'lead'
        if any(k in name_lower for k in ['pad', 'atmo', 'ambient']):
            return 'pad'
        if any(k in name_lower for k in ['synth']):
            return 'synth'
        if any(k in name_lower for k in ['vocal', 'vox']):
            return 'vocal'
        if any(k in name_lower for k in ['drum', 'perc']):
            return 'drums'
        if any(k in name_lower for k in ['fx', 'riser', 'impact']):
            return 'fx'

        return 'other'

    def _generate_fixes(
        self,
        stem_analyses: List[StemAnalysis],
        track_device_map: Dict[int, List[Dict]],
        session_state
    ) -> List[SmartFix]:
        """Generate targeted fixes based on stem analysis and available devices."""
        fixes = []
        device_finder = self._get_device_finder()

        for stem in stem_analyses:
            track_devices = track_device_map.get(stem.track_index, [])

            for issue in stem.issues:
                fix = self._create_fix_for_issue(
                    stem, issue, track_devices, device_finder
                )
                if fix:
                    fixes.append(fix)

            # Check for device-related issues (too many effects, etc.)
            device_fixes = self._check_device_issues(stem, track_devices, device_finder)
            fixes.extend(device_fixes)

        # Sort by severity
        severity_order = {'critical': 0, 'warning': 1, 'suggestion': 2}
        fixes.sort(key=lambda f: severity_order.get(f.severity, 3))

        return fixes

    def _create_fix_for_issue(
        self,
        stem: StemAnalysis,
        issue: Dict,
        track_devices: List[Dict],
        device_finder
    ) -> Optional[SmartFix]:
        """Create a fix for a specific issue on a track."""
        issue_type = issue['type']

        # Find relevant devices
        eq_devices = device_finder.get_eq_devices_on_track(track_devices)
        utility = device_finder.get_utility_on_track(track_devices)
        compressor = device_finder.get_compressor_on_track(track_devices)

        # LOW-MID BUILDUP -> EQ cut at 300Hz
        if issue_type == 'low_mid_buildup':
            if eq_devices:
                device_idx, template = eq_devices[0]
                from ableton_devices import freq_to_eq_param, gain_db_to_eq_param

                return SmartFix(
                    id=f"{stem.track_name}_lowmid_cut",
                    track_name=stem.track_name,
                    track_index=stem.track_index,
                    device_name=track_devices[device_idx]['name'],
                    device_index=device_idx,
                    action=FixAction.ADJUST_PARAM,
                    parameter_name="2 Gain" if "EQ Eight" in template.name else "GainMid",
                    parameter_index=9 if "EQ Eight" in template.name else 5,
                    target_value=gain_db_to_eq_param(-3.5),  # -3.5dB cut
                    severity=issue['severity'],
                    title=f"Cut low-mids on {stem.track_name}",
                    description=f"Reduce muddiness by cutting 300Hz by 3-4dB",
                    reason=issue['message']
                )
            else:
                return SmartFix(
                    id=f"{stem.track_name}_lowmid_cut",
                    track_name=stem.track_name,
                    track_index=stem.track_index,
                    device_name=None,
                    device_index=None,
                    action=FixAction.MANUAL_REQUIRED,
                    severity=issue['severity'],
                    title=f"Cut low-mids on {stem.track_name}",
                    description="Add EQ and cut 300Hz by 3-4dB",
                    reason=issue['message'],
                    manual_steps=[
                        "Add EQ Eight to track",
                        "Enable Band 2",
                        "Set frequency to 300Hz",
                        "Cut gain by 3-4dB",
                        "Q around 1.0"
                    ]
                )

        # HARSH PRESENCE -> EQ cut at 3-5kHz
        if issue_type == 'harsh_presence':
            if eq_devices:
                device_idx, template = eq_devices[0]
                from ableton_devices import gain_db_to_eq_param

                return SmartFix(
                    id=f"{stem.track_name}_presence_cut",
                    track_name=stem.track_name,
                    track_index=stem.track_index,
                    device_name=track_devices[device_idx]['name'],
                    device_index=device_idx,
                    action=FixAction.ADJUST_PARAM,
                    parameter_name="4 Gain" if "EQ Eight" in template.name else "GainHi",
                    parameter_index=19 if "EQ Eight" in template.name else 6,
                    target_value=gain_db_to_eq_param(-2.5),  # -2.5dB cut
                    severity=issue['severity'],
                    title=f"Tame harshness on {stem.track_name}",
                    description=f"Cut 3-5kHz by 2-3dB to reduce harshness",
                    reason=issue['message']
                )

        # TOO WIDE -> Utility width reduction
        if issue_type == 'too_wide':
            if utility:
                device_idx, template = utility
                from ableton_devices import width_pct_to_utility_param

                return SmartFix(
                    id=f"{stem.track_name}_width_reduce",
                    track_name=stem.track_name,
                    track_index=stem.track_index,
                    device_name=track_devices[device_idx]['name'],
                    device_index=device_idx,
                    action=FixAction.ADJUST_PARAM,
                    parameter_name="Stereo Width",
                    parameter_index=5,
                    target_value=width_pct_to_utility_param(80),  # Reduce to 80%
                    severity=issue['severity'],
                    title=f"Reduce width on {stem.track_name}",
                    description="Reduce stereo width to improve mono compatibility",
                    reason=issue['message']
                )

        # PHASE ISSUE -> Check for stereo wideners to disable
        if issue_type == 'phase_issue':
            # Look for likely culprits: Utility with wide setting, stereo effects
            for i, device in enumerate(track_devices):
                device_name_lower = device['name'].lower()
                if any(w in device_name_lower for w in ['wider', 'dimension', 'stereo', 'spread', 'haas']):
                    return SmartFix(
                        id=f"{stem.track_name}_disable_widener",
                        track_name=stem.track_name,
                        track_index=stem.track_index,
                        device_name=device['name'],
                        device_index=i,
                        action=FixAction.DISABLE_DEVICE,
                        severity='critical',
                        title=f"DISABLE {device['name']} on {stem.track_name}",
                        description="This stereo widener is causing phase cancellation",
                        reason=issue['message']
                    )

        # OVER-COMPRESSED -> Check for compressor to adjust or disable
        if issue_type == 'over_compressed':
            if compressor:
                device_idx, template = compressor
                return SmartFix(
                    id=f"{stem.track_name}_comp_reduce",
                    track_name=stem.track_name,
                    track_index=stem.track_index,
                    device_name=track_devices[device_idx]['name'],
                    device_index=device_idx,
                    action=FixAction.BYPASS_DEVICE,
                    severity=issue['severity'],
                    title=f"Try bypassing compressor on {stem.track_name}",
                    description="Track may be over-compressed - try A/B testing without compressor",
                    reason=issue['message'],
                    manual_steps=[
                        f"Try disabling {track_devices[device_idx]['name']}",
                        "Compare with and without",
                        "If better without, remove or reduce compression"
                    ]
                )

        # TOO LOUD -> Track volume reduction
        if issue_type == 'too_loud':
            return SmartFix(
                id=f"{stem.track_name}_volume_reduce",
                track_name=stem.track_name,
                track_index=stem.track_index,
                device_name=None,
                device_index=None,
                action=FixAction.TRACK_VOLUME,
                target_value=0.7,  # Reduce by ~3dB
                severity=issue['severity'],
                title=f"Reduce volume on {stem.track_name}",
                description=f"Track is very loud ({issue['value']:.1f} LUFS) - reduce by 3-6dB",
                reason=issue['message']
            )

        return None

    def _check_device_issues(
        self,
        stem: StemAnalysis,
        track_devices: List[Dict],
        device_finder
    ) -> List[SmartFix]:
        """Check for device-related issues like over-processing."""
        fixes = []

        # Count effect types
        eq_count = len([d for d in track_devices if 'eq' in d['name'].lower()])
        comp_count = len([d for d in track_devices
                         if any(c in d['name'].lower() for c in ['compress', 'limit', 'glue'])])
        saturator_count = len([d for d in track_devices
                              if any(s in d['name'].lower() for s in ['saturator', 'distort', 'overdrive'])])

        # Too many EQs
        if eq_count > 2:
            fixes.append(SmartFix(
                id=f"{stem.track_name}_too_many_eq",
                track_name=stem.track_name,
                track_index=stem.track_index,
                device_name=None,
                device_index=None,
                action=FixAction.MANUAL_REQUIRED,
                severity='suggestion',
                title=f"Consider consolidating EQs on {stem.track_name}",
                description=f"Track has {eq_count} EQs - consider merging into one",
                reason="Multiple EQs can cause phase issues and make mixing harder",
                manual_steps=[
                    "Review each EQ's purpose",
                    "Combine curves into a single EQ Eight",
                    "Remove redundant EQs"
                ]
            ))

        # Too much compression (multiple compressors)
        if comp_count > 2:
            fixes.append(SmartFix(
                id=f"{stem.track_name}_too_many_comp",
                track_name=stem.track_name,
                track_index=stem.track_index,
                device_name=None,
                device_index=None,
                action=FixAction.MANUAL_REQUIRED,
                severity='warning',
                title=f"Excessive compression on {stem.track_name}",
                description=f"Track has {comp_count} compressors - likely over-compressed",
                reason="Stacking compressors often reduces dynamics and punch",
                manual_steps=[
                    "Disable all but one compressor",
                    "A/B test the difference",
                    "Keep only the compression that improves the sound"
                ]
            ))

        # Too much saturation
        if saturator_count > 1:
            fixes.append(SmartFix(
                id=f"{stem.track_name}_too_many_sat",
                track_name=stem.track_name,
                track_index=stem.track_index,
                device_name=None,
                device_index=None,
                action=FixAction.MANUAL_REQUIRED,
                severity='suggestion',
                title=f"Multiple saturators on {stem.track_name}",
                description=f"Track has {saturator_count} saturation effects",
                reason="Stacking saturation can cause harshness and loss of clarity",
                manual_steps=[
                    "Disable extra saturators",
                    "Compare the sound",
                    "Keep saturation subtle"
                ]
            ))

        return fixes


def analyze_and_fix(
    stems_dir: str,
    max_fixes: int = None
) -> Tuple[SessionAnalysis, str]:
    """
    Convenience function: Connect to Ableton, analyze stems, generate fixes.

    Returns:
        Tuple of (SessionAnalysis, summary_string)
    """
    from ableton_bridge import quick_connect

    # Connect to Ableton
    bridge = quick_connect()
    if not bridge:
        raise RuntimeError("Could not connect to Ableton. Is it running with AbletonOSC enabled?")

    # Analyze
    generator = SmartFixGenerator(verbose=True)
    analysis = generator.analyze_session(stems_dir, bridge)

    # Limit fixes if requested
    if max_fixes and max_fixes > 0:
        analysis.fixes = analysis.fixes[:max_fixes]

    # Build summary
    lines = [
        f"\nAnalyzed {len(analysis.stems)} stems",
        f"Matched to Ableton tracks: {len(analysis.stems)}",
        f"Unmatched: {len(analysis.unmapped_stems)}",
        f"\nGenerated {len(analysis.fixes)} fixes:"
    ]

    for fix in analysis.fixes:
        auto = "[AUTO]" if fix.is_automatable else "[MANUAL]"
        lines.append(f"  {auto} {fix.title}")

    summary = "\n".join(lines)
    return analysis, summary
