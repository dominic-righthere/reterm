/**
 * Terminal color themes - mirrors Python themes from reterm/render/themes.py
 */

export interface Theme {
  name: string;
  background: string;
  foreground: string;
  cursor: string;
  // ANSI colors (0-7)
  black: string;
  red: string;
  green: string;
  yellow: string;
  blue: string;
  magenta: string;
  cyan: string;
  white: string;
  // Bright variants (8-15)
  brightBlack: string;
  brightRed: string;
  brightGreen: string;
  brightYellow: string;
  brightBlue: string;
  brightMagenta: string;
  brightCyan: string;
  brightWhite: string;
  // Window frame colors
  titleBar?: string;
  titleText?: string;
}

export const themes: Record<string, Theme> = {
  dracula: {
    name: 'dracula',
    background: '#282a36',
    foreground: '#f8f8f2',
    cursor: '#f8f8f2',
    black: '#21222c',
    red: '#ff5555',
    green: '#50fa7b',
    yellow: '#f1fa8c',
    blue: '#bd93f9',
    magenta: '#ff79c6',
    cyan: '#8be9fd',
    white: '#f8f8f2',
    brightBlack: '#6272a4',
    brightRed: '#ff6e6e',
    brightGreen: '#69ff94',
    brightYellow: '#ffffa5',
    brightBlue: '#d6acff',
    brightMagenta: '#ff92df',
    brightCyan: '#a4ffff',
    brightWhite: '#ffffff',
    titleBar: '#21222c',
    titleText: '#6272a4',
  },

  nord: {
    name: 'nord',
    background: '#2e3440',
    foreground: '#d8dee9',
    cursor: '#d8dee9',
    black: '#3b4252',
    red: '#bf616a',
    green: '#a3be8c',
    yellow: '#ebcb8b',
    blue: '#81a1c1',
    magenta: '#b48ead',
    cyan: '#88c0d0',
    white: '#e5e9f0',
    brightBlack: '#4c566a',
    brightRed: '#bf616a',
    brightGreen: '#a3be8c',
    brightYellow: '#ebcb8b',
    brightBlue: '#81a1c1',
    brightMagenta: '#b48ead',
    brightCyan: '#8fbcbb',
    brightWhite: '#eceff4',
    titleBar: '#242933',
    titleText: '#4c566a',
  },

  monokai: {
    name: 'monokai',
    background: '#272822',
    foreground: '#f8f8f2',
    cursor: '#f8f8f2',
    black: '#272822',
    red: '#f92672',
    green: '#a6e22e',
    yellow: '#f4bf75',
    blue: '#66d9ef',
    magenta: '#ae81ff',
    cyan: '#a1efe4',
    white: '#f8f8f2',
    brightBlack: '#75715e',
    brightRed: '#f92672',
    brightGreen: '#a6e22e',
    brightYellow: '#f4bf75',
    brightBlue: '#66d9ef',
    brightMagenta: '#ae81ff',
    brightCyan: '#a1efe4',
    brightWhite: '#f9f8f5',
    titleBar: '#1e1f1c',
    titleText: '#75715e',
  },

  'solarized-dark': {
    name: 'solarized-dark',
    background: '#002b36',
    foreground: '#839496',
    cursor: '#839496',
    black: '#073642',
    red: '#dc322f',
    green: '#859900',
    yellow: '#b58900',
    blue: '#268bd2',
    magenta: '#d33682',
    cyan: '#2aa198',
    white: '#eee8d5',
    brightBlack: '#002b36',
    brightRed: '#cb4b16',
    brightGreen: '#586e75',
    brightYellow: '#657b83',
    brightBlue: '#839496',
    brightMagenta: '#6c71c4',
    brightCyan: '#93a1a1',
    brightWhite: '#fdf6e3',
    titleBar: '#00212b',
    titleText: '#586e75',
  },

  'github-dark': {
    name: 'github-dark',
    background: '#0d1117',
    foreground: '#c9d1d9',
    cursor: '#c9d1d9',
    black: '#484f58',
    red: '#ff7b72',
    green: '#3fb950',
    yellow: '#d29922',
    blue: '#58a6ff',
    magenta: '#bc8cff',
    cyan: '#39c5cf',
    white: '#b1bac4',
    brightBlack: '#6e7681',
    brightRed: '#ffa198',
    brightGreen: '#56d364',
    brightYellow: '#e3b341',
    brightBlue: '#79c0ff',
    brightMagenta: '#d2a8ff',
    brightCyan: '#56d4dd',
    brightWhite: '#f0f6fc',
    titleBar: '#010409',
    titleText: '#6e7681',
  },

  'one-dark': {
    name: 'one-dark',
    background: '#282c34',
    foreground: '#abb2bf',
    cursor: '#528bff',
    black: '#1e2127',
    red: '#e06c75',
    green: '#98c379',
    yellow: '#d19a66',
    blue: '#61afef',
    magenta: '#c678dd',
    cyan: '#56b6c2',
    white: '#abb2bf',
    brightBlack: '#5c6370',
    brightRed: '#e06c75',
    brightGreen: '#98c379',
    brightYellow: '#d19a66',
    brightBlue: '#61afef',
    brightMagenta: '#c678dd',
    brightCyan: '#56b6c2',
    brightWhite: '#ffffff',
    titleBar: '#21252b',
    titleText: '#5c6370',
  },
};

/**
 * Get ANSI color by index (0-15)
 */
export function getAnsiColor(theme: Theme, index: number): string {
  const colors = [
    theme.black,
    theme.red,
    theme.green,
    theme.yellow,
    theme.blue,
    theme.magenta,
    theme.cyan,
    theme.white,
    theme.brightBlack,
    theme.brightRed,
    theme.brightGreen,
    theme.brightYellow,
    theme.brightBlue,
    theme.brightMagenta,
    theme.brightCyan,
    theme.brightWhite,
  ];
  return index >= 0 && index < colors.length ? colors[index] : theme.foreground;
}

/**
 * Resolve 256-color index to hex color
 */
export function resolve256Color(index: number, theme: Theme): string {
  if (index < 16) {
    return getAnsiColor(theme, index);
  } else if (index < 232) {
    // 216 color cube (6x6x6)
    const i = index - 16;
    const r = Math.floor(i / 36) * 51;
    const g = (Math.floor(i / 6) % 6) * 51;
    const b = (i % 6) * 51;
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  } else if (index < 256) {
    // Grayscale
    const gray = (index - 232) * 10 + 8;
    return `#${gray.toString(16).padStart(2, '0')}${gray.toString(16).padStart(2, '0')}${gray.toString(16).padStart(2, '0')}`;
  }
  return theme.foreground;
}

export function getTheme(name: string): Theme {
  const theme = themes[name.toLowerCase()];
  if (!theme) {
    console.warn(`Unknown theme: ${name}, falling back to dracula`);
    return themes.dracula;
  }
  return theme;
}

export function listThemes(): string[] {
  return Object.keys(themes);
}
