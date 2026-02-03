"""Tests for the output models module."""

from datetime import datetime

from reterm.output.models import (
    CommandExecution,
    RecordingLog,
    RecordingMetadata,
    StyledChar,
    TerminalSnapshot,
)


class TestStyledChar:
    """Tests for StyledChar model."""

    def test_defaults(self):
        sc = StyledChar(char="A")
        assert sc.fg == "default"
        assert sc.bg == "default"
        assert sc.bold is False
        assert sc.italic is False
        assert sc.underline is False
        assert sc.reverse is False

    def test_with_styles(self):
        sc = StyledChar(char="X", fg="red", bg="blue", bold=True, italic=True)
        assert sc.fg == "red"
        assert sc.bg == "blue"
        assert sc.bold is True
        assert sc.italic is True

    def test_serialization_roundtrip(self):
        sc = StyledChar(char="Z", fg="brightgreen", bold=True)
        data = sc.model_dump()
        sc2 = StyledChar.model_validate(data)
        assert sc == sc2


class TestTerminalSnapshot:
    """Tests for TerminalSnapshot model."""

    def test_without_styled_content(self):
        snap = TerminalSnapshot(
            timestamp=datetime.now(),
            cursor_position=(0, 0),
            screen_content=["hello", "world"],
            screen_content_plain="hello\nworld",
            dimensions=(24, 80),
        )
        assert snap.styled_content is None

    def test_with_styled_content(self):
        styled = [[StyledChar(char="h", fg="red"), StyledChar(char="i")]]
        snap = TerminalSnapshot(
            timestamp=datetime.now(),
            cursor_position=(0, 2),
            screen_content=["hi"],
            screen_content_plain="hi",
            dimensions=(24, 80),
            styled_content=styled,
        )
        assert snap.styled_content is not None
        assert len(snap.styled_content) == 1
        assert snap.styled_content[0][0].fg == "red"


class TestRecordingLogDerivedFields:
    """Tests for RecordingLog computed derived fields."""

    def _make_log(self, commands: list[CommandExecution]) -> RecordingLog:
        now = datetime.now()
        metadata = RecordingMetadata(
            tool_version="0.1.0",
            started_at=now,
            finished_at=now,
            total_duration_ms=0,
            shell="/bin/zsh",
            terminal_size=(80, 24),
            theme="dracula",
            platform="linux",
            python_version="3.12.0",
        )
        return RecordingLog(metadata=metadata, commands=commands)

    def _make_cmd(self, command: str, exit_code: int, stdout: str = "") -> CommandExecution:
        now = datetime.now()
        return CommandExecution(
            id="cmd_001",
            command=command,
            started_at=now,
            finished_at=now,
            duration_ms=100,
            exit_code=exit_code,
            stdout=stdout,
            stderr="",
            combined_output=stdout,
            working_directory="/tmp",
        )

    def test_all_success(self):
        cmds = [
            self._make_cmd("echo hello", 0, "hello"),
            self._make_cmd("ls", 0, "file.txt"),
        ]
        log = self._make_log(cmds)
        assert log.success is True
        assert log.failed_commands == []
        assert log.all_commands_text == "echo hello\nls"

    def test_with_failures(self):
        cmds = [
            self._make_cmd("echo hello", 0, "hello"),
            self._make_cmd("false", 1),
            self._make_cmd("bad_cmd", 127),
        ]
        log = self._make_log(cmds)
        assert log.success is False
        assert log.failed_commands == ["false", "bad_cmd"]

    def test_empty_commands(self):
        log = self._make_log([])
        assert log.success is True
        assert log.all_commands_text == ""
        assert log.all_output_text == ""

    def test_recompute_after_modification(self):
        cmds = [self._make_cmd("echo hi", 0, "hi")]
        log = self._make_log(cmds)
        assert log.success is True

        # Add a failed command and recompute
        log.commands.append(self._make_cmd("fail", 1))
        log.compute_derived_fields()
        assert log.success is False
        assert log.failed_commands == ["fail"]
