"""
Reference Library - Store and retrieve analyzed reference track structures.

This module provides persistent storage for ArrangementTemplate objects,
allowing quick re-use of previously analyzed reference tracks without
needing to re-analyze the audio.
"""

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import template classes
try:
    from template_generator import ArrangementTemplate, TemplateSection
except ImportError:
    from src.template_generator import ArrangementTemplate, TemplateSection


@dataclass
class StoredReference:
    """A saved reference track structure."""
    id: str                        # Hash of original file path
    name: str                      # Display name (editable)
    original_path: str             # Where it was analyzed from
    bpm: float
    total_duration: float
    section_count: int
    sections: List[Dict]           # Serialized TemplateSection list
    tags: List[str] = field(default_factory=list)
    analyzed_at: str = ""          # ISO timestamp
    notes: str = ""                # User notes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'original_path': self.original_path,
            'bpm': self.bpm,
            'total_duration': round(self.total_duration, 2),
            'total_duration_formatted': self._format_duration(),
            'section_count': self.section_count,
            'sections': self.sections,
            'section_summary': self._section_summary(),
            'tags': self.tags,
            'analyzed_at': self.analyzed_at,
            'notes': self.notes
        }

    def _format_duration(self) -> str:
        """Format duration as MM:SS."""
        mins = int(self.total_duration // 60)
        secs = int(self.total_duration % 60)
        return f"{mins}:{secs:02d}"

    def _section_summary(self) -> str:
        """Create a short summary of sections like 'Intro → Build → Drop → ...'"""
        if not self.sections:
            return ""

        type_map = {
            'intro': 'Intro',
            'buildup': 'Build',
            'drop': 'Drop',
            'breakdown': 'Break',
            'outro': 'Outro',
            'unknown': '?'
        }

        parts = []
        for s in self.sections:
            section_type = s.get('section_type', 'unknown')
            parts.append(type_map.get(section_type, section_type.title()))

        return ' → '.join(parts)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StoredReference':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            original_path=data['original_path'],
            bpm=data['bpm'],
            total_duration=data['total_duration'],
            section_count=data['section_count'],
            sections=data['sections'],
            tags=data.get('tags', []),
            analyzed_at=data.get('analyzed_at', ''),
            notes=data.get('notes', '')
        )


