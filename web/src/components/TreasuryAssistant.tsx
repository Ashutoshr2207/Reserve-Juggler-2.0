import React, { useEffect, useRef, useState } from 'react';
import { useHashRoute } from '../hooks/useHashRoute';
import { useAuth } from '../hooks/useAuth';
import { api, ApiError } from '../utils/api';
import SpecularButton from './SpecularButton';
import './TreasuryAssistant.css';

type Message = { role: 'user' | 'assistant'; content: string };
type Answer = {
  reply: string;
  context: { available: boolean; revision: number | null; as_of: string | null };
};
const suggestions = [
  'How is the required reserve calculated?',
  'Why is my sweep blocked?',
  'How reliable is this forecast?',
  'How do I test a withdrawal spike?'
];

export const TreasuryAssistant: React.FC = () => {
  const { route } = useHashRoute();
  const { authenticated } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [failed, setFailed] = useState('');
  const [context, setContext] = useState<Answer['context'] | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inFlight = useRef(false);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (open) inputRef.current?.focus();
    else if (wasOpen.current) launcherRef.current?.focus();
    wasOpen.current = open;
  }, [open]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'nearest' }); }, [messages, pending, error]);

  const close = () => { setOpen(false); launcherRef.current?.focus(); };
  const send = async (text: string, retry = false) => {
    const question = text.trim();
    if (!question || question.length > 2000 || inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError('');
    setFailed('');
    const history = retry ? messages.slice(0, -1) : messages;
    if (!retry) setMessages([...messages, { role: 'user', content: question }]);
    setInput('');
    try {
      const result = await api<Answer>('assistant', {
        message: question, history: history.slice(-12), section: route
      });
      if (typeof result.reply !== 'string' || !result.reply.trim()) {
        throw new Error('No answer was received. Please retry.');
      }
      setMessages([...history, { role: 'user', content: question }, { role: 'assistant', content: result.reply }]);
      setContext(result.context);
    } catch (err) {
      let detail = 'Treasury Assistant is unavailable. Please retry.';
      if (err instanceof ApiError && err.responseBody) {
        try {
          const body = JSON.parse(err.responseBody);
          if (typeof body.error === 'string') detail = body.error;
        } catch { /* Keep a safe, readable error for malformed responses. */ }
      } else if (err instanceof ApiError && err.isNetworkError) {
        detail = 'Cannot connect to the treasury server. Check the connection and retry.';
      }
      setError(detail);
      setFailed(question);
    } finally {
      inFlight.current = false;
      setPending(false);
      inputRef.current?.focus();
    }
  };

  const restart = () => {
    setMessages([]); setError(''); setFailed(''); setContext(null); setInput('');
    inputRef.current?.focus();
  };

  if (
    !authenticated ||
    route === 'home' ||
    route === 'method' ||
    route === 'login' ||
    route === 'register'
  ) {
    return null;
  }

  return (
    <div className="treasury-assistant">
      {!open && <button ref={launcherRef} className="assistant-launcher" onClick={() => setOpen(true)}
        aria-expanded={open} aria-controls="treasury-assistant-panel">
        <span aria-hidden="true">₹</span> Ask Treasury Assistant
      </button>}
      {open && <section id="treasury-assistant-panel" className="assistant-panel"
        role="dialog" aria-modal="false" aria-labelledby="assistant-title"
        onKeyDown={(e) => { if (e.key === 'Escape') close(); }}>
        <header className="assistant-header">
          <div><h2 id="assistant-title">Treasury Assistant</h2><p>Reserve Juggler · Read-only help</p></div>
          <button type="button" onClick={close} aria-label="Close Treasury Assistant">×</button>
        </header>
        <div className="assistant-toolbar">
          <span>Simulation guidance</span>
          <button type="button" onClick={restart} disabled={pending}>New conversation</button>
        </div>
        <div className="assistant-messages" role="log" aria-label="Treasury conversation" aria-live="polite" aria-relevant="additions text">
          <div className="assistant-message assistant-message-assistant">
            <p>Hello! I can explain reserves, forecasts and sweep decisions, or guide you through this workspace. I cannot change treasury data or execute investments.</p>
          </div>
          {messages.length === 0 && <div className="assistant-suggestions">
            {suggestions.map((q) => <button key={q} onClick={() => void send(q)}>{q}</button>)}
          </div>}
          {messages.map((m, i) => <div key={i} className={`assistant-message assistant-message-${m.role}`}>
            <span className="assistant-speaker">{m.role === 'user' ? 'You' : 'Treasury Assistant'}</span>
            <p>{m.content}</p>
          </div>)}
          {pending && <p className="assistant-loading" role="status">Preparing an explanation…</p>}
          {error && <div className="assistant-error" role="alert">
            <p>{error}</p><p>Your treasury workspace is unaffected.</p>
            <button onClick={() => void send(failed, true)}>Retry answer</button>
          </div>}
          <div ref={endRef} />
        </div>
        {context && <p className="assistant-context">{context.available
          ? `State at ${context.as_of} · revision ${context.revision}. Refresh your question after changes.`
          : 'Current state unavailable. Answers provide general product guidance.'}</p>}
        <form className="assistant-compose" onSubmit={(e) => { e.preventDefault(); void send(input); }}>
          <label htmlFor="assistant-input">Ask about Reserve Juggler</label>
          <textarea ref={inputRef} id="assistant-input" value={input} maxLength={2000} rows={2}
            placeholder="Ask about your treasury workspace…" disabled={pending || !!failed}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault(); void send(input);
              }
            }} />
          <div><small>Do not share API keys or customer details.</small>
            <SpecularButton
              type="submit"
              size="sm"
              radius={18}
              tint="#ffffff"
              tintOpacity={0.04}
              textColor="#f5f5f5"
              lineColor="#ffffff"
              baseColor="#525252"
              intensity={1}
              idleIntensity={0.35}
              shineSize={10}
              shineFade={34}
              thickness={1.2}
              glow={1}
              followMouse
              proximity={250}
              disabled={pending || !!failed || !input.trim()}
            >
              Send
            </SpecularButton></div>
          {failed && <button type="button" className="assistant-dismiss-error" onClick={() => {
            setMessages(messages.slice(0, -1)); setInput(failed); setFailed(''); setError('');
          }}>Edit question</button>}
        </form>
      </section>}
    </div>
  );
};
