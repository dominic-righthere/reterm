import { useState, useEffect } from 'react';
import type { TerminalSnapshot } from '../types/recording';
import type { Theme } from '../themes';

export type CursorStyle = 'block' | 'underline' | 'bar';

export interface TerminalProps {
  snapshot: TerminalSnapshot | null;
  theme: Theme;
  dimensions: [number, number]; // [cols, rows]
  fontSize?: number;
  fontFamily?: string;
  showCursor?: boolean;
  cursorStyle?: CursorStyle;
  typingText?: string; // Text being typed at cursor position (for animation)
  isTyping?: boolean; // Whether currently in typing animation mode
}

// Pattern detection for common prompts
const PROMPT_PATTERNS = [
  // oh-my-zsh style: ➜  dirname command
  { regex: /^(➜\s+)(\S+)(\s+)(.*)$/, styles: ['cyan', 'green', null, 'foreground'] },
  // oh-my-zsh style: ➜  dirname (no command)
  { regex: /^(➜\s+)(\S+)(\s*)$/, styles: ['cyan', 'green', null] },
  // bash style: user@host:dir$
  { regex: /^(\S+@\S+):([^$]+)(\$\s*)(.*)$/, styles: ['green', 'blue', 'foreground', 'foreground'] },
  // simple: $ command
  { regex: /^(\$\s+)(.*)$/, styles: ['green', 'foreground'] },
];

/**
 * Renders a terminal snapshot with proper styling.
 */
export function Terminal({
  snapshot,
  theme,
  dimensions,
  fontSize = 14,
  fontFamily = '"SF Mono", "Fira Code", "JetBrains Mono", Menlo, Monaco, "Cascadia Code", Consolas, monospace',
  showCursor = true,
  cursorStyle = 'block',
  typingText,
  isTyping = false,
}: TerminalProps) {
  const [cols, rows] = dimensions;
  const lineHeight = Math.round(fontSize * 1.4);

  // Measure actual character width
  const [charWidth, setCharWidth] = useState(fontSize * 0.6);

  useEffect(() => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.font = `${fontSize}px ${fontFamily.split(',')[0].replace(/"/g, '')}`;
      const measured = ctx.measureText('M').width;
      setCharWidth(measured);
    }
  }, [fontSize, fontFamily]);

  const terminalStyle: React.CSSProperties = {
    backgroundColor: theme.background,
    color: theme.foreground,
    fontFamily,
    fontSize: `${fontSize}px`,
    lineHeight: `${lineHeight}px`,
    width: `${cols * charWidth + 32}px`,
    maxWidth: '100%',
    minHeight: `${rows * lineHeight + 24}px`,
    padding: '12px 16px',
    overflowX: 'auto',
    overflowY: 'hidden',
    // Better font rendering
    fontVariantLigatures: 'none',
    fontFeatureSettings: '"liga" 0, "calt" 0',
    WebkitFontSmoothing: 'antialiased',
    MozOsxFontSmoothing: 'grayscale',
    letterSpacing: '0',
    tabSize: 4,
  };

  if (!snapshot) {
    // Render empty terminal
    return (
      <div className="reterm-terminal" style={terminalStyle} />
    );
  }

  const [cursorRow, cursorCol] = snapshot.cursor_position;

  return (
    <div className="reterm-terminal" style={terminalStyle}>
      {snapshot.screen_content.map((line, rowIndex) => (
        <div
          key={rowIndex}
          className="reterm-line"
          style={{ whiteSpace: 'pre', height: `${lineHeight}px` }}
        >
          {renderLine(
            line,
            rowIndex,
            cursorRow,
            cursorCol,
            theme,
            showCursor,
            cursorStyle,
            charWidth,
            lineHeight,
            isTyping && rowIndex === cursorRow ? typingText : undefined
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Renders a line with prompt styling, cursor, and typing animation.
 */
function renderLine(
  line: string,
  rowIndex: number,
  cursorRow: number,
  cursorCol: number,
  theme: Theme,
  showCursor: boolean,
  cursorStyle: CursorStyle,
  charWidth: number,
  lineHeight: number,
  typingText?: string
): React.ReactNode {
  // If we have typing text, show the line with typing animation
  if (typingText !== undefined && rowIndex === cursorRow) {
    const lineUpToCursor = line.slice(0, cursorCol);
    const needsSpace = lineUpToCursor.length > 0 &&
                       !lineUpToCursor.endsWith(' ') &&
                       typingText.length > 0;

    // Style the prompt part
    const styledPrompt = styleLine(lineUpToCursor, theme);

    return (
      <>
        {styledPrompt}
        {needsSpace && ' '}
        <span style={{ color: theme.foreground }}>{typingText}</span>
        {showCursor && renderCursor(' ', cursorStyle, theme, charWidth, lineHeight)}
      </>
    );
  }

  // Pad line to cursor position if needed
  const paddedLine = line.padEnd(Math.max(line.length, cursorCol + 1));

  // Non-cursor line - just style it
  if (!showCursor || rowIndex !== cursorRow) {
    const styled = styleLine(paddedLine || '\u00A0', theme);
    return styled;
  }

  // Split line at cursor position for cursor row
  const beforeCursor = paddedLine.slice(0, cursorCol);
  const cursorChar = paddedLine[cursorCol] || ' ';
  const afterCursor = paddedLine.slice(cursorCol + 1);

  // Style the parts
  const styledBefore = styleLine(beforeCursor, theme);

  return (
    <>
      {styledBefore}
      {renderCursor(cursorChar, cursorStyle, theme, charWidth, lineHeight)}
      {afterCursor}
    </>
  );
}

/**
 * Apply prompt styling to a line based on pattern detection.
 */
function styleLine(line: string, theme: Theme): React.ReactNode {
  if (!line || line === '\u00A0') return line;

  for (const pattern of PROMPT_PATTERNS) {
    const match = line.match(pattern.regex);
    if (match) {
      return (
        <>
          {match.slice(1).map((segment, i) => {
            if (!segment) return null;
            const colorKey = pattern.styles[i];
            const color = colorKey ? (theme as unknown as Record<string, string>)[colorKey] || theme.foreground : undefined;
            return (
              <span key={i} style={color ? { color } : undefined}>
                {segment}
              </span>
            );
          })}
        </>
      );
    }
  }
  return line;
}

/**
 * Render cursor with different styles.
 */
function renderCursor(
  char: string,
  style: CursorStyle,
  theme: Theme,
  charWidth: number,
  lineHeight: number
): React.ReactNode {
  const baseStyle: React.CSSProperties = {
    display: 'inline-block',
    animation: 'reterm-blink 1s step-end infinite',
  };

  switch (style) {
    case 'block':
      return (
        <span
          className="reterm-cursor"
          style={{
            ...baseStyle,
            backgroundColor: theme.cursor,
            color: theme.background,
            width: `${charWidth}px`,
          }}
        >
          {char}
        </span>
      );
    case 'underline':
      return (
        <span
          className="reterm-cursor"
          style={{
            ...baseStyle,
            borderBottom: `2px solid ${theme.cursor}`,
            width: `${charWidth}px`,
          }}
        >
          {char}
        </span>
      );
    case 'bar':
      return (
        <span className="reterm-cursor" style={{ position: 'relative', display: 'inline-block' }}>
          <span
            style={{
              ...baseStyle,
              position: 'absolute',
              left: 0,
              top: '2px',
              width: '2px',
              height: `${lineHeight - 4}px`,
              backgroundColor: theme.cursor,
            }}
          />
          {char}
        </span>
      );
  }
}
