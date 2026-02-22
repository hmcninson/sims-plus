"use client";

import { useState, useEffect, useCallback } from "react";
import {
  CreditCard,
  Receipt,
  ChevronRight,
  Loader2,
  Wallet,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { formatGHS, getInitials, formatGhanaDate } from "@/lib/format";
import { getChildInvoices } from "@/actions/parent.action";
import type { ChildSummary, ParentInvoiceSummary } from "@/types/parent.type";

interface PaymentsViewProps {
  children: ChildSummary[];
}

const statusStyles: Record<string, string> = {
  paid: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  partial: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  issued: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  overdue: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  cancelled: "bg-muted text-muted-foreground",
  draft: "bg-muted text-muted-foreground",
  write_off: "bg-muted text-muted-foreground",
};

export function PaymentsView({ children }: PaymentsViewProps) {
  const [selectedChildId, setSelectedChildId] = useState<string>(
    children[0]?.id || ""
  );
  const [invoices, setInvoices] = useState<ParentInvoiceSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const loadInvoices = useCallback(async (childId: string) => {
    if (!childId) return;
    setLoading(true);
    const result = await getChildInvoices(childId);
    if (result.success) {
      setInvoices(result.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (selectedChildId) {
      loadInvoices(selectedChildId);
    }
  }, [selectedChildId, loadInvoices]);

  const totalOutstanding = invoices
    .filter((inv) => inv.status !== "paid" && inv.status !== "cancelled")
    .reduce((sum, inv) => sum + inv.balance, 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Payments</h1>
          <p className="text-sm text-muted-foreground">
            View invoices and make payments for your children.
          </p>
        </div>
        {children.length > 1 && (
          <Select value={selectedChildId} onValueChange={setSelectedChildId}>
            <SelectTrigger className="w-full sm:w-[220px]">
              <SelectValue placeholder="Select child" />
            </SelectTrigger>
            <SelectContent>
              {children.map((child) => (
                <SelectItem key={child.id} value={child.id}>
                  {child.first_name} {child.last_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Outstanding balance summary */}
      {selectedChildId && !loading && (
        <Card
          className={cn(
            totalOutstanding > 0
              ? "border-amber-500/30 bg-amber-50/50 dark:bg-amber-950/20"
              : "border-green-500/30 bg-green-50/50 dark:bg-green-950/20"
          )}
        >
          <CardContent className="flex items-center gap-4 py-4">
            <div
              className={cn(
                "flex h-12 w-12 items-center justify-center rounded-full",
                totalOutstanding > 0
                  ? "bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-300"
                  : "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300"
              )}
            >
              <Wallet className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">
                Total Outstanding Balance
              </p>
              <p className="text-2xl font-bold">
                {formatGHS(totalOutstanding)}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Invoices list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : children.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <CreditCard className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No payment information</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Payment details will appear here once your children are linked.
            </p>
          </CardContent>
        </Card>
      ) : invoices.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Receipt className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No invoices yet</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Invoices for the current term will appear here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {invoices.map((invoice) => (
            <Card
              key={invoice.id}
              className="hover:shadow-md transition-shadow cursor-pointer"
            >
              <CardContent className="flex items-center gap-4 p-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold">
                      {invoice.invoice_number}
                    </p>
                    <Badge
                      variant="secondary"
                      className={cn(
                        "text-[10px] h-5 capitalize",
                        statusStyles[invoice.status] || ""
                      )}
                    >
                      {invoice.status.replace("_", " ")}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {invoice.term_name}
                    {invoice.due_date
                      ? ` | Due: ${formatGhanaDate(invoice.due_date)}`
                      : ""}
                  </p>
                  <div className="flex items-center gap-4 mt-2 text-sm">
                    <span className="text-muted-foreground">
                      Total: {formatGHS(invoice.total_amount)}
                    </span>
                    <span className="text-muted-foreground">
                      Paid: {formatGHS(invoice.amount_paid)}
                    </span>
                    {invoice.balance > 0 && (
                      <span className="font-medium text-amber-600 dark:text-amber-400">
                        Balance: {formatGHS(invoice.balance)}
                      </span>
                    )}
                  </div>
                </div>
                {invoice.balance > 0 && (
                  <Button size="sm" className="shrink-0">
                    Pay Now
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
