"use client";

import { useEffect, useState, useTransition, useCallback, useMemo, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Award,
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  Edit,
  UserPlus,
  AlertCircle,
  Users,
  Loader2,
  Download,
  ChevronLeft,
  ChevronRight,
  Trash2,
} from "lucide-react";
import { getScholarships, deleteScholarship } from "@/actions/finance.action";
import { getAcademicYears } from "@/actions/academic.action";
import type { ScholarshipWithStats, AcademicYear } from "@/types";
import { formatCurrency } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

// ============================================
// Debounce Hook
// ============================================

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

// ============================================
// Constants
// ============================================

const TYPE_OPTIONS = [
  { value: "all", label: "All Types" },
  { value: "full", label: "Full" },
  { value: "partial", label: "Partial" },
  { value: "merit", label: "Merit" },
  { value: "need_based", label: "Need Based" },
  { value: "athletic", label: "Athletic" },
  { value: "special", label: "Special" },
];

const TYPE_COLORS: Record<string, string> = {
  full: "bg-green-100 text-green-800",
  partial: "bg-blue-100 text-blue-800",
  merit: "bg-purple-100 text-purple-800",
  need_based: "bg-orange-100 text-orange-800",
  athletic: "bg-red-100 text-red-800",
  special: "bg-gray-100 text-gray-800",
};

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

