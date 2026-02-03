"""Terminal emulation using pyte."""

from dataclasses import dataclass
from datetime import datetime

import pyte

from reterm.output.models import StyledChar, TerminalSnapshot


@dataclass
class TerminalConfig:
    """Configuration for terminal emulator."""

    rows: int = 24
    cols: int = 80


class Terminal:
    """Terminal emulator wrapper around pyte."""

    def __init__(self, config: TerminalConfig | None = None) -> None:
        self.config = config or TerminalConfig()
        self.screen = pyte.Screen(self.config.cols, self.config.rows)
        self.stream = pyte.Stream(self.screen)
        self._history: list[TerminalSnapshot] = []

    def feed(self, data: str) -> None:
        """Feed data to the terminal emulator.

        This processes escape sequences and updates the screen state.
        """
        self.stream.feed(data)

    def get_lines(self) -> list[str]:
        """Get current screen content as list of lines."""
        return [line.rstrip() for line in self.screen.display]

    def get_text(self) -> str:
        """Get current screen content as single string."""
        return "\n".join(self.get_lines())

    def get_cursor_position(self) -> tuple[int, int]:
        """Get current cursor position as (row, col)."""
        return (self.screen.cursor.y, self.screen.cursor.x)

    def get_dimensions(self) -> tuple[int, int]:
        """Get terminal dimensions as (rows, cols)."""
        return (self.config.rows, self.config.cols)

    def snapshot(self, include_styles: bool = True) -> TerminalSnapshot:
        """Create a snapshot of current terminal state.

        Args:
            include_styles: Whether to include per-character style data.
                Defaults to True. Set to False for internal probes where
                style data is not needed.
        """
        lines = self.get_lines()

        styled_content = None
        if include_styles:
            styled_content = self._build_styled_content()

        return TerminalSnapshot(
            timestamp=datetime.now(),
            cursor_position=self.get_cursor_position(),
            screen_content=lines,
            screen_content_plain="\n".join(lines),
            dimensions=self.get_dimensions(),
            styled_content=styled_content,
        )

    def _build_styled_content(self) -> list[list[StyledChar]]:
        """Build per-character styled content from the pyte screen buffer.

        Trims trailing default-styled spaces from each line for compact serialization.
        """
        styled_lines: list[list[StyledChar]] = []
        for row in range(self.config.rows):
            line: list[StyledChar] = []
            for col in range(self.config.cols):
                char_data = self.screen.buffer[row][col]
                line.append(
                    StyledChar(
                        char=char_data.data,
                        fg=char_data.fg if char_data.fg != "default" else "default",
                        bg=char_data.bg if char_data.bg != "default" else "default",
                        bold=bool(char_data.bold),
                        italic=bool(char_data.italics),
                        underline=bool(char_data.underscore),
                        reverse=bool(char_data.reverse),
                    )
                )
            # Trim trailing default-styled whitespace for compact JSON
            while (
                line
                and line[-1].char == " "
                and line[-1].fg == "default"
                and line[-1].bg == "default"
                and not line[-1].bold
                and not line[-1].italic
                and not line[-1].underline
                and not line[-1].reverse
            ):
                line.pop()
            styled_lines.append(line)
        return styled_lines

    def save_snapshot(self) -> TerminalSnapshot:
        """Create and save a snapshot to history."""
        snapshot = self.snapshot()
        self._history.append(snapshot)
        return snapshot

    def get_history(self) -> list[TerminalSnapshot]:
        """Get all saved snapshots."""
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear saved snapshots."""
        self._history.clear()

    def resize(self, rows: int, cols: int) -> None:
        """Resize the terminal."""
        self.screen.resize(rows, cols)
        self.config.rows = rows
        self.config.cols = cols

    def reset(self) -> None:
        """Reset terminal to initial state."""
        self.screen.reset()
        self._history.clear()

    def get_dirty_lines(self) -> set[int]:
        """Get line numbers that have changed since last check."""
        dirty = self.screen.dirty.copy()
        self.screen.dirty.clear()
        return dirty

    def has_changes(self) -> bool:
        """Check if screen has pending changes."""
        return len(self.screen.dirty) > 0

    def get_line(self, row: int) -> str:
        """Get a specific line by row number."""
        if 0 <= row < self.config.rows:
            return self.screen.display[row].rstrip()
        return ""

    def get_char_at(self, row: int, col: int) -> str:
        """Get character at specific position."""
        if 0 <= row < self.config.rows and 0 <= col < self.config.cols:
            return self.screen.buffer[row][col].data
        return ""

    def get_styled_char_at(
        self, row: int, col: int
    ) -> tuple[str, dict[str, object]]:
        """Get character and its style at specific position.

        Returns (char, style_dict) where style_dict contains:
        - fg: foreground color
        - bg: background color
        - bold: bool
        - italics: bool
        - underscore: bool
        - reverse: bool
        """
        if 0 <= row < self.config.rows and 0 <= col < self.config.cols:
            char_data = self.screen.buffer[row][col]
            style = {
                "fg": char_data.fg,
                "bg": char_data.bg,
                "bold": char_data.bold,
                "italics": char_data.italics,
                "underscore": char_data.underscore,
                "reverse": char_data.reverse,
            }
            return (char_data.data, style)
        return ("", {})

    def get_styled_lines(self) -> list[list[tuple[str, dict[str, object]]]]:
        """Get all lines with character styles.

        Returns list of lines, where each line is a list of (char, style) tuples.
        """
        lines = []
        for row in range(self.config.rows):
            line = []
            for col in range(self.config.cols):
                char, style = self.get_styled_char_at(row, col)
                line.append((char, style))
            lines.append(line)
        return lines
