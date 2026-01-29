"""Redaction engine for hiding sensitive information in recordings."""

import re
from dataclasses import dataclass

from reterm.output.models import RecordingLog, TerminalSnapshot


@dataclass
class RedactionRule:
    """A single redaction rule."""

    pattern: str
    replacement: str
    is_regex: bool = False
    seamless: bool = False  # If False, wrap replacement in brackets


class Redactor:
    """Applies redaction rules to recording logs."""

    def __init__(self, rules: list[RedactionRule]) -> None:
        self.rules = rules

    def redact_text(self, text: str) -> str:
        """Apply all redaction rules to a text string."""
        for rule in self.rules:
            if rule.is_regex:
                if rule.seamless:
                    text = re.sub(rule.pattern, rule.replacement, text)
                else:
                    text = re.sub(rule.pattern, f"[{rule.replacement}]", text)
            else:
                if rule.seamless:
                    text = text.replace(rule.pattern, rule.replacement)
                else:
                    text = text.replace(rule.pattern, f"[{rule.replacement}]")
        return text

    def redact_log(self, log: RecordingLog) -> RecordingLog:
        """Apply redactions to all text fields in a recording log."""
        # Redact commands
        for cmd in log.commands:
            cmd.command = self.redact_text(cmd.command)
            cmd.stdout = self.redact_text(cmd.stdout)
            cmd.stderr = self.redact_text(cmd.stderr)
            cmd.combined_output = self.redact_text(cmd.combined_output)
            cmd.working_directory = self.redact_text(cmd.working_directory)

            # Redact terminal snapshots
            if cmd.terminal_before:
                self._redact_snapshot(cmd.terminal_before)
            if cmd.terminal_after:
                self._redact_snapshot(cmd.terminal_after)

        # Redact final terminal state
        if log.final_terminal_state:
            self._redact_snapshot(log.final_terminal_state)

        # Redact captured variables
        log.captured_variables = {
            k: self.redact_text(v) for k, v in log.captured_variables.items()
        }

        # Redact failed commands list
        log.failed_commands = [self.redact_text(cmd) for cmd in log.failed_commands]

        # Recompute derived fields
        log.compute_derived_fields()

        return log

    def _redact_snapshot(self, snapshot: TerminalSnapshot) -> None:
        """Apply redactions to a terminal snapshot."""
        snapshot.screen_content = [
            self.redact_text(line) for line in snapshot.screen_content
        ]
        snapshot.screen_content_plain = self.redact_text(snapshot.screen_content_plain)


def create_redactor(
    patterns: list[str],
    replacements: list[str],
    is_regex: bool = False,
    seamless: bool = False,
) -> Redactor:
    """Create a Redactor from lists of patterns and replacements.

    Args:
        patterns: List of patterns to match
        replacements: List of replacement strings (must match length of patterns)
        is_regex: If True, treat patterns as regular expressions
        seamless: If True, don't wrap replacements in brackets

    Returns:
        Configured Redactor instance
    """
    if len(patterns) != len(replacements):
        raise ValueError(
            f"Number of patterns ({len(patterns)}) must match "
            f"number of replacements ({len(replacements)})"
        )

    rules = [
        RedactionRule(
            pattern=pattern,
            replacement=replacement,
            is_regex=is_regex,
            seamless=seamless,
        )
        for pattern, replacement in zip(patterns, replacements)
    ]

    return Redactor(rules)
