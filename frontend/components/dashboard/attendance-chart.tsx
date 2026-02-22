"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import type { AttendanceTrendPoint } from "@/types";

interface AttendanceChartProps {
  data: AttendanceTrendPoint[];
}

export function AttendanceChart({ data }: AttendanceChartProps) {
  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            Attendance Trend
          </CardTitle>
          <CardDescription>
            Daily attendance over the last 30 days
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-[250px] items-center justify-center rounded-lg border border-dashed">
            <p className="text-sm text-muted-foreground">
              No attendance data available
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold">
          Attendance Trend
        </CardTitle>
        <CardDescription>
          Daily attendance over the last 30 days
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 5, right: 10, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                tickFormatter={(v: string) => v.slice(5)}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null;
                  return (
                    <div className="rounded-lg border bg-background p-3 shadow-md">
                      <p className="mb-1 text-sm font-medium">{label}</p>
                      {payload.map((entry) => (
                        <p
                          key={entry.dataKey as string}
                          className="text-xs text-muted-foreground"
                        >
                          {entry.name}: {entry.value}
                        </p>
                      ))}
                    </div>
                  );
                }}
              />
              <Area
                type="monotone"
                dataKey="present"
                stackId="1"
                stroke="hsl(var(--chart-1))"
                fill="hsl(var(--chart-1))"
                fillOpacity={0.4}
                name="Present"
              />
              <Area
                type="monotone"
                dataKey="late"
                stackId="1"
                stroke="hsl(var(--chart-3))"
                fill="hsl(var(--chart-3))"
                fillOpacity={0.4}
                name="Late"
              />
              <Area
                type="monotone"
                dataKey="absent"
                stackId="1"
                stroke="hsl(var(--chart-5))"
                fill="hsl(var(--chart-5))"
                fillOpacity={0.4}
                name="Absent"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
