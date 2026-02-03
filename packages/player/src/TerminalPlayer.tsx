import { useEffect, useRef, useState, useCallback } from 'react';
import { useRecording } from './hooks/useRecording';
import { usePlayback } from './hooks/usePlayback';
import { Terminal, type CursorStyle } from './components/Terminal';
import { WindowFrame } from './components/WindowFrame';
import { Controls } from './components/Controls';
import { getTheme, type Theme } from './themes';
import type { RecordingLog } from './types/recording';

/**
 * Hook to measure container width and calculate scale factor for fit mode.
 */
function useFitScale(
  enabled: boolean,
  nativeWidth: number,
  fontSize: number,
  fontFamily: string
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [charWidth, setCharWidth] = useState(fontSize * 0.6);

  // Measure character width
  useEffect(() => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.font = `${fontSize}px ${fontFamily.split(',')[0].replace(/"/g, '')}`;
      const measured = ctx.measureText('M').width;
      setCharWidth(measured);
    }
  }, [fontSize, fontFamily]);

  const updateScale = useCallback(() => {
    if (!enabled || !containerRef.current) {
      setScale(1);
      return;
    }

    const containerWidth = containerRef.current.offsetWidth;
    // Terminal width = cols * charWidth + padding (32px)
    const terminalWidth = nativeWidth * charWidth + 32;

    if (containerWidth < terminalWidth) {
      setScale(containerWidth / terminalWidth);
    } else {
      setScale(1);
    }
  }, [enabled, nativeWidth, charWidth]);

  useEffect(() => {
    updateScale();

    if (!enabled) return;

    const resizeObserver = new ResizeObserver(updateScale);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, [enabled, updateScale]);

  return { containerRef, scale, charWidth };
}

export interface TerminalPlayerProps {
  /** Inline recording data */
  data?: RecordingLog;
  /** URL to fetch recording from */
  src?: string;
  /** Start playing automatically */
  autoPlay?: boolean;
  /** Loop playback */
  loop?: boolean;
  /** Playback speed multiplier */
  speed?: number;
  /** Override theme from recording */
  theme?: string;
  /** Show playback controls */
  showControls?: boolean;
  /** Font size in pixels */
  fontSize?: number;
  /** Font family */
  fontFamily?: string;
  /** Show blinking cursor */
  showCursor?: boolean;
  /** Cursor style: 'block' | 'underline' | 'bar' */
  cursorStyle?: CursorStyle;
  /** Typing animation speed in ms per character (default 50) */
  typingSpeed?: number;
  /** Show macOS-style window frame (default: true) */
  showWindowFrame?: boolean;
  /** Window title (defaults to script name from recording or 'Terminal') */
  title?: string;
  /**
   * Scale terminal to fit container width.
   * When true, the terminal scales down (never up) to fit available width.
   * Preserves exact character layout and aspect ratio.
   */
  fit?: boolean;
  /** Callback when playback completes */
  onComplete?: () => void;
  /** Callback when recording loads */
  onLoad?: (recording: RecordingLog) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
  /** Additional CSS class */
  className?: string;
  /** Inline styles */
  style?: React.CSSProperties;
}

/**
 * React component for replaying terminal recordings from reterm JSON logs.
 *
 * @example
 * ```tsx
 * // From inline data
 * <TerminalPlayer data={recordingJson} />
 *
 * // From URL
 * <TerminalPlayer src="/recordings/demo.json" autoPlay />
 *
 * // Full options
 * <TerminalPlayer
 *   data={json}
 *   autoPlay={true}
 *   speed={1.5}
 *   theme="dracula"
 *   showControls={true}
 *   showWindowFrame={true}
 *   title="my-project"
 *   cursorStyle="block"
 *   onComplete={() => console.log('done')}
 * />
 * ```
 */
const DEFAULT_FONT_FAMILY = '"SF Mono", "Fira Code", "JetBrains Mono", Menlo, Monaco, "Cascadia Code", Consolas, monospace';

