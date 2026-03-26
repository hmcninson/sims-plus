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
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SourceEffectivenessRow } from "@/types/admissions.type";

interface LeadSourceChartProps {
  sources: SourceEffectivenessRow[];
}

export function LeadSourceChart({ sources }: LeadSourceChartProps) {
  if (sources.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lead Source Effectiveness</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[300px] items-center justify-center text-muted-foreground">
            No lead source data available
          </div>
        </CardContent>
      </Card>
    );
  }

  const data = sources.map((s) => ({
    name: s.source || "Unknown",
    inquiries: s.inquiry_count,
    applications: s.application_count,
    enrolled: s.enrollment_count,
    conversionRate: s.inquiry_to_enrollment_rate,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Lead Source Effectiveness</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
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
                  const conversionRate = (
                    payload[0]?.payload as Record<string, number>
                  )?.conversionRate;
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
                      {conversionRate != null && (
                        <p className="mt-1 text-xs font-medium text-muted-foreground">
                          Conversion: {conversionRate.toFixed(1)}%
                        </p>
                      )}
                    </div>
                  );
                }}
              />
              <Legend />
              <Bar
                dataKey="inquiries"
                name="Inquiries"
                fill="hsl(221, 83%, 53%)"
                radius={[2, 2, 0, 0]}
              />
              <Bar
                dataKey="applications"
                name="Applications"
                fill="hsl(38, 92%, 50%)"
                radius={[2, 2, 0, 0]}
              />
              <Bar
                dataKey="enrolled"
                name="Enrolled"
                fill="hsl(142, 71%, 45%)"
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
