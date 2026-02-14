"use client";

import { useEffect, useState, useTransition, useCallback, useMemo, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  Edit,
  UserPlus,
  MoreHorizontal,
  UserMinus,
  AlertCircle,
  Award,
  Users,
  Percent,
  DollarSign,
  Loader2,
  Download,
  Search,
  ChevronLeft,
  ChevronRight,
  Calculator,
} from "lucide-react";
import {
  getScholarship,
  getScholarshipRecipients,
  revokeScholarship,
} from "@/actions/finance.action";
import type { ScholarshipWithStats, StudentScholarshipWithDetails } from "@/types";
import { formatCurrency, formatDate } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

// ============================================
// Constants (outside component)
// ============================================

const TYPE_COLORS: Record<string, string> = {
  full: "bg-green-100 text-green-800",
  partial: "bg-blue-100 text-blue-800",
  merit: "bg-purple-100 text-purple-800",
  need_based: "bg-orange-100 text-orange-800",
  athletic: "bg-red-100 text-red-800",
  special: "bg-gray-100 text-gray-800",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  suspended: "bg-yellow-100 text-yellow-800",
  revoked: "bg-red-100 text-red-800",
  expired: "bg-gray-100 text-gray-800",
};

const STATUS_OPTIONS = [
  { value: "all", label: "All Status" },
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
  { value: "revoked", label: "Revoked" },
  { value: "expired", label: "Expired" },
];

