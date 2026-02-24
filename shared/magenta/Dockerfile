# Magenta Docker Image
# Uses Python 3.9 + TensorFlow 2.11 to avoid compatibility issues on modern Python
#
# Magenta requires TF 2.11 and has never been updated for TF 2.12+/Python 3.10+.
# This container isolates the entire Magenta stack (TF, numpy 1.x, protobuf 3.x)
# from the host environment.
#
# Build:
#   docker build -t magenta:latest .
#
# Run (generate with Improv RNN):
#   echo '{"action":"generate_melody","params":{...}}' | \
#     docker run --rm -i -v /path/to/midi:/output magenta:latest
#
# Run (vary with MusicVAE):
#   echo '{"action":"vary_motif","params":{...}}' | \
#     docker run --rm -i -v /path/to/midi:/input:ro -v /path/to/output:/output magenta:latest

FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libasound2-dev \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Pin numpy/protobuf BEFORE installing anything else — Magenta's
# transitive dependencies pull incompatible versions otherwise
RUN pip install --no-cache-dir \
    numpy==1.23.5 \
    protobuf==3.20.3

# Install TensorFlow 2.11 (last version that works with Magenta)
RUN pip install --no-cache-dir tensorflow==2.11.0

# Install Magenta
RUN pip install --no-cache-dir magenta

# Install additional utilities for MIDI I/O and JSON handling
RUN pip install --no-cache-dir \
    pretty-midi \
    mido

# Create directories
RUN mkdir -p /input /output /models

# Download pre-trained model bundles
# Improv RNN (chord-conditioned melody generation)
RUN curl -fSL "https://storage.googleapis.com/magentadata/models/improv_rnn/chord_pitches_improv.mag" \
    -o /models/chord_pitches_improv.mag

# Melody RNN attention (unconditional melody generation)
RUN curl -fSL "https://storage.googleapis.com/magentadata/models/melody_rnn/attention_rnn.mag" \
    -o /models/attention_rnn.mag

# MusicVAE 2-bar melody (motif variation + interpolation)
RUN curl -fSL "https://storage.googleapis.com/magentadata/models/music_vae/colab2/mel_2bar_small.ckpt.index" \
    -o /models/mel_2bar_small.ckpt.index && \
    curl -fSL "https://storage.googleapis.com/magentadata/models/music_vae/colab2/mel_2bar_small.ckpt.meta" \
    -o /models/mel_2bar_small.ckpt.meta && \
    curl -fSL "https://storage.googleapis.com/magentadata/models/music_vae/colab2/mel_2bar_small.ckpt.data-00000-of-00001" \
    -o /models/mel_2bar_small.ckpt.data-00000-of-00001

# MusicVAE 16-bar melody (longer-form variation)
RUN curl -fSL "https://storage.googleapis.com/magentadata/models/music_vae/colab2/mel_16bar_small_q2.ckpt.index" \
    -o /models/mel_16bar_small_q2.ckpt.index && \
    curl -fSL "https://storage.googleapis.com/magentadata/models/music_vae/colab2/mel_16bar_small_q2.ckpt.meta" \
    -o /models/mel_16bar_small_q2.ckpt.meta && \
    curl -fSL "https://storage.googleapis.com/magentadata/models/music_vae/colab2/mel_16bar_small_q2.ckpt.data-00000-of-00001" \
    -o /models/mel_16bar_small_q2.ckpt.data-00000-of-00001

# Copy worker script
COPY magenta_worker.py /app/magenta_worker.py

ENTRYPOINT ["python", "/app/magenta_worker.py"]
