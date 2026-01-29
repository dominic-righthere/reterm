import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import 'reterm-player/style.css';
import Doc from './demo.mdx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <div className="container">
      <Doc />
    </div>
  </StrictMode>
);
