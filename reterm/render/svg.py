"""Animated SVG rendering for terminal recordings.

Produces a self-contained animated SVG (a CSS-keyframe "flipbook") suitable for
embedding inline in a GitHub README via ``![demo](demo.svg)``. Declarative SVG/CSS
animations play when an SVG is referenced as an ``<img>`` — unlike a JS player,
which GitHub strips — so this is the richest preview that animates inline.

Each captured frame becomes a ``<g>`` that is opaque only during its slice of the
cumulative timeline; ``step-end`` timing makes the transitions instant (a flipbook,
not a fade). Consecutive identical frames are merged to keep the file small.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reterm.render.themes import Theme


@dataclass
class _Cell:
    """One terminal cell: a character plus its (pyte) style."""

    char: str
    fg: str | None = None
    bg: str | None = None
    bold: bool = False
    underline: bool = False
    reverse: bool = False


def cells_from_styled_tuples(
    styled_lines: list[list[tuple[str, dict[str, Any]]]],
) -> list[list[_Cell]]:
    """Convert FrameRenderer-style ``[(char, style_dict), ...]`` rows to cells."""
    return [
        [
            _Cell(
                char=char,
                fg=style.get("fg"),  # type: ignore[arg-type]
                bg=style.get("bg"),  # type: ignore[arg-type]
                bold=bool(style.get("bold")),
                underline=bool(style.get("underscore")),
                reverse=bool(style.get("reverse")),
            )
            for char, style in line
        ]
        for line in styled_lines
    ]


def cells_from_styled_content(styled_content: list[list[Any]]) -> list[list[_Cell]]:
    """Convert a ``TerminalSnapshot.styled_content`` (StyledChar rows) to cells."""
    return [
        [
            _Cell(
                char=c.char,
                fg=c.fg,
                bg=c.bg,
                bold=bool(c.bold),
                underline=bool(c.underline),
                reverse=bool(c.reverse),
            )
            for c in line
        ]
        for line in styled_content
    ]


def cells_from_plain(lines: list[str]) -> list[list[_Cell]]:
    """Convert plain text lines to default-styled cells."""
    return [[_Cell(char=ch) for ch in line] for line in lines]


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# A run of same-styled cells on one row: (start_col, text, fg_hex, bg_hex|None, bold, underline)
_Run = tuple[int, str, str, "str | None", bool, bool]


class SvgWriter:
    """Builds an animated SVG flipbook from styled terminal frames."""

    def __init__(
        self,
        output_path: Path | str,
        theme: Theme,
        cols: int,
        rows: int,
        font_size: int = 14,
        padding: int = 16,
        loop: bool = True,
        max_frame_ms: int | None = None,  # cap any single frame's hold time
    ) -> None:
        self.output_path = Path(output_path)
        self.theme = theme
        self.cols = cols
        self.rows = rows
        self.font_size = font_size
        self.char_w = font_size * 0.6
        self.char_h = font_size * 1.2
        self.padding = padding
        self.loop = loop
        self.max_frame_ms = max_frame_ms
        # (rows_of_cells, cursor_pos, duration_ms)
        self._frames: list[tuple[list[list[_Cell]], tuple[int, int] | None, int]] = []

    @property
    def width(self) -> int:
        return int(self.cols * self.char_w + 2 * self.padding)

    @property
    def height(self) -> int:
        return int(self.rows * self.char_h + 2 * self.padding)

    def frame_count(self) -> int:
        return len(self._frames)

    def add_frame(
        self,
        rows: list[list[_Cell]],
        cursor_pos: tuple[int, int] | None,
        duration_ms: int,
    ) -> None:
        """Append a frame, merging it into the previous one if identical."""
        duration_ms = max(int(duration_ms), 1)
        if self.max_frame_ms is not None:
            duration_ms = min(duration_ms, self.max_frame_ms)
        if self._frames:
            prev_rows, prev_cursor, prev_dur = self._frames[-1]
            if prev_cursor == cursor_pos and self._rows_key(prev_rows) == self._rows_key(rows):
                merged = prev_dur + duration_ms
                if self.max_frame_ms is not None:
                    merged = min(merged, self.max_frame_ms)
                self._frames[-1] = (prev_rows, prev_cursor, merged)
                return
        self._frames.append((rows, cursor_pos, duration_ms))

    @staticmethod
    def _rows_key(rows: list[list[_Cell]]) -> list[list[tuple]]:
        return [
            [(c.char, c.fg, c.bg, c.bold, c.underline, c.reverse) for c in row]
            for row in rows
        ]

    def _runs(self, row: list[_Cell]) -> list[_Run]:
        """Group a row's cells into runs of identical resolved style."""
        runs: list[_Run] = []
        start = 0
        buf = ""
        key: tuple | None = None
        cur_fg = self.theme.foreground
        cur_bg: str | None = None

        def resolve(cell: _Cell) -> tuple[str, str | None, bool, bool]:
            fg = self.theme.resolve_color(cell.fg, is_foreground=True)
            bg: str | None = None
            if cell.bg not in (None, "default"):
                bg = self.theme.resolve_color(cell.bg, is_foreground=False)
            if cell.reverse:
                fg, bg = (bg or self.theme.background), fg
            return fg, bg, cell.bold, cell.underline

        for col, cell in enumerate(row):
            if col >= self.cols:
                break
            fg, bg, bold, underline = resolve(cell)
            ckey = (fg, bg, bold, underline)
            char = cell.char or " "
            if ckey != key:
                if key is not None and buf:
                    runs.append((start, buf, cur_fg, cur_bg, key[2], key[3]))
                start, buf, key = col, char, ckey
                cur_fg, cur_bg = fg, bg
            else:
                buf += char
        if key is not None and buf:
            runs.append((start, buf, cur_fg, cur_bg, key[2], key[3]))
        return runs

    def _render_frame(self, rows: list[list[_Cell]], cursor: tuple[int, int] | None) -> str:
        out: list[str] = []
        for r, row in enumerate(rows):
            if r >= self.rows:
                break
            runs = self._runs(row)
            y = self.padding + r * self.char_h
            # Background rects first (so text sits on top)
            for start, text, _fg, bg, _bold, _ul in runs:
                if bg is not None:
                    x = self.padding + start * self.char_w
                    out.append(
                        f'<rect x="{x:.2f}" y="{y:.2f}" '
                        f'width="{len(text) * self.char_w:.2f}" height="{self.char_h:.2f}" fill="{bg}"/>'
                    )
            # Text runs (skip invisible default-fg whitespace)
            spans: list[str] = []
            for start, text, fg, bg, bold, underline in runs:
                if not text.strip() and bg is None:
                    continue
                # Pin each glyph to its exact grid column so alignment never
                # depends on the font's glyph advance — but only for runs with
                # non-ASCII glyphs (box-drawing rule rows, CJK), whose advance is
                # the unreliable case. Plain ASCII keeps a single x so normal
                # shell recordings stay small (per-char x lists ~2.5x the file).
                if any(ord(c) > 0x7e for c in text):
                    x_attr = " ".join(
                        f"{self.padding + (start + i) * self.char_w:.2f}" for i in range(len(text))
                    )
                else:
                    x_attr = f"{self.padding + start * self.char_w:.2f}"
                attrs = f' x="{x_attr}" fill="{fg}"'
                if bold:
                    attrs += ' font-weight="bold"'
                if underline:
                    attrs += ' text-decoration="underline"'
                spans.append(f'<tspan{attrs} xml:space="preserve">{_xml_escape(text)}</tspan>')
            if spans:
                ty = y + self.char_h * 0.78
                out.append(f'<text y="{ty:.2f}">{"".join(spans)}</text>')
        if cursor is not None:
            cr, cc = cursor
            if 0 <= cr < self.rows and 0 <= cc < self.cols:
                cx = self.padding + cc * self.char_w
                cy = self.padding + cr * self.char_h
                out.append(
                    f'<rect x="{cx:.2f}" y="{cy:.2f}" width="{self.char_w:.2f}" '
                    f'height="{self.char_h:.2f}" fill="{self.theme.cursor}" opacity="0.7"/>'
                )
        return "".join(out)

    def _keyframes(self, i: int, start_pct: float, end_pct: float, total_s: float) -> str:
        name = f"f{i}"
        iterations = "infinite" if self.loop else "1"
        rule = f".{name}{{animation:{name} {total_s:.3f}s step-end {iterations}}}"
        stops: list[str] = []
        if start_pct <= 0:
            stops.append("0%{opacity:1}")
        else:
            stops.append("0%{opacity:0}")
            stops.append(f"{start_pct:.4f}%{{opacity:1}}")
        if end_pct < 100:
            stops.append(f"{end_pct:.4f}%{{opacity:0}}")
        return f"{rule}@keyframes {name}{{{''.join(stops)}}}"

    def to_svg(self) -> str:
        if not self._frames:
            raise ValueError("No frames to render")

        total_ms = sum(dur for _, _, dur in self._frames) or 1
        total_s = total_ms / 1000.0
        font_family = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"

        css: list[str] = [f"text{{font-family:{font_family};font-size:{self.font_size}px}}"]
        elapsed = 0
        for i, (_, _, dur) in enumerate(self._frames):
            start_pct = elapsed / total_ms * 100
            end_pct = (elapsed + dur) / total_ms * 100
            elapsed += dur
            css.append(self._keyframes(i, start_pct, end_pct, total_s))

        parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{self.height}" viewBox="0 0 {self.width} {self.height}">',
            f"<style>{''.join(css)}</style>",
            f'<rect width="{self.width}" height="{self.height}" rx="6" fill="{self.theme.background}"/>',
        ]
        # Base opacity: hide all but the LAST frame, so a viewer that rasterizes
        # the SVG (ignoring the animation) shows the populated final terminal
        # instead of a blank image. Animating browsers override this at 0% (the
        # last frame's first keyframe is opacity:0), so there's no flash.
        last = len(self._frames) - 1
        for i, (rows, cursor, _) in enumerate(self._frames):
            base = "1" if i == last else "0"
            parts.append(f'<g class="f{i}" opacity="{base}">{self._render_frame(rows, cursor)}</g>')
        parts.append("</svg>")
        return "".join(parts)

    def save(self) -> None:
        self.output_path.write_text(self.to_svg())


