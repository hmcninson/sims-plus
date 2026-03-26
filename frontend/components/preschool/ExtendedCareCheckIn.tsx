"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { format } from "date-fns";
import {
  Loader2,
  Sun,
  Moon,
  CheckCircle2,
  Circle,
  LogIn,
  LogOut,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getStudents } from "@/actions/students.action";
import {
  checkInExtendedCare,
  checkOutExtendedCare,
  listExtendedCareSessions,
} from "@/actions/preschool.action";
import type { Class, ExtendedCareSession, ExtendedCareSessionType } from "@/types";

interface StudentItem {
  id: string;
  first_name: string;
  last_name: string;
  student_id: string;
}

interface ExtendedCareCheckInProps {
  classes: Class[];
}

export function ExtendedCareCheckIn({ classes }: ExtendedCareCheckInProps) {
  const [selectedClassId, setSelectedClassId] = useState("");
  const [students, setStudents] = useState<StudentItem[]>([]);
  const [sessions, setSessions] = useState<ExtendedCareSession[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());

  const today = format(new Date(), "yyyy-MM-dd");

  const loadStudents = useCallback(async (classId: string) => {
    setLoadingStudents(true);
    const result = await getStudents({ class_id: classId, status: "active" });
    if (result.success && result.data) {
      setStudents(
        result.data.items.map((s) => ({
          id: s.id,
          first_name: s.first_name,
          last_name: s.last_name,
          student_id: s.student_id,
        }))
      );
    }
    setLoadingStudents(false);
  }, []);

  const loadSessions = useCallback(async (classId: string) => {
    setLoadingSessions(true);
    const result = await listExtendedCareSessions({
      class_id: classId,
      date_from: today,
      date_to: today,
    });
    if (result.success && result.data) {
      setSessions(result.data);
    }
    setLoadingSessions(false);
  }, [today]);

  useEffect(() => {
    if (selectedClassId) {
      loadStudents(selectedClassId);
      loadSessions(selectedClassId);
    } else {
      setStudents([]);
      setSessions([]);
    }
  }, [selectedClassId, loadStudents, loadSessions]);

  function getStudentSession(
    studentId: string,
    type: ExtendedCareSessionType
  ): ExtendedCareSession | undefined {
    return sessions.find(
      (s) => s.student_id === studentId && s.session_type === type
    );
  }

  async function handleCheckIn(studentId: string, type: ExtendedCareSessionType) {
    const key = `${studentId}-${type}-in`;
    setProcessingIds((prev) => new Set(prev).add(key));
    try {
      const result = await checkInExtendedCare({
        student_id: studentId,
        session_type: type,
        check_in_time: format(new Date(), "HH:mm"),
      });
      if (result.success && result.data) {
        setSessions((prev) => [...prev, result.data]);
        toast.success("Checked in successfully");
      } else {
        toast.error(result.error || "Check-in failed");
      }
    } catch {
      toast.error("Check-in failed");
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  }

  async function handleCheckOut(sessionId: string, studentId: string, type: ExtendedCareSessionType) {
    const key = `${studentId}-${type}-out`;
    setProcessingIds((prev) => new Set(prev).add(key));
    try {
      const result = await checkOutExtendedCare(sessionId);
      if (result.success && result.data) {
        setSessions((prev) =>
          prev.map((s) => (s.id === sessionId ? result.data : s))
        );
        toast.success("Checked out successfully");
      } else {
        toast.error(result.error || "Check-out failed");
      }
    } catch {
      toast.error("Check-out failed");
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  }

  function StudentRow({
    student,
    type,
  }: {
    student: StudentItem;
    type: ExtendedCareSessionType;
  }) {
    const session = getStudentSession(student.id, type);
    const isCheckedIn = !!session && !session.check_out_time;
    const isCheckedOut = !!session?.check_out_time;
    const checkInKey = `${student.id}-${type}-in`;
    const checkOutKey = `${student.id}-${type}-out`;
    const isProcessing = processingIds.has(checkInKey) || processingIds.has(checkOutKey);

    return (
      <div
        className={cn(
          "flex items-center justify-between rounded-lg border p-3 transition-colors",
          isCheckedIn && "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/30",
          isCheckedOut && "border-muted bg-muted/30"
        )}
      >
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "h-2.5 w-2.5 rounded-full",
              isCheckedIn ? "bg-green-500" : isCheckedOut ? "bg-gray-400" : "bg-transparent border border-muted-foreground"
            )}
          />
          <div>
            <p className="text-sm font-medium">
              {student.first_name} {student.last_name}
            </p>
            {session && (
              <p className="text-xs text-muted-foreground">
                In: {session.check_in_time}
                {session.check_out_time && ` | Out: ${session.check_out_time}`}
                {session.duration_minutes != null && ` (${session.duration_minutes} min)`}
              </p>
            )}
          </div>
        </div>

        <div>
          {!session && (
            <Button
              size="sm"
              variant="outline"
              disabled={isProcessing}
              onClick={() => handleCheckIn(student.id, type)}
            >
              {isProcessing ? (
                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
              ) : (
                <LogIn className="mr-1 h-3.5 w-3.5" />
              )}
              Check In
            </Button>
          )}
          {isCheckedIn && (
            <Button
              size="sm"
              variant="default"
              disabled={isProcessing}
              onClick={() => handleCheckOut(session.id, student.id, type)}
            >
              {isProcessing ? (
                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
              ) : (
                <LogOut className="mr-1 h-3.5 w-3.5" />
              )}
              Check Out
            </Button>
          )}
          {isCheckedOut && (
            <Badge variant="secondary" className="text-xs">
              <CheckCircle2 className="mr-1 h-3 w-3" />
              Done
            </Badge>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Class Selector */}
      <Select value={selectedClassId} onValueChange={setSelectedClassId}>
        <SelectTrigger className="w-full md:w-[280px]">
          <SelectValue placeholder="Select class..." />
        </SelectTrigger>
        <SelectContent>
          {classes.map((c) => (
            <SelectItem key={c.id} value={c.id}>
              {c.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {!selectedClassId && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Circle className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground">
              Select a class to manage extended care check-ins.
            </p>
          </CardContent>
        </Card>
      )}

      {selectedClassId && (loadingStudents || loadingSessions) && (
        <div className="grid gap-6 md:grid-cols-2">
          {[0, 1].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-32" />
              </CardHeader>
              <CardContent className="space-y-3">
                {Array.from({ length: 4 }).map((_, j) => (
                  <Skeleton key={j} className="h-14 w-full rounded-lg" />
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {selectedClassId && !loadingStudents && !loadingSessions && (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Before Care Column */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Sun className="h-5 w-5 text-amber-500" />
                <CardTitle className="text-lg">Before Care</CardTitle>
              </div>
              <CardDescription>Morning extended care sessions</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {students.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No students in this class.
                </p>
              ) : (
                students.map((student) => (
                  <StudentRow
                    key={student.id}
                    student={student}
                    type="before_care"
                  />
                ))
              )}
            </CardContent>
          </Card>

          {/* After Care Column */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Moon className="h-5 w-5 text-indigo-500" />
                <CardTitle className="text-lg">After Care</CardTitle>
              </div>
              <CardDescription>Afternoon extended care sessions</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {students.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No students in this class.
                </p>
              ) : (
                students.map((student) => (
                  <StudentRow
                    key={student.id}
                    student={student}
                    type="after_care"
                  />
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
