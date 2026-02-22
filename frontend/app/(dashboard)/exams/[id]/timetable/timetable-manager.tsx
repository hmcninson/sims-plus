"use client";

import { useState, useTransition, useMemo } from "react";
import Link from "next/link";
import { format, parseISO } from "date-fns";
import {
  ArrowLeft,
  Calendar,
  Clock,
  MapPin,
  AlertTriangle,
  CheckCircle2,
  Save,
  Pencil,
  X,
  Loader2,
  CalendarDays,
  BookOpen,
  GraduationCap,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

import {
  getExamTimetable,
  checkTimetableConflicts,
  bulkUpdateTimetable,
  type ExamTimetable,
  type TimetableEntry,
  type TimetableConflicts,
  type TimetableEntryUpdate,
} from "@/actions/exams.action";
import type { ExamWithContext } from "@/types";

interface TimetableManagerProps {
  exam: ExamWithContext;
  initialTimetable: ExamTimetable | null;
  initialConflicts: TimetableConflicts | null;
}

interface EditingEntry extends TimetableEntryUpdate {
  subject_name: string;
  class_name: string;
}

export function TimetableManager({ exam, initialTimetable, initialConflicts }: TimetableManagerProps) {
  const [isPending, startTransition] = useTransition();
  const [timetable, setTimetable] = useState<ExamTimetable | null>(initialTimetable);
  const [conflicts, setConflicts] = useState<TimetableConflicts | null>(initialConflicts);
  const [isEditing, setIsEditing] = useState(false);
  const [editingEntries, setEditingEntries] = useState<Map<string, EditingEntry>>(new Map());
  const [editDialogEntry, setEditDialogEntry] = useState<TimetableEntry | null>(null);

  // Group entries by date
  const groupedEntries = useMemo(() => {
    if (!timetable?.entries) return new Map<string, TimetableEntry[]>();

    const grouped = new Map<string, TimetableEntry[]>();
    const sortedEntries = [...timetable.entries].sort((a, b) => {
      // Sort by date first, then time
      if (a.exam_date && b.exam_date) {
        const dateCompare = a.exam_date.localeCompare(b.exam_date);
        if (dateCompare !== 0) return dateCompare;
        if (a.exam_time && b.exam_time) {
          return a.exam_time.localeCompare(b.exam_time);
        }
      }
      // Entries without dates go last
      if (!a.exam_date && b.exam_date) return 1;
      if (a.exam_date && !b.exam_date) return -1;
      return 0;
    });

    for (const entry of sortedEntries) {
      const dateKey = entry.exam_date || "unscheduled";
      if (!grouped.has(dateKey)) {
        grouped.set(dateKey, []);
      }
      grouped.get(dateKey)!.push(entry);
    }

    return grouped;
  }, [timetable?.entries]);

  const refreshData = async () => {
    startTransition(async () => {
      const [timetableResult, conflictsResult] = await Promise.all([
        getExamTimetable(exam.id),
        checkTimetableConflicts(exam.id),
      ]);
      if (timetableResult.success && timetableResult.data) {
        setTimetable(timetableResult.data);
      }
      if (conflictsResult.success && conflictsResult.data) {
        setConflicts(conflictsResult.data);
      }
    });
  };

  const handleEditEntry = (entry: TimetableEntry) => {
    setEditDialogEntry(entry);
  };

  const handleSaveEntry = async (entry: TimetableEntry, updates: Partial<EditingEntry>) => {
    const updateData: TimetableEntryUpdate = {
      exam_subject_id: entry.exam_subject_id,
      exam_date: updates.exam_date || entry.exam_date,
      exam_time: updates.exam_time || entry.exam_time,
      duration_minutes: updates.duration_minutes || entry.duration_minutes,
      venue: updates.venue || entry.venue,
    };

    startTransition(async () => {
      const result = await bulkUpdateTimetable(exam.id, [updateData]);
      if (result.success && result.data) {
        if (result.data.failed > 0) {
          toast.error("Failed to update entry", {
            description: result.data.errors?.[0]?.error || "Unknown error",
          });
        } else {
          toast.success("Timetable updated");
          await refreshData();
        }
        setEditDialogEntry(null);
      } else {
        toast.error("Failed to update timetable");
      }
    });
  };

  const handleBulkSave = async () => {
    if (editingEntries.size === 0) {
      setIsEditing(false);
      return;
    }

    const updates: TimetableEntryUpdate[] = Array.from(editingEntries.values()).map((entry) => ({
      exam_subject_id: entry.exam_subject_id,
      exam_date: entry.exam_date,
      exam_time: entry.exam_time,
      duration_minutes: entry.duration_minutes,
      venue: entry.venue,
    }));

    startTransition(async () => {
      const result = await bulkUpdateTimetable(exam.id, updates);
      if (result.success && result.data) {
        if (result.data.failed > 0) {
          toast.error(`${result.data.failed} entries failed to update`, {
            description: result.data.errors?.[0]?.error,
          });
        } else {
          toast.success(`${result.data.updated} entries updated`);
        }
        await refreshData();
        setIsEditing(false);
        setEditingEntries(new Map());
      } else {
        toast.error("Failed to update timetable");
      }
    });
  };

  const formatTime = (time: string | undefined) => {
    if (!time) return "Not set";
    // Time is in HH:MM format
    const [hours, minutes] = time.split(":");
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? "PM" : "AM";
    const displayHour = hour % 12 || 12;
    return `${displayHour}:${minutes} ${ampm}`;
  };

  const formatDate = (date: string) => {
    if (date === "unscheduled") return "Unscheduled";
    try {
      return format(parseISO(date), "EEEE, MMMM d, yyyy");
    } catch {
      return date;
    }
  };

  const getStatusBadge = (status: string) => {
    const config: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string }> = {
      pending: { variant: "secondary", label: "Pending" },
      in_progress: { variant: "default", label: "In Progress" },
      submitted: { variant: "outline", label: "Submitted" },
      published: { variant: "default", label: "Published" },
    };
    const { variant, label } = config[status] || { variant: "secondary", label: status };
    return <Badge variant={variant}>{label}</Badge>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/exams/${exam.id}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{exam.name} - Timetable</h1>
          <p className="text-muted-foreground">
            {exam.academic_year_name} - {exam.term_name}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              <Button variant="outline" onClick={() => { setIsEditing(false); setEditingEntries(new Map()); }}>
                <X className="mr-2 h-4 w-4" />
                Cancel
              </Button>
              <Button onClick={handleBulkSave} disabled={isPending}>
                {isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Save Changes
              </Button>
            </>
          ) : (
            <Button onClick={() => setIsEditing(true)}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit Timetable
            </Button>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      {timetable && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Subjects</CardDescription>
              <CardTitle className="text-2xl flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-muted-foreground" />
                {timetable.total_subjects}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Scheduled</CardDescription>
              <CardTitle className="text-2xl flex items-center gap-2 text-green-600">
                <CheckCircle2 className="h-5 w-5" />
                {timetable.scheduled_subjects}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Unscheduled</CardDescription>
              <CardTitle className="text-2xl flex items-center gap-2 text-amber-600">
                <AlertCircle className="h-5 w-5" />
                {timetable.unscheduled_subjects}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Exam Period</CardDescription>
              <CardTitle className="text-lg flex items-center gap-2">
                <CalendarDays className="h-5 w-5 text-muted-foreground" />
                {timetable.start_date && timetable.end_date ? (
                  <span className="text-sm">
                    {format(parseISO(timetable.start_date), "MMM d")} - {format(parseISO(timetable.end_date), "MMM d")}
                  </span>
                ) : (
                  <span className="text-sm text-muted-foreground">Not set</span>
                )}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Conflict Warnings */}
      {conflicts && conflicts.has_conflicts && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Scheduling Conflicts Detected</AlertTitle>
          <AlertDescription>
            <div className="mt-2 space-y-2">
              {conflicts.conflicts.map((conflict, index) => (
                <div key={index} className="flex items-start gap-2">
                  <Badge variant={conflict.severity === "error" ? "destructive" : "secondary"}>
                    {conflict.conflict_type}
                  </Badge>
                  <span className="text-sm">{conflict.message}</span>
                </div>
              ))}
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* No Conflicts */}
      {conflicts && !conflicts.has_conflicts && timetable && timetable.scheduled_subjects > 0 && (
        <Alert className="border-green-500 bg-green-50 dark:bg-green-950">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertTitle className="text-green-600">No Conflicts</AlertTitle>
          <AlertDescription className="text-green-600">
            All scheduled exams are free of venue and time conflicts.
          </AlertDescription>
        </Alert>
      )}

      {/* Loading State */}
      {isPending && (
        <div className="flex h-32 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Timetable Content */}
      {timetable && !isPending && (
        <div className="space-y-6">
          {Array.from(groupedEntries.entries()).map(([date, entries]) => (
            <Card key={date}>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-muted-foreground" />
                  <CardTitle className="text-lg">{formatDate(date)}</CardTitle>
                  <Badge variant="secondary">{entries.length} subjects</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[100px]">Time</TableHead>
                      <TableHead>Subject</TableHead>
                      <TableHead>Class</TableHead>
                      <TableHead>Venue</TableHead>
                      <TableHead className="text-center">Duration</TableHead>
                      <TableHead className="text-center">Status</TableHead>
                      <TableHead className="w-[80px]"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entries.map((entry) => (
                      <TableRow key={entry.exam_subject_id}>
                        <TableCell>
                          <div className="flex items-center gap-1 text-sm">
                            <Clock className="h-4 w-4 text-muted-foreground" />
                            {formatTime(entry.exam_time)}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div>
                            <p className="font-medium">{entry.subject_name}</p>
                            {entry.subject_code && (
                              <p className="text-xs text-muted-foreground">{entry.subject_code}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <GraduationCap className="h-4 w-4 text-muted-foreground" />
                            <span>{entry.class_name}</span>
                            {entry.section_name && (
                              <Badge variant="outline" className="text-xs">
                                {entry.section_name}
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <MapPin className="h-4 w-4 text-muted-foreground" />
                            <span>{entry.venue || "Not assigned"}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          {entry.duration_minutes ? `${entry.duration_minutes} min` : "-"}
                        </TableCell>
                        <TableCell className="text-center">
                          {getStatusBadge(entry.status)}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEditEntry(entry)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ))}

          {timetable.entries.length === 0 && (
            <Card>
              <CardContent className="py-12 text-center">
                <Calendar className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <h3 className="mt-4 text-lg font-semibold">No subjects added</h3>
                <p className="text-muted-foreground">
                  Add subjects to this exam to create a timetable.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Edit Entry Dialog */}
      <EditEntryDialog
        entry={editDialogEntry}
        onClose={() => setEditDialogEntry(null)}
        onSave={handleSaveEntry}
        isPending={isPending}
      />
    </div>
  );
}

interface EditEntryDialogProps {
  entry: TimetableEntry | null;
  onClose: () => void;
  onSave: (entry: TimetableEntry, updates: Partial<EditingEntry>) => void;
  isPending: boolean;
}

function EditEntryDialog({ entry, onClose, onSave, isPending }: EditEntryDialogProps) {
  const [formData, setFormData] = useState({
    exam_date: "",
    exam_time: "",
    duration_minutes: "",
    venue: "",
  });

  // Update form when entry changes
  useState(() => {
    if (entry) {
      setFormData({
        exam_date: entry.exam_date || "",
        exam_time: entry.exam_time || "",
        duration_minutes: entry.duration_minutes?.toString() || "",
        venue: entry.venue || "",
      });
    }
  });

  if (!entry) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(entry, {
      exam_date: formData.exam_date || undefined,
      exam_time: formData.exam_time || undefined,
      duration_minutes: formData.duration_minutes ? parseInt(formData.duration_minutes) : undefined,
      venue: formData.venue || undefined,
    });
  };

  return (
    <Dialog open={!!entry} onOpenChange={() => onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Schedule</DialogTitle>
          <DialogDescription>
            {entry.subject_name} - {entry.class_name}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-1 sm:grid-cols-4 items-center gap-4">
              <Label htmlFor="exam_date" className="sm:text-right">
                Date
              </Label>
              <Input
                id="exam_date"
                type="date"
                value={formData.exam_date}
                onChange={(e) => setFormData({ ...formData, exam_date: e.target.value })}
                className="sm:col-span-3"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 items-center gap-4">
              <Label htmlFor="exam_time" className="sm:text-right">
                Time
              </Label>
              <Input
                id="exam_time"
                type="time"
                value={formData.exam_time}
                onChange={(e) => setFormData({ ...formData, exam_time: e.target.value })}
                className="sm:col-span-3"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 items-center gap-4">
              <Label htmlFor="duration" className="sm:text-right">
                Duration (min)
              </Label>
              <Input
                id="duration"
                type="number"
                value={formData.duration_minutes}
                onChange={(e) => setFormData({ ...formData, duration_minutes: e.target.value })}
                placeholder="e.g., 120"
                className="sm:col-span-3"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 items-center gap-4">
              <Label htmlFor="venue" className="sm:text-right">
                Venue
              </Label>
              <Input
                id="venue"
                value={formData.venue}
                onChange={(e) => setFormData({ ...formData, venue: e.target.value })}
                placeholder="e.g., Main Hall"
                className="sm:col-span-3"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
