import type { AskFilters, Citation, DashboardMetrics, IngestJob, SourcePreview, User } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

function authHeaders(token?: string): HeadersInit {
  const t = token || localStorage.getItem('eka_token');
  return {
    'Content-Type': 'application/json',
    ...(t ? { Authorization: `Bearer ${t}` } : {}),
  };
}

export async function login(email: string, password: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Login failed');
  }
  const data = await res.json();
  const user: User = {
    email: data.email,
    role: data.role,
    department: data.department,
    token: data.access_token,
  };
  localStorage.setItem('eka_token', user.token);
  localStorage.setItem('eka_user', JSON.stringify(user));
  return user;
}

export function logout(): void {
  localStorage.removeItem('eka_token');
  localStorage.removeItem('eka_user');
}

export function getStoredUser(): User | null {
  const raw = localStorage.getItem('eka_user');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

/** Retry health check until backend is ready (handles slow startup). */
export async function checkHealthWithRetry(maxAttempts = 20, intervalMs = 1000): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    if (await checkHealth()) return true;
    if (i < maxAttempts - 1) {
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }
  return false;
}

export async function* streamAsk(
  question: string,
  sessionId: string,
  filters: AskFilters,
  token: string,
): AsyncGenerator<{ type: string; data: Record<string, unknown> }> {
  const res = await fetch(`${API_BASE}/ask/stream`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({
      question,
      session_id: sessionId,
      include_debug: false,
      filters: Object.keys(filters).length ? filters : undefined,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const evt = JSON.parse(line);
        yield { type: evt.event, data: evt.data };
      } catch {
        /* skip malformed */
      }
    }
  }
}

export async function submitFeedback(
  payload: {
    session_id: string;
    message_id: string;
    question: string;
    answer: string;
    rating: number;
    category?: string;
    comment?: string;
  },
  token: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to submit feedback');
}

export async function getSourcePreview(chunkId: string, token: string): Promise<SourcePreview> {
  const res = await fetch(`${API_BASE}/sources/${chunkId}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Source not found');
  return res.json();
}

export async function getDashboard(token: string): Promise<DashboardMetrics> {
  const res = await fetch(`${API_BASE}/admin/dashboard`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to load dashboard');
  return res.json();
}

export async function uploadDocument(file: File, token: string): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
}

export async function ingestDocuments(token: string): Promise<{ run_id: string }> {
  const res = await fetch(`${API_BASE}/ingest/directory`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error('Ingest failed');
  return res.json();
}

export async function getIngestJob(jobId: string, token: string): Promise<IngestJob> {
  const res = await fetch(`${API_BASE}/ingest/jobs/${jobId}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Job not found');
  return res.json();
}

export async function getRetrievalStats(token: string): Promise<Record<string, unknown>[]> {
  const res = await fetch(`${API_BASE}/admin/retrieval-stats?limit=20`, {
    headers: authHeaders(token),
  });
  if (!res.ok) return [];
  return res.json();
}

export function exportFeedbackUrl(): string {
  return `${API_BASE}/admin/feedback/export`;
}

export type { Citation };
