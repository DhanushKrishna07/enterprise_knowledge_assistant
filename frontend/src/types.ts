export interface User {
  email: string;
  role: string;
  department: string;
  token: string;
}

export interface Citation {
  citation_id: number;
  document: string;
  page: number | null;
  chunk_id: string;
  snippet: string;
  score: number;
  content_type: string;
  extraction_method: string;
  section_title: string;
}

export interface SourcePreview {
  chunk_id: string;
  document: string;
  page: number | null;
  text: string;
  content_type: string;
  extraction_method: string;
  section_title: string;
  department: string;
  document_id: string;
  tags: string;
  policy_version: string;
  uploaded_at: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Citation[];
  confidence?: number;
  rewrittenQuery?: string;
  retrievalTrace?: Record<string, unknown>;
  latencies?: Record<string, number>;
  answerability?: string;
  isStreaming?: boolean;
}

export interface AskFilters {
  department?: string;
  document_type?: string;
  author?: string;
  tags?: string[];
  policy_version?: string;
  uploaded_after?: string;
  content_types?: string[];
}

export interface DashboardMetrics {
  index: {
    chroma_collection: string;
    vector_chunks: number;
    bm25_chunks: number;
    embedding_model: string;
  };
  feedback: { total: number; positive: number; negative: number };
  ingestion: { runs: number; total_chunks: number };
  performance: {
    total_requests: number;
    avg_latency_ms: number;
    answerability_ratio: number;
  };
  config: {
    llm_model: string;
    reranker_model: string;
    top_k_semantic: number;
    top_k_context: number;
  };
}

export interface IngestJob {
  job_id: string;
  run_id: string;
  filename: string;
  status: string;
  stage: string;
  progress: number;
  chunks_added: number;
  error: string;
}

export type StreamEvent =
  | { event: 'retrieval_started'; data: { session_id: string } }
  | { event: 'query_rewritten'; data: { rewritten_query: string } }
  | { event: 'semantic_search_done'; data: { count: number } }
  | { event: 'keyword_search_done'; data: { count: number } }
  | { event: 'rerank_done'; data: { count: number; latency_ms: number } }
  | { event: 'generation_token'; data: { token: string } }
  | { event: 'final_sources'; data: Record<string, unknown> }
  | { event: 'done'; data: Record<string, unknown> }
  | { event: 'error'; data: { message: string } };
