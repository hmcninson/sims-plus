"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
import { BookOpen, Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import {
  getSubjects,
  createSubject,
  updateSubject,
  deleteSubject,
} from "@/actions/academic.action";
import { SubjectTemplateSelector } from "@/components/academic/SubjectTemplateSelector";
import type { Subject, SubjectCreate, SubjectUpdate, SubjectCategory } from "@/types";

interface SubjectsProps {
  initialData?: Subject[];
  schoolType?: string;
}

export function Subjects({ initialData, schoolType }: SubjectsProps) {
  const [subjects, setSubjects] = useState<Subject[]>(initialData || []);
  const [loading, setLoading] = useState(!initialData);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSubject, setEditingSubject] = useState<Subject | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [subjectToDelete, setSubjectToDelete] = useState<Subject | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    code: "",
    description: "",
    category: "core" as SubjectCategory,
  });

  useEffect(() => {
    if (!initialData) {
      loadSubjects();
    }
  }, [initialData]);

  const loadSubjects = async () => {
    setLoading(true);
    const result = await getSubjects();
    if (result.success && result.data) {
      setSubjects(result.data);
    }
    setLoading(false);
  };

  const resetForm = () => {
    setFormData({
      name: "",
      code: "",
      description: "",
      category: "core",
    });
    setEditingSubject(null);
    setError(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setIsDialogOpen(true);
  };

  const openEditDialog = (subject: Subject) => {
    setEditingSubject(subject);
    setFormData({
      name: subject.name,
      code: subject.code,
      description: subject.description || "",
      category: subject.category as SubjectCategory,
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingSubject) {
        const updateData: SubjectUpdate = {
          name: formData.name,
          code: formData.code,
          description: formData.description || undefined,
          category: formData.category,
        };
        const result = await updateSubject(editingSubject.id, updateData);
        if (result.success && result.data) {
          setSubjects(subjects.map((s) => (s.id === editingSubject.id ? result.data! : s)));
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to update subject");
        }
      } else {
        const createData: SubjectCreate = {
          name: formData.name,
          code: formData.code,
          description: formData.description || undefined,
          category: formData.category,
        };
        const result = await createSubject(createData);
        if (result.success && result.data) {
          setSubjects([...subjects, result.data]);
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to create subject");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteDialog = (subject: Subject) => {
    setSubjectToDelete(subject);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!subjectToDelete) return;

    setIsDeleting(true);
    const result = await deleteSubject(subjectToDelete.id);
    if (result.success) {
      setSubjects(subjects.filter((s) => s.id !== subjectToDelete.id));
      setDeleteDialogOpen(false);
      setSubjectToDelete(null);
    } else {
      setError(result.error || "Failed to delete subject");
    }
    setIsDeleting(false);
  };

  const getCategoryBadge = (category: string) => {
    switch (category) {
      case "core":
        return <Badge variant="default">Core</Badge>;
      case "elective":
        return <Badge variant="secondary">Elective</Badge>;
      case "vocational":
        return <Badge variant="outline">Vocational</Badge>;
      case "extra":
        return <Badge variant="outline">Extra-Curricular</Badge>;
      default:
        return <Badge variant="outline">{category}</Badge>;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      {schoolType && subjects.length < 5 && (
        <SubjectTemplateSelector
          schoolType={schoolType}
          onComplete={() => loadSubjects()}
        />
      )}
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5" />
              Subjects
            </CardTitle>
            <CardDescription>
              Manage subjects taught at your school.
            </CardDescription>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" onClick={openCreateDialog}>
                <Plus className="mr-2 h-4 w-4" />
                New Subject
              </Button>
            </DialogTrigger>
            <DialogContent>
              <form onSubmit={handleSubmit}>
                <DialogHeader>
                  <DialogTitle>
                    {editingSubject ? "Edit Subject" : "Create Subject"}
                  </DialogTitle>
                  <DialogDescription>
                    {editingSubject
                      ? "Update the subject details."
                      : "Add a new subject to your school's curriculum."}
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  {error && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {error}
                    </div>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="name">Name</Label>
                      <Input
                        id="name"
                        placeholder="e.g., Mathematics"
                        value={formData.name}
                        onChange={(e) =>
                          setFormData({ ...formData, name: e.target.value })
                        }
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="code">Code</Label>
                      <Input
                        id="code"
                        placeholder="e.g., MATH"
                        value={formData.code}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            code: e.target.value.toUpperCase(),
                          })
                        }
                        required
                      />
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="category">Category</Label>
                    <Select
                      value={formData.category}
                      onValueChange={(value) =>
                        setFormData({
                          ...formData,
                          category: value as SubjectCategory,
                        })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="core">Core Subject</SelectItem>
                        <SelectItem value="elective">Elective</SelectItem>
                        <SelectItem value="vocational">Vocational</SelectItem>
                        <SelectItem value="extra">Extra-Curricular</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="description">Description (Optional)</Label>
                    <Input
                      id="description"
                      placeholder="Brief description of the subject"
                      value={formData.description}
                      onChange={(e) =>
                        setFormData({ ...formData, description: e.target.value })
                      }
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={submitting}>
                    {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {editingSubject ? "Update" : "Create"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {subjects.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            No subjects found. Add subjects to your school&apos;s curriculum.
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subjects
                  .sort((a, b) => a.code.localeCompare(b.code))
                  .map((subject) => (
                    <TableRow key={subject.id}>
                      <TableCell className="font-mono font-medium">
                        {subject.code}
                      </TableCell>
                      <TableCell>{subject.name}</TableCell>
                      <TableCell>{getCategoryBadge(subject.category)}</TableCell>
                      <TableCell>
                        {subject.is_active ? (
                          <Badge variant="default" className="bg-green-600">
                            Active
                          </Badge>
                        ) : (
                          <Badge variant="secondary">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(subject)}
                          >
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDeleteDialog(subject)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>

      {/* Delete Subject Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Subject</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{subjectToDelete?.name}&quot; ({subjectToDelete?.code})?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
    </>
  );
}
