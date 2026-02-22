"use client";

import { useState, useTransition, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  format,
  subDays,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  startOfMonth,
  endOfMonth,
  eachWeekOfInterval,
  getDay,
  isSameMonth,
  addMonths,
  subMonths,
} from "date-fns";
import {
  Calendar,
  Users,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  Pill,
  Loader2,
  Download,
  TrendingUp,
  TrendingDown,
  BarChart3,
  CalendarDays,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Search,
  UserCheck,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart as RechartsPieChart,
  Pie,
  Legend,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";

import {
  getDailyAttendanceReport,
  getSectionAttendanceSummary,
  getStudentAttendanceSummary,
  listStudentAttendance,
} from "@/actions/attendance.action";
import { getStudents } from "@/actions/students.action";
import type {
  DailyAttendanceReport,
  Class,
  ClassSection,
  SectionAttendanceSummary,
  StudentAttendanceSummary,
  StudentAttendance,
  StudentListItem,
  AttendanceStatus,
} from "@/types";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import { formatDate } from "@/lib/format";

// ==========================================
// Constants
// ==========================================

const STATUS_COLORS: Record<AttendanceStatus, string> = {
  present: "#22c55e",
  absent: "#ef4444",
  late: "#eab308",
  excused: "#3b82f6",
  sick: "#a855f7",
};

const STATUS_LABELS: Record<AttendanceStatus, string> = {
  present: "Present",
  absent: "Absent",
  late: "Late",
  excused: "Excused",
  sick: "Sick",
};

// ==========================================
// Types
// ==========================================

interface WeeklyData {
  date: string;
  dayName: string;
  shortDate: string;
  data: DailyAttendanceReport | null;
}

interface ClassComparisonData {
  className: string;
  sectionName: string;
  sectionId: string;
  data: SectionAttendanceSummary | null;
}

interface AttendanceReportsProps {
  classes: Class[];
}

// ==========================================
// Main Component
// ==========================================

export function AttendanceReports({ classes }: AttendanceReportsProps) {
  const [isPending, startTransition] = useTransition();

  // Date state
  const [selectedDate, setSelectedDate] = useState<string>(format(new Date(), "yyyy-MM-dd"));

  // School-wide data
  const [report, setReport] = useState<DailyAttendanceReport | null>(null);
  const [weeklyData, setWeeklyData] = useState<WeeklyData[]>([]);

  // Class data
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedSectionId, setSelectedSectionId] = useState<string>("");
  const [sectionSummary, setSectionSummary] = useState<SectionAttendanceSummary | null>(null);
  const [classComparison, setClassComparison] = useState<ClassComparisonData[]>([]);

  // Student data
  const [studentSearchQuery, setStudentSearchQuery] = useState<string>("");
  const [studentsList, setStudentsList] = useState<StudentListItem[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState<string>("");
  const [studentSummary, setStudentSummary] = useState<StudentAttendanceSummary | null>(null);
  const [studentRecords, setStudentRecords] = useState<StudentAttendance[]>([]);
  const [heatmapMonth, setHeatmapMonth] = useState<Date>(new Date());
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [isLoadingStudentData, setIsLoadingStudentData] = useState(false);

  const selectedClass = classes.find((c) => c.id === selectedClassId);
  const sections = selectedClass?.sections || [];

  // ==========================================
  // Data Fetching
  // ==========================================

  const fetchReport = useCallback(async (date: string) => {
    const result = await getDailyAttendanceReport(date);
    if (result.success && result.data) {
      setReport(result.data);
    } else {
      setReport(null);
    }
  }, []);

  const fetchWeeklyData = useCallback(async (date: string) => {
    const currentDate = new Date(date);
    const weekStart = startOfWeek(currentDate, { weekStartsOn: 1 });
    const weekEnd = endOfWeek(currentDate, { weekStartsOn: 1 });
    const days = eachDayOfInterval({ start: weekStart, end: weekEnd });

    const promises = days.map(async (day) => {
      const dateStr = format(day, "yyyy-MM-dd");
      const result = await getDailyAttendanceReport(dateStr);
      return {
        date: dateStr,
        dayName: format(day, "EEE"),
        shortDate: format(day, "d/M"),
        data: result.success && result.data ? result.data : null,
      };
    });

    const results = await Promise.all(promises);
    setWeeklyData(results);
  }, []);

  const fetchClassComparison = useCallback(
    async (date: string) => {
      const allSections: { className: string; section: ClassSection }[] = [];
      for (const cls of classes) {
        if (cls.sections) {
          for (const section of cls.sections) {
            allSections.push({ className: cls.name, section });
          }
        }
      }

      const promises = allSections.map(async ({ className, section }) => {
        const result = await getSectionAttendanceSummary(section.id, date);
        return {
          className,
          sectionName: section.name,
          sectionId: section.id,
          data: result.success && result.data ? result.data : null,
        };
      });

      const results = await Promise.all(promises);
      setClassComparison(results.filter((r) => r.data !== null));
    },
    [classes]
  );

  const fetchSectionSummary = useCallback(async (sectionId: string, date: string) => {
    const result = await getSectionAttendanceSummary(sectionId, date);
    if (result.success && result.data) {
      setSectionSummary(result.data);
    } else {
      setSectionSummary(null);
    }
  }, []);

  const searchStudents = useCallback(async (query: string) => {
    if (query.length < 2) {
      setStudentsList([]);
      return;
    }
    setIsLoadingStudents(true);
    const result = await getStudents({ search: query, page_size: 10, status: "active" });
    if (result.success && result.data) {
      setStudentsList(result.data.items);
    } else {
      setStudentsList([]);
    }
    setIsLoadingStudents(false);
  }, []);

  const fetchStudentData = useCallback(async (studentId: string, month: Date) => {
    setIsLoadingStudentData(true);
    const monthStart = format(startOfMonth(month), "yyyy-MM-dd");
    const monthEnd = format(endOfMonth(month), "yyyy-MM-dd");

    const [summaryResult, recordsResult] = await Promise.all([
      getStudentAttendanceSummary(studentId, {
        start_date: monthStart,
        end_date: monthEnd,
      }),
      listStudentAttendance({
        student_id: studentId,
        start_date: monthStart,
        end_date: monthEnd,
        page_size: 100,
      }),
    ]);

    if (summaryResult.success && summaryResult.data) {
      setStudentSummary(summaryResult.data);
    } else {
      setStudentSummary(null);
    }

    if (recordsResult.success && recordsResult.data) {
      setStudentRecords(recordsResult.data.items);
    } else {
      setStudentRecords([]);
    }
    setIsLoadingStudentData(false);
  }, []);

  // ==========================================
  // Effects
  // ==========================================

  // Fetch school-wide data on date change
  useEffect(() => {
    if (selectedDate) {
      startTransition(async () => {
        await Promise.all([
          fetchReport(selectedDate),
          fetchWeeklyData(selectedDate),
          fetchClassComparison(selectedDate),
        ]);
      });
    }
  }, [selectedDate, fetchReport, fetchWeeklyData, fetchClassComparison]);

  // Fetch section summary when section changes
  useEffect(() => {
    if (selectedSectionId && selectedDate) {
      startTransition(async () => {
        await fetchSectionSummary(selectedSectionId, selectedDate);
      });
    } else {
      setSectionSummary(null);
    }
  }, [selectedSectionId, selectedDate, fetchSectionSummary]);

  // Reset section when class changes
  useEffect(() => {
    setSelectedSectionId("");
    setSectionSummary(null);
  }, [selectedClassId]);

  // Debounced student search
  useEffect(() => {
    const timeout = setTimeout(() => {
      searchStudents(studentSearchQuery);
    }, 300);
    return () => clearTimeout(timeout);
  }, [studentSearchQuery, searchStudents]);

  // Fetch student data when student or heatmap month changes
  useEffect(() => {
    if (selectedStudentId) {
      fetchStudentData(selectedStudentId, heatmapMonth);
    }
  }, [selectedStudentId, heatmapMonth, fetchStudentData]);

  // ==========================================
  // Computed Values
  // ==========================================

  // Attendance trend from weekly data
  const trend = useMemo(() => {
    const validDays = weeklyData.filter((d) => d.data && d.data.marked > 0);
    if (validDays.length < 2) return null;

    const rates = validDays.map((d) => d.data!.attendance_rate);
    const recent = rates.slice(-2);
    const diff = recent[1] - recent[0];

    return {
      direction: diff >= 0 ? ("up" as const) : ("down" as const),
      value: Math.abs(diff).toFixed(1),
    };
  }, [weeklyData]);

  // Chart data: attendance trend (area chart)
  const trendChartData = useMemo(
    () =>
      weeklyData
        .filter((d) => d.data !== null)
        .map((d) => ({
          name: d.dayName,
          date: d.shortDate,
          rate: d.data!.attendance_rate,
          present: d.data!.present,
          absent: d.data!.absent,
          late: d.data!.late,
        })),
    [weeklyData]
  );

  // Chart data: status distribution (pie chart)
  const statusDistributionData = useMemo(() => {
    if (!report) return [];
    return [
      { name: "Present", value: report.present, fill: STATUS_COLORS.present },
      { name: "Absent", value: report.absent, fill: STATUS_COLORS.absent },
      { name: "Late", value: report.late, fill: STATUS_COLORS.late },
      { name: "Excused", value: report.excused, fill: STATUS_COLORS.excused },
      { name: "Sick", value: report.sick, fill: STATUS_COLORS.sick },
    ].filter((d) => d.value > 0);
  }, [report]);

  // Chart data: class comparison (bar chart)
  const classComparisonChartData = useMemo(
    () =>
      classComparison
        .filter((c) => c.data !== null)
        .map((c) => ({
          name: `${c.className} ${c.sectionName}`,
          rate: c.data!.attendance_rate,
          present: c.data!.present,
          absent: c.data!.absent,
          total: c.data!.total_students,
        }))
        .sort((a, b) => b.rate - a.rate),
    [classComparison]
  );

  // Best and worst classes
  const bestClass = classComparisonChartData.length > 0 ? classComparisonChartData[0] : null;
  const worstClass =
    classComparisonChartData.length > 0
      ? classComparisonChartData[classComparisonChartData.length - 1]
      : null;

  // Quick date options
  const quickDates = useMemo(
    () => [
      { label: "Today", value: format(new Date(), "yyyy-MM-dd") },
      { label: "Yesterday", value: format(subDays(new Date(), 1), "yyyy-MM-dd") },
      { label: "Last Week", value: format(subDays(new Date(), 7), "yyyy-MM-dd") },
    ],
    []
  );

  // Selected student info
  const selectedStudent = studentsList.find((s) => s.id === selectedStudentId);

  // ==========================================
  // Heatmap Calendar
  // ==========================================

  const heatmapCalendar = useMemo(() => {
    const monthStart = startOfMonth(heatmapMonth);
    const monthEnd = endOfMonth(heatmapMonth);
    const weeks = eachWeekOfInterval(
      { start: monthStart, end: monthEnd },
      { weekStartsOn: 1 }
    );

    const recordsByDate = new Map<string, AttendanceStatus>();
    studentRecords.forEach((record) => {
      recordsByDate.set(record.date, record.status);
    });

    return weeks.map((weekStart) => {
      const weekEnd = endOfWeek(weekStart, { weekStartsOn: 1 });
      const days = eachDayOfInterval({ start: weekStart, end: weekEnd });
      return days.map((day) => {
        const dateStr = format(day, "yyyy-MM-dd");
        const isCurrentMonth = isSameMonth(day, heatmapMonth);
        const dayOfWeek = getDay(day);
        const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
        const status = recordsByDate.get(dateStr);

        return {
          date: dateStr,
          day: format(day, "d"),
          isCurrentMonth,
          isWeekend,
          status,
        };
      });
    });
  }, [heatmapMonth, studentRecords]);

  // ==========================================
  // CSV Export
  // ==========================================

  const handleExport = useCallback(() => {
    if (!report) return;

    const csvRows: (string | number)[][] = [
      [
        "Date",
        "Total Students",
        "Marked",
        "Unmarked",
        "Present",
        "Absent",
        "Late",
        "Excused",
        "Sick",
        "Attendance Rate",
        "Marking Rate",
      ],
      [
        report.date,
        report.total_students,
        report.marked,
        report.unmarked,
        report.present,
        report.absent,
        report.late,
        report.excused,
        report.sick,
        `${report.attendance_rate}%`,
        `${report.marking_rate}%`,
      ],
    ];

    // Add weekly data
    csvRows.push([], ["Weekly Overview"]);
    csvRows.push(["Day", "Date", "Present", "Absent", "Late", "Excused", "Sick", "Attendance Rate"]);
    weeklyData.forEach((day) => {
      if (day.data) {
        csvRows.push([
          day.dayName,
          day.date,
          day.data.present,
          day.data.absent,
          day.data.late,
          day.data.excused,
          day.data.sick,
          `${day.data.attendance_rate}%`,
        ]);
      }
    });

    // Add class comparison
    if (classComparison.length > 0) {
      csvRows.push([], ["Class Comparison"]);
      csvRows.push(["Class", "Section", "Total", "Present", "Absent", "Late", "Rate"]);
      classComparison.forEach((c) => {
        if (c.data) {
          csvRows.push([
            c.className,
            c.sectionName,
            c.data.total_students,
            c.data.present,
            c.data.absent,
            c.data.late,
            `${c.data.attendance_rate}%`,
          ]);
        }
      });
    }

    const csvContent = csvRows.map((row) => row.join(",")).join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `attendance_report_${selectedDate}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [report, weeklyData, classComparison, selectedDate]);

  // ==========================================
  // Render
  // ==========================================

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/attendance">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Attendance Reports</h1>
            <p className="text-muted-foreground">
              Analyze attendance statistics, trends, and patterns
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport} disabled={!report}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Date & Quick Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-full sm:w-[200px]">
              <Label htmlFor="report-date">Report Date</Label>
              <Input
                id="report-date"
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="mt-1.5"
              />
            </div>
            <div className="flex gap-2">
              {quickDates.map((qd) => (
                <Button
                  key={qd.value}
                  variant={selectedDate === qd.value ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedDate(qd.value)}
                >
                  {qd.label}
                </Button>
              ))}
            </div>
            {isPending && (
              <div className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading...
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Main Tabs */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">
            <BarChart3 className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="by-class">
            <Users className="h-4 w-4 mr-2" />
            By Class
          </TabsTrigger>
          <TabsTrigger value="by-student">
            <UserCheck className="h-4 w-4 mr-2" />
            By Student
          </TabsTrigger>
        </TabsList>

        {/* ============================== */}
        {/* OVERVIEW TAB                   */}
        {/* ============================== */}
        <TabsContent value="overview" className="space-y-6">
          {isPending && !report ? (
            <OverviewSkeleton />
          ) : report ? (
            <>
              {/* Summary Stats Cards */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Attendance Rate</CardTitle>
                    {trend &&
                      (trend.direction === "up" ? (
                        <TrendingUp className="h-4 w-4 text-green-500" />
                      ) : (
                        <TrendingDown className="h-4 w-4 text-red-500" />
                      ))}
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{report.attendance_rate}%</div>
                    {trend && (
                      <p
                        className={`text-xs ${
                          trend.direction === "up" ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {trend.direction === "up" ? "+" : "-"}
                        {trend.value}% from previous day
                      </p>
                    )}
                    <Progress value={report.attendance_rate} className="mt-2" />
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Present / Absent / Late</CardTitle>
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">
                      <span className="text-green-600">{report.present}</span>
                      <span className="text-muted-foreground mx-1">/</span>
                      <span className="text-red-600">{report.absent}</span>
                      <span className="text-muted-foreground mx-1">/</span>
                      <span className="text-yellow-600">{report.late}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Out of {report.total_students} total students
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Best Attending</CardTitle>
                    <TrendingUp className="h-4 w-4 text-green-500" />
                  </CardHeader>
                  <CardContent>
                    {bestClass ? (
                      <>
                        <div className="text-2xl font-bold text-green-600">{bestClass.rate}%</div>
                        <p className="text-xs text-muted-foreground mt-1 truncate">
                          {bestClass.name}
                        </p>
                      </>
                    ) : (
                      <div className="text-sm text-muted-foreground">No data</div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Most Absent</CardTitle>
                    <TrendingDown className="h-4 w-4 text-red-500" />
                  </CardHeader>
                  <CardContent>
                    {worstClass ? (
                      <>
                        <div className="text-2xl font-bold text-red-600">{worstClass.rate}%</div>
                        <p className="text-xs text-muted-foreground mt-1 truncate">
                          {worstClass.name}
                        </p>
                      </>
                    ) : (
                      <div className="text-sm text-muted-foreground">No data</div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Charts Row */}
              <div className="grid gap-6 lg:grid-cols-2">
                {/* Attendance Trend Chart */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <CalendarDays className="h-5 w-5" />
                      Weekly Attendance Trend
                    </CardTitle>
                    <CardDescription>
                      Daily attendance rate for the week of{" "}
                      {format(new Date(selectedDate), "MMMM d, yyyy")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {trendChartData.length > 0 ? (
                      <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart
                            data={trendChartData}
                            margin={{ top: 5, right: 10, left: -10, bottom: 0 }}
                          >
                            <defs>
                              <linearGradient id="attendanceGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                            <XAxis
                              dataKey="name"
                              tick={{ fontSize: 12 }}
                              tickLine={false}
                              axisLine={false}
                            />
                            <YAxis
                              domain={[0, 100]}
                              tick={{ fontSize: 12 }}
                              tickLine={false}
                              axisLine={false}
                              tickFormatter={(value: number) => `${value}%`}
                            />
                            <Tooltip
                              content={({ active, payload, label }) => {
                                if (!active || !payload || payload.length === 0) return null;
                                const data = payload[0].payload as (typeof trendChartData)[0];
                                return (
                                  <div className="rounded-lg border bg-background p-3 shadow-md">
                                    <p className="text-sm font-medium">
                                      {label} ({data.date})
                                    </p>
                                    <p className="text-sm text-green-600">Rate: {data.rate}%</p>
                                    <p className="text-xs text-muted-foreground">
                                      Present: {data.present} | Absent: {data.absent} | Late:{" "}
                                      {data.late}
                                    </p>
                                  </div>
                                );
                              }}
                            />
                            <Area
                              type="monotone"
                              dataKey="rate"
                              stroke="#22c55e"
                              strokeWidth={2}
                              fill="url(#attendanceGradient)"
                              dot={{ r: 4, fill: "#22c55e", strokeWidth: 2 }}
                              activeDot={{ r: 6 }}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <EmptyChart message="No attendance data for this week" />
                    )}
                  </CardContent>
                </Card>

                {/* Status Distribution Pie Chart */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <BarChart3 className="h-5 w-5" />
                      Status Distribution
                    </CardTitle>
                    <CardDescription>
                      Breakdown for {format(new Date(selectedDate), "MMMM d, yyyy")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {statusDistributionData.length > 0 ? (
                      <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <RechartsPieChart>
                            <Pie
                              data={statusDistributionData}
                              dataKey="value"
                              nameKey="name"
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={100}
                              paddingAngle={2}
                              label={({ name, value }) => `${name}: ${value}`}
                            >
                              {statusDistributionData.map((entry, index) => (
                                <Cell key={index} fill={entry.fill} />
                              ))}
                            </Pie>
                            <Legend
                              verticalAlign="bottom"
                              height={36}
                              formatter={(value: string) => (
                                <span className="text-sm">{value}</span>
                              )}
                            />
                            <Tooltip
                              content={({ active, payload }) => {
                                if (!active || !payload || payload.length === 0) return null;
                                const data = payload[0];
                                const total = report.marked || 1;
                                const pct = (((data.value as number) / total) * 100).toFixed(1);
                                return (
                                  <div className="rounded-lg border bg-background p-3 shadow-md">
                                    <p className="text-sm font-medium">{data.name}</p>
                                    <p className="text-sm">
                                      {data.value} students ({pct}%)
                                    </p>
                                  </div>
                                );
                              }}
                            />
                          </RechartsPieChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <EmptyChart message="No attendance data for this date" />
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Class Comparison Bar Chart */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-5 w-5" />
                    Class Comparison
                  </CardTitle>
                  <CardDescription>
                    Attendance rate by class/section for{" "}
                    {format(new Date(selectedDate), "MMMM d, yyyy")}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {classComparisonChartData.length > 0 ? (
                    <div className="h-[350px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={classComparisonChartData}
                          margin={{ top: 5, right: 10, left: -10, bottom: 60 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                          <XAxis
                            dataKey="name"
                            tick={{ fontSize: 11 }}
                            tickLine={false}
                            axisLine={false}
                            angle={-45}
                            textAnchor="end"
                            interval={0}
                            height={80}
                          />
                          <YAxis
                            domain={[0, 100]}
                            tick={{ fontSize: 12 }}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(value: number) => `${value}%`}
                          />
                          <Tooltip
                            content={({ active, payload }) => {
                              if (!active || !payload || payload.length === 0) return null;
                              const data = payload[0].payload as (typeof classComparisonChartData)[0];
                              return (
                                <div className="rounded-lg border bg-background p-3 shadow-md">
                                  <p className="text-sm font-medium">{data.name}</p>
                                  <p className="text-sm text-green-600">Rate: {data.rate}%</p>
                                  <p className="text-xs text-muted-foreground">
                                    Present: {data.present} | Absent: {data.absent} | Total:{" "}
                                    {data.total}
                                  </p>
                                </div>
                              );
                            }}
                          />
                          <Bar dataKey="rate" radius={[4, 4, 0, 0]} maxBarSize={40}>
                            {classComparisonChartData.map((entry, index) => (
                              <Cell
                                key={index}
                                fill={
                                  entry.rate >= 90
                                    ? "#22c55e"
                                    : entry.rate >= 75
                                      ? "#eab308"
                                      : "#ef4444"
                                }
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChart message="No class data available for this date" />
                  )}
                </CardContent>
              </Card>

              {/* Weekly Data Table */}
              <Card>
                <CardHeader>
                  <CardTitle>Weekly Details</CardTitle>
                  <CardDescription>Day-by-day attendance breakdown for the week</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="rounded-md border overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Day</TableHead>
                          <TableHead className="text-center">Present</TableHead>
                          <TableHead className="text-center">Absent</TableHead>
                          <TableHead className="hidden sm:table-cell text-center">Late</TableHead>
                          <TableHead className="hidden md:table-cell text-center">Excused</TableHead>
                          <TableHead className="hidden md:table-cell text-center">Sick</TableHead>
                          <TableHead className="text-right">Rate</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {weeklyData.length > 0 ? (
                          weeklyData.map((day) => (
                            <TableRow
                              key={day.date}
                              className={day.date === selectedDate ? "bg-muted/50" : ""}
                            >
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <span className="font-medium">{day.dayName}</span>
                                  <span className="text-muted-foreground text-sm">
                                    {day.shortDate}
                                  </span>
                                  {day.date === selectedDate && (
                                    <Badge variant="secondary" className="text-xs">
                                      Selected
                                    </Badge>
                                  )}
                                </div>
                              </TableCell>
                              {day.data ? (
                                <>
                                  <TableCell className="text-center">
                                    <span className="text-green-600 font-medium">
                                      {day.data.present}
                                    </span>
                                  </TableCell>
                                  <TableCell className="text-center">
                                    <span className="text-red-600 font-medium">
                                      {day.data.absent}
                                    </span>
                                  </TableCell>
                                  <TableCell className="hidden sm:table-cell text-center">
                                    <span className="text-yellow-600 font-medium">
                                      {day.data.late}
                                    </span>
                                  </TableCell>
                                  <TableCell className="hidden md:table-cell text-center">
                                    <span className="text-blue-600 font-medium">
                                      {day.data.excused}
                                    </span>
                                  </TableCell>
                                  <TableCell className="hidden md:table-cell text-center">
                                    <span className="text-purple-600 font-medium">
                                      {day.data.sick}
                                    </span>
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <Badge
                                      variant="secondary"
                                      className={
                                        day.data.attendance_rate >= 90
                                          ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                                          : day.data.attendance_rate >= 75
                                            ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                                            : "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                                      }
                                    >
                                      {day.data.attendance_rate}%
                                    </Badge>
                                  </TableCell>
                                </>
                              ) : (
                                <TableCell
                                  colSpan={6}
                                  className="text-center text-muted-foreground"
                                >
                                  No data
                                </TableCell>
                              )}
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                              No weekly data available
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <EmptyState
              icon={Calendar}
              title="No Attendance Data"
              description="No attendance data found for the selected date. Try selecting a different date or start marking attendance."
            />
          )}
        </TabsContent>

        {/* ============================== */}
        {/* BY CLASS TAB                   */}
        {/* ============================== */}
        <TabsContent value="by-class" className="space-y-6">
          {/* Class/Section Selector */}
          <Card>
            <CardContent className="pt-6">
              <CollapsibleFilters
                activeFilterCount={
                  (selectedClassId ? 1 : 0) +
                  (selectedSectionId ? 1 : 0)
                }
              >
                <div className="w-full md:w-[240px]">
                  <Label htmlFor="class-select">Class</Label>
                  <Select value={selectedClassId} onValueChange={setSelectedClassId}>
                    <SelectTrigger id="class-select" className="mt-1.5 w-full">
                      <SelectValue placeholder="Select class" />
                    </SelectTrigger>
                    <SelectContent>
                      {classes.map((cls) => (
                        <SelectItem key={cls.id} value={cls.id}>
                          {cls.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="w-full md:w-[240px]">
                  <Label htmlFor="section-select">Section</Label>
                  <Select
                    value={selectedSectionId}
                    onValueChange={setSelectedSectionId}
                    disabled={sections.length === 0}
                  >
                    <SelectTrigger id="section-select" className="mt-1.5 w-full">
                      <SelectValue
                        placeholder={
                          sections.length === 0 ? "Select class first" : "Select section"
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {sections.map((section) => (
                        <SelectItem key={section.id} value={section.id}>
                          {section.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CollapsibleFilters>
            </CardContent>
          </Card>

          {isPending && selectedSectionId ? (
            <ClassSkeleton />
          ) : sectionSummary ? (
            <>
              {/* Section Stats */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Total</CardTitle>
                    <Users className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{sectionSummary.total_students}</div>
                    <p className="text-xs text-muted-foreground">
                      {sectionSummary.marked} marked, {sectionSummary.unmarked} pending
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Present</CardTitle>
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-green-600">
                      {sectionSummary.present}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Absent</CardTitle>
                    <XCircle className="h-4 w-4 text-red-500" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-red-600">{sectionSummary.absent}</div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Late</CardTitle>
                    <Clock className="h-4 w-4 text-yellow-500" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-yellow-600">{sectionSummary.late}</div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Rate</CardTitle>
                    <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{sectionSummary.attendance_rate}%</div>
                    <Progress value={sectionSummary.attendance_rate} className="mt-2" />
                  </CardContent>
                </Card>
              </div>

              {/* Status Breakdown */}
              <Card>
                <CardHeader>
                  <CardTitle>Status Breakdown</CardTitle>
                  <CardDescription>
                    {selectedClass?.name} -{" "}
                    {sections.find((s) => s.id === selectedSectionId)?.name} on{" "}
                    {format(new Date(selectedDate), "dd/MM/yyyy")}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-5">
                    {(
                      [
                        {
                          label: "Present",
                          value: sectionSummary.present,
                          color: "text-green-600",
                          bg: "bg-green-100 dark:bg-green-900",
                          icon: CheckCircle2,
                        },
                        {
                          label: "Absent",
                          value: sectionSummary.absent,
                          color: "text-red-600",
                          bg: "bg-red-100 dark:bg-red-900",
                          icon: XCircle,
                        },
                        {
                          label: "Late",
                          value: sectionSummary.late,
                          color: "text-yellow-600",
                          bg: "bg-yellow-100 dark:bg-yellow-900",
                          icon: Clock,
                        },
                        {
                          label: "Excused",
                          value: sectionSummary.excused,
                          color: "text-blue-600",
                          bg: "bg-blue-100 dark:bg-blue-900",
                          icon: AlertCircle,
                        },
                        {
                          label: "Sick",
                          value: sectionSummary.sick,
                          color: "text-purple-600",
                          bg: "bg-purple-100 dark:bg-purple-900",
                          icon: Pill,
                        },
                      ] as const
                    ).map((item) => {
                      const Icon = item.icon;
                      return (
                        <div key={item.label} className="flex items-center gap-3 rounded-lg border p-4">
                          <div className={`rounded-full ${item.bg} p-2`}>
                            <Icon className={`h-5 w-5 ${item.color}`} />
                          </div>
                          <div>
                            <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
                            <p className="text-sm text-muted-foreground">{item.label}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Marking & Rate Progress */}
              <Card>
                <CardHeader>
                  <CardTitle>Progress</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-6 md:grid-cols-2">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Marking Progress</span>
                        <span className="text-sm text-muted-foreground">
                          {sectionSummary.marked} of {sectionSummary.total_students}
                        </span>
                      </div>
                      <Progress
                        value={
                          sectionSummary.total_students > 0
                            ? (sectionSummary.marked / sectionSummary.total_students) * 100
                            : 0
                        }
                      />
                      {sectionSummary.unmarked > 0 && (
                        <p className="text-xs text-muted-foreground">
                          {sectionSummary.unmarked} students still need attendance marked
                        </p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Attendance Rate</span>
                        <span className="text-sm text-muted-foreground">
                          {sectionSummary.attendance_rate}%
                        </span>
                      </div>
                      <Progress
                        value={sectionSummary.attendance_rate}
                        className={
                          sectionSummary.attendance_rate >= 90
                            ? "[&>div]:bg-green-500"
                            : sectionSummary.attendance_rate >= 75
                              ? "[&>div]:bg-yellow-500"
                              : "[&>div]:bg-red-500"
                        }
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : !selectedSectionId ? (
            <EmptyState
              icon={Users}
              title="Select a Class and Section"
              description="Choose a class and section above to view detailed attendance reports for that group."
            />
          ) : (
            <EmptyState
              icon={Calendar}
              title="No Data Available"
              description="No attendance data found for the selected class and date. Try a different date."
            />
          )}
        </TabsContent>

        {/* ============================== */}
        {/* BY STUDENT TAB                 */}
        {/* ============================== */}
        <TabsContent value="by-student" className="space-y-6">
          {/* Student Search */}
          <Card>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div>
                  <Label htmlFor="student-search">Search Student</Label>
                  <div className="relative mt-1.5">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      id="student-search"
                      placeholder="Type student name or ID to search..."
                      value={studentSearchQuery}
                      onChange={(e) => setStudentSearchQuery(e.target.value)}
                      className="pl-9"
                    />
                    {isLoadingStudents && (
                      <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
                    )}
                  </div>
                </div>

                {/* Search Results */}
                {studentsList.length > 0 && (
                  <div className="rounded-md border divide-y max-h-[240px] overflow-y-auto">
                    {studentsList.map((student) => (
                      <button
                        key={student.id}
                        type="button"
                        className={`flex w-full items-center gap-3 p-3 text-left transition-colors hover:bg-muted/50 ${
                          selectedStudentId === student.id ? "bg-muted" : ""
                        }`}
                        onClick={() => {
                          setSelectedStudentId(student.id);
                          setStudentSearchQuery("");
                          setStudentsList([]);
                          setHeatmapMonth(new Date());
                        }}
                      >
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium">
                          {student.first_name[0]}
                          {student.last_name[0]}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium truncate">
                            {student.first_name}{" "}
                            {student.middle_name ? `${student.middle_name} ` : ""}
                            {student.last_name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {student.student_id}
                            {student.class_name ? ` - ${student.class_name}` : ""}
                            {student.section_name ? ` (${student.section_name})` : ""}
                          </p>
                        </div>
                        <Badge variant="outline" className="shrink-0 text-xs">
                          {student.status}
                        </Badge>
                      </button>
                    ))}
                  </div>
                )}

                {studentSearchQuery.length >= 2 &&
                  !isLoadingStudents &&
                  studentsList.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No students found matching &quot;{studentSearchQuery}&quot;
                    </p>
                  )}
              </div>
            </CardContent>
          </Card>

          {/* Student Attendance Data */}
          {selectedStudentId ? (
            isLoadingStudentData ? (
              <StudentSkeleton />
            ) : (
              <>
                {/* Student Info Header */}
                {selectedStudent && (
                  <Card>
                    <CardContent className="pt-6">
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-lg font-semibold text-primary">
                          {selectedStudent.first_name[0]}
                          {selectedStudent.last_name[0]}
                        </div>
                        <div className="min-w-0 flex-1">
                          <h3 className="text-lg font-semibold truncate">
                            {selectedStudent.first_name}{" "}
                            {selectedStudent.middle_name
                              ? `${selectedStudent.middle_name} `
                              : ""}
                            {selectedStudent.last_name}
                          </h3>
                          <p className="text-sm text-muted-foreground">
                            {selectedStudent.student_id}
                            {selectedStudent.class_name
                              ? ` | ${selectedStudent.class_name}`
                              : ""}
                            {selectedStudent.section_name
                              ? ` (${selectedStudent.section_name})`
                              : ""}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Student Summary Stats */}
                {studentSummary ? (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <Card>
                      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Attendance Rate</CardTitle>
                        <UserCheck className="h-4 w-4 text-muted-foreground" />
                      </CardHeader>
                      <CardContent>
                        <div className="text-2xl font-bold">{studentSummary.attendance_rate}%</div>
                        <Progress value={studentSummary.attendance_rate} className="mt-2" />
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Days Present</CardTitle>
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      </CardHeader>
                      <CardContent>
                        <div className="text-2xl font-bold text-green-600">
                          {studentSummary.present}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          Out of {studentSummary.total_days} school days
                        </p>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Days Absent</CardTitle>
                        <XCircle className="h-4 w-4 text-red-500" />
                      </CardHeader>
                      <CardContent>
                        <div className="text-2xl font-bold text-red-600">
                          {studentSummary.absent}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {studentSummary.sick} sick, {studentSummary.excused} excused
                        </p>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Days Late</CardTitle>
                        <Clock className="h-4 w-4 text-yellow-500" />
                      </CardHeader>
                      <CardContent>
                        <div className="text-2xl font-bold text-yellow-600">
                          {studentSummary.late}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {studentSummary.total_days} total days tracked
                        </p>
                      </CardContent>
                    </Card>
                  </div>
                ) : (
                  <Card>
                    <CardContent className="py-8 text-center text-muted-foreground">
                      No attendance summary available for this period
                    </CardContent>
                  </Card>
                )}

                {/* Attendance Heatmap Calendar */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Attendance Calendar</CardTitle>
                        <CardDescription>
                          Daily attendance for {format(heatmapMonth, "MMMM yyyy")}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => setHeatmapMonth((prev) => subMonths(prev, 1))}
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setHeatmapMonth(new Date())}
                        >
                          Today
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => setHeatmapMonth((prev) => addMonths(prev, 1))}
                        >
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {/* Legend */}
                    <div className="mb-4 flex flex-wrap gap-3">
                      {(Object.keys(STATUS_COLORS) as AttendanceStatus[]).map((status) => (
                        <div key={status} className="flex items-center gap-1.5">
                          <div
                            className="h-3 w-3 rounded-sm"
                            style={{ backgroundColor: STATUS_COLORS[status] }}
                          />
                          <span className="text-xs text-muted-foreground">
                            {STATUS_LABELS[status]}
                          </span>
                        </div>
                      ))}
                      <div className="flex items-center gap-1.5">
                        <div className="h-3 w-3 rounded-sm bg-muted" />
                        <span className="text-xs text-muted-foreground">No data</span>
                      </div>
                    </div>

                    {/* Calendar Grid */}
                    <div className="overflow-x-auto">
                      <div className="min-w-[320px]">
                        {/* Day of week headers */}
                        <div className="grid grid-cols-7 gap-1 mb-1">
                          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
                            <div
                              key={day}
                              className="text-center text-xs font-medium text-muted-foreground py-1"
                            >
                              {day}
                            </div>
                          ))}
                        </div>

                        {/* Calendar weeks */}
                        {heatmapCalendar.map((week, weekIndex) => (
                          <div key={weekIndex} className="grid grid-cols-7 gap-1 mb-1">
                            {week.map((day) => {
                              const bgColor = !day.isCurrentMonth
                                ? "bg-transparent"
                                : day.status
                                  ? ""
                                  : day.isWeekend
                                    ? "bg-muted/30"
                                    : "bg-muted/50";
                              const statusColor = day.status
                                ? STATUS_COLORS[day.status]
                                : undefined;

                              return (
                                <div
                                  key={day.date}
                                  className={`relative flex h-10 items-center justify-center rounded-md text-xs transition-colors ${bgColor} ${
                                    !day.isCurrentMonth
                                      ? "text-muted-foreground/30"
                                      : "text-foreground"
                                  }`}
                                  style={
                                    statusColor
                                      ? {
                                          backgroundColor: `${statusColor}20`,
                                          border: `1px solid ${statusColor}50`,
                                        }
                                      : undefined
                                  }
                                  title={
                                    day.status
                                      ? `${formatDate(day.date)} - ${STATUS_LABELS[day.status]}`
                                      : formatDate(day.date)
                                  }
                                >
                                  <span className="relative z-10">{day.day}</span>
                                  {day.status && day.isCurrentMonth && (
                                    <div
                                      className="absolute bottom-1 left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full"
                                      style={{ backgroundColor: statusColor }}
                                    />
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Student Attendance Records Table */}
                <Card>
                  <CardHeader>
                    <CardTitle>Attendance Records</CardTitle>
                    <CardDescription>
                      Individual attendance entries for {format(heatmapMonth, "MMMM yyyy")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {studentRecords.length > 0 ? (
                      <div className="rounded-md border overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Date</TableHead>
                              <TableHead>Status</TableHead>
                              <TableHead className="hidden sm:table-cell">Check-in</TableHead>
                              <TableHead className="hidden md:table-cell">Remarks</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {studentRecords
                              .sort(
                                (a, b) =>
                                  new Date(b.date).getTime() - new Date(a.date).getTime()
                              )
                              .map((record) => (
                                <TableRow key={record.id}>
                                  <TableCell className="font-medium">
                                    {formatDate(record.date)}
                                  </TableCell>
                                  <TableCell>
                                    <StatusBadge status={record.status} />
                                  </TableCell>
                                  <TableCell className="hidden sm:table-cell text-muted-foreground">
                                    {record.check_in_time || "-"}
                                  </TableCell>
                                  <TableCell className="hidden md:table-cell text-muted-foreground max-w-[200px] truncate">
                                    {record.remarks || record.excuse_reason || "-"}
                                  </TableCell>
                                </TableRow>
                              ))}
                          </TableBody>
                        </Table>
                      </div>
                    ) : (
                      <div className="py-8 text-center text-muted-foreground">
                        No attendance records found for this month
                      </div>
                    )}
                  </CardContent>
                </Card>
              </>
            )
          ) : (
            <EmptyState
              icon={UserCheck}
              title="Search for a Student"
              description="Type a student name or ID in the search box above to view their individual attendance record and calendar heatmap."
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ==========================================
// Sub-Components
// ==========================================

function StatusBadge({ status }: { status: AttendanceStatus }) {
  const config: Record<
    AttendanceStatus,
    { label: string; className: string }
  > = {
    present: {
      label: "Present",
      className:
        "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    },
    absent: {
      label: "Absent",
      className: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    },
    late: {
      label: "Late",
      className:
        "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    },
    excused: {
      label: "Excused",
      className:
        "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    },
    sick: {
      label: "Sick",
      className:
        "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    },
  };

  const { label, className } = config[status];
  return (
    <Badge variant="secondary" className={className}>
      {label}
    </Badge>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="flex h-[300px] flex-col items-center justify-center text-muted-foreground">
      <BarChart3 className="h-10 w-10 mb-2 opacity-50" />
      <p className="text-sm">{message}</p>
    </div>
  );
}

function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center py-16">
        <Icon className="h-12 w-12 text-muted-foreground mb-4" />
        <h3 className="text-lg font-medium">{title}</h3>
        <p className="text-sm text-muted-foreground text-center max-w-md mt-2">{description}</p>
      </CardContent>
    </Card>
  );
}

function OverviewSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
              <Skeleton className="mt-2 h-2 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        {[...Array(2)].map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-56" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-[300px] w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ClassSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {[...Array(5)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-16" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-12" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function StudentSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-4">
            <Skeleton className="h-12 w-12 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-56" />
            </div>
          </div>
        </CardContent>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
              <Skeleton className="mt-2 h-2 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[250px] w-full" />
        </CardContent>
      </Card>
    </div>
  );
}
