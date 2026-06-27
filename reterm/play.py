"""Terminal playback — replay a RecordingLog directly in the terminal."""

from __future__ import annotations

import sys
import time

from reterm.output.models import RecordingLog, StyledChar, TerminalSnapshot

# Named color → ANSI index mapping
_NAMED_COLORS: dict[str, int] = {
    "black": 0,
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
    "magenta": 5,
    "cyan": 6,
    "white": 7,
    "brightblack": 8,
    "brightred": 9,
    "brightgreen": 10,
    "brightyellow": 11,
    "brightblue": 12,
    "brightmagenta": 13,
    "brightcyan": 14,
    "brightwhite": 15,
}


def _color_to_sgr(color: str, is_foreground: bool) -> str:
    """Convert a pyte color value to an ANSI SGR parameter string.

    Returns the SGR parameter(s) only (no ESC[ or m wrapper), or empty string
    for "default".
    """
    if color == "default":
        return "39" if is_foreground else "49"

    # Named colors
    lower = color.lower()
    if lower in _NAMED_COLORS:
        idx = _NAMED_COLORS[lower]
        if idx < 8:
            return str((30 if is_foreground else 40) + idx)
        else:
            return str((90 if is_foreground else 100) + idx - 8)

    # Hex colors → 24-bit truecolor
    if color.startswith("#") and len(color) == 7:
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        base = 38 if is_foreground else 48
        return f"{base};2;{r};{g};{b}"

    # Numeric (string-encoded int)
    try:
        idx = int(color)
    except ValueError:
        return "39" if is_foreground else "49"

    if idx < 8:
        return str((30 if is_foreground else 40) + idx)
    elif idx < 16:
        return str((90 if is_foreground else 100) + idx - 8)
    else:
        # 256-color
        base = 38 if is_foreground else 48
        return f"{base};5;{idx}"


def styled_char_to_ansi(char: StyledChar) -> str:
    """Convert a StyledChar to an ANSI-escaped string."""
    params: list[str] = []

    if char.bold:
        params.append("1")
    if char.italic:
        params.append("3")
    if char.underline:
        params.append("4")
    if char.reverse:
        params.append("7")

    fg = _color_to_sgr(char.fg, is_foreground=True)
    bg = _color_to_sgr(char.bg, is_foreground=False)
    params.append(fg)
    if char.bg != "default":
        params.append(bg)

    return f"\x1b[{';'.join(params)}m{char.char}"


def _render_snapshot(snapshot: TerminalSnapshot) -> str:
    """Render a TerminalSnapshot to a string of ANSI escape sequences."""
    buf: list[str] = []
    # Move cursor home
    buf.append("\x1b[H")

    rows, cols = snapshot.dimensions

    if snapshot.styled_content:
        for row_idx, row in enumerate(snapshot.styled_content):
            if row_idx > 0:
                buf.append("\r\n")
            # Reset at start of each row
            buf.append("\x1b[0m")
            for char in row:
                buf.append(styled_char_to_ansi(char))
            # Clear to end of line in case previous frame was wider
            buf.append("\x1b[0m\x1b[K")
        # Clear remaining rows
        for _ in range(len(snapshot.styled_content), rows):
            buf.append("\r\n\x1b[0m\x1b[K")
    else:
        # Fallback: plain screen_content
        for row_idx, line in enumerate(snapshot.screen_content):
            if row_idx > 0:
                buf.append("\r\n")
            buf.append("\x1b[0m")
            buf.append(line)
            buf.append("\x1b[K")
        for _ in range(len(snapshot.screen_content), rows):
            buf.append("\r\n\x1b[0m\x1b[K")

    # Reset styling at end
    buf.append("\x1b[0m")
    return "".join(buf)


def play_recording(
    log: RecordingLog,
    speed: float = 1.0,
    idle_limit: float | None = None,
) -> None:
    """Play a RecordingLog back in the terminal.

    Args:
        log: The recording to play back.
        speed: Playback speed multiplier (2.0 = twice as fast).
        idle_limit: Cap pause duration at this many seconds.
    """
    out = sys.stdout

    # Enter alternate screen buffer and hide cursor
    out.write("\x1b[?1049h")  # alternate screen
    out.write("\x1b[?25l")  # hide cursor
    out.flush()

    try:
        for cmd in log.commands:
            snapshots: list[TerminalSnapshot] = []
            if cmd.intermediate_snapshots:
                snapshots.extend(cmd.intermediate_snapshots)
            if cmd.terminal_after:
                snapshots.append(cmd.terminal_after)

            if not snapshots:
                continue

            total_duration_ms = cmd.duration_ms if cmd.duration_ms else 500
            per_snapshot_ms = total_duration_ms / len(snapshots)

            for snapshot in snapshots:
                out.write(_render_snapshot(snapshot))
                out.flush()

                delay = per_snapshot_ms / 1000.0 / speed
                if idle_limit is not None:
                    delay = min(delay, idle_limit)
                time.sleep(delay)

        # Show final state
        if log.final_terminal_state:
            out.write(_render_snapshot(log.final_terminal_state))
            out.flush()

        # Brief hold on final frame
        time.sleep(min(1.0 / speed, 2.0))

    finally:
        # Restore screen and cursor
        out.write("\x1b[?25h")  # show cursor
        out.write("\x1b[?1049l")  # leave alternate screen
        out.flush()
