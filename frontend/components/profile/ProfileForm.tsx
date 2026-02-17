"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ProfilePayload } from "@/lib/profile";

const ROLE_TITLES = ["Solo Founder", "CTO", "CEO", "Product", "Other"];
const CURRENT_STAGES = ["Idea", "MVP", "Launched", "Growth"];
const INDUSTRY_FOCUS = ["SaaS", "FinTech", "HealthTech", "E-commerce", "Developer Tools", "Cybersecurity", "EdTech"];
const BUSINESS_MODELS = ["SaaS", "Usage-based", "Marketplace", "Services", "Hybrid"];
const TARGET_MARKETS = ["B2B", "B2C", "B2B2C", "Enterprise"];
const TEAM_SIZES = ["Solo", "2-3", "4-10", "10+"];
const BUDGET_RANGES = ["<$10k", "$10k-$50k", "$50k-$100k", "$100k+"];
const HIRING_ABILITY = ["None", "1-2", "3+"];
const LEVEL_OPTIONS = ["None", "Basic", "Intermediate", "Advanced", "Expert"];
const SHIPPING_VELOCITY = ["Slow", "Moderate", "Fast"];
const DISTRIBUTION_CHANNELS = ["SEO", "Paid Ads", "Community", "Outbound Sales", "Partnerships", "Content", "Personal Network"];
const AUDIENCE_ACCESS = ["None", "<1k", "1k-10k", "10k+"];
const SALES_EXPERIENCE = ["None", "Some", "Strong"];
const RISK_TOLERANCE = ["Low", "Medium", "High"];
const TIME_TO_REVENUE = ["<3m", "3-6m", "6-12m", "12m+"];
const MOTIVATION_TYPES = ["Financial", "Mission", "Lifestyle", "Technical challenge"];
const COMMITMENT_HORIZON = ["<1y", "1-2y", "3y+"];
const CONFIDENCE_STYLE = ["Conservative", "Balanced", "Aggressive"];
const PRIORITY_DIMENSIONS = ["Market", "Technical", "Distribution", "Founder Fit", "Timing"];

