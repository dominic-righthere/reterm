import type { Theme } from '../themes';
import { ProgressBar } from './ProgressBar';

export interface ControlsProps {
  isPlaying: boolean;
  progress: number;
  currentTime: number;
  totalDuration: number;
  speed: number;
  theme: Theme;
  onToggle: () => void;
  onSeek: (progress: number) => void;
  onSpeedChange: (speed: number) => void;
}

/**
 * Playback controls with play/pause, seek, and speed control.
 */
export function Controls({
  isPlaying,
  progress,
  currentTime,
  totalDuration,
  speed,
  theme,
  onToggle,
  onSeek,
  onSpeedChange,
}: ControlsProps) {
  const formatTime = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div
      className="reterm-controls"
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '8px 12px',
        backgroundColor: `${theme.background}ee`,
        borderRadius: '0 0 8px 8px',
        gap: '8px',
      }}
    >
      {/* Play/Pause Button */}
      <button
        onClick={onToggle}
        className="reterm-play-button"
        style={{
          width: '32px',
          height: '32px',
          border: 'none',
          borderRadius: '50%',
          backgroundColor: theme.foreground,
          color: theme.background,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '12px',
          fontWeight: 'bold',
        }}
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? (
          <PauseIcon color={theme.background} />
        ) : (
          <PlayIcon color={theme.background} />
        )}
      </button>

      {/* Time Display */}
      <span
        className="reterm-time"
        style={{
          color: theme.foreground,
          fontSize: '12px',
          fontFamily: 'ui-monospace, monospace',
          minWidth: '80px',
        }}
      >
        {formatTime(currentTime)} / {formatTime(totalDuration)}
      </span>

      {/* Progress Bar */}
      <ProgressBar value={progress} onChange={onSeek} theme={theme} />

      {/* Speed Control */}
      <select
        value={speed}
        onChange={(e) => onSpeedChange(Number(e.target.value))}
        className="reterm-speed"
        style={{
          backgroundColor: 'transparent',
          color: theme.foreground,
          border: `1px solid ${theme.foreground}44`,
          borderRadius: '4px',
          padding: '4px 8px',
          fontSize: '12px',
          cursor: 'pointer',
        }}
        aria-label="Playback speed"
      >
        <option value={0.25}>0.25x</option>
        <option value={0.5}>0.5x</option>
        <option value={1}>1x</option>
        <option value={1.5}>1.5x</option>
        <option value={2}>2x</option>
        <option value={3}>3x</option>
      </select>
    </div>
  );
}

function PlayIcon({ color }: { color: string }) {
  return (
    <svg width="12" height="14" viewBox="0 0 12 14" fill={color}>
      <path d="M0 0L12 7L0 14V0Z" />
    </svg>
  );
}

function PauseIcon({ color }: { color: string }) {
  return (
    <svg width="10" height="12" viewBox="0 0 10 12" fill={color}>
      <rect x="0" y="0" width="3" height="12" />
      <rect x="7" y="0" width="3" height="12" />
    </svg>
  );
}
