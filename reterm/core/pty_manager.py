"""PTY process management using ptyprocess."""

import os
import select
import signal
from dataclasses import dataclass, field
from typing import Callable

from ptyprocess import PtyProcessUnicode


@dataclass
class PTYConfig:
    """Configuration for PTY process."""

    shell: str = "/bin/zsh"
    rows: int = 24
    cols: int = 80
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None


class PTYManager:
    """Manages a pseudo-terminal process."""

    def __init__(self, config: PTYConfig) -> None:
        self.config = config
        self.process: PtyProcessUnicode | None = None
        self._output_callbacks: list[Callable[[str], None]] = []

    def start(self) -> None:
        """Start the PTY process."""
        # Build environment
        env = os.environ.copy()
        env.update(self.config.env)
        # Set TERM for proper terminal behavior
        env["TERM"] = "xterm-256color"
        # Disable prompt customization that might interfere
        env["PROMPT_COMMAND"] = ""

        self.process = PtyProcessUnicode.spawn(
            [self.config.shell],
            dimensions=(self.config.rows, self.config.cols),
            env=env,
            cwd=self.config.cwd,
        )

    def stop(self) -> None:
        """Stop the PTY process."""
        if self.process is not None:
            try:
                # Send exit command first
                self.write("exit\r")
                # Give it a moment to exit gracefully
                import time
                for _ in range(10):
                    if not self.process.isalive():
                        break
                    time.sleep(0.05)
                # Force kill if still alive
                if self.process.isalive():
                    self.process.kill(signal.SIGKILL)
                # Brief wait with timeout by checking isalive
                for _ in range(10):
                    if not self.process.isalive():
                        break
                    time.sleep(0.05)
            except Exception:
                pass
            self.process = None

    def write(self, data: str) -> None:
        """Write data to the PTY (simulates user input)."""
        if self.process is None:
            raise RuntimeError("PTY not started")
        self.process.write(data)

    def write_line(self, line: str) -> None:
        """Write a line followed by Enter."""
        self.write(line + "\r")

    def read(self, timeout: float = 0.1) -> str:
        """Read available output from PTY with timeout.

        Returns empty string if no data available or timeout.
        """
        if self.process is None:
            raise RuntimeError("PTY not started")

        try:
            # Check if data is available
            fd = self.process.fd
            readable, _, _ = select.select([fd], [], [], timeout)
            if not readable:
                return ""

            # Read available data
            data = self.process.read(1024)

            # Notify callbacks
            for callback in self._output_callbacks:
                callback(data)

            return data
        except EOFError:
            return ""

    def read_until_idle(
        self,
        idle_timeout: float = 0.5,
        max_timeout: float = 30.0,
        read_interval: float = 0.05,
    ) -> str:
        """Read until no output for idle_timeout seconds.

        Args:
            idle_timeout: How long to wait with no output before considering idle
            max_timeout: Maximum total time to wait
            read_interval: How often to check for new output

        Returns:
            All accumulated output
        """
        import time

        output = ""
        last_output_time = time.time()
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed >= max_timeout:
                break

            idle_time = time.time() - last_output_time
            if idle_time >= idle_timeout:
                break

            chunk = self.read(timeout=read_interval)
            if chunk:
                output += chunk
                last_output_time = time.time()

        return output

    def send_key(self, key: str) -> None:
        """Send a special key to the PTY."""
        key_map = {
            "enter": "\r",
            "tab": "\t",
            "escape": "\x1b",
            "backspace": "\x7f",
            "delete": "\x1b[3~",
            "up": "\x1b[A",
            "down": "\x1b[B",
            "left": "\x1b[D",
            "right": "\x1b[C",
            "home": "\x1b[H",
            "end": "\x1b[F",
            "pageup": "\x1b[5~",
            "pagedown": "\x1b[6~",
            "ctrl+c": "\x03",
            "ctrl+d": "\x04",
            "ctrl+z": "\x1a",
            "ctrl+l": "\x0c",
            "ctrl+a": "\x01",
            "ctrl+e": "\x05",
            "ctrl+k": "\x0b",
            "ctrl+u": "\x15",
            "ctrl+w": "\x17",
        }

        key_lower = key.lower()
        if key_lower in key_map:
            self.write(key_map[key_lower])
        elif key_lower.startswith("ctrl+") and len(key_lower) == 6:
            # Handle ctrl+<letter> generically
            char = key_lower[5]
            if char.isalpha():
                ctrl_code = chr(ord(char.upper()) - ord("A") + 1)
                self.write(ctrl_code)
        else:
            # Unknown key, write as-is
            self.write(key)

    def resize(self, rows: int, cols: int) -> None:
        """Resize the PTY."""
        if self.process is not None:
            self.process.setwinsize(rows, cols)
            self.config.rows = rows
            self.config.cols = cols

    def is_alive(self) -> bool:
        """Check if the PTY process is still running."""
        if self.process is None:
            return False
        return self.process.isalive()

    def get_exit_code(self) -> int | None:
        """Get the exit code of the PTY process (if terminated)."""
        if self.process is None:
            return None
        if self.process.isalive():
            return None
        return self.process.exitstatus

    def add_output_callback(self, callback: Callable[[str], None]) -> None:
        """Add a callback to be called when output is received."""
        self._output_callbacks.append(callback)

    def __enter__(self) -> "PTYManager":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