const EMPTY_PROFILE: ProfilePayload = {
  full_name: "",
  role_title: "",
  linkedin_url: null,
  location_city_country: "",
  timezone: "",
  current_stage: "",
  industry_focus: [],
  business_model: "",
  target_market: "",
  team_size: "",
  weekly_hours_available: 20,
  budget_range: "",
  hiring_ability: "",
  cloud_deployment_level: "",
  ai_coding_agents_level: "",
  backend_engineering_level: "",
  product_ux_level: "",
  data_ml_engineering_level: "",
  shipping_velocity: "",
  domain_expertise_level: 3,
  distribution_channels: [],
  audience_access: "",
  sales_experience: "",
  risk_tolerance: "",
  preferred_time_to_revenue: "",
  motivation_type: "",
  commitment_horizon: "",
  regulatory_constraints: false,
  regulatory_constraints_notes: null,
  ip_constraints: false,
  ip_constraints_notes: null,
  geo_legal_constraints: false,
  geo_legal_constraints_notes: null,
  confidence_style: "",
  priority_dimensions: [],
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

function normalizeOptional(value: string): string | null {
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

export function ProfileForm({ initialValue, submitLabel, onSubmit }: ProfileFormProps) {
  const [form, setForm] = useState<ProfilePayload>(initialValue ?? EMPTY_PROFILE);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timezoneStatus, setTimezoneStatus] = useState<string>("Using browser timezone.");
  const detectedTimezone =
    typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone ?? "UTC" : "UTC";

  useEffect(() => {
    if (!form.timezone) {
      setForm((prev) => ({ ...prev, timezone: detectedTimezone }));
    }
  }, [detectedTimezone, form.timezone]);

  useEffect(() => {
    const query = form.location_city_country.trim();
    if (query.length < 3) {
      return;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(async () => {
      try {
        const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query)}&count=1&language=en&format=json`;
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
          setTimezoneStatus("Could not resolve timezone from location.");
          return;
        }

        const payload = (await response.json()) as {
          results?: Array<{ timezone?: string }>;
        };
        const inferred = payload.results?.[0]?.timezone;
        if (!inferred) {
          setTimezoneStatus("No timezone match found for this location.");
          return;
        }

        setForm((prev) => ({ ...prev, timezone: inferred }));
        setTimezoneStatus(`Timezone inferred from location: ${inferred}`);
      } catch {
        setTimezoneStatus("Could not resolve timezone from location.");
      }
    }, 600);

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [form.location_city_country]);

  const isValid = useMemo(() => {
    return (
      Boolean(form.full_name.trim()) &&
      Boolean(form.role_title) &&
      Boolean(form.location_city_country.trim()) &&
      Boolean(form.timezone.trim()) &&
      Boolean(form.current_stage) &&
      form.industry_focus.length > 0 &&
      Boolean(form.business_model) &&
      Boolean(form.target_market) &&
      Boolean(form.team_size) &&
      form.weekly_hours_available >= 1 &&
      form.weekly_hours_available <= 80 &&
      Boolean(form.budget_range) &&
      Boolean(form.hiring_ability) &&
      Boolean(form.cloud_deployment_level) &&
      Boolean(form.ai_coding_agents_level) &&
      Boolean(form.backend_engineering_level) &&
      Boolean(form.product_ux_level) &&
      Boolean(form.data_ml_engineering_level) &&
      Boolean(form.shipping_velocity) &&
      form.domain_expertise_level >= 1 &&
      form.domain_expertise_level <= 5 &&
      form.distribution_channels.length > 0 &&
      Boolean(form.audience_access) &&
      Boolean(form.sales_experience) &&
      Boolean(form.risk_tolerance) &&
      Boolean(form.preferred_time_to_revenue) &&
      Boolean(form.motivation_type) &&
      Boolean(form.commitment_horizon) &&
      Boolean(form.confidence_style) &&
      form.priority_dimensions.length === 2
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
        full_name: form.full_name.trim(),
        location_city_country: form.location_city_country.trim(),
        timezone: form.timezone.trim(),
        linkedin_url: normalizeOptional(form.linkedin_url ?? ""),
        regulatory_constraints_notes: normalizeOptional(form.regulatory_constraints_notes ?? ""),
        ip_constraints_notes: normalizeOptional(form.ip_constraints_notes ?? ""),
        geo_legal_constraints_notes: normalizeOptional(form.geo_legal_constraints_notes ?? ""),
      });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to save profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="profile-form">
      <section className="profile-section">
        <h3>Founder Basics</h3>
        <label>
          Full name
          <input
            type="text"
            value={form.full_name}
            onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))}
            required
          />
        </label>
        <label>
          Role / title
          <select
            value={form.role_title}
            onChange={(event) => setForm((prev) => ({ ...prev, role_title: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {ROLE_TITLES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          LinkedIn URL (optional)
          <input
            type="url"
            placeholder="https://linkedin.com/in/..."
            value={form.linkedin_url ?? ""}
            onChange={(event) => setForm((prev) => ({ ...prev, linkedin_url: event.target.value }))}
          />
        </label>
        <label>
          Location (city, country)
          <input
            type="text"
            placeholder="New York, USA"
            value={form.location_city_country}
            onChange={(event) => setForm((prev) => ({ ...prev, location_city_country: event.target.value }))}
            required
          />
        </label>
        <label>
          Timezone
          <input
            placeholder="Timezone auto-detected from location"
            value={form.timezone}
            readOnly
            required
          />
        </label>
        <p className="form-note">
          {timezoneStatus} Browser default: <strong>{detectedTimezone}</strong>
        </p>
      </section>

      <section className="profile-section">
        <h3>Startup Context</h3>
        <label>
          Current stage
          <select
            value={form.current_stage}
            onChange={(event) => setForm((prev) => ({ ...prev, current_stage: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {CURRENT_STAGES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <div>
          <h4>Industry focus</h4>
          <div className="pill-grid">
            {INDUSTRY_FOCUS.map((option) => (
              <label key={option} className="checkbox-pill">
                <input
                  type="checkbox"
                  checked={form.industry_focus.includes(option)}
                  onChange={() =>
                    setForm((prev) => ({
                      ...prev,
                      industry_focus: toggleItem(prev.industry_focus, option),
                    }))
                  }
                />
                <span>{option}</span>
              </label>
            ))}
          </div>
        </div>
        <label>
          Business model
          <select
            value={form.business_model}
            onChange={(event) => setForm((prev) => ({ ...prev, business_model: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {BUSINESS_MODELS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <fieldset>
          <legend>Target market</legend>
          <div className="inline-options">
            {TARGET_MARKETS.map((option) => (
              <label key={option}>
                <input
                  type="radio"
                  name="target_market"
                  value={option}
                  checked={form.target_market === option}
                  onChange={(event) => setForm((prev) => ({ ...prev, target_market: event.target.value }))}
                />
                {option}
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      <section className="profile-section">
        <h3>Execution Capacity</h3>
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
          Weekly hours available ({form.weekly_hours_available})
          <input
            type="range"
            min={1}
            max={80}
            value={form.weekly_hours_available}
            onChange={(event) =>
              setForm((prev) => ({
                ...prev,
                weekly_hours_available: Number.parseInt(event.target.value, 10),
              }))
            }
          />
        </label>
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
          Hiring ability (next 6 months)
          <select
            value={form.hiring_ability}
            onChange={(event) => setForm((prev) => ({ ...prev, hiring_ability: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {HIRING_ABILITY.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="profile-section">
        <h3>Technical Capability</h3>
        <label>
          Cloud & deployment
          <select
            value={form.cloud_deployment_level}
            onChange={(event) => setForm((prev) => ({ ...prev, cloud_deployment_level: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {LEVEL_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          AI coding agents
          <select
            value={form.ai_coding_agents_level}
            onChange={(event) => setForm((prev) => ({ ...prev, ai_coding_agents_level: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {LEVEL_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Backend engineering
          <select
            value={form.backend_engineering_level}
            onChange={(event) => setForm((prev) => ({ ...prev, backend_engineering_level: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {LEVEL_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Product & UX execution
          <select
            value={form.product_ux_level}
            onChange={(event) => setForm((prev) => ({ ...prev, product_ux_level: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {LEVEL_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Data / ML engineering
          <select
            value={form.data_ml_engineering_level}
            onChange={(event) => setForm((prev) => ({ ...prev, data_ml_engineering_level: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {LEVEL_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <fieldset>
          <legend>Shipping velocity</legend>
          <div className="inline-options">
            {SHIPPING_VELOCITY.map((option) => (
              <label key={option}>
                <input
                  type="radio"
                  name="shipping_velocity"
                  value={option}
                  checked={form.shipping_velocity === option}
                  onChange={(event) => setForm((prev) => ({ ...prev, shipping_velocity: event.target.value }))}
                />
                {option}
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      <section className="profile-section">
        <h3>Go-to-Market Strength</h3>
        <label>
          Domain expertise level ({form.domain_expertise_level}/5)
          <input
            type="range"
            min={1}
            max={5}
            value={form.domain_expertise_level}
            onChange={(event) =>
              setForm((prev) => ({
                ...prev,
                domain_expertise_level: Number.parseInt(event.target.value, 10),
              }))
            }
          />
        </label>
        <div>
          <h4>Distribution channels available</h4>
          <div className="pill-grid">
            {DISTRIBUTION_CHANNELS.map((option) => (
              <label key={option} className="checkbox-pill">
                <input
                  type="checkbox"
                  checked={form.distribution_channels.includes(option)}
                  onChange={() =>
                    setForm((prev) => ({
                      ...prev,
                      distribution_channels: toggleItem(prev.distribution_channels, option),
                    }))
                  }
                />
                <span>{option}</span>
              </label>
            ))}
          </div>
        </div>
        <label>
          Audience access
          <select
            value={form.audience_access}
            onChange={(event) => setForm((prev) => ({ ...prev, audience_access: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {AUDIENCE_ACCESS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sales experience
          <select
            value={form.sales_experience}
            onChange={(event) => setForm((prev) => ({ ...prev, sales_experience: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {SALES_EXPERIENCE.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="profile-section">
        <h3>Founder Fit and Risk Profile</h3>
        <fieldset>
          <legend>Risk tolerance</legend>
          <div className="inline-options">
            {RISK_TOLERANCE.map((option) => (
              <label key={option}>
                <input
                  type="radio"
                  name="risk_tolerance"
                  value={option}
                  checked={form.risk_tolerance === option}
                  onChange={(event) => setForm((prev) => ({ ...prev, risk_tolerance: event.target.value }))}
                />
                {option}
              </label>
            ))}
          </div>
        </fieldset>
        <label>
          Preferred time-to-revenue
          <select
            value={form.preferred_time_to_revenue}
            onChange={(event) => setForm((prev) => ({ ...prev, preferred_time_to_revenue: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {TIME_TO_REVENUE.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Motivation type
          <select
            value={form.motivation_type}
            onChange={(event) => setForm((prev) => ({ ...prev, motivation_type: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {MOTIVATION_TYPES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Commitment horizon
          <select
            value={form.commitment_horizon}
            onChange={(event) => setForm((prev) => ({ ...prev, commitment_horizon: event.target.value }))}
            required
          >
            <option value="">Select...</option>
            {COMMITMENT_HORIZON.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="profile-section">
        <h3>Constraints</h3>
        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={form.regulatory_constraints}
            onChange={(event) => setForm((prev) => ({ ...prev, regulatory_constraints: event.target.checked }))}
          />
          Regulatory constraints relevant
        </label>
        {form.regulatory_constraints ? (
          <label>
            Regulatory notes
            <textarea
              rows={3}
              value={form.regulatory_constraints_notes ?? ""}
              onChange={(event) => setForm((prev) => ({ ...prev, regulatory_constraints_notes: event.target.value }))}
            />
          </label>
        ) : null}

        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={form.ip_constraints}
            onChange={(event) => setForm((prev) => ({ ...prev, ip_constraints: event.target.checked }))}
          />
          Non-compete / IP constraints
        </label>
        {form.ip_constraints ? (
          <label>
            IP constraint notes
            <textarea
              rows={3}
              value={form.ip_constraints_notes ?? ""}
              onChange={(event) => setForm((prev) => ({ ...prev, ip_constraints_notes: event.target.value }))}
            />
          </label>
        ) : null}

        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={form.geo_legal_constraints}
            onChange={(event) => setForm((prev) => ({ ...prev, geo_legal_constraints: event.target.checked }))}
          />
          Geographic / legal constraints
        </label>
        {form.geo_legal_constraints ? (
          <label>
            Geographic/legal notes
            <textarea
              rows={3}
              value={form.geo_legal_constraints_notes ?? ""}
              onChange={(event) => setForm((prev) => ({ ...prev, geo_legal_constraints_notes: event.target.value }))}
            />
          </label>
        ) : null}
      </section>

      <section className="profile-section">
        <h3>Evaluation Preferences</h3>
        <fieldset>
          <legend>Confidence style</legend>
          <div className="inline-options">
            {CONFIDENCE_STYLE.map((option) => (
              <label key={option}>
                <input
                  type="radio"
                  name="confidence_style"
                  value={option}
                  checked={form.confidence_style === option}
                  onChange={(event) => setForm((prev) => ({ ...prev, confidence_style: event.target.value }))}
                />
                {option}
              </label>
            ))}
          </div>
        </fieldset>
        <div>
          <h4>Priority dimensions (pick exactly 2)</h4>
          <div className="pill-grid">
            {PRIORITY_DIMENSIONS.map((option) => {
              const checked = form.priority_dimensions.includes(option);
              const maxed = !checked && form.priority_dimensions.length >= 2;
              return (
                <label key={option} className="checkbox-pill">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={maxed}
                    onChange={() =>
                      setForm((prev) => ({
                        ...prev,
                        priority_dimensions: toggleItem(prev.priority_dimensions, option),
                      }))
                    }
                  />
                  <span>{option}</span>
                </label>
              );
            })}
          </div>
        </div>
      </section>

      {error ? <p className="form-error">{error}</p> : null}
      {!isValid ? <p className="form-note">Complete all required fields to continue.</p> : null}

      <button type="submit" disabled={!isValid || saving}>
        {saving ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}
