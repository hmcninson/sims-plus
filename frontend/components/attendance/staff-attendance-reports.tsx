"use client";

import { useState, useTransition, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { format, subDays } from "date-fns";
import {
  ArrowLeft,
  Loader2,
  Download,
  Users,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  BarChart3,
  Search,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
import { Skeleton } from "@/components/ui/skeleton";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";

import { getStaffAttendanceReport } from "@/actions/attendance.action";
import { getDepartments } from "@/actions/staff.action";
import type { StaffAttendanceReportData } from "@/types";

// ==========================================
// Constants
// ==========================================

const RATE_COLORS = {
  excellent: "#22c55e", // >= 95%
  good: "#3b82f6", // >= 90%
  fair: "#eab308", // >= 80%
  poor: "#ef4444", // < 80%
};

function getRateColor(rate: number): string {
  if (rate >= 95) return RATE_COLORS.excellent;
  if (rate >= 90) return RATE_COLORS.good;
  if (rate >= 80) return RATE_COLORS.fair;
  return RATE_COLORS.poor;
}

interface DepartmentOption {
  id: string;
  name: string;
}

// ==========================================
// Custom Chart Tooltip
// ==========================================

interface ChartTooltipProps {
  active?: boolean;
  payload?: Array<{
    value: number;
    payload: {
      date: string;
      present: number;
      absent: number;
      late: number;
      rate: number;
    };
  }>;
  label?: string;
}

function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;
  return (
    <div className="rounded-lg border bg-background p-3 shadow-md">
      <p className="text-sm font-medium">{label}</p>
      <div className="mt-1 space-y-0.5 text-xs text-muted-foreground">
        <p>Attendance Rate: <span className="font-medium text-foreground">{data.rate.toFixed(1)}%</span></p>
        <p>Present: {data.present}</p>
        <p>Absent: {data.absent}</p>
        <p>Late: {data.late}</p>
      </div>
    </div>
  );
}

// ==========================================
// Main Component
// ==========================================

export function StaffAttendanceReports() {
  const [isPending, startTransition] = useTransition();
  const [reportData, setReportData] = useState<StaffAttendanceReportData | null>(null);

  // Filters
  const [startDate, setStartDate] = useState<string>(
    format(subDays(new Date(), 30), "yyyy-MM-dd")
  );
  const [endDate, setEndDate] = useState<string>(format(new Date(), "yyyy-MM-dd"));
  const [departmentFilter, setDepartmentFilter] = useState<string>("all");
  const [departments, setDepartments] = useState<DepartmentOption[]>([]);

  // Individual staff table
  const [staffSearch, setStaffSearch] = useState("");
  const [sortField, setSortField] = useState<"staff_name" | "rate" | "total_days" | "absent">("rate");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Load departments on mount
  useEffect(() => {
    const loadDepartments = async () => {
      const result = await getDepartments();
      if (result.success && result.data) {
        setDepartments(result.data.map((d) => ({ id: d.id, name: d.name })));
      }
    };
    loadDepartments();
  }, []);

  // Fetch report data
  const fetchReport = useCallback(async () => {
    startTransition(async () => {
      const result = await getStaffAttendanceReport({
        start_date: startDate,
        end_date: endDate,
        department_id: departmentFilter !== "all" ? departmentFilter : undefined,
      });

      if (result.success && result.data) {
        setReportData(result.data);
      } else {
        setReportData(null);
      }
    });
  }, [startDate, endDate, departmentFilter]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  // Filtered and sorted staff data
  const filteredStaff = useMemo(() => {
    if (!reportData) return [];
    let staff = [...reportData.by_staff];

    // Search
    if (staffSearch.trim()) {
      const q = staffSearch.toLowerCase();
      staff = staff.filter(
        (s) =>
          s.staff_name.toLowerCase().includes(q) ||
          (s.department && s.department.toLowerCase().includes(q))
      );
    }

    // Sort
    staff.sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case "staff_name":
          comparison = a.staff_name.localeCompare(b.staff_name);
          break;
        case "rate":
          comparison = a.rate - b.rate;
          break;
        case "total_days":
          comparison = a.total_days - b.total_days;
          break;
        case "absent":
          comparison = a.absent - b.absent;
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });

    return staff;
  }, [reportData, staffSearch, sortField, sortDirection]);

  // Pagination
  const totalPages = Math.ceil(filteredStaff.length / pageSize);
  const paginatedStaff = filteredStaff.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  // Handle sort toggle
  const handleSort = (field: typeof sortField) => {
    if (field === sortField) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection(field === "rate" ? "asc" : "desc");
    }
    setCurrentPage(1);
  };

  const getSortIndicator = (field: typeof sortField) => {
    if (field !== sortField) return "";
    return sortDirection === "asc" ? " \u2191" : " \u2193";
  };

  // Chart data
  const chartData = useMemo(() => {
    if (!reportData) return [];
    return reportData.daily_breakdown.map((d) => ({
      ...d,
      date: format(new Date(d.date), "dd/MM"),
      fullDate: format(new Date(d.date), "dd MMM yyyy"),
    }));
  }, [reportData]);

  // CSV Export
  const handleExportCSV = () => {
    if (!reportData) return;

    const headers = ["Staff Name", "Department", "Total Days", "Present", "Absent", "Late", "Rate (%)"];
    const rows = reportData.by_staff.map((s) => [
      s.staff_name,
      s.department || "",
      String(s.total_days),
      String(s.present),
      String(s.absent),
      String(s.late),
      s.rate.toFixed(1),
    ]);

    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `staff-attendance-report-${startDate}-to-${endDate}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const activeFilterCount = departmentFilter !== "all" ? 1 : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/attendance/staff">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Staff Attendance Reports</h1>
            <p className="text-muted-foreground">
              Analyze staff attendance trends and patterns
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          onClick={handleExportCSV}
          disabled={!reportData || reportData.by_staff.length === 0}
        >
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-full sm:w-auto">
              <Label htmlFor="start-date">From</Label>
              <Input
                id="start-date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="mt-1.5 w-full sm:w-[180px]"
              />
            </div>
            <div className="w-full sm:w-auto">
              <Label htmlFor="end-date">To</Label>
              <Input
                id="end-date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                max={format(new Date(), "yyyy-MM-dd")}
                className="mt-1.5 w-full sm:w-[180px]"
              />
            </div>

            <CollapsibleFilters activeFilterCount={activeFilterCount}>
              <div className="w-full md:w-auto">
                <Label className="md:sr-only">Department</Label>
                <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
                  <SelectTrigger className="w-full md:w-[180px] mt-1.5 md:mt-0">
                    <SelectValue placeholder="Department" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Departments</SelectItem>
                    {departments.map((dept) => (
                      <SelectItem key={dept.id} value={dept.id}>
                        {dept.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CollapsibleFilters>
          </div>
        </CardContent>
      </Card>

      {isPending ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="rounded-lg border bg-card p-6">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="mt-3 h-8 w-16" />
              </div>
            ))}
          </div>
          <div className="rounded-lg border bg-card p-6">
            <Skeleton className="h-[300px] w-full" />
          </div>
        </div>
      ) : !reportData ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <BarChart3 className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">No Report Data</h3>
            <p className="text-sm text-muted-foreground mt-2">
              No staff attendance data found for the selected date range.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Overview Stats */}
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Staff</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{reportData.total_staff}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Overall Rate</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold" style={{ color: getRateColor(reportData.overall_rate) }}>
                  {reportData.overall_rate.toFixed(1)}%
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Days Covered</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{reportData.daily_breakdown.length}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Departments</CardTitle>
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{reportData.by_department.length}</div>
              </CardContent>
            </Card>
          </div>

          {/* Daily Attendance Chart */}
          {chartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Daily Attendance Rate</CardTitle>
                <CardDescription>
                  Staff attendance rate over the selected period
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 12 }}
                        className="text-muted-foreground"
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fontSize: 12 }}
                        className="text-muted-foreground"
                        tickFormatter={(v) => `${v}%`}
                      />
                      <Tooltip content={<ChartTooltip />} />
                      <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
                        {chartData.map((entry, index) => (
                          <Cell key={index} fill={getRateColor(entry.rate)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Department Breakdown */}
          {reportData.by_department.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Department Breakdown</CardTitle>
                <CardDescription>
                  Attendance rates by department
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Department</TableHead>
                        <TableHead className="hidden sm:table-cell">Staff</TableHead>
                        <TableHead>Present %</TableHead>
                        <TableHead className="hidden sm:table-cell">Absent %</TableHead>
                        <TableHead className="hidden sm:table-cell">Late %</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {reportData.by_department.map((dept) => (
                        <TableRow key={dept.department}>
                          <TableCell className="font-medium">{dept.department}</TableCell>
                          <TableCell className="hidden sm:table-cell">{dept.total}</TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={
                                dept.present_rate >= 95
                                  ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                                  : dept.present_rate >= 90
                                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                                  : dept.present_rate >= 80
                                  ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                                  : "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                              }
                            >
                              {dept.present_rate.toFixed(1)}%
                            </Badge>
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            {dept.absent_rate.toFixed(1)}%
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            {dept.late_rate.toFixed(1)}%
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Individual Staff Attendance */}
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle>Individual Staff Attendance</CardTitle>
                  <CardDescription>
                    {filteredStaff.length} staff members
                  </CardDescription>
                </div>
              </div>
              {/* Search */}
              <div className="relative mt-2">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search by name or department..."
                  value={staffSearch}
                  onChange={(e) => {
                    setStaffSearch(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="pl-9"
                />
              </div>
            </CardHeader>
            <CardContent>
              {filteredStaff.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Search className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="text-muted-foreground">No staff match your search</p>
                </div>
              ) : (
                <>
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead
                            className="cursor-pointer select-none"
                            onClick={() => handleSort("staff_name")}
                          >
                            Staff Name{getSortIndicator("staff_name")}
                          </TableHead>
                          <TableHead className="hidden sm:table-cell">Department</TableHead>
                          <TableHead
                            className="hidden sm:table-cell cursor-pointer select-none"
                            onClick={() => handleSort("total_days")}
                          >
                            Days{getSortIndicator("total_days")}
                          </TableHead>
                          <TableHead className="hidden md:table-cell">Present</TableHead>
                          <TableHead
                            className="hidden md:table-cell cursor-pointer select-none"
                            onClick={() => handleSort("absent")}
                          >
                            Absent{getSortIndicator("absent")}
                          </TableHead>
                          <TableHead className="hidden md:table-cell">Late</TableHead>
                          <TableHead
                            className="cursor-pointer select-none"
                            onClick={() => handleSort("rate")}
                          >
                            Rate{getSortIndicator("rate")}
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {paginatedStaff.map((staff) => (
                          <TableRow key={staff.staff_id}>
                            <TableCell className="font-medium">{staff.staff_name}</TableCell>
                            <TableCell className="hidden sm:table-cell text-muted-foreground">
                              {staff.department || "--"}
                            </TableCell>
                            <TableCell className="hidden sm:table-cell">{staff.total_days}</TableCell>
                            <TableCell className="hidden md:table-cell">{staff.present}</TableCell>
                            <TableCell className="hidden md:table-cell">{staff.absent}</TableCell>
                            <TableCell className="hidden md:table-cell">{staff.late}</TableCell>
                            <TableCell>
                              <Badge
                                variant="secondary"
                                className={
                                  staff.rate >= 95
                                    ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                                    : staff.rate >= 90
                                    ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                                    : staff.rate >= 80
                                    ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                                    : "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                                }
                              >
                                {staff.rate.toFixed(1)}%
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between mt-4">
                      <p className="text-sm text-muted-foreground">
                        Page {currentPage} of {totalPages} ({filteredStaff.length} total)
                      </p>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={currentPage <= 1}
                          onClick={() => setCurrentPage((p) => p - 1)}
                        >
                          Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={currentPage >= totalPages}
                          onClick={() => setCurrentPage((p) => p + 1)}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
