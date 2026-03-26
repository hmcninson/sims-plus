"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Plus, Search, Landmark, ArrowRight } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { Skeleton } from "@/components/ui/skeleton";
import { LoanStatusBadge } from "@/components/payroll/LoanStatusBadge";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import { getLoans, getLoanTypes } from "@/actions/loans.action";
import { formatGHS, formatGhanaDate } from "@/lib/format";
import type { StaffLoanListItem, LoanType, LoanStatus } from "@/types/loan.type";

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All Statuses" },
  { value: "draft", label: "Draft" },
  { value: "pending_approval", label: "Pending Approval" },
  { value: "approved", label: "Approved" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "written_off", label: "Written Off" },
  { value: "restructured", label: "Restructured" },
  { value: "rejected", label: "Rejected" },
];

export function LoansList() {
  const [loans, setLoans] = useState<StaffLoanListItem[]>([]);
  const [loanTypes, setLoanTypes] = useState<LoanType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const loadData = useCallback(async () => {
    setIsLoading(true);
    const [loansResult, typesResult] = await Promise.all([
      getLoans({
        status: statusFilter !== "all" ? statusFilter : undefined,
        loan_type_id: typeFilter !== "all" ? typeFilter : undefined,
        search: search.trim() || undefined,
      }),
      getLoanTypes(),
    ]);

    if (loansResult.success) {
      setLoans(loansResult.data.items);
    }
    if (typesResult.success) {
      setLoanTypes(typesResult.data);
    }
    setIsLoading(false);
  }, [statusFilter, typeFilter, search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const activeFilterCount =
    (statusFilter !== "all" ? 1 : 0) + (typeFilter !== "all" ? 1 : 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Staff Loans</h1>
          <p className="text-muted-foreground">
            Manage loan applications, approvals, and repayments
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href="/payroll/loans/portfolio">
              <Landmark className="h-4 w-4 mr-2" />
              Portfolio
            </Link>
          </Button>
          <Button asChild>
            <Link href="/payroll/loans/new">
              <Plus className="h-4 w-4 mr-2" />
              New Loan
            </Link>
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative w-full md:w-[280px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by loan number or staff..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <CollapsibleFilters activeFilterCount={activeFilterCount}>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Loan Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {loanTypes.map((lt) => (
                <SelectItem key={lt.id} value={lt.id}>
                  {lt.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CollapsibleFilters>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : loans.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <Landmark className="h-10 w-10 text-muted-foreground" />
              <h3 className="text-lg font-semibold">No loans found</h3>
              <p className="text-sm text-muted-foreground">
                {search || statusFilter !== "all" || typeFilter !== "all"
                  ? "Try adjusting your filters"
                  : "Create a new loan application to get started"}
              </p>
              {!search && statusFilter === "all" && typeFilter === "all" && (
                <Button asChild size="sm">
                  <Link href="/payroll/loans/new">
                    <Plus className="h-4 w-4 mr-1" />
                    New Loan
                  </Link>
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Loan #</TableHead>
                    <TableHead>Staff</TableHead>
                    <TableHead className="hidden sm:table-cell">Type</TableHead>
                    <TableHead className="text-right">Principal</TableHead>
                    <TableHead className="text-right hidden md:table-cell">
                      Outstanding
                    </TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden lg:table-cell">Date</TableHead>
                    <TableHead className="w-[50px]" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loans.map((loan) => (
                    <TableRow key={loan.id}>
                      <TableCell className="font-mono text-sm">
                        {loan.loan_number}
                      </TableCell>
                      <TableCell>{loan.staff_name || "—"}</TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {loan.loan_type_name || "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatGHS(loan.principal_amount)}
                      </TableCell>
                      <TableCell className="text-right hidden md:table-cell">
                        {formatGHS(loan.outstanding_balance)}
                      </TableCell>
                      <TableCell>
                        <LoanStatusBadge status={loan.status} />
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {formatGhanaDate(loan.application_date)}
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" asChild>
                          <Link href={`/payroll/loans/${loan.id}`}>
                            <ArrowRight className="h-4 w-4" />
                          </Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
