/**
 * TypeScript types for reterm recording JSON logs.
 * These mirror the Python Pydantic models from reterm/output/models.py
 */

export interface TerminalSnapshot {
  timestamp: string;
  cursor_position: [number, number]; // [row, col]
  screen_content: string[];
  screen_content_plain: string;
  dimensions: [number, number]; // [rows, cols]
}

export interface CommandExecution {
  id: string;
  command: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  exit_code: number;
  stdout: string;
  stderr: string;
  combined_output: string;
  working_directory: string;
  terminal_before: TerminalSnapshot | null;
  terminal_after: TerminalSnapshot | null;
  intermediate_snapshots?: TerminalSnapshot[];
}

export interface StepExecution {
  type: string;
  timestamp: string;
  duration_ms: number | null;
  details: Record<string, unknown>;
}

export interface RecordingMetadata {
  tool_version: string;
  script_file: string | null;
  started_at: string;
  finished_at: string;
  total_duration_ms: number;
  shell: string;
  terminal_size: [number, number]; // [cols, rows]
  theme: string;
  platform: string;
  python_version: string;
}

export interface RecordingLog {
  schema_version: string;
  metadata: RecordingMetadata;
  commands: CommandExecution[];
  steps: StepExecution[];
  final_terminal_state: TerminalSnapshot | null;
  errors: Record<string, unknown>[];
  captured_variables: Record<string, string>;
  all_commands_text: string;
  all_output_text: string;
  success: boolean;
  failed_commands: string[];
}
