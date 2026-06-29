import { useEffect, useState } from 'react';
import { getSourcePreview } from '../api/client';
import type { SourcePreview } from '../types';

interface Props {
  chunkId: string;
  token: string;
  onClose: () => void;
}

export default function SourcePreviewModal({ chunkId, token, onClose }: Props) {
  const [source, setSource] = useState<SourcePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    getSourcePreview(chunkId, token)
      .then(setSource)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [chunkId, token]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-title">{source?.document || 'Source Preview'}</div>
            {source && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                {source.page ? `Page ${source.page}` : ''}
                {source.section_title ? ` · ${source.section_title}` : ''}
                {source.department ? ` · ${source.department}` : ''}
              </div>
            )}
          </div>
          <button className="btn-ghost" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {loading && <div className="spinner" />}
          {error && <div className="login-error">{error}</div>}
          {source && (
            <>
              <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
                <span className="badge badge-accent">{source.content_type}</span>
                {source.extraction_method && (
                  <span className="badge badge-accent">{source.extraction_method}</span>
                )}
                {source.policy_version && (
                  <span className="badge badge-accent">v{source.policy_version}</span>
                )}
              </div>
              <div className="modal-text">{source.text}</div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
