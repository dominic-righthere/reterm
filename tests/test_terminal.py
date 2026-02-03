"""Tests for the terminal module."""

import pytest

from reterm.core.terminal import Terminal, TerminalConfig, Screen


class TestBoxDrawingCharacters:
    """Tests for DEC line drawing character set support."""

    def test_box_corners(self):
        t = Terminal(TerminalConfig(rows=3, cols=10))
        # ESC(0 = switch to line drawing, l=┌ q=─ k=┐, ESC(B = back to ASCII
        t.feed("\x1b(0lqk\x1b(B")
        assert t.get_line(0) == "┌─┐"

    def test_vertical_lines(self):
        t = Terminal(TerminalConfig(rows=3, cols=10))
        t.feed("\x1b(0x\x1b(B")  # x = │
        assert "│" in t.get_line(0)

    def test_bottom_corners(self):
        t = Terminal(TerminalConfig(rows=3, cols=10))
        # m=└ j=┘
        t.feed("\x1b(0mqj\x1b(B")
        assert t.get_line(0) == "└─┘"

    def test_mixed_box_and_text(self):
        t = Terminal(TerminalConfig(rows=3, cols=20))
        t.feed("\x1b(0l\x1b(B Hello \x1b(0k\x1b(B")
        assert t.get_line(0) == "┌ Hello ┐"


class TestAlternateScreenBuffer:
    """Tests for alternate screen buffer support (tmux, vim, etc.)."""

    def test_mode_1049_enter_exit(self):
        """Test most common alternate screen mode (with cursor save)."""
        t = Terminal(TerminalConfig(rows=5, cols=20))
        t.feed("Main content")

        assert not t.screen.on_alt_screen
        assert "Main content" in t.get_line(0)

        # Enter alternate screen
        t.feed("\x1b[?1049h")
        assert t.screen.on_alt_screen
        assert t.get_line(0) == ""  # Alt screen is blank

        # Write to alternate screen
        t.feed("Alt content")
        assert "Alt content" in t.get_line(0)

        # Exit - main content should be restored
        t.feed("\x1b[?1049l")
        assert not t.screen.on_alt_screen
        assert "Main content" in t.get_line(0)
        assert "Alt content" not in t.get_line(0)

    def test_mode_47_old_xterm(self):
        """Test old xterm alternate screen mode."""
        t = Terminal(TerminalConfig(rows=3, cols=15))
        t.feed("MAIN")
        t.feed("\x1b[?47h")
        assert t.screen.on_alt_screen
        t.feed("ALT")
        t.feed("\x1b[?47l")
        assert "MAIN" in t.get_line(0)

    def test_mode_1047_xterm(self):
        """Test xterm alternate screen mode."""
        t = Terminal(TerminalConfig(rows=3, cols=15))
        t.feed("MAIN")
        t.feed("\x1b[?1047h")
        assert t.screen.on_alt_screen
        t.feed("ALT")
        t.feed("\x1b[?1047l")
        assert "MAIN" in t.get_line(0)

    def test_cursor_preserved_on_1049(self):
        """Test that cursor position is saved/restored with mode 1049."""
        t = Terminal(TerminalConfig(rows=5, cols=20))
        t.feed("Line1\nLine2\nLine3")
        # Cursor should be at row 2 after the feeds
        original_pos = t.get_cursor_position()

        t.feed("\x1b[?1049h")  # Enter alt screen
        t.feed("\x1b[1;1H")  # Move cursor to top-left on alt screen

        t.feed("\x1b[?1049l")  # Exit alt screen
        restored_pos = t.get_cursor_position()

        # Cursor should be restored to original position
        assert restored_pos == original_pos

    def test_nested_alt_screen_ignored(self):
        """Test that entering alt screen twice doesn't nest."""
        t = Terminal(TerminalConfig(rows=3, cols=20))
        t.feed("MAIN")
        t.feed("\x1b[?1049h")  # Enter
        t.feed("ALT1")
        t.feed("\x1b[?1049h")  # Enter again (should be no-op)
        t.feed("ALT2")
        assert "ALT2" in t.get_line(0)  # Should still be on alt screen

        t.feed("\x1b[?1049l")  # Exit once
        assert "MAIN" in t.get_line(0)  # Should restore main

    def test_exit_without_enter_no_crash(self):
        """Test that exiting alt screen without entering doesn't crash."""
        t = Terminal(TerminalConfig(rows=3, cols=20))
        t.feed("Content")
        t.feed("\x1b[?1049l")  # Exit without entering
        assert "Content" in t.get_line(0)  # Nothing should change


class TestScreenClass:
    """Tests for the extended Screen class."""

    def test_on_alt_screen_property(self):
        screen = Screen(80, 24)
        assert not screen.on_alt_screen

        screen.set_mode(1049, private=True)
        assert screen.on_alt_screen

        screen.reset_mode(1049, private=True)
        assert not screen.on_alt_screen
