#!/usr/bin/env python3
"""
Magenta worker script — runs inside the Docker container.

Accepts a JSON command on stdin describing the operation to perform.
Outputs JSON results to stdout.  All MIDI files are read from /input
and written to /output (both mounted by the host wrapper).

Supported actions:
  - generate_melody      Improv RNN chord-conditioned melody generation
  - generate_attention    Attention RNN unconditional melody generation
  - vary_motif           MusicVAE encode→perturb→decode
  - interpolate          MusicVAE interpolation between two melodies
  - sample_musicvae      MusicVAE random sampling from latent space
  - encode_motif         MusicVAE encode only (return latent vector)
"""

import json
import os
import sys
import tempfile
import warnings

# Suppress TF/Magenta noise on stderr so only our JSON hits stdout
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore")

import numpy as np
import note_seq
from note_seq.protobuf import music_pb2


# ---------------------------------------------------------------------------
# Model loading (lazy — loaded on first use, then cached)
# ---------------------------------------------------------------------------

_improv_rnn = None
_attention_rnn = None
_musicvae_2bar = None
_musicvae_16bar = None


def _get_improv_rnn():
    global _improv_rnn
    if _improv_rnn is None:
        from magenta.models.improv_rnn import improv_rnn_sequence_generator
        from magenta.models.shared import sequence_generator_bundle
        bundle = sequence_generator_bundle.read_bundle_file(
            "/models/chord_pitches_improv.mag"
        )
        config_id = bundle.generator_details.id
        config = improv_rnn_sequence_generator.default_configs[config_id]
        _improv_rnn = improv_rnn_sequence_generator.ImprovRnnSequenceGenerator(
            model=improv_rnn_sequence_generator.ImprovRnnModel(),
            details=config.details,
            steps_per_quarter=config.steps_per_quarter,
            checkpoint=None,
            bundle=bundle,
        )
    return _improv_rnn


def _get_attention_rnn():
    global _attention_rnn
    if _attention_rnn is None:
        from magenta.models.melody_rnn import melody_rnn_sequence_generator
        from magenta.models.shared import sequence_generator_bundle
        bundle = sequence_generator_bundle.read_bundle_file(
            "/models/attention_rnn.mag"
        )
        config_id = bundle.generator_details.id
        config = melody_rnn_sequence_generator.default_configs[config_id]
        _attention_rnn = melody_rnn_sequence_generator.MelodyRnnSequenceGenerator(
            model=melody_rnn_sequence_generator.MelodyRnnModel(),
            details=config.details,
            steps_per_quarter=config.steps_per_quarter,
            checkpoint=None,
            bundle=bundle,
        )
    return _attention_rnn


def _get_musicvae(bars=2):
    global _musicvae_2bar, _musicvae_16bar
    from magenta.models.music_vae import configs as vae_configs
    from magenta.models.music_vae.trained_model import TrainedModel

    if bars <= 2:
        if _musicvae_2bar is None:
            config = vae_configs.CONFIG_MAP["cat-mel_2bar_small"]
            _musicvae_2bar = TrainedModel(
                config,
                batch_size=4,
                checkpoint_dir_or_path="/models/mel_2bar_small.ckpt",
            )
        return _musicvae_2bar
    else:
        if _musicvae_16bar is None:
            config = vae_configs.CONFIG_MAP["cat-mel_16bar_small_q2"]
            _musicvae_16bar = TrainedModel(
                config,
                batch_size=4,
                checkpoint_dir_or_path="/models/mel_16bar_small_q2.ckpt",
            )
        return _musicvae_16bar


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _ns_to_midi_path(ns, filename):
    """Write a NoteSequence to /output/<filename> and return the path."""
    path = f"/output/{filename}"
    note_seq.sequence_proto_to_midi_file(ns, path)
    return path


def _midi_to_ns(midi_path):
    """Read a MIDI file and return a NoteSequence."""
    return note_seq.midi_file_to_note_sequence(midi_path)


