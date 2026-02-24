"""
Production-Grade Melody Generation System

A sophisticated system for generating professional-quality melodies
that are chord-aware, context-aware, and musically intelligent.

Components:
- models: Core data structures (Chord, Note, Motif, Phrase, etc.)
- harmonic_engine: Chord parsing and harmonic analysis
- motif_engine: Motivic development and transformation
- phrase_builder: Phrase structure and contour planning
- coordinator: Inter-track coordination
- lead_generator: Main melody generator
- arp_generator: Chord-aware arpeggio generator
- humanizer: Expression and micro-timing

Usage:
    from melody_generation import LeadGenerator, ArpGenerator, TrackContext
    from melody_generation import parse_progression, create_motif_engine

    # Parse chord progression
    chords = parse_progression(["Am", "F", "C", "G"], key="A", scale="minor")

    # Create context
    context = TrackContext(chord_events=chords)

    # Generate lead
    lead_gen = LeadGenerator(key="A", scale="minor", genre="trance")
    melody = lead_gen.generate_for_section(
        section_type="drop",
        bars=16,
        energy=0.9,
        context=context,
    )

    # Generate arp
    arp_gen = ArpGenerator(key="A", scale="minor")
    arp = arp_gen.generate_for_section(
        section_type="drop",
        bars=16,
        energy=0.9,
        chord_events=chords,
    )

    # Humanize
    from melody_generation import humanize, GrooveStyle
    melody = humanize(melody, groove=GrooveStyle.TRANCE)
"""

__version__ = "1.0.0"

# Core models
from .models import (
    # Pitch & Note
    PitchClass,
    Pitch,
    NoteEvent,

    # Chords
    Chord,
    ChordQuality,
    ChordEvent,
    ChordTemplate,

    # Harmonic concepts
    HarmonicFunction,
    TensionLevel,

    # Motifs
    Motif,
    MotifInterval,
    MotifTransform,

    # Phrases
    PhraseSpec,
    PhraseType,
    CadenceType,
    ContourShape,
    Phrase,

    # Articulation
    ArticulationType,

    # Context
    TrackContext,
    MelodyGenConfig,
)

# Harmonic engine
from .harmonic_engine import (
    HarmonicEngine,
    ChordParser,
    HarmonicAnalysis,
    VoiceLeadingResult,
    parse_chord,
    parse_progression,
    get_scale_intervals,
    SCALE_INTERVALS,
)

# Motif engine
from .motif_engine import (
    MotifEngine,
    MotifTransformer,
    MotifMemory,
    create_motif_engine,
    develop_melody_motifs,
    TRANCE_MOTIFS,
    PROGRESSIVE_MOTIFS,
    TECHNO_MOTIFS,
)

# Phrase builder
from .phrase_builder import (
    PhraseBuilder,
    PhrasePlan,
    PhraseTemplate,
    ContourPlanner,
    CadencePlanner,
    create_phrase_builder,
    plan_section_phrases,
    PHRASE_TEMPLATES,
)

# Coordinator
from .coordinator import (
    InterTrackCoordinator,
    RhythmAnalyzer,
    RhythmPattern,
    CollisionDetector,
    Collision,
    MotionPlanner,
    MotionType,
    RhythmicRelation,
    create_coordinator,
    analyze_context,
    REGISTER_ALLOCATIONS,
)

# Lead generator
from .lead_generator import (
    LeadGenerator,
    GenerationContext,
    generate_lead,
)

# Arp generator
from .arp_generator import (
    ArpGenerator,
    ArpConfig,
    ArpDirection,
    ArpStyle,
    generate_arp,
    ARP_PATTERNS,
)

# Humanizer
from .humanizer import (
    Humanizer,
    HumanizeConfig,
    GrooveStyle,
    GrooveTemplate,
    VelocityCurve,
    ExpressionSuggester,
    ExpressionSuggestion,
    humanize,
    GROOVE_TEMPLATES,
)

# Integration
from .integration import (
    MIDIExporter,
    LegacyAdapter,
    LegacyMelodyNote,
    MelodyGenerationPipeline,
    GeneratedTrack,
    GenerationResult,
    generate_melody,
    generate_arp as generate_arp_track,
    HybridPipeline,
    HybridResult,
    ScoredCandidate,
)

# Tokenizer (Step 1.3)
from .tokenizer import (
    get_tokenizer,
    notes_to_midi,
    midi_to_notes,
    notes_to_tokens,
    tokens_to_notes,
    midi_to_tokens,
    tokens_to_midi,
    validate_roundtrip,
    train_bpe,
    save_tokenizer,
    load_tokenizer,
    RoundtripReport,
)

