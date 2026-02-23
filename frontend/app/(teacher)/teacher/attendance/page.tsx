"use client";

/**
 * SIMS Plus - Teacher Attendance Page (Offline-Capable)
 *
 * Optimized attendance marking interface with offline support:
 * - All students default to "present" (most common case)
 * - Tap-to-cycle through statuses: present -> absent -> late -> excused -> sick -> present
 * - Color-coded status chips for fast visual scanning
 * - Batch submit with loading state
 * - Class/section selector for teachers with multiple assignments
 * - Offline: saves to IndexedDB and auto-syncs when back online
 * - Shows offline banner and sync status indicator
 */

import { useEffect, useState, useCallback, useTransition } from "react";
import {
  AlertCircle,
  Check,
  Cloud,
  Loader2,
  RefreshCw,
  RotateCcw,
  Save,
  Users,
  WifiOff,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getTeacherClasses,
  getTeacherAttendance,
  submitTeacherAttendance,
} from "@/actions/teacher.action";
import type {
  TeacherClassSummary,
  TeacherAttendanceStudent,
  TeacherAttendanceStatus,
} from "@/types/teacher.type";
import { useSession } from "@/components/providers/SessionProvider";
import { useOfflineAttendance } from "@/hooks/use-offline-attendance";
import { useNetworkStatus } from "@/hooks/use-network-status";
import { getInitials } from "@/lib/format";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { AttendanceRecord } from "@/lib/offline/db";

const STATUS_CYCLE: TeacherAttendanceStatus[] = [
  "present", "absent", "late", "excused", "sick",
];

const STATUS_COLORS: Record<TeacherAttendanceStatus, string> = {
  present: "bg-green-100 text-green-800 border-green-300",
  absent: "bg-red-100 text-red-800 border-red-300",
  late: "bg-amber-100 text-amber-800 border-amber-300",
  excused: "bg-blue-100 text-blue-800 border-blue-300",
  sick: "bg-purple-100 text-purple-800 border-purple-300",
};

const STATUS_LABELS: Record<TeacherAttendanceStatus, string> = {
  present: "P",
  absent: "A",
  late: "L",
  excused: "E",
  sick: "S",
};

