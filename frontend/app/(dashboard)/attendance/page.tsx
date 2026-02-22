import Link from "next/link";
import { format } from "date-fns";
import {
  Users,
  CheckCircle2,
  XCircle,
  Clock,
  BarChart3,
  ClipboardCheck,
  ArrowRight,
  Calendar,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

import { getDailyAttendanceReport } from "@/actions/attendance.action";

export const metadata = {
  title: "Attendance",
};

export default async function AttendancePage() {
  const today = format(new Date(), "yyyy-MM-dd");
  const reportResult = await getDailyAttendanceReport(today);
  const report = reportResult.success && reportResult.data ? reportResult.data : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Attendance</h1>
          <p className="text-muted-foreground">
            Manage and track student attendance records
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild>
            <Link href="/attendance/mark">
              <ClipboardCheck className="mr-2 h-4 w-4" />
              Mark Attendance
            </Link>
          </Button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="hover:border-primary/50 transition-colors">
          <Link href="/attendance/mark">
            <CardHeader>
              <div className="flex items-center justify-between">
                <ClipboardCheck className="h-8 w-8 text-primary" />
                <ArrowRight className="h-5 w-5 text-muted-foreground" />
              </div>
              <CardTitle className="mt-4">Mark Attendance</CardTitle>
              <CardDescription>
                Record daily student attendance for each class section
              </CardDescription>
            </CardHeader>
          </Link>
        </Card>

        <Card className="hover:border-primary/50 transition-colors">
          <Link href="/attendance/reports">
            <CardHeader>
              <div className="flex items-center justify-between">
                <BarChart3 className="h-8 w-8 text-primary" />
                <ArrowRight className="h-5 w-5 text-muted-foreground" />
              </div>
              <CardTitle className="mt-4">View Reports</CardTitle>
              <CardDescription>
                Analyze attendance statistics, trends, and generate reports
              </CardDescription>
            </CardHeader>
          </Link>
        </Card>
      </div>

      {/* Today's Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Today&apos;s Overview</CardTitle>
              <CardDescription>
                {format(new Date(), "EEEE, MMMM d, yyyy")}
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-sm">
              <Calendar className="mr-1 h-3 w-3" />
              Live
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {report ? (
            <div className="space-y-6">
              {/* Stats Grid */}
              <div className="grid gap-4 md:grid-cols-4">
                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-muted p-2">
                    <Users className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{report.total_students}</p>
                    <p className="text-sm text-muted-foreground">Total Students</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-green-100 p-2 dark:bg-green-900">
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-green-600">{report.present}</p>
                    <p className="text-sm text-muted-foreground">Present</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-red-100 p-2 dark:bg-red-900">
                    <XCircle className="h-5 w-5 text-red-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-red-600">{report.absent}</p>
                    <p className="text-sm text-muted-foreground">Absent</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-yellow-100 p-2 dark:bg-yellow-900">
                    <Clock className="h-5 w-5 text-yellow-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-yellow-600">{report.late}</p>
                    <p className="text-sm text-muted-foreground">Late</p>
                  </div>
                </div>
              </div>

              {/* Progress Indicators */}
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Marking Progress</span>
                    <span className="text-sm text-muted-foreground">
                      {report.marked} of {report.total_students}
                    </span>
                  </div>
                  <Progress value={report.marking_rate} />
                  <p className="text-xs text-muted-foreground">
                    {report.marking_rate}% of students have attendance marked
                  </p>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Attendance Rate</span>
                    <span className="text-sm text-muted-foreground">{report.attendance_rate}%</span>
                  </div>
                  <Progress
                    value={report.attendance_rate}
                    className={
                      report.attendance_rate >= 90
                        ? "[&>div]:bg-green-500"
                        : report.attendance_rate >= 75
                        ? "[&>div]:bg-yellow-500"
                        : "[&>div]:bg-red-500"
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    {report.present + report.late} present or late out of {report.marked} marked
                  </p>
                </div>
              </div>

              {/* Action Prompt */}
              {report.unmarked > 0 && (
                <div className="flex items-center justify-between rounded-lg border border-yellow-200 bg-yellow-50 p-4 dark:border-yellow-900 dark:bg-yellow-950">
                  <div className="flex items-center gap-3">
                    <ClipboardCheck className="h-5 w-5 text-yellow-600" />
                    <div>
                      <p className="font-medium text-yellow-800 dark:text-yellow-200">
                        {report.unmarked} students need attendance marked
                      </p>
                      <p className="text-sm text-yellow-600">
                        Complete attendance marking to get accurate reports
                      </p>
                    </div>
                  </div>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/attendance/mark">Mark Now</Link>
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Calendar className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">No Attendance Data Yet</h3>
              <p className="text-sm text-muted-foreground max-w-md mt-2">
                Start marking attendance for today to see the overview here.
              </p>
              <Button asChild className="mt-4">
                <Link href="/attendance/mark">
                  <ClipboardCheck className="mr-2 h-4 w-4" />
                  Start Marking
                </Link>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
