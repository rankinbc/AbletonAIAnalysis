#!/usr/bin/env python3
"""
Claude Code Integration Module for AI Song Generator

This module provides helper functions for Claude Code to generate
Ableton Live projects from natural language descriptions.

Usage (from Claude Code):
    1. User describes the track they want
    2. Claude interprets and calls generate_from_description()
    3. Project is created and returned

Example:
    from claude_generator import generate_from_description

    result = generate_from_description(
        description="uplifting trance with emotional breakdown",
        name="MyTrack",
        tempo=138,
        key="A",
        scale="minor"
    )
    print(f"Created: {result['als_path']}")
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from config import Config, DEFAULT_CONFIG
from song_spec import SongSpec, SectionSpec, SectionType, TrackSpec
from ableton_project import AbletonProject


# Genre templates with typical characteristics
GENRE_TEMPLATES = {
    "trance": {
        "uplifting": {"tempo": 138, "key": "A", "scale": "minor", "mood": "euphoric"},
        "dark": {"tempo": 140, "key": "F#", "scale": "minor", "mood": "aggressive"},
        "progressive": {"tempo": 132, "key": "D", "scale": "minor", "mood": "hypnotic"},
        "psytrance": {"tempo": 145, "key": "E", "scale": "harmonic_minor", "mood": "psychedelic"},
    },
    "techno": {
        "driving": {"tempo": 130, "key": "F", "scale": "minor", "mood": "hypnotic"},
        "dark": {"tempo": 135, "key": "D", "scale": "minor", "mood": "aggressive"},
        "melodic": {"tempo": 125, "key": "C", "scale": "minor", "mood": "emotional"},
    },
    "house": {
        "progressive": {"tempo": 124, "key": "G", "scale": "minor", "mood": "groovy"},
        "deep": {"tempo": 122, "key": "A", "scale": "minor", "mood": "smooth"},
    },
}

# Structure presets
STRUCTURE_PRESETS = {
    "standard": "Standard trance structure with 2 drops",
    "extended": "Extended mix with longer intro/outro",
    "radio": "Radio edit - short and punchy",
    "progressive": "Progressive build with long breakdown",
    "techno": "Driving techno with minimal breakdown",
    "festival": "High energy with short breakdowns",
}


def infer_genre_from_description(description: str) -> Dict[str, Any]:
    """
    Infer genre parameters from a natural language description.
    Returns a dict with genre, subgenre, tempo, key, scale, mood.
    """
    desc_lower = description.lower()

    # Default values
    params = {
        "genre": "trance",
        "subgenre": "uplifting",
        "tempo": 138,
        "key": "A",
        "scale": "minor",
        "mood": "euphoric",
        "structure_type": "standard",
    }

    # Detect genre
    if any(word in desc_lower for word in ["techno", "tech"]):
        params["genre"] = "techno"
        params["subgenre"] = "driving"
        params["tempo"] = 130
        params["structure_type"] = "techno"

    elif any(word in desc_lower for word in ["house", "progressive house"]):
        params["genre"] = "house"
        params["subgenre"] = "progressive"
        params["tempo"] = 124
        params["structure_type"] = "progressive_house"

    elif any(word in desc_lower for word in ["psy", "psytrance", "goa"]):
        params["genre"] = "trance"
        params["subgenre"] = "psytrance"
        params["tempo"] = 145
        params["scale"] = "harmonic_minor"
        params["structure_type"] = "psytrance"

    # Detect subgenre/mood
    if any(word in desc_lower for word in ["dark", "aggressive", "hard"]):
        params["subgenre"] = "dark"
        params["mood"] = "aggressive"
        if params["genre"] == "trance":
            params["key"] = "F#"
            params["tempo"] = 140

    elif any(word in desc_lower for word in ["uplifting", "euphoric", "happy", "emotional"]):
        params["subgenre"] = "uplifting"
        params["mood"] = "euphoric"

    elif any(word in desc_lower for word in ["progressive", "deep", "hypnotic"]):
        params["subgenre"] = "progressive"
        params["mood"] = "hypnotic"
        params["tempo"] = min(params["tempo"], 132)
        params["structure_type"] = "progressive"

    elif any(word in desc_lower for word in ["melodic"]):
        params["subgenre"] = "melodic"
        params["mood"] = "emotional"
        params["structure_type"] = "melodic_techno"

    # Detect tempo hints
    if "fast" in desc_lower or "high energy" in desc_lower:
        params["tempo"] += 5
    elif "slow" in desc_lower or "chill" in desc_lower:
        params["tempo"] -= 10

    # Detect structure hints
    if any(word in desc_lower for word in ["radio", "short", "edit"]):
        params["structure_type"] = "radio"
    elif any(word in desc_lower for word in ["extended", "long", "dj"]):
        params["structure_type"] = "progressive"
    elif "big breakdown" in desc_lower or "long breakdown" in desc_lower:
        params["structure_type"] = "progressive"

    return params


def create_song_spec(
    name: str,
    genre: str = "trance",
    subgenre: str = "uplifting",
    tempo: int = 138,
    key: str = "A",
    scale: str = "minor",
    mood: str = "euphoric",
    structure_type: str = "standard",
    chord_progression: List[str] = None,
    hints: Dict[str, Any] = None,
) -> SongSpec:
    """
    Create a complete SongSpec from parameters.

    Args:
        name: Song/project name
        genre: Main genre (trance, techno, house)
        subgenre: Subgenre (uplifting, dark, progressive, etc.)
        tempo: BPM
        key: Musical key (A, F#, etc.)
        scale: Scale type (minor, major, harmonic_minor)
        mood: Mood descriptor
        structure_type: Structure preset name
        chord_progression: Optional chord progression
        hints: Additional generation hints

    Returns:
        Complete SongSpec ready for generation
    """
    from ai_song_generator import create_spec_from_preset, PRESETS

    # Find matching preset
    preset_key = None
    for key_name, preset in PRESETS.items():
        if preset.get("genre") == genre and preset.get("subgenre") == subgenre:
            preset_key = key_name
            break

    if preset_key:
        spec = create_spec_from_preset(preset_key, name)
    else:
        # Create custom spec
        spec = create_spec_from_preset("uplifting_trance", name)

    # Override with provided values
    spec.genre = genre
    spec.subgenre = subgenre
    spec.tempo = tempo
    spec.key = key
    spec.scale = scale
    spec.mood = mood

    if chord_progression:
        spec.chord_progression = chord_progression
    if hints:
        spec.hints = hints

    return spec


def generate_from_description(
    description: str,
    name: str = None,
    tempo: int = None,
    key: str = None,
    scale: str = None,
    open_in_ableton: bool = False,
    output_dir: Path = None,
    enable_textures: bool = True,
    enable_stem_arranger: bool = True,
    enable_sidechain: bool = False,
    enable_sends: bool = False,
    enable_mix_templates: bool = False,
    enable_vst_presets: bool = False,
    full_mix: bool = False,
) -> Dict[str, Any]:
    """
    Generate an Ableton Live project from a natural language description.

    This is the main entry point for Claude Code integration.

    Args:
        description: Natural language description of the desired track
        name: Optional song name (auto-generated if not provided)
        tempo: Optional tempo override
        key: Optional key override
        scale: Optional scale override
        open_in_ableton: Whether to open the project after generation
        output_dir: Optional output directory override
        enable_textures: Generate texture MIDI (risers, impacts) - default True
        enable_stem_arranger: Use intelligent track activation - default True
        enable_sidechain: Generate sidechain routing config - default False
        enable_sends: Generate send routing config - default False
        enable_mix_templates: Generate EQ/compression templates - default False
        enable_vst_presets: Generate VST preset suggestions - default False
        full_mix: Enable all mixing features - default False

    Returns:
        Dict with:
            - als_path: Path to generated .als file
            - midi_dir: Path to MIDI files directory
            - spec: The SongSpec used
            - success: Boolean indicating success

    Example:
        result = generate_from_description(
            "uplifting trance with emotional breakdown and big drop",
            name="Euphoria"
        )

        # With full mixing features
        result = generate_from_description(
            "dark techno",
            name="Warehouse",
            full_mix=True
        )
    """
    # Infer parameters from description
    params = infer_genre_from_description(description)

    # Apply overrides
    if tempo:
        params["tempo"] = tempo
    if key:
        params["key"] = key
    if scale:
        params["scale"] = scale

    # Generate name if not provided
    if not name:
        name = f"Track_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Create spec
    spec = create_song_spec(
        name=name,
        hints={"original_description": description},
        **params
    )

    # Configure output
    config = DEFAULT_CONFIG
    if output_dir:
        config = Config()
        config.OUTPUT_BASE = output_dir

    # Determine feature flags
    use_sidechain = enable_sidechain or full_mix
    use_sends = enable_sends or full_mix
    use_mix_templates = enable_mix_templates or full_mix
    use_vst_presets = enable_vst_presets or full_mix

    # Generate project
    project = AbletonProject(
        spec, config,
        enable_textures=enable_textures,
        enable_stem_arranger=enable_stem_arranger,
        enable_sidechain=use_sidechain,
        enable_sends=use_sends,
        enable_mix_templates=use_mix_templates,
        enable_vst_presets=use_vst_presets
    )
    als_path = project.generate()

    result = {
        "success": True,
        "als_path": str(als_path),
        "midi_dir": str(project.midi_dir),
        "project_dir": str(als_path.parent),
        "spec": spec.to_dict(),
        "description": description,
        "parameters": params,
    }

    # Open in Ableton if requested
    if open_in_ableton and als_path.exists():
        try:
            subprocess.Popen([str(config.ABLETON_EXE), str(als_path)])
            result["opened_in_ableton"] = True
        except FileNotFoundError:
            result["opened_in_ableton"] = False
            result["ableton_error"] = f"Ableton not found at {config.ABLETON_EXE}"

    return result


def generate_from_spec_dict(spec_dict: Dict[str, Any], open_in_ableton: bool = False) -> Dict[str, Any]:
    """
    Generate from a complete spec dictionary.

    Use this when Claude has already constructed the full SongSpec.

    Args:
        spec_dict: Complete SongSpec as a dictionary
        open_in_ableton: Whether to open after generation

    Returns:
        Same as generate_from_description()
    """
    spec = SongSpec.from_dict(spec_dict)

    config = DEFAULT_CONFIG
    project = AbletonProject(spec, config)
    als_path = project.generate()

    result = {
        "success": True,
        "als_path": str(als_path),
        "midi_dir": str(project.midi_dir),
        "project_dir": str(als_path.parent),
        "spec": spec.to_dict(),
    }

    if open_in_ableton and als_path.exists():
        try:
            subprocess.Popen([str(config.ABLETON_EXE), str(als_path)])
            result["opened_in_ableton"] = True
        except FileNotFoundError:
            result["opened_in_ableton"] = False

    return result


def list_presets() -> Dict[str, str]:
    """List all available presets with descriptions."""
    from ai_song_generator import PRESETS

    result = {}
    for name, config in PRESETS.items():
        result[name] = f"{config['genre']} / {config['subgenre']} - {config['tempo']} BPM, {config['key']} {config['scale']}"
    return result


# =============================================================================
# INTERACTIVE MODE - Conversational Track Generation
# =============================================================================

class InteractiveGenerator:
    """
    Conversational track generator that guides users through choices.

    Usage:
        generator = InteractiveGenerator()
        result = generator.run()
    """

    # Genre options with subgenres
    GENRES = {
        "trance": {
            "name": "Trance",
            "description": "Euphoric, melodic, emotional builds and drops",
            "subgenres": {
                "uplifting": {"name": "Uplifting", "tempo": 138, "key": "A", "mood": "euphoric"},
                "progressive": {"name": "Progressive", "tempo": 132, "key": "D", "mood": "hypnotic"},
                "dark": {"name": "Dark", "tempo": 140, "key": "F#", "mood": "aggressive"},
                "psytrance": {"name": "Psytrance", "tempo": 145, "key": "E", "mood": "psychedelic"},
            }
        },
        "techno": {
            "name": "Techno",
            "description": "Driving, hypnotic, repetitive grooves",
            "subgenres": {
                "driving": {"name": "Driving", "tempo": 130, "key": "F", "mood": "hypnotic"},
                "melodic": {"name": "Melodic", "tempo": 125, "key": "C", "mood": "emotional"},
                "dark": {"name": "Dark", "tempo": 135, "key": "D", "mood": "aggressive"},
            }
        },
        "house": {
            "name": "House",
            "description": "Groovy, soulful, four-on-the-floor",
            "subgenres": {
                "progressive": {"name": "Progressive", "tempo": 124, "key": "G", "mood": "groovy"},
                "deep": {"name": "Deep", "tempo": 122, "key": "A", "mood": "smooth"},
            }
        },
    }

    # Structure options
    STRUCTURES = {
        "standard": {"name": "Standard", "description": "Classic structure with 2 drops (~6 min)"},
        "extended": {"name": "Extended/DJ", "description": "Long intro/outro for mixing (~8 min)"},
        "radio": {"name": "Radio Edit", "description": "Short and punchy (~3:30)"},
        "progressive": {"name": "Progressive", "description": "Long builds, big breakdown (~7 min)"},
    }

    # Key options
    KEYS = ["A", "B", "C", "D", "E", "F", "G", "F#", "C#", "Bb", "Eb"]

    def __init__(self):
        self.spec_params = {
            "genre": None,
            "subgenre": None,
            "tempo": 138,
            "key": "A",
            "scale": "minor",
            "mood": "euphoric",
            "structure_type": "standard",
            "name": None,
        }
        self.special_requests = []

    def _print_header(self, text: str):
        """Print a section header."""
        print(f"\n{'='*60}")
        print(f"  {text}")
        print('='*60)

    def _print_options(self, options: List[tuple], prompt: str = "Your choice"):
        """Print numbered options and get user choice."""
        for i, (key, label, desc) in enumerate(options, 1):
            if desc:
                print(f"  {i}. {label} - {desc}")
            else:
                print(f"  {i}. {label}")
        print()

        while True:
            try:
                choice = input(f"{prompt} [1-{len(options)}]: ").strip()
                if not choice:
                    return options[0][0]  # Default to first
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx][0]
                print(f"  Please enter 1-{len(options)}")
            except ValueError:
                print(f"  Please enter a number 1-{len(options)}")

    def _ask_yes_no(self, prompt: str, default: bool = True) -> bool:
        """Ask a yes/no question."""
        default_str = "Y/n" if default else "y/N"
        response = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not response:
            return default
        return response in ('y', 'yes', '1', 'true')

    def step_welcome(self):
        """Welcome message."""
        self._print_header("AI SONG GENERATOR - Interactive Mode")
        print("\n  Let's create a track together!")
        print("  I'll guide you through the options.\n")

    def step_genre(self) -> str:
        """Select main genre."""
        print("\n  What genre are we making?\n")

        options = [
            (key, data["name"], data["description"])
            for key, data in self.GENRES.items()
        ]

        genre = self._print_options(options, "Genre")
        self.spec_params["genre"] = genre
        return genre

    def step_subgenre(self, genre: str) -> str:
        """Select subgenre/style."""
        genre_data = self.GENRES[genre]
        print(f"\n  What style of {genre_data['name']}?\n")

        options = [
            (key, data["name"], f"{data['tempo']} BPM, {data['mood']}")
            for key, data in genre_data["subgenres"].items()
        ]

        subgenre = self._print_options(options, "Style")

        # Apply subgenre defaults
        sub_data = genre_data["subgenres"][subgenre]
        self.spec_params["subgenre"] = subgenre
        self.spec_params["tempo"] = sub_data["tempo"]
        self.spec_params["key"] = sub_data["key"]
        self.spec_params["mood"] = sub_data["mood"]

        return subgenre

    def step_tempo(self) -> int:
        """Confirm or adjust tempo."""
        current = self.spec_params["tempo"]
        print(f"\n  Tempo is set to {current} BPM.")

        options = [
            ("keep", f"Keep {current} BPM", "recommended for this style"),
            ("slower", f"Slower ({current - 8} BPM)", "more relaxed feel"),
            ("faster", f"Faster ({current + 5} BPM)", "more energy"),
            ("custom", "Custom", "enter your own"),
        ]

        choice = self._print_options(options, "Tempo")

        if choice == "keep":
            return current
        elif choice == "slower":
            self.spec_params["tempo"] = current - 8
        elif choice == "faster":
            self.spec_params["tempo"] = current + 5
        else:
            while True:
                try:
                    custom = input("  Enter BPM (100-180): ").strip()
                    tempo = int(custom)
                    if 100 <= tempo <= 180:
                        self.spec_params["tempo"] = tempo
                        break
                    print("  Please enter a value between 100-180")
                except ValueError:
                    print("  Please enter a number")

        return self.spec_params["tempo"]

    def step_key(self) -> str:
        """Select musical key."""
        current = self.spec_params["key"]
        print(f"\n  Key is set to {current} minor.")

        if self._ask_yes_no("  Keep this key?", default=True):
            return current

        print("\n  Popular keys for electronic music:\n")
        options = [
            ("A", "A minor", "most popular, emotional"),
            ("F#", "F# minor", "dark, powerful"),
            ("D", "D minor", "melancholic, deep"),
            ("C", "C minor", "dramatic, classical"),
            ("G", "G minor", "groovy, uplifting"),
            ("E", "E minor", "psychedelic, driving"),
        ]

        key = self._print_options(options, "Key")
        self.spec_params["key"] = key
        return key

    def step_structure(self) -> str:
        """Select arrangement structure."""
        print("\n  What kind of arrangement?\n")

        options = [
            (key, data["name"], data["description"])
            for key, data in self.STRUCTURES.items()
        ]

        structure = self._print_options(options, "Structure")
        self.spec_params["structure_type"] = structure
        return structure

    def step_special_requests(self) -> List[str]:
        """Gather any special requests."""
        print("\n  Any special requests? (optional)\n")

        requests = []

        if self._ask_yes_no("  Long emotional breakdown?", default=False):
            requests.append("long_breakdown")

        if self._ask_yes_no("  Extra punchy kick?", default=False):
            requests.append("punchy_kick")

        if self._ask_yes_no("  Rolling bassline?", default=True):
            requests.append("rolling_bass")

        custom = input("\n  Anything else? (or press Enter to skip): ").strip()
        if custom:
            requests.append(custom)

        self.special_requests = requests
        return requests

    def step_name(self) -> str:
        """Get track name."""
        print("\n  What should we call this track?\n")
        name = input("  Track name (or Enter for auto): ").strip()

        if not name:
            name = f"Track_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"  Using: {name}")

        self.spec_params["name"] = name
        return name

    def step_confirm(self) -> bool:
        """Show summary and confirm generation."""
        self._print_header("TRACK SUMMARY")

        print(f"""
  Name:      {self.spec_params['name']}
  Genre:     {self.spec_params['genre']} / {self.spec_params['subgenre']}
  Tempo:     {self.spec_params['tempo']} BPM
  Key:       {self.spec_params['key']} {self.spec_params['scale']}
  Mood:      {self.spec_params['mood']}
  Structure: {self.spec_params['structure_type']}
""")

        if self.special_requests:
            print(f"  Extras:   {', '.join(self.special_requests)}")

        print()
        return self._ask_yes_no("  Generate this track?", default=True)

    def generate(self) -> Dict[str, Any]:
        """Generate the track based on collected parameters."""
        self._print_header("GENERATING")

        # Build description from params
        description = f"{self.spec_params['mood']} {self.spec_params['subgenre']} {self.spec_params['genre']}"
        if self.special_requests:
            description += f" with {', '.join(self.special_requests)}"

        result = generate_from_description(
            description=description,
            name=self.spec_params["name"],
            tempo=self.spec_params["tempo"],
            key=self.spec_params["key"],
            scale=self.spec_params["scale"],
        )

        return result

    def run(self, open_in_ableton: bool = False) -> Optional[Dict[str, Any]]:
        """
        Run the full interactive flow.

        Returns the generation result or None if cancelled.
        """
        try:
            self.step_welcome()

            genre = self.step_genre()
            self.step_subgenre(genre)
            self.step_tempo()
            self.step_key()
            self.step_structure()
            self.step_special_requests()
            self.step_name()

            if not self.step_confirm():
                print("\n  Cancelled. No track generated.")
                return None

            result = self.generate()

            if result["success"]:
                self._print_header("COMPLETE")
                print(f"""
  Track generated successfully!

  Project: {result['project_dir']}
  ALS:     {result['als_path']}
  MIDI:    {result['midi_dir']}
""")
                if open_in_ableton:
                    print("  Opening in Ableton...")
                    subprocess.Popen([str(DEFAULT_CONFIG.ABLETON_EXE), result['als_path']])

            return result

        except KeyboardInterrupt:
            print("\n\n  Cancelled by user.")
            return None


def interactive_mode(open_in_ableton: bool = False) -> Optional[Dict[str, Any]]:
    """
    Run interactive track generation.

    This is the main entry point for interactive mode.

    Args:
        open_in_ableton: Whether to open the project after generation

    Returns:
        Generation result dict or None if cancelled
    """
    generator = InteractiveGenerator()
    return generator.run(open_in_ableton=open_in_ableton)


def get_preset_spec(preset_name: str, song_name: str = None) -> Dict[str, Any]:
    """Get a SongSpec dict for a preset (for Claude to modify before generation)."""
    from ai_song_generator import create_spec_from_preset

    spec = create_spec_from_preset(preset_name, song_name)
    return spec.to_dict()


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Claude Generator CLI")
    parser.add_argument("description", nargs="?", default=None)
    parser.add_argument("--name", "-n", help="Song name")
    parser.add_argument("--open", action="store_true", help="Open in Ableton")
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive guided mode")

    args = parser.parse_args()

    if args.list_presets:
        print("\nAvailable Presets:")
        for name, desc in list_presets().items():
            print(f"  {name}: {desc}")
        sys.exit(0)

    if args.interactive or args.description is None:
        # Run interactive mode
        result = interactive_mode(open_in_ableton=args.open)
        if result:
            sys.exit(0)
        else:
            sys.exit(1)

    print(f"\nGenerating from: '{args.description}'")
    result = generate_from_description(
        args.description,
        name=args.name,
        open_in_ableton=args.open
    )

    if result["success"]:
        print(f"\n[OK] Success!")
        print(f"  Project: {result['project_dir']}")
        print(f"  ALS: {result['als_path']}")
        print(f"  Inferred: {result['parameters']['genre']} / {result['parameters']['subgenre']}")
        print(f"  Tempo: {result['parameters']['tempo']} BPM")
        print(f"  Key: {result['parameters']['key']} {result['parameters']['scale']}")
    else:
        print(f"\n[FAIL] Failed")
