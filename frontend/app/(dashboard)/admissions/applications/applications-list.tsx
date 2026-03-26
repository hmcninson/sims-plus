"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
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
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import { BulkDecisionToolbar } from "@/components/admissions/bulk-decision-toolbar";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  FileText,
  Download,
} from "lucide-react";
import { getApplications, getAdmissionPeriods } from "@/actions/admissions.action";
import { getClasses } from "@/actions/academic.action";
import type {
  ApplicationListItem,
  ApplicationStatus,
} from "@/types/admissions.type";
import type { Class } from "@/types";

const ALL_STATUSES: ApplicationStatus[] = [
  "draft",
  "submitted",
  "under_review",
  "shortlisted",
  "exam_scheduled",
  "exam_completed",
  "offered",
  "accepted",
  "waitlisted",
  "rejected",
  "enrolled",
  "withdrawn",
  "expired",
  "deferred",
];

export function ApplicationsList() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [applications, setApplications] = useState<ApplicationListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>(
    searchParams.get("status") || "all"
  );
  const [periodFilter, setPeriodFilter] = useState<string>(
    searchParams.get("admission_period_id") || "all"
  );
  const [classFilter, setClassFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>("created_at");
  const [sortOrder, setSortOrder] = useState<string>("desc");

  // Selection
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Lookup data
  const [periods, setPeriods] = useState<
    Array<{ id: string; name: string }>
  >([]);
  const [classes, setClasses] = useState<Class[]>([]);

  const loadApplications = useCallback(async () => {
    startTransition(async () => {
      const result = await getApplications({
        page,
        page_size: 20,
        status: statusFilter !== "all" ? statusFilter : undefined,
        admission_period_id:
          periodFilter !== "all" ? periodFilter : undefined,
        target_class_id: classFilter !== "all" ? classFilter : undefined,
        search: search || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      if (result.success && result.data) {
        setApplications(result.data.items);
        setTotal(result.data.total);
        setTotalPages(result.data.pages);
      }
      setLoading(false);
    });
  }, [page, statusFilter, periodFilter, classFilter, search, sortBy, sortOrder]);

  useEffect(() => {
    loadApplications();
  }, [loadApplications]);

  useEffect(() => {
    async function loadLookups() {
      const [periodsResult, classesResult] = await Promise.all([
        getAdmissionPeriods({ page_size: 50 }),
        getClasses(),
      ]);
      if (periodsResult.success && periodsResult.data) {
        setPeriods(
          periodsResult.data.items.map((p) => ({ id: p.id, name: p.name }))
        );
      }
      if (classesResult.success && classesResult.data) {
        setClasses(classesResult.data);
      }
    }
    loadLookups();
  }, []);

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
    setSelectedIds([]);
  }

  function handleSort(field: string) {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("asc");
    }
    setPage(1);
  }

  const isAllSelected =
    applications.length > 0 &&
    applications.every((a) => selectedIds.includes(a.id));

  function toggleAll() {
    if (isAllSelected) {
      setSelectedIds([]);
    } else {
      setSelectedIds(applications.map((a) => a.id));
    }
  }

  function toggleOne(id: string) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function exportCsv() {
    const headers = [
      "Tracking Code",
      "First Name",
      "Last Name",
      "Gender",
      "Class",
      "Status",
      "Submitted",
    ];
    const rows = applications.map((app) => [
      app.tracking_code,
      app.applicant_first_name,
      app.applicant_last_name,
      app.gender,
      app.target_class_name || "",
      app.status,
      app.submitted_at
        ? new Date(app.submitted_at).toLocaleDateString("en-GB")
        : "",
    ]);
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "applications.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const activeFilterCount =
    (statusFilter !== "all" ? 1 : 0) +
    (periodFilter !== "all" ? 1 : 0) +
    (classFilter !== "all" ? 1 : 0);

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-[500px]" />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Applications</h1>
          <p className="text-sm text-muted-foreground">
            {total} total application{total !== 1 ? "s" : ""}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={exportCsv}>
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {/* Bulk Decision Toolbar */}
      <BulkDecisionToolbar
        selectedIds={selectedIds}
        onComplete={() => {
          setSelectedIds([]);
          loadApplications();
        }}
      />

      {/* Search + Filters */}
      <div className="flex flex-col gap-3">
        <div className="relative w-full sm:w-[300px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by name or tracking code..."
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <CollapsibleFilters activeFilterCount={activeFilterCount}>
          <Select
            value={statusFilter}
            onValueChange={(v) => {
              setStatusFilter(v);
              setPage(1);
              setSelectedIds([]);
            }}
          >
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              {ALL_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s
                    .split("_")
                    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                    .join(" ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={periodFilter}
            onValueChange={(v) => {
              setPeriodFilter(v);
              setPage(1);
              setSelectedIds([]);
            }}
          >
            <SelectTrigger className="w-full md:w-[200px]">
              <SelectValue placeholder="Period" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Periods</SelectItem>
              {periods.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={classFilter}
            onValueChange={(v) => {
              setClassFilter(v);
              setPage(1);
              setSelectedIds([]);
            }}
          >
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Class" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Classes</SelectItem>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CollapsibleFilters>
      </div>

      {/* Data Table */}
      <Card>
        <CardContent className="p-0">
          {applications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <FileText className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">No applications found</p>
              <p className="text-sm text-muted-foreground">
                {search || statusFilter !== "all" || periodFilter !== "all"
                  ? "Try adjusting your filters"
                  : "Applications will appear here when submitted"}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[40px]">
                      <Checkbox
                        checked={isAllSelected}
                        onCheckedChange={toggleAll}
                      />
                    </TableHead>
                    <TableHead>
                      <button
                        onClick={() => handleSort("tracking_code")}
                        className="flex items-center gap-1 hover:text-foreground"
                      >
                        Code
                        <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button
                        onClick={() => handleSort("applicant_last_name")}
                        className="flex items-center gap-1 hover:text-foreground"
                      >
                        Name
                        <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </TableHead>
                    <TableHead className="hidden md:table-cell">
                      Class
                    </TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden sm:table-cell">
                      <button
                        onClick={() => handleSort("submitted_at")}
                        className="flex items-center gap-1 hover:text-foreground"
                      >
                        Submitted
                        <ArrowUpDown className="h-3 w-3" />
                      </button>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {applications.map((app) => (
                    <TableRow
                      key={app.id}
                      className="cursor-pointer"
                      onClick={() =>
                        router.push(`/admissions/applications/${app.id}`)
                      }
                    >
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={selectedIds.includes(app.id)}
                          onCheckedChange={() => toggleOne(app.id)}
                        />
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {app.tracking_code}
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">
                          {app.applicant_first_name} {app.applicant_last_name}
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                        {app.target_class_name || "-"}
                      </TableCell>
                      <TableCell>
                        <ApplicationStatusBadge status={app.status} />
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                        {app.submitted_at
                          ? new Date(app.submitted_at).toLocaleDateString(
                              "en-GB"
                            )
                          : "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages} ({total} total)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setPage(page - 1);
                setSelectedIds([]);
              }}
              disabled={page <= 1 || isPending}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setPage(page + 1);
                setSelectedIds([]);
              }}
              disabled={page >= totalPages || isPending}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
