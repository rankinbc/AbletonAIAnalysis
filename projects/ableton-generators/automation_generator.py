#!/usr/bin/env python3
"""
Automation Generator for Ableton Projects

Generates automation curves for common effects:
- Filter sweeps (buildup risers)
- Volume automation (section-based)
- Effect sends (reverb/delay throws)
- Sidechain pumping patterns

Usage:
    from automation_generator import AutomationGenerator

    gen = AutomationGenerator(tempo=138, ticks_per_beat=480)

    # Generate filter sweep automation
    events = gen.filter_sweep(start_bar=32, bars=16, start_freq=200, end_freq=8000)

    # Generate volume fade
    events = gen.volume_fade(start_bar=0, bars=4, start_db=-inf, end_db=0)
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import math


@dataclass
class AutomationPoint:
    """A single automation point."""
    time_beats: float  # Time in beats from start
    value: float       # Normalized value (0.0 - 1.0) or actual value
    curve_type: str = "linear"  # linear, exponential, logarithmic, hold


@dataclass
class AutomationCurve:
    """A complete automation curve."""
    parameter_name: str  # e.g., "Filter Freq", "Volume", "Send A"
    points: List[AutomationPoint]
    value_min: float = 0.0
    value_max: float = 1.0

    def to_midi_events(self, cc_number: int, ticks_per_beat: int = 480) -> List[Tuple[int, int]]:
        """Convert to MIDI CC events (tick, value 0-127)."""
        events = []
        for point in self.points:
            tick = int(point.time_beats * ticks_per_beat)
            # Normalize to 0-127
            normalized = (point.value - self.value_min) / (self.value_max - self.value_min)
            cc_value = int(normalized * 127)
            cc_value = max(0, min(127, cc_value))
            events.append((tick, cc_value))
        return events


class AutomationGenerator:
    """Generates automation curves for various effects."""

    def __init__(self, tempo: int = 138, ticks_per_beat: int = 480):
        self.tempo = tempo
        self.ticks_per_beat = ticks_per_beat

    def _bar_to_beats(self, bar: float) -> float:
        """Convert bar number to beats."""
        return bar * 4  # Assuming 4/4 time

    def _interpolate(
        self,
        start_val: float,
        end_val: float,
        num_points: int,
        curve_type: str = "linear"
    ) -> List[float]:
        """Generate interpolated values between start and end."""
        if num_points <= 1:
            return [start_val]

        values = []
        for i in range(num_points):
            t = i / (num_points - 1)  # 0 to 1

            if curve_type == "linear":
                val = start_val + (end_val - start_val) * t

            elif curve_type == "exponential":
                # Exponential curve (faster at end)
                val = start_val + (end_val - start_val) * (t ** 2)

            elif curve_type == "logarithmic":
                # Logarithmic curve (faster at start)
                val = start_val + (end_val - start_val) * math.sqrt(t)

            elif curve_type == "s_curve":
                # S-curve (smooth start and end)
                t_smooth = t * t * (3 - 2 * t)
                val = start_val + (end_val - start_val) * t_smooth

            elif curve_type == "ease_in":
                # Ease in (slow start)
                val = start_val + (end_val - start_val) * (1 - math.cos(t * math.pi / 2))

            elif curve_type == "ease_out":
                # Ease out (slow end)
                val = start_val + (end_val - start_val) * math.sin(t * math.pi / 2)

            else:
                val = start_val + (end_val - start_val) * t

            values.append(val)

        return values

    def filter_sweep(
        self,
        start_bar: int,
        bars: int,
        start_freq: float = 200,
        end_freq: float = 8000,
        curve_type: str = "exponential",
        resolution: int = 16
    ) -> AutomationCurve:
        """
        Generate a filter sweep automation curve.

        Args:
            start_bar: Starting bar number
            bars: Number of bars for the sweep
            start_freq: Starting frequency in Hz
            end_freq: Ending frequency in Hz
            curve_type: Type of curve (linear, exponential, logarithmic)
            resolution: Number of points per bar

        Returns:
            AutomationCurve with filter frequency points
        """
        total_points = bars * resolution
        start_beat = self._bar_to_beats(start_bar)

        # Use logarithmic for frequency (sounds more linear to ears)
        if curve_type == "exponential":
            # Exponential frequency sweep
            log_start = math.log(start_freq)
            log_end = math.log(end_freq)
            log_values = self._interpolate(log_start, log_end, total_points, "exponential")
            freq_values = [math.exp(v) for v in log_values]
        else:
            freq_values = self._interpolate(start_freq, end_freq, total_points, curve_type)

        points = []
        for i, freq in enumerate(freq_values):
            beat_offset = (i / resolution) * 4  # 4 beats per bar
            points.append(AutomationPoint(
                time_beats=start_beat + beat_offset,
                value=freq,
                curve_type=curve_type
            ))

        return AutomationCurve(
            parameter_name="Filter Frequency",
            points=points,
            value_min=20,
            value_max=20000
        )

    def volume_fade(
        self,
        start_bar: int,
        bars: int,
        start_db: float = -60,
        end_db: float = 0,
        curve_type: str = "logarithmic"
    ) -> AutomationCurve:
        """
        Generate a volume fade automation curve.

        Args:
            start_bar: Starting bar number
            bars: Number of bars for the fade
            start_db: Starting volume in dB (use -60 or lower for silence)
            end_db: Ending volume in dB
            curve_type: Type of curve

        Returns:
            AutomationCurve with volume points (in dB)
        """
        resolution = 8  # Points per bar
        total_points = bars * resolution
        start_beat = self._bar_to_beats(start_bar)

        db_values = self._interpolate(start_db, end_db, total_points, curve_type)

        points = []
        for i, db in enumerate(db_values):
            beat_offset = (i / resolution) * 4
            points.append(AutomationPoint(
                time_beats=start_beat + beat_offset,
                value=db
            ))

        return AutomationCurve(
            parameter_name="Track Volume",
            points=points,
            value_min=-70,
            value_max=6
        )

    def send_throw(
        self,
        bar: int,
        beats: float = 0.5,
        send_level: float = 1.0,
        decay_bars: float = 2.0
    ) -> AutomationCurve:
        """
        Generate a send throw (momentary send increase for effect).

        Args:
            bar: Bar where the throw happens
            beats: Duration of full send in beats
            send_level: Maximum send level (0-1)
            decay_bars: How long the send takes to decay

        Returns:
            AutomationCurve with send level points
        """
        start_beat = self._bar_to_beats(bar)

        points = [
            # Jump to full send
            AutomationPoint(time_beats=start_beat, value=0),
            AutomationPoint(time_beats=start_beat + 0.01, value=send_level),
            # Hold
            AutomationPoint(time_beats=start_beat + beats, value=send_level),
            # Decay
            AutomationPoint(time_beats=start_beat + beats + (decay_bars * 4), value=0),
        ]

        return AutomationCurve(
            parameter_name="Send Level",
            points=points,
            value_min=0,
            value_max=1
        )

    def sidechain_pump(
        self,
        start_bar: int,
        bars: int,
        attack_beats: float = 0.0625,  # 1/16 beat
        release_beats: float = 0.375,   # 3/8 beat
        depth: float = 0.8
    ) -> AutomationCurve:
        """
        Generate a sidechain pumping pattern.

        Args:
            start_bar: Starting bar
            bars: Number of bars
            attack_beats: Attack time in beats
            release_beats: Release time in beats
            depth: Pumping depth (0-1, how much volume drops)

        Returns:
            AutomationCurve with pumping pattern
        """
        start_beat = self._bar_to_beats(start_bar)
        total_beats = bars * 4
        points = []

        # Generate one pump per beat
        beat = 0
        while beat < total_beats:
            # Kick moment - duck down
            points.append(AutomationPoint(
                time_beats=start_beat + beat,
                value=1.0
            ))
            points.append(AutomationPoint(
                time_beats=start_beat + beat + attack_beats,
                value=1.0 - depth
            ))
            # Release back up
            points.append(AutomationPoint(
                time_beats=start_beat + beat + attack_beats + release_beats,
                value=1.0
            ))
            beat += 1

        return AutomationCurve(
            parameter_name="Sidechain Volume",
            points=points,
            value_min=0,
            value_max=1
        )

    def riser_sweep(
        self,
        start_bar: int,
        bars: int,
        include_filter: bool = True,
        include_volume: bool = True,
        include_pitch: bool = False
    ) -> List[AutomationCurve]:
        """
        Generate a complete riser effect with multiple automation curves.

        Args:
            start_bar: Starting bar
            bars: Duration in bars
            include_filter: Include filter sweep
            include_volume: Include volume swell
            include_pitch: Include pitch rise

        Returns:
            List of AutomationCurves for the riser
        """
        curves = []

        if include_filter:
            curves.append(self.filter_sweep(
                start_bar=start_bar,
                bars=bars,
                start_freq=200,
                end_freq=12000,
                curve_type="exponential"
            ))

        if include_volume:
            curves.append(self.volume_fade(
                start_bar=start_bar,
                bars=bars,
                start_db=-20,
                end_db=0,
                curve_type="exponential"
            ))

        if include_pitch:
            # Pitch bend from -12 to 0 semitones
            resolution = 8
            total_points = bars * resolution
            start_beat = self._bar_to_beats(start_bar)

            pitch_values = self._interpolate(-12, 0, total_points, "exponential")
            points = []
            for i, pitch in enumerate(pitch_values):
                beat_offset = (i / resolution) * 4
                points.append(AutomationPoint(
                    time_beats=start_beat + beat_offset,
                    value=pitch
                ))

            curves.append(AutomationCurve(
                parameter_name="Pitch Bend",
                points=points,
                value_min=-24,
                value_max=24
            ))

        return curves

    def impact_drop(
        self,
        bar: int,
        filter_drop: bool = True,
        volume_drop: bool = False
    ) -> List[AutomationCurve]:
        """
        Generate impact/drop automation (sudden filter or volume change).

        Args:
            bar: Bar where drop happens
            filter_drop: Include filter drop (high to low)
            volume_drop: Include volume drop

        Returns:
            List of AutomationCurves for the impact
        """
        curves = []
        start_beat = self._bar_to_beats(bar)

        if filter_drop:
            points = [
                AutomationPoint(time_beats=start_beat - 0.01, value=12000),
                AutomationPoint(time_beats=start_beat, value=200),
                AutomationPoint(time_beats=start_beat + 8, value=12000),  # Recover over 2 bars
            ]
            curves.append(AutomationCurve(
                parameter_name="Filter Frequency",
                points=points,
                value_min=20,
                value_max=20000
            ))

        if volume_drop:
            points = [
                AutomationPoint(time_beats=start_beat - 0.01, value=0),
                AutomationPoint(time_beats=start_beat, value=-6),
                AutomationPoint(time_beats=start_beat + 0.5, value=0),
            ]
            curves.append(AutomationCurve(
                parameter_name="Track Volume",
                points=points,
                value_min=-70,
                value_max=6
            ))

        return curves


def generate_section_automation(
    section_type: str,
    start_bar: int,
    bars: int,
    tempo: int = 138
) -> List[AutomationCurve]:
    """
    Generate appropriate automation for a song section.

    Args:
        section_type: Type of section (intro, buildup, breakdown, drop, outro)
        start_bar: Starting bar
        bars: Section length in bars
        tempo: BPM

    Returns:
        List of automation curves for the section
    """
    gen = AutomationGenerator(tempo=tempo)
    curves = []

    if section_type == "buildup":
        # Filter sweep rising
        curves.extend(gen.riser_sweep(start_bar, bars, include_filter=True, include_volume=True))

    elif section_type == "drop":
        # Impact at drop start
        curves.extend(gen.impact_drop(start_bar, filter_drop=True))

    elif section_type == "breakdown":
        # Gentle filter opening
        curves.append(gen.filter_sweep(
            start_bar=start_bar,
            bars=bars,
            start_freq=500,
            end_freq=8000,
            curve_type="linear"
        ))

    elif section_type == "intro":
        # Volume fade in over first 8 bars
        fade_bars = min(8, bars)
        curves.append(gen.volume_fade(
            start_bar=start_bar,
            bars=fade_bars,
            start_db=-40,
            end_db=0
        ))

    elif section_type == "outro":
        # Volume fade out over last 8 bars
        fade_bars = min(8, bars)
        fade_start = start_bar + bars - fade_bars
        curves.append(gen.volume_fade(
            start_bar=fade_start,
            bars=fade_bars,
            start_db=0,
            end_db=-40
        ))

    return curves


# CLI for testing
if __name__ == "__main__":
    gen = AutomationGenerator(tempo=138)

    print("Automation Generator Demo")
    print("=" * 50)

    # Filter sweep
    print("\nFilter Sweep (bar 32, 16 bars):")
    sweep = gen.filter_sweep(32, 16, 200, 8000)
    print(f"  Parameter: {sweep.parameter_name}")
    print(f"  Points: {len(sweep.points)}")
    print(f"  Start: {sweep.points[0].value:.0f} Hz @ beat {sweep.points[0].time_beats}")
    print(f"  End: {sweep.points[-1].value:.0f} Hz @ beat {sweep.points[-1].time_beats}")

    # Riser
    print("\nRiser Effect (bar 32, 8 bars):")
    riser = gen.riser_sweep(32, 8)
    for curve in riser:
        print(f"  {curve.parameter_name}: {len(curve.points)} points")

    # Sidechain pump
    print("\nSidechain Pump (4 bars):")
    pump = gen.sidechain_pump(0, 4)
    print(f"  Points: {len(pump.points)}")
    print(f"  Pattern: pump on every beat")

    print("\n" + "=" * 50)
    print("Demo complete!")
