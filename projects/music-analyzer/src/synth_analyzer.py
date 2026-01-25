"""
Synth Analyzer Module

Analyzes extracted synth sounds to characterize their properties
for recreation in software synthesizers like Serum, Wavetable, or Vital.

Extracts:
- Waveform type estimation
- Harmonic content analysis
- Filter characteristics
- Envelope shape estimation
- Stereo width and processing
- Modulation detection
"""

import numpy as np
import librosa
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path


@dataclass
class WaveformAnalysis:
    """Estimated waveform characteristics."""
    primary_type: str           # 'saw', 'square', 'triangle', 'sine', 'complex', 'noise'
    confidence: float           # 0-1 confidence in detection
    harmonic_richness: float    # 0-1, how many harmonics present
    odd_even_ratio: float       # >1 = more odd harmonics (square-like), <1 = more even
    estimated_unison: int       # Estimated number of unison voices
    detuning_cents: float       # Estimated detuning amount
    description: str            # Human-readable description


@dataclass
class FilterAnalysis:
    """Estimated filter characteristics."""
    filter_type: str            # 'lowpass', 'highpass', 'bandpass', 'none'
    cutoff_hz: float           # Estimated cutoff frequency
    resonance: str             # 'none', 'low', 'medium', 'high'
    has_envelope: bool         # Whether filter moves over time
    envelope_amount: float     # 0-100% estimated envelope modulation
    envelope_direction: str    # 'up', 'down', 'both'
    description: str


@dataclass
class EnvelopeAnalysis:
    """Estimated ADSR envelope."""
    attack_ms: float
    decay_ms: float
    sustain_level: float       # 0-1
    release_ms: float
    envelope_type: str         # 'pluck', 'pad', 'lead', 'percussive', 'sustained'
    description: str


@dataclass
class ModulationAnalysis:
    """Detected modulation characteristics."""
    has_vibrato: bool
    vibrato_rate_hz: float
    vibrato_depth_cents: float
    has_tremolo: bool
    tremolo_rate_hz: float
    has_filter_lfo: bool
    filter_lfo_rate_hz: float
    has_evolving_timbre: bool  # Wavetable movement, etc.
    description: str


@dataclass
class StereoAnalysis:
    """Stereo characteristics."""
    width_percent: float       # 0-100
    correlation: float         # -1 to 1
    is_mono: bool
    has_stereo_movement: bool  # Panning, auto-pan, etc.
    stereo_type: str          # 'mono', 'narrow', 'wide', 'super_wide', 'unison_spread'
    description: str


