"""
Ableton Project Assembly

Generates complete Ableton Live projects with:
- .als file with configured tracks
- MIDI files for each track
- Arrangement markers for song structure
"""

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
import copy
import json
from typing import Dict, List, Optional
from datetime import datetime

from config import Config, DEFAULT_CONFIG
from song_spec import SongSpec, SectionSpec, TrackSpec, SectionType, create_default_trance_spec
from midi_generator import MIDIGenerator, GeneratorConfig
from melody_generator import MelodyGenerator, ArpGeneratorWrapper
from transition_generator import TransitionGenerator, TransitionType
from xml_utils import (
    analyze_ids, generate_safe_ids, update_ids_with_offset,
    update_next_pointee_id, set_track_name, validate_als_structure,
    IdAnalysis, ValidationResult
)
from clip_embedder import ClipEmbedder
from device_library import add_devices_to_template

# Default features (always included)
from texture_midi_export import generate_textures_for_song
from stem_arranger import StemArranger, GENRE_TEMPLATES


class AbletonProject:
    """Generates complete Ableton Live projects."""

    # Track colors (Ableton color palette indices)
    TRACK_COLORS = {
        "kick": 69,   # Red
        "bass": 20,   # Orange
        "perc": 26,   # Yellow-Orange
        "chords": 15, # Green
        "pad": 15,    # Green
        "lead": 3,    # Cyan
        "arp": 13,    # Blue
        "hats": 26,   # Yellow-Orange
        "clap": 26,   # Yellow-Orange
        "fx": 60,     # Purple
        "vox": 8,     # Pink
        # Texture tracks
        "riser": 60,      # Purple
        "impact": 69,     # Red
        "atmosphere": 8,  # Pink
        "texture": 60,    # Purple
    }

    def __init__(self, spec: SongSpec, config: Config = None,
                 create_tracks: bool = False, embed_midi: bool = False,
                 add_devices: bool = False,
                 enable_textures: bool = True, enable_stem_arranger: bool = True,
                 enable_sidechain: bool = False, enable_sends: bool = False,
                 enable_mix_templates: bool = False, enable_vst_presets: bool = False):
        self.spec = spec
        self.config = config or DEFAULT_CONFIG
        self.output_dir = self.config.get_output_dir(spec.name)
        self.midi_dir = self.config.get_midi_dir(spec.name)
        self.create_tracks = create_tracks  # Whether to create/rename tracks in .als
        self.embed_midi = embed_midi  # Whether to embed MIDI clips in .als
        self.add_devices = add_devices  # Whether to add instrument devices to tracks

        # Default features (included by default)
        self.enable_textures = enable_textures
        self.enable_stem_arranger = enable_stem_arranger

        # Optional mixing features (disabled by default)
        self.enable_sidechain = enable_sidechain
        self.enable_sends = enable_sends
        self.enable_mix_templates = enable_mix_templates
        self.enable_vst_presets = enable_vst_presets

        # Clip splitting
        self.split_sections = False  # Set via set_split_sections()

        # Initialize generators
        self.midi_gen = MIDIGenerator(GeneratorConfig(
            key=spec.key,
            scale=spec.scale,
            tempo=spec.tempo,
            ticks_per_beat=self.config.TICKS_PER_BEAT
        ))
        self.melody_gen = MelodyGenerator(
            key=spec.key,
            scale=spec.scale,
            tempo=spec.tempo,
            config=self.config
        )

        # Chord-aware arp generator (uses new melody-generation system)
        self.arp_gen = ArpGeneratorWrapper(
            key=spec.key,
            scale=spec.scale,
            tempo=spec.tempo,
        )
        self.transition_gen = TransitionGenerator(
            tempo=spec.tempo,
            ticks_per_beat=self.config.TICKS_PER_BEAT
        )

        # Initialize stem arranger if enabled
        if self.enable_stem_arranger:
            genre = spec.genre.lower()
            self.stem_arranger = StemArranger(genre=genre)
        else:
            self.stem_arranger = None

    def generate(self) -> Path:
        """
        Generate complete project.

        Returns:
            Path to .als file
        """
        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.midi_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nGenerating project: {self.spec.name}")
        print(f"Output directory: {self.output_dir}")

        # Apply stem arrangement to update active_tracks per section
        if self.enable_stem_arranger:
            self._apply_stem_arrangement()
            print("Applied stem arrangement")

        # Generate all MIDI files
        midi_files = self._generate_all_midi()
        print(f"Generated {len(midi_files)} MIDI files")

        # Generate texture MIDI files (default feature)
        if self.enable_textures:
            texture_files = self._generate_textures()
            print(f"Generated {len(texture_files)} texture files")

        # Generate optional mixing configuration
        mix_config = self._generate_mix_config()
        if mix_config:
            print(f"Generated mixing configuration")

        # Generate .als file
        als_path = self._generate_als()
        print(f"Generated: {als_path.name}")

        # Save spec for reference
        self._save_spec()
        print("Saved song_spec.json")

        return als_path

    def _apply_stem_arrangement(self):
        """Apply stem arranger to update active_tracks per section."""
        if not self.stem_arranger:
            return

        # Get available stem names from tracks
        available_stems = [t.name.lower() for t in self.spec.tracks]

        # Update each section's active_tracks based on stem arranger
        for section in self.spec.structure:
            active_stems = self.stem_arranger.get_stems_for_section(section, available_stems)
            # Merge with existing active_tracks (user overrides take precedence)
            if not section.active_tracks:
                section.active_tracks = list(active_stems)
            else:
                # Keep user-specified tracks and add stem arranger suggestions
                existing = set(t.lower() for t in section.active_tracks)
                section.active_tracks = list(existing | active_stems)

    def _generate_textures(self) -> Dict[str, Path]:
        """Generate texture MIDI files."""
        try:
            files = generate_textures_for_song(self.spec, self.midi_dir)
            return files
        except Exception as e:
            print(f"  Warning: Texture generation failed: {e}")
            return {}

    def _generate_mix_config(self) -> Optional[Dict]:
        """Generate optional mixing configuration based on enabled features."""
        mix_config = {}

        # Sidechain configuration
        if self.enable_sidechain:
            try:
                from sidechain_config import SidechainConfigurator
                tracks = [t.name.lower() for t in self.spec.tracks]
                config = SidechainConfigurator(
                    genre=self.spec.genre,
                    tempo=self.spec.tempo
                )
                routes = config.get_routes(tracks)
                mix_config["sidechain"] = [r.to_dict() for r in routes]
                print(f"  Sidechain: {len(routes)} routes")
            except ImportError:
                print("  Warning: sidechain_config module not available")

        # Send routing
        if self.enable_sends:
            try:
                from send_routing import SendRouter
                router = SendRouter(genre=self.spec.genre)
                tracks = [t.name.lower() for t in self.spec.tracks]
                send_levels = {t: router.get_levels_for_track(t) for t in tracks}
                mix_config["sends"] = send_levels
                print(f"  Sends: {len(tracks)} tracks configured")
            except ImportError:
                print("  Warning: send_routing module not available")

        # Mix templates
        if self.enable_mix_templates:
            try:
                from mix_templates import MixTemplateManager
                manager = MixTemplateManager()
                templates = {}
                for track in self.spec.tracks:
                    track_name = track.name.lower()
                    template = manager.get_template(track_name)
                    if template:
                        templates[track_name] = template.to_dict()
                mix_config["templates"] = templates
                print(f"  Mix templates: {len(templates)} tracks")
            except ImportError:
                print("  Warning: mix_templates module not available")

        # VST preset suggestions
        if self.enable_vst_presets:
            try:
                from vst_preset_matcher import VSTPresetMatcher
                matcher = VSTPresetMatcher()
                presets = {}
                for track in self.spec.tracks:
                    track_name = track.name.lower()
                    matches = matcher.search(
                        track.instrument_hint or track_name,
                        genre=self.spec.genre,
                        mood=self.spec.mood,
                        limit=3
                    )
                    if matches:
                        presets[track_name] = [m.to_dict() for m in matches]
                mix_config["vst_presets"] = presets
                print(f"  VST presets: {len(presets)} tracks")
            except ImportError:
                print("  Warning: vst_preset_matcher module not available")

        # Save mix config if anything was generated
        if mix_config:
            mix_path = self.output_dir / "mix_config.json"
            with open(mix_path, "w") as f:
                json.dump(mix_config, f, indent=2)

        return mix_config if mix_config else None

    def _generate_all_midi(self) -> Dict[str, Path]:
        """Generate MIDI files for all tracks."""
        files = {}

        # Pre-generate all transitions
        all_transitions = self._generate_all_transitions()
        print(f"  Generated transitions for {len(all_transitions)} section boundaries")

        for track in self.spec.tracks:
            if track.track_type != "midi":
                continue

            track_name = track.name.lower()
            print(f"  Generating {track_name}...")

            if track_name == "lead":
                midi_path = self._generate_lead_track(all_transitions)
            else:
                midi_path = self._generate_pattern_track(track_name, all_transitions)

            if midi_path:
                files[track_name] = midi_path

        # Generate FX tracks (riser, crash) if transitions have them
        fx_path = self._generate_fx_track(all_transitions)
        if fx_path:
            files['fx'] = fx_path
            print(f"  Generated fx (risers/crashes)")

        return files

    def _generate_all_transitions(self) -> Dict[int, dict]:
        """
        Generate all transition events for the song.

        Returns dict mapping section_end_bar -> transition events dict
        """
        all_transitions = {}
        ticks_per_bar = self.config.TICKS_PER_BEAT * 4

        for i, section in enumerate(self.spec.structure):
            # Check if there's a next section
            if i + 1 >= len(self.spec.structure):
                continue

            next_section = self.spec.structure[i + 1]

            # Get transition config based on section types
            config = self.transition_gen.get_transition_config(
                section.section_type.value,
                next_section.section_type.value
            )

            if config.transition_type == TransitionType.NONE:
                continue

            # Generate transition events
            section_end_tick = section.end_bar * ticks_per_bar
            transitions = self.transition_gen.generate_full_transition(
                config,
                section_end_tick,
                section_end_tick  # next section starts where this ends
            )

            all_transitions[section.end_bar] = transitions

        return all_transitions

    def _generate_lead_track(self, all_transitions: Dict[int, dict] = None) -> Path:
        """Generate lead/melody track following song structure with chord awareness."""
        from mido import MidiFile, MidiTrack, MetaMessage
        import mido

        mid = MidiFile(ticks_per_beat=self.config.TICKS_PER_BEAT)
        track = MidiTrack()
        mid.tracks.append(track)

        # Add tempo
        tempo_us = mido.bpm2tempo(self.spec.tempo)
        track.append(MetaMessage("set_tempo", tempo=tempo_us, time=0))
        track.append(MetaMessage("track_name", name="Lead", time=0))

        # Get chord progression from spec or use default
        chord_progression = self.spec.chord_progression if self.spec.chord_progression else ["Am", "F", "C", "G"]

        # Collect all melody notes across sections
        all_notes = []

        for section in self.spec.structure:
            # Only generate melody in breakdown and drop sections
            if section.section_type in [SectionType.BREAKDOWN, SectionType.DROP]:
                import time
                # Timestamp-based seed - different every generation
                seed = int(time.time() * 1000 + hash(section.name)) % 2147483647

                # Use chord-aware generation
                notes = self.melody_gen.generate_for_section(
                    section.section_type.value,
                    section.bars,
                    section.energy,
                    seed=seed,
                    chord_progression=chord_progression,
                    variation=0.3,  # Ensure variety
                )
                # Offset notes to section start
                for note in notes:
                    note.start += section.start_bar * 4
                all_notes.extend(notes)

        # Convert to MIDI track
        if all_notes:
            melody_track = self.melody_gen.to_midi_track(all_notes)
            for msg in melody_track:
                if not msg.is_meta:
                    track.append(msg.copy())

        track.append(MetaMessage("end_of_track", time=0))

        midi_path = self.midi_dir / "lead.mid"
        mid.save(str(midi_path))
        return midi_path

    def _generate_fx_track(self, all_transitions: Dict[int, dict]) -> Optional[Path]:
        """Generate FX track with risers and crashes from transitions."""
        from mido import MidiFile, MidiTrack, MetaMessage, Message
        import mido

        all_events = []

        # Collect riser and crash events from all transitions
        for end_bar, transitions in all_transitions.items():
            # Add risers
            if 'riser' in transitions:
                all_events.extend(transitions['riser'])
            # Add crashes
            if 'crash' in transitions:
                all_events.extend(transitions['crash'])

        if not all_events:
            return None

        # Create MIDI file
        mid = MidiFile(ticks_per_beat=self.config.TICKS_PER_BEAT)
        track = MidiTrack()
        mid.tracks.append(track)

        tempo_us = mido.bpm2tempo(self.spec.tempo)
        track.append(MetaMessage("set_tempo", tempo=tempo_us, time=0))
        track.append(MetaMessage("track_name", name="FX", time=0))

        # Sort and convert events
        sorted_events = sorted(all_events, key=lambda x: x[0])
        current_time = 0

        for event in sorted_events:
            abs_time, msg_type, *params = event
            delta = abs_time - current_time
            current_time = abs_time

            if msg_type == "note_on":
                note, velocity = params
                track.append(Message("note_on", note=note, velocity=velocity, time=delta))
            elif msg_type == "note_off":
                note = params[0] if params else 0
                track.append(Message("note_off", note=note, velocity=0, time=delta))

        track.append(MetaMessage("end_of_track", time=0))

        midi_path = self.midi_dir / "fx.mid"
        mid.save(str(midi_path))
        return midi_path

    def _generate_pattern_track(self, track_name: str, all_transitions: Dict[int, dict] = None) -> Optional[Path]:
        """Generate pattern track following song structure, including transitions."""
        from mido import MidiFile, MidiTrack, MetaMessage, Message
        import mido

        # Map track names to transition event keys
        TRANSITION_TRACK_MAP = {
            "kick": "kick",
            "clap": "clap",
            "hats": "hats",
            # snare roll goes into clap track
        }

        # Section patterns configuration
        SECTION_PATTERNS = {
            "intro": {
                "kick": {"active": True, "pattern": "four_on_floor", "energy_mult": 0.7},
                "bass": {"active": False},
                "chords": {"active": False},
                "arp": {"active": False},
                "hats": {"active": True, "pattern": "offbeat", "energy_mult": 0.5},
                "clap": {"active": False},
            },
            "buildup": {
                "kick": {"active": True, "pattern": "four_on_floor", "energy_mult": 0.9},
                "bass": {"active": True, "pattern": "sustained", "energy_mult": 0.7},
                "chords": {"active": False},
                "arp": {"active": True, "pattern": "trance", "energy_mult": 0.6},
                "hats": {"active": True, "pattern": "offbeat", "energy_mult": 0.8},
                "clap": {"active": True, "energy_mult": 0.7},
            },
            "breakdown": {
                "kick": {"active": False},
                "bass": {"active": False},
                "chords": {"active": True, "pattern": "sustained", "energy_mult": 0.8},
                "arp": {"active": True, "pattern": "trance", "energy_mult": 0.5},
                "hats": {"active": False},
                "clap": {"active": False},
            },
            "drop": {
                "kick": {"active": True, "pattern": "four_on_floor", "energy_mult": 1.0},
                "bass": {"active": True, "pattern": "sustained", "energy_mult": 1.0},
                "chords": {"active": True, "pattern": "stabs", "energy_mult": 0.9},
                "arp": {"active": True, "pattern": "trance", "energy_mult": 1.0},
                "hats": {"active": True, "pattern": "offbeat", "energy_mult": 1.0},
                "clap": {"active": True, "energy_mult": 1.0},
            },
            "break": {
                "kick": {"active": True, "pattern": "four_on_floor", "energy_mult": 0.8},
                "bass": {"active": True, "pattern": "sustained", "energy_mult": 0.6},
                "chords": {"active": False},
                "arp": {"active": False},
                "hats": {"active": True, "pattern": "offbeat", "energy_mult": 0.6},
                "clap": {"active": True, "energy_mult": 0.6},
            },
            "outro": {
                "kick": {"active": True, "pattern": "four_on_floor", "energy_mult": 0.6},
                "bass": {"active": False},
                "chords": {"active": False},
                "arp": {"active": False},
                "hats": {"active": True, "pattern": "offbeat", "energy_mult": 0.4},
                "clap": {"active": False},
            },
        }

        all_events = []
        ticks_per_bar = self.config.TICKS_PER_BEAT * 4

        for section in self.spec.structure:
            section_type = section.section_type.value
            pattern_config = SECTION_PATTERNS.get(section_type, {}).get(track_name, {})

            if not pattern_config.get("active", False):
                continue

            pattern_type = pattern_config.get("pattern", None)
            energy_mult = pattern_config.get("energy_mult", 1.0)
            energy = section.energy * energy_mult

            # Calculate bar offset
            bar_offset = section.start_bar * ticks_per_bar

            # Generate pattern for this section
            if track_name == "kick":
                events = self.midi_gen.generate_kick(
                    bars=section.bars,
                    energy=energy,
                    pattern_type=pattern_type or "four_on_floor"
                )
            elif track_name == "bass":
                events = self.midi_gen.generate_bass(
                    bars=section.bars,
                    energy=energy,
                    pattern_type=pattern_type or "rolling"
                )
            elif track_name == "chords":
                events = self.midi_gen.generate_chords(
                    bars=section.bars,
                    energy=energy,
                    pattern_type=pattern_type or "sustained"
                )
            elif track_name == "arp":
                # Use chord-aware arp generation
                chord_progression = self.spec.chord_progression if self.spec.chord_progression else ["Am", "F", "C", "G"]
                arp_notes = self.arp_gen.generate_for_section(
                    section_type=section_type,
                    bars=section.bars,
                    energy=energy,
                    chord_progression=chord_progression,
                    style=pattern_type or "trance",
                )
                # Convert MelodyNote to events format
                events = []
                for note in arp_notes:
                    note_on_tick = int(note.start * self.config.TICKS_PER_BEAT)
                    note_off_tick = int((note.start + note.duration) * self.config.TICKS_PER_BEAT)
                    events.append((note_on_tick, "note_on", note.pitch, note.velocity))
                    events.append((note_off_tick, "note_off", note.pitch))
            elif track_name == "hats":
                events = self.midi_gen.generate_hats(
                    bars=section.bars,
                    energy=energy,
                    pattern_type=pattern_type or "offbeat"
                )
            elif track_name == "clap":
                events = self.midi_gen.generate_clap(
                    bars=section.bars,
                    energy=energy
                )
            else:
                continue

            # Offset events to correct position
            for event in events:
                time, msg_type, *params = event
                all_events.append((time + bar_offset, msg_type, *params))

        # Add transition events for this track
        if all_transitions:
            transition_key = TRANSITION_TRACK_MAP.get(track_name)
            if transition_key:
                for end_bar, transitions in all_transitions.items():
                    if transition_key in transitions:
                        all_events.extend(transitions[transition_key])
            # Snare rolls go into clap track
            if track_name == "clap":
                for end_bar, transitions in all_transitions.items():
                    if "snare" in transitions:
                        all_events.extend(transitions["snare"])

        if not all_events:
            return None

        # Create MIDI file
        mid = MidiFile(ticks_per_beat=self.config.TICKS_PER_BEAT)
        track = MidiTrack()
        mid.tracks.append(track)

        # Add tempo and track name
        tempo_us = mido.bpm2tempo(self.spec.tempo)
        track.append(MetaMessage("set_tempo", tempo=tempo_us, time=0))
        track.append(MetaMessage("track_name", name=track_name.capitalize(), time=0))

        # Sort events and convert to MIDI messages
        sorted_events = sorted(all_events, key=lambda x: x[0])
        current_time = 0

        for event in sorted_events:
            abs_time, msg_type, *params = event
            delta = abs_time - current_time
            current_time = abs_time

            if msg_type == "note_on":
                note, velocity = params
                track.append(Message("note_on", note=note, velocity=velocity, time=delta))
            elif msg_type == "note_off":
                note = params[0]
                track.append(Message("note_off", note=note, velocity=0, time=delta))

        track.append(MetaMessage("end_of_track", time=0))

        midi_path = self.midi_dir / f"{track_name}.mid"
        mid.save(str(midi_path))
        return midi_path

    def _generate_als(self) -> Path:
        """Generate Ableton Live Set file."""
        template_path = self._find_template()

        if not template_path.exists():
            print(f"Warning: Template not found at {template_path}")
            print("Creating minimal .als file...")
            return self._create_minimal_als()

        # Load template
        with gzip.open(template_path, "rb") as f:
            xml_content = f.read().decode("utf-8")

        root = ET.fromstring(xml_content)
        live_set = root.find("LiveSet")

        # Set tempo
        self._set_tempo(root, self.spec.tempo)

        # Add/update locators for sections
        self._add_locators(root, live_set)

        # Optionally create/rename tracks
        if self.create_tracks:
            try:
                self._create_tracks(root, live_set)
                print("  Created tracks from spec")
            except Exception as e:
                print(f"  Warning: Track creation failed: {e}")
                print("  Using template tracks as-is")

        # Optionally embed MIDI clips
        if self.embed_midi:
            try:
                self._embed_midi_clips(root)
                print("  Embedded MIDI clips")
            except Exception as e:
                print(f"  Warning: MIDI embedding failed: {e}")
                import traceback
                traceback.print_exc()

        # Optionally add devices (instruments) to tracks
        if self.add_devices:
            try:
                analysis = analyze_ids(root)
                device_start_id = max(analysis.max_numeric_id, analysis.next_pointee_id) + 1000
                next_id = add_devices_to_template(root, device_start_id, add_synths=False)
                # Update NextPointeeId
                update_next_pointee_id(root, next_id + 100)
                print("  Added devices to tracks")
            except Exception as e:
                print(f"  Warning: Device insertion failed: {e}")
                import traceback
                traceback.print_exc()

        # Validate before saving
        validation = validate_als_structure(root)
        if not validation.is_valid:
            print("  Warning: Generated .als has validation errors:")
            for err in validation.errors:
                print(f"    - {err}")
        if validation.warnings:
            for warn in validation.warnings[:3]:  # Show first 3 warnings
                print(f"    - {warn}")

        # Save
        als_path = self.output_dir / f"{self.spec.name}.als"
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")

        with gzip.open(als_path, "wb") as f:
            f.write(xml_str.encode("utf-8"))

        return als_path

    def _find_template(self) -> Path:
        """Find suitable Ableton template."""
        # Use configured template first (should have properly named tracks)
        if self.config.DEFAULT_LIVE_SET.exists():
            return self.config.DEFAULT_LIVE_SET

        # Fall back to searching for any template
        custom_paths = [
            self.config.OUTPUT_BASE / "Base_Template.als",
            self.config.OUTPUT_BASE / "Base_Template Project" / "Base_Template.als",
        ]
        for custom in custom_paths:
            if custom.exists():
                return custom

        # Return configured path even if doesn't exist (error will be reported)
        return self.config.DEFAULT_LIVE_SET

    def _set_tempo(self, root: ET.Element, tempo: float):
        """Set project tempo."""
        tempo_elem = root.find(".//MasterTrack//Tempo/Manual")
        if tempo_elem is not None:
            tempo_elem.set("Value", str(float(tempo)))

    def _add_locators(self, root: ET.Element, live_set: ET.Element):
        """Add arrangement locators for sections."""
        # Get max ID to avoid conflicts
        max_id = self._get_max_id(root)
        locator_base_id = max_id + 10000  # Start locator IDs well above existing

        locators_container = live_set.find("Locators")
        if locators_container is None:
            locators_container = ET.SubElement(live_set, "Locators")

        locators = locators_container.find("Locators")
        if locators is None:
            locators = ET.SubElement(locators_container, "Locators")

        # Clear existing locators
        for loc in list(locators):
            locators.remove(loc)

        # Add markers for each section
        max_locator_id = locator_base_id
        for i, section in enumerate(self.spec.structure):
            beat = section.start_bar * 4  # Convert bars to beats
            loc_id = locator_base_id + i
            max_locator_id = loc_id
            loc = ET.SubElement(locators, "Locator", {"Id": str(loc_id)})
            ET.SubElement(loc, "LomId", {"Value": "0"})
            ET.SubElement(loc, "Time", {"Value": str(beat)})
            ET.SubElement(loc, "Name", {"Value": section.name})
            ET.SubElement(loc, "Annotation", {"Value": ""})
            ET.SubElement(loc, "IsSongStart", {"Value": "true" if i == 0 else "false"})

        # Update NextPointeeId to account for the new locators
        next_pointee = live_set.find("NextPointeeId")
        if next_pointee is not None:
            next_pointee.set("Value", str(max_locator_id + 1))

    def _get_max_id(self, root: ET.Element) -> int:
        """Find the maximum numeric ID in the document."""
        max_id = 0
        for elem in root.iter():
            if "Id" in elem.attrib:
                try:
                    val = int(elem.attrib["Id"])
                    if val > max_id:
                        max_id = val
                except ValueError:
                    pass
        return max_id

    def _update_ids_in_element(self, elem: ET.Element, id_offset: int):
        """Update all numeric IDs in an element tree by adding offset."""
        for e in elem.iter():
            if "Id" in e.attrib:
                try:
                    old_id = int(e.attrib["Id"])
                    e.set("Id", str(old_id + id_offset))
                except ValueError:
                    pass

    def _set_track_name(self, track: ET.Element, name: str, color: int):
        """Set the track name and color."""
        name_elem = track.find(".//Name")
        if name_elem is not None:
            eff = name_elem.find("EffectiveName")
            if eff is not None:
                eff.set("Value", name)
            user = name_elem.find("UserName")
            if user is not None:
                user.set("Value", name)

        color_elem = track.find("Color")
        if color_elem is not None:
            color_elem.set("Value", str(color))

    def _create_tracks(self, root: ET.Element, live_set: ET.Element):
        """
        Create and configure tracks based on song spec.

        Uses safe ID generation that:
        - Generates completely new IDs for all elements in copied tracks
        - Updates internal Pointee references within each track copy
        - Updates NextPointeeId after all tracks are created
        """
        tracks_elem = live_set.find("Tracks")
        if tracks_elem is None:
            raise ValueError("No Tracks element found in template")

        # Get template tracks
        midi_tracks = tracks_elem.findall("MidiTrack")
        audio_tracks = tracks_elem.findall("AudioTrack")

        if not midi_tracks:
            raise ValueError("No MIDI tracks found in template to use as base")

        midi_template = midi_tracks[0]
        audio_template = audio_tracks[0] if audio_tracks else None

        # Analyze IDs to understand the document structure
        analysis = analyze_ids(root)
        print(f"  ID analysis: max={analysis.max_numeric_id}, next={analysis.next_pointee_id}, refs={len(analysis.referenced_ids)}")

        # Count IDs we need per track (estimate by counting IDs in template)
        ids_per_track = sum(1 for e in midi_template.iter() if 'Id' in e.attrib)
        total_tracks = len([t for t in self.spec.tracks if t.track_type in ("midi", "audio")])
        total_ids_needed = ids_per_track * total_tracks + total_tracks  # +1 for each track root

        # Generate safe IDs - start from a safe point
        next_id = max(analysis.max_numeric_id, analysis.next_pointee_id) + 1

        # Find return tracks (we'll insert before them)
        return_tracks = tracks_elem.findall("ReturnTrack")

        # Remove existing MIDI and Audio tracks
        for track in midi_tracks + audio_tracks:
            tracks_elem.remove(track)

        # Track the highest ID we use
        max_used_id = next_id - 1

        # Create tracks from spec
        for track_spec in self.spec.tracks:
            if track_spec.track_type == "midi":
                new_track = copy.deepcopy(midi_template)
            elif track_spec.track_type == "audio" and audio_template is not None:
                new_track = copy.deepcopy(audio_template)
            else:
                continue  # Skip if no template available

            # Build mapping of old IDs to new IDs for this track
            id_mapping = {}

            # First pass: assign new IDs to ALL elements with Id attribute
            for elem in new_track.iter():
                if 'Id' in elem.attrib:
                    old_id = elem.attrib['Id']
                    new_id = next_id
                    next_id += 1
                    id_mapping[old_id] = str(new_id)
                    elem.set('Id', str(new_id))
                    max_used_id = max(max_used_id, new_id)

            # Second pass: update Pointee references within this track
            for elem in new_track.iter():
                if elem.tag == 'Pointee' and 'Id' in elem.attrib:
                    old_ref = elem.attrib['Id']
                    if old_ref in id_mapping:
                        elem.set('Id', id_mapping[old_ref])

            # Also update PointeeId elements (different format)
            for elem in new_track.iter():
                if elem.tag == 'PointeeId' and 'Value' in elem.attrib:
                    old_ref = elem.attrib['Value']
                    if old_ref in id_mapping:
                        elem.set('Value', id_mapping[old_ref])

            # Set name and color using xml_utils function
            color = self.TRACK_COLORS.get(track_spec.name.lower(), 0)
            set_track_name(new_track, track_spec.name, color)

            # Insert before return tracks
            if return_tracks:
                idx = list(tracks_elem).index(return_tracks[0])
                tracks_elem.insert(idx, new_track)
            else:
                tracks_elem.append(new_track)

        # Update NextPointeeId to be higher than all used IDs
        update_next_pointee_id(root, max_used_id + 1)
        print(f"  Updated NextPointeeId to {max_used_id + 1}")

    def _embed_midi_clips(self, root: ET.Element):
        """Embed MIDI clips from midi/ folder into tracks."""
        # Get current max ID for clip IDs
        analysis = analyze_ids(root)
        start_id = max(analysis.max_numeric_id, analysis.next_pointee_id) + 1

        # Create embedder
        embedder = ClipEmbedder(ticks_per_beat=self.config.TICKS_PER_BEAT)

        # Build track name -> MIDI file mapping
        track_mapping = {}
        for track_spec in self.spec.tracks:
            track_name = track_spec.name.lower()
            midi_file = f"{track_name}.mid"
            if (self.midi_dir / midi_file).exists():
                track_mapping[track_name] = midi_file

        # Build sections list if splitting is enabled
        sections = None
        if self.split_sections and self.spec.structure:
            sections = [
                (section.name, section.start_bar, section.end_bar)
                for section in self.spec.structure
            ]
            print(f"  Splitting clips into {len(sections)} sections")

        # Embed clips
        next_id = embedder.embed_midi_files(
            root,
            self.midi_dir,
            track_mapping,
            self.spec.total_bars,
            start_id,
            sections=sections
        )

        # Update NextPointeeId
        update_next_pointee_id(root, next_id + 1)

    def _create_minimal_als(self) -> Path:
        """Create a minimal .als file when no template is available."""
        # This is a fallback - creates a very basic structure
        als_path = self.output_dir / f"{self.spec.name}.als"

        # For now, just create an empty marker file
        # The user will need to create the project manually
        readme_path = self.output_dir / "README.txt"
        with open(readme_path, "w") as f:
            f.write(f"Project: {self.spec.name}\n")
            f.write(f"Tempo: {self.spec.tempo} BPM\n")
            f.write(f"Key: {self.spec.key} {self.spec.scale}\n")
            f.write(f"\nMIDI files are in the 'midi' folder.\n")
            f.write("Drag them into Ableton to use.\n")
            f.write("\nStructure:\n")
            for section in self.spec.structure:
                f.write(f"  Bar {section.start_bar:3}: {section.name}\n")

        print(f"Warning: No template available. Created README at {readme_path}")
        print("MIDI files are ready - drag them into a new Ableton project.")

        return als_path

    def _save_spec(self):
        """Save song spec as JSON for reference."""
        spec_path = self.output_dir / "song_spec.json"
        with open(spec_path, "w") as f:
            json.dump(self.spec.to_dict(), f, indent=2)


def generate_project(spec: SongSpec, config: Config = None) -> Path:
    """
    Convenience function to generate a project.

    Args:
        spec: Song specification
        config: Optional configuration

    Returns:
        Path to generated .als file
    """
    project = AbletonProject(spec, config)
    return project.generate()


def demo():
    """Demo the project generator."""
    print("=" * 60)
    print("ABLETON PROJECT GENERATOR - Demo")
    print("=" * 60)

    # Create a default trance spec
    spec = create_default_trance_spec("Demo_Track")

    print(f"\nSong: {spec.name}")
    print(f"Key: {spec.key} {spec.scale}")
    print(f"Tempo: {spec.tempo} BPM")
    print(f"Duration: {spec.duration_formatted}")
    print(f"\nStructure ({spec.total_bars} bars):")
    for section in spec.structure:
        print(f"  Bar {section.start_bar:3}: {section.name} ({section.bars} bars, energy: {section.energy})")

    # Generate project
    project = AbletonProject(spec)
    als_path = project.generate()

    print("\n" + "=" * 60)
    print("Generation complete!")
    print(f"Output: {als_path.parent}")
    print("=" * 60)


if __name__ == "__main__":
    demo()
