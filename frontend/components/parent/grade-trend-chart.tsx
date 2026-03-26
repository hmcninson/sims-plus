"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GradeTrend, CurriculumType } from "@/types/parent.type";

interface GradeTrendChartProps {
  trend: GradeTrend[];
  curriculumType: CurriculumType | undefined;
}

/**
 * Returns the Y-axis configuration based on curriculum type.
 */
function getYAxisConfig(curriculum: CurriculumType | undefined): {
  domain: [number, number];
  label: string;
  dataKey: string;
} {
  switch (curriculum) {
    case "american":
      return { domain: [0, 4.0], label: "GPA", dataKey: "value" };
    case "ib":
      return { domain: [0, 45], label: "IB Points", dataKey: "value" };
    case "french":
      return { domain: [0, 20], label: "Average (0-20)", dataKey: "value" };
    default:
      // GES, Cambridge, Edexcel, Montessori, custom — use percentage average
      return { domain: [0, 100], label: "Average Score (%)", dataKey: "value" };
  }
}

/**
 * Formats a tooltip value based on the curriculum type and trend entry.
 */
function formatTrendTooltipValue(
  entry: GradeTrend,
  curriculum: CurriculumType | undefined
): string {
  if (entry.value == null) return "N/A";

  switch (curriculum) {
    case "american":
      return `GPA: ${entry.value.toFixed(2)}`;
    case "ib":
      return `Points: ${entry.value}/45`;
    case "french":
      return `Average: ${entry.value.toFixed(1)}/20`;
    default:
      return `Average: ${entry.value.toFixed(1)}%`;
  }
}

/**
 * Curriculum-aware grade trend line chart.
 *
 * Adapts the Y-axis scale and tooltip labels based on the curriculum:
 * - american: 0-4.0 GPA scale
 * - ib: 0-45 IB points
 * - french: 0-20 French scale
 * - default: 0-100 percentage
 *
 * Falls back to the legacy `average` field when `value` is not present,
 * ensuring backward compatibility with existing GES-only data.
 */
export function GradeTrendChart({
  trend,
  curriculumType,
}: GradeTrendChartProps) {
  if (trend.length < 2) return null;

  const { domain, label, dataKey } = getYAxisConfig(curriculumType);

  // Normalize data: use `value` if available, else fall back to `average`
  const chartData = trend.map((t) => ({
    ...t,
    value: t.value ?? t.average,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Grade Trend</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid
                strokeDasharray="3 3"
                className="stroke-muted"
              />
              <XAxis
                dataKey="term_name"
                className="text-xs"
                tick={{ fontSize: 12 }}
              />
              <YAxis
                domain={domain}
                className="text-xs"
                tick={{ fontSize: 12 }}
                label={{
                  value: label,
                  angle: -90,
                  position: "insideLeft",
                  style: { fontSize: 11, fill: "var(--muted-foreground)" },
                }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as GradeTrend & {
                    value: number;
                  };
                  return (
                    <div className="rounded-lg border bg-background p-3 shadow-md">
                      <p className="text-sm font-medium">{d.term_name}</p>
                      <p className="text-sm text-muted-foreground">
                        {formatTrendTooltipValue(d, curriculumType)}
                      </p>
                      {d.position != null && d.class_size != null && (
                        <p className="text-sm text-muted-foreground">
                          Position: {d.position}/{d.class_size}
                        </p>
                      )}
                      {d.label && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {d.label}
                        </p>
                      )}
                    </div>
                  );
                }}
              />
              <Line
                type="monotone"
                dataKey={dataKey}
                stroke="var(--primary)"
                strokeWidth={2}
                dot={{ fill: "var(--primary)", r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
