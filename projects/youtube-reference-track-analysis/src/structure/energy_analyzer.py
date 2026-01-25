"""
Energy analysis for trance section classification.

Trance structure is driven by energy curves rather than harmonic content.
Key signals:
- Buildups: Rising energy gradient, filter sweeps
- Breakdowns: Low energy, reduced bass
- Drops: Sudden energy spike, strong bass return
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np


@dataclass
class EnergyProfile:
    """Energy profile for a time segment."""
    timestamp: float
    rms_energy: float  # Overall RMS energy (0-1 normalized)
    bass_energy: float  # Low frequency energy (20-200 Hz)
    mid_energy: float  # Mid frequency energy (200-2000 Hz)
    high_energy: float  # High frequency energy (2000+ Hz)
    spectral_flux: float  # Rate of spectral change
    energy_level: int  # 1-10 scale like Mixed In Key


@dataclass
class SectionEnergy:
    """Energy characteristics for a section."""
    avg_energy: float
    avg_bass: float
    energy_trend: str  # 'rising', 'falling', 'stable'
    bass_present: bool  # True if significant bass
    energy_level: int  # 1-10 scale


def extract_energy_profile(
    audio_path: Path,
    hop_duration: float = 1.0
) -> Optional[List[EnergyProfile]]:
    """
    Extract energy profile over time.

    Args:
        audio_path: Path to audio file
        hop_duration: Time between measurements in seconds

    Returns:
        List of EnergyProfile or None on error
    """
    try:
        import librosa
        from scipy.signal import butter, sosfilt
    except ImportError:
        return None

    audio_path = Path(audio_path)
    if not audio_path.exists():
        return None

    try:
        # Load audio
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
        duration = len(y) / sr

        # Design filters for frequency bands
        def bandpass_energy(y, sr, low, high):
            """Get energy in a frequency band."""
            nyq = sr / 2
            low_n = max(low / nyq, 0.001)
            high_n = min(high / nyq, 0.999)
            if low_n >= high_n:
                return np.zeros_like(y)
            sos = butter(4, [low_n, high_n], btype='band', output='sos')
            filtered = sosfilt(sos, y)
            return filtered

        # Filter into bands
        y_bass = bandpass_energy(y, sr, 20, 200)
        y_mid = bandpass_energy(y, sr, 200, 2000)
        y_high = bandpass_energy(y, sr, 2000, min(10000, sr // 2 - 100))

        # Calculate frame-level features
        hop_samples = int(hop_duration * sr)
        frame_length = hop_samples * 2  # 50% overlap

        profiles = []
        timestamps = np.arange(0, duration - hop_duration, hop_duration)

        # Pre-compute spectral flux
        S = np.abs(librosa.stft(y, hop_length=hop_samples // 4))
        flux = librosa.onset.onset_strength(S=S, sr=sr, hop_length=hop_samples // 4)

        # Normalize
        y_max = np.max(np.abs(y)) if np.max(np.abs(y)) > 0 else 1.0

        for i, t in enumerate(timestamps):
            start = int(t * sr)
            end = min(start + frame_length, len(y))

            if end - start < sr // 4:  # Minimum 250ms
                continue

            # Energy calculations
            seg = y[start:end]
            seg_bass = y_bass[start:end]
            seg_mid = y_mid[start:end]
            seg_high = y_high[start:end]

            rms = np.sqrt(np.mean(seg ** 2)) / y_max
            bass = np.sqrt(np.mean(seg_bass ** 2)) / y_max
            mid = np.sqrt(np.mean(seg_mid ** 2)) / y_max
            high = np.sqrt(np.mean(seg_high ** 2)) / y_max

            # Spectral flux for this window
            flux_start = int(t * sr / (hop_samples // 4))
            flux_end = int((t + hop_duration) * sr / (hop_samples // 4))
            flux_seg = flux[flux_start:flux_end] if flux_end <= len(flux) else flux[flux_start:]
            spec_flux = np.mean(flux_seg) if len(flux_seg) > 0 else 0

            # Energy level (1-10 scale)
            energy_level = min(10, max(1, int(rms * 12)))

            profiles.append(EnergyProfile(
                timestamp=round(t, 2),
                rms_energy=round(rms, 4),
                bass_energy=round(bass, 4),
                mid_energy=round(mid, 4),
                high_energy=round(high, 4),
                spectral_flux=round(spec_flux, 4),
                energy_level=energy_level
            ))

        return profiles

    except Exception as e:
        print(f"Error extracting energy profile: {e}")
        return None


def analyze_section_energy(
    energy_profile: List[EnergyProfile],
    start_time: float,
    end_time: float
) -> Optional[SectionEnergy]:
    """
    Analyze energy characteristics for a section.

    Args:
        energy_profile: Full track energy profile
        start_time: Section start time
        end_time: Section end time

    Returns:
        SectionEnergy or None
    """
    # Get profiles within section
    section_profiles = [
        p for p in energy_profile
        if start_time <= p.timestamp < end_time
    ]

    if not section_profiles:
        return None

    # Calculate averages
    avg_energy = np.mean([p.rms_energy for p in section_profiles])
    avg_bass = np.mean([p.bass_energy for p in section_profiles])

    # Determine energy trend
    if len(section_profiles) >= 3:
        energies = [p.rms_energy for p in section_profiles]
        first_third = np.mean(energies[:len(energies)//3])
        last_third = np.mean(energies[-len(energies)//3:])

        if last_third > first_third * 1.2:
            trend = 'rising'
        elif last_third < first_third * 0.8:
            trend = 'falling'
        else:
            trend = 'stable'
    else:
        trend = 'stable'

    # Check bass presence (threshold based on typical trance)
    bass_present = avg_bass > 0.02

    # Overall energy level
    avg_level = int(np.mean([p.energy_level for p in section_profiles]))

    return SectionEnergy(
        avg_energy=round(avg_energy, 4),
        avg_bass=round(avg_bass, 4),
        energy_trend=trend,
        bass_present=bass_present,
        energy_level=avg_level
    )


def classify_section_by_energy(
    section_energy: SectionEnergy,
    prev_energy: Optional[SectionEnergy] = None,
    next_energy: Optional[SectionEnergy] = None
) -> str:
    """
    Classify a section based on energy characteristics.

    Uses trance-specific patterns:
    - DROP: High energy + bass present
    - BUILDUP: Rising energy, often reduced bass
    - BREAKDOWN: Low energy, reduced bass
    - INTRO/OUTRO: Low energy at start/end

    Args:
        section_energy: Current section's energy
        prev_energy: Previous section's energy (if available)
        next_energy: Next section's energy (if available)

    Returns:
        Section type string
    """
    # High energy with bass = DROP
    if section_energy.energy_level >= 7 and section_energy.bass_present:
        return 'DROP'

    # Rising energy leading to high energy = BUILDUP
    if section_energy.energy_trend == 'rising':
        if next_energy and next_energy.energy_level >= 7:
            return 'BUILDUP'

    # Low energy without bass = BREAKDOWN
    if section_energy.energy_level <= 5 and not section_energy.bass_present:
        return 'BREAKDOWN'

    # Medium energy with bass = main groove (could be verse equivalent)
    if section_energy.bass_present and 4 <= section_energy.energy_level <= 6:
        # If it follows a drop, it's likely a continuation
        if prev_energy and prev_energy.energy_level >= 7:
            return 'DROP'
        return 'BREAKDOWN'

    # Default based on energy level
    if section_energy.energy_level >= 6:
        return 'DROP'
    elif section_energy.energy_level <= 3:
        return 'BREAKDOWN'
    else:
        return 'BUILDUP'


def refine_sections_with_energy(
    sections: list,
    audio_path: Path
) -> list:
    """
    Refine section labels using energy analysis.

    This improves on allin1's generic labels by using
    trance-specific energy patterns.

    Args:
        sections: List of SectionInfo objects
        audio_path: Path to audio file

    Returns:
        Sections with refined labels
    """
    if not sections:
        return sections

    # Extract energy profile
    energy_profile = extract_energy_profile(audio_path)
    if not energy_profile:
        return sections

    # Analyze each section
    section_energies = []
    for section in sections:
        energy = analyze_section_energy(
            energy_profile,
            section.start_time,
            section.end_time
        )
        section_energies.append(energy)

    # Classify sections based on energy
    from .section_detector import SectionInfo

    refined = []
    for i, section in enumerate(sections):
        energy = section_energies[i]
        if energy is None:
            refined.append(section)
            continue

        # Get context
        prev_energy = section_energies[i - 1] if i > 0 else None
        next_energy = section_energies[i + 1] if i < len(sections) - 1 else None

        # Keep intro/outro labels
        if section.section_type in ['INTRO', 'OUTRO']:
            new_type = section.section_type
        else:
            # Reclassify based on energy
            new_type = classify_section_by_energy(energy, prev_energy, next_energy)

        refined.append(SectionInfo(
            section_type=new_type,
            original_label=section.original_label,
            start_time=section.start_time,
            end_time=section.end_time,
            start_bar=section.start_bar,
            end_bar=section.end_bar,
            duration_bars=section.duration_bars,
            confidence=section.confidence
        ))

    return refined


def detect_drops_by_bass(
    audio_path: Path,
    bpm: float,
    threshold: float = 0.03
) -> List[Tuple[float, float]]:
    """
    Detect drop sections by sudden bass energy increase.

    In trance, drops are characterized by the return of bass
    after a breakdown or buildup.

    Args:
        audio_path: Path to audio file
        bpm: Track BPM for bar alignment
        threshold: Bass energy threshold

    Returns:
        List of (start_time, end_time) tuples for drops
    """
    energy_profile = extract_energy_profile(audio_path, hop_duration=0.5)
    if not energy_profile:
        return []

    drops = []
    in_drop = False
    drop_start = 0.0

    for i, profile in enumerate(energy_profile):
        # Detect bass onset (start of drop)
        if not in_drop and profile.bass_energy > threshold:
            # Check if previous was low bass (transition point)
            if i > 0 and energy_profile[i - 1].bass_energy < threshold * 0.5:
                in_drop = True
                drop_start = profile.timestamp

        # Detect bass offset (end of drop)
        elif in_drop and profile.bass_energy < threshold * 0.3:
            drops.append((drop_start, profile.timestamp))
            in_drop = False

    # Close any open drop
    if in_drop and energy_profile:
        drops.append((drop_start, energy_profile[-1].timestamp))

    return drops


def get_energy_curve(
    audio_path: Path,
    resolution_sec: float = 0.5
) -> List[Tuple[float, float, int]]:
    """
    Get energy curve for visualization.

    Args:
        audio_path: Path to audio file
        resolution_sec: Time resolution

    Returns:
        List of (timestamp, rms_energy, energy_level) tuples
    """
    profile = extract_energy_profile(audio_path, hop_duration=resolution_sec)
    if not profile:
        return []

    return [
        (p.timestamp, p.rms_energy, p.energy_level)
        for p in profile
    ]
