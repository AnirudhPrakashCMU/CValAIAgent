import React, { useEffect, useRef, useState } from 'react';
import ReconnectingWebSocket from 'reconnecting-websocket';

const HTTP_URL = import.meta.env.VITE_ORCHESTRATOR_HTTP_URL || 'http://localhost:8000';
const WS_BASE = import.meta.env.VITE_ORCHESTRATOR_WS_URL || 'ws://localhost:8000';

function useSession() {
  const [session, setSession] = useState(null);
  const [token, setToken] = useState(null);

  useEffect(() => {
    async function create() {
      try {
        const res = await fetch(`${HTTP_URL}/v1/sessions`, { method: 'POST' });
        const data = await res.json();
        setSession(data.session_id);
        setToken(data.token.access_token);
      } catch (err) {
        console.error('Failed to create session', err);
      }
    }
    create();
  }, []);
  return { session, token };
}

export default function App() {
  const { session, token } = useSession();
  const [ws, setWs] = useState(null);
  const [transcripts, setTranscripts] = useState([]);
  const [componentCode, setComponentCode] = useState('');
  const [insight, setInsight] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const recordingChunksRef = useRef([]);
  const recorderRef = useRef(null);

  useEffect(() => {
    if (!session || !token) return;
    const url = `${WS_BASE}/v1/ws/${session}?token=${token}`;
    const socket = new ReconnectingWebSocket(url);
    socket.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.kind === 'transcript') setTranscripts((t) => [...t, msg.text]);
        else if (msg.kind === 'component') setComponentCode(msg.jsx);
        else if (msg.kind === 'insight') setInsight(msg);
        else if (msg.kind === 'error') console.error(msg.message);
      } catch (err) {
        console.log('WS raw:', e.data);
      }
    };
    setWs(socket);
    return () => socket.close();
  }, [session, token]);

  async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream);
    recorderRef.current = mr;
    recordingChunksRef.current = [];
    setAudioUrl(null);
    mr.ondataavailable = async (e) => {
      recordingChunksRef.current.push(e.data);
      if (ws && ws.readyState === WebSocket.OPEN) {
        const array = new Uint8Array(await e.data.arrayBuffer());
        const binary = Array.from(array, (b) => String.fromCharCode(b)).join('');
        const b64 = btoa(binary);
        ws.send(
          JSON.stringify({
            kind: 'audio_chunk',
            session_id: session,
            data_b64: b64,
          })
        );
      }
    };
    mr.start(500);
  }

  function stopRecording() {
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current.stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(recordingChunksRef.current, { type: 'audio/webm' });
      setAudioUrl(URL.createObjectURL(blob));
      recordingChunksRef.current = [];
    }
  }

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-2xl font-bold">MockPilot</h1>
      <div className="space-x-2">
        <button className="px-3 py-1 bg-blue-500 text-white rounded" onClick={startRecording}>
          Start
        </button>
        <button className="px-3 py-1 bg-gray-500 text-white rounded" onClick={stopRecording}>
          Stop
        </button>
      </div>
      {audioUrl && (
        <div>
          <h2 className="font-semibold mt-2">Recorded Audio</h2>
          <audio src={audioUrl} controls className="w-full" />
        </div>
      )}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <h2 className="font-semibold mb-2">Transcripts</h2>
          <ul className="text-sm max-h-64 overflow-auto list-disc pl-5 space-y-1">
            {transcripts.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="font-semibold mb-2">Latest Component</h2>
          {componentCode ? (
            <pre className="bg-gray-100 p-2 text-xs overflow-auto">{componentCode}</pre>
          ) : (
            <p className="text-sm text-gray-500">Waiting for component...</p>
          )}
        </div>
      </div>
      {insight && (
        <div>
          <h2 className="font-semibold mb-2">Insights</h2>
          <pre className="bg-gray-100 p-2 text-xs overflow-auto">
            {JSON.stringify(insight, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
