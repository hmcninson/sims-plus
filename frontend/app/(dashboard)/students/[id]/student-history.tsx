"use client";

import { useEffect, useState } from "react";
import {
  ArrowRight,
  Calendar,
  Clock,
  GraduationCap,
  History,
  Loader2,
  UserCheck,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { getClassHistory, getStatusHistory } from "@/actions/students.action";
import type { ClassHistoryRecord, StatusChangeRecord } from "@/types";

interface StudentHistoryProps {
  studentId: string;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getStatusBadgeVariant(status: string): {
  className: string;
  label: string;
} {
  const map: Record<string, { className: string; label: string }> = {
    active: {
      className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      label: "Active",
    },
    inactive: {
      className: "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400",
      label: "Inactive",
    },
    graduated: {
      className: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
      label: "Graduated",
    },
    transferred: {
      className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
      label: "Transferred",
    },
    withdrawn: {
      className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
      label: "Withdrawn",
    },
    suspended: {
      className: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
      label: "Suspended",
    },
  };
  const fallback = {
    className: "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400",
    label: status.charAt(0).toUpperCase() + status.slice(1),
  };
  return map[status] || fallback;
}

function HistorySkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function StudentHistory({ studentId }: StudentHistoryProps) {
  const [classHistory, setClassHistory] = useState<ClassHistoryRecord[]>([]);
  const [statusHistory, setStatusHistory] = useState<StatusChangeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchHistory() {
      setLoading(true);
      setError(null);

      const [classRes, statusRes] = await Promise.all([
        getClassHistory(studentId),
        getStatusHistory(studentId),
      ]);

      if (classRes.success && classRes.data) {
        setClassHistory(classRes.data.records);
      } else {
        setError(classRes.error || "Failed to load history");
      }

      if (statusRes.success && statusRes.data) {
        setStatusHistory(statusRes.data.records);
      }

      setLoading(false);
    }

    fetchHistory();
  }, [studentId]);

  if (loading) {
    return <HistorySkeleton />;
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
          <History className="h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Class Assignment History */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <GraduationCap className="h-4 w-4" />
            Class Assignment History
          </CardTitle>
          <CardDescription>
            Track of all class and section assignments across academic years
          </CardDescription>
        </CardHeader>
        <CardContent>
          {classHistory.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <GraduationCap className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No class history records found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Academic Year</TableHead>
                    <TableHead>Class</TableHead>
                    <TableHead className="hidden sm:table-cell">Enrolled</TableHead>
                    <TableHead className="hidden sm:table-cell">Left</TableHead>
                    <TableHead className="hidden md:table-cell">Reason</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {classHistory.map((record) => {
                    const isCurrent = !record.left_date;
                    return (
                      <TableRow key={record.id}>
                        <TableCell className="font-medium">
                          {record.academic_year_name || "N/A"}
                        </TableCell>
                        <TableCell>
                          <div>
                            <span>{record.class_name || "N/A"}</span>
                            {record.section_name && (
                              <span className="text-muted-foreground">
                                {" "}({record.section_name})
                              </span>
                            )}
                          </div>
                          {/* Mobile-only: show dates inline */}
                          <div className="sm:hidden text-xs text-muted-foreground mt-1">
                            {formatDate(record.enrolled_date)}
                            {record.left_date && ` - ${formatDate(record.left_date)}`}
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          {formatDate(record.enrolled_date)}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          {record.left_date ? formatDate(record.left_date) : "--"}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-muted-foreground">
                          {record.reason || "--"}
                        </TableCell>
                        <TableCell>
                          {isCurrent ? (
                            <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-100">
                              Current
                            </Badge>
                          ) : (
                            <Badge variant="secondary">Past</Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Status Change History */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Status Change History
          </CardTitle>
          <CardDescription>
            Timeline of enrollment status changes for this student
          </CardDescription>
        </CardHeader>
        <CardContent>
          {statusHistory.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <Clock className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No status changes recorded</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Status Change</TableHead>
                    <TableHead className="hidden sm:table-cell">Reason</TableHead>
                    <TableHead className="hidden md:table-cell">Performed By</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {statusHistory.map((record) => {
                    const fromBadge = record.from_status
                      ? getStatusBadgeVariant(record.from_status)
                      : null;
                    const toBadge = getStatusBadgeVariant(record.to_status);
                    return (
                      <TableRow key={record.id}>
                        <TableCell className="font-medium whitespace-nowrap">
                          {formatDate(record.effective_date)}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {fromBadge ? (
                              <>
                                <Badge
                                  variant="outline"
                                  className={fromBadge.className}
                                >
                                  {fromBadge.label}
                                </Badge>
                                <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                              </>
                            ) : (
                              <span className="text-xs text-muted-foreground mr-1">New:</span>
                            )}
                            <Badge
                              variant="outline"
                              className={toBadge.className}
                            >
                              {toBadge.label}
                            </Badge>
                          </div>
                          {/* Mobile-only: show reason + performer */}
                          <div className="sm:hidden text-xs text-muted-foreground mt-1">
                            {record.reason && <span>{record.reason}</span>}
                            {record.performed_by_name && (
                              <span className="block">By: {record.performed_by_name}</span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-muted-foreground">
                          {record.reason || "--"}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-muted-foreground">
                          {record.performed_by_name || "--"}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
