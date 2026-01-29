import type { Theme } from '../themes';

export interface ProgressBarProps {
  value: number; // 0-1
  onChange: (value: number) => void;
  theme: Theme;
}

/**
 * Seekable progress bar for playback.
 */
export function ProgressBar({ value, onChange, theme }: ProgressBarProps) {
  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const progress = x / rect.width;
    onChange(Math.max(0, Math.min(1, progress)));
  };

  const handleDrag = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.buttons !== 1) return; // Only left mouse button
    handleClick(e);
  };

  return (
    <div
      className="reterm-progress"
      onClick={handleClick}
      onMouseMove={handleDrag}
      style={{
        flex: 1,
        height: '6px',
        backgroundColor: `${theme.foreground}33`,
        borderRadius: '3px',
        cursor: 'pointer',
        position: 'relative',
        margin: '0 8px',
      }}
    >
      <div
        className="reterm-progress-fill"
        style={{
          width: `${value * 100}%`,
          height: '100%',
          backgroundColor: theme.foreground,
          borderRadius: '3px',
          transition: 'width 0.05s linear',
        }}
      />
      <div
        className="reterm-progress-handle"
        style={{
          position: 'absolute',
          left: `${value * 100}%`,
          top: '50%',
          transform: 'translate(-50%, -50%)',
          width: '12px',
          height: '12px',
          backgroundColor: theme.foreground,
          borderRadius: '50%',
          boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
        }}
      />
    </div>
  );
}
