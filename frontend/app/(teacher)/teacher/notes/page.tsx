"use client";

/**
 * SIMS Plus - Teacher Notes Page
 *
 * Create and manage notes about students. Notes can be:
 * - positive: praise, achievements
 * - concern: behavioral or academic concerns
 * - information: general observations
 * - action_required: needs follow-up
 *
 * Notes can optionally be shared with parents.
 */

import { useEffect, useState, useTransition } from "react";
import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  Loader2,
  Plus,
  StickyNote,
  Eye,
  EyeOff,
  Check,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  getTeacherNotes,
  createTeacherNote,
  getTeacherClasses,
  getTeacherClassStudents,
} from "@/actions/teacher.action";
import type {
  TeacherNoteItem,
  TeacherNoteType,
  TeacherClassSummary,
  TeacherStudentSummary,
} from "@/types/teacher.type";
import { getInitials } from "@/lib/format";
import { NOTE_TYPE_COLORS, NOTE_TYPE_LABELS } from "@/lib/teacher-constants";
import { toast } from "sonner";

export default function TeacherNotesPage() {
  const searchParams = useSearchParams();
  const preselectedStudentId = searchParams.get("student_id") || undefined;

  const [notes, setNotes] = useState<TeacherNoteItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(!!preselectedStudentId);

  // New note form
  const [classes, setClasses] = useState<TeacherClassSummary[]>([]);
  const [selectedClassId, setSelectedClassId] = useState("");
  const [students, setStudents] = useState<TeacherStudentSummary[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [selectedStudentId, setSelectedStudentId] = useState(preselectedStudentId || "");
  const [noteType, setNoteType] = useState<TeacherNoteType>("information");
  const [content, setContent] = useState("");
  const [visibleToParent, setVisibleToParent] = useState(false);
  const [isPending, startTransition] = useTransition();

  // Load notes -- backend returns { notes, total } with limit/offset pagination
  useEffect(() => {
    async function load() {
      const result = await getTeacherNotes(page);
      if (result.success) {
        setNotes(result.data.notes);
        setTotalCount(result.data.total);
      } else {
        setError(result.error);
      }
      setLoading(false);
    }
    load();
  }, [page]);

  // Load classes for student selection
  useEffect(() => {
    async function loadClasses() {
      const result = await getTeacherClasses();
      if (result.success) {
        setClasses(result.data);
      }
    }
    loadClasses();
  }, []);

  // Load students when a class is selected (separate endpoint from class detail)
  useEffect(() => {
    if (!selectedClassId) {
      setStudents([]);
      return;
    }
    let cancelled = false;
    async function loadStudents() {
      setLoadingStudents(true);
      setSelectedStudentId("");
      const result = await getTeacherClassStudents(selectedClassId);
      if (!cancelled && result.success) {
        setStudents(result.data.students);
      }
      if (!cancelled) setLoadingStudents(false);
    }
    loadStudents();
    return () => { cancelled = true; };
  }, [selectedClassId]);

  const handleCreateNote = () => {
    if (!selectedStudentId || !content.trim()) {
      toast.error("Please select a student and enter a note");
      return;
    }

    startTransition(async () => {
      const result = await createTeacherNote({
        student_id: selectedStudentId,
        note_type: noteType,
        content: content.trim(),
        is_visible_to_parent: visibleToParent,
      });

      if (result.success) {
        toast.success("Note created");
        // Add to top of list
        setNotes((prev) => [result.data, ...prev]);
        // Reset form
        setSelectedClassId("");
        setSelectedStudentId("");
        setStudents([]);
        setNoteType("information");
        setContent("");
        setVisibleToParent(false);
        setDialogOpen(false);
      } else {
        toast.error(result.error);
      }
    });
  };

  if (loading) {
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Student Notes</h1>
          <p className="text-muted-foreground">
            Create and manage notes about your students
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-1" />
              New Note
            </Button>
          </DialogTrigger>
          <DialogContent className="max-sm:max-w-[calc(100vw-2rem)]">
            <DialogHeader>
              <DialogTitle>Create Student Note</DialogTitle>
              <DialogDescription>
                Add a note about a student. Optionally share with parents.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              {/* Two-step student selection: pick class, then pick student */}
              <div className="space-y-2">
                <Label>Class</Label>
                <Select
                  value={selectedClassId}
                  onValueChange={setSelectedClassId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a class" />
                  </SelectTrigger>
                  <SelectContent>
                    {classes.map((cls) => (
                      <SelectItem key={`${cls.class_id}-${cls.section_id || "main"}`} value={cls.class_id}>
                        {cls.class_name}
                        {cls.section_name ? ` - ${cls.section_name}` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Student</Label>
                <Select
                  value={selectedStudentId}
                  onValueChange={setSelectedStudentId}
                  disabled={!selectedClassId || loadingStudents}
                >
                  <SelectTrigger>
                    {loadingStudents ? (
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Loading students...
                      </span>
                    ) : (
                      <SelectValue placeholder={selectedClassId ? "Select a student" : "Select a class first"} />
                    )}
                  </SelectTrigger>
                  <SelectContent>
                    {students.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.first_name} {s.last_name} ({s.student_id})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Note Type</Label>
                <Select
                  value={noteType}
                  onValueChange={(v) => setNoteType(v as TeacherNoteType)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(NOTE_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Content</Label>
                <Textarea
                  placeholder="Write your note here..."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={4}
                />
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={visibleToParent}
                  onCheckedChange={setVisibleToParent}
                  id="visible-to-parent"
                />
                <Label htmlFor="visible-to-parent" className="text-sm">
                  Visible to parents
                </Label>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setDialogOpen(false)}
                disabled={isPending}
              >
                Cancel
              </Button>
              <Button onClick={handleCreateNote} disabled={isPending}>
                {isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Create Note"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Notes list */}
      {notes.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <StickyNote className="h-12 w-12 text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">No notes created yet</p>
            <p className="text-xs text-muted-foreground mt-1">
              Click &quot;New Note&quot; to get started
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {notes.map((note) => (
            <Card key={note.id}>
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <Avatar className="h-9 w-9 shrink-0 mt-0.5">
                    <AvatarFallback className="bg-primary/10 text-primary text-xs">
                      {getInitials(note.student_name || "?")}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{note.student_name || "Unknown"}</span>
                      <Badge
                        className={`text-[10px] ${NOTE_TYPE_COLORS[note.note_type as TeacherNoteType] || "bg-gray-100 text-gray-800"}`}
                      >
                        {NOTE_TYPE_LABELS[note.note_type as TeacherNoteType] || note.note_type}
                      </Badge>
                      {note.is_visible_to_parent ? (
                        <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                          <Eye className="h-3 w-3" /> Shared
                        </span>
                      ) : (
                        <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                          <EyeOff className="h-3 w-3" /> Private
                        </span>
                      )}
                    </div>
                    <p className="text-sm mt-1.5">{note.content}</p>
                    <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
                      <span>{new Date(note.created_at).toLocaleDateString("en-GB")}</span>
                      {note.subject_name && <span>{note.subject_name}</span>}
                      {note.parent_acknowledged && (
                        <span className="flex items-center gap-0.5 text-green-600">
                          <Check className="h-3 w-3" /> Acknowledged
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="flex items-center text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
