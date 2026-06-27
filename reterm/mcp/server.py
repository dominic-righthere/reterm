"""MCP server for AI tool integration."""

import io
import json
from typing import Any

from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from reterm.core.engine import Engine
from reterm.output.models import RecordingLog
from reterm.render.frame import FrameRenderer
from reterm.render.themes import list_themes, get_theme
from reterm.script.parser import ScriptError, parse_script_string

# Create the MCP server
mcp = FastMCP(
    name="reterm",
    instructions="AI-native terminal recording tool with structured output. Use run_script to execute .reterm scripts and get structured logs.",
)


@mcp.tool
def run_script(
    script_content: str,
    theme: str = "dracula",
    shell: str | None = None,
    generate_gif: bool = False,
) -> dict[str, Any]:
    """Execute a .reterm script and return the structured log.

    This is the primary tool for recording terminal sessions. The script
    uses YAML format to define commands, typing animations, and assertions.

    Args:
        script_content: The .reterm script content in YAML format
        theme: Terminal color theme (dracula, nord, monokai, etc.)
        shell: Shell to use (default: $SHELL or /bin/zsh)
        generate_gif: Whether to generate GIF frames (usually False for AI use)

    Returns:
        Complete recording log with commands, outputs, exit codes, and more.
        Key fields:
        - commands: List of executed commands with stdout/stderr/exit_code
        - success: True if all commands exited with code 0
        - all_commands_text: All commands as newline-separated text
        - all_output_text: All output concatenated
        - failed_commands: List of commands that failed

    Example script:
        meta:
          name: "Demo"
        config:
          shell: /bin/bash
        steps:
          - run: echo "Hello World"
          - run: ls -la
    """
    try:
        script = parse_script_string(script_content)
    except ScriptError as e:
        return {
            "success": False,
            "error": f"Script parse error: {e}",
            "error_type": "parse_error",
        }

    try:
        engine = Engine(
            shell=shell,
            theme=theme,
            generate_gif=generate_gif,
        )
        result = engine.run(script)

        # Return the log as a dict
        return result.log.model_dump(mode="json")

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }


