import { useEffect, useState, useRef, useCallback } from 'react';
import {
  getDashboard,
  getRetrievalStats,
  uploadDocument,
  ingestDocuments,
  getIngestJob,
} from '../api/client';
import type { DashboardMetrics, User } from '../types';

interface Props {
  user: User;
}

export default function AdminDashboard({ user }: Props) {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [traces, setTraces] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadStatus, setUploadStatus] = useState('');
  const [jobProgress, setJobProgress] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, stats] = await Promise.all([
        getDashboard(user.token),
        getRetrievalStats(user.token),
      ]);
      setMetrics(dash);
      setTraces(stats);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [user.token]);

  useEffect(() => { loadData(); }, [loadData]);

  const pollJob = async (jobId: string) => {
    const poll = async () => {
      const job = await getIngestJob(jobId, user.token);
      setJobProgress(job.progress * 100);
      setUploadStatus(`${job.stage} — ${job.status}`);
      if (job.status === 'completed' || job.status === 'failed') {
        setUploadStatus(job.status === 'completed'
          ? `✓ Ingested ${job.chunks_added} chunks`
          : `✗ ${job.error || 'Failed'}`);
        loadData();
        return;
      }
      setTimeout(poll, 1500);
    };
    poll();
  };

  const handleUpload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploadStatus('Uploading...');
    try {
      const result = await uploadDocument(files[0], user.token);
      setUploadStatus('Processing...');
      pollJob(result.job_id);
    } catch (e) {
      setUploadStatus(`Error: ${e instanceof Error ? e.message : 'Upload failed'}`);
    }
  };

  const handleExportFeedback = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE || ''}/admin/feedback/export`, {
        headers: { Authorization: `Bearer ${user.token}` },
      });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'feedback_export.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setUploadStatus(`Export error: ${e instanceof Error ? e.message : 'Failed'}`);
    }
  };

  const handleIngestDocuments = async () => {
    setUploadStatus('Indexing documents folder...');
    try {
      await ingestDocuments(user.token);
      setUploadStatus('✓ Documents queued for indexing');
      setTimeout(loadData, 3000);
    } catch (e) {
      setUploadStatus(`Error: ${e instanceof Error ? e.message : 'Failed'}`);
    }
  };

  if (loading && !metrics) {
    return (
      <div className="admin-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="spinner" />
      </div>
    );
  }

  return (
    <div className="admin-panel animate-fade-in">
      <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>Admin Dashboard</h2>

      {metrics && (
        <div className="admin-grid">
          <div className="metric-card">
            <div className="metric-label">Vector Chunks</div>
            <div className="metric-value">{metrics.index.vector_chunks.toLocaleString()}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">BM25 Chunks</div>
            <div className="metric-value">{metrics.index.bm25_chunks.toLocaleString()}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Total Requests</div>
            <div className="metric-value">{metrics.performance.total_requests}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Avg Latency</div>
            <div className="metric-value">{Math.round(metrics.performance.avg_latency_ms)}ms</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Answer Rate</div>
            <div className="metric-value">{(metrics.performance.answerability_ratio * 100).toFixed(0)}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Feedback</div>
            <div className="metric-value">
              👍 {metrics.feedback.positive} / 👎 {metrics.feedback.negative}
            </div>
          </div>
        </div>
      )}

      <div className="admin-section">
        <div className="admin-section-title">Document Ingestion</div>
        <div
          className="upload-zone"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('drag-over'); }}
          onDragLeave={(e) => e.currentTarget.classList.remove('drag-over')}
          onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove('drag-over'); handleUpload(e.dataTransfer.files); }}
        >
          <div style={{ fontSize: 32, marginBottom: 8 }}>📄</div>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Drop files here or click to upload</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>PDF, DOCX, TXT, MD, CSV</div>
          <input ref={fileRef} type="file" hidden accept=".pdf,.docx,.doc,.txt,.md,.csv" onChange={(e) => handleUpload(e.target.files)} />
        </div>
        {jobProgress > 0 && jobProgress < 100 && (
          <div className="upload-progress">
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${jobProgress}%` }} />
            </div>
          </div>
        )}
        {uploadStatus && (
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>{uploadStatus}</div>
        )}
        <div style={{ display: 'flex', gap: 12 }}>
          <button className="btn btn-secondary" onClick={handleIngestDocuments}>Re-index Documents</button>
          <button className="btn btn-secondary" onClick={handleExportFeedback}>Export Feedback CSV</button>
          <button className="btn btn-secondary" onClick={loadData}>Refresh</button>
        </div>
      </div>

      {metrics && (
        <div className="admin-section">
          <div className="admin-section-title">System Configuration</div>
          <div className="card" style={{ fontSize: 13, fontFamily: 'var(--font-mono)' }}>
            <div>LLM: {metrics.config.llm_model}</div>
            <div>Embedding: {metrics.index.embedding_model}</div>
            <div>Reranker: {metrics.config.reranker_model}</div>
            <div>Top-K Semantic: {metrics.config.top_k_semantic} · Context: {metrics.config.top_k_context}</div>
          </div>
        </div>
      )}

      {traces.length > 0 && (
        <div className="admin-section">
          <div className="admin-section-title">Recent Retrieval Traces</div>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table className="trace-table">
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Latency</th>
                  <th>Answerability</th>
                </tr>
              </thead>
              <tbody>
                {traces.slice(0, 10).map((t, i) => (
                  <tr key={i}>
                    <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {String(t.question || '')}
                    </td>
                    <td>{Math.round(Number(t.latency_ms || 0))}ms</td>
                    <td>
                      <span className="badge badge-accent">
                        {String((t.details as Record<string, unknown>)?.answerability || '—')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
