import React, { useEffect } from 'react';

const wsUrl = import.meta.env.VITE_ORCHESTRATOR_WS_URL || 'ws://localhost:8000/v1/ws';

export default function App() {
  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      console.log('WS:', event.data);
    };
    ws.onopen = () => console.log('WebSocket connected');
    ws.onclose = () => console.log('WebSocket closed');
    return () => ws.close();
  }, []);

  return (
    <div style={{ padding: '1rem' }}>
      <h1>MockPilot Preview</h1>
      <p>Check console for WebSocket messages.</p>
    </div>
  );
}
