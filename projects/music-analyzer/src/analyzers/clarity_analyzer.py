"""
Clarity Analyzer

Analyzes spectral clarity including:
- Spectral contrast (band prominence)
- Spectral flatness (tonal vs noise content)
- Spectral centroid (brightness center)
- Masking risk assessment
- Overall clarity scoring

Based on ai-music-mix-analyzer implementation, adapted for AbletonAIAnalysis.
"""

import numpy as np
import librosa
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ClarityInfo:
    """Clarity analysis results."""
    clarity_score: float                # 0-100 overall clarity score
    spectral_contrast: float            # Average spectral contrast in dB
    spectral_flatness: float            # 0-1 (0 = tonal, 1 = noise-like)
    spectral_centroid: float            # Hz - brightness center of mass
    masking_risk: str                   # 'low', 'moderate', 'high'
    brightness_category: str            # 'dark', 'balanced', 'bright', 'harsh'
    analysis: List[str] = field(default_factory=list)


class ClarityAnalyzer:
    """
    Analyzes spectral clarity of audio files.

    Uses spectral contrast, flatness, and centroid to assess mix clarity,
    definition, and potential masking issues.
    """

    def __init__(self, config=None):
        """
        Initialize the clarity analyzer.

        Args:
            config: Optional configuration object with clarity analysis settings
        """
        self.config = config

        # Load settings from config or use defaults
        if config and hasattr(config, 'clarity'):
            clarity_cfg = config.clarity
            self.muddy_flatness_threshold = clarity_cfg.get('muddy_flatness_threshold', 0.3)
            self.harsh_centroid_threshold = clarity_cfg.get('harsh_centroid_threshold', 4000)
            self.good_contrast_range = clarity_cfg.get('good_contrast_range', [20, 60])
        else:
            self.muddy_flatness_threshold = 0.3
            self.harsh_centroid_threshold = 4000
            self.good_contrast_range = [20, 60]

    def analyze(self, y: np.ndarray, sr: int) -> ClarityInfo:
        """
        Perform clarity analysis on audio.

        Args:
            y: Audio time series (mono or stereo)
            sr: Sample rate

        Returns:
            ClarityInfo with clarity metrics and analysis
        """
        # Ensure mono for analysis
        if len(y.shape) > 1:
            y = librosa.to_mono(y)

        analysis = []

        # Calculate spectral features with robust error handling
        spectral_contrast = self._calculate_spectral_contrast(y, sr)
        spectral_flatness = self._calculate_spectral_flatness(y, sr)
        spectral_centroid = self._calculate_spectral_centroid(y, sr)

        # Interpret brightness
        brightness_category = self._categorize_brightness(spectral_centroid)

        # Assess masking risk
        masking_risk = self._assess_masking_risk(spectral_contrast, spectral_flatness)

        # Calculate overall clarity score
        clarity_score = self._calculate_clarity_score(
            spectral_contrast,
            spectral_flatness,
            spectral_centroid
        )

        # Generate analysis text
        analysis.append(f"Clarity score: {clarity_score:.0f}/100")

        # Spectral contrast analysis
        if spectral_contrast < self.good_contrast_range[0]:
            analysis.append(f"Low spectral contrast ({spectral_contrast:.1f} dB) - mix may lack definition between instruments")
        elif spectral_contrast > self.good_contrast_range[1]:
            analysis.append(f"High spectral contrast ({spectral_contrast:.1f} dB) - prominent peaks, potential harshness")
        else:
            analysis.append(f"Good spectral contrast ({spectral_contrast:.1f} dB) - clear separation between elements")

        # Spectral flatness analysis
        if spectral_flatness > 0.5:
            analysis.append(f"High spectral flatness ({spectral_flatness:.2f}) - noisy or heavily processed sound")
        elif spectral_flatness < 0.1:
            analysis.append(f"Low spectral flatness ({spectral_flatness:.2f}) - strong tonal content")
        else:
            analysis.append(f"Moderate spectral flatness ({spectral_flatness:.2f}) - mix of tonal and textural content")

        # Brightness analysis
        analysis.append(f"Brightness: {brightness_category} (centroid: {spectral_centroid:.0f} Hz)")

        if brightness_category == 'dark':
            analysis.append("Mix sounds dark/muffled - consider adding presence (2-5kHz) or air (10-20kHz)")
        elif brightness_category == 'harsh':
            analysis.append("Mix sounds harsh - consider reducing 3-6kHz or using de-esser/dynamic EQ")

        # Masking risk
        if masking_risk == 'high':
            analysis.append("HIGH masking risk - elements may be fighting for the same frequencies")
        elif masking_risk == 'moderate':
            analysis.append("Moderate masking risk - some frequency overlap between elements")
        else:
            analysis.append("Low masking risk - good frequency separation")

        return ClarityInfo(
            clarity_score=clarity_score,
            spectral_contrast=spectral_contrast,
            spectral_flatness=spectral_flatness,
            spectral_centroid=spectral_centroid,
            masking_risk=masking_risk,
            brightness_category=brightness_category,
            analysis=analysis
        )

    def _calculate_spectral_contrast(self, y: np.ndarray, sr: int) -> float:
        """
        Calculate average spectral contrast.

        Spectral contrast measures the difference between peaks and valleys
        in the spectrum across frequency bands. Higher contrast = more definition.

        Returns:
            Average spectral contrast in dB
        """
        try:
            # Try primary method with 4 bands
            contrast = librosa.feature.spectral_contrast(
                y=y, sr=sr,
                n_fft=2048,
                hop_length=512,
                n_bands=4
            )
            # Average across time and bands
            avg_contrast = np.mean(contrast)
            return float(avg_contrast)

        except Exception:
            # Fallback method 1: Different parameters
            try:
                contrast = librosa.feature.spectral_contrast(
                    y=y, sr=sr,
                    n_fft=4096,
                    hop_length=1024,
                    n_bands=6
                )
                return float(np.mean(contrast))
            except Exception:
                pass

            # Fallback method 2: Manual calculation
            try:
                D = np.abs(librosa.stft(y, n_fft=2048))
                # Calculate std dev across frequency as rough contrast measure
                contrast_approx = np.std(librosa.amplitude_to_db(D, ref=np.max))
                return float(contrast_approx)
            except Exception:
                return 30.0  # Default mid-range value

    def _calculate_spectral_flatness(self, y: np.ndarray, sr: int) -> float:
        """
        Calculate average spectral flatness.

        Flatness close to 0 = tonal (clear pitches)
        Flatness close to 1 = noise-like (no clear pitches)

        Returns:
            Average spectral flatness (0-1)
        """
        try:
            flatness = librosa.feature.spectral_flatness(y=y)
            avg_flatness = np.mean(flatness)
            return float(avg_flatness)
        except Exception:
            return 0.3  # Default mid-range value

    def _calculate_spectral_centroid(self, y: np.ndarray, sr: int) -> float:
        """
        Calculate average spectral centroid.

        The centroid is the "center of mass" of the spectrum.
        Higher centroid = brighter sound.

        Returns:
            Average spectral centroid in Hz
        """
        try:
            centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
            avg_centroid = np.mean(centroid)
            return float(avg_centroid)
        except Exception:
            return 2500.0  # Default mid-range value

    def _categorize_brightness(self, centroid: float) -> str:
        """
        Categorize brightness based on spectral centroid.

        Args:
            centroid: Spectral centroid in Hz

        Returns:
            Brightness category string
        """
        if centroid < 1000:
            return 'dark'
        elif centroid < 2000:
            return 'warm'
        elif centroid < 3500:
            return 'balanced'
        elif centroid < self.harsh_centroid_threshold:
            return 'bright'
        else:
            return 'harsh'

    def _assess_masking_risk(self, contrast: float, flatness: float) -> str:
        """
        Assess masking risk based on spectral characteristics.

        Low contrast + high flatness = high masking risk
        (everything is at similar levels, hard to distinguish elements)

        Returns:
            Risk level: 'low', 'moderate', or 'high'
        """
        # Calculate risk score
        # Low contrast increases risk
        contrast_risk = max(0, (30 - contrast) / 30)

        # High flatness increases risk
        flatness_risk = flatness

        # Combined risk
        combined_risk = (contrast_risk * 0.6) + (flatness_risk * 0.4)

        if combined_risk > 0.6:
            return 'high'
        elif combined_risk > 0.3:
            return 'moderate'
        else:
            return 'low'

    def _calculate_clarity_score(
        self,
        contrast: float,
        flatness: float,
        centroid: float
    ) -> float:
        """
        Calculate overall clarity score (0-100).

        Combines spectral metrics into a single score.
        """
        # Contrast score (optimal range: 20-50 dB)
        if contrast < 15:
            contrast_score = contrast / 15 * 50  # 0-50 for low contrast
        elif contrast <= 50:
            contrast_score = 80 + ((contrast - 20) / 30 * 20)  # 80-100 for good range
        else:
            contrast_score = max(50, 100 - (contrast - 50) * 2)  # Penalty for too high

        # Flatness score (lower is generally better for clarity)
        # But very low can indicate lack of texture
        if flatness < 0.1:
            flatness_score = 70 + flatness * 200  # 70-90 for very tonal
        elif flatness <= 0.4:
            flatness_score = 90 - (flatness - 0.1) * 50  # 90-75 for moderate
        else:
            flatness_score = max(30, 75 - (flatness - 0.4) * 100)  # Penalty for noisy

        # Centroid score (optimal: 1500-3500 Hz for most music)
        if centroid < 1000:
            centroid_score = 50 + (centroid / 1000) * 30  # Dark penalty
        elif centroid <= 3500:
            centroid_score = 90 + ((centroid - 1500) / 2000 * 10)  # Optimal range
        elif centroid <= 4500:
            centroid_score = 85 - ((centroid - 3500) / 1000 * 15)  # Slight bright penalty
        else:
            centroid_score = max(50, 70 - ((centroid - 4500) / 1000 * 20))  # Harsh penalty

        # Weighted combination
        clarity_score = (
            contrast_score * 0.4 +
            flatness_score * 0.35 +
            centroid_score * 0.25
        )

        return max(0, min(100, clarity_score))