@mcp.tool
def run_command(
    command: str,
    shell: str | None = None,
    theme: str = "dracula",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Execute a single shell command and return structured output.

    This is a convenience tool for running one command without writing
    a full script. Useful for quick command execution with full output capture.

    Args:
        command: Shell command to execute
        shell: Shell to use (default: $SHELL or /bin/zsh)
        theme: Terminal color theme
        timeout_seconds: Maximum execution time (not yet implemented)

    Returns:
        Structured output with:
        - command: The executed command
        - exit_code: Exit code (0 = success)
        - stdout: Standard output
        - stderr: Standard error
        - success: True if exit_code == 0
    """
    script_content = f"""
meta:
  name: "Single Command"
steps:
  - run: {json.dumps(command)}
"""

    try:
        script = parse_script_string(script_content)
        engine = Engine(
            shell=shell,
            theme=theme,
            generate_gif=False,
        )
        result = engine.run(script)

        # Extract the first (only) command result
        if result.log.commands:
            cmd = result.log.commands[0]
            return {
                "command": cmd.command,
                "exit_code": cmd.exit_code,
                "stdout": cmd.stdout,
                "stderr": cmd.stderr,
                "combined_output": cmd.combined_output,
                "duration_ms": cmd.duration_ms,
                "success": cmd.exit_code == 0,
            }
        else:
            return {
                "success": False,
                "error": "No command output captured",
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }


@mcp.tool
def generate_script(
    commands: list[str],
    name: str = "Generated Script",
    description: str = "",
    shell: str = "/bin/zsh",
    theme: str = "dracula",
    typing_speed: str = "50ms",
) -> str:
    """Generate a .reterm script from a list of commands.

    This tool helps AI create recording scripts programmatically.

    Args:
        commands: List of shell commands to include
        name: Name for the recording
        description: Description of what the recording demonstrates
        shell: Shell to use
        theme: Terminal color theme
        typing_speed: Speed for typing animations

    Returns:
        Complete .reterm script as YAML string
    """
    import yaml

    steps = [{"run": cmd} for cmd in commands]

    script_dict = {
        "meta": {
            "name": name,
            "description": description,
        },
        "config": {
            "shell": shell,
            "theme": theme,
            "typing_speed": typing_speed,
        },
        "steps": steps,
    }

    return yaml.dump(script_dict, default_flow_style=False, sort_keys=False)


@mcp.tool
def validate_script(script_content: str) -> dict[str, Any]:
    """Validate a .reterm script without executing it.

    Args:
        script_content: The script content to validate

    Returns:
        Validation result with:
        - valid: True if script is valid
        - step_count: Number of steps in the script
        - errors: Any validation errors
        - warnings: Any validation warnings
    """
    try:
        script = parse_script_string(script_content)

        warnings = []
        if not script.steps:
            warnings.append("Script has no steps")

        return {
            "valid": True,
            "step_count": len(script.steps),
            "meta": script.meta.model_dump(),
            "config": script.config.model_dump(),
            "warnings": warnings,
        }

    except ScriptError as e:
        return {
            "valid": False,
            "error": str(e),
        }


# Resources

@mcp.resource("reterm://schema")
def get_schema() -> str:
    """Get the JSON schema for recording logs."""
    schema = RecordingLog.model_json_schema()
    return json.dumps(schema, indent=2)


@mcp.resource("reterm://themes")
def get_themes() -> str:
    """Get list of available terminal themes."""
    themes = list_themes()
    return json.dumps({"themes": themes})


@mcp.resource("reterm://example")
def get_example_script() -> str:
    """Get an example .reterm script."""
    return """\
# Example reterm script
meta:
  name: "Hello World Demo"
  description: "A simple demonstration of reterm capabilities"

config:
  shell: /bin/zsh
  theme: dracula
  size: [80, 24]
  typing_speed: 50ms

env:
  GREETING: "Hello"

steps:
  # Run a simple command
  - run: echo "$GREETING, World!"

  # Type with animation then press enter
  - type: "ls -la"
    then: enter

  # Sleep for a moment
  - sleep: 1s

  # Run a command and capture its output
  - run: date +%Y
    capture: year

  # Use the captured variable
  - run: echo "Current year is ${year}"

  # Add a note (appears in log, not terminal)
  - note: "Demo completed successfully"
"""


@mcp.tool
def format_as_markdown(
    log: dict[str, Any],
    title: str | None = None,
) -> str:
    """Format a recording log as markdown text for attachment or sharing.

    Takes the dict returned by run_script or run_command and produces a
    clean markdown document with each command and its output in fenced
    code blocks — ready to paste into docs, issues, or Claude messages.

    Args:
        log: The recording log dict returned by run_script / run_command
        title: Optional heading override (defaults to the recording name)

    Returns:
        Markdown-formatted string with commands and their outputs.
    """
    lines: list[str] = []

    # Heading
    heading = title or (log.get("metadata") or {}).get("name") or "Terminal Recording"
    lines.append(f"# {heading}")
    lines.append("")

    commands = log.get("commands", [])
    if not commands:
        # run_command returns a flat dict, not nested commands
        cmd = log.get("command")
        output = log.get("combined_output") or log.get("stdout") or ""
        exit_code = log.get("exit_code", 0)
        if cmd:
            lines.append(f"```bash\n$ {cmd}\n```")
            if output.strip():
                lines.append(f"```\n{output.rstrip()}\n```")
            if exit_code != 0:
                lines.append(f"> Exit code: `{exit_code}`")
    else:
        for cmd_entry in commands:
            command = cmd_entry.get("command", "")
            output = cmd_entry.get("combined_output") or cmd_entry.get("stdout") or ""
            exit_code = cmd_entry.get("exit_code", 0)

            lines.append(f"```bash\n$ {command}\n```")
            if output.strip():
                lines.append(f"```\n{output.rstrip()}\n```")
            if exit_code != 0:
                lines.append(f"> Exit code: `{exit_code}`")
            lines.append("")

    # Footer summary
    success = log.get("success", True)
    lines.append("---")
    lines.append(f"*Status: {'✓ success' if success else '✗ failed'}*")

    return "\n".join(lines)


@mcp.tool
def screenshot_terminal(
    script_content: str,
    theme: str = "dracula",
    shell: str | None = None,
    snapshot: str = "final",
) -> Image:
    """Run a script and return a PNG screenshot of the terminal state.

    Executes the script and renders the terminal as a pixel-perfect image
    using the selected theme. Returns an MCP image that Claude can display
    inline — useful for visually verifying command output or creating docs.

    Args:
        script_content: The .reterm script content in YAML format
        theme: Terminal color theme (dracula, nord, monokai, etc.)
        shell: Shell to use (default: $SHELL or /bin/zsh)
        snapshot: Which terminal state to capture — "final" (default) or
                  "before"/"after" the first command

    Returns:
        PNG image of the terminal.
    """
    try:
        script = parse_script_string(script_content)
    except ScriptError as e:
        raise ValueError(f"Script parse error: {e}") from e

    engine = Engine(shell=shell, theme=theme, generate_gif=False)
    result = engine.run(script)
    log = result.log

    # Pick the snapshot to render
    terminal_snapshot = None
    if snapshot == "final":
        terminal_snapshot = log.final_terminal_state
    elif snapshot == "before" and log.commands:
        terminal_snapshot = log.commands[0].terminal_before
    elif snapshot == "after" and log.commands:
        terminal_snapshot = log.commands[-1].terminal_after

    if terminal_snapshot is None:
        raise ValueError("No terminal snapshot available — run at least one command")

    cols, rows = log.metadata.terminal_size
    theme_obj = get_theme(theme)
    renderer = FrameRenderer(cols=cols, rows=rows, theme=theme_obj)

    styled = terminal_snapshot.styled_content
    if styled:
        styled_lines = [
            [(sc.char, {"fg": sc.fg, "bg": sc.bg, "bold": sc.bold, "italic": sc.italic, "reverse": sc.reverse, "underscore": sc.underline})
             for sc in line]
            for line in styled
        ]
        img = renderer.render(styled_lines, cursor_pos=terminal_snapshot.cursor_position)
    else:
        img = renderer.render_simple(
            terminal_snapshot.screen_content,
            cursor_pos=terminal_snapshot.cursor_position,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Image(data=buf.getvalue(), format="png")


@mcp.tool
def render_svg(
    script_content: str,
    theme: str = "dracula",
    shell: str | None = None,
) -> str:
    """Run a .reterm script and return an animated SVG of the session.

    The SVG is a self-contained CSS animation that plays inline on GitHub when
    embedded via ``![demo](demo.svg)`` (GitHub strips JS players, but declarative
    SVG animation works). Save the returned markup to a ``.svg`` file and embed it
    in a README — crisp, small, and selectable, unlike a GIF.

    Args:
        script_content: The .reterm script content in YAML format
        theme: Terminal color theme (dracula, nord, monokai, etc.)
        shell: Shell to use (default: $SHELL or /bin/zsh)

    Returns:
        The animated SVG markup as a string (write it to a .svg file).
    """
    try:
        script = parse_script_string(script_content)
    except ScriptError as e:
        raise ValueError(f"Script parse error: {e}") from e

    engine = Engine(shell=shell, theme=theme, generate_gif=True)
    result = engine.run(script)
    return result.to_svg_markup(theme)


def run_server(transport: str = "stdio", port: int = 8080) -> None:
    """Run the MCP server.

    Args:
        transport: Transport type ('stdio' or 'sse')
        port: Port for SSE transport
    """
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # SSE transport
        mcp.run(transport="sse", port=port)
