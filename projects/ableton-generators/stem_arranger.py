"""
Stem Arranger - Intelligent Layering/Unlayering System

Provides intelligent control over which tracks play during each section,
with smooth transitions, energy-based activation, and professional
arrangement patterns.

Features:
- Stem groups (drums, bass, harmony, leads, fx)
- Layer activation curves based on energy
- Smooth transitions (fade in/out, filter sweeps)
- Genre-specific arrangement templates
- Counter-layering (elements that enter/exit opposite to energy)
- Build-up and breakdown automation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import math

from song_spec import SongSpec, SectionSpec, SectionType


class StemGroup(Enum):
    """Logical groupings of stems/tracks."""
    DRUMS = "drums"           # Kick, snare, hats, percussion
    BASS = "bass"             # Bass, sub
    HARMONY = "harmony"       # Chords, pads, arps
    LEADS = "leads"           # Lead, vocals, hooks
    FX = "fx"                 # Risers, impacts, textures, atmosphere
    PERCUSSION = "percussion" # Additional percussion layers


@dataclass
class StemConfig:
    """Configuration for a single stem/track."""
    name: str
    group: StemGroup
    priority: int = 5           # 1-10, higher = more important
    min_energy: float = 0.0     # Minimum energy to activate
    max_energy: float = 1.0     # Maximum energy (for counter-layers)
    fade_in_bars: float = 0.0   # Bars to fade in
    fade_out_bars: float = 0.0  # Bars to fade out
    filter_sweep: bool = False  # Use filter sweep on entry/exit
    is_counter_layer: bool = False  # Exits when energy increases

    # Relationships
    requires: List[str] = field(default_factory=list)  # Must have these active
    excludes: List[str] = field(default_factory=list)  # Cannot play with these

    def should_activate(self, energy: float) -> bool:
        """Check if stem should be active at given energy level."""
        if self.is_counter_layer:
            return energy <= self.max_energy and energy >= self.min_energy
        return energy >= self.min_energy and energy <= self.max_energy


@dataclass
class LayerEvent:
    """An event in the arrangement (stem activation/deactivation)."""
    bar: int
    stem_name: str
    action: str  # "enter", "exit", "fade_in", "fade_out", "filter_in", "filter_out"
    duration_bars: float = 0.0

    # Automation values
    volume_start: float = 1.0
    volume_end: float = 1.0
    filter_start: float = 1.0  # 0-1, normalized cutoff
    filter_end: float = 1.0


@dataclass
class ArrangementLayer:
    """Complete arrangement layer data for a section."""
    section_name: str
    section_type: SectionType
    start_bar: int
    bars: int
    energy: float

    # Active stems in this section
    active_stems: Set[str] = field(default_factory=set)

    # Events at section boundaries
    entry_events: List[LayerEvent] = field(default_factory=list)
    exit_events: List[LayerEvent] = field(default_factory=list)

    # Volume levels per stem (for mixing)
    stem_volumes: Dict[str, float] = field(default_factory=dict)


# =============================================================================
# DEFAULT STEM CONFIGURATIONS
# =============================================================================

DEFAULT_STEM_CONFIGS: Dict[str, StemConfig] = {
    # Drums group
    "kick": StemConfig(
        name="kick",
        group=StemGroup.DRUMS,
        priority=10,
        min_energy=0.2,
        fade_in_bars=0,
    ),
    "clap": StemConfig(
        name="clap",
        group=StemGroup.DRUMS,
        priority=8,
        min_energy=0.4,
        requires=["kick"],
    ),
    "hats": StemConfig(
        name="hats",
        group=StemGroup.DRUMS,
        priority=6,
        min_energy=0.3,
        fade_in_bars=0.5,
    ),
    "perc": StemConfig(
        name="perc",
        group=StemGroup.PERCUSSION,
        priority=4,
        min_energy=0.5,
        fade_in_bars=1,
    ),

    # Bass group
    "bass": StemConfig(
        name="bass",
        group=StemGroup.BASS,
        priority=9,
        min_energy=0.4,
        requires=["kick"],  # Bass usually comes with kick
    ),
    "sub": StemConfig(
        name="sub",
        group=StemGroup.BASS,
        priority=7,
        min_energy=0.6,
        requires=["bass"],
    ),

    # Harmony group
    "chords": StemConfig(
        name="chords",
        group=StemGroup.HARMONY,
        priority=7,
        min_energy=0.3,
        filter_sweep=True,
    ),
    "pad": StemConfig(
        name="pad",
        group=StemGroup.HARMONY,
        priority=5,
        min_energy=0.2,
        max_energy=0.8,  # Exits during drops
        fade_in_bars=2,
        fade_out_bars=2,
        is_counter_layer=True,
    ),
    "arp": StemConfig(
        name="arp",
        group=StemGroup.HARMONY,
        priority=6,
        min_energy=0.4,
        filter_sweep=True,
    ),

    # Leads group
    "lead": StemConfig(
        name="lead",
        group=StemGroup.LEADS,
        priority=8,
        min_energy=0.5,
    ),
    "vox": StemConfig(
        name="vox",
        group=StemGroup.LEADS,
        priority=9,
        min_energy=0.3,
        excludes=["lead"],  # Usually not both at same time
    ),

    # FX group
    "riser": StemConfig(
        name="riser",
        group=StemGroup.FX,
        priority=7,
        min_energy=0.5,
        max_energy=0.9,  # Only during builds
    ),
    "impact": StemConfig(
        name="impact",
        group=StemGroup.FX,
        priority=8,
        min_energy=0.9,  # Only on drops
    ),
    "atmosphere": StemConfig(
        name="atmosphere",
        group=StemGroup.FX,
        priority=3,
        min_energy=0.0,
        max_energy=0.6,  # Counter-layer, exits on drops
        is_counter_layer=True,
        fade_in_bars=4,
        fade_out_bars=2,
    ),
    "texture": StemConfig(
        name="texture",
        group=StemGroup.FX,
        priority=2,
        min_energy=0.0,
        fade_in_bars=2,
    ),
    "downlifter": StemConfig(
        name="downlifter",
        group=StemGroup.FX,
        priority=5,
        min_energy=0.0,
        max_energy=0.4,  # After drops
    ),
}


# =============================================================================
# GENRE-SPECIFIC ARRANGEMENT TEMPLATES
# =============================================================================

@dataclass
class GenreTemplate:
    """Genre-specific arrangement rules."""
    name: str

    # Section stem overrides
    # Format: section_type -> list of always-active stems
    section_stems: Dict[str, List[str]] = field(default_factory=dict)

    # Energy thresholds for this genre
    low_energy_threshold: float = 0.3
    mid_energy_threshold: float = 0.6
    high_energy_threshold: float = 0.85

    # Transition style
    use_filter_sweeps: bool = True
    use_volume_fades: bool = True
    build_bars: int = 8  # Standard build length

    # Counter-layer behavior
    pads_exit_on_drop: bool = True
    atmosphere_during_breaks: bool = True


GENRE_TEMPLATES: Dict[str, GenreTemplate] = {
    "trance": GenreTemplate(
        name="trance",
        section_stems={
            "intro": ["kick", "hats", "atmosphere"],
            "buildup": ["kick", "bass", "arp", "hats", "clap", "riser"],
            "breakdown": ["chords", "arp", "lead", "pad", "atmosphere"],
            "drop": ["kick", "bass", "chords", "arp", "lead", "hats", "clap", "impact"],
            "break": ["kick", "bass", "hats"],
            "outro": ["kick", "hats", "atmosphere"],
        },
        use_filter_sweeps=True,
        build_bars=8,
        pads_exit_on_drop=True,
    ),
    "techno": GenreTemplate(
        name="techno",
        section_stems={
            "intro": ["kick", "hats", "texture"],
            "buildup": ["kick", "bass", "hats", "clap", "perc", "riser"],
            "breakdown": ["pad", "texture", "atmosphere"],
            "drop": ["kick", "bass", "hats", "clap", "perc", "lead"],
            "break": ["kick", "perc"],
            "outro": ["kick", "hats"],
        },
        use_filter_sweeps=True,
        build_bars=16,
        pads_exit_on_drop=True,
    ),
    "house": GenreTemplate(
        name="house",
        section_stems={
            "intro": ["kick", "hats"],
            "buildup": ["kick", "bass", "chords", "hats", "clap"],
            "breakdown": ["chords", "pad", "vox"],
            "drop": ["kick", "bass", "chords", "hats", "clap", "vox"],
            "break": ["kick", "chords", "hats"],
            "outro": ["kick", "hats"],
        },
        use_filter_sweeps=True,
        use_volume_fades=True,
        build_bars=8,
    ),
    "progressive": GenreTemplate(
        name="progressive",
        section_stems={
            "intro": ["kick", "hats", "pad", "atmosphere"],
            "buildup": ["kick", "bass", "arp", "pad", "hats", "texture"],
            "breakdown": ["pad", "arp", "lead", "atmosphere"],
            "drop": ["kick", "bass", "arp", "lead", "hats", "clap"],
            "break": ["kick", "bass", "pad"],
            "outro": ["kick", "hats", "pad", "atmosphere"],
        },
        use_filter_sweeps=True,
        build_bars=16,
        pads_exit_on_drop=False,  # Progressive keeps pads
    ),
}


# =============================================================================
# STEM ARRANGER CLASS
# =============================================================================

class StemArranger:
    """
    Intelligent stem arrangement system.

    Determines which tracks should be active in each section based on:
    - Energy levels
    - Section type
    - Genre conventions
    - Layer relationships
    """

    def __init__(
        self,
        genre: str = "trance",
        stem_configs: Dict[str, StemConfig] = None,
        custom_template: GenreTemplate = None
    ):
        self.genre = genre
        self.stem_configs = stem_configs or DEFAULT_STEM_CONFIGS.copy()
        self.template = custom_template or GENRE_TEMPLATES.get(genre, GENRE_TEMPLATES["trance"])

    def add_stem(self, config: StemConfig):
        """Add or update a stem configuration."""
        self.stem_configs[config.name] = config

    def get_active_stems_for_energy(self, energy: float, available_stems: List[str] = None) -> Set[str]:
        """
        Get stems that should be active at a given energy level.

        Args:
            energy: 0-1 energy level
            available_stems: Optional list of available stem names

        Returns:
            Set of active stem names
        """
        active = set()

        stems_to_check = available_stems or list(self.stem_configs.keys())

        for stem_name in stems_to_check:
            config = self.stem_configs.get(stem_name)
            if config and config.should_activate(energy):
                # Check requirements
                requirements_met = all(
                    req in active or self.stem_configs.get(req, StemConfig(req, StemGroup.FX)).should_activate(energy)
                    for req in config.requires
                )

                # Check exclusions
                no_exclusions = not any(excl in active for excl in config.excludes)

                if requirements_met and no_exclusions:
                    active.add(stem_name)

        return active

    def get_stems_for_section(
        self,
        section: SectionSpec,
        available_stems: List[str] = None
    ) -> Set[str]:
        """
        Get stems that should be active in a section.

        Combines energy-based activation with genre template.
        """
        section_type = section.section_type.value

        # Start with template stems for this section type
        template_stems = set(self.template.section_stems.get(section_type, []))

        # Add energy-based stems
        energy_stems = self.get_active_stems_for_energy(section.energy, available_stems)

        # Combine (template takes precedence)
        all_stems = template_stems | energy_stems

        # Filter to available stems if specified
        if available_stems:
            all_stems = all_stems & set(available_stems)

        return all_stems

    def generate_arrangement(self, spec: SongSpec) -> List[ArrangementLayer]:
        """
        Generate complete arrangement layers for a song.

        Returns:
            List of ArrangementLayer objects, one per section
        """
        # Get available stems from spec tracks
        available_stems = [t.name.lower() for t in spec.tracks]

        layers = []
        prev_active_stems = set()

        for i, section in enumerate(spec.structure):
            # Get stems for this section
            active_stems = self.get_stems_for_section(section, available_stems)

            # Determine entry/exit events
            entering = active_stems - prev_active_stems
            exiting = prev_active_stems - active_stems

            # Create layer
            layer = ArrangementLayer(
                section_name=section.name,
                section_type=section.section_type,
                start_bar=section.start_bar,
                bars=section.bars,
                energy=section.energy,
                active_stems=active_stems,
            )

            # Generate entry events
            for stem_name in entering:
                config = self.stem_configs.get(stem_name, StemConfig(stem_name, StemGroup.FX))
                event = self._create_entry_event(stem_name, config, section)
                layer.entry_events.append(event)

            # Generate exit events (at end of section)
            for stem_name in exiting:
                config = self.stem_configs.get(stem_name, StemConfig(stem_name, StemGroup.FX))
                event = self._create_exit_event(stem_name, config, section)
                layer.exit_events.append(event)

            # Calculate stem volumes based on energy and priority
            layer.stem_volumes = self._calculate_stem_volumes(active_stems, section.energy)

            layers.append(layer)
            prev_active_stems = active_stems

        return layers

    def _create_entry_event(self, stem_name: str, config: StemConfig, section: SectionSpec) -> LayerEvent:
        """Create an entry event for a stem."""
        if config.filter_sweep and self.template.use_filter_sweeps:
            return LayerEvent(
                bar=section.start_bar,
                stem_name=stem_name,
                action="filter_in",
                duration_bars=config.fade_in_bars or 2,
                filter_start=0.2,
                filter_end=1.0,
            )
        elif config.fade_in_bars > 0 and self.template.use_volume_fades:
            return LayerEvent(
                bar=section.start_bar,
                stem_name=stem_name,
                action="fade_in",
                duration_bars=config.fade_in_bars,
                volume_start=0.0,
                volume_end=1.0,
            )
        else:
            return LayerEvent(
                bar=section.start_bar,
                stem_name=stem_name,
                action="enter",
            )

    def _create_exit_event(self, stem_name: str, config: StemConfig, section: SectionSpec) -> LayerEvent:
        """Create an exit event for a stem."""
        exit_bar = section.start_bar + section.bars - config.fade_out_bars

        if config.filter_sweep and self.template.use_filter_sweeps:
            return LayerEvent(
                bar=max(section.start_bar, exit_bar),
                stem_name=stem_name,
                action="filter_out",
                duration_bars=config.fade_out_bars or 2,
                filter_start=1.0,
                filter_end=0.2,
            )
        elif config.fade_out_bars > 0 and self.template.use_volume_fades:
            return LayerEvent(
                bar=max(section.start_bar, exit_bar),
                stem_name=stem_name,
                action="fade_out",
                duration_bars=config.fade_out_bars,
                volume_start=1.0,
                volume_end=0.0,
            )
        else:
            return LayerEvent(
                bar=section.start_bar + section.bars,
                stem_name=stem_name,
                action="exit",
            )

    def _calculate_stem_volumes(self, active_stems: Set[str], energy: float) -> Dict[str, float]:
        """Calculate relative volumes for active stems based on energy and priority."""
        volumes = {}

        for stem_name in active_stems:
            config = self.stem_configs.get(stem_name, StemConfig(stem_name, StemGroup.FX))

            # Base volume from priority (higher priority = louder)
            base_volume = 0.7 + (config.priority / 10) * 0.3

            # Energy modifier
            if config.is_counter_layer:
                # Counter-layers get quieter with energy
                energy_mod = 1.0 - (energy * 0.3)
            else:
                # Normal layers get slightly louder with energy
                energy_mod = 0.8 + (energy * 0.2)

            volumes[stem_name] = min(1.0, base_volume * energy_mod)

        return volumes

    def get_layer_summary(self, layers: List[ArrangementLayer]) -> str:
        """Generate a human-readable summary of the arrangement."""
        lines = []
        lines.append("=" * 60)
        lines.append("STEM ARRANGEMENT SUMMARY")
        lines.append("=" * 60)

        for layer in layers:
            lines.append(f"\n{layer.section_name} (bars {layer.start_bar}-{layer.start_bar + layer.bars})")
            lines.append(f"  Energy: {layer.energy:.1%}")
            lines.append(f"  Active: {', '.join(sorted(layer.active_stems))}")

            if layer.entry_events:
                entries = [f"{e.stem_name}({e.action})" for e in layer.entry_events]
                lines.append(f"  Enter: {', '.join(entries)}")

            if layer.exit_events:
                exits = [f"{e.stem_name}({e.action})" for e in layer.exit_events]
                lines.append(f"  Exit: {', '.join(exits)}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def to_section_spec_updates(self, layers: List[ArrangementLayer]) -> Dict[str, List[str]]:
        """
        Convert arrangement layers to section spec active_tracks updates.

        Returns dict of section_name -> active_tracks list
        """
        return {
            layer.section_name: list(layer.active_stems)
            for layer in layers
        }

    def generate_automation_events(
        self,
        layers: List[ArrangementLayer],
        ticks_per_beat: int = 480
    ) -> Dict[str, List[Tuple]]:
        """
        Generate MIDI CC automation events for layer transitions.

        Returns dict of stem_name -> list of (tick, cc_type, value) events
        """
        ticks_per_bar = ticks_per_beat * 4
        automation = {}

        for layer in layers:
            # Process entry events
            for event in layer.entry_events:
                if event.stem_name not in automation:
                    automation[event.stem_name] = []

                start_tick = event.bar * ticks_per_bar
                duration_ticks = int(event.duration_bars * ticks_per_bar)

                if event.action in ["fade_in", "fade_out"]:
                    # Volume automation (CC7)
                    events = self._generate_cc_sweep(
                        start_tick, duration_ticks,
                        7,  # CC7 = Volume
                        int(event.volume_start * 127),
                        int(event.volume_end * 127)
                    )
                    automation[event.stem_name].extend(events)

                elif event.action in ["filter_in", "filter_out"]:
                    # Filter automation (CC74 = brightness/cutoff)
                    events = self._generate_cc_sweep(
                        start_tick, duration_ticks,
                        74,  # CC74 = Filter cutoff
                        int(event.filter_start * 127),
                        int(event.filter_end * 127)
                    )
                    automation[event.stem_name].extend(events)

            # Process exit events
            for event in layer.exit_events:
                if event.stem_name not in automation:
                    automation[event.stem_name] = []

                start_tick = event.bar * ticks_per_bar
                duration_ticks = int(event.duration_bars * ticks_per_bar)

                if event.action in ["fade_in", "fade_out"]:
                    events = self._generate_cc_sweep(
                        start_tick, duration_ticks,
                        7,
                        int(event.volume_start * 127),
                        int(event.volume_end * 127)
                    )
                    automation[event.stem_name].extend(events)

                elif event.action in ["filter_in", "filter_out"]:
                    events = self._generate_cc_sweep(
                        start_tick, duration_ticks,
                        74,
                        int(event.filter_start * 127),
                        int(event.filter_end * 127)
                    )
                    automation[event.stem_name].extend(events)

        return automation

    def _generate_cc_sweep(
        self,
        start_tick: int,
        duration_ticks: int,
        cc_num: int,
        start_value: int,
        end_value: int,
        num_steps: int = 32
    ) -> List[Tuple]:
        """Generate smooth CC automation sweep."""
        events = []
        step_ticks = duration_ticks // num_steps

        for i in range(num_steps + 1):
            tick = start_tick + i * step_ticks
            progress = i / num_steps
            # Exponential curve for more natural feel
            curved_progress = progress ** 0.7 if start_value < end_value else 1 - ((1 - progress) ** 0.7)
            value = int(start_value + (end_value - start_value) * curved_progress)
            value = max(0, min(127, value))
            events.append((tick, 'cc', cc_num, value))

        return events


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def arrange_song(spec: SongSpec, genre: str = None) -> List[ArrangementLayer]:
    """
    Convenience function to arrange a song.

    Args:
        spec: Song specification
        genre: Override genre (default: from spec)

    Returns:
        List of arrangement layers
    """
    genre = genre or spec.genre
    arranger = StemArranger(genre=genre)
    return arranger.generate_arrangement(spec)


def get_section_stems(
    section_type: str,
    energy: float,
    genre: str = "trance",
    available_stems: List[str] = None
) -> Set[str]:
    """
    Get active stems for a section without full song context.

    Args:
        section_type: Type of section
        energy: Energy level 0-1
        genre: Genre for template
        available_stems: Optional list of available stems

    Returns:
        Set of stem names that should be active
    """
    arranger = StemArranger(genre=genre)
    section = SectionSpec(
        name="temp",
        section_type=SectionType(section_type),
        start_bar=0,
        bars=16,
        energy=energy
    )
    return arranger.get_stems_for_section(section, available_stems)


def apply_arrangement_to_spec(spec: SongSpec, layers: List[ArrangementLayer]) -> SongSpec:
    """
    Apply arrangement layers to update a song spec's active_tracks.

    Args:
        spec: Original song specification
        layers: Arrangement layers

    Returns:
        Updated SongSpec with correct active_tracks per section
    """
    # Create mapping of section name to active stems
    stem_map = {layer.section_name: list(layer.active_stems) for layer in layers}

    # Update each section
    for section in spec.structure:
        if section.name in stem_map:
            section.active_tracks = stem_map[section.name]

    return spec


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    from song_spec import create_default_trance_spec

    print("=" * 60)
    print("STEM ARRANGER - Demo")
    print("=" * 60)

    # Create a demo song
    spec = create_default_trance_spec("ArrangementDemo")

    print(f"\nSong: {spec.name}")
    print(f"Genre: {spec.genre}")
    print(f"Duration: {spec.duration_formatted}")

    # Create arranger
    arranger = StemArranger(genre=spec.genre)

    # Generate arrangement
    layers = arranger.generate_arrangement(spec)

    # Print summary
    print(arranger.get_layer_summary(layers))

    # Show automation events
    print("\nAutomation Events:")
    automation = arranger.generate_automation_events(layers)
    for stem, events in automation.items():
        if events:
            print(f"  {stem}: {len(events)} CC events")

    # Apply to spec
    updated_spec = apply_arrangement_to_spec(spec, layers)

    print("\nUpdated Section Active Tracks:")
    for section in updated_spec.structure:
        print(f"  {section.name}: {', '.join(section.active_tracks)}")

    print("\nDone!")
