"""
Report Generator Module

Generates comprehensive analysis reports in various formats:
- Plain text reports
- HTML reports with visualizations
- JSON data export
"""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import asdict, is_dataclass
from typing import Optional, Dict, Any, List
import numpy as np

try:
    from .audio_analyzer import AnalysisResult, SectionAnalysisResult, SectionInfo, TimestampedIssue, TransientInfo
    from .stem_analyzer import StemAnalysisResult
    from .als_parser import ALSProject
    from .mastering import MasteringResult
    from .reference_comparator import ComparisonResult
except ImportError:
    from audio_analyzer import AnalysisResult, SectionAnalysisResult, SectionInfo, TimestampedIssue, TransientInfo
    from stem_analyzer import StemAnalysisResult
    from als_parser import ALSProject
    from mastering import MasteringResult
    from reference_comparator import ComparisonResult


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


def _serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert dataclasses and special types to JSON-serializable format.

    Handles:
    - Dataclasses -> dicts
    - Tuples -> lists
    - numpy types -> Python types
    - NaN/Inf floats -> null/strings
    - Nested structures
    """
    if obj is None:
        return None
    elif is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize_for_json(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, dict):
        return {str(k): _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, np.ndarray):
        return _serialize_for_json(obj.tolist())
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        val = float(obj)
        if np.isnan(val):
            return None
        elif np.isinf(val):
            return "Infinity" if val > 0 else "-Infinity"
        return round(val, 4)
    elif isinstance(obj, float):
        if obj != obj:  # NaN check
            return None
        elif obj == float('inf'):
            return "Infinity"
        elif obj == float('-inf'):
            return "-Infinity"
        return round(obj, 4)
    elif isinstance(obj, Path):
        return str(obj)
    else:
        return obj


class ReportGenerator:
    """Generates analysis reports in multiple formats."""

    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _format_time(self, seconds: float) -> str:
        """Format seconds as M:SS or H:MM:SS."""
        if seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}:{secs:02d}"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours}:{mins:02d}:{secs:02d}"

    def _generate_json_data(
        self,
        audio_analysis: Optional[AnalysisResult] = None,
        stem_analysis: Optional[StemAnalysisResult] = None,
        als_project: Optional[ALSProject] = None,
        mastering_result: Optional[MasteringResult] = None,
        section_analysis: Optional[SectionAnalysisResult] = None,
        comparison_result: Optional[ComparisonResult] = None,
        project_name: str = "analysis",
        version: str = "v1"
    ) -> dict:
        """
        Generate comprehensive JSON data from all analysis results.

        This captures ALL metrics from every analysis module for complete
        data preservation and reusability.
        """
        data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "analyzer_version": "1.0.0",
                "project_name": project_name,
                "version": version
            }
        }

        # Serialize each analysis type (if present)
        if als_project:
            data["als_project"] = _serialize_for_json(als_project)

        if audio_analysis:
            data["audio_analysis"] = _serialize_for_json(audio_analysis)

        if stem_analysis:
            data["stem_analysis"] = _serialize_for_json(stem_analysis)

        if section_analysis:
            data["section_analysis"] = _serialize_for_json(section_analysis)

        if comparison_result:
            data["comparison_result"] = _serialize_for_json(comparison_result)

        if mastering_result:
            data["mastering_result"] = _serialize_for_json(mastering_result)

        # Build summary with aggregated issues and recommendations
        data["summary"] = self._build_json_summary(
            audio_analysis, stem_analysis, als_project,
            section_analysis, comparison_result
        )

        return data

    def _build_json_summary(
        self,
        audio_analysis: Optional[AnalysisResult] = None,
        stem_analysis: Optional[StemAnalysisResult] = None,
        als_project: Optional[ALSProject] = None,
        section_analysis: Optional[SectionAnalysisResult] = None,
        comparison_result: Optional[ComparisonResult] = None
    ) -> dict:
        """Build aggregated summary of all issues and recommendations."""
        summary = {
            "critical_issues": [],
            "warnings": [],
            "info": [],
            "recommendations": [],
            "stats": {}
        }

        # Aggregate from audio analysis
        if audio_analysis:
            for issue in audio_analysis.overall_issues:
                severity = issue.get('severity', 'info')
                item = {"source": "audio", "message": issue.get('message', '')}
                if severity == 'critical':
                    summary["critical_issues"].append(item)
                elif severity == 'warning':
                    summary["warnings"].append(item)
                else:
                    summary["info"].append(item)

            summary["recommendations"].extend([
                {"source": "audio", "text": r} for r in audio_analysis.recommendations
            ])

            summary["stats"]["duration_seconds"] = audio_analysis.duration_seconds
            summary["stats"]["detected_tempo"] = audio_analysis.detected_tempo

        # Aggregate from stem analysis
        if stem_analysis:
            severe_clashes = [c for c in stem_analysis.clashes if c.severity == 'severe']
            moderate_clashes = [c for c in stem_analysis.clashes if c.severity == 'moderate']

            for clash in severe_clashes:
                summary["critical_issues"].append({
                    "source": "stems",
                    "message": f"Severe frequency clash: {clash.stem1} vs {clash.stem2} ({clash.frequency_range[0]:.0f}-{clash.frequency_range[1]:.0f}Hz)"
                })

            for clash in moderate_clashes:
                summary["warnings"].append({
                    "source": "stems",
                    "message": f"Frequency clash: {clash.stem1} vs {clash.stem2} ({clash.frequency_range[0]:.0f}-{clash.frequency_range[1]:.0f}Hz)"
                })

            summary["recommendations"].extend([
                {"source": "stems", "text": r} for r in stem_analysis.recommendations
            ])

            summary["stats"]["stem_count"] = len(stem_analysis.stems)
            summary["stats"]["clash_count"] = len(stem_analysis.clashes)
            summary["stats"]["severe_clash_count"] = len(severe_clashes)

        # Aggregate from ALS project
        if als_project:
            # Robotic MIDI warnings
            if als_project.midi_analysis:
                robotic_tracks = [
                    name for name, a in als_project.midi_analysis.items()
                    if a.humanization_score == 'robotic'
                ]
                for track in robotic_tracks:
                    summary["warnings"].append({
                        "source": "midi",
                        "message": f"Track '{track}' has robotic velocity (no humanization)"
                    })

                # Severe quantization errors
                for name, analysis in als_project.midi_analysis.items():
                    severe_quant = [e for e in analysis.quantization_errors if e.severity == 'severe']
                    if len(severe_quant) > 5:
                        summary["warnings"].append({
                            "source": "midi",
                            "message": f"Track '{name}' has {len(severe_quant)} notes significantly off-grid"
                        })

            summary["stats"]["tempo"] = als_project.tempo
            summary["stats"]["midi_note_count"] = als_project.midi_note_count
            summary["stats"]["track_count"] = len(als_project.tracks)

        # Aggregate from section analysis
        if section_analysis:
            for issue in section_analysis.all_issues:
                severity = issue.severity
                item = {"source": "sections", "message": issue.message}
                if severity == 'severe':
                    summary["critical_issues"].append(item)
                elif severity == 'moderate':
                    summary["warnings"].append(item)
                else:
                    summary["info"].append(item)

        # Aggregate from comparison
        if comparison_result and comparison_result.success:
            summary["recommendations"].extend([
                {"source": "comparison", "text": r}
                for r in comparison_result.priority_recommendations[:5]
            ])

        return summary

    def save_json(
        self,
        json_data: dict,
        output_path: str
    ) -> str:
        """Save JSON data to file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

        return str(path)

    def generate_full_report(
        self,
        audio_analysis: Optional[AnalysisResult] = None,
        stem_analysis: Optional[StemAnalysisResult] = None,
        als_project: Optional[ALSProject] = None,
        mastering_result: Optional[MasteringResult] = None,
        section_analysis: Optional[SectionAnalysisResult] = None,
        comparison_result: Optional[ComparisonResult] = None,
        project_name: str = "analysis",
        output_format: str = "html",
        version: str = "v1"
    ) -> str:
        """
        Generate a comprehensive report combining all analysis results.

        Args:
            audio_analysis: Single audio file analysis result
            stem_analysis: Multi-stem analysis result
            als_project: Parsed ALS project
            mastering_result: Mastering operation result
            section_analysis: Time-based section analysis result
            comparison_result: Reference track comparison result
            project_name: Name for the output file
            output_format: 'html', 'text', or 'json'
            version: Mix version (e.g., 'v1', 'v2')

        Returns:
            Path to the generated report file
        """
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Create song-specific subdirectory: reports/<songtitle>/
        song_dir = self.output_dir / project_name
        song_dir.mkdir(parents=True, exist_ok=True)

        # Filename format: <songtitle>_<version>_analysis_<date>
        filename = f"{project_name}_{version}_analysis_{date_str}"

        # Store original output_dir and temporarily use song_dir
        original_output_dir = self.output_dir
        self.output_dir = song_dir

        try:
            # Always generate comprehensive JSON data
            json_data = self._generate_json_data(
                audio_analysis, stem_analysis, als_project,
                mastering_result, section_analysis, comparison_result,
                project_name, version
            )

            # Always save JSON file alongside other formats
            json_path = song_dir / f"{filename}.json"
            self.save_json(json_data, str(json_path))

            if output_format == "html":
                # Use enhanced HTML generator with all data points
                result = self._generate_html_report(
                    audio_analysis, stem_analysis, als_project,
                    mastering_result, section_analysis, comparison_result, filename
                )
            elif output_format == "json":
                # JSON already saved, just return the path
                result = str(json_path)
            else:
                result = self._generate_text_report(
                    audio_analysis, stem_analysis, als_project,
                    mastering_result, section_analysis, comparison_result, filename
                )
            return result
        finally:
            self.output_dir = original_output_dir

    def _generate_text_report(
        self,
        audio_analysis: Optional[AnalysisResult],
        stem_analysis: Optional[StemAnalysisResult],
        als_project: Optional[ALSProject],
        mastering_result: Optional[MasteringResult],
        section_analysis: Optional[SectionAnalysisResult],
        comparison_result: Optional[ComparisonResult],
        filename: str
    ) -> str:
        """Generate a plain text report."""
        lines = []
        lines.append("=" * 60)
        lines.append("MUSIC PRODUCTION ANALYSIS REPORT")
        lines.append("=" * 60)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # ALS Project Info
        if als_project:
            lines.append("-" * 40)
            lines.append("PROJECT INFORMATION")
            lines.append("-" * 40)
            lines.append(f"File: {Path(als_project.file_path).name}")
            lines.append(f"Ableton Version: {als_project.ableton_version}")
            lines.append(f"Tempo: {als_project.tempo:.1f} BPM")
            lines.append(f"Time Signature: {als_project.time_signature_numerator}/{als_project.time_signature_denominator}")
            lines.append(f"Duration: {als_project.total_duration_seconds / 60:.1f} minutes")
            lines.append(f"Tracks: {len(als_project.tracks)}")
            lines.append(f"MIDI Notes: {als_project.midi_note_count}")
            lines.append(f"Audio Clips: {als_project.audio_clip_count}")
            if als_project.plugin_list:
                lines.append(f"Plugins: {', '.join(als_project.plugin_list[:10])}")
            lines.append("")

        # Audio Analysis
        if audio_analysis:
            lines.append("-" * 40)
            lines.append("MIX ANALYSIS")
            lines.append("-" * 40)
            lines.append(f"File: {Path(audio_analysis.file_path).name}")
            lines.append(f"Duration: {audio_analysis.duration_seconds:.1f} seconds")
            lines.append(f"Sample Rate: {audio_analysis.sample_rate} Hz")
            lines.append(f"Channels: {'Stereo' if audio_analysis.channels == 2 else 'Mono'}")
            if audio_analysis.detected_tempo:
                lines.append(f"Detected Tempo: {audio_analysis.detected_tempo:.1f} BPM")
            lines.append("")

            # Critical Issues
            critical_issues = [i for i in audio_analysis.overall_issues if i.get('severity') == 'critical']
            if critical_issues:
                lines.append("CRITICAL ISSUES:")
                for issue in critical_issues:
                    lines.append(f"  [X] {issue['message']}")
                lines.append("")

            # Warnings
            warnings = [i for i in audio_analysis.overall_issues if i.get('severity') == 'warning']
            if warnings:
                lines.append("WARNINGS:")
                for issue in warnings:
                    lines.append(f"  [!] {issue['message']}")
                lines.append("")

            # Info
            info = [i for i in audio_analysis.overall_issues if i.get('severity') == 'info']
            if info:
                lines.append("INFO:")
                for issue in info:
                    lines.append(f"  [i] {issue['message']}")
                lines.append("")

            # Loudness (LUFS)
            lines.append("LOUDNESS:")
            lines.append(f"  Integrated LUFS: {audio_analysis.loudness.integrated_lufs:.1f}")
            lines.append(f"  True Peak: {audio_analysis.loudness.true_peak_db:.1f} dBTP")
            lines.append(f"  Loudness Range: {audio_analysis.loudness.loudness_range_lu:.1f} LU")
            lines.append("  Streaming Targets:")
            lines.append(f"    Spotify (-14 LUFS): {audio_analysis.loudness.spotify_diff_db:+.1f} dB")
            lines.append(f"    Apple Music (-16 LUFS): {audio_analysis.loudness.apple_music_diff_db:+.1f} dB")
            lines.append(f"    YouTube (-14 LUFS): {audio_analysis.loudness.youtube_diff_db:+.1f} dB")
            lines.append("")

            # Dynamics / Crest Factor
            lines.append("DYNAMICS:")
            lines.append(f"  Peak Level: {audio_analysis.dynamics.peak_db:.1f} dBFS")
            lines.append(f"  RMS Level: {audio_analysis.dynamics.rms_db:.1f} dBFS")
            lines.append(f"  Crest Factor: {audio_analysis.dynamics.crest_factor_db:.1f} dB ({audio_analysis.dynamics.crest_interpretation})")
            lines.append(f"  Dynamic Range: {audio_analysis.dynamics.dynamic_range_db:.1f} dB")
            if audio_analysis.dynamics.recommended_action:
                lines.append(f"  Status: {audio_analysis.dynamics.recommended_action}")
            lines.append("")

            # Stereo / Phase
            lines.append("STEREO/PHASE:")
            if audio_analysis.stereo.is_stereo:
                lines.append(f"  L/R Correlation: {audio_analysis.stereo.correlation:.2f} ({audio_analysis.stereo.width_category})")
                lines.append(f"  Width Estimate: {audio_analysis.stereo.width_estimate:.0f}%")
                lines.append(f"  Phase Safe: {'Yes' if audio_analysis.stereo.phase_safe else 'NO - OUT OF PHASE!'}")
                lines.append(f"  Mono Compatible: {'Yes' if audio_analysis.stereo.is_mono_compatible else 'No'}")
                if audio_analysis.stereo.recommended_width:
                    lines.append(f"  Recommendation: {audio_analysis.stereo.recommended_width}")
            else:
                lines.append("  File is mono - stereo analysis skipped")
            lines.append("")

            # Transients
            if audio_analysis.transients:
                lines.append("TRANSIENTS:")
                lines.append(f"  Count: {audio_analysis.transients.transient_count}")
                lines.append(f"  Density: {audio_analysis.transients.transients_per_second:.1f}/sec")
                lines.append(f"  Avg Strength: {audio_analysis.transients.avg_transient_strength:.2f}")
                lines.append(f"  Peak Strength: {audio_analysis.transients.peak_transient_strength:.2f}")
                lines.append(f"  Attack Quality: {audio_analysis.transients.attack_quality}")
                lines.append(f"  Assessment: {audio_analysis.transients.interpretation}")
                lines.append("")

            # Frequency Balance
            lines.append("FREQUENCY BALANCE:")
            lines.append(f"  Bass (20-250Hz): {audio_analysis.frequency.bass_energy:.1f}%")
            lines.append(f"  Low-Mid (250-500Hz): {audio_analysis.frequency.low_mid_energy:.1f}%")
            lines.append(f"  Mid (500-2kHz): {audio_analysis.frequency.mid_energy:.1f}%")
            lines.append(f"  High-Mid (2-6kHz): {audio_analysis.frequency.high_mid_energy:.1f}%")
            lines.append(f"  High (6-20kHz): {audio_analysis.frequency.high_energy:.1f}%")
            lines.append("")

        # Stem Analysis
        if stem_analysis:
            lines.append("-" * 40)
            lines.append("STEM ANALYSIS")
            lines.append("-" * 40)
            lines.append(f"Stems Analyzed: {len(stem_analysis.stems)}")
            lines.append("")

            # Stem List
            lines.append("STEMS:")
            for stem in stem_analysis.stems:
                pan_str = "C" if abs(stem.panning) < 0.1 else f"{'L' if stem.panning < 0 else 'R'}{abs(stem.panning)*100:.0f}%"
                lines.append(f"  {stem.name}: {stem.rms_db:.1f} dBRMS, Pan: {pan_str}")
            lines.append("")

            # Clashes
            if stem_analysis.clashes:
                lines.append("FREQUENCY CLASHES:")
                for clash in stem_analysis.clashes:
                    severity_marker = {'severe': '[!!!]', 'moderate': '[!!]', 'minor': '[!]'}
                    marker = severity_marker.get(clash.severity, '[!]')
                    lines.append(f"  {marker} {clash.stem1} vs {clash.stem2}")
                    lines.append(f"      Range: {clash.frequency_range[0]:.0f}-{clash.frequency_range[1]:.0f} Hz")
                    lines.append(f"      Fix: {clash.recommendation}")
                lines.append("")

            # Masking Issues
            if stem_analysis.masking_issues:
                lines.append("MASKING ISSUES:")
                for issue in stem_analysis.masking_issues:
                    lines.append(f"  [!] {issue['message']}")
                    lines.append(f"      Fix: {issue['recommendation']}")
                lines.append("")

        # Section/Timeline Analysis
        if section_analysis:
            lines.append("-" * 40)
            lines.append("TIMELINE ANALYSIS")
            lines.append("-" * 40)
            lines.append(f"Sections Detected: {len(section_analysis.sections)}")
            if section_analysis.worst_section:
                lines.append(f"Worst Section: {section_analysis.worst_section}")
            lines.append("")

            lines.append("SECTION BREAKDOWN:")
            for section in section_analysis.sections:
                severity_marker = {
                    'clean': '[OK]',
                    'minor': '[!]',
                    'moderate': '[!!]',
                    'severe': '[!!!]'
                }.get(section.severity_summary, '[?]')

                lines.append(f"  {self._format_time(section.start_time)}-{self._format_time(section.end_time)} ({section.section_type.upper()}):")
                lines.append(f"      {severity_marker} {section.severity_summary.upper()}")
                lines.append(f"      RMS: {section.avg_rms_db:.1f} dB | Peak: {section.peak_db:.1f} dB")

                if section.issues:
                    for issue in section.issues:
                        lines.append(f"      - {issue.message}")
                lines.append("")

            # Clipping timestamps
            if section_analysis.clipping_timestamps:
                lines.append("CLIPPING TIMESTAMPS:")
                clip_times = [self._format_time(t) for t in section_analysis.clipping_timestamps[:20]]
                lines.append(f"  {', '.join(clip_times)}")
                if len(section_analysis.clipping_timestamps) > 20:
                    lines.append(f"  ... and {len(section_analysis.clipping_timestamps) - 20} more")
                lines.append("")

            # All timestamped issues summary
            if section_analysis.all_issues:
                lines.append("ALL TIMESTAMPED ISSUES:")
                for issue in section_analysis.all_issues:
                    severity_marker = {'minor': '[!]', 'moderate': '[!!]', 'severe': '[!!!]'}.get(issue.severity, '[!]')
                    lines.append(f"  {severity_marker} {issue.message}")
                lines.append("")

        # Reference Comparison Results
        if comparison_result and comparison_result.success:
            lines.append("-" * 40)
            lines.append("REFERENCE TRACK COMPARISON")
            lines.append("-" * 40)
            lines.append(f"Your Mix: {Path(comparison_result.user_file).name}")
            lines.append(f"Reference: {Path(comparison_result.reference_file).name}")
            lines.append(f"Balance Score: {comparison_result.overall_balance_score:.0f}/100")
            lines.append("")

            for stem_name, comp in comparison_result.stem_comparisons.items():
                severity_marker = {
                    'good': '[OK]',
                    'minor': '[!]',
                    'moderate': '[!!]',
                    'significant': '[!!!]'
                }.get(comp.severity, '[?]')

                lines.append(f"{stem_name.upper()}: {severity_marker}")
                lines.append(f"  Level: {comp.user_rms_db:.1f} dB (ref: {comp.ref_rms_db:.1f} dB) -> {comp.rms_diff_db:+.1f} dB")
                lines.append(f"  Width: {comp.user_stereo_width_pct:.0f}% (ref: {comp.ref_stereo_width_pct:.0f}%)")

                if comp.recommendations:
                    for rec in comp.recommendations[:2]:
                        lines.append(f"    -> {rec}")
                lines.append("")

            if comparison_result.priority_recommendations:
                lines.append("PRIORITY ACTIONS:")
                for i, rec in enumerate(comparison_result.priority_recommendations[:5], 1):
                    lines.append(f"  {i}. {rec}")
                lines.append("")

        # Recommendations
        all_recommendations = []
        if audio_analysis:
            all_recommendations.extend(audio_analysis.recommendations)
        if stem_analysis:
            all_recommendations.extend(stem_analysis.recommendations)
        if comparison_result and comparison_result.success:
            all_recommendations.extend(comparison_result.priority_recommendations[:3])

        if all_recommendations:
            lines.append("-" * 40)
            lines.append("RECOMMENDATIONS")
            lines.append("-" * 40)
            for i, rec in enumerate(all_recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")

        # Mastering Results
        if mastering_result:
            lines.append("-" * 40)
            lines.append("MASTERING RESULTS")
            lines.append("-" * 40)
            if mastering_result.success:
                lines.append(f"  Status: Success")
                lines.append(f"  Output: {mastering_result.output_path}")
                if mastering_result.before_lufs and mastering_result.after_lufs:
                    change = mastering_result.after_lufs - mastering_result.before_lufs
                    lines.append(f"  Loudness Change: {change:+.1f} LUFS")
                    lines.append(f"  Before: {mastering_result.before_lufs:.1f} LUFS")
                    lines.append(f"  After: {mastering_result.after_lufs:.1f} LUFS")
            else:
                lines.append(f"  Status: Failed")
                lines.append(f"  Error: {mastering_result.error_message}")
            lines.append("")

        lines.append("=" * 60)
        lines.append("END OF REPORT")
        lines.append("=" * 60)

        # Write to file
        output_path = self.output_dir / f"{filename}.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return str(output_path)

    def _generate_html_report_from_json(
        self,
        json_data: dict,
        filename: str
    ) -> str:
        """
        Generate an HTML dashboard that renders from embedded JSON data.

        The HTML embeds the complete JSON and uses JavaScript to render
        all sections dynamically, ensuring no data is lost.
        """
        # Escape JSON for embedding in HTML
        json_str = json.dumps(json_data, indent=2, ensure_ascii=False, cls=NumpyEncoder)

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Music Analysis Report - {json_data['metadata']['project_name']}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        header h1 {{ font-size: 2em; margin-bottom: 10px; }}
        .timestamp {{ opacity: 0.8; font-size: 0.9em; }}
        .section {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #1a1a2e;
            border-bottom: 2px solid #e94560;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .section h3 {{ color: #333; margin: 20px 0 10px 0; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #0f3460;
        }}
        .card h4 {{ color: #0f3460; margin-bottom: 8px; font-size: 0.9em; }}
        .card p {{ color: #333; font-size: 1.1em; font-weight: 500; }}
        .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .stat-card.warning {{ background: #fff8e6; border: 2px solid #f39c12; }}
        .stat-card.critical {{ background: #fee; border: 2px solid #e74c3c; }}
        .stat-card.success {{ background: #e8f5e9; border: 2px solid #27ae60; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #1a1a2e; }}
        .stat-label {{ color: #666; font-size: 0.9em; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; color: #1a1a2e; font-weight: 600; }}
        tr:hover {{ background: #f8f9fa; }}
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-danger {{ background: #f8d7da; color: #721c24; }}
        .badge-info {{ background: #cce5ff; color: #004085; }}
        .severity-severe {{ background: #fee; }}
        .severity-moderate {{ background: #fff8e6; }}
        .issue {{ padding: 15px; border-radius: 8px; margin-bottom: 10px; }}
        .issue.critical {{ background: #fee; border-left: 4px solid #e94560; }}
        .issue.warning {{ background: #fff8e6; border-left: 4px solid #f39c12; }}
        .issue.info {{ background: #e8f4fd; border-left: 4px solid #3498db; }}
        .recommendation {{
            display: flex;
            align-items: flex-start;
            padding: 12px;
            background: #f0fff0;
            border-radius: 8px;
            margin-bottom: 10px;
        }}
        .recommendation .number {{
            background: #27ae60;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
            flex-shrink: 0;
            font-weight: bold;
        }}
        .meter {{
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }}
        .meter-fill {{
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s ease;
        }}
        .timeline-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 15px 0;
        }}
        .timeline-marker {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 10px;
            min-width: 100px;
            text-align: center;
            box-shadow: 0 3px 10px rgba(102, 126, 234, 0.3);
        }}
        .timeline-marker .marker-name {{ font-weight: bold; font-size: 1.1em; }}
        .timeline-marker .marker-time {{ font-size: 1.2em; opacity: 0.9; }}
        .timeline-marker .marker-bar {{ font-size: 0.8em; opacity: 0.7; }}
        .json-viewer {{
            background: #1a1a2e;
            color: #a8e6cf;
            padding: 20px;
            border-radius: 8px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.85em;
            max-height: 400px;
            overflow: auto;
            white-space: pre-wrap;
        }}
        .collapsible {{
            cursor: pointer;
            user-select: none;
        }}
        .collapsible:hover {{ background: #f0f0f0; }}
        .collapse-content {{ display: none; }}
        .collapse-content.active {{ display: block; }}
        .tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }}
        .tab {{
            padding: 10px 20px;
            border-radius: 8px 8px 0 0;
            cursor: pointer;
            background: #f8f9fa;
            border: none;
            font-size: 1em;
        }}
        .tab.active {{ background: #e94560; color: white; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
    </style>
</head>
<body>
    <div class="container" id="app">
        <!-- Content will be rendered by JavaScript -->
        <p>Loading analysis data...</p>
    </div>

    <!-- Embedded JSON Data -->
    <script id="analysis-data" type="application/json">
{json_str}
    </script>

    <script>
        // Load JSON data
        const data = JSON.parse(document.getElementById('analysis-data').textContent);

        // Utility functions
        function formatTime(seconds) {{
            if (!seconds) return '0:00';
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return mins + ':' + secs.toString().padStart(2, '0');
        }}

        function formatNumber(num, decimals = 1) {{
            if (num === null || num === undefined) return '-';
            return typeof num === 'number' ? num.toFixed(decimals) : num;
        }}

        // Render header
        function renderHeader() {{
            const meta = data.metadata;
            return `
                <header>
                    <h1>Music Analysis Report</h1>
                    <p class="timestamp">Project: ${{meta.project_name}} (Version: ${{meta.version}})</p>
                    <p class="timestamp">Generated: ${{new Date(meta.generated_at).toLocaleString()}}</p>
                </header>
            `;
        }}

        // Render summary section
        function renderSummary() {{
            const s = data.summary;
            const stats = s.stats || {{}};

            return `
                <section class="section">
                    <h2>Summary</h2>
                    <div class="stat-grid">
                        <div class="stat-card ${{s.critical_issues.length > 0 ? 'critical' : 'success'}}">
                            <div class="stat-value">${{s.critical_issues.length}}</div>
                            <div class="stat-label">Critical Issues</div>
                        </div>
                        <div class="stat-card ${{s.warnings.length > 5 ? 'warning' : ''}}">
                            <div class="stat-value">${{s.warnings.length}}</div>
                            <div class="stat-label">Warnings</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${{s.recommendations.length}}</div>
                            <div class="stat-label">Recommendations</div>
                        </div>
                        ${{stats.tempo ? `<div class="stat-card"><div class="stat-value">${{formatNumber(stats.tempo, 0)}}</div><div class="stat-label">BPM</div></div>` : ''}}
                    </div>

                    ${{s.critical_issues.length > 0 ? `
                        <h3>Critical Issues</h3>
                        ${{s.critical_issues.map(i => `<div class="issue critical"><strong>[${{i.source}}]</strong> ${{i.message}}</div>`).join('')}}
                    ` : ''}}

                    ${{s.warnings.length > 0 ? `
                        <h3>Warnings</h3>
                        ${{s.warnings.slice(0, 10).map(i => `<div class="issue warning"><strong>[${{i.source}}]</strong> ${{i.message}}</div>`).join('')}}
                        ${{s.warnings.length > 10 ? `<p><em>...and ${{s.warnings.length - 10}} more warnings</em></p>` : ''}}
                    ` : ''}}
                </section>
            `;
        }}

        // Render ALS project section
        function renderProject() {{
            if (!data.als_project) return '';
            const p = data.als_project;
            const midiTracks = p.tracks.filter(t => t.track_type === 'midi').length;
            const audioTracks = p.tracks.filter(t => t.track_type === 'audio').length;

            return `
                <section class="section">
                    <h2>Project Information</h2>
                    <div class="grid">
                        <div class="card"><h4>File</h4><p>${{p.file_path.split(/[\\\\/]/).pop()}}</p></div>
                        <div class="card"><h4>Ableton Version</h4><p>${{p.ableton_version}}</p></div>
                        <div class="card"><h4>Tempo</h4><p>${{formatNumber(p.tempo, 1)}} BPM</p></div>
                        <div class="card"><h4>Time Signature</h4><p>${{p.time_signature_numerator}}/${{p.time_signature_denominator}}</p></div>
                        <div class="card"><h4>Duration</h4><p>${{formatTime(p.total_duration_seconds)}}</p></div>
                        <div class="card"><h4>Tracks</h4><p>${{p.tracks.length}} (${{midiTracks}} MIDI, ${{audioTracks}} Audio)</p></div>
                        <div class="card"><h4>MIDI Notes</h4><p>${{p.midi_note_count.toLocaleString()}}</p></div>
                        <div class="card"><h4>Audio Clips</h4><p>${{p.audio_clip_count}}</p></div>
                    </div>
                    ${{p.plugin_list && p.plugin_list.length > 0 ? `
                        <h3>Plugins</h3>
                        <p>${{p.plugin_list.join(', ')}}</p>
                    ` : ''}}
                </section>
            `;
        }}

        // Render MIDI analysis section
        function renderMIDI() {{
            if (!data.als_project || !data.als_project.midi_analysis) return '';
            const p = data.als_project;
            const midi = p.midi_analysis;
            const tracks = Object.entries(midi);
            if (tracks.length === 0) return '';

            const humanized = tracks.filter(([_, a]) => a.humanization_score !== 'robotic').length;
            const robotic = tracks.filter(([_, a]) => a.humanization_score === 'robotic');

            return `
                <section class="section">
                    <h2>MIDI Analysis</h2>
                    <div class="stat-grid">
                        <div class="stat-card"><div class="stat-value">${{tracks.length}}</div><div class="stat-label">MIDI Tracks</div></div>
                        <div class="stat-card"><div class="stat-value">${{p.midi_note_count.toLocaleString()}}</div><div class="stat-label">Total Notes</div></div>
                        <div class="stat-card ${{humanized < tracks.length ? 'warning' : ''}}">
                            <div class="stat-value">${{humanized}}/${{tracks.length}}</div>
                            <div class="stat-label">Humanized</div>
                        </div>
                        <div class="stat-card ${{p.quantization_issues_count > 0 ? 'warning' : ''}}">
                            <div class="stat-value">${{p.quantization_issues_count}}</div>
                            <div class="stat-label">Off-Grid Notes</div>
                        </div>
                    </div>

                    <h3>Humanization by Track</h3>
                    <table>
                        <thead><tr><th>Track</th><th>Notes</th><th>Vel Mean</th><th>Vel Std</th><th>Assessment</th><th>Chords</th></tr></thead>
                        <tbody>
                            ${{tracks.sort((a, b) => (a[1].humanization_score === 'robotic' ? -1 : 1)).map(([name, a]) => `
                                <tr class="${{a.humanization_score === 'robotic' ? 'severity-severe' : ''}}">
                                    <td><strong>${{name}}</strong></td>
                                    <td>${{a.note_count}}</td>
                                    <td>${{formatNumber(a.velocity_mean, 0)}}</td>
                                    <td>${{formatNumber(a.velocity_std, 1)}}</td>
                                    <td><span class="badge badge-${{a.humanization_score === 'robotic' ? 'danger' : a.humanization_score === 'slightly_humanized' ? 'warning' : 'success'}}">${{a.humanization_score === 'robotic' ? 'ROBOTIC' : a.humanization_score === 'slightly_humanized' ? 'Slight' : 'Natural'}}</span></td>
                                    <td>${{a.chord_count}}</td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>
                </section>
            `;
        }}

        // Render project structure section
        function renderStructure() {{
            if (!data.als_project || !data.als_project.project_structure) return '';
            const s = data.als_project.project_structure;
            if (!s.locators.length && !s.scenes.length) return '';

            const tempo = data.als_project.tempo;
            const timeSig = data.als_project.time_signature_numerator;

            return `
                <section class="section">
                    <h2>Song Structure</h2>
                    ${{s.locators.length > 0 ? `
                        <h3>Arrangement Markers</h3>
                        <div class="timeline-container">
                            ${{s.locators.map(l => {{
                                const timeSec = (l.time / tempo) * 60;
                                const bar = Math.floor(l.time / timeSig) + 1;
                                return `
                                    <div class="timeline-marker">
                                        <div class="marker-name">${{l.name}}</div>
                                        <div class="marker-time">${{formatTime(timeSec)}}</div>
                                        <div class="marker-bar">Bar ${{bar}}</div>
                                    </div>
                                `;
                            }}).join('')}}
                        </div>
                    ` : ''}}
                    ${{s.scenes.length > 0 ? `
                        <h3>Session View Scenes</h3>
                        <p><strong>${{s.scenes.length}}</strong> scenes defined</p>
                    ` : ''}}
                </section>
            `;
        }}

        // Render audio analysis section
        function renderAudio() {{
            if (!data.audio_analysis) return '';
            const a = data.audio_analysis;

            return `
                <section class="section">
                    <h2>Audio Analysis</h2>

                    <h3>Loudness</h3>
                    <div class="grid">
                        <div class="card"><h4>Integrated LUFS</h4><p>${{formatNumber(a.loudness.integrated_lufs, 1)}} LUFS</p></div>
                        <div class="card"><h4>True Peak</h4><p>${{formatNumber(a.loudness.true_peak_db, 1)}} dB</p></div>
                        <div class="card"><h4>Loudness Range</h4><p>${{formatNumber(a.loudness.loudness_range_lu, 1)}} LU</p></div>
                        <div class="card"><h4>Spotify Diff</h4><p>${{formatNumber(a.loudness.spotify_diff_db, 1)}} dB</p></div>
                    </div>

                    <h3>Dynamics</h3>
                    <div class="grid">
                        <div class="card"><h4>Peak</h4><p>${{formatNumber(a.dynamics.peak_db, 1)}} dB</p></div>
                        <div class="card"><h4>RMS</h4><p>${{formatNumber(a.dynamics.rms_db, 1)}} dB</p></div>
                        <div class="card"><h4>Dynamic Range</h4><p>${{formatNumber(a.dynamics.dynamic_range_db, 1)}} dB</p></div>
                        <div class="card"><h4>Crest Factor</h4><p>${{formatNumber(a.dynamics.crest_factor_db, 1)}} dB (${{a.dynamics.crest_interpretation}})</p></div>
                    </div>

                    <h3>Frequency Balance</h3>
                    <div class="grid">
                        <div class="card"><h4>Bass (20-250Hz)</h4><p>${{formatNumber(a.frequency.bass_energy, 1)}}%</p></div>
                        <div class="card"><h4>Low Mid (250-500Hz)</h4><p>${{formatNumber(a.frequency.low_mid_energy, 1)}}%</p></div>
                        <div class="card"><h4>Mid (500-2kHz)</h4><p>${{formatNumber(a.frequency.mid_energy, 1)}}%</p></div>
                        <div class="card"><h4>High Mid (2-6kHz)</h4><p>${{formatNumber(a.frequency.high_mid_energy, 1)}}%</p></div>
                        <div class="card"><h4>High (6-20kHz)</h4><p>${{formatNumber(a.frequency.high_energy, 1)}}%</p></div>
                    </div>

                    <h3>Stereo</h3>
                    <div class="grid">
                        <div class="card"><h4>Width</h4><p>${{formatNumber(a.stereo.width_estimate, 0)}}% (${{a.stereo.width_category}})</p></div>
                        <div class="card"><h4>Correlation</h4><p>${{formatNumber(a.stereo.correlation, 2)}}</p></div>
                        <div class="card"><h4>Mono Compatible</h4><p>${{a.stereo.is_mono_compatible ? 'Yes' : 'No'}}</p></div>
                        <div class="card"><h4>Phase Safe</h4><p>${{a.stereo.phase_safe ? 'Yes' : 'No'}}</p></div>
                    </div>

                    ${{a.transients ? `
                        <h3>Transients</h3>
                        <div class="grid">
                            <div class="card"><h4>Count</h4><p>${{a.transients.transient_count}}</p></div>
                            <div class="card"><h4>Per Second</h4><p>${{formatNumber(a.transients.transients_per_second, 1)}}</p></div>
                            <div class="card"><h4>Attack Quality</h4><p>${{a.transients.attack_quality}}</p></div>
                        </div>
                    ` : ''}}
                </section>
            `;
        }}

        // Render stem analysis section
        function renderStems() {{
            if (!data.stem_analysis) return '';
            const s = data.stem_analysis;

            const severeClashes = s.clashes.filter(c => c.severity === 'severe');
            const moderateClashes = s.clashes.filter(c => c.severity === 'moderate');

            return `
                <section class="section">
                    <h2>Stem Analysis</h2>

                    <div class="stat-grid">
                        <div class="stat-card"><div class="stat-value">${{s.stems.length}}</div><div class="stat-label">Stems</div></div>
                        <div class="stat-card ${{severeClashes.length > 0 ? 'critical' : ''}}">
                            <div class="stat-value">${{severeClashes.length}}</div>
                            <div class="stat-label">Severe Clashes</div>
                        </div>
                        <div class="stat-card ${{moderateClashes.length > 0 ? 'warning' : ''}}">
                            <div class="stat-value">${{moderateClashes.length}}</div>
                            <div class="stat-label">Moderate Clashes</div>
                        </div>
                    </div>

                    <h3>Stems</h3>
                    <table>
                        <thead><tr><th>Name</th><th>Peak dB</th><th>RMS dB</th><th>Panning</th><th>Mono</th></tr></thead>
                        <tbody>
                            ${{s.stems.map(stem => `
                                <tr>
                                    <td><strong>${{stem.name}}</strong></td>
                                    <td>${{formatNumber(stem.peak_db, 1)}}</td>
                                    <td>${{formatNumber(stem.rms_db, 1)}}</td>
                                    <td>${{formatNumber(stem.panning, 2)}}</td>
                                    <td>${{stem.is_mono ? 'Yes' : 'No'}}</td>
                                </tr>
                            `).join('')}}
                        </tbody>
                    </table>

                    ${{s.clashes.length > 0 ? `
                        <h3>Frequency Clashes</h3>
                        <table>
                            <thead><tr><th>Stem 1</th><th>Stem 2</th><th>Frequency Range</th><th>Overlap</th><th>Severity</th></tr></thead>
                            <tbody>
                                ${{s.clashes.slice(0, 30).map(c => `
                                    <tr class="severity-${{c.severity}}">
                                        <td>${{c.stem1}}</td>
                                        <td>${{c.stem2}}</td>
                                        <td>${{c.frequency_range[0].toFixed(0)}}-${{c.frequency_range[1].toFixed(0)}} Hz</td>
                                        <td>${{(c.overlap_amount * 100).toFixed(0)}}%</td>
                                        <td><span class="badge badge-${{c.severity === 'severe' ? 'danger' : c.severity === 'moderate' ? 'warning' : 'info'}}">${{c.severity}}</span></td>
                                    </tr>
                                `).join('')}}
                                ${{s.clashes.length > 30 ? `<tr><td colspan="5"><em>...and ${{s.clashes.length - 30}} more clashes</em></td></tr>` : ''}}
                            </tbody>
                        </table>
                    ` : ''}}
                </section>
            `;
        }}

        // Render recommendations section
        function renderRecommendations() {{
            const recs = data.summary.recommendations;
            if (!recs || recs.length === 0) return '';

            return `
                <section class="section">
                    <h2>Recommendations</h2>
                    ${{recs.map((r, i) => `
                        <div class="recommendation">
                            <div class="number">${{i + 1}}</div>
                            <div><strong>[${{r.source}}]</strong> ${{r.text}}</div>
                        </div>
                    `).join('')}}
                </section>
            `;
        }}

        // Render raw JSON viewer
        function renderJsonViewer() {{
            return `
                <section class="section">
                    <h2 class="collapsible" onclick="this.nextElementSibling.classList.toggle('active')">
                        Raw JSON Data (click to expand)
                    </h2>
                    <div class="collapse-content">
                        <div class="json-viewer">${{JSON.stringify(data, null, 2)}}</div>
                    </div>
                </section>
            `;
        }}

        // Main render function
        function renderDashboard() {{
            const app = document.getElementById('app');
            app.innerHTML = `
                ${{renderHeader()}}
                ${{renderSummary()}}
                ${{renderProject()}}
                ${{renderMIDI()}}
                ${{renderStructure()}}
                ${{renderAudio()}}
                ${{renderStems()}}
                ${{renderRecommendations()}}
                ${{renderJsonViewer()}}
            `;
        }}

        // Initialize
        renderDashboard();
    </script>
</body>
</html>'''

        # Write to file
        output_path = self.output_dir / f"{filename}.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return str(output_path)

    def _generate_html_report(
        self,
        audio_analysis: Optional[AnalysisResult],
        stem_analysis: Optional[StemAnalysisResult],
        als_project: Optional[ALSProject],
        mastering_result: Optional[MasteringResult],
        section_analysis: Optional[SectionAnalysisResult],
        comparison_result: Optional[ComparisonResult],
        filename: str
    ) -> str:
        """Generate an HTML report with styling (legacy method)."""
        html = self._get_html_template()

        # Build content sections
        content = []

        # Header
        content.append(f'''
        <header>
            <h1>Music Production Analysis Report</h1>
            <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        ''')

        # Project Info Section
        if als_project:
            content.append(self._html_project_section(als_project))

            # MIDI Analysis Section (if project has MIDI data)
            if als_project.midi_analysis:
                content.append(self._html_midi_analysis_section(als_project))

            # Song Structure Section (if project has markers/scenes)
            if als_project.project_structure and (
                als_project.project_structure.locators or
                als_project.project_structure.scenes or
                als_project.project_structure.tempo_automation
            ):
                content.append(self._html_structure_section(als_project))

        # Audio Analysis Section
        if audio_analysis:
            content.append(self._html_audio_section(audio_analysis))

        # Timeline/Section Analysis Section
        if section_analysis:
            content.append(self._html_timeline_section(section_analysis))

        # Stem Analysis Section
        if stem_analysis:
            content.append(self._html_stem_section(stem_analysis))

        # Reference Comparison Section
        if comparison_result and comparison_result.success:
            content.append(self._html_comparison_section(comparison_result))

        # Recommendations Section
        all_recommendations = []
        if audio_analysis:
            all_recommendations.extend(audio_analysis.recommendations)
        if stem_analysis:
            all_recommendations.extend(stem_analysis.recommendations)
        if comparison_result and comparison_result.success:
            all_recommendations.extend(comparison_result.priority_recommendations[:5])

        if all_recommendations:
            content.append(self._html_recommendations_section(all_recommendations))

        # Mastering Results
        if mastering_result:
            content.append(self._html_mastering_section(mastering_result))

        # Combine
        html = html.replace('{{CONTENT}}', '\n'.join(content))

        # Write to file
        output_path = self.output_dir / f"{filename}.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return str(output_path)

    def _get_html_template(self) -> str:
        """Get the HTML template."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Music Analysis Report</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        header h1 { font-size: 2em; margin-bottom: 10px; }
        .timestamp { opacity: 0.8; font-size: 0.9em; }
        .section {
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .section h2 {
            color: #1a1a2e;
            border-bottom: 2px solid #e94560;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
        .card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #0f3460;
        }
        .card h4 { color: #0f3460; margin-bottom: 8px; }
        .card p { color: #666; }
        .issue { padding: 15px; border-radius: 8px; margin-bottom: 10px; }
        .issue.critical { background: #fee; border-left: 4px solid #e94560; }
        .issue.warning { background: #fff8e6; border-left: 4px solid #f39c12; }
        .issue.info { background: #e8f4fd; border-left: 4px solid #3498db; }
        .recommendation {
            display: flex;
            align-items: flex-start;
            padding: 12px;
            background: #f0fff0;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .recommendation .number {
            background: #27ae60;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
            flex-shrink: 0;
            font-weight: bold;
        }
        .recommendation.priority-critical .number { background: #e74c3c; }
        .recommendation.priority-high .number { background: #e67e22; }
        .recommendation.priority-medium .number { background: #f39c12; }
        .meter {
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 8px;
        }
        .meter-fill {
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s ease;
        }
        .meter-fill.bass { background: linear-gradient(90deg, #e94560, #ff6b6b); }
        .meter-fill.mid { background: linear-gradient(90deg, #f39c12, #f1c40f); }
        .meter-fill.high { background: linear-gradient(90deg, #3498db, #5dade2); }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; color: #1a1a2e; font-weight: 600; }
        tr:hover { background: #f8f9fa; }
        .success { color: #27ae60; }
        .error { color: #e74c3c; }
        .clash-severe { background: #fee; }
        .clash-moderate { background: #fff8e6; }
        .clash-minor { background: #f8f9fa; }
        /* Timeline styles */
        .timeline-container { margin: 20px 0; }
        .timeline {
            position: relative;
            height: 60px;
            background: #2c3e50;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 10px;
        }
        .timeline-section {
            position: absolute;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75em;
            font-weight: 600;
            color: white;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
            border-right: 1px solid rgba(255,255,255,0.3);
            transition: opacity 0.2s;
        }
        .timeline-section:hover { opacity: 0.9; }
        .timeline-section.intro { background: linear-gradient(135deg, #3498db, #2980b9); }
        .timeline-section.buildup { background: linear-gradient(135deg, #f39c12, #e67e22); }
        .timeline-section.drop { background: linear-gradient(135deg, #e74c3c, #c0392b); }
        .timeline-section.breakdown { background: linear-gradient(135deg, #9b59b6, #8e44ad); }
        .timeline-section.outro { background: linear-gradient(135deg, #1abc9c, #16a085); }
        .timeline-section.unknown { background: linear-gradient(135deg, #95a5a6, #7f8c8d); }
        .timeline-section.severity-severe { box-shadow: inset 0 0 0 3px #e74c3c; }
        .timeline-section.severity-moderate { box-shadow: inset 0 0 0 3px #f39c12; }
        .timeline-section.severity-minor { box-shadow: inset 0 0 0 2px #f1c40f; }
        .timeline-markers {
            display: flex;
            justify-content: space-between;
            font-size: 0.8em;
            color: #666;
            padding: 0 5px;
        }
        .section-detail {
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid #3498db;
            background: #f8f9fa;
        }
        .section-detail.severity-clean { border-left-color: #27ae60; }
        .section-detail.severity-minor { border-left-color: #f1c40f; background: #fffef0; }
        .section-detail.severity-moderate { border-left-color: #f39c12; background: #fff8e6; }
        .section-detail.severity-severe { border-left-color: #e74c3c; background: #fee; }
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .section-type {
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.9em;
        }
        .section-time { color: #666; font-size: 0.9em; }
        .section-severity {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
        }
        .section-severity.clean { background: #d4edda; color: #155724; }
        .section-severity.minor { background: #fff3cd; color: #856404; }
        .section-severity.moderate { background: #ffe0b2; color: #e65100; }
        .section-severity.severe { background: #f8d7da; color: #721c24; }
        .section-issues { margin-top: 10px; }
        .section-issue {
            padding: 8px 12px;
            margin: 5px 0;
            background: white;
            border-radius: 4px;
            font-size: 0.9em;
            border-left: 3px solid #e74c3c;
        }
        .clipping-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .clip-time {
            background: #fee;
            color: #c0392b;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 500;
        }
        /* Executive Summary */
        .exec-summary {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        .summary-stat {
            text-align: center;
            padding: 20px;
            border-radius: 10px;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .summary-stat .number {
            font-size: 2.5em;
            font-weight: bold;
            line-height: 1;
        }
        .summary-stat .label {
            color: #666;
            margin-top: 5px;
            font-size: 0.9em;
        }
        .summary-stat.critical .number { color: #e74c3c; }
        .summary-stat.warning .number { color: #f39c12; }
        .summary-stat.info .number { color: #3498db; }
        .summary-stat.good .number { color: #27ae60; }
        /* Stat Cards (MIDI Analysis) */
        .stat-card {
            text-align: center;
            padding: 20px;
            border-radius: 10px;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .stat-card.warning { background: #fff8e6; border: 2px solid #f39c12; }
        .stat-card .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #1a1a2e;
        }
        .stat-card .stat-label {
            color: #666;
            margin-top: 5px;
            font-size: 0.9em;
        }
        /* Badges */
        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-warning { background: #fff3cd; color: #856404; }
        .badge-danger { background: #f8d7da; color: #721c24; }
        /* Section Description */
        .section-desc {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 15px;
            font-style: italic;
        }
        /* Timeline Container (Song Structure) */
        .timeline-container {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 15px 0;
        }
        .timeline-marker {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 10px;
            min-width: 100px;
            text-align: center;
            box-shadow: 0 3px 10px rgba(102, 126, 234, 0.3);
        }
        .timeline-marker .marker-name {
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 5px;
        }
        .timeline-marker .marker-time {
            font-size: 1.2em;
            opacity: 0.9;
        }
        .timeline-marker .marker-bar {
            font-size: 0.8em;
            opacity: 0.7;
            margin-top: 3px;
        }
        /* Scene List */
        .scene-list {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 10px 0;
        }
        .scene-badge {
            background: #e8f4fd;
            color: #2980b9;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            border: 1px solid #bcdff1;
        }
        /* Track Filter */
        .track-filter {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            position: sticky;
            top: 10px;
            z-index: 100;
            box-shadow: 0 2px 10px rgba(0,0,0,0.15);
        }
        .track-filter h3 { margin-bottom: 10px; color: #1a1a2e; }
        .track-filter select {
            width: 100%;
            padding: 12px;
            font-size: 1em;
            border: 2px solid #ddd;
            border-radius: 8px;
            background: white;
            cursor: pointer;
        }
        .track-filter select:focus {
            outline: none;
            border-color: #e94560;
        }
        .track-info {
            margin-top: 15px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            display: none;
        }
        .track-info.active { display: block; }
        .track-info h4 { color: #1a1a2e; margin-bottom: 10px; }
        .track-stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        .track-stat {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 6px;
            text-align: center;
        }
        .track-stat .value { font-weight: bold; font-size: 1.1em; }
        .track-stat .label { font-size: 0.8em; color: #666; }
        .track-clashes { margin-top: 15px; }
        .track-clash {
            padding: 10px 15px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 4px solid #e74c3c;
            background: #fff;
        }
        .track-clash.severe { border-left-color: #e74c3c; background: #fee; }
        .track-clash.moderate { border-left-color: #f39c12; background: #fff8e6; }
        .track-clash.minor { border-left-color: #f1c40f; background: #fffef0; }
        .track-clash .clash-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 5px;
        }
        .track-clash .other-track { font-weight: 600; }
        .track-clash .freq-range { color: #666; font-size: 0.9em; }
        .track-clash .recommendation {
            font-size: 0.9em;
            color: #333;
            margin-top: 5px;
            padding: 8px;
            background: rgba(255,255,255,0.7);
            border-radius: 4px;
        }
        .severity-badge {
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75em;
            font-weight: 600;
            text-transform: uppercase;
        }
        .severity-badge.severe { background: #e74c3c; color: white; }
        .severity-badge.moderate { background: #f39c12; color: white; }
        .severity-badge.minor { background: #f1c40f; color: #333; }
        /* Priority Section */
        .priority-actions {
            background: linear-gradient(135deg, #fee 0%, #fff8e6 100%);
            border: 2px solid #e74c3c;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .priority-actions h2 {
            color: #c0392b;
            border-bottom: 2px solid #e74c3c;
        }
        .priority-item {
            display: flex;
            align-items: flex-start;
            padding: 15px;
            margin: 10px 0;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .priority-item .priority-number {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
            margin-right: 15px;
            flex-shrink: 0;
        }
        .priority-item.critical .priority-number { background: #e74c3c; }
        .priority-item.high .priority-number { background: #e67e22; }
        .priority-item.medium .priority-number { background: #f39c12; }
        .priority-item .priority-content { flex: 1; }
        .priority-item .priority-title { font-weight: 600; margin-bottom: 5px; }
        .priority-item .priority-detail { color: #666; font-size: 0.9em; }
        .priority-item .priority-tracks {
            margin-top: 8px;
            font-size: 0.85em;
            color: #888;
        }
        /* Collapsible sections */
        .collapsible-header {
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
        }
        .collapsible-header:hover { opacity: 0.8; }
        .collapsible-header::after {
            content: '▼';
            font-size: 0.8em;
            transition: transform 0.3s;
        }
        .collapsible-header.collapsed::after {
            transform: rotate(-90deg);
        }
        .collapsible-content {
            overflow: hidden;
            transition: max-height 0.3s ease;
        }
        .collapsible-content.collapsed {
            max-height: 0 !important;
        }
        /* Tab navigation */
        .tab-nav {
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
        .tab-btn {
            padding: 10px 20px;
            border: none;
            background: #f8f9fa;
            border-radius: 8px 8px 0 0;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        }
        .tab-btn:hover { background: #e9ecef; }
        .tab-btn.active {
            background: #e94560;
            color: white;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        {{CONTENT}}
    </div>
    <script>
        // Track filter functionality
        function filterByTrack(trackName) {
            const infoDiv = document.getElementById('track-info');
            const clashesDiv = document.getElementById('track-clashes-list');

            if (!trackName || trackName === 'all') {
                infoDiv.classList.remove('active');
                // Show all clashes in main table
                document.querySelectorAll('.clash-row').forEach(row => {
                    row.style.display = '';
                });
                return;
            }

            // Get track data from embedded JSON
            const trackData = window.trackData[trackName];
            if (!trackData) return;

            // Update track info display
            document.getElementById('track-name').textContent = trackName;
            document.getElementById('track-peak').textContent = trackData.peak_db.toFixed(1) + ' dB';
            document.getElementById('track-rms').textContent = trackData.rms_db.toFixed(1) + ' dB';
            document.getElementById('track-pan').textContent = trackData.panning;
            document.getElementById('track-mono').textContent = trackData.is_mono ? 'Mono' : 'Stereo';
            document.getElementById('track-clash-count').textContent = trackData.clashes.length;

            // Build dominant frequencies display
            let domFreqsHtml = '';
            if (trackData.dominant_frequencies && trackData.dominant_frequencies.length > 0) {
                trackData.dominant_frequencies.forEach(f => {
                    domFreqsHtml += `<span style="background: #e8f4fd; padding: 4px 10px; border-radius: 4px; font-size: 0.85em;">${f.freq.toFixed(0)} Hz</span>`;
                });
            } else {
                domFreqsHtml = '<span style="color: #666;">No dominant frequencies detected</span>';
            }
            document.getElementById('track-dominant-freqs').innerHTML = domFreqsHtml;

            // Build frequency profile display
            let freqProfileHtml = '';
            if (trackData.frequency_profile && Object.keys(trackData.frequency_profile).length > 0) {
                const bands = ['sub', 'bass', 'low_mid', 'mid', 'high_mid', 'high', 'air'];
                const bandNames = ['Sub', 'Bass', 'Low-Mid', 'Mid', 'High-Mid', 'High', 'Air'];
                const colors = ['#9b59b6', '#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db', '#9b59b6'];
                bands.forEach((band, i) => {
                    const value = trackData.frequency_profile[band] || 0;
                    freqProfileHtml += `
                        <div style="margin: 5px 0;">
                            <span style="display: inline-block; width: 70px;">${bandNames[i]}:</span>
                            <span style="display: inline-block; width: 50px; text-align: right;">${value.toFixed(1)}%</span>
                            <div style="display: inline-block; width: 200px; height: 12px; background: #e0e0e0; border-radius: 6px; margin-left: 10px; vertical-align: middle;">
                                <div style="width: ${Math.min(value * 2, 100)}%; height: 100%; background: ${colors[i]}; border-radius: 6px;"></div>
                            </div>
                        </div>
                    `;
                });
            } else {
                freqProfileHtml = '<span style="color: #666;">No frequency profile available</span>';
            }
            document.getElementById('track-freq-profile').innerHTML = freqProfileHtml;

            // Build clashes list for this track
            let clashesHtml = '';
            const sortedClashes = [...trackData.clashes].sort((a, b) => {
                const order = {severe: 0, moderate: 1, minor: 2};
                return order[a.severity] - order[b.severity];
            });

            sortedClashes.forEach(clash => {
                clashesHtml += `
                    <div class="track-clash ${clash.severity}">
                        <div class="clash-header">
                            <span class="other-track">vs ${clash.other_track}</span>
                            <span class="severity-badge ${clash.severity}">${clash.severity}</span>
                        </div>
                        <div class="freq-range">${clash.freq_range}</div>
                        <div class="recommendation">${clash.recommendation}</div>
                    </div>
                `;
            });

            if (clashesHtml === '') {
                clashesHtml = '<p style="color: #27ae60; padding: 10px;">No frequency clashes detected for this track!</p>';
            }

            clashesDiv.innerHTML = clashesHtml;
            infoDiv.classList.add('active');

            // Filter main clash table
            document.querySelectorAll('.clash-row').forEach(row => {
                const stem1 = row.dataset.stem1;
                const stem2 = row.dataset.stem2;
                if (stem1 === trackName || stem2 === trackName) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        }

        // Tab switching
        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }

        // Collapsible sections
        function toggleCollapsible(header) {
            header.classList.toggle('collapsed');
            const content = header.nextElementSibling;
            content.classList.toggle('collapsed');
        }
    </script>
</body>
</html>'''

    def _html_project_section(self, project: ALSProject) -> str:
        """Generate HTML for project section."""
        duration_min = project.total_duration_seconds / 60
        return f'''
        <section class="section">
            <h2>Project Information</h2>
            <div class="grid">
                <div class="card">
                    <h4>File</h4>
                    <p>{Path(project.file_path).name}</p>
                </div>
                <div class="card">
                    <h4>Ableton Version</h4>
                    <p>{project.ableton_version}</p>
                </div>
                <div class="card">
                    <h4>Tempo</h4>
                    <p>{project.tempo:.1f} BPM</p>
                </div>
                <div class="card">
                    <h4>Time Signature</h4>
                    <p>{project.time_signature_numerator}/{project.time_signature_denominator}</p>
                </div>
                <div class="card">
                    <h4>Duration</h4>
                    <p>{duration_min:.1f} minutes</p>
                </div>
                <div class="card">
                    <h4>Tracks</h4>
                    <p>{len(project.tracks)} tracks</p>
                </div>
                <div class="card">
                    <h4>MIDI Notes</h4>
                    <p>{project.midi_note_count:,}</p>
                </div>
                <div class="card">
                    <h4>Audio Clips</h4>
                    <p>{project.audio_clip_count}</p>
                </div>
            </div>
        </section>
        '''

    def _html_midi_analysis_section(self, project: ALSProject) -> str:
        """Generate HTML for MIDI analysis section."""
        if not project.midi_analysis:
            return ""

        # Calculate summary stats
        total_tracks = len(project.midi_analysis)
        humanized = sum(1 for a in project.midi_analysis.values()
                       if a.humanization_score in ('slightly_humanized', 'natural'))
        robotic = sum(1 for a in project.midi_analysis.values()
                     if a.humanization_score == 'robotic')

        # Summary cards
        html = f'''
        <section class="section">
            <h2>MIDI Analysis</h2>
            <div class="exec-summary">
                <div class="stat-card">
                    <div class="stat-value">{total_tracks}</div>
                    <div class="stat-label">MIDI Tracks</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{project.midi_note_count:,}</div>
                    <div class="stat-label">Total Notes</div>
                </div>
                <div class="stat-card {'warning' if humanized < total_tracks else ''}">
                    <div class="stat-value">{humanized}/{total_tracks}</div>
                    <div class="stat-label">Humanized</div>
                </div>
                <div class="stat-card {'warning' if project.quantization_issues_count > 0 else ''}">
                    <div class="stat-value">{project.quantization_issues_count}</div>
                    <div class="stat-label">Off-Grid Notes</div>
                </div>
            </div>
        '''

        # Humanization table
        html += '''
            <h3>Humanization by Track</h3>
            <table>
                <thead>
                    <tr>
                        <th>Track</th>
                        <th>Notes</th>
                        <th>Vel Mean</th>
                        <th>Vel Std Dev</th>
                        <th>Assessment</th>
                        <th>Chords</th>
                    </tr>
                </thead>
                <tbody>
        '''

        # Sort by humanization score (robotic first)
        sorted_analysis = sorted(
            project.midi_analysis.items(),
            key=lambda x: (x[1].humanization_score != 'robotic', x[0])
        )

        for track_name, analysis in sorted_analysis:
            if analysis.humanization_score == 'robotic':
                badge = '<span class="badge badge-danger">ROBOTIC</span>'
            elif analysis.humanization_score == 'slightly_humanized':
                badge = '<span class="badge badge-warning">Slight</span>'
            else:
                badge = '<span class="badge badge-success">Natural</span>'

            html += f'''
                    <tr class="{'severity-severe' if analysis.humanization_score == 'robotic' else ''}">
                        <td><strong>{track_name}</strong></td>
                        <td>{analysis.note_count}</td>
                        <td>{analysis.velocity_mean:.0f}</td>
                        <td>{analysis.velocity_std:.1f}</td>
                        <td>{badge}</td>
                        <td>{analysis.chord_count}</td>
                    </tr>
            '''

        html += '''
                </tbody>
            </table>
        '''

        # Quantization issues table (if any)
        all_quant_errors = []
        for track_name, analysis in project.midi_analysis.items():
            for err in analysis.quantization_errors:
                if err.severity in ('severe', 'notable'):
                    all_quant_errors.append(err)

        if all_quant_errors:
            # Sort by severity
            all_quant_errors.sort(key=lambda e: (e.severity != 'severe', e.error_beats), reverse=True)

            html += '''
            <h3>Quantization Issues</h3>
            <p class="section-desc">Notes that are significantly off the grid (may be intentional for humanization)</p>
            <table>
                <thead>
                    <tr>
                        <th>Track</th>
                        <th>Note</th>
                        <th>Position</th>
                        <th>Grid</th>
                        <th>Error</th>
                        <th>Severity</th>
                    </tr>
                </thead>
                <tbody>
            '''

            note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

            for err in all_quant_errors[:20]:  # Limit to 20
                note_name = note_names[err.pitch % 12]
                octave = err.pitch // 12 - 1
                severity_class = 'severity-severe' if err.severity == 'severe' else 'severity-moderate'
                severity_badge = (
                    '<span class="badge badge-danger">Severe</span>' if err.severity == 'severe'
                    else '<span class="badge badge-warning">Notable</span>'
                )

                html += f'''
                    <tr class="{severity_class}">
                        <td>{err.track_name}</td>
                        <td>{note_name}{octave}</td>
                        <td>{err.time:.3f}</td>
                        <td>{err.nearest_grid:.3f}</td>
                        <td>{err.error_beats:.3f}</td>
                        <td>{severity_badge}</td>
                    </tr>
                '''

            if len(all_quant_errors) > 20:
                html += f'''
                    <tr>
                        <td colspan="6" style="text-align: center; font-style: italic;">
                            ...and {len(all_quant_errors) - 20} more
                        </td>
                    </tr>
                '''

            html += '''
                </tbody>
            </table>
            '''

        # Chord summary (if any chords detected)
        if project.total_chord_count > 0:
            html += f'''
            <h3>Chord Detection</h3>
            <p><strong>{project.total_chord_count}</strong> chords detected across all tracks</p>
            '''

            # Show unique chords by track
            for track_name, analysis in sorted_analysis:
                if analysis.chords:
                    chord_names = [c.chord_name for c in analysis.chords if c.chord_name]
                    unique_chords = list(dict.fromkeys(chord_names))[:10]
                    if unique_chords:
                        html += f'<p><strong>{track_name}:</strong> {", ".join(unique_chords)}</p>'

        html += '''
        </section>
        '''
        return html

    def _html_structure_section(self, project: ALSProject) -> str:
        """Generate HTML for song structure section."""
        if not project.project_structure:
            return ""

        struct = project.project_structure
        tempo = project.tempo

        html = '''
        <section class="section">
            <h2>Song Structure</h2>
        '''

        # Locators/Markers
        if struct.locators:
            html += '''
            <h3>Arrangement Markers</h3>
            <div class="timeline-container">
            '''

            for loc in struct.locators:
                # Convert beats to time
                time_seconds = (loc.time / tempo) * 60 if tempo > 0 else 0
                time_str = f"{int(time_seconds // 60)}:{int(time_seconds % 60):02d}"
                bar = int(loc.time / project.time_signature_numerator) + 1

                html += f'''
                <div class="timeline-marker">
                    <div class="marker-name">{loc.name}</div>
                    <div class="marker-time">{time_str}</div>
                    <div class="marker-bar">Bar {bar}</div>
                </div>
                '''

            html += '''
            </div>
            '''

        # Scenes
        if struct.scenes:
            html += f'''
            <h3>Session View Scenes</h3>
            <p><strong>{len(struct.scenes)}</strong> scenes defined</p>
            <div class="scene-list">
            '''

            for scene in struct.scenes[:10]:
                tempo_str = f" ({scene.tempo:.0f} BPM)" if scene.tempo else ""
                html += f'<span class="scene-badge">{scene.name}{tempo_str}</span>'

            if len(struct.scenes) > 10:
                html += f'<span class="scene-badge">...+{len(struct.scenes) - 10} more</span>'

            html += '''
            </div>
            '''

        # Tempo Automation
        if struct.tempo_automation and len(struct.tempo_automation) > 1:
            html += '''
            <h3>Tempo Map</h3>
            <table>
                <thead>
                    <tr>
                        <th>Position</th>
                        <th>Time</th>
                        <th>Tempo</th>
                        <th>Change</th>
                    </tr>
                </thead>
                <tbody>
            '''

            prev_tempo = None
            for tc in struct.tempo_automation:
                time_seconds = (tc.time / tempo) * 60 if tempo > 0 else 0
                time_str = f"{int(time_seconds // 60)}:{int(time_seconds % 60):02d}"
                bar = int(tc.time / project.time_signature_numerator) + 1

                if prev_tempo:
                    diff = tc.tempo - prev_tempo
                    change_str = f"+{diff:.1f}" if diff > 0 else f"{diff:.1f}"
                else:
                    change_str = "-"

                html += f'''
                    <tr>
                        <td>Bar {bar}</td>
                        <td>{time_str}</td>
                        <td>{tc.tempo:.1f} BPM</td>
                        <td>{change_str}</td>
                    </tr>
                '''
                prev_tempo = tc.tempo

            html += '''
                </tbody>
            </table>
            '''

        html += '''
        </section>
        '''
        return html

    def _html_audio_section(self, analysis: AnalysisResult) -> str:
        """Generate HTML for audio analysis section with ALL metrics."""
        issues_html = ""

        # Critical issues
        critical = [i for i in analysis.overall_issues if i.get('severity') == 'critical']
        for issue in critical:
            issues_html += f'<div class="issue critical"><strong>CRITICAL:</strong> {issue["message"]}</div>'

        # Warnings
        warnings = [i for i in analysis.overall_issues if i.get('severity') == 'warning']
        for issue in warnings:
            issues_html += f'<div class="issue warning"><strong>Warning:</strong> {issue["message"]}</div>'

        # Info
        info = [i for i in analysis.overall_issues if i.get('severity') == 'info']
        for issue in info:
            issues_html += f'<div class="issue info"><strong>Info:</strong> {issue["message"]}</div>'

        if not issues_html:
            issues_html = '<div class="issue info">No significant issues detected.</div>'

        # Clipping details section
        clipping_html = ""
        if analysis.clipping.has_clipping:
            clip_positions_html = ""
            if analysis.clipping.clip_positions:
                clip_times = [self._format_time(t) for t in analysis.clipping.clip_positions[:10]]
                clip_positions_html = f'''
                <div style="margin-top: 10px;">
                    <strong>Clipping at:</strong>
                    <div class="clipping-list">
                        {''.join(f'<span class="clip-time">{t}</span>' for t in clip_times)}
                    </div>
                </div>
                '''
            severity_color = {"severe": "#e74c3c", "moderate": "#f39c12", "minor": "#f1c40f"}.get(analysis.clipping.severity, "#666")
            clipping_html = f'''
            <h3 style="margin: 20px 0 15px;">Clipping Analysis</h3>
            <div class="grid">
                <div class="card">
                    <h4>Clipped Samples</h4>
                    <p style="color: {severity_color}; font-weight: bold;">{analysis.clipping.clip_count:,}</p>
                </div>
                <div class="card">
                    <h4>Max Peak</h4>
                    <p>{analysis.clipping.max_peak:.4f}</p>
                </div>
                <div class="card">
                    <h4>Severity</h4>
                    <p style="color: {severity_color}; font-weight: bold;">{analysis.clipping.severity.upper()}</p>
                </div>
            </div>
            {clip_positions_html}
            '''

        # Enhanced stereo/phase section
        stereo_html = ""
        if analysis.stereo.is_stereo:
            phase_color = "#27ae60" if analysis.stereo.phase_safe else "#e74c3c"
            phase_text = "Safe" if analysis.stereo.phase_safe else "OUT OF PHASE!"
            stereo_issues_html = ""
            if analysis.stereo.issues:
                stereo_issues_html = '<div style="margin-top: 10px;">' + ''.join(f'<div class="issue warning" style="margin: 5px 0;">{issue}</div>' for issue in analysis.stereo.issues) + '</div>'
            stereo_html = f'''
            <div class="card">
                <h4>Stereo Width</h4>
                <p>{analysis.stereo.width_estimate:.0f}% ({analysis.stereo.width_category})</p>
            </div>
            <div class="card">
                <h4>L/R Correlation</h4>
                <p>{analysis.stereo.correlation:.2f}</p>
            </div>
            <div class="card">
                <h4>Phase Status</h4>
                <p style="color: {phase_color}; font-weight: bold;">{phase_text}</p>
            </div>
            <div class="card">
                <h4>Mono Compatible</h4>
                <p>{'Yes' if analysis.stereo.is_mono_compatible else 'No'}</p>
            </div>
            '''

        # Transients section with positions
        transients_html = ""
        if analysis.transients:
            attack_color = {"punchy": "#27ae60", "average": "#f39c12", "soft": "#e74c3c"}.get(analysis.transients.attack_quality, "#666")
            transient_positions_html = ""
            if analysis.transients.transient_positions:
                positions = [self._format_time(t) for t in analysis.transients.transient_positions[:10]]
                transient_positions_html = f'''
                <div style="margin-top: 15px;">
                    <strong>First 10 Transient Positions:</strong>
                    <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px;">
                        {''.join(f'<span style="background: #e8f4fd; padding: 4px 10px; border-radius: 4px; font-size: 0.85em;">{t}</span>' for t in positions)}
                    </div>
                </div>
                '''
            transients_html = f'''
            <h3 style="margin: 20px 0 15px;">Transient Analysis</h3>
            <div class="grid">
                <div class="card">
                    <h4>Transient Count</h4>
                    <p>{analysis.transients.transient_count}</p>
                </div>
                <div class="card">
                    <h4>Density</h4>
                    <p>{analysis.transients.transients_per_second:.1f}/sec</p>
                </div>
                <div class="card">
                    <h4>Avg Strength</h4>
                    <p>{analysis.transients.avg_transient_strength:.2f}</p>
                </div>
                <div class="card">
                    <h4>Peak Strength</h4>
                    <p>{analysis.transients.peak_transient_strength:.2f}</p>
                </div>
                <div class="card">
                    <h4>Attack Quality</h4>
                    <p style="color: {attack_color}; font-weight: bold;">{analysis.transients.attack_quality.upper()}</p>
                </div>
            </div>
            <p style="margin-top: 10px; color: #666;">{analysis.transients.interpretation}</p>
            {transient_positions_html}
            '''

        # Spectral analysis section (NEW)
        spectral_html = f'''
        <h3 style="margin: 20px 0 15px;">Spectral Analysis</h3>
        <div class="grid">
            <div class="card">
                <h4>Spectral Centroid</h4>
                <p>{analysis.frequency.spectral_centroid_hz:.0f} Hz</p>
                <p style="font-size: 0.8em; color: #666;">Brightness indicator</p>
            </div>
            <div class="card">
                <h4>Spectral Rolloff</h4>
                <p>{analysis.frequency.spectral_rolloff_hz:.0f} Hz</p>
                <p style="font-size: 0.8em; color: #666;">High freq content ends</p>
            </div>
        </div>
        '''

        # Problem frequencies section (NEW)
        problem_freq_html = ""
        if analysis.frequency.problem_frequencies:
            problem_freq_html = '<h4 style="margin-top: 15px;">Problem Frequency Ranges:</h4><div style="margin-top: 10px;">'
            for start_hz, end_hz, issue_type in analysis.frequency.problem_frequencies:
                issue_color = {"excessive_energy": "#e74c3c", "lacking_energy": "#3498db", "buildup": "#f39c12"}.get(issue_type, "#666")
                problem_freq_html += f'''
                <div class="issue warning" style="margin: 5px 0; border-left-color: {issue_color};">
                    <strong>{start_hz:.0f}-{end_hz:.0f} Hz:</strong> {issue_type.replace('_', ' ').title()}
                </div>
                '''
            problem_freq_html += '</div>'

        # Streaming targets color coding
        def streaming_diff_color(diff):
            if abs(diff) <= 2:
                return "#27ae60"  # Good
            elif abs(diff) <= 4:
                return "#f39c12"  # Warning
            else:
                return "#e74c3c"  # Bad

        # Crest factor color
        crest_color = {"very_dynamic": "#3498db", "good": "#27ae60", "compressed": "#f39c12", "over_compressed": "#e74c3c"}.get(analysis.dynamics.crest_interpretation, "#666")

        return f'''
        <section class="section">
            <h2>Mix Analysis</h2>

            <h3 style="margin-bottom: 15px;">Issues Found</h3>
            {issues_html}

            {clipping_html}

            <h3 style="margin: 20px 0 15px;">Loudness (LUFS)</h3>
            <div class="grid">
                <div class="card">
                    <h4>Integrated LUFS</h4>
                    <p style="font-size: 1.4em; font-weight: bold;">{analysis.loudness.integrated_lufs:.1f}</p>
                </div>
                <div class="card">
                    <h4>Short-Term Max</h4>
                    <p>{analysis.loudness.short_term_max_lufs:.1f} LUFS</p>
                </div>
                <div class="card">
                    <h4>Momentary Max</h4>
                    <p>{analysis.loudness.momentary_max_lufs:.1f} LUFS</p>
                </div>
                <div class="card">
                    <h4>True Peak</h4>
                    <p>{analysis.loudness.true_peak_db:.1f} dBTP</p>
                </div>
                <div class="card">
                    <h4>Loudness Range</h4>
                    <p>{analysis.loudness.loudness_range_lu:.1f} LU</p>
                </div>
            </div>
            <div class="grid" style="margin-top: 15px;">
                <div class="card">
                    <h4>Spotify (-14 LUFS)</h4>
                    <p style="color: {streaming_diff_color(analysis.loudness.spotify_diff_db)}; font-weight: bold;">{analysis.loudness.spotify_diff_db:+.1f} dB</p>
                </div>
                <div class="card">
                    <h4>Apple Music (-16 LUFS)</h4>
                    <p style="color: {streaming_diff_color(analysis.loudness.apple_music_diff_db)}; font-weight: bold;">{analysis.loudness.apple_music_diff_db:+.1f} dB</p>
                </div>
                <div class="card">
                    <h4>YouTube (-14 LUFS)</h4>
                    <p style="color: {streaming_diff_color(analysis.loudness.youtube_diff_db)}; font-weight: bold;">{analysis.loudness.youtube_diff_db:+.1f} dB</p>
                </div>
            </div>

            <h3 style="margin: 20px 0 15px;">Dynamics / Crest Factor</h3>
            <div class="grid">
                <div class="card">
                    <h4>Peak Level</h4>
                    <p>{analysis.dynamics.peak_db:.1f} dBFS</p>
                </div>
                <div class="card">
                    <h4>RMS Level</h4>
                    <p>{analysis.dynamics.rms_db:.1f} dBFS</p>
                </div>
                <div class="card">
                    <h4>Crest Factor</h4>
                    <p style="color: {crest_color}; font-weight: bold;">{analysis.dynamics.crest_factor_db:.1f} dB ({analysis.dynamics.crest_interpretation})</p>
                </div>
                <div class="card">
                    <h4>Dynamic Range</h4>
                    <p>{analysis.dynamics.dynamic_range_db:.1f} dB</p>
                </div>
            </div>
            <p style="margin-top: 10px; color: #666;">{analysis.dynamics.recommended_action}</p>

            <h3 style="margin: 20px 0 15px;">Stereo / Phase</h3>
            <div class="grid">
                {stereo_html}
            </div>
            {f'<p style="margin-top: 10px; color: #666;">{analysis.stereo.recommended_width}</p>' if analysis.stereo.is_stereo and analysis.stereo.recommended_width else ''}

            {transients_html}

            {spectral_html}

            <h3 style="margin: 20px 0 15px;">Frequency Balance</h3>
            <div>
                <p>Bass (20-250Hz): {analysis.frequency.bass_energy:.1f}%</p>
                <div class="meter"><div class="meter-fill bass" style="width: {min(analysis.frequency.bass_energy, 100)}%"></div></div>

                <p style="margin-top: 10px;">Low-Mid (250-500Hz): {analysis.frequency.low_mid_energy:.1f}%</p>
                <div class="meter"><div class="meter-fill mid" style="width: {min(analysis.frequency.low_mid_energy * 3, 100)}%"></div></div>

                <p style="margin-top: 10px;">Mid (500-2kHz): {analysis.frequency.mid_energy:.1f}%</p>
                <div class="meter"><div class="meter-fill mid" style="width: {min(analysis.frequency.mid_energy, 100)}%"></div></div>

                <p style="margin-top: 10px;">High-Mid (2-6kHz): {analysis.frequency.high_mid_energy:.1f}%</p>
                <div class="meter"><div class="meter-fill high" style="width: {min(analysis.frequency.high_mid_energy * 2, 100)}%"></div></div>

                <p style="margin-top: 10px;">High (6-20kHz): {analysis.frequency.high_energy:.1f}%</p>
                <div class="meter"><div class="meter-fill high" style="width: {min(analysis.frequency.high_energy * 3, 100)}%"></div></div>
            </div>
            {problem_freq_html}
        </section>
        '''

    def _html_timeline_section(self, analysis: SectionAnalysisResult) -> str:
        """Generate HTML for timeline/section analysis."""
        duration = analysis.timeline_data.get('duration', 0)

        # Build visual timeline
        timeline_sections = ""
        for section in analysis.sections:
            left_pct = (section.start_time / duration) * 100 if duration > 0 else 0
            width_pct = ((section.end_time - section.start_time) / duration) * 100 if duration > 0 else 0
            severity_class = f"severity-{section.severity_summary}" if section.severity_summary != 'clean' else ''

            timeline_sections += f'''
            <div class="timeline-section {section.section_type} {severity_class}"
                 style="left: {left_pct}%; width: {width_pct}%;"
                 title="{self._format_time(section.start_time)}-{self._format_time(section.end_time)}: {section.section_type.upper()} ({section.severity_summary})">
                {section.section_type[:4].upper()}
            </div>
            '''

        # Time markers
        markers = []
        marker_count = min(6, int(duration / 30) + 1)
        for i in range(marker_count):
            time = (duration / (marker_count - 1)) * i if marker_count > 1 else 0
            markers.append(self._format_time(time))

        markers_html = ''.join([f'<span>{m}</span>' for m in markers])

        # Section details
        sections_html = ""
        for section in analysis.sections:
            issues_html = ""
            if section.issues:
                issues_html = '<div class="section-issues">'
                for issue in section.issues:
                    issues_html += f'<div class="section-issue">{issue.message}</div>'
                issues_html += '</div>'

            sections_html += f'''
            <div class="section-detail severity-{section.severity_summary}">
                <div class="section-header">
                    <div>
                        <span class="section-type">{section.section_type}</span>
                        <span class="section-time">{self._format_time(section.start_time)} - {self._format_time(section.end_time)}</span>
                    </div>
                    <span class="section-severity {section.severity_summary}">{section.severity_summary.upper()}</span>
                </div>
                <div class="grid" style="grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 10px;">
                    <div><strong>RMS:</strong> {section.avg_rms_db:.1f} dB</div>
                    <div><strong>Peak:</strong> {section.peak_db:.1f} dB</div>
                    <div><strong>Transients:</strong> {section.transient_density:.1f}/sec</div>
                    <div><strong>Brightness:</strong> {section.spectral_centroid_hz:.0f} Hz</div>
                </div>
                {issues_html}
            </div>
            '''

        # Clipping timestamps
        clipping_html = ""
        if analysis.clipping_timestamps:
            clip_times = [f'<span class="clip-time">{self._format_time(t)}</span>'
                         for t in analysis.clipping_timestamps[:30]]
            more_text = f'<span class="clip-time">+{len(analysis.clipping_timestamps) - 30} more</span>' if len(analysis.clipping_timestamps) > 30 else ''
            clipping_html = f'''
            <h3 style="margin: 20px 0 10px;">Clipping Timestamps ({len(analysis.clipping_timestamps)} total)</h3>
            <div class="clipping-list">
                {''.join(clip_times)}
                {more_text}
            </div>
            '''

        # Summary stats
        worst_section_html = ""
        if analysis.worst_section:
            worst_section_html = f'<div class="issue warning" style="margin-top: 15px;"><strong>Worst Section:</strong> {analysis.worst_section}</div>'

        return f'''
        <section class="section">
            <h2>Timeline Analysis</h2>

            <p style="margin-bottom: 15px;">{len(analysis.sections)} sections detected | Duration: {self._format_time(duration)}</p>

            <div class="timeline-container">
                <div class="timeline">
                    {timeline_sections}
                </div>
                <div class="timeline-markers">
                    {markers_html}
                </div>
            </div>

            {worst_section_html}

            <h3 style="margin: 20px 0 15px;">Section-by-Section Breakdown</h3>
            {sections_html}

            {clipping_html}
        </section>
        '''

    def _html_stem_section(self, analysis: StemAnalysisResult) -> str:
        """Generate HTML for stem analysis section with track filter and prioritized recommendations."""
        # Build track data for JavaScript with ALL metrics
        track_data = {}
        for stem in analysis.stems:
            pan_str = "Center" if abs(stem.panning) < 0.1 else f"{'Left' if stem.panning < 0 else 'Right'} {abs(stem.panning)*100:.0f}%"
            # Format dominant frequencies (convert numpy types to Python native)
            dom_freqs = []
            if stem.dominant_frequencies:
                dom_freqs = [{"freq": float(f[0]), "mag": float(f[1])} for f in stem.dominant_frequencies[:5]]
            # Convert frequency profile values to native Python floats
            freq_profile = {}
            if stem.frequency_profile:
                freq_profile = {k: float(v) for k, v in stem.frequency_profile.items()}
            track_data[stem.name] = {
                "peak_db": round(float(stem.peak_db), 1),
                "rms_db": round(float(stem.rms_db), 1),
                "panning": pan_str,
                "is_mono": bool(stem.is_mono),
                "dominant_frequencies": dom_freqs,
                "frequency_profile": freq_profile,
                "clashes": []
            }

        # Add clashes to track data
        for clash in analysis.clashes:
            freq_range = f"{clash.frequency_range[0]:.0f}-{clash.frequency_range[1]:.0f} Hz"
            if clash.stem1 in track_data:
                track_data[clash.stem1]["clashes"].append({
                    "other_track": clash.stem2,
                    "freq_range": freq_range,
                    "severity": clash.severity,
                    "recommendation": clash.recommendation
                })
            if clash.stem2 in track_data:
                track_data[clash.stem2]["clashes"].append({
                    "other_track": clash.stem1,
                    "freq_range": freq_range,
                    "severity": clash.severity,
                    "recommendation": clash.recommendation
                })

        # Count clashes by severity
        severe_count = sum(1 for c in analysis.clashes if c.severity == 'severe')
        moderate_count = sum(1 for c in analysis.clashes if c.severity == 'moderate')
        minor_count = sum(1 for c in analysis.clashes if c.severity == 'minor')

        # Build track selector options
        track_options = '<option value="all">-- Show All Tracks --</option>'
        # Sort stems by number of clashes (most problematic first)
        stems_by_clashes = sorted(analysis.stems, key=lambda s: len(track_data[s.name]["clashes"]), reverse=True)
        for stem in stems_by_clashes:
            clash_count = len(track_data[stem.name]["clashes"])
            severe_for_track = sum(1 for c in track_data[stem.name]["clashes"] if c["severity"] == "severe")
            indicator = "🔴" if severe_for_track > 0 else ("🟡" if clash_count > 5 else "🟢")
            track_options += f'<option value="{stem.name}">{indicator} {stem.name} ({clash_count} clashes)</option>'

        # Stem table
        stem_rows = ""
        for stem in analysis.stems:
            pan_str = "Center" if abs(stem.panning) < 0.1 else f"{'Left' if stem.panning < 0 else 'Right'} {abs(stem.panning)*100:.0f}%"
            clash_count = len(track_data[stem.name]["clashes"])
            severe_for_track = sum(1 for c in track_data[stem.name]["clashes"] if c["severity"] == "severe")

            # Color code based on issues
            row_class = ""
            if severe_for_track > 3:
                row_class = "clash-severe"
            elif clash_count > 10:
                row_class = "clash-moderate"

            stem_rows += f'''
            <tr class="{row_class}" style="cursor: pointer;" onclick="document.getElementById('track-select').value='{stem.name}'; filterByTrack('{stem.name}');">
                <td>{stem.name}</td>
                <td>{stem.peak_db:.1f} dB</td>
                <td>{stem.rms_db:.1f} dB</td>
                <td>{pan_str}</td>
                <td>{clash_count}</td>
            </tr>
            '''

        # Clashes table - sorted by severity
        sorted_clashes = sorted(analysis.clashes, key=lambda c: {'severe': 0, 'moderate': 1, 'minor': 2}[c.severity])
        clashes_html = ""
        if sorted_clashes:
            for clash in sorted_clashes[:100]:  # Limit to top 100 for performance
                css_class = f"clash-{clash.severity} clash-row"
                clashes_html += f'''
                <tr class="{css_class}" data-stem1="{clash.stem1}" data-stem2="{clash.stem2}">
                    <td>{clash.stem1}</td>
                    <td>{clash.stem2}</td>
                    <td>{clash.frequency_range[0]:.0f}-{clash.frequency_range[1]:.0f} Hz</td>
                    <td><span class="severity-badge {clash.severity}">{clash.severity.upper()}</span></td>
                    <td>{clash.recommendation}</td>
                </tr>
                '''
            if len(analysis.clashes) > 100:
                clashes_html += f'<tr><td colspan="5" style="text-align: center; color: #666;">... and {len(analysis.clashes) - 100} more clashes. Use the track filter above to see specific issues.</td></tr>'
        else:
            clashes_html = '<tr><td colspan="5">No significant frequency clashes detected.</td></tr>'

        # Executive summary for stems
        exec_summary = f'''
        <div class="exec-summary">
            <div class="summary-stat info">
                <div class="number">{len(analysis.stems)}</div>
                <div class="label">Total Stems</div>
            </div>
            <div class="summary-stat critical">
                <div class="number">{severe_count}</div>
                <div class="label">Severe Clashes</div>
            </div>
            <div class="summary-stat warning">
                <div class="number">{moderate_count}</div>
                <div class="label">Moderate Clashes</div>
            </div>
            <div class="summary-stat good">
                <div class="number">{minor_count}</div>
                <div class="label">Minor Clashes</div>
            </div>
        </div>
        '''

        # Priority fixes section - aggregate common issues
        priority_html = self._build_priority_fixes(analysis)

        return f'''
        <script>
            window.trackData = {json.dumps(track_data, cls=NumpyEncoder)};
        </script>

        <section class="section">
            <h2>Stem Analysis</h2>

            {exec_summary}

            <!-- Track Filter -->
            <div class="track-filter">
                <h3>🔍 Filter by Track</h3>
                <select id="track-select" onchange="filterByTrack(this.value)">
                    {track_options}
                </select>

                <div id="track-info" class="track-info">
                    <h4 id="track-name">Track Name</h4>
                    <div class="track-stats">
                        <div class="track-stat">
                            <div class="value" id="track-peak">-</div>
                            <div class="label">Peak</div>
                        </div>
                        <div class="track-stat">
                            <div class="value" id="track-rms">-</div>
                            <div class="label">RMS</div>
                        </div>
                        <div class="track-stat">
                            <div class="value" id="track-pan">-</div>
                            <div class="label">Panning</div>
                        </div>
                        <div class="track-stat">
                            <div class="value" id="track-mono">-</div>
                            <div class="label">Mono/Stereo</div>
                        </div>
                        <div class="track-stat">
                            <div class="value" id="track-clash-count">-</div>
                            <div class="label">Clashes</div>
                        </div>
                    </div>
                    <h4 style="margin-top: 15px;">Dominant Frequencies:</h4>
                    <div id="track-dominant-freqs" style="display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0;"></div>
                    <h4 style="margin-top: 15px;">Frequency Profile:</h4>
                    <div id="track-freq-profile" style="margin: 10px 0;"></div>
                    <h4 style="margin-top: 15px;">Frequency Clashes for This Track:</h4>
                    <div id="track-clashes-list" class="track-clashes"></div>
                </div>
            </div>

            {priority_html}

            <h3 style="margin-bottom: 15px;">All Stems ({len(analysis.stems)} total)</h3>
            <p style="color: #666; margin-bottom: 10px; font-size: 0.9em;">Click any row to filter clashes for that track</p>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Peak (dB)</th>
                        <th>RMS (dB)</th>
                        <th>Panning</th>
                        <th>Clashes</th>
                    </tr>
                </thead>
                <tbody>
                    {stem_rows}
                </tbody>
            </table>

            <h3 style="margin: 20px 0 15px;">Frequency Clashes ({len(analysis.clashes)} total)</h3>
            <table>
                <thead>
                    <tr>
                        <th>Stem 1</th>
                        <th>Stem 2</th>
                        <th>Frequency Range</th>
                        <th>Severity</th>
                        <th>Recommendation</th>
                    </tr>
                </thead>
                <tbody>
                    {clashes_html}
                </tbody>
            </table>
        </section>
        '''

    def _build_priority_fixes(self, analysis: StemAnalysisResult) -> str:
        """Build prioritized fix recommendations based on clash analysis."""
        if not analysis.clashes:
            return ""

        # Aggregate issues by frequency band and type
        freq_bands = {
            "sub_bass": (20, 80, "Sub Bass", []),
            "bass": (80, 250, "Bass", []),
            "low_mid": (250, 500, "Low Mid", []),
            "mid": (500, 2000, "Mid", []),
            "high_mid": (2000, 6000, "High Mid", []),
            "high": (6000, 20000, "High", [])
        }

        # Count clashes per track
        track_clash_counts = {}
        for clash in analysis.clashes:
            for track in [clash.stem1, clash.stem2]:
                if track not in track_clash_counts:
                    track_clash_counts[track] = {"severe": 0, "moderate": 0, "minor": 0, "total": 0}
                track_clash_counts[track][clash.severity] += 1
                track_clash_counts[track]["total"] += 1

        # Find most problematic tracks
        problematic_tracks = sorted(
            track_clash_counts.items(),
            key=lambda x: (x[1]["severe"] * 10 + x[1]["moderate"] * 3 + x[1]["minor"]),
            reverse=True
        )[:5]

        # Categorize clashes by frequency band
        for clash in analysis.clashes:
            center_freq = (clash.frequency_range[0] + clash.frequency_range[1]) / 2
            for band_key, (low, high, name, clashes_list) in freq_bands.items():
                if low <= center_freq < high:
                    clashes_list.append(clash)
                    break

        # Build priority items
        priority_items = []

        # Most problematic tracks
        for track, counts in problematic_tracks[:3]:
            if counts["severe"] > 0:
                priority = "critical"
                title = f"Fix '{track}' - {counts['severe']} severe clashes"
            elif counts["total"] > 10:
                priority = "high"
                title = f"Review '{track}' - {counts['total']} total clashes"
            else:
                continue

            priority_items.append({
                "priority": priority,
                "title": title,
                "detail": f"This track has significant frequency overlap with other elements. Consider EQ carving or reducing its presence.",
                "tracks": f"Severe: {counts['severe']}, Moderate: {counts['moderate']}, Minor: {counts['minor']}"
            })

        # Frequency band issues
        for band_key, (low, high, name, clashes_list) in freq_bands.items():
            severe_in_band = sum(1 for c in clashes_list if c.severity == 'severe')
            if severe_in_band > 5:
                priority_items.append({
                    "priority": "high",
                    "title": f"{name} frequency congestion ({low}-{high} Hz)",
                    "detail": f"{severe_in_band} severe clashes in this range. Multiple tracks competing for the same frequencies.",
                    "tracks": f"Apply high-pass filters or EQ cuts on non-essential elements in this range"
                })

        # Build HTML
        if not priority_items:
            return ""

        items_html = ""
        for i, item in enumerate(priority_items[:6], 1):
            items_html += f'''
            <div class="priority-item {item['priority']}">
                <div class="priority-number">{i}</div>
                <div class="priority-content">
                    <div class="priority-title">{item['title']}</div>
                    <div class="priority-detail">{item['detail']}</div>
                    <div class="priority-tracks">{item['tracks']}</div>
                </div>
            </div>
            '''

        return f'''
        <div class="priority-actions section">
            <h2>🎯 Priority Fixes</h2>
            <p style="margin-bottom: 15px; color: #666;">Address these issues first for the biggest improvement in mix clarity:</p>
            {items_html}
        </div>
        '''

    def _html_comparison_section(self, result: ComparisonResult) -> str:
        """Generate HTML for reference track comparison section."""
        # Build stem comparison cards
        stem_cards = ""
        for stem_name, comp in result.stem_comparisons.items():
            severity_class = {
                'good': 'severity-clean',
                'minor': 'severity-minor',
                'moderate': 'severity-moderate',
                'significant': 'severity-severe'
            }.get(comp.severity, '')

            severity_badge_class = {
                'good': 'clean',
                'minor': 'minor',
                'moderate': 'moderate',
                'significant': 'severe'
            }.get(comp.severity, 'minor')

            # Build recommendations list
            recs_html = ""
            if comp.recommendations:
                recs_html = '<div class="section-issues">'
                for rec in comp.recommendations[:3]:
                    recs_html += f'<div class="section-issue">{rec}</div>'
                recs_html += '</div>'

            # Determine diff indicators
            level_indicator = "OK" if abs(comp.rms_diff_db) < 2 else ("HIGH" if comp.rms_diff_db > 0 else "LOW")
            level_class = "good" if abs(comp.rms_diff_db) < 2 else "issue"

            # Additional metrics with safe access
            lufs_diff = getattr(comp, 'lufs_diff', 0) or 0
            centroid_diff = getattr(comp, 'spectral_centroid_diff_hz', 0) or 0
            dyn_range_diff = getattr(comp, 'dynamic_range_diff_db', 0) or 0
            low_mid_diff = getattr(comp, 'low_mid_diff_pct', 0) or 0
            mid_diff = getattr(comp, 'mid_diff_pct', 0) or 0
            high_mid_diff = getattr(comp, 'high_mid_diff_pct', 0) or 0

            stem_cards += f'''
            <div class="section-detail {severity_class}">
                <div class="section-header">
                    <div>
                        <span class="section-type">{stem_name}</span>
                    </div>
                    <span class="section-severity {severity_badge_class}">{comp.severity.upper()}</span>
                </div>
                <table style="width: 100%; margin-top: 10px;">
                    <tr>
                        <th>Metric</th>
                        <th>Your Mix</th>
                        <th>Reference</th>
                        <th>Difference</th>
                    </tr>
                    <tr>
                        <td>RMS Level</td>
                        <td>{comp.user_rms_db:.1f} dB</td>
                        <td>{comp.ref_rms_db:.1f} dB</td>
                        <td class="{level_class}">{comp.rms_diff_db:+.1f} dB</td>
                    </tr>
                    <tr>
                        <td>LUFS</td>
                        <td>{getattr(comp, 'user_lufs', 0) or 0:.1f}</td>
                        <td>{getattr(comp, 'ref_lufs', 0) or 0:.1f}</td>
                        <td>{lufs_diff:+.1f}</td>
                    </tr>
                    <tr>
                        <td>Spectral Centroid</td>
                        <td>{getattr(comp, 'user_spectral_centroid_hz', 0) or 0:.0f} Hz</td>
                        <td>{getattr(comp, 'ref_spectral_centroid_hz', 0) or 0:.0f} Hz</td>
                        <td>{centroid_diff:+.0f} Hz</td>
                    </tr>
                    <tr>
                        <td>Stereo Width</td>
                        <td>{comp.user_stereo_width_pct:.0f}%</td>
                        <td>{comp.ref_stereo_width_pct:.0f}%</td>
                        <td>{comp.stereo_width_diff_pct:+.0f}%</td>
                    </tr>
                    <tr>
                        <td>Dynamic Range</td>
                        <td colspan="2" style="text-align: center;">-</td>
                        <td>{dyn_range_diff:+.1f} dB</td>
                    </tr>
                </table>
                <h5 style="margin: 15px 0 10px;">Frequency Band Differences:</h5>
                <table style="width: 100%;">
                    <tr>
                        <td>Bass (20-250Hz)</td>
                        <td style="text-align: right; color: {'#e74c3c' if abs(comp.bass_diff_pct) > 8 else '#27ae60'};">{comp.bass_diff_pct:+.1f}%</td>
                    </tr>
                    <tr>
                        <td>Low-Mid (250-500Hz)</td>
                        <td style="text-align: right; color: {'#e74c3c' if abs(low_mid_diff) > 8 else '#27ae60'};">{low_mid_diff:+.1f}%</td>
                    </tr>
                    <tr>
                        <td>Mid (500-2kHz)</td>
                        <td style="text-align: right; color: {'#e74c3c' if abs(mid_diff) > 8 else '#27ae60'};">{mid_diff:+.1f}%</td>
                    </tr>
                    <tr>
                        <td>High-Mid (2-6kHz)</td>
                        <td style="text-align: right; color: {'#e74c3c' if abs(high_mid_diff) > 8 else '#27ae60'};">{high_mid_diff:+.1f}%</td>
                    </tr>
                    <tr>
                        <td>High (6-20kHz)</td>
                        <td style="text-align: right; color: {'#e74c3c' if abs(comp.high_diff_pct) > 8 else '#27ae60'};">{comp.high_diff_pct:+.1f}%</td>
                    </tr>
                </table>
                {recs_html}
            </div>
            '''

        # Priority recommendations
        priority_html = ""
        if result.priority_recommendations:
            priority_items = ""
            for i, rec in enumerate(result.priority_recommendations[:5], 1):
                priority_items += f'''
                <div class="recommendation">
                    <span class="number">{i}</span>
                    <span>{rec}</span>
                </div>
                '''
            priority_html = f'''
            <h3 style="margin: 20px 0 15px;">Priority Actions</h3>
            {priority_items}
            '''

        # Balance score color
        score = result.overall_balance_score
        if score >= 80:
            score_color = "#27ae60"
        elif score >= 60:
            score_color = "#f39c12"
        else:
            score_color = "#e74c3c"

        return f'''
        <section class="section">
            <h2>Reference Track Comparison</h2>

            <div class="comparison-header" style="display: flex; justify-content: space-between; align-items: center; padding: 20px; background: #f8f9fa; border-radius: 10px; margin-bottom: 20px;">
                <div>
                    <h4 style="margin-bottom: 5px;">Your Mix</h4>
                    <p style="color: #666;">{Path(result.user_file).name}</p>
                </div>
                <div style="background: #e94560; color: white; padding: 10px 20px; border-radius: 50%; font-weight: bold;">VS</div>
                <div style="text-align: right;">
                    <h4 style="margin-bottom: 5px;">Reference</h4>
                    <p style="color: #666;">{Path(result.reference_file).name}</p>
                </div>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <h3>Overall Balance Score</h3>
                <div style="display: inline-block; width: 120px; height: 120px; border-radius: 50%; background: {score_color}; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white; margin-top: 10px;">
                    <span style="font-size: 2.5em; font-weight: bold;">{score:.0f}</span>
                    <span style="font-size: 0.9em;">/100</span>
                </div>
            </div>

            <h3 style="margin: 20px 0 15px;">Stem-by-Stem Comparison</h3>
            {stem_cards}

            {priority_html}
        </section>
        '''

    def _html_recommendations_section(self, recommendations: List[str]) -> str:
        """Generate HTML for recommendations section."""
        recs_html = ""
        for i, rec in enumerate(recommendations, 1):
            recs_html += f'''
            <div class="recommendation">
                <span class="number">{i}</span>
                <span>{rec}</span>
            </div>
            '''

        return f'''
        <section class="section">
            <h2>Recommendations</h2>
            {recs_html}
        </section>
        '''

    def _html_mastering_section(self, result: MasteringResult) -> str:
        """Generate HTML for mastering section."""
        if result.success:
            status_class = "success"
            status_text = "Success"
            details = f'''
            <div class="grid">
                <div class="card">
                    <h4>Output File</h4>
                    <p>{Path(result.output_path).name}</p>
                </div>
                <div class="card">
                    <h4>Before LUFS</h4>
                    <p>{result.before_lufs:.1f if result.before_lufs else 'N/A'}</p>
                </div>
                <div class="card">
                    <h4>After LUFS</h4>
                    <p>{result.after_lufs:.1f if result.after_lufs else 'N/A'}</p>
                </div>
                <div class="card">
                    <h4>Reference LUFS</h4>
                    <p>{result.reference_lufs:.1f if result.reference_lufs else 'N/A'}</p>
                </div>
            </div>
            '''
        else:
            status_class = "error"
            status_text = "Failed"
            details = f'<div class="issue critical">{result.error_message}</div>'

        return f'''
        <section class="section">
            <h2>Mastering Results</h2>
            <p class="{status_class}" style="font-size: 1.2em; margin-bottom: 15px;">
                <strong>Status:</strong> {status_text}
            </p>
            {details}
        </section>
        '''

    def _generate_json_report(
        self,
        audio_analysis: Optional[AnalysisResult],
        stem_analysis: Optional[StemAnalysisResult],
        als_project: Optional[ALSProject],
        mastering_result: Optional[MasteringResult],
        section_analysis: Optional[SectionAnalysisResult],
        comparison_result: Optional[ComparisonResult],
        filename: str
    ) -> str:
        """Generate a JSON report for programmatic use."""
        data = {
            "generated": datetime.now().isoformat(),
            "version": "1.0"
        }

        if als_project:
            data["project"] = {
                "file": als_project.file_path,
                "version": als_project.ableton_version,
                "tempo": als_project.tempo,
                "time_signature": f"{als_project.time_signature_numerator}/{als_project.time_signature_denominator}",
                "duration_seconds": als_project.total_duration_seconds,
                "track_count": len(als_project.tracks),
                "midi_notes": als_project.midi_note_count,
                "audio_clips": als_project.audio_clip_count,
                "plugins": als_project.plugin_list
            }

        if audio_analysis:
            data["audio_analysis"] = {
                "file": audio_analysis.file_path,
                "duration": audio_analysis.duration_seconds,
                "sample_rate": audio_analysis.sample_rate,
                "channels": audio_analysis.channels,
                "detected_tempo": audio_analysis.detected_tempo,
                "dynamics": {
                    "peak_db": audio_analysis.dynamics.peak_db,
                    "rms_db": audio_analysis.dynamics.rms_db,
                    "dynamic_range_db": audio_analysis.dynamics.dynamic_range_db,
                    "crest_factor_db": audio_analysis.dynamics.crest_factor_db,
                    "crest_interpretation": audio_analysis.dynamics.crest_interpretation,
                    "recommended_action": audio_analysis.dynamics.recommended_action,
                    "is_over_compressed": audio_analysis.dynamics.is_over_compressed
                },
                "frequency": {
                    "spectral_centroid_hz": audio_analysis.frequency.spectral_centroid_hz,
                    "bass_energy_pct": audio_analysis.frequency.bass_energy,
                    "low_mid_energy_pct": audio_analysis.frequency.low_mid_energy,
                    "mid_energy_pct": audio_analysis.frequency.mid_energy,
                    "high_mid_energy_pct": audio_analysis.frequency.high_mid_energy,
                    "high_energy_pct": audio_analysis.frequency.high_energy,
                    "balance_issues": audio_analysis.frequency.balance_issues
                },
                "stereo": {
                    "is_stereo": audio_analysis.stereo.is_stereo,
                    "correlation": audio_analysis.stereo.correlation,
                    "width_pct": audio_analysis.stereo.width_estimate,
                    "width_category": audio_analysis.stereo.width_category,
                    "phase_safe": audio_analysis.stereo.phase_safe,
                    "is_mono_compatible": audio_analysis.stereo.is_mono_compatible,
                    "recommended_width": audio_analysis.stereo.recommended_width
                },
                "loudness": {
                    "integrated_lufs": audio_analysis.loudness.integrated_lufs,
                    "short_term_max_lufs": audio_analysis.loudness.short_term_max_lufs,
                    "momentary_max_lufs": audio_analysis.loudness.momentary_max_lufs,
                    "loudness_range_lu": audio_analysis.loudness.loudness_range_lu,
                    "true_peak_db": audio_analysis.loudness.true_peak_db,
                    "streaming_targets": {
                        "spotify_diff_db": audio_analysis.loudness.spotify_diff_db,
                        "apple_music_diff_db": audio_analysis.loudness.apple_music_diff_db,
                        "youtube_diff_db": audio_analysis.loudness.youtube_diff_db
                    },
                    "target_platform": audio_analysis.loudness.target_platform
                },
                "transients": {
                    "count": audio_analysis.transients.transient_count if audio_analysis.transients else 0,
                    "per_second": audio_analysis.transients.transients_per_second if audio_analysis.transients else 0,
                    "avg_strength": audio_analysis.transients.avg_transient_strength if audio_analysis.transients else 0,
                    "peak_strength": audio_analysis.transients.peak_transient_strength if audio_analysis.transients else 0,
                    "attack_quality": audio_analysis.transients.attack_quality if audio_analysis.transients else "unknown",
                    "interpretation": audio_analysis.transients.interpretation if audio_analysis.transients else ""
                } if audio_analysis.transients else None,
                "clipping": {
                    "has_clipping": audio_analysis.clipping.has_clipping,
                    "clip_count": audio_analysis.clipping.clip_count,
                    "max_peak": audio_analysis.clipping.max_peak
                },
                "issues": audio_analysis.overall_issues,
                "recommendations": audio_analysis.recommendations
            }

        if stem_analysis:
            data["stem_analysis"] = {
                "stem_count": len(stem_analysis.stems),
                "stems": [
                    {
                        "name": s.name,
                        "peak_db": s.peak_db,
                        "rms_db": s.rms_db,
                        "panning": s.panning,
                        "frequency_profile": s.frequency_profile
                    }
                    for s in stem_analysis.stems
                ],
                "clashes": [
                    {
                        "stem1": c.stem1,
                        "stem2": c.stem2,
                        "frequency_range": c.frequency_range,
                        "severity": c.severity,
                        "recommendation": c.recommendation
                    }
                    for c in stem_analysis.clashes
                ],
                "recommendations": stem_analysis.recommendations
            }

        if section_analysis:
            data["section_analysis"] = {
                "section_count": len(section_analysis.sections),
                "worst_section": section_analysis.worst_section,
                "clipping_timestamps": [
                    self._format_time(t) for t in section_analysis.clipping_timestamps
                ],
                "section_summary": section_analysis.section_summary,
                "sections": [
                    {
                        "type": s.section_type,
                        "start_time": s.start_time,
                        "end_time": s.end_time,
                        "start_formatted": self._format_time(s.start_time),
                        "end_formatted": self._format_time(s.end_time),
                        "avg_rms_db": s.avg_rms_db,
                        "peak_db": s.peak_db,
                        "transient_density": s.transient_density,
                        "spectral_centroid_hz": s.spectral_centroid_hz,
                        "severity": s.severity_summary,
                        "issues": [
                            {
                                "type": i.issue_type,
                                "start_time": i.start_time,
                                "end_time": i.end_time,
                                "severity": i.severity,
                                "message": i.message,
                                "details": i.details
                            }
                            for i in s.issues
                        ]
                    }
                    for s in section_analysis.sections
                ],
                "all_issues": [
                    {
                        "type": i.issue_type,
                        "start_time": i.start_time,
                        "end_time": i.end_time,
                        "start_formatted": self._format_time(i.start_time),
                        "end_formatted": self._format_time(i.end_time) if i.end_time else None,
                        "severity": i.severity,
                        "message": i.message
                    }
                    for i in section_analysis.all_issues
                ]
            }

        if comparison_result and comparison_result.success:
            data["comparison"] = {
                "user_file": comparison_result.user_file,
                "reference_file": comparison_result.reference_file,
                "overall_balance_score": comparison_result.overall_balance_score,
                "stem_comparisons": {
                    stem_name: {
                        "stem_type": comp.stem_type,
                        "user_rms_db": comp.user_rms_db,
                        "ref_rms_db": comp.ref_rms_db,
                        "rms_diff_db": comp.rms_diff_db,
                        "user_stereo_width_pct": comp.user_stereo_width_pct,
                        "ref_stereo_width_pct": comp.ref_stereo_width_pct,
                        "stereo_width_diff_pct": comp.stereo_width_diff_pct,
                        "bass_diff_pct": comp.bass_diff_pct,
                        "high_diff_pct": comp.high_diff_pct,
                        "severity": comp.severity,
                        "recommendations": comp.recommendations
                    }
                    for stem_name, comp in comparison_result.stem_comparisons.items()
                },
                "priority_recommendations": comparison_result.priority_recommendations
            }

        if mastering_result:
            data["mastering"] = {
                "success": mastering_result.success,
                "output_path": mastering_result.output_path,
                "before_lufs": mastering_result.before_lufs,
                "after_lufs": mastering_result.after_lufs,
                "error": mastering_result.error_message
            }

        # Write to file
        output_path = self.output_dir / f"{filename}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        return str(output_path)


def generate_report(
    audio_analysis: Optional[AnalysisResult] = None,
    stem_analysis: Optional[StemAnalysisResult] = None,
    section_analysis: Optional[SectionAnalysisResult] = None,
    project_name: str = "analysis",
    output_format: str = "html",
    output_dir: str = "./reports",
    version: str = "v1"
) -> str:
    """Quick function to generate a report."""
    generator = ReportGenerator(output_dir)
    return generator.generate_full_report(
        audio_analysis=audio_analysis,
        stem_analysis=stem_analysis,
        section_analysis=section_analysis,
        project_name=project_name,
        output_format=output_format,
        version=version
    )
