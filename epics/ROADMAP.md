# AbletonAIAnalysis Roadmap

## Vision

Transform from an analysis tool into a **personalized AI mixing coach** that learns your style, tracks your progress, and tells you exactly what to work on next.

---

## Current State (Shipped)

### ALS Doctor v1.0
- Device chain extraction from .als files
- Health scoring (0-100) with letter grades
- Issue detection (clutter, wrong effects, chain order, duplicates, parameters)
- Version comparison
- Batch scanning with filters
- CLI interface (`als-doctor quick/diagnose/compare/scan`)

### Audio Analysis Pipeline
- Clipping, dynamics, frequency, stereo, loudness analysis
- Stem clash detection
- Reference track comparison
- AI stem separation (Spleeter)
- AI mastering (Matchering)
- HTML/JSON/text reports

### LLM Recommendation Prompts
- 17 specialist prompts for domain-specific advice
- Optional integration via workflows

---

## Roadmap Overview

```
PHASE 1: Foundation          PHASE 2: Intelligence
┌─────────────────────┐     ┌─────────────────────┐
│ SQLite Database     │     │ Change Tracking     │
│ Health History      │────▶│ Pattern Correlation │
│ Best Version Track  │     │ Style Profile       │
│ Library Queries     │     │ Smart Recommendations│
└─────────────────────┘     └─────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐
│ Watch Folder        │     │ CLI Colors          │
│ Coach Mode          │────▶│ HTML Reports        │
│ Scheduled Scans     │     │ Web Dashboard       │
│ OSC Integration     │     │ "What to Work On"   │
└─────────────────────┘     └─────────────────────┘
PHASE 3: Automation          PHASE 4: Visibility
```

---

## Phase 1: Foundation

**Goal:** Persistent storage for project data, enabling historical tracking.

**Status:** Not Started

| Story | Description | Effort | Status |
|-------|-------------|--------|--------|
| 1.1 | Initialize SQLite Database | Small | - |
| 1.2 | Persist Scan Results (`--save`) | Medium | - |
| 1.3 | List All Projects | Small | - |
| 1.4 | View Health History | Small | - |
| 1.5 | Find Best Version | Small | - |
| 1.6 | Library Status Summary | Medium | - |

**New Commands:**
```
als-doctor db init
als-doctor db list [--sort name|score|date]
als-doctor db history <song>
als-doctor db status
als-doctor best <song> [--open]
als-doctor scan <dir> --save
als-doctor diagnose <file> --save
```

**Deliverable:** Scan results persist across sessions. Query any project's history.

**Epic:** [phase-1-foundation.md](phase-1-foundation.md)

---

## Phase 2: Intelligence

**Goal:** Learn from your history to provide personalized recommendations.

**Status:** Not Started

| Story | Description | Effort | Status |
|-------|-------------|--------|--------|
| 2.1 | Track Changes Between Versions | Medium | - |
| 2.2 | Correlate Changes with Outcomes | Large | - |
| 2.3 | MIDI/Arrangement Analysis | Medium | - |
| 2.4 | Personal Style Profile | Large | - |
| 2.5 | Template Comparison | Medium | - |
| 2.6 | Smart Recommendations Engine | Large | - |

**New Commands:**
```
als-doctor db changes <song> [--from X --to Y]
als-doctor db insights
als-doctor db profile [--compare <file>]
als-doctor diagnose <file> --midi
als-doctor diagnose <file> --smart
als-doctor templates list|add
als-doctor compare-template <file> --template <T>
```

**Deliverable:** System learns what works for YOU and tailors recommendations.

**Epic:** [phase-2-intelligence.md](phase-2-intelligence.md)

---

## Phase 3: Automation

**Goal:** Reduce friction with auto-analysis, guided workflows, and Ableton integration.

**Status:** Not Started

| Story | Description | Effort | Risk | Status |
|-------|-------------|--------|------|--------|
| 3.1 | Watch Folder Auto-Analysis | Medium | Low | - |
| 3.2 | Guided Coach Mode | Medium | Low | - |
| 3.3 | Scheduled Batch Scans | Medium | Low | - |
| 3.4 | Pre-Export Checklist | Small | Low | - |
| 3.5 | AbletonOSC Integration | Large | High | - |
| 3.6 | Quick Actions via OSC | Large | High | - |

**New Commands:**
```
als-doctor watch <folder> [--quiet] [--notify]
als-doctor coach <file> [--auto-check N] [--live]
als-doctor schedule add|list|remove|run
als-doctor preflight <file> [--strict]
als-doctor osc connect|status|tracks|devices|fix
```

**Deliverable:** Hands-off operation. System watches, analyzes, and guides you.

**Epic:** [phase-3-automation.md](phase-3-automation.md)

---

## Phase 4: Visibility

**Goal:** Make data visible through enhanced CLI, reports, and web dashboard.

**Status:** Not Started

