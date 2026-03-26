import Link from "next/link";
import { format } from "date-fns";
import {
  Users,
  CheckCircle2,
  XCircle,
  Clock,
  ClipboardCheck,
  BarChart3,
  ArrowRight,
  Calendar,
  UserCog,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { listStaffAttendance } from "@/actions/attendance.action";

export const metadata = {
  title: "Staff Attendance",
};

export default async function StaffAttendancePage() {
  const today = format(new Date(), "yyyy-MM-dd");

  // Fetch today's staff attendance records
  const result = await listStaffAttendance({
    start_date: today,
    end_date: today,
    page_size: 200,
  });

  const records = result.success && result.data ? result.data.items : [];

  // Calculate summary stats
  const totalMarked = records.length;
  const present = records.filter((r) => r.status === "present").length;
  const absent = records.filter((r) => r.status === "absent").length;
  const late = records.filter((r) => r.status === "late").length;
  const excused = records.filter((r) => r.status === "excused").length;
  const sick = records.filter((r) => r.status === "sick").length;

  // Staff that are absent or late
  const absentLateStaff = records.filter(
    (r) => r.status === "absent" || r.status === "late" || r.status === "sick"
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Staff Attendance</h1>
          <p className="text-muted-foreground">
            Track and manage staff attendance records
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href="/attendance/staff/reports">
              <BarChart3 className="mr-2 h-4 w-4" />
              Reports
            </Link>
          </Button>
          <Button asChild>
            <Link href="/attendance/staff/mark">
              <ClipboardCheck className="mr-2 h-4 w-4" />
              Mark Attendance
            </Link>
          </Button>
        </div>
      </div>

      {/* Quick Action Cards */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="hover:border-primary/50 transition-colors">
          <Link href="/attendance/staff/mark">
            <CardHeader>
              <div className="flex items-center justify-between">
                <ClipboardCheck className="h-8 w-8 text-primary" />
                <ArrowRight className="h-5 w-5 text-muted-foreground" />
              </div>
              <CardTitle className="mt-4">Mark Attendance</CardTitle>
              <CardDescription>
                Record daily staff attendance for all departments
              </CardDescription>
            </CardHeader>
          </Link>
        </Card>

        <Card className="hover:border-primary/50 transition-colors">
          <Link href="/attendance/staff/reports">
            <CardHeader>
              <div className="flex items-center justify-between">
                <BarChart3 className="h-8 w-8 text-primary" />
                <ArrowRight className="h-5 w-5 text-muted-foreground" />
              </div>
              <CardTitle className="mt-4">View Reports</CardTitle>
              <CardDescription>
                Analyze staff attendance statistics, trends, and generate reports
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
          {totalMarked > 0 ? (
            <div className="space-y-6">
              {/* Stats Grid */}
              <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-muted p-2">
                    <UserCog className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{totalMarked}</p>
                    <p className="text-sm text-muted-foreground">Total Marked</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-green-100 p-2 dark:bg-green-900">
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-green-600">{present}</p>
                    <p className="text-sm text-muted-foreground">Present</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-red-100 p-2 dark:bg-red-900">
                    <XCircle className="h-5 w-5 text-red-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-red-600">{absent + sick}</p>
                    <p className="text-sm text-muted-foreground">Absent / Sick</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 rounded-lg border p-4">
                  <div className="rounded-full bg-yellow-100 p-2 dark:bg-yellow-900">
                    <Clock className="h-5 w-5 text-yellow-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-yellow-600">{late}</p>
                    <p className="text-sm text-muted-foreground">Late</p>
                  </div>
                </div>
              </div>

              {/* Absent/Late Staff Table */}
              {absentLateStaff.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-3">
                    Absent / Late / Sick Staff Today
                  </h3>
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead className="hidden sm:table-cell">Staff ID</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="hidden sm:table-cell">Remarks</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {absentLateStaff.map((record) => (
                          <TableRow key={record.id}>
                            <TableCell className="font-medium">
                              {record.staff_name || "Unknown"}
                            </TableCell>
                            <TableCell className="hidden sm:table-cell font-mono text-sm">
                              {record.staff_number || "--"}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant="secondary"
                                className={
                                  record.status === "absent"
                                    ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                                    : record.status === "late"
                                    ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                                    : "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300"
                                }
                              >
                                {record.status.charAt(0).toUpperCase() + record.status.slice(1)}
                              </Badge>
                            </TableCell>
                            <TableCell className="hidden sm:table-cell text-muted-foreground">
                              {record.remarks || "--"}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Users className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">No Attendance Data Yet</h3>
              <p className="text-sm text-muted-foreground max-w-md mt-2">
                Start marking staff attendance for today to see the overview here.
              </p>
              <Button asChild className="mt-4">
                <Link href="/attendance/staff/mark">
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
