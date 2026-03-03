"""Main engine orchestrating terminal recording."""

import copy
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from reterm.core.events import EventCollector
from reterm.core.pty_manager import PTYConfig, PTYManager
from reterm.core.terminal import Terminal, TerminalConfig
from reterm.output.models import RecordingLog, Script, Step, TerminalSnapshot

if TYPE_CHECKING:
    from reterm.render.frame import FrameRenderer


def parse_duration(duration_str: str) -> float:
    """Parse a duration string like '50ms', '1s', '2m' to seconds."""
    duration_str = duration_str.strip().lower()

    match = re.match(r"^(\d+(?:\.\d+)?)\s*(ms|s|m)?$", duration_str)
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}")

    value = float(match.group(1))
    unit = match.group(2) or "s"

    if unit == "ms":
        return value / 1000
    elif unit == "s":
        return value
    elif unit == "m":
        return value * 60
    else:
        return value


@dataclass
class EngineConfig:
    """Configuration for the engine."""

    shell: str | None = None
    theme: str = "dracula"
    terminal_size: tuple[int, int] = (80, 24)  # cols, rows
    typing_speed: float = 0.05  # seconds between characters
    generate_gif: bool = True
    frame_rate: int = 30
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class RecordingResult:
    """Result of a recording session."""

    log: RecordingLog
    frames: list[Image.Image]
    frame_durations: list[int]  # ms per frame

    def save_log(self, path: Path) -> None:
        """Save the log to a JSON file."""
        path.write_text(self.log.model_dump_json(indent=2))

    def save_gif(self, path: Path) -> None:
        """Save frames as an animated GIF."""
        if not self.frames:
            raise ValueError("No frames to save")

        from reterm.render.gif import GIFWriter

        writer = GIFWriter(path)
        for frame, duration in zip(self.frames, self.frame_durations):
            writer.add_frame(frame, duration)
        writer.save()


