export type RetrievalMode = "hybrid" | "local" | "web";

export interface ExampleQuestion {
  label: string;
  question: string;
  retrieval_mode: RetrievalMode;
}

export interface Citation {
  source_id: string;
  source_type: "document" | "web";
  label: string;
  reference: string;
  metadata: Record<string, unknown>;
}

export interface ExecutionEvent {
  event_id: string;
  node: string;
  status: "started" | "succeeded" | "skipped" | "failed";
  branch: string | null;
  message: string;
  duration_ms: number | null;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface ComparisonSections {
  documented_approach: string | null;
  web_findings: string | null;
  comparison: string | null;
  engineering_implications: string | null;
  evidence_gap_message: string | null;
}

export interface UsageMetrics {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  estimated_cost_usd: number | null;
  cost_status: "estimated" | "unavailable";
  tavily_calls: number;
  llm_calls: number;
  local_chunk_count: number;
  web_result_count: number;
}

export interface AskResponse {
  request_id: string;
  question: string;
  retrieval_mode: RetrievalMode;
  comparison_status: string;
  answer_markdown: string;
  sections: ComparisonSections;
  citations: Citation[];
  local_sources: unknown[];
  web_sources: Array<{
    source_id: string;
    title: string;
    url: string;
    snippet: string;
    retrieved_at: string;
    published_at: string | null;
  }>;
  local_evidence_status: string;
  web_evidence_status: string;
  overall_evidence_status: string;
  execution_events: ExecutionEvent[];
  usage_metrics: UsageMetrics;
  langsmith_run_id: string | null;
  duration_ms: number;
  error: string | null;
}