// CSV escape helper
function escapeCSV(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

// ============================================
// Main Component
// ============================================

export default function ScholarshipDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [scholarship, setScholarship] = useState<ScholarshipWithStats | null>(null);
  const [recipients, setRecipients] = useState<StudentScholarshipWithDetails[]>([]);
  const [totalRecipients, setTotalRecipients] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const hasLoadedRef = useRef(false);

  // Recipients filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Revoke dialog state
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
  const [revokeReason, setRevokeReason] = useState("");
  const [recipientToRevoke, setRecipientToRevoke] = useState<StudentScholarshipWithDetails | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);

  const scholarshipId = params.id as string;

  // Fetch scholarship data
  const fetchScholarship = useCallback(() => {
    startTransition(async () => {
      const result = await getScholarship(scholarshipId);
      if (result.success && result.data) {
        setScholarship(result.data);
        setError(null);
      } else {
        setError(result.error || "Failed to load scholarship");
      }
    });
  }, [scholarshipId]);

  // Fetch recipients with filters
  const fetchRecipients = useCallback(() => {
    startTransition(async () => {
      const params: Record<string, string | number> = {
        page: currentPage,
        pageSize,
      };
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }

      const result = await getScholarshipRecipients(scholarshipId, params);
      if (result.success && result.data) {
        setRecipients(result.data.items);
        setTotalRecipients(result.data.total);
      }
      setIsInitialLoad(false);
    });
  }, [scholarshipId, currentPage, statusFilter]);

  // Initial load
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;
    fetchScholarship();
  }, [fetchScholarship]);

  // Fetch recipients when filters change
  useEffect(() => {
    fetchRecipients();
  }, [fetchRecipients]);

  // Reset page when status filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter]);

  // Open revoke dialog
  const handleOpenRevokeDialog = useCallback((recipient: StudentScholarshipWithDetails) => {
    setRecipientToRevoke(recipient);
    setRevokeReason("");
    setRevokeDialogOpen(true);
  }, []);

  // Handle revoke
  const handleRevoke = useCallback(async () => {
    if (!recipientToRevoke || !revokeReason.trim()) return;

    setIsRevoking(true);
    try {
      const result = await revokeScholarship(scholarshipId, recipientToRevoke.id, {
        reason: revokeReason,
      });

      if (result.success) {
        toast({
          title: "Scholarship revoked",
          description: `The scholarship has been revoked from ${recipientToRevoke.student_name}.`,
        });
        setRevokeDialogOpen(false);
        setRecipientToRevoke(null);
        setRevokeReason("");
        fetchRecipients();
        fetchScholarship(); // Refresh stats
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to revoke scholarship",
          variant: "destructive",
        });
      }
    } finally {
      setIsRevoking(false);
    }
  }, [recipientToRevoke, revokeReason, scholarshipId, toast, fetchRecipients, fetchScholarship]);

  // Export recipients to CSV
  const handleExportCSV = useCallback(() => {
    const headers = [
      "Student Name",
      "Student ID",
      "Effective From",
      "Effective To",
      "Coverage Override",
      "Status",
      "Notes",
    ];
    const rows = recipients.map((r) => [
      escapeCSV(r.student_name),
      escapeCSV(r.student_id_number),
      escapeCSV(r.effective_from),
      escapeCSV(r.effective_to || "End of Year"),
      escapeCSV(r.coverage_override),
      escapeCSV(r.status),
      escapeCSV(r.notes),
    ]);

    const csvContent =
      [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${scholarship?.code || "scholarship"}-recipients-${new Date().toISOString().split("T")[0]}.csv`;
    link.click();
  }, [recipients, scholarship?.code]);

  // Client-side search filter
  const filteredRecipients = useMemo(() => {
    if (!searchQuery) return recipients;
    const search = searchQuery.toLowerCase();
    return recipients.filter(
      (r) =>
        r.student_name?.toLowerCase().includes(search) ||
        r.student_id_number?.toLowerCase().includes(search)
    );
  }, [recipients, searchQuery]);

  // Memoized stats
  const stats = useMemo(() => {
    const activeCount = recipients.filter((r) => r.status === "active").length;

    // Calculate estimated total value for active recipients
    let estimatedValue = 0;
    if (scholarship && scholarship.coverage_type === "fixed_amount") {
      estimatedValue = scholarship.coverage_value * activeCount;
    }

    return {
      activeCount,
      totalCount: recipients.length,
      estimatedValue,
    };
  }, [recipients, scholarship]);

  // Pagination
  const totalPages = Math.ceil(totalRecipients / pageSize);

  // Loading state
  if (isInitialLoad && isPending) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">{error}</p>
        <Button onClick={() => router.push("/finance/scholarships")}>
          Back to Scholarships
        </Button>
      </div>
    );
  }

  if (!scholarship) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/finance/scholarships">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">
                {scholarship.name}
              </h1>
              <Badge
                variant="secondary"
                className={TYPE_COLORS[scholarship.scholarship_type] || "bg-gray-100 text-gray-800"}
              >
                {scholarship.scholarship_type.replace("_", " ")}
              </Badge>
            </div>
            <p className="text-muted-foreground">{scholarship.code}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href={`/finance/scholarships/${scholarshipId}/edit`}>
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </Link>
          </Button>
          <Button asChild>
            <Link href={`/finance/scholarships/${scholarshipId}/award`}>
              <UserPlus className="mr-2 h-4 w-4" />
              Award to Students
            </Link>
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Coverage</CardTitle>
            {scholarship.coverage_type === "percentage" ? (
              <Percent className="h-4 w-4 text-muted-foreground" />
            ) : (
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            )}
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {scholarship.coverage_type === "percentage"
                ? `${scholarship.coverage_value}%`
                : formatCurrency(scholarship.coverage_value)}
            </div>
            <p className="text-xs text-muted-foreground">
              {scholarship.coverage_type === "percentage"
                ? "of applicable fees"
                : "fixed discount"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Active Recipients
            </CardTitle>
            <Users className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {scholarship.recipients_count || stats.activeCount}
            </div>
            <p className="text-xs text-muted-foreground">
              {scholarship.max_recipients
                ? `of ${scholarship.max_recipients} max`
                : "no limit"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              {scholarship.coverage_type === "fixed_amount" ? "Est. Total Value" : "Total Awards"}
            </CardTitle>
            {scholarship.coverage_type === "fixed_amount" ? (
              <Calculator className="h-4 w-4 text-blue-600" />
            ) : (
              <Award className="h-4 w-4 text-muted-foreground" />
            )}
          </CardHeader>
          <CardContent>
            {scholarship.coverage_type === "fixed_amount" ? (
              <>
                <div className="text-2xl font-bold text-blue-600">
                  {formatCurrency(scholarship.coverage_value * (scholarship.recipients_count || 0))}
                </div>
                <p className="text-xs text-muted-foreground">
                  for {scholarship.recipients_count || 0} active recipients
                </p>
              </>
            ) : (
              <>
                <div className="text-2xl font-bold">{totalRecipients}</div>
                <p className="text-xs text-muted-foreground">all-time awards</p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Status</CardTitle>
            <Award className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Badge variant={scholarship.is_active ? "default" : "secondary"}>
              {scholarship.is_active ? "Active" : "Inactive"}
            </Badge>
            <p className="mt-1 text-xs text-muted-foreground">
              {scholarship.is_active
                ? "Accepting new awards"
                : "Not accepting awards"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Description */}
      {scholarship.description && (
        <Card>
          <CardHeader>
            <CardTitle>Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">{scholarship.description}</p>
          </CardContent>
        </Card>
      )}

      {/* Applicable Fee Components */}
      <Card>
        <CardHeader>
          <CardTitle>Applicable Fee Components</CardTitle>
          <CardDescription>
            Which fee types this scholarship covers
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!scholarship.applicable_fees ||
          scholarship.applicable_fees.length === 0 ||
          scholarship.applicable_fees.includes("all") ? (
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                All Fees
              </Badge>
              <span className="text-sm text-muted-foreground">
                This scholarship applies to the entire invoice amount
              </span>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2">
                {scholarship.applicable_fees.map((fee, index) => (
                  <Badge key={index} variant="secondary">
                    {fee}
                  </Badge>
                ))}
              </div>
              <p className="text-sm text-muted-foreground">
                This scholarship only applies to the fee types listed above
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recipients */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Recipients</CardTitle>
            <CardDescription>
              Students awarded this scholarship
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleExportCSV} disabled={recipients.length === 0}>
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
            <Button asChild size="sm">
              <Link href={`/finance/scholarships/${scholarshipId}/award`}>
                <UserPlus className="mr-2 h-4 w-4" />
                Award
              </Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="mb-4 flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by student name or ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[140px]">
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
          </div>

          {/* Loading Overlay */}
          <div className="relative">
            {isPending && !isInitialLoad && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/50">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            )}

            {filteredRecipients.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Student</TableHead>
                        <TableHead className="hidden sm:table-cell">Effective From</TableHead>
                        <TableHead className="hidden md:table-cell">Effective To</TableHead>
                        <TableHead className="hidden lg:table-cell">Override</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="w-[70px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredRecipients.map((recipient) => (
                        <TableRow key={recipient.id}>
                          <TableCell className="font-medium">
                            <Link
                              href={`/students/${recipient.student_id}`}
                              className="hover:underline"
                            >
                              {recipient.student_name}
                            </Link>
                            {recipient.student_id_number && (
                              <p className="text-xs text-muted-foreground">
                                {recipient.student_id_number}
                              </p>
                            )}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            {formatDate(recipient.effective_from)}
                          </TableCell>
                          <TableCell className="hidden md:table-cell">
                            {recipient.effective_to
                              ? formatDate(recipient.effective_to)
                              : "End of Year"}
                          </TableCell>
                          <TableCell className="hidden lg:table-cell">
                            {recipient.coverage_override
                              ? scholarship.coverage_type === "percentage"
                                ? `${recipient.coverage_override}%`
                                : formatCurrency(recipient.coverage_override)
                              : "-"}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={STATUS_COLORS[recipient.status] || "bg-gray-100 text-gray-800"}
                            >
                              {recipient.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {recipient.status === "active" && (
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem
                                    onClick={() => handleOpenRevokeDialog(recipient)}
                                    className="text-destructive"
                                  >
                                    <UserMinus className="mr-2 h-4 w-4" />
                                    Revoke
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="mt-4 flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Showing {(currentPage - 1) * pageSize + 1} to{" "}
                      {Math.min(currentPage * pageSize, totalRecipients)} of{" "}
                      {totalRecipients} recipients
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                        disabled={currentPage === 1 || isPending}
                      >
                        <ChevronLeft className="h-4 w-4" />
                        Previous
                      </Button>
                      <span className="text-sm">
                        Page {currentPage} of {totalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages || isPending}
                      >
                        Next
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
                <Users className="h-12 w-12" />
                <p>{searchQuery || statusFilter !== "all" ? "No matching recipients" : "No recipients yet"}</p>
                {(searchQuery || statusFilter !== "all") ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSearchQuery("");
                      setStatusFilter("all");
                    }}
                  >
                    Clear filters
                  </Button>
                ) : (
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/finance/scholarships/${scholarshipId}/award`}>
                      Award to students
                    </Link>
                  </Button>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Revoke Dialog */}
      <Dialog open={revokeDialogOpen} onOpenChange={setRevokeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revoke Scholarship</DialogTitle>
            <DialogDescription>
              Are you sure you want to revoke this scholarship from{" "}
              <span className="font-semibold">{recipientToRevoke?.student_name}</span>?
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {recipientToRevoke && (
            <div className="rounded-md bg-muted p-3 text-sm">
              <p><span className="text-muted-foreground">Student:</span> {recipientToRevoke.student_name}</p>
              <p><span className="text-muted-foreground">Effective From:</span> {formatDate(recipientToRevoke.effective_from)}</p>
              <p><span className="text-muted-foreground">Coverage:</span> {
                recipientToRevoke.coverage_override
                  ? scholarship.coverage_type === "percentage"
                    ? `${recipientToRevoke.coverage_override}%`
                    : formatCurrency(recipientToRevoke.coverage_override)
                  : scholarship.coverage_type === "percentage"
                    ? `${scholarship.coverage_value}%`
                    : formatCurrency(scholarship.coverage_value)
              }</p>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="revoke-reason">
              Reason for revoking <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="revoke-reason"
              placeholder="Enter the reason for revoking this scholarship..."
              value={revokeReason}
              onChange={(e) => setRevokeReason(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setRevokeDialogOpen(false);
                setRecipientToRevoke(null);
                setRevokeReason("");
              }}
              disabled={isRevoking}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleRevoke}
              disabled={isRevoking || !revokeReason.trim()}
            >
              {isRevoking ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Revoking...
                </>
              ) : (
                "Revoke Scholarship"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
