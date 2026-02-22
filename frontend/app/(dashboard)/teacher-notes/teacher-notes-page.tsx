"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import {
  Plus,
  Loader2,
  StickyNote,
  MoreHorizontal,
  Pencil,
  Trash2,
  Eye,
  EyeOff,
  CheckCircle2,
  ChevronsUpDown,
  Check,
  Search,
} from "lucide-react";

import {
  getTeacherNotes,
  createTeacherNote,
  updateTeacherNote,
  deleteTeacherNote,
} from "@/actions/teacher-note.action";
import { getStudents } from "@/actions/students.action";
import { getSubjects } from "@/actions/academic.action";
import type { TeacherNote, NoteType } from "@/types/parent.type";
import type { StudentListItem, Subject } from "@/types";
import { useToast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

// -------------------------------------------------------------------
// Constants
// -------------------------------------------------------------------

const NOTE_TYPES: { value: NoteType; label: string }[] = [
  { value: "positive", label: "Positive" },
  { value: "concern", label: "Concern" },
  { value: "information", label: "Information" },
  { value: "action_required", label: "Action Required" },
];

// -------------------------------------------------------------------
// Badge helpers
// -------------------------------------------------------------------

function getNoteTypeBadge(noteType: NoteType | string) {
  switch (noteType) {
    case "positive":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Positive
        </Badge>
      );
    case "concern":
      return (
        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
          Concern
        </Badge>
      );
    case "information":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Information
        </Badge>
      );
    case "action_required":
      return <Badge variant="destructive">Action Required</Badge>;
    default:
      return <Badge variant="secondary">{noteType}</Badge>;
  }
}

// -------------------------------------------------------------------
// Zod schemas
// -------------------------------------------------------------------

const teacherNoteFormSchema = z.object({
  student_id: z.string().min(1, "Please select a student"),
  subject_id: z.string().optional(),
  note_type: z.enum(["positive", "concern", "information", "action_required"], {
    message: "Please select a note type",
  }),
  content: z
    .string()
    .min(1, "Content is required")
    .max(3000, "Content must be under 3000 characters"),
  is_visible_to_parent: z.boolean().optional(),
});

type TeacherNoteFormData = z.infer<typeof teacherNoteFormSchema>;

// -------------------------------------------------------------------
// Main component
// -------------------------------------------------------------------

