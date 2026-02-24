#!/usr/bin/env python3
"""
Ableton AI Analysis - Music Production Analysis Tool

CLI tool for analyzing Ableton 11 projects and audio files.

Usage:
    python analyze.py --audio mix.wav
    python analyze.py --stems ./stems/
    python analyze.py --als project.als --stems ./stems/
    python analyze.py --audio mix.wav --reference ref.wav --master
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

import click
from colorama import init, Fore, Style
from tqdm import tqdm

# Initialize colorama for Windows support
init()

# Import our modules
from audio_analyzer import AudioAnalyzer
from stem_analyzer import StemAnalyzer
from als_parser import ALSParser
from mastering import MasteringEngine
from reporter import ReportGenerator
from stem_separator import StemSeparator
from reference_comparator import ReferenceComparator
from reference_storage import ReferenceStorage
from reference_analyzer import ReferenceAnalyzer
from config import load_config, get_config


def print_header():
    """Print the application header."""
    print(f"""
{Fore.CYAN}================================================================
         {Fore.WHITE}ABLETON AI ANALYSIS{Fore.CYAN}
         {Fore.YELLOW}Music Production Analysis Tool{Fore.CYAN}
================================================================{Style.RESET_ALL}
""")


def print_section(title: str):
    """Print a section header."""
    print(f"\n{Fore.GREEN}>> {title}{Style.RESET_ALL}")
    print("-" * 50)


def print_issue(severity: str, message: str):
    """Print an issue with appropriate formatting."""
    if severity == 'critical':
        print(f"  {Fore.RED}[X] CRITICAL: {message}{Style.RESET_ALL}")
    elif severity == 'warning':
        print(f"  {Fore.YELLOW}[!] Warning: {message}{Style.RESET_ALL}")
    else:
        print(f"  {Fore.BLUE}[i] Info: {message}{Style.RESET_ALL}")


def print_recommendation(num: int, text: str):
    """Print a numbered recommendation."""
    print(f"  {Fore.GREEN}{num}.{Style.RESET_ALL} {text}")


@click.command()
@click.option('--audio', '-a', type=click.Path(exists=True),
              help='Path to audio file (WAV/FLAC) to analyze')
@click.option('--stems', '-s', type=click.Path(exists=True),
              help='Path to directory containing stem files')
@click.option('--als', type=click.Path(exists=True),
              help='Path to Ableton .als project file')
@click.option('--reference', '-r', type=click.Path(exists=True),
              help='Reference track for mastering comparison')
@click.option('--master', '-m', is_flag=True,
              help='Apply AI mastering to the audio file')
@click.option('--output', '-o', default='./reports',
              help='Output directory for reports and mastered files')
@click.option('--format', 'output_format', type=click.Choice(['html', 'text', 'json']),
              default='html', help='Report output format')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose output')
@click.option('--separate', type=click.Path(exists=True),
              help='Separate audio file into stems (vocals, drums, bass, other)')
@click.option('--compare-ref', 'compare_ref', type=click.Path(exists=True),
              help='Compare mix against reference track stem-by-stem')
@click.option('--analyze-reference', 'analyze_reference', type=click.Path(exists=True),
              help='Standalone analysis of a reference track (structure, sections, production targets)')
@click.option('--deep', 'deep_analysis', is_flag=True,
              help='Include stem separation in reference analysis (slower but more detailed)')
@click.option('--add-reference', 'add_reference', type=click.Path(exists=True),
              help='Add a track to the reference library')
@click.option('--reference-id', 'reference_id', type=str,
              help='Use stored reference by ID (faster than file comparison)')
@click.option('--list-references', 'list_references', is_flag=True,
              help='List all stored reference tracks')
@click.option('--genre', type=str,
              help='Genre tag when adding reference (e.g., trance, house)')
@click.option('--tags', type=str,
              help='Comma-separated tags when adding reference')
@click.option('--config', 'config_path', type=click.Path(exists=True),
              help='Path to custom config.yaml file')
@click.option('--no-sections', 'no_sections', is_flag=True,
              help='Skip section/timeline analysis')
@click.option('--no-stems', 'no_stems', is_flag=True,
              help='Skip stem analysis even if stems provided')
@click.option('--no-midi', 'no_midi', is_flag=True,
              help='Skip MIDI analysis from ALS file')
@click.option('--ai-recommend', 'ai_recommend', is_flag=True,
              help='After analysis, launch Claude with recommendations (requires claude CLI)')
@click.option('--genre-preset', 'genre_preset', type=click.Choice(['trance', 'house', 'techno', 'dnb', 'progressive']),
              help='Use genre-specific target values for analysis')
@click.option('--trance-score', 'trance_score', is_flag=True,
              help='Compute trance DNA score (tempo, pumping, energy, supersaw, 303, etc.)')
@click.option('--arrangement-score', 'arrangement_score', is_flag=True,
              help='Score arrangement structure against trance conventions (section lengths, 8-bar rule, energy contrast)')
@click.option('--gap-analysis', 'gap_analysis', type=click.Path(exists=True),
              help='Compare audio against a reference profile (JSON) and show production gaps')
@click.option('--prescriptive', 'prescriptive_fixes', is_flag=True,
              help='Generate detailed prescriptive fixes with OSC commands (use with --gap-analysis)')
@click.option('--build-embeddings', 'build_embeddings', type=click.Path(exists=True),
              help='Build similarity index from reference audio directory')
@click.option('--embedding-output', 'embedding_output', type=click.Path(),
              help='Output path for embeddings index (default: ./embeddings_index/)')
@click.option('--find-similar', 'find_similar', type=click.Path(exists=True),
              help='Find tracks similar to this audio file')
@click.option('--embedding-index', 'embedding_index', type=click.Path(exists=True),
              help='Path to embeddings index for similarity search')
@click.option('--top', 'top_k', type=int, default=5,
              help='Number of similar tracks to return (default: 5)')
@click.option('--collect-feedback', 'collect_feedback', is_flag=True,
              help='Collect user feedback on fixes during gap analysis (enables continuous learning)')
@click.option('--learning-stats', 'learning_stats', is_flag=True,
              help='Show learning statistics from collected feedback')
@click.option('--tune-profile', 'tune_profile', type=click.Path(exists=True),
              help='Apply learned adjustments to a reference profile')
@click.option('--tuned-output', 'tuned_output', type=click.Path(),
              help='Output path for tuned profile (default: <profile>_tuned.json)')
@click.option('--reset-learning', 'reset_learning', is_flag=True,
              help='Reset all learning data (use with caution)')
@click.option('--learning-db', 'learning_db_path', type=click.Path(),
              default='learning_data.db',
              help='Path to learning database (default: learning_data.db)')
def main(audio, stems, als, reference, master, output, output_format, verbose,
         separate, compare_ref, analyze_reference, deep_analysis, add_reference, reference_id, list_references, genre, tags,
         config_path, no_sections, no_stems, no_midi, ai_recommend, genre_preset, trance_score, arrangement_score, gap_analysis,
         prescriptive_fixes, build_embeddings, embedding_output, find_similar, embedding_index, top_k,
         collect_feedback, learning_stats, tune_profile, tuned_output, reset_learning, learning_db_path):
    """
    Analyze Ableton projects and audio files for mixing issues.

    Examples:

    \b
    Analyze a single mixdown:
        python analyze.py --audio my_mix.wav

    \b
    Analyze stems for frequency clashes:
        python analyze.py --stems ./exported_stems/

    \b
    Full analysis with project file:
        python analyze.py --als my_song.als --stems ./stems/ --audio my_mix.wav

    \b
    Analyze and master:
        python analyze.py --audio my_mix.wav --reference pro_track.wav --master

    \b
    Separate a mix into stems:
        python analyze.py --separate my_mix.wav

    \b
    Compare your mix against a reference track:
        python analyze.py --audio my_mix.wav --compare-ref pro_track.wav

    \b
    Add a reference track to library:
        python analyze.py --add-reference pro_track.wav --genre trance --tags "anthem,uplifting"

    \b
    List stored reference tracks:
        python analyze.py --list-references

    \b
    Standalone reference track analysis (get production targets):
        python analyze.py --analyze-reference pro_track.wav
        python analyze.py --analyze-reference pro_track.wav --deep

    \b
    Compute trance DNA score (sidechain, supersaw, 303, energy, etc.):
        python analyze.py --audio my_mix.wav --trance-score

    \b
    Score arrangement structure against trance conventions:
        python analyze.py --audio my_mix.wav --arrangement-score

    \b
    Compare WIP against reference profile (gap analysis):
        python analyze.py --audio my_mix.wav --gap-analysis trance_profile.json

    \b
    Gap analysis with prescriptive fixes (detailed actionable recommendations):
        python analyze.py --audio my_mix.wav --gap-analysis profile.json --prescriptive
        python analyze.py --audio my_mix.wav --als project.als --gap-analysis profile.json --prescriptive

    \b
    Build embeddings index for similarity search:
        python analyze.py --build-embeddings ./references/ --embedding-output ./my_index/

    \b
    Find similar tracks using embeddings:
        python analyze.py --find-similar my_track.wav --embedding-index ./my_index/ --top 5

    \b
    Continuous learning - collect feedback on fixes:
        python analyze.py --audio my_mix.wav --gap-analysis profile.json --prescriptive --collect-feedback

    \b
    View learning statistics:
        python analyze.py --learning-stats

    \b
    Apply learned adjustments to a profile:
        python analyze.py --tune-profile profile.json --tuned-output tuned_profile.json

    \b
    Reset learning data:
        python analyze.py --reset-learning
    """
    print_header()

    # Load configuration
    cfg = load_config(config_path)

    # Apply CLI overrides to stage config
    if no_sections:
        cfg._config['stages']['section_analysis'] = False
    if no_stems:
        cfg._config['stages']['stem_analysis'] = False
    if no_midi:
        cfg._config['stages']['midi_humanization'] = False
        cfg._config['stages']['midi_quantization'] = False
        cfg._config['stages']['midi_chord_detection'] = False

    if verbose:
        print(f"{Fore.CYAN}Configuration loaded{Style.RESET_ALL}")
        if config_path:
            print(f"  Config file: {config_path}")
        disabled = [k for k, v in cfg.stages.items() if not v]
        if disabled:
            print(f"  Disabled stages: {', '.join(disabled)}")
        print()

    # Handle --reset-learning
    if reset_learning:
        print_section("Reset Learning Data")
        try:
            from learning import LearningDatabase
            print(f"  {Fore.YELLOW}WARNING: This will delete all learning data!{Style.RESET_ALL}")
            print(f"  Database: {learning_db_path}")
            confirm = input("  Type 'yes' to confirm: ").strip().lower()
            if confirm == 'yes':
                db = LearningDatabase(learning_db_path)
                db.reset()
                print(f"  {Fore.GREEN}[OK] Learning data reset{Style.RESET_ALL}")
            else:
                print(f"  {Fore.YELLOW}Cancelled{Style.RESET_ALL}")
        except ImportError as e:
            print(f"  {Fore.RED}[ERROR] Learning module not available: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Reset failed: {e}{Style.RESET_ALL}")
        return

    # Handle --learning-stats
    if learning_stats:
        print_section("Learning Statistics")
        try:
            from learning import LearningDatabase, EffectivenessTracker, ProfileTuner
            from learning.effectiveness_tracker import format_effectiveness_report

            db = LearningDatabase(learning_db_path)
            tracker = EffectivenessTracker(db=db, verbose=verbose)

            # Get effectiveness report
            report = tracker.get_feature_effectiveness_report()

            # Print formatted report
            print(format_effectiveness_report(report))

            # Also show tuning recommendations if there's enough data
            summary = db.get_summary_stats()
            if summary.get('session_count', 0) >= 3:
                tuner = ProfileTuner(db=db, verbose=verbose)
                learning_report = tuner.export_learning_report()
                print(learning_report)

        except ImportError as e:
            print(f"  {Fore.RED}[ERROR] Learning module not available: {e}{Style.RESET_ALL}")
            print(f"  Make sure the learning module is installed.")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Failed to get learning stats: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()
        return

    # Handle --tune-profile
    if tune_profile:
        print_section("Profile Tuning")
        try:
            from learning import LearningDatabase, ProfileTuner
            from learning.profile_tuner import format_tuning_report
            from profiling import ReferenceProfile

            db = LearningDatabase(learning_db_path)
            tuner = ProfileTuner(db=db, verbose=verbose)

            print(f"  Loading profile: {Path(tune_profile).name}")
            profile = ReferenceProfile.load(tune_profile)

            # Generate tuning report
            report = tuner.suggest_profile_updates(profile)

            # Print recommendations
            print(format_tuning_report(report))

            # Determine output path
            if tuned_output:
                output_path = tuned_output
            else:
                stem = Path(tune_profile).stem
                output_path = str(Path(tune_profile).parent / f"{stem}_tuned.json")

            # Ask for confirmation
            print(f"\n  Output: {output_path}")
            confirm = input("  Apply tuning? [y/N]: ").strip().lower()
            if confirm in ('y', 'yes'):
                tuner.save_tuned_profile(
                    profile,
                    output_path,
                    apply_weights=True,
                    apply_confidence=True,
                    apply_ranges=False  # Conservative by default
                )
                print(f"  {Fore.GREEN}[OK] Tuned profile saved to: {output_path}{Style.RESET_ALL}")
            else:
                print(f"  {Fore.YELLOW}Cancelled{Style.RESET_ALL}")

        except ImportError as e:
            print(f"  {Fore.RED}[ERROR] Learning module not available: {e}{Style.RESET_ALL}")
        except FileNotFoundError as e:
            print(f"  {Fore.RED}[ERROR] Profile not found: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Profile tuning failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()
        return

    # Handle list-references first (doesn't need other inputs)
    if list_references:
        print_section("Reference Library")
        storage = ReferenceStorage(verbose=verbose)
        refs = storage.list_references()

        if not refs:
            print(f"  {Fore.YELLOW}No reference tracks in library{Style.RESET_ALL}")
            print(f"  Add with: python analyze.py --add-reference track.wav --genre trance")
        else:
            print(f"  Found {len(refs)} reference track(s):\n")
            for ref in refs:
                genre_str = f" [{ref.genre}]" if ref.genre else ""
                tempo_str = f" {ref.tempo_bpm:.0f}BPM" if ref.tempo_bpm else ""
                tags_str = f" tags: {', '.join(ref.tags)}" if ref.tags else ""
                print(f"  {Fore.CYAN}{ref.track_id}{Style.RESET_ALL}: {ref.file_name}{genre_str}{tempo_str}")
                if tags_str:
                    print(f"      {tags_str}")

            # Print stats
            stats = storage.get_library_stats()
            print(f"\n  {Fore.GREEN}Library Stats:{Style.RESET_ALL}")
            print(f"    Tracks: {stats['track_count']}")
            if stats['genres']:
                print(f"    Genres: {', '.join(f'{k}({v})' for k, v in stats['genres'].items())}")
            if stats['tempo_range']:
                print(f"    Tempo Range: {stats['tempo_range'][0]:.0f}-{stats['tempo_range'][1]:.0f} BPM")
        return

    # Handle add-reference
    if add_reference:
        print_section("Adding Reference Track")
        storage = ReferenceStorage(verbose=verbose)

        metadata = {}
        if genre:
            metadata['genre'] = genre
        if tags:
            metadata['tags'] = [t.strip() for t in tags.split(',')]

        try:
            print(f"  Adding: {Path(add_reference).name}")
            analytics = storage.add_reference(add_reference, metadata=metadata)

            print(f"\n  {Fore.GREEN}[OK] Reference added successfully{Style.RESET_ALL}")
            print(f"  ID: {analytics.metadata.track_id}")
            print(f"  Tempo: {analytics.metadata.tempo_bpm:.1f} BPM" if analytics.metadata.tempo_bpm else "")
            print(f"  Duration: {analytics.metadata.duration_seconds:.1f}s")
            print(f"\n  Use with: python analyze.py --audio mix.wav --reference-id {analytics.metadata.track_id}")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] {e}{Style.RESET_ALL}")
        return

    # Handle --analyze-reference (standalone reference analysis)
    if analyze_reference:
        print_section("Standalone Reference Analysis")
        try:
            analyzer = ReferenceAnalyzer(
                include_stems=deep_analysis,
                verbose=verbose,
                config=cfg
            )

            print(f"  Analyzing: {Path(analyze_reference).name}")
            if deep_analysis:
                print(f"  Mode: Deep analysis (with stem separation)")
            else:
                print(f"  Mode: Quick analysis (structure + sections)")
            print()

            def ref_progress_cb(progress):
                stage_msgs = {
                    'structure': 'Detecting song structure...',
                    'global': 'Computing global metrics...',
                    'sections': 'Analyzing sections...',
                    'stems': 'Separating and analyzing stems...',
                    'targets': 'Generating production targets...',
                    'summary': 'Creating summary...',
                    'complete': 'Analysis complete!'
                }
                msg = stage_msgs.get(progress.stage, progress.message)
                print(f"  [{progress.progress_pct:3.0f}%] {msg}")

            result = analyzer.analyze(analyze_reference, progress_callback=ref_progress_cb)

            if result.success:
                # Display results
                print(f"\n  {Fore.CYAN}=== TRACK OVERVIEW ==={Style.RESET_ALL}")
                print(f"  Duration: {result.duration_seconds/60:.1f} min | Tempo: {result.tempo_bpm:.0f} BPM | Key: {result.key or 'Unknown'}")
                print(f"  LUFS: {result.integrated_lufs:.1f} | Dynamic Range: {result.dynamic_range_db:.1f} dB")

                print(f"\n  {Fore.CYAN}=== SONG STRUCTURE ==={Style.RESET_ALL}")
                print(f"  Method: {result.structure.detection_method} (confidence: {result.structure.confidence:.0%})")
                print(f"  Sections: {result.section_count} | Bars: {result.structure.total_bars}")
                print()

                # Section table
                print(f"  {'#':<3} {'Section':<12} {'Time':<12} {'Bars':<6} {'RMS (dB)':<10} {'vs Avg':<8}")
                print(f"  {'-'*3} {'-'*12} {'-'*12} {'-'*6} {'-'*10} {'-'*8}")
                for i, sm in enumerate(result.section_metrics, 1):
                    vs_avg = f"{sm.loudness_vs_average_db:+.1f}" if sm.loudness_vs_average_db else "REF"
                    print(f"  {i:<3} {sm.section_type:<12} {sm.start_time/60:.0f}:{sm.start_time%60:04.1f}-{sm.end_time/60:.0f}:{sm.end_time%60:04.1f}  {sm.duration_bars:<6} {sm.rms_db:<10.1f} {vs_avg:<8}")

                # Production targets
                print(f"\n  {Fore.CYAN}=== PRODUCTION TARGETS ==={Style.RESET_ALL}")
                for stype, targets in result.production_targets.by_section_type.items():
                    print(f"\n  {Fore.WHITE}{stype.upper()}:{Style.RESET_ALL}")
                    print(f"    Target RMS: {targets['target_rms_db']:.0f} dB")
                    print(f"    Target Width: {targets['target_stereo_width_pct']:.0f}%")
                    print(f"    Has Kick: {'Yes' if targets['has_kick'] else 'No'}")

                if result.production_targets.contrasts:
                    print(f"\n  {Fore.WHITE}CONTRASTS:{Style.RESET_ALL}")
                    for key, value in result.production_targets.contrasts.items():
                        label = key.replace('_', ' ').title()
                        print(f"    {label}: {value:+.1f}")

                # AI summary
                print(f"\n  {Fore.CYAN}=== KEY INSIGHTS ==={Style.RESET_ALL}")
                print(f"  {result.ai_summary.get('track_character', '')}")
                print()
                for insight in result.ai_summary.get('actionable_insights', []):
                    print(f"  {Fore.GREEN}>{Style.RESET_ALL} {insight}")

                # Save JSON
                from datetime import datetime
                output_dir = Path(output)
                output_dir.mkdir(parents=True, exist_ok=True)
                json_filename = f"reference_analysis_{Path(analyze_reference).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                json_path = output_dir / json_filename
                result.save(str(json_path))
                print(f"\n  {Fore.GREEN}[OK] Full analysis saved to: {json_path}{Style.RESET_ALL}")

            else:
                print(f"  {Fore.RED}[ERROR] {result.error_message}{Style.RESET_ALL}")

        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Reference analysis failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()
        return

    # Handle --trance-score (standalone trance DNA analysis)
    if trance_score and audio:
        print_section("Trance DNA Analysis")
        try:
            from feature_extraction import extract_all_trance_features, TranceScoreCalculator
            from feature_extraction.trance_features import format_trance_features_report

            print(f"  Analyzing: {Path(audio).name}")
            print(f"  Computing trance-specific features...")
            print()

            features = extract_all_trance_features(audio, verbose=verbose)

            # Print formatted report
            report = format_trance_features_report(features)
            for line in report.split('\n'):
                print(f"  {line}")

            # Get improvement suggestions
            scorer = TranceScoreCalculator()
            from feature_extraction.trance_scorer import TranceScoreBreakdown
            breakdown = TranceScoreBreakdown(**features.trance_score_breakdown)
            suggestions = scorer.get_improvement_suggestions(breakdown)

            if suggestions:
                print(f"\n  {Fore.YELLOW}IMPROVEMENT SUGGESTIONS:{Style.RESET_ALL}")
                for i, suggestion in enumerate(suggestions, 1):
                    print(f"  {i}. {suggestion}")

            # Save JSON output
            from datetime import datetime
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)
            json_filename = f"trance_score_{Path(audio).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            json_path = output_dir / json_filename

            import json
            with open(json_path, 'w') as f:
                json.dump(features.to_dict(), f, indent=2, default=str)
            print(f"\n  {Fore.GREEN}[OK] Analysis saved to: {json_path}{Style.RESET_ALL}")

        except ImportError as e:
            print(f"  {Fore.RED}[ERROR] Trance feature extraction module not available: {e}{Style.RESET_ALL}")
            print(f"  Make sure all dependencies are installed (librosa, scipy, numpy)")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Trance analysis failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()
        return

    # Handle --arrangement-score (standalone arrangement structure analysis)
    if arrangement_score and audio:
        print_section("Arrangement Analysis")
        try:
            from src.structure_detector import StructureDetector
            from src.arrangement_scorer import ArrangementScorer, IssueSeverity

            print(f"  Analyzing: {Path(audio).name}")
            print(f"  Detecting song structure...")
            print()

            # Detect structure
            detector = StructureDetector(verbose=verbose)
            structure = detector.detect(audio)

            if not structure.success:
                print(f"  {Fore.RED}[ERROR] Structure detection failed: {structure.error_message}{Style.RESET_ALL}")
                return

            # Score arrangement
            scorer = ArrangementScorer(config=cfg)
            score = scorer.score(structure)

            # Print results
            print(f"  {Fore.CYAN}ARRANGEMENT SCORE: {score.overall_score:.0f}/100 ({score.grade}){Style.RESET_ALL}")
            print(f"  Sections: {score.section_count} | Bars: {score.total_bars} | Tempo: {score.detected_tempo:.0f} BPM")
            print()

            # Section map
            print(f"  {Fore.WHITE}Section Map:{Style.RESET_ALL}")
            for sec in score.section_scores:
                status = "OK" if sec.length_score >= 70 else "WARN" if sec.length_score >= 50 else "ISSUE"
                color = Fore.GREEN if status == "OK" else Fore.YELLOW if status == "WARN" else Fore.RED
                eight_bar_mark = "" if sec.eight_bar_compliant else f" {Fore.YELLOW}(not /8){Style.RESET_ALL}"
                print(f"    [{sec.time_range_formatted}] {sec.section_type.title():12} | {sec.duration_bars:3} bars | Score: {sec.length_score:.0f}{eight_bar_mark}")
            print()

            # Component breakdown
            print(f"  {Fore.WHITE}Component Scores:{Style.RESET_ALL}")
            for component, value in score.component_scores.items():
                status = "OK" if value >= 70 else "WARN" if value >= 50 else "ISSUE"
                color = Fore.GREEN if status == "OK" else Fore.YELLOW if status == "WARN" else Fore.RED
                print(f"    [{color}{status:5}{Style.RESET_ALL}] {component.replace('_', ' ').title():20}: {value:.0f}/100")
            print()

            # Issues
            if score.issues:
                print(f"  {Fore.WHITE}Issues:{Style.RESET_ALL}")
                for issue in score.issues:
                    if issue.severity == IssueSeverity.CRITICAL:
                        color = Fore.RED
                    elif issue.severity == IssueSeverity.WARNING:
                        color = Fore.YELLOW
                    else:
                        color = Fore.CYAN
                    print(f"    [{color}{issue.severity.value}{Style.RESET_ALL}] {issue.message}")
                    print(f"           {Fore.WHITE}Fix:{Style.RESET_ALL} {issue.fix}")
                print()

            # Suggestions
            if score.suggestions:
                print(f"  {Fore.WHITE}Suggestions:{Style.RESET_ALL}")
                for i, suggestion in enumerate(score.suggestions, 1):
                    print(f"    {i}. {suggestion}")
                print()

            # Save JSON output
            from datetime import datetime
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)
            json_filename = f"arrangement_score_{Path(audio).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            json_path = output_dir / json_filename

            import json
            with open(json_path, 'w') as f:
                json.dump(score.to_dict(), f, indent=2, default=str)
            print(f"  {Fore.GREEN}[OK] Analysis saved to: {json_path}{Style.RESET_ALL}")

        except ImportError as e:
            print(f"  {Fore.RED}[ERROR] Arrangement scoring module not available: {e}{Style.RESET_ALL}")
            print(f"  Make sure structure_detector.py and arrangement_scorer.py are present")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Arrangement analysis failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()
        return

    # Handle --build-embeddings (build similarity index)
    if build_embeddings:
        print_section("Building Embeddings Index")
        try:
            from embeddings import OpenL3Extractor, SimilarityIndex
            from embeddings.openl3_extractor import get_extractor

            refs_dir = Path(build_embeddings)
            output_dir = Path(embedding_output) if embedding_output else Path('./embeddings_index')

            print(f"  Source: {refs_dir}")
            print(f"  Output: {output_dir}")
            print()

            # Find audio files
            audio_files = []
            for ext in ['*.wav', '*.flac', '*.mp3', '*.WAV', '*.FLAC', '*.MP3']:
                audio_files.extend(refs_dir.glob(f'**/{ext}'))

            if not audio_files:
                print(f"  {Fore.YELLOW}No audio files found in {refs_dir}{Style.RESET_ALL}")
                return

            print(f"  Found {len(audio_files)} audio files")
            print()

            # Initialize extractor and index
            print(f"  Initializing OpenL3 extractor...")
            extractor = get_extractor(content_type="music", embedding_size=512, verbose=verbose)

            index = SimilarityIndex(dimension=512, index_type="flat")

            # Extract embeddings with progress
            print(f"  Extracting embeddings...")
            for i, audio_path in enumerate(audio_files):
                print(f"  [{i+1}/{len(audio_files)}] {audio_path.name}")
                try:
                    result = extractor.extract(str(audio_path))
                    track_id = audio_path.stem
                    index.add(
                        result.embedding,
                        track_id,
                        metadata={
                            'path': str(audio_path),
                            'duration': result.duration_seconds
                        }
                    )
                except Exception as e:
                    print(f"    {Fore.YELLOW}Warning: Failed to process {audio_path.name}: {e}{Style.RESET_ALL}")

            # Save index
            print()
            print(f"  Saving index...")
            index.save(str(output_dir))

            print(f"\n  {Fore.GREEN}[OK] Embeddings index built successfully{Style.RESET_ALL}")
            print(f"  Index: {output_dir}")
            print(f"  Tracks: {index.size}")
            print(f"\n  Use with: python analyze.py --find-similar track.wav --embedding-index {output_dir}")

        except ImportError as e:
            print(f"  {Fore.RED}[ERROR] Embeddings module not available: {e}{Style.RESET_ALL}")
            print(f"  Install dependencies: pip install openl3 faiss-cpu")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Building embeddings failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()
        return

    # Handle --find-similar (similarity search)
    if find_similar:
        print_section("Finding Similar Tracks")
        try:
            from embeddings import SimilarityIndex
            from embeddings.openl3_extractor import get_extractor

            index_path = Path(embedding_index) if embedding_index else Path('./embeddings_index')

            if not index_path.exists():
                print(f"  {Fore.RED}[ERROR] Embeddings index not found: {index_path}{Style.RESET_ALL}")
                print(f"  Build an index first: python analyze.py --build-embeddings references/")
                return

            print(f"  Query: {Path(find_similar).name}")
            print(f"  Index: {index_path}")
            print()

            # Load index
            print(f"  Loading index...")
            index = SimilarityIndex(dimension=512)
            index.load(str(index_path))
            print(f"  Index contains {index.size} tracks")
            print()

            # Extract query embedding
            print(f"  Extracting query embedding...")
            extractor = get_extractor(content_type="music", embedding_size=512, verbose=verbose)
            query_result = extractor.extract(find_similar)

            # Search
            print(f"  Searching for similar tracks...")
            results = index.search(query_result.embedding, k=top_k)

            print(f"\n  {Fore.CYAN}=== SIMILAR TRACKS ==={Style.RESET_ALL}\n")

            for i, result in enumerate(results, 1):
                similarity_pct = result.similarity * 100
                color = Fore.GREEN if similarity_pct > 70 else Fore.YELLOW if similarity_pct > 50 else Fore.WHITE
                print(f"  {i}. {color}{result.track_id}{Style.RESET_ALL}")
                print(f"     Similarity: {similarity_pct:.1f}%")
                if result.metadata and 'path' in result.metadata:
                    print(f"     Path: {result.metadata['path']}")
                print()

        except ImportError as e:
            print(f"  {Fore.RED}[ERROR] Embeddings module not available: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Similarity search failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()
        return

    # Handle --gap-analysis (compare against reference profile)
    if gap_analysis and audio:
        print_section("Gap Analysis (Profile Comparison)")
        try:
            from profiling import ReferenceProfile
            from analysis import GapAnalyzer

            print(f"  Track: {Path(audio).name}")
            print(f"  Profile: {Path(gap_analysis).name}")
            print()

            # Load profile
            profile = ReferenceProfile.load(gap_analysis)
            print(f"  Loaded profile: {profile.name} ({profile.track_count} reference tracks)")
            print()

            # Run analysis
            analyzer = GapAnalyzer(profile)
            report = analyzer.analyze(audio)

            # Print summary
            print(f"  {Fore.CYAN}=== OVERALL ASSESSMENT ==={Style.RESET_ALL}")
            print(f"  Similarity to References: {report.overall_similarity:.0%}")
            print(f"  Trance Score: {report.trance_score:.2f} / 1.00")
            print(f"  Nearest Style: \"{report.nearest_cluster_name}\"")
            print()

            # Issues summary
            print(f"  {Fore.CYAN}=== ISSUES FOUND ==={Style.RESET_ALL}")
            print(f"  Critical: {report.gap_count_by_severity.get('critical', 0)}    "
                  f"Warning: {report.gap_count_by_severity.get('warning', 0)}    "
                  f"Minor: {report.gap_count_by_severity.get('minor', 0)}")
            print()

            # Critical issues
            if report.critical_gaps:
                print(f"  {Fore.RED}CRITICAL ISSUES:{Style.RESET_ALL}")
                for i, gap in enumerate(report.critical_gaps[:5], 1):
                    print(f"    {i}. {gap.description}")
                    print(f"       → {gap.recommendation}")
                print()

            # Warnings
            if report.warning_gaps:
                print(f"  {Fore.YELLOW}WARNINGS:{Style.RESET_ALL}")
                for i, gap in enumerate(report.warning_gaps[:5], 1):
                    print(f"    {i}. {gap.description}")
                print()

            # Top recommendations
            print(f"  {Fore.GREEN}TOP RECOMMENDATIONS:{Style.RESET_ALL}")
            for fix in report.prioritized_fixes[:5]:
                severity_color = Fore.RED if fix.severity == 'critical' else Fore.YELLOW if fix.severity == 'warning' else Fore.WHITE
                print(f"    {fix.priority}. {severity_color}[{fix.severity.upper()}]{Style.RESET_ALL} {fix.action}")
            print()

            # Prescriptive fixes (if requested)
            prescriptive_data = None
            if prescriptive_fixes:
                try:
                    from fixes import PrescriptiveFixGenerator, FixValidator

                    print(f"  {Fore.CYAN}=== PRESCRIPTIVE FIXES ==={Style.RESET_ALL}")
                    print()

                    # Load ALS data if available
                    als_data = None
                    if als:
                        try:
                            parser = ALSParser(verbose=verbose)
                            als_data = parser.parse(als)
                            print(f"  Using ALS file for track-specific recommendations: {Path(als).name}")
                            print()
                        except Exception:
                            pass

                    # Generate prescriptive fixes
                    generator = PrescriptiveFixGenerator(profile=profile)
                    fixes = generator.generate_fixes(report, als_data=als_data)

                    # Validate fixes
                    validator = FixValidator()
                    valid_fixes = []
                    for fix in fixes:
                        result = validator.validate(fix)
                        if result.is_valid:
                            valid_fixes.append(fix)
                            # Add validation info
                            fix.confidence *= result.estimated_impact

                    # Show fixes
                    automatable = [f for f in valid_fixes if f.is_automatable]
                    manual = [f for f in valid_fixes if not f.is_automatable]

                    if automatable:
                        print(f"  {Fore.GREEN}🤖 AUTOMATABLE FIXES ({len(automatable)}):{Style.RESET_ALL}")
                        print()
                        for fix in automatable[:5]:
                            severity_icon = {'critical': '🔴', 'warning': '🟡', 'minor': '🟢'}.get(fix.severity, '⚪')
                            print(f"  [{fix.priority}] {severity_icon} {fix.feature.replace('_', ' ').title()} (Confidence: {fix.confidence*100:.0f}%)")
                            print(f"      Current: {fix.current_value:.2f} | Target: {fix.target_value:.2f}")
                            if fix.target_track:
                                print(f"      Track: \"{fix.target_track}\" | Device: {fix.target_device}")
                            print(f"      → {fix.suggested_change}")
                            if fix.osc_command:
                                print(f"      OSC: {fix.osc_command}")
                            print()

                    if manual:
                        print(f"  {Fore.YELLOW}👤 MANUAL FIXES ({len(manual)}):{Style.RESET_ALL}")
                        print()
                        for fix in manual[:5]:
                            severity_icon = {'critical': '🔴', 'warning': '🟡', 'minor': '🟢'}.get(fix.severity, '⚪')
                            print(f"  [{fix.priority}] {severity_icon} {fix.feature.replace('_', ' ').title()} (Confidence: {fix.confidence*100:.0f}%)")
                            print(f"      Current: {fix.current_value:.2f} | Target: {fix.target_value:.2f}")
                            print(f"      → {fix.suggested_change}")
                            if fix.manual_steps:
                                for step in fix.manual_steps[:2]:
                                    print(f"        • {step}")
                            print()

                    # Store for JSON output
                    prescriptive_data = [f.to_dict() for f in valid_fixes]

                    # Collect feedback if requested
                    if collect_feedback and valid_fixes:
                        try:
                            from learning import LearningDatabase, FeedbackCollector
                            from learning.feedback_collector import format_session_summary

                            print(f"\n  {Fore.CYAN}=== FEEDBACK COLLECTION ==={Style.RESET_ALL}")
                            print(f"  Collecting feedback to improve future recommendations...")
                            print()

                            db = LearningDatabase(learning_db_path)
                            collector = FeedbackCollector(db=db, verbose=verbose)

                            # Collect batch feedback
                            feedback_result = collector.collect_batch_feedback(
                                fixes=valid_fixes,
                                track_path=audio,
                                profile_name=profile.name,
                                gap_report=report
                            )

                            if feedback_result['session_id']:
                                # Print session summary
                                print(format_session_summary(feedback_result['session']))

                                # Prompt for re-analysis
                                print(f"\n  {Fore.YELLOW}Re-analyze to measure improvement? [y/N]:{Style.RESET_ALL} ", end='')
                                try:
                                    reanalyze = input().strip().lower()
                                except (EOFError, KeyboardInterrupt):
                                    reanalyze = 'n'

                                if reanalyze in ('y', 'yes'):
                                    print(f"\n  {Fore.CYAN}Re-analyzing track...{Style.RESET_ALL}")
                                    print(f"  {Fore.YELLOW}Note: Re-run analysis after applying fixes to your project{Style.RESET_ALL}")
                                    print(f"  {Fore.YELLOW}Then use --learning-stats to see improvement metrics{Style.RESET_ALL}")

                                print(f"\n  {Fore.GREEN}[OK] Feedback saved to {learning_db_path}{Style.RESET_ALL}")

                        except ImportError as e:
                            print(f"  {Fore.YELLOW}[WARNING] Learning module not available: {e}{Style.RESET_ALL}")
                        except Exception as e:
                            print(f"  {Fore.YELLOW}[WARNING] Feedback collection failed: {e}{Style.RESET_ALL}")
                            if verbose:
                                import traceback
                                traceback.print_exc()

                except ImportError as e:
                    print(f"  {Fore.YELLOW}[WARNING] Prescriptive fixes module not available: {e}{Style.RESET_ALL}")
                except Exception as e:
                    print(f"  {Fore.YELLOW}[WARNING] Could not generate prescriptive fixes: {e}{Style.RESET_ALL}")
                    if verbose:
                        import traceback
                        traceback.print_exc()

            # Save report
            from datetime import datetime
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)
            json_filename = f"gap_report_{Path(audio).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            json_path = output_dir / json_filename

            import json
            report_data = report.to_dict()
            if prescriptive_data:
                report_data['prescriptive_fixes'] = prescriptive_data
            with open(json_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            print(f"  {Fore.GREEN}[OK] Full report saved to: {json_path}{Style.RESET_ALL}")

        except FileNotFoundError as e:
            print(f"  {Fore.RED}[ERROR] Profile not found: {e}{Style.RESET_ALL}")
        except ImportError as e:
            print(f"  {Fore.RED}[ERROR] Gap analysis module not available: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Gap analysis failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()
        return

    # Validate inputs
    if not any([audio, stems, als, separate, compare_ref, analyze_reference]):
        click.echo(f"{Fore.RED}Error: Please provide at least one of: --audio, --stems, --als, --separate, --compare-ref, or --analyze-reference{Style.RESET_ALL}")
        click.echo("Run 'python analyze.py --help' for usage information.")
        sys.exit(1)

    if master and not reference:
        click.echo(f"{Fore.RED}Error: --master requires --reference to be specified{Style.RESET_ALL}")
        sys.exit(1)

    if master and not audio:
        click.echo(f"{Fore.RED}Error: --master requires --audio to be specified{Style.RESET_ALL}")
        sys.exit(1)

    if compare_ref and not audio:
        click.echo(f"{Fore.RED}Error: --compare-ref requires --audio to be specified{Style.RESET_ALL}")
        sys.exit(1)

    # Create output directory
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize results
    audio_result = None
    stem_result = None
    als_result = None
    mastering_result = None
    comparison_result = None
    section_result = None

    # Handle stem separation
    if separate:
        print_section("Separating Stems")
        try:
            separator = StemSeparator(cache_dir=str(output_path / "cache" / "stems"), verbose=verbose)
            print(f"  Source: {Path(separate).name}")
            print(f"  Model: spleeter:4stems")
            print(f"\n  {Fore.YELLOW}Separating (this may take 30-60 seconds)...{Style.RESET_ALL}")

            def progress_cb(progress):
                if progress.stage == 'cached':
                    print(f"  {Fore.GREEN}[CACHED] Using previously separated stems{Style.RESET_ALL}")
                elif progress.stage == 'complete':
                    print(f"  {Fore.GREEN}[OK] Separation complete{Style.RESET_ALL}")

            sep_result = separator.separate(separate, progress_callback=progress_cb)

            if sep_result.success:
                print(f"\n  Stems saved to: {sep_result.output_dir}")
                for stem_type, stem_info in sep_result.stems.items():
                    print(f"    - {stem_type.value}.wav ({stem_info.rms_db:.1f} dB RMS)")

                if sep_result.cached:
                    print(f"\n  {Fore.CYAN}(Retrieved from cache in {sep_result.separation_time_seconds:.1f}s){Style.RESET_ALL}")
                else:
                    print(f"\n  {Fore.CYAN}(Separated in {sep_result.separation_time_seconds:.1f}s){Style.RESET_ALL}")
            else:
                print(f"  {Fore.RED}[ERROR] {sep_result.error_message}{Style.RESET_ALL}")

        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Stem separation failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()

    # Handle reference comparison
    if compare_ref and audio and cfg.stage_enabled('reference_comparison'):
        print_section("Reference Track Comparison")
        try:
            comparator = ReferenceComparator(
                cache_dir=str(output_path / "cache" / "stems"),
                library_dir=str(output_path.parent / "reference_library"),
                verbose=verbose
            )

            print(f"  Your Mix: {Path(audio).name}")
            print(f"  Reference: {Path(compare_ref).name}")
            print(f"\n  {Fore.YELLOW}Separating and analyzing stems...{Style.RESET_ALL}")

            def comp_progress_cb(progress):
                if progress.stage == 'separating_user':
                    print(f"  Separating your mix...")
                elif progress.stage == 'separating_reference':
                    print(f"  Separating reference track...")
                elif progress.stage == 'analyzing':
                    print(f"  Comparing stems...")
                elif progress.stage == 'complete':
                    print(f"  {Fore.GREEN}[OK] Comparison complete{Style.RESET_ALL}")

            comparison_result = comparator.compare(audio, compare_ref, progress_callback=comp_progress_cb)

            if comparison_result.success:
                print(f"\n  {Fore.CYAN}=== STEM-BY-STEM COMPARISON ==={Style.RESET_ALL}\n")

                for stem_name, comp in comparison_result.stem_comparisons.items():
                    severity_color = {
                        'good': Fore.GREEN,
                        'minor': Fore.BLUE,
                        'moderate': Fore.YELLOW,
                        'significant': Fore.RED
                    }.get(comp.severity, Fore.WHITE)

                    print(f"  {Fore.WHITE}{stem_name.upper()}:{Style.RESET_ALL} {severity_color}[{comp.severity.upper()}]{Style.RESET_ALL}")
                    print(f"    Level: {comp.user_rms_db:.1f} dB (ref: {comp.ref_rms_db:.1f} dB) -> {comp.rms_diff_db:+.1f} dB")
                    print(f"    Width: {comp.user_stereo_width_pct:.0f}% (ref: {comp.ref_stereo_width_pct:.0f}%)")

                    if comp.recommendations:
                        for rec in comp.recommendations[:2]:
                            print(f"    {Fore.YELLOW}> {rec}{Style.RESET_ALL}")
                    print()

                print(f"  {Fore.CYAN}Overall Balance Score: {comparison_result.overall_balance_score:.0f}/100{Style.RESET_ALL}")

                if comparison_result.priority_recommendations:
                    print(f"\n  {Fore.GREEN}Priority Actions:{Style.RESET_ALL}")
                    for i, rec in enumerate(comparison_result.priority_recommendations[:5], 1):
                        print(f"    {i}. {rec}")

                if comparison_result.reference_id:
                    print(f"\n  {Fore.CYAN}Reference stored (ID: {comparison_result.reference_id}){Style.RESET_ALL}")
            else:
                print(f"  {Fore.RED}[ERROR] {comparison_result.error_message}{Style.RESET_ALL}")

        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Reference comparison failed: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()

    # Parse ALS file
    if als and cfg.stage_enabled('als_parsing'):
        print_section("Parsing Ableton Project")
        try:
            parser = ALSParser(verbose=verbose)
            als_result = parser.parse(als)

            print(f"  Project: {Path(als).name}")
            print(f"  Tempo: {als_result.tempo:.1f} BPM", end="")

            # Show tempo automation status
            if als_result.project_structure and als_result.project_structure.has_tempo_changes:
                print(f" {Fore.YELLOW}(with tempo automation){Style.RESET_ALL}")
            else:
                print(" (constant)")

            print(f"  Time Signature: {als_result.time_signature_numerator}/{als_result.time_signature_denominator}")

            # Track breakdown
            midi_tracks = len([t for t in als_result.tracks if t.track_type == 'midi'])
            audio_tracks = len([t for t in als_result.tracks if t.track_type == 'audio'])
            print(f"  Tracks: {len(als_result.tracks)} ({midi_tracks} MIDI, {audio_tracks} Audio)")
            print(f"  MIDI Notes: {als_result.midi_note_count:,}")
            print(f"  Audio Clips: {als_result.audio_clip_count}")

            if als_result.plugin_list:
                print(f"  Plugins: {', '.join(als_result.plugin_list[:5])}")
                if len(als_result.plugin_list) > 5:
                    print(f"           ...and {len(als_result.plugin_list) - 5} more")

            # MIDI Analysis Summary
            if als_result.midi_analysis:
                print(f"\n  {Fore.CYAN}MIDI Analysis:{Style.RESET_ALL}")
                humanized = sum(1 for a in als_result.midi_analysis.values()
                              if a.humanization_score in ('slightly_humanized', 'natural'))
                total_midi = len(als_result.midi_analysis)
                print(f"    Humanized Tracks: {humanized}/{total_midi} ({100*humanized//total_midi if total_midi else 0}%)")
                print(f"    Off-Grid Notes: {als_result.quantization_issues_count}")
                print(f"    Detected Chords: {als_result.total_chord_count}")

                # Show robotic tracks as warnings
                robotic_tracks = [name for name, a in als_result.midi_analysis.items()
                                 if a.humanization_score == 'robotic']
                if robotic_tracks:
                    print(f"\n  {Fore.YELLOW}MIDI Issues:{Style.RESET_ALL}")
                    for track in robotic_tracks[:5]:
                        analysis = als_result.midi_analysis[track]
                        print(f"    {Fore.YELLOW}[!]{Style.RESET_ALL} {track}: ROBOTIC (vel std={analysis.velocity_std})")
                    if len(robotic_tracks) > 5:
                        print(f"        ...and {len(robotic_tracks) - 5} more")

                # Show severe quantization errors
                severe_errors = []
                for name, analysis in als_result.midi_analysis.items():
                    for err in analysis.quantization_errors:
                        if err.severity == 'severe':
                            severe_errors.append((name, err))

                if severe_errors:
                    print(f"\n    {Fore.RED}Severe Off-Grid Notes:{Style.RESET_ALL}")
                    for track_name, err in severe_errors[:5]:
                        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                        note_name = note_names[err.pitch % 12]
                        octave = err.pitch // 12 - 1
                        print(f"      {track_name}: {note_name}{octave} at beat {err.time:.2f} (off by {err.error_beats:.3f})")
                    if len(severe_errors) > 5:
                        print(f"      ...and {len(severe_errors) - 5} more")

            # Project Structure
            if als_result.project_structure:
                struct = als_result.project_structure

                if struct.locators:
                    print(f"\n  {Fore.CYAN}Song Structure:{Style.RESET_ALL}")
                    markers = " -> ".join(f"{l.name} ({l.time:.0f})" for l in struct.locators[:6])
                    print(f"    Markers: {markers}")
                    if len(struct.locators) > 6:
                        print(f"             ...and {len(struct.locators) - 6} more")

                if struct.scenes:
                    print(f"    Scenes: {len(struct.scenes)}")

                if struct.tempo_automation and len(struct.tempo_automation) > 1:
                    print(f"    Tempo Changes: {len(struct.tempo_automation)} points")
                    for tc in struct.tempo_automation[:3]:
                        print(f"      Beat {tc.time:.1f}: {tc.tempo:.1f} BPM")
                    if len(struct.tempo_automation) > 3:
                        print(f"      ...and {len(struct.tempo_automation) - 3} more")

            print(f"\n  {Fore.GREEN}[OK] Project parsed successfully{Style.RESET_ALL}")

        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Error parsing ALS file: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()

    # Analyze single audio file
    if audio and cfg.stage_enabled('audio_analysis'):
        print_section("Analyzing Audio Mix")
        try:
            analyzer = AudioAnalyzer(verbose=verbose, config=cfg)
            reference_tempo = als_result.tempo if als_result else None

            print(f"  Analyzing: {Path(audio).name}")
            audio_result = analyzer.analyze(
                audio,
                reference_tempo=reference_tempo,
                genre_preset=genre_preset
            )

            # Display results
            print(f"\n  Duration: {audio_result.duration_seconds:.1f}s")
            print(f"  Sample Rate: {audio_result.sample_rate} Hz")
            print(f"  Channels: {'Stereo' if audio_result.channels == 2 else 'Mono'}")

            if audio_result.detected_tempo:
                print(f"  Detected Tempo: {audio_result.detected_tempo:.1f} BPM")

            # Print issues
            if audio_result.overall_issues:
                print(f"\n  {Fore.YELLOW}Issues Found:{Style.RESET_ALL}")
                for issue in audio_result.overall_issues:
                    print_issue(issue.get('severity', 'info'), issue['message'])
            else:
                print(f"\n  {Fore.GREEN}[OK] No significant issues detected{Style.RESET_ALL}")

            # Print key metrics
            print(f"\n  {Fore.CYAN}Key Metrics:{Style.RESET_ALL}")
            print(f"    Peak: {audio_result.dynamics.peak_db:.1f} dBFS")
            print(f"    RMS: {audio_result.dynamics.rms_db:.1f} dBFS")
            print(f"    Dynamic Range: {audio_result.dynamics.dynamic_range_db:.1f} dB")
            print(f"    Est. LUFS: {audio_result.loudness.integrated_lufs:.1f}")

            if audio_result.stereo.is_stereo:
                print(f"    Stereo Width: {audio_result.stereo.width_estimate:.0f}%")

            # Display genre comparison if available
            if audio_result.genre_comparison:
                print(f"\n  {Fore.CYAN}Genre Comparison ({audio_result.genre_preset.upper()}):{Style.RESET_ALL}")
                for param, result in audio_result.genre_comparison.items():
                    status = result['status']
                    if status == 'ok':
                        color = Fore.GREEN
                        icon = '[OK]'
                    elif status == 'warning':
                        color = Fore.YELLOW
                        icon = '[!]'
                    else:
                        color = Fore.RED
                        icon = '[X]'
                    print(f"    {color}{icon}{Style.RESET_ALL} {param}: {result['message']}")

        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Error analyzing audio: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()

    # Analyze stems
    if stems and cfg.stage_enabled('stem_analysis'):
        print_section("Analyzing Stems")
        try:
            stems_path = Path(stems)
            stem_files = []

            # Find audio files in stems directory
            for ext in ['*.wav', '*.WAV', '*.flac', '*.FLAC', '*.aiff', '*.AIFF']:
                stem_files.extend(stems_path.glob(ext))

            if not stem_files:
                print(f"  {Fore.YELLOW}No audio files found in {stems}{Style.RESET_ALL}")
            else:
                print(f"  Found {len(stem_files)} stems:")
                for sf in stem_files[:10]:
                    print(f"    - {sf.name}")
                if len(stem_files) > 10:
                    print(f"    ...and {len(stem_files) - 10} more")

                stem_analyzer = StemAnalyzer(config=cfg)
                stem_result = stem_analyzer.analyze_stems(
                    [str(f) for f in stem_files]
                )

                # Print clash analysis
                if stem_result.clashes:
                    print(f"\n  {Fore.YELLOW}Frequency Clashes Found:{Style.RESET_ALL}")
                    for clash in stem_result.clashes:
                        severity_color = {
                            'severe': Fore.RED,
                            'moderate': Fore.YELLOW,
                            'minor': Fore.BLUE
                        }.get(clash.severity, Fore.WHITE)

                        print(f"    {severity_color}[{clash.severity.upper()}]{Style.RESET_ALL} "
                              f"{clash.stem1} vs {clash.stem2}")
                        print(f"      Range: {clash.frequency_range[0]:.0f}-{clash.frequency_range[1]:.0f} Hz")
                        print(f"      Fix: {clash.recommendation}")
                else:
                    print(f"\n  {Fore.GREEN}[OK] No significant frequency clashes{Style.RESET_ALL}")

                # Print balance issues
                if stem_result.balance_issues:
                    print(f"\n  {Fore.YELLOW}Balance Issues:{Style.RESET_ALL}")
                    for issue in stem_result.balance_issues:
                        print(f"    [!] {issue['message']}")

        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Error analyzing stems: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()

    # Mastering
    if master and audio and reference and cfg.stage_enabled('ai_mastering'):
        print_section("AI Mastering")
        try:
            engine = MasteringEngine(output_dir=output)
            print(f"  Target: {Path(audio).name}")
            print(f"  Reference: {Path(reference).name}")
            print(f"  Processing...")

            mastering_result = engine.master(audio, reference)

            if mastering_result.success:
                print(f"\n  {Fore.GREEN}[OK] Mastering complete{Style.RESET_ALL}")
                print(f"  Output: {mastering_result.output_path}")

                if mastering_result.before_lufs and mastering_result.after_lufs:
                    change = mastering_result.after_lufs - mastering_result.before_lufs
                    print(f"\n  Loudness Change: {change:+.1f} LUFS")
                    print(f"    Before: {mastering_result.before_lufs:.1f} LUFS")
                    print(f"    After: {mastering_result.after_lufs:.1f} LUFS")
                    print(f"    Reference: {mastering_result.reference_lufs:.1f} LUFS")
            else:
                print(f"\n  {Fore.RED}[ERROR] Mastering failed: {mastering_result.error_message}{Style.RESET_ALL}")

        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Error during mastering: {e}{Style.RESET_ALL}")
            if verbose:
                import traceback
                traceback.print_exc()

    # Generate report
    print_section("Generating Report")
    try:
        reporter = ReportGenerator(output_dir=output)
        # Derive project name from als/audio filename
        project_name = Path(als).stem if als else (Path(audio).stem if audio else "analysis")

        report_path = reporter.generate_full_report(
            audio_analysis=audio_result,
            stem_analysis=stem_result,
            als_project=als_result,
            mastering_result=mastering_result,
            comparison_result=comparison_result,
            project_name=project_name,
            output_format=output_format
        )

        print(f"  {Fore.GREEN}[OK] Report saved to: {report_path}{Style.RESET_ALL}")

    except Exception as e:
        print(f"  {Fore.RED}[ERROR] Error generating report: {e}{Style.RESET_ALL}")
        if verbose:
            import traceback
            traceback.print_exc()

    # Print recommendations summary
    all_recommendations = []
    if audio_result:
        all_recommendations.extend(audio_result.recommendations)
    if stem_result:
        all_recommendations.extend(stem_result.recommendations)
    if comparison_result and comparison_result.success:
        all_recommendations.extend(comparison_result.priority_recommendations[:5])

    if all_recommendations:
        print_section("Recommendations Summary")
        for i, rec in enumerate(all_recommendations[:10], 1):
            print_recommendation(i, rec)
        if len(all_recommendations) > 10:
            print(f"\n  ...and {len(all_recommendations) - 10} more in the full report")

    # Final summary
    date_str = __import__('datetime').datetime.now().strftime("%Y-%m-%d")
    report_base = f"{output}/{project_name}/{project_name}_analysis_{date_str}"
    json_report_path = f"{report_base}.json"

    print(f"""
{Fore.CYAN}==============================================================={Style.RESET_ALL}
{Fore.GREEN}Analysis Complete!{Style.RESET_ALL}

