"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  DimensionKey,
  EvaluationKeywordTrends,
  StoredEvaluation,
  downloadEvaluationPdf,
  fetchEvaluationKeywordTrends,
} from "@/lib/evaluations";
import { HistoryModal } from "./HistoryModal";
import { KeywordTrendsChart } from "./KeywordTrendsChart";
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

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractLabeledValue(text: string, label: string): string | null {
  const pattern = new RegExp(`(?:^|\\n)\\s*(?:[-*]\\s*)?${escapeRegex(label)}\\s*:\\s*(.+)$`, "im");
  const match = text.match(pattern);
  if (!match?.[1]) {
    return null;
  }
  const cleaned = match[1].trim().replace(/\s+/g, " ");
  return cleaned || null;
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
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [trendsLoading, setTrendsLoading] = useState(true);
  const [trendsError, setTrendsError] = useState<string | null>(null);
  const [trendsData, setTrendsData] = useState<EvaluationKeywordTrends | null>(null);
  const [selectedTrendKeyword, setSelectedTrendKeyword] = useState<string>("");
  const [trendsLoadingStep, setTrendsLoadingStep] = useState(1);

  const scores = evaluation.result.dimension_scores ?? {
    market: null,
    technical: null,
    distribution: null,
    founder_fit: null,
    timing: null,
  };

  const recent = useMemo(() => history.slice(0, 5), [history]);
  const previewHistory = useMemo(() => recent.slice(0, 2), [recent]);
  const sources = useMemo(() => evaluation.result.evidence_sources ?? [], [evaluation.result.evidence_sources]);

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

  const ideaCategorization = useMemo(() => {
    const description = evaluation.idea_input.idea_description ?? "";
    const aiCategorization = evaluation.result.idea_categorization ?? {};
    const type = aiCategorization.type ?? evaluation.idea_input.startup_type ?? extractLabeledValue(description, "Type");
    const market = aiCategorization.market ?? evaluation.idea_input.market_type ?? extractLabeledValue(description, "Market");
    const target = aiCategorization.target ?? evaluation.idea_input.target_customer ?? extractLabeledValue(description, "Target");
    const mainCompetitor = aiCategorization.main_competitor ?? extractLabeledValue(description, "Main Competitor");
    const trendAnalysis = aiCategorization.trend_analysis ?? extractLabeledValue(description, "Trend Analysis");

    return {
      type: type?.trim() || "Not specified",
      market: market?.trim() || "Not specified",
      target: target?.trim() || "Not specified",
      mainCompetitor: mainCompetitor?.trim() || "Not specified",
      trendAnalysis: trendAnalysis?.trim() || "Not specified",
    };
  }, [evaluation.idea_input.idea_description, evaluation.idea_input.market_type, evaluation.idea_input.startup_type, evaluation.idea_input.target_customer]);

  const confidenceMessage = useMemo(() => {
    if (!evaluation.result.low_confidence) {
      return null;
    }
    return "Confidence is reduced because evidence quality or coverage was limited in one or more dimensions.";
  }, [evaluation.result.low_confidence]);

  const trendStatusMessage = useMemo(() => {
    if (!trendsData?.status || trendsData.status === "ok") {
      return null;
    }
    if (trendsData.status === "no_keywords") {
      return "No keywords could be extracted automatically.";
    }
    if (trendsData.status === "no_trends_data") {
      return "No trend data for this keyword.";
    }
    if (trendsData.status === "provider_error") {
      return "Trend provider unavailable. Try again later.";
    }
    return null;
  }, [trendsData?.status]);

  const selectedTrendSeries = useMemo(() => {
    if (!trendsData?.series?.length) {
      return null;
    }
    return (
      trendsData.series.find((item) => item.keyword === selectedTrendKeyword) ??
      trendsData.series[0]
    );
  }, [selectedTrendKeyword, trendsData?.series]);

  useEffect(() => {
    let active = true;
    async function loadKeywordTrends() {
      setTrendsLoading(true);
      setTrendsError(null);
      const data = await fetchEvaluationKeywordTrends(evaluation.id);
      if (!active) {
        return;
      }
      if (!data) {
        setTrendsError("Unable to load keyword trend data.");
        setTrendsLoading(false);
        return;
      }
      setTrendsData(data);
      if (data.error) {
        setTrendsError(data.error);
      } else if (data.details && data.status !== "ok") {
        setTrendsError(data.details);
      } else {
        setTrendsError(null);
      }
      const defaultKeyword = data.selected_keyword ?? data.keywords?.[0] ?? data.series?.[0]?.keyword ?? "";
      setSelectedTrendKeyword(defaultKeyword);
      setTrendsLoading(false);
    }
    void loadKeywordTrends();
    return () => {
      active = false;
    };
  }, [evaluation.id]);

  useEffect(() => {
    if (!trendsLoading) {
      return;
    }
    setTrendsLoadingStep(1);
    const timer = window.setInterval(() => {
      setTrendsLoadingStep((prev) => (prev >= 5 ? 5 : prev + 1));
    }, 700);
    return () => window.clearInterval(timer);
  }, [trendsLoading]);

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
        <div className="results-panel results-panel-score">
          <h3 className="results-panel-title-centered">Scoring Profile</h3>
          <div className="scoring-profile-center">
            <RadarChart scores={scores} />
          </div>
        </div>

        <div className="results-panel results-panel-risks">
          <h3>Top 3 Critical Risks</h3>
          <div className="risk-cards">
            {(evaluation.result.top_risks ?? []).slice(0, 3).map((risk, index) => (
              <div key={risk} className="risk-card">
                <span className="risk-card-index">Risk {index + 1}</span>
                <p>{risk}</p>
              </div>
            ))}
            {!(evaluation.result.top_risks ?? []).length ? (
              <p className="form-note">No explicit critical risks were returned in this run.</p>
            ) : null}
          </div>
        </div>
      </section>

      <section className="results-section">
        <h3>Idea Categorization</h3>
        <div className="categorization-grid">
          <div className="categorization-item categorization-type">
            <span className="categorization-label">Type</span>
            <span>{ideaCategorization.type}</span>
          </div>
          <div className="categorization-item categorization-market">
            <span className="categorization-label">Market</span>
            <span>{ideaCategorization.market}</span>
          </div>
          <div className="categorization-item categorization-target">
            <span className="categorization-label">Target</span>
            <span>{ideaCategorization.target}</span>
          </div>
          <div className="categorization-item categorization-competitor">
            <span className="categorization-label">Main Competitor</span>
            <span>{ideaCategorization.mainCompetitor}</span>
          </div>
          <div className="categorization-item categorization-item-wide categorization-trend">
            <span className="categorization-label">Trend Analysis</span>
            <span>{ideaCategorization.trendAnalysis}</span>
          </div>
        </div>
      </section>

      <section className="results-section">
        <h3>Keyword Trend Volume</h3>
        {trendsLoading ? <p className="form-note">Loading keyword trends... keyword {trendsLoadingStep}/5</p> : null}
        {!trendsLoading && trendsError ? <p className="form-note">{trendsError}</p> : null}
        {!trendsLoading && trendStatusMessage ? <p className="form-note">{trendStatusMessage}</p> : null}
        {!trendsLoading && !trendsError && trendsData?.keywords?.length ? (
          <div className="keyword-trends-block">
            <label className="keyword-select-label">
              Keyword
              <select
                value={selectedTrendKeyword}
                onChange={(event) => setSelectedTrendKeyword(event.target.value)}
                className="keyword-select"
              >
                {trendsData.keywords.map((keyword) => (
                  <option key={keyword} value={keyword}>
                    {keyword}
                  </option>
                ))}
              </select>
            </label>
            {selectedTrendSeries ? <KeywordTrendsChart series={selectedTrendSeries} /> : null}
            <p className="form-note keyword-source-note">
              Source - Google Trends - Worldwide (web search) - past 12 months
            </p>
          </div>
        ) : null}
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
          const improvementText = evaluation.result.dimension_analyses?.[dimension.key]?.improvement?.trim();
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
                  {improvementText ? <p className="dimension-improvement">{improvementText}</p> : null}
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
        <div className="sources-compact">
          <div className="sources-compact-title">
            <strong>{sources.length} unique sources consulted</strong>
            <span className="form-note">
              {internalSourceCount} internal · {webSourceCount} web
            </span>
          </div>
          {sources.length ? (
            <button type="button" className="button-muted sources-toggle" onClick={() => setSourcesExpanded((prev) => !prev)}>
              {sourcesExpanded ? "Hide files" : "Show files"}
            </button>
          ) : null}
        </div>

        {sourcesExpanded ? (
          <div className="sources-list">
            {sources.map((source, index) => {
              const title = source.doc_name ?? source.title ?? "Untitled source";
              const collection = source.collection ?? "unknown";
              const sourceLabel = source.source_name ?? source.source ?? null;
              return (
                <article key={`${source.chunk_id ?? `${title}-${collection}`}-${index}`} className="source-file-row">
                  <div className="source-file-main">
                    <strong>{title}</strong>
                    <span className="source-collection">{collection}</span>
                  </div>
                  <div className="source-file-meta">
                    <span>{formatRetrievalMethod(source.retrieval_method)}</span>
                    {source.source_url ? (
                      <a href={source.source_url} target="_blank" rel="noreferrer" className="source-link">
                        Open source
                      </a>
                    ) : sourceLabel ? (
                      <span>{sourceLabel}</span>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}

        {!sources.length ? <p className="form-note">No evidence sources were captured.</p> : null}
      </section>

      <section className="results-section">
        <h3>Previous Evaluations</h3>
        <div className="history-preview">
          {previewHistory.map((item, index) => (
            <button
              type="button"
              key={item.id}
              className={`history-card history-card-compact ${index === 1 ? "history-card-faded" : ""}`}
              onClick={() => router.push(`/evaluations/${item.id}`)}
            >
              <div className="history-card-title">{item.idea_input.idea_description.slice(0, 52)}</div>
              <div className="history-meta">
                <span>{item.result.verdict ?? "N/A"}</span>
                <span>{item.result.overall_score ?? "N/A"}</span>
                <span>{new Date(item.created_at).toLocaleDateString()}</span>
              </div>
            </button>
          ))}
          {!recent.length ? <p className="form-note">No previous evaluations yet.</p> : null}
        </div>
      </section>

      <div className="results-actions-row">
        {history.length > 1 ? (
          <button type="button" className="button-muted" onClick={() => setShowAllHistory(true)}>
            View All History
          </button>
        ) : (
          <span />
        )}
        <button type="button" onClick={() => router.push("/evaluate")}>
          Evaluate Another Idea
        </button>
      </div>

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
