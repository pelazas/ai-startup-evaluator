"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { DimensionKey, StoredEvaluation, downloadEvaluationPdf } from "@/lib/evaluations";
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

const DIMENSION_LABELS = DIMENSIONS.reduce(
  (acc, item) => {
    acc[item.key] = item.label;
    return acc;
  },
  {} as Record<DimensionKey, string>
);

function fallbackIdeaTitle(raw: string): string {
  const normalized = raw.trim().replace(/\s+/g, " ");
  if (!normalized) {
    return "Untitled Startup Idea";
  }
  return normalized.length > 72 ? `${normalized.slice(0, 72).trim()}...` : normalized;
}

function normalizeDimensionRationale(rationale: string, score: number | null): string {
  const text = rationale.trim().replace(/\s+/g, " ");
  if (!text) {
    return score === null
      ? "This dimension could not be scored with the current evidence."
      : "The system scored this dimension, but did not provide detailed reasoning.";
  }

  if (text.startsWith("Score interpreted as")) {
    const detailedMatch = text.match(
      /^Score interpreted as\s+(.+?)\s+confidence for this dimension\.\s+(.+?)\s+inferred from\s+(.+?)\s+evidence\s+\(e\.g\.,\s+(.+?)\)\s+with signal:\s+(.+)$/i
    );
    if (detailedMatch) {
      const confidence = `${detailedMatch[1].charAt(0).toUpperCase()}${detailedMatch[1].slice(1)}`;
      const topic = detailedMatch[2];
      const corpus = detailedMatch[3];
      const sourceTitle = detailedMatch[4];
      const signal = detailedMatch[5];
      if (score === null) {
        return `Score unavailable. ${confidence} confidence for this dimension. ${topic} based on ${corpus} evidence from ${sourceTitle}. Evidence signal: ${signal}`;
      }
      return `Score ${score}/100. ${confidence} confidence for this dimension. ${topic} based on ${corpus} evidence from ${sourceTitle}. Evidence signal: ${signal}`;
    }

    const cleaned = text.replace(/^Score interpreted as\s+/i, "").trim();
    return score === null ? `Score unavailable. ${cleaned}` : `Score ${score}/100. ${cleaned}`;
  }

  return text;
}

function buildIdeaSummary(
  summary: string | null | undefined,
  verdict: string | null,
  overall: number | null,
  topRisks: string[]
): string {
  const cleaned = summary?.trim();
  if (cleaned) {
    return cleaned;
  }
  const riskHint = topRisks[0] ? ` Main concern: ${topRisks[0]}` : "";
  if (overall === null) {
    return `The current run does not have enough valid evidence to produce a reliable final verdict.${riskHint}`;
  }
  return `This idea is currently ${verdict ?? "UNAVAILABLE"} with a score of ${overall}/100. The result reflects the weighted strength across market, technical, distribution, founder fit, and timing dimensions.${riskHint}`;
}

function badgeClass(verdict: string | null): string {
  if (verdict === "GO") return "badge-go";
  if (verdict === "CONDITIONAL") return "badge-conditional";
  if (verdict === "NO-GO") return "badge-no-go";
  return "badge-neutral";
}

function normalizeDiagnosticMessage(message: string): string {
  const trimmed = message.trim();
  if (!trimmed) {
    return "No additional details were provided by the parser.";
  }
  if (trimmed === "normalized_score_scale:1_to_10_to_100") {
    return "Some critic scores were normalized from a 1-10 scale to the app's 0-100 scale.";
  }
  return trimmed;
}

function formatRetrievalMethod(value: string | null | undefined): string {
  if (!value) {
    return "Not specified";
  }
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

async function radarChartToDataUrl(): Promise<string | null> {
  const svg = document.querySelector(".radar-svg") as SVGSVGElement | null;
  if (!svg) {
    return null;
  }

  const serializer = new XMLSerializer();
  const rawSvg = serializer.serializeToString(svg);
  const svgBlob = new Blob([rawSvg], { type: "image/svg+xml;charset=utf-8" });
  const blobUrl = URL.createObjectURL(svgBlob);

  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Unable to render chart image."));
      img.src = blobUrl;
    });

    const width = Number(svg.getAttribute("width")) || 340;
    const height = Number(svg.getAttribute("height")) || 340;
    const scale = Math.min(2, window.devicePixelRatio || 1);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return null;
    }
    ctx.scale(scale, scale);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(image, 0, 0, width, height);
    return canvas.toDataURL("image/png");
  } finally {
    URL.revokeObjectURL(blobUrl);
  }
}

