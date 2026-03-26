"use client";

import { useState, useMemo, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Search,
  ArrowUpDown,
} from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatGHS } from "@/lib/format";
import { getPayrollRunItem } from "@/actions/payroll.action";
import type {
  PayrollItem,
  PayrollItemDetail,
  PayrollItemEarning,
  PayrollItemDeduction,
} from "@/types/payroll.type";

interface PayrollItemsTableProps {
  items: PayrollItem[];
  runId: string;
  isLoading?: boolean;
}

type SortField = "staff_name" | "department_name" | "net_salary" | "gross_salary" | "basic_salary";
type SortDir = "asc" | "desc";

function maskAccountNumber(acct: string | null): string {
  if (!acct || acct.length < 4) return acct || "---";
  return "****" + acct.slice(-4);
}

export function PayrollItemsTable({ items, runId, isLoading }: PayrollItemsTableProps) {
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<SortField>("staff_name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [itemDetails, setItemDetails] = useState<Record<string, PayrollItemDetail>>({});
  const [loadingDetails, setLoadingDetails] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    let result = items;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (item) =>
          item.staff_name.toLowerCase().includes(q) ||
          item.staff_code.toLowerCase().includes(q) ||
          (item.department_name && item.department_name.toLowerCase().includes(q))
      );
    }
    result = [...result].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }
      const diff = (aVal as number) - (bVal as number);
      return sortDir === "asc" ? diff : -diff;
    });
    return result;
  }, [items, search, sortField, sortDir]);

  const toggleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDir("asc");
      }
    },
    [sortField]
  );

  const toggleRow = useCallback(
    async (itemId: string) => {
      const next = new Set(expandedRows);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
        // Load details if not cached
        if (!itemDetails[itemId]) {
          setLoadingDetails((prev) => new Set(prev).add(itemId));
          const result = await getPayrollRunItem(runId, itemId);
          if (result.success) {
            setItemDetails((prev) => ({ ...prev, [itemId]: result.data }));
          }
          setLoadingDetails((prev) => {
            const s = new Set(prev);
            s.delete(itemId);
            return s;
          });
        }
      }
      setExpandedRows(next);
    },
    [expandedRows, itemDetails, runId]
  );

  function SortIcon({ field }: { field: SortField }) {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 ml-1" />;
    return sortDir === "asc" ? (
      <ChevronUp className="h-3 w-3 ml-1" />
    ) : (
      <ChevronDown className="h-3 w-3 ml-1" />
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-full" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-lg font-medium text-muted-foreground">No payroll items</p>
        <p className="text-sm text-muted-foreground mt-1">
          Run the payroll calculation to generate staff breakdowns.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search staff name or code..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
        <span className="text-sm text-muted-foreground">
          {filtered.length} of {items.length} staff
        </span>
      </div>

      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40px]" />
              <TableHead>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-medium hover:bg-transparent"
                  onClick={() => toggleSort("staff_name")}
                >
                  Staff <SortIcon field="staff_name" />
                </Button>
              </TableHead>
              <TableHead className="hidden md:table-cell">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-medium hover:bg-transparent"
                  onClick={() => toggleSort("department_name")}
                >
                  Department <SortIcon field="department_name" />
                </Button>
              </TableHead>
              <TableHead className="text-right hidden sm:table-cell">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-medium hover:bg-transparent ml-auto"
                  onClick={() => toggleSort("basic_salary")}
                >
                  Basic <SortIcon field="basic_salary" />
                </Button>
              </TableHead>
              <TableHead className="text-right hidden lg:table-cell">Allowances</TableHead>
              <TableHead className="text-right hidden sm:table-cell">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-medium hover:bg-transparent ml-auto"
                  onClick={() => toggleSort("gross_salary")}
                >
                  Gross <SortIcon field="gross_salary" />
                </Button>
              </TableHead>
              <TableHead className="text-right hidden lg:table-cell">PAYE</TableHead>
              <TableHead className="text-right hidden lg:table-cell">SSNIT</TableHead>
              <TableHead className="text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-medium hover:bg-transparent ml-auto"
                  onClick={() => toggleSort("net_salary")}
                >
                  Net <SortIcon field="net_salary" />
                </Button>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((item) => {
              const isExpanded = expandedRows.has(item.id);
              const detail = itemDetails[item.id];
              const isLoadingDetail = loadingDetails.has(item.id);

              return (
                <ExpandableRow
                  key={item.id}
                  item={item}
                  isExpanded={isExpanded}
                  detail={detail}
                  isLoadingDetail={isLoadingDetail}
                  onToggle={() => toggleRow(item.id)}
                />
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function ExpandableRow({
  item,
  isExpanded,
  detail,
  isLoadingDetail,
  onToggle,
}: {
  item: PayrollItem;
  isExpanded: boolean;
  detail: PayrollItemDetail | undefined;
  isLoadingDetail: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-muted/50"
        onClick={onToggle}
      >
        <TableCell className="w-[40px]">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </TableCell>
        <TableCell>
          <div>
            <p className="font-medium">{item.staff_name}</p>
            <p className="text-xs text-muted-foreground">{item.staff_code}</p>
          </div>
        </TableCell>
        <TableCell className="hidden md:table-cell">
          {item.department_name || "---"}
        </TableCell>
        <TableCell className="text-right hidden sm:table-cell">
          {formatGHS(item.basic_salary)}
        </TableCell>
        <TableCell className="text-right hidden lg:table-cell">
          {formatGHS(item.total_allowances)}
        </TableCell>
        <TableCell className="text-right hidden sm:table-cell">
          {formatGHS(item.gross_salary)}
        </TableCell>
        <TableCell className="text-right hidden lg:table-cell">
          {formatGHS(item.paye_tax)}
        </TableCell>
        <TableCell className="text-right hidden lg:table-cell">
          {formatGHS(item.ssnit_employee)}
        </TableCell>
        <TableCell className="text-right font-medium">
          {formatGHS(item.net_salary)}
        </TableCell>
      </TableRow>

      {isExpanded && (
        <TableRow>
          <TableCell colSpan={9} className="bg-muted/30 p-0">
            {isLoadingDetail ? (
              <div className="p-4 space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-36" />
                <Skeleton className="h-4 w-40" />
              </div>
            ) : detail ? (
              <ExpandedDetail detail={detail} />
            ) : (
              <div className="p-4 text-sm text-muted-foreground">
                Unable to load details.
              </div>
            )}
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function ExpandedDetail({ detail }: { detail: PayrollItemDetail }) {
  return (
    <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Earnings */}
      <div>
        <h4 className="text-sm font-semibold mb-2">Earnings</h4>
        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span>Basic Salary</span>
            <span className="font-medium">{formatGHS(detail.basic_salary)}</span>
          </div>
          {detail.earnings.map((e: PayrollItemEarning) => (
            <div key={e.id} className="flex justify-between text-sm">
              <span className="flex items-center gap-1.5">
                {e.name}
                {!e.is_taxable && (
                  <Badge variant="outline" className="text-[10px] px-1 py-0">
                    Non-taxable
                  </Badge>
                )}
              </span>
              <span>{formatGHS(e.amount)}</span>
            </div>
          ))}
          <div className="flex justify-between text-sm font-semibold border-t pt-1 mt-1">
            <span>Gross Salary</span>
            <span>{formatGHS(detail.gross_salary)}</span>
          </div>
        </div>
      </div>

      {/* Deductions */}
      <div>
        <h4 className="text-sm font-semibold mb-2">Deductions</h4>
        <div className="space-y-1">
          {detail.deductions.map((d: PayrollItemDeduction) => (
            <div key={d.id} className="flex justify-between text-sm">
              <span className="flex items-center gap-1.5">
                {d.name}
                {d.is_statutory && (
                  <Badge variant="secondary" className="text-[10px] px-1 py-0">
                    Statutory
                  </Badge>
                )}
                {d.is_employer_portion && (
                  <Badge variant="outline" className="text-[10px] px-1 py-0">
                    Employer
                  </Badge>
                )}
              </span>
              <span>{formatGHS(d.amount)}</span>
            </div>
          ))}
          <div className="flex justify-between text-sm font-semibold border-t pt-1 mt-1">
            <span>Total Deductions</span>
            <span>{formatGHS(detail.total_deductions)}</span>
          </div>
          <div className="flex justify-between text-sm font-bold border-t pt-1 mt-1">
            <span>Net Salary</span>
            <span className="text-green-600 dark:text-green-400">
              {formatGHS(detail.net_salary)}
            </span>
          </div>
        </div>

        {/* Payment info */}
        {detail.payment_method && (
          <div className="mt-3 pt-2 border-t text-xs text-muted-foreground">
            <span>Payment: {detail.payment_method}</span>
          </div>
        )}
      </div>
    </div>
  );
}