export function TeacherNotesPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  // List state
  const [notes, setNotes] = useState<TeacherNote[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [noteTypeFilter, setNoteTypeFilter] = useState<string>("");

  // Dialog state
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingNote, setEditingNote] = useState<TeacherNote | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TeacherNote | null>(null);

  // Lookup data
  const [students, setStudents] = useState<StudentListItem[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [studentSearchOpen, setStudentSearchOpen] = useState(false);
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);

  // Submitting state
  const [isSubmitting, setIsSubmitting] = useState(false);

  // -------------------------------------------------------------------
  // Form setup
  // -------------------------------------------------------------------

  const form = useForm<TeacherNoteFormData>({
    resolver: zodResolver(teacherNoteFormSchema),
    defaultValues: {
      student_id: "",
      subject_id: "",
      note_type: "information",
      content: "",
      is_visible_to_parent: true,
    },
  });

  // -------------------------------------------------------------------
  // Data loading
  // -------------------------------------------------------------------

  const loadNotes = useCallback(() => {
    startTransition(async () => {
      const result = await getTeacherNotes({
        search: searchQuery || undefined,
        noteType: noteTypeFilter || undefined,
        page,
        pageSize: 20,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        const pages = Array.isArray(data) ? 1 : (data.total_pages ?? 1);
        setNotes(items);
        setTotal(count);
        setTotalPages(pages);
      }
    });
  }, [searchQuery, noteTypeFilter, page]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  const loadStudents = useCallback(async () => {
    if (students.length > 0) return;
    setIsLoadingStudents(true);
    try {
      const result = await getStudents({ status: "active", page_size: 500 });
      if (result.success && result.data) {
        const data = result.data;
        setStudents(Array.isArray(data) ? data : (data.items ?? []));
      }
    } finally {
      setIsLoadingStudents(false);
    }
  }, [students.length]);

  const loadSubjects = useCallback(async () => {
    if (subjects.length > 0) return;
    try {
      const result = await getSubjects();
      if (result.success && result.data) {
        setSubjects(Array.isArray(result.data) ? result.data : []);
      }
    } catch {
      // Non-critical, subjects are optional
    }
  }, [subjects.length]);

  // -------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------

  const handleOpenCreate = () => {
    setEditingNote(null);
    form.reset({
      student_id: "",
      subject_id: "",
      note_type: "information",
      content: "",
      is_visible_to_parent: true,
    });
    loadStudents();
    loadSubjects();
    setIsFormOpen(true);
  };

  const handleOpenEdit = (note: TeacherNote) => {
    setEditingNote(note);
    form.reset({
      student_id: note.student_id,
      subject_id: note.subject_id || "",
      note_type: note.note_type,
      content: note.content,
      is_visible_to_parent: note.is_visible_to_parent,
    });
    loadStudents();
    loadSubjects();
    setIsFormOpen(true);
  };

  const handleSubmit = async (data: TeacherNoteFormData) => {
    setIsSubmitting(true);
    try {
      if (editingNote) {
        const result = await updateTeacherNote(editingNote.id, {
          subject_id: data.subject_id || undefined,
          note_type: data.note_type,
          content: data.content,
          is_visible_to_parent: data.is_visible_to_parent,
        });
        if (result.success) {
          toast({ title: "Note updated" });
          setIsFormOpen(false);
          setEditingNote(null);
          form.reset();
          loadNotes();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createTeacherNote({
          student_id: data.student_id,
          subject_id: data.subject_id || undefined,
          note_type: data.note_type,
          content: data.content,
          is_visible_to_parent: data.is_visible_to_parent,
        });
        if (result.success) {
          toast({ title: "Note created" });
          setIsFormOpen(false);
          form.reset();
          loadNotes();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsSubmitting(true);
    try {
      const result = await deleteTeacherNote(deleteTarget.id);
      if (result.success) {
        toast({ title: "Note deleted" });
        loadNotes();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteTarget(null);
    }
  };

  // -------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------

  const getSelectedStudentName = (studentId: string): string => {
    const student = students.find((s) => s.id === studentId);
    return student ? `${student.first_name} ${student.last_name}` : "";
  };

  const activeFilterCount = noteTypeFilter ? 1 : 0;

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setPage(1);
  };

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Teacher Notes</h1>
          <p className="text-muted-foreground">
            Create and manage notes about students
          </p>
        </div>
        <Button onClick={handleOpenCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Create Note
        </Button>
      </div>

      {/* Search and filters */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative w-full md:w-[300px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by student or content..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>
        <CollapsibleFilters activeFilterCount={activeFilterCount}>
          <Select
            value={noteTypeFilter}
            onValueChange={(v) => {
              setNoteTypeFilter(v === "all" ? "" : v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Note Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {NOTE_TYPES.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CollapsibleFilters>
      </div>

      {/* Data table */}
      <Card>
        <CardHeader>
          <CardTitle>Notes</CardTitle>
          <CardDescription>
            {total} note{total !== 1 ? "s" : ""} found
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : notes.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Student</TableHead>
                      <TableHead className="hidden sm:table-cell">Subject</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead className="hidden md:table-cell">Content</TableHead>
                      <TableHead className="text-center">Visible</TableHead>
                      <TableHead className="hidden sm:table-cell text-center">Acknowledged</TableHead>
                      <TableHead className="hidden lg:table-cell">Created</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {notes.map((note) => (
                      <TableRow key={note.id}>
                        <TableCell className="font-medium whitespace-nowrap">
                          {note.student_name}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          {note.subject_name || "--"}
                        </TableCell>
                        <TableCell>{getNoteTypeBadge(note.note_type)}</TableCell>
                        <TableCell className="hidden max-w-[250px] truncate md:table-cell">
                          {note.content}
                        </TableCell>
                        <TableCell className="text-center">
                          {note.is_visible_to_parent ? (
                            <Eye className="mx-auto h-4 w-4 text-green-600" aria-label="Visible to parent" />
                          ) : (
                            <EyeOff className="mx-auto h-4 w-4 text-muted-foreground" aria-label="Hidden from parent" />
                          )}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-center">
                          {note.parent_acknowledged ? (
                            <CheckCircle2 className="mx-auto h-4 w-4 text-green-600" aria-label="Acknowledged" />
                          ) : (
                            <span className="text-sm text-muted-foreground">--</span>
                          )}
                        </TableCell>
                        <TableCell className="hidden whitespace-nowrap lg:table-cell">
                          {formatDate(note.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                aria-label="Row actions"
                              >
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleOpenEdit(note)}>
                                <Pencil className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                className="text-destructive focus:text-destructive"
                                onClick={() => setDeleteTarget(note)}
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between border-t pt-4 mt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {totalPages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <StickyNote className="h-12 w-12" />
              <p className="font-medium">No notes found</p>
              <p className="text-sm">
                {searchQuery || noteTypeFilter
                  ? "Try adjusting your search or filters."
                  : "Create a note to record observations about students."}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ============================================================= */}
      {/* Create / Edit Dialog                                           */}
      {/* ============================================================= */}
      <Dialog
        open={isFormOpen}
        onOpenChange={(open) => {
          if (!open) {
            form.reset();
            setEditingNote(null);
          }
          setIsFormOpen(open);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>
              {editingNote ? "Edit Note" : "Create Note"}
            </DialogTitle>
            <DialogDescription>
              {editingNote
                ? "Update the note details below."
                : "Record an observation or note about a student."}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
              {/* Student select (searchable combobox) */}
              <FormField
                control={form.control}
                name="student_id"
                render={({ field }) => (
                  <FormItem className="flex flex-col">
                    <FormLabel>Student *</FormLabel>
                    <Popover
                      open={studentSearchOpen}
                      onOpenChange={setStudentSearchOpen}
                    >
                      <PopoverTrigger asChild>
                        <FormControl>
                          <Button
                            variant="outline"
                            role="combobox"
                            aria-expanded={studentSearchOpen}
                            disabled={!!editingNote}
                            className={cn(
                              "w-full justify-between",
                              !field.value && "text-muted-foreground"
                            )}
                          >
                            {field.value
                              ? getSelectedStudentName(field.value) || "Student selected"
                              : "Search students..."}
                            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                          </Button>
                        </FormControl>
                      </PopoverTrigger>
                      <PopoverContent className="w-full p-0" align="start">
                        <Command>
                          <CommandInput placeholder="Type a name to search..." />
                          <CommandList>
                            <CommandEmpty>
                              {isLoadingStudents
                                ? "Loading students..."
                                : "No students found."}
                            </CommandEmpty>
                            <CommandGroup>
                              {students.map((student) => (
                                <CommandItem
                                  key={student.id}
                                  value={`${student.first_name} ${student.last_name}`}
                                  onSelect={() => {
                                    field.onChange(student.id);
                                    setStudentSearchOpen(false);
                                  }}
                                >
                                  <Check
                                    className={cn(
                                      "mr-2 h-4 w-4",
                                      field.value === student.id
                                        ? "opacity-100"
                                        : "opacity-0"
                                    )}
                                  />
                                  <div className="flex flex-col">
                                    <span>
                                      {student.first_name} {student.last_name}
                                    </span>
                                    <span className="text-xs text-muted-foreground">
                                      {student.class_name || "No class"}
                                      {student.section_name
                                        ? ` - ${student.section_name}`
                                        : ""}
                                    </span>
                                  </div>
                                </CommandItem>
                              ))}
                            </CommandGroup>
                          </CommandList>
                        </Command>
                      </PopoverContent>
                    </Popover>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Subject + Note Type row */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="subject_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Subject</FormLabel>
                      <Select
                        onValueChange={(v) => field.onChange(v === "none" ? "" : v)}
                        value={field.value || "none"}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select subject (optional)" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="none">No Subject</SelectItem>
                          {subjects.map((subject) => (
                            <SelectItem key={subject.id} value={subject.id}>
                              {subject.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="note_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Note Type *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {NOTE_TYPES.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Content */}
              <FormField
                control={form.control}
                name="content"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Content *</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Write your observation or note here..."
                        rows={5}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Visible to Parent */}
              <FormField
                control={form.control}
                name="is_visible_to_parent"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>Visible to parent</FormLabel>
                      <FormDescription>
                        If checked, the parent will be able to see this note in their portal.
                      </FormDescription>
                    </div>
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsFormOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingNote ? "Update Note" : "Create Note"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* ============================================================= */}
      {/* Delete Confirmation Dialog                                      */}
      {/* ============================================================= */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Note</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this note about{" "}
              <span className="font-medium">{deleteTarget?.student_name}</span>? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
