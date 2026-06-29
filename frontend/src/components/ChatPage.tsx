import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { streamAsk, logout } from '../api/client';
import type { AskFilters, ChatMessage, Citation, User } from '../types';
import Sidebar from './Sidebar';
import ChatMessageView from './ChatMessageView';
import SourcePanel from './SourcePanel';
import SourcePreviewModal from './SourcePreviewModal';
import AdminDashboard from './AdminDashboard';

/** Strip <think>...</think> blocks from model output as a client-side safety net. */
function stripThinkBlocks(text: string): string {
  // Remove complete <think>...</think> blocks
  text = text.replace(/<think>[\s\S]*?<\/think>/gi, '');
  // If an opening tag exists without a closing tag, discard from that point
  const openIdx = text.toLowerCase().indexOf('<think>');
  if (openIdx !== -1) {
    text = text.slice(0, openIdx);
  }
  return text.trimStart();
}

interface Props {
  user: User;
  onLogout: () => void;
  apiOnline: boolean | null;
}

const SUGGESTIONS = [
  { title: 'Leave Policy', desc: 'What is the annual leave policy for employees?', q: 'What is the leave policy for employees?' },
  { title: 'Remote Work', desc: 'Can employees work remotely?', q: 'What is the remote work policy?' },
  { title: 'Password Rules', desc: 'Security compliance requirements', q: 'What are the password requirements?' },
  { title: 'Refund Policy', desc: 'Process and conditions for refunds', q: 'What is the refund policy?' },
];

export default function ChatPage({ user, onLogout, apiOnline }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [filters, setFilters] = useState<AskFilters>({});
  const [activeSources, setActiveSources] = useState<Citation[]>([]);
  const [previewChunkId, setPreviewChunkId] = useState<string | null>(null);
  const [showAdmin, setShowAdmin] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleLogout = () => {
    logout();
    onLogout();
  };

  const handleNewChat = () => {
    setMessages([]);
    setActiveSources([]);
    setSessionId(crypto.randomUUID());
    setStatusText('');
  };

  const sendMessage = async (text: string) => {
    const question = text.trim();
    if (!question || isLoading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
    };

    const assistantId = crypto.randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput('');
    setIsLoading(true);
    setStatusText('Searching knowledge base...');

    try {
      let fullAnswer = '';
      let sources: Citation[] = [];
      let confidence = 0;
      let rewrittenQuery = '';
      let retrievalTrace: Record<string, unknown> | undefined;
      let answerability = '';

      for await (const evt of streamAsk(question, sessionId, filters, user.token)) {
        switch (evt.type) {
          case 'query_rewritten':
            rewrittenQuery = String(evt.data.rewritten_query || '');
            setStatusText('Retrieving documents...');
            break;
          case 'semantic_search_done':
            setStatusText(`Found ${evt.data.count} semantic matches...`);
            break;
          case 'keyword_search_done':
            setStatusText(`Found ${evt.data.count} keyword matches...`);
            break;
          case 'rerank_done':
            setStatusText('Generating answer...');
            break;
          case 'generation_token': {
            const token = stripThinkBlocks(String(evt.data.token || ''));
            if (token) {
              fullAnswer += token;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: fullAnswer } : m,
                ),
              );
            }
            break;
          }
          case 'final_sources': {
            const data = evt.data;
            // Always use the server-finalized clean answer — overrides any streamed content
            const cleanAnswer = stripThinkBlocks(String(data.answer || fullAnswer));
            fullAnswer = cleanAnswer;
            sources = (data.sources as Citation[]) || [];
            confidence = Number(data.confidence || 0);
            answerability = String(data.answerability || '');
            retrievalTrace = data.retrieval_trace as Record<string, unknown>;
            rewrittenQuery = String(data.rewritten_query || rewrittenQuery);
            setActiveSources(sources);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content: cleanAnswer,
                      sources,
                      confidence,
                      rewrittenQuery,
                      retrievalTrace,
                      answerability,
                      isStreaming: false,
                    }
                  : m,
              ),
            );
            break;
          }
          case 'error':
            throw new Error(String(evt.data.message));
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Something went wrong';
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `Error: ${msg}`, isStreaming: false }
            : m,
        ),
      );
    } finally {
      setIsLoading(false);
      setStatusText('');
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="app-layout">
      <Sidebar
        user={user}
        filters={filters}
        onFiltersChange={setFilters}
        onNewChat={handleNewChat}
        onLogout={handleLogout}
        onShowAdmin={() => setShowAdmin(!showAdmin)}
        showAdmin={showAdmin}
      />

      <div className="main-content">
        <header className="app-header">
          <div className="header-title">
            {showAdmin ? 'Admin Dashboard' : 'Enterprise Knowledge Assistant'}
          </div>
          <div className="header-actions">
            {apiOnline === null ? (
              <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className="status-dot connecting" />
                Connecting…
              </span>
            ) : (
              <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className={`status-dot ${apiOnline ? 'online' : 'offline'}`} />
                {apiOnline ? 'Connected' : 'Offline'}
              </span>
            )}
          </div>
        </header>

        {showAdmin ? (
          <AdminDashboard user={user} />
        ) : (
          <div className="chat-area">
            <div className="chat-main">
              <div className="messages-container">
                {messages.length === 0 ? (
                  <div className="welcome-screen">
                    <div className="welcome-icon">🧠</div>
                    <h1 className="welcome-title">How can I <span className="gradient-text">help you</span> today?</h1>
                    <p className="welcome-subtitle">
                      Ask questions about company policies, procedures, and documentation.
                      Answers are grounded in your knowledge base with source citations.
                    </p>
                    <div className="suggestion-grid">
                      {SUGGESTIONS.map((s) => (
                        <button
                          key={s.q}
                          className="suggestion-card"
                          onClick={() => sendMessage(s.q)}
                        >
                          <div className="suggestion-card-title">{s.title}</div>
                          <div className="suggestion-card-desc">{s.desc}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((msg, index) => (
                    <ChatMessageView
                      key={msg.id}
                      message={msg}
                      previousMessage={index > 0 ? messages[index - 1] : undefined}
                      token={user.token}
                      sessionId={sessionId}
                      onSourceClick={setPreviewChunkId}
                    />
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>

              <div className="input-area">
                <div className="input-wrapper">
                  <textarea
                    ref={inputRef}
                    className="chat-input"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask a question about your documents..."
                    rows={1}
                    disabled={isLoading}
                  />
                  <button
                    className="send-btn"
                    onClick={() => sendMessage(input)}
                    disabled={isLoading || !input.trim()}
                  >
                    {isLoading ? <span className="spinner" /> : '➤'}
                  </button>
                </div>
                <div className="status-bar">{statusText}</div>
              </div>
            </div>

            {activeSources.length > 0 && (
              <SourcePanel
                sources={activeSources}
                onSourceClick={setPreviewChunkId}
                onClose={() => setActiveSources([])}
              />
            )}
          </div>
        )}
      </div>

      {previewChunkId && (
        <SourcePreviewModal
          chunkId={previewChunkId}
          token={user.token}
          onClose={() => setPreviewChunkId(null)}
        />
      )}
    </div>
  );
}
