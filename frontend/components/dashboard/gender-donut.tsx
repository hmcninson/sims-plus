"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";

import type { GenderDistribution } from "@/types";

interface GenderDonutProps {
  data: GenderDistribution | null;
}

const COLORS = ["hsl(var(--chart-1))", "hsl(var(--chart-4))"];

export function GenderDonut({ data }: GenderDonutProps) {
  if (!data || (data.male === 0 && data.female === 0)) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            Gender Distribution
          </CardTitle>
          <CardDescription>Student breakdown by gender</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-[200px] items-center justify-center rounded-lg border border-dashed">
            <p className="text-sm text-muted-foreground">No student data</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const chartData = [
    { name: "Male", value: data.male },
    { name: "Female", value: data.female },
  ];
  const total = data.male + data.female;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold">
          Gender Distribution
        </CardTitle>
        <CardDescription>
          {total.toLocaleString()} total students
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <RechartsPieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={4}
                dataKey="value"
              >
                {chartData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const entry = payload[0];
                  return (
                    <div className="rounded-lg border bg-background p-3 shadow-md">
                      <p className="text-sm font-medium">{entry.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {(entry.value as number).toLocaleString()} students
                      </p>
                    </div>
                  );
                }}
              />
              <Legend />
            </RechartsPieChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