# Evaluation (Step 1.6)
from .evaluation import (
    evaluate_melody as evaluate_melody_metrics,
    evaluate_midi,
    evaluate_batch,
    compute_reference_stats,
    compare_baselines,
    save_baseline,
    load_baseline,
    print_metrics,
    MelodyMetrics,
    ReferenceStats,
    ComparisonReport,
    METRIC_WEIGHTS,
    TRANCE_TARGETS,
)

# ML Bridge (Steps 1.4 + 1.5) — lazy imports to avoid Docker dependency
# at module load time. Use: from melody_generation.ml_bridge import ...


# Convenience function to run all demos
def run_demos():
    """Run demos for all components."""
    print("\n" + "=" * 60)
    print("MELODY GENERATION SYSTEM DEMOS")
    print("=" * 60)

    from . import harmonic_engine
    from . import motif_engine
    from . import phrase_builder
    from . import coordinator
    from . import lead_generator
    from . import arp_generator
    from . import humanizer

    print("\n\n--- HARMONIC ENGINE ---")
    harmonic_engine.demo()

    print("\n\n--- MOTIF ENGINE ---")
    motif_engine.demo()

    print("\n\n--- PHRASE BUILDER ---")
    phrase_builder.demo()

    print("\n\n--- COORDINATOR ---")
    coordinator.demo()

    print("\n\n--- LEAD GENERATOR ---")
    lead_generator.demo()

    print("\n\n--- ARP GENERATOR ---")
    arp_generator.demo()

    print("\n\n--- HUMANIZER ---")
    humanizer.demo()

    print("\n" + "=" * 60)
    print("ALL DEMOS COMPLETE")
    print("=" * 60)


__all__ = [
    # Version
    "__version__",

    # Core models
    "PitchClass",
    "Pitch",
    "NoteEvent",
    "Chord",
    "ChordQuality",
    "ChordEvent",
    "ChordTemplate",
    "HarmonicFunction",
    "TensionLevel",
    "Motif",
    "MotifInterval",
    "MotifTransform",
    "PhraseSpec",
    "PhraseType",
    "CadenceType",
    "ContourShape",
    "Phrase",
    "ArticulationType",
    "TrackContext",
    "MelodyGenConfig",

    # Harmonic
    "HarmonicEngine",
    "ChordParser",
    "HarmonicAnalysis",
    "VoiceLeadingResult",
    "parse_chord",
    "parse_progression",
    "get_scale_intervals",
    "SCALE_INTERVALS",

    # Motif
    "MotifEngine",
    "MotifTransformer",
    "MotifMemory",
    "create_motif_engine",
    "develop_melody_motifs",
    "TRANCE_MOTIFS",
    "PROGRESSIVE_MOTIFS",
    "TECHNO_MOTIFS",

    # Phrase
    "PhraseBuilder",
    "PhrasePlan",
    "PhraseTemplate",
    "ContourPlanner",
    "CadencePlanner",
    "create_phrase_builder",
    "plan_section_phrases",
    "PHRASE_TEMPLATES",

    # Coordinator
    "InterTrackCoordinator",
    "RhythmAnalyzer",
    "RhythmPattern",
    "CollisionDetector",
    "Collision",
    "MotionPlanner",
    "MotionType",
    "RhythmicRelation",
    "create_coordinator",
    "analyze_context",
    "REGISTER_ALLOCATIONS",

    # Lead generator
    "LeadGenerator",
    "GenerationContext",
    "generate_lead",

    # Arp generator
    "ArpGenerator",
    "ArpConfig",
    "ArpDirection",
    "ArpStyle",
    "generate_arp",
    "ARP_PATTERNS",

    # Humanizer
    "Humanizer",
    "HumanizeConfig",
    "GrooveStyle",
    "GrooveTemplate",
    "VelocityCurve",
    "ExpressionSuggester",
    "ExpressionSuggestion",
    "humanize",
    "GROOVE_TEMPLATES",

    # Integration
    "MIDIExporter",
    "LegacyAdapter",
    "LegacyMelodyNote",
    "MelodyGenerationPipeline",
    "GeneratedTrack",
    "GenerationResult",
    "generate_melody",
    "generate_arp_track",
    "HybridPipeline",
    "HybridResult",
    "ScoredCandidate",

    # Tokenizer
    "get_tokenizer",
    "notes_to_midi",
    "midi_to_notes",
    "notes_to_tokens",
    "tokens_to_notes",
    "midi_to_tokens",
    "tokens_to_midi",
    "validate_roundtrip",
    "train_bpe",
    "save_tokenizer",
    "load_tokenizer",
    "RoundtripReport",

    # Evaluation
    "evaluate_melody_metrics",
    "evaluate_midi",
    "evaluate_batch",
    "compute_reference_stats",
    "compare_baselines",
    "save_baseline",
    "load_baseline",
    "print_metrics",
    "MelodyMetrics",
    "ReferenceStats",
    "ComparisonReport",
    "METRIC_WEIGHTS",
    "TRANCE_TARGETS",

    # Demo
    "run_demos",
]
