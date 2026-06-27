# reterm-player

React component for replaying terminal recordings from [reterm](https://github.com/dominic-righthere/reterm) JSON logs.

## Install

```bash
npm install reterm-player
```

## Usage

```tsx
import { TerminalPlayer } from 'reterm-player';
import 'reterm-player/style.css';

// From inline data
<TerminalPlayer data={recording} autoPlay />

// From URL
<TerminalPlayer src="/recordings/demo.json" showControls />

// Full options
<TerminalPlayer
  data={recording}
  autoPlay
  loop
  speed={1.5}
  theme="dracula"
  title="my-project"
  showControls
  showWindowFrame
  fit
  cursorStyle="block"
/>
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `data` | `RecordingLog` | - | Inline JSON recording data |
| `src` | `string` | - | URL to fetch recording from |
| `autoPlay` | `boolean` | `false` | Start playing automatically |
| `loop` | `boolean` | `false` | Loop playback |
| `speed` | `number` | `1.0` | Playback speed multiplier |
| `theme` | `string` | from log | Theme override |
| `showControls` | `boolean` | `true` | Show play/pause/seek/speed controls |
| `showWindowFrame` | `boolean` | `true` | Show macOS-style window frame |
| `title` | `string` | from log | Window title (defaults to script name or `'Terminal'`) |
| `fit` | `boolean` | `false` | Fill container width; terminal scrolls horizontally if needed |
| `cursorStyle` | `'block' \| 'underline' \| 'bar'` | `'block'` | Cursor appearance |
| `fontSize` | `number` | `14` | Font size in pixels |
| `typingSpeed` | `number` | `50` | Typing animation speed in ms per character |
| `className` | `string` | - | Additional CSS class |
| `style` | `CSSProperties` | - | Inline styles |
| `onComplete` | `() => void` | - | Callback when playback completes |
| `onLoad` | `(recording) => void` | - | Callback when recording loads |
| `onError` | `(error) => void` | - | Callback on error |

## License

MIT — see the main [reterm](https://github.com/dominic-righthere/reterm) repo for details.