class ReferenceLibrary:
    """Manage saved reference track structures."""

    STORAGE_FILE = 'structure_templates.json'
    VERSION = 1

    def __init__(self, storage_dir: str = None):
        """Initialize the reference library.

        Args:
            storage_dir: Directory for storing library data.
                        Defaults to 'reference_library' in project root.
        """
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            # Default to reference_library in project root
            self.storage_dir = Path(__file__).parent.parent / 'reference_library'

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / self.STORAGE_FILE
        self._ensure_index()

    def _ensure_index(self):
        """Ensure the index file exists with proper structure."""
        if not self.index_file.exists():
            self._save_index({
                'version': self.VERSION,
                'references': {},
                'last_updated': datetime.now().isoformat()
            })

    def _load_index(self) -> Dict[str, Any]:
        """Load the index file."""
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {
                'version': self.VERSION,
                'references': {},
                'last_updated': datetime.now().isoformat()
            }

    def _save_index(self, data: Dict[str, Any]):
        """Save the index file."""
        data['last_updated'] = datetime.now().isoformat()
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _generate_id(self, path: str) -> str:
        """Generate a unique ID from file path."""
        return hashlib.md5(path.encode()).hexdigest()[:12]

    def save_reference(self,
                       template: ArrangementTemplate,
                       name: str = None,
                       tags: List[str] = None,
                       notes: str = "") -> str:
        """Save a template to the library.

        Args:
            template: The ArrangementTemplate to save
            name: Display name (defaults to template.name)
            tags: Optional tags for filtering
            notes: Optional user notes

        Returns:
            The reference ID
        """
        # Generate ID from source path or name
        source = template.source
        if source.startswith('reference:'):
            original_path = source[10:]  # Remove 'reference:' prefix
        else:
            original_path = source

        ref_id = self._generate_id(original_path)

        # Serialize sections
        sections = []
        for section in template.sections:
            sections.append({
                'section_type': section.section_type,
                'bars': section.bars,
                'position_bars': section.position_bars,
                'color': section.color
            })

        # Create stored reference
        stored = StoredReference(
            id=ref_id,
            name=name or template.name,
            original_path=original_path,
            bpm=template.bpm,
            total_duration=template.total_duration,
            section_count=len(template.sections),
            sections=sections,
            tags=tags or [],
            analyzed_at=datetime.now().isoformat(),
            notes=notes
        )

        # Save to index
        index = self._load_index()
        index['references'][ref_id] = stored.to_dict()
        self._save_index(index)

        return ref_id

    def get_reference(self, ref_id: str) -> Optional[StoredReference]:
        """Get a stored reference by ID.

        Args:
            ref_id: The reference ID

        Returns:
            StoredReference or None if not found
        """
        index = self._load_index()
        ref_data = index['references'].get(ref_id)

        if ref_data:
            return StoredReference.from_dict(ref_data)
        return None

    def list_references(self, tag: str = None) -> List[StoredReference]:
        """List all references, optionally filtered by tag.

        Args:
            tag: Optional tag to filter by

        Returns:
            List of StoredReference objects
        """
        index = self._load_index()
        references = []

        for ref_data in index['references'].values():
            ref = StoredReference.from_dict(ref_data)
            if tag is None or tag in ref.tags:
                references.append(ref)

        # Sort by analyzed_at descending (newest first)
        references.sort(key=lambda r: r.analyzed_at, reverse=True)
        return references

    def delete_reference(self, ref_id: str) -> bool:
        """Remove a reference from the library.

        Args:
            ref_id: The reference ID

        Returns:
            True if deleted, False if not found
        """
        index = self._load_index()

        if ref_id in index['references']:
            del index['references'][ref_id]
            self._save_index(index)
            return True
        return False

    def update_reference(self,
                         ref_id: str,
                         name: str = None,
                         tags: List[str] = None,
                         notes: str = None) -> bool:
        """Update reference metadata.

        Args:
            ref_id: The reference ID
            name: New name (optional)
            tags: New tags (optional)
            notes: New notes (optional)

        Returns:
            True if updated, False if not found
        """
        index = self._load_index()

        if ref_id not in index['references']:
            return False

        ref_data = index['references'][ref_id]

        if name is not None:
            ref_data['name'] = name
        if tags is not None:
            ref_data['tags'] = tags
        if notes is not None:
            ref_data['notes'] = notes

        self._save_index(index)
        return True

    def to_template(self, ref_id: str, bpm: float = None) -> Optional[ArrangementTemplate]:
        """Convert stored reference back to ArrangementTemplate.

        Args:
            ref_id: The reference ID
            bpm: Optional BPM override (uses stored BPM if not provided)

        Returns:
            ArrangementTemplate or None if not found
        """
        ref = self.get_reference(ref_id)
        if not ref:
            return None

        effective_bpm = bpm or ref.bpm

        # Reconstruct sections
        sections = []
        for s in ref.sections:
            sections.append(TemplateSection(
                section_type=s['section_type'],
                bars=s['bars'],
                position_bars=s['position_bars']
            ))

        return ArrangementTemplate(
            name=ref.name,
            source=f"library:{ref_id}",
            bpm=effective_bpm,
            sections=sections
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get library statistics.

        Returns:
            Dictionary with count, tags, BPM range, etc.
        """
        references = self.list_references()

        if not references:
            return {
                'count': 0,
                'tags': [],
                'bpm_range': None,
                'duration_range': None
            }

        all_tags = set()
        bpms = []
        durations = []

        for ref in references:
            all_tags.update(ref.tags)
            bpms.append(ref.bpm)
            durations.append(ref.total_duration)

        return {
            'count': len(references),
            'tags': sorted(list(all_tags)),
            'bpm_range': {'min': min(bpms), 'max': max(bpms)},
            'duration_range': {
                'min': min(durations),
                'max': max(durations),
                'min_formatted': f"{int(min(durations)//60)}:{int(min(durations)%60):02d}",
                'max_formatted': f"{int(max(durations)//60)}:{int(max(durations)%60):02d}"
            }
        }


# Convenience functions
def get_library() -> ReferenceLibrary:
    """Get the default reference library instance."""
    return ReferenceLibrary()


def save_to_library(template: ArrangementTemplate,
                    name: str = None,
                    tags: List[str] = None) -> str:
    """Quick save a template to the library."""
    library = get_library()
    return library.save_reference(template, name=name, tags=tags)


def load_from_library(ref_id: str, bpm: float = None) -> Optional[ArrangementTemplate]:
    """Quick load a template from the library."""
    library = get_library()
    return library.to_template(ref_id, bpm=bpm)
