"""
Tests for Trance DNA Feature Extraction Module.

Tests cover:
- Pumping detection (sidechain analysis)
- Acid/303 bassline detection
- Supersaw stereo analysis
- Energy curve extraction
- Rhythm analysis
- Trance score calculation
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from feature_extraction.pumping_detector import (
    extract_pumping_features,
    compute_pumping_score,
    PumpingFeatures
)
from feature_extraction.acid_detector import (
    extract_acid_features,
    compute_303_score,
    compute_303_score_from_components,
    AcidFeatures
)
from feature_extraction.supersaw_analyzer import (
    analyze_supersaw_characteristics,
    compute_supersaw_score,
    SupersawFeatures
)
from feature_extraction.energy_curves import (
    extract_energy_curves,
    detect_drops,
    compute_energy_progression_score,
    EnergyCurves
)
from feature_extraction.rhythm_analyzer import (
    detect_trance_tempo,
    detect_four_on_floor,
    detect_offbeat_hihats,
    analyze_rhythm,
    TempoFeatures,
    RhythmFeatures
)
from feature_extraction.trance_scorer import (
    TranceScoreCalculator,
    TranceScoreBreakdown
)


# Sample rate for test audio
SR = 44100


def generate_sine_wave(freq: float, duration: float, sr: int = SR) -> np.ndarray:
    """Generate a simple sine wave."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def generate_kick_pattern(bpm: float, duration: float, sr: int = SR) -> np.ndarray:
    """Generate a 4-on-the-floor kick pattern."""
    samples = int(sr * duration)
    audio = np.zeros(samples, dtype=np.float32)

    beat_interval = 60.0 / bpm  # seconds per beat
    kick_duration = 0.1  # seconds

    t_kick = np.linspace(0, kick_duration, int(sr * kick_duration), endpoint=False)
    kick = np.sin(2 * np.pi * 50 * t_kick) * np.exp(-t_kick * 30)  # Exponential decay

    current_time = 0
    while current_time < duration:
        start_sample = int(current_time * sr)
        end_sample = min(start_sample + len(kick), samples)
        audio[start_sample:end_sample] += kick[:end_sample - start_sample]
        current_time += beat_interval

    return audio