def _ns_summary(ns):
    """Return a compact summary dict for a NoteSequence."""
    notes = list(ns.notes)
    if not notes:
        return {"num_notes": 0, "duration_seconds": 0.0}
    pitches = [n.pitch for n in notes]
    return {
        "num_notes": len(notes),
        "duration_seconds": float(ns.total_time),
        "pitch_min": int(min(pitches)),
        "pitch_max": int(max(pitches)),
        "pitch_mean": float(np.mean(pitches)),
    }


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def generate_melody(params):
    """
    Generate a chord-conditioned melody with Improv RNN.

    params:
        chords: list of chord symbols, e.g. ["Am", "F", "C", "G"]
        bars: int (default 8)
        bpm: float (default 140)
        temperature: float (default 1.0)
        key: str (default "Am") — not used by Improv RNN directly, for metadata
        num_candidates: int (default 1) — generate N melodies to choose from
    """
    chords = params["chords"]
    bars = params.get("bars", 8)
    bpm = params.get("bpm", 140.0)
    temperature = params.get("temperature", 1.0)
    num_candidates = params.get("num_candidates", 1)

    generator = _get_improv_rnn()
    steps_per_bar = 16  # 16th-note resolution at 4/4
    total_steps = bars * steps_per_bar
    seconds_per_step = 60.0 / bpm / 4.0
    total_seconds = total_steps * seconds_per_step

    # Build a backing chord sequence
    backing_chords = music_pb2.NoteSequence()
    backing_chords.tempos.add(qpm=bpm)
    steps_per_chord = total_steps // len(chords)
    for i, chord_name in enumerate(chords):
        start = i * steps_per_chord * seconds_per_step
        end = (i + 1) * steps_per_chord * seconds_per_step
        backing_chords.text_annotations.add(
            text=chord_name,
            time=start,
            annotation_type=music_pb2.NoteSequence.TextAnnotation.CHORD_SYMBOL,
        )
    backing_chords.total_time = total_seconds

    results = []
    for idx in range(num_candidates):
        generator_options = note_seq.protobuf.generator_pb2.GeneratorOptions()
        generator_options.args["temperature"].float_value = temperature
        generator_options.generate_sections.add(
            start_time=0,
            end_time=total_seconds,
        )

        sequence = generator.generate(backing_chords, generator_options)
        filename = f"improv_rnn_{idx}.mid"
        midi_path = _ns_to_midi_path(sequence, filename)
        results.append({
            "midi_path": midi_path,
            "filename": filename,
            "summary": _ns_summary(sequence),
        })

    return {"candidates": results}


def generate_attention(params):
    """
    Generate an unconditional melody with Attention RNN.

    params:
        bars: int (default 8)
        bpm: float (default 140)
        temperature: float (default 1.0)
        num_candidates: int (default 1)
    """
    bars = params.get("bars", 8)
    bpm = params.get("bpm", 140.0)
    temperature = params.get("temperature", 1.0)
    num_candidates = params.get("num_candidates", 1)

    generator = _get_attention_rnn()
    steps_per_bar = 16
    total_steps = bars * steps_per_bar
    seconds_per_step = 60.0 / bpm / 4.0
    total_seconds = total_steps * seconds_per_step

    primer = music_pb2.NoteSequence()
    primer.tempos.add(qpm=bpm)

    results = []
    for idx in range(num_candidates):
        generator_options = note_seq.protobuf.generator_pb2.GeneratorOptions()
        generator_options.args["temperature"].float_value = temperature
        generator_options.generate_sections.add(
            start_time=0,
            end_time=total_seconds,
        )

        sequence = generator.generate(primer, generator_options)
        filename = f"attention_rnn_{idx}.mid"
        midi_path = _ns_to_midi_path(sequence, filename)
        results.append({
            "midi_path": midi_path,
            "filename": filename,
            "summary": _ns_summary(sequence),
        })

    return {"candidates": results}


def vary_motif(params):
    """
    Create variations of a MIDI motif using MusicVAE.

    params:
        input_midi: str — path inside /input, e.g. "/input/motif.mid"
        num_variants: int (default 4)
        noise_scale: float (default 0.3)
        bars: int (default 2) — determines which MusicVAE model (2 or 16)
    """
    input_midi = params["input_midi"]
    num_variants = params.get("num_variants", 4)
    noise_scale = params.get("noise_scale", 0.3)
    bars = params.get("bars", 2)

    model = _get_musicvae(bars=bars)
    ns = _midi_to_ns(input_midi)

    # Encode
    z, mu, sigma = model.encode([ns])

    results = []
    for idx in range(num_variants):
        z_perturbed = mu + np.random.normal(0, noise_scale, mu.shape)
        decoded = model.decode(z_perturbed, length=model._config.hparams.max_seq_len)
        variant_ns = decoded[0]
        filename = f"variant_{idx}.mid"
        midi_path = _ns_to_midi_path(variant_ns, filename)
        results.append({
            "midi_path": midi_path,
            "filename": filename,
            "summary": _ns_summary(variant_ns),
        })

    return {
        "input_summary": _ns_summary(ns),
        "latent_dim": int(mu.shape[-1]),
        "noise_scale": noise_scale,
        "variants": results,
    }


