"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Landmark, ArrowRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getStaffLoans } from "@/actions/loans.action";
import { formatGHS } from "@/lib/format";
import type { StaffLoan } from "@/types/loan.type";

interface StaffLoanSummaryCardProps {
  staffId: string;
}

export function StaffLoanSummaryCard({ staffId }: StaffLoanSummaryCardProps) {
  const [loans, setLoans] = useState<StaffLoan[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      const result = await getStaffLoans(staffId);
      if (result.success) {
        setLoans(result.data);
      }
      setIsLoading(false);
    }
    load();
  }, [staffId]);

  const activeLoans = loans.filter(
    (l) => l.status === "active" || l.status === "approved"
  );
  const totalOutstanding = activeLoans.reduce(
    (sum, l) => sum + l.outstanding_balance,
    0
  );

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-4" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-24 mb-1" />
          <Skeleton className="h-3 w-32" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">Active Loans</CardTitle>
        <Landmark className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{activeLoans.length}</div>
        <p className="text-xs text-muted-foreground">
          {formatGHS(totalOutstanding)} outstanding
        </p>
        {loans.length > 0 && (
          <Link
            href={`/payroll/loans?staff_id=${staffId}`}
            className="mt-2 flex items-center gap-1 text-xs text-primary hover:underline"
          >
            View loans <ArrowRight className="h-3 w-3" />
          </Link>
        )}
      </CardContent>
    </Card>
  );
}
