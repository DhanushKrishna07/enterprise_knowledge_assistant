import type { ChatMessage, Citation } from '../types';
import { useState } from 'react';
import { submitFeedback } from '../api/client';
import FeedbackModal from './FeedbackModal';

interface Props {
  message: ChatMessage;
  previousMessage?: ChatMessage;
  token: string;
  sessionId: string;
  onSourceClick: (chunkId: string) => void;
}

export default function ChatMessageView({ message, previousMessage, token, sessionId, onSourceClick }: Props) {
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  const questionText = previousMessage?.role === 'user' ? previousMessage.content : '';

  const handleThumb = async (rating: number) => {
    if (message.role !== 'assistant' || message.isStreaming) return;
    if (rating === 1) {
      setFeedback('up');
      showToast('Thanks for your feedback! 👍');
      await submitFeedback({
        session_id: sessionId,
        message_id: message.id,
        question: questionText,
        answer: message.content,
        rating: 1,
      }, token);
    } else {
      setShowFeedbackModal(true);
    }
  };

  const handleFeedbackSubmit = async (category: string, comment: string) => {
    setFeedback('down');
    showToast(`Feedback submitted. We'll use this to improve. 🙏`);
    await submitFeedback({
      session_id: sessionId,
      message_id: message.id,
      question: questionText,
      answer: message.content,
      rating: -1,
      category,
      comment,
    }, token);
    setShowFeedbackModal(false);
  };

  return (
    <div className={`message ${message.role} animate-fade-in`}>
      <div className="message-avatar">
        {message.role === 'user' ? '👤' : '🤖'}
      </div>
      <div className="message-body">
        <div className="message-bubble">
          {message.isStreaming && !message.content ? (
            <div className="typing-dots"><span /><span /><span /></div>
          ) : (
            message.content
          )}
        </div>

        {message.role === 'assistant' && !message.isStreaming && (
          <div className="message-meta">
            {message.confidence !== undefined && (
              <div className="confidence-bar">
                <span>Confidence</span>
                <div className="confidence-track">
                  <div className="confidence-fill" style={{ width: `${message.confidence * 100}%` }} />
                </div>
                <span>{Math.round(message.confidence * 100)}%</span>
              </div>
            )}
            {message.answerability && (
              <span className={`badge ${message.answerability === 'not_found' ? 'badge-warning' : 'badge-success'}`}>
                {message.answerability.replace('_', ' ')}
              </span>
            )}
            <div className="message-actions">
              <button
                className={`feedback-btn ${feedback === 'up' ? 'active-up' : ''}`}
                onClick={() => handleThumb(1)}
                title="Helpful"
              >
                👍
              </button>
              <button
                className={`feedback-btn ${feedback === 'down' ? 'active-down' : ''}`}
                onClick={() => handleThumb(-1)}
                title="Not helpful"
              >
                👎
              </button>
            </div>

            {/* Toast notification */}
            {toast && (
              <div className="feedback-toast">{toast}</div>
            )}
          </div>
        )}

        {message.sources && message.sources.length > 0 && !message.isStreaming && (
          <div className="message-sources">
            {message.sources.map((s: Citation) => {
              const name = s.document.split(/[/\\]/).pop() || s.document;
              return (
                <button
                  key={s.chunk_id}
                  type="button"
                  className="source-chip"
                  onClick={() => onSourceClick(s.chunk_id)}
                  title={s.snippet}
                >
                  <span className="source-chip-icon">📄</span>
                  <span className="source-chip-name">{name}</span>
                  {s.page != null && (
                    <span className="source-chip-page">p.{s.page}</span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {showFeedbackModal && (
        <FeedbackModal
          onSubmit={handleFeedbackSubmit}
          onClose={() => setShowFeedbackModal(false)}
        />
      )}
    </div>
  );
}
