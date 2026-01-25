#!/usr/bin/env python3
"""
YouTube Reference Track Analyzer

A CLI tool for analyzing trance music reference tracks from YouTube.
Downloads audio, extracts features, and stores data for production guidance.

Usage:
    yt-analyzer db init              Initialize database tables
    yt-analyzer ingest <url>         Download and add track(s)
    yt-analyzer analyze <id>         Run analysis pipeline
    yt-analyzer list                 List all tracks
    yt-analyzer show <id>            Show track details
    yt-analyzer search --similar-to  Find similar tracks
"""

import sys
from pathlib import Path

import click

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from database import init_yt_schema, YTRepository, YTTrack, YTFeatures, YTSection, YTArrangementStats
from ingest import YouTubeDownloader, parse_urls, extract_youtube_id
from features import extract_all_features, format_all_features
from structure import extract_structure, format_structure_display, refine_sections_with_energy

# Default database path (shared with als-doctor)
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "projects.db"


def get_repo(ctx) -> YTRepository:
    """Get repository from context."""
    db_path = ctx.obj.get('db_path', DEFAULT_DB_PATH)
    return YTRepository(db_path)


def format_duration(seconds: float) -> str:
    """Format duration as MM:SS or HH:MM:SS."""
    if not seconds:
        return "--:--"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# ==================== ROOT GROUP ====================

