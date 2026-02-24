"""
XML Utilities for Ableton Live Set Manipulation

Provides safe ID management, Pointee reference tracking, and XML validation
for manipulating .als files without causing corruption.

Key concepts:
- Id: Unique identifier on most XML elements
- Pointee: Reference to another element's Id (creates dependency)
- PointeeId: Another reference type (Value attribute instead of Id)
- NextPointeeId: Counter in LiveSet that must exceed all used IDs
"""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass


@dataclass
class IdAnalysis:
    """Analysis of IDs and references in an Ableton Live Set."""
    all_ids: Set[str]
    referenced_ids: Set[str]  # IDs that Pointee/PointeeId elements point to
    max_numeric_id: int
    next_pointee_id: int
    duplicates: Dict[str, int]  # id -> count (for duplicates)


def load_als(path: Path) -> ET.Element:
    """Load and parse an Ableton Live Set file."""
    with gzip.open(path, 'rb') as f:
        content = f.read().decode('utf-8')
    return ET.fromstring(content)


def save_als(root: ET.Element, path: Path):
    """Save an Ableton Live Set file."""
    xml_str = ET.tostring(root, encoding='unicode')
    with gzip.open(path, 'wb') as f:
        f.write(xml_str.encode('utf-8'))


def analyze_ids(root: ET.Element) -> IdAnalysis:
    """
    Analyze all IDs and references in a Live Set.

    Returns IdAnalysis with:
    - all_ids: Set of all Id attribute values
    - referenced_ids: IDs that are referenced by Pointee/PointeeId elements
    - max_numeric_id: Highest numeric ID value
    - next_pointee_id: Value of NextPointeeId element
    - duplicates: Any duplicate IDs found
    """
    all_ids: Set[str] = set()
    id_counts: Dict[str, int] = {}
    max_numeric = 0

    # Collect all IDs
    for elem in root.iter():
        if 'Id' in elem.attrib:
            id_val = elem.attrib['Id']
            all_ids.add(id_val)
            id_counts[id_val] = id_counts.get(id_val, 0) + 1
            try:
                num_id = int(id_val)
                if num_id > max_numeric:
                    max_numeric = num_id
            except ValueError:
                pass

    # Collect referenced IDs (Pointee elements)
    referenced_ids: Set[str] = set()
    for elem in root.findall('.//Pointee'):
        if 'Id' in elem.attrib:
            referenced_ids.add(elem.attrib['Id'])

    # Collect PointeeId references (different format)
    for elem in root.findall('.//PointeeId'):
        if 'Value' in elem.attrib:
            referenced_ids.add(elem.attrib['Value'])

    # Get NextPointeeId
    next_id_elem = root.find('.//LiveSet/NextPointeeId')
    next_pointee_id = int(next_id_elem.get('Value')) if next_id_elem is not None else max_numeric + 1

    # Find duplicates
    duplicates = {k: v for k, v in id_counts.items() if v > 1}

    return IdAnalysis(
        all_ids=all_ids,
        referenced_ids=referenced_ids,
        max_numeric_id=max_numeric,
        next_pointee_id=next_pointee_id,
        duplicates=duplicates,
    )


def get_max_id(root: ET.Element) -> int:
    """Find the maximum numeric ID in the document."""
    max_id = 0
    for elem in root.iter():
        if 'Id' in elem.attrib:
            try:
                val = int(elem.attrib['Id'])
                if val > max_id:
                    max_id = val
            except ValueError:
                pass
    return max_id


def generate_safe_ids(count: int, analysis: IdAnalysis) -> List[int]:
    """
    Generate a list of safe, unique IDs that won't conflict.

    Args:
        count: Number of IDs needed
        analysis: IdAnalysis from analyze_ids()

    Returns:
        List of safe integer IDs starting from next_pointee_id
    """
    start = max(analysis.max_numeric_id, analysis.next_pointee_id) + 1
    return list(range(start, start + count))


def update_ids_in_element(elem: ET.Element, id_mapping: Dict[str, str]):
    """
    Update all IDs in an element tree using a mapping.

    Args:
        elem: Root element to update
        id_mapping: Dict mapping old_id -> new_id
    """
    for e in elem.iter():
        if 'Id' in e.attrib and e.attrib['Id'] in id_mapping:
            e.set('Id', id_mapping[e.attrib['Id']])


def update_ids_with_offset(elem: ET.Element, offset: int,
                           protected_ids: Set[str] = None) -> Dict[str, str]:
    """
    Update all numeric IDs in an element tree by adding an offset.

    Args:
        elem: Root element to update
        offset: Offset to add to each ID
        protected_ids: IDs that should NOT be modified (referenced by Pointees)

    Returns:
        Dict mapping old_id -> new_id for all updated IDs
    """
    protected = protected_ids or set()
    mapping = {}

    for e in elem.iter():
        if 'Id' in e.attrib:
            old_id = e.attrib['Id']
            if old_id in protected:
                continue
            try:
                old_val = int(old_id)
                new_val = old_val + offset
                new_id = str(new_val)
                mapping[old_id] = new_id
                e.set('Id', new_id)
            except ValueError:
                pass

    return mapping