export default function TeacherAttendancePage() {
  const { tenant } = useSession();
  const { isOnline } = useNetworkStatus();

  const [classes, setClasses] = useState<TeacherClassSummary[]>([]);
  const [selectedSection, setSelectedSection] = useState<string>("");
  const [date] = useState(() => new Date().toISOString().split("T")[0]);
  const [students, setStudents] = useState<TeacherAttendanceStudent[]>([]);
  const [records, setRecords] = useState<Map<string, TeacherAttendanceStatus>>(new Map());
  const [isMarked, setIsMarked] = useState(false);
  const [loadingClasses, setLoadingClasses] = useState(true);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [saved, setSaved] = useState(false);

  /**
   * Adapter: postAttendance converts the IndexedDB record shape into the
   * submitTeacherAttendance server action call. Returns true on success.
   */
  const postAttendance = useCallback(
    async (
      sectionId: string,
      attendanceDate: string,
      attendanceRecords: AttendanceRecord[]
    ): Promise<boolean> => {
      const result = await submitTeacherAttendance({
        section_id: sectionId,
        date: attendanceDate,
        records: attendanceRecords.map((r) => ({
          student_id: r.student_id,
          status: r.status as TeacherAttendanceStatus,
        })),
      });
      return result.success;
    },
    []
  );

  /**
   * Adapter: fetchStudents for the offline hook. Loads attendance data
   * and returns the student list in the shape the hook expects.
   */
  const fetchStudentsForSection = useCallback(async () => {
    const result = await getTeacherAttendance(selectedSection, date);
    if (result.success) {
      return result.data.students.map((s: TeacherAttendanceStudent) => ({
        id: s.student_id,
        student_id: s.student_id,
        first_name: s.first_name,
        last_name: s.last_name,
        gender: s.gender,
      }));
    }
    return [];
  }, [selectedSection, date]);

  // Wire up the offline attendance hook for background sync
  const {
    pendingCount,
    isSyncing,
    saveAttendance: saveOfflineAttendance,
    syncNow,
  } = useOfflineAttendance({
    sectionId: selectedSection,
    tenantId: tenant.id,
    fetchStudents: fetchStudentsForSection,
    postAttendance,
  });

  // Load classes on mount
  useEffect(() => {
    async function load() {
      const result = await getTeacherClasses();
      if (result.success) {
        setClasses(result.data);
        // Auto-select the class teacher's section, or the first section
        const classTeacherSection = result.data.find((c) => c.is_class_teacher);
        if (classTeacherSection?.section_id) {
          setSelectedSection(classTeacherSection.section_id);
        } else if (result.data.length > 0 && result.data[0].section_id) {
          setSelectedSection(result.data[0].section_id);
        }
      } else {
        setError(result.error);
      }
      setLoadingClasses(false);
    }
    load();
  }, []);

  // Load attendance when section changes
  useEffect(() => {
    if (!selectedSection) return;

    async function loadAttendance() {
      setLoadingStudents(true);
      setSaved(false);
      const result = await getTeacherAttendance(selectedSection, date);
      if (result.success) {
        setStudents(result.data.students);
        setIsMarked(result.data.is_marked);

        // Initialize records: use existing statuses or default all to "present"
        const newRecords = new Map<string, TeacherAttendanceStatus>();
        result.data.students.forEach((s: TeacherAttendanceStudent) => {
          newRecords.set(s.student_id, s.status || "present");
        });
        setRecords(newRecords);
      } else {
        // When offline, the server action will fail. Clear error if offline
        // since the user can still mark attendance locally.
        if (!isOnline) {
          setError(null);
        } else {
          setError(result.error);
        }
      }
      setLoadingStudents(false);
    }
    loadAttendance();
  }, [selectedSection, date]); // eslint-disable-line react-hooks/exhaustive-deps

  // Tap to cycle status
  const cycleStatus = useCallback((studentId: string) => {
    setRecords((prev) => {
      const next = new Map(prev);
      const current = next.get(studentId) || "present";
      const currentIdx = STATUS_CYCLE.indexOf(current);
      const nextStatus = STATUS_CYCLE[(currentIdx + 1) % STATUS_CYCLE.length];
      next.set(studentId, nextStatus);
      return next;
    });
    setSaved(false);
  }, []);

  // Reset all to present
  const resetAll = useCallback(() => {
    setRecords((prev) => {
      const next = new Map(prev);
      for (const key of next.keys()) {
        next.set(key, "present");
      }
      return next;
    });
    setSaved(false);
  }, []);

  // Submit attendance -- uses offline queue when network is unavailable
  const handleSubmit = () => {
    startTransition(async () => {
      const attendanceRecords: AttendanceRecord[] = [];
      records.forEach((status, student_id) => {
        attendanceRecords.push({ student_id, status });
      });

      // Use the offline-capable save path. It tries the API first,
      // and falls back to IndexedDB if the network is down.
      const { saved: didSave, offline } = await saveOfflineAttendance(
        date,
        attendanceRecords
      );

      if (didSave) {
        setSaved(true);
        setIsMarked(true);
        if (offline) {
          toast.success(
            "Attendance saved offline. It will sync when you reconnect."
          );
        } else {
          toast.success("Attendance saved successfully.");
        }
      } else {
        toast.error("Failed to save attendance. Please try again.");
      }
    });
  };

  // Compute summary
  const summary = {
    present: 0,
    absent: 0,
    late: 0,
    excused: 0,
    sick: 0,
  };
  records.forEach((status) => {
    summary[status]++;
  });

  // Get unique sections from classes
  const sectionOptions = classes
    .filter((c) => c.section_id)
    .reduce<{ id: string; label: string }[]>((acc, c) => {
      if (c.section_id && !acc.find((s) => s.id === c.section_id)) {
        acc.push({
          id: c.section_id,
          label: `${c.class_name}${c.section_name ? ` - ${c.section_name}` : ""}`,
        });
      }
      return acc;
    }, []);

  if (loadingClasses) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {/* Offline banner */}
      {!isOnline && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-4 py-2.5">
          <div className="flex items-center gap-2 text-sm text-yellow-700 dark:text-yellow-400">
            <WifiOff className="h-4 w-4 shrink-0" />
            <span>
              You are offline. Attendance will be saved locally and synced when
              you reconnect.
            </span>
          </div>
        </div>
      )}

      {/* Sync status: show pending count or syncing state */}
      {(pendingCount > 0 || isSyncing) && (
        <div className="flex items-center gap-2">
          {isSyncing ? (
            <Badge variant="secondary" className="gap-1 text-xs">
              <Loader2 className="h-3 w-3 animate-spin" />
              Syncing {pendingCount} record(s)...
            </Badge>
          ) : (
            <Badge variant="outline" className="gap-1 text-xs">
              <Cloud className="h-3 w-3" />
              {pendingCount} pending sync
            </Badge>
          )}
          {isOnline && pendingCount > 0 && !isSyncing && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={() => syncNow()}
            >
              <RefreshCw className="h-3 w-3 mr-1" />
              Sync Now
            </Button>
          )}
        </div>
      )}

      <div>
        <h1 className="text-2xl font-bold tracking-tight">Attendance</h1>
        <p className="text-muted-foreground">
          {new Date(date).toLocaleDateString("en-GB", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
          })}
        </p>
      </div>

      {/* Section selector */}
      <div className="flex flex-col sm:flex-row gap-3">
        <Select value={selectedSection} onValueChange={setSelectedSection}>
          <SelectTrigger className="w-full sm:w-[280px]">
            <SelectValue placeholder="Select a class/section" />
          </SelectTrigger>
          <SelectContent>
            {sectionOptions.map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {isMarked && (
          <Badge variant="outline" className="self-center text-green-600 border-green-300">
            <Check className="h-3 w-3 mr-1" />
            Already marked
          </Badge>
        )}
      </div>

      {!selectedSection ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Users className="h-10 w-10 text-muted-foreground/50 mx-auto mb-3" />
            <p className="text-muted-foreground">Select a class to mark attendance</p>
          </CardContent>
        </Card>
      ) : loadingStudents ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : (
        <>
          {/* Summary strip */}
          <div className="flex flex-wrap gap-2">
            <Badge className={STATUS_COLORS.present}>
              Present: {summary.present}
            </Badge>
            <Badge className={STATUS_COLORS.absent}>
              Absent: {summary.absent}
            </Badge>
            <Badge className={STATUS_COLORS.late}>
              Late: {summary.late}
            </Badge>
            <Badge className={STATUS_COLORS.excused}>
              Excused: {summary.excused}
            </Badge>
            <Badge className={STATUS_COLORS.sick}>
              Sick: {summary.sick}
            </Badge>
          </div>

          {/* Legend */}
          <p className="text-xs text-muted-foreground">
            Tap a student&apos;s status to cycle: Present {"->"} Absent {"->"} Late {"->"} Excused {"->"} Sick
          </p>

          {/* Student list */}
          <div className="space-y-1.5">
            {students.map((student: TeacherAttendanceStudent) => {
              const status = records.get(student.student_id) || "present";
              return (
                <div
                  key={student.student_id}
                  className="flex items-center gap-3 rounded-lg border p-2.5 hover:bg-muted/30 transition-colors"
                >
                  <Avatar className="h-8 w-8 shrink-0">
                    <AvatarFallback className="bg-primary/10 text-primary text-[10px]">
                      {getInitials(`${student.first_name} ${student.last_name}`)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {student.first_name} {student.last_name}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {student.student_number}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => cycleStatus(student.student_id)}
                    className={cn(
                      "flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm font-bold transition-all active:scale-95",
                      STATUS_COLORS[status]
                    )}
                    aria-label={`${student.first_name} ${student.last_name}: ${status}. Tap to change.`}
                  >
                    {STATUS_LABELS[status]}
                  </button>
                </div>
              );
            })}
          </div>

          {/* Action buttons */}
          <div className="sticky bottom-20 md:bottom-4 flex gap-2 bg-background/95 backdrop-blur pt-3 pb-1 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={resetAll}
              disabled={isPending}
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1" />
              Reset All
            </Button>
            <Button
              size="sm"
              className="flex-1"
              onClick={handleSubmit}
              disabled={isPending || saved}
            >
              {isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  Saving...
                </>
              ) : saved ? (
                <>
                  <Check className="h-3.5 w-3.5 mr-1" />
                  Saved{!isOnline ? " (Offline)" : ""}
                </>
              ) : (
                <>
                  <Save className="h-3.5 w-3.5 mr-1" />
                  Save Attendance
                </>
              )}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
