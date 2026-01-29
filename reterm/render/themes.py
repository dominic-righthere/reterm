"""Terminal color themes."""

from dataclasses import dataclass


@dataclass
class Theme:
    """Terminal color theme."""

    name: str

    # Base colors
    background: str
    foreground: str
    cursor: str

    # ANSI colors (0-15)
    black: str
    red: str
    green: str
    yellow: str
    blue: str
    magenta: str
    cyan: str
    white: str

    # Bright variants
    bright_black: str
    bright_red: str
    bright_green: str
    bright_yellow: str
    bright_blue: str
    bright_magenta: str
    bright_cyan: str
    bright_white: str

    def get_ansi_color(self, index: int) -> str:
        """Get ANSI color by index (0-15)."""
        colors = [
            self.black,
            self.red,
            self.green,
            self.yellow,
            self.blue,
            self.magenta,
            self.cyan,
            self.white,
            self.bright_black,
            self.bright_red,
            self.bright_green,
            self.bright_yellow,
            self.bright_blue,
            self.bright_magenta,
            self.bright_cyan,
            self.bright_white,
        ]
        if 0 <= index < len(colors):
            return colors[index]
        return self.foreground

    def resolve_color(self, color: str | None, is_foreground: bool = True) -> str:
        """Resolve a pyte color value to hex color."""
        if color is None or color == "default":
            return self.foreground if is_foreground else self.background

        # Handle named colors
        if isinstance(color, str):
            color_lower = color.lower()
            color_map = {
                "black": self.black,
                "red": self.red,
                "green": self.green,
                "yellow": self.yellow,
                "blue": self.blue,
                "magenta": self.magenta,
                "cyan": self.cyan,
                "white": self.white,
                "brightblack": self.bright_black,
                "brightred": self.bright_red,
                "brightgreen": self.bright_green,
                "brightyellow": self.bright_yellow,
                "brightblue": self.bright_blue,
                "brightmagenta": self.bright_magenta,
                "brightcyan": self.bright_cyan,
                "brightwhite": self.bright_white,
            }
            if color_lower in color_map:
                return color_map[color_lower]

            # Handle hex colors
            if color.startswith("#"):
                return color

            # Handle numeric ANSI codes
            try:
                index = int(color)
                if 0 <= index < 16:
                    return self.get_ansi_color(index)
                elif 16 <= index < 232:
                    # 216 color cube (6x6x6)
                    index -= 16
                    r = (index // 36) * 51
                    g = ((index // 6) % 6) * 51
                    b = (index % 6) * 51
                    return f"#{r:02x}{g:02x}{b:02x}"
                elif 232 <= index < 256:
                    # Grayscale
                    gray = (index - 232) * 10 + 8
                    return f"#{gray:02x}{gray:02x}{gray:02x}"
            except ValueError:
                pass

        return self.foreground if is_foreground else self.background


# Define popular themes
DRACULA = Theme(
    name="dracula",
    background="#282a36",
    foreground="#f8f8f2",
    cursor="#f8f8f2",
    black="#21222c",
    red="#ff5555",
    green="#50fa7b",
    yellow="#f1fa8c",
    blue="#bd93f9",
    magenta="#ff79c6",
    cyan="#8be9fd",
    white="#f8f8f2",
    bright_black="#6272a4",
    bright_red="#ff6e6e",
    bright_green="#69ff94",
    bright_yellow="#ffffa5",
    bright_blue="#d6acff",
    bright_magenta="#ff92df",
    bright_cyan="#a4ffff",
    bright_white="#ffffff",
)

NORD = Theme(
    name="nord",
    background="#2e3440",
    foreground="#d8dee9",
    cursor="#d8dee9",
    black="#3b4252",
    red="#bf616a",
    green="#a3be8c",
    yellow="#ebcb8b",
    blue="#81a1c1",
    magenta="#b48ead",
    cyan="#88c0d0",
    white="#e5e9f0",
    bright_black="#4c566a",
    bright_red="#bf616a",
    bright_green="#a3be8c",
    bright_yellow="#ebcb8b",
    bright_blue="#81a1c1",
    bright_magenta="#b48ead",
    bright_cyan="#8fbcbb",
    bright_white="#eceff4",
)

MONOKAI = Theme(
    name="monokai",
    background="#272822",
    foreground="#f8f8f2",
    cursor="#f8f8f2",
    black="#272822",
    red="#f92672",
    green="#a6e22e",
    yellow="#f4bf75",
    blue="#66d9ef",
    magenta="#ae81ff",
    cyan="#a1efe4",
    white="#f8f8f2",
    bright_black="#75715e",
    bright_red="#f92672",
    bright_green="#a6e22e",
    bright_yellow="#f4bf75",
    bright_blue="#66d9ef",
    bright_magenta="#ae81ff",
    bright_cyan="#a1efe4",
    bright_white="#f9f8f5",
)

SOLARIZED_DARK = Theme(
    name="solarized-dark",
    background="#002b36",
    foreground="#839496",
    cursor="#839496",
    black="#073642",
    red="#dc322f",
    green="#859900",
    yellow="#b58900",
    blue="#268bd2",
    magenta="#d33682",
    cyan="#2aa198",
    white="#eee8d5",
    bright_black="#002b36",
    bright_red="#cb4b16",
    bright_green="#586e75",
    bright_yellow="#657b83",
    bright_blue="#839496",
    bright_magenta="#6c71c4",
    bright_cyan="#93a1a1",
    bright_white="#fdf6e3",
)

GITHUB_DARK = Theme(
    name="github-dark",
    background="#0d1117",
    foreground="#c9d1d9",
    cursor="#c9d1d9",
    black="#484f58",
    red="#ff7b72",
    green="#3fb950",
    yellow="#d29922",
    blue="#58a6ff",
    magenta="#bc8cff",
    cyan="#39c5cf",
    white="#b1bac4",
    bright_black="#6e7681",
    bright_red="#ffa198",
    bright_green="#56d364",
    bright_yellow="#e3b341",
    bright_blue="#79c0ff",
    bright_magenta="#d2a8ff",
    bright_cyan="#56d4dd",
    bright_white="#f0f6fc",
)

ONE_DARK = Theme(
    name="one-dark",
    background="#282c34",
    foreground="#abb2bf",
    cursor="#528bff",
    black="#1e2127",
    red="#e06c75",
    green="#98c379",
    yellow="#d19a66",
    blue="#61afef",
    magenta="#c678dd",
    cyan="#56b6c2",
    white="#abb2bf",
    bright_black="#5c6370",
    bright_red="#e06c75",
    bright_green="#98c379",
    bright_yellow="#d19a66",
    bright_blue="#61afef",
    bright_magenta="#c678dd",
    bright_cyan="#56b6c2",
    bright_white="#ffffff",
)

# Theme registry
THEMES: dict[str, Theme] = {
    "dracula": DRACULA,
    "nord": NORD,
    "monokai": MONOKAI,
    "solarized-dark": SOLARIZED_DARK,
    "github-dark": GITHUB_DARK,
    "one-dark": ONE_DARK,
}


def get_theme(name: str) -> Theme:
    """Get a theme by name."""
    theme = THEMES.get(name.lower())
    if theme is None:
        raise ValueError(f"Unknown theme: {name}. Available: {list(THEMES.keys())}")
    return theme


def list_themes() -> list[str]:
    """List available theme names."""
    return list(THEMES.keys())
