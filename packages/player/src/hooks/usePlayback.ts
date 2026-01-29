import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { RecordingLog, TerminalSnapshot } from '../types/recording';

export interface TimelineEntry {
  snapshot: TerminalSnapshot;
  startTime: number; // ms from start
  duration: number; // ms
  typingCommand?: string; // Full command to type (for animation)
  typingDuration?: number; // Total duration for typing animation
  isTyping?: boolean; // Whether this frame shows typing animation
}

export interface PlaybackState {
  isPlaying: boolean;
  currentIndex: number;
  currentTime: number; // ms from start
  totalDuration: number;
  speed: number;
}

export interface PlaybackOptions {
  speed?: number;
  loop?: boolean;
  autoPlay?: boolean;
  onComplete?: () => void;
  typingSpeed?: number; // ms per character for typing animation (default 50)
}

export interface UsePlaybackResult {
  currentSnapshot: TerminalSnapshot | null;
  isPlaying: boolean;
  progress: number; // 0-1
  currentTime: number;
  totalDuration: number;
  speed: number;
  typingText?: string; // Current typing text for animation
  isTyping: boolean; // Whether currently showing typing animation
  play: () => void;
  pause: () => void;
  toggle: () => void;
  seek: (progress: number) => void;
  setSpeed: (speed: number) => void;
}

/**
 * Check if a terminal snapshot has all blank/empty lines.
 */
function isBlankScreen(snapshot: TerminalSnapshot): boolean {
  return snapshot.screen_content.every(line => line.trim() === '');
}

/**
 * Extract the prompt pattern from terminal_after snapshot.
 * Looks for oh-my-zsh style "➜  dirname" pattern.
 */
function extractPromptFromAfter(snapshot: TerminalSnapshot): string | null {
  for (const line of snapshot.screen_content) {
    // Match oh-my-zsh prompt: ➜  dirname (with trailing space before command)
    const match = line.match(/^(➜\s+\S+)/);
    if (match) return match[1];
  }
  return null;
}

/**
 * Filter out echoed command line from terminal_after.
 * Some terminals echo the typed command on a separate line before the prompt+command line.
 */
