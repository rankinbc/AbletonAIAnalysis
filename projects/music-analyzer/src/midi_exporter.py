"""
MIDI Exporter

Exports MIDI data to standard .mid files.
Uses midiutil library for MIDI file creation.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from midiutil import MIDIFile
    MIDIUTIL_AVAILABLE = True
except ImportError:
    MIDIUTIL_AVAILABLE = False

try:
    from als_parser import MIDINote, MIDIClip
except ImportError:
    from src.als_parser import MIDINote, MIDIClip


@dataclass
class ExportResult:
    """Result of a MIDI export operation."""
    success: bool
    file_path: str
    message: str
    note_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'file_path': self.file_path,
            'message': self.message,
            'note_count': self.note_count
        }


class MIDIExporter:
    """Export MIDI data to standard .mid files."""

    def __init__(self, default_tempo: float = 120.0):
        """Initialize the exporter.

        Args:
            default_tempo: Default tempo in BPM if not specified
        """
        self.default_tempo = default_tempo

        if not MIDIUTIL_AVAILABLE:
            raise ImportError(
                "midiutil library not available. Install with: pip install midiutil"
            )

    def export_notes(self, notes: List[MIDINote],
                     output_path: str,
                     tempo: float = None,
                     track_name: str = "Track 1") -> ExportResult:
        """Export a list of notes to a MIDI file.

        Args:
            notes: List of MIDINote objects
            output_path: Path for the output .mid file
            tempo: Tempo in BPM (uses default if not specified)
            track_name: Name for the MIDI track

        Returns:
            ExportResult with success status and file path
        """
        if not notes:
            return ExportResult(
                success=False,
                file_path="",
                message="No notes to export"
            )

        tempo = tempo or self.default_tempo

        try:
            # Create MIDI file with 1 track
            midi = MIDIFile(1)
            track = 0
            channel = 0
            time = 0  # Start at beat 0

            # Set tempo and track name
            midi.addTempo(track, time, tempo)
            midi.addTrackName(track, time, track_name)

            # Add all notes
            for note in notes:
                if not note.mute:
                    midi.addNote(
                        track=track,
                        channel=channel,
                        pitch=note.pitch,
                        time=note.start_time,
                        duration=note.duration,
                        volume=note.velocity
                    )

            # Ensure output directory exists
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            with open(output_path, 'wb') as f:
                midi.writeFile(f)

            return ExportResult(
                success=True,
                file_path=str(output_path),
                message=f"Exported {len(notes)} notes to {output_path.name}",
                note_count=len(notes)
            )

        except Exception as e:
            return ExportResult(
                success=False,
                file_path="",
                message=f"Export failed: {str(e)}"
            )

    def export_clip(self, clip: MIDIClip,
                    output_path: str,
                    tempo: float = None) -> ExportResult:
        """Export a MIDI clip to a file.

        Args:
            clip: MIDIClip object to export
            output_path: Path for the output .mid file
            tempo: Tempo in BPM

        Returns:
            ExportResult with success status and file path
        """
        return self.export_notes(
            notes=clip.notes,
            output_path=output_path,
            tempo=tempo,
            track_name=clip.name
        )

    def export_clips(self, clips: List[MIDIClip],
                     output_dir: str,
                     tempo: float = None,
                     single_file: bool = False) -> List[ExportResult]:
        """Export multiple clips to MIDI files.

        Args:
            clips: List of MIDIClip objects
            output_dir: Directory for output files
            tempo: Tempo in BPM
            single_file: If True, combine all clips into one multi-track file

        Returns:
            List of ExportResult objects
        """
        if not clips:
            return []

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        tempo = tempo or self.default_tempo

        if single_file:
            return [self._export_clips_combined(clips, output_dir, tempo)]
        else:
            return self._export_clips_separate(clips, output_dir, tempo)

    def _export_clips_separate(self, clips: List[MIDIClip],
                               output_dir: Path,
                               tempo: float) -> List[ExportResult]:
        """Export each clip to a separate file."""
        results = []

        for i, clip in enumerate(clips):
            # Sanitize filename
            safe_name = self._sanitize_filename(clip.name or f"clip_{i}")
            output_path = output_dir / f"{safe_name}.mid"

            # Handle duplicates
            counter = 1
            while output_path.exists():
                output_path = output_dir / f"{safe_name}_{counter}.mid"
                counter += 1

            result = self.export_clip(clip, str(output_path), tempo)
            results.append(result)

        return results

    def _export_clips_combined(self, clips: List[MIDIClip],
                               output_dir: Path,
                               tempo: float) -> ExportResult:
        """Export all clips to a single multi-track file."""
        try:
            # Create MIDI file with multiple tracks
            midi = MIDIFile(len(clips))
            channel = 0
            time = 0

            total_notes = 0

            for track, clip in enumerate(clips):
                midi.addTempo(track, time, tempo)
                midi.addTrackName(track, time, clip.name or f"Track {track + 1}")

                for note in clip.notes:
                    if not note.mute:
                        midi.addNote(
                            track=track,
                            channel=channel,
                            pitch=note.pitch,
                            time=note.start_time,
                            duration=note.duration,
                            volume=note.velocity
                        )
                        total_notes += 1

            output_path = output_dir / "combined_clips.mid"
            with open(output_path, 'wb') as f:
                midi.writeFile(f)

            return ExportResult(
                success=True,
                file_path=str(output_path),
                message=f"Exported {len(clips)} clips ({total_notes} notes) to combined file",
                note_count=total_notes
            )

        except Exception as e:
            return ExportResult(
                success=False,
                file_path="",
                message=f"Combined export failed: {str(e)}"
            )

    def export_to_bytes(self, notes: List[MIDINote],
                        tempo: float = None,
                        track_name: str = "Track 1") -> Optional[bytes]:
        """Export notes to MIDI data in memory.

        Args:
            notes: List of MIDINote objects
            tempo: Tempo in BPM
            track_name: Name for the MIDI track

        Returns:
            MIDI file data as bytes, or None on failure
        """
        if not notes:
            return None

        tempo = tempo or self.default_tempo

        try:
            midi = MIDIFile(1)
            track = 0
            channel = 0
            time = 0

            midi.addTempo(track, time, tempo)
            midi.addTrackName(track, time, track_name)

            for note in notes:
                if not note.mute:
                    midi.addNote(
                        track=track,
                        channel=channel,
                        pitch=note.pitch,
                        time=note.start_time,
                        duration=note.duration,
                        volume=note.velocity
                    )

            # Write to temporary file and read bytes
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mid') as f:
                temp_path = f.name
                midi.writeFile(f)

            with open(temp_path, 'rb') as f:
                data = f.read()

            os.unlink(temp_path)
            return data

        except Exception:
            return None

    def _sanitize_filename(self, name: str) -> str:
        """Remove invalid characters from filename."""
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        # Limit length
        return name[:50].strip()


def export_clip_to_midi(clip: MIDIClip,
                        output_path: str,
                        tempo: float = 120.0) -> ExportResult:
    """Convenience function to export a clip to MIDI.

    Args:
        clip: MIDIClip to export
        output_path: Output file path
        tempo: Tempo in BPM

    Returns:
        ExportResult with status
    """
    try:
        exporter = MIDIExporter(default_tempo=tempo)
        return exporter.export_clip(clip, output_path, tempo)
    except ImportError as e:
        return ExportResult(
            success=False,
            file_path="",
            message=str(e)
        )


def export_notes_to_midi(notes: List[MIDINote],
                         output_path: str,
                         tempo: float = 120.0,
                         track_name: str = "Exported") -> ExportResult:
    """Convenience function to export notes to MIDI.

    Args:
        notes: List of MIDINote objects
        output_path: Output file path
        tempo: Tempo in BPM
        track_name: Track name

    Returns:
        ExportResult with status
    """
    try:
        exporter = MIDIExporter(default_tempo=tempo)
        return exporter.export_notes(notes, output_path, tempo, track_name)
    except ImportError as e:
        return ExportResult(
            success=False,
            file_path="",
            message=str(e)
        )
