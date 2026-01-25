@plan.md @activity.md @epics/phase-1-foundation.md

# AbletonAIAnalysis Ralph Loop - Implementation Agent

You are implementing the **AbletonAIAnalysis** project - a music production analysis tool for Ableton Live. This is a Python project focused on analyzing .als files (Ableton projects) and providing health scores, issue detection, and recommendations.

## Context Files
- `plan.md` - Tasks with passes field (your work queue)
- `activity.md` - Recent progress log
- `epics/phase-1-foundation.md` - Detailed acceptance criteria

## Your Mission

1. **Read activity.md** to see what was recently accomplished
2. **Open plan.md** and find the single highest priority task where `passes` is `false`
3. **Implement that ONE task completely**:
   - Create/modify source files in `projects/music-analyzer/src/`
   - Write tests in `projects/music-analyzer/tests/`
   - Update CLI in `projects/music-analyzer/als_doctor.py` if needed
4. **Run tests** to verify your implementation works
5. **Update activity.md** with a dated progress entry describing what you changed
6. **Update plan.md** - set that task's `passes` from `false` to `true`
7. **Make one git commit** for that task only with a clear message

## Project Structure

```
AbletonAIAnalysis/
├── projects/
│   └── music-analyzer/
│       ├── src/
│       │   ├── als_parser.py          # Existing: Parses .als XML files
│       │   ├── config.py              # Existing: Configuration
│       │   ├── stem_analyzer.py       # Existing: Audio analysis
│       │   ├── reference_comparator.py # Existing: Compare to reference
│       │   ├── reporter.py            # Existing: Generate reports
│       │   ├── database.py            # TO CREATE: SQLite database layer
│       │   └── cli_formatter.py       # TO CREATE: Colored CLI output
│       ├── tests/
│       │   └── test_database.py       # TO CREATE: Database tests
│       └── als_doctor.py              # Main CLI entry point (create if missing)
├── data/
│   └── projects.db                    # TO CREATE: SQLite database
├── epics/                             # Implementation plans (read-only reference)
├── plan.md                            # Your task queue
├── activity.md                        # Your progress log
└── ralph.sh                           # This loop runner
```

## Implementation Guidelines

- **Python 3.10+** - Use type hints
- **SQLite** for database (no external DB required)
- **Click** or **argparse** for CLI
- **Rich** library for colored output (Phase 4.1)
- Follow existing code patterns in `projects/music-analyzer/src/`
- Keep implementations simple and focused
- Write tests for new functionality

## Important Rules

- **ONLY WORK ON ONE TASK** per iteration
- **Do NOT skip ahead** to other tasks
- **Do NOT refactor** code outside the current task
- **Make tests pass** before marking task complete
- **Update activity.md** with clear description of changes

## Completion Signal

When ALL tasks in plan.md have `"passes": true`, output:

```
<promise>COMPLETE</promise>
```

Otherwise, complete your one task and stop.
