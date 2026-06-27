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
from reterm.output.models import ExpectClause, RecordingLog, Script, Step, TerminalSnapshot

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
    # Per-frame styled terminal content (styled_lines, cursor_pos), index-aligned
    # with frame_durations. Used to render a colored animated SVG.
    styled_frames: list[tuple[list[list[tuple[str, dict]]], tuple[int, int]]] = field(
        default_factory=list
    )

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

    def save_svg(self, path: Path, theme: str | None = None) -> None:
        """Save the recording as an animated SVG (flipbook of the styled frames)."""
        if not self.styled_frames:
            raise ValueError("No frames to save")

        from reterm.render.svg import SvgWriter, cells_from_styled_tuples
        from reterm.render.themes import get_theme

        cols, rows = self.log.metadata.terminal_size
        theme_obj = get_theme(theme or self.log.metadata.theme)
        writer = SvgWriter(path, theme_obj, cols, rows)
        for (styled_lines, cursor_pos), duration in zip(
            self.styled_frames, self.frame_durations
        ):
            writer.add_frame(cells_from_styled_tuples(styled_lines), cursor_pos, duration)
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
        self.styled_frames: list[tuple[list[list[tuple[str, dict]]], tuple[int, int]]] = []

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

        # Resolve the shell to a concrete path (never None past this point)
        shell = self.config.shell or os.environ.get("SHELL", "/bin/zsh")
        self.config.shell = shell

        # Initialize components
        cols, rows = self.config.terminal_size
        self.terminal = Terminal(TerminalConfig(rows=rows, cols=cols))
        self.events = EventCollector(
            script_file=script.meta.name,
            shell=shell,
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
            shell=shell,
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

            # One-time hidden setup before recording any steps
            self._prepare_shell()

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
            styled_frames=self.styled_frames,
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

    # Disable interactive history expansion so commands containing '!'
    # (e.g. echo "Done!") don't trigger history substitution, which would
    # otherwise wedge the shell into a continuation/error state and corrupt
    # the rest of the recording. zsh uses `unsetopt banghist`; bash uses
    # `set +H`. Each errors harmlessly in the other shell, so send both and
    # swallow stderr.
    _SHELL_SETUP = "unsetopt banghist 2>/dev/null; set +H 2>/dev/null"

    # OSC 133 shell-integration hooks. The shell emits invisible escape marks
    # around each command so reterm can slice exact per-command output and read
    # the real exit code straight from the byte stream — the same mechanism
    # iTerm2/WezTerm/kitty/VS Code use. The D hook is *prepended* to precmd so
    # it fires before the prompt theme's own precmds (titles, PROMPT_SP); the C
    # hook is appended to preexec so it fires right before output. BEL-terminated
    # (\007) marks are used because pyte ignores them, keeping the GIF clean.
    _ZSH_OSC133_SETUP = (
        # Disable zsh-autosuggestions for the session: otherwise the grey
        # history suggestion (e.g. reterm's own setup line, or a prior command)
        # is drawn on screen and leaks into recorded frames. Recordings should
        # show only what's typed.
        "ZSH_AUTOSUGGEST_STRATEGY=() 2>/dev/null; "
        "__rt_pe(){ printf '\\033]133;C\\007' }; "
        "__rt_pc(){ local rc=$?; printf '\\033]133;D;%s\\007' \"$rc\"; "
        "printf '\\033]1337;Cwd=%s\\007' \"$PWD\" }; "
        "typeset -ag preexec_functions precmd_functions; "
        "preexec_functions+=(__rt_pe); precmd_functions=(__rt_pc $precmd_functions)"
    )
    # PS0 (output start) needs bash >= 4.4; guard so older bash (e.g. macOS's
    # 3.2) is left untouched and cleanly uses the snapshot+probe fallback.
    _BASH_OSC133_SETUP = (
        "if [ \"${BASH_VERSINFO:-0}\" -ge 5 ] || "
        "{ [ \"${BASH_VERSINFO:-0}\" -eq 4 ] && [ \"${BASH_VERSINFO[1]:-0}\" -ge 4 ]; }; then "
        "PS0=$'\\033]133;C\\007'; "
        "PROMPT_COMMAND='__rt_rc=$?; printf \"\\033]133;D;%s\\007\" \"$__rt_rc\"; "
        "printf \"\\033]1337;Cwd=%s\\007\" \"$PWD\"; '\"$PROMPT_COMMAND\"; fi"
    )

    def _shell_setup_commands(self) -> str:
        """Build the one-time hidden setup line for the active shell."""
        parts = [self._SHELL_SETUP]
        shell_name = os.path.basename(self.config.shell or "")
        if "zsh" in shell_name:
            parts.append(self._ZSH_OSC133_SETUP)
        elif "bash" in shell_name:
            parts.append(self._BASH_OSC133_SETUP)
        return "; ".join(parts)

    def _prepare_shell(self) -> None:
        """Send one-time hidden setup to the shell before recording steps.

        Disables history expansion and installs OSC 133 shell-integration hooks
        (when the shell supports them). Mirrors the hide/save/restore pattern
        used by ``_capture_shell_state`` so the setup and its echoed prompt never
        appear in the GIF or in any command's terminal snapshots.
        """
        if not self.pty or not self.terminal:
            return

        self._recording_hidden = True
        saved_buffer = copy.deepcopy(self.terminal.screen.buffer)
        saved_cursor_x = self.terminal.screen.cursor.x
        saved_cursor_y = self.terminal.screen.cursor.y

        # Append a sentinel echo and block until it appears, so ALL of the
        # (long, multi-line) setup echo is consumed while hidden. Without this
        # barrier, late-arriving setup bytes can land after we un-hide and leak
        # the hook definitions into recorded frames.
        sentinel = "__RT_SETUP_DONE__"
        self.pty.write_line(f"{self._shell_setup_commands()}; echo {sentinel}")
        deadline = time.time() + 5.0
        while time.time() < deadline:
            self.pty.read(timeout=0.05)
            if sentinel in self.terminal.get_text():
                break
        # Drain the prompt redraw that follows the sentinel (still hidden).
        self._read_and_capture(idle_timeout=0.2, max_timeout=1.0)

        self.terminal.screen.buffer = saved_buffer
        self.terminal.screen.cursor.x = saved_cursor_x
        self.terminal.screen.cursor.y = saved_cursor_y
        self._recording_hidden = False

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

        # Wait for output, capturing frames, intermediate snapshots, and the raw
        # PTY byte stream (so we can slice exact output from OSC 133 marks).
        intermediate_snapshots: list[TerminalSnapshot] = []
        raw_chunks: list[str] = []
        self._read_and_capture(
            idle_timeout=0.5,
            max_timeout=30.0,
            intermediate_snapshots=intermediate_snapshots,
            output_accumulator=raw_chunks,
        )

        # Capture state after command output (this is what the user sees)
        terminal_after = self.terminal.snapshot()
        finished_at = datetime.now()

        # Primary: exact output/exit/cwd from OSC 133 shell-integration marks.
        # This captures full output regardless of screen height (it reads the
        # raw stream, not the scrolled screen) and handles output with no
        # trailing newline. Falls back to snapshot diff + a hidden state probe
        # for shells without integration.
        marked = self._extract_marked_output("".join(raw_chunks))
        if marked is not None:
            stdout, exit_code, cwd = marked
            working_directory = cwd if cwd is not None else "."
        else:
            stdout = self._extract_command_output(
                terminal_before.screen_content_plain,
                terminal_after.screen_content_plain,
                command,
            )
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
        # Braces are required around the variable names: the marker suffix is
        # "___", and without braces the shell would read "$__rc___" / "$PWD___"
        # as the (undefined) variable names "__rc___" / "PWD___" since
        # underscores are valid identifier characters, yielding empty markers.
        self.pty.write_line(
            f'__rc=$?; echo "{ec_marker}${{__rc}}___"; echo "{cwd_marker}${{PWD}}___"'
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

    # OSC 133 shell-integration marks emitted by the hooks in _prepare_shell:
    #   ESC ] 133 ; C BEL            -> output start (preexec)
    #   ESC ] 133 ; D ; <exit> BEL   -> command finished, with exit code (precmd)
    #   ESC ] 1337 ; Cwd=<path> BEL  -> working directory (precmd)
    _OSC133_RE = re.compile(r"\x1b\]133;C\x07(.*?)\x1b\]133;D;(\d+)\x07", re.DOTALL)
    _OSC_CWD_RE = re.compile(r"\x1b\]1337;Cwd=(.*?)\x07")
    # Control sequences to strip from captured raw output for the structured log:
    # OSC strings (BEL- or ST-terminated), CSI / charset escapes, and CRs.
    _OSC_STRIP_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
    _CSI_STRIP_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b[=>NODEM()][AB012]?")
    # zsh PROMPT_SP partial-line marker shown after output with no trailing newline.
    _PROMPTSP_RE = re.compile(r"%\s*$")

    @classmethod
    def _strip_terminal_sequences(cls, text: str) -> str:
        """Strip escape/control sequences from raw output for the structured log."""
        text = cls._OSC_STRIP_RE.sub("", text)
        text = cls._CSI_STRIP_RE.sub("", text)
        text = text.replace("\r", "")
        text = cls._PROMPTSP_RE.sub("", text)
        return text

    @classmethod
    def _extract_marked_output(cls, raw: str) -> tuple[str, int, str | None] | None:
        """Extract (stdout, exit_code, cwd) from OSC 133 marks in a raw PTY stream.

        The output is the exact bytes between the ``C`` (output start) and ``D``
        (command finished) marks, so it is immune to terminal scrolling and to
        output with no trailing newline. Returns ``None`` when the marks are
        absent (a shell without integration), so the caller falls back to
        snapshot-based extraction.
        """
        match = cls._OSC133_RE.search(raw)
        if match is None:
            return None

        stdout = cls._strip_terminal_sequences(match.group(1)).strip("\n").rstrip()
        exit_code = int(match.group(2))
        cwd_match = cls._OSC_CWD_RE.search(raw)
        cwd = cwd_match.group(1) if cwd_match else None
        return (stdout, exit_code, cwd)

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
        output_accumulator: list[str] | None = None,
    ) -> None:
        """Read PTY output and capture frames.

        Args:
            idle_timeout: Timeout to wait for more output
            max_timeout: Maximum total time to wait
            intermediate_snapshots: Optional list to collect terminal snapshots during execution
            output_accumulator: Optional list to collect the raw PTY output chunks
                (used to slice exact command output from OSC 133 marks)
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

                if output_accumulator is not None:
                    output_accumulator.append(output)

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
        # Keep the styled content too, for rendering a colored animated SVG.
        self.styled_frames.append((styled_lines, cursor_pos))

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

    def _extract_command_output(self, before: str, after: str, command: str) -> str:
        """Extract command output from the post-command terminal screen.

        Primary strategy (scroll-tolerant): locate the command-echo line in the
        ``after`` screen by matching the command text as a line suffix, then
        return everything between it and the trailing prompt. Reading a single
        post-command screen makes this immune to scrolling that shifts absolute
        line indices — which is what broke the older before/after diff once a
        recording grew past the screen height.

        Falls back to the before/after diff when the echo line can't be located
        (e.g. output so tall it scrolled the command line off the top).
        """
        cmd = command.strip()
        after_lines = [line.rstrip() for line in after.split("\n")]

        if cmd:
            echo_idx: int | None = None
            for i, line in enumerate(after_lines):
                # The echo line is "<prompt><command>", so the command appears
                # as a suffix. Require the char before it to be a non-word char
                # (prompt boundary) so e.g. "update" doesn't match command "date".
                if line.endswith(cmd):
                    prefix = line[: len(line) - len(cmd)]
                    if not prefix or not prefix[-1].isalnum():
                        echo_idx = i
                        break

            if echo_idx is not None:
                # Trailing prompt = last non-empty line below the echo
                last = len(after_lines) - 1
                while last > echo_idx and not after_lines[last].strip():
                    last -= 1
                output_lines = after_lines[echo_idx + 1 : last]
                while output_lines and not output_lines[-1].strip():
                    output_lines.pop()
                return "\n".join(output_lines).strip()

        return self._extract_output_diff(before, after)

    def _extract_output_diff(self, before: str, after: str) -> str:
        """Fallback output extraction by diffing before/after terminal states.

        Finds the first and last changed lines: the first is typically the
        command echo, the last the new prompt, and everything between is output.
        Used when the command-echo line can't be located on the after screen.
        """
        before_lines = [line.rstrip() for line in before.split("\n")]
        after_lines = [line.rstrip() for line in after.split("\n")]

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
        expect: ExpectClause,
        exit_code: int,
        output: str,
    ) -> None:
        """Check if output meets expectations."""
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