@dataclass
class SynthCharacteristics:
    """Complete synth sound analysis."""
    # Source file
    file_path: str
    duration_seconds: float
    sample_rate: int

    # Analysis components
    waveform: WaveformAnalysis
    filter: FilterAnalysis
    amplitude_envelope: EnvelopeAnalysis
    filter_envelope: Optional[EnvelopeAnalysis]
    modulation: ModulationAnalysis
    stereo: StereoAnalysis

    # Overall classification
    synth_type: str            # 'supersaw', 'pluck', 'pad', 'lead', 'bass', 'fx'
    complexity: str            # 'simple', 'moderate', 'complex'

    # Recreation guide
    recreation_notes: List[str] = field(default_factory=list)
    recommended_synth: str = ""
    preset_starting_point: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'file_path': self.file_path,
            'duration_seconds': self.duration_seconds,
            'synth_type': self.synth_type,
            'complexity': self.complexity,
            'waveform': {
                'type': self.waveform.primary_type,
                'confidence': self.waveform.confidence,
                'unison_voices': self.waveform.estimated_unison,
                'detuning_cents': self.waveform.detuning_cents,
                'description': self.waveform.description
            },
            'filter': {
                'type': self.filter.filter_type,
                'cutoff_hz': self.filter.cutoff_hz,
                'resonance': self.filter.resonance,
                'has_envelope': self.filter.has_envelope,
                'description': self.filter.description
            },
            'envelope': {
                'attack_ms': self.amplitude_envelope.attack_ms,
                'decay_ms': self.amplitude_envelope.decay_ms,
                'sustain': self.amplitude_envelope.sustain_level,
                'release_ms': self.amplitude_envelope.release_ms,
                'type': self.amplitude_envelope.envelope_type,
                'description': self.amplitude_envelope.description
            },
            'stereo': {
                'width': self.stereo.width_percent,
                'type': self.stereo.stereo_type,
                'description': self.stereo.description
            },
            'recreation': {
                'recommended_synth': self.recommended_synth,
                'notes': self.recreation_notes
            }
        }

    def print_report(self) -> None:
        """Print a formatted analysis report."""
        print("\n" + "=" * 70)
        print("SYNTH SOUND ANALYSIS")
        print("=" * 70)
        print(f"File: {Path(self.file_path).name}")
        print(f"Duration: {self.duration_seconds:.2f}s")
        print(f"Type: {self.synth_type.upper()} ({self.complexity} complexity)")

        print("\n🎵 WAVEFORM:")
        print(f"  {self.waveform.description}")
        if self.waveform.estimated_unison > 1:
            print(f"  Unison: ~{self.waveform.estimated_unison} voices, ~{self.waveform.detuning_cents:.0f} cents detune")

        print("\n🎚️ FILTER:")
        print(f"  {self.filter.description}")

        print("\n📈 AMPLITUDE ENVELOPE:")
        print(f"  {self.amplitude_envelope.description}")
        print(f"  A: {self.amplitude_envelope.attack_ms:.0f}ms | "
              f"D: {self.amplitude_envelope.decay_ms:.0f}ms | "
              f"S: {self.amplitude_envelope.sustain_level*100:.0f}% | "
              f"R: {self.amplitude_envelope.release_ms:.0f}ms")

        if self.filter_envelope:
            print("\n📈 FILTER ENVELOPE:")
            print(f"  {self.filter_envelope.description}")

        print("\n🔊 STEREO:")
        print(f"  {self.stereo.description}")

        if self.modulation.has_vibrato or self.modulation.has_filter_lfo:
            print("\n〰️ MODULATION:")
            print(f"  {self.modulation.description}")

        print("\n" + "-" * 70)
        print("🔧 RECREATION GUIDE:")
        print(f"  Recommended synth: {self.recommended_synth}")
        for note in self.recreation_notes:
            print(f"  • {note}")
        print("=" * 70)


