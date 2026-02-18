import { apiRequest } from "./api";

export type DimensionKey = "market" | "technical" | "distribution" | "founder_fit" | "timing";

export type EvaluationCreatePayload = {
  idea_description: string;
  target_customer?: string | null;
  problem_statement?: string | null;
  startup_type?: string | null;
  market_type?: string | null;
  web_enabled?: boolean;
};

export type EvaluationResultData = {
  evaluation_id: string;
  idea_description?: string | null;
  target_customer?: string | null;
  problem_statement?: string | null;
  startup_type?: string | null;
  market_type?: string | null;
  created_at?: string | null;
  idea_tags?: string[];
  idea_folder?: string | null;
  idea_categorization?: {
    type?: string;
    market?: string;
    target?: string;
    main_competitor?: string;
    trend_analysis?: string;
  } | null;
  status: "completed" | "partial" | "failed" | "pending";
  overall_score: number | null;
  verdict: "GO" | "CONDITIONAL" | "NO-GO" | null;
  low_confidence: boolean;
  dimension_scores?: Record<DimensionKey, number | null>;
  dimension_analyses?: Record<DimensionKey, { rationale?: string; improvement?: string }>;
  failed_dimensions?: DimensionKey[];
  parse_diagnostics?: string[];
  top_risks?: string[];
  idea_title?: string | null;
  idea_summary?: string | null;
  founder_fit_summary?: string | null;
  error_message?: string | null;
  web_enabled?: boolean;
  web_queries_used?: string[];
  evidence_mix?: {
    internal_sources?: number;
    web_sources?: number;
    total_sources?: number;
  };
  evidence_sources?: Array<{
    chunk_id?: string | null;
    title?: string;
    collection?: string;
    source_name?: string | null;
    source_url?: string | null;
    snippet?: string | null;
    retrieval_method?: string | null;
    supporting_dimensions?: string[];
    why_relevant?: string;
    doc_name?: string;
    source?: string;
  }>;
};

export type EvaluationEvent =
  | { type: "progress"; node: string; status: string }
  | { type: "result"; data: EvaluationResultData }
  | { type: "error"; message: string };

export type StoredEvaluation = {
  id: string;
  created_at: string;
  status: EvaluationResultData["status"];
  idea_input: EvaluationCreatePayload;
  result: EvaluationResultData;
};

export type EvaluationPdfExportPayload = {
  chart_image_data_url?: string;
  company_name?: string;
  company_tagline?: string;
  primary_color_hex?: string;
  custom_sections?: Array<{ title: string; content: string }>;
};

export type KeywordTrendPoint = {
  date: string;
  value: number;
};

export type KeywordTrendSeries = {
  keyword: string;
  volume: number;
  latest_volume?: number;
  growth_percent: number | null;
  points: KeywordTrendPoint[];
};

export type EvaluationKeywordTrends = {
  status?: "ok" | "no_keywords" | "no_trends_data" | "provider_error";
  error_code?: string;
  details?: string;
  keywords: string[];
  selected_keyword?: string | null;
  series: KeywordTrendSeries[];
  timeframe?: string;
  location?: string;
  source?: string;
  metric?: string;
  generated_at?: string;
  diagnostics?: {
    extracted_keywords_count?: number;
    provider_success_count?: number;
    provider_fail_count?: number;
    series_count?: number;
    point_count?: number;
    manual_override_used?: boolean;
  };
  error?: string;
};

const HISTORY_KEY = "evaluation_history_v1";

function getAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const injected = (window as unknown as { __CRAG_TOKEN__?: string }).__CRAG_TOKEN__;
  if (injected) {
    return injected;
  }
  return null;
}

