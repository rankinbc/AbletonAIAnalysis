"""
Docker wrapper for Google Magenta (Melody RNN, Improv RNN, MusicVAE).

Runs Magenta in a Docker container with Python 3.9 / TensorFlow 2.11
to avoid compatibility issues on modern Python (3.11+).

Communication is JSON over stdin/stdout — the same pattern used by
shared/allin1 and shared/openl3.

Usage:
    from shared.magenta import DockerMagenta

    magenta = DockerMagenta()

    # Generate a chord-conditioned melody
    result = magenta.generate_melody(
        chords=["Am", "F", "C", "G"],
        bars=8, bpm=140, temperature=1.0
    )
    for candidate in result["candidates"]:
        print(candidate["midi_path"])

    # Create motif variations
    result = magenta.vary_motif("motif.mid", num_variants=4, noise_scale=0.3)

    # Interpolate between two melodies
    result = magenta.interpolate("melody_a.mid", "melody_b.mid", steps=8)
"""

import json
import subprocess
import tempfile
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Union


@dataclass
class MelodySummary:
    """Compact summary of a generated MIDI melody."""
    num_notes: int
    duration_seconds: float
    pitch_min: int = 0
    pitch_max: int = 0
    pitch_mean: float = 0.0


@dataclass
class GenerationResult:
    """Result from a melody generation or variation operation."""
    action: str
    success: bool
    midi_paths: List[Path] = field(default_factory=list)
    summaries: List[MelodySummary] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class DockerMagenta:
    """
    Wrapper to run Magenta operations via Docker.

    Each method call spins up a container, runs one operation, and
    returns structured results.  MIDI files are exchanged through
    mounted volumes — input MIDI is mounted read-only, output MIDI
    is written to a host directory.

    Usage:
        magenta = DockerMagenta()
        result = magenta.generate_melody(
            chords=["Am", "F", "C", "G"], bars=8
        )
        print(result.midi_paths)  # list of Path objects on the host

        result = magenta.vary_motif("motif.mid", num_variants=4)
        print(result.midi_paths)
    """

    def __init__(
        self,
        image_name: str = "magenta:latest",
        output_dir: Optional[Path] = None,
        use_gpu: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize Docker Magenta wrapper.

        Args:
            image_name: Docker image name (default: magenta:latest)
            output_dir: Directory for generated MIDI files.
                        If None, uses a temp directory per call.
            use_gpu: Whether to use GPU (requires nvidia-docker)
            verbose: Print Docker commands and raw output
        """
        self.image_name = image_name
        self.output_dir = Path(output_dir) if output_dir else None
        self.use_gpu = use_gpu
        self.verbose = verbose

    # ------------------------------------------------------------------
    # Docker health checks
    # ------------------------------------------------------------------

    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _check_image_exists(self) -> bool:
        """Check if the Magenta Docker image exists."""
        try:
            result = subprocess.run(
                ["docker", "images", "-q", self.image_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def build_image(self, dockerfile_dir: Optional[Path] = None) -> bool:
        """
        Build the Magenta Docker image.

        Args:
            dockerfile_dir: Directory containing Dockerfile
                            (auto-detected if None)

        Returns:
            True if build succeeded
        """
        if dockerfile_dir is None:
            dockerfile_dir = Path(__file__).parent

        dockerfile_path = dockerfile_dir / "Dockerfile"
        if not dockerfile_path.exists():
            print(f"Dockerfile not found: {dockerfile_path}")
            return False

        print(f"Building Docker image {self.image_name}...")
        print("This may take 10-15 minutes on first build "
              "(downloading models + TensorFlow)...")

        try:
            result = subprocess.run(
                [
                    "docker", "build",
                    "-t", self.image_name,
                    str(dockerfile_dir),
                ],
                capture_output=False,  # show build output
                timeout=3600,  # 60 minute timeout (large downloads)
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("Build timed out after 60 minutes")
            return False

    # ------------------------------------------------------------------
    # Core dispatch — sends a command to the container
    # ------------------------------------------------------------------

    def _run(
        self,
        command: Dict[str, Any],
        input_paths: Optional[List[Path]] = None,
        timeout: int = 120,
    ) -> GenerationResult:
        """
        Run a Magenta command inside Docker.

        Args:
            command: JSON-serializable dict with "action" and "params"
            input_paths: MIDI files to mount read-only in /input
            timeout: Timeout in seconds

        Returns:
            GenerationResult
        """
        action = command["action"]

        if not self._check_image_exists():
            print(f"Docker image {self.image_name} not found.")
            print("Build it with:")
            print(f"  cd {Path(__file__).parent}")
            print(f"  docker build -t {self.image_name} .")
            return GenerationResult(
                action=action, success=False,
                error=f"Docker image {self.image_name} not found",
            )

        # Determine output directory
        if self.output_dir:
            out_dir = self.output_dir
            out_dir.mkdir(parents=True, exist_ok=True)
            tmp_dir = None
        else:
            tmp_dir = tempfile.mkdtemp(prefix="magenta_")
            out_dir = Path(tmp_dir)

        # Build Docker command
        cmd = ["docker", "run", "--rm", "-i"]

        if self.use_gpu:
            cmd.extend(["--gpus", "all"])

        # Mount output directory
        cmd.extend(["-v", f"{out_dir}:/output"])

        # Mount input directories (deduplicated)
        if input_paths:
            mounted_dirs = set()
            for p in input_paths:
                p = Path(p).resolve()
                parent = str(p.parent)
                if parent not in mounted_dirs:
                    cmd.extend(["-v", f"{parent}:/input:ro"])
                    mounted_dirs.add(parent)
                    # Only mount one input dir; remap paths in params
                    break  # Docker can't mount multiple dirs to /input

            # Rewrite input paths relative to /input mount
            if input_paths:
                mount_root = Path(input_paths[0]).resolve().parent

        cmd.append(self.image_name)

        command_json = json.dumps(command)

        if self.verbose:
            print(f"Docker cmd: {' '.join(cmd)}")
            print(f"Input JSON: {command_json}")

        try:
            result = subprocess.run(
                cmd,
                input=command_json,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if self.verbose:
                if result.stderr:
                    print(f"stderr: {result.stderr[:500]}")

            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Container exited with non-zero status"
                # Try to parse stdout for a structured error
                try:
                    data = json.loads(result.stdout)
                    error_msg = data.get("error", error_msg)
                except (json.JSONDecodeError, ValueError):
                    pass
                return GenerationResult(
                    action=action, success=False, error=error_msg,
                )

            # Parse JSON output
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                return GenerationResult(
                    action=action, success=False,
                    error=f"Failed to parse output: {e}\n"
                          f"Raw: {result.stdout[:500]}",
                )

            if not data.get("success", False):
                return GenerationResult(
                    action=action, success=False,
                    error=data.get("error", "Unknown error"),
                    raw=data,
                )

            # Collect MIDI paths and summaries
            midi_paths = []
            summaries = []

            # Results can be in "candidates", "variants", "interpolations",
            # or "samples" depending on the action
            for key in ("candidates", "variants", "interpolations", "samples"):
                if key in data:
                    for item in data[key]:
                        container_path = item.get("midi_path", "")
                        filename = item.get("filename", "")
                        host_path = out_dir / filename
                        if host_path.exists():
                            midi_paths.append(host_path)
                        summary_data = item.get("summary", {})
                        summaries.append(MelodySummary(
                            num_notes=summary_data.get("num_notes", 0),
                            duration_seconds=summary_data.get("duration_seconds", 0.0),
                            pitch_min=summary_data.get("pitch_min", 0),
                            pitch_max=summary_data.get("pitch_max", 0),
                            pitch_mean=summary_data.get("pitch_mean", 0.0),
                        ))

            return GenerationResult(
                action=action,
                success=True,
                midi_paths=midi_paths,
                summaries=summaries,
                raw=data,
            )

        except subprocess.TimeoutExpired:
            return GenerationResult(
                action=action, success=False,
                error=f"Operation timed out after {timeout} seconds",
            )
        except FileNotFoundError:
            return GenerationResult(
                action=action, success=False,
                error="Docker not found. Is Docker installed and running?",
            )

    # ------------------------------------------------------------------
    # Public API — one method per Magenta action
    # ------------------------------------------------------------------

    def generate_melody(
        self,
        chords: List[str],
        bars: int = 8,
        bpm: float = 140.0,
        temperature: float = 1.0,
        key: str = "Am",
        num_candidates: int = 1,
        timeout: int = 120,
    ) -> GenerationResult:
        """
        Generate a chord-conditioned melody using Improv RNN.

        Args:
            chords: Chord symbols, e.g. ["Am", "F", "C", "G"]
            bars: Number of bars to generate
            bpm: Tempo
            temperature: Sampling temperature (0.5=conservative, 1.5=wild)
            key: Key signature (metadata only)
            num_candidates: Number of melodies to generate
            timeout: Timeout in seconds

        Returns:
            GenerationResult with midi_paths
        """
        return self._run({
            "action": "generate_melody",
            "params": {
                "chords": chords,
                "bars": bars,
                "bpm": bpm,
                "temperature": temperature,
                "key": key,
                "num_candidates": num_candidates,
            },
        }, timeout=timeout)

    def generate_attention(
        self,
        bars: int = 8,
        bpm: float = 140.0,
        temperature: float = 1.0,
        num_candidates: int = 1,
        timeout: int = 120,
    ) -> GenerationResult:
        """
        Generate an unconditional melody using Attention RNN.

        Args:
            bars: Number of bars
            bpm: Tempo
            temperature: Sampling temperature
            num_candidates: Number of melodies to generate
            timeout: Timeout in seconds

        Returns:
            GenerationResult with midi_paths
        """
        return self._run({
            "action": "generate_attention",
            "params": {
                "bars": bars,
                "bpm": bpm,
                "temperature": temperature,
                "num_candidates": num_candidates,
            },
        }, timeout=timeout)

    def vary_motif(
        self,
        input_midi: Union[str, Path],
        num_variants: int = 4,
        noise_scale: float = 0.3,
        bars: int = 2,
        timeout: int = 120,
    ) -> GenerationResult:
        """
        Create variations of a MIDI motif using MusicVAE.

        Args:
            input_midi: Path to input MIDI file
            num_variants: Number of variations
            noise_scale: How different the variations are
                         (0.1=subtle, 0.3=moderate, 0.8=major)
            bars: 2 or 16 (determines which MusicVAE model)
            timeout: Timeout in seconds

        Returns:
            GenerationResult with midi_paths for each variation
        """
        input_midi = Path(input_midi).resolve()
        if not input_midi.exists():
            return GenerationResult(
                action="vary_motif", success=False,
                error=f"Input MIDI not found: {input_midi}",
            )

        return self._run(
            {
                "action": "vary_motif",
                "params": {
                    "input_midi": f"/input/{input_midi.name}",
                    "num_variants": num_variants,
                    "noise_scale": noise_scale,
                    "bars": bars,
                },
            },
            input_paths=[input_midi],
            timeout=timeout,
        )

    def interpolate(
        self,
        input_midi_a: Union[str, Path],
        input_midi_b: Union[str, Path],
        steps: int = 8,
        bars: int = 2,
        timeout: int = 120,
    ) -> GenerationResult:
        """
        Interpolate between two MIDI melodies using MusicVAE.

        Args:
            input_midi_a: Path to first MIDI file
            input_midi_b: Path to second MIDI file
            steps: Number of intermediates
            bars: 2 or 16
            timeout: Timeout in seconds

        Returns:
            GenerationResult with midi_paths for each interpolation step
        """
        a = Path(input_midi_a).resolve()
        b = Path(input_midi_b).resolve()

        for path in (a, b):
            if not path.exists():
                return GenerationResult(
                    action="interpolate", success=False,
                    error=f"Input MIDI not found: {path}",
                )

        # Both files must be in the same directory for a single /input mount
        if a.parent != b.parent:
            # Copy both to a temp directory
            tmp = Path(tempfile.mkdtemp(prefix="magenta_interp_"))
            shutil.copy2(a, tmp / a.name)
            shutil.copy2(b, tmp / b.name)
            mount_dir = tmp
        else:
            mount_dir = a.parent

        return self._run(
            {
                "action": "interpolate",
                "params": {
                    "input_midi_a": f"/input/{a.name}",
                    "input_midi_b": f"/input/{b.name}",
                    "steps": steps,
                    "bars": bars,
                },
            },
            input_paths=[mount_dir / a.name],
            timeout=timeout,
        )

    def sample_musicvae(
        self,
        num_samples: int = 4,
        temperature: float = 0.5,
        bars: int = 2,
        timeout: int = 120,
    ) -> GenerationResult:
        """
        Sample random melodies from MusicVAE latent space.

        Args:
            num_samples: Number of melodies to sample
            temperature: Sampling temperature
            bars: 2 or 16
            timeout: Timeout in seconds

        Returns:
            GenerationResult with midi_paths
        """
        return self._run({
            "action": "sample_musicvae",
            "params": {
                "num_samples": num_samples,
                "temperature": temperature,
                "bars": bars,
            },
        }, timeout=timeout)

    def encode_motif(
        self,
        input_midi: Union[str, Path],
        bars: int = 2,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """
        Encode a MIDI motif to MusicVAE latent vector.

        Useful for building a motif similarity index.

        Args:
            input_midi: Path to MIDI file
            bars: 2 or 16
            timeout: Timeout in seconds

        Returns:
            Dict with 'mu' (mean latent vector) and 'sigma'
        """
        input_midi = Path(input_midi).resolve()
        if not input_midi.exists():
            return {"success": False, "error": f"Not found: {input_midi}"}

        result = self._run(
            {
                "action": "encode_motif",
                "params": {
                    "input_midi": f"/input/{input_midi.name}",
                    "bars": bars,
                },
            },
            input_paths=[input_midi],
            timeout=timeout,
        )
        return result.raw if result.success else {"success": False, "error": result.error}


# ------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------

def is_docker_available() -> bool:
    """Check if Docker is available on the system."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_magenta_image_available(image_name: str = "magenta:latest") -> bool:
    """Check if the Magenta Docker image exists."""
    try:
        result = subprocess.run(
            ["docker", "images", "-q", image_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
