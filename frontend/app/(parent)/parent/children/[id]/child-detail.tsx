"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CalendarCheck,
  GraduationCap,
  CreditCard,
  TrendingUp,
  MessageSquare,
  User,
  Home,
  Bus,
  Loader2,
  Download,
  ChevronLeft,
  ChevronRight,
  Check,
  AlertCircle,
  FileText,
  Receipt,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { cn } from "@/lib/utils";
import {
  formatGHS,
  formatGhanaDate,
  formatRelativeTime,
  getInitials,
} from "@/lib/format";
import {
  getChildGrades,
  getChildGradeTrend,
  downloadReportCard,
  getChildAttendance,
  getChildAttendanceTrend,
  getChildInvoices,
  getChildPaymentHistory,
  getChildTeacherNotes,
  acknowledgeTeacherNote,
  getChildBoardingInfo,
  getChildTransportInfo,
} from "@/actions/parent.action";
import type {
  ChildOverview,
  ActivityItem,
  TermGrades,
  GradeTrend,
  AttendanceSummary,
  AttendanceTrend,
  ParentInvoiceSummary,
  ParentPaymentRecord,
  TeacherNote,
  NoteType,
  ChildBoardingInfo,
  ChildTransportInfo,
} from "@/types/parent.type";

// =========================
// Main Component
// =========================

interface ChildDetailViewProps {
  studentId: string;
  overview: ChildOverview | null;
  initialTab: string;
}

