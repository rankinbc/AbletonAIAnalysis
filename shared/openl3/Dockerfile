# OpenL3 Docker Image
# Uses Python 3.11 to avoid compatibility issues with openl3/resampy on Python 3.13
#
# Build:
#   docker build -t openl3:latest .
#
# Run:
#   docker run --rm -v /path/to/audio:/input:ro openl3:latest /input/song.wav
#
# With specific options:
#   docker run --rm -v /path/to/audio:/input:ro openl3:latest \
#     --embedding-size 512 --content-type music /input/song.wav

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install TensorFlow and OpenL3
# Using CPU version to keep image smaller and more portable
RUN pip install --no-cache-dir \
    tensorflow>=2.0.0 \
    openl3>=0.4.0 \
    soundfile \
    numpy \
    scipy

# Create directories for input/output
RUN mkdir -p /input /output

# Create the embedding extraction script
COPY extract_embedding.py /app/extract_embedding.py

ENTRYPOINT ["python", "/app/extract_embedding.py"]
CMD ["--help"]
