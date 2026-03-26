"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

import type { LeaveBalance } from "@/types/leave.type";

interface LeaveBalanceCardProps {
  balances: LeaveBalance[];
}

export function LeaveBalanceCard({ balances }: LeaveBalanceCardProps) {
  if (balances.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Leave Balances</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No leave balances found for this period.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
      {balances.map((balance) => {
        const total = balance.entitled_days + balance.carried_over;
        const used = balance.used_days + balance.pending_days;
        const usagePercent = total > 0 ? Math.min((used / total) * 100, 100) : 0;

        return (
          <Card key={balance.id}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                {balance.leave_type_name || "Leave Type"}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold">{balance.remaining_days}</span>
                <span className="text-xs text-muted-foreground">
                  of {total} days remaining
                </span>
              </div>
              <Progress value={usagePercent} className="h-2" />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Used: {balance.used_days}</span>
                {balance.pending_days > 0 && (
                  <span>Pending: {balance.pending_days}</span>
                )}
                {balance.carried_over > 0 && (
                  <span>Carried: {balance.carried_over}</span>
                )}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
