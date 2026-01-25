# Shared allin1 Docker Service

This module provides a Docker-based wrapper for the [allin1](https://github.com/CPJKU/allin1) music structure analyzer, solving Python 3.13 compatibility issues with madmom/natten dependencies.

## Features

- **Docker isolation**: Runs allin1 in Python 3.11 container, compatible with your Python 3.13 environment
- **GPU support**: CUDA 11.8 enabled for faster analysis
- **Optional caching**: File-hash based caching for batch processing
- **Shared across projects**: Used by both music-analyzer and youtube-reference-track-analysis

## Quick Start

### 1. Build the Docker Image

```bash
cd AbletonAIAnalysis/shared/allin1
docker build -t allin1:latest .
```

First build takes 5-10 minutes (downloads PyTorch, natten, etc.).

### 2. Test the Image

```bash
# Check it works
docker run --rm allin1:latest --help

# Analyze a file (JSON output)
docker run --rm -v /path/to/audio:/input:ro allin1:latest --json /input/song.wav
```

### 3. Use from Python

```python
from shared.allin1 import DockerAllin1

# Without caching (music-analyzer style)
analyzer = DockerAllin1()
result = analyzer.analyze("song.wav")
print(f"BPM: {result.bpm}")
print(f"Sections: {len(result.segments)}")

# With caching (youtube-analyzer style)
analyzer = DockerAllin1(
    enable_cache=True,
    cache_dir=Path("~/.cache/allin1")
)
result = analyzer.analyze("song.wav")  # Cached on second run
```

## GPU Support

The Dockerfile includes CUDA 11.8 support. To use GPU:

```python
analyzer = DockerAllin1(use_gpu=True)
```

Or via command line:

```bash
docker run --rm --gpus all -v /path/to/audio:/input:ro allin1:latest --json /input/song.wav
```

Requires nvidia-docker to be installed.

## Project Integration

### music-analyzer

```python
# In structure_detector.py
# Automatically uses Docker allin1 if available, no caching
from shared.allin1 import DockerAllin1
analyzer = DockerAllin1(enable_cache=False)
```

### youtube-reference-track-analysis

```python
# In section_detector.py
# Uses Docker allin1 with caching for batch processing
from shared.allin1 import DockerAllin1
analyzer = DockerAllin1(
    enable_cache=True,
    cache_dir=Path.home() / ".cache" / "allin1",
    use_gpu=True
)
```

## API Reference

### DockerAllin1

```python
class DockerAllin1:
    def __init__(
        self,
        image_name: str = "allin1:latest",
        enable_cache: bool = False,
        cache_dir: Optional[Path] = None,
        use_gpu: bool = False
    ): ...

    def analyze(self, audio_path: Path, timeout: int = 300) -> Optional[Allin1Result]: ...
    def analyze_batch(self, audio_paths: List[Path]) -> List[Optional[Allin1Result]]: ...
    def cache_stats(self) -> Optional[dict]: ...
    def clear_cache(self) -> int: ...
```

### Allin1Result

```python
@dataclass
class Allin1Result:
    bpm: float
    beats: List[float]       # Beat times in seconds
    downbeats: List[float]   # Downbeat times in seconds
    segments: List[Allin1Segment]

@dataclass
class Allin1Segment:
    label: str    # intro, verse, chorus, bridge, outro, etc.
    start: float  # Start time in seconds
    end: float    # End time in seconds
```

## Cache Management

```python
analyzer = DockerAllin1(enable_cache=True)

# Check cache stats
stats = analyzer.cache_stats()
print(f"Cached: {stats['count']} files, {stats['size_bytes']} bytes")

# Clear cache
cleared = analyzer.clear_cache()
print(f"Cleared {cleared} cache entries")
```

Cache location: `~/.cache/allin1/` (configurable)

## Troubleshooting

### "Docker not found"

Install Docker Desktop: https://www.docker.com/products/docker-desktop

### "allin1 Docker image not found"

Build the image:
```bash
cd AbletonAIAnalysis/shared/allin1
docker build -t allin1:latest .
```

### "Analysis timed out"

Increase timeout:
```python
result = analyzer.analyze("song.wav", timeout=600)  # 10 minutes
```

### "GPU not working"

1. Install nvidia-docker: https://github.com/NVIDIA/nvidia-docker
2. Verify: `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`

## Performance

| Mode | Speed (per 5-min track) |
|------|-------------------------|
| CPU | ~60-90 seconds |
| GPU | ~10-15 seconds |
| Cached | <1 second |

## Files

```
shared/allin1/
├── __init__.py       # Module exports
├── docker_allin1.py  # Docker wrapper with caching
├── cache.py          # File-hash based cache
├── Dockerfile        # GPU-enabled Docker image
├── docker-compose.yml
└── README.md         # This file
```
