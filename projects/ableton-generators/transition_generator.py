"""
Transition Generator

Generates transition elements for trance tracks:
- Drum rushes (accelerating kicks)
- Snare rolls (32nd note crescendo)
- Risers (rising pitch sweep)
- Crashes (impact on beat 1)
- Offbeat entry (hats before kick)
- Breath/break (silence before drop)

These transitions are designed to be embedded into track MIDI files
at section boundaries.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum
import math

from config import Config, DEFAULT_CONFIG


class TransitionType(Enum):
    """Types of transitions between sections."""
    NONE = "none"
    SOFT = "soft"           # Gradual, subtle transition
    BUILD = "build"         # Building energy
    RUSH = "rush"           # Full drum rush + roll
    BREAK = "break"         # Quick stop/filter
    DROP = "drop"           # Hard entry (crash, full elements)


@dataclass
class TransitionConfig:
    """Configuration for a transition."""
    transition_type: TransitionType
    bars: int = 2                    # Length of transition
    include_rush: bool = True        # Accelerating kicks
    include_roll: bool = True        # Snare roll
    include_riser: bool = True       # Rising pitch
    include_crash: bool = True       # Crash on downbeat
    include_breath: bool = False     # Silent bar before drop
    rush_start_division: int = 4     # Start with quarter notes
    rush_end_division: int = 32      # End with 32nd notes
    roll_division: int = 32          # Snare roll note division
    roll_crescendo: bool = True      # Velocity increases


# Preset transition configs for section changes
TRANSITION_PRESETS = {
    # From breakdown/buildup to drop - THE BIG ONE
    ("breakdown", "drop"): TransitionConfig(
        TransitionType.RUSH,
        bars=2,
        include_rush=True,
        include_roll=True,
        include_riser=True,
        include_crash=True,
        include_breath=True,
    ),
    ("buildup", "drop"): TransitionConfig(
        TransitionType.RUSH,
        bars=2,
        include_rush=True,
        include_roll=True,
        include_riser=True,
        include_crash=True,
        include_breath=False,
    ),
    # Intro transitions
    ("intro", "buildup"): TransitionConfig(
        TransitionType.SOFT,
        bars=1,
        include_rush=False,
        include_roll=False,
        include_riser=False,
        include_crash=False,
    ),
    # Break transitions
    ("drop", "break"): TransitionConfig(
        TransitionType.BREAK,
        bars=1,
        include_rush=False,
        include_roll=False,
        include_riser=False,
        include_crash=False,
    ),
    ("break", "breakdown"): TransitionConfig(
        TransitionType.SOFT,
        bars=1,
        include_rush=False,
        include_roll=False,
        include_riser=False,
        include_crash=False,
    ),
    # Outro
    ("drop", "outro"): TransitionConfig(
        TransitionType.SOFT,
        bars=2,
        include_rush=False,
        include_roll=False,
        include_riser=False,
        include_crash=False,
    ),
}


class TransitionGenerator:
    """Generates transition MIDI events."""

    # MIDI note numbers
    KICK_NOTE = 36      # C1
    SNARE_NOTE = 38     # D1
    CLAP_NOTE = 39      # D#1
    CRASH_NOTE = 49     # C#2 (crash cymbal)
    RIDE_NOTE = 51      # D#2

    def __init__(self, tempo: int = 138, ticks_per_beat: int = 480):
        self.tempo = tempo
        self.ticks_per_beat = ticks_per_beat
        self.ticks_per_bar = ticks_per_beat * 4

    def get_transition_config(
        self,
        from_section: str,
        to_section: str
    ) -> TransitionConfig:
        """Get transition config for section change."""
        key = (from_section.lower(), to_section.lower())
        return TRANSITION_PRESETS.get(key, TransitionConfig(TransitionType.NONE, bars=0))

    def generate_drum_rush(
        self,
        bars: int = 2,
        start_division: int = 4,
        end_division: int = 32,
        start_velocity: int = 80,
        end_velocity: int = 127,
        offset_ticks: int = 0
    ) -> List[Tuple]:
        """
        Generate accelerating kick pattern.

        Kicks start sparse and double in density:
        4ths → 8ths → 16ths → 32nds

        Returns list of MIDI events: (tick, 'note_on'/'note_off', note, velocity)
        """
        events = []
        total_ticks = bars * self.ticks_per_bar

        # Calculate how many "phases" we need
        # Each phase doubles the density
        divisions = []
        div = start_division
        while div <= end_division:
            divisions.append(div)
            div *= 2

        if not divisions:
            return events

        # Split total time among phases (later phases get less time but more notes)
        # Weight toward end: first phase gets more time, last phase less
        phase_weights = [1 / (i + 1) for i in range(len(divisions))]
        total_weight = sum(phase_weights)
        phase_ticks = [int(total_ticks * w / total_weight) for w in phase_weights]

        current_tick = offset_ticks

        for phase_idx, (division, phase_duration) in enumerate(zip(divisions, phase_ticks)):
            ticks_per_note = self.ticks_per_beat * 4 // division
            num_notes = max(1, phase_duration // ticks_per_note)

            # Velocity ramps up through the rush
            phase_progress = phase_idx / len(divisions)
            base_velocity = int(start_velocity + (end_velocity - start_velocity) * phase_progress)

            for i in range(num_notes):
                tick = current_tick + i * ticks_per_note
                # Add slight velocity variation within phase
                vel = min(127, base_velocity + (i * 2))

                events.append((tick, 'note_on', self.KICK_NOTE, vel))
                events.append((tick + ticks_per_note // 2, 'note_off', self.KICK_NOTE))

            current_tick += phase_duration

        return events

    def generate_snare_roll(
        self,
        bars: int = 1,
        division: int = 32,
        start_velocity: int = 60,
        end_velocity: int = 127,
        offset_ticks: int = 0,
        note: int = None
    ) -> List[Tuple]:
        """
        Generate snare/clap roll with crescendo.

        Rapid notes (32nds by default) building in velocity.
        """
        if note is None:
            note = self.SNARE_NOTE

        events = []
        total_ticks = bars * self.ticks_per_bar
        ticks_per_note = self.ticks_per_beat * 4 // division
        num_notes = total_ticks // ticks_per_note

        for i in range(num_notes):
            tick = offset_ticks + i * ticks_per_note
            progress = i / max(1, num_notes - 1)
            velocity = int(start_velocity + (end_velocity - start_velocity) * progress)
            velocity = min(127, velocity)

            events.append((tick, 'note_on', note, velocity))
            events.append((tick + ticks_per_note // 2, 'note_off', note))

        return events

    def generate_riser(
        self,
        bars: int = 4,
        start_note: int = 48,      # C3
        end_note: int = 72,        # C5
        division: int = 8,         # 8th notes
        velocity: int = 100,
        offset_ticks: int = 0
    ) -> List[Tuple]:
        """
        Generate rising pitch pattern for riser synth.

        Notes ascend chromatically or in scale steps.
        """
        events = []
        total_ticks = bars * self.ticks_per_bar
        ticks_per_note = self.ticks_per_beat * 4 // division
        num_notes = total_ticks // ticks_per_note

        note_range = end_note - start_note

        for i in range(num_notes):
            tick = offset_ticks + i * ticks_per_note
            progress = i / max(1, num_notes - 1)

            # Exponential curve for more dramatic rise at the end
            curved_progress = progress ** 0.7
            note = int(start_note + note_range * curved_progress)
            note = min(127, max(0, note))

            # Velocity increases slightly
            vel = min(127, velocity + int(20 * progress))

            events.append((tick, 'note_on', note, vel))
            events.append((tick + ticks_per_note - 10, 'note_off', note))

        return events

    def generate_crash(
        self,
        offset_ticks: int = 0,
        velocity: int = 127
    ) -> List[Tuple]:
        """
        Generate crash cymbal hit on the downbeat.
        """
        events = [
            (offset_ticks, 'note_on', self.CRASH_NOTE, velocity),
            (offset_ticks + self.ticks_per_beat * 2, 'note_off', self.CRASH_NOTE),
        ]
        return events

    def generate_offbeat_entry(
        self,
        bars: int = 1,
        offset_ticks: int = 0,
        note: int = 42,  # Closed hi-hat
        velocity: int = 90
    ) -> List[Tuple]:
        """
        Generate offbeat hi-hats leading into the drop.

        Creates anticipation before the kick enters.
        """
        events = []
        ticks_per_8th = self.ticks_per_beat // 2
        num_hits = bars * 8  # 8th notes per bar

        for i in range(num_hits):
            # Offbeat = every other 8th, starting on the "and"
            tick = offset_ticks + ticks_per_8th + (i * ticks_per_8th * 2)
            if tick >= offset_ticks + bars * self.ticks_per_bar:
                break

            # Slight velocity variation
            vel = velocity + ((i % 4) - 2) * 5
            vel = max(60, min(127, vel))

            events.append((tick, 'note_on', note, vel))
            events.append((tick + ticks_per_8th // 2, 'note_off', note))

        return events

    def generate_breath(
        self,
        beats: int = 2,
        offset_ticks: int = 0
    ) -> Tuple[int, int]:
        """
        Return start/end ticks for a "breath" (silence) before the drop.

        This doesn't generate events - it returns the range to EXCLUDE
        from other patterns.
        """
        start = offset_ticks
        end = offset_ticks + beats * self.ticks_per_beat
        return (start, end)

    def generate_full_transition(
        self,
        config: TransitionConfig,
        section_end_tick: int,
        next_section_start_tick: int
    ) -> dict:
        """
        Generate all transition elements based on config.

        Returns dict of track_name -> list of events
        """
        result = {
            'kick': [],
            'snare': [],
            'clap': [],
            'hats': [],
            'riser': [],
            'crash': [],
        }

        if config.transition_type == TransitionType.NONE:
            return result

        transition_bars = config.bars
        transition_start = section_end_tick - (transition_bars * self.ticks_per_bar)

        # Breath - calculate the silence zone
        breath_range = None
        if config.include_breath:
            breath_range = self.generate_breath(
                beats=2,
                offset_ticks=next_section_start_tick - self.ticks_per_beat * 2
            )

        # Drum rush
        if config.include_rush:
            rush_events = self.generate_drum_rush(
                bars=transition_bars,
                start_division=config.rush_start_division,
                end_division=config.rush_end_division,
                offset_ticks=transition_start
            )
            # Filter out events in breath zone
            if breath_range:
                rush_events = [e for e in rush_events
                              if not (breath_range[0] <= e[0] < breath_range[1])]
            result['kick'].extend(rush_events)

        # Snare roll
        if config.include_roll:
            # Roll in the last bar
            roll_start = next_section_start_tick - self.ticks_per_bar
            roll_events = self.generate_snare_roll(
                bars=1,
                division=config.roll_division,
                offset_ticks=roll_start
            )
            if breath_range:
                roll_events = [e for e in roll_events
                              if not (breath_range[0] <= e[0] < breath_range[1])]
            result['snare'].extend(roll_events)

            # Also add clap roll
            clap_roll = self.generate_snare_roll(
                bars=1,
                division=16,  # Slightly slower for clap
                offset_ticks=roll_start,
                note=self.CLAP_NOTE,
                start_velocity=50,
                end_velocity=110
            )
            if breath_range:
                clap_roll = [e for e in clap_roll
                            if not (breath_range[0] <= e[0] < breath_range[1])]
            result['clap'].extend(clap_roll)

        # Riser
        if config.include_riser:
            # Riser spans full transition
            riser_events = self.generate_riser(
                bars=transition_bars,
                offset_ticks=transition_start
            )
            result['riser'].extend(riser_events)

        # Crash on the drop
        if config.include_crash:
            crash_events = self.generate_crash(
                offset_ticks=next_section_start_tick
            )
            result['crash'].extend(crash_events)

        return result


def get_transition_for_sections(
    from_section_type: str,
    to_section_type: str,
    from_section_end_bar: int,
    tempo: int = 138,
    ticks_per_beat: int = 480
) -> dict:
    """
    Convenience function to get transition events between sections.

    Args:
        from_section_type: Type of section ending (e.g., "breakdown")
        to_section_type: Type of section starting (e.g., "drop")
        from_section_end_bar: Bar number where the section ends
        tempo: BPM
        ticks_per_beat: MIDI resolution

    Returns:
        Dict of track_name -> list of MIDI events
    """
    gen = TransitionGenerator(tempo, ticks_per_beat)
    config = gen.get_transition_config(from_section_type, to_section_type)

    ticks_per_bar = ticks_per_beat * 4
    section_end_tick = from_section_end_bar * ticks_per_bar
    next_section_start_tick = section_end_tick

    return gen.generate_full_transition(config, section_end_tick, next_section_start_tick)


# Demo
if __name__ == "__main__":
    print("Transition Generator Demo")
    print("=" * 50)

    gen = TransitionGenerator(tempo=138)

    # Test breakdown -> drop transition
    config = gen.get_transition_config("breakdown", "drop")
    print(f"\nBreakdown → Drop transition:")
    print(f"  Type: {config.transition_type.value}")
    print(f"  Bars: {config.bars}")
    print(f"  Rush: {config.include_rush}")
    print(f"  Roll: {config.include_roll}")
    print(f"  Riser: {config.include_riser}")
    print(f"  Crash: {config.include_crash}")
    print(f"  Breath: {config.include_breath}")

    # Generate transition
    section_end = 80 * gen.ticks_per_bar  # End of bar 80
    transitions = gen.generate_full_transition(config, section_end, section_end)

    print(f"\nGenerated events:")
    for track, events in transitions.items():
        if events:
            print(f"  {track}: {len(events)} events")
