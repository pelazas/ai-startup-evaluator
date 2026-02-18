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
  const month = parsed.toLocaleDateString(undefined, { month: "short" });
  const year = parsed.toLocaleDateString(undefined, { year: "2-digit" });
  return `${month} ${year}'`;
}

export function KeywordTrendsChart({ series }: KeywordTrendsChartProps) {
  const chartWidth = 620;
  const chartHeight = 305;
  const paddingX = 24;
  const paddingTop = 16;
  const paddingBottom = 32;
  const usableWidth = chartWidth - paddingX * 2;
  const usableHeight = chartHeight - paddingTop - paddingBottom;
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const points = useMemo(() => {
    const raw = series.points;
    if (!raw.length) {
      return { mapped: [], path: "", maxValue: 1 };
    }
    const maxValue = Math.max(1, ...raw.map((item) => item.value));
    const mapped = raw.map((item, index) => {
      const x = paddingX + (index / Math.max(1, raw.length - 1)) * usableWidth;
      const y = paddingTop + (1 - item.value / maxValue) * usableHeight;
      return { x, y, date: item.date, value: item.value };
    });
    const path = mapped.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
    return { mapped, path, maxValue };
  }, [series.points]);

  const activePoint = hoveredIndex !== null ? points.mapped[hoveredIndex] : null;
  const tooltipWidth = 116;
  const tooltipHeight = 32;
  const tooltipPadding = 8;
  const tooltipX = activePoint
    ? activePoint.x > chartWidth - tooltipWidth - paddingX
      ? activePoint.x - tooltipWidth - tooltipPadding
      : activePoint.x + tooltipPadding
    : 0;
  const tooltipY = activePoint
    ? activePoint.y - tooltipHeight - 4 < paddingTop
      ? Math.min(chartHeight - paddingBottom - tooltipHeight - 2, activePoint.y + 10)
      : activePoint.y - tooltipHeight - 4
    : 0;
  const growthLabel =
    series.growth_percent === null
      ? "N/A"
      : `${series.growth_percent > 0 ? "+" : ""}${series.growth_percent}%`;
  const horizontalGridSteps = 5;
  const horizontalLines = Array.from({ length: horizontalGridSteps }, (_, index) => {
    const ratio = index / Math.max(1, horizontalGridSteps - 1);
    const y = paddingTop + ratio * usableHeight;
    return { key: `h-${index}`, y };
  });

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
          <strong
            className={
              series.growth_percent === null
                ? ""
                : series.growth_percent >= 0
                  ? "positive-growth"
                  : "negative-growth"
            }
          >
            {growthLabel}
          </strong>
          <span>Growth</span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        className="keyword-trends-chart"
        role="img"
        aria-label={`Web trend volume for ${series.keyword}`}
      >
        {horizontalLines.map((line) => (
          <line
            key={line.key}
            x1={paddingX}
            y1={line.y}
            x2={chartWidth - paddingX}
            y2={line.y}
            className="trend-grid-line"
          />
        ))}
        {points.mapped.map((point, index) => (
          <line
            key={`v-grid-${index}`}
            x1={point.x}
            y1={paddingTop}
            x2={point.x}
            y2={chartHeight - paddingBottom}
            className="trend-grid-line trend-grid-line-vertical"
          />
        ))}
        <line
          x1={paddingX}
          y1={chartHeight - paddingBottom}
          x2={chartWidth - paddingX}
          y2={chartHeight - paddingBottom}
          className="trend-axis"
        />
        <line x1={paddingX} y1={paddingTop} x2={paddingX} y2={chartHeight - paddingBottom} className="trend-axis" />
        {points.path ? <path d={points.path} className="trend-line" /> : null}

        {points.mapped.map((point, idx) => {
          return (
            <g key={`tick-${idx}`} transform={`translate(${point.x}, ${chartHeight - paddingBottom + 2})`}>
              <text className="trend-x-tick" transform="rotate(90)">
                {formatMonth(point.date)}
              </text>
            </g>
          );
        })}

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
            <line
              x1={activePoint.x}
              y1={paddingTop}
              x2={activePoint.x}
              y2={chartHeight - paddingBottom}
              className="trend-cursor"
            />
            <rect x={tooltipX} y={tooltipY} width={tooltipWidth} height={tooltipHeight} rx={6} className="trend-tooltip-bg" />
            <text x={tooltipX + 8} y={tooltipY + 14} className="trend-tooltip-text">
              {formatMonth(activePoint.date)}
            </text>
            <text x={tooltipX + 8} y={tooltipY + 26} className="trend-tooltip-text trend-tooltip-value">
              {activePoint.value} mentions
            </text>
          </g>
        ) : null}
      </svg>
    </div>
  );
}
