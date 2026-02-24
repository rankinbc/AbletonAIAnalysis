"""
JSON Output Module for ALS Doctor.

Provides structured JSON output for als_doctor diagnose command,
suitable for consumption by Claude Code and the DeviceResolver.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path


@dataclass
class DeviceInfo:
    """Device information for JSON output."""
    index: int
    name: str
    device_type: str
    category: str
    is_enabled: bool
    plugin_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            'index': self.index,
            'name': self.name,
            'device_type': self.device_type,
            'category': self.category,
            'is_enabled': self.is_enabled
        }
        if self.plugin_name:
            d['plugin_name'] = self.plugin_name
        return d


@dataclass
class TrackInfo:
    """Track information for JSON output."""
    index: int
    name: str
    track_type: str  # midi, audio, return, master, group
    volume_db: float
    pan: float
    is_muted: bool
    is_solo: bool
    devices: List[DeviceInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'name': self.name,
            'track_type': self.track_type,
            'volume_db': round(self.volume_db, 2),
            'pan': round(self.pan, 2),
            'is_muted': self.is_muted,
            'is_solo': self.is_solo,
            'device_count': len(self.devices),
            'devices': [d.to_dict() for d in self.devices]
        }


@dataclass
class IssueInfo:
    """Issue information for JSON output."""
    track_name: Optional[str]
    severity: str  # critical, warning, info
    category: str
    description: str
    fix_suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            'severity': self.severity,
            'category': self.category,
            'description': self.description
        }
        if self.track_name:
            d['track_name'] = self.track_name
        if self.fix_suggestion:
            d['fix_suggestion'] = self.fix_suggestion
        return d


@dataclass
class ALSDoctorJSON:
    """
    Complete JSON output from ALS Doctor diagnose.

    This structure is designed for:
    1. DeviceResolver - track/device names to indices mapping
    2. Claude Code - structured analysis results
    3. Reference integration - health metrics
    """
    # File info
    als_path: str
    als_filename: str
    song_name: str
    analyzed_at: str

    # Ableton project info
    ableton_version: str
    tempo: float

    # Health metrics
    health_score: int
    grade: str
    total_issues: int
    critical_issues: int
    warning_issues: int

    # Device stats
    total_devices: int
    disabled_devices: int
    clutter_percentage: float

    # Track and device structure (for DeviceResolver)
    tracks: List[TrackInfo] = field(default_factory=list)

    # Issues
    issues: List[IssueInfo] = field(default_factory=list)

    # Optional MIDI stats
    midi_stats: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            'version': '1.0',
            'file': {
                'als_path': self.als_path,
                'als_filename': self.als_filename,
                'song_name': self.song_name,
                'analyzed_at': self.analyzed_at
            },
            'project': {
                'ableton_version': self.ableton_version,
                'tempo': self.tempo
            },
            'health': {
                'score': self.health_score,
                'grade': self.grade,
                'total_issues': self.total_issues,
                'critical_issues': self.critical_issues,
                'warning_issues': self.warning_issues
            },
            'devices': {
                'total': self.total_devices,
                'disabled': self.disabled_devices,
                'clutter_percentage': round(self.clutter_percentage, 1)
            },
            'tracks': [t.to_dict() for t in self.tracks],
            'issues': [i.to_dict() for i in self.issues]
        }

        if self.midi_stats:
            d['midi'] = self.midi_stats

        return d

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str) -> None:
        """Save to JSON file."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())


def create_json_output(
    als_path: str,
    scan_result: Any,
    device_analysis: Any,
    midi_analysis: Any = None
) -> ALSDoctorJSON:
    """
    Create structured JSON output from ALS Doctor analysis.

    Args:
        als_path: Path to the .als file
        scan_result: ScanResult from _analyze_als_file
        device_analysis: ProjectDeviceAnalysis from device_chain_analyzer
        midi_analysis: Optional MIDIAnalysisResult

    Returns:
        ALSDoctorJSON object
    """
    file_path = Path(als_path)

    # Build track info with devices
    tracks = []
    for track in device_analysis.tracks:
        devices = []
        for device in track.devices:
            devices.append(DeviceInfo(
                index=device.index,
                name=device.name,
                device_type=device.device_type,
                category=device.category.value if hasattr(device.category, 'value') else str(device.category),
                is_enabled=device.is_enabled,
                plugin_name=device.plugin_name
            ))

        tracks.append(TrackInfo(
            index=track.track_index,
            name=track.track_name,
            track_type=track.track_type,
            volume_db=track.volume_db,
            pan=track.pan,
            is_muted=track.is_muted,
            is_solo=track.is_solo,
            devices=devices
        ))

    # Build issues list
    issues = []
    for issue in scan_result.issues:
        issues.append(IssueInfo(
            track_name=issue.track_name,
            severity=issue.severity,
            category=issue.category,
            description=issue.description,
            fix_suggestion=issue.fix_suggestion
        ))

    # Build MIDI stats if available
    midi_stats = None
    if midi_analysis:
        midi_stats = {
            'total_clips': midi_analysis.total_midi_clips,
            'total_notes': midi_analysis.total_notes,
            'empty_clips': midi_analysis.total_empty_clips,
            'short_clips': midi_analysis.total_short_clips,
            'duplicate_clips': midi_analysis.total_duplicate_clips
        }
        if midi_analysis.arrangement:
            midi_stats['arrangement'] = {
                'has_markers': midi_analysis.arrangement.has_arrangement_markers,
                'total_sections': midi_analysis.arrangement.total_sections,
                'structure': midi_analysis.arrangement.suggested_structure
            }

    return ALSDoctorJSON(
        als_path=str(file_path),
        als_filename=file_path.name,
        song_name=file_path.parent.name,
        analyzed_at=datetime.now().isoformat(),
        ableton_version=device_analysis.ableton_version,
        tempo=device_analysis.tempo,
        health_score=scan_result.health_score,
        grade=scan_result.grade,
        total_issues=scan_result.total_issues,
        critical_issues=scan_result.critical_issues,
        warning_issues=scan_result.warning_issues,
        total_devices=scan_result.total_devices,
        disabled_devices=scan_result.disabled_devices,
        clutter_percentage=scan_result.clutter_percentage,
        tracks=tracks,
        issues=issues,
        midi_stats=midi_stats
    )


def format_json_for_resolver(json_output: ALSDoctorJSON) -> Dict[str, Any]:
    """
    Format JSON output specifically for DeviceResolver.

    Returns a simplified structure optimized for device resolution.
    """
    return {
        'tracks': [
            {
                'index': t.index,
                'name': t.name,
                'type': t.track_type,
                'devices': [
                    {
                        'index': d.index,
                        'name': d.name,
                        'type': d.device_type
                    }
                    for d in t.devices
                ]
            }
            for t in json_output.tracks
        ]
    }
