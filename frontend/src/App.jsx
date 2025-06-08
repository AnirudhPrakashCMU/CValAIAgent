import React, { useEffect, useRef, useState } from 'react';
import ReconnectingWebSocket from 'reconnecting-websocket';
import DOMPurify from 'dompurify';
import StripeGradient from './components/StripeGradient';
import { STRIPE_GRADIENT_SNIPPET } from './stripeCode';

const HTTP_URL = import.meta.env.VITE_ORCHESTRATOR_HTTP_URL || 'http://localhost:8000';
const STT_HTTP_URL = import.meta.env.VITE_STT_HTTP_URL || 'http://localhost:8001';
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
  const [intents, setIntents] = useState([]);
  const [insight, setInsight] = useState(null);
  const [showGradient, setShowGradient] = useState(false);
  const [showSnippet, setShowSnippet] = useState(false);
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
        else if (msg.kind === 'component') {
          setComponentCode(msg.jsx);
          console.log('Component code:', msg.jsx);
        }
        else if (msg.kind === 'intent') {
          setIntents((i) => [...i, msg]);
          console.log('Intent:', msg);
        }
        else if (msg.kind === 'insight') setInsight(msg);
        else if (msg.kind === 'error') console.error(msg.message);
      } catch (err) {
        /* ignore malformed messages */
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
      sendForTranscription(blob);
      setShowGradient(true);
      setShowSnippet(true);
      console.log('Stripe snippet:', STRIPE_GRADIENT_SNIPPET);
    }
  }

  async function sendForTranscription(blob) {
    const form = new FormData();
    form.append('file', blob, 'recording.webm');
    try {
      const res = await fetch(`${STT_HTTP_URL}/v1/transcribe`, { method: 'POST', body: form });
      const data = await res.json();
      if (data.text) {
        setTranscripts((t) => [...t, data.text]);
      } else {
        /* response had no text */
      }
    } catch (err) {
      console.error(`Transcription failed: ${err}`);
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
      <div className="grid grid-cols-3 gap-4">
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
        <div>
          <h2 className="font-semibold mb-2">Design Intents</h2>
          <ul className="text-sm max-h-64 overflow-auto list-disc pl-5 space-y-1">
            {intents.map((it, i) => (
              <li key={i}>{it.component} - {it.styles.join(', ')}</li>
            ))}
          </ul>
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
      {componentCode && (
        <div>
          <h2 className="font-semibold mt-4 mb-2">Component Preview</h2>
          <div
            className="border p-4"
            dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(componentCode) }}
          />
        </div>
      )}
      {showSnippet && (
        <div className="mt-4">
          <h2 className="font-semibold mb-2">Stripe Gradient Code</h2>
          <pre className="bg-gray-100 p-2 text-xs overflow-auto">
            {STRIPE_GRADIENT_SNIPPET}
          </pre>
        </div>
      )}
      <StripeGradient show={showGradient} />
    </div>
  );
}
