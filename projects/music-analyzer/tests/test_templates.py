#!/usr/bin/env python3
"""
Tests for template comparison functionality (Story 2.5).
"""

import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime

# Add the src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

# Import directly from database module
import importlib.util
spec = importlib.util.spec_from_file_location('database', src_path / 'database.py')
database_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database_module)

# Template-related imports
list_templates = database_module.list_templates
get_template_by_name = database_module.get_template_by_name
add_template_from_file = database_module.add_template_from_file
remove_template = database_module.remove_template
compare_template = database_module.compare_template
ProjectTemplate = database_module.ProjectTemplate
TemplateComparisonResult = database_module.TemplateComparisonResult
TrackTemplate = database_module.TrackTemplate
DeviceChainTemplate = database_module.DeviceChainTemplate
_load_templates_index = database_module._load_templates_index
_save_templates_index = database_module._save_templates_index


def test_empty_templates_list(tmp_path):
    """list_templates should return empty list when no templates exist."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    templates, msg = list_templates(templates_path)

    assert templates == [], "Should return empty list"
    assert msg == "OK", f"Expected OK but got: {msg}"
    return True


def test_load_creates_index_if_missing(tmp_path):
    """_load_templates_index should create index.json if missing."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    index, msg = _load_templates_index(templates_path)

    assert index is not None, "Index should be created"
    assert 'templates' in index, "Index should have templates key"
    assert (templates_path / 'index.json').exists(), "index.json should be created"
    return True


