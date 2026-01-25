"""
CLI Formatter - Rich terminal output for ALS Doctor

Provides consistent color coding and formatting for all CLI output.
Supports graceful fallback when rich is unavailable or --no-color is set.

Color Scheme:
    Grades: A=green, B=cyan, C=yellow, D=orange/bright_red, F=red
    Severity: Critical=red, Warning=yellow, Suggestion=cyan
    Status: Success=green, Error=red, Info=blue
"""

import os
import sys
from typing import Optional, List, Tuple, Any
from dataclasses import dataclass
from contextlib import contextmanager

# Try to import rich, fallback to plain text if unavailable
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.style import Style
    from rich.theme import Theme
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# Color scheme constants
GRADE_COLORS = {
    'A': 'green',
    'B': 'cyan',
    'C': 'yellow',
    'D': 'orange3',  # rich uses orange3, click uses bright_red
    'F': 'red',
}

SEVERITY_COLORS = {
    'critical': 'red',
    'warning': 'yellow',
    'suggestion': 'cyan',
    'info': 'blue',
}

TREND_COLORS = {
    'up': 'green',
    'down': 'red',
    'stable': 'white',
    'new': 'cyan',
}

TREND_SYMBOLS = {
    'up': '[up]',
    'down': '[down]',
    'stable': '[stable]',
    'new': '[new]',
}

# Custom theme for rich console
CUSTOM_THEME = Theme({
    'grade.a': 'bold green',
    'grade.b': 'bold cyan',
    'grade.c': 'bold yellow',
    'grade.d': 'bold orange3',
    'grade.f': 'bold red',
    'severity.critical': 'bold red',
    'severity.warning': 'bold yellow',
    'severity.suggestion': 'cyan',
    'status.success': 'bold green',
    'status.error': 'bold red',
    'status.info': 'blue',
    'trend.up': 'green',
    'trend.down': 'red',
    'trend.stable': 'white',
    'trend.new': 'cyan',
    'header': 'bold',
    'dim': 'dim',
    'highlight': 'bold yellow',
})


@dataclass
class FormatterConfig:
    """Configuration for CLI output formatting."""
    no_color: bool = False
    force_terminal: bool = False
    width: Optional[int] = None