export function ResultsDisplay({ evaluation, history }: ResultsDisplayProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState<DimensionKey | null>(null);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [showAllSources, setShowAllSources] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const scores = evaluation.result.dimension_scores ?? {
    market: null,
    technical: null,
    distribution: null,
    founder_fit: null,
    timing: null,
  };

  const recent = useMemo(() => history.slice(0, 5), [history]);
  const sources = useMemo(() => evaluation.result.evidence_sources ?? [], [evaluation.result.evidence_sources]);
  const visibleSources = useMemo(() => (showAllSources ? sources : sources.slice(0, 8)), [showAllSources, sources]);

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

  const diagnostics = useMemo(() => {
    const byDimension: Record<DimensionKey, string[]> = {
      market: [],
      technical: [],
      distribution: [],
      founder_fit: [],
      timing: [],
    };
    const general: string[] = [];

    for (const diagnostic of evaluation.result.parse_diagnostics ?? []) {
      const cleaned = normalizeDiagnosticMessage(diagnostic);
      const match = cleaned.match(/^(market|technical|distribution|founder_fit|timing)\s*:\s*(.+)$/i);
      if (!match) {
        general.push(cleaned);
        continue;
      }
      const key = match[1].toLowerCase() as DimensionKey;
      const reason = match[2].trim() || "The critic output could not be parsed for this dimension.";
      byDimension[key].push(reason);
    }

    return { byDimension, general };
  }, [evaluation.result.parse_diagnostics]);

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

  const isFailed = evaluation.result.status === "failed";

  const webSourceCount = useMemo(() => {
    if (typeof evaluation.result.evidence_mix?.web_sources === "number") {
      return evaluation.result.evidence_mix.web_sources;
    }
    return sources.filter((source) => source.collection?.toLowerCase() === "web" || Boolean(source.source_url)).length;
  }, [evaluation.result.evidence_mix?.web_sources, sources]);

  const internalSourceCount = useMemo(() => {
    if (typeof evaluation.result.evidence_mix?.internal_sources === "number") {
      return evaluation.result.evidence_mix.internal_sources;
    }
    return Math.max(0, sources.length - webSourceCount);
  }, [evaluation.result.evidence_mix?.internal_sources, sources.length, webSourceCount]);

  const ideaTitle = useMemo(() => {
    const candidate = evaluation.result.idea_title?.trim();
    if (candidate) {
      return candidate;
    }
    return fallbackIdeaTitle(evaluation.idea_input.idea_description);
  }, [evaluation.idea_input.idea_description, evaluation.result.idea_title]);

  const ideaSummary = useMemo(
    () =>
      buildIdeaSummary(
        evaluation.result.idea_summary,
        evaluation.result.verdict,
        displayedOverall,
        evaluation.result.top_risks ?? []
      ),
    [displayedOverall, evaluation.result.idea_summary, evaluation.result.top_risks, evaluation.result.verdict]
  );

  const sourceTitlesByDimension = useMemo(() => {
    const grouped: Record<DimensionKey, string[]> = {
      market: [],
      technical: [],
      distribution: [],
      founder_fit: [],
      timing: [],
    };

    for (const source of sources) {
      const title = (source.doc_name ?? source.title ?? "Untitled source").trim();
      for (const rawDimension of source.supporting_dimensions ?? []) {
        if (rawDimension in grouped && !grouped[rawDimension as DimensionKey].includes(title)) {
          grouped[rawDimension as DimensionKey].push(title);
        }
      }
    }

    return grouped;
  }, [sources]);

  const founderFitSummary = useMemo(() => {
    const cleaned = evaluation.result.founder_fit_summary?.trim();
    if (cleaned) {
      return cleaned;
    }
    const founderScore = scores.founder_fit;
    if (founderScore === null) {
      return "Founder-Idea fit is not available yet. Add more founder profile detail and rerun.";
    }
    return `Founder-Idea Fit scored ${founderScore}/100 based on the available profile and evidence.`;
  }, [evaluation.result.founder_fit_summary, scores.founder_fit]);

  const confidenceMessage = useMemo(() => {
    if (!evaluation.result.low_confidence) {
      return null;
    }
    return "Confidence is reduced because evidence quality or coverage was limited in one or more dimensions.";
  }, [evaluation.result.low_confidence]);

  async function handleDownloadPdf() {
    setPdfError(null);
    setDownloadingPdf(true);
    try {
      const chartImageDataUrl = await radarChartToDataUrl();
      await downloadEvaluationPdf(evaluation.id, {
        chart_image_data_url: chartImageDataUrl ?? undefined,
      });
    } catch (error) {
      setPdfError(error instanceof Error ? error.message : "Unable to export PDF report.");
    } finally {
      setDownloadingPdf(false);
    }
  }

  return (
    <main className="results-main">
      {evaluation.result.status === "partial" ? (
        <p className="form-note">
          Partial scoring: {failedLabels.length ? failedLabels.join(", ") : "some dimensions"} could not be evaluated.
        </p>
      ) : null}

      {isFailed ? (
        <p className="form-error">
          Evaluation failed before any dimension could be scored. {" "}
          {evaluation.result.error_message ? `Reason: ${evaluation.result.error_message}` : "Try running it again."}
        </p>
      ) : null}

      {failedDimensions.length || diagnostics.general.length ? (
        <section className="results-section diagnostics-section">
          <h3>Run Diagnostics</h3>
          <p className="form-note">Parser and scoring details for this run.</p>
          {failedDimensions.length ? (
            <ul className="diagnostic-list">
              {failedDimensions.map((dimension) => {
                const reasons = diagnostics.byDimension[dimension];
                return (
                  <li key={dimension}>
                    <strong>{DIMENSION_LABELS[dimension]}:</strong>{" "}
                    {reasons.length
                      ? reasons.join(" ")
                      : "This dimension could not be scored from the returned critic output."}
                  </li>
                );
              })}
            </ul>
          ) : null}
          {diagnostics.general.length ? (
            <ul className="diagnostic-list">
              {diagnostics.general.map((message, index) => (
                <li key={`${message}-${index}`}>{message}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      <section className="results-hero">
        <p className="results-kicker">Evaluation Results</p>
        <p className="idea-title">{ideaTitle}</p>
        {(evaluation.result.idea_folder || (evaluation.result.idea_tags ?? []).length) ? (
          <p className="form-note">
            {evaluation.result.idea_folder ? `Folder: ${evaluation.result.idea_folder}` : ""}
            {evaluation.result.idea_folder && (evaluation.result.idea_tags ?? []).length ? " · " : ""}
            {(evaluation.result.idea_tags ?? []).length ? `Tags: ${(evaluation.result.idea_tags ?? []).join(", ")}` : ""}
          </p>
        ) : null}
        <p className="hero-summary">{ideaSummary}</p>

        <div className="results-header">
          <div className="results-header-left">
            <div className={`verdict-badge ${badgeClass(evaluation.result.verdict)}`}>{evaluation.result.verdict ?? "UNAVAILABLE"}</div>
            <div className="score-box">{displayedOverall === null ? "Score unavailable" : `${displayedOverall}/100`}</div>
          </div>
          <button type="button" className="button-muted" onClick={() => void handleDownloadPdf()} disabled={downloadingPdf}>
            {downloadingPdf ? "Generating PDF..." : "Download PDF Report"}
          </button>
        </div>

        {pdfError ? <p className="form-error">{pdfError}</p> : null}
        <p className="form-note">Scoring scale: 0-100 per dimension and overall.</p>
        {confidenceMessage ? <p className="confidence-note">{confidenceMessage}</p> : null}
      </section>

      <section className="results-grid">
        <div className="results-panel">
          <h3>Scoring Profile</h3>
          <RadarChart scores={scores} />
        </div>

        <div className="results-panel">
          <h3>Top 3 Critical Risks</h3>
          <ul>
            {(evaluation.result.top_risks ?? []).slice(0, 3).map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="results-section">
        <h3>Dimension Details</h3>
        {DIMENSIONS.map((dimension) => {
          const score = scores[dimension.key];
          const isOpen = expanded === dimension.key;
          const resourceTitles = sourceTitlesByDimension[dimension.key];
          const resourceCount = resourceTitles.length;
          const resourceLabel = `(${resourceCount} resources consulted)`;
          const readableRationale = normalizeDimensionRationale(
            evaluation.result.dimension_analyses?.[dimension.key]?.rationale ??
              (score === null
                ? "This dimension could not be evaluated with the current evidence."
                : "The system scored this dimension but returned no explanation."),
            score
          );
          const resourceHover = resourceTitles.length
            ? resourceTitles.map((title, index) => `${index + 1}. ${title}`).join("\n")
            : "No linked evidence sources";
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
              {isOpen ? (
                <div className="collapsible-content">
                  {readableRationale}{" "}
                  <span className="resource-count" title={resourceHover}>
                    {resourceLabel}
                  </span>
                </div>
              ) : null}
            </div>
          );
        })}
      </section>

      <section className="results-section">
        <h3>Founder-Idea Fit</h3>
        <p>{founderFitSummary}</p>
      </section>

      <section className="results-section">
        <h3>Sources Used</h3>
        <div className="source-explainer">
          <p>
            The critic consulted <strong>{sources.length}</strong> unique resources: <strong>{internalSourceCount}</strong> internal and{" "}
            <strong>{webSourceCount}</strong> from web retrieval.
          </p>
          <p>Each source card explains why it was used, what it supports, and how it was retrieved.</p>
        </div>

        {evaluation.result.evidence_mix ? (
          <p className="form-note">
            Internal: {evaluation.result.evidence_mix.internal_sources ?? 0} · Web: {evaluation.result.evidence_mix.web_sources ?? 0} · Total:{" "}
            {evaluation.result.evidence_mix.total_sources ?? 0}
          </p>
        ) : null}

        <p className="form-note">
          Mode: {evaluation.result.web_enabled === false ? "Internal corpus only" : "Hybrid (internal + web)"}
        </p>

        {evaluation.result.web_queries_used?.length ? (
          <p className="form-note">Web queries: {evaluation.result.web_queries_used.join(" | ")}</p>
        ) : null}

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
                <p className="source-meta">
                  <strong>Retrieved via:</strong> {formatRetrievalMethod(source.retrieval_method)}
                </p>
                {source.why_relevant ? (
                  <p className="source-meta">
                    <strong>Why used:</strong> {source.why_relevant}
                  </p>
                ) : null}
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
          <button type="button" className="button-muted" onClick={() => setShowAllSources((prev) => !prev)}>
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
          <button type="button" className="button-muted" onClick={() => setShowAllHistory(true)}>
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
