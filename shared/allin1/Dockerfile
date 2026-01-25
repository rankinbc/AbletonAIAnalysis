# allin1 Docker Image with GPU Support
# Uses Python 3.11 to avoid compatibility issues with madmom/natten on Python 3.13
#
# Build:
#   docker build -t allin1:latest .
#
# Run (CPU):
#   docker run --rm -v /path/to/audio:/input:ro allin1:latest --json /input/song.wav
#
# Run (GPU):
#   docker run --rm --gpus all -v /path/to/audio:/input:ro allin1:latest --json /input/song.wav

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install PyTorch with CUDA 11.8 support
# This works for both CPU and GPU - PyTorch auto-detects hardware
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install allin1 dependencies
RUN pip install --no-cache-dir \
    numpy \
    scipy \
    librosa \
    soundfile \
    cython

# Install madmom (works on Python 3.11)
RUN pip install --no-cache-dir madmom

# Install natten with CUDA support
# Falls back to CPU if no GPU available
RUN pip install --no-cache-dir natten -f https://shi-labs.com/natten/wheels/cu118/torch2.0.0/index.html || \
    pip install --no-cache-dir natten

# Install allin1
RUN pip install --no-cache-dir allin1

# Create directories for input/output
RUN mkdir -p /input /output

# Create entrypoint script that outputs JSON
RUN echo '#!/bin/bash\n\
if [ "$1" = "--json" ]; then\n\
    shift\n\
    python -c "\n\
import sys\n\
import json\n\
import allin1\n\
\n\
audio_path = sys.argv[1]\n\
result = allin1.analyze(audio_path)\n\
\n\
output = {\n\
    \"bpm\": float(result.bpm),\n\
    \"beats\": [float(b) for b in result.beats],\n\
    \"downbeats\": [float(d) for d in result.downbeats],\n\
    \"segments\": [\n\
        {\n\
            \"label\": s.label,\n\
            \"start\": float(s.start),\n\
            \"end\": float(s.end)\n\
        }\n\
        for s in result.segments\n\
    ]\n\
}\n\
print(json.dumps(output))\n\
" "$@"\n\
else\n\
    allin1 "$@"\n\
fi' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