Report: {report_base}.{output_format}
""")

    if mastering_result and mastering_result.success:
        print(f"Mastered: {mastering_result.output_path}")

    # Next step: AI-powered recommendations
    prompts_dir = "C:\\claude-workspace\\AbletonAIAnalysis\\docs\\ai\\RecommendationGuide\\prompts"

    print(f"""
{Fore.CYAN}==============================================================={Style.RESET_ALL}
{Fore.YELLOW}NEXT STEP: Get AI-Powered Recommendations{Style.RESET_ALL}

Your analysis JSON: {json_report_path}

{Fore.WHITE}Run specialist analyses (recommended order):{Style.RESET_ALL}

  {Fore.GREEN}1. Low End{Style.RESET_ALL} (kick/bass relationship, sub-bass, sidechain)
     claude --add-file "{prompts_dir}\\LowEnd.md" --add-file "{json_report_path}"

  {Fore.GREEN}2. Frequency Balance{Style.RESET_ALL} (EQ, muddy/harsh frequencies, clashes)
     claude --add-file "{prompts_dir}\\FrequencyBalance.md" --add-file "{json_report_path}"

  {Fore.GREEN}3. Dynamics{Style.RESET_ALL} (compression, transients, punch)
     claude --add-file "{prompts_dir}\\Dynamics.md" --add-file "{json_report_path}"

  {Fore.GREEN}4. Stereo & Phase{Style.RESET_ALL} (width, mono compatibility, phase)
     claude --add-file "{prompts_dir}\\StereoPhase.md" --add-file "{json_report_path}"

  {Fore.GREEN}5. Sections{Style.RESET_ALL} (drop impact, transitions, energy flow)
     claude --add-file "{prompts_dir}\\Sections.md" --add-file "{json_report_path}"

  {Fore.GREEN}6. Loudness{Style.RESET_ALL} (LUFS, true peak, streaming targets)
     claude --add-file "{prompts_dir}\\Loudness.md" --add-file "{json_report_path}"

