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
import { Calendar, Plus, Settings2, Trash2, Loader2 } from "lucide-react";
import {
  getAcademicYears,
  createAcademicYear,
  updateAcademicYear,
  deleteAcademicYear,
} from "@/actions/academic.action";
import type { AcademicYear, AcademicYearCreate, AcademicYearUpdate } from "@/types";

interface AcademicYearsProps {
  initialData?: AcademicYear[];
}

export function AcademicYears({ initialData }: AcademicYearsProps) {
  const [years, setYears] = useState<AcademicYear[]>(initialData || []);
  const [loading, setLoading] = useState(!initialData);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingYear, setEditingYear] = useState<AcademicYear | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [yearToDelete, setYearToDelete] = useState<AcademicYear | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    start_date: "",
    end_date: "",
    is_current: false,
    status: "planning" as "planning" | "active" | "completed",
  });

  useEffect(() => {
    if (!initialData) {
      loadYears();
    }
  }, [initialData]);

  const loadYears = async () => {
    setLoading(true);
    const result = await getAcademicYears();
    if (result.success && result.data) {
      setYears(result.data);
    } else {
      setError(result.error || "Failed to load academic years");
    }
    setLoading(false);
  };

  const resetForm = () => {
    setFormData({
      name: "",
      description: "",
      start_date: "",
      end_date: "",
      is_current: false,
      status: "planning",
    });
    setEditingYear(null);
    setError(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setIsDialogOpen(true);
  };

  const openEditDialog = (year: AcademicYear) => {
    setEditingYear(year);
    setFormData({
      name: year.name,
      description: year.description || "",
      start_date: year.start_date,
      end_date: year.end_date,
      is_current: year.is_current,
      status: year.status as "planning" | "active" | "completed",
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingYear) {
        const updateData: AcademicYearUpdate = {
          name: formData.name,
          description: formData.description || undefined,
          start_date: formData.start_date,
          end_date: formData.end_date,
          is_current: formData.is_current,
          status: formData.status,
        };
        const result = await updateAcademicYear(editingYear.id, updateData);
        if (result.success && result.data) {
          setYears(years.map((y) => (y.id === editingYear.id ? result.data! : y)));
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to update academic year");
        }
      } else {
        const createData: AcademicYearCreate = {
          name: formData.name,
          description: formData.description || undefined,
          start_date: formData.start_date,
          end_date: formData.end_date,
          is_current: formData.is_current,
        };
        const result = await createAcademicYear(createData);
        if (result.success && result.data) {
          setYears([...years, result.data]);
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to create academic year");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteDialog = (year: AcademicYear) => {
    setYearToDelete(year);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!yearToDelete) return;

    setIsDeleting(true);
    const result = await deleteAcademicYear(yearToDelete.id);
    if (result.success) {
      setYears(years.filter((y) => y.id !== yearToDelete.id));
      setDeleteDialogOpen(false);
      setYearToDelete(null);
    } else {
      setError(result.error || "Failed to delete academic year");
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
        return <Badge variant="outline">Planning</Badge>;
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
              <Calendar className="h-5 w-5" />
              Academic Years
            </CardTitle>
            <CardDescription>
              Manage your school&apos;s academic years.
            </CardDescription>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" onClick={openCreateDialog}>
                <Plus className="mr-2 h-4 w-4" />
                New Year
              </Button>
            </DialogTrigger>
            <DialogContent>
              <form onSubmit={handleSubmit}>
                <DialogHeader>
                  <DialogTitle>
                    {editingYear ? "Edit Academic Year" : "Create Academic Year"}
                  </DialogTitle>
                  <DialogDescription>
                    {editingYear
                      ? "Update the academic year details."
                      : "Add a new academic year for your school."}
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  {error && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {error}
                    </div>
                  )}
                  <div className="grid gap-2">
                    <Label htmlFor="name">Name</Label>
                    <Input
                      id="name"
                      placeholder="e.g., 2025/2026"
                      value={formData.name}
                      onChange={(e) =>
                        setFormData({ ...formData, name: e.target.value })
                      }
                      required
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="description">Description (Optional)</Label>
                    <Input
                      id="description"
                      placeholder="Brief description"
                      value={formData.description}
                      onChange={(e) =>
                        setFormData({ ...formData, description: e.target.value })
                      }
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
                  {editingYear && (
                    <div className="grid gap-2">
                      <Label htmlFor="status">Status</Label>
                      <Select
                        value={formData.status}
                        onValueChange={(value) =>
                          setFormData({
                            ...formData,
                            status: value as "planning" | "active" | "completed",
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="planning">Planning</SelectItem>
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
                      Set as current academic year
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
                    {editingYear ? "Update" : "Create"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {years.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            No academic years found. Create your first academic year to get started.
          </div>
        ) : (
          <div className="space-y-3">
            {years.map((year) => (
              <div
                key={year.id}
                className="flex items-center justify-between rounded-lg border p-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{year.name}</p>
                    {getStatusBadge(year.status, year.is_current)}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {formatDate(year.start_date)} - {formatDate(year.end_date)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEditDialog(year)}
                  >
                    <Settings2 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openDeleteDialog(year)}
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

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Academic Year</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the academic year &quot;{yearToDelete?.name}&quot;?
              This action cannot be undone and will remove all associated data.
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