class Engine:
    """Main engine for terminal recording."""

    def __init__(
        self,
        shell: str | None = None,
        theme: str = "dracula",
        terminal_size: tuple[int, int] | None = None,
        typing_speed: float = 0.05,
        generate_gif: bool = True,
        frame_rate: int = 30,
        env: dict[str, str] | None = None,
    ) -> None:
        self.config = EngineConfig(
            shell=shell or os.environ.get("SHELL", "/bin/zsh"),
            theme=theme,
            terminal_size=terminal_size or (80, 24),
            typing_speed=typing_speed,
            generate_gif=generate_gif,
            frame_rate=frame_rate,
            env=env or {},
        )

        self.pty: PTYManager | None = None
        self.terminal: Terminal | None = None
        self.events: EventCollector | None = None
        self.renderer: "FrameRenderer | None" = None

        self.frames: list[Image.Image] = []
        self.frame_durations: list[int] = []

        self._frame_interval = 1.0 / frame_rate
        self._last_frame_time = 0.0
        self._recording_hidden = False

    def run(self, script: Script) -> RecordingResult:
        """Run a script and return the result."""
        # Apply script config
        if script.config.shell:
            self.config.shell = script.config.shell
        if script.config.theme:
            self.config.theme = script.config.theme
        if script.config.size:
            self.config.terminal_size = tuple(script.config.size)  # type: ignore
        if script.config.typing_speed:
            self.config.typing_speed = parse_duration(script.config.typing_speed)

        # Merge environment
        env = {**self.config.env, **script.env}

        # Initialize components
        cols, rows = self.config.terminal_size
        self.terminal = Terminal(TerminalConfig(rows=rows, cols=cols))
        self.events = EventCollector(
            script_file=script.meta.name,
            shell=self.config.shell,
            theme=self.config.theme,
            terminal_size=self.config.terminal_size,
        )

        if self.config.generate_gif:
            from reterm.render.frame import FrameRenderer
            from reterm.render.themes import get_theme

            theme_colors = get_theme(self.config.theme)
            self.renderer = FrameRenderer(
                cols=cols,
                rows=rows,
                theme=theme_colors,
            )

        # Start PTY
        pty_config = PTYConfig(
            shell=self.config.shell,
            rows=rows,
            cols=cols,
            env=env,
        )

        with PTYManager(pty_config) as pty:
            self.pty = pty

            # Connect PTY output to terminal
            def on_output(data: str) -> None:
                if self.terminal:
                    self.terminal.feed(data)

            pty.add_output_callback(on_output)

            # Start recording
            self.events.start_recording()

            # Wait for shell to initialize
            pty.read_until_idle(idle_timeout=0.3, max_timeout=2.0)
            self._capture_frame()

            # Execute steps
            for i, step in enumerate(script.steps):
                try:
                    self._execute_step(step, i)
                except Exception as e:
                    self.events.record_error(
                        error_type=type(e).__name__,
                        message=str(e),
                        step_index=i,
                    )
                    raise

            # Final capture
            self._capture_frame()
            final_state = self.terminal.snapshot() if self.terminal else None
            self.events.stop_recording(final_state)

        # Build result
        log = self.events.build_log()
        return RecordingResult(
            log=log,
            frames=self.frames,
            frame_durations=self.frame_durations,
        )

    def _execute_step(self, step: Step, index: int) -> None:
        """Execute a single step."""
        step_type = step.get_step_type()

        if step_type == "run":
            self._execute_run(step)
        elif step_type == "type":
            self._execute_type(step)
        elif step_type == "sleep":
            self._execute_sleep(step)
        elif step_type == "key":
            self._execute_key(step)
        elif step_type == "screenshot":
            self._execute_screenshot(step)
        elif step_type == "note":
            self._execute_note(step)
        elif step_type == "wait_for":
            self._execute_wait_for(step)
        else:
            raise ValueError(f"Unknown step type: {step_type}")

        # Record step execution
        if self.events:
            self.events.record_step(
                step_type=step_type,
                hidden=step.hidden,
            )

    # Unique markers for probing shell state - unlikely to collide with real output
    _EXIT_CODE_MARKER = "___RETERM_EC:"
    _CWD_MARKER = "___RETERM_CWD:"

    def _execute_run(self, step: Step) -> None:
        """Execute a run command."""
        if not self.pty or not self.terminal or not self.events:
            raise RuntimeError("Engine not initialized")

        command = self._interpolate(step.run or "")

        # Capture state before
        terminal_before = self.terminal.snapshot()
        started_at = datetime.now()

        # Type the command (no animation for run)
        self.pty.write_line(command)

        # Wait for output and capture frames, collecting intermediate snapshots
        intermediate_snapshots: list[TerminalSnapshot] = []
        self._read_and_capture(
            idle_timeout=0.5,
            max_timeout=30.0,
            intermediate_snapshots=intermediate_snapshots,
        )

        # Capture state after command output (this is what the user sees)
        terminal_after = self.terminal.snapshot()
        finished_at = datetime.now()

        # Extract output from terminal (before injecting probes)
        stdout = self._extract_command_output(
            terminal_before.screen_content_plain,
            terminal_after.screen_content_plain,
        )

        # Capture exit code and working directory via hidden probes
        exit_code, working_directory = self._capture_shell_state()

        # Record command
        cmd = self.events.record_command(
            command=command,
            stdout=stdout,
            stderr="",
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            working_directory=working_directory,
            terminal_before=terminal_before,
            terminal_after=terminal_after,
            intermediate_snapshots=intermediate_snapshots,
        )

        # Handle capture
        if step.capture:
            self.events.capture_variable(step.capture, stdout)

        # Handle expect
        if step.expect:
            self._check_expectations(step.expect, cmd.exit_code, stdout)

    def _capture_shell_state(self) -> tuple[int, str]:
        """Capture exit code and working directory by injecting probe commands.

        Sends a single compound echo that outputs both markers, then parses
        the result from terminal output.

        Returns:
            (exit_code, working_directory) - exit_code is -1 if parsing fails,
            working_directory is "." if parsing fails.
        """
        if not self.pty or not self.terminal:
            return (-1, ".")

        ec_marker = self._EXIT_CODE_MARKER
        cwd_marker = self._CWD_MARKER

        # Hide recording so probe output doesn't appear in GIF frames
        self._recording_hidden = True

        # Save terminal state so probe output doesn't leak into subsequent frames
        saved_buffer = copy.deepcopy(self.terminal.screen.buffer)
        saved_cursor_x = self.terminal.screen.cursor.x
        saved_cursor_y = self.terminal.screen.cursor.y

        # Single probe: capture $? first (before it gets overwritten by pwd),
        # then capture pwd. Use a subshell-free approach to preserve $?.
        # The semicolon between the two echos will reset $?, so we save it first.
        self.pty.write_line(
            f'__rc=$?; echo "{ec_marker}$__rc___"; echo "{cwd_marker}$PWD___"'
        )
        self._read_and_capture(idle_timeout=0.3, max_timeout=5.0)

        # Read the terminal to find our markers
        screen_text = self.terminal.get_text()

        exit_code = self._parse_marker(screen_text, ec_marker, default="-1")
        cwd_raw = self._parse_marker(screen_text, cwd_marker, default=".")

        # Restore terminal state to erase probe output
        self.terminal.screen.buffer = saved_buffer
        self.terminal.screen.cursor.x = saved_cursor_x
        self.terminal.screen.cursor.y = saved_cursor_y

        self._recording_hidden = False

        try:
            exit_code_int = int(exit_code)
        except ValueError:
            exit_code_int = -1

        return (exit_code_int, cwd_raw)

    @staticmethod
    def _parse_marker(screen_text: str, marker: str, default: str = "") -> str:
        """Parse a value from terminal text between a marker prefix and '___' suffix."""
        for line in screen_text.split("\n"):
            line = line.strip()
            if line.startswith(marker) and line.endswith("___"):
                return line[len(marker):-3]
        return default

    def _execute_type(self, step: Step) -> None:
        """Execute a type command with animation."""
        if not self.pty:
            raise RuntimeError("Engine not initialized")

        text = self._interpolate(step.type or "")

        # Type character by character with animation
        for char in text:
            self.pty.write(char)
            self._read_and_capture(
                idle_timeout=self.config.typing_speed,
                max_timeout=self.config.typing_speed * 2,
            )

        # Handle 'then' action
        if step.then:
            then_lower = step.then.lower()
            if then_lower == "enter":
                self.pty.send_key("enter")
                self._read_and_capture(idle_timeout=0.5, max_timeout=30.0)
            else:
                self.pty.send_key(step.then)
                self._read_and_capture(idle_timeout=0.3, max_timeout=5.0)

    def _execute_sleep(self, step: Step) -> None:
        """Execute a sleep command."""
        duration = parse_duration(step.sleep or "1s")

        # Capture frames during sleep
        end_time = time.time() + duration
        while time.time() < end_time:
            self._capture_frame()
            time.sleep(self._frame_interval)

    def _execute_key(self, step: Step) -> None:
        """Execute a key press."""
        if not self.pty:
            raise RuntimeError("Engine not initialized")

        self.pty.send_key(step.key or "")
        self._read_and_capture(idle_timeout=0.3, max_timeout=5.0)

    def _execute_screenshot(self, step: Step) -> None:
        """Execute a screenshot command."""
        self._capture_frame(force=True)

        if self.events:
            self.events.record_step(
                step_type="screenshot",
                filename=step.screenshot,
            )

    def _execute_note(self, step: Step) -> None:
        """Execute a note command (log only, no terminal effect)."""
        if self.events:
            self.events.record_step(
                step_type="note",
                message=step.note,
            )

    def _execute_wait_for(self, step: Step) -> None:
        """Wait for specific output pattern before continuing."""
        if not self.pty or not self.terminal:
            raise RuntimeError("Engine not initialized")

        pattern = step.wait_for or ""
        timeout_seconds = parse_duration(step.timeout or "10s")
        is_regex = step.regex

        start_time = time.time()

        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout_seconds:
                raise TimeoutError(
                    f"Timed out after {timeout_seconds}s waiting for: {pattern}"
                )

            # Read any new output
            self.pty.read(timeout=0.1)

            # Check if pattern matches current terminal content
            terminal_text = self.terminal.get_text()

            if is_regex:
                if re.search(pattern, terminal_text):
                    break
            else:
                if pattern in terminal_text:
                    break

            # Capture frame while waiting
            self._capture_frame()

    def _read_and_capture(
        self,
        idle_timeout: float = 0.5,
        max_timeout: float = 30.0,
        intermediate_snapshots: list[TerminalSnapshot] | None = None,
    ) -> None:
        """Read PTY output and capture frames.

        Args:
            idle_timeout: Timeout to wait for more output
            max_timeout: Maximum total time to wait
            intermediate_snapshots: Optional list to collect terminal snapshots during execution
        """
        if not self.pty:
            return

        start_time = time.time()
        last_output_time = time.time()
        last_snapshot_time = 0.0
        snapshot_interval = 0.1  # Capture intermediate snapshot every 100ms

        while True:
            elapsed = time.time() - start_time
            if elapsed >= max_timeout:
                break

            idle_time = time.time() - last_output_time
            if idle_time >= idle_timeout:
                break

            # Read output
            output = self.pty.read(timeout=self._frame_interval)
            if output:
                last_output_time = time.time()

                # Capture intermediate snapshot when there's output
                now = time.time()
                if (
                    intermediate_snapshots is not None
                    and self.terminal
                    and (now - last_snapshot_time) >= snapshot_interval
                ):
                    intermediate_snapshots.append(self.terminal.snapshot())
                    last_snapshot_time = now

            # Capture frame
            self._capture_frame()

    def _capture_frame(self, force: bool = False) -> None:
        """Capture a frame if enough time has passed."""
        if self._recording_hidden:
            return

        if not self.config.generate_gif or not self.renderer or not self.terminal:
            return

        now = time.time()
        if not force and (now - self._last_frame_time) < self._frame_interval:
            return

        # Get styled terminal content
        styled_lines = self.terminal.get_styled_lines()
        cursor_pos = self.terminal.get_cursor_position()

        # Render frame
        frame = self.renderer.render(styled_lines, cursor_pos)
        self.frames.append(frame)

        # Calculate duration (enforce minimum to avoid 0ms frames)
        if self._last_frame_time > 0:
            duration_ms = max(
                int((now - self._last_frame_time) * 1000),
                int(1000 / self.config.frame_rate),
            )
        else:
            duration_ms = int(1000 / self.config.frame_rate)
        self.frame_durations.append(duration_ms)

        self._last_frame_time = now

    def _interpolate(self, text: str) -> str:
        """Interpolate ${variable} references in text."""
        if not self.events:
            return text

        def replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            value = self.events.get_variable(var_name) if self.events else None
            if value is not None:
                return value
            # Check environment
            return os.environ.get(var_name, match.group(0))

        return re.sub(r"\$\{(\w+)\}", replace, text)

    def _extract_command_output(self, before: str, after: str) -> str:
        """Extract command output by comparing terminal states.

        Strategy: find the first and last changed lines. The first changed line
        is typically the command echo, the last is the new prompt. Everything
        between them is the output.

        Handles scrolling by comparing from both ends to find the stable
        boundaries.
        """
        before_lines = [l.rstrip() for l in before.split("\n")]
        after_lines = [l.rstrip() for l in after.split("\n")]

        # Find first line that differs
        first_diff = 0
        for i in range(min(len(before_lines), len(after_lines))):
            if before_lines[i] != after_lines[i]:
                first_diff = i
                break
        else:
            # All shared lines are the same - check if after has more lines
            first_diff = min(len(before_lines), len(after_lines))

        # Find last line that differs (scan from bottom)
        last_diff = len(after_lines) - 1
        b_end = len(before_lines) - 1
        a_end = len(after_lines) - 1
        while b_end >= first_diff and a_end >= first_diff:
            if before_lines[b_end].rstrip() != after_lines[a_end].rstrip():
                break
            b_end -= 1
            a_end -= 1
        last_diff = a_end

        # Extract the changed region
        changed = after_lines[first_diff : last_diff + 1]

        if not changed:
            return ""

        # Skip the command echo (first changed line) and new prompt (last changed line)
        # But only if there are enough lines - a single changed line means either
        # just the command echo or just output on one line
        if len(changed) == 1:
            # Single changed line - could be the command echo with no output
            return ""
        elif len(changed) == 2:
            # Two changed lines: command echo + prompt, no output between them
            return ""
        else:
            # Skip first (command echo) and last (new prompt)
            output_lines = changed[1:-1]
            return "\n".join(output_lines).strip()

    def _check_expectations(
        self,
        expect: "Step.expect",  # type: ignore
        exit_code: int,
        output: str,
    ) -> None:
        """Check if output meets expectations."""
        from reterm.output.models import ExpectClause

        if not isinstance(expect, ExpectClause):
            return

        if expect.exit_code is not None and exit_code != expect.exit_code:
            raise AssertionError(
                f"Expected exit code {expect.exit_code}, got {exit_code}"
            )

        if expect.contains is not None and expect.contains not in output:
            raise AssertionError(
                f"Expected output to contain '{expect.contains}'"
            )

        if expect.not_contains is not None and expect.not_contains in output:
            raise AssertionError(
                f"Expected output to not contain '{expect.not_contains}'"
            )

        if expect.matches is not None:
            if not re.search(expect.matches, output):
                raise AssertionError(
                    f"Expected output to match '{expect.matches}'"
                )
