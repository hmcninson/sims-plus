"use client";

import {
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AttritionResponse } from "@/types/admissions.type";

interface AttritionReportProps {
  data: AttritionResponse;
}

const PIE_COLORS = [
  "hsl(0, 84%, 60%)",
  "hsl(38, 92%, 50%)",
  "hsl(221, 83%, 53%)",
  "hsl(142, 71%, 45%)",
  "hsl(280, 67%, 60%)",
  "hsl(160, 60%, 45%)",
  "hsl(330, 70%, 55%)",
];

export function AttritionReport({ data }: AttritionReportProps) {
  const allReasons = [
    ...data.withdrawal_reasons.map((r) => ({
      name: r.reason || "Unspecified",
      value: r.count,
      category: "Withdrawn",
    })),
    ...data.not_returning_reasons.map((r) => ({
      name: r.reason || "Unspecified",
      value: r.count,
      category: "Not Returning",
    })),
  ];

  const isEmpty = data.total_attrition === 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Attrition Analysis</CardTitle>
      </CardHeader>
      <CardContent>
        {isEmpty ? (
          <div className="flex h-[200px] items-center justify-center text-muted-foreground">
            No attrition data available
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary stats */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
              <div className="rounded-lg border p-3">
                <p className="text-2xl font-bold text-red-600">{data.total_attrition}</p>
                <p className="text-xs text-muted-foreground">Total Attrition</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-2xl font-bold">{data.withdrawn_count}</p>
                <p className="text-xs text-muted-foreground">Withdrawn</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-2xl font-bold">{data.not_returning_count}</p>
                <p className="text-xs text-muted-foreground">Not Returning</p>
              </div>
            </div>

            {/* Pie chart */}
            {allReasons.length > 0 && (
              <div className="h-[250px]">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPieChart>
                    <Pie
                      data={allReasons}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      nameKey="name"
                      label={({ name, percent }) =>
                        `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`
                      }
                    >
                      {allReasons.map((_, index) => (
                        <Cell
                          key={index}
                          fill={PIE_COLORS[index % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const item = payload[0].payload as {
                          name: string;
                          value: number;
                          category: string;
                        };
                        return (
                          <div className="rounded-lg border bg-background p-3 shadow-md">
                            <p className="font-medium">{item.name}</p>
                            <p className="text-sm">Count: {item.value}</p>
                            <p className="text-xs text-muted-foreground">
                              {item.category}
                            </p>
                          </div>
                        );
                      }}
                    />
                    <Legend />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Reasons table */}
            {allReasons.length > 0 && (
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Reason</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead className="text-right">Count</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allReasons.map((reason, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{reason.name}</TableCell>
                        <TableCell>{reason.category}</TableCell>
                        <TableCell className="text-right">
                          {reason.value}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
