"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowRight } from "lucide-react";
import type { FunnelStageResponse } from "@/types/admissions.type";

interface EnrollmentFunnelProps {
  stages: FunnelStageResponse[];
}

const STAGE_COLORS = [
  "bg-blue-500",
  "bg-indigo-500",
  "bg-violet-500",
  "bg-purple-500",
  "bg-fuchsia-500",
  "bg-pink-500",
  "bg-green-500",
];

const STAGE_LABELS: Record<string, string> = {
  inquiry: "Inquiries",
  application: "Applications",
  submitted: "Submitted",
  under_review: "Under Review",
  shortlisted: "Shortlisted",
  offered: "Offered",
  accepted: "Accepted",
  enrolled: "Enrolled",
};

export function EnrollmentFunnel({ stages }: EnrollmentFunnelProps) {
  if (stages.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Admissions Funnel</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[200px] items-center justify-center text-muted-foreground">
            No funnel data available
          </div>
        </CardContent>
      </Card>
    );
  }

  const maxCount = Math.max(...stages.map((s) => s.count), 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Admissions Funnel</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {stages.map((stage, index) => {
            const widthPct = Math.max((stage.count / maxCount) * 100, 8);
            const color = STAGE_COLORS[index % STAGE_COLORS.length];
            const label = STAGE_LABELS[stage.stage] ?? stage.stage;

            return (
              <div key={stage.stage}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="font-medium">{label}</span>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold tabular-nums">
                      {stage.count}
                    </span>
                    {stage.conversion_rate != null && index > 0 && (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <ArrowRight className="h-3 w-3" />
                        {stage.conversion_rate.toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
                <div className="h-8 w-full rounded-sm bg-muted">
                  <div
                    className={`h-full rounded-sm ${color} transition-all duration-500`}
                    style={{ width: `${widthPct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
