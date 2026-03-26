"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { YearTrendRow } from "@/types/admissions.type";

interface TrendChartProps {
  years: YearTrendRow[];
}

const LINE_COLORS = [
  "hsl(221, 83%, 53%)",
  "hsl(142, 71%, 45%)",
  "hsl(38, 92%, 50%)",
  "hsl(280, 67%, 60%)",
  "hsl(0, 84%, 60%)",
];

export function TrendChart({ years }: TrendChartProps) {
  if (years.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Enrollment Trends</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[300px] items-center justify-center text-muted-foreground">
            No trend data available
          </div>
        </CardContent>
      </Card>
    );
  }

  // Collect all unique class names across all years
  const classNames = new Set<string>();
  years.forEach((y) => y.by_class.forEach((c) => classNames.add(c.class_name)));

  // Build chart data: each row is a year, with total + per-class columns
  const data = years.map((year) => {
    const row: Record<string, string | number> = {
      year: year.academic_year_name,
      total: year.total_enrolled,
    };
    year.by_class.forEach((c) => {
      row[c.class_name] = c.count;
    });
    return row;
  });

  const classNameArray = Array.from(classNames);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Enrollment Trends</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="year"
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
              <Line
                type="monotone"
                dataKey="total"
                name="Total"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                dot={{ r: 4 }}
              />
              {classNameArray.map((name, idx) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  name={name}
                  stroke={LINE_COLORS[idx % LINE_COLORS.length]}
                  strokeWidth={1}
                  strokeDasharray="5 5"
                  dot={{ r: 3 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
