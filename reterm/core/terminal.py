"""Terminal emulation using pyte.

Extends pyte with:
- Alternate screen buffer support (for tmux, vim, etc.)
- Proper DEC line drawing charset handling
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pyte
from pyte.screens import StaticDefaultDict

from reterm.output.models import StyledChar, TerminalSnapshot

if TYPE_CHECKING:
    # For type-checking, treat the mixin as a pyte.Screen subclass so the
    # checker sees cursor/buffer/lines/columns/set_mode/etc. At runtime it bases
    # on object; the real MRO is Screen(AltScreenMixin, pyte.Screen), so super()
    # resolves to pyte.Screen regardless.
    _ScreenBase = pyte.Screen
else:
    _ScreenBase = object


# Alternate screen private modes (from xterm)
ALT_SCREEN_MODES = {
    47,    # Use Alternate Screen Buffer (old xterm)
    1047,  # Use Alternate Screen Buffer (xterm)
    1049,  # Save cursor + Use Alternate Screen Buffer (most common)
}


class AltScreenMixin(_ScreenBase):
    """Mixin that adds alternate screen buffer support to pyte.Screen.

    This handles DEC private modes 47, 1047, and 1049 which are used by
    full-screen applications like tmux, vim, less, htop, etc.

    Also fixes pyte method signatures that don't accept **kwargs properly.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._alt_buffer: Any = None
        self._alt_cursor: tuple[int, int] | None = None
        self._saved_cursor_main: tuple[int, int] | None = None
        self._on_alt_screen = False

    @property
    def on_alt_screen(self) -> bool:
        """Whether currently on alternate screen."""
        return self._on_alt_screen

    def set_mode(self, *modes: int, **kwargs: Any) -> None:
        """Override to handle alternate screen modes."""
        private = kwargs.get("private", False)

        if private:
            for mode in modes:
                if mode in ALT_SCREEN_MODES:
                    self._enter_alt_screen(save_cursor=(mode == 1049))
                    return

        super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes: int, **kwargs: Any) -> None:
        """Override to handle alternate screen modes."""
        private = kwargs.get("private", False)

        if private:
            for mode in modes:
                if mode in ALT_SCREEN_MODES:
                    self._exit_alt_screen(restore_cursor=(mode == 1049))
                    return

        super().reset_mode(*modes, **kwargs)

    def report_device_status(self, mode: int, **kwargs: Any) -> None:
        """Override to accept private kwarg that pyte's Stream passes."""
        # pyte.Stream passes private=True but pyte.Screen doesn't accept it
        super().report_device_status(mode)

    def _enter_alt_screen(self, save_cursor: bool = False) -> None:
        """Switch to alternate screen buffer."""
        if self._on_alt_screen:
            return

        # Save main screen cursor position if requested (mode 1049)
        if save_cursor:
            self._saved_cursor_main = (self.cursor.y, self.cursor.x)

        # Save main buffer, switch to a blank alternate buffer. Mirror pyte's
        # main buffer (a defaultdict whose rows auto-create default-char cells):
        # a plain dict here caused KeyError crashes when an app on the alternate
        # screen (e.g. nvim with `laststatus=2`) erased/drew on a row that wasn't
        # pre-populated.
        self._alt_buffer = self.buffer
        self.buffer = defaultdict(lambda: StaticDefaultDict(self.default_char))

        # Reset cursor to top-left on alternate screen
        self.cursor.y = 0
        self.cursor.x = 0

        self._on_alt_screen = True
        self.dirty.update(range(self.lines))

    def _exit_alt_screen(self, restore_cursor: bool = False) -> None:
        """Switch back to main screen buffer."""
        if not self._on_alt_screen or self._alt_buffer is None:
            return

        # Restore main buffer
        self.buffer = self._alt_buffer
        self._alt_buffer = None

        # Restore cursor position if we saved it
        if restore_cursor and self._saved_cursor_main:
            self.cursor.y, self.cursor.x = self._saved_cursor_main
            self._saved_cursor_main = None

        self._on_alt_screen = False
        self.dirty.update(range(self.lines))


class Screen(AltScreenMixin, pyte.Screen):
    """Extended pyte.Screen with alternate screen buffer support."""
    pass


@dataclass
class TerminalConfig:
    """Configuration for terminal emulator."""

    rows: int = 24
    cols: int = 80


class Terminal:
    """Terminal emulator wrapper around pyte.

    Uses an extended Screen class with alternate screen buffer support
    for compatibility with tmux, vim, and other full-screen applications.
    """

    def __init__(self, config: TerminalConfig | None = None) -> None:
        self.config = config or TerminalConfig()
        self.screen = Screen(self.config.cols, self.config.rows)
        self.stream = pyte.Stream(self.screen)
        # Disable UTF-8 mode to enable DEC line drawing charset switching
        # This allows box-drawing characters (┌─┐│└┘) used by tmux, etc.
        self.stream.use_utf8 = False
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
