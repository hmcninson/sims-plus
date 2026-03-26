"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { ClassCapacityRow } from "@/types/admissions.type";

interface CapacityChartProps {
  classes: ClassCapacityRow[];
}

export function CapacityChart({ classes }: CapacityChartProps) {
  const data = classes.map((c) => ({
    name: c.class_name,
    target: c.target ?? 0,
    enrolled: c.current_enrolled,
    capacity: c.capacity ?? 0,
    pipeline: c.applications_in_pipeline,
  }));

  if (data.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-muted-foreground">
        No class data available
      </div>
    );
  }

  return (
    <div className="h-[350px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 12 }}
            className="fill-muted-foreground"
          />
          <YAxis tick={{ fontSize: 12 }} className="fill-muted-foreground" />
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              return (
                <div className="rounded-lg border bg-background p-3 shadow-md">
                  <p className="mb-1 font-medium">{label}</p>
                  {payload.map((entry) => (
                    <p
                      key={entry.name}
                      className="text-sm"
                      style={{ color: entry.color }}
                    >
                      {entry.name}: {entry.value}
                    </p>
                  ))}
                </div>
              );
            }}
          />
          <Legend />
          <Bar dataKey="capacity" name="Capacity" fill="hsl(var(--muted-foreground))" opacity={0.3} radius={[2, 2, 0, 0]} />
          <Bar dataKey="target" name="Target" fill="hsl(var(--primary))" opacity={0.6} radius={[2, 2, 0, 0]} />
          <Bar dataKey="enrolled" name="Enrolled" radius={[2, 2, 0, 0]}>
            {data.map((entry, index) => {
              const isOverTarget =
                entry.target > 0 && entry.enrolled > entry.target;
              const isOverCapacity =
                entry.capacity > 0 && entry.enrolled > entry.capacity;
              let fill = "hsl(142, 71%, 45%)"; // green
              if (isOverCapacity) {
                fill = "hsl(0, 84%, 60%)"; // red
              } else if (isOverTarget) {
                fill = "hsl(38, 92%, 50%)"; // amber
              }
              return <Cell key={index} fill={fill} />;
            })}
          </Bar>
          <Bar dataKey="pipeline" name="Pipeline" fill="hsl(var(--primary))" opacity={0.3} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
