"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import {
  UserPlus,
  ChevronLeft,
  ChevronRight,
  Loader2,
  CheckCircle,
  ExternalLink,
} from "lucide-react";
import {
  getApplications,
  getAdmissionPeriods,
  enrollApplicant,
  bulkEnroll,
} from "@/actions/admissions.action";
import { getClasses } from "@/actions/academic.action";
import type {
  ApplicationListItem,
  EnrollResponse,
  BulkEnrollResponse,
} from "@/types/admissions.type";
import type { Class, ClassSection } from "@/types";

export function EnrollmentQueue() {
  const [applications, setApplications] = useState<ApplicationListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();

  // Filters
  const [periodFilter, setPeriodFilter] = useState<string>("all");
  const [classFilter, setClassFilter] = useState<string>("all");

  // Selection
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Enrollment
  const [enrollingId, setEnrollingId] = useState<string | null>(null);
  const [showEnrollDialog, setShowEnrollDialog] = useState(false);
  const [currentEnrollId, setCurrentEnrollId] = useState<string | null>(null);
  const [generateInvoice, setGenerateInvoice] = useState(true);
  const [sectionId, setSectionId] = useState("");
  const [enrollResult, setEnrollResult] = useState<EnrollResponse | null>(null);
  const [bulkEnrolling, setBulkEnrolling] = useState(false);
  const [bulkResult, setBulkResult] = useState<BulkEnrollResponse | null>(null);

  // Lookups
  const [periods, setPeriods] = useState<
    Array<{ id: string; name: string }>
  >([]);
  const [classes, setClasses] = useState<Class[]>([]);

  const loadApplications = useCallback(async () => {
    startTransition(async () => {
      const result = await getApplications({
        page,
        page_size: 20,
        status: "accepted",
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
  }, [page, periodFilter, classFilter]);

  useEffect(() => {
    loadApplications();
  }, [loadApplications]);

  useEffect(() => {
    async function loadLookups() {
      const [periodsResult, classesResult] = await Promise.all([
        getAdmissionPeriods({ page_size: 50 }),
        getClasses(true),
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

  function openEnrollDialog(applicationId: string) {
    setCurrentEnrollId(applicationId);
    setGenerateInvoice(true);
    setSectionId("");
    setEnrollResult(null);
    setShowEnrollDialog(true);
  }

  async function handleEnroll() {
    if (!currentEnrollId) return;
    setEnrollingId(currentEnrollId);
    try {
      const result = await enrollApplicant(currentEnrollId, {
        generate_invoice: generateInvoice,
        class_section_id: sectionId || undefined,
      });
      if (result.success && result.data) {
        setEnrollResult(result.data);
        toast.success(
          `Enrolled successfully. Student #: ${result.data.student_number}`
        );
        loadApplications();
      } else {
        toast.error(result.error);
      }
    } finally {
      setEnrollingId(null);
    }
  }

  async function handleBulkEnroll() {
    setBulkEnrolling(true);
    try {
      const result = await bulkEnroll({
        application_ids: selectedIds,
        generate_invoice: generateInvoice,
      });
      if (result.success && result.data) {
        setBulkResult(result.data);
        const { total_succeeded, total_failed } = result.data;
        if (total_failed === 0) {
          toast.success(
            `${total_succeeded} applicant${total_succeeded !== 1 ? "s" : ""} enrolled`
          );
        } else {
          toast.warning(
            `${total_succeeded} succeeded, ${total_failed} failed`
          );
        }
        setSelectedIds([]);
        loadApplications();
      } else {
        toast.error(result.error);
      }
    } finally {
      setBulkEnrolling(false);
    }
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

  // Get sections for the current app being enrolled
  const currentApp = applications.find((a) => a.id === currentEnrollId);
  const appClassId = currentApp
    ? classes.find((c) => c.name === currentApp.target_class_name)?.id
    : null;
  const sections: ClassSection[] =
    (appClassId
      ? classes.find((c) => c.id === appClassId)?.sections
      : []) ?? [];

  const activeFilterCount =
    (periodFilter !== "all" ? 1 : 0) + (classFilter !== "all" ? 1 : 0);

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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Enrollment Queue</h1>
          <p className="text-sm text-muted-foreground">
            {total} accepted applicant{total !== 1 ? "s" : ""} ready for
            enrollment
          </p>
        </div>
      </div>

      {/* Bulk Enroll Toolbar */}
      {selectedIds.length > 0 && (
        <div className="sticky top-0 z-10 flex items-center gap-3 rounded-lg border bg-muted/80 px-4 py-3 backdrop-blur-sm">
          <span className="text-sm font-medium">
            {selectedIds.length} selected
          </span>
          <div className="flex items-center gap-2">
            <Checkbox
              id="bulk-invoice"
              checked={generateInvoice}
              onCheckedChange={(c) => setGenerateInvoice(Boolean(c))}
            />
            <Label htmlFor="bulk-invoice" className="text-sm cursor-pointer">
              Generate invoices
            </Label>
          </div>
          <Button
            size="sm"
            onClick={handleBulkEnroll}
            disabled={bulkEnrolling}
          >
            {bulkEnrolling ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <UserPlus className="mr-1.5 h-4 w-4" />
            )}
            Enroll Selected
          </Button>
          {bulkResult && (
            <span className="text-sm text-muted-foreground ml-auto">
              {bulkResult.total_succeeded} enrolled
              {bulkResult.total_failed > 0 && (
                <span className="text-destructive">
                  , {bulkResult.total_failed} failed
                </span>
              )}
            </span>
          )}
        </div>
      )}

      {/* Filters */}
      <CollapsibleFilters activeFilterCount={activeFilterCount}>
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
              <CheckCircle className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">
                No applicants awaiting enrollment
              </p>
              <p className="text-sm text-muted-foreground">
                Accepted applicants will appear here for enrollment
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
                    <TableHead className="w-[180px]">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {applications.map((app) => (
                    <TableRow key={app.id}>
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.includes(app.id)}
                          onCheckedChange={() => toggleOne(app.id)}
                        />
                      </TableCell>
                      <TableCell className="font-medium">
                        <Link
                          href={`/admissions/applications/${app.id}`}
                          className="hover:underline"
                        >
                          {app.applicant_first_name} {app.applicant_last_name}
                        </Link>
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
                        <div className="flex items-center gap-1.5">
                          <Link href={`/admissions/enrollment/${app.id}/checklist`}>
                            <Button variant="ghost" size="sm">
                              <ExternalLink className="mr-1 h-3.5 w-3.5" />
                              <span className="hidden sm:inline">Checklist</span>
                            </Button>
                          </Link>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openEnrollDialog(app.id)}
                            disabled={enrollingId === app.id}
                          >
                            {enrollingId === app.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <>
                                <UserPlus className="mr-1.5 h-3.5 w-3.5" />
                                Enroll
                              </>
                            )}
                          </Button>
                        </div>
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

      {/* Enroll Dialog */}
      <AlertDialog open={showEnrollDialog} onOpenChange={setShowEnrollDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Enroll Applicant</AlertDialogTitle>
            <AlertDialogDescription>
              {enrollResult ? (
                <span>Enrollment completed successfully.</span>
              ) : (
                <span>
                  Convert this applicant into a student. A student ID will be
                  generated automatically.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>

          {enrollResult ? (
            <div className="space-y-3 py-4">
              <div className="rounded-lg border p-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Student Number</span>
                  <span className="font-mono font-medium">
                    {enrollResult.student_number}
                  </span>
                </div>
                {enrollResult.invoice_id && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Invoice</span>
                    <span className="text-green-600">Created</span>
                  </div>
                )}
                {enrollResult.parent_account_created && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">
                      Parent Account
                    </span>
                    <span className="text-green-600">Created</span>
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" className="flex-1" asChild>
                  <Link href={`/students?id=${enrollResult.student_id}`}>
                    <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                    View Student
                  </Link>
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4 py-4">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="enroll-invoice"
                  checked={generateInvoice}
                  onCheckedChange={(c) => setGenerateInvoice(Boolean(c))}
                />
                <Label htmlFor="enroll-invoice" className="cursor-pointer">
                  Generate invoice
                </Label>
              </div>
              {sections.length > 0 && (
                <div className="space-y-2">
                  <Label>Section (Optional)</Label>
                  <Select value={sectionId} onValueChange={setSectionId}>
                    <SelectTrigger>
                      <SelectValue placeholder="No section" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">No section</SelectItem>
                      {sections.map((sec) => (
                        <SelectItem key={sec.id} value={sec.id}>
                          {sec.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          )}

          <AlertDialogFooter>
            {enrollResult ? (
              <AlertDialogAction onClick={() => setShowEnrollDialog(false)}>
                Done
              </AlertDialogAction>
            ) : (
              <>
                <AlertDialogCancel disabled={!!enrollingId}>
                  Cancel
                </AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleEnroll}
                  disabled={!!enrollingId}
                >
                  {enrollingId && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Enroll
                </AlertDialogAction>
              </>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