class CLIFormatter:
    """
    Formatter class for consistent CLI output.

    Handles color coding, tables, and formatting with graceful
    fallback when rich is unavailable or colors are disabled.
    """

    def __init__(self, config: Optional[FormatterConfig] = None):
        self.config = config or FormatterConfig()
        self._console: Optional[Any] = None
        self._setup_console()

    def _setup_console(self):
        """Initialize the rich console or set up fallback mode."""
        # Detect if we should disable colors
        no_color = (
            self.config.no_color or
            os.environ.get('NO_COLOR', '').lower() in ('1', 'true', 'yes') or
            os.environ.get('ALS_DOCTOR_NO_COLOR', '').lower() in ('1', 'true', 'yes')
        )

        if RICH_AVAILABLE and not no_color:
            self._console = Console(
                theme=CUSTOM_THEME,
                force_terminal=self.config.force_terminal,
                width=self.config.width,
            )
            self._use_rich = True
        else:
            self._use_rich = False

    @property
    def use_rich(self) -> bool:
        """Check if rich formatting is enabled."""
        return self._use_rich

    def disable_colors(self):
        """Disable color output."""
        self.config.no_color = True
        self._use_rich = False

    def enable_colors(self):
        """Enable color output if rich is available."""
        if RICH_AVAILABLE:
            self.config.no_color = False
            self._setup_console()

    # === Basic Output ===

    def print(self, text: str = "", style: Optional[str] = None):
        """Print text with optional styling."""
        if self._use_rich and self._console:
            self._console.print(text, style=style)
        else:
            print(text)

    def print_line(self, char: str = "-", width: int = 50):
        """Print a horizontal line."""
        self.print(char * width)

    # === Styled Text ===

    def grade_text(self, grade: str, include_brackets: bool = True) -> str:
        """Format a grade letter with appropriate color."""
        grade_upper = grade.upper()
        text = f"[{grade_upper}]" if include_brackets else grade_upper

        if self._use_rich:
            style = f"grade.{grade_upper.lower()}"
            return f"[{style}]{text}[/{style}]"
        return text

    def grade_with_score(self, score: int, grade: str) -> str:
        """Format score with colored grade, e.g. '85 [A]'."""
        grade_text = self.grade_text(grade)
        if self._use_rich:
            return f"{score:>3} {grade_text}"
        return f"{score:>3} [{grade}]"

    def severity_text(self, severity: str, text: str) -> str:
        """Format text with severity-based color."""
        severity_lower = severity.lower()

        if self._use_rich:
            style = f"severity.{severity_lower}"
            return f"[{style}]{text}[/{style}]"
        return text

    def trend_text(self, trend: str) -> str:
        """Format trend indicator with color."""
        symbol = TREND_SYMBOLS.get(trend, '[?]')

        if self._use_rich:
            style = f"trend.{trend}"
            return f"[{style}]{symbol}[/{style}]"
        return symbol

    def delta_text(self, delta: int) -> str:
        """Format a delta value with +/- and color."""
        if delta > 0:
            text = f"+{delta}"
            style = "green" if self._use_rich else None
        elif delta < 0:
            text = str(delta)
            style = "red" if self._use_rich else None
        else:
            text = "0"
            style = None

        if self._use_rich and style:
            return f"[{style}]{text}[/{style}]"
        return text

    # === Status Messages ===

    def success(self, message: str, prefix: str = "SUCCESS: "):
        """Print a success message."""
        if self._use_rich and self._console:
            self._console.print(f"[status.success]{prefix}[/status.success]{message}")
        else:
            print(f"{prefix}{message}")

    def error(self, message: str, prefix: str = "ERROR: "):
        """Print an error message."""
        if self._use_rich and self._console:
            self._console.print(f"[status.error]{prefix}[/status.error]{message}")
        else:
            print(f"{prefix}{message}", file=sys.stderr)

    def warning(self, message: str, prefix: str = "WARNING: "):
        """Print a warning message."""
        if self._use_rich and self._console:
            self._console.print(f"[severity.warning]{prefix}[/severity.warning]{message}")
        else:
            print(f"{prefix}{message}")

    def info(self, message: str):
        """Print an info message."""
        if self._use_rich and self._console:
            self._console.print(f"[status.info]{message}[/status.info]")
        else:
            print(message)

    # === Headers & Sections ===

    def header(self, text: str, style: str = "header"):
        """Print a header."""
        if self._use_rich and self._console:
            self._console.print(f"[{style}]{text}[/{style}]")
        else:
            print(text)

    def section_header(self, text: str, char: str = "=", width: int = 50):
        """Print a section header with decorative lines."""
        self.print(char * width)
        self.header(f"  {text}")
        self.print(char * width)

    def panel(self, content: str, title: Optional[str] = None,
              border_style: str = "blue"):
        """Print content in a panel/box."""
        if self._use_rich and self._console:
            panel = Panel(content, title=title, border_style=border_style)
            self._console.print(panel)
        else:
            width = 50
            self.print("+" + "-" * (width - 2) + "+")
            if title:
                self.print(f"| {title.center(width - 4)} |")
                self.print("+" + "-" * (width - 2) + "+")
            for line in content.split('\n'):
                self.print(f"| {line.ljust(width - 4)} |")
            self.print("+" + "-" * (width - 2) + "+")

    # === Tables ===

    def create_table(self, title: Optional[str] = None,
                     show_header: bool = True) -> 'TableBuilder':
        """Create a table builder for structured output."""
        return TableBuilder(self, title=title, show_header=show_header)

    # === Health Score Display ===

    def health_score_display(self, score: int, grade: str):
        """Display a prominent health score with grade."""
        if self._use_rich and self._console:
            grade_style = f"grade.{grade.lower()}"
            text = Text()
            text.append("  HEALTH SCORE: ", style="bold")
            text.append(f"{score}/100 ", style=grade_style)
            text.append(f"[{grade}]", style=grade_style)
            self._console.print(text)
        else:
            self.print(f"  HEALTH SCORE: {score}/100 [{grade}]")

    # === Issue Display ===

    def issue(self, severity: str, description: str,
              track_name: Optional[str] = None,
              fix_suggestion: Optional[str] = None):
        """Display a single issue with appropriate formatting."""
        prefix_map = {
            'critical': '!',
            'warning': '?',
            'suggestion': '-',
            'info': '*',
        }
        prefix = prefix_map.get(severity.lower(), '*')

        track_text = f"[{track_name}] " if track_name else ""

        if self._use_rich and self._console:
            style = f"severity.{severity.lower()}"
            self._console.print(f"  [{style}]{prefix}[/{style}] {track_text}{description}")
            if fix_suggestion:
                self._console.print(f"    [dim]{fix_suggestion}[/dim]")
        else:
            print(f"  {prefix} {track_text}{description}")
            if fix_suggestion:
                print(f"    -> {fix_suggestion}")

    # === Progress & ASCII Charts ===

    def grade_bar(self, grade: str, count: int, total: int,
                  max_width: int = 20) -> str:
        """Generate a colored ASCII bar for grade distribution."""
        if total == 0:
            return ""

        percentage = (count / total) * 100
        bar_length = int((count / total) * max_width) if total > 0 else 0
        bar = "=" * bar_length

        if self._use_rich:
            color = GRADE_COLORS.get(grade, 'white')
            return f"[{color}]{bar}[/{color}]"
        return bar

    def progress_bar(self, current: int, total: int,
                     width: int = 30,
                     filled_char: str = "=",
                     empty_char: str = " ") -> str:
        """Generate a simple progress bar."""
        if total == 0:
            return f"[{empty_char * width}]"

        filled = int((current / total) * width)
        bar = filled_char * filled + empty_char * (width - filled)

        if self._use_rich:
            return f"[green]{bar[:filled]}[/green]{bar[filled:]}"
        return f"[{bar}]"


