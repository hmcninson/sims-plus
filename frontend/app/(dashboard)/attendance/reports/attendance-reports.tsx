"use client";

import { useState, useTransition, useEffect, useCallback } from "react";
import { format, subDays, startOfWeek, endOfWeek, eachDayOfInterval } from "date-fns";
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
} from "lucide-react";

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

import { getDailyAttendanceReport, getSectionAttendanceSummary } from "@/actions/attendance.action";
import { getClasses } from "@/actions/academic.action";
import type { DailyAttendanceReport, Class, SectionAttendanceSummary } from "@/types";

interface WeeklyData {
  date: string;
  dayName: string;
  data: DailyAttendanceReport | null;
}

export function AttendanceReports() {
  const [isPending, startTransition] = useTransition();
  const [selectedDate, setSelectedDate] = useState<string>(format(new Date(), "yyyy-MM-dd"));
  const [report, setReport] = useState<DailyAttendanceReport | null>(null);
  const [weeklyData, setWeeklyData] = useState<WeeklyData[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedSectionId, setSelectedSectionId] = useState<string>("");
  const [sectionSummary, setSectionSummary] = useState<SectionAttendanceSummary | null>(null);
  const [viewMode, setViewMode] = useState<"school" | "class">("school");

  // Fetch classes on mount
  useEffect(() => {
    const fetchClasses = async () => {
      const result = await getClasses(true);
      if (result.success && result.data) {
        setClasses(result.data);
      }
    };
    fetchClasses();
  }, []);

  const selectedClass = classes.find((c) => c.id === selectedClassId);
  const sections = selectedClass?.sections || [];

  // Fetch daily report
  const fetchReport = useCallback(async (date: string) => {
    startTransition(async () => {
      const result = await getDailyAttendanceReport(date);
      if (result.success && result.data) {
        setReport(result.data);
      } else {
        setReport(null);
      }
    });
  }, []);

  // Fetch weekly data
  const fetchWeeklyData = useCallback(async (date: string) => {
    const currentDate = new Date(date);
    const weekStart = startOfWeek(currentDate, { weekStartsOn: 1 }); // Monday
    const weekEnd = endOfWeek(currentDate, { weekStartsOn: 1 }); // Sunday
    const days = eachDayOfInterval({ start: weekStart, end: weekEnd });

    const promises = days.map(async (day) => {
      const dateStr = format(day, "yyyy-MM-dd");
      const result = await getDailyAttendanceReport(dateStr);
      return {
        date: dateStr,
        dayName: format(day, "EEE"),
        data: result.success && result.data ? result.data : null,
      };
    });

    const results = await Promise.all(promises);
    setWeeklyData(results);
  }, []);

  // Fetch section summary
  const fetchSectionSummary = useCallback(async (sectionId: string, date: string) => {
    const result = await getSectionAttendanceSummary(sectionId, date);
    if (result.success && result.data) {
      setSectionSummary(result.data);
    } else {
      setSectionSummary(null);
    }
  }, []);

  // Fetch data on date change
  useEffect(() => {
    if (selectedDate) {
      fetchReport(selectedDate);
      fetchWeeklyData(selectedDate);
    }
  }, [selectedDate, fetchReport, fetchWeeklyData]);

  // Fetch section summary when section changes
  useEffect(() => {
    if (selectedSectionId && selectedDate) {
      fetchSectionSummary(selectedSectionId, selectedDate);
    } else {
      setSectionSummary(null);
    }
  }, [selectedSectionId, selectedDate, fetchSectionSummary]);

  // Export to CSV
  const handleExport = () => {
    if (!report) return;

    const csvData = [
      ["Date", "Total Students", "Marked", "Unmarked", "Present", "Absent", "Late", "Excused", "Sick", "Attendance Rate", "Marking Rate"],
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
    csvData.push([""], ["Weekly Overview"]);
    csvData.push(["Day", "Present", "Absent", "Late", "Attendance Rate"]);
    weeklyData.forEach((day) => {
      if (day.data) {
        csvData.push([
          `${day.dayName} (${day.date})`,
          day.data.present,
          day.data.absent,
          day.data.late,
          `${day.data.attendance_rate}%`,
        ]);
      }
    });

    const csvContent = csvData.map((row) => row.join(",")).join("\n");
    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `attendance_report_${selectedDate}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Get quick date options
  const quickDates = [
    { label: "Today", value: format(new Date(), "yyyy-MM-dd") },
    { label: "Yesterday", value: format(subDays(new Date(), 1), "yyyy-MM-dd") },
    { label: "Last Week", value: format(subDays(new Date(), 7), "yyyy-MM-dd") },
  ];

  // Calculate attendance trend
  const getTrend = () => {
    const validDays = weeklyData.filter((d) => d.data && d.data.marked > 0);
    if (validDays.length < 2) return null;

    const rates = validDays.map((d) => d.data!.attendance_rate);
    const recent = rates.slice(-2);
    const diff = recent[1] - recent[0];

    return {
      direction: diff >= 0 ? "up" : "down",
      value: Math.abs(diff).toFixed(1),
    };
  };

  const trend = getTrend();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Attendance Reports</h1>
          <p className="text-muted-foreground">
            View and analyze attendance statistics and trends
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport} disabled={!report}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Report Filters</CardTitle>
          <CardDescription>Select date and scope for the report</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-[280px]">
              <Label htmlFor="date">Date</Label>
              <Input
                id="date"
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

            <div className="ml-auto flex gap-2">
              <Button
                variant={viewMode === "school" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("school")}
              >
                <BarChart3 className="mr-1 h-4 w-4" />
                School-wide
              </Button>
              <Button
                variant={viewMode === "class" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("class")}
              >
                <Users className="mr-1 h-4 w-4" />
                By Class
              </Button>
            </div>
          </div>

          {viewMode === "class" && (
            <div className="mt-4 flex flex-wrap gap-4">
              <div className="w-[280px]">
                <Label htmlFor="class">Class</Label>
                <Select value={selectedClassId} onValueChange={setSelectedClassId}>
                  <SelectTrigger id="class" className="mt-1.5 w-full">
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

              <div className="w-[280px]">
                <Label htmlFor="section">Section</Label>
                <Select
                  value={selectedSectionId}
                  onValueChange={setSelectedSectionId}
                  disabled={sections.length === 0}
                >
                  <SelectTrigger id="section" className="mt-1.5 w-full">
                    <SelectValue
                      placeholder={sections.length === 0 ? "Select class first" : "Select section"}
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
            </div>
          )}
        </CardContent>
      </Card>

      {isPending ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : viewMode === "school" && report ? (
        <>
          {/* School-wide Stats */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Students</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{report.total_students}</div>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="secondary">{report.marked} marked</Badge>
                  {report.unmarked > 0 && (
                    <Badge variant="outline" className="text-yellow-600">
                      {report.unmarked} pending
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Attendance Rate</CardTitle>
                {trend && (
                  trend.direction === "up" ? (
                    <TrendingUp className="h-4 w-4 text-green-500" />
                  ) : (
                    <TrendingDown className="h-4 w-4 text-red-500" />
                  )
                )}
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{report.attendance_rate}%</div>
                {trend && (
                  <p className={`text-xs ${trend.direction === "up" ? "text-green-600" : "text-red-600"}`}>
                    {trend.direction === "up" ? "+" : "-"}{trend.value}% from previous day
                  </p>
                )}
                <Progress value={report.attendance_rate} className="mt-2" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Marking Progress</CardTitle>
                <CalendarDays className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{report.marking_rate}%</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {report.marked} of {report.total_students} marked
                </p>
                <Progress value={report.marking_rate} className="mt-2" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Report Date</CardTitle>
                <Calendar className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {format(new Date(report.date), "d MMM")}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {format(new Date(report.date), "EEEE, yyyy")}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Status Breakdown */}
          <Card>
            <CardHeader>
              <CardTitle>Attendance Breakdown</CardTitle>
              <CardDescription>
                Distribution of attendance statuses for {format(new Date(selectedDate), "MMMM d, yyyy")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-5">
                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-green-100 p-2 dark:bg-green-900">
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{report.present}</p>
                    <p className="text-sm text-muted-foreground">Present</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-red-100 p-2 dark:bg-red-900">
                    <XCircle className="h-5 w-5 text-red-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{report.absent}</p>
                    <p className="text-sm text-muted-foreground">Absent</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-yellow-100 p-2 dark:bg-yellow-900">
                    <Clock className="h-5 w-5 text-yellow-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{report.late}</p>
                    <p className="text-sm text-muted-foreground">Late</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-blue-100 p-2 dark:bg-blue-900">
                    <AlertCircle className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{report.excused}</p>
                    <p className="text-sm text-muted-foreground">Excused</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-purple-100 p-2 dark:bg-purple-900">
                    <Pill className="h-5 w-5 text-purple-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{report.sick}</p>
                    <p className="text-sm text-muted-foreground">Sick</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Weekly Overview */}
          <Card>
            <CardHeader>
              <CardTitle>Weekly Overview</CardTitle>
              <CardDescription>Attendance trends for the current week</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Day</TableHead>
                      <TableHead className="text-center">Present</TableHead>
                      <TableHead className="text-center">Absent</TableHead>
                      <TableHead className="text-center">Late</TableHead>
                      <TableHead className="text-center">Excused</TableHead>
                      <TableHead className="text-center">Sick</TableHead>
                      <TableHead className="text-right">Rate</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {weeklyData.map((day) => (
                      <TableRow
                        key={day.date}
                        className={day.date === selectedDate ? "bg-muted/50" : ""}
                      >
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{day.dayName}</span>
                            <span className="text-muted-foreground text-sm">
                              {format(new Date(day.date), "d/M")}
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
                              <span className="text-green-600 font-medium">{day.data.present}</span>
                            </TableCell>
                            <TableCell className="text-center">
                              <span className="text-red-600 font-medium">{day.data.absent}</span>
                            </TableCell>
                            <TableCell className="text-center">
                              <span className="text-yellow-600 font-medium">{day.data.late}</span>
                            </TableCell>
                            <TableCell className="text-center">
                              <span className="text-blue-600 font-medium">{day.data.excused}</span>
                            </TableCell>
                            <TableCell className="text-center">
                              <span className="text-purple-600 font-medium">{day.data.sick}</span>
                            </TableCell>
                            <TableCell className="text-right">
                              <Badge
                                variant="secondary"
                                className={
                                  day.data.attendance_rate >= 90
                                    ? "bg-green-100 text-green-700"
                                    : day.data.attendance_rate >= 75
                                    ? "bg-yellow-100 text-yellow-700"
                                    : "bg-red-100 text-red-700"
                                }
                              >
                                {day.data.attendance_rate}%
                              </Badge>
                            </TableCell>
                          </>
                        ) : (
                          <TableCell colSpan={6} className="text-center text-muted-foreground">
                            No data
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      ) : viewMode === "class" && sectionSummary ? (
        <>
          {/* Section Stats */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
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
                <div className="text-2xl font-bold text-green-600">{sectionSummary.present}</div>
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

          {/* Class Info */}
          <Card>
            <CardHeader>
              <CardTitle>Class Information</CardTitle>
              <CardDescription>
                {selectedClass?.name} - {sections.find((s) => s.id === selectedSectionId)?.name}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Marking Progress</Label>
                  <div className="flex items-center gap-2">
                    <Progress value={(sectionSummary.marked / sectionSummary.total_students) * 100} />
                    <span className="text-sm text-muted-foreground">
                      {Math.round((sectionSummary.marked / sectionSummary.total_students) * 100)}%
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {sectionSummary.unmarked} students still need attendance marked
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>Attendance Rate</Label>
                  <div className="flex items-center gap-2">
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
                    <span className="text-sm text-muted-foreground">
                      {sectionSummary.attendance_rate}%
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      ) : viewMode === "class" && !selectedSectionId ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Users className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">Select a Class and Section</h3>
            <p className="text-sm text-muted-foreground text-center max-w-md mt-2">
              Choose a class and section above to view detailed attendance reports.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Calendar className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">No Data Available</h3>
            <p className="text-sm text-muted-foreground text-center max-w-md mt-2">
              No attendance data found for the selected date. Try selecting a different date.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
