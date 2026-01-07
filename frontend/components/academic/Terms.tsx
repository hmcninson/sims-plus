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
import { BookOpen, Plus, Settings2, Trash2, Loader2 } from "lucide-react";
import {
  getTerms,
  createTerm,
  updateTerm,
  deleteTerm,
  getAcademicYears,
} from "@/actions/academic.action";
import type { Term, TermCreate, TermUpdate, AcademicYear } from "@/types";

interface TermsProps {
  academicYearId?: string;
  initialData?: Term[];
}

export function Terms({ academicYearId, initialData }: TermsProps) {
  const [terms, setTerms] = useState<Term[]>(initialData || []);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [loading, setLoading] = useState(!initialData);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingTerm, setEditingTerm] = useState<Term | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [termToDelete, setTermToDelete] = useState<Term | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    academic_year_id: academicYearId || "",
    name: "",
    short_name: "",
    sequence: 1,
    start_date: "",
    end_date: "",
    status: "upcoming" as "upcoming" | "active" | "completed",
    is_current: false,
  });

  useEffect(() => {
    loadData();
  }, [academicYearId]);

  const loadData = async () => {
    setLoading(true);
    const [termsResult, yearsResult] = await Promise.all([
      getTerms(academicYearId),
      getAcademicYears(),
    ]);

    if (termsResult.success && termsResult.data) {
      setTerms(termsResult.data);
    }
    if (yearsResult.success && yearsResult.data) {
      setAcademicYears(yearsResult.data);
    }
    setLoading(false);
  };

  const resetForm = () => {
    setFormData({
      academic_year_id: academicYearId || "",
      name: "",
      short_name: "",
      sequence: terms.length + 1,
      start_date: "",
      end_date: "",
      status: "upcoming",
      is_current: false,
    });
    setEditingTerm(null);
    setError(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setIsDialogOpen(true);
  };

  const openEditDialog = (term: Term) => {
    setEditingTerm(term);
    setFormData({
      academic_year_id: term.academic_year_id,
      name: term.name,
      short_name: term.short_name || "",
      sequence: term.sequence,
      start_date: term.start_date,
      end_date: term.end_date,
      status: term.status as "upcoming" | "active" | "completed",
      is_current: term.is_current,
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingTerm) {
        const updateData: TermUpdate = {
          name: formData.name,
          short_name: formData.short_name || undefined,
          sequence: formData.sequence,
          start_date: formData.start_date,
          end_date: formData.end_date,
          status: formData.status,
          is_current: formData.is_current,
        };
        const result = await updateTerm(editingTerm.id, updateData);
        if (result.success && result.data) {
          setTerms(terms.map((t) => (t.id === editingTerm.id ? result.data! : t)));
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to update term");
        }
      } else {
        const createData: TermCreate = {
          academic_year_id: formData.academic_year_id,
          name: formData.name,
          short_name: formData.short_name || undefined,
          sequence: formData.sequence,
          start_date: formData.start_date,
          end_date: formData.end_date,
        };
        const result = await createTerm(createData);
        if (result.success && result.data) {
          setTerms([...terms, result.data]);
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to create term");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteDialog = (term: Term) => {
    setTermToDelete(term);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!termToDelete) return;

    setIsDeleting(true);
    const result = await deleteTerm(termToDelete.id);
    if (result.success) {
      setTerms(terms.filter((t) => t.id !== termToDelete.id));
      setDeleteDialogOpen(false);
      setTermToDelete(null);
    } else {
      setError(result.error || "Failed to delete term");
    }
    setIsDeleting(false);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      month: "short",
      year: "numeric",
    });
  };

  const getStatusBadge = (status: string, isCurrent: boolean) => {
    if (isCurrent) {
      return <Badge variant="default">Current</Badge>;
    }
    switch (status) {
      case "active":
        return <Badge variant="default">Active</Badge>;
      case "completed":
        return <Badge variant="secondary">Completed</Badge>;
      default:
        return <Badge variant="outline">Upcoming</Badge>;
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
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5" />
              Terms / Semesters
            </CardTitle>
            <CardDescription>
              Configure terms for the academic year.
            </CardDescription>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline" onClick={openCreateDialog}>
                <Plus className="mr-2 h-4 w-4" />
                Add Term
              </Button>
            </DialogTrigger>
            <DialogContent>
              <form onSubmit={handleSubmit}>
                <DialogHeader>
                  <DialogTitle>
                    {editingTerm ? "Edit Term" : "Create Term"}
                  </DialogTitle>
                  <DialogDescription>
                    {editingTerm
                      ? "Update the term details."
                      : "Add a new term to the academic year."}
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  {error && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {error}
                    </div>
                  )}
                  {!academicYearId && (
                    <div className="grid gap-2">
                      <Label htmlFor="academic_year_id">Academic Year</Label>
                      <Select
                        value={formData.academic_year_id}
                        onValueChange={(value) =>
                          setFormData({ ...formData, academic_year_id: value })
                        }
                        required
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select academic year" />
                        </SelectTrigger>
                        <SelectContent>
                          {academicYears.map((year) => (
                            <SelectItem key={year.id} value={year.id}>
                              {year.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="name">Name</Label>
                      <Input
                        id="name"
                        placeholder="e.g., First Term"
                        value={formData.name}
                        onChange={(e) =>
                          setFormData({ ...formData, name: e.target.value })
                        }
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="short_name">Short Name</Label>
                      <Input
                        id="short_name"
                        placeholder="e.g., Term 1"
                        value={formData.short_name}
                        onChange={(e) =>
                          setFormData({ ...formData, short_name: e.target.value })
                        }
                      />
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="sequence">Sequence</Label>
                    <Input
                      id="sequence"
                      type="number"
                      min={1}
                      max={4}
                      value={formData.sequence}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          sequence: parseInt(e.target.value) || 1,
                        })
                      }
                      required
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="start_date">Start Date</Label>
                      <Input
                        id="start_date"
                        type="date"
                        value={formData.start_date}
                        onChange={(e) =>
                          setFormData({ ...formData, start_date: e.target.value })
                        }
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="end_date">End Date</Label>
                      <Input
                        id="end_date"
                        type="date"
                        value={formData.end_date}
                        onChange={(e) =>
                          setFormData({ ...formData, end_date: e.target.value })
                        }
                        required
                      />
                    </div>
                  </div>
                  {editingTerm && (
                    <div className="grid gap-2">
                      <Label htmlFor="status">Status</Label>
                      <Select
                        value={formData.status}
                        onValueChange={(value) =>
                          setFormData({
                            ...formData,
                            status: value as "upcoming" | "active" | "completed",
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="upcoming">Upcoming</SelectItem>
                          <SelectItem value="active">Active</SelectItem>
                          <SelectItem value="completed">Completed</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_current"
                      checked={formData.is_current}
                      onChange={(e) =>
                        setFormData({ ...formData, is_current: e.target.checked })
                      }
                      className="h-4 w-4"
                    />
                    <Label htmlFor="is_current" className="text-sm font-normal">
                      Set as current term
                    </Label>
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
                    {editingTerm ? "Update" : "Create"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {terms.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            No terms found. Add terms to organize your academic year.
          </div>
        ) : (
          <div className="space-y-3">
            {terms
              .sort((a, b) => a.sequence - b.sequence)
              .map((term) => (
                <div
                  key={term.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium">{term.name}</p>
                      {getStatusBadge(term.status, term.is_current)}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {formatDate(term.start_date)} - {formatDate(term.end_date)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(term)}
                    >
                      <Settings2 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openDeleteDialog(term)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
          </div>
        )}
      </CardContent>

      {/* Delete Term Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Term</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{termToDelete?.name}&quot;?
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
  );
}