| Story | Description | Effort | Status |
|-------|-------------|--------|--------|
| 4.1 | CLI Colors & Formatting | Small | - |
| 4.2 | HTML Report Generation | Medium | - |
| 4.3 | Health Timeline Charts | Medium | - |
| 4.4 | Local Web Dashboard | Large | - |
| 4.5 | Side-by-Side Compare View | Medium | - |
| 4.6 | "What Should I Work On?" | Medium | - |
| 4.7 | Desktop Notifications | Small | - |

**New Commands:**
```
als-doctor [any] --no-color
als-doctor diagnose <file> --html
als-doctor db report <song> --html
als-doctor db report --all --html
als-doctor dashboard [--port N]
```

**Deliverable:** Beautiful, actionable visualizations. One-glance project status.

**Epic:** [phase-4-visibility.md](phase-4-visibility.md)

---

## Dependency Graph

```
Phase 1 (Foundation)
    │
    ├──────────────────────────┐
    ▼                          ▼
Phase 2 (Intelligence)    Phase 3 (Automation)
    │                          │
    ├──────────────────────────┤
    ▼                          ▼
Phase 4 (Visibility) ◄─────────┘
```

- **Phase 1** must complete first (data layer)
- **Phase 2** and **Phase 3** can run in parallel
- **Phase 4** benefits from all phases but can start after Phase 1

---

## Recommended Implementation Order

### Sprint 1: Foundation Core
- [ ] 1.1 DB Init
- [ ] 1.2 Persist Scan
- [ ] 4.1 CLI Colors (parallel, no deps)

### Sprint 2: Foundation Complete + Quick Wins
- [ ] 1.3 List Projects
- [ ] 1.4 Health History
- [ ] 1.5 Best Version
- [ ] 1.6 Library Status
- [ ] 3.4 Preflight Check (small, immediate value)

### Sprint 3: Intelligence Begins
- [ ] 2.1 Track Changes
- [ ] 2.3 MIDI Analysis (parallel)
- [ ] 2.5 Template Compare (parallel)

### Sprint 4: Automation Core
- [ ] 3.1 Watch Folder
- [ ] 3.2 Coach Mode
- [ ] 4.7 Notifications

### Sprint 5: Intelligence Deep
- [ ] 2.2 Correlate Outcomes
- [ ] 2.4 Style Profile
- [ ] 3.3 Scheduled Scans

### Sprint 6: Smart Features
- [ ] 2.6 Smart Recommendations
- [ ] 4.2 HTML Reports
- [ ] 4.3 Health Timeline

### Sprint 7: Dashboard
- [ ] 4.4 Web Dashboard
- [ ] 4.5 Compare View
- [ ] 4.6 "What to Work On"

### Sprint 8: Experimental (Optional)
- [ ] 3.5 OSC Connect
- [ ] 3.6 OSC Quick Actions

---

## Story Count Summary

| Phase | Stories | Small | Medium | Large | Total Effort |
|-------|---------|-------|--------|-------|--------------|
| 1. Foundation | 6 | 4 | 2 | 0 | ~1 week |
| 2. Intelligence | 6 | 0 | 3 | 3 | ~2-3 weeks |
| 3. Automation | 6 | 1 | 3 | 2 | ~2 weeks |
| 4. Visibility | 7 | 2 | 4 | 1 | ~2 weeks |
| **Total** | **25** | **7** | **12** | **6** | **~7-9 weeks** |

---

## Success Metrics

### Phase 1 Success
- Can query any project's health history
- Best version instantly identifiable
- No more re-scanning to see old results

### Phase 2 Success
- System identifies YOUR common mistakes
- Recommendations tailored to what works for YOU
- Style profile shows what makes your best work good

### Phase 3 Success
- Zero-friction analysis (watch folder just works)
- Coach mode guides you through fixes step-by-step
- Pre-export catches problems before wasted exports

### Phase 4 Success
- One glance shows what to work on today
- Health trends visible over time
- Shareable reports for feedback/collaboration

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| AbletonOSC breaks with Ableton updates | High | Medium | Keep OSC features experimental, fallback to file-based |
| Database grows too large | Medium | Low | Add cleanup commands, archive old data |
| Too many features, user overwhelm | Medium | Medium | Progressive disclosure, sensible defaults |
| Phase 2 needs lots of data to be useful | Medium | High | Show "insufficient data" messages, encourage scanning |

---

## Out of Scope (Future Considerations)

- Cloud sync / multi-machine support
- Collaboration features
- DAW plugins (VST/AU)
- Support for other DAWs (Logic, FL Studio)
- Mobile app
- AI-generated fix suggestions (beyond rules)

---

## Getting Started

1. Review epic documents for detailed acceptance criteria
2. Start with Phase 1, Story 1.1 (DB Init)
3. Use `als-doctor` commands to validate each story
4. Update this roadmap as stories complete

---

*Last Updated: January 2026*