class TableBuilder:
    """Builder for creating formatted tables."""

    def __init__(self, formatter: CLIFormatter,
                 title: Optional[str] = None,
                 show_header: bool = True):
        self.formatter = formatter
        self.title = title
        self.show_header = show_header
        self.columns: List[Tuple[str, str, Optional[str]]] = []  # (header, justify, style)
        self.rows: List[List[str]] = []

    def add_column(self, header: str, justify: str = "left",
                   style: Optional[str] = None) -> 'TableBuilder':
        """Add a column to the table."""
        self.columns.append((header, justify, style))
        return self

    def add_row(self, *values) -> 'TableBuilder':
        """Add a row to the table."""
        self.rows.append(list(values))
        return self

    def render(self):
        """Render the table to the console."""
        if self.formatter.use_rich and RICH_AVAILABLE:
            self._render_rich()
        else:
            self._render_plain()

    def _render_rich(self):
        """Render using rich Table."""
        table = Table(title=self.title, show_header=self.show_header)

        for header, justify, style in self.columns:
            table.add_column(header, justify=justify, style=style)

        for row in self.rows:
            table.add_row(*row)

        if self.formatter._console:
            self.formatter._console.print(table)

    def _render_plain(self):
        """Render as plain text."""
        if self.title:
            print(self.title)
            print()

        if not self.columns:
            return

        # Calculate column widths
        widths = []
        for i, (header, _, _) in enumerate(self.columns):
            col_values = [header] + [row[i] if i < len(row) else "" for row in self.rows]
            # Strip ANSI codes for width calculation
            widths.append(max(len(self._strip_markup(str(v))) for v in col_values))

        # Print header
        if self.show_header:
            header_row = "  ".join(
                self._justify(col[0], widths[i], col[1])
                for i, col in enumerate(self.columns)
            )
            print(header_row)
            print("-" * len(header_row))

        # Print rows
        for row in self.rows:
            row_str = "  ".join(
                self._justify(str(row[i]) if i < len(row) else "", widths[i], self.columns[i][1])
                for i in range(len(self.columns))
            )
            print(row_str)

    def _justify(self, text: str, width: int, align: str) -> str:
        """Justify text to the given width."""
        # Strip markup for plain text
        clean_text = self._strip_markup(text)
        padding = width - len(clean_text)

        if align == "right":
            return " " * padding + text
        elif align == "center":
            left = padding // 2
            right = padding - left
            return " " * left + text + " " * right
        else:  # left
            return text + " " * padding

    def _strip_markup(self, text: str) -> str:
        """Remove rich markup tags from text."""
        import re
        # Remove [tag] and [/tag] patterns
        return re.sub(r'\[/?[^\]]+\]', '', str(text))


# === Global Formatter Instance ===

_formatter: Optional[CLIFormatter] = None


def get_formatter(no_color: bool = False) -> CLIFormatter:
    """Get or create the global formatter instance."""
    global _formatter

    if _formatter is None:
        _formatter = CLIFormatter(FormatterConfig(no_color=no_color))
    elif no_color and _formatter.use_rich:
        _formatter.disable_colors()
    elif not no_color and not _formatter.use_rich and RICH_AVAILABLE:
        _formatter.enable_colors()

    return _formatter


def reset_formatter():
    """Reset the global formatter instance."""
    global _formatter
    _formatter = None


@contextmanager
def no_color_context():
    """Context manager for temporarily disabling colors."""
    formatter = get_formatter()
    was_rich = formatter.use_rich
    formatter.disable_colors()
    try:
        yield formatter
    finally:
        if was_rich:
            formatter.enable_colors()


# === Convenience Functions ===

def print_success(message: str):
    """Print a success message."""
    get_formatter().success(message)


def print_error(message: str):
    """Print an error message."""
    get_formatter().error(message)


def print_warning(message: str):
    """Print a warning message."""
    get_formatter().warning(message)


def format_grade(grade: str) -> str:
    """Format a grade with color."""
    return get_formatter().grade_text(grade)


def format_severity(severity: str, text: str) -> str:
    """Format text with severity color."""
    return get_formatter().severity_text(severity, text)


def format_trend(trend: str) -> str:
    """Format a trend indicator."""
    return get_formatter().trend_text(trend)


def format_delta(delta: int) -> str:
    """Format a delta value."""
    return get_formatter().delta_text(delta)
