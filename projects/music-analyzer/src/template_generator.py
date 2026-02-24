"""
Arrangement Template Generator

Generates arrangement templates from:
1. Genre presets (Standard Trance, Extended Mix, Radio Edit)
2. Reference track analysis (extract structure from audio)

Templates can be customized and sent to Ableton Live via OSC.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

# Import structure detector for reference analysis
try:
    from .structure_detector import StructureDetector, SectionType
except ImportError:
    from structure_detector import StructureDetector, SectionType


# Section colors matching dashboard
SECTION_COLORS = {
    'intro': '#3b82f6',      # blue
    'buildup': '#f97316',    # orange
    'drop': '#ef4444',       # red
    'breakdown': '#8b5cf6',  # purple
    'outro': '#14b8a6',      # teal
    'unknown': '#6b7280',    # gray
}


@dataclass
class TemplateSection:
    """A section in an arrangement template."""
    section_type: str       # intro, buildup, drop, breakdown, outro
    bars: int               # Must be divisible by 8
    position_bars: int      # Starting position in bars (0-indexed)

    @property
    def color(self) -> str:
        """Get the color for this section type."""
        return SECTION_COLORS.get(self.section_type, SECTION_COLORS['unknown'])

    def duration_seconds(self, bpm: float) -> float:
        """Calculate duration in seconds based on BPM."""
        beats_per_bar = 4  # Assuming 4/4 time
        total_beats = self.bars * beats_per_bar
        return total_beats * (60.0 / bpm)

    def start_time(self, bpm: float) -> float:
        """Calculate start time in seconds."""
        beats_per_bar = 4
        total_beats = self.position_bars * beats_per_bar
        return total_beats * (60.0 / bpm)

    def end_time(self, bpm: float) -> float:
        """Calculate end time in seconds."""
        return self.start_time(bpm) + self.duration_seconds(bpm)

    def time_range_formatted(self, bpm: float) -> str:
        """Format time range as MM:SS - MM:SS."""
        start = self.start_time(bpm)
        end = self.end_time(bpm)
        return f"{int(start//60)}:{int(start%60):02d} - {int(end//60)}:{int(end%60):02d}"

    def to_dict(self, bpm: float = 138) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'section_type': self.section_type,
            'bars': self.bars,
            'position_bars': self.position_bars,
            'color': self.color,
            'start_time': round(self.start_time(bpm), 2),
            'end_time': round(self.end_time(bpm), 2),
            'duration': round(self.duration_seconds(bpm), 2),
            'time_range': self.time_range_formatted(bpm),
        }


@dataclass
class ArrangementTemplate:
    """Complete arrangement template."""
    name: str
    source: str             # "genre:standard_trance", "reference:filename.wav", "custom"
    bpm: float
    sections: List[TemplateSection] = field(default_factory=list)

    @property
    def total_bars(self) -> int:
        """Calculate total bars in template."""
        if not self.sections:
            return 0
        last_section = self.sections[-1]
        return last_section.position_bars + last_section.bars

    @property
    def total_duration(self) -> float:
        """Calculate total duration in seconds."""
        if not self.sections:
            return 0.0
        return self.sections[-1].end_time(self.bpm)

    @property
    def total_duration_formatted(self) -> str:
        """Format total duration as MM:SS."""
        duration = self.total_duration
        return f"{int(duration//60)}:{int(duration%60):02d}"

    def to_locators(self) -> List[Dict[str, Any]]:
        """Convert sections to locator data for Ableton."""
        locators = []
        for section in self.sections:
            locators.append({
                'name': section.section_type.upper(),
                'time_seconds': section.start_time(self.bpm),
                'time_beats': section.position_bars * 4,  # Assuming 4/4
                'color': section.color,
            })
        return locators

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'source': self.source,
            'bpm': self.bpm,
            'total_bars': self.total_bars,
            'total_duration': round(self.total_duration, 2),
            'total_duration_formatted': self.total_duration_formatted,
            'sections': [s.to_dict(self.bpm) for s in self.sections],
            'locators': self.to_locators(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArrangementTemplate':
        """Create template from dictionary."""
        sections = [
            TemplateSection(
                section_type=s['section_type'],
                bars=s['bars'],
                position_bars=s['position_bars']
            )
            for s in data.get('sections', [])
        ]
        return cls(
            name=data['name'],
            source=data['source'],
            bpm=data['bpm'],
            sections=sections
        )


# ============================================================================
# Genre Presets
# ============================================================================

GENRE_PRESETS = {
    'standard_trance': {
        'name': 'Standard Trance',
        'description': 'Classic trance structure with intro, double drop, and DJ-friendly outro',
        'default_bpm': 138,
        'sections': [
            {'type': 'intro', 'bars': 32},
            {'type': 'buildup', 'bars': 16},
            {'type': 'drop', 'bars': 32},
            {'type': 'breakdown', 'bars': 32},
            {'type': 'buildup', 'bars': 16},
            {'type': 'drop', 'bars': 32},
            {'type': 'outro', 'bars': 32},
        ]
    },
    'extended_mix': {
        'name': 'Extended Mix',
        'description': 'DJ-friendly extended version with longer intro/outro and extra breakdown',
        'default_bpm': 138,
        'sections': [
            {'type': 'intro', 'bars': 64},
            {'type': 'buildup', 'bars': 16},
            {'type': 'drop', 'bars': 32},
            {'type': 'breakdown', 'bars': 32},
            {'type': 'buildup', 'bars': 16},
            {'type': 'drop', 'bars': 32},
            {'type': 'breakdown', 'bars': 32},
            {'type': 'buildup', 'bars': 16},
            {'type': 'drop', 'bars': 32},
            {'type': 'outro', 'bars': 64},
        ]
    },
    'radio_edit': {
        'name': 'Radio Edit',
        'description': 'Short version for radio play (~3:30)',
        'default_bpm': 138,
        'sections': [
            {'type': 'intro', 'bars': 16},
            {'type': 'buildup', 'bars': 8},
            {'type': 'drop', 'bars': 32},
            {'type': 'breakdown', 'bars': 16},
            {'type': 'buildup', 'bars': 8},
            {'type': 'drop', 'bars': 32},
            {'type': 'outro', 'bars': 8},
        ]
    },
    'progressive': {
        'name': 'Progressive Trance',
        'description': 'Longer builds with extended sections for progressive style',
        'default_bpm': 132,
        'sections': [
            {'type': 'intro', 'bars': 64},
            {'type': 'buildup', 'bars': 32},
            {'type': 'drop', 'bars': 64},
            {'type': 'breakdown', 'bars': 64},
            {'type': 'buildup', 'bars': 32},
            {'type': 'drop', 'bars': 64},
            {'type': 'outro', 'bars': 32},
        ]
    },
}


class TemplateGenerator:
    """Generate arrangement templates from various sources."""

    def __init__(self, config: Dict = None):
        """Initialize the generator.

        Args:
            config: Optional config dict with trance_arrangement conventions
        """
        self.config = config or {}
        self.conventions = self.config.get('trance_arrangement', {})

    def get_preset_names(self) -> List[Dict[str, str]]:
        """List available genre presets with descriptions."""
        return [
            {
                'id': preset_id,
                'name': preset['name'],
                'description': preset['description'],
                'default_bpm': preset['default_bpm'],
            }
            for preset_id, preset in GENRE_PRESETS.items()
        ]

    def from_genre_preset(self, preset_name: str, bpm: float = None) -> ArrangementTemplate:
        """Generate template from built-in genre preset.

        Args:
            preset_name: Name of preset (e.g., 'standard_trance', 'extended_mix')
            bpm: Optional BPM override (uses preset default if not specified)

        Returns:
            ArrangementTemplate with sections based on preset
        """
        preset = GENRE_PRESETS.get(preset_name)
        if not preset:
            raise ValueError(f"Unknown preset: {preset_name}. Available: {list(GENRE_PRESETS.keys())}")

        bpm = bpm or preset['default_bpm']

        # Build sections with calculated positions
        sections = []
        position = 0
        for section_def in preset['sections']:
            sections.append(TemplateSection(
                section_type=section_def['type'],
                bars=section_def['bars'],
                position_bars=position
            ))
            position += section_def['bars']

        return ArrangementTemplate(
            name=preset['name'],
            source=f"genre:{preset_name}",
            bpm=bpm,
            sections=sections
        )

    def from_reference(self, audio_path: str) -> ArrangementTemplate:
        """Extract template from reference track structure.

        Args:
            audio_path: Path to audio file to analyze

        Returns:
            ArrangementTemplate based on detected structure
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Use structure detector
        detector = StructureDetector()
        structure = detector.detect(str(audio_path))

        if not structure.success or not structure.sections:
            raise ValueError(f"Could not detect structure in {audio_path.name}")

        # Convert detected sections to template sections
        sections = []
        for section in structure.sections:
            # Map SectionType enum to string
            section_type = section.section_type.value if hasattr(section.section_type, 'value') else str(section.section_type)

            sections.append(TemplateSection(
                section_type=section_type,
                bars=section.duration_bars,
                position_bars=int(section.start_time * structure.tempo_bpm / 60 / 4)  # Convert time to bars
            ))

        # Recalculate positions sequentially (in case of gaps)
        position = 0
        for section in sections:
            section.position_bars = position
            position += section.bars

        return ArrangementTemplate(
            name=f"From: {audio_path.name}",
            source=f"reference:{audio_path.name}",
            bpm=structure.tempo_bpm,
            sections=sections
        )

    def customize(self,
                  template: ArrangementTemplate,
                  bpm: float = None,
                  sections: List[Dict] = None,
                  name: str = None) -> ArrangementTemplate:
        """Apply customizations to a template.

        Args:
            template: Template to customize
            bpm: New BPM (optional)
            sections: New section list (optional)
            name: New name (optional)

        Returns:
            New ArrangementTemplate with customizations applied
        """
        new_bpm = bpm or template.bpm
        new_name = name or template.name
        new_source = "custom" if sections else template.source

        if sections:
            # Rebuild sections from provided data
            new_sections = []
            position = 0
            for section_data in sections:
                new_sections.append(TemplateSection(
                    section_type=section_data['section_type'],
                    bars=section_data['bars'],
                    position_bars=position
                ))
                position += section_data['bars']
        else:
            # Keep existing sections
            new_sections = template.sections

        return ArrangementTemplate(
            name=new_name,
            source=new_source,
            bpm=new_bpm,
            sections=new_sections
        )

    def add_section(self,
                    template: ArrangementTemplate,
                    section_type: str,
                    bars: int,
                    index: int = None) -> ArrangementTemplate:
        """Add a section to the template.

        Args:
            template: Template to modify
            section_type: Type of section to add
            bars: Number of bars for the section
            index: Position to insert (None = append to end)

        Returns:
            New ArrangementTemplate with section added
        """
        sections_data = [
            {'section_type': s.section_type, 'bars': s.bars}
            for s in template.sections
        ]

        new_section = {'section_type': section_type, 'bars': bars}

        if index is None:
            sections_data.append(new_section)
        else:
            sections_data.insert(index, new_section)

        return self.customize(template, sections=sections_data)

    def remove_section(self,
                       template: ArrangementTemplate,
                       index: int) -> ArrangementTemplate:
        """Remove a section from the template.

        Args:
            template: Template to modify
            index: Index of section to remove

        Returns:
            New ArrangementTemplate with section removed
        """
        sections_data = [
            {'section_type': s.section_type, 'bars': s.bars}
            for s in template.sections
        ]

        if 0 <= index < len(sections_data):
            sections_data.pop(index)

        return self.customize(template, sections=sections_data)

    def adjust_section_length(self,
                              template: ArrangementTemplate,
                              index: int,
                              delta_bars: int) -> ArrangementTemplate:
        """Adjust a section's length by delta bars.

        Args:
            template: Template to modify
            index: Index of section to adjust
            delta_bars: Change in bars (positive or negative, must result in multiple of 8)

        Returns:
            New ArrangementTemplate with section adjusted
        """
        sections_data = [
            {'section_type': s.section_type, 'bars': s.bars}
            for s in template.sections
        ]

        if 0 <= index < len(sections_data):
            new_bars = sections_data[index]['bars'] + delta_bars
            # Enforce minimum of 8 bars and multiple of 8
            new_bars = max(8, (new_bars // 8) * 8)
            sections_data[index]['bars'] = new_bars

        return self.customize(template, sections=sections_data)

    def reorder_sections(self,
                         template: ArrangementTemplate,
                         new_order: List[int]) -> ArrangementTemplate:
        """Reorder sections according to new indices.

        Args:
            template: Template to modify
            new_order: List of current indices in new order

        Returns:
            New ArrangementTemplate with sections reordered
        """
        sections_data = [
            {'section_type': s.section_type, 'bars': s.bars}
            for s in template.sections
        ]

        reordered = [sections_data[i] for i in new_order if 0 <= i < len(sections_data)]

        return self.customize(template, sections=reordered)


# ============================================================================
# Convenience Functions
# ============================================================================

def create_template(preset: str = 'standard_trance', bpm: float = 138) -> ArrangementTemplate:
    """Quick function to create a template from a preset.

    Args:
        preset: Preset name (standard_trance, extended_mix, radio_edit, progressive)
        bpm: Tempo in BPM

    Returns:
        ArrangementTemplate ready to use
    """
    generator = TemplateGenerator()
    return generator.from_genre_preset(preset, bpm)


def analyze_reference(audio_path: str) -> ArrangementTemplate:
    """Quick function to create a template from a reference track.

    Args:
        audio_path: Path to audio file

    Returns:
        ArrangementTemplate based on reference structure
    """
    generator = TemplateGenerator()
    return generator.from_reference(audio_path)


# ============================================================================
# Reference Overlay Comparison
# ============================================================================

@dataclass
class SectionAlignment:
    """Alignment between a user section and reference section."""
    user_section: Optional[TemplateSection]
    ref_section: Optional[TemplateSection]
    time_position: float  # Time in seconds where this alignment occurs
    status: str  # 'aligned', 'early', 'late', 'missing_user', 'missing_ref', 'type_mismatch'
    time_diff: float  # Difference in seconds (positive = user is late)
    message: str  # Human-readable description


@dataclass
class OverlayComparison:
    """Complete overlay comparison between user track and reference."""
    user_template: ArrangementTemplate
    ref_template: ArrangementTemplate
    alignments: List[SectionAlignment]

    # Summary stats
    overall_alignment_score: float  # 0-100
    avg_time_diff: float  # Average time difference in seconds
    sections_matched: int
    sections_missing: int
    sections_extra: int

    # Key insights
    insights: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'user_template': self.user_template.to_dict(),
            'ref_template': self.ref_template.to_dict(),
            'alignments': [
                {
                    'user_section': a.user_section.to_dict(self.user_template.bpm) if a.user_section else None,
                    'ref_section': a.ref_section.to_dict(self.ref_template.bpm) if a.ref_section else None,
                    'time_position': round(a.time_position, 2),
                    'status': a.status,
                    'time_diff': round(a.time_diff, 2),
                    'message': a.message
                }
                for a in self.alignments
            ],
            'overall_alignment_score': round(self.overall_alignment_score, 1),
            'avg_time_diff': round(self.avg_time_diff, 2),
            'sections_matched': self.sections_matched,
            'sections_missing': self.sections_missing,
            'sections_extra': self.sections_extra,
            'insights': self.insights
        }


class ReferenceOverlay:
    """Compare user's track arrangement against a reference track."""

    def __init__(self, tolerance_seconds: float = 5.0):
        """Initialize overlay comparator.

        Args:
            tolerance_seconds: How close sections need to be to be considered "aligned"
        """
        self.tolerance = tolerance_seconds

    def compare(self,
                user_template: ArrangementTemplate,
                ref_template: ArrangementTemplate) -> OverlayComparison:
        """Compare user template against reference template.

        Args:
            user_template: User's current arrangement
            ref_template: Reference track arrangement

        Returns:
            OverlayComparison with alignments and insights
        """
        alignments = []
        matched = 0
        missing = 0
        extra = 0
        total_diff = 0.0
        diff_count = 0

        # Track which reference sections have been matched
        ref_matched = [False] * len(ref_template.sections)

        # For each user section, find best matching reference section
        for user_section in user_template.sections:
            user_start = user_section.start_time(user_template.bpm)
            best_match = None
            best_diff = float('inf')
            best_idx = -1

            for idx, ref_section in enumerate(ref_template.sections):
                if ref_matched[idx]:
                    continue

                ref_start = ref_section.start_time(ref_template.bpm)
                diff = user_start - ref_start

                # Check if this is a potential match (same type, close in time)
                if abs(diff) < best_diff:
                    if user_section.section_type == ref_section.section_type:
                        best_match = ref_section
                        best_diff = abs(diff)
                        best_idx = idx

            if best_match and best_diff < 60:  # Within 60 seconds
                ref_matched[best_idx] = True
                time_diff = user_start - best_match.start_time(ref_template.bpm)

                if abs(time_diff) <= self.tolerance:
                    status = 'aligned'
                    message = f"{user_section.section_type.upper()} aligned with reference"
                    matched += 1
                elif time_diff > 0:
                    status = 'late'
                    message = f"{user_section.section_type.upper()} is {abs(time_diff):.1f}s late vs reference"
                else:
                    status = 'early'
                    message = f"{user_section.section_type.upper()} is {abs(time_diff):.1f}s early vs reference"

                total_diff += abs(time_diff)
                diff_count += 1

                alignments.append(SectionAlignment(
                    user_section=user_section,
                    ref_section=best_match,
                    time_position=user_start,
                    status=status,
                    time_diff=time_diff,
                    message=message
                ))
            else:
                # No match found - extra section in user
                extra += 1
                alignments.append(SectionAlignment(
                    user_section=user_section,
                    ref_section=None,
                    time_position=user_start,
                    status='missing_ref',
                    time_diff=0,
                    message=f"{user_section.section_type.upper()} not in reference"
                ))

        # Check for unmatched reference sections (missing in user)
        for idx, ref_section in enumerate(ref_template.sections):
            if not ref_matched[idx]:
                missing += 1
                ref_start = ref_section.start_time(ref_template.bpm)
                alignments.append(SectionAlignment(
                    user_section=None,
                    ref_section=ref_section,
                    time_position=ref_start,
                    status='missing_user',
                    time_diff=0,
                    message=f"Reference has {ref_section.section_type.upper()} at {self._format_time(ref_start)} - you don't"
                ))

        # Sort alignments by time
        alignments.sort(key=lambda a: a.time_position)

        # Calculate overall score
        total_sections = max(len(user_template.sections), len(ref_template.sections))
        if total_sections > 0:
            alignment_score = (matched / total_sections) * 100
            # Penalty for misalignment
            if diff_count > 0:
                avg_diff = total_diff / diff_count
                alignment_score *= max(0.5, 1 - (avg_diff / 30))  # Penalty increases with avg diff
        else:
            alignment_score = 0

        avg_time_diff = total_diff / diff_count if diff_count > 0 else 0

        # Generate insights
        insights = self._generate_insights(
            user_template, ref_template, alignments,
            matched, missing, extra, avg_time_diff
        )

        return OverlayComparison(
            user_template=user_template,
            ref_template=ref_template,
            alignments=alignments,
            overall_alignment_score=alignment_score,
            avg_time_diff=avg_time_diff,
            sections_matched=matched,
            sections_missing=missing,
            sections_extra=extra,
            insights=insights
        )

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        return f"{int(seconds // 60)}:{int(seconds % 60):02d}"

    def _generate_insights(self,
                          user: ArrangementTemplate,
                          ref: ArrangementTemplate,
                          alignments: List[SectionAlignment],
                          matched: int,
                          missing: int,
                          extra: int,
                          avg_diff: float) -> List[str]:
        """Generate actionable insights from the comparison."""
        insights = []

        # Duration comparison
        user_duration = user.total_duration
        ref_duration = ref.total_duration
        duration_diff = user_duration - ref_duration

        if abs(duration_diff) > 30:
            if duration_diff > 0:
                insights.append(f"Your track is {self._format_time(abs(duration_diff))} longer than reference")
            else:
                insights.append(f"Your track is {self._format_time(abs(duration_diff))} shorter than reference")

        # Missing sections
        missing_types = set()
        for a in alignments:
            if a.status == 'missing_user' and a.ref_section:
                missing_types.add(a.ref_section.section_type)

        if missing_types:
            insights.append(f"Missing sections: {', '.join(t.upper() for t in missing_types)}")

        # Timing issues
        late_sections = [a for a in alignments if a.status == 'late']
        early_sections = [a for a in alignments if a.status == 'early']

        if len(late_sections) > len(early_sections) and late_sections:
            avg_late = sum(a.time_diff for a in late_sections) / len(late_sections)
            insights.append(f"Sections tend to come {avg_late:.0f}s late - consider tightening arrangement")
        elif len(early_sections) > len(late_sections) and early_sections:
            avg_early = sum(abs(a.time_diff) for a in early_sections) / len(early_sections)
            insights.append(f"Sections tend to come {avg_early:.0f}s early - consider extending sections")

        # First drop timing
        user_drops = [s for s in user.sections if s.section_type == 'drop']
        ref_drops = [s for s in ref.sections if s.section_type == 'drop']

        if user_drops and ref_drops:
            user_first_drop = user_drops[0].start_time(user.bpm)
            ref_first_drop = ref_drops[0].start_time(ref.bpm)
            drop_diff = user_first_drop - ref_first_drop

            if abs(drop_diff) > 10:
                if drop_diff > 0:
                    insights.append(f"First drop is {abs(drop_diff):.0f}s later than reference")
                else:
                    insights.append(f"First drop is {abs(drop_diff):.0f}s earlier than reference")

        # Breakdown presence
        user_breakdowns = [s for s in user.sections if s.section_type == 'breakdown']
        ref_breakdowns = [s for s in ref.sections if s.section_type == 'breakdown']

        if ref_breakdowns and not user_breakdowns:
            ref_bd = ref_breakdowns[0]
            insights.append(f"Add a breakdown around {self._format_time(ref_bd.start_time(ref.bpm))}")

        # Overall assessment
        if matched == len(ref.sections) and avg_diff < 5:
            insights.insert(0, "Structure closely matches reference!")
        elif matched >= len(ref.sections) * 0.7:
            insights.insert(0, "Good structural similarity to reference")

        return insights


def compare_to_reference(user_audio: str, ref_audio: str) -> OverlayComparison:
    """Quick function to compare user track against reference.

    Args:
        user_audio: Path to user's audio file
        ref_audio: Path to reference audio file

    Returns:
        OverlayComparison with alignments and insights
    """
    generator = TemplateGenerator()
    user_template = generator.from_reference(user_audio)
    ref_template = generator.from_reference(ref_audio)

    overlay = ReferenceOverlay()
    return overlay.compare(user_template, ref_template)


# ============================================================================
# CLI Test
# ============================================================================

if __name__ == '__main__':
    import sys

    print("=== Template Generator Test ===\n")

    # Test genre preset
    generator = TemplateGenerator()

    print("Available presets:")
    for preset in generator.get_preset_names():
        print(f"  - {preset['id']}: {preset['name']} ({preset['default_bpm']} BPM)")

    print("\n--- Standard Trance Template ---")
    template = generator.from_genre_preset('standard_trance', bpm=140)
    print(f"Name: {template.name}")
    print(f"BPM: {template.bpm}")
    print(f"Total: {template.total_bars} bars ({template.total_duration_formatted})")
    print("\nSections:")
    for i, section in enumerate(template.sections):
        print(f"  {i+1}. {section.section_type.upper():12} | {section.bars:3} bars | {section.time_range_formatted(template.bpm)}")

    print("\nLocators:")
    for loc in template.to_locators():
        print(f"  {loc['name']:12} @ {loc['time_seconds']:.1f}s (beat {loc['time_beats']})")

    # Test customization
    print("\n--- After adding +8 bars to first drop ---")
    template = generator.adjust_section_length(template, 2, 8)
    print(f"Total: {template.total_bars} bars ({template.total_duration_formatted})")

    # Test reference if provided
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
        print(f"\n--- Reference Analysis: {audio_path} ---")
        try:
            ref_template = generator.from_reference(audio_path)
            print(f"Name: {ref_template.name}")
            print(f"BPM: {ref_template.bpm}")
            print(f"Total: {ref_template.total_bars} bars ({ref_template.total_duration_formatted})")
            print("\nSections:")
            for i, section in enumerate(ref_template.sections):
                print(f"  {i+1}. {section.section_type.upper():12} | {section.bars:3} bars")
        except Exception as e:
            print(f"Error: {e}")
