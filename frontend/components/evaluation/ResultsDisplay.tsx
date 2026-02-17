"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { DimensionKey, StoredEvaluation } from "@/lib/evaluations";
import { HistoryModal } from "./HistoryModal";
import { RadarChart } from "./RadarChart";

type ResultsDisplayProps = {
  evaluation: StoredEvaluation;
  history: StoredEvaluation[];
};

const DIMENSIONS: Array<{ key: DimensionKey; label: string }> = [
  { key: "market", label: "Market Analysis" },
  { key: "technical", label: "Technical Feasibility" },
  { key: "distribution", label: "Distribution Strategy" },
  { key: "founder_fit", label: "Founder Fit" },
  { key: "timing", label: "Timing Assessment" },
];

function badgeClass(verdict: string | null): string {
  if (verdict === "GO") return "badge-go";
  if (verdict === "CONDITIONAL") return "badge-conditional";
  return "badge-no-go";
}

export function ResultsDisplay({ evaluation, history }: ResultsDisplayProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState<DimensionKey | null>(null);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const scores = evaluation.result.dimension_scores ?? {
    market: null,
    technical: null,
    distribution: null,
    founder_fit: null,
    timing: null,
  };

  const recent = useMemo(() => history.slice(0, 5), [history]);

  return (
    <main>
      {evaluation.result.status === "partial" ? (
        <p className="form-note">Some dimensions could not be evaluated. Results below are partial.</p>
      ) : null}
      <div className="results-header">
        <div className={`verdict-badge ${badgeClass(evaluation.result.verdict)}`}>{evaluation.result.verdict ?? "NO-GO"}</div>
        <div className="score-box">{evaluation.result.overall_score ?? "N/A"}/100</div>
      </div>

      {evaluation.result.low_confidence ? <p className="form-note">Low confidence due to limited evidence.</p> : null}

      <RadarChart scores={scores} />

      <section className="results-section">
        <h3>Top 3 Critical Risks</h3>
        <ul>
          {(evaluation.result.top_risks ?? []).slice(0, 3).map((risk) => (
            <li key={risk}>{risk}</li>
          ))}
        </ul>
      </section>

      <section className="results-section">
        <h3>Dimension Details</h3>
        {DIMENSIONS.map((dimension) => {
          const score = scores[dimension.key];
          const isOpen = expanded === dimension.key;
          const rationale = evaluation.result.dimension_analyses?.[dimension.key]?.rationale ?? "No rationale provided.";
          return (
            <div key={dimension.key} className="collapsible">
              <button
                type="button"
                className="collapsible-trigger"
                onClick={() => setExpanded((prev) => (prev === dimension.key ? null : dimension.key))}
              >
                <span>{dimension.label}</span>
                <span>{score === null ? "Unavailable" : score}</span>
              </button>
              {isOpen ? <div className="collapsible-content">{rationale}</div> : null}
            </div>
          );
        })}
      </section>

      <section className="results-section">
        <h3>Sources Used</h3>
        <ul>
          {(evaluation.result.evidence_sources ?? []).map((source, index) => (
            <li key={`${source.chunk_id ?? "source"}-${index}`}>
              {(source.doc_name ?? "Unknown doc") + " · " + (source.collection ?? "unknown collection")}
            </li>
          ))}
        </ul>
      </section>

      <section className="results-section">
        <h3>Previous Evaluations</h3>
        <div className="history-preview">
          {recent.map((item) => (
            <button
              type="button"
              key={item.id}
              className="history-card"
              onClick={() => router.push(`/evaluations/${item.id}`)}
            >
              <div>{item.idea_input.idea_description.slice(0, 60)}</div>
              <div className="history-meta">
                <span>{item.result.verdict ?? "N/A"}</span>
                <span>{item.result.overall_score ?? "N/A"}</span>
                <span>{new Date(item.created_at).toLocaleDateString()}</span>
              </div>
            </button>
          ))}
          {!recent.length ? <p className="form-note">No previous evaluations yet.</p> : null}
        </div>
        {history.length > 5 ? (
          <button type="button" onClick={() => setShowAllHistory(true)}>
            View All History
          </button>
        ) : null}
      </section>

      <button type="button" onClick={() => router.push("/evaluate")}>
        Evaluate Another Idea
      </button>

      {showAllHistory ? (
        <HistoryModal
          items={history}
          onClose={() => setShowAllHistory(false)}
          onSelect={(id) => {
            setShowAllHistory(false);
            router.push(`/evaluations/${id}`);
          }}
        />
      ) : null}
    </main>
  );
}

