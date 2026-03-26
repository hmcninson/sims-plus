"use client";

import {
  Bar,
  BarChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";

interface PipelineChartProps {
  data: Record<string, number>;
}

const PIPELINE_ORDER = [
  "submitted",
  "under_review",
  "shortlisted",
  "exam_scheduled",
  "exam_completed",
  "offered",
  "accepted",
  "enrolled",
  "waitlisted",
  "rejected",
  "withdrawn",
];

const STATUS_COLORS: Record<string, string> = {
  submitted: "#3b82f6",
  under_review: "#8b5cf6",
  shortlisted: "#06b6d4",
  exam_scheduled: "#f59e0b",
  exam_completed: "#eab308",
  offered: "#10b981",
  accepted: "#22c55e",
  enrolled: "#059669",
  waitlisted: "#6b7280",
  rejected: "#ef4444",
  withdrawn: "#9ca3af",
};

function formatStatusLabel(status: string): string {
  return status
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function PipelineChart({ data }: PipelineChartProps) {
  const chartData = PIPELINE_ORDER.filter((s) => (data[s] ?? 0) > 0).map(
    (status) => ({
      status: formatStatusLabel(status),
      count: data[status] ?? 0,
      fill: STATUS_COLORS[status] ?? "#6b7280",
    })
  );

  if (chartData.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
        No application data yet
      </div>
    );
  }

  return (
    <div className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ left: 20 }}>
          <XAxis type="number" />
          <YAxis
            type="category"
            dataKey="status"
            width={120}
            tick={{ fontSize: 12 }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const item = payload[0];
              return (
                <div className="rounded-lg border bg-background p-3 shadow-md">
                  <p className="text-sm font-medium">{item.payload.status}</p>
                  <p className="text-sm text-muted-foreground">
                    {item.value} application{item.value !== 1 ? "s" : ""}
                  </p>
                </div>
              );
            }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]}>
            {chartData.map((entry, index) => (
              <Cell key={index} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
