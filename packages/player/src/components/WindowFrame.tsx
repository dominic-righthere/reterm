import type { Theme } from '../themes';

export interface WindowFrameProps {
  title?: string;
  theme: Theme;
  children: React.ReactNode;
}

/**
 * macOS-style terminal window frame with traffic light buttons.
 */
export function WindowFrame({ title = 'Terminal', theme, children }: WindowFrameProps) {
  // Use theme's titleBar color or derive from background
  const titleBarBg = (theme as { titleBar?: string }).titleBar || darken(theme.background, 0.1);
  const titleTextColor = (theme as { titleText?: string }).titleText || theme.foreground + '99';

  return (
    <div
      className="reterm-window"
      style={{
        borderRadius: '8px',
        overflow: 'hidden',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Title bar */}
      <div
        className="reterm-titlebar"
        style={{
          background: titleBarBg,
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          borderBottom: `1px solid rgba(0, 0, 0, 0.2)`,
        }}
      >
        {/* Traffic lights */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <TrafficLight color="#ff5f57" hoverColor="#ff3b30" />
          <TrafficLight color="#febc2e" hoverColor="#ffcc00" />
          <TrafficLight color="#28c840" hoverColor="#00c853" />
        </div>
        {/* Title */}
        <span
          style={{
            flex: 1,
            textAlign: 'center',
            color: titleTextColor,
            fontSize: '13px',
            fontWeight: 500,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            letterSpacing: '0.01em',
            userSelect: 'none',
          }}
        >
          {title}
        </span>
        {/* Spacer for symmetry */}
        <div style={{ width: '52px' }} />
      </div>
      {/* Terminal content */}
      {children}
    </div>
  );
}

function TrafficLight({ color, hoverColor }: { color: string; hoverColor: string }) {
  return (
    <span
      style={{
        width: '12px',
        height: '12px',
        borderRadius: '50%',
        background: color,
        boxShadow: `inset 0 0 0 0.5px rgba(0, 0, 0, 0.15), 0 1px 1px rgba(0, 0, 0, 0.1)`,
        cursor: 'default',
        transition: 'background 0.15s ease',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = hoverColor)}
      onMouseLeave={(e) => (e.currentTarget.style.background = color)}
    />
  );
}

/**
 * Darken a hex color by a percentage.
 */
function darken(hex: string, amount: number): string {
  const num = parseInt(hex.replace('#', ''), 16);
  const r = Math.max(0, Math.floor((num >> 16) * (1 - amount)));
  const g = Math.max(0, Math.floor(((num >> 8) & 0x00ff) * (1 - amount)));
  const b = Math.max(0, Math.floor((num & 0x0000ff) * (1 - amount)));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}
