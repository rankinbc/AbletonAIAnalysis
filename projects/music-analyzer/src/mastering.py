"""
Mastering Module

AI-powered mastering using Matchering library.
Matches the loudness, EQ, and dynamics of a target track
to a reference track.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
import soundfile as sf


@dataclass
class MasteringResult:
    """Result of the mastering process."""
    success: bool
    input_path: str
    output_path: str
    reference_path: str
    error_message: Optional[str] = None
    before_lufs: Optional[float] = None
    after_lufs: Optional[float] = None
    reference_lufs: Optional[float] = None


class MasteringEngine:
    """AI mastering engine using Matchering."""

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def master(
        self,
        target_path: str,
        reference_path: str,
        output_name: Optional[str] = None
    ) -> MasteringResult:
        """
        Master a track to match a reference.

        Args:
            target_path: Path to the track to be mastered
            reference_path: Path to the reference track
            output_name: Optional name for output file (without extension)

        Returns:
            MasteringResult with success status and file paths
        """
        target = Path(target_path)
        reference = Path(reference_path)

        if not target.exists():
            return MasteringResult(
                success=False,
                input_path=str(target),
                output_path="",
                reference_path=str(reference),
                error_message=f"Target file not found: {target_path}"
            )

        if not reference.exists():
            return MasteringResult(
                success=False,
                input_path=str(target),
                output_path="",
                reference_path=str(reference),
                error_message=f"Reference file not found: {reference_path}"
            )

        # Generate output filename
        if output_name is None:
            output_name = f"{target.stem}_mastered"

        output_path = self.output_dir / f"{output_name}.wav"

        try:
            # Try to use matchering
            import matchering as mg

            # Measure levels before mastering
            before_lufs = self._estimate_lufs(target_path)
            ref_lufs = self._estimate_lufs(reference_path)

            # Run matchering
            mg.process(
                target=str(target),
                reference=str(reference),
                results=[
                    mg.Result(
                        str(output_path),
                        subtype="PCM_16",
                        use_limiter=True
                    )
                ]
            )

            # Measure after
            after_lufs = self._estimate_lufs(str(output_path))

            return MasteringResult(
                success=True,
                input_path=str(target),
                output_path=str(output_path),
                reference_path=str(reference),
                before_lufs=before_lufs,
                after_lufs=after_lufs,
                reference_lufs=ref_lufs
            )

        except ImportError:
            # Matchering not installed, try fallback
            return self._fallback_master(target_path, reference_path, str(output_path))

        except Exception as e:
            return MasteringResult(
                success=False,
                input_path=str(target),
                output_path=str(output_path),
                reference_path=str(reference),
                error_message=str(e)
            )

    def _fallback_master(
        self,
        target_path: str,
        reference_path: str,
        output_path: str
    ) -> MasteringResult:
        """
        Fallback mastering when matchering isn't available.
        Does basic loudness matching.
        """
        try:
            # Load audio
            target_audio, target_sr = sf.read(target_path)
            ref_audio, ref_sr = sf.read(reference_path)

            # Calculate RMS
            target_rms = np.sqrt(np.mean(target_audio ** 2))
            ref_rms = np.sqrt(np.mean(ref_audio ** 2))

            # Calculate gain to match
            if target_rms > 0:
                gain = ref_rms / target_rms
            else:
                gain = 1.0

            # Apply gain with limiting
            mastered = target_audio * gain

            # Simple limiter
            peak = np.max(np.abs(mastered))
            if peak > 0.99:
                mastered = mastered * (0.99 / peak)

            # Save
            sf.write(output_path, mastered, target_sr, subtype='PCM_16')

            before_lufs = self._estimate_lufs(target_path)
            after_lufs = self._estimate_lufs(output_path)
            ref_lufs = self._estimate_lufs(reference_path)

            return MasteringResult(
                success=True,
                input_path=target_path,
                output_path=output_path,
                reference_path=reference_path,
                before_lufs=before_lufs,
                after_lufs=after_lufs,
                reference_lufs=ref_lufs,
                error_message="Used fallback mastering (matchering not available)"
            )

        except Exception as e:
            return MasteringResult(
                success=False,
                input_path=target_path,
                output_path=output_path,
                reference_path=reference_path,
                error_message=f"Fallback mastering failed: {str(e)}"
            )

    def _estimate_lufs(self, audio_path: str) -> float:
        """
        Estimate integrated LUFS of an audio file.
        This is a simplified approximation.
        """
        try:
            audio, sr = sf.read(audio_path)

            # Convert to mono if stereo
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)

            # Simple RMS-based LUFS approximation
            rms = np.sqrt(np.mean(audio ** 2))
            lufs_estimate = 20 * np.log10(rms + 1e-10) - 0.691

            return float(lufs_estimate)

        except Exception:
            return -24.0  # Default if estimation fails

    def compare_before_after(
        self,
        result: MasteringResult
    ) -> dict:
        """
        Generate comparison metrics between original and mastered.

        Args:
            result: MasteringResult from a mastering operation

        Returns:
            Dictionary with comparison metrics
        """
        if not result.success:
            return {"error": result.error_message}

        try:
            # Load both versions
            original, sr1 = sf.read(result.input_path)
            mastered, sr2 = sf.read(result.output_path)
            reference, sr3 = sf.read(result.reference_path)

            # Make mono for analysis
            if len(original.shape) > 1:
                original = np.mean(original, axis=1)
            if len(mastered.shape) > 1:
                mastered = np.mean(mastered, axis=1)
            if len(reference.shape) > 1:
                reference = np.mean(reference, axis=1)

            # Calculate metrics
            orig_peak = float(20 * np.log10(np.max(np.abs(original)) + 1e-10))
            mast_peak = float(20 * np.log10(np.max(np.abs(mastered)) + 1e-10))
            ref_peak = float(20 * np.log10(np.max(np.abs(reference)) + 1e-10))

            orig_rms = float(20 * np.log10(np.sqrt(np.mean(original ** 2)) + 1e-10))
            mast_rms = float(20 * np.log10(np.sqrt(np.mean(mastered ** 2)) + 1e-10))
            ref_rms = float(20 * np.log10(np.sqrt(np.mean(reference ** 2)) + 1e-10))

            return {
                "original": {
                    "peak_db": orig_peak,
                    "rms_db": orig_rms,
                    "estimated_lufs": result.before_lufs
                },
                "mastered": {
                    "peak_db": mast_peak,
                    "rms_db": mast_rms,
                    "estimated_lufs": result.after_lufs
                },
                "reference": {
                    "peak_db": ref_peak,
                    "rms_db": ref_rms,
                    "estimated_lufs": result.reference_lufs
                },
                "changes": {
                    "loudness_increase_db": mast_rms - orig_rms,
                    "peak_increase_db": mast_peak - orig_peak,
                    "lufs_change": (result.after_lufs or 0) - (result.before_lufs or 0)
                },
                "match_quality": {
                    "rms_diff_from_ref": abs(mast_rms - ref_rms),
                    "lufs_diff_from_ref": abs((result.after_lufs or 0) - (result.reference_lufs or 0))
                }
            }

        except Exception as e:
            return {"error": str(e)}


def quick_master(target: str, reference: str, output_dir: str = "./output") -> MasteringResult:
    """Quick function to master a track."""
    engine = MasteringEngine(output_dir)
    return engine.master(target, reference)
