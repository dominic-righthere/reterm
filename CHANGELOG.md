# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `reterm play` command to replay a recording in the terminal, with `--speed`
  and `--idle-limit` controls
- MCP tools `format_as_markdown` (render a log as shareable markdown) and
  `screenshot_terminal` (return a PNG of the terminal state)

### Changed

- **Per-command capture now uses OSC 133 shell-integration marks.** reterm
  injects invisible `preexec`/`precmd` hooks into the recording shell (zsh, and
  bash ≥ 4.4) that delimit each command's output and report its exit code — the
  same mechanism iTerm2/WezTerm/kitty/VS Code use. Output is sliced exactly from
  the raw byte stream between marks, so it captures **full output of any length**
  (even when it scrolls past the screen) and output with **no trailing newline**,
  and reads the **exact exit code** from the `D;<code>` mark. The marks are
  invisible, so the GIF is unaffected. Shells without integration fall back to
  the previous screen-based capture.

### Fixed

- **Accurate exit codes.** The shell-state probe expanded `$__rc___` / `$PWD___`
  as the (undefined) variables `__rc___` / `PWD___`, so every command recorded
  `exit_code: -1` and `success` was always wrong. Now uses `${__rc}` / `${PWD}`.
- **Commands containing `!` no longer break recordings.** Interactive history
  expansion (e.g. `echo "Done!"`) wedged the shell and corrupted every
  following command. History expansion is now disabled in the recording shell.
- **Accurate output past one screen.** Output extraction diffed terminal
  snapshots by absolute line index, which misattributed output once a recording
  scrolled. It now locates the command on the post-command screen, making
  capture scroll-tolerant.

## [0.1.0] - 2025-12-01

### Added

- YAML-based `.reterm` scripts for declarative terminal recording
- Dual output: GIF for humans + structured JSON log for AI tools
- CLI commands: `run`, `new`, `validate`, `redact`, `render`, `serve`, `themes`, `schema`
- Redaction support: visible, seamless, and regex-based
- MCP server for AI tool integration (stdio and SSE transports)
- React player component (`reterm-player` npm package)
- Playback controls: play/pause, seek, speed adjustment, looping
- macOS-style window frame with customizable title
- `fit` prop to scale terminal to container width
- Typing animation with configurable speed
- 6 built-in themes: Dracula, Nord, Monokai, Solarized Dark, GitHub Dark, One Dark
- Interactive `wait_for` step for prompt-driven flows
- Screenshot capture step
