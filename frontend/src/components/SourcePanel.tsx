import type { Citation } from '../types';

interface Props {
  sources: Citation[];
  onSourceClick: (chunkId: string) => void;
  onClose: () => void;
}

export default function SourcePanel({ sources, onSourceClick, onClose }: Props) {
  if (!sources.length) return null;

  return (
    <aside className="source-panel">
      <div className="source-panel-header">
        <span className="source-panel-title">Sources ({sources.length})</span>
        <button className="btn-ghost" onClick={onClose}>✕</button>
      </div>
      <div className="source-list">
        {sources.map((source) => (
          <div
            key={source.chunk_id}
            className="source-card animate-fade-in"
            onClick={() => onSourceClick(source.chunk_id)}
          >
            <div className="source-card-header">
              <span className="source-doc-name">
                [{source.citation_id}] {source.document}
              </span>
              <span className="source-score">{(source.score * 100).toFixed(0)}%</span>
            </div>
            {source.section_title && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                {source.section_title}
              </div>
            )}
            <div className="source-snippet">{source.snippet}</div>
            <div className="source-meta">
              {source.page && <span className="badge badge-accent">Page {source.page}</span>}
              {source.content_type !== 'text' && (
                <span className="badge badge-warning">{source.content_type}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
