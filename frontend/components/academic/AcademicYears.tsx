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
import { Checkbox } from "@/components/ui/checkbox";
import { Calendar, Plus, Settings2, Trash2, Loader2, Archive } from "lucide-react";
import { toast } from "sonner";
import {
  getAcademicYears,
  createAcademicYear,
  updateAcademicYear,
  deleteAcademicYear,
  archiveAcademicYear,
} from "@/actions/academic.action";
import type { AcademicYear, AcademicYearCreate, AcademicYearUpdate } from "@/types";

interface AcademicYearsProps {
  initialData?: AcademicYear[];
  /** Pre-fetched academic years from the parent page to avoid duplicate API calls */
  initialAcademicYears?: AcademicYear[];
  /** Callback to notify parent when the years list changes (create/update/delete) */
  onYearsChange?: (years: AcademicYear[]) => void;
}

export function AcademicYears({ initialData, initialAcademicYears, onYearsChange }: AcademicYearsProps) {
  // Prefer parent-provided data over component-level initialData
  const providedData = initialAcademicYears ?? initialData;
  const [years, setYears] = useState<AcademicYear[]>(providedData || []);
  const [loading, setLoading] = useState(!providedData);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingYear, setEditingYear] = useState<AcademicYear | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [yearToDelete, setYearToDelete] = useState<AcademicYear | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);
  const [archiveDialogOpen, setArchiveDialogOpen] = useState(false);
  const [yearToArchive, setYearToArchive] = useState<AcademicYear | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    start_date: "",
    end_date: "",
    is_current: false,
    status: "planning" as "planning" | "active" | "completed" | "archived",
  });

  // Sync from parent when initialAcademicYears changes (e.g., after parent re-fetches)
  useEffect(() => {
    if (initialAcademicYears) {
      setYears(initialAcademicYears);
      setLoading(false);
    }
  }, [initialAcademicYears]);

  useEffect(() => {
    if (!providedData) {
      loadYears();
    }
  }, [providedData]);

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
      status: year.status as "planning" | "active" | "completed" | "archived",
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
          const updatedYears = years.map((y) => (y.id === editingYear.id ? result.data! : y));
          setYears(updatedYears);
          onYearsChange?.(updatedYears);
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
          const updatedYears = [...years, result.data];
          setYears(updatedYears);
          onYearsChange?.(updatedYears);
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
      const updatedYears = years.filter((y) => y.id !== yearToDelete.id);
      setYears(updatedYears);
      onYearsChange?.(updatedYears);
      setDeleteDialogOpen(false);
      setYearToDelete(null);
    } else {
      setError(result.error || "Failed to delete academic year");
    }
    setIsDeleting(false);
  };

  const openArchiveDialog = (year: AcademicYear) => {
    setYearToArchive(year);
    setArchiveDialogOpen(true);
  };

  const handleArchive = async () => {
    if (!yearToArchive) return;

    setIsArchiving(true);
    const result = await archiveAcademicYear(yearToArchive.id);
    if (result.success && result.data) {
      const updatedYears = years.map((y) =>
        y.id === yearToArchive.id ? result.data! : y,
      );
      setYears(updatedYears);
      onYearsChange?.(updatedYears);
      toast.success("Academic year archived", {
        description: `"${yearToArchive.name}" has been archived successfully.`,
      });
      setArchiveDialogOpen(false);
      setYearToArchive(null);
    } else {
      toast.error("Failed to archive", {
        description: result.error || "An error occurred while archiving.",
      });
    }
    setIsArchiving(false);
  };

  const filteredYears = years.filter((y) =>
    showArchived ? true : y.status !== "archived",
  );

  const archivedCount = years.filter((y) => y.status === "archived").length;

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
      case "archived":
        return <Badge variant="outline" className="text-amber-700 border-amber-300 bg-amber-50 dark:text-amber-400 dark:border-amber-700 dark:bg-amber-950">Archived</Badge>;
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
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
        {archivedCount > 0 && (
          <div className="flex items-center gap-2 mb-4">
            <Checkbox
              id="show-archived"
              checked={showArchived}
              onCheckedChange={(v) => setShowArchived(!!v)}
            />
            <label
              htmlFor="show-archived"
              className="text-sm text-muted-foreground cursor-pointer select-none"
            >
              Show archived years ({archivedCount})
            </label>
          </div>
        )}

        {filteredYears.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            {years.length === 0
              ? "No academic years found. Create your first academic year to get started."
              : "No academic years to display. Toggle \"Show archived years\" to see archived entries."}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredYears.map((year) => (
              <div
                key={year.id}
                className={`flex items-center justify-between rounded-lg border p-4 ${
                  year.status === "archived" ? "opacity-60" : ""
                }`}
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
                  {year.status === "archived" ? (
                    <span className="text-xs text-muted-foreground px-2">Read-only</span>
                  ) : (
                    <>
                      {year.status === "completed" && !year.is_current && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openArchiveDialog(year)}
                          title="Archive this academic year"
                        >
                          <Archive className="mr-1 h-4 w-4" />
                          Archive
                        </Button>
                      )}
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
                    </>
                  )}
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

      {/* Archive Confirmation Dialog */}
      <AlertDialog open={archiveDialogOpen} onOpenChange={setArchiveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive Academic Year</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to archive &quot;{yearToArchive?.name}&quot;?
              Once archived, all records for this academic year will become read-only.
              This includes terms, exams, scores, and attendance data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isArchiving}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleArchive}
              disabled={isArchiving}
            >
              {isArchiving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Archiving...
                </>
              ) : (
                <>
                  <Archive className="mr-2 h-4 w-4" />
                  Archive
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
