"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { DecisionDialog } from "@/components/admissions/decision-dialog";
import {
  Scale,
  ChevronLeft,
  ChevronRight,
  Gavel,
  ListOrdered,
} from "lucide-react";
import { getApplications, getAdmissionPeriods } from "@/actions/admissions.action";
import { getClasses } from "@/actions/academic.action";
import type { ApplicationListItem } from "@/types/admissions.type";
import type { Class } from "@/types";

// Only show applications ready for decision
const DECISION_STATUSES = [
  "shortlisted",
  "exam_completed",
  "waitlisted",
  "under_review",
];

export function DecisionsManagement() {
  const router = useRouter();
  const [applications, setApplications] = useState<ApplicationListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [periodFilter, setPeriodFilter] = useState<string>("all");
  const [classFilter, setClassFilter] = useState<string>("all");

  // Selection
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Lookups
  const [periods, setPeriods] = useState<
    Array<{ id: string; name: string }>
  >([]);
  const [classes, setClasses] = useState<Class[]>([]);

  const loadApplications = useCallback(async () => {
    startTransition(async () => {
      // Fetch applications with decision-ready statuses
      const statusParam =
        statusFilter !== "all"
          ? statusFilter
          : DECISION_STATUSES.join(",");

      const result = await getApplications({
        page,
        page_size: 20,
        status: statusParam,
        admission_period_id:
          periodFilter !== "all" ? periodFilter : undefined,
        target_class_id: classFilter !== "all" ? classFilter : undefined,
        sort_by: "created_at",
        sort_order: "desc",
      });

      if (result.success && result.data) {
        setApplications(result.data.items);
        setTotal(result.data.total);
        setTotalPages(result.data.pages);
      }
      setLoading(false);
    });
  }, [page, statusFilter, periodFilter, classFilter]);

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

  const activeFilterCount =
    (statusFilter !== "all" ? 1 : 0) +
    (periodFilter !== "all" ? 1 : 0) +
    (classFilter !== "all" ? 1 : 0);

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[500px]" />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admission Decisions</h1>
          <p className="text-sm text-muted-foreground">
            {total} application{total !== 1 ? "s" : ""} ready for decision
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href="/admissions/decisions/waitlist">
            <ListOrdered className="mr-2 h-4 w-4" />
            Manage Waitlist
          </Link>
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

      {/* Filters */}
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
            <SelectItem value="all">All Decision-Ready</SelectItem>
            {DECISION_STATUSES.map((s) => (
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

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {applications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <Scale className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">
                No applications ready for decision
              </p>
              <p className="text-sm text-muted-foreground">
                Applications in shortlisted, exam completed, or waitlisted
                status will appear here
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
                    <TableHead>Name</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Class
                    </TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden sm:table-cell">
                      Submitted
                    </TableHead>
                    <TableHead className="w-[100px]">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {applications.map((app) => (
                    <TableRow key={app.id}>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={selectedIds.includes(app.id)}
                          onCheckedChange={() => toggleOne(app.id)}
                        />
                      </TableCell>
                      <TableCell
                        className="font-medium cursor-pointer"
                        onClick={() =>
                          router.push(`/admissions/applications/${app.id}`)
                        }
                      >
                        {app.applicant_first_name} {app.applicant_last_name}
                        <span className="text-xs text-muted-foreground ml-2 font-mono">
                          {app.tracking_code}
                        </span>
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
                      <TableCell>
                        <DecisionDialog
                          applicationId={app.id}
                          currentStatus={app.status}
                          applicantName={`${app.applicant_first_name} ${app.applicant_last_name}`}
                          onSuccess={loadApplications}
                          trigger={
                            <Button variant="outline" size="sm">
                              <Gavel className="mr-1.5 h-3.5 w-3.5" />
                              Decide
                            </Button>
                          }
                        />
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
            Page {page} of {totalPages}
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