export async function streamEvaluation(
  payload: EvaluationCreatePayload,
  onEvent: (event: EvaluationEvent) => void
): Promise<void> {
  const token = getAuthToken();
  if (!token) {
    throw new Error("Missing auth token.");
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiBase}/api/evaluations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Evaluation request failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const rawChunk of chunks) {
      const dataLines = rawChunk
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.replace(/^data:\s?/, ""));
      if (!dataLines.length) {
        continue;
      }

      const mergedData = dataLines.join("\n");
      try {
        const parsed = JSON.parse(mergedData) as EvaluationEvent;
        onEvent(parsed);
      } catch {
        onEvent({ type: "error", message: "Failed to parse streaming event." });
      }
    }
  }
}

export function setRuntimeToken(token: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  (window as unknown as { __CRAG_TOKEN__?: string }).__CRAG_TOKEN__ = token ?? undefined;
}

export function loadStoredEvaluations(): StoredEvaluation[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as StoredEvaluation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function upsertStoredEvaluation(record: StoredEvaluation): void {
  if (typeof window === "undefined") {
    return;
  }
  const history = loadStoredEvaluations();
  const without = history.filter((item) => item.id !== record.id);
  const next = [record, ...without].sort((a, b) => (a.created_at > b.created_at ? -1 : 1));
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
}

export function getStoredEvaluationById(id: string): StoredEvaluation | null {
  return loadStoredEvaluations().find((item) => item.id === id) ?? null;
}

export async function fetchEvaluationById(id: string): Promise<EvaluationResultData | null> {
  try {
    const data = await apiRequest<EvaluationResultData>(`/api/evaluations/${id}`, { method: "GET" });
    return data;
  } catch {
    return null;
  }
}

export async function fetchEvaluationsList(): Promise<EvaluationResultData[] | null> {
  try {
    const data = await apiRequest<EvaluationResultData[]>("/api/evaluations", { method: "GET" });
    return data;
  } catch {
    return null;
  }
}

export async function fetchEvaluationsFiltered(params: {
  limit?: number;
  tag?: string;
  folder?: string;
  q?: string;
  ai_filter?: boolean;
}): Promise<EvaluationResultData[] | null> {
  const search = new URLSearchParams();
  if (typeof params.limit === "number") {
    search.set("limit", String(params.limit));
  }
  if (params.tag) {
    search.set("tag", params.tag);
  }
  if (params.folder) {
    search.set("folder", params.folder);
  }
  if (params.q) {
    search.set("q", params.q);
  }
  if (params.ai_filter) {
    search.set("ai_filter", "true");
  }
  try {
    const data = await apiRequest<EvaluationResultData[]>(`/api/evaluations?${search.toString()}`, { method: "GET" });
    return data;
  } catch {
    return null;
  }
}

export async function fetchEvaluationKeywordTrends(
  evaluationId: string,
  options?: { keyword_override?: string }
): Promise<EvaluationKeywordTrends | null> {
  try {
    const query = new URLSearchParams();
    if (options?.keyword_override?.trim()) {
      query.set("keyword_override", options.keyword_override.trim());
    }
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const data = await apiRequest<EvaluationKeywordTrends>(`/api/evaluations/${evaluationId}/keyword-trends${suffix}`, {
      method: "GET",
    });
    return data;
  } catch {
    return null;
  }
}

function filenameFromContentDisposition(contentDisposition: string | null, fallback: string): string {
  if (!contentDisposition) {
    return fallback;
  }
  const match = contentDisposition.match(/filename="?([^"]+)"?/i);
  return match?.[1] ?? fallback;
}

export async function downloadEvaluationPdf(
  evaluationId: string,
  payload?: EvaluationPdfExportPayload
): Promise<void> {
  const token = getAuthToken();
  if (!token) {
    throw new Error("Missing auth token.");
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiBase}/api/evaluations/${evaluationId}/export`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload ?? {}),
  });

  if (!response.ok) {
    throw new Error(`PDF export failed (${response.status})`);
  }

  const blob = await response.blob();
  const fallback = `evaluation-${evaluationId}.pdf`;
  const filename = filenameFromContentDisposition(response.headers.get("Content-Disposition"), fallback);
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}
