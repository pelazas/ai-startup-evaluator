"use client";

import { useMemo, useState } from "react";

import { DimensionKey } from "@/lib/evaluations";

type RadarChartProps = {
  scores: Record<DimensionKey, number | null>;
};

const DIMENSIONS: Array<{ key: DimensionKey; label: string }> = [
  { key: "market", label: "Market" },
  { key: "technical", label: "Technical" },
  { key: "distribution", label: "Distribution" },
  { key: "founder_fit", label: "Founder Fit" },
  { key: "timing", label: "Timing" },
];

function toPoint(index: number, value: number, total: number, radius: number, center: number) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const scaled = (Math.max(0, Math.min(100, value)) / 100) * radius;
  return {
    x: center + Math.cos(angle) * scaled,
    y: center + Math.sin(angle) * scaled,
  };
}

export function RadarChart({ scores }: RadarChartProps) {
  const [hover, setHover] = useState<{ label: string; value: number | null; x: number; y: number } | null>(null);
  const size = 340;
  const center = size / 2;
  const radius = 120;

  const polygon = useMemo(() => {
    return DIMENSIONS.map((dimension, index) => {
      const value = scores[dimension.key];
      return toPoint(index, value ?? 0, DIMENSIONS.length, radius, center);
    });
  }, [scores]);

  const points = polygon.map((point) => `${point.x},${point.y}`).join(" ");

  return (
    <div className="radar-wrap">
      <svg viewBox={`0 0 ${size} ${size}`} className="radar-svg" role="img" aria-label="Dimension radar chart">
        {[20, 40, 60, 80, 100].map((level) => (
          <polygon
            key={level}
            points={DIMENSIONS.map((_, index) => {
              const p = toPoint(index, level, DIMENSIONS.length, radius, center);
              return `${p.x},${p.y}`;
            }).join(" ")}
            className="radar-grid"
          />
        ))}

        {DIMENSIONS.map((dimension, index) => {
          const axis = toPoint(index, 100, DIMENSIONS.length, radius, center);
          return <line key={dimension.key} x1={center} y1={center} x2={axis.x} y2={axis.y} className="radar-axis" />;
        })}

        <polygon
          points={points}
          className={Object.values(scores).some((value) => value === null) ? "radar-shape-partial" : "radar-shape"}
        />

        {DIMENSIONS.map((dimension, index) => {
          const value = scores[dimension.key];
          const point = toPoint(index, value ?? 0, DIMENSIONS.length, radius, center);
          const labelPoint = toPoint(index, 112, DIMENSIONS.length, radius, center);
          const unavailable = value === null;
          return (
            <g key={dimension.key}>
              <circle
                cx={point.x}
                cy={point.y}
                r={5}
                className={unavailable ? "radar-point-unavailable" : "radar-point"}
                onMouseEnter={() => setHover({ label: dimension.label, value, x: point.x, y: point.y })}
                onMouseLeave={() => setHover(null)}
              />
              <text x={labelPoint.x} y={labelPoint.y} className="radar-label">
                {dimension.label}
              </text>
            </g>
          );
        })}
      </svg>
      {hover ? (
        <div className="radar-tooltip" style={{ left: hover.x, top: hover.y }}>
          {hover.label}: {hover.value === null ? "Unavailable" : hover.value}
        </div>
      ) : null}
    </div>
  );
}

