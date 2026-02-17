"use client";

import { FormEvent, useMemo, useState } from "react";

import { ProfilePayload } from "@/lib/profile";

const TECHNICAL_SKILLS = ["Python", "JavaScript", "ML/AI", "DevOps", "Data Engineering", "Cloud"];
const DOMAIN_EXPERTISE = ["SaaS", "FinTech", "HealthTech", "E-commerce", "EdTech", "Cybersecurity"];
const YEARS_EXPERIENCE = ["0-2", "3-5", "6-10", "10+"];
const TEAM_SIZES = ["Solo", "2-3", "4-10", "10+"];
const BUDGET_RANGES = ["<$10k", "$10k-$50k", "$50k-$100k", "$100k+"];
const RISK_TOLERANCE = ["Low", "Medium", "High"];

const EMPTY_PROFILE: ProfilePayload = {
  technical_skills: [],
  domain_expertise: [],
  years_experience: "",
  team_size: "",
  budget_range: "",
  network_strength: 5,
  risk_tolerance: "",
  geographic_location: "",
};

type ProfileFormProps = {
  initialValue?: ProfilePayload;
  submitLabel: string;
  onSubmit: (payload: ProfilePayload) => Promise<void>;
};

function toggleItem(items: string[], value: string): string[] {
  if (items.includes(value)) {
    return items.filter((item) => item !== value);
  }
  return [...items, value];
}

export function ProfileForm({ initialValue, submitLabel, onSubmit }: ProfileFormProps) {
  const [form, setForm] = useState<ProfilePayload>(initialValue ?? EMPTY_PROFILE);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValid = useMemo(() => {
    return (
      form.technical_skills.length > 0 &&
      form.domain_expertise.length > 0 &&
      Boolean(form.years_experience) &&
      Boolean(form.team_size) &&
      Boolean(form.budget_range) &&
      form.network_strength >= 1 &&
      form.network_strength <= 10 &&
      Boolean(form.risk_tolerance) &&
      Boolean(form.geographic_location.trim())
    );
  }, [form]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isValid || saving) {
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        ...form,
        geographic_location: form.geographic_location.trim(),
      });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to save profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="profile-form">
      <div>
        <h3>Technical skills</h3>
        <div className="pill-grid">
          {TECHNICAL_SKILLS.map((skill) => (
            <label key={skill} className="checkbox-pill">
              <input
                type="checkbox"
                checked={form.technical_skills.includes(skill)}
                onChange={() =>
                  setForm((prev) => ({
                    ...prev,
                    technical_skills: toggleItem(prev.technical_skills, skill),
                  }))
                }
              />
              <span>{skill}</span>
            </label>
          ))}
        </div>
      </div>

      <div>
        <h3>Domain expertise</h3>
        <div className="pill-grid">
          {DOMAIN_EXPERTISE.map((domain) => (
            <label key={domain} className="checkbox-pill">
              <input
                type="checkbox"
                checked={form.domain_expertise.includes(domain)}
                onChange={() =>
                  setForm((prev) => ({
                    ...prev,
                    domain_expertise: toggleItem(prev.domain_expertise, domain),
                  }))
                }
              />
              <span>{domain}</span>
            </label>
          ))}
        </div>
      </div>

      <label>
        Years of experience
        <select
          value={form.years_experience}
          onChange={(event) => setForm((prev) => ({ ...prev, years_experience: event.target.value }))}
          required
        >
          <option value="">Select...</option>
          {YEARS_EXPERIENCE.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>

      <fieldset>
        <legend>Team size</legend>
        <div className="inline-options">
          {TEAM_SIZES.map((size) => (
            <label key={size}>
              <input
                type="radio"
                name="team_size"
                value={size}
                checked={form.team_size === size}
                onChange={(event) => setForm((prev) => ({ ...prev, team_size: event.target.value }))}
              />
              {size}
            </label>
          ))}
        </div>
      </fieldset>

      <label>
        Budget range
        <select
          value={form.budget_range}
          onChange={(event) => setForm((prev) => ({ ...prev, budget_range: event.target.value }))}
          required
        >
          <option value="">Select...</option>
          {BUDGET_RANGES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>

      <label>
        Network strength ({form.network_strength})
        <input
          type="range"
          min={1}
          max={10}
          value={form.network_strength}
          onChange={(event) =>
            setForm((prev) => ({
              ...prev,
              network_strength: Number.parseInt(event.target.value, 10),
            }))
          }
        />
      </label>

      <fieldset>
        <legend>Risk tolerance</legend>
        <div className="inline-options">
          {RISK_TOLERANCE.map((risk) => (
            <label key={risk}>
              <input
                type="radio"
                name="risk_tolerance"
                value={risk}
                checked={form.risk_tolerance === risk}
                onChange={(event) => setForm((prev) => ({ ...prev, risk_tolerance: event.target.value }))}
              />
              {risk}
            </label>
          ))}
        </div>
      </fieldset>

      <label>
        Geographic location
        <input
          type="text"
          placeholder="City, Country"
          value={form.geographic_location}
          onChange={(event) => setForm((prev) => ({ ...prev, geographic_location: event.target.value }))}
          required
        />
      </label>

      {error ? <p className="form-error">{error}</p> : null}
      {!isValid ? <p className="form-note">Complete all required fields to continue.</p> : null}

      <button type="submit" disabled={!isValid || saving}>
        {saving ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}

