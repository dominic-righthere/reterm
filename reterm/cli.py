"""CLI interface for reterm."""

import click

from reterm import __version__


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """reterm - AI-native terminal recording tool."""
    pass


@cli.command()
@click.argument("script_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="GIF output path")
@click.option("--log", "-l", type=click.Path(), help="JSON log output path")
@click.option("--log-only", is_flag=True, help="Skip GIF generation, output log only")
@click.option("--theme", "-t", default="dracula", help="Terminal theme")
@click.option("--shell", default=None, help="Shell to use (default: $SHELL)")
def run(
    script_file: str,
    output: str | None,
    log: str | None,
    log_only: bool,
    theme: str,
    shell: str | None,
) -> None:
    """Execute a .reterm script and generate outputs."""
    from reterm.core.engine import Engine
    from reterm.script.parser import parse_script
    from pathlib import Path

    script_path = Path(script_file)
    script = parse_script(script_path)

    engine = Engine(
        shell=shell,
        theme=theme,
        generate_gif=not log_only,
    )

    result = engine.run(script)

    # Determine output paths
    if output is None and not log_only:
        output = script_path.with_suffix(".gif")
    if log is None:
        log = script_path.with_suffix(".json")

    # Write outputs
    if not log_only and output:
        result.save_gif(Path(output))
        click.echo(f"GIF saved to: {output}")

    if log:
        result.save_log(Path(log))
        click.echo(f"Log saved to: {log}")


@cli.command()
@click.argument("script_file", type=click.Path(exists=True))
def validate(script_file: str) -> None:
    """Validate a .reterm script without executing."""
    from reterm.script.parser import parse_script, ScriptError
    from pathlib import Path

    try:
        script = parse_script(Path(script_file))
        click.echo(f"Valid script: {len(script.steps)} steps")
    except ScriptError as e:
        click.echo(f"Invalid script: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("script_file", type=click.Path())
def new(script_file: str) -> None:
    """Create a new .reterm script from template."""
    from pathlib import Path

    template = '''\
meta:
  name: "My Recording"
  description: "Description of what this recording demonstrates"

config:
  shell: /bin/zsh
  theme: dracula
  size: [80, 24]
  typing_speed: 50ms

output:
  gif: output.gif
  log: output.json

steps:
  - run: echo "Hello, World!"
  - sleep: 1s
'''

    path = Path(script_file)
    if path.exists():
        click.echo(f"File already exists: {script_file}", err=True)
        raise SystemExit(1)

    path.write_text(template)
    click.echo(f"Created: {script_file}")


@cli.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio")
@click.option("--port", default=8080, help="Port for SSE transport")
def serve(transport: str, port: int) -> None:
    """Start MCP server for AI tool integration."""
    from reterm.mcp.server import run_server

    run_server(transport=transport, port=port)


@cli.command()
def themes() -> None:
    """List available terminal themes."""
    from reterm.render.themes import list_themes

    click.echo("Available themes:")
    for theme_name in list_themes():
        click.echo(f"  - {theme_name}")


@cli.command()
def schema() -> None:
    """Print the JSON schema for recording logs."""
    from reterm.output.models import RecordingLog

    click.echo(RecordingLog.model_json_schema())


@cli.command()
@click.argument("log_file", type=click.Path(exists=True))
@click.option("--pattern", "-p", multiple=True, help="Pattern to redact")
@click.option("--replace", "-r", multiple=True, help="Replacement text")
@click.option("--regex", is_flag=True, help="Treat patterns as regex")
@click.option("--seamless", is_flag=True, help="No visible redaction indicator")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: overwrites input)")
def redact(
    log_file: str,
    pattern: tuple[str, ...],
    replace: tuple[str, ...],
    regex: bool,
    seamless: bool,
    output: str | None,
) -> None:
    """Redact sensitive information from a recording log.

    Examples:

        # Visible redaction (shows [HOME] in output)
        reterm redact demo.json -p "/Users/dom" -r "HOME" -o redacted.json

        # Seamless replacement (looks like original)
        reterm redact demo.json -p "/Users/dom" -r "/Users/alice" --seamless -o clean.json

        # Regex pattern
        reterm redact demo.json -p "sk-[a-zA-Z0-9]+" -r "API_KEY" --regex -o redacted.json
    """
    from pathlib import Path
    from reterm.output.models import RecordingLog
    from reterm.redact import create_redactor

    if len(pattern) != len(replace):
        click.echo(
            f"Error: Number of patterns ({len(pattern)}) must match "
            f"number of replacements ({len(replace)})",
            err=True,
        )
        raise SystemExit(1)

    if not pattern:
        click.echo("Error: At least one --pattern/-p is required", err=True)
        raise SystemExit(1)

    # Load log
    log_path = Path(log_file)
    log = RecordingLog.model_validate_json(log_path.read_text())

    # Create redactor and apply
    redactor = create_redactor(
        patterns=list(pattern),
        replacements=list(replace),
        is_regex=regex,
        seamless=seamless,
    )
    redacted_log = redactor.redact_log(log)

    # Write output
    output_path = Path(output) if output else log_path
    output_path.write_text(redacted_log.model_dump_json(indent=2))
    click.echo(f"Redacted log saved to: {output_path}")


@cli.command()
@click.argument("log_file", type=click.Path(exists=True))
@click.option("--output", "-o", required=True, type=click.Path(), help="GIF output path")
@click.option("--theme", "-t", default=None, help="Override theme from log")
@click.option("--fps", default=30, help="Frames per second")
def render(
    log_file: str,
    output: str,
    theme: str | None,
    fps: int,
) -> None:
    """Re-render a GIF from a (possibly redacted) log file.

    Examples:

        # Render GIF from log
        reterm render recording.json -o output.gif

        # Override theme
        reterm render recording.json -o output.gif --theme monokai
    """
    from pathlib import Path
    from reterm.output.models import RecordingLog
    from reterm.render.from_log import render_gif_from_log

    # Load log
    log_path = Path(log_file)
    log = RecordingLog.model_validate_json(log_path.read_text())

    # Render GIF
    output_path = Path(output)
    render_gif_from_log(
        log=log,
        output_path=output_path,
        theme=theme,
        fps=fps,
    )
    click.echo(f"GIF rendered to: {output_path}")


if __name__ == "__main__":
    cli()