@click.group()
@click.option('--db', 'db_path', type=click.Path(), default=None,
              help='Database path (default: data/projects.db)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.version_option(version="0.1.0", prog_name="yt-analyzer")
@click.pass_context
def cli(ctx, db_path, verbose):
    """YouTube Reference Track Analyzer for Trance Music

    Analyze reference tracks from YouTube to guide your productions.
    """
    ctx.ensure_object(dict)
    ctx.obj['db_path'] = Path(db_path) if db_path else DEFAULT_DB_PATH
    ctx.obj['verbose'] = verbose


# ==================== DATABASE COMMANDS ====================

@cli.group()
@click.pass_context
def db(ctx):
    """Database management commands."""
    pass


@db.command('init')
@click.pass_context
def db_init(ctx):
    """Initialize YouTube reference track tables.

    Creates the yt_ prefixed tables in the shared database.
    Safe to run multiple times.

    Example:
        yt-analyzer db init
    """
    db_path = ctx.obj.get('db_path', DEFAULT_DB_PATH)

    success, message = init_yt_schema(db_path)

    if success:
        click.secho(f"SUCCESS: {message}", fg='green')
    else:
        click.secho(f"ERROR: {message}", fg='red')
        raise SystemExit(1)


@db.command('status')
@click.pass_context
def db_status(ctx):
    """Show database status.

    Example:
        yt-analyzer db status
    """
    repo = get_repo(ctx)

    if not repo.is_initialized():
        click.secho("Database not initialized. Run 'yt-analyzer db init' first.", fg='red')
        raise SystemExit(1)

    stats = repo.get_stats()

    click.echo("\nYOUTUBE REFERENCE TRACKS DATABASE")
    click.echo("=" * 40)
    click.echo(f"Total tracks:      {stats['tracks']}")
    click.echo(f"Analyzed:          {stats['analyzed']}")
    click.echo(f"With stems:        {stats['with_stems']}")
    click.echo(f"With embeddings:   {stats['with_embeddings']}")
    click.echo()


# ==================== INGEST COMMANDS ====================

@cli.command('ingest')
@click.argument('source')
@click.option('--from-file', 'from_file', is_flag=True,
              help='Treat SOURCE as a file containing URLs')
@click.option('--limit', '-l', type=int, default=None,
              help='Limit number of downloads (for playlists)')
@click.option('--genre', '-g', default='trance',
              help='Genre tag for ingested tracks')
@click.option('--tags', '-t', default=None,
              help='Comma-separated tags')
@click.option('--no-analyze', is_flag=True,
              help='Skip immediate analysis')
@click.pass_context
def ingest(ctx, source, from_file, limit, genre, tags, no_analyze):
    """Download and add track(s) from YouTube.

    SOURCE can be:
        - A single YouTube URL
        - A playlist URL
        - A file path containing URLs (with --from-file)

    Examples:
        yt-analyzer ingest "https://youtube.com/watch?v=xxx"
        yt-analyzer ingest "https://youtube.com/playlist?list=xxx" --limit 10
        yt-analyzer ingest urls.txt --from-file
    """
    repo = get_repo(ctx)
    verbose = ctx.obj.get('verbose', False)

    if not repo.is_initialized():
        click.secho("Database not initialized. Run 'yt-analyzer db init' first.", fg='red')
        raise SystemExit(1)

    # Parse source
    if from_file:
        urls, is_playlist, playlist_id = parse_urls(source)
        is_playlist = False  # File is never a playlist
    else:
        urls, is_playlist, playlist_id = parse_urls(source)

    if not urls:
        click.secho("No valid URLs found.", fg='red')
        raise SystemExit(1)

    # Initialize downloader
    tracks_dir = Path(__file__).parent / "tracks"
    downloader = YouTubeDownloader(output_dir=tracks_dir)

    # Download tracks
    results = []

    if is_playlist:
        click.echo(f"Downloading playlist (ID: {playlist_id})...")

        def progress(msg, current, total):
            click.echo(f"  [{current}/{total}] {msg}")

        results = downloader.download_playlist(urls[0], limit=limit, progress_callback=progress)
    else:
        for i, url in enumerate(urls):
            if limit and i >= limit:
                break

            click.echo(f"[{i+1}/{len(urls)}] Downloading: {url}")
            result = downloader.download(url)
            results.append(result)

            if result.success:
                click.secho(f"  Downloaded: {result.title or result.youtube_id}", fg='green')
            else:
                click.secho(f"  Failed: {result.error_message}", fg='red')

    # Save to database
    success_count = 0
    for result in results:
        if not result.success:
            continue

        track = YTTrack(
            youtube_id=result.youtube_id,
            youtube_url=result.youtube_url,
            title=result.title,
            artist=result.artist,
            channel=result.channel,
            duration_seconds=result.duration_seconds,
            local_path=result.local_path,
            thumbnail_url=result.thumbnail_url,
            upload_date=result.upload_date,
            genre_tag=genre,
            user_tags=tags
        )

        success, msg, track_id = repo.create_track(track)
        if success:
            success_count += 1
            if verbose:
                click.echo(f"  Saved to database: {msg}")

    # Summary
    click.echo()
    click.echo(f"Ingested: {success_count}/{len(results)} tracks")

    if not no_analyze and success_count > 0:
        click.echo()
        click.echo("To analyze, run:")
        click.secho("  yt-analyzer analyze --all-pending", fg='cyan')


# ==================== LIST COMMAND ====================

@cli.command('list')
@click.option('--genre', '-g', default=None, help='Filter by genre')
@click.option('--analyzed', is_flag=True, help='Show only analyzed tracks')
@click.option('--not-analyzed', is_flag=True, help='Show only non-analyzed tracks')
@click.option('--rating', '-r', type=int, default=None, help='Filter by exact rating (1-3)')
@click.option('--min-rating', type=int, default=None, help='Filter by minimum rating')
@click.option('--favorites', is_flag=True, help='Show only 3-star favorites')
@click.option('--limit', '-l', type=int, default=50, help='Max results')
@click.pass_context
def list_tracks(ctx, genre, analyzed, not_analyzed, rating, min_rating, favorites, limit):
    """List tracks in the database.

    Examples:
        yt-analyzer list
        yt-analyzer list --genre trance
        yt-analyzer list --favorites
        yt-analyzer list --min-rating 2
    """
    repo = get_repo(ctx)

    if not repo.is_initialized():
        click.secho("Database not initialized. Run 'yt-analyzer db init' first.", fg='red')
        raise SystemExit(1)

    tracks = repo.list_tracks(
        genre=genre,
        analyzed_only=analyzed,
        not_analyzed_only=not_analyzed,
        rating=rating,
        min_rating=min_rating,
        favorites_only=favorites,
        limit=limit
    )

    if not tracks:
        click.echo("No tracks found.")
        return

    click.echo(f"\nTRACKS ({len(tracks)} shown)")
    click.echo("=" * 85)

    # Header
    click.echo(f"{'ID':<12} {'Title':<32} {'BPM':>5} {'Key':<4} {'Dur':>6} {'Rate':<4} {'Status':<8}")
    click.echo("-" * 85)

    for t in tracks:
        title = (t.title or "Untitled")[:30]
        if len(t.title or "") > 30:
            title += ".."

        bpm_str = f"{t.bpm:.0f}" if t.bpm else "--"
        key_str = t.key_camelot or t.key_name or "--"
        dur_str = format_duration(t.duration_seconds)

        # Rating display
        if t.rating:
            rating_str = "*" * t.rating
        else:
            rating_str = "---"

        status_parts = []
        if t.is_analyzed:
            status_parts.append("A")
        if t.has_stems:
            status_parts.append("S")
        if t.has_embeddings:
            status_parts.append("E")
        status = "[" + "".join(status_parts) + "]" if status_parts else "[--]"

        click.echo(f"{t.youtube_id:<12} {title:<32} {bpm_str:>5} {key_str:<4} {dur_str:>6} {rating_str:<4} {status:<8}")

    click.echo()
    click.echo("Rating: * ** *** | Status: [A]=Analyzed [S]=Stems [E]=Embeddings")


# ==================== RATE COMMAND ====================

@cli.command('rate')
@click.argument('youtube_id')
@click.argument('rating', type=int)
@click.pass_context
def rate_track(ctx, youtube_id, rating):
    """Set rating for a track (1-3 stars).

    Rating levels:
        1 = Good reference
        2 = Great reference
        3 = Top-tier favorite

    Use 0 to clear rating.

    Examples:
        yt-analyzer rate dQw4w9WgXcQ 3
        yt-analyzer rate dQw4w9WgXcQ 0  # Clear rating
    """
    repo = get_repo(ctx)

    if not repo.is_initialized():
        click.secho("Database not initialized. Run 'yt-analyzer db init' first.", fg='red')
        raise SystemExit(1)

    # Convert 0 to None (clear rating)
    if rating == 0:
        actual_rating = None
    elif rating < 1 or rating > 3:
        click.secho("Rating must be 1, 2, or 3 (or 0 to clear)", fg='red')
        raise SystemExit(1)
    else:
        actual_rating = rating

    success, message = repo.set_rating(youtube_id, actual_rating)

    if success:
        click.secho(message, fg='green')
    else:
        click.secho(message, fg='red')
        raise SystemExit(1)


# ==================== SHOW COMMAND ====================

@cli.command('show')
@click.argument('youtube_id')
@click.option('--sections', is_flag=True, help='Show section breakdown')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.pass_context
def show_track(ctx, youtube_id, sections, as_json):
    """Show details for a track.

    Examples:
        yt-analyzer show dQw4w9WgXcQ
        yt-analyzer show dQw4w9WgXcQ --sections
    """
    repo = get_repo(ctx)

    if not repo.is_initialized():
        click.secho("Database not initialized. Run 'yt-analyzer db init' first.", fg='red')
        raise SystemExit(1)

    detail = repo.get_track_detail(youtube_id)

    if not detail:
        click.secho(f"Track not found: {youtube_id}", fg='red')
        raise SystemExit(1)

    track = detail.track
    features = detail.features

    if as_json:
        import json
        # Simplified JSON export
        data = {
            'youtube_id': track.youtube_id,
            'title': track.title,
            'artist': track.artist,
            'duration': track.duration_seconds,
            'rating': track.rating,
            'bpm': features.bpm if features else None,
            'key': features.key_name if features else None,
            'lufs': features.integrated_lufs if features else None,
        }
        click.echo(json.dumps(data, indent=2))
        return

    # Display header
    click.echo()
    click.echo("=" * 60)
    title_line = track.title or "Untitled"
    if track.rating:
        title_line += "  " + "*" * track.rating
    click.secho(title_line, fg='cyan', bold=True)
    click.echo("=" * 60)
    click.echo()

    # Basic info
    click.echo(f"YouTube ID:  {track.youtube_id}")
    click.echo(f"Artist:      {track.artist or track.channel or 'Unknown'}")
    click.echo(f"Duration:    {format_duration(track.duration_seconds)}")
    click.echo(f"Genre:       {track.genre_tag}")
    click.echo(f"Rating:      {track.rating_stars}")
    if track.user_tags:
        click.echo(f"Tags:        {track.user_tags}")
    click.echo()

    # Features
    if features:
        click.echo("FEATURES")
        click.echo("-" * 40)
        click.echo(f"BPM:         {features.bpm:.1f}" if features.bpm else "BPM:         --")
        click.echo(f"Key:         {features.key_name} ({features.key_camelot})" if features.key_name else "Key:         --")
        click.echo(f"Loudness:    {features.integrated_lufs:.1f} LUFS" if features.integrated_lufs else "Loudness:    --")
        if features.stereo_width is not None:
            try:
                stereo_val = float(features.stereo_width)
                click.echo(f"Stereo:      {stereo_val:.0f}%")
            except (TypeError, ValueError):
                click.echo("Stereo:      --")
        else:
            click.echo("Stereo:      --")
        click.echo()
    else:
        click.echo("Not analyzed yet. Run: yt-analyzer analyze " + youtube_id)
        click.echo()

    # Sections
    if sections and detail.sections:
        click.echo("SECTIONS")
        click.echo("-" * 40)
        for s in detail.sections:
            bar_info = f"bars {s.start_bar}-{s.end_bar}" if s.start_bar is not None else ""
            click.echo(f"  {s.section_index+1}. {s.section_type:<12} {format_duration(s.start_time)}-{format_duration(s.end_time)} {bar_info}")
        click.echo()

    # Arrangement stats
    if detail.arrangement:
        arr = detail.arrangement
        click.echo("ARRANGEMENT")
        click.echo("-" * 40)
        click.echo(f"Total bars:        {arr.total_bars or '--'}")
        click.echo(f"First drop at:     bar {arr.bars_to_first_drop or '--'}")
        click.echo(f"First breakdown:   bar {arr.bars_to_first_breakdown or '--'}")
        click.echo(f"Drops:             {arr.num_drops}")
        click.echo(f"Breakdowns:        {arr.num_breakdowns}")
        click.echo(f"Phrase length:     {arr.phrase_length_bars or '--'} bars")
        click.echo()


# ==================== ANALYZE COMMAND ====================

@cli.command('analyze')
@click.argument('youtube_id', required=False)
@click.option('--all-pending', is_flag=True, help='Analyze all non-analyzed tracks')
@click.option('--favorites', is_flag=True, help='Analyze only 3-star favorites')
@click.option('--min-rating', type=int, default=None, help='Analyze tracks with at least this rating')
@click.option('--features', 'stage_features', is_flag=True, help='Extract features only')
@click.option('--structure', 'stage_structure', is_flag=True, help='Include structure analysis')
@click.option('--stems', 'stage_stems', is_flag=True, help='Include stem separation')
@click.option('--arrangement', 'stage_arrangement', is_flag=True, help='Include arrangement analysis')
@click.option('--embeddings', 'stage_embeddings', is_flag=True, help='Include embeddings')
@click.option('--full', is_flag=True, help='Run all analysis stages')
@click.pass_context
def analyze(ctx, youtube_id, all_pending, favorites, min_rating, stage_features, stage_structure,
            stage_stems, stage_arrangement, stage_embeddings, full):
    """Run analysis pipeline on track(s).

    Examples:
        yt-analyzer analyze dQw4w9WgXcQ
        yt-analyzer analyze dQw4w9WgXcQ --full
        yt-analyzer analyze --all-pending --features
        yt-analyzer analyze --favorites --features
        yt-analyzer analyze --min-rating 2 --features
    """
    repo = get_repo(ctx)

    if not repo.is_initialized():
        click.secho("Database not initialized. Run 'yt-analyzer db init' first.", fg='red')
        raise SystemExit(1)

    # Validation moved to track selection section below

    # Determine which stages to run
    if full:
        stages = ['features', 'structure', 'arrangement', 'stems', 'embeddings']
    elif not any([stage_features, stage_structure, stage_stems, stage_arrangement, stage_embeddings]):
        # Default: just features
        stages = ['features']
    else:
        stages = []
        if stage_features:
            stages.append('features')
        if stage_structure:
            stages.append('structure')
        if stage_arrangement:
            stages.append('arrangement')
        if stage_stems:
            stages.append('stems')
        if stage_embeddings:
            stages.append('embeddings')

    click.echo(f"Analysis stages: {', '.join(stages)}")
    click.echo()

    # Get tracks to analyze
    if all_pending or favorites or min_rating:
        tracks = repo.list_tracks(
            not_analyzed_only=all_pending,  # Only filter by not_analyzed if --all-pending
            favorites_only=favorites,
            min_rating=min_rating,
            limit=1000
        )
        if not tracks:
            click.echo("No tracks found matching criteria.")
            return
        youtube_ids = [t.youtube_id for t in tracks]
        click.echo(f"Found {len(youtube_ids)} track(s) to analyze")
    else:
        if not youtube_id:
            click.secho("Provide a YouTube ID, --all-pending, --favorites, or --min-rating", fg='red')
            raise SystemExit(1)
        youtube_ids = [youtube_id]

    verbose = ctx.obj.get('verbose', False)
    success_count = 0
    error_count = 0

    for yt_id in youtube_ids:
        track = repo.get_track_by_youtube_id(yt_id)
        if not track:
            click.secho(f"Track not found: {yt_id}", fg='red')
            error_count += 1
            continue

        click.echo(f"Analyzing: {track.title or yt_id}")

        if not track.local_path or not Path(track.local_path).exists():
            click.secho(f"  Audio file not found: {track.local_path}", fg='red')
            error_count += 1
            continue

        audio_path = Path(track.local_path)

        # Run feature extraction
        if 'features' in stages:
            click.echo("  Extracting features (BPM, key, loudness, spectral, stereo)...")

            def progress(msg):
                if verbose:
                    click.echo(f"    {msg}")

            try:
                all_features = extract_all_features(
                    audio_path,
                    progress_callback=progress,
                    skip_slow=not verbose  # Skip spectral in non-verbose mode for speed
                )

                # Display results
                if verbose:
                    click.echo()
                    click.echo(format_all_features(all_features, verbose=True))
                    click.echo()

                # Build YTFeatures for database
                yt_features = YTFeatures(
                    track_id=track.id,
                    bpm=all_features.rhythm.bpm if all_features.rhythm else None,
                    bpm_confidence=all_features.rhythm.bpm_confidence if all_features.rhythm else None,
                    key_name=f"{all_features.key.key}{' minor' if all_features.key.scale == 'minor' else ''}" if all_features.key else None,
                    key_camelot=all_features.key.camelot if all_features.key else None,
                    key_confidence=all_features.key.key_confidence if all_features.key else None,
                    integrated_lufs=all_features.loudness.integrated_lufs if all_features.loudness else None,
                    loudness_range_lu=all_features.loudness.loudness_range_lu if all_features.loudness else None,
                    true_peak_db=all_features.loudness.true_peak_dbtp if all_features.loudness else None,
                    dynamic_range_db=all_features.loudness.dynamic_range_db if all_features.loudness else None,
                    spectral_centroid_hz=all_features.spectral.spectral_centroid_hz if all_features.spectral else None,
                    spectral_rolloff_hz=all_features.spectral.spectral_rolloff_hz if all_features.spectral else None,
                    stereo_width=all_features.stereo.stereo_width if all_features.stereo else None,
                    stereo_correlation=all_features.stereo.correlation if all_features.stereo else None,
                    mono_compatible=all_features.stereo.mono_compatible if all_features.stereo else None
                )

                # Save to database
                saved, msg = repo.save_features(yt_features)
                if saved:
                    # Build quick summary
                    summary_parts = []
                    if all_features.rhythm:
                        summary_parts.append(f"{all_features.rhythm.bpm:.0f} BPM")
                    if all_features.key:
                        summary_parts.append(all_features.key.camelot)
                    if all_features.loudness:
                        summary_parts.append(f"{all_features.loudness.integrated_lufs:.1f} LUFS")

                    click.secho(f"  Features saved: {' | '.join(summary_parts)}", fg='green')
                else:
                    click.secho(f"  Failed to save: {msg}", fg='red')

                # Show any extraction errors
                if all_features.errors:
                    for err in all_features.errors:
                        click.secho(f"    Warning: {err}", fg='yellow')

            except ImportError as e:
                click.secho(f"  Missing dependency: {e}", fg='red')
                click.echo("  Install with: pip install -r requirements.txt")
                error_count += 1
                continue
            except Exception as e:
                click.secho(f"  Feature extraction failed: {e}", fg='red')
                error_count += 1
                continue

        # Structure analysis
        if 'structure' in stages:
            click.echo("  Detecting structure (sections, beats, bars)...")

            try:
                # Get BPM hint from features if we just extracted them
                bpm_hint = None
                if 'features' in stages and all_features and all_features.rhythm:
                    bpm_hint = all_features.rhythm.bpm

                structure = extract_structure(audio_path, bpm_hint=bpm_hint)

                if structure:
                    # Refine sections with energy analysis
                    if structure.sections:
                        structure.sections = refine_sections_with_energy(
                            structure.sections, audio_path
                        )

                    if verbose:
                        click.echo()
                        click.echo(format_structure_display(structure))
                        click.echo()

                    # Convert sections to YTSection objects
                    yt_sections = []
                    for i, section in enumerate(structure.sections):
                        yt_section = YTSection(
                            track_id=track.id,
                            section_type=section.section_type,
                            original_label=section.original_label,
                            start_time=section.start_time,
                            end_time=section.end_time,
                            start_bar=section.start_bar,
                            end_bar=section.end_bar,
                            duration_bars=section.duration_bars,
                            section_index=i
                        )
                        yt_sections.append(yt_section)

                    # Save sections
                    if yt_sections:
                        saved, msg = repo.save_sections(yt_sections)
                        if saved:
                            section_counts = {}
                            for s in structure.sections:
                                section_counts[s.section_type] = section_counts.get(s.section_type, 0) + 1

                            summary = ", ".join(f"{c} {t.lower()}{'s' if c > 1 else ''}"
                                              for t, c in section_counts.items())
                            click.secho(f"  Structure saved: {structure.total_bars} bars | {summary}", fg='green')
                        else:
                            click.secho(f"  Failed to save sections: {msg}", fg='red')

                    # Calculate arrangement stats
                    if structure.sections:
                        drops = [s for s in structure.sections if s.section_type == 'DROP']
                        breakdowns = [s for s in structure.sections if s.section_type == 'BREAKDOWN']
                        buildups = [s for s in structure.sections if s.section_type == 'BUILDUP']

                        arr_stats = YTArrangementStats(
                            track_id=track.id,
                            total_bars=structure.total_bars,
                            bars_to_first_drop=drops[0].start_bar if drops and drops[0].start_bar else None,
                            bars_to_first_breakdown=breakdowns[0].start_bar if breakdowns and breakdowns[0].start_bar else None,
                            num_drops=len(drops),
                            num_breakdowns=len(breakdowns),
                            num_buildups=len(buildups),
                            avg_drop_length_bars=sum(d.duration_bars or 0 for d in drops) / len(drops) if drops else None,
                            avg_breakdown_length_bars=sum(b.duration_bars or 0 for b in breakdowns) / len(breakdowns) if breakdowns else None,
                            avg_buildup_length_bars=sum(b.duration_bars or 0 for b in buildups) / len(buildups) if buildups else None,
                            max_buildup_length_bars=max((b.duration_bars or 0 for b in buildups), default=None) if buildups else None,
                            phrase_length_bars=16  # Default for trance
                        )

                        repo.save_arrangement_stats(arr_stats)

                    # Show warnings
                    if structure.errors:
                        for err in structure.errors:
                            click.secho(f"    Warning: {err}", fg='yellow')
                else:
                    click.secho("  Structure analysis failed", fg='yellow')

            except ImportError as e:
                click.secho(f"  Missing dependency for structure: {e}", fg='yellow')
                click.echo("  Install with: pip install allin1")
            except Exception as e:
                click.secho(f"  Structure analysis failed: {e}", fg='red')
                if verbose:
                    import traceback
                    traceback.print_exc()

        # Arrangement analysis (TODO)
        if 'arrangement' in stages:
            click.echo("  [TODO] Arrangement metrics (drops, breakdowns, risers)")

        # Stem separation (TODO)
        if 'stems' in stages:
            click.echo("  [TODO] Stem separation (demucs)")

        # Embeddings (TODO)
        if 'embeddings' in stages:
            click.echo("  [TODO] Embeddings (PANNs)")

        click.echo()
        success_count += 1

    # Summary
    click.echo()
    if success_count > 0:
        click.secho(f"Successfully analyzed {success_count} track(s)", fg='green')
    if error_count > 0:
        click.secho(f"Failed: {error_count} track(s)", fg='red')


# ==================== SEARCH COMMAND ====================

@cli.command('search')
@click.option('--similar-to', 'similar_to', help='Find tracks similar to this YouTube ID')
@click.option('--top', '-n', type=int, default=10, help='Number of results')
@click.pass_context
def search(ctx, similar_to, top):
    """Search for similar tracks.

    Examples:
        yt-analyzer search --similar-to dQw4w9WgXcQ --top 5
    """
    repo = get_repo(ctx)

    if not repo.is_initialized():
        click.secho("Database not initialized. Run 'yt-analyzer db init' first.", fg='red')
        raise SystemExit(1)

    if not similar_to:
        click.secho("Provide --similar-to with a YouTube ID", fg='red')
        raise SystemExit(1)

    # TODO: Implement similarity search using embeddings
    click.secho("Similarity search not yet implemented. Coming soon!", fg='yellow')
    click.echo()
    click.echo("This feature requires:")
    click.echo("  1. Run 'yt-analyzer analyze <id> --embeddings' on tracks")
    click.echo("  2. Use cosine similarity to find nearest neighbors")


# ==================== EXPORT COMMAND ====================

@cli.command('export')
@click.option('--all', 'export_all', is_flag=True, help='Export all tracks')
@click.option('--track', 'track_id', help='Export specific track')
@click.option('--format', 'fmt', type=click.Choice(['csv', 'json']), default='csv')
@click.option('--output', '-o', type=click.Path(), help='Output file')
@click.pass_context
def export(ctx, export_all, track_id, fmt, output):
    """Export track data.

    Examples:
        yt-analyzer export --all --format csv -o tracks.csv
        yt-analyzer export --track dQw4w9WgXcQ --format json
    """
    repo = get_repo(ctx)

    if not repo.is_initialized():
        click.secho("Database not initialized. Run 'yt-analyzer db init' first.", fg='red')
        raise SystemExit(1)

    if not export_all and not track_id:
        click.secho("Specify --all or --track <id>", fg='red')
        raise SystemExit(1)

    # TODO: Implement export
    click.secho("Export not yet implemented. Coming soon!", fg='yellow')


# ==================== MAIN ====================

if __name__ == '__main__':
    cli()