{Fore.CYAN}Then ask: "Analyze my mix"{Style.RESET_ALL}
{Fore.CYAN}==============================================================={Style.RESET_ALL}
""")

    # AI Recommend: Auto-launch Claude with the analysis
    if ai_recommend:
        print(f"\n{Fore.CYAN}>> Launching AI Recommendations{Style.RESET_ALL}")
        print(f"--------------------------------------------------")

        guide_path = "C:\\claude-workspace\\AbletonAIAnalysis\\docs\\ai\\RecommendationGuide\\RecommendationGuide.md"

        # Build the claude command
        import subprocess
        import sys

        try:
            # Check if claude is available
            result = subprocess.run(['claude', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  {Fore.RED}[ERROR] Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code{Style.RESET_ALL}")
            else:
                # Launch Claude with the analysis files
                print(f"  Starting Claude with analysis data...")
                print(f"  Files: RecommendationGuide.md + {project_name}_analysis.json")
                print(f"\n  {Fore.YELLOW}Claude will open. Ask: 'Analyze my mix'{Style.RESET_ALL}\n")

                # Use subprocess to launch claude interactively
                claude_cmd = [
                    'claude',
                    '--add-file', guide_path,
                    '--add-file', json_report_path
                ]

                # Launch interactively (don't capture output)
                subprocess.run(claude_cmd)

        except FileNotFoundError:
            print(f"  {Fore.RED}[ERROR] Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code{Style.RESET_ALL}")
        except Exception as e:
            print(f"  {Fore.RED}[ERROR] Could not launch Claude: {e}{Style.RESET_ALL}")


if __name__ == '__main__':
    main()