export function ChildDetailView({
  studentId,
  overview,
  initialTab,
}: ChildDetailViewProps) {
  const [activeTab, setActiveTab] = useState(initialTab);

  if (!overview) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <User className="h-10 w-10 text-muted-foreground" />
        <h2 className="text-lg font-semibold">Child not found</h2>
        <p className="text-sm text-muted-foreground">
          We could not find this child in your account.
        </p>
        <Button variant="outline" asChild>
          <Link href="/parent/children">Back to My Children</Link>
        </Button>
      </div>
    );
  }

  const { child, stats, recent_activity } = overview;

  // Determine which optional tabs to show
  // We always show Overview, Grades, Attendance, Finance, Notes
  // Boarding and Transport are conditional
  const tabItems: { value: string; label: string; icon: React.ReactNode }[] = [
    { value: "overview", label: "Overview", icon: <User className="h-4 w-4" /> },
    { value: "grades", label: "Grades", icon: <GraduationCap className="h-4 w-4" /> },
    { value: "attendance", label: "Attendance", icon: <CalendarCheck className="h-4 w-4" /> },
    { value: "finance", label: "Finance", icon: <CreditCard className="h-4 w-4" /> },
    { value: "notes", label: "Notes", icon: <MessageSquare className="h-4 w-4" /> },
    { value: "boarding", label: "Boarding", icon: <Home className="h-4 w-4" /> },
    { value: "transport", label: "Transport", icon: <Bus className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/parent/children"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        My Children
      </Link>

      {/* Child header */}
      <div className="flex items-center gap-4">
        <Avatar className="h-16 w-16">
          <AvatarFallback className="bg-primary/10 text-primary text-xl">
            {getInitials(`${child.first_name} ${child.last_name}`)}
          </AvatarFallback>
        </Avatar>
        <div>
          <h1 className="text-xl md:text-2xl font-bold tracking-tight">
            {child.first_name} {child.last_name}
          </h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground mt-0.5">
            <span>
              {child.class_name}
              {child.section_name ? ` ${child.section_name}` : ""}
            </span>
            <span className="text-muted-foreground/50">|</span>
            <span>ID: {child.admission_number}</span>
            {child.current_term && (
              <>
                <span className="text-muted-foreground/50 hidden sm:inline">|</span>
                <span className="hidden sm:inline">{child.current_term}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <QuickStatCard
          title="Attendance"
          value={`${stats.attendance_rate}%`}
          icon={CalendarCheck}
          color="text-green-600"
        />
        <QuickStatCard
          title="Average Score"
          value={
            stats.average_score !== null
              ? `${stats.average_score.toFixed(1)}%`
              : "--"
          }
          icon={GraduationCap}
          color="text-blue-600"
        />
        <QuickStatCard
          title="Position"
          value={
            stats.class_position !== null
              ? `${stats.class_position}/${stats.class_size || "--"}`
              : "--"
          }
          icon={TrendingUp}
          color="text-purple-600"
        />
        <QuickStatCard
          title="Balance"
          value={formatGHS(stats.outstanding_balance)}
          icon={CreditCard}
          color={
            stats.outstanding_balance > 0 ? "text-amber-600" : "text-green-600"
          }
        />
      </div>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-4"
      >
        <TabsList className="w-full overflow-x-auto flex h-auto p-1 gap-1">
          {tabItems.map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              className="flex items-center gap-1.5 text-xs sm:text-sm px-2 sm:px-3 py-1.5 shrink-0"
            >
              <span className="hidden sm:inline">{tab.icon}</span>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab
            child={child}
            recentActivity={recent_activity}
          />
        </TabsContent>

        <TabsContent value="grades">
          <GradesTab studentId={studentId} />
        </TabsContent>

        <TabsContent value="attendance">
          <AttendanceTab studentId={studentId} />
        </TabsContent>

        <TabsContent value="finance">
          <FinanceTab studentId={studentId} />
        </TabsContent>

        <TabsContent value="notes">
          <NotesTab studentId={studentId} />
        </TabsContent>

        <TabsContent value="boarding">
          <BoardingTab studentId={studentId} />
        </TabsContent>

        <TabsContent value="transport">
          <TransportTab studentId={studentId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// =========================
// Quick Stat Card
// =========================

function QuickStatCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  color?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
        <CardTitle className="text-xs font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className={cn("h-4 w-4", color || "text-muted-foreground")} />
      </CardHeader>
      <CardContent>
        <div className={cn("text-lg md:text-xl font-bold", color)}>{value}</div>
      </CardContent>
    </Card>
  );
}

// =========================
// Overview Tab
// =========================

function OverviewTab({
  child,
  recentActivity,
}: {
  child: ChildOverview["child"];
  recentActivity: ActivityItem[];
}) {
  const activityTypeIcons: Record<
    string,
    React.ComponentType<{ className?: string }>
  > = {
    grade: GraduationCap,
    attendance: CalendarCheck,
    finance: CreditCard,
    announcement: MessageSquare,
    note: AlertCircle,
    report: FileText,
  };

  const activityTypeColors: Record<string, string> = {
    grade: "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300",
    attendance:
      "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300",
    finance:
      "bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-300",
    announcement:
      "bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300",
    note: "bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-300",
    report: "bg-cyan-100 text-cyan-600 dark:bg-cyan-900 dark:text-cyan-300",
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Student Details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Student Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-3 text-sm">
            <DetailRow label="Full Name" value={`${child.first_name} ${child.last_name}`} />
            <DetailRow label="Admission Number" value={child.admission_number} />
            <DetailRow
              label="Class"
              value={`${child.class_name}${child.section_name ? ` ${child.section_name}` : ""}`}
            />
            <DetailRow label="Gender" value={child.gender === "male" ? "Male" : "Female"} />
            <DetailRow label="Date of Birth" value={formatGhanaDate(child.date_of_birth)} />
            <DetailRow label="Academic Year" value={child.academic_year || "--"} />
            <DetailRow label="Current Term" value={child.current_term || "--"} />
            {child.class_teacher_name && (
              <DetailRow label="Class Teacher" value={child.class_teacher_name} />
            )}
            <DetailRow
              label="Status"
              value={
                <Badge
                  variant="secondary"
                  className={cn(
                    "text-[10px] capitalize",
                    child.enrollment_status === "active"
                      ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {child.enrollment_status}
                </Badge>
              }
            />
          </dl>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {recentActivity.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No recent activity to display.
            </p>
          ) : (
            <div className="space-y-4">
              {recentActivity.slice(0, 8).map((activity) => {
                const Icon =
                  activityTypeIcons[activity.type] || AlertCircle;
                const colorClass =
                  activityTypeColors[activity.type] ||
                  "bg-muted text-muted-foreground";
                return (
                  <div key={activity.id} className="flex items-start gap-3">
                    <div
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                        colorClass
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {activity.title}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {activity.description}
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatRelativeTime(activity.date)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex justify-between">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-right">{value}</dd>
    </div>
  );
}

// =========================
// Grades Tab
// =========================

function GradesTab({ studentId }: { studentId: string }) {
  const [termId, setTermId] = useState<string>("current");
  const [grades, setGrades] = useState<TermGrades | null>(null);
  const [trend, setTrend] = useState<GradeTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  const loadGrades = useCallback(
    async (tid: string) => {
      setLoading(true);
      const result = await getChildGrades(studentId, tid);
      if (result.success) {
        setGrades(result.data);
      }
      setLoading(false);
    },
    [studentId]
  );

  const loadTrend = useCallback(async () => {
    const result = await getChildGradeTrend(studentId);
    if (result.success) {
      setTrend(result.data);
    }
  }, [studentId]);

  useEffect(() => {
    loadGrades(termId);
    loadTrend();
  }, [termId, loadGrades, loadTrend]);

  const handleDownload = async () => {
    if (!grades) return;
    setDownloading(true);
    const result = await downloadReportCard(studentId, grades.term.id);
    if (result.success) {
      window.open(result.data.url, "_blank");
    }
    setDownloading(false);
  };

  if (loading) {
    return <GradesTabSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Term selector + download button */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        {grades?.term && (
          <div className="text-sm text-muted-foreground">
            {grades.term.name} - {grades.term.academic_year}
          </div>
        )}
        <div className="flex items-center gap-2">
          <Select value={termId} onValueChange={setTermId}>
            <SelectTrigger className="w-full sm:w-[180px]">
              <SelectValue placeholder="Select term" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="current">Current Term</SelectItem>
              {trend.map((t) => (
                <SelectItem key={t.term_id} value={t.term_id}>
                  {t.term_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownload}
            disabled={downloading || !grades}
          >
            {downloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            <span className="hidden sm:inline ml-1.5">Report Card</span>
          </Button>
        </div>
      </div>

      {/* Overall summary */}
      {grades?.overall && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MiniStat
            label="Total Marks"
            value={grades.overall.total_marks.toString()}
          />
          <MiniStat
            label="Average"
            value={`${grades.overall.average.toFixed(1)}%`}
          />
          <MiniStat
            label="Position"
            value={`${grades.overall.class_position}/${grades.overall.class_size}`}
          />
          <MiniStat
            label="Subjects"
            value={grades.subjects.length.toString()}
          />
        </div>
      )}

      {/* Subject grades table */}
      {grades && grades.subjects.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Subject</TableHead>
                    <TableHead className="text-center hidden sm:table-cell">
                      CA
                    </TableHead>
                    <TableHead className="text-center hidden sm:table-cell">
                      Exam
                    </TableHead>
                    <TableHead className="text-center">Total</TableHead>
                    <TableHead className="text-center">Grade</TableHead>
                    <TableHead className="text-center hidden md:table-cell">
                      Position
                    </TableHead>
                    <TableHead className="text-center hidden md:table-cell">
                      Class Avg
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {grades.subjects.map((subject) => (
                    <TableRow key={subject.subject_id}>
                      <TableCell className="font-medium">
                        {subject.subject_name}
                      </TableCell>
                      <TableCell className="text-center hidden sm:table-cell">
                        {subject.ca_score !== null
                          ? `${subject.ca_score}/${subject.ca_max}`
                          : "--"}
                      </TableCell>
                      <TableCell className="text-center hidden sm:table-cell">
                        {subject.exam_score !== null
                          ? `${subject.exam_score}/${subject.exam_max}`
                          : "--"}
                      </TableCell>
                      <TableCell className="text-center font-semibold">
                        {subject.total !== null ? subject.total : "--"}
                      </TableCell>
                      <TableCell className="text-center">
                        {subject.grade ? (
                          <Badge variant="outline" className="font-mono">
                            {subject.grade}
                          </Badge>
                        ) : (
                          "--"
                        )}
                      </TableCell>
                      <TableCell className="text-center hidden md:table-cell">
                        {subject.position ?? "--"}
                      </TableCell>
                      <TableCell className="text-center hidden md:table-cell">
                        {subject.class_average !== null
                          ? subject.class_average.toFixed(1)
                          : "--"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <GraduationCap className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No grades available</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Grades for this term have not been published yet.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Grade trend chart */}
      {trend.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Grade Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="term_name"
                    className="text-xs"
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis
                    domain={[0, 100]}
                    className="text-xs"
                    tick={{ fontSize: 12 }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload as GradeTrend;
                      return (
                        <div className="rounded-lg border bg-background p-3 shadow-md">
                          <p className="text-sm font-medium">{d.term_name}</p>
                          <p className="text-sm text-muted-foreground">
                            Average: {d.average.toFixed(1)}%
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Position: {d.position}/{d.class_size}
                          </p>
                        </div>
                      );
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="average"
                    stroke="var(--primary)"
                    strokeWidth={2}
                    dot={{ fill: "var(--primary)", r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="bg-muted/30">
      <CardContent className="p-3">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-lg font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

function GradesTabSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-9 w-44" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="bg-muted/30">
            <CardContent className="p-3 space-y-1">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-6 w-12" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="p-4 space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

// =========================
// Attendance Tab
// =========================

function AttendanceTab({ studentId }: { studentId: string }) {
  const now = new Date();
  const [currentMonth, setCurrentMonth] = useState(
    `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`
  );
  const [attendance, setAttendance] = useState<AttendanceSummary | null>(null);
  const [trend, setTrend] = useState<AttendanceTrend[]>([]);
  const [loading, setLoading] = useState(true);

  const loadAttendance = useCallback(
    async (month: string) => {
      setLoading(true);
      const result = await getChildAttendance(studentId, month);
      if (result.success) {
        setAttendance(result.data);
      }
      setLoading(false);
    },
    [studentId]
  );

  const loadTrend = useCallback(async () => {
    const result = await getChildAttendanceTrend(studentId);
    if (result.success) {
      setTrend(result.data);
    }
  }, [studentId]);

  useEffect(() => {
    loadAttendance(currentMonth);
    loadTrend();
  }, [currentMonth, loadAttendance, loadTrend]);

  const navigateMonth = (direction: -1 | 1) => {
    const [year, month] = currentMonth.split("-").map(Number);
    const d = new Date(year, month - 1 + direction, 1);
    setCurrentMonth(
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
    );
  };

  const monthLabel = (() => {
    const [year, month] = currentMonth.split("-").map(Number);
    return new Date(year, month - 1).toLocaleDateString("en-GB", {
      month: "long",
      year: "numeric",
    });
  })();

  if (loading) {
    return <AttendanceTabSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Month navigator */}
      <div className="flex items-center justify-between">
        <Button variant="outline" size="icon" onClick={() => navigateMonth(-1)}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <h3 className="text-sm font-semibold">{monthLabel}</h3>
        <Button variant="outline" size="icon" onClick={() => navigateMonth(1)}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Summary stats */}
      {attendance && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <MiniStat
            label="Attendance Rate"
            value={`${attendance.rate.toFixed(1)}%`}
          />
          <MiniStat
            label="Present"
            value={attendance.present.toString()}
          />
          <MiniStat label="Absent" value={attendance.absent.toString()} />
          <MiniStat label="Late" value={attendance.late.toString()} />
          <MiniStat label="Excused" value={attendance.excused.toString()} />
        </div>
      )}

      {/* Attendance calendar */}
      {attendance && attendance.daily.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Daily Attendance</CardTitle>
          </CardHeader>
          <CardContent>
            <AttendanceCalendar
              month={currentMonth}
              days={attendance.daily}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <CalendarCheck className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No attendance data</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Attendance records for this month are not available.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Attendance trend chart */}
      {trend.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Attendance Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="month"
                    className="text-xs"
                    tick={{ fontSize: 12 }}
                    tickFormatter={(val: string) => {
                      const [y, m] = val.split("-");
                      return new Date(Number(y), Number(m) - 1).toLocaleDateString(
                        "en-GB",
                        { month: "short" }
                      );
                    }}
                  />
                  <YAxis
                    domain={[0, 100]}
                    className="text-xs"
                    tick={{ fontSize: 12 }}
                    tickFormatter={(val: number) => `${val}%`}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload as AttendanceTrend;
                      return (
                        <div className="rounded-lg border bg-background p-3 shadow-md">
                          <p className="text-sm font-medium">{d.month}</p>
                          <p className="text-sm text-muted-foreground">
                            Rate: {d.rate.toFixed(1)}%
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Present: {d.present}/{d.total_days} days
                          </p>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
                    {trend.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={entry.rate >= 80 ? "#22c55e" : entry.rate >= 60 ? "#eab308" : "#ef4444"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

const attendanceStatusColors: Record<string, string> = {
  present: "bg-green-500",
  absent: "bg-red-500",
  late: "bg-amber-500",
  excused: "bg-blue-500",
  sick: "bg-purple-500",
};

const attendanceStatusLabels: Record<string, string> = {
  present: "Present",
  absent: "Absent",
  late: "Late",
  excused: "Excused",
  sick: "Sick",
};

function AttendanceCalendar({
  month,
  days,
}: {
  month: string;
  days: AttendanceSummary["daily"];
}) {
  const [year, mon] = month.split("-").map(Number);
  const firstDay = new Date(year, mon - 1, 1);
  const daysInMonth = new Date(year, mon, 0).getDate();
  // Monday = 0, Sunday = 6 (shift for week starting Monday)
  const startOffset = (firstDay.getDay() + 6) % 7;

  const dayMap = new Map(days.map((d) => [d.date, d]));

  const weekDays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div>
      {/* Legend */}
      <div className="flex flex-wrap gap-3 mb-4">
        {Object.entries(attendanceStatusLabels).map(([key, label]) => (
          <div key={key} className="flex items-center gap-1.5">
            <div
              className={cn("h-3 w-3 rounded-full", attendanceStatusColors[key])}
            />
            <span className="text-xs text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {weekDays.map((d) => (
          <div
            key={d}
            className="text-center text-xs font-medium text-muted-foreground py-1"
          >
            {d}
          </div>
        ))}
        {/* Empty cells for offset */}
        {Array.from({ length: startOffset }).map((_, i) => (
          <div key={`empty-${i}`} />
        ))}
        {/* Day cells */}
        {Array.from({ length: daysInMonth }).map((_, i) => {
          const dayNum = i + 1;
          const dateStr = `${year}-${String(mon).padStart(2, "0")}-${String(dayNum).padStart(2, "0")}`;
          const dayData = dayMap.get(dateStr);
          const isWeekend =
            new Date(year, mon - 1, dayNum).getDay() === 0 ||
            new Date(year, mon - 1, dayNum).getDay() === 6;

          return (
            <div
              key={dayNum}
              className={cn(
                "relative flex flex-col items-center justify-center rounded-md p-1 text-xs h-9",
                isWeekend && !dayData
                  ? "bg-muted/30 text-muted-foreground"
                  : ""
              )}
              title={
                dayData
                  ? `${formatGhanaDate(dateStr)} - ${attendanceStatusLabels[dayData.status] || dayData.status}${dayData.note ? `: ${dayData.note}` : ""}`
                  : undefined
              }
            >
              <span className="leading-none">{dayNum}</span>
              {dayData && (
                <div
                  className={cn(
                    "h-1.5 w-1.5 rounded-full mt-0.5",
                    attendanceStatusColors[dayData.status] || "bg-muted"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AttendanceTabSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-9 w-9" />
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-9 w-9" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Card key={i} className="bg-muted/30">
            <CardContent className="p-3 space-y-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-6 w-10" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: 35 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-full rounded-md" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// =========================
// Finance Tab
// =========================

const invoiceStatusStyles: Record<string, string> = {
  paid: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  partial:
    "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  issued: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  overdue: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  cancelled: "bg-muted text-muted-foreground",
  draft: "bg-muted text-muted-foreground",
  write_off: "bg-muted text-muted-foreground",
};

function FinanceTab({ studentId }: { studentId: string }) {
  const [invoices, setInvoices] = useState<ParentInvoiceSummary[]>([]);
  const [payments, setPayments] = useState<ParentPaymentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<"invoices" | "payments">(
    "invoices"
  );

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [invResult, payResult] = await Promise.all([
        getChildInvoices(studentId),
        getChildPaymentHistory(studentId),
      ]);
      if (invResult.success) setInvoices(invResult.data);
      if (payResult.success) setPayments(payResult.data);
      setLoading(false);
    }
    load();
  }, [studentId]);

  const totalOutstanding = invoices
    .filter((inv) => inv.status !== "paid" && inv.status !== "cancelled")
    .reduce((sum, inv) => sum + inv.balance, 0);

  if (loading) {
    return <FinanceTabSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Outstanding balance card */}
      <Card
        className={cn(
          totalOutstanding > 0
            ? "border-amber-500/30 bg-amber-50/50 dark:bg-amber-950/20"
            : "border-green-500/30 bg-green-50/50 dark:bg-green-950/20"
        )}
      >
        <CardContent className="flex items-center gap-4 py-4">
          <div
            className={cn(
              "flex h-12 w-12 items-center justify-center rounded-full",
              totalOutstanding > 0
                ? "bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-300"
                : "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300"
            )}
          >
            <CreditCard className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">
              Outstanding Balance
            </p>
            <p className="text-2xl font-bold">
              {formatGHS(totalOutstanding)}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Toggle: Invoices / Payments */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => setActiveSection("invoices")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
            activeSection === "invoices"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          Invoices ({invoices.length})
        </button>
        <button
          onClick={() => setActiveSection("payments")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
            activeSection === "payments"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          Payments ({payments.length})
        </button>
      </div>

      {/* Invoices list */}
      {activeSection === "invoices" && (
        <>
          {invoices.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <Receipt className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold">No invoices yet</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Invoices for the current term will appear here.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {invoices.map((invoice) => (
                <Link
                  key={invoice.id}
                  href={`/parent/children/${studentId}/invoices/${invoice.id}`}
                >
                  <Card className="hover:shadow-md transition-shadow cursor-pointer">
                    <CardContent className="flex items-center gap-4 p-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold">
                            {invoice.invoice_number}
                          </p>
                          <Badge
                            variant="secondary"
                            className={cn(
                              "text-[10px] h-5 capitalize",
                              invoiceStatusStyles[invoice.status] || ""
                            )}
                          >
                            {invoice.status.replace("_", " ")}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {invoice.term_name}
                          {invoice.due_date
                            ? ` | Due: ${formatGhanaDate(invoice.due_date)}`
                            : ""}
                        </p>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm">
                          <span className="text-muted-foreground">
                            Total: {formatGHS(invoice.total_amount)}
                          </span>
                          <span className="text-muted-foreground">
                            Paid: {formatGHS(invoice.amount_paid)}
                          </span>
                          {invoice.balance > 0 && (
                            <span className="font-medium text-amber-600 dark:text-amber-400">
                              Balance: {formatGHS(invoice.balance)}
                            </span>
                          )}
                        </div>
                      </div>
                      {invoice.balance > 0 && (
                        <Button size="sm" className="shrink-0">
                          Pay
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </>
      )}

      {/* Payments list */}
      {activeSection === "payments" && (
        <>
          {payments.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <CreditCard className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold">No payments yet</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Payment records will appear here after your first payment.
                </p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Receipt</TableHead>
                        <TableHead className="hidden sm:table-cell">
                          Invoice
                        </TableHead>
                        <TableHead className="hidden sm:table-cell">
                          Method
                        </TableHead>
                        <TableHead className="text-right">Amount</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {payments.map((payment) => (
                        <TableRow key={payment.id}>
                          <TableCell className="text-sm">
                            {formatGhanaDate(payment.date)}
                          </TableCell>
                          <TableCell className="text-sm font-medium">
                            {payment.receipt_number}
                          </TableCell>
                          <TableCell className="text-sm hidden sm:table-cell">
                            {payment.invoice_number}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            <Badge variant="outline" className="text-xs capitalize">
                              {payment.method.replace("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-semibold text-sm">
                            {formatGHS(payment.amount)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function FinanceTabSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-20 w-full rounded-lg" />
      <Skeleton className="h-10 w-64" />
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4 space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
              <Skeleton className="h-3 w-40" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// =========================
// Notes Tab
// =========================

const noteTypeColors: Record<NoteType, string> = {
  positive:
    "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  concern:
    "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  action_required:
    "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  information:
    "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
};

const noteTypeLabels: Record<NoteType, string> = {
  positive: "Positive",
  concern: "Concern",
  action_required: "Action Required",
  information: "Information",
};

function NotesTab({ studentId }: { studentId: string }) {
  const [notes, setNotes] = useState<TeacherNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [acknowledging, setAcknowledging] = useState<string | null>(null);

  const loadNotes = useCallback(async () => {
    setLoading(true);
    const result = await getChildTeacherNotes(studentId);
    if (result.success) {
      setNotes(result.data);
    }
    setLoading(false);
  }, [studentId]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  const handleAcknowledge = async (noteId: string) => {
    setAcknowledging(noteId);
    const result = await acknowledgeTeacherNote(studentId, noteId);
    if (result.success) {
      setNotes((prev) =>
        prev.map((n) =>
          n.id === noteId
            ? {
                ...n,
                parent_acknowledged: true,
                parent_acknowledged_at: new Date().toISOString(),
              }
            : n
        )
      );
    }
    setAcknowledging(null);
  };

  if (loading) {
    return <NotesTabSkeleton />;
  }

  if (notes.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <MessageSquare className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">No notes from teachers</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Teacher notes and observations will appear here.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {notes.map((note) => (
        <Card key={note.id}>
          <CardContent className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <Badge
                    variant="secondary"
                    className={cn(
                      "text-[10px] h-5",
                      noteTypeColors[note.note_type]
                    )}
                  >
                    {noteTypeLabels[note.note_type]}
                  </Badge>
                  {note.subject_name && (
                    <Badge variant="outline" className="text-[10px] h-5">
                      {note.subject_name}
                    </Badge>
                  )}
                  {note.parent_acknowledged && (
                    <Badge
                      variant="secondary"
                      className="text-[10px] h-5 bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                    >
                      <Check className="h-3 w-3 mr-0.5" />
                      Acknowledged
                    </Badge>
                  )}
                </div>
                <p className="text-sm mt-2">{note.content}</p>
                <p className="text-xs text-muted-foreground mt-2">
                  {note.teacher_name} &middot;{" "}
                  {formatRelativeTime(note.created_at)}
                </p>
              </div>
              {!note.parent_acknowledged && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleAcknowledge(note.id)}
                  disabled={acknowledging === note.id}
                  className="shrink-0"
                >
                  {acknowledging === note.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4" />
                  )}
                  <span className="ml-1.5 hidden sm:inline">Acknowledge</span>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function NotesTabSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-20" />
              <Skeleton className="h-5 w-16" />
            </div>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-40" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// =========================
// Boarding Tab
// =========================

function BoardingTab({ studentId }: { studentId: string }) {
  const [info, setInfo] = useState<ChildBoardingInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [notBoarder, setNotBoarder] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const result = await getChildBoardingInfo(studentId);
      if (result.success) {
        setInfo(result.data);
      } else {
        // If error, child is likely not a boarder
        setNotBoarder(true);
      }
      setLoading(false);
    }
    load();
  }, [studentId]);

  if (loading) {
    return <BoardingTabSkeleton />;
  }

  if (notBoarder || !info) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <Home className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">Not a boarding student</h3>
          <p className="text-sm text-muted-foreground mt-1">
            This child is not registered as a boarding student.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Boarding details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Boarding Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-3 text-sm">
            <DetailRow label="House" value={info.house_name} />
            <DetailRow label="Dormitory" value={info.dormitory_name} />
            {info.bed_number && (
              <DetailRow label="Bed Number" value={info.bed_number} />
            )}
            <DetailRow label="House Parent" value={info.house_parent_name} />
            {info.house_parent_phone && (
              <DetailRow label="House Parent Phone" value={info.house_parent_phone} />
            )}
          </dl>
        </CardContent>
      </Card>

      {/* Recent Roll Calls */}
      {info.recent_roll_calls.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Roll Calls</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {info.recent_roll_calls.map((rc, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <span className="text-sm">
                    {formatGhanaDate(rc.date)}
                  </span>
                  <Badge
                    variant="secondary"
                    className={cn(
                      "text-[10px] capitalize",
                      rc.status === "present"
                        ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                        : rc.status === "absent"
                          ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                          : "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
                    )}
                  >
                    {rc.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Active Exeats */}
      {info.active_exeats.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Active Exeats</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {info.active_exeats.map((exeat) => (
                <div
                  key={exeat.id}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium capitalize">
                      {exeat.type} Exeat
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatGhanaDate(exeat.start_date)} -{" "}
                      {formatGhanaDate(exeat.end_date)}
                    </p>
                  </div>
                  <Badge
                    variant="secondary"
                    className={cn(
                      "text-[10px] capitalize",
                      exeat.status === "approved"
                        ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                        : exeat.status === "active"
                          ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                          : "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
                    )}
                  >
                    {exeat.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function BoardingTabSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-32" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex justify-between">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-32" />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

// =========================
// Transport Tab
// =========================

function TransportTab({ studentId }: { studentId: string }) {
  const [info, setInfo] = useState<ChildTransportInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [notRegistered, setNotRegistered] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const result = await getChildTransportInfo(studentId);
      if (result.success) {
        setInfo(result.data);
      } else {
        setNotRegistered(true);
      }
      setLoading(false);
    }
    load();
  }, [studentId]);

  if (loading) {
    return <TransportTabSkeleton />;
  }

  if (notRegistered || !info) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <Bus className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">Not using school transport</h3>
          <p className="text-sm text-muted-foreground mt-1">
            This child is not registered for school transport.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Route details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Route Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-3 text-sm">
            <DetailRow label="Route" value={info.route_name} />
            {info.route_number && (
              <DetailRow label="Route Number" value={info.route_number} />
            )}
            <DetailRow label="Vehicle" value={info.vehicle_registration} />
          </dl>
        </CardContent>
      </Card>

      {/* Pickup / Dropoff */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Morning Pickup</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3 text-sm">
              <DetailRow label="Stop" value={info.pickup_stop} />
              <DetailRow label="Time" value={info.pickup_time} />
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Afternoon Dropoff</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3 text-sm">
              <DetailRow label="Stop" value={info.dropoff_stop} />
              <DetailRow label="Time" value={info.dropoff_time} />
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Driver contact */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Driver Contact</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-3 text-sm">
            <DetailRow label="Driver" value={info.driver_name} />
            <DetailRow label="Phone" value={info.driver_phone} />
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}

function TransportTabSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-28" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex justify-between">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-32" />
            </div>
          ))}
        </CardContent>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-32" />
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-24" />
              </div>
              <div className="flex justify-between">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-16" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
