import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { RecordingLog } from '../src/types/recording';
import { buildTimeline } from '../src/utils/timeline';

const filePath = process.argv[2];
if (!filePath) {
  console.error('Usage: tsx scripts/dump-timeline.ts <recording.json>');
  process.exit(1);
}

const absolutePath = resolve(filePath);
const raw = readFileSync(absolutePath, 'utf-8');
const recording: RecordingLog = JSON.parse(raw);

const timeline = buildTimeline(recording);

console.log(`Recording: ${absolutePath}`);
console.log(`Commands:  ${recording.commands.length}`);
console.log(`Timeline:  ${timeline.length} entries`);

const totalDuration = timeline.length > 0
  ? timeline[timeline.length - 1].startTime + timeline[timeline.length - 1].duration
  : 0;
console.log(`Duration:  ${(totalDuration / 1000).toFixed(2)}s`);
console.log('─'.repeat(80));

for (let i = 0; i < timeline.length; i++) {
  const entry = timeline[i];
  const type = entry.isTyping ? 'typing' : 'output';
  const tag = i === timeline.length - 1 && !entry.isTyping ? 'final' : type;

  const startSec = (entry.startTime / 1000).toFixed(2);
  const durMs = Math.round(entry.duration);

  const screenPreview = entry.snapshot.screen_content
    .filter(line => line.trim() !== '')
    .slice(0, 3)
    .map(line => line.length > 72 ? line.slice(0, 72) + '...' : line);

  console.log(`[${String(i).padStart(3)}] ${tag.padEnd(6)}  start=${startSec}s  dur=${durMs}ms`);

  if (entry.typingCommand) {
    console.log(`       cmd: ${entry.typingCommand}`);
  }

  for (const line of screenPreview) {
    console.log(`       | ${line}`);
  }

  console.log();
}
