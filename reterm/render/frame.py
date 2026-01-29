"""Terminal frame rendering using Pillow."""

import importlib.resources
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from reterm.render.themes import Theme


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


@lru_cache(maxsize=1)
def _get_default_font(size: int) -> ImageFont.FreeTypeFont:
    """Get a monospace font, preferring system fonts."""
    # Try common monospace font paths
    font_paths = [
        # macOS
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFMono-Regular.otf",
        "/Library/Fonts/JetBrainsMono-Regular.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/TTF/JetBrainsMono-Regular.ttf",
        # Windows
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/lucon.ttf",
    ]

    for font_path in font_paths:
        try:
            if Path(font_path).exists():
                return ImageFont.truetype(font_path, size)
        except Exception:
            continue

    # Fall back to default font
    try:
        return ImageFont.truetype("DejaVuSansMono.ttf", size)
    except Exception:
        # Ultimate fallback - use default bitmap font
        return ImageFont.load_default()


class FrameRenderer:
    """Renders terminal content to image frames."""

    def __init__(
        self,
        cols: int = 80,
        rows: int = 24,
        theme: Theme | None = None,
        font_size: int = 14,
        padding: int = 20,
        line_height: float = 1.2,
    ) -> None:
        self.cols = cols
        self.rows = rows
        self.font_size = font_size
        self.padding = padding
        self.line_height = line_height

        # Get theme
        if theme is None:
            from reterm.render.themes import DRACULA

            theme = DRACULA
        self.theme = theme

        # Load font
        self.font = _get_default_font(font_size)

        # Calculate character dimensions
        self._calculate_char_dimensions()

    def _calculate_char_dimensions(self) -> None:
        """Calculate character width and height."""
        # Create a temporary image to measure text
        img = Image.new("RGB", (100, 100))
        draw = ImageDraw.Draw(img)

        # Measure a representative character
        bbox = draw.textbbox((0, 0), "M", font=self.font)
        self.char_width = bbox[2] - bbox[0]
        self.char_height = int((bbox[3] - bbox[1]) * self.line_height)

        # Ensure minimum dimensions
        self.char_width = max(self.char_width, 8)
        self.char_height = max(self.char_height, 14)

    def get_image_size(self) -> tuple[int, int]:
        """Get the size of rendered images."""
        width = self.cols * self.char_width + 2 * self.padding
        height = self.rows * self.char_height + 2 * self.padding
        return (width, height)

    def render(
        self,
        styled_lines: list[list[tuple[str, dict[str, object]]]],
        cursor_pos: tuple[int, int] | None = None,
    ) -> Image.Image:
        """Render terminal content to an image.

        Args:
            styled_lines: List of lines, each line is list of (char, style) tuples
            cursor_pos: Optional cursor position as (row, col)

        Returns:
            PIL Image with rendered terminal content
        """
        width, height = self.get_image_size()

        # Create image with background color
        bg_color = _hex_to_rgb(self.theme.background)
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Render each character
        for row, line in enumerate(styled_lines):
            if row >= self.rows:
                break

            y = self.padding + row * self.char_height

            for col, (char, style) in enumerate(line):
                if col >= self.cols:
                    break

                x = self.padding + col * self.char_width

                # Get colors from style
                fg_color = self._resolve_fg_color(style)
                bg_color_char = self._resolve_bg_color(style)

                # Handle reverse video
                if style.get("reverse"):
                    fg_color, bg_color_char = bg_color_char, fg_color

                # Draw background if not default
                if bg_color_char != bg_color:
                    draw.rectangle(
                        [x, y, x + self.char_width, y + self.char_height],
                        fill=bg_color_char,
                    )

                # Draw character
                if char and char != " ":
                    # Handle bold by using slightly different rendering
                    # (In a full implementation, we'd load a bold font variant)
                    draw.text((x, y), char, font=self.font, fill=fg_color)

                # Draw underline
                if style.get("underscore"):
                    underline_y = y + self.char_height - 2
                    draw.line(
                        [(x, underline_y), (x + self.char_width, underline_y)],
                        fill=fg_color,
                        width=1,
                    )

        # Draw cursor
        if cursor_pos:
            cursor_row, cursor_col = cursor_pos
            if 0 <= cursor_row < self.rows and 0 <= cursor_col < self.cols:
                cursor_x = self.padding + cursor_col * self.char_width
                cursor_y = self.padding + cursor_row * self.char_height
                cursor_color = _hex_to_rgb(self.theme.cursor)

                # Draw block cursor
                draw.rectangle(
                    [
                        cursor_x,
                        cursor_y,
                        cursor_x + self.char_width,
                        cursor_y + self.char_height,
                    ],
                    fill=cursor_color,
                )

        return img

    def _resolve_fg_color(self, style: dict[str, object]) -> tuple[int, int, int]:
        """Resolve foreground color from style."""
        fg = style.get("fg")
        hex_color = self.theme.resolve_color(fg, is_foreground=True)  # type: ignore
        return _hex_to_rgb(hex_color)

    def _resolve_bg_color(self, style: dict[str, object]) -> tuple[int, int, int]:
        """Resolve background color from style."""
        bg = style.get("bg")
        hex_color = self.theme.resolve_color(bg, is_foreground=False)  # type: ignore
        return _hex_to_rgb(hex_color)

    def render_simple(
        self,
        lines: list[str],
        cursor_pos: tuple[int, int] | None = None,
    ) -> Image.Image:
        """Render simple text lines (no styling).

        Args:
            lines: List of text lines
            cursor_pos: Optional cursor position as (row, col)

        Returns:
            PIL Image with rendered terminal content
        """
        # Convert to styled format
        styled_lines: list[list[tuple[str, dict[str, object]]]] = []
        for line in lines:
            styled_line: list[tuple[str, dict[str, object]]] = []
            for char in line:
                styled_line.append((char, {}))
            # Pad to terminal width
            while len(styled_line) < self.cols:
                styled_line.append((" ", {}))
            styled_lines.append(styled_line)

        # Pad to terminal height
        while len(styled_lines) < self.rows:
            styled_lines.append([(" ", {})] * self.cols)

        return self.render(styled_lines, cursor_pos)
