"use client";

const STEP_LABELS: Record<string, string> = {
  intake: "Intake",
  retrieval: "Retrieval",
  critic: "Strategic Critic",
  verdict: "Verdict Generation",
};

const STEP_ORDER = ["intake", "retrieval", "critic", "verdict"];

type ProgressIndicatorProps = {
  completedNodes: string[];
  activeNode: string | null;
  errorMessage?: string | null;
};

export function ProgressIndicator({ completedNodes, activeNode, errorMessage }: ProgressIndicatorProps) {
  return (
    <section className="progress-card">
      <h3>Step 3 of 3: Evaluation</h3>
      <p>This usually takes 30-60 seconds.</p>
      <div className="progress-list">
        {STEP_ORDER.map((step) => {
          const done = completedNodes.includes(step);
          const active = activeNode === step && !done;
          return (
            <div key={step} className={`progress-item ${done ? "done" : active ? "active" : "pending"}`}>
              <span className="progress-icon">{done ? "✓" : active ? "⟳" : "○"}</span>
              <span>{STEP_LABELS[step]}</span>
            </div>
          );
        })}
      </div>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
    </section>
  );
}

