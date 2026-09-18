import { useState, useEffect, useRef } from 'react';
import { Send, Activity, RotateCcw, Zap, Database, KeyRound, Radio } from 'lucide-react';
import './index.css';

const API_BASE = "http://127.0.0.1:8000/api";

const INCIDENTS = [
  {
    id: 'bank_node_timeout',
    title: 'Bank Node Timeout',
    sub: 'Axis UPI rail 504s',
    Icon: Zap,
  },
  {
    id: 'bad_deployment',
    title: 'Bad Deployment',
    sub: 'Settlement DB spin',
    Icon: Database,
  },
  {
    id: 'auth_token_expiry',
    title: 'Auth Cascade',
    sub: 'JWT expiry → 401s',
    Icon: KeyRound,
  },
];

function formatMessage(text) {
  if (!text) return null;
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: 'agent',
      content:
        'OpsMate online. I am your Paytm SRE teammate — ask for a health check, or inject an incident from the left rail to start a demo.',
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch(`${API_BASE}/metrics`);
        const data = await res.json();
        setMetrics(data);
      } catch {
        /* backend may be down during UI work */
      }
    };
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 2000);
    return () => clearInterval(interval);
  }, []);

  const sendToAgent = async (chatHistory) => {
    setIsTyping(true);
    try {
      const payload = {
        messages: chatHistory,
        session_id: 'demo_session',
      };

      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok || !response.body) {
        const errText = await response.text().catch(() => '');
        throw new Error(errText || `Backend returned HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let agentMessage = '';
      let buffer = '';
      let started = false;

      const pushAgent = (content) => {
        const isFirst = !started;
        if (!started) started = true;

        setMessages((prev) => {
          if (isFirst) {
            return [...prev, { role: 'agent', content }];
          }
          const next = [...prev];
          next[next.length - 1] = { ...next[next.length - 1], content };
          return next;
        });
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const chunkStr = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);

          for (const line of chunkStr.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.substring(6);
            if (dataStr === '[DONE]') break;
            try {
              const data = JSON.parse(dataStr);
              if (data.text) {
                agentMessage += data.text;
                pushAgent(agentMessage);
              } else if (data.error) {
                agentMessage += agentMessage
                  ? `\n\n**Backend error:** ${data.error}`
                  : `**OpsMate error:** ${data.error}`;
                pushAgent(agentMessage);
              }
            } catch {
              /* ignore partial JSON */
            }
          }
          boundary = buffer.indexOf('\n\n');
        }
      }

      if (!agentMessage.trim()) {
        pushAgent(
          'OpsMate returned an empty reply. Confirm `python server.py` is still running in another terminal and watch that window for Gemini/Vertex errors.',
        );
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'agent',
          content: `Connection to OpsMate failed. Start the backend with \`python server.py\` (port 8000). ${err?.message ? `(${err.message})` : ''}`,
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    const newHistory = [...messages, userMessage];
    setMessages(newHistory);
    setInput('');
    await sendToAgent(newHistory);
  };

  const triggerChaos = async (scenario) => {
    await fetch(`${API_BASE}/chaos/${scenario}`, { method: 'POST' });
    
    const alertMsg = {
      role: 'agent',
      content: `**ALERT:** Incident "${scenario}" injected. Metrics will degrade shortly. Investigating automatically...`,
    };
    const autoUserMsg = { role: 'user', content: 'Investigate' };
    
    const newHistory = [...messages, alertMsg, autoUserMsg];
    setMessages(newHistory);
    
    await sendToAgent(newHistory);
  };

  const resolveChaos = async () => {
    await fetch(`${API_BASE}/resolve`, { method: 'POST' });
    setMessages((prev) => [
      ...prev,
      {
        role: 'agent',
        content: '**SYSTEM RESET:** Infrastructure restored to healthy. Session memory cleared.',
      },
    ]);
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand-row">
            <div className="paytm-mark" aria-hidden>
              P
            </div>
            <div className="brand-text">
              <span className="product">OpsMate</span>
              <span className="org">Paytm · SRE</span>
            </div>
          </div>
          <div className="live-pill">
            <span className="dot" />
            War room live
          </div>
        </div>

        <div className="sidebar-section">
          <div className="section-label">Inject incident</div>
          <div className="chaos-list">
            {INCIDENTS.map(({ id, title, sub, Icon }) => (
              <button key={id} type="button" className="chaos-btn" onClick={() => triggerChaos(id)}>
                <Icon className="chaos-icon" size={16} strokeWidth={2.25} />
                <span className="chaos-copy">
                  <span className="chaos-title">{title}</span>
                  <span className="chaos-sub">{sub}</span>
                </span>
              </button>
            ))}
            <button type="button" className="chaos-btn resolve" onClick={resolveChaos}>
              <RotateCcw className="chaos-icon" size={16} strokeWidth={2.25} />
              <span className="chaos-copy">
                <span className="chaos-title">Reset infrastructure</span>
                <span className="chaos-sub">Clear chaos + agent memory</span>
              </span>
            </button>
          </div>
        </div>

        <div className="sidebar-section health-widgets">
          <div className="section-label">Live services</div>
          {metrics?.services ? (
            Object.entries(metrics.services).map(([key, svc], idx) => {
              const statusClass =
                svc.status === 'healthy' ? 'healthy' : svc.status === 'down' ? 'critical' : 'warning';
              const statusLabel =
                svc.status === 'healthy' ? 'Healthy' : svc.status === 'down' ? 'Down' : 'Degraded';
              return (
                <div key={key} className="metric-row" style={{ animationDelay: `${idx * 40}ms` }}>
                  <div className="metric-top">
                    <span className="metric-name">{svc.display_name}</span>
                    <span className={`status-badge ${statusClass}`}>{statusLabel}</span>
                  </div>
                  <div className="metric-stats">
                    <div className="stat">
                      <span className="stat-label">Err rate</span>
                      <span className={`stat-value ${svc.error_rate_pct > 5 ? 'bad' : ''}`}>
                        {svc.error_rate_pct.toFixed(1)}%
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">p99</span>
                      <span className={`stat-value ${svc.latency_p99_ms > 200 ? 'bad' : ''}`}>
                        {svc.latency_p99_ms.toFixed(0)}ms
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <p style={{ fontSize: 12, color: 'var(--text-on-navy-muted)' }}>Waiting for metrics…</p>
          )}
        </div>
      </aside>

      <main className="main-content">
        <header className="chat-header">
          <div className="channel-meta">
            <div className="channel-icon">
              <Activity size={18} />
            </div>
            <div className="channel-copy">
              <h2>#incident-war-room</h2>
              <p>Paytm payments · autonomous SRE teammate</p>
            </div>
          </div>
          <div className="header-chip">
            <span />
            Gemini · Vertex
          </div>
        </header>

        <div className="chat-history">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message-bubble ${msg.role}`}>
              <div className={`avatar ${msg.role}`}>{msg.role === 'agent' ? 'OM' : 'YOU'}</div>
              <div className="message-stack">
                <div className="message-meta">{msg.role === 'agent' ? 'OpsMate' : 'Engineer'}</div>
                <div className="message-content">{formatMessage(msg.content)}</div>
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="message-bubble agent">
              <div className="avatar agent">OM</div>
              <div className="message-stack">
                <div className="message-meta">OpsMate</div>
                <div className="message-content">
                  <div className="typing-row" aria-label="OpsMate is thinking">
                    <i />
                    <i />
                    <i />
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="chat-input-container">
          <form className="chat-input-wrapper" onSubmit={handleSend}>
            <Radio size={16} color="var(--paytm-cyan)" strokeWidth={2.25} aria-hidden />
            <input
              type="text"
              className="chat-input"
              placeholder="Ask OpsMate — e.g. investigate the spike in 5xx errors…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isTyping}
            />
            <button type="submit" className="send-btn" disabled={!input.trim() || isTyping} aria-label="Send">
              <Send size={18} />
            </button>
          </form>
          <p className="input-hint">Inject an incident on the left, then ask OpsMate to investigate.</p>
        </div>
      </main>
    </div>
  );
}