def update_next_pointee_id(root: ET.Element, new_value: int):
    """Update the NextPointeeId in the LiveSet."""
    live_set = root.find('LiveSet')
    if live_set is None:
        return

    next_id = live_set.find('NextPointeeId')
    if next_id is not None:
        next_id.set('Value', str(new_value))


def set_track_name(track: ET.Element, name: str, color: int = None):
    """
    Set the track name and optionally color.

    Args:
        track: Track element (MidiTrack, AudioTrack, etc.)
        name: New track name
        color: Ableton color index (0-68), or None to keep existing
    """
    name_elem = track.find('.//Name')
    if name_elem is not None:
        eff = name_elem.find('EffectiveName')
        if eff is not None:
            eff.set('Value', name)
        user = name_elem.find('UserName')
        if user is not None:
            user.set('Value', name)

    if color is not None:
        color_elem = track.find('Color')
        if color_elem is not None:
            color_elem.set('Value', str(color))


def find_element_safe(root: ET.Element, path: str,
                      default: ET.Element = None) -> Optional[ET.Element]:
    """
    Safely find an element, returning default if not found.

    Args:
        root: Root element to search from
        path: XPath-like path to element
        default: Value to return if not found (default: None)
    """
    elem = root.find(path)
    return elem if elem is not None else default


@dataclass
class ValidationResult:
    """Result of validating an Ableton Live Set."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


def validate_als_structure(root: ET.Element) -> ValidationResult:
    """
    Validate an Ableton Live Set XML structure.

    Checks for:
    - Required elements present
    - NextPointeeId consistency
    - No orphaned Pointee references
    - Reasonable ID values

    Returns:
        ValidationResult with is_valid, errors, and warnings
    """
    errors = []
    warnings = []

    # Check root element
    if root.tag != 'Ableton':
        errors.append(f"Root element should be 'Ableton', found '{root.tag}'")

    # Check LiveSet exists
    live_set = root.find('LiveSet')
    if live_set is None:
        errors.append("Missing LiveSet element")
        return ValidationResult(False, errors, warnings)

    # Check required LiveSet children
    required_children = ['NextPointeeId', 'Tracks', 'MasterTrack']
    for child in required_children:
        if live_set.find(child) is None:
            errors.append(f"Missing required element: LiveSet/{child}")

    # Analyze IDs
    analysis = analyze_ids(root)

    # Check for duplicate IDs
    if analysis.duplicates:
        for dup_id, count in analysis.duplicates.items():
            warnings.append(f"Duplicate ID '{dup_id}' appears {count} times")

    # Check NextPointeeId consistency
    if analysis.next_pointee_id <= analysis.max_numeric_id:
        errors.append(
            f"NextPointeeId ({analysis.next_pointee_id}) <= max used ID ({analysis.max_numeric_id})"
        )

    # Check for orphaned Pointee references
    orphaned = analysis.referenced_ids - analysis.all_ids
    if orphaned:
        for orphan in orphaned:
            errors.append(f"Orphaned Pointee reference to non-existent ID: {orphan}")

    # Check tracks exist
    tracks_elem = live_set.find('Tracks')
    if tracks_elem is not None:
        midi_tracks = tracks_elem.findall('MidiTrack')
        audio_tracks = tracks_elem.findall('AudioTrack')
        if len(midi_tracks) == 0 and len(audio_tracks) == 0:
            warnings.append("No MIDI or Audio tracks found")

    is_valid = len(errors) == 0
    return ValidationResult(is_valid, errors, warnings)


def validate_als_file(path: Path) -> ValidationResult:
    """Load and validate an Ableton Live Set file."""
    try:
        root = load_als(path)
        return validate_als_structure(root)
    except Exception as e:
        return ValidationResult(False, [f"Failed to load file: {e}"], [])


def print_validation_result(result: ValidationResult, verbose: bool = True):
    """Print validation results in a readable format."""
    if result.is_valid:
        print("[OK] Live Set is valid")
    else:
        print("[FAIL] Live Set has errors")

    if result.errors:
        print("\nErrors:")
        for err in result.errors:
            print(f"  - {err}")

    if verbose and result.warnings:
        print("\nWarnings:")
        for warn in result.warnings:
            print(f"  - {warn}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate Ableton Live Set files")
    parser.add_argument("path", type=Path, help="Path to .als file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show warnings")
    parser.add_argument("--analyze", action="store_true", help="Show ID analysis")

    args = parser.parse_args()

    if not args.path.exists():
        print(f"File not found: {args.path}")
        exit(1)

    if args.analyze:
        root = load_als(args.path)
        analysis = analyze_ids(root)
        print(f"=== ID Analysis: {args.path.name} ===")
        print(f"Total IDs: {len(analysis.all_ids)}")
        print(f"Max numeric ID: {analysis.max_numeric_id}")
        print(f"NextPointeeId: {analysis.next_pointee_id}")
        print(f"Referenced IDs: {len(analysis.referenced_ids)}")
        print(f"Duplicates: {len(analysis.duplicates)}")
        if analysis.duplicates:
            print(f"  {list(analysis.duplicates.keys())[:10]}...")
        print()

    result = validate_als_file(args.path)
    print_validation_result(result, args.verbose)

    exit(0 if result.is_valid else 1)
