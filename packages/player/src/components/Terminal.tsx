import { useState, useEffect } from 'react';
import type { TerminalSnapshot, StyledChar } from '../types/recording';
import type { Theme } from '../themes';
import { getAnsiColor } from '../themes';

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
  /** When true, terminal fills container width with horizontal scroll */
  fillWidth?: boolean;
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
  fillWidth = false,
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
    width: fillWidth ? '100%' : `${cols * charWidth + 32}px`,
    minHeight: `${rows * lineHeight + 24}px`,
    padding: '12px 16px',
    overflowX: fillWidth ? 'hidden' : 'auto',  // No scroll in fit mode
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

  const styledContent = snapshot.styled_content;

  // Line styles change based on fit mode
  const lineStyle: React.CSSProperties = fillWidth
    ? {
        whiteSpace: 'pre-wrap',      // Allow wrapping in fit mode
        wordBreak: 'break-all',      // Break long strings
        minHeight: `${lineHeight}px`, // Minimum height, can grow
      }
    : {
        whiteSpace: 'pre',
        height: `${lineHeight}px`,
      };

  return (
    <div className="reterm-terminal" style={terminalStyle}>
      {snapshot.screen_content.map((line, rowIndex) => (
        <div
          key={rowIndex}
          className="reterm-line"
          style={lineStyle}
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
            isTyping && rowIndex === cursorRow ? typingText : undefined,
            styledContent?.[rowIndex]
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Style a line using styled_content data if available, otherwise fall back to regex heuristics.
 */
function styleLineContent(line: string, theme: Theme, styledChars?: StyledChar[]): React.ReactNode {
  if (styledChars && styledChars.length > 0) {
    return renderStyledChars(styledChars, theme);
  }
  return styleLine(line, theme);
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
  typingText?: string,
  styledChars?: StyledChar[]
): React.ReactNode {
  // If we have typing text, show the line with typing animation
  if (typingText !== undefined && rowIndex === cursorRow) {
    const lineUpToCursor = line.slice(0, cursorCol);
    const needsSpace = lineUpToCursor.length > 0 &&
                       !lineUpToCursor.endsWith(' ') &&
                       typingText.length > 0;

    // Style the prompt part using styled data if available
    const promptChars = styledChars?.slice(0, cursorCol);
    const styledPrompt = styleLineContent(lineUpToCursor, theme, promptChars);

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
    return styleLineContent(paddedLine || '\u00A0', theme, styledChars);
  }

  // Split line at cursor position for cursor row
  const beforeCursor = paddedLine.slice(0, cursorCol);
  const cursorChar = paddedLine[cursorCol] || ' ';
  const afterCursor = paddedLine.slice(cursorCol + 1);

  // Style the parts using styled data
  const beforeChars = styledChars?.slice(0, cursorCol);
  const afterChars = styledChars?.slice(cursorCol + 1);
  const styledBefore = styleLineContent(beforeCursor, theme, beforeChars);
  const styledAfter = afterCursor ? styleLineContent(afterCursor, theme, afterChars) : null;

  return (
    <>
      {styledBefore}
      {renderCursor(cursorChar, cursorStyle, theme, charWidth, lineHeight)}
      {styledAfter}
    </>
  );
}

/**
 * Map pyte color names to theme keys.
 * Pyte uses lowercase concatenated names like "brightred", "brightgreen", etc.
 */
const PYTE_COLOR_MAP: Record<string, keyof Theme> = {
  black: 'black',
  red: 'red',
  green: 'green',
  yellow: 'yellow',
  brown: 'yellow', // pyte alias
  blue: 'blue',
  magenta: 'magenta',
  cyan: 'cyan',
  white: 'white',
  brightblack: 'brightBlack',
  brightred: 'brightRed',
  brightgreen: 'brightGreen',
  brightyellow: 'brightYellow',
  brightbrown: 'brightYellow',
  brightblue: 'brightBlue',
  brightmagenta: 'brightMagenta',
  brightcyan: 'brightCyan',
  brightwhite: 'brightWhite',
};

/**
 * Resolve a pyte color value to a CSS color string.
 * Handles: "default", named colors, hex strings (with or without #).
 */
function resolveColor(pyteColor: string, theme: Theme, isForeground: boolean): string | undefined {
  if (pyteColor === 'default') return undefined;

  // Named ANSI color
  const themeKey = PYTE_COLOR_MAP[pyteColor];
  if (themeKey) return theme[themeKey] as string;

  // Numeric ANSI index (0-15)
  const num = Number(pyteColor);
  if (!isNaN(num) && num >= 0 && num < 16) {
    return getAnsiColor(theme, num);
  }

  // Hex color (pyte uses "rrggbb" without #)
  if (/^[0-9a-fA-F]{6}$/.test(pyteColor)) return `#${pyteColor}`;

  // Already a CSS color (e.g., "#rrggbb")
  if (pyteColor.startsWith('#')) return pyteColor;

  return isForeground ? theme.foreground : undefined;
}

/**
 * Render a line using per-character styled data from Python.
 * Groups consecutive characters with the same style into spans for efficiency.
 */
function renderStyledChars(chars: StyledChar[], theme: Theme): React.ReactNode {
  if (!chars.length) return '\u00A0';

  // Group consecutive characters with the same style
  const groups: { text: string; fg?: string; bg?: string; bold?: boolean; italic?: boolean; underline?: boolean }[] = [];

  for (const ch of chars) {
    const fg = resolveColor(ch.fg, theme, true);
    const bg = resolveColor(ch.bg, theme, false);
    const bold = ch.bold || false;
    const italic = ch.italic || false;
    const underline = ch.underline || false;

    const last = groups[groups.length - 1];
    if (last && last.fg === fg && last.bg === bg && last.bold === bold && last.italic === italic && last.underline === underline) {
      last.text += ch.char;
    } else {
      groups.push({ text: ch.char, fg, bg, bold, italic, underline });
    }
  }

  // If all default style, return plain text
  if (groups.length === 1 && !groups[0].fg && !groups[0].bg && !groups[0].bold && !groups[0].italic && !groups[0].underline) {
    return groups[0].text;
  }

  return (
    <>
      {groups.map((g, i) => {
        const style: React.CSSProperties = {};
        if (g.fg) style.color = g.fg;
        if (g.bg) style.backgroundColor = g.bg;
        if (g.bold) style.fontWeight = 'bold';
        if (g.italic) style.fontStyle = 'italic';
        if (g.underline) style.textDecoration = 'underline';

        if (Object.keys(style).length === 0) {
          return <span key={i}>{g.text}</span>;
        }
        return <span key={i} style={style}>{g.text}</span>;
      })}
    </>
  );
}

/**
 * Apply prompt styling to a line based on pattern detection.
 * This is the fallback when styled_content is not available in the recording.
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
