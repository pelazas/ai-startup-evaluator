"use client";

import { useMemo, useState } from "react";

import { KeywordTrendSeries } from "@/lib/evaluations";

type KeywordTrendsChartProps = {
  series: KeywordTrendSeries;
};

function compactVolume(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return `${value}`;
}

function formatMonth(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

export function KeywordTrendsChart({ series }: KeywordTrendsChartProps) {
  const chartWidth = 680;
  const chartHeight = 260;
  const padding = 30;
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const points = useMemo(() => {
    const raw = series.points;
    if (!raw.length) {
      return { mapped: [], path: "", areaPath: "", maxValue: 1 };
    }
    const maxValue = Math.max(1, ...raw.map((item) => item.value));
    const usableWidth = chartWidth - padding * 2;
    const usableHeight = chartHeight - padding * 2;
    const mapped = raw.map((item, index) => {
      const x = padding + (index / Math.max(1, raw.length - 1)) * usableWidth;
      const y = padding + (1 - item.value / maxValue) * usableHeight;
      return { x, y, date: item.date, value: item.value };
    });
    const path = mapped.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
    const areaPath = `${path} L ${padding + usableWidth} ${padding + usableHeight} L ${padding} ${padding + usableHeight} Z`;
    return { mapped, path, areaPath, maxValue };
  }, [series.points]);

  const activePoint = hoveredIndex !== null ? points.mapped[hoveredIndex] : null;
  const growthLabel =
    series.growth_percent === null
      ? "N/A"
      : `${series.growth_percent > 0 ? "+" : ""}${series.growth_percent}%`;

  return (
    <div className="keyword-trends-chart-wrap">
      <div className="keyword-trends-legend">
        <div className="keyword-trends-chip keyword-trends-chip-primary">
          <span className="dot" />
          <strong>{compactVolume(series.volume)}</strong>
          <span>Total Volume</span>
        </div>
        <div className="keyword-trends-chip">
          <strong>{compactVolume(series.latest_volume ?? 0)}</strong>
          <span>Latest Month</span>
        </div>
        <div className="keyword-trends-chip">
          <strong className={series.growth_percent !== null && series.growth_percent >= 0 ? "positive-growth" : ""}>{growthLabel}</strong>
          <span>Growth</span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        className="keyword-trends-chart"
        role="img"
        aria-label={`Web trend volume for ${series.keyword}`}
      >
        <line x1={padding} y1={chartHeight - padding} x2={chartWidth - padding} y2={chartHeight - padding} className="trend-axis" />
        <line x1={padding} y1={padding} x2={padding} y2={chartHeight - padding} className="trend-axis" />
        {points.areaPath ? <path d={points.areaPath} className="trend-area" /> : null}
        {points.path ? <path d={points.path} className="trend-line" /> : null}

        {points.mapped.map((point, index) => (
          <g key={`${point.date}-${index}`}>
            <circle
              cx={point.x}
              cy={point.y}
              r={hoveredIndex === index ? 5 : 3}
              className="trend-point"
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
            />
          </g>
        ))}

        {activePoint ? (
          <g>
            <line x1={activePoint.x} y1={padding} x2={activePoint.x} y2={chartHeight - padding} className="trend-cursor" />
            <rect x={activePoint.x + 8} y={activePoint.y - 36} width={106} height={32} rx={6} className="trend-tooltip-bg" />
            <text x={activePoint.x + 14} y={activePoint.y - 22} className="trend-tooltip-text">
              {formatMonth(activePoint.date)}
            </text>
            <text x={activePoint.x + 14} y={activePoint.y - 10} className="trend-tooltip-text trend-tooltip-value">
              {activePoint.value} mentions
            </text>
          </g>
        ) : null}
      </svg>
    </div>
  );
}
