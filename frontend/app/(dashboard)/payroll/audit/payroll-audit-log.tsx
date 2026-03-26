"use client";

import { useState, useCallback, useEffect } from "react";
import {
  Shield,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Filter,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import { getPayrollAuditLog } from "@/actions/payroll.action";
import { formatGhanaDate, formatRelativeTime } from "@/lib/format";
import type { PayrollAuditLogResponse, PayrollAuditLogEntry } from "@/types/payroll.type";

const ENTITY_TYPES = [
  { value: "", label: "All Entities" },
  { value: "payroll_run", label: "Payroll Run" },
  { value: "payroll_item", label: "Payroll Item" },
  { value: "salary_config", label: "Salary Config" },
  { value: "salary_grade", label: "Salary Grade" },
  { value: "allowance_type", label: "Allowance Type" },
  { value: "deduction_type", label: "Deduction Type" },
  { value: "tax_bracket", label: "Tax Bracket" },
  { value: "bank_file_config", label: "Bank File Config" },
];

const ACTION_COLORS: Record<string, string> = {
  create: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  update: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  delete: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  approve: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-300",
  reject: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
  calculate: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  submit: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300",
  mark_paid: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-300",
  cancel: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
  adjust: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
};

const PAGE_SIZE = 20;

export function PayrollAuditLog() {
  const [data, setData] = useState<PayrollAuditLogResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [entityType, setEntityType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    const result = await getPayrollAuditLog({
      page,
      page_size: PAGE_SIZE,
      entity_type: entityType || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    });
    setIsLoading(false);
    if (result.success) {
      setData(result.data);
    } else {
      toast.error(result.error);
    }
  }, [page, entityType, dateFrom, dateTo]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function handleFilter() {
    setPage(1);
    fetchData();
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Payroll Audit Log</h1>
        <p className="text-sm text-muted-foreground">
          Complete audit trail of all payroll changes and actions
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:flex-wrap">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Entity Type</label>
          <Select value={entityType} onValueChange={(v) => { setEntityType(v); setPage(1); }}>
            <SelectTrigger className="w-full md:w-[200px]">
              <SelectValue placeholder="All Entities" />
            </SelectTrigger>
            <SelectContent>
              {ENTITY_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">From Date</label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="w-full md:w-[160px]"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">To Date</label>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="w-full md:w-[160px]"
          />
        </div>
        <Button onClick={handleFilter} variant="outline" className="gap-1.5">
          <Filter className="h-4 w-4" />
          Apply Filters
        </Button>
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Shield className="h-4 w-4" />
              Audit Entries
            </CardTitle>
            {data && (
              <span className="text-sm text-muted-foreground">
                {data.total} total entries
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : !data || data.items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Clock className="h-10 w-10 text-muted-foreground mb-3" />
              <h3 className="text-sm font-medium">No audit entries found</h3>
              <p className="text-xs text-muted-foreground mt-1">
                {entityType || dateFrom || dateTo
                  ? "Try adjusting your filters"
                  : "Audit entries will appear as payroll actions are performed"}
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto -mx-6">
                <div className="min-w-[800px] px-6">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Timestamp</TableHead>
                        <TableHead>User</TableHead>
                        <TableHead>Action</TableHead>
                        <TableHead>Entity</TableHead>
                        <TableHead>Field</TableHead>
                        <TableHead>Old Value</TableHead>
                        <TableHead>New Value</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.items.map((entry) => (
                        <TableRow key={entry.id}>
                          <TableCell className="text-xs whitespace-nowrap">
                            <div>
                              <p>{formatGhanaDate(entry.performed_at)}</p>
                              <p className="text-muted-foreground">
                                {formatRelativeTime(entry.performed_at)}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell className="text-sm">
                            {entry.performed_by_name || entry.performed_by.slice(0, 8)}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={`text-xs capitalize ${ACTION_COLORS[entry.action] || ""}`}
                            >
                              {entry.action.replace("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs">
                            <span className="capitalize">{entry.entity_type.replace("_", " ")}</span>
                            <br />
                            <span className="text-muted-foreground font-mono">{entry.entity_id.slice(0, 8)}...</span>
                          </TableCell>
                          <TableCell className="text-xs font-mono">
                            {entry.field_name || "--"}
                          </TableCell>
                          <TableCell className="text-xs max-w-[120px] truncate" title={entry.old_value ?? undefined}>
                            {entry.old_value || "--"}
                          </TableCell>
                          <TableCell className="text-xs max-w-[120px] truncate" title={entry.new_value ?? undefined}>
                            {entry.new_value || "--"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {totalPages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
