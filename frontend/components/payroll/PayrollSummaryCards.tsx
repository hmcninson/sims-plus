"use client";

import {
  DollarSign,
  Receipt,
  Shield,
  MinusCircle,
  Wallet,
  Users,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { formatGHS } from "@/lib/format";
import type { PayrollRun } from "@/types/payroll.type";

interface PayrollSummaryCardsProps {
  run: PayrollRun;
}

const cards = [
  {
    label: "Total Basic",
    key: "total_basic" as const,
    icon: DollarSign,
    className: "text-blue-600 bg-blue-50 dark:bg-blue-950 dark:text-blue-400",
  },
  {
    label: "Gross Pay",
    key: "total_gross" as const,
    icon: Wallet,
    className: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-400",
  },
  {
    label: "PAYE Tax",
    key: "total_paye" as const,
    icon: Receipt,
    className: "text-amber-600 bg-amber-50 dark:bg-amber-950 dark:text-amber-400",
  },
  {
    label: "SSNIT (EE)",
    key: "total_ssnit_ee" as const,
    icon: Shield,
    className: "text-purple-600 bg-purple-50 dark:bg-purple-950 dark:text-purple-400",
  },
  {
    label: "Other Deductions",
    key: "total_other_deductions" as const,
    icon: MinusCircle,
    className: "text-red-600 bg-red-50 dark:bg-red-950 dark:text-red-400",
  },
  {
    label: "Net Pay",
    key: "total_net" as const,
    icon: DollarSign,
    className: "text-green-600 bg-green-50 dark:bg-green-950 dark:text-green-400",
  },
];

export function PayrollSummaryCards({ run }: PayrollSummaryCardsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <Card key={card.key}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className={`rounded-md p-1.5 ${card.className}`}>
                  <Icon className="h-4 w-4" />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">{card.label}</p>
              <p className="text-lg font-semibold tracking-tight mt-0.5">
                {formatGHS(run[card.key])}
              </p>
            </CardContent>
          </Card>
        );
      })}
      <Card className="col-span-2 md:col-span-3 lg:col-span-6">
        <CardContent className="p-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Staff Count</span>
          </div>
          <span className="text-lg font-semibold">{run.staff_count}</span>
          <div className="flex items-center gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Employer SSNIT: </span>
              <span className="font-medium">{formatGHS(run.total_ssnit_er)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Tier 2 ER: </span>
              <span className="font-medium">{formatGHS(run.total_tier2_er)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Total Cost: </span>
              <span className="font-semibold">{formatGHS(run.total_employer_cost)}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
