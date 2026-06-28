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
@click.option("--output", "-o", type=click.Path(), help="Visual output path (.gif or .svg)")
@click.option("--log", "-l", type=click.Path(), help="JSON log output path")
@click.option("--log-only", is_flag=True, help="Skip visual output, write the log only")
@click.option("--theme", "-t", default="dracula", help="Terminal theme")
@click.option("--shell", default=None, help="Shell to use (default: $SHELL)")
@click.option(
    "--idle-limit",
    "-i",
    default=2.0,
    type=float,
    help="Cap any static frame at N seconds in the GIF/SVG so long waits don't drag (0 = uncapped)",
)
def run(
    script_file: str,
    output: str | None,
    log: str | None,
    log_only: bool,
    theme: str,
    shell: str | None,
    idle_limit: float,
) -> None:
    """Execute a .reterm script and generate outputs.

    The visual format is chosen from the -o extension: .gif (default) or .svg
    (an animated SVG you can embed inline in a GitHub README).
    """
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
    out_path = Path(output) if output else script_path.with_suffix(".gif")
    log_path = Path(log) if log else script_path.with_suffix(".json")

    # Write outputs (visual format from the -o extension)
    if not log_only:
        suffix = out_path.suffix.lower()
        if suffix == ".svg":
            result.save_svg(out_path, idle_limit=idle_limit)
        elif suffix == ".gif":
            result.save_gif(out_path, idle_limit=idle_limit)
        else:
            raise click.ClickException(
                f"Unsupported output format '{suffix}'. Use .gif or .svg."
            )
        click.echo(f"Saved {suffix.lstrip('.').upper()} to: {out_path}")

    result.save_log(log_path)
    click.echo(f"Log saved to: {log_path}")


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
        reterm redact demo.json -p "/home/user" -r "HOME" -o redacted.json

        # Seamless replacement (looks like original)
        reterm redact demo.json -p "/home/user" -r "/home/alice" --seamless -o clean.json

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
@click.option("--speed", "-s", default=1.0, help="Playback speed multiplier")
@click.option("--idle-limit", "-i", default=None, type=float, help="Cap pause duration at N seconds")
def play(log_file: str, speed: float, idle_limit: float | None) -> None:
    """Play back a recording in the terminal.

    Examples:

        reterm play recording.json
        reterm play recording.json --speed 2
        reterm play recording.json --idle-limit 2
    """
    from pathlib import Path
    from reterm.output.models import RecordingLog
    from reterm.play import play_recording

    log_path = Path(log_file)
    log = RecordingLog.model_validate_json(log_path.read_text())
    play_recording(log, speed=speed, idle_limit=idle_limit)


@cli.command()
@click.argument("log_file", type=click.Path(exists=True))
@click.option("--output", "-o", required=True, type=click.Path(), help="Output path (.gif or .svg)")
@click.option("--theme", "-t", default=None, help="Override theme from log")
@click.option("--fps", default=30, help="Frames per second")
@click.option(
    "--idle-limit",
    "-i",
    default=2.0,
    type=float,
    help="Cap any static frame at N seconds so long waits don't drag (0 = uncapped)",
)
def render(
    log_file: str,
    output: str,
    theme: str | None,
    fps: int,
    idle_limit: float,
) -> None:
    """Re-render a GIF or animated SVG from a (possibly redacted) log file.

    The format is chosen from the -o extension.

    Examples:

        # Render a GIF from a log
        reterm render recording.json -o output.gif

        # Render an animated SVG (embeddable inline in a GitHub README)
        reterm render recording.json -o output.svg

        # Override theme
        reterm render recording.json -o output.gif --theme monokai
    """
    from pathlib import Path
    from reterm.output.models import RecordingLog

    # Load log
    log_path = Path(log_file)
    log = RecordingLog.model_validate_json(log_path.read_text())

    output_path = Path(output)
    suffix = output_path.suffix.lower()
    if suffix == ".svg":
        from reterm.render.svg import render_svg_from_log

        render_svg_from_log(
            log=log, output_path=output_path, theme=theme, fps=fps, idle_limit=idle_limit
        )
        click.echo(f"SVG rendered to: {output_path}")
    elif suffix == ".gif":
        from reterm.render.from_log import render_gif_from_log

        render_gif_from_log(
            log=log, output_path=output_path, theme=theme, fps=fps, idle_limit=idle_limit
        )
        click.echo(f"GIF rendered to: {output_path}")
    else:
        raise click.ClickException(
            f"Unsupported output format '{suffix}'. Use .gif or .svg."
        )


@cli.command()
@click.argument("poster", type=click.Path(), default="assets/demo.svg")
@click.option("--base", help="Base URL of the hosted player, e.g. https://you.github.io/reterm")
@click.option("--recording", "-r", "recording", default="demo", help="Recording name under <base>/recordings/<name>.json")
@click.option("--src", default=None, help="Direct recording URL for the player (?src=...)")
@click.option("--alt", default="terminal recording", help="Image alt text")
def embed(poster: str, base: str | None, recording: str, src: str | None, alt: str) -> None:
    """Print Markdown to embed a recording in a README.

    GitHub READMEs can't run a JS player inline, so this produces an animated-SVG
    (or GIF) poster that links to the hosted interactive player.

    Examples:

        # Inline animated SVG poster only
        reterm embed assets/demo.svg

        # SVG poster that links to the hosted player
        reterm embed assets/demo.svg --base https://you.github.io/reterm -r demo
    """
    if base:
        base_url = base.rstrip("/")
        target = f"{base_url}/play/?src={src}" if src else f"{base_url}/play/?r={recording}"
        click.echo(f"[![{alt}]({poster})]({target})")
    else:
        click.echo(f"![{alt}]({poster})")
        click.echo(
            "tip: pass --base https://<you>.github.io/reterm to link an interactive player",
            err=True,
        )


if __name__ == "__main__":
    cli()