def generate_pumping_audio(bpm: float, duration: float, depth: float = 0.5, sr: int = SR) -> np.ndarray:
    """Generate audio with sidechain pumping effect."""
    samples = int(sr * duration)
    t = np.linspace(0, duration, samples, endpoint=False)

    # Base synth pad
    base = np.sin(2 * np.pi * 220 * t) * 0.5

    # Sidechain envelope (pumping)
    beat_interval = 60.0 / bpm
    pump_env = np.ones(samples)

    for beat_start in np.arange(0, duration, beat_interval):
        start_idx = int(beat_start * sr)
        pump_duration = int(beat_interval * sr * 0.5)  # Half a beat

        if start_idx + pump_duration < samples:
            # Quick drop, slow release
            pump_shape = np.concatenate([
                np.linspace(1.0, 1.0 - depth, pump_duration // 4),  # Quick drop
                np.linspace(1.0 - depth, 1.0, pump_duration - pump_duration // 4)  # Slow release
            ])
            pump_env[start_idx:start_idx + len(pump_shape)] = pump_shape

    return (base * pump_env).astype(np.float32)


def generate_stereo_audio(width: float, duration: float, sr: int = SR) -> np.ndarray:
    """Generate stereo audio with specified width."""
    samples = int(sr * duration)
    t = np.linspace(0, duration, samples, endpoint=False)

    # Mid signal
    mid = np.sin(2 * np.pi * 440 * t)

    # Side signal (detuned for stereo)
    side = np.sin(2 * np.pi * 443 * t) * width

    # Convert to L/R
    left = mid + side
    right = mid - side

    return np.vstack([left, right]).astype(np.float32)


class TestPumpingDetector:
    """Tests for sidechain pumping detection."""

    def test_no_pumping(self):
        """Constant signal should have no pumping detected."""
        audio = generate_sine_wave(440, 5.0)
        features = extract_pumping_features(audio, sr=SR)

        assert features.modulation_depth_db < 2.0
        assert features.modulation_depth_linear < 0.2

    def test_heavy_pumping(self):
        """Heavy sidechain should be detected."""
        audio = generate_pumping_audio(138, 5.0, depth=0.7)
        features = extract_pumping_features(audio, sr=SR, expected_bpm=138)

        assert features.modulation_depth_linear > 0.3
        assert features.num_pump_cycles > 5

    def test_pumping_score_range(self):
        """Pumping score should be 0-1."""
        audio = generate_pumping_audio(138, 5.0, depth=0.5)
        features = extract_pumping_features(audio, sr=SR)
        score = compute_pumping_score(features)

        assert 0.0 <= score <= 1.0

    def test_pumping_regularity(self):
        """Regular pumping should have low regularity value."""
        audio = generate_pumping_audio(138, 10.0, depth=0.5)
        features = extract_pumping_features(audio, sr=SR, expected_bpm=138)

        # Low regularity value = more consistent pumping
        assert features.pumping_regularity < 0.5


class TestAcidDetector:
    """Tests for 303 acid bassline detection."""

    def test_plain_bass_low_acid_score(self):
        """Plain sine bass should have low acid score."""
        audio = generate_sine_wave(80, 5.0)
        features = extract_acid_features(audio, sr=SR)

        assert features.overall_303_score < 0.5

    def test_score_components(self):
        """Score components should be 0-1 range."""
        audio = generate_sine_wave(100, 3.0)
        features = extract_acid_features(audio, sr=SR)

        assert 0.0 <= features.filter_sweep_score <= 1.0
        assert 0.0 <= features.resonance_score <= 1.0
        assert 0.0 <= features.glide_score <= 1.0
        assert 0.0 <= features.accent_score <= 1.0

    def test_compute_303_score_weights(self):
        """Weighted score computation should work correctly."""
        score = compute_303_score_from_components(
            filter_sweep=1.0,
            resonance=0.0,
            glides=0.0,
            accents=0.0
        )
        # Filter sweep weight is 0.30
        assert abs(score - 0.30) < 0.01


class TestSupersawAnalyzer:
    """Tests for supersaw stereo spread analysis."""

    def test_mono_signal(self):
        """Mono signal should have zero width."""
        mono = generate_sine_wave(440, 3.0)
        features = analyze_supersaw_characteristics(mono, sr=SR)

        assert features.stereo_width == 0.0
        assert features.phase_correlation == 1.0

    def test_stereo_width(self):
        """Stereo signal should have positive width."""
        stereo = generate_stereo_audio(width=0.5, duration=3.0)
        features = analyze_supersaw_characteristics(stereo, sr=SR)

        assert features.stereo_width > 0.0
        assert features.phase_correlation < 1.0

    def test_supersaw_score_range(self):
        """Supersaw score should be 0-1."""
        stereo = generate_stereo_audio(width=0.5, duration=3.0)
        features = analyze_supersaw_characteristics(stereo, sr=SR)
        score = compute_supersaw_score(features)

        assert 0.0 <= score <= 1.0


class TestEnergyCurves:
    """Tests for energy curve extraction."""

    def test_energy_curve_shape(self):
        """Energy curve should have expected shape."""
        audio = generate_sine_wave(440, 5.0)
        curves = extract_energy_curves(audio, sr=SR)

        assert len(curves.energy_curve) > 0
        assert len(curves.times) == len(curves.energy_curve)
        assert curves.energy_curve.min() >= 0.0
        assert curves.energy_curve.max() <= 1.0

    def test_energy_range(self):
        """Energy range should be computed correctly."""
        audio = generate_sine_wave(440, 5.0)
        curves = extract_energy_curves(audio, sr=SR)

        expected_range = curves.energy_curve.max() - curves.energy_curve.min()
        assert abs(curves.energy_range - expected_range) < 0.01

    def test_drop_detection_no_drops(self):
        """Constant audio should have no drops."""
        audio = generate_sine_wave(440, 10.0)
        curves = extract_energy_curves(audio, sr=SR)
        drops = detect_drops(curves)

        assert len(drops) == 0

    def test_progression_score_range(self):
        """Energy progression score should be 0-1."""
        audio = generate_sine_wave(440, 5.0)
        curves = extract_energy_curves(audio, sr=SR)
        score = compute_energy_progression_score(curves)

        assert 0.0 <= score <= 1.0


class TestRhythmAnalyzer:
    """Tests for tempo and rhythm analysis."""

    def test_tempo_detection_trance_range(self):
        """Should detect tempo in trance range."""
        audio = generate_kick_pattern(138, 10.0)
        features = detect_trance_tempo(audio, sr=SR)

        # Allow some tolerance
        assert 130 <= features.tempo <= 145
        assert features.is_trance_tempo

    def test_four_on_floor_detection(self):
        """Should detect 4-on-the-floor pattern."""
        audio = generate_kick_pattern(138, 10.0)
        features = detect_four_on_floor(audio, sr=SR, tempo=138)

        assert features.strength > 0.3
        # Note: is_four_on_floor requires both strength and consistency

    def test_tempo_stability(self):
        """Regular kick pattern should have high stability."""
        audio = generate_kick_pattern(138, 15.0)
        features = detect_trance_tempo(audio, sr=SR)

        assert features.tempo_stability > 0.5

    def test_rhythm_analysis_complete(self):
        """Complete rhythm analysis should return all components."""
        audio = generate_kick_pattern(138, 10.0)
        features = analyze_rhythm(audio, sr=SR)

        assert isinstance(features.tempo, TempoFeatures)
        assert hasattr(features, 'kicks')
        assert hasattr(features, 'hihats')
        assert hasattr(features, 'four_on_floor_score')
        assert hasattr(features, 'tempo_score')


class TestTranceScorer:
    """Tests for TranceScoreCalculator."""

    def test_score_range(self):
        """Total score should always be 0-1."""
        features = {
            'tempo_score': 0.5,
            'pumping_score': 0.5,
            'energy_progression': 0.5,
            'four_on_floor': 0.5,
            'supersaw_score': 0.5,
            'acid_303_score': 0.5,
            'offbeat_hihat': 0.5,
            'spectral_brightness': 0.5,
            'tempo_stability': 0.5
        }

        scorer = TranceScoreCalculator()
        score, breakdown = scorer.compute_total_score(features)

        assert 0.0 <= score <= 1.0

    def test_perfect_score(self):
        """All 1.0 components should give 1.0 total."""
        features = {
            'tempo_score': 1.0,
            'pumping_score': 1.0,
            'energy_progression': 1.0,
            'four_on_floor': 1.0,
            'supersaw_score': 1.0,
            'acid_303_score': 1.0,
            'offbeat_hihat': 1.0,
            'spectral_brightness': 1.0,
            'tempo_stability': 1.0
        }

        scorer = TranceScoreCalculator()
        score, _ = scorer.compute_total_score(features)

        assert abs(score - 1.0) < 0.01

    def test_zero_score(self):
        """All 0.0 components should give 0.0 total."""
        features = {
            'tempo_score': 0.0,
            'pumping_score': 0.0,
            'energy_progression': 0.0,
            'four_on_floor': 0.0,
            'supersaw_score': 0.0,
            'acid_303_score': 0.0,
            'offbeat_hihat': 0.0,
            'spectral_brightness': 0.0,
            'tempo_stability': 0.0
        }

        scorer = TranceScoreCalculator()
        score, _ = scorer.compute_total_score(features)

        assert abs(score - 0.0) < 0.01

    def test_weights_sum_to_one(self):
        """Default weights should sum to 1.0."""
        scorer = TranceScoreCalculator()
        total_weight = sum(scorer.weights.values())

        assert abs(total_weight - 1.0) < 0.01

    def test_custom_weights(self):
        """Custom weights should be normalized."""
        custom = {'tempo_score': 2.0, 'pumping_score': 2.0}
        scorer = TranceScoreCalculator(custom_weights=custom)

        total_weight = sum(scorer.weights.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_breakdown_components(self):
        """Breakdown should contain all components."""
        features = {
            'tempo_score': 0.8,
            'pumping_score': 0.6,
            'energy_progression': 0.7,
            'four_on_floor': 0.9,
            'supersaw_score': 0.5,
            'acid_303_score': 0.2,
            'offbeat_hihat': 0.7,
            'spectral_brightness': 0.6,
            'tempo_stability': 0.85
        }

        scorer = TranceScoreCalculator()
        _, breakdown = scorer.compute_total_score(features)

        assert breakdown.tempo_score == 0.8
        assert breakdown.pumping_score == 0.6
        assert breakdown.four_on_floor == 0.9

    def test_improvement_suggestions(self):
        """Should provide suggestions for low-scoring components."""
        breakdown = TranceScoreBreakdown(
            tempo_score=0.2,
            pumping_score=0.9,
            energy_progression=0.8,
            four_on_floor=0.9,
            supersaw_score=0.2,
            acid_303_score=0.5,
            offbeat_hihat=0.8,
            spectral_brightness=0.7,
            tempo_stability=0.9
        )

        scorer = TranceScoreCalculator()
        suggestions = scorer.get_improvement_suggestions(breakdown, threshold=0.5)

        # Should have suggestions for tempo and supersaw (both below 0.5)
        assert len(suggestions) >= 2
        assert any('tempo' in s.lower() for s in suggestions)
        assert any('stereo' in s.lower() or 'supersaw' in s.lower() for s in suggestions)

    def test_format_report(self):
        """Report formatting should not raise errors."""
        scorer = TranceScoreCalculator()
        breakdown = TranceScoreBreakdown(
            tempo_score=0.8,
            pumping_score=0.6,
            energy_progression=0.7,
            four_on_floor=0.9,
            supersaw_score=0.5,
            acid_303_score=0.2,
            offbeat_hihat=0.7,
            spectral_brightness=0.6,
            tempo_stability=0.85
        )

        report = scorer.format_score_report(0.65, breakdown)

        assert "Trance Score" in report
        assert "Tempo" in report
        assert "0.65" in report


class TestIntegration:
    """Integration tests for the full feature extraction pipeline."""

    def test_full_extraction_mono(self):
        """Full extraction should work on mono audio."""
        from feature_extraction import extract_all_trance_features

        # Generate test audio with kick pattern
        audio = generate_kick_pattern(138, 10.0)

        features = extract_all_trance_features(audio, sr=SR)

        assert 0.0 <= features.trance_score <= 1.0
        assert features.tempo > 0
        assert hasattr(features, 'trance_score_breakdown')

    def test_full_extraction_stereo(self):
        """Full extraction should work on stereo audio."""
        from feature_extraction import extract_all_trance_features

        # Generate stereo test audio
        stereo = generate_stereo_audio(width=0.5, duration=10.0)

        features = extract_all_trance_features(stereo, sr=SR)

        assert 0.0 <= features.trance_score <= 1.0
        assert features.stereo_width > 0.0

    def test_features_to_dict(self):
        """Features should be serializable to dict."""
        from feature_extraction import extract_all_trance_features

        audio = generate_sine_wave(440, 5.0)
        features = extract_all_trance_features(audio, sr=SR)

        feature_dict = features.to_dict()

        assert isinstance(feature_dict, dict)
        assert 'trance_score' in feature_dict
        assert 'tempo' in feature_dict


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
