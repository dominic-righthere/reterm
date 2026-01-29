"""Event collection for structured logging."""

import platform
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from reterm.output.models import (
    CommandExecution,
    RecordingLog,
    RecordingMetadata,
    StepExecution,
    TerminalSnapshot,
)


class EventCollector:
    """Collects events during recording for structured output."""

    def __init__(
        self,
        script_file: str | Path | None = None,
        shell: str = "/bin/zsh",
        theme: str = "dracula",
        terminal_size: tuple[int, int] = (80, 24),
    ) -> None:
        self.script_file = str(script_file) if script_file else None
        self.shell = shell
        self.theme = theme
        self.terminal_size = terminal_size

        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None

        self.commands: list[CommandExecution] = []
        self.steps: list[StepExecution] = []
        self.errors: list[dict[str, Any]] = []
        self.captured_variables: dict[str, str] = {}

        self.final_terminal_state: TerminalSnapshot | None = None

        self._command_counter = 0

    def start_recording(self) -> None:
        """Mark the start of recording."""
        self.started_at = datetime.now()

    def stop_recording(self, final_state: TerminalSnapshot | None = None) -> None:
        """Mark the end of recording."""
        self.finished_at = datetime.now()
        self.final_terminal_state = final_state

    def record_command(
        self,
        command: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        started_at: datetime,
        finished_at: datetime,
        working_directory: str = ".",
        terminal_before: TerminalSnapshot | None = None,
        terminal_after: TerminalSnapshot | None = None,
        intermediate_snapshots: list[TerminalSnapshot] | None = None,
    ) -> CommandExecution:
        """Record a command execution."""
        self._command_counter += 1
        cmd_id = f"cmd_{self._command_counter:03d}"

        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        execution = CommandExecution(
            id=cmd_id,
            command=command,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            combined_output=stdout + stderr,  # simplified; real would interleave
            working_directory=working_directory,
            terminal_before=terminal_before,
            terminal_after=terminal_after,
            intermediate_snapshots=intermediate_snapshots or [],
        )

        self.commands.append(execution)
        return execution

    def record_step(
        self,
        step_type: str,
        timestamp: datetime | None = None,
        duration_ms: int | None = None,
        **details: Any,
    ) -> StepExecution:
        """Record a step execution."""
        step = StepExecution(
            type=step_type,
            timestamp=timestamp or datetime.now(),
            duration_ms=duration_ms,
            details=details,
        )
        self.steps.append(step)
        return step

    def record_error(
        self,
        error_type: str,
        message: str,
        step_index: int | None = None,
        **details: Any,
    ) -> None:
        """Record an error that occurred during execution."""
        error = {
            "id": str(uuid.uuid4())[:8],
            "type": error_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "step_index": step_index,
            **details,
        }
        self.errors.append(error)

    def capture_variable(self, name: str, value: str) -> None:
        """Capture a variable value for interpolation."""
        self.captured_variables[name] = value.strip()

    def get_variable(self, name: str) -> str | None:
        """Get a captured variable value."""
        return self.captured_variables.get(name)

    def build_log(self) -> RecordingLog:
        """Build the complete recording log."""
        if self.started_at is None:
            self.started_at = datetime.now()
        if self.finished_at is None:
            self.finished_at = datetime.now()

        total_duration_ms = int(
            (self.finished_at - self.started_at).total_seconds() * 1000
        )

        metadata = RecordingMetadata(
            tool_version="0.1.0",
            script_file=self.script_file,
            started_at=self.started_at,
            finished_at=self.finished_at,
            total_duration_ms=total_duration_ms,
            shell=self.shell,
            terminal_size=self.terminal_size,
            theme=self.theme,
            platform=platform.system().lower(),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )

        log = RecordingLog(
            metadata=metadata,
            commands=self.commands,
            steps=self.steps,
            final_terminal_state=self.final_terminal_state,
            errors=self.errors,
            captured_variables=self.captured_variables,
        )

        # Compute derived fields
        log.compute_derived_fields()

        return log
