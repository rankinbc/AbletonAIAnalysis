"""
MidiTok REMI tokenization for trance melody generation.

Provides a configured REMI tokenizer and bidirectional conversion
pipeline between MIDI files, NoteEvent lists, and token sequences.

This is the standard tokenization layer used by all ML models in the
melody improvement pipeline (Phase 1 Step 1.3).

Usage:
    from melody_generation.tokenizer import (
        get_tokenizer,
        notes_to_midi,
        midi_to_tokens,
        tokens_to_midi,
        notes_to_tokens,
        validate_roundtrip,
    )

    # NoteEvent list → MIDI file
    midi_path = notes_to_midi(notes, "output.mid", bpm=140)

    # MIDI file → tokens
    tokens = midi_to_tokens("melody.mid")

    # Tokens → MIDI file
    midi_path = tokens_to_midi(tokens, "decoded.mid")

    # NoteEvent list → tokens (shortcut)
    tokens = notes_to_tokens(notes, bpm=140)

    # Validate roundtrip fidelity
    report = validate_roundtrip("melody.mid")
    print(f"Pitch match: {report['pitch_match_ratio']:.1%}")
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from miditok import REMI, TokenizerConfig
    from miditok.constants import MIDI_INSTRUMENTS
    MIDITOK_AVAILABLE = True
except ImportError:
    MIDITOK_AVAILABLE = False

try:
    import mido
    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False

from .models import NoteEvent, Pitch


# ---------------------------------------------------------------------------
# Tokenizer configuration — trance-specific REMI settings
# ---------------------------------------------------------------------------

# Default config tuned for trance lead melodies
TRANCE_TOKENIZER_CONFIG = {
    "num_velocities": 32,
    "use_chords": True,
    "use_programs": False,       # monophonic lead melody — no program changes
    "use_tempos": True,
    "use_time_signatures": True,
    "beat_res": {(0, 4): 4},    # 16th note resolution within each beat
    "tempo_range": (130, 150),   # trance BPM range
    "num_tempos": 10,
}

# BPE configuration
DEFAULT_BPE_VOCAB_SIZE = 3000


@dataclass
class TokenizerConfig_:
    """Wrapper for tokenizer configuration with save/load."""
    remi_config: Dict[str, Any] = field(default_factory=lambda: dict(TRANCE_TOKENIZER_CONFIG))
    bpe_vocab_size: int = DEFAULT_BPE_VOCAB_SIZE
    bpe_trained: bool = False

    def to_dict(self) -> dict:
        cfg = dict(self.remi_config)
        # Convert tuple keys to strings for JSON serialization
        if "beat_res" in cfg:
            cfg["beat_res"] = {f"{k[0]},{k[1]}": v for k, v in cfg["beat_res"].items()}
        if "tempo_range" in cfg:
            cfg["tempo_range"] = list(cfg["tempo_range"])
        return {
            "remi_config": cfg,
            "bpe_vocab_size": self.bpe_vocab_size,
            "bpe_trained": self.bpe_trained,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TokenizerConfig_":
        cfg = dict(d["remi_config"])
        # Restore tuple keys
        if "beat_res" in cfg:
            cfg["beat_res"] = {
                tuple(int(x) for x in k.split(",")): v
                for k, v in cfg["beat_res"].items()
            }
        if "tempo_range" in cfg:
            cfg["tempo_range"] = tuple(cfg["tempo_range"])
        return cls(
            remi_config=cfg,
            bpe_vocab_size=d.get("bpe_vocab_size", DEFAULT_BPE_VOCAB_SIZE),
            bpe_trained=d.get("bpe_trained", False),
        )

    def save(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "TokenizerConfig_":
        with open(path) as f:
            return cls.from_dict(json.load(f))


# ---------------------------------------------------------------------------
# Tokenizer singleton
# ---------------------------------------------------------------------------

_tokenizer: Optional[Any] = None
_tokenizer_config: Optional[TokenizerConfig_] = None


def get_tokenizer(config: Optional[TokenizerConfig_] = None) -> Any:
    """
    Get or create the REMI tokenizer with trance-appropriate settings.

    Returns the MidiTok REMI tokenizer instance. Creates one with default
    trance config if none exists yet.

    Args:
        config: Optional custom config. If None, uses trance defaults.

    Returns:
        REMI tokenizer instance

    Raises:
        ImportError: If miditok is not installed
    """
    global _tokenizer, _tokenizer_config

    if not MIDITOK_AVAILABLE:
        raise ImportError(
            "miditok is required for tokenization. "
            "Install with: pip install miditok"
        )

    if config is not None or _tokenizer is None:
        cfg = config or TokenizerConfig_()
        _tokenizer_config = cfg

        tok_config = TokenizerConfig(**cfg.remi_config)
        _tokenizer = REMI(tok_config)

    return _tokenizer


def save_tokenizer(path: Path, tokenizer=None):
    """Save tokenizer (with vocabulary if BPE was trained) to directory."""
    if not MIDITOK_AVAILABLE:
        raise ImportError("miditok is required")

    tok = tokenizer or get_tokenizer()
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)

    tok.save(path / "tokenizer.json")
    if _tokenizer_config:
        _tokenizer_config.save(path / "config.json")


def load_tokenizer(path: Path):
    """Load tokenizer from directory."""
    global _tokenizer, _tokenizer_config

    if not MIDITOK_AVAILABLE:
        raise ImportError("miditok is required")

    path = Path(path)
    config_path = path / "config.json"

    if config_path.exists():
        _tokenizer_config = TokenizerConfig_.load(config_path)

    _tokenizer = REMI(params=path / "tokenizer.json")
    return _tokenizer


# ---------------------------------------------------------------------------
# NoteEvent ↔ MIDI conversion (works without miditok)
# ---------------------------------------------------------------------------

def notes_to_midi(
    notes: List[NoteEvent],
    output_path: str | Path,
    bpm: float = 140.0,
    ticks_per_beat: int = 480,
) -> Path:
    """
    Convert NoteEvent list to a MIDI file.

    Args:
        notes: List of NoteEvent objects
        output_path: Where to write the MIDI file
        bpm: Tempo
        ticks_per_beat: MIDI resolution

    Returns:
        Path to written MIDI file
    """
    if not MIDO_AVAILABLE:
        raise ImportError("mido is required. Install with: pip install mido")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Tempo meta message
    tempo_us = mido.bpm2tempo(bpm)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo_us, time=0))

    # Time signature
    track.append(mido.MetaMessage(
        "time_signature", numerator=4, denominator=4, time=0
    ))

    # Sort notes by start time
    sorted_notes = sorted(notes, key=lambda n: n.actual_start)

    # Build note-on/note-off events
    events = []
    for note in sorted_notes:
        start_tick = int(note.actual_start * ticks_per_beat)
        end_tick = int(note.end_beat * ticks_per_beat)
        midi_note = note.pitch.midi_note
        vel = max(1, min(127, note.velocity))

        events.append((start_tick, "note_on", midi_note, vel))
        events.append((end_tick, "note_off", midi_note, 0))

    # Sort by tick, note_off before note_on at same tick
    events.sort(key=lambda e: (e[0], 0 if e[1] == "note_off" else 1))

    # Convert to delta-time MIDI messages
    current_tick = 0
    for tick, msg_type, note, vel in events:
        delta = tick - current_tick
        track.append(mido.Message(msg_type, note=note, velocity=vel, time=delta))
        current_tick = tick

    mid.save(str(output_path))
    return output_path


def midi_to_notes(
    midi_path: str | Path,
    bpm: Optional[float] = None,
) -> List[NoteEvent]:
    """
    Read a MIDI file and convert to NoteEvent list.

    Args:
        midi_path: Path to MIDI file
        bpm: Override tempo (if None, reads from MIDI)

    Returns:
        List of NoteEvent objects
    """
    if not MIDO_AVAILABLE:
        raise ImportError("mido is required")

    mid = mido.MidiFile(str(midi_path))
    ticks_per_beat = mid.ticks_per_beat

    # Find tempo from MIDI (default 120 BPM)
    midi_tempo = 500000  # 120 BPM default
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                midi_tempo = msg.tempo
                break

    if bpm is not None:
        effective_bpm = bpm
    else:
        effective_bpm = mido.tempo2bpm(midi_tempo)

    notes = []
    # Track active notes: {(channel, pitch): (start_beat, velocity)}
    active: Dict[Tuple[int, int], Tuple[float, int]] = {}

    for track in mid.tracks:
        current_tick = 0
        for msg in track:
            current_tick += msg.time
            current_beat = current_tick / ticks_per_beat

            if msg.type == "note_on" and msg.velocity > 0:
                active[(msg.channel, msg.note)] = (current_beat, msg.velocity)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                key = (msg.channel, msg.note)
                if key in active:
                    start_beat, velocity = active.pop(key)
                    duration = current_beat - start_beat
                    if duration > 0:
                        notes.append(NoteEvent(
                            pitch=Pitch.from_midi(msg.note),
                            start_beat=start_beat,
                            duration_beats=duration,
                            velocity=velocity,
                        ))

    notes.sort(key=lambda n: n.start_beat)
    return notes


# ---------------------------------------------------------------------------
# Token conversion (requires miditok)
# ---------------------------------------------------------------------------

def midi_to_tokens(midi_path: str | Path) -> List:
    """
    Tokenize a MIDI file using REMI.

    Args:
        midi_path: Path to MIDI file

    Returns:
        Token sequence (MidiTok TokSequence)
    """
    tokenizer = get_tokenizer()
    return tokenizer(Path(midi_path))


def tokens_to_midi(tokens, output_path: str | Path) -> Path:
    """
    Decode token sequence back to MIDI.

    Args:
        tokens: Token sequence from midi_to_tokens
        output_path: Where to write the MIDI file

    Returns:
        Path to decoded MIDI file
    """
    tokenizer = get_tokenizer()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    midi = tokenizer.decode(tokens)
    midi.dump_midi(output_path)
    return output_path


def notes_to_tokens(
    notes: List[NoteEvent],
    bpm: float = 140.0,
) -> List:
    """
    Convert NoteEvent list directly to tokens.

    Shortcut: notes → temp MIDI → tokens.

    Args:
        notes: List of NoteEvent objects
        bpm: Tempo for MIDI export

    Returns:
        Token sequence
    """
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        tmp_path = Path(f.name)

    try:
        notes_to_midi(notes, tmp_path, bpm=bpm)
        return midi_to_tokens(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def tokens_to_notes(tokens, bpm: Optional[float] = None) -> List[NoteEvent]:
    """
    Convert tokens back to NoteEvent list.

    Shortcut: tokens → temp MIDI → notes.

    Args:
        tokens: Token sequence
        bpm: Override tempo

    Returns:
        List of NoteEvent objects
    """
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        tmp_path = Path(f.name)

    try:
        tokens_to_midi(tokens, tmp_path)
        return midi_to_notes(tmp_path, bpm=bpm)
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Roundtrip validation
# ---------------------------------------------------------------------------

@dataclass
class RoundtripReport:
    """Results of a tokenize→decode roundtrip validation."""
    original_notes: int
    decoded_notes: int
    pitch_match_ratio: float
    timing_match_ratio: float
    duration_match_ratio: float
    max_pitch_error: int
    max_timing_error: float
    passed: bool

    def to_dict(self) -> dict:
        return {
            "original_notes": self.original_notes,
            "decoded_notes": self.decoded_notes,
            "pitch_match_ratio": self.pitch_match_ratio,
            "timing_match_ratio": self.timing_match_ratio,
            "duration_match_ratio": self.duration_match_ratio,
            "max_pitch_error": self.max_pitch_error,
            "max_timing_error": self.max_timing_error,
            "passed": self.passed,
        }


def validate_roundtrip(
    midi_path: str | Path,
    pitch_tolerance: int = 0,
    timing_tolerance: float = 0.05,
) -> RoundtripReport:
    """
    Validate tokenize→decode roundtrip fidelity.

    Tokenizes a MIDI file, decodes back, and compares note-by-note.

    Args:
        midi_path: Path to original MIDI file
        pitch_tolerance: Allowed pitch difference (semitones)
        timing_tolerance: Allowed timing difference (beats)

    Returns:
        RoundtripReport with match ratios
    """
    original = midi_to_notes(midi_path)
    tokens = midi_to_tokens(midi_path)

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        tmp_path = Path(f.name)

    try:
        tokens_to_midi(tokens, tmp_path)
        decoded = midi_to_notes(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not original or not decoded:
        return RoundtripReport(
            original_notes=len(original),
            decoded_notes=len(decoded),
            pitch_match_ratio=0.0,
            timing_match_ratio=0.0,
            duration_match_ratio=0.0,
            max_pitch_error=0,
            max_timing_error=0.0,
            passed=False,
        )

    # Match notes greedily by timing proximity
    pitch_matches = 0
    timing_matches = 0
    duration_matches = 0
    max_pitch_err = 0
    max_timing_err = 0.0

    decoded_used = set()
    for orig in original:
        best_idx = None
        best_dist = float("inf")
        for i, dec in enumerate(decoded):
            if i in decoded_used:
                continue
            dist = abs(orig.start_beat - dec.start_beat)
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_idx is not None:
            decoded_used.add(best_idx)
            dec = decoded[best_idx]

            pitch_err = abs(orig.pitch.midi_note - dec.pitch.midi_note)
            timing_err = abs(orig.start_beat - dec.start_beat)
            dur_err = abs(orig.duration_beats - dec.duration_beats)

            max_pitch_err = max(max_pitch_err, pitch_err)
            max_timing_err = max(max_timing_err, timing_err)

            if pitch_err <= pitch_tolerance:
                pitch_matches += 1
            if timing_err <= timing_tolerance:
                timing_matches += 1
            if dur_err <= timing_tolerance:
                duration_matches += 1

    n = len(original)
    pitch_ratio = pitch_matches / n
    timing_ratio = timing_matches / n
    duration_ratio = duration_matches / n

    passed = (
        pitch_ratio >= 0.95
        and timing_ratio >= 0.90
        and abs(len(original) - len(decoded)) <= max(2, n * 0.1)
    )

    return RoundtripReport(
        original_notes=len(original),
        decoded_notes=len(decoded),
        pitch_match_ratio=pitch_ratio,
        timing_match_ratio=timing_ratio,
        duration_match_ratio=duration_ratio,
        max_pitch_error=max_pitch_err,
        max_timing_error=max_timing_err,
        passed=passed,
    )


# ---------------------------------------------------------------------------
# BPE training
# ---------------------------------------------------------------------------

def train_bpe(
    midi_dir: str | Path,
    vocab_size: int = DEFAULT_BPE_VOCAB_SIZE,
    output_dir: Optional[str | Path] = None,
) -> Any:
    """
    Train BPE on top of REMI tokens from a directory of MIDI files.

    Args:
        midi_dir: Directory containing MIDI files
        vocab_size: Target BPE vocabulary size (1000–5000)
        output_dir: Where to save the trained tokenizer

    Returns:
        Trained tokenizer
    """
    global _tokenizer_config

    tokenizer = get_tokenizer()
    midi_dir = Path(midi_dir)
    midi_files = list(midi_dir.glob("**/*.mid")) + list(midi_dir.glob("**/*.midi"))

    if not midi_files:
        raise ValueError(f"No MIDI files found in {midi_dir}")

    tokenizer.learn_bpe(
        vocab_size=vocab_size,
        files_paths=midi_files,
    )

    if _tokenizer_config:
        _tokenizer_config.bpe_trained = True
        _tokenizer_config.bpe_vocab_size = vocab_size

    if output_dir:
        save_tokenizer(Path(output_dir), tokenizer)

    return tokenizer
