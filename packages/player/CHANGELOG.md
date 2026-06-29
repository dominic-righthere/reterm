# Changelog

All notable changes to `reterm-player` are documented here.

## 0.1.2

### Fixed

- **Player no longer resizes and reflows the page.** The terminal grew vertically
  as output appeared (fit mode wrapped long lines and the box used `min-height`),
  then shrank on loop — moving surrounding page content around. The terminal now
  has a fixed height (the recording's rows); lines never wrap and overflow scrolls
  inside the box like a real terminal.
- **Playback no longer pins at `0:00`.** While the timeline duration was still
  resolving on load (`totalDuration === 0`), the animation loop treated
  `currentTime >= totalDuration` as "complete" every frame and reset to zero, so
  the progress bar was stuck at the start. The loop now waits for a resolved
  duration before advancing.

## 0.1.1

### Fixed

- Command text briefly flashed to only its first word (e.g. `echo` for
  `echo "hi"`) just before output appeared, due to pre-output echo frames being
  rendered as intermediate snapshots.

## 0.1.0

- Initial release: `TerminalPlayer` React component for replaying reterm JSON
  recordings, with play/pause/seek/speed controls, theming, typing animation, and
  an optional macOS-style window frame.
