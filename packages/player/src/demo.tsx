import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { TerminalPlayer } from './TerminalPlayer';
import type { RecordingLog } from './types/recording';
import './styles/terminal.css';

function App() {
  const [recording, setRecording] = useState<RecordingLog | null>(null);

  useEffect(() => {
    fetch('/demo/recording.json')
      .then((res) => res.json())
      .then(setRecording);
  }, []);

  if (!recording) {
    return <div>Loading recording...</div>;
  }

  return (
    <div>
      <h1>@reterm/player Demo</h1>

      <div className="demo-section">
        <h2>Default (Dracula theme, with controls)</h2>
        <TerminalPlayer data={recording} showControls />
      </div>

      <div className="demo-section">
        <h2>Nord theme, auto-play, looping, 1.5x speed</h2>
        <TerminalPlayer data={recording} theme="nord" autoPlay loop speed={1.5} />
      </div>

      <div className="demo-section">
        <h2>GitHub Dark, no controls, auto-play</h2>
        <TerminalPlayer data={recording} theme="github-dark" autoPlay showControls={false} loop />
      </div>

      <div className="demo-section">
        <h2>Monokai, larger font</h2>
        <TerminalPlayer data={recording} theme="monokai" fontSize={16} />
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
