"""Tests for the engine module."""


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
    """Tests for Engine._extract_command_output (scroll-tolerant extraction)."""

    def _extract(self, before: str, after: str, command: str) -> str:
        engine = Engine(generate_gif=False)
        return engine._extract_command_output(before, after, command)

    def test_simple_output(self):
        before = "$ \n\n\n"
        after = "$ echo hello\nhello\n$ \n"
        result = self._extract(before, after, "echo hello")
        assert result == "hello"

    def test_multiline_output(self):
        before = "$ \n\n\n\n"
        after = "$ ls\nfile1.txt\nfile2.txt\n$ \n"
        result = self._extract(before, after, "ls")
        assert result == "file1.txt\nfile2.txt"

    def test_no_output(self):
        before = "$ \n\n"
        after = "$ cd /tmp\n$ \n"
        result = self._extract(before, after, "cd /tmp")
        assert result == ""

    def test_trailing_whitespace_ignored(self):
        before = "$ \n\n"
        after = "$ echo hi\nhi\n$ \n"
        result = self._extract(before, after, "echo hi")
        assert result == "hi"

    def test_scroll_tolerant_uses_after_screen(self):
        # After scrolling, absolute line indices no longer align between
        # before/after, but the command echo and its output remain visible
        # together on the after screen. Output below an unrelated command must
        # not bleed into this command's output.
        before = "old1\nold2\n$ echo target\ntarget\n$ "
        after = "old2\ntarget\n$ echo target\ntarget-real\n$ "
        result = self._extract(before, after, "echo target")
        assert result == "target-real"

    def test_command_substring_not_matched_as_word(self):
        # A line ending in "update" must not be mistaken for command "date".
        before = "$ \n\n"
        after = "$ ran update\nirrelevant\n$ date\nMon Jan 1\n$ "
        result = self._extract(before, after, "date")
        assert result == "Mon Jan 1"

    def test_noisy_prompt(self):
        # Realistic multi-segment prompt (oh-my-zsh style).
        before = "➜  proj git:(main) \n\n"
        after = "➜  proj git:(main) echo hi\nhi\n➜  proj git:(main) "
        result = self._extract(before, after, "echo hi")
        assert result == "hi"


class TestShellProbes:
    """Guards for the hidden shell-state probe and one-time setup."""

    def test_exit_code_probe_uses_braced_vars(self):
        # Without braces, "$__rc___" / "$PWD___" parse as the (undefined)
        # variables "__rc___" / "PWD___" since underscores are valid in
        # identifiers, yielding empty markers and a permanent exit_code of -1.
        assert "${__rc}___" in (
            '__rc=$?; echo "%s${__rc}___"' % Engine._EXIT_CODE_MARKER
        )

    def test_shell_setup_disables_history_expansion(self):
        # Commands containing '!' (e.g. echo "Done!") would otherwise trigger
        # interactive history expansion and wedge the shell.
        assert "banghist" in Engine._SHELL_SETUP  # zsh
        assert "set +H" in Engine._SHELL_SETUP  # bash

    def test_zsh_setup_emits_osc133_marks(self):
        # Pass shell explicitly so the assertion doesn't depend on the host's
        # $SHELL (CI runners default to bash).
        setup = Engine(shell="/bin/zsh")._shell_setup_commands()
        # Hooks emit the C (output start) and D (exit code) marks, and the
        # D hook is prepended to precmd so it fires before the prompt theme's.
        assert "133;C" in setup and "133;D" in setup
        assert "precmd_functions=(__rt_pc $precmd_functions)" in setup

    def test_bash_setup_emits_osc133_marks(self):
        setup = Engine(shell="/bin/bash")._shell_setup_commands()
        assert "133;C" in setup and "133;D" in setup
        assert "PS0=" in setup  # output-start mark via PS0 (bash >= 4.4)


class TestMarkedOutput:
    """Tests for OSC 133 mark parsing — the primary capture path."""

    C = "\x1b]133;C\x07"  # output start
    CWD = "\x1b]1337;Cwd=/tmp/work\x07"

    def D(self, code: int) -> str:
        return f"\x1b]133;D;{code}\x07"

    def test_multiline_output_with_cwd(self):
        raw = f"{self.C}line1\r\nline2\r\n{self.D(0)}{self.CWD}"
        assert Engine._extract_marked_output(raw) == ("line1\nline2", 0, "/tmp/work")

    def test_no_trailing_newline(self):
        # The hard case the snapshot/prompt-guess approach can't do: output with
        # no trailing newline is sliced exactly between the C and D marks.
        raw = f"{self.C}noeol{self.D(0)}"
        assert Engine._extract_marked_output(raw) == ("noeol", 0, None)

    def test_empty_output_nonzero_exit(self):
        raw = f"prompt $ false\r\n{self.C}{self.D(1)}"
        assert Engine._extract_marked_output(raw) == ("", 1, None)

    def test_strips_embedded_ansi(self):
        raw = f"{self.C}\x1b[32mgreen\x1b[0m\r\n{self.D(0)}"
        assert Engine._extract_marked_output(raw) == ("green", 0, None)

    def test_strips_zsh_promptsp_marker(self):
        # zsh prints a trailing '%' partial-line marker after no-newline output.
        raw = f"{self.C}noeol%      \r{self.D(0)}"
        assert Engine._extract_marked_output(raw) == ("noeol", 0, None)

    def test_no_marks_returns_none(self):
        # A shell without integration → caller falls back to snapshot extraction.
        assert Engine._extract_marked_output("plain output, no marks") is None
