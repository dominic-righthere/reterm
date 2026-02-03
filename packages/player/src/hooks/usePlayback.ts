import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { RecordingLog, TerminalSnapshot } from '../types/recording';
import { buildTimeline } from '../utils/timeline';
import type { TimelineEntry } from '../utils/timeline';

export type { TimelineEntry };

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

  // Stabilize onComplete so inline callbacks don't restart the animation loop
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

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
          onCompleteRef.current?.();
          return;
        }
      }

      animationId = requestAnimationFrame(animate);
    };

    animationId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [state.isPlaying, state.speed, state.totalDuration, timeline, loop]);

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
