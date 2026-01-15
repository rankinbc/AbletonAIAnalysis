# Organizational Rules - AbletonAIAnalysis

## Project-Specific Rules

1. **Source Code**: All Python source code goes in `/projects/music-analyzer/src/`
2. **Song Inputs**: Songs for analysis go in `/inputs/<songname>/` (see Input Structure below)
3. **Analysis Output**: Generated reports go to `/reports/<songname>/`

## Input Structure

Songs ready for analysis use this standard structure:

```
/inputs/
  └── <songname>/
      ├── info.json                 # Optional: Song metadata
      ├── project.als               # Optional: Ableton project file
      ├── mix/                      # Mix versions (subfolders)
      │   ├── v1/
      │   │   └── mix.flac
      │   ├── v2/
      │   │   └── mix.flac
      │   └── ...
      ├── stems/                    # Individual track exports
      │   ├── kick.wav
      │   ├── bass.wav
      │   └── ...
      ├── midi/                     # Optional: MIDI files
      │   └── *.mid
      └── references/               # Optional: Reference tracks
          └── reference.wav
```

**Usage:**
```bash
python analyze.py --song MySong           # Analyzes latest version
python analyze.py --song MySong --version v1  # Analyzes specific version
```

## Output Organization

Reports are auto-generated with versioning:
```
/reports/
  └── <songname>/
      ├── <songname>_v1_analysis_2026-01-14.html
      ├── <songname>_v2_analysis_2026-01-15.html
      └── ...
```

This groups all reports for a song together and tracks mix version progress.

## File Naming Conventions

- **Source files**: `snake_case.py`
- **Analysis reports**: `<songname>_<version>_analysis_<date>.html`
- **Mix files**: `mix.flac` or `mix.wav` (inside version folder)
- **Stems**: Descriptive names like `kick.wav`, `bass.wav`, `lead_synth.wav`

## Module Structure

The project follows a modular architecture:

### Core Modules (`/projects/music-analyzer/src/`)
- `audio_analyzer.py` - Core audio analysis functions
- `stem_analyzer.py` - Multi-stem clash detection
- `als_parser.py` - Ableton .als file parsing
- `mastering.py` - Matchering integration
- `reporter.py` - Report generation
- `stem_separator.py` - Spleeter/Demucs-based stem separation
- `reference_storage.py` - Reference track library
- `reference_comparator.py` - Mix vs reference comparison
- `config.py` - Configuration loader and validation
- `genre_presets.py` - Genre-specific analysis presets

### Specialized Analyzers (`/projects/music-analyzer/src/analyzers/`)
- `harmonic_analyzer.py` - Key detection, chord analysis
- `clarity_analyzer.py` - Mix clarity and muddiness detection
- `spatial_analyzer.py` - Stereo field and spatial depth
- `overall_score.py` - Composite mix quality scoring

### Music Theory Utilities (`/projects/music-analyzer/src/music_theory/`)
- `key_relationships.py` - Key signature and chord relationships

## AI Recommendation System

The RecommendationGuide system provides specialized analysis prompts:

### Location: `/docs/ai/RecommendationGuide/`
- `RecommendationGuide.md` - Master prompt system and priority scoring
- `PIPELINE.md` - Analysis workflow specification
- `INDEX.md` - Index of available specialist prompts

### Specialist Prompts (`/docs/ai/RecommendationGuide/prompts/`)
20+ specialized analysis prompts covering:
- **Frequency**: LowEnd, FrequencyBalance, FrequencyCollisionDetection
- **Dynamics**: Dynamics, DynamicsHumanization, GainStaging
- **Stereo/Spatial**: StereoPhase, StereoFieldAudit, SpatialAnalysis
- **Arrangement**: Sections, SectionContrast, DensityBusyness, TranceArrangement
- **Harmonic**: ChordHarmony, HarmonicAnalysis
- **Quality**: Clarity, OverallScore, Loudness
- **Reference**: StemReference, DeviceChain
- **Playback**: PlaybackOptimization, SurroundCompatibility

## Reference Library

Location: `/projects/music-analyzer/reference_library/`
- `index.json` - Index of stored reference tracks
- `analytics/` - Cached analysis data for references (auto-generated)
