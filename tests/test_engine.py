"""Tests for the engine module."""

import pytest

from reterm.core.engine import Engine


class TestParseMarker:
    """Tests for Engine._parse_marker (exit code and cwd extraction)."""

    def test_exit_code_zero(self):
        screen = "some output\n___RETERM_EC:0___\n$ "
        result = Engine._parse_marker(screen, "___RETERM_EC:", default="-1")
        assert result == "0"

    def test_exit_code_nonzero(self):
        screen = "ls: No such file\n___RETERM_EC:127___\n$ "
        result = Engine._parse_marker(screen, "___RETERM_EC:", default="-1")
        assert result == "127"

    def test_exit_code_not_found(self):
        screen = "some output\nno marker here\n$ "
        result = Engine._parse_marker(screen, "___RETERM_EC:", default="-1")
        assert result == "-1"

    def test_exit_code_with_surrounding_noise(self):
        screen = (
            "➜  project echo \"___RETERM_EC:$__rc___\"\n"
            "___RETERM_EC:1___\n"
            "➜  project "
        )
        result = Engine._parse_marker(screen, "___RETERM_EC:", default="-1")
        assert result == "1"

    def test_cwd_marker(self):
        screen = "___RETERM_CWD:/home/user/project___\n$ "
        result = Engine._parse_marker(screen, "___RETERM_CWD:", default=".")
        assert result == "/home/user/project"

    def test_cwd_with_spaces(self):
        screen = "___RETERM_CWD:/home/user/my project___\n$ "
        result = Engine._parse_marker(screen, "___RETERM_CWD:", default=".")
        assert result == "/home/user/my project"

    def test_cwd_not_found(self):
        screen = "some output\n$ "
        result = Engine._parse_marker(screen, "___RETERM_CWD:", default=".")
        assert result == "."

    def test_empty_screen(self):
        result = Engine._parse_marker("", "___RETERM_EC:", default="-1")
        assert result == "-1"

    def test_multiple_markers_returns_first(self):
        screen = "___RETERM_EC:0___\n___RETERM_EC:1___\n"
        result = Engine._parse_marker(screen, "___RETERM_EC:", default="-1")
        assert result == "0"


class TestExtractCommandOutput:
    """Tests for Engine._extract_command_output."""

    def _extract(self, before: str, after: str) -> str:
        engine = Engine(generate_gif=False)
        return engine._extract_command_output(before, after)

    def test_simple_output(self):
        before = "$ \n\n\n"
        after = "$ echo hello\nhello\n$ \n"
        result = self._extract(before, after)
        assert result == "hello"

    def test_multiline_output(self):
        before = "$ \n\n\n\n"
        after = "$ ls\nfile1.txt\nfile2.txt\n$ \n"
        result = self._extract(before, after)
        assert result == "file1.txt\nfile2.txt"

    def test_no_output(self):
        before = "$ \n\n"
        after = "$ cd /tmp\n$ \n"
        result = self._extract(before, after)
        assert result == ""

    def test_identical_screens(self):
        before = "$ \n\n"
        after = "$ \n\n"
        result = self._extract(before, after)
        assert result == ""

    def test_trailing_whitespace_ignored(self):
        before = "$ \n\n"
        after = "$ echo hi  \nhi\n$ \n"
        result = self._extract(before, after)
        assert result == "hi"
