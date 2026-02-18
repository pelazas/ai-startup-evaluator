"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "../contexts/auth-context";
import { loadStoredEvaluations, StoredEvaluation } from "../lib/evaluations";

function summarizeIdea(text: string): string {
  const normalized = text.trim().replace(/\s+/g, " ");
  if (!normalized) {
    return "Untitled idea";
  }
  return normalized.length > 110 ? `${normalized.slice(0, 110).trim()}...` : normalized;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function verdictClass(verdict: string | null | undefined): string {
  if (verdict === "GO") return "home-verdict home-verdict-go";
  if (verdict === "CONDITIONAL") return "home-verdict home-verdict-conditional";
  if (verdict === "NO-GO") return "home-verdict home-verdict-no-go";
  return "home-verdict home-verdict-neutral";
}

export default function HomePage() {
  const { isAuthenticated, user } = useAuth();
  const [items, setItems] = useState<StoredEvaluation[]>([]);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }
    setItems(loadStoredEvaluations());
  }, [isAuthenticated]);

  if (!isAuthenticated) {
    return (
      <main>
        <h1>AI Startup Audit</h1>
        <p>Please log in to continue.</p>
        <Link href="/login">Go to login</Link>
      </main>
    );
  }

  return (
    <main>
      <section className="home-hero">
        <p className="home-eyebrow">Dashboard</p>
        <h1>Welcome back</h1>
        <p className="home-subtitle">
          {user?.has_profile
            ? "Review your latest idea verdicts or launch a new startup evaluation."
            : "Complete your founder profile first to unlock startup evaluations."}
        </p>
      </section>

      <div className="home-actions">
        <Link href={user?.has_profile ? "/evaluate" : "/profile/setup"}>
          {user?.has_profile ? "Start New Evaluation" : "Finish Profile Setup"} <span aria-hidden>→</span>
        </Link>
      </div>

      <section className="idea-summary">
        <div className="idea-summary-header">
          <h2>Previous AI ideas</h2>
          <span className="idea-count">{items.length}</span>
        </div>
        {!items.length ? (
          <article className="idea-empty-state">
            <p className="form-note">No previous ideas yet. Run your first evaluation to populate this feed.</p>
          </article>
        ) : null}
        <div className="idea-card-grid">
          {items.map((item) => (
            <article key={item.id} className="idea-card">
              <div className="idea-card-top">
                <span className={verdictClass(item.result.verdict)}>{item.result.verdict ?? "UNAVAILABLE"}</span>
                <span className="idea-score-pill">
                  {typeof item.result.overall_score === "number" ? `${item.result.overall_score}/100` : "No score"}
                </span>
              </div>
              <h3>{summarizeIdea(item.idea_input.idea_description)}</h3>
              <p className="idea-meta">{formatTimestamp(item.created_at)}</p>
              <Link href={`/evaluations/${item.id}`} className="idea-link">
                Open details
              </Link>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
