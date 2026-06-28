import type { RecordingLog, TerminalSnapshot, CommandExecution } from '../types/recording';

export interface TimelineEntry {
  snapshot: TerminalSnapshot;
  startTime: number; // ms from start
  duration: number; // ms
  typingCommand?: string; // Full command to type (for animation)
  typingDuration?: number; // Total duration for typing animation
  isTyping?: boolean; // Whether this frame shows typing animation
}

/**
 * Check if a terminal snapshot has all blank/empty lines.
 */
export function isBlankScreen(snapshot: TerminalSnapshot): boolean {
  return snapshot.screen_content.every(line => line.trim() === '');
}

export const PROMPT_REGEXES = [
  /^(➜\s+\S+)/,           // oh-my-zsh
  /^(\S+@\S+:[^$]+\$\s*)/, // bash
  /^(\$\s+)/,              // simple $
];

/**
 * Extract the prompt pattern by searching all commands in the recording.
 * Supports oh-my-zsh, bash, and simple $ prompts.
 */
export function extractPromptFromRecording(commands: CommandExecution[]): string | null {
  for (const cmd of commands) {
    if (!cmd.terminal_after) continue;
    for (const line of cmd.terminal_after.screen_content) {
      for (const regex of PROMPT_REGEXES) {
        const match = line.match(regex);
        if (match) return match[1];
      }
    }
  }
  return null;
}

/**
 * Filter out echoed command line from terminal_after.
 * Some terminals echo the typed command on a separate line before the prompt+command line.
 */
export function filterEchoedCommand(snapshot: TerminalSnapshot, command: string): TerminalSnapshot {
  const firstLine = snapshot.screen_content[0]?.trim();
  if (firstLine && firstLine === command.trim()) {
    const remaining = snapshot.screen_content.slice(1);
    // Don't filter if it would leave a blank screen
    if (remaining.every(line => line.trim() === '')) {
      return snapshot;
    }
    return {
      ...snapshot,
      screen_content: remaining,
      cursor_position: [
        Math.max(0, snapshot.cursor_position[0] - 1),
        snapshot.cursor_position[1],
      ] as [number, number],
    };
  }
  return snapshot;
}

/**
 * Build a timeline of snapshots with proper timing from the recording.
 * Uses single entries for typing phases with time-based interpolation.
 */
export function buildTimeline(recording: RecordingLog | null, typingSpeed: number = 50): TimelineEntry[] {
  if (!recording) return [];

  const timeline: TimelineEntry[] = [];
  let currentTime = 0;

  for (let i = 0; i < recording.commands.length; i++) {
    const cmd = recording.commands[i];

    // Add single typing phase entry if we have terminal_before
    if (cmd.terminal_before && cmd.command) {
      let snapshot = cmd.terminal_before;

      // For the first command, if terminal_before is blank, synthesize initial state with prompt
      if (i === 0 && isBlankScreen(cmd.terminal_before) && cmd.terminal_after) {
        const prompt = extractPromptFromRecording(recording.commands);
        if (prompt) {
          snapshot = {
            ...cmd.terminal_before,
            screen_content: [prompt, ...cmd.terminal_before.screen_content.slice(1)],
            cursor_position: [0, prompt.length] as [number, number],
          };
        }
      }

      // For subsequent commands, filter out echoed line from previous command
      if (i > 0) {
        const prevCmd = recording.commands[i - 1];
        if (prevCmd?.command) {
          snapshot = filterEchoedCommand(snapshot, prevCmd.command);
        }
      }

      const typingDuration = cmd.command.length * typingSpeed;
      timeline.push({
        snapshot,
        startTime: currentTime,
        duration: typingDuration,
        typingCommand: cmd.command,
        typingDuration: typingDuration,
        isTyping: true,
      });
      currentTime += typingDuration + 100; // + pause before result
    }

    // Add intermediate snapshots if available (progressive output).
    // Skip pre-output frames that only show the command being echoed (a prefix
    // of the full command): the typing animation already shows the command
    // appearing, so these would make it flash back to a partial word (e.g.
    // `echo`, `ls`, `uname`) right before the output.
    const showsFullCommand = (s: TerminalSnapshot) =>
      !cmd.command || s.screen_content.join('\n').includes(cmd.command);
    const intermediateSnapshots = (cmd.intermediate_snapshots || []).filter(showsFullCommand);
    if (intermediateSnapshots.length > 0 && cmd.terminal_after) {
      // Calculate duration for each intermediate snapshot
      const totalDuration = cmd.duration_ms || 500;
      const snapshotDuration = totalDuration / (intermediateSnapshots.length + 1);

      for (const snapshot of intermediateSnapshots) {
        // Filter echoed command from intermediate snapshots too
        const filteredSnapshot = cmd.command
          ? filterEchoedCommand(snapshot, cmd.command)
          : snapshot;

        timeline.push({
          snapshot: filteredSnapshot,
          startTime: currentTime,
          duration: snapshotDuration,
          isTyping: false,
        });
        currentTime += snapshotDuration;
      }

      // Add final terminal_after
      const filteredFinal = cmd.command
        ? filterEchoedCommand(cmd.terminal_after, cmd.command)
        : cmd.terminal_after;

      timeline.push({
        snapshot: filteredFinal,
        startTime: currentTime,
        duration: snapshotDuration,
        isTyping: false,
      });
      currentTime += snapshotDuration;
    } else if (cmd.terminal_after) {
      // No intermediate snapshots - add result directly
      const filteredSnapshot = cmd.command
        ? filterEchoedCommand(cmd.terminal_after, cmd.command)
        : cmd.terminal_after;

      const duration = cmd.duration_ms || 500;
      timeline.push({
        snapshot: filteredSnapshot,
        startTime: currentTime,
        duration,
        isTyping: false,
      });
      currentTime += duration;
    }
  }

  // Add final state if available
  if (recording.final_terminal_state && timeline.length > 0) {
    const lastEntry = timeline[timeline.length - 1];
    // Only add if it's different from the last command's snapshot
    if (recording.final_terminal_state.timestamp !== lastEntry.snapshot.timestamp) {
      timeline.push({
        snapshot: recording.final_terminal_state,
        startTime: currentTime,
        duration: 500, // hold final frame
        isTyping: false,
      });
    }
  }

  return timeline;
}
