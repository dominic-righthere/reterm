// Main component
export { TerminalPlayer } from './TerminalPlayer';
export type { TerminalPlayerProps } from './TerminalPlayer';

// Sub-components (for advanced usage)
export { Terminal } from './components/Terminal';
export type { TerminalProps } from './components/Terminal';

export { Controls } from './components/Controls';
export type { ControlsProps } from './components/Controls';

export { ProgressBar } from './components/ProgressBar';
export type { ProgressBarProps } from './components/ProgressBar';

// Hooks (for custom implementations)
export { useRecording } from './hooks/useRecording';
export type { UseRecordingOptions, UseRecordingResult } from './hooks/useRecording';

export { usePlayback } from './hooks/usePlayback';
export type { UsePlaybackResult, PlaybackOptions } from './hooks/usePlayback';

// Timeline utilities (usable outside React)
export { buildTimeline } from './utils/timeline';
export type { TimelineEntry } from './utils/timeline';

// Themes
export { themes, getTheme, listThemes, getAnsiColor, resolve256Color } from './themes';
export type { Theme } from './themes';

// Types
export type {
  RecordingLog,
  RecordingMetadata,
  CommandExecution,
  TerminalSnapshot,
  StepExecution,
} from './types/recording';

// CSS import helper
import './styles/terminal.css';