function filterEchoedCommand(snapshot: TerminalSnapshot, command: string): TerminalSnapshot {
  const firstLine = snapshot.screen_content[0]?.trim();
  // If first line matches the command (without prompt), remove it
  if (firstLine && firstLine === command.trim()) {
    return {
      ...snapshot,
      screen_content: snapshot.screen_content.slice(1),
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
function buildTimeline(recording: RecordingLog | null, typingSpeed: number = 50): TimelineEntry[] {
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
        const prompt = extractPromptFromAfter(cmd.terminal_after);
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

    // Add intermediate snapshots if available (progressive output)
    const intermediateSnapshots = cmd.intermediate_snapshots || [];
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

/**
 * Find the timeline index for a given time.
 */
function findIndexForTime(timeline: TimelineEntry[], time: number): number {
  for (let i = timeline.length - 1; i >= 0; i--) {
    if (time >= timeline[i].startTime) {
      return i;
    }
  }
  return 0;
}

/**
 * Hook to manage playback state for terminal recordings.
 */
export function usePlayback(
  recording: RecordingLog | null,
  options: PlaybackOptions = {}
): UsePlaybackResult {
  const { speed: initialSpeed = 1.0, loop = false, autoPlay = false, onComplete, typingSpeed = 50 } = options;

  const [state, setState] = useState<PlaybackState>({
    isPlaying: false,
    currentIndex: 0,
    currentTime: 0,
    totalDuration: 0,
    speed: initialSpeed,
  });

  const timeline = useMemo(() => buildTimeline(recording, typingSpeed), [recording, typingSpeed]);
  const startTimeRef = useRef<number | null>(null);
  const pausedAtRef = useRef<number>(0);

  // Calculate total duration
  useEffect(() => {
    if (timeline.length > 0) {
      const last = timeline[timeline.length - 1];
      const total = last.startTime + last.duration;
      setState((s) => ({ ...s, totalDuration: total }));
    } else {
      setState((s) => ({ ...s, totalDuration: 0 }));
    }
  }, [timeline]);

  // Auto-play on mount if enabled
  useEffect(() => {
    if (autoPlay && timeline.length > 0) {
      setState((s) => ({ ...s, isPlaying: true }));
    }
  }, [autoPlay, timeline.length]);

  // Animation loop
  useEffect(() => {
    if (!state.isPlaying || timeline.length === 0) return;

    let animationId: number;

    const animate = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp - pausedAtRef.current;
      }

      const elapsed = (timestamp - startTimeRef.current) * state.speed;
      const currentTime = Math.min(elapsed, state.totalDuration);
      const currentIndex = findIndexForTime(timeline, currentTime);

      setState((s) => ({
        ...s,
        currentTime,
        currentIndex,
      }));

      // Check if playback is complete
      if (currentTime >= state.totalDuration) {
        if (loop) {
          // Reset and continue
          startTimeRef.current = null;
          pausedAtRef.current = 0;
          setState((s) => ({ ...s, currentTime: 0, currentIndex: 0 }));
        } else {
          // Stop playback
          setState((s) => ({ ...s, isPlaying: false }));
          onComplete?.();
          return;
        }
      }

      animationId = requestAnimationFrame(animate);
    };

    animationId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [state.isPlaying, state.speed, state.totalDuration, timeline, loop, onComplete]);

  const play = useCallback(() => {
    startTimeRef.current = null;
    setState((s) => ({ ...s, isPlaying: true }));
  }, []);

  const pause = useCallback(() => {
    pausedAtRef.current = state.currentTime;
    startTimeRef.current = null;
    setState((s) => ({ ...s, isPlaying: false }));
  }, [state.currentTime]);

  const toggle = useCallback(() => {
    if (state.isPlaying) {
      pause();
    } else {
      // If at end, restart
      if (state.currentTime >= state.totalDuration) {
        pausedAtRef.current = 0;
        setState((s) => ({ ...s, currentTime: 0, currentIndex: 0 }));
      }
      play();
    }
  }, [state.isPlaying, state.currentTime, state.totalDuration, play, pause]);

  const seek = useCallback(
    (progress: number) => {
      const clampedProgress = Math.max(0, Math.min(1, progress));
      const newTime = clampedProgress * state.totalDuration;
      const newIndex = findIndexForTime(timeline, newTime);

      pausedAtRef.current = newTime;
      startTimeRef.current = null;

      setState((s) => ({
        ...s,
        currentTime: newTime,
        currentIndex: newIndex,
      }));
    },
    [state.totalDuration, timeline]
  );

  const setSpeed = useCallback((newSpeed: number) => {
    // Preserve current position when changing speed
    pausedAtRef.current = state.currentTime;
    startTimeRef.current = null;
    setState((s) => ({ ...s, speed: newSpeed }));
  }, [state.currentTime]);

  const currentEntry = timeline[state.currentIndex];
  const currentSnapshot = currentEntry?.snapshot ?? null;
  const progress = state.totalDuration > 0 ? state.currentTime / state.totalDuration : 0;

  // Calculate typing text dynamically based on time interpolation
  let typingText: string | undefined;
  if (currentEntry?.typingCommand && currentEntry.typingDuration) {
    const entryElapsed = state.currentTime - currentEntry.startTime;
    const typingProgress = Math.min(entryElapsed / currentEntry.typingDuration, 1);
    const charIndex = Math.floor(typingProgress * currentEntry.typingCommand.length);
    typingText = currentEntry.typingCommand.slice(0, charIndex);
  }

  return {
    currentSnapshot,
    isPlaying: state.isPlaying,
    progress,
    currentTime: state.currentTime,
    totalDuration: state.totalDuration,
    speed: state.speed,
    typingText,
    isTyping: currentEntry?.isTyping ?? false,
    play,
    pause,
    toggle,
    seek,
    setSpeed,
  };
}