class SynthAnalyzer:
    """
    Analyzes synth sounds for recreation.

    Usage:
        analyzer = SynthAnalyzer()
        result = analyzer.analyze("extracted_lead.wav")
        result.print_report()
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def analyze(self, audio_path: str) -> SynthCharacteristics:
        """
        Analyze a synth sound file.

        Args:
            audio_path: Path to audio file (preferably isolated synth sound)

        Returns:
            SynthCharacteristics with analysis results
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Load audio
        y, sr = librosa.load(audio_path, sr=None, mono=False)

        # Convert to mono for most analysis
        if len(y.shape) > 1:
            y_mono = librosa.to_mono(y)
            is_stereo = True
        else:
            y_mono = y
            is_stereo = False

        duration = librosa.get_duration(y=y_mono, sr=sr)

        # Run all analyses
        waveform = self._analyze_waveform(y_mono, sr)
        filter_analysis = self._analyze_filter(y_mono, sr)
        amp_envelope = self._analyze_amplitude_envelope(y_mono, sr, duration)
        filter_envelope = self._analyze_filter_envelope(y_mono, sr) if filter_analysis.has_envelope else None
        modulation = self._analyze_modulation(y_mono, sr)
        stereo = self._analyze_stereo(y, sr) if is_stereo else self._mono_stereo_info()

        # Classify synth type
        synth_type = self._classify_synth_type(waveform, filter_analysis, amp_envelope, stereo)
        complexity = self._estimate_complexity(waveform, filter_analysis, modulation)

        # Generate recreation guide
        recreation_notes, recommended_synth = self._generate_recreation_guide(
            waveform, filter_analysis, amp_envelope, stereo, synth_type
        )

        return SynthCharacteristics(
            file_path=str(path.absolute()),
            duration_seconds=duration,
            sample_rate=sr,
            waveform=waveform,
            filter=filter_analysis,
            amplitude_envelope=amp_envelope,
            filter_envelope=filter_envelope,
            modulation=modulation,
            stereo=stereo,
            synth_type=synth_type,
            complexity=complexity,
            recreation_notes=recreation_notes,
            recommended_synth=recommended_synth
        )

    def _analyze_waveform(self, y: np.ndarray, sr: int) -> WaveformAnalysis:
        """Analyze waveform type and characteristics."""
        # Compute spectrum
        n_fft = 4096
        D = np.abs(librosa.stft(y, n_fft=n_fft))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        # Find fundamental frequency
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        pitch_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                pitch_values.append(pitch)

        if pitch_values:
            fundamental = np.median(pitch_values)
        else:
            fundamental = 440.0  # Default

        # Analyze harmonic content
        harmonic_peaks = []
        for n in range(1, 20):
            harmonic_freq = fundamental * n
            if harmonic_freq > sr / 2:
                break
            idx = np.argmin(np.abs(freqs - harmonic_freq))
            harmonic_peaks.append(np.mean(D[idx, :]))

        if len(harmonic_peaks) > 1:
            harmonic_peaks = np.array(harmonic_peaks) / (harmonic_peaks[0] + 1e-10)
        else:
            harmonic_peaks = np.array([1.0])

        # Calculate harmonic richness
        harmonic_richness = min(1.0, len([h for h in harmonic_peaks if h > 0.1]) / 10)

        # Calculate odd/even ratio
        odd_harmonics = harmonic_peaks[::2]  # 1st, 3rd, 5th...
        even_harmonics = harmonic_peaks[1::2]  # 2nd, 4th, 6th...
        odd_sum = np.sum(odd_harmonics) if len(odd_harmonics) > 0 else 0
        even_sum = np.sum(even_harmonics) if len(even_harmonics) > 0 else 0.001
        odd_even_ratio = odd_sum / (even_sum + 0.001)

        # Determine waveform type
        if harmonic_richness < 0.15:
            wave_type = 'sine'
            confidence = 0.8
            description = "Pure or near-sine wave - minimal harmonics"
        elif odd_even_ratio > 2.5 and harmonic_richness > 0.3:
            wave_type = 'square'
            confidence = 0.7
            description = "Square-like wave - strong odd harmonics, hollow sound"
        elif odd_even_ratio > 1.5 and harmonic_richness < 0.4:
            wave_type = 'triangle'
            confidence = 0.6
            description = "Triangle-like wave - odd harmonics with fast rolloff"
        elif harmonic_richness > 0.5:
            wave_type = 'saw'
            confidence = 0.75
            description = "Sawtooth-like wave - rich harmonic content"
        else:
            wave_type = 'complex'
            confidence = 0.5
            description = "Complex waveform - possibly wavetable or FM"

        # Estimate unison from spectral spread around harmonics
        spectral_spread = np.std(D, axis=1)
        spread_around_fundamental = spectral_spread[max(0, int(fundamental/sr*n_fft)-5):
                                                     int(fundamental/sr*n_fft)+5]
        avg_spread = np.mean(spread_around_fundamental) if len(spread_around_fundamental) > 0 else 0

        # Higher spread suggests unison/detuning
        if avg_spread > 0.1:
            estimated_unison = min(9, max(1, int(avg_spread * 20)))
            detuning_cents = min(50, avg_spread * 100)
            if estimated_unison > 3:
                wave_type = 'saw'  # Supersaw likely
                description = f"Supersaw - {wave_type} wave with unison detuning"
        else:
            estimated_unison = 1
            detuning_cents = 0

        return WaveformAnalysis(
            primary_type=wave_type,
            confidence=confidence,
            harmonic_richness=harmonic_richness,
            odd_even_ratio=odd_even_ratio,
            estimated_unison=estimated_unison,
            detuning_cents=detuning_cents,
            description=description
        )

    def _analyze_filter(self, y: np.ndarray, sr: int) -> FilterAnalysis:
        """Analyze filter characteristics."""
        # Compute spectrum at different time points
        n_fft = 4096
        hop = n_fft // 4

        D = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        # Average spectrum
        avg_spectrum = np.mean(D, axis=1)

        # Find rolloff point (where energy drops significantly)
        cumsum = np.cumsum(avg_spectrum)
        total = cumsum[-1]
        rolloff_85 = freqs[np.argmin(np.abs(cumsum - 0.85 * total))]
        rolloff_95 = freqs[np.argmin(np.abs(cumsum - 0.95 * total))]

        # Estimate cutoff
        cutoff_hz = rolloff_85

        # Detect filter type
        low_energy = np.sum(avg_spectrum[freqs < 500])
        high_energy = np.sum(avg_spectrum[freqs > 5000])
        mid_energy = np.sum(avg_spectrum[(freqs >= 500) & (freqs <= 5000)])

        total_energy = low_energy + mid_energy + high_energy + 0.001

        if high_energy / total_energy < 0.05 and cutoff_hz < 8000:
            filter_type = 'lowpass'
        elif low_energy / total_energy < 0.1:
            filter_type = 'highpass'
        elif mid_energy / total_energy > 0.7:
            filter_type = 'bandpass'
        else:
            filter_type = 'none'

        # Check for resonance (peak at cutoff)
        cutoff_idx = np.argmin(np.abs(freqs - cutoff_hz))
        local_region = avg_spectrum[max(0, cutoff_idx-10):cutoff_idx+10]
        if len(local_region) > 0 and avg_spectrum[cutoff_idx] > np.mean(local_region) * 1.5:
            resonance = 'high'
        elif avg_spectrum[cutoff_idx] > np.mean(local_region) * 1.2:
            resonance = 'medium'
        else:
            resonance = 'low'

        # Check for filter envelope (spectrum changes over time)
        if D.shape[1] > 10:
            start_spectrum = np.mean(D[:, :3], axis=1)
            mid_spectrum = np.mean(D[:, D.shape[1]//2-1:D.shape[1]//2+2], axis=1)

            start_centroid = np.sum(freqs * start_spectrum) / (np.sum(start_spectrum) + 0.001)
            mid_centroid = np.sum(freqs * mid_spectrum) / (np.sum(mid_spectrum) + 0.001)

            centroid_change = abs(start_centroid - mid_centroid)
            has_envelope = centroid_change > 500

            if has_envelope:
                envelope_direction = 'down' if start_centroid > mid_centroid else 'up'
                envelope_amount = min(100, centroid_change / 50)
            else:
                envelope_direction = 'none'
                envelope_amount = 0
        else:
            has_envelope = False
            envelope_direction = 'none'
            envelope_amount = 0

        # Build description
        if filter_type == 'none':
            description = "No significant filtering detected - full spectrum"
        else:
            desc_parts = [f"{filter_type.capitalize()} filter around {cutoff_hz:.0f}Hz"]
            if resonance != 'low':
                desc_parts.append(f"{resonance} resonance")
            if has_envelope:
                desc_parts.append(f"envelope sweeping {envelope_direction}")
            description = ", ".join(desc_parts)

        return FilterAnalysis(
            filter_type=filter_type,
            cutoff_hz=cutoff_hz,
            resonance=resonance,
            has_envelope=has_envelope,
            envelope_amount=envelope_amount,
            envelope_direction=envelope_direction,
            description=description
        )

    def _analyze_amplitude_envelope(
        self,
        y: np.ndarray,
        sr: int,
        duration: float
    ) -> EnvelopeAnalysis:
        """Analyze amplitude envelope (ADSR)."""
        # Get RMS envelope
        hop_length = 512
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        times = librosa.times_like(rms, sr=sr, hop_length=hop_length)

        if len(rms) < 3:
            return EnvelopeAnalysis(
                attack_ms=10, decay_ms=100, sustain_level=0.7, release_ms=200,
                envelope_type='unknown', description="Audio too short for envelope analysis"
            )

        # Normalize
        rms = rms / (np.max(rms) + 1e-10)

        # Find peak
        peak_idx = np.argmax(rms)
        peak_time = times[peak_idx]

        # Attack time (10% to peak)
        start_idx = np.argmax(rms > 0.1)
        attack_ms = (times[peak_idx] - times[start_idx]) * 1000

        # Find sustain level (average of middle section)
        if len(rms) > 20:
            sustain_level = np.mean(rms[len(rms)//3:2*len(rms)//3])
        else:
            sustain_level = np.mean(rms[peak_idx:])

        # Decay time (peak to sustain)
        decay_end_idx = peak_idx
        for i in range(peak_idx, len(rms)):
            if rms[i] <= sustain_level * 1.1:
                decay_end_idx = i
                break
        decay_ms = (times[min(decay_end_idx, len(times)-1)] - times[peak_idx]) * 1000

        # Release time (last 20% of sound)
        release_start = int(len(rms) * 0.8)
        if release_start < len(rms) - 1:
            release_rms = rms[release_start:]
            release_time = times[-1] - times[release_start]
            release_ms = release_time * 1000
        else:
            release_ms = 200

        # Clamp values
        attack_ms = max(0, min(5000, attack_ms))
        decay_ms = max(0, min(5000, decay_ms))
        release_ms = max(10, min(5000, release_ms))
        sustain_level = max(0, min(1, sustain_level))

        # Classify envelope type
        if attack_ms < 20 and decay_ms < 200 and sustain_level < 0.3:
            envelope_type = 'pluck'
            description = "Plucky envelope - fast attack, quick decay, low sustain"
        elif attack_ms < 20 and sustain_level > 0.6:
            envelope_type = 'lead'
            description = "Lead-style envelope - immediate attack, sustained"
        elif attack_ms > 200:
            envelope_type = 'pad'
            description = "Pad-style envelope - slow attack, sustained"
        elif attack_ms < 10 and decay_ms < 100 and sustain_level < 0.2:
            envelope_type = 'percussive'
            description = "Percussive envelope - instant attack, very fast decay"
        else:
            envelope_type = 'sustained'
            description = "Sustained envelope - moderate attack and decay"

        return EnvelopeAnalysis(
            attack_ms=attack_ms,
            decay_ms=decay_ms,
            sustain_level=sustain_level,
            release_ms=release_ms,
            envelope_type=envelope_type,
            description=description
        )

    def _analyze_filter_envelope(self, y: np.ndarray, sr: int) -> EnvelopeAnalysis:
        """Analyze filter envelope movement."""
        # Track spectral centroid over time
        hop_length = 512
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
        times = librosa.times_like(centroid, sr=sr, hop_length=hop_length)

        if len(centroid) < 3:
            return EnvelopeAnalysis(0, 100, 0.5, 100, 'unknown', "Too short")

        # Normalize centroid
        centroid_norm = (centroid - np.min(centroid)) / (np.max(centroid) - np.min(centroid) + 0.001)

        # Find peak brightness
        peak_idx = np.argmax(centroid_norm)

        # Estimate ADSR for filter
        attack_ms = times[peak_idx] * 1000 if peak_idx > 0 else 0

        # Decay
        sustain_level = np.mean(centroid_norm[len(centroid_norm)//2:])
        decay_end_idx = peak_idx
        for i in range(peak_idx, len(centroid_norm)):
            if centroid_norm[i] <= sustain_level * 1.1:
                decay_end_idx = i
                break
        decay_ms = (times[min(decay_end_idx, len(times)-1)] - times[peak_idx]) * 1000

        return EnvelopeAnalysis(
            attack_ms=max(0, attack_ms),
            decay_ms=max(0, min(2000, decay_ms)),
            sustain_level=sustain_level,
            release_ms=200,
            envelope_type='filter',
            description=f"Filter opens in {attack_ms:.0f}ms, decays over {decay_ms:.0f}ms"
        )

    def _analyze_modulation(self, y: np.ndarray, sr: int) -> ModulationAnalysis:
        """Detect modulation (vibrato, tremolo, LFO)."""
        # Analyze pitch variation for vibrato
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)

        pitch_track = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                pitch_track.append(pitch)

        has_vibrato = False
        vibrato_rate = 0
        vibrato_depth = 0

        if len(pitch_track) > 10:
            pitch_track = np.array(pitch_track)
            pitch_variation = np.std(pitch_track) / (np.mean(pitch_track) + 0.001)

            if pitch_variation > 0.01:  # More than 1% variation
                has_vibrato = True
                # Estimate rate from pitch oscillation
                pitch_diff = np.diff(pitch_track)
                zero_crossings = np.where(np.diff(np.sign(pitch_diff)))[0]
                if len(zero_crossings) > 2:
                    avg_period = len(pitch_track) / len(zero_crossings) * 2
                    vibrato_rate = sr / (avg_period * 512)  # Approximate
                vibrato_depth = pitch_variation * 100  # cents (approximate)

        # Analyze amplitude variation for tremolo
        rms = librosa.feature.rms(y=y)[0]
        has_tremolo = False
        tremolo_rate = 0

        if len(rms) > 10:
            rms_variation = np.std(rms) / (np.mean(rms) + 0.001)
            if rms_variation > 0.1:
                has_tremolo = True
                rms_diff = np.diff(rms)
                zero_crossings = np.where(np.diff(np.sign(rms_diff)))[0]
                if len(zero_crossings) > 2:
                    avg_period = len(rms) / len(zero_crossings) * 2
                    tremolo_rate = sr / (avg_period * 512)

        # Check for filter LFO (spectral centroid oscillation)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        has_filter_lfo = False
        filter_lfo_rate = 0

        if len(centroid) > 10:
            centroid_variation = np.std(centroid) / (np.mean(centroid) + 0.001)
            if centroid_variation > 0.05:
                has_filter_lfo = True

        # Check for evolving timbre
        if len(centroid) > 20:
            first_half = np.mean(centroid[:len(centroid)//2])
            second_half = np.mean(centroid[len(centroid)//2:])
            has_evolving = abs(first_half - second_half) / (first_half + 0.001) > 0.1
        else:
            has_evolving = False

        # Build description
        desc_parts = []
        if has_vibrato:
            desc_parts.append(f"Vibrato detected (~{vibrato_rate:.1f}Hz)")
        if has_tremolo:
            desc_parts.append(f"Tremolo/amplitude modulation detected")
        if has_filter_lfo:
            desc_parts.append("Filter modulation detected")
        if has_evolving:
            desc_parts.append("Evolving timbre (wavetable movement?)")

        description = "; ".join(desc_parts) if desc_parts else "No significant modulation detected"

        return ModulationAnalysis(
            has_vibrato=has_vibrato,
            vibrato_rate_hz=vibrato_rate,
            vibrato_depth_cents=vibrato_depth,
            has_tremolo=has_tremolo,
            tremolo_rate_hz=tremolo_rate,
            has_filter_lfo=has_filter_lfo,
            filter_lfo_rate_hz=filter_lfo_rate,
            has_evolving_timbre=has_evolving,
            description=description
        )

    def _analyze_stereo(self, y: np.ndarray, sr: int) -> StereoAnalysis:
        """Analyze stereo characteristics."""
        if len(y.shape) != 2 or y.shape[0] != 2:
            return self._mono_stereo_info()

        left = y[0]
        right = y[1]

        # Correlation
        correlation = float(np.corrcoef(left, right)[0, 1])

        # Width estimate
        width_percent = (1 - abs(correlation)) * 100

        # Determine stereo type
        if correlation > 0.95:
            stereo_type = 'mono'
            description = "Essentially mono - no stereo spread"
        elif correlation > 0.7:
            stereo_type = 'narrow'
            description = "Narrow stereo - subtle width"
        elif correlation > 0.3:
            stereo_type = 'wide'
            description = "Wide stereo - good spread, likely unison or stereo processing"
        elif correlation > 0:
            stereo_type = 'super_wide'
            description = "Very wide stereo - heavy unison spread or stereo widening"
        else:
            stereo_type = 'out_of_phase'
            description = "Out of phase content detected - check for issues"

        # Check for stereo movement (auto-pan, etc.)
        # Compare left/right balance over time
        hop = 2048
        left_rms = librosa.feature.rms(y=left, hop_length=hop)[0]
        right_rms = librosa.feature.rms(y=right, hop_length=hop)[0]

        balance = (left_rms - right_rms) / (left_rms + right_rms + 0.001)
        balance_variation = np.std(balance)
        has_movement = balance_variation > 0.1

        if has_movement:
            description += "; stereo movement detected (auto-pan?)"

        return StereoAnalysis(
            width_percent=width_percent,
            correlation=correlation,
            is_mono=correlation > 0.95,
            has_stereo_movement=has_movement,
            stereo_type=stereo_type,
            description=description
        )

    def _mono_stereo_info(self) -> StereoAnalysis:
        """Return stereo info for mono files."""
        return StereoAnalysis(
            width_percent=0,
            correlation=1.0,
            is_mono=True,
            has_stereo_movement=False,
            stereo_type='mono',
            description="Mono source file"
        )

    def _classify_synth_type(
        self,
        waveform: WaveformAnalysis,
        filter: FilterAnalysis,
        envelope: EnvelopeAnalysis,
        stereo: StereoAnalysis
    ) -> str:
        """Classify the overall synth type."""
        # Supersaw detection
        if (waveform.primary_type == 'saw' and
            waveform.estimated_unison >= 5 and
            stereo.stereo_type in ['wide', 'super_wide']):
            return 'supersaw'

        # Pluck detection
        if envelope.envelope_type == 'pluck':
            return 'pluck'

        # Pad detection
        if envelope.envelope_type == 'pad':
            return 'pad'

        # Bass detection (low filter cutoff, mono-ish)
        if filter.cutoff_hz < 500 and stereo.stereo_type in ['mono', 'narrow']:
            return 'bass'

        # Lead detection
        if envelope.envelope_type in ['lead', 'sustained']:
            return 'lead'

        return 'synth'

    def _estimate_complexity(
        self,
        waveform: WaveformAnalysis,
        filter: FilterAnalysis,
        modulation: ModulationAnalysis
    ) -> str:
        """Estimate sound complexity."""
        complexity_score = 0

        if waveform.estimated_unison > 3:
            complexity_score += 1
        if waveform.primary_type == 'complex':
            complexity_score += 1
        if filter.has_envelope:
            complexity_score += 1
        if filter.resonance == 'high':
            complexity_score += 1
        if modulation.has_vibrato:
            complexity_score += 1
        if modulation.has_filter_lfo:
            complexity_score += 1
        if modulation.has_evolving_timbre:
            complexity_score += 2

        if complexity_score <= 1:
            return 'simple'
        elif complexity_score <= 3:
            return 'moderate'
        else:
            return 'complex'

    def _generate_recreation_guide(
        self,
        waveform: WaveformAnalysis,
        filter: FilterAnalysis,
        envelope: EnvelopeAnalysis,
        stereo: StereoAnalysis,
        synth_type: str
    ) -> Tuple[List[str], str]:
        """Generate recreation notes and recommend synth."""
        notes = []

        # Recommend synth
        if synth_type == 'supersaw':
            recommended = "Serum, Sylenth1, or Vital"
            notes.append(f"OSC1: Saw wave, {waveform.estimated_unison} unison voices")
            notes.append(f"Detune: ~{waveform.detuning_cents:.0f} cents")
            notes.append("Unison spread: 100% for width")
        elif synth_type == 'pluck':
            recommended = "Serum or Spire"
            notes.append("Use saw or square wave")
            notes.append("Filter envelope: fast attack, quick decay")
        elif synth_type == 'pad':
            recommended = "Vital, Serum, or Diva"
            notes.append("Multiple detuned oscillators")
            notes.append("Slow attack envelope (200-500ms)")
            notes.append("Add subtle LFO to filter/pitch")
        elif synth_type == 'bass':
            recommended = "Serum or Massive"
            notes.append("Keep it mono (bass mono below 150Hz)")
            notes.append(f"Filter cutoff around {filter.cutoff_hz:.0f}Hz")
        else:
            recommended = "Serum, Vital, or Wavetable"

        # Oscillator notes
        notes.append(f"Waveform: {waveform.primary_type.capitalize()}")

        # Filter notes
        if filter.filter_type != 'none':
            notes.append(f"Filter: {filter.filter_type} @ {filter.cutoff_hz:.0f}Hz, {filter.resonance} resonance")
            if filter.has_envelope:
                notes.append(f"Filter envelope: sweeping {filter.envelope_direction}")

        # Envelope notes
        notes.append(f"Amp ADSR: {envelope.attack_ms:.0f}/{envelope.decay_ms:.0f}/{envelope.sustain_level*100:.0f}%/{envelope.release_ms:.0f}ms")

        # Stereo notes
        if stereo.stereo_type in ['wide', 'super_wide']:
            notes.append(f"Stereo: Use unison spread or Utility width (~{100 + stereo.width_percent/2:.0f}%)")

        return notes, recommended


def analyze_synth(audio_path: str) -> SynthCharacteristics:
    """Convenience function to analyze a synth sound."""
    analyzer = SynthAnalyzer()
    return analyzer.analyze(audio_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python synth_analyzer.py <audio_file>")
        print("\nAnalyzes a synth sound and provides recreation guidance.")
        sys.exit(1)

    result = analyze_synth(sys.argv[1])
    result.print_report()
