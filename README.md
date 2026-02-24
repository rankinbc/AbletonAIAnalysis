# AbletonAIAnalysis

AI-powered music production analysis and coaching system for Ableton Live.

## Overview

AbletonAIAnalysis is a comprehensive toolkit for analyzing, comparing, and improving your music productions. It combines static analysis of Ableton projects with real-time control and AI-powered coaching.

### Key Features

- **Mix Analysis** - Analyze frequency balance, dynamics, stereo width, loudness
- **Stem Clash Detection** - Find frequency overlaps causing muddiness
- **Reference Comparison** - Compare your mix against professional tracks
- **ALS Doctor** - Analyze Ableton projects without exporting audio
- **MIDI Extraction** - Extract MIDI clips from ALS files, generate variations, export as .mid
- **AI Coaching Pipeline** - Real-time guidance with undo/redo and A/B comparison
- **Reference Library** - Build profiles from professional tracks

## Quick Start

### Analyze a Mix

```bash
cd projects/music-analyzer
python analyze.py --song MySong
```

### ALS Doctor (No Export Needed)

```bash
python als_doctor.py diagnose "path/to/project.als"
python als_doctor.py diagnose "project.als" --format json  # For Claude Code integration
```

### Real-Time Coaching with Ableton

1. Start OSC daemon:
   ```bash
   cd ableton-live-mcp-server
   python osc_daemon.py
   ```

2. Ask Claude for mixing help - it can now:
   - Adjust volumes, panning, sends
   - Modify effect parameters
   - Compare changes A/B
   - Undo any modifications

## Project Structure

```
AbletonAIAnalysis/
├── projects/
│   └── music-analyzer/          # Core analysis tools
│       ├── als_doctor.py        # ALS project analyzer
│       ├── analyze.py           # Mix/stem analyzer
│       └── src/
│           ├── live_control/    # AI Coaching Pipeline
│           │   ├── state.py     # Session state & undo
│           │   ├── resolver.py  # Device resolution
│           │   ├── conversions.py # Value conversions
│           │   ├── reference_integration.py
│           │   └── errors.py    # Error handling
│           └── als_json_output.py
├── ableton-live-mcp-server/     # MCP server for Ableton control
├── docs/
│   ├── human/                   # User documentation
│   ├── ai/                      # AI context docs
│   └── feature_docs/            # Feature specifications
├── inputs/                      # Song inputs for analysis
├── reports/                     # Generated analysis reports
└── references/                  # Reference tracks
```

## AI Coaching Pipeline

The coaching pipeline enables Claude Code to act as a mixing coach, providing real-time guidance while you work in Ableton.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                             │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Reference  │  │   Device     │  │   Session    │      │
│  │  Integration │  │   Resolver   │  │   State      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                 │               │
│         └─────────────────┼─────────────────┘               │
│                           │                                  │
│                    ┌──────┴──────┐                          │
│                    │  MCP Server │                          │
│                    └──────┬──────┘                          │
└───────────────────────────┼─────────────────────────────────┘
                            │
                    ┌───────┴───────┐
                    │  Ableton Live │
                    └───────────────┘
```

### Capabilities

| Component | Function |
|-----------|----------|
| **Session State** | Track all changes with full undo/redo support |
| **Device Resolver** | Map track/device names to MCP indices |
| **Value Conversions** | Convert Hz, dB, ms to normalized 0.0-1.0 |
| **Reference Integration** | Gap analysis against professional profiles |
| **A/B Comparison** | Toggle between original and modified states |
| **Error Handling** | Recovery suggestions and manual fallbacks |

### Example Coaching Session

```
User: "My bass sounds muddy compared to references"

Claude:
1. Analyzes your track against trance reference profile
2. Identifies: bass_energy +4.2dB above target, 200Hz buildup
3. Suggests: "Cut EQ Eight Band 2 on Bass track by 3dB"
4. Applies fix via MCP (with undo recorded)
5. Offers A/B comparison: "Toggle between A (original) and B (fixed)"
6. User keeps the fix or reverts
```

### Session Persistence

All changes persist across conversation restarts:
- Changes saved to `~/.claude_ableton_session.json`
- Undo/redo stacks preserved
- Song context maintained

## Documentation

| Document | Description |
|----------|-------------|
| [docs/human/README.md](docs/human/README.md) | Complete user guide |
| [projects/music-analyzer/src/live_control/README.md](projects/music-analyzer/src/live_control/README.md) | Coaching pipeline API |
| [projects/music-analyzer/src/live_control/TESTING.md](projects/music-analyzer/src/live_control/TESTING.md) | Testing checklist |
| [docs/feature_docs/README.md](docs/feature_docs/README.md) | ML implementation plan |
| [docs/ai/RecommendationGuide/](docs/ai/RecommendationGuide/) | Analysis prompts |

## Requirements

- Python 3.9+
- Ableton Live 11+ (for live control)
- AbletonOSC (for MCP integration)

### Installation

```bash
cd projects/music-analyzer
pip install -r requirements.txt
```

## License

MIT License
