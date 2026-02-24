"""
Live DAW Control Package.

State tracking and device resolution for Claude Code conversations with Ableton.
Claude uses MCP tools directly to communicate with Ableton.
This package provides:
- Change tracking for undo/redo and A/B comparison
- Device resolution (map names to indices)
- Value conversions (Hz, dB, ms to normalized 0.0-1.0)

Usage (in Claude Code conversation):
    1. Claude calls MCP tools: get_track_names, set_device_parameter, etc.
    2. Claude uses DeviceResolver to map "Bass" -> track_index 1
    3. Claude uses conversions to map "100Hz" -> 0.30 normalized
    4. Claude records changes for undo capability
    5. User says "undo" - Claude looks up previous value and calls MCP to revert
"""

from .state import (
    ChangeTracker,
    Change,
    ABComparison,
    get_tracker,
    record_change,
    get_undo_info,
    confirm_undo,
    get_session_summary,
    clear_session,
)

from .resolver import (
    DeviceResolver,
    ResolvedFix,
    get_resolver,
    reset_resolver,
)

from .conversions import (
    # Frequency
    hz_to_normalized,
    normalized_to_hz,
    # Gain/dB
    db_to_normalized,
    normalized_to_db,
    # Time
    ms_to_normalized,
    normalized_to_ms,
    # Ratio
    ratio_to_normalized,
    normalized_to_ratio,
    # Volume fader
    volume_db_to_normalized,
    normalized_to_volume_db,
    # Q factor
    q_to_normalized,
    normalized_to_q,
    # Percentage
    percent_to_normalized,
    normalized_to_percent,
    # Auto-detection
    detect_parameter_type,
    convert_to_normalized,
    convert_from_normalized,
)

from .reference_integration import (
    ReferenceIntegration,
    FeatureGap,
    GapAnalysis,
    get_reference_integration,
    load_default_profile,
)

from .errors import (
    CoachingError,
    ErrorCategory,
    RecoveryAction,
    ErrorHandler,
    # Factory functions
    connection_error,
    ableton_not_running,
    osc_daemon_not_running,
    track_not_found,
    device_not_found,
    parameter_not_found,
    mcp_timeout,
    mcp_error,
    analysis_failed,
    reference_not_loaded,
    reference_feature_missing,
    invalid_value,
    session_corrupted,
    internal_error,
    # Helpers
    format_manual_instructions,
    can_retry,
    get_fallback_action,
    get_error_handler,
)

__version__ = "1.3.0"

__all__ = [
    # State tracking
    "ChangeTracker",
    "Change",
    "ABComparison",
    "get_tracker",
    "record_change",
    "get_undo_info",
    "confirm_undo",
    "get_session_summary",
    "clear_session",
    # Device resolution
    "DeviceResolver",
    "ResolvedFix",
    "get_resolver",
    "reset_resolver",
    # Conversions
    "hz_to_normalized",
    "normalized_to_hz",
    "db_to_normalized",
    "normalized_to_db",
    "ms_to_normalized",
    "normalized_to_ms",
    "ratio_to_normalized",
    "normalized_to_ratio",
    "volume_db_to_normalized",
    "normalized_to_volume_db",
    "q_to_normalized",
    "normalized_to_q",
    "percent_to_normalized",
    "normalized_to_percent",
    "detect_parameter_type",
    "convert_to_normalized",
    "convert_from_normalized",
    # Reference integration
    "ReferenceIntegration",
    "FeatureGap",
    "GapAnalysis",
    "get_reference_integration",
    "load_default_profile",
    # Error handling
    "CoachingError",
    "ErrorCategory",
    "RecoveryAction",
    "ErrorHandler",
    "connection_error",
    "ableton_not_running",
    "osc_daemon_not_running",
    "track_not_found",
    "device_not_found",
    "parameter_not_found",
    "mcp_timeout",
    "mcp_error",
    "analysis_failed",
    "reference_not_loaded",
    "reference_feature_missing",
    "invalid_value",
    "session_corrupted",
    "internal_error",
    "format_manual_instructions",
    "can_retry",
    "get_fallback_action",
    "get_error_handler",
]
