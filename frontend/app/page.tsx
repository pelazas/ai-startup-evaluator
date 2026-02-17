"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "../contexts/auth-context";
import { loadStoredEvaluations, StoredEvaluation } from "../lib/evaluations";

export default function HomePage() {
  const { isAuthenticated, user } = useAuth();
  const [items, setItems] = useState<StoredEvaluation[]>([]);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }
    setItems(loadStoredEvaluations().slice(0, 8));
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
      <h1>Welcome back</h1>
      <p>
        {user?.has_profile
          ? "You are ready to evaluate new startup ideas."
          : "Complete your founder profile before creating a new evaluation."}
      </p>
      <div className="home-actions">
        <Link href={user?.has_profile ? "/evaluate" : "/profile/setup"}>
          {user?.has_profile ? "Start New Evaluation" : "Finish Profile Setup"}
        </Link>
      </div>

      <section className="idea-summary">
        <h2>Previous AI ideas</h2>
        {!items.length ? <p className="form-note">No previous ideas yet.</p> : null}
        {items.map((item) => (
          <article key={item.id} className="idea-card">
            <h3>{item.idea_input.idea_description.slice(0, 130)}</h3>
            <p>
              Verdict: <strong>{item.result.verdict ?? "N/A"}</strong> | Score:{" "}
              <strong>{item.result.overall_score ?? "N/A"}</strong>
            </p>
            <p className="form-note">{new Date(item.created_at).toLocaleString()}</p>
            <Link href={`/evaluations/${item.id}`}>Open details</Link>
          </article>
        ))}
      </section>
    </main>
  );
}
