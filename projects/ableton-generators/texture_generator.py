"""
Texture Generator - Foley/Texture Layer

Generates ambient textures, risers, impacts, and atmospheric elements
based on mood and energy level for electronic music production.

Texture Types:
- Ambient pads (sustained atmospheric backgrounds)
- Risers (upward pitch sweeps for builds)
- Impacts (downbeats, hits, crashes)
- Downlifters (falling sweeps after drops)
- Noise sweeps (filtered white noise transitions)
- Sub drops (low frequency impacts)
- Atmospheres (evolving textural beds)

Moods:
- dark: Minor keys, lower frequencies, ominous textures
- euphoric: Major feel, bright textures, uplifting energy
- aggressive: Harsh textures, punchy impacts, distorted
- hypnotic: Subtle, evolving, repetitive textures
- melancholic: Sad, emotional, sparse textures
- ethereal: Airy, spacious, reverberant textures
- industrial: Metallic, mechanical, gritty textures
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from enum import Enum
import random
import math

from config import Config, DEFAULT_CONFIG


class TextureType(Enum):
    """Types of texture elements."""
    AMBIENT_PAD = "ambient_pad"
    RISER = "riser"
    IMPACT = "impact"
    DOWNLIFTER = "downlifter"
    NOISE_SWEEP = "noise_sweep"
    SUB_DROP = "sub_drop"
    ATMOSPHERE = "atmosphere"
    REVERSE_CRASH = "reverse_crash"
    WHITE_NOISE = "white_noise"
    TENSION_RISER = "tension_riser"


class Mood(Enum):
    """Mood presets that affect texture characteristics."""
    DARK = "dark"
    EUPHORIC = "euphoric"
    AGGRESSIVE = "aggressive"
    HYPNOTIC = "hypnotic"
    MELANCHOLIC = "melancholic"
    ETHEREAL = "ethereal"
    INDUSTRIAL = "industrial"
    MYSTERIOUS = "mysterious"
    UPLIFTING = "uplifting"
    TENSE = "tense"


@dataclass
class TextureConfig:
    """Configuration for a texture element."""
    texture_type: TextureType
    bars: int = 4
    intensity: float = 0.7          # 0-1, overall intensity
    pitch_range: Tuple[int, int] = (36, 84)  # MIDI note range
    velocity_range: Tuple[int, int] = (60, 100)
    use_pitch_bend: bool = True     # Use pitch bend for smooth sweeps
    use_mod_wheel: bool = True      # CC1 for modulation/filter
    fade_in: bool = False
    fade_out: bool = False
    humanize: bool = True           # Add subtle timing/velocity variations


# Mood-specific parameter adjustments
MOOD_PARAMETERS: Dict[Mood, Dict] = {
    Mood.DARK: {
        "pitch_offset": -12,        # Lower octave
        "velocity_mod": -10,        # Slightly softer
        "preferred_intervals": [0, 3, 5, 7, 10],  # Minor intervals
        "noise_filter_start": 20,   # Low filter cutoff
        "noise_filter_end": 60,
        "riser_curve": 0.5,         # Slower rise
        "impact_velocity": 127,
        "atmosphere_density": 0.6,
    },
    Mood.EUPHORIC: {
        "pitch_offset": 0,
        "velocity_mod": 10,
        "preferred_intervals": [0, 4, 7, 12, 16],  # Major/bright
        "noise_filter_start": 40,
        "noise_filter_end": 127,
        "riser_curve": 0.8,         # Dramatic rise
        "impact_velocity": 127,
        "atmosphere_density": 0.8,
    },
    Mood.AGGRESSIVE: {
        "pitch_offset": -6,
        "velocity_mod": 20,
        "preferred_intervals": [0, 1, 6, 7, 12],  # Dissonant
        "noise_filter_start": 60,
        "noise_filter_end": 127,
        "riser_curve": 0.9,         # Sharp rise
        "impact_velocity": 127,
        "atmosphere_density": 0.9,
    },
    Mood.HYPNOTIC: {
        "pitch_offset": 0,
        "velocity_mod": -20,
        "preferred_intervals": [0, 5, 7, 12],  # Perfect intervals
        "noise_filter_start": 30,
        "noise_filter_end": 80,
        "riser_curve": 0.4,         # Gradual
        "impact_velocity": 90,
        "atmosphere_density": 0.5,
    },
    Mood.MELANCHOLIC: {
        "pitch_offset": 0,
        "velocity_mod": -15,
        "preferred_intervals": [0, 3, 5, 8, 10],  # Minor/diminished
        "noise_filter_start": 20,
        "noise_filter_end": 70,
        "riser_curve": 0.3,
        "impact_velocity": 80,
        "atmosphere_density": 0.4,
    },
    Mood.ETHEREAL: {
        "pitch_offset": 12,         # Higher octave
        "velocity_mod": -25,
        "preferred_intervals": [0, 4, 7, 11, 14],  # Major 7th feel
        "noise_filter_start": 50,
        "noise_filter_end": 100,
        "riser_curve": 0.5,
        "impact_velocity": 70,
        "atmosphere_density": 0.3,
    },
    Mood.INDUSTRIAL: {
        "pitch_offset": -12,
        "velocity_mod": 15,
        "preferred_intervals": [0, 1, 5, 6, 11],  # Harsh intervals
        "noise_filter_start": 80,
        "noise_filter_end": 127,
        "riser_curve": 0.95,        # Very sharp
        "impact_velocity": 127,
        "atmosphere_density": 0.7,
    },
    Mood.MYSTERIOUS: {
        "pitch_offset": 0,
        "velocity_mod": -10,
        "preferred_intervals": [0, 2, 5, 7, 9],  # Whole tone feel
        "noise_filter_start": 30,
        "noise_filter_end": 90,
        "riser_curve": 0.6,
        "impact_velocity": 85,
        "atmosphere_density": 0.5,
    },
    Mood.UPLIFTING: {
        "pitch_offset": 5,
        "velocity_mod": 5,
        "preferred_intervals": [0, 4, 5, 7, 12],  # Major
        "noise_filter_start": 50,
        "noise_filter_end": 127,
        "riser_curve": 0.75,
        "impact_velocity": 110,
        "atmosphere_density": 0.7,
    },
    Mood.TENSE: {
        "pitch_offset": -3,
        "velocity_mod": 0,
        "preferred_intervals": [0, 1, 4, 6, 7],  # Tritone/minor 2nd
        "noise_filter_start": 40,
        "noise_filter_end": 100,
        "riser_curve": 0.85,
        "impact_velocity": 100,
        "atmosphere_density": 0.6,
    },
}


# Texture presets for different section types
SECTION_TEXTURE_PRESETS = {
    "intro": {
        "textures": [TextureType.ATMOSPHERE, TextureType.AMBIENT_PAD],
        "intensity": 0.4,
        "fade_in": True,
    },
    "buildup": {
        "textures": [TextureType.RISER, TextureType.NOISE_SWEEP, TextureType.TENSION_RISER],
        "intensity": 0.8,
        "fade_in": False,
    },
    "breakdown": {
        "textures": [TextureType.AMBIENT_PAD, TextureType.ATMOSPHERE],
        "intensity": 0.5,
        "fade_in": True,
    },
    "drop": {
        "textures": [TextureType.IMPACT, TextureType.SUB_DROP],
        "intensity": 1.0,
        "fade_in": False,
    },
    "break": {
        "textures": [TextureType.DOWNLIFTER, TextureType.ATMOSPHERE],
        "intensity": 0.3,
        "fade_in": False,
    },
    "outro": {
        "textures": [TextureType.AMBIENT_PAD, TextureType.ATMOSPHERE],
        "intensity": 0.4,
        "fade_out": True,
    },
}


class TextureGenerator:
    """Generates MIDI-based texture elements for atmospheric effects."""

    # MIDI channels for different texture types
    CHANNEL_PAD = 0
    CHANNEL_FX = 1
    CHANNEL_NOISE = 2

    def __init__(
        self,
        tempo: int = 138,
        key: str = "A",
        scale: str = "minor",
        mood: Mood = Mood.EUPHORIC,
        ticks_per_beat: int = 480
    ):
        self.tempo = tempo
        self.key = key
        self.scale = scale
        self.mood = mood
        self.ticks_per_beat = ticks_per_beat
        self.ticks_per_bar = ticks_per_beat * 4
        self.mood_params = MOOD_PARAMETERS.get(mood, MOOD_PARAMETERS[Mood.EUPHORIC])

    def set_mood(self, mood: Mood):
        """Update the mood and its parameters."""
        self.mood = mood
        self.mood_params = MOOD_PARAMETERS.get(mood, MOOD_PARAMETERS[Mood.EUPHORIC])

    def _get_root_note(self, octave: int = 4) -> int:
        """Get MIDI note number for the root note."""
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        note_idx = notes.index(self.key.upper().replace('b', '#'))
        return note_idx + (octave + 1) * 12

    def _apply_humanization(
        self,
        tick: int,
        velocity: int,
        timing_range: int = 10,
        velocity_range: int = 8
    ) -> Tuple[int, int]:
        """Apply subtle humanization to timing and velocity."""
        tick_offset = random.randint(-timing_range, timing_range)
        vel_offset = random.randint(-velocity_range, velocity_range)
        return (max(0, tick + tick_offset), max(1, min(127, velocity + vel_offset)))

    # =========================================================================
    # AMBIENT PAD - Sustained atmospheric background
    # =========================================================================

    def generate_ambient_pad(
        self,
        bars: int = 8,
        intensity: float = 0.6,
        offset_ticks: int = 0,
        fade_in: bool = False,
        fade_out: bool = False
    ) -> List[Tuple]:
        """
        Generate sustained ambient pad notes.

        Creates long, evolving pad notes that provide atmospheric background.
        Uses the mood's preferred intervals to create harmonic texture.
        """
        events = []
        total_ticks = bars * self.ticks_per_bar

        root = self._get_root_note(4) + self.mood_params["pitch_offset"]
        intervals = self.mood_params["preferred_intervals"]

        base_velocity = int(60 + intensity * 40 + self.mood_params["velocity_mod"])
        base_velocity = max(30, min(100, base_velocity))

        # Create layered pad notes
        num_layers = 2 if intensity < 0.5 else 3
        note_length = total_ticks - 100  # Slight release before end

        for i in range(num_layers):
            interval = intervals[i % len(intervals)]
            note = root + interval

            # Stagger entry slightly for richness
            entry_offset = i * (self.ticks_per_beat // 4)
            tick = offset_ticks + entry_offset

            # Velocity variation between layers
            vel = base_velocity - (i * 10)

            # Apply fade envelope via velocity
            if fade_in:
                vel = int(vel * 0.3)  # Start quiet

            events.append((tick, 'note_on', note, max(20, vel)))
            events.append((tick + note_length - entry_offset, 'note_off', note))

        # Add mod wheel automation for movement
        if intensity > 0.4:
            events.extend(self._generate_mod_wheel_sweep(
                offset_ticks, total_ticks,
                start_value=40, end_value=90,
                curve=0.5
            ))

        return events

    # =========================================================================
    # RISER - Upward pitch sweep for builds
    # =========================================================================

    def generate_riser(
        self,
        bars: int = 4,
        intensity: float = 0.8,
        offset_ticks: int = 0,
        riser_type: str = "pitch"  # "pitch", "noise", "layered"
    ) -> List[Tuple]:
        """
        Generate riser/uplift effect.

        Creates ascending pitch or filter sweep for building energy.

        Args:
            bars: Length in bars
            intensity: 0-1, affects velocity and pitch range
            offset_ticks: Start position
            riser_type: Type of riser effect
        """
        events = []
        total_ticks = bars * self.ticks_per_bar

        curve = self.mood_params["riser_curve"]

        if riser_type == "pitch":
            events.extend(self._generate_pitch_riser(
                bars, intensity, offset_ticks, curve
            ))
        elif riser_type == "noise":
            events.extend(self._generate_noise_riser(
                bars, intensity, offset_ticks
            ))
        elif riser_type == "layered":
            events.extend(self._generate_pitch_riser(
                bars, intensity * 0.7, offset_ticks, curve
            ))
            events.extend(self._generate_noise_riser(
                bars, intensity * 0.5, offset_ticks
            ))

        return events

    def _generate_pitch_riser(
        self,
        bars: int,
        intensity: float,
        offset_ticks: int,
        curve: float
    ) -> List[Tuple]:
        """Generate rising pitch pattern."""
        events = []
        total_ticks = bars * self.ticks_per_bar

        # Start low, end high
        start_note = self._get_root_note(2) + self.mood_params["pitch_offset"]
        pitch_range = int(24 + intensity * 24)  # 2-4 octaves
        end_note = start_note + pitch_range

        # Number of note steps (more = smoother)
        num_steps = bars * 4  # One note per beat
        step_length = total_ticks // num_steps

        base_velocity = int(60 + intensity * 50)

        for i in range(num_steps):
            tick = offset_ticks + i * step_length

            # Apply curve to progress
            progress = i / max(1, num_steps - 1)
            curved_progress = progress ** (1 / curve)  # Curve affects acceleration

            note = int(start_note + (end_note - start_note) * curved_progress)
            note = max(24, min(108, note))

            # Velocity increases throughout
            vel = int(base_velocity * (0.5 + 0.5 * progress))
            vel = min(127, vel + self.mood_params["velocity_mod"])

            events.append((tick, 'note_on', note, vel))
            events.append((tick + step_length - 20, 'note_off', note))

        return events

    def _generate_noise_riser(
        self,
        bars: int,
        intensity: float,
        offset_ticks: int
    ) -> List[Tuple]:
        """Generate filter sweep riser using mod wheel and sustained note."""
        events = []
        total_ticks = bars * self.ticks_per_bar

        # Single sustained noise note
        noise_note = 60  # C4 - will be filtered
        velocity = int(80 + intensity * 40)

        events.append((offset_ticks, 'note_on', noise_note, velocity))
        events.append((offset_ticks + total_ticks - 20, 'note_off', noise_note))

        # Filter sweep via mod wheel (CC1)
        filter_start = self.mood_params["noise_filter_start"]
        filter_end = self.mood_params["noise_filter_end"]

        events.extend(self._generate_mod_wheel_sweep(
            offset_ticks, total_ticks,
            start_value=filter_start,
            end_value=filter_end,
            curve=self.mood_params["riser_curve"]
        ))

        # Pitch bend for additional sweep (optional)
        events.extend(self._generate_pitch_bend_sweep(
            offset_ticks, total_ticks,
            start_value=0,
            end_value=8191,  # Max pitch bend up
            curve=self.mood_params["riser_curve"]
        ))

        return events

    # =========================================================================
    # IMPACT - Downbeat hits and crashes
    # =========================================================================

    def generate_impact(
        self,
        offset_ticks: int = 0,
        intensity: float = 1.0,
        impact_type: str = "full"  # "full", "sub", "crash", "hit"
    ) -> List[Tuple]:
        """
        Generate impact/hit on the downbeat.

        Creates punchy transient for drop entries and accents.
        """
        events = []

        base_velocity = int(self.mood_params["impact_velocity"] * intensity)

        if impact_type in ["full", "crash"]:
            # Crash/impact layer - high frequency content
            crash_note = 84  # High C
            events.append((offset_ticks, 'note_on', crash_note, base_velocity))
            events.append((offset_ticks + self.ticks_per_beat * 2, 'note_off', crash_note))

        if impact_type in ["full", "sub"]:
            # Sub layer - low frequency thump
            sub_note = self._get_root_note(1) + self.mood_params["pitch_offset"]
            sub_velocity = min(127, base_velocity + 10)
            events.append((offset_ticks, 'note_on', sub_note, sub_velocity))
            events.append((offset_ticks + self.ticks_per_beat, 'note_off', sub_note))

        if impact_type in ["full", "hit"]:
            # Mid layer - body
            mid_note = self._get_root_note(3)
            events.append((offset_ticks, 'note_on', mid_note, base_velocity - 10))
            events.append((offset_ticks + self.ticks_per_beat // 2, 'note_off', mid_note))

        return events

    # =========================================================================
    # DOWNLIFTER - Falling sweep after drops
    # =========================================================================

    def generate_downlifter(
        self,
        bars: int = 2,
        intensity: float = 0.7,
        offset_ticks: int = 0
    ) -> List[Tuple]:
        """
        Generate downward pitch/filter sweep.

        Creates falling effect for post-drop transitions.
        """
        events = []
        total_ticks = bars * self.ticks_per_bar

        # High to low pitch sweep
        start_note = self._get_root_note(5) + self.mood_params["pitch_offset"]
        end_note = self._get_root_note(2) + self.mood_params["pitch_offset"]

        num_steps = bars * 4
        step_length = total_ticks // num_steps

        base_velocity = int(80 + intensity * 30)

        for i in range(num_steps):
            tick = offset_ticks + i * step_length

            # Exponential decay curve
            progress = i / max(1, num_steps - 1)
            curved_progress = 1 - ((1 - progress) ** 2)

            note = int(start_note - (start_note - end_note) * curved_progress)

            # Velocity decreases
            vel = int(base_velocity * (1 - progress * 0.6))
            vel = max(30, vel)

            events.append((tick, 'note_on', note, vel))
            events.append((tick + step_length - 20, 'note_off', note))

        # Falling filter via mod wheel
        events.extend(self._generate_mod_wheel_sweep(
            offset_ticks, total_ticks,
            start_value=100, end_value=20,
            curve=0.5
        ))

        return events

    # =========================================================================
    # SUB DROP - Low frequency impact
    # =========================================================================

    def generate_sub_drop(
        self,
        offset_ticks: int = 0,
        intensity: float = 1.0,
        sustain_bars: float = 0.5
    ) -> List[Tuple]:
        """
        Generate sub-bass drop impact.

        Deep low-frequency thump with pitch decay.
        """
        events = []

        sustain_ticks = int(sustain_bars * self.ticks_per_bar)

        # Sub note
        sub_note = self._get_root_note(1) + self.mood_params["pitch_offset"]
        velocity = int(100 + intensity * 27)

        events.append((offset_ticks, 'note_on', sub_note, min(127, velocity)))
        events.append((offset_ticks + sustain_ticks, 'note_off', sub_note))

        # Pitch bend down for "wub" effect
        events.extend(self._generate_pitch_bend_sweep(
            offset_ticks, sustain_ticks,
            start_value=4096,  # Slightly up
            end_value=-4096,   # Down
            curve=0.3          # Fast initial drop
        ))

        return events

    # =========================================================================
    # ATMOSPHERE - Evolving textural bed
    # =========================================================================

    def generate_atmosphere(
        self,
        bars: int = 8,
        intensity: float = 0.5,
        offset_ticks: int = 0,
        density: float = None
    ) -> List[Tuple]:
        """
        Generate evolving atmospheric texture.

        Creates sparse, evolving notes that form a textural bed.
        """
        events = []
        total_ticks = bars * self.ticks_per_bar

        if density is None:
            density = self.mood_params["atmosphere_density"]

        root = self._get_root_note(4) + self.mood_params["pitch_offset"]
        intervals = self.mood_params["preferred_intervals"]

        base_velocity = int(40 + intensity * 40 + self.mood_params["velocity_mod"])
        base_velocity = max(20, min(80, base_velocity))

        # Number of texture events based on density
        num_events = int(bars * 2 * density)

        for i in range(num_events):
            # Random position within the duration
            tick = offset_ticks + random.randint(0, total_ticks - self.ticks_per_beat)

            # Random interval from mood palette
            interval = random.choice(intervals)
            octave_shift = random.choice([0, 12, -12]) if intensity > 0.5 else 0
            note = root + interval + octave_shift

            # Random note length (1-4 beats)
            note_length = random.randint(1, 4) * self.ticks_per_beat

            # Humanized velocity
            vel = base_velocity + random.randint(-15, 15)
            vel = max(20, min(100, vel))

            events.append((tick, 'note_on', note, vel))
            events.append((tick + note_length, 'note_off', note))

        # Slow mod wheel movement for evolution
        events.extend(self._generate_mod_wheel_lfo(
            offset_ticks, total_ticks,
            center=60, depth=30, cycles=bars / 4
        ))

        return events

    # =========================================================================
    # NOISE SWEEP - Filtered white noise transition
    # =========================================================================

    def generate_noise_sweep(
        self,
        bars: int = 2,
        intensity: float = 0.7,
        offset_ticks: int = 0,
        direction: str = "up"  # "up", "down", "peak"
    ) -> List[Tuple]:
        """
        Generate filtered noise sweep.

        White noise with filter automation for transitions.
        """
        events = []
        total_ticks = bars * self.ticks_per_bar

        # Sustained noise note
        noise_note = 60
        velocity = int(60 + intensity * 50)

        events.append((offset_ticks, 'note_on', noise_note, velocity))
        events.append((offset_ticks + total_ticks - 20, 'note_off', noise_note))

        # Filter sweep based on direction
        filter_start = self.mood_params["noise_filter_start"]
        filter_end = self.mood_params["noise_filter_end"]

        if direction == "up":
            events.extend(self._generate_mod_wheel_sweep(
                offset_ticks, total_ticks,
                start_value=filter_start,
                end_value=filter_end,
                curve=0.7
            ))
        elif direction == "down":
            events.extend(self._generate_mod_wheel_sweep(
                offset_ticks, total_ticks,
                start_value=filter_end,
                end_value=filter_start,
                curve=0.7
            ))
        elif direction == "peak":
            # Rise then fall
            half_ticks = total_ticks // 2
            events.extend(self._generate_mod_wheel_sweep(
                offset_ticks, half_ticks,
                start_value=filter_start,
                end_value=filter_end,
                curve=0.8
            ))
            events.extend(self._generate_mod_wheel_sweep(
                offset_ticks + half_ticks, half_ticks,
                start_value=filter_end,
                end_value=filter_start,
                curve=0.6
            ))

        return events

    # =========================================================================
    # TENSION RISER - Dramatic multi-layer build
    # =========================================================================

    def generate_tension_riser(
        self,
        bars: int = 8,
        intensity: float = 0.9,
        offset_ticks: int = 0
    ) -> List[Tuple]:
        """
        Generate dramatic tension-building riser.

        Combines multiple elements for maximum build impact.
        """
        events = []

        # Layer 1: Pitch riser
        events.extend(self._generate_pitch_riser(
            bars, intensity * 0.8, offset_ticks,
            self.mood_params["riser_curve"]
        ))

        # Layer 2: Noise sweep in second half
        half_bars = bars // 2
        half_ticks = half_bars * self.ticks_per_bar
        events.extend(self.generate_noise_sweep(
            half_bars, intensity * 0.6,
            offset_ticks + half_ticks, "up"
        ))

        # Layer 3: Accelerating pulse in final bars
        final_bars = min(2, bars // 2)
        final_start = offset_ticks + (bars - final_bars) * self.ticks_per_bar
        events.extend(self._generate_accelerating_pulse(
            final_bars, intensity, final_start
        ))

        return events

    def _generate_accelerating_pulse(
        self,
        bars: int,
        intensity: float,
        offset_ticks: int
    ) -> List[Tuple]:
        """Generate accelerating rhythmic pulse."""
        events = []
        total_ticks = bars * self.ticks_per_bar

        note = self._get_root_note(3)
        base_velocity = int(70 + intensity * 40)

        # Start with quarter notes, accelerate to 32nds
        divisions = [4, 8, 16, 32]
        ticks_per_phase = total_ticks // len(divisions)

        current_tick = offset_ticks

        for div_idx, division in enumerate(divisions):
            note_length = self.ticks_per_beat * 4 // division
            notes_in_phase = ticks_per_phase // note_length

            # Velocity increases with acceleration
            phase_velocity = base_velocity + (div_idx * 10)

            for i in range(notes_in_phase):
                tick = current_tick + i * note_length
                vel = min(127, phase_velocity)

                events.append((tick, 'note_on', note, vel))
                events.append((tick + note_length // 2, 'note_off', note))

            current_tick += ticks_per_phase

        return events

    # =========================================================================
    # REVERSE CRASH - Reversed cymbal effect
    # =========================================================================

    def generate_reverse_crash(
        self,
        bars: int = 1,
        intensity: float = 0.8,
        offset_ticks: int = 0
    ) -> List[Tuple]:
        """
        Generate reverse crash/swell effect.

        Crescendo leading into a downbeat.
        """
        events = []
        total_ticks = bars * self.ticks_per_bar

        crash_note = 84  # High C

        # Volume envelope via velocity layering
        num_layers = 8
        layer_length = total_ticks // num_layers

        for i in range(num_layers):
            tick = offset_ticks + i * layer_length

            # Exponential velocity increase
            progress = i / (num_layers - 1)
            vel = int(30 + (intensity * 97) * (progress ** 2))
            vel = min(127, vel)

            events.append((tick, 'note_on', crash_note, vel))
            events.append((tick + layer_length - 10, 'note_off', crash_note))

        return events

    # =========================================================================
    # HELPER METHODS - CC/Pitch Bend automation
    # =========================================================================

    def _generate_mod_wheel_sweep(
        self,
        offset_ticks: int,
        duration_ticks: int,
        start_value: int,
        end_value: int,
        curve: float = 0.5
    ) -> List[Tuple]:
        """Generate mod wheel (CC1) automation sweep."""
        events = []

        # Number of CC messages (more = smoother)
        num_steps = max(8, duration_ticks // (self.ticks_per_beat // 2))
        step_ticks = duration_ticks // num_steps

        for i in range(num_steps + 1):
            tick = offset_ticks + i * step_ticks

            progress = i / num_steps
            curved_progress = progress ** (1 / curve) if curve != 0 else progress

            value = int(start_value + (end_value - start_value) * curved_progress)
            value = max(0, min(127, value))

            events.append((tick, 'cc', 1, value))  # CC1 = Mod Wheel

        return events

    def _generate_mod_wheel_lfo(
        self,
        offset_ticks: int,
        duration_ticks: int,
        center: int = 64,
        depth: int = 30,
        cycles: float = 2
    ) -> List[Tuple]:
        """Generate LFO-style mod wheel movement."""
        events = []

        num_steps = int(cycles * 32)  # 32 points per cycle
        step_ticks = duration_ticks // num_steps

        for i in range(num_steps):
            tick = offset_ticks + i * step_ticks

            # Sine wave
            phase = (i / num_steps) * cycles * 2 * math.pi
            value = int(center + depth * math.sin(phase))
            value = max(0, min(127, value))

            events.append((tick, 'cc', 1, value))

        return events

    def _generate_pitch_bend_sweep(
        self,
        offset_ticks: int,
        duration_ticks: int,
        start_value: int,
        end_value: int,
        curve: float = 0.5
    ) -> List[Tuple]:
        """Generate pitch bend automation sweep."""
        events = []

        num_steps = max(8, duration_ticks // (self.ticks_per_beat // 2))
        step_ticks = duration_ticks // num_steps

        for i in range(num_steps + 1):
            tick = offset_ticks + i * step_ticks

            progress = i / num_steps
            curved_progress = progress ** (1 / curve) if curve != 0 else progress

            value = int(start_value + (end_value - start_value) * curved_progress)
            value = max(-8192, min(8191, value))

            events.append((tick, 'pitch_bend', value))

        return events

    # =========================================================================
    # SECTION-BASED GENERATION
    # =========================================================================

    def generate_for_section(
        self,
        section_type: str,
        bars: int,
        offset_ticks: int = 0,
        intensity: float = None
    ) -> Dict[str, List[Tuple]]:
        """
        Generate appropriate textures for a song section.

        Args:
            section_type: 'intro', 'buildup', 'breakdown', 'drop', 'break', 'outro'
            bars: Length of section
            offset_ticks: Start position
            intensity: Override intensity (uses preset if None)

        Returns:
            Dict of texture_type -> events
        """
        preset = SECTION_TEXTURE_PRESETS.get(
            section_type.lower(),
            SECTION_TEXTURE_PRESETS["breakdown"]
        )

        if intensity is None:
            intensity = preset["intensity"]

        result = {}

        for texture_type in preset["textures"]:
            events = []

            if texture_type == TextureType.AMBIENT_PAD:
                events = self.generate_ambient_pad(
                    bars, intensity, offset_ticks,
                    fade_in=preset.get("fade_in", False),
                    fade_out=preset.get("fade_out", False)
                )
            elif texture_type == TextureType.ATMOSPHERE:
                events = self.generate_atmosphere(
                    bars, intensity, offset_ticks
                )
            elif texture_type == TextureType.RISER:
                events = self.generate_riser(
                    bars, intensity, offset_ticks, "layered"
                )
            elif texture_type == TextureType.TENSION_RISER:
                events = self.generate_tension_riser(
                    bars, intensity, offset_ticks
                )
            elif texture_type == TextureType.NOISE_SWEEP:
                events = self.generate_noise_sweep(
                    bars, intensity, offset_ticks, "up"
                )
            elif texture_type == TextureType.IMPACT:
                events = self.generate_impact(
                    offset_ticks, intensity, "full"
                )
            elif texture_type == TextureType.SUB_DROP:
                events = self.generate_sub_drop(
                    offset_ticks, intensity
                )
            elif texture_type == TextureType.DOWNLIFTER:
                events = self.generate_downlifter(
                    min(bars, 4), intensity, offset_ticks
                )
            elif texture_type == TextureType.REVERSE_CRASH:
                events = self.generate_reverse_crash(
                    min(bars, 2), intensity, offset_ticks
                )

            if events:
                result[texture_type.value] = events

        return result

    def generate_full_song_textures(
        self,
        structure: Dict[str, int],
        energy_curve: Dict[str, float] = None
    ) -> Dict[str, List[Tuple]]:
        """
        Generate textures for an entire song structure.

        Args:
            structure: Dict of section_name -> bars
            energy_curve: Optional dict of section_name -> energy (0-1)

        Returns:
            Dict of texture_type -> all events for that texture
        """
        all_textures = {}
        current_tick = 0

        for section_name, bars in structure.items():
            # Determine section type from name
            section_type = self._infer_section_type(section_name)

            # Get energy for this section
            energy = 0.5
            if energy_curve and section_name in energy_curve:
                energy = energy_curve[section_name]

            # Generate textures for section
            section_textures = self.generate_for_section(
                section_type, bars, current_tick, energy
            )

            # Merge into all_textures
            for tex_type, events in section_textures.items():
                if tex_type not in all_textures:
                    all_textures[tex_type] = []
                all_textures[tex_type].extend(events)

            current_tick += bars * self.ticks_per_bar

        return all_textures

    def _infer_section_type(self, section_name: str) -> str:
        """Infer section type from section name."""
        name = section_name.lower()

        if "intro" in name:
            return "intro"
        elif "buildup" in name or "build" in name:
            return "buildup"
        elif "breakdown" in name:
            return "breakdown"
        elif "drop" in name:
            return "drop"
        elif "break" in name:
            return "break"
        elif "outro" in name:
            return "outro"
        else:
            return "breakdown"  # Default


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_mood_from_string(mood_str: str) -> Mood:
    """Convert string to Mood enum."""
    mood_map = {
        "dark": Mood.DARK,
        "euphoric": Mood.EUPHORIC,
        "aggressive": Mood.AGGRESSIVE,
        "hypnotic": Mood.HYPNOTIC,
        "melancholic": Mood.MELANCHOLIC,
        "ethereal": Mood.ETHEREAL,
        "industrial": Mood.INDUSTRIAL,
        "mysterious": Mood.MYSTERIOUS,
        "uplifting": Mood.UPLIFTING,
        "tense": Mood.TENSE,
    }
    return mood_map.get(mood_str.lower(), Mood.EUPHORIC)


def generate_texture_for_mood(
    texture_type: str,
    mood: str,
    bars: int = 4,
    key: str = "A",
    tempo: int = 138
) -> List[Tuple]:
    """
    Convenience function to generate a single texture.

    Args:
        texture_type: 'riser', 'impact', 'downlifter', 'atmosphere', etc.
        mood: 'dark', 'euphoric', 'aggressive', etc.
        bars: Length in bars
        key: Musical key
        tempo: BPM

    Returns:
        List of MIDI events
    """
    gen = TextureGenerator(
        tempo=tempo,
        key=key,
        mood=get_mood_from_string(mood)
    )

    texture_map = {
        "riser": lambda: gen.generate_riser(bars, 0.8),
        "impact": lambda: gen.generate_impact(0, 1.0),
        "downlifter": lambda: gen.generate_downlifter(bars, 0.7),
        "atmosphere": lambda: gen.generate_atmosphere(bars, 0.5),
        "ambient_pad": lambda: gen.generate_ambient_pad(bars, 0.6),
        "noise_sweep": lambda: gen.generate_noise_sweep(bars, 0.7),
        "sub_drop": lambda: gen.generate_sub_drop(0, 1.0),
        "tension_riser": lambda: gen.generate_tension_riser(bars, 0.9),
        "reverse_crash": lambda: gen.generate_reverse_crash(min(bars, 2), 0.8),
    }

    generator_func = texture_map.get(texture_type.lower())
    if generator_func:
        return generator_func()
    else:
        raise ValueError(f"Unknown texture type: {texture_type}")


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEXTURE GENERATOR - Foley/Texture Layer Demo")
    print("=" * 60)
    print()

    # Test different moods
    moods = [Mood.DARK, Mood.EUPHORIC, Mood.AGGRESSIVE, Mood.HYPNOTIC]

    for mood in moods:
        print(f"\n{'-' * 40}")
        print(f"Mood: {mood.value.upper()}")
        print(f"{'-' * 40}")

        gen = TextureGenerator(tempo=138, key="A", mood=mood)
        params = gen.mood_params

        print(f"  Pitch offset: {params['pitch_offset']}")
        print(f"  Velocity mod: {params['velocity_mod']}")
        print(f"  Riser curve:  {params['riser_curve']}")
        print(f"  Impact vel:   {params['impact_velocity']}")
        print(f"  Atmos density: {params['atmosphere_density']}")

        # Generate sample textures
        riser = gen.generate_riser(bars=4, intensity=0.8)
        print(f"  Riser events: {len(riser)}")

        impact = gen.generate_impact(intensity=1.0)
        print(f"  Impact events: {len(impact)}")

        atmos = gen.generate_atmosphere(bars=8, intensity=0.5)
        print(f"  Atmosphere events: {len(atmos)}")

    print()
    print("=" * 60)
    print("Section-based generation test")
    print("=" * 60)

    gen = TextureGenerator(tempo=138, key="A", mood=Mood.EUPHORIC)

    structure = {
        "intro": 16,
        "buildup_1": 16,
        "breakdown_1": 32,
        "drop_1": 32,
        "break": 8,
        "outro": 16,
    }

    energy_curve = {
        "intro": 0.3,
        "buildup_1": 0.7,
        "breakdown_1": 0.4,
        "drop_1": 1.0,
        "break": 0.2,
        "outro": 0.3,
    }

    textures = gen.generate_full_song_textures(structure, energy_curve)

    print("\nGenerated textures per type:")
    for tex_type, events in textures.items():
        print(f"  {tex_type}: {len(events)} events")

    print()
    print("Texture Generator ready!")
