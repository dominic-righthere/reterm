"""Render GIF from an existing recording log."""

from pathlib import Path

from reterm.output.models import RecordingLog
from reterm.render.frame import FrameRenderer
from reterm.render.gif import GIFWriter
from reterm.render.themes import get_theme


def render_gif_from_log(
    log: RecordingLog,
    output_path: Path,
    theme: str | None = None,
    fps: int = 30,
    idle_limit: float | None = None,
) -> None:
    """Render a GIF from an existing recording log.

    Args:
        log: The recording log to render
        output_path: Path to save the GIF
        theme: Optional theme override (uses log's theme if not specified)
        fps: Frames per second for the GIF
    """
    # Get terminal dimensions from log
    cols, rows = log.metadata.terminal_size

    # Get theme
    theme_name = theme or log.metadata.theme
    theme_obj = get_theme(theme_name)

    # Create renderer
    renderer = FrameRenderer(
        cols=cols,
        rows=rows,
        theme=theme_obj,
    )

    # Create GIF writer
    max_frame_ms = int(idle_limit * 1000) if idle_limit and idle_limit > 0 else None
    writer = GIFWriter(output_path, fps=fps, max_frame_ms=max_frame_ms)

    # Render frames from terminal snapshots
    for cmd in log.commands:
        if cmd.intermediate_snapshots and cmd.terminal_after:
            total_duration = cmd.duration_ms if cmd.duration_ms else int(1000 / fps)
            snapshot_count = len(cmd.intermediate_snapshots) + 1
            snapshot_duration = total_duration // snapshot_count

            for snapshot in cmd.intermediate_snapshots:
                frame = renderer.render_simple(
                    lines=snapshot.screen_content,
                    cursor_pos=snapshot.cursor_position,
                )
                writer.add_frame(frame, duration_ms=snapshot_duration)

            frame = renderer.render_simple(
                lines=cmd.terminal_after.screen_content,
                cursor_pos=cmd.terminal_after.cursor_position,
            )
            writer.add_frame(frame, duration_ms=snapshot_duration)
        elif cmd.terminal_after:
            frame = renderer.render_simple(
                lines=cmd.terminal_after.screen_content,
                cursor_pos=cmd.terminal_after.cursor_position,
            )
            duration_ms = cmd.duration_ms if cmd.duration_ms else int(1000 / fps)
            writer.add_frame(frame, duration_ms=duration_ms)

    # Add final state if available and different from last command
    if log.final_terminal_state:
        frame = renderer.render_simple(
            lines=log.final_terminal_state.screen_content,
            cursor_pos=log.final_terminal_state.cursor_position,
        )
        writer.add_frame(frame, duration_ms=500)  # Hold final frame

    # Save the GIF
    if writer.frames:
        writer.save_optimized()
    else:
        raise ValueError("No frames to render - log has no terminal snapshots")
