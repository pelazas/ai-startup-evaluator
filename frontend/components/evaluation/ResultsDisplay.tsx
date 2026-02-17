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
  if (verdict === "NO-GO") return "badge-no-go";
  return "badge-neutral";
}

export function ResultsDisplay({ evaluation, history }: ResultsDisplayProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState<DimensionKey | null>(null);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [showAllSources, setShowAllSources] = useState(false);
  const scores = evaluation.result.dimension_scores ?? {
    market: null,
    technical: null,
    distribution: null,
    founder_fit: null,
    timing: null,
  };

  const recent = useMemo(() => history.slice(0, 5), [history]);
  const failedDimensions = useMemo(() => {
    if (evaluation.result.failed_dimensions?.length) {
      return evaluation.result.failed_dimensions;
    }
    return DIMENSIONS.filter((item) => scores[item.key] === null).map((item) => item.key);
  }, [evaluation.result.failed_dimensions, scores]);
  const failedLabels = useMemo(
    () => DIMENSIONS.filter((item) => failedDimensions.includes(item.key)).map((item) => item.label),
    [failedDimensions]
  );

  const displayedOverall = useMemo(() => {
    if (evaluation.result.status === "failed") {
      return null;
    }
    if (typeof evaluation.result.overall_score === "number") {
      return evaluation.result.overall_score;
    }
    const available = Object.values(scores).filter((value): value is number => typeof value === "number");
    if (!available.length) {
      return null;
    }
    return Math.round(available.reduce((total, value) => total + value, 0) / available.length);
  }, [evaluation.result.overall_score, evaluation.result.status, scores]);

  const sources = useMemo(() => evaluation.result.evidence_sources ?? [], [evaluation.result.evidence_sources]);
  const visibleSources = useMemo(() => (showAllSources ? sources : sources.slice(0, 8)), [showAllSources, sources]);
  const isFailed = evaluation.result.status === "failed";

  return (
    <main>
      {evaluation.result.status === "partial" ? (
        <p className="form-note">
          Partial scoring: {failedLabels.length ? failedLabels.join(", ") : "some dimensions"} could not be evaluated.
        </p>
      ) : null}
      {isFailed ? (
        <p className="form-error">Evaluation failed before any dimension could be scored. Try running it again.</p>
      ) : null}
      <div className="results-header">
        <div className={`verdict-badge ${badgeClass(evaluation.result.verdict)}`}>{evaluation.result.verdict ?? "UNAVAILABLE"}</div>
        <div className="score-box">{displayedOverall === null ? "Score unavailable" : `${displayedOverall}/100`}</div>
      </div>
      <p className="form-note">Scoring scale: 0-100 per dimension and overall.</p>

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
          const rationale =
            evaluation.result.dimension_analyses?.[dimension.key]?.rationale ??
            (score === null
              ? "Unavailable - No output returned for this dimension."
              : "Rationale unavailable - please re-run evaluation with stronger evidence coverage.");
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
        <p className="form-note">{sources.length} unique sources used.</p>
        <div className="sources-list">
          {visibleSources.map((source, index) => {
            const title = source.title ?? source.doc_name ?? "Untitled source";
            const collection = source.collection ?? "unknown";
            const snippet = source.snippet ?? null;
            return (
              <article key={`${source.chunk_id ?? `${title}-${collection}`}-${index}`} className="source-card">
                <div className="source-card-header">
                  <strong>{title}</strong>
                  <span className="source-collection">{collection}</span>
                </div>
                {source.source_url ? (
                  <a href={source.source_url} target="_blank" rel="noreferrer" className="source-link">
                    {source.source_name ?? "Open source"}
                  </a>
                ) : source.source_name || source.source ? (
                  <p className="source-meta">{source.source_name ?? source.source}</p>
                ) : null}
                {source.why_relevant ? <p className="source-meta"><strong>Why used:</strong> {source.why_relevant}</p> : null}
                {source.supporting_dimensions?.length ? (
                  <p className="source-meta">
                    <strong>Supports:</strong> {source.supporting_dimensions.join(", ")}
                  </p>
                ) : null}
                {snippet ? <p className="source-snippet">{snippet}</p> : null}
              </article>
            );
          })}
          {!sources.length ? <p className="form-note">No evidence sources were captured.</p> : null}
        </div>
        {sources.length > 8 ? (
          <button type="button" onClick={() => setShowAllSources((prev) => !prev)}>
            {showAllSources ? "Show fewer sources" : `Show all sources (${sources.length})`}
          </button>
        ) : null}
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
