"use client";

import { useState, useMemo, useTransition } from "react";
import { useRouter } from "next/navigation";
import { format, parseISO } from "date-fns";
import {
  BookOpen,
  Filter,
  MoreHorizontal,
  Pencil,
  Trash2,
  Loader2,
  ClipboardEdit,
  BarChart3,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { AddSubjectsDialog } from "./add-subjects-dialog";
import { updateExamSubject, removeExamSubject } from "@/actions/exams.action";
import type { ExamSubjectWithDetails, ExamSubjectStatus, ExamSubjectUpdate } from "@/types";

interface ExamSubjectsProps {
  examId: string;
  subjects: ExamSubjectWithDetails[];
}

const SUBJECT_STATUS_CONFIG: Record<ExamSubjectStatus, { label: string; color: string }> = {
  pending: { label: "Not Started", color: "bg-gray-400" },
  scores_entered: { label: "In Progress", color: "bg-amber-500" },
  submitted: { label: "Submitted", color: "bg-blue-500" },
  published: { label: "Published", color: "bg-green-500" },
};

export function ExamSubjects({ examId, subjects }: ExamSubjectsProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [selectedClass, setSelectedClass] = useState<string>("all");

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingSubject, setEditingSubject] = useState<ExamSubjectWithDetails | null>(null);
  const [editForm, setEditForm] = useState<ExamSubjectUpdate>({});

  // Delete dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingSubject, setDeletingSubject] = useState<ExamSubjectWithDetails | null>(null);

  // Get unique classes (sorted by sequence)
  const classes = useMemo(() => {
    const classMap = new Map<string, { name: string; sequence: number }>();
    for (const subject of subjects) {
      if (!classMap.has(subject.class_id)) {
        classMap.set(subject.class_id, {
          name: subject.class_name,
          sequence: subject.class_sequence,
        });
      }
    }
    return Array.from(classMap.entries())
      .map(([id, { name, sequence }]) => ({ id, name, sequence }))
      .sort((a, b) => a.sequence - b.sequence);
  }, [subjects]);

  // Filter and group subjects by class
  const filteredSubjects = useMemo(() => {
    if (selectedClass === "all") {
      return subjects;
    }
    return subjects.filter((s) => s.class_id === selectedClass);
  }, [subjects, selectedClass]);

  // Group filtered subjects by class/section
  const subjectsByClassSection = useMemo(() => {
    const grouped: Record<string, ExamSubjectWithDetails[]> = {};
    for (const subject of filteredSubjects) {
      // Create key that includes section if available
      const key = subject.section_name
        ? `${subject.class_name} - ${subject.section_name}`
        : subject.class_name;
      if (!grouped[key]) {
        grouped[key] = [];
      }
      grouped[key].push(subject);
    }
    return grouped;
  }, [filteredSubjects]);

  // Calculate stats
  const totalSubjects = filteredSubjects.length;
  const totalScoresEntered = filteredSubjects.reduce(
    (sum, s) => sum + (s.scores_count || 0),
    0
  );
  const totalStudents = filteredSubjects.reduce(
    (sum, s) => sum + (s.students_count || 0),
    0
  );

  // Handle edit
  const handleEditClick = (subject: ExamSubjectWithDetails) => {
    setEditingSubject(subject);
    setEditForm({
      max_score: subject.max_score,
      pass_mark: subject.pass_mark,
      exam_date: subject.exam_date || undefined,
      exam_time: subject.exam_time || undefined,
      duration_minutes: subject.duration_minutes || undefined,
      venue: subject.venue || undefined,
    });
    setEditDialogOpen(true);
  };

  const handleEditSave = () => {
    if (!editingSubject) return;

    startTransition(async () => {
      const result = await updateExamSubject(examId, editingSubject.id, editForm);
      if (result.success) {
        toast.success("Subject updated");
        setEditDialogOpen(false);
        setEditingSubject(null);
        router.refresh();
      } else {
        toast.error("Failed to update subject", { description: result.error });
      }
    });
  };

  // Handle delete
  const handleDeleteClick = (subject: ExamSubjectWithDetails) => {
    setDeletingSubject(subject);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (!deletingSubject) return;

    startTransition(async () => {
      const result = await removeExamSubject(examId, deletingSubject.id);
      if (result.success) {
        toast.success("Subject removed from exam");
        setDeleteDialogOpen(false);
        setDeletingSubject(null);
        router.refresh();
      } else {
        toast.error("Failed to remove subject", { description: result.error });
      }
    });
  };

  if (subjects.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Exam Subjects</CardTitle>
          <CardDescription>
            Subjects and classes included in this examination.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-semibold">No subjects added</h3>
            <p className="text-muted-foreground mb-4">
              Add subjects to this exam to start entering scores.
            </p>
            <AddSubjectsDialog examId={examId} />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Exam Subjects</CardTitle>
              <CardDescription>
                {totalSubjects} subjects across {classes.length} classes
                {selectedClass !== "all" && (
                  <span className="ml-1">
                    ({totalScoresEntered} / {totalStudents} scores entered)
                  </span>
                )}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Select value={selectedClass} onValueChange={setSelectedClass}>
                <SelectTrigger className="w-full sm:w-[200px]">
                  <SelectValue placeholder="Filter by class" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Classes ({subjects.length})</SelectItem>
                  {classes.map((cls) => {
                    const count = subjects.filter((s) => s.class_id === cls.id).length;
                    return (
                      <SelectItem key={cls.id} value={cls.id}>
                        {cls.name} ({count})
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {Object.entries(subjectsByClassSection).map(([groupName, classSubjects]) => (
              <div key={groupName}>
                <h3 className="font-semibold text-lg mb-3">{groupName}</h3>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Subject</TableHead>
                        <TableHead className="hidden sm:table-cell">Max Score</TableHead>
                        <TableHead className="hidden md:table-cell">Pass Mark</TableHead>
                        <TableHead className="hidden md:table-cell">Date/Time</TableHead>
                        <TableHead>Progress</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="w-[50px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {classSubjects.map((subject) => (
                        <TableRow key={subject.id}>
                          <TableCell>
                            <div>
                              <p className="font-medium">{subject.subject_name}</p>
                              <p className="text-sm text-muted-foreground">
                                {subject.subject_code}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">{subject.max_score}</TableCell>
                          <TableCell className="hidden md:table-cell">{subject.pass_mark}</TableCell>
                          <TableCell className="hidden md:table-cell">
                            {subject.exam_date ? (
                              <div>
                                <p>{format(parseISO(subject.exam_date), "MMM d")}</p>
                                {subject.exam_time && (
                                  <p className="text-sm text-muted-foreground">
                                    {subject.exam_time}
                                  </p>
                                )}
                              </div>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {subject.scores_count} / {subject.students_count}
                          </TableCell>
                          <TableCell>
                            <Badge
                              className={`${
                                SUBJECT_STATUS_CONFIG[subject.status]?.color
                              } text-white`}
                            >
                              {SUBJECT_STATUS_CONFIG[subject.status]?.label}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  onClick={() =>
                                    router.push(
                                      `/exams/${examId}/scores/${subject.id}`
                                    )
                                  }
                                >
                                  <ClipboardEdit className="mr-2 h-4 w-4" />
                                  Enter Scores
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() =>
                                    router.push(
                                      `/exams/${examId}/results?class=${subject.class_id}`
                                    )
                                  }
                                >
                                  <BarChart3 className="mr-2 h-4 w-4" />
                                  View Results
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem onClick={() => handleEditClick(subject)}>
                                  <Pencil className="mr-2 h-4 w-4" />
                                  Edit
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => handleDeleteClick(subject)}
                                  className="text-destructive focus:text-destructive"
                                >
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  Remove
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Exam Subject</DialogTitle>
            <DialogDescription>
              {editingSubject?.subject_name} - {editingSubject?.class_name}
              {editingSubject?.section_name && ` (${editingSubject.section_name})`}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="max_score">Max Score</Label>
                <Input
                  id="max_score"
                  type="number"
                  min={1}
                  value={editForm.max_score || ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, max_score: Number(e.target.value) })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pass_mark">Pass Mark</Label>
                <Input
                  id="pass_mark"
                  type="number"
                  min={0}
                  value={editForm.pass_mark || ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, pass_mark: Number(e.target.value) })
                  }
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="exam_date">Exam Date</Label>
                <Input
                  id="exam_date"
                  type="date"
                  value={editForm.exam_date || ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, exam_date: e.target.value || undefined })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="exam_time">Exam Time</Label>
                <Input
                  id="exam_time"
                  type="time"
                  value={editForm.exam_time || ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, exam_time: e.target.value || undefined })
                  }
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="duration">Duration (minutes)</Label>
                <Input
                  id="duration"
                  type="number"
                  min={0}
                  value={editForm.duration_minutes || ""}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      duration_minutes: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="venue">Venue</Label>
                <Input
                  id="venue"
                  value={editForm.venue || ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, venue: e.target.value || undefined })
                  }
                  placeholder="e.g., Room 101"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEditSave} disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Subject from Exam?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove{" "}
              <span className="font-semibold">{deletingSubject?.subject_name}</span> for{" "}
              <span className="font-semibold">
                {deletingSubject?.class_name}
                {deletingSubject?.section_name && ` - ${deletingSubject.section_name}`}
              </span>{" "}
              from this exam?
              {deletingSubject && deletingSubject.scores_count > 0 && (
                <span className="block mt-2 text-destructive">
                  Warning: This will also delete {deletingSubject.scores_count} score(s) already entered.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isPending}
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