def interpolate(params):
    """
    Interpolate between two MIDI melodies using MusicVAE.

    params:
        input_midi_a: str — path inside /input
        input_midi_b: str — path inside /input
        steps: int (default 8) — number of intermediates
        bars: int (default 2)
    """
    input_a = params["input_midi_a"]
    input_b = params["input_midi_b"]
    steps = params.get("steps", 8)
    bars = params.get("bars", 2)

    model = _get_musicvae(bars=bars)
    ns_a = _midi_to_ns(input_a)
    ns_b = _midi_to_ns(input_b)

    z_a, _, _ = model.encode([ns_a])
    z_b, _, _ = model.encode([ns_b])

    results = []
    for idx in range(steps):
        t = idx / max(steps - 1, 1)
        z_interp = z_a * (1 - t) + z_b * t
        decoded = model.decode(z_interp, length=model._config.hparams.max_seq_len)
        interp_ns = decoded[0]
        filename = f"interp_{idx:02d}.mid"
        midi_path = _ns_to_midi_path(interp_ns, filename)
        results.append({
            "midi_path": midi_path,
            "filename": filename,
            "t": float(t),
            "summary": _ns_summary(interp_ns),
        })

    return {
        "input_a_summary": _ns_summary(ns_a),
        "input_b_summary": _ns_summary(ns_b),
        "steps": steps,
        "interpolations": results,
    }


def sample_musicvae(params):
    """
    Sample random melodies from MusicVAE latent space.

    params:
        num_samples: int (default 4)
        temperature: float (default 0.5)
        bars: int (default 2)
    """
    num_samples = params.get("num_samples", 4)
    temperature = params.get("temperature", 0.5)
    bars = params.get("bars", 2)

    model = _get_musicvae(bars=bars)
    samples = model.sample(n=num_samples, length=model._config.hparams.max_seq_len,
                           temperature=temperature)

    results = []
    for idx, sample_ns in enumerate(samples):
        filename = f"sample_{idx}.mid"
        midi_path = _ns_to_midi_path(sample_ns, filename)
        results.append({
            "midi_path": midi_path,
            "filename": filename,
            "summary": _ns_summary(sample_ns),
        })

    return {"temperature": temperature, "samples": results}


def encode_motif(params):
    """
    Encode a MIDI motif to MusicVAE latent vector (for similarity indexing).

    params:
        input_midi: str — path inside /input
        bars: int (default 2)
    """
    input_midi = params["input_midi"]
    bars = params.get("bars", 2)

    model = _get_musicvae(bars=bars)
    ns = _midi_to_ns(input_midi)

    z, mu, sigma = model.encode([ns])

    return {
        "input_summary": _ns_summary(ns),
        "latent_dim": int(mu.shape[-1]),
        "mu": mu[0].tolist(),
        "sigma": sigma[0].tolist(),
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

ACTIONS = {
    "generate_melody": generate_melody,
    "generate_attention": generate_attention,
    "vary_motif": vary_motif,
    "interpolate": interpolate,
    "sample_musicvae": sample_musicvae,
    "encode_motif": encode_motif,
}


def main():
    # Read JSON command from stdin
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "No input received on stdin. "
                          "Pipe a JSON command, e.g.: "
                          'echo \'{"action":"sample_musicvae","params":{}}\' | '
                          "docker run --rm -i magenta:latest"}),
              file=sys.stdout)
        sys.exit(1)

    try:
        command = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stdout)
        sys.exit(1)

    action = command.get("action")
    if action not in ACTIONS:
        print(json.dumps({
            "error": f"Unknown action: {action}",
            "available_actions": list(ACTIONS.keys()),
        }), file=sys.stdout)
        sys.exit(1)

    params = command.get("params", {})

    try:
        result = ACTIONS[action](params)
        result["action"] = action
        result["success"] = True
        print(json.dumps(result), file=sys.stdout)
    except Exception as e:
        print(json.dumps({
            "action": action,
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }), file=sys.stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