export function ScholarshipsList() {
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();

  // State
  const [isPending, startTransition] = useTransition();
  const [scholarships, setScholarships] = useState<ScholarshipWithStats[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [totalScholarships, setTotalScholarships] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const hasLoadedRef = useRef(false);

  // Filter state from URL params
  const [currentPage, setCurrentPage] = useState(
    parseInt(searchParams.get("page") || "1")
  );
  const [selectedYear, setSelectedYear] = useState<string>(
    searchParams.get("year") || "all"
  );
  const [selectedType, setSelectedType] = useState<string>(
    searchParams.get("type") || "all"
  );
  const [selectedStatus, setSelectedStatus] = useState<string>(
    searchParams.get("status") || "all"
  );
  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") || "");

  const pageSize = 20;
  const debouncedSearch = useDebounce(searchQuery, 300);
  const lastUrlRef = useRef<string>("");

  // Update URL when filters change
  const updateURL = useCallback(
    (updates: Record<string, string>) => {
      const params = new URLSearchParams();
      Object.entries(updates).forEach(([key, value]) => {
        if (value && value !== "all" && value !== "1" && value !== "") {
          params.set(key, value);
        }
      });
      const newUrl = params.toString() ? `?${params.toString()}` : "";

      if (newUrl !== lastUrlRef.current) {
        lastUrlRef.current = newUrl;
        router.replace(newUrl, { scroll: false });
      }
    },
    [router]
  );

  // Fetch scholarships
  const fetchScholarships = useCallback(() => {
    startTransition(async () => {
      const params: Record<string, string | number | boolean> = {
        page: currentPage,
        pageSize,
      };

      if (selectedYear !== "all") {
        params.academicYearId = selectedYear;
      }
      if (selectedType !== "all") {
        params.scholarshipType = selectedType;
      }
      if (selectedStatus !== "all") {
        params.isActive = selectedStatus === "active";
      }

      const result = await getScholarships(params);
      if (result.success && result.data) {
        setScholarships(result.data.items);
        setTotalScholarships(result.data.total);
        setError(null);
      } else {
        setError(result.error || "Failed to load scholarships");
      }
      setIsInitialLoad(false);
    });
  }, [currentPage, selectedYear, selectedType, selectedStatus]);

  // Load academic years on mount
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    lastUrlRef.current = window.location.search;

    const urlYear = searchParams.get("year");

    startTransition(async () => {
      const yearsResult = await getAcademicYears();
      if (yearsResult.success && yearsResult.data) {
        setAcademicYears(yearsResult.data);
        if (!urlYear) {
          const currentYear = yearsResult.data.find((y) => y.is_current);
          if (currentYear) {
            setSelectedYear(currentYear.id);
          }
        }
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch scholarships when filters change
  useEffect(() => {
    fetchScholarships();
  }, [fetchScholarships]);

  // Update URL when filters change (after initial load)
  useEffect(() => {
    if (isInitialLoad) return;

    updateURL({
      year: selectedYear,
      type: selectedType,
      status: selectedStatus,
      page: String(currentPage),
      q: debouncedSearch,
    });
  }, [selectedYear, selectedType, selectedStatus, currentPage, debouncedSearch, isInitialLoad, updateURL]);

  // Reset page when filters change
  const prevFiltersRef = useRef({
    selectedYear,
    selectedType,
    selectedStatus,
    debouncedSearch,
  });

  useEffect(() => {
    const prev = prevFiltersRef.current;
    const filtersChanged =
      prev.selectedYear !== selectedYear ||
      prev.selectedType !== selectedType ||
      prev.selectedStatus !== selectedStatus ||
      prev.debouncedSearch !== debouncedSearch;

    if (filtersChanged && !isInitialLoad) {
      setCurrentPage(1);
    }

    prevFiltersRef.current = {
      selectedYear,
      selectedType,
      selectedStatus,
      debouncedSearch,
    };
  }, [selectedYear, selectedType, selectedStatus, debouncedSearch, isInitialLoad]);

  // Handle delete
  const handleDelete = useCallback(async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete "${name}"?`)) return;

    startTransition(async () => {
      const result = await deleteScholarship(id);
      if (result.success) {
        toast({
          title: "Scholarship deleted",
          description: "The scholarship has been deleted successfully.",
        });
        fetchScholarships();
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to delete scholarship",
          variant: "destructive",
        });
      }
    });
  }, [toast, fetchScholarships]);

  // Format applies to display
  const formatAppliesTo = useCallback((scholarship: ScholarshipWithStats) => {
    if (
      !scholarship.applicable_fees ||
      scholarship.applicable_fees.length === 0 ||
      scholarship.applicable_fees.includes("all")
    ) {
      return "All Fees";
    }
    return scholarship.applicable_fees.join(", ");
  }, []);

  // Export to CSV
  const handleExportCSV = useCallback(() => {
    const headers = [
      "Name",
      "Code",
      "Type",
      "Coverage Type",
      "Coverage Value",
      "Applies To",
      "Max Recipients",
      "Current Recipients",
      "Status",
    ];
    const rows = scholarships.map((s) => [
      escapeCSV(s.name),
      escapeCSV(s.code),
      escapeCSV(s.scholarship_type),
      escapeCSV(s.coverage_type),
      escapeCSV(s.coverage_value),
      escapeCSV(formatAppliesTo(s)),
      escapeCSV(s.max_recipients),
      escapeCSV(s.recipients_count),
      escapeCSV(s.is_active ? "Active" : "Inactive"),
    ]);

    const csvContent =
      [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `scholarships-${new Date().toISOString().split("T")[0]}.csv`;
    link.click();
  }, [scholarships, formatAppliesTo]);

  // Format coverage display
  const formatCoverage = useCallback((scholarship: ScholarshipWithStats) => {
    if (scholarship.coverage_type === "percentage") {
      return `${scholarship.coverage_value}%`;
    }
    return formatCurrency(scholarship.coverage_value);
  }, []);

  // Client-side search filter
  const filteredScholarships = useMemo(() => {
    if (!debouncedSearch) return scholarships;
    const search = debouncedSearch.toLowerCase();
    return scholarships.filter(
      (s) =>
        s.name.toLowerCase().includes(search) ||
        s.code.toLowerCase().includes(search)
    );
  }, [scholarships, debouncedSearch]);

  // Memoized stats
  const stats = useMemo(() => {
    const activeCount = scholarships.filter((s) => s.is_active).length;
    const totalRecipients = scholarships.reduce(
      (sum, s) => sum + (s.recipients_count || 0),
      0
    );
    const totalFixedDiscounts = scholarships.reduce((sum, s) => {
      if (s.coverage_type === "percentage") return sum;
      return sum + s.coverage_value * (s.recipients_count || 0);
    }, 0);

    return {
      activeCount,
      totalCount: scholarships.length,
      totalRecipients,
      totalFixedDiscounts,
    };
  }, [scholarships]);

  // Pagination
  const totalPages = Math.ceil(totalScholarships / pageSize);

  // Clear filters
  const clearFilters = useCallback(() => {
    setSelectedYear("all");
    setSelectedType("all");
    setSelectedStatus("all");
    setSearchQuery("");
  }, []);

  const hasActiveFilters =
    selectedYear !== "all" ||
    selectedType !== "all" ||
    selectedStatus !== "all" ||
    searchQuery;

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
        <Button onClick={fetchScholarships}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Scholarships</h1>
          <p className="text-muted-foreground">
            Manage scholarships and financial aid programs
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExportCSV}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
          <Button asChild>
            <Link href="/finance/scholarships/new">
              <Plus className="mr-2 h-4 w-4" />
              New Scholarship
            </Link>
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Active Scholarships
            </CardTitle>
            <Award className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.activeCount}</div>
            <p className="text-xs text-muted-foreground">
              of {stats.totalCount} total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Total Recipients
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalRecipients}</div>
            <p className="text-xs text-muted-foreground">
              Students receiving aid
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Fixed Amount Awards
            </CardTitle>
            <Award className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {formatCurrency(stats.totalFixedDiscounts)}
            </div>
            <p className="text-xs text-muted-foreground">
              In scholarship discounts
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters & Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Scholarships</CardTitle>
          <CardDescription>
            View and manage all scholarship programs
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="mb-4 flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name or code..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={selectedYear} onValueChange={setSelectedYear}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Academic Year" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Years</SelectItem>
                {academicYears.map((year) => (
                  <SelectItem key={year.id} value={year.id}>
                    {year.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedType} onValueChange={setSelectedType}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                {TYPE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedStatus} onValueChange={setSelectedStatus}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                Clear filters
              </Button>
            )}
          </div>

          {/* Loading Overlay */}
          <div className="relative">
            {isPending && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/50">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            )}

            {filteredScholarships.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead className="hidden sm:table-cell">Code</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Coverage</TableHead>
                        <TableHead className="hidden md:table-cell">Applies To</TableHead>
                        <TableHead className="text-center">Recipients</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="w-[70px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredScholarships.map((scholarship) => (
                        <TableRow key={scholarship.id}>
                          <TableCell className="font-medium">
                            <Link
                              href={`/finance/scholarships/${scholarship.id}`}
                              className="hover:underline"
                            >
                              {scholarship.name}
                            </Link>
                          </TableCell>
                          <TableCell className="hidden text-muted-foreground sm:table-cell">
                            {scholarship.code}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={TYPE_COLORS[scholarship.scholarship_type] || "bg-gray-100 text-gray-800"}
                            >
                              {scholarship.scholarship_type.replace("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell>{formatCoverage(scholarship)}</TableCell>
                          <TableCell className="hidden md:table-cell">
                            {!scholarship.applicable_fees ||
                            scholarship.applicable_fees.length === 0 ||
                            scholarship.applicable_fees.includes("all") ? (
                              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                                All Fees
                              </Badge>
                            ) : (
                              <span className="text-sm text-muted-foreground">
                                {scholarship.applicable_fees.length} fee type{scholarship.applicable_fees.length !== 1 ? "s" : ""}
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            {scholarship.recipients_count || 0}
                            {scholarship.max_recipients && (
                              <span className="text-muted-foreground">
                                /{scholarship.max_recipients}
                              </span>
                            )}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={scholarship.is_active ? "default" : "secondary"}
                            >
                              {scholarship.is_active ? "Active" : "Inactive"}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem asChild>
                                  <Link href={`/finance/scholarships/${scholarship.id}`}>
                                    <Eye className="mr-2 h-4 w-4" />
                                    View Details
                                  </Link>
                                </DropdownMenuItem>
                                <DropdownMenuItem asChild>
                                  <Link href={`/finance/scholarships/${scholarship.id}/edit`}>
                                    <Edit className="mr-2 h-4 w-4" />
                                    Edit
                                  </Link>
                                </DropdownMenuItem>
                                <DropdownMenuItem asChild>
                                  <Link href={`/finance/scholarships/${scholarship.id}/award`}>
                                    <UserPlus className="mr-2 h-4 w-4" />
                                    Award to Students
                                  </Link>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onClick={() => handleDelete(scholarship.id, scholarship.name)}
                                  className="text-destructive"
                                >
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  Delete
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
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
                      {Math.min(currentPage * pageSize, totalScholarships)} of{" "}
                      {totalScholarships} scholarships
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
                <Award className="h-12 w-12" />
                <p>No scholarships found</p>
                {hasActiveFilters && (
                  <Button variant="ghost" size="sm" onClick={clearFilters}>
                    Clear filters
                  </Button>
                )}
                <Button asChild variant="outline" size="sm">
                  <Link href="/finance/scholarships/new">
                    Create your first scholarship
                  </Link>
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