def test_save_and_load_index(tmp_path):
    """_save_templates_index and _load_templates_index should work correctly."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    # Create test data
    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'test_template_1',
                'name': 'Test Template',
                'description': 'A test template',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 5,
                'total_devices': 10,
                'device_categories': {'eq': 3, 'compressor': 2},
                'tags': ['test']
            }
        ]
    }

    # Save
    success, msg = _save_templates_index(test_index, templates_path)
    assert success, f"Save should succeed: {msg}"

    # Load
    loaded, msg = _load_templates_index(templates_path)
    assert loaded is not None, f"Load should succeed: {msg}"
    assert len(loaded['templates']) == 1, "Should have 1 template"
    assert loaded['templates'][0]['name'] == 'Test Template'
    return True


def test_list_templates_with_data(tmp_path):
    """list_templates should return all templates."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    # Create test data
    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'Template One',
                'description': 'First template',
                'created_at': datetime.now().isoformat(),
                'tracks': [
                    {'track_type': 'midi', 'name_pattern': 'Kick', 'device_chain': []}
                ],
                'total_tracks': 1,
                'total_devices': 0,
                'device_categories': {},
                'tags': ['trance']
            },
            {
                'id': 'template_2',
                'name': 'Template Two',
                'description': 'Second template',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 5,
                'total_devices': 10,
                'device_categories': {'eq': 5},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    templates, msg = list_templates(templates_path)

    assert len(templates) == 2, f"Should have 2 templates, got {len(templates)}"
    assert templates[0].name == 'Template One'
    assert templates[1].name == 'Template Two'
    assert templates[0].total_tracks == 1
    assert templates[1].total_devices == 10
    return True


def test_get_template_by_name_exact(tmp_path):
    """get_template_by_name should find template by exact name."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'Trance Template',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    template, msg = get_template_by_name('Trance Template', templates_path)

    assert template is not None, f"Should find template: {msg}"
    assert template.name == 'Trance Template'
    return True


def test_get_template_by_name_case_insensitive(tmp_path):
    """get_template_by_name should be case insensitive."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'Trance Template',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    template, msg = get_template_by_name('trance template', templates_path)

    assert template is not None, f"Should find template: {msg}"
    assert template.name == 'Trance Template'
    return True


def test_get_template_by_name_partial(tmp_path):
    """get_template_by_name should find by partial match."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'Trance Mixdown Template',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    template, msg = get_template_by_name('mixdown', templates_path)

    assert template is not None, f"Should find template by partial match: {msg}"
    assert template.name == 'Trance Mixdown Template'
    return True


def test_get_template_by_id(tmp_path):
    """get_template_by_name should find by ID."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_abc123',
                'name': 'My Template',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    template, msg = get_template_by_name('template_abc123', templates_path)

    assert template is not None, f"Should find template by ID: {msg}"
    assert template.id == 'template_abc123'
    return True


def test_get_template_not_found(tmp_path):
    """get_template_by_name should return None for non-existent template."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'Existing Template',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    template, msg = get_template_by_name('Nonexistent', templates_path)

    assert template is None, "Should return None for non-existent template"
    assert 'not found' in msg.lower() or 'no template' in msg.lower()
    return True


def test_remove_template(tmp_path):
    """remove_template should remove template by name."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'To Remove',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            },
            {
                'id': 'template_2',
                'name': 'To Keep',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    success, msg = remove_template('To Remove', templates_path)

    assert success, f"Remove should succeed: {msg}"

    # Verify it's removed
    templates, _ = list_templates(templates_path)
    assert len(templates) == 1, "Should have 1 template left"
    assert templates[0].name == 'To Keep'
    return True


def test_remove_template_by_id(tmp_path):
    """remove_template should remove template by ID."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'remove_me_123',
                'name': 'Remove Me',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    success, msg = remove_template('remove_me_123', templates_path)

    assert success, f"Remove by ID should succeed: {msg}"

    templates, _ = list_templates(templates_path)
    assert len(templates) == 0, "Should have no templates left"
    return True


def test_remove_template_not_found(tmp_path):
    """remove_template should fail for non-existent template."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {'version': '1.0', 'templates': []}
    _save_templates_index(test_index, templates_path)

    success, msg = remove_template('Nonexistent', templates_path)

    assert not success, "Remove should fail for non-existent template"
    assert 'not found' in msg.lower()
    return True


def test_template_tracks_structure(tmp_path):
    """Templates should correctly parse track structure."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'With Tracks',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [
                    {
                        'track_type': 'midi',
                        'name_pattern': 'Kick',
                        'device_chain': [
                            {'device_type': 'Eq8', 'category': 'eq', 'name': 'Kick EQ'},
                            {'device_type': 'Compressor2', 'category': 'compressor', 'name': 'Kick Comp'}
                        ]
                    },
                    {
                        'track_type': 'audio',
                        'name_pattern': 'Vocal',
                        'device_chain': [
                            {'device_type': 'Eq8', 'category': 'eq'}
                        ]
                    }
                ],
                'total_tracks': 2,
                'total_devices': 3,
                'device_categories': {'eq': 2, 'compressor': 1},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    template, msg = get_template_by_name('With Tracks', templates_path)

    assert template is not None, f"Should find template: {msg}"
    assert len(template.tracks) == 2, "Should have 2 tracks"

    kick_track = template.tracks[0]
    assert kick_track.track_type == 'midi'
    assert kick_track.name_pattern == 'Kick'
    assert len(kick_track.device_chain) == 2
    assert kick_track.device_chain[0].device_type == 'Eq8'
    assert kick_track.device_chain[0].name == 'Kick EQ'

    vocal_track = template.tracks[1]
    assert vocal_track.track_type == 'audio'
    assert len(vocal_track.device_chain) == 1
    return True


def test_template_device_categories(tmp_path):
    """Templates should correctly track device categories."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'Categories',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 10,
                'total_devices': 50,
                'device_categories': {
                    'eq': 15,
                    'compressor': 10,
                    'reverb': 5,
                    'delay': 8,
                    'utility': 12
                },
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    template, msg = get_template_by_name('Categories', templates_path)

    assert template is not None
    assert template.device_categories['eq'] == 15
    assert template.device_categories['compressor'] == 10
    assert template.device_categories['reverb'] == 5
    return True


def test_template_tags(tmp_path):
    """Templates should correctly store and retrieve tags."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'Tagged Template',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': ['trance', 'mixdown', 'mastering']
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    template, msg = get_template_by_name('Tagged Template', templates_path)

    assert template is not None
    assert len(template.tags) == 3
    assert 'trance' in template.tags
    assert 'mixdown' in template.tags
    assert 'mastering' in template.tags
    return True


def test_add_template_file_not_found(tmp_path):
    """add_template_from_file should fail for non-existent file."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    template, msg = add_template_from_file(
        '/nonexistent/file.als',
        'Test',
        templates_path=templates_path
    )

    assert template is None, "Should fail for non-existent file"
    assert 'not found' in msg.lower()
    return True


def test_add_template_wrong_extension(tmp_path):
    """add_template_from_file should fail for non-.als file."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    # Create a non-.als file
    wrong_file = tmp_path / 'test.txt'
    wrong_file.write_text('not an als file')

    template, msg = add_template_from_file(
        str(wrong_file),
        'Test',
        templates_path=templates_path
    )

    assert template is None, "Should fail for non-.als file"
    assert '.als' in msg.lower()
    return True


def test_add_template_duplicate_name(tmp_path):
    """add_template_from_file should fail for duplicate name."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    # Create existing template
    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'existing_1',
                'name': 'My Template',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    # Try to add with same name (we'll use a fake .als that will fail to parse)
    fake_als = tmp_path / 'test.als'
    fake_als.write_bytes(b'not valid als')

    template, msg = add_template_from_file(
        str(fake_als),
        'My Template',
        templates_path=templates_path
    )

    # It will fail either due to duplicate name or parse error
    # Either way, we shouldn't have two templates with same name
    templates, _ = list_templates(templates_path)
    names = [t.name for t in templates]
    assert names.count('My Template') <= 1, "Should not allow duplicate names"
    return True


def test_compare_template_not_found(tmp_path):
    """compare_template should fail for non-existent template."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {'version': '1.0', 'templates': []}
    _save_templates_index(test_index, templates_path)

    # Create a dummy .als file
    als_file = tmp_path / 'test.als'
    als_file.write_bytes(b'not valid')

    result, msg = compare_template(str(als_file), 'Nonexistent', templates_path)

    assert result is None, "Should fail for non-existent template"
    assert 'no template' in msg.lower() or 'not found' in msg.lower()
    return True


def test_compare_template_file_not_found(tmp_path):
    """compare_template should fail for non-existent file."""
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()

    test_index = {
        'version': '1.0',
        'templates': [
            {
                'id': 'template_1',
                'name': 'Exists',
                'description': '',
                'created_at': datetime.now().isoformat(),
                'tracks': [],
                'total_tracks': 0,
                'total_devices': 0,
                'device_categories': {},
                'tags': []
            }
        ]
    }
    _save_templates_index(test_index, templates_path)

    result, msg = compare_template('/nonexistent/file.als', 'Exists', templates_path)

    assert result is None, "Should fail for non-existent file"
    assert 'not found' in msg.lower()
    return True


def run_tests():
    """Run all template tests."""
    import tempfile

    tests = [
        ('Empty templates list', test_empty_templates_list),
        ('Load creates index if missing', test_load_creates_index_if_missing),
        ('Save and load index', test_save_and_load_index),
        ('List templates with data', test_list_templates_with_data),
        ('Get template by exact name', test_get_template_by_name_exact),
        ('Get template case insensitive', test_get_template_by_name_case_insensitive),
        ('Get template partial match', test_get_template_by_name_partial),
        ('Get template by ID', test_get_template_by_id),
        ('Get template not found', test_get_template_not_found),
        ('Remove template', test_remove_template),
        ('Remove template by ID', test_remove_template_by_id),
        ('Remove template not found', test_remove_template_not_found),
        ('Template tracks structure', test_template_tracks_structure),
        ('Template device categories', test_template_device_categories),
        ('Template tags', test_template_tags),
        ('Add template file not found', test_add_template_file_not_found),
        ('Add template wrong extension', test_add_template_wrong_extension),
        ('Add template duplicate name', test_add_template_duplicate_name),
        ('Compare template not found', test_compare_template_not_found),
        ('Compare template file not found', test_compare_template_file_not_found),
    ]

    print("=" * 60)
    print("Template Tests (Story 2.5)")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                result = test_func(Path(tmp_dir))
                if result:
                    print(f"  ✓ {name}")
                    passed += 1
                else:
                    print(f"  ✗ {name} (returned False)")
                    failed += 1
        except Exception as e:
            print(f"  ✗ {name}")
            print(f"      Error: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
