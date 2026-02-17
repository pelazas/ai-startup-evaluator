import { apiRequest } from "./api";

export type DimensionKey = "market" | "technical" | "distribution" | "founder_fit" | "timing";

export type EvaluationCreatePayload = {
  idea_description: string;
  target_customer?: string | null;
  problem_statement?: string | null;
  startup_type?: string | null;
  market_type?: string | null;
};

export type EvaluationResultData = {
  evaluation_id: string;
  status: "completed" | "partial" | "failed" | "pending";
  overall_score: number | null;
  verdict: "GO" | "CONDITIONAL" | "NO-GO" | null;
  low_confidence: boolean;
  dimension_scores?: Record<DimensionKey, number | null>;
  dimension_analyses?: Record<DimensionKey, { rationale?: string }>;
  top_risks?: string[];
  evidence_sources?: Array<{ doc_name?: string; collection?: string; source?: string; chunk_id?: string }>;
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

