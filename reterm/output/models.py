"""Pydantic models for structured JSON log output."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StyledChar(BaseModel):
    """A single character with ANSI style information."""

    char: str = Field(description="The character")
    fg: str = Field(default="default", description="Foreground color (name, hex, or 'default')")
    bg: str = Field(default="default", description="Background color (name, hex, or 'default')")
    bold: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False


class TerminalSnapshot(BaseModel):
    """Captures terminal state at a point in time."""

    timestamp: datetime
    cursor_position: tuple[int, int] = Field(description="(row, col)")
    screen_content: list[str] = Field(description="Each line of terminal content")
    screen_content_plain: str = Field(description="All lines joined with newlines")
    dimensions: tuple[int, int] = Field(description="(rows, cols)")
    styled_content: list[list[StyledChar]] | None = Field(
        default=None,
        description="Per-character styled content for each line. Each line is a list of StyledChar with fg/bg/bold/italic/underline/reverse attributes.",
    )


class CommandExecution(BaseModel):
    """A single command execution with full context.

    Note on stdout/stderr: Because commands run inside a PTY, stdout and stderr
    are merged into a single stream by the kernel. The ``stderr`` field will
    always be empty and ``stdout`` / ``combined_output`` both contain the merged
    PTY output. Use ``exit_code`` to determine success or failure.
    """

    id: str = Field(description="Unique identifier for this command")
    command: str = Field(description="The command that was executed")
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(description="Execution time in milliseconds")
    exit_code: int
    stdout: str = Field(
        description="Captured output (merged stdout+stderr from PTY)"
    )
    stderr: str = Field(
        default="",
        description="Always empty — PTY merges stderr into stdout. Kept for schema compatibility.",
    )
    combined_output: str = Field(
        description="Same as stdout (PTY merges both streams)"
    )
    working_directory: str = Field(description="CWD at execution time")
    terminal_before: TerminalSnapshot | None = None
    terminal_after: TerminalSnapshot | None = None
    intermediate_snapshots: list[TerminalSnapshot] = Field(
        default_factory=list,
        description="Terminal states captured during command execution"
    )


class StepExecution(BaseModel):
    """Any step from the script."""

    type: str = Field(description="Step type: run, type, sleep, screenshot, note, etc.")
    timestamp: datetime
    duration_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class RecordingMetadata(BaseModel):
    """Recording session metadata."""

    tool_version: str
    script_file: str | None = None
    started_at: datetime
    finished_at: datetime
    total_duration_ms: int
    shell: str
    terminal_size: tuple[int, int] = Field(description="(cols, rows)")
    theme: str
    platform: str
    python_version: str


class RecordingLog(BaseModel):
    """Complete recording output - the main export format for AI consumption."""

    schema_version: str = "1.0.0"
    metadata: RecordingMetadata
    commands: list[CommandExecution] = Field(
        default_factory=list, description="All commands with full data"
    )
    steps: list[StepExecution] = Field(
        default_factory=list, description="Full step timeline"
    )
    final_terminal_state: TerminalSnapshot | None = None
    errors: list[dict[str, Any]] = Field(
        default_factory=list, description="Any errors during recording"
    )
    captured_variables: dict[str, str] = Field(
        default_factory=dict, description="Variables captured during execution"
    )

    # AI-friendly computed fields
    all_commands_text: str = Field(
        default="", description="All commands newline-separated"
    )
    all_output_text: str = Field(default="", description="All output concatenated")
    success: bool = Field(
        default=True, description="True if all exit codes were 0"
    )
    failed_commands: list[str] = Field(
        default_factory=list, description="Commands with non-zero exit codes"
    )

    def compute_derived_fields(self) -> None:
        """Compute the AI-friendly derived fields from the commands."""
        self.all_commands_text = "\n".join(cmd.command for cmd in self.commands)
        self.all_output_text = "\n".join(cmd.combined_output for cmd in self.commands)
        self.failed_commands = [
            cmd.command for cmd in self.commands if cmd.exit_code != 0
        ]
        self.success = len(self.failed_commands) == 0

    def model_post_init(self, __context: Any) -> None:
        """Compute derived fields after initialization."""
        self.compute_derived_fields()


class ScriptConfig(BaseModel):
    """Configuration section of a .reterm script."""

    shell: str = "/bin/zsh"
    theme: str = "dracula"
    size: tuple[int, int] = Field(default=(80, 24), description="(cols, rows)")
    typing_speed: str = "50ms"
    frame_rate: int = 30


class ScriptMeta(BaseModel):
    """Metadata section of a .reterm script."""

    name: str = "Untitled Recording"
    description: str = ""
    author: str | None = None
    tags: list[str] = Field(default_factory=list)


class ScriptOutput(BaseModel):
    """Output section of a .reterm script."""

    gif: str | None = None
    log: str | None = None
    video: str | None = None


class ExpectClause(BaseModel):
    """Expectation clause for a step."""

    exit_code: int | None = None
    contains: str | None = None
    not_contains: str | None = None
    matches: str | None = None  # regex pattern


class Step(BaseModel):
    """A single step in a .reterm script."""

    # Step types - only one should be set
    run: str | None = None
    type: str | None = None  # with typing animation
    sleep: str | None = None
    screenshot: str | None = None
    note: str | None = None
    key: str | None = None  # special keys like Enter, Tab, Ctrl+C
    wait_for: str | None = None  # wait for output pattern before continuing

    # Modifiers
    then: str | None = None  # action after type, like "enter"
    capture: str | None = None  # variable name to capture output
    expect: ExpectClause | None = None
    hidden: bool = False  # don't show in GIF (but log it)
    timeout: str | None = None  # timeout for wait_for (default "10s")
    regex: bool = False  # if True, wait_for uses regex matching

    def get_step_type(self) -> str:
        """Get the type of this step."""
        if self.run is not None:
            return "run"
        if self.type is not None:
            return "type"
        if self.sleep is not None:
            return "sleep"
        if self.screenshot is not None:
            return "screenshot"
        if self.note is not None:
            return "note"
        if self.key is not None:
            return "key"
        if self.wait_for is not None:
            return "wait_for"
        return "unknown"


class Script(BaseModel):
    """Complete parsed .reterm script."""

    meta: ScriptMeta = Field(default_factory=ScriptMeta)
    config: ScriptConfig = Field(default_factory=ScriptConfig)
    output: ScriptOutput = Field(default_factory=ScriptOutput)
    env: dict[str, str] = Field(default_factory=dict)
    steps: list[Step] = Field(default_factory=list)
