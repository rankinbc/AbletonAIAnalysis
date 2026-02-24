"""
Error Handling for Live DAW Control.

Provides structured error types, recovery strategies, and user-friendly messages
for the coaching pipeline.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum


class ErrorCategory(Enum):
    """Categories of errors in the coaching pipeline."""
    CONNECTION = "connection"       # Ableton/OSC connection issues
    RESOLUTION = "resolution"       # Track/device/parameter not found
    MCP = "mcp"                     # MCP tool failures
    ANALYSIS = "analysis"           # Audio/ALS analysis failures
    REFERENCE = "reference"         # Reference profile issues
    STATE = "state"                 # Session state issues
    VALIDATION = "validation"       # Invalid input/values
    INTERNAL = "internal"           # Unexpected errors


class RecoveryAction(Enum):
    """Possible recovery actions."""
    RETRY = "retry"                 # Try the operation again
    REFRESH = "refresh"             # Refresh caches/state
    RECONNECT = "reconnect"         # Reconnect to Ableton
    MANUAL = "manual"               # Provide manual instructions
    SKIP = "skip"                   # Skip this operation
    ABORT = "abort"                 # Cannot recover


@dataclass
class CoachingError:
    """
    Structured error for the coaching pipeline.

    Provides user-friendly messages and recovery suggestions.
    """
    category: ErrorCategory
    message: str                     # User-friendly message
    technical_detail: Optional[str]  # Technical info for debugging
    recovery_action: RecoveryAction
    recovery_hint: Optional[str]     # Specific recovery instructions
    context: Dict[str, Any] = None   # Additional context

    def __post_init__(self):
        if self.context is None:
            self.context = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category.value,
            'message': self.message,
            'technical_detail': self.technical_detail,
            'recovery_action': self.recovery_action.value,
            'recovery_hint': self.recovery_hint,
            'context': self.context
        }

    def __str__(self) -> str:
        parts = [self.message]
        if self.recovery_hint:
            parts.append(f"Recovery: {self.recovery_hint}")
        return " | ".join(parts)


# =============================================================================
# Error Factory Functions
# =============================================================================

def connection_error(detail: str = None) -> CoachingError:
    """Create a connection error."""
    return CoachingError(
        category=ErrorCategory.CONNECTION,
        message="Cannot connect to Ableton Live",
        technical_detail=detail,
        recovery_action=RecoveryAction.RECONNECT,
        recovery_hint="Ensure Ableton is running with AbletonOSC installed and the OSC daemon is active"
    )


def ableton_not_running() -> CoachingError:
    """Ableton Live is not running."""
    return CoachingError(
        category=ErrorCategory.CONNECTION,
        message="Ableton Live is not running",
        technical_detail=None,
        recovery_action=RecoveryAction.MANUAL,
        recovery_hint="Start Ableton Live and open your project, then try again"
    )


def osc_daemon_not_running() -> CoachingError:
    """OSC daemon is not running."""
    return CoachingError(
        category=ErrorCategory.CONNECTION,
        message="OSC daemon is not running",
        technical_detail="Could not connect to OSC daemon on port 65432",
        recovery_action=RecoveryAction.MANUAL,
        recovery_hint="Start the OSC daemon: python osc_daemon.py"
    )


def track_not_found(track_name: str, available: List[str] = None) -> CoachingError:
    """Track was not found."""
    hint = f"Track '{track_name}' not found"
    if available:
        hint += f". Available tracks: {', '.join(available[:5])}"
        if len(available) > 5:
            hint += f" (+{len(available) - 5} more)"

    return CoachingError(
        category=ErrorCategory.RESOLUTION,
        message=f"Track '{track_name}' not found in Ableton",
        technical_detail=None,
        recovery_action=RecoveryAction.REFRESH,
        recovery_hint="The track may have been renamed or deleted. Refresh track list and try again.",
        context={'track_name': track_name, 'available': available}
    )


def device_not_found(track_name: str, device_name: str, available: List[str] = None) -> CoachingError:
    """Device was not found on track."""
    hint = f"Device '{device_name}' not found on track '{track_name}'"
    if available:
        hint += f". Available devices: {', '.join(available)}"

    return CoachingError(
        category=ErrorCategory.RESOLUTION,
        message=f"Device '{device_name}' not found on '{track_name}'",
        technical_detail=None,
        recovery_action=RecoveryAction.MANUAL,
        recovery_hint="The device may have been removed. Check the track's device chain.",
        context={'track_name': track_name, 'device_name': device_name, 'available': available}
    )


def parameter_not_found(device_name: str, param_name: str) -> CoachingError:
    """Parameter was not found on device."""
    return CoachingError(
        category=ErrorCategory.RESOLUTION,
        message=f"Parameter '{param_name}' not found on '{device_name}'",
        technical_detail=None,
        recovery_action=RecoveryAction.MANUAL,
        recovery_hint="Parameter names may vary by device version. Query device parameters to find the correct name.",
        context={'device_name': device_name, 'parameter_name': param_name}
    )


def mcp_timeout(operation: str) -> CoachingError:
    """MCP operation timed out."""
    return CoachingError(
        category=ErrorCategory.MCP,
        message=f"Operation timed out: {operation}",
        technical_detail="MCP request did not receive a response within 5 seconds",
        recovery_action=RecoveryAction.RETRY,
        recovery_hint="Ableton may be busy. Wait a moment and try again."
    )


def mcp_error(operation: str, error_msg: str) -> CoachingError:
    """MCP operation failed."""
    return CoachingError(
        category=ErrorCategory.MCP,
        message=f"Failed to {operation}",
        technical_detail=error_msg,
        recovery_action=RecoveryAction.RETRY,
        recovery_hint="Check if Ableton is responsive and try again."
    )


def analysis_failed(file_path: str, reason: str) -> CoachingError:
    """Audio/ALS analysis failed."""
    return CoachingError(
        category=ErrorCategory.ANALYSIS,
        message=f"Could not analyze file",
        technical_detail=reason,
        recovery_action=RecoveryAction.MANUAL,
        recovery_hint="Ensure the file exists and is a valid Ableton project or audio file.",
        context={'file_path': file_path}
    )


def reference_not_loaded() -> CoachingError:
    """Reference profile not loaded."""
    return CoachingError(
        category=ErrorCategory.REFERENCE,
        message="No reference profile loaded",
        technical_detail=None,
        recovery_action=RecoveryAction.MANUAL,
        recovery_hint="Load a reference profile first: integration.load_profile('path/to/profile.json')"
    )


def reference_feature_missing(feature: str) -> CoachingError:
    """Feature not in reference profile."""
    return CoachingError(
        category=ErrorCategory.REFERENCE,
        message=f"Feature '{feature}' not in reference profile",
        technical_detail=None,
        recovery_action=RecoveryAction.SKIP,
        recovery_hint="This feature is not tracked in the current reference profile."
    )


def invalid_value(param: str, value: Any, expected: str) -> CoachingError:
    """Invalid parameter value."""
    return CoachingError(
        category=ErrorCategory.VALIDATION,
        message=f"Invalid value for {param}: {value}",
        technical_detail=f"Expected: {expected}",
        recovery_action=RecoveryAction.MANUAL,
        recovery_hint=f"Provide a valid value. Expected: {expected}"
    )


def session_corrupted() -> CoachingError:
    """Session state is corrupted."""
    return CoachingError(
        category=ErrorCategory.STATE,
        message="Session state is corrupted",
        technical_detail=None,
        recovery_action=RecoveryAction.MANUAL,
        recovery_hint="Clear the session with clear_session() and start fresh."
    )


def internal_error(detail: str) -> CoachingError:
    """Unexpected internal error."""
    return CoachingError(
        category=ErrorCategory.INTERNAL,
        message="An unexpected error occurred",
        technical_detail=detail,
        recovery_action=RecoveryAction.ABORT,
        recovery_hint="This is a bug. Please report it with the technical details."
    )


# =============================================================================
# Error Recovery Helpers
# =============================================================================

def format_manual_instructions(
    operation: str,
    track_name: str = None,
    device_name: str = None,
    parameter_name: str = None,
    value: Any = None,
    display_value: str = None
) -> str:
    """
    Generate manual instructions when automatic fix fails.

    Returns formatted instructions for the user to apply the fix manually.
    """
    lines = [f"Manual steps to {operation}:"]
    step = 1

    if track_name:
        lines.append(f"{step}. Select the '{track_name}' track")
        step += 1

    if device_name:
        lines.append(f"{step}. Find the '{device_name}' device")
        step += 1

    if parameter_name and value is not None:
        val_str = display_value if display_value else str(value)
        lines.append(f"{step}. Set '{parameter_name}' to {val_str}")
        step += 1

    return "\n".join(lines)


def can_retry(error: CoachingError) -> bool:
    """Check if an error is retriable."""
    return error.recovery_action in (RecoveryAction.RETRY, RecoveryAction.REFRESH, RecoveryAction.RECONNECT)


def get_fallback_action(error: CoachingError) -> str:
    """Get suggested fallback action for an error."""
    fallbacks = {
        ErrorCategory.CONNECTION: "Switch to manual mode - I'll provide instructions you can follow in Ableton",
        ErrorCategory.RESOLUTION: "Let me query Ableton for the current track/device names",
        ErrorCategory.MCP: "I'll provide manual instructions instead",
        ErrorCategory.ANALYSIS: "Try with a different file or check file permissions",
        ErrorCategory.REFERENCE: "Continue without reference comparison",
        ErrorCategory.STATE: "Start a fresh session",
        ErrorCategory.VALIDATION: "Please provide a corrected value",
        ErrorCategory.INTERNAL: "Report this issue"
    }
    return fallbacks.get(error.category, "Try again or contact support")


# =============================================================================
# Error Handler Class
# =============================================================================

class ErrorHandler:
    """
    Handles errors in the coaching pipeline with logging and recovery.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.error_log: List[CoachingError] = []

    def handle(self, error: CoachingError) -> str:
        """
        Handle an error and return a user-friendly message.
        """
        self.error_log.append(error)

        if self.verbose:
            return self._format_verbose(error)
        return self._format_simple(error)

    def _format_simple(self, error: CoachingError) -> str:
        """Simple error format."""
        parts = [error.message]
        if error.recovery_hint:
            parts.append(error.recovery_hint)
        return ". ".join(parts)

    def _format_verbose(self, error: CoachingError) -> str:
        """Verbose error format with technical details."""
        lines = [
            f"Error: {error.message}",
            f"Category: {error.category.value}",
        ]
        if error.technical_detail:
            lines.append(f"Detail: {error.technical_detail}")
        lines.append(f"Recovery: {error.recovery_action.value}")
        if error.recovery_hint:
            lines.append(f"Hint: {error.recovery_hint}")
        return "\n".join(lines)

    def get_recent_errors(self, count: int = 5) -> List[CoachingError]:
        """Get most recent errors."""
        return self.error_log[-count:]

    def clear(self) -> None:
        """Clear error log."""
        self.error_log.clear()

    @property
    def has_errors(self) -> bool:
        return len(self.error_log) > 0

    @property
    def error_count(self) -> int:
        return len(self.error_log)


# Global error handler
_handler: Optional[ErrorHandler] = None


def get_error_handler(verbose: bool = False) -> ErrorHandler:
    """Get or create the global error handler."""
    global _handler
    if _handler is None:
        _handler = ErrorHandler(verbose=verbose)
    return _handler
