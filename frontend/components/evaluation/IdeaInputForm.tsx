"use client";

import { FormEvent, useMemo, useState } from "react";

import { EvaluationCreatePayload } from "@/lib/evaluations";

const STARTUP_TYPES = ["AI Infrastructure", "Vertical SaaS", "Developer Tool", "Consumer AI"];
const MARKET_TYPES = ["B2B", "B2C"];

type IdeaInputFormProps = {
  initialValue?: EvaluationCreatePayload;
  onSubmit: (payload: EvaluationCreatePayload) => Promise<void>;
  disabled?: boolean;
};

export function IdeaInputForm({ initialValue, onSubmit, disabled = false }: IdeaInputFormProps) {
  const [form, setForm] = useState<EvaluationCreatePayload>(
    initialValue ?? {
      idea_description: "",
      target_customer: "",
      problem_statement: "",
      startup_type: "",
      market_type: "",
      web_enabled: true,
    }
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValid = useMemo(() => form.idea_description.trim().length >= 10, [form.idea_description]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isValid || submitting || disabled) {
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        idea_description: form.idea_description.trim(),
        target_customer: form.target_customer?.trim() || null,
        problem_statement: form.problem_statement?.trim() || null,
        startup_type: form.startup_type || null,
        market_type: form.market_type || null,
        web_enabled: form.web_enabled ?? true,
      });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to submit evaluation.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="evaluation-form" onSubmit={handleSubmit}>
      <label>
        Describe your startup idea
        <textarea
          rows={7}
          placeholder="Describe your startup idea in detail..."
          value={form.idea_description}
          onChange={(event) => setForm((prev) => ({ ...prev, idea_description: event.target.value }))}
          required
          disabled={disabled || submitting}
        />
      </label>

      <label>
        Target customer (optional)
        <input
          type="text"
          placeholder="Who will buy/use this?"
          value={form.target_customer ?? ""}
          onChange={(event) => setForm((prev) => ({ ...prev, target_customer: event.target.value }))}
          disabled={disabled || submitting}
        />
      </label>

      <label>
        Problem statement (optional)
        <input
          type="text"
          placeholder="What core problem are you solving?"
          value={form.problem_statement ?? ""}
          onChange={(event) => setForm((prev) => ({ ...prev, problem_statement: event.target.value }))}
          disabled={disabled || submitting}
        />
      </label>

      <fieldset>
        <legend>Startup type</legend>
        <div className="inline-options">
          {STARTUP_TYPES.map((type) => (
            <label key={type}>
              <input
                type="radio"
                name="startup_type"
                checked={form.startup_type === type}
                onChange={() => setForm((prev) => ({ ...prev, startup_type: type }))}
                disabled={disabled || submitting}
              />
              {type}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Market</legend>
        <div className="inline-options">
          {MARKET_TYPES.map((type) => (
            <label key={type}>
              <input
                type="radio"
                name="market_type"
                checked={form.market_type === type}
                onChange={() => setForm((prev) => ({ ...prev, market_type: type }))}
                disabled={disabled || submitting}
              />
              {type}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="inline-toggle">
        <input
          type="checkbox"
          checked={Boolean(form.web_enabled ?? true)}
          onChange={(event) => setForm((prev) => ({ ...prev, web_enabled: event.target.checked }))}
          disabled={disabled || submitting}
        />
        Use live web data (slower, more accurate)
      </label>

      {!isValid ? <p className="form-note">Idea description must be at least 10 characters.</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      <button type="submit" disabled={!isValid || submitting || disabled}>
        {submitting ? "Submitting..." : "Evaluate Idea"}
      </button>
    </form>
  );
}