def render_svg_from_log(
    log: Any,
    output_path: Path,
    theme: str | None = None,
    fps: int = 30,
    idle_limit: float | None = None,
) -> None:
    """Render an animated SVG from an existing recording log.

    Uses each snapshot's ``styled_content`` (so the SVG is colored). Animation
    fidelity depends on the snapshots the log carries: ``run`` steps record
    intermediate snapshots, so run-based recordings animate richly; ``type``-only
    scripts capture animation in the live frame stream instead (see
    ``RecordingResult.save_svg``).
    """
    from reterm.render.themes import get_theme

    cols, rows = log.metadata.terminal_size
    theme_obj = get_theme(theme or log.metadata.theme)
    max_frame_ms = int(idle_limit * 1000) if idle_limit and idle_limit > 0 else None
    writer = SvgWriter(output_path, theme_obj, cols, rows, max_frame_ms=max_frame_ms)

    def add_snapshot(snapshot: Any, duration_ms: int) -> None:
        if snapshot.styled_content:
            cells = cells_from_styled_content(snapshot.styled_content)
        else:
            cells = cells_from_plain(snapshot.screen_content)
        writer.add_frame(cells, snapshot.cursor_position, duration_ms)

    default_ms = int(1000 / fps)
    for cmd in log.commands:
        if cmd.intermediate_snapshots and cmd.terminal_after:
            total = cmd.duration_ms or default_ms
            per = max(total // (len(cmd.intermediate_snapshots) + 1), 1)
            for snap in cmd.intermediate_snapshots:
                add_snapshot(snap, per)
            add_snapshot(cmd.terminal_after, per)
        elif cmd.terminal_after:
            add_snapshot(cmd.terminal_after, cmd.duration_ms or default_ms)

    if log.final_terminal_state:
        add_snapshot(log.final_terminal_state, 1500)

    if writer.frame_count() == 0:
        raise ValueError("No frames to render - log has no terminal snapshots")
    writer.save()
