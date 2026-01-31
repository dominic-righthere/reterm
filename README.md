# reterm

AI-native terminal recording tool. Dual output: GIF for humans, structured JSON for AI tools.

## Features

- **YAML-based scripts** - Declarative `.reterm` files define what to record
- **Dual output** - GIF for visual sharing + structured JSON log for AI/CLI consumption
- **MCP server** - Expose recordings as tools for AI agents
- **Redaction** - Hide secrets/paths with visible (`[REDACTED]`) or seamless replacement
- **React player** - `reterm-player` npm package for embedding recordings in MDX/docs
- **Interactive support** - `wait_for` step for prompt-driven flows
- **6 themes** - Dracula, Nord, Monokai, Solarized Dark, GitHub Dark, One Dark

## Install

**Python CLI** (requires Python 3.11+):

```bash
uv tool install reterm
```

**React player**:

```bash
npm install reterm-player
```

## Quick Start

Create a `.reterm` script:

```yaml
meta:
  name: "Hello World"

config:
  shell: /bin/zsh
  theme: dracula

steps:
  - run: echo "Hello from reterm!"
  - sleep: 500ms
  - run: ls -la
  - sleep: 1s
```

Run it:

```bash
# Generate GIF + JSON log
reterm run hello.reterm -o hello.gif -l hello.json

# JSON log only (no GIF)
reterm run hello.reterm --log-only -l hello.json
```

## CLI Commands

```bash
reterm run <script>          # Execute script, generate outputs
reterm new <file>            # Create script from template
reterm validate <script>     # Validate without executing
reterm redact <log>          # Redact sensitive info from log
reterm render <log> -o <gif> # Re-render GIF from (redacted) log
reterm serve                 # Start MCP server
reterm themes                # List available themes
reterm schema                # Print JSON log schema
```

### Redaction

```bash
# Visible redaction - shows [HOME] in output
reterm redact demo.json -p "/home/user" -r "HOME" -o redacted.json

# Seamless - replaces without visual indicator
reterm redact demo.json -p "/home/user" -r "/home/alice" --seamless -o clean.json

# Regex
reterm redact demo.json -p "sk-[a-zA-Z0-9]+" -r "API_KEY" --regex -o redacted.json

# Re-render GIF from redacted log
reterm render redacted.json -o redacted.gif
```

## React Player

```bash
npm install reterm-player
```

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
  showControls
  showWindowFrame
  cursorStyle="block"
/>
```

### Props

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
| `cursorStyle` | `'block' \| 'underline' \| 'bar'` | `'block'` | Cursor appearance |
| `fontSize` | `number` | `14` | Font size in pixels |

## MCP Server

Start the MCP server for AI tool integration:

```bash
reterm serve                  # stdio transport (default)
reterm serve --transport sse  # SSE transport
```

## Script Format

```yaml
meta:
  name: "Script Name"
  description: "What this records"

config:
  shell: /bin/zsh        # Shell to use
  theme: dracula         # Color theme
  size: [80, 24]         # Terminal size [cols, rows]
  typing_speed: 50ms     # Typing animation speed

steps:
  - run: echo "execute a command"
  - type: "typed with animation"
    then: enter
  - sleep: 1s
  - key: ctrl+c
  - wait_for: "pattern"           # Wait for output
    timeout: 5s
  - screenshot: capture.png
  - note: "Not visible in terminal"
```

### Step Types

| Step | Description |
|------|-------------|
| `run` | Execute command |
| `type` | Type with animation |
| `sleep` | Pause |
| `key` | Send special key |
| `wait_for` | Wait for output pattern |
| `screenshot` | Capture frame |
| `note` | Metadata only |

## JSON Log Output

Every recording produces a structured JSON log:

```json
{
  "schema_version": "1.0.0",
  "metadata": {
    "terminal_size": [80, 24],
    "theme": "dracula",
    "total_duration_ms": 2500
  },
  "commands": [
    {
      "command": "echo hello",
      "exit_code": 0,
      "stdout": "hello",
      "duration_ms": 120,
      "terminal_before": { "screen_content": ["..."], "cursor_position": [0, 0] },
      "terminal_after": { "screen_content": ["..."], "cursor_position": [1, 0] }
    }
  ],
  "success": true,
  "all_commands_text": "echo hello",
  "all_output_text": "hello"
}
```

## License

MIT