export function TerminalPlayer({
  data,
  src,
  autoPlay = false,
  loop = false,
  speed = 1.0,
  theme: themeName,
  showControls = true,
  fontSize = 14,
  fontFamily = DEFAULT_FONT_FAMILY,
  showCursor = true,
  cursorStyle = 'block',
  typingSpeed = 50,
  showWindowFrame = true,
  title,
  fit = false,
  onComplete,
  onLoad,
  onError,
  className,
  style,
}: TerminalPlayerProps) {
  const { recording, loading, error } = useRecording({ data, src });

  const playback = usePlayback(recording, {
    speed,
    loop,
    autoPlay,
    onComplete,
    typingSpeed,
  });

  // Resolve theme
  const resolvedTheme: Theme = getTheme(
    themeName || recording?.metadata.theme || 'dracula'
  );

  // Resolve title from prop or recording metadata
  const resolvedTitle = title || recording?.metadata.script_file || 'Terminal';

  // Get terminal dimensions
  const dimensions: [number, number] = recording?.metadata.terminal_size || [80, 24];
  const [cols, rows] = dimensions;

  // Fit mode scaling
  const { containerRef, scale, charWidth } = useFitScale(fit, cols, fontSize, fontFamily);
  const lineHeight = Math.round(fontSize * 1.4);
  const nativeWidth = cols * charWidth + 32;
  const nativeHeight = rows * lineHeight + 24 + (showControls ? 40 : 0) + (showWindowFrame ? 36 : 0);

  // Handle callbacks in effects to avoid side effects during render
  const onLoadRef = useRef(onLoad);
  onLoadRef.current = onLoad;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  useEffect(() => {
    if (error && onErrorRef.current) {
      onErrorRef.current(error);
    }
  }, [error]);

  useEffect(() => {
    if (recording && onLoadRef.current) {
      onLoadRef.current(recording);
    }
  }, [recording]);

  if (loading) {
    const loadingContent = (
      <div
        style={{
          backgroundColor: resolvedTheme.background,
          padding: '24px',
          color: resolvedTheme.foreground,
          fontFamily: 'ui-monospace, monospace',
        }}
      >
        <LoadingSpinner theme={resolvedTheme} />
      </div>
    );

    if (showWindowFrame) {
      return (
        <div className={`reterm-player reterm-loading ${className || ''}`} style={style}>
          <WindowFrame title={resolvedTitle} theme={resolvedTheme}>
            {loadingContent}
          </WindowFrame>
        </div>
      );
    }

    return (
      <div
        className={`reterm-player reterm-loading ${className || ''}`}
        style={{
          borderRadius: '8px',
          overflow: 'hidden',
          ...style,
        }}
      >
        {loadingContent}
      </div>
    );
  }

  if (error) {
    const errorContent = (
      <div
        style={{
          backgroundColor: resolvedTheme.background,
          padding: '24px',
          color: resolvedTheme.red,
          fontFamily: 'ui-monospace, monospace',
        }}
      >
        Error: {error.message}
      </div>
    );

    if (showWindowFrame) {
      return (
        <div className={`reterm-player reterm-error ${className || ''}`} style={style}>
          <WindowFrame title={resolvedTitle} theme={resolvedTheme}>
            {errorContent}
          </WindowFrame>
        </div>
      );
    }

    return (
      <div
        className={`reterm-player reterm-error ${className || ''}`}
        style={{
          borderRadius: '8px',
          overflow: 'hidden',
          ...style,
        }}
      >
        {errorContent}
      </div>
    );
  }

  const terminalContent = (
    <>
      <Terminal
        snapshot={playback.currentSnapshot}
        theme={resolvedTheme}
        dimensions={dimensions}
        fontSize={fontSize}
        fontFamily={fontFamily}
        showCursor={showCursor}
        cursorStyle={cursorStyle}
        typingText={playback.typingText}
        isTyping={playback.isTyping}
      />
      {showControls && (
        <Controls
          isPlaying={playback.isPlaying}
          progress={playback.progress}
          currentTime={playback.currentTime}
          totalDuration={playback.totalDuration}
          speed={playback.speed}
          theme={resolvedTheme}
          onToggle={playback.toggle}
          onSeek={playback.seek}
          onSpeedChange={playback.setSpeed}
        />
      )}
    </>
  );

  // Wrap content with scaling container for fit mode
  const scaledContent = fit ? (
    <div
      style={{
        width: `${nativeWidth}px`,
        transform: `scale(${scale})`,
        transformOrigin: 'top left',
      }}
    >
      {showWindowFrame ? (
        <WindowFrame title={resolvedTitle} theme={resolvedTheme}>
          {terminalContent}
        </WindowFrame>
      ) : (
        <div
          style={{
            borderRadius: '8px',
            overflow: 'hidden',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          }}
        >
          {terminalContent}
        </div>
      )}
    </div>
  ) : null;

  // Fit mode container - scales content to fit width
  if (fit) {
    return (
      <div
        ref={containerRef}
        className={`reterm-player ${className || ''}`}
        style={{
          display: 'block',
          width: '100%',
          height: `${nativeHeight * scale}px`,
          overflow: 'hidden',
          ...style,
        }}
      >
        {scaledContent}
      </div>
    );
  }

  if (showWindowFrame) {
    return (
      <div
        className={`reterm-player ${className || ''}`}
        style={{
          display: 'block',
          maxWidth: '100%',
          ...style,
        }}
      >
        <WindowFrame title={resolvedTitle} theme={resolvedTheme}>
          {terminalContent}
        </WindowFrame>
      </div>
    );
  }

  return (
    <div
      className={`reterm-player ${className || ''}`}
      style={{
        display: 'block',
        maxWidth: '100%',
        borderRadius: '8px',
        overflow: 'hidden',
        boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        ...style,
      }}
    >
      {terminalContent}
    </div>
  );
}

function LoadingSpinner({ theme }: { theme: Theme }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
      }}
    >
      <div
        style={{
          width: '20px',
          height: '20px',
          border: `2px solid ${theme.foreground}33`,
          borderTopColor: theme.foreground,
          borderRadius: '50%',
          animation: 'reterm-spin 1s linear infinite',
        }}
      />
      Loading recording...
    </div>
  );
}
