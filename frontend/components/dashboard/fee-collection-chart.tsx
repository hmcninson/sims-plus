"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

import type { FeeCollectionTrendPoint } from "@/types";

interface FeeCollectionChartProps {
  data: FeeCollectionTrendPoint[];
}

export function FeeCollectionChart({ data }: FeeCollectionChartProps) {
  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            Fee Collection
          </CardTitle>
          <CardDescription>Monthly billed vs collected</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-[250px] items-center justify-center rounded-lg border border-dashed">
            <p className="text-sm text-muted-foreground">
              No finance data available
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
          Fee Collection
        </CardTitle>
        <CardDescription>Monthly billed vs collected</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 5, right: 10, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
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
                          {entry.name}: GHS{" "}
                          {(entry.value as number).toLocaleString()}
                        </p>
                      ))}
                    </div>
                  );
                }}
              />
              <Legend />
              <Bar
                dataKey="billed"
                fill="hsl(var(--chart-2))"
                name="Billed"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="collected"
                fill="hsl(var(--chart-1))"
                name="Collected"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
